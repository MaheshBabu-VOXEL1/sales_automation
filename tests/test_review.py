import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import provider_search
import server

KEYS = {"APOLLO_API_KEY": "test", "BRAVE_SEARCH_API_KEY": "test"}
LIMITS = {"VOXEL1_MONTHLY_SEARCH_LIMIT": "10", "VOXEL1_MONTHLY_APOLLO_REQUESTS": "200",
          "VOXEL1_MONTHLY_BRAVE_REQUESTS": "200", "VOXEL1_MONTHLY_GEMINI_REQUESTS": "200"}


def confirm(gemini=False):
    return {"confirmed": True, "estimate": {"apollo": 11, "brave": 10, "gemini": 10 if gemini else 0}}


class FakeProviders:
    """Two Apollo companies with BIM pages; records every simulated request. No network access."""

    def __init__(self):
        self.calls = []

    def __call__(self, url, _header, _key, params):
        self.calls.append((url, dict(params)))
        if url.endswith("mixed_companies/search"):
            return {"organizations": [
                {"id": "a", "name": "Alpha Architects", "website_url": "https://alpha.test", "country": "India"},
                {"id": "b", "name": "Beta Engineering", "website_url": "https://beta.test", "country": "India"},
            ]}
        if url == provider_search.BRAVE:
            domain = params["q"].split("site:", 1)[1].split(" ", 1)[0]
            return {"web": {"results": [{"url": f"https://{domain}/bim", "title": "BIM projects"}]}}
        return {"people": [{"first_name": "Alex", "title": "BIM Manager"}]}

    def brave_domains(self):
        return [params["q"].split("site:", 1)[1].split(" ", 1)[0] for url, params in self.calls if url == provider_search.BRAVE]


class ReviewTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = server.DB_PATH
        server.DB_PATH = Path(self.temp.name) / "test.db"
        server.init_db()

    def tearDown(self):
        server.DB_PATH = self.old_db
        self.temp.cleanup()

    def request(self, method, path, body=None):
        data = json.dumps(body).encode() if body is not None else b""
        handler = object.__new__(server.Handler)
        handler.path = path
        handler.headers = {"Content-Length": str(len(data))}
        handler.rfile = io.BytesIO(data)
        handler.wfile = io.BytesIO()
        handler.send_response = lambda code: setattr(handler, "response_code", code)
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        getattr(handler, "do_" + method)()
        return handler.response_code, json.loads(handler.wfile.getvalue())

    def search(self, fake, gemini=None):
        env = {**KEYS, **LIMITS, **({"GEMINI_API_KEY": "test"} if gemini else {})}
        with patch.dict(os.environ, env, clear=True), patch.object(provider_search, "request_json", side_effect=fake), \
                patch.object(provider_search, "gemini_buyer_candidate", side_effect=gemini or (lambda *a: (True, ""))):
            code, result = self.request("POST", "/api/services/training/discover", confirm(bool(gemini)))
        self.assertEqual(code, 200, result)
        return result

    def leads(self, service="training"):
        return {lead["company"]: lead for lead in self.request("GET", f"/api/services/{service}/leads")[1]}

    def test_search_records_reason_source_and_ai_judgement(self):
        result = self.search(FakeProviders(), gemini=lambda *a: (True, "Architecture firm delivering client projects"))
        self.assertEqual(result["added"], 2)
        lead = self.leads()["Alpha Architects"]
        self.assertIn("Apollo company search in USA, UAE, Saudi Arabia, India, Singapore", lead["match_reason"])
        self.assertIn("Brave found a page on alpha.test mentioning BIM or Revit; the page itself is not stored", lead["match_reason"])
        self.assertEqual(lead["source_url"], "https://alpha.test")
        self.assertEqual((lead["ai_screened"], lead["ai_reason"], lead["ai_model"]), (1, "Architecture firm delivering client projects", provider_search.DEFAULT_GEMINI_MODEL))
        self.assertTrue(lead["screened_at"])
        self.assertEqual(lead["review_decision"], "active")
        # A later search without Gemini keeps the earlier recorded AI judgement.
        self.search(FakeProviders())
        self.assertEqual(self.leads()["Alpha Architects"]["ai_reason"], "Architecture firm delivering client projects")

    def test_reject_keeps_record_and_history_and_restore_reactivates(self):
        self.search(FakeProviders())
        lead = self.leads()["Alpha Architects"]
        self.request("PATCH", f"/api/services/training/leads/{lead['id']}/status", {"status": "interested", "notes": "Asked for brochure"})
        code, updated = self.request("PATCH", f"/api/services/training/leads/{lead['id']}/review",
                                     {"decision": "rejected", "reason": "vendor_or_competitor", "notes": "Sells BIM services"})
        self.assertEqual(code, 200)
        self.assertEqual((updated["review_decision"], updated["review_reason"], updated["review_note"]), ("rejected", "vendor_or_competitor", "Sells BIM services"))
        self.assertEqual((updated["status"], updated["notes"]), ("interested", "Asked for brochure"))  # Interest history is untouched.
        self.assertEqual(len(self.leads()), 2)  # Nothing deleted.
        code, restored = self.request("PATCH", f"/api/services/training/leads/{lead['id']}/review", {"decision": "active"})
        self.assertEqual((code, restored["review_decision"], restored["review_reason"]), (200, "active", ""))
        _, history = self.request("GET", f"/api/services/training/leads/{lead['id']}/history")
        self.assertEqual([item["event"] for item in history], ["review", "review", "interest", "discovered"])
        self.assertEqual(history[1]["detail"], {"from": "active", "to": "rejected", "reason": "vendor_or_competitor", "note": "Sells BIM services"})
        self.assertEqual(history[0]["detail"]["to"], "active")

    def test_review_requires_valid_decision_and_reason(self):
        self.search(FakeProviders())
        lead_id = self.leads()["Alpha Architects"]["id"]
        path = f"/api/services/training/leads/{lead_id}/review"
        self.assertEqual(self.request("PATCH", path, {"decision": "deleted"})[0], 400)
        self.assertEqual(self.request("PATCH", path, {"decision": "rejected"})[0], 400)
        self.assertEqual(self.request("PATCH", path, {"decision": "rejected", "reason": "made_up"})[0], 400)
        code, body = self.request("PATCH", path, {"decision": "archived", "reason": "other"})
        self.assertEqual(code, 400)
        self.assertIn("note", body["error"])
        self.assertEqual(self.request("PATCH", path, {"decision": "archived", "reason": "other", "notes": "Merger pending"})[0], 200)
        # The same lead cannot be changed through the other service's pipeline.
        self.assertEqual(self.request("PATCH", f"/api/services/bim/leads/{lead_id}/review", {"decision": "active"})[0], 404)

    def test_rejected_company_is_skipped_before_paid_followup_requests(self):
        self.search(FakeProviders())
        lead = self.leads()["Alpha Architects"]
        _, rejected = self.request("PATCH", f"/api/services/training/leads/{lead['id']}/review", {"decision": "rejected", "reason": "not_target_industry"})
        fake = FakeProviders()
        result = self.search(fake)
        self.assertEqual(fake.brave_domains(), ["beta.test"])  # No Brave request for the rejected company.
        self.assertEqual(sum(url.endswith("mixed_people/api_search") for url, _ in fake.calls), 1)
        self.assertEqual(result["skipped_reviewed"], 1)
        self.assertEqual(result["usage"]["actual"], {"apollo": 2, "brave": 1, "gemini": 0})
        after = self.leads()["Alpha Architects"]
        self.assertEqual((after["review_decision"], after["updated_at"]), ("rejected", rejected["updated_at"]))
        _, history = self.request("GET", f"/api/services/training/leads/{lead['id']}/history")
        self.assertNotIn("found_again", [item["event"] for item in history])

    def test_map_mode_leaves_archived_record_unchanged(self):
        source = [{"source_id": "node/1", "company": "Map Firm", "category": "architect", "city": "Dubai", "country": "AE",
                   "email": None, "phone": None, "website": None, "source_url": "https://www.openstreetmap.org/node/1",
                   "match_reason": "OpenStreetMap lists it as a architect within 12 km of Dubai."}]
        with patch.dict(os.environ, {}, clear=True), patch.object(server, "find_companies", return_value={"companies": source, "coverage": []}):
            self.request("POST", "/api/services/training/discover")
            lead = self.leads()["Map Firm"]
            self.assertIn("OpenStreetMap lists it", lead["match_reason"])
            self.request("PATCH", f"/api/services/training/leads/{lead['id']}/review", {"decision": "archived", "reason": "no_current_need"})
            source[0]["company"] = "Renamed Map Firm"
            _, result = self.request("POST", "/api/services/training/discover")
        self.assertEqual(result["skipped_reviewed"], 1)
        self.assertIn("Map Firm", self.leads())

    def test_legacy_leads_migrate_as_active_without_reason(self):
        with server.connect() as db:
            server.run(db, "DROP TABLE leads")
            server.run(db, f"""CREATE TABLE leads (
                id {'BIGINT GENERATED BY DEFAULT AS IDENTITY' if server.DATABASE_URL else 'INTEGER'} PRIMARY KEY, service TEXT NOT NULL, source_id TEXT NOT NULL,
                company TEXT NOT NULL, category TEXT NOT NULL, city TEXT NOT NULL,
                country TEXT NOT NULL, email TEXT, phone TEXT, website TEXT,
                source_url TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'new',
                notes TEXT NOT NULL DEFAULT '', discovered_at TEXT NOT NULL,
                updated_at TEXT NOT NULL, UNIQUE(service, source_id))""")
            server.run(db, "INSERT INTO leads (service, source_id, company, category, city, country, source_url, status, notes, discovered_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ("training", "apollo/old", "Old candidate", "business", "", "India", "https://old.test", "interested", "Called", server.now(), server.now()))
        server.init_db()
        lead = self.leads()["Old candidate"]
        self.assertEqual((lead["review_decision"], lead["match_reason"], lead["ai_reason"]), ("active", "", ""))
        self.assertEqual((lead["status"], lead["notes"]), ("interested", "Called"))
        self.assertEqual(self.request("GET", f"/api/services/training/leads/{lead['id']}/history"), (200, []))

    def test_system_endpoint_reports_storage_without_secrets(self):
        code, info = self.request("GET", "/api/system")
        self.assertEqual(code, 200)
        if server.DATABASE_URL:  # Disposable PostgreSQL run (tests/postgres_runner.py).
            self.assertEqual(info["database"], "postgresql")
            self.assertNotIn(server.DATABASE_URL, json.dumps(info))
        else:
            self.assertEqual(info["database"], "sqlite")
            self.assertIn("data_directory_is_mount", info)
        self.assertEqual(set(info["row_counts"]), {"leads", "lead_events", "search_runs", "provider_usage"})

    def test_icp_lists_review_reasons(self):
        _, icp = self.request("GET", "/api/services/bim/icp")
        self.assertIn("vendor_or_competitor", icp["review_reasons"])


if __name__ == "__main__":
    unittest.main()
