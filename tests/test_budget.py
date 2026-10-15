import io
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

import provider_search
import server

KEYS = {"APOLLO_API_KEY": "test", "BRAVE_SEARCH_API_KEY": "test"}
LIMITS = {"VOXEL1_MONTHLY_SEARCH_LIMIT": "10", "VOXEL1_MONTHLY_APOLLO_REQUESTS": "200", "VOXEL1_MONTHLY_BRAVE_REQUESTS": "200"}
ESTIMATE = {"apollo": 11, "brave": 10, "gemini": 0}
CONFIRM = {"confirmed": True, "estimate": ESTIMATE}


def fake_providers(url, _header, _key, params):
    """One company with a matching BIM page and one decision-maker; no network access."""
    if url.endswith("mixed_companies/search"):
        return {"organizations": [{"id": "a", "name": "Example Architects", "website_url": "https://example.test", "country": "India"}]}
    if url == provider_search.BRAVE:
        return {"web": {"results": [{"url": "https://example.test/bim", "title": "BIM projects"}]}}
    return {"people": [{"first_name": "Alex", "title": "BIM Manager"}]}


class BudgetTest(unittest.TestCase):
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

    def run_count(self):
        with server.connect() as db:
            return server.run(db, "SELECT COUNT(*) AS n FROM search_runs").fetchone()["n"]

    def test_unset_limits_block_paid_search_without_provider_calls(self):
        with patch.dict(os.environ, KEYS, clear=True), patch.object(provider_search, "request_json") as call:
            code, body = self.request("POST", "/api/services/training/discover", CONFIRM)
        self.assertEqual(code, 409)
        self.assertIn("VOXEL1_MONTHLY_SEARCH_LIMIT", body["error"])
        self.assertIn("VOXEL1_MONTHLY_APOLLO_REQUESTS", body["error"])
        self.assertFalse(body["budget"]["allowed"])
        call.assert_not_called()
        self.assertEqual(self.run_count(), 0)

    def test_search_requires_confirmation_of_current_estimate(self):
        with patch.dict(os.environ, {**KEYS, **LIMITS}, clear=True), patch.object(provider_search, "request_json") as call:
            code, body = self.request("POST", "/api/services/training/discover")
            self.assertEqual((code, body["needs_confirmation"]), (409, True))
            self.assertEqual(body["budget"]["estimate"], ESTIMATE)
            # Enabling enrichment after the preview raises the estimate; the old confirmation no longer applies.
            with patch.dict(os.environ, {"APOLLO_ENRICH_DETAILS": "1"}):
                code, body = self.request("POST", "/api/services/training/discover", CONFIRM)
            self.assertEqual(code, 409)
            self.assertEqual(body["budget"]["estimate"]["apollo"], 17)
        call.assert_not_called()
        self.assertEqual(self.run_count(), 0)

    def test_confirmed_search_records_measured_usage_in_ledger(self):
        with patch.dict(os.environ, {**KEYS, **LIMITS}, clear=True), patch.object(provider_search, "request_json", side_effect=fake_providers) as call:
            code, result = self.request("POST", "/api/services/training/discover", CONFIRM)
            _, budget = self.request("GET", "/api/budget")
        self.assertEqual(code, 200)
        self.assertEqual(call.call_count, 3)
        self.assertEqual(result["usage"]["estimate"], ESTIMATE)
        self.assertEqual(result["usage"]["actual"], {"apollo": 2, "brave": 1, "gemini": 0})
        self.assertEqual(budget["used"], {"apollo": 2, "brave": 1, "gemini": 0})
        self.assertEqual(budget["searches_used"], 1)
        self.assertEqual(budget["recent"][0]["status"], "completed")
        with server.connect() as db:
            rows = [(row["provider"], row["operation"]) for row in server.run(db, "SELECT provider, operation FROM provider_usage ORDER BY id")]
        self.assertEqual(rows, [("apollo", "company_search"), ("brave", "web_search"), ("apollo", "people_search")])

    def test_exhausted_cap_blocks_next_search_before_any_request(self):
        limits = {**LIMITS, "VOXEL1_MONTHLY_APOLLO_REQUESTS": "15"}
        with patch.dict(os.environ, {**KEYS, **limits}, clear=True), patch.object(provider_search, "request_json", side_effect=fake_providers) as call:
            self.assertEqual(self.request("POST", "/api/services/training/discover", CONFIRM)[0], 200)
            self.assertEqual(self.request("POST", "/api/services/bim/discover", CONFIRM)[0], 200)
            calls_before = call.call_count
            # 4 Apollo requests measured; 11 of the remaining 11 cover one more worst case.
            self.assertEqual(self.request("POST", "/api/services/training/discover", CONFIRM)[0], 200)
            code, body = self.request("POST", "/api/services/training/discover", CONFIRM)
        self.assertEqual(calls_before + 3, call.call_count)
        self.assertEqual(code, 409)
        self.assertIn("Apollo: this search may need up to 11 requests but only 9 remain", body["error"])
        self.assertEqual(self.run_count(), 3)

    def test_monthly_search_limit_counts_failed_searches(self):
        limits = {**LIMITS, "VOXEL1_MONTHLY_SEARCH_LIMIT": "1"}
        def failure(*_args):
            raise provider_search.ProviderError("Apollo returned HTTP 500.")
        with patch.dict(os.environ, {**KEYS, **limits}, clear=True), patch.object(provider_search, "request_json", side_effect=failure) as call:
            code, _ = self.request("POST", "/api/services/training/discover", CONFIRM)
            self.assertEqual(code, 502)
            code, body = self.request("POST", "/api/services/training/discover", CONFIRM)
            _, budget = self.request("GET", "/api/budget")
        self.assertEqual(call.call_count, 1)
        self.assertEqual(code, 409)
        self.assertIn("search limit reached (1 of 1", body["error"])
        self.assertEqual(budget["used"]["apollo"], 1)  # The failed request is still counted.
        self.assertEqual(budget["recent"][0]["status"], "failed")

    def test_concurrent_reservations_cannot_exceed_cap(self):
        limits = {**LIMITS, "VOXEL1_MONTHLY_SEARCH_LIMIT": "2"}
        results = []
        start = threading.Barrier(8)

        def attempt():
            start.wait()
            try:
                results.append(server.reserve_search("training")[0])
            except server.BudgetBlocked:
                results.append(None)

        with patch.dict(os.environ, {**KEYS, **limits}, clear=True):
            threads = [threading.Thread(target=attempt) for _ in range(8)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()
        self.assertEqual(sum(result is not None for result in results), 2)
        self.assertEqual(self.run_count(), 2)

    def test_interrupted_reservation_keeps_holding_its_estimate(self):
        with patch.dict(os.environ, {**KEYS, **LIMITS}, clear=True):
            server.reserve_search("training")
            server.init_db()  # Simulates a restart while the search was running.
            with server.connect() as db:
                budget = server.budget_status(db)
        self.assertEqual(budget["recent"][0]["status"], "interrupted")
        self.assertEqual(budget["held"], ESTIMATE)
        self.assertEqual(budget["used"], {"apollo": 0, "brave": 0, "gemini": 0})

    def test_gemini_needs_its_own_cap_when_enabled(self):
        with patch.dict(os.environ, {**KEYS, **LIMITS, "GEMINI_API_KEY": "test"}, clear=True), patch.object(provider_search, "request_json") as call:
            code, body = self.request("POST", "/api/services/training/discover", {"confirmed": True, "estimate": {**ESTIMATE, "gemini": 10}})
        self.assertEqual(code, 409)
        self.assertIn("VOXEL1_MONTHLY_GEMINI_REQUESTS", body["error"])
        call.assert_not_called()

    def test_map_mode_is_not_budgeted(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(server, "find_companies", return_value={"companies": [], "coverage": []}):
            code, body = self.request("POST", "/api/services/training/discover")
        self.assertEqual(code, 200)
        self.assertIsNone(body["usage"])
        self.assertEqual(self.run_count(), 0)


class MeterTest(unittest.TestCase):
    def test_meter_refuses_requests_beyond_reserved_allowance(self):
        meter = provider_search.Meter({"apollo": 1, "brave": 10, "gemini": 0})
        with patch.dict(os.environ, KEYS, clear=True), patch.object(provider_search, "request_json", side_effect=fake_providers) as call:
            result = provider_search.discover({"countries": ["India"]}, "training", meter)
        self.assertEqual(call.call_count, 2)  # Company search and Brave; the people search was refused.
        self.assertEqual(meter.totals(), {"apollo": 1, "brave": 1, "gemini": 0})
        self.assertTrue(any("allowance is used up" in warning for warning in result["warnings"]))

    def test_estimate_reflects_enrichment_and_gemini(self):
        self.assertEqual(provider_search.estimate_requests({}), {"apollo": 11, "brave": 10, "gemini": 0})
        self.assertEqual(provider_search.estimate_requests({"APOLLO_ENRICH_DETAILS": "1", "GEMINI_API_KEY": "x"}), {"apollo": 17, "brave": 10, "gemini": 10})


if __name__ == "__main__":
    unittest.main()
