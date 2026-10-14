import gc
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import ai_draft
import provider_search
import server

ENV = {"GEMINI_API_KEY": "test", "VOXEL1_MONTHLY_GEMINI_REQUESTS": "2"}
GOOD = {"title": "BIM support for Example Architects", "body": "Hello,\n\nWould a short call be useful?\n\nThe Voxel1 team", "model": "gemini-test"}


class AiDraftTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_db = server.DB_PATH
        server.DB_PATH = Path(self.temp.name) / "test.db"
        server.init_db()
        with server.connect() as db:
            self.lead = server.run(db, """INSERT INTO leads (service, source_id, company, category, city, country, source_url, discovered_at, updated_at)
                VALUES ('bim', 'manual/1', 'Example Architects', 'architecture', '', 'India', 'https://example.test', 'x', 'x') RETURNING id""").fetchone()["id"]

    def tearDown(self):
        server.DB_PATH = self.old_db
        gc.collect()  # Exception tracebacks can hold the SQLite file open on Windows.
        self.temp.cleanup()

    def request(self, path, body):
        data = json.dumps(body).encode()
        handler = object.__new__(server.Handler)
        handler.path = path
        handler.headers = {"Content-Length": str(len(data))}
        handler.rfile = io.BytesIO(data)
        handler.wfile = io.BytesIO()
        handler.send_response = lambda code: setattr(handler, "response_code", code)
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler.authorized = lambda: True
        handler.same_origin_write = lambda: True
        handler.do_POST()
        return handler.response_code, json.loads(handler.wfile.getvalue())

    def draft(self, body=None):
        return self.request(f"/api/services/bim/leads/{self.lead}/ai-draft", body or {"purpose": "First contact"})

    def usage(self):
        with server.connect() as db:
            return server.ai_draft_count(db, server.month_key())

    def test_draft_saved_as_pending_outreach_and_counted(self):
        with patch.dict(os.environ, ENV), patch.object(ai_draft, "write_draft", return_value=GOOD) as write:
            code, item = self.draft()
        self.assertEqual(code, 200)
        self.assertEqual((item["kind"], item["state"], item["channel"], item["label"]), ("outreach", "pending", "Email", "First contact"))
        self.assertEqual(item["lead_id"], self.lead)
        self.assertEqual(write.call_args.args[0]["company"], "Example Architects")
        self.assertEqual(self.usage(), 1)

    def test_no_gemini_limit_blocks_before_any_request(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": "test"}, clear=True), patch.object(ai_draft, "write_draft") as write:
            code, body = self.draft()
        self.assertEqual(code, 409)
        self.assertIn("VOXEL1_MONTHLY_GEMINI_REQUESTS", body["error"])
        write.assert_not_called()

    def test_monthly_limit_is_enforced_and_failures_still_count(self):
        with patch.dict(os.environ, ENV), patch.object(ai_draft, "write_draft", side_effect=provider_search.ProviderError("down")):
            self.assertEqual(self.draft()[0], 502)
        with patch.dict(os.environ, ENV), patch.object(ai_draft, "write_draft", return_value=GOOD):
            self.assertEqual(self.draft()[0], 200)
            code, body = self.draft()
        self.assertEqual(code, 409)
        self.assertEqual(self.usage(), 2)
        with server.connect() as db:
            self.assertEqual(server.run(db, "SELECT COUNT(*) AS n FROM growth_items").fetchone()["n"], 1)

    def test_follow_up_needs_an_approved_message(self):
        with patch.dict(os.environ, ENV), patch.object(ai_draft, "write_draft") as write:
            code, body = self.draft({"purpose": "Follow-up"})
        self.assertEqual(code, 400)
        write.assert_not_called()

    def test_paused_and_rejected_leads_are_refused(self):
        with server.connect() as db:
            server.run(db, "UPDATE leads SET review_decision='rejected' WHERE id=?", (self.lead,))
        with patch.dict(os.environ, ENV), patch.object(ai_draft, "write_draft") as write:
            self.assertEqual(self.draft()[0], 400)
        write.assert_not_called()

    def test_hard_rules_discard_unsafe_drafts(self):
        for text in ("We offer a free pilot workshop.", "Rates start at $40 per hour.", "Our Hyderabad team can help.",
                     "See our case study for Acme."):
            self.assertTrue(ai_draft.check_rules("Subject", text), text)
        self.assertFalse(ai_draft.check_rules("BIM support", "Would a short call be useful? The Voxel1 team, India."))

    def test_unsafe_model_output_raises_and_hidden_names_are_dropped(self):
        reply = {"candidates": [{"content": {"parts": [{"text": json.dumps({"subject": "Hi", "body": "Free trial for you!"})}]}}]}

        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *a): return False

        sent = {}
        def opened(req, timeout):
            sent["body"] = json.loads(req.data)
            return Response(json.dumps(reply).encode())

        lead = {"company": "Example", "contact_name": "Al***x", "category": "business"}
        with patch.dict(os.environ, {"GEMINI_API_KEY": "k"}), patch.object(ai_draft.urllib.request, "urlopen", side_effect=opened):
            with self.assertRaises(provider_search.ProviderError):
                ai_draft.write_draft(lead, "training", "First contact")
        prompt = sent["body"]["contents"][0]["parts"][0]["text"]
        self.assertNotIn("Al***x", prompt)
        self.assertNotIn('"industry"', prompt)


if __name__ == "__main__":
    unittest.main()
