import json
import io
import base64
import sys
import tempfile
import types
import unittest
import urllib.parse
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

import server


class AppTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = server.DB_PATH
        server.DB_PATH = Path(self.temp.name) / "test.db"
        server.init_db()

    def tearDown(self):
        server.DB_PATH = self.old_db
        self.temp.cleanup()

    def request(self, method, path, body=None, headers=None):
        data = json.dumps(body).encode() if body is not None else None
        handler = object.__new__(server.Handler)
        handler.path = path
        handler.headers = {"Content-Length": str(len(data or b"")), **(headers or {})}
        handler.rfile = io.BytesIO(data or b"")
        handler.wfile = io.BytesIO()
        handler.send_response = lambda code: setattr(handler, "response_code", code)
        handler.send_header = lambda *args: None
        handler.end_headers = lambda: None
        getattr(handler, "do_" + method)()
        raw = handler.wfile.getvalue()
        return handler.response_code, json.loads(raw) if raw else None

    def test_private_demo_requires_credentials_and_rejects_cross_site_writes(self):
        with patch.object(server, "AUTH_USER", "team"), patch.object(server, "AUTH_PASSWORD", "secret"):
            code, _ = self.request("GET", "/api/services/training/leads")
            self.assertEqual(code, 401)
            token = base64.b64encode(b"team:wrong").decode()
            code, _ = self.request("GET", "/api/services/training/leads", headers={"Authorization": f"Basic {token}"})
            self.assertEqual(code, 401)
            token = base64.b64encode(b"team:secret").decode()
            headers = {"Authorization": f"Basic {token}", "Host": "example.onrender.com"}
            code, leads = self.request("GET", "/api/services/training/leads", headers=headers)
            self.assertEqual((code, leads), (200, []))
            code, _ = self.request("POST", "/api/services/training/discover", headers={**headers, "Origin": "https://evil.example"})
            self.assertEqual(code, 403)

    def test_host_probe_can_check_root_without_credentials(self):
        with patch.object(server, "AUTH_USER", "team"), patch.object(server, "AUTH_PASSWORD", "secret"):
            code, body = self.request("HEAD", "/")
            self.assertEqual((code, body), (200, None))
            code, body = self.request("HEAD", "/api/services/training/leads")
            self.assertEqual((code, body), (404, None))

    def test_explicit_public_mode_opens_app_without_browser_login(self):
        with patch.object(server, "PUBLIC_NO_AUTH", True), patch.object(server, "AUTH_USER", "team"), patch.object(server, "AUTH_PASSWORD", "secret"):
            code, icp = self.request("GET", "/api/services/training/icp")
            self.assertEqual(code, 200)
            self.assertEqual(icp["service"], "training")

    def test_service_separation_and_manual_interest(self):
        source = [{
            "source_id": "node/123", "company": "Example Architects", "category": "architect",
            "city": "Dubai", "country": "AE", "email": "hello@example.com", "phone": None,
            "website": "https://example.com", "source_url": "https://www.openstreetmap.org/node/123",
        }]
        code, icp = self.request("PUT", "/api/services/training/icp", {
            "name": "Training prospects", "countries": ["India"], "categories": ["architecture"],
            "employee_min": "20", "employee_max": "500", "titles": "BIM Manager, Director",
            "keywords": "Revit", "exclusions": "Residential only", "goal": "Book a meeting",
            "notes": "Training target",
        })
        self.assertEqual(code, 200)
        self.assertEqual(icp["countries"], ["India"])
        self.assertEqual(icp["employee_min"], "20")
        self.assertEqual(icp["titles"], "BIM Manager, Director")
        _, bim_icp = self.request("GET", "/api/services/bim/icp")
        self.assertEqual(len(bim_icp["countries"]), 5)
        with patch.object(server, "find_companies", return_value={"companies": source, "coverage": [{"country": "AE", "city": "Dubai", "found": 1}]}):
            code, result = self.request("POST", "/api/services/training/discover")
            self.assertEqual((code, result["added"]), (200, 1))
            _, repeat = self.request("POST", "/api/services/training/discover")
            self.assertEqual(repeat["added"], 0)
        _, leads = self.request("GET", "/api/services/training/leads")
        self.assertEqual(len(leads), 1)
        self.assertEqual(leads[0]["status"], "new")
        _, bim_leads = self.request("GET", "/api/services/bim/leads")
        self.assertEqual(bim_leads, [])
        code, lead = self.request("PATCH", f'/api/services/training/leads/{leads[0]["id"]}/status', {
            "status": "interested", "notes": "Requested a training proposal",
        })
        self.assertEqual(code, 200)
        self.assertEqual(lead["status"], "interested")
        self.assertEqual(lead["notes"], "Requested a training proposal")

    def test_invalid_icp_and_status_are_rejected(self):
        code, _ = self.request("PUT", "/api/services/bim/icp", {
            "name": "BIM", "countries": ["India"], "categories": ["unknown_industry"], "notes": "",
        })
        self.assertEqual(code, 400)
        code, _ = self.request("PATCH", "/api/services/bim/leads/99/status", {"status": "interested_by_ai"})
        self.assertEqual(code, 400)

    def test_map_results_only_use_supplied_public_fields(self):
        sample = {"elements": [
            {"type": "node", "id": 1, "tags": {"name": "Example BIM", "office": "architect", "contact:email": "office@example.com"}},
            {"type": "way", "id": 2, "tags": {"name": "No Contact Ltd", "office": "architect"}},
        ]}
        with patch.object(server, "public_get", return_value=sample) as provider, patch.object(server.time, "sleep"):
            result = server.find_companies({"categories": ["architecture"], "countries": ["USA", "UAE", "Saudi Arabia", "India", "Singapore"]})
        found = result["companies"]
        self.assertEqual(len(result["coverage"]), 5)
        self.assertEqual([item["country"] for item in result["coverage"]], ["US", "AE", "SA", "IN", "SG"])
        self.assertEqual(provider.call_count, 5)
        self.assertEqual(len(found), 10)
        self.assertEqual(found[0]["email"], "office@example.com")
        self.assertIsNone(found[0]["phone"])
        self.assertIsNone(found[1]["email"])
        self.assertEqual(found[1]["source_url"], "https://www.openstreetmap.org/way/2")
        query = urllib.parse.parse_qs(provider.call_args.kwargs["data"].decode())["data"][0]
        self.assertIn("around:12000,1.3521,103.8198", query)

    def test_partial_country_failure_is_visible(self):
        responses = [RuntimeError("Unavailable"), {"elements": []}, {"elements": []}, {"elements": []}, {"elements": []}]
        with patch.object(server, "public_get", side_effect=responses), patch.object(server.time, "sleep"):
            result = server.find_companies({"categories": ["architecture"], "countries": ["USA", "UAE", "Saudi Arabia", "India", "Singapore"]})
        self.assertEqual(result["coverage"][0]["country"], "US")
        self.assertIn("error", result["coverage"][0])
        self.assertEqual(len(result["coverage"]), 5)

    def test_all_map_failures_report_underlying_cause(self):
        with patch.object(server, "public_get", side_effect=RuntimeError("HTTP 429: the public map service is rate limiting requests.")):
            with self.assertRaisesRegex(RuntimeError, "First error: HTTP 429"):
                server.find_companies({"categories": ["architecture"], "countries": ["India"]})

    def test_network_failure_uses_backup_for_remaining_countries(self):
        responses = [server.MapConnectionError("Network is unreachable"), {"elements": []}, {"elements": []}]
        with patch.object(server, "public_get", side_effect=responses) as provider, patch.object(server.time, "sleep"):
            result = server.find_companies({"categories": ["architecture"], "countries": ["India", "Singapore"]})
        self.assertEqual([call.args[0] for call in provider.call_args_list],
                         [server.OVERPASS, server.OVERPASS_BACKUP, server.OVERPASS_BACKUP])
        self.assertEqual(len(result["coverage"]), 2)

    def test_backup_failure_preserves_both_errors(self):
        with patch.object(server, "public_get", side_effect=[server.MapConnectionError("Network is unreachable"), RuntimeError("Backup timeout")]):
            with self.assertRaisesRegex(RuntimeError, "Primary connection failed:.*Backup failed: Backup timeout"):
                server.find_companies({"categories": ["architecture"], "countries": ["India"]})

    def test_rate_limit_does_not_trigger_backup(self):
        with patch.object(server, "public_get", side_effect=RuntimeError("HTTP 429")) as provider:
            with self.assertRaises(RuntimeError):
                server.find_companies({"categories": ["architecture"], "countries": ["India"]})
        self.assertEqual(provider.call_count, 1)

    def test_map_http_error_identifies_rate_limit(self):
        error = urllib.error.HTTPError(server.OVERPASS, 429, "Too Many Requests", {}, None)
        with patch.object(server.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(RuntimeError, "HTTP 429:.*rate limiting"):
                server.public_get(server.OVERPASS, data=b"data=test")

    def test_country_focus_controls_search_and_reports_unsupported(self):
        icp = server.validate_icp({"name": "Training", "countries": ["India", "Germany"], "categories": ["architecture"]})
        with patch.object(server, "public_get", return_value={"elements": []}) as provider:
            result = server.find_companies(icp)
        self.assertEqual(provider.call_count, 1)
        self.assertEqual(result["coverage"][0]["country"], "IN")
        self.assertEqual(result["coverage"][1]["country"], "Germany")
        self.assertIn("error", result["coverage"][1])

    def test_existing_icp_database_is_migrated_without_losing_values(self):
        legacy_db = Path(self.temp.name) / "legacy.db"
        with server.sqlite3.connect(legacy_db) as db:
            db.execute("""CREATE TABLE icps (service TEXT PRIMARY KEY, name TEXT NOT NULL,
                country TEXT NOT NULL, city TEXT NOT NULL, categories TEXT NOT NULL,
                notes TEXT NOT NULL, updated_at TEXT NOT NULL)""")
            db.execute("INSERT INTO icps VALUES (?, ?, ?, ?, ?, ?, ?)",
                       ("training", "Existing Training ICP", "ALL", "Five-country sample", '["education"]', "Keep this note", server.now()))
        server.DB_PATH = legacy_db
        server.init_db()
        with server.connect() as db:
            migrated = server.get_icp(db, "training")
        self.assertEqual(migrated["name"], "Existing Training ICP")
        self.assertEqual(migrated["categories"], ["education"])
        self.assertEqual(migrated["notes"], "Keep this note")
        self.assertEqual(len(migrated["countries"]), 5)

    def test_postgres_url_selects_postgres_and_initializes_schema(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        psycopg = types.ModuleType("psycopg")
        psycopg.__path__ = []
        psycopg.connect = MagicMock(return_value=connection)
        rows = types.ModuleType("psycopg.rows")
        rows.dict_row = object()
        with patch.object(server, "DATABASE_URL", "postgresql://example.invalid/voxel1"), patch.dict(sys.modules, {"psycopg": psycopg, "psycopg.rows": rows}):
            server.init_db()
            server.run(connection, "SELECT * FROM icps WHERE service = ?", ("training",))
        self.assertEqual(psycopg.connect.call_args.kwargs["row_factory"], rows.dict_row)
        statements = [call.args[0] for call in connection.execute.call_args_list]
        self.assertTrue(any("BIGINT GENERATED BY DEFAULT AS IDENTITY" in sql for sql in statements))
        self.assertTrue(any("ON CONFLICT(service) DO NOTHING" in sql for sql in statements))
        self.assertEqual(statements[-1], "SELECT * FROM icps WHERE service = %s")


if __name__ == "__main__":
    unittest.main()
