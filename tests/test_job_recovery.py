"""Explicit retries preserve approval, attempt history and existing spending caps."""
import gc
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone, timedelta
from unittest.mock import patch
from concurrent.futures import ThreadPoolExecutor

import automation
import draft_outputs
import growth
import job_recovery
import provider_search
import rhythm_engine
import server

GOOD = {"title": "Scan-to-BIM introduction", "body": "Would a call about Scan-to-BIM be useful?", "model": "test"}


class JobRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(server, "DB_PATH", Path(self.temp.name) / "test.db"),
                        patch.object(server, "PUBLIC_NO_AUTH", False),
                        patch.dict(os.environ, {"GEMINI_API_KEY": "test", "VOXEL1_MONTHLY_GEMINI_REQUESTS": "100"})]
        for p in self.patches: p.start()
        server.init_db()
        self.day = datetime.now(timezone.utc).astimezone(growth.IST).date().isoformat()
        with closing(server.connect()) as db, db:
            self.lead = growth.add_company(db, server.run, {"service": "bim", "company": "Example Buyer", "country": "Saudi Arabia"}, server.log_event)
            server.run(db, "UPDATE leads SET ai_screened=1 WHERE id=?", (self.lead["id"],))
            config = {"objective": "Scan-to-BIM", "start": self.day, "end": "", "auto_rooms": True,
                      "full_rhythm": True, "search_time": "06:00", "draft_time": "09:00", "accept_budget": True,
                      "service_focus": "Scan-to-BIM", "targeting": {"name": "BIM", "countries": ["Saudi Arabia"], "categories": ["engineering"]}}
            automation.save(server, db, "bim", config)
        self.job = f"message:LinkedIn:{self.lead['id']}"

    def tearDown(self):
        for p in reversed(self.patches): p.stop()
        gc.collect()
        self.temp.cleanup()

    def rows(self, sql, values=()):
        with closing(server.connect()) as db, db:
            cursor = server.run(db, sql, values)
            return [dict(r) for r in cursor] if cursor.description else []

    def failed(self, job=None, exception=None):
        job = job or self.job
        self.assertTrue(automation.claim(server, "bim", self.day, job))
        with self.assertLogs(level="ERROR"):
            try:
                raise exception or provider_search.DraftGenerationError("Gemini returned no answer candidate. No output was saved.")
            except Exception as exc:
                automation.finish(server, "bim", self.day, job, "needs_you", {"message": automation.safe_error(server, exc)})
        row = self.rows("SELECT * FROM agent_jobs WHERE service='bim' AND day=? AND job=?", (self.day, job))[0]
        return {"service": "bim", "day": self.day, "job": job, "confirmed": True,
                "failure_token": json.loads(row["result"]).get("failure_token")}

    def usage(self):
        with closing(server.connect()) as db:
            return server.ai_draft_count(db, server.month_key())

    def test_generation_reason_is_saved_and_safe_retry_creates_one_pending_draft(self):
        request = self.failed()
        before = json.loads(self.rows("SELECT result FROM agent_jobs")[0]["result"])
        self.assertIn("no answer candidate", before["message"])
        with patch.object(draft_outputs, "generate", return_value=GOOD) as generate:
            result = job_recovery.retry(server, request)
            with self.assertRaises(ValueError): job_recovery.retry(server, request)
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(result["state"], "needs_approval")
        self.assertEqual(self.usage(), 1)
        self.assertEqual(self.rows("SELECT state FROM growth_items"), [{"state": "pending"}])
        history = self.rows("SELECT previous_result, state FROM agent_retry_attempts")[0]
        self.assertEqual(json.loads(history["previous_result"]), before)
        self.assertEqual(history["state"], "needs_approval")

    def test_existing_saved_output_is_reused_without_a_paid_call(self):
        request = self.failed()
        with closing(server.connect()) as db, db:
            saved = growth.save_item(db, server.run, None, {"service": "bim", "kind": "outreach", "lead_id": self.lead["id"],
                "title": "Existing", "body": "Existing draft", "channel": "LinkedIn", "label": "First contact"})
        with patch.object(draft_outputs, "generate") as generate:
            result = job_recovery.retry(server, request)
        self.assertEqual(result["item_id"], saved["id"])
        generate.assert_not_called()
        self.assertEqual(self.usage(), 0)
        self.assertEqual(self.rows("SELECT * FROM agent_retry_attempts"), [])

    def test_legacy_and_storage_failures_cannot_be_retried_blindly(self):
        request = self.failed(exception=OSError("PRIVATE DATABASE DETAIL"))
        result = json.loads(self.rows("SELECT result FROM agent_jobs")[0]["result"])
        self.assertNotIn("PRIVATE", result["message"])
        with self.assertRaises(ValueError): job_recovery.retry(server, {**request, "failure_token": "invented"})
        self.assertEqual(self.usage(), 0)

    def test_pause_budget_confirmation_and_service_are_checked_before_generation(self):
        request = self.failed()
        for changes in ({"confirmed": False}, {"service": "training"}, {"day": "2000-01-01"}, {"failure_token": "stale"}, {"job": "rhythm:4"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                job_recovery.retry(server, {**request, **changes})
        self.rows("UPDATE growth_settings SET paused=1 WHERE service='bim'")
        with self.assertRaises(ValueError): job_recovery.retry(server, request)
        self.rows("UPDATE growth_settings SET paused=0 WHERE service='bim'")
        with patch.dict(os.environ, {"VOXEL1_MONTHLY_GEMINI_REQUESTS": "0"}), self.assertRaises(server.BudgetBlocked):
            job_recovery.retry(server, request)
        self.assertEqual(self.rows("SELECT * FROM agent_retry_attempts"), [])
        self.assertEqual(self.usage(), 0)

    def test_daily_attempt_limit_is_not_bypassed_by_retry(self):
        request = self.failed()
        for i in range(4):
            self.failed(job=f"message:LinkedIn:{100 + i}")
        with self.assertRaises(server.BudgetBlocked): job_recovery.retry(server, request)
        self.assertEqual(self.usage(), 0)

    def test_retry_failure_rotates_token_and_is_not_automatically_repeated(self):
        request = self.failed()
        with self.assertLogs(level="ERROR"), patch.object(draft_outputs, "generate", side_effect=provider_search.DraftGenerationError("Gemini output-token limit. No output saved.")) as generate:
            failed = job_recovery.retry(server, request)
        self.assertEqual(failed["state"], "needs_you")
        self.assertNotEqual(failed["failure_token"], request["failure_token"])
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(self.usage(), 1)
        with self.assertRaises(ValueError): job_recovery.retry(server, request)

    def test_storage_failure_after_generation_has_uncertain_outcome_and_no_retry(self):
        request = self.failed()
        with self.assertLogs(level="ERROR"), patch.object(draft_outputs, "generate", return_value=GOOD), patch.object(rhythm_engine, "save_item", side_effect=OSError("storage offline")):
            result = job_recovery.retry(server, request)
        self.assertFalse(result["retry_safe"])
        with self.assertRaises(ValueError): job_recovery.retry(server, {**request, "failure_token": result.get("failure_token")})

    def test_concurrent_clicks_make_only_one_paid_request(self):
        request = self.failed()
        def attempted():
            try:
                return job_recovery.retry(server, request)["state"]
            except ValueError:
                return "refused"
        with patch.object(draft_outputs, "generate", return_value=GOOD) as generate, ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: attempted(), range(2)))
        self.assertCountEqual(results, ["needs_approval", "refused"])
        self.assertEqual(generate.call_count, 1)
        self.assertEqual(self.usage(), 1)

    def test_http_route_returns_the_saved_result_and_requires_authentication(self):
        request = self.failed()
        def posted(authorized):
            encoded = json.dumps(request).encode()
            handler = object.__new__(server.Handler)
            handler.path = "/api/growth/retry-draft"
            handler.headers = {"Content-Length": str(len(encoded))}
            handler.rfile, handler.wfile = io.BytesIO(encoded), io.BytesIO()
            handler.send_response = lambda value: setattr(handler, "response_code", value)
            handler.send_header = lambda *args: None
            handler.end_headers = lambda: None
            def authorize():
                if not authorized:
                    handler.respond(401, {"error": "Sign in required"})
                return authorized
            handler.authorized = authorize
            handler.same_origin_write = lambda: True
            handler.do_POST()
            return handler.response_code, json.loads(handler.wfile.getvalue())
        with patch.object(draft_outputs, "generate", return_value=GOOD) as generate:
            self.assertEqual(posted(False)[0], 401)
            generate.assert_not_called()
            code, result = posted(True)
        self.assertEqual(code, 200)
        self.assertEqual(result["state"], "needs_approval")

    def test_retry_is_not_allowed_after_human_rejects_a_saved_output(self):
        request = self.failed()
        with closing(server.connect()) as db, db:
            saved = growth.save_item(db, server.run, None, {"service": "bim", "kind": "outreach", "lead_id": self.lead["id"],
                "title": "Existing", "body": "Not suitable", "channel": "LinkedIn", "label": "First contact"})
            growth.save_item(db, server.run, saved["id"], {"action": "reject", "revision": saved["revision"]})
        with patch.object(draft_outputs, "generate") as generate:
            result = job_recovery.retry(server, request)
        generate.assert_not_called()
        self.assertEqual(result["item_id"], saved["id"])

    def test_email_and_room_retries_use_their_original_workflows(self):
        email_request = self.failed(job=f"draft:{self.lead['id']}")
        with patch.object(server.ai_draft, "write_draft", return_value=GOOD):
            email = job_recovery.retry(server, email_request)
        with closing(server.connect()) as db:
            lead = server.run(db, "SELECT * FROM leads WHERE id=?", (self.lead["id"],)).fetchone()
            _, digest, _, _ = draft_outputs.room_context(server, db, lead, "bim", self.day)
        room_request = self.failed(job=f"room:{self.lead['id']}:{digest[:12]}")
        with patch.object(draft_outputs, "generate", return_value=GOOD):
            room = job_recovery.retry(server, room_request)
        items = self.rows("SELECT kind, channel, state FROM growth_items")
        self.assertIn({"kind": "outreach", "channel": "Email", "state": "pending"}, items)
        self.assertIn({"kind": "room", "channel": "Internal", "state": "pending"}, items)
        self.assertEqual(self.usage(), 2)

    def test_unknown_persistence_outcome_and_already_saved_ids_are_refused(self):
        request = self.failed()
        row = self.rows("SELECT result FROM agent_jobs")[0]
        result = json.loads(row["result"])
        result["item_ids"] = [999]
        self.rows("UPDATE agent_jobs SET result=?", (json.dumps(result),))
        with self.assertRaises(ValueError): job_recovery.retry(server, request)
        self.assertEqual(self.usage(), 0)

    def test_two_retry_limit_and_new_claims_respect_retry_attempt_count(self):
        request = self.failed()
        for _ in range(2):
            with self.assertLogs(level="ERROR"), patch.object(draft_outputs, "generate", side_effect=provider_search.DraftGenerationError("Missing JSON; no output saved.")):
                result = job_recovery.retry(server, request)
            request = {**request, "failure_token": result["failure_token"]}
        with self.assertRaisesRegex(ValueError, "two explicit retries"):
            job_recovery.retry(server, request)
        for i in range(2):
            self.assertTrue(automation.claim(server, "bim", self.day, f"message:LinkedIn:{900+i}"))
        self.assertFalse(automation.claim(server, "bim", self.day, "message:LinkedIn:999"))

    def test_http_failure_reason_never_includes_provider_body(self):
        import urllib.error
        exception = urllib.error.HTTPError("https://example.test", 429, "PRIVATE API DETAIL", {}, io.BytesIO(b'{"error":{"message":"SECRET"}}'))
        reason = provider_search.draft_failure(exception)
        self.assertIn("429", reason)
        self.assertNotIn("SECRET", reason)
        self.assertNotIn("PRIVATE", reason)
