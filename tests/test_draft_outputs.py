import gc
import io
import json
import os
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import automation
import draft_outputs
import growth
import server
from provider_search import ProviderError

GOOD = {"title": "BIM planning considerations", "body": "Proposed scope: review requirements.\nQuestions: project timing is unknown.", "model": "test-model"}


class DraftOutputsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(server, "DB_PATH", Path(self.temp.name) / "test.db"),
                        patch.dict(os.environ, {"GEMINI_API_KEY": "test", "VOXEL1_MONTHLY_GEMINI_REQUESTS": "20"})]
        for p in self.patches:
            p.start()
        server.init_db()
        with closing(server.connect()) as db, db:
            self.lead = growth.add_company(db, server.run, {"service": "bim", "company": "Private Buyer", "email": "private@example.test", "country": "Saudi Arabia"}, server.log_event)
            server.run(db, "UPDATE leads SET ai_screened=1 WHERE id=?", (self.lead["id"],))
            self.config = {"objective": "Explain Scan-to-BIM", "start": "2026-10-01", "end": "", "search_time": "06:00", "draft_time": "09:00", "accept_budget": True,
                           "targeting": {"name": "BIM", "countries": ["Saudi Arabia"], "categories": ["engineering"]}}
            automation.save(server, db, "bim", self.config)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        gc.collect()
        self.temp.cleanup()

    def sql(self, statement, values=()):
        with closing(server.connect()) as db, db:
            cursor = server.run(db, statement, values)
            # PostgreSQL cursors for INSERT/UPDATE have no rows to iterate; SQLite's are empty.
            return [dict(r) for r in cursor] if cursor.description else []

    def room(self):
        with patch.object(draft_outputs, "generate", return_value=GOOD):
            return draft_outputs.create(server, "bim", "room", self.lead["id"])

    def test_room_stays_pending_and_duplicate_reuses_without_extra_request(self):
        item = self.room()
        again = self.room()
        self.assertEqual(item["id"], again["id"])
        self.assertEqual((item["state"], item["kind"], item["channel"]), ("pending", "room", "Internal"))
        self.assertEqual(self.sql("SELECT room_notes FROM growth_leads"), [])
        self.assertEqual(len(self.sql("SELECT * FROM provider_usage")), 1)
        with closing(server.connect()) as db, db:
            with self.assertRaises(ValueError):
                draft_outputs.apply_room(db, server.run, {"item_id": item["id"], "revision": item["revision"]})

    def test_approved_room_apply_preserves_owner_and_stage_and_rejects_stale_notes(self):
        item = self.room()
        with closing(server.connect()) as db, db:
            before = growth.save_lead(db, server.run, self.lead["id"], {"service": "bim", "stage": "meeting", "owner": "Delivery head", "room_notes": "Existing manual notes"})
            item = growth.save_item(db, server.run, item["id"], {"action": "approve", "revision": item["revision"]})
        self.assertEqual(self.sql("SELECT room_notes FROM growth_leads")[0]["room_notes"], "Existing manual notes")
        with self.assertRaises(growth.Conflict):
            with closing(server.connect()) as db, db:
                draft_outputs.apply_room(db, server.run, {"item_id": item["id"], "revision": item["revision"], "room_updated_at": "stale"})
        with closing(server.connect()) as db, db:
            draft_outputs.apply_room(db, server.run, {"item_id": item["id"], "revision": item["revision"], "room_updated_at": before["updated_at"]})
        room = self.sql("SELECT * FROM growth_leads")[0]
        self.assertEqual((room["stage"], room["owner"], room["room_notes"]), ("meeting", "Delivery head", GOOD["body"]))
        self.assertEqual(self.sql("SELECT state FROM growth_items")[0]["state"], "done")

    def test_public_post_never_receives_private_lead_facts(self):
        with patch.object(draft_outputs, "generate", return_value=GOOD) as generate:
            item = draft_outputs.create(server, "bim", "linkedin")
        facts = generate.call_args.args[2]
        self.assertNotIn("Private Buyer", json.dumps(facts))
        self.assertNotIn("private@example.test", json.dumps(facts))
        self.assertEqual((item["kind"], item["channel"], item["lead_id"], item["state"]), ("content", "LinkedIn", None, "pending"))

    def test_pause_and_budget_block_before_generation(self):
        self.sql("UPDATE growth_settings SET paused=1 WHERE service='global'")
        with patch.object(draft_outputs, "generate") as generate:
            with self.assertRaises(ValueError):
                draft_outputs.create(server, "bim", "linkedin")
            generate.assert_not_called()
        self.sql("UPDATE growth_settings SET paused=0 WHERE service='global'")
        with patch.dict(os.environ, {"VOXEL1_MONTHLY_GEMINI_REQUESTS": "0"}), patch.object(draft_outputs, "generate") as generate:
            with self.assertRaises(server.BudgetBlocked):
                draft_outputs.create(server, "bim", "linkedin")
            generate.assert_not_called()

    def test_failure_counts_request_without_saving_placeholder(self):
        with patch.object(draft_outputs, "generate", side_effect=ProviderError("Unavailable")):
            with self.assertRaises(ProviderError):
                draft_outputs.create(server, "bim", "linkedin")
        self.assertEqual(len(self.sql("SELECT * FROM provider_usage")), 1)
        self.assertEqual(self.sql("SELECT * FROM growth_items"), [])

    def test_unsafe_generated_copy_is_rejected(self):
        answer = {"title": "Special offer", "body": "Get a free trial for your team."}
        response = {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]}
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())):
            with self.assertRaises(ProviderError):
                draft_outputs.generate("linkedin", "bim", {}, "")

    def test_scheduled_room_and_post_drafts_run_once_without_new_discovery(self):
        config = {**self.config, "auto_rooms": True, "auto_linkedin": True, "content_targets": {"LinkedIn": 2}, "goal": 4, "quarter": "2026-Q4", "strategy": "Buyer education"}
        with closing(server.connect()) as db, db:
            automation.save(server, db, "bim", config)
        automation.claim(server, "bim", "2026-10-15", "discovery")
        automation.finish(server, "bim", "2026-10-15", "discovery", "done", {"lead_ids": []})
        instant = datetime(2026, 10, 15, 8, tzinfo=timezone.utc)
        with patch.object(draft_outputs, "generate", return_value=GOOD) as generate, patch.object(automation, "discovery") as discover:
            automation.tick(server, instant)
            automation.tick(server, instant)
            self.assertEqual(generate.call_count, 3)
            discover.assert_not_called()
        items = self.sql("SELECT kind, channel, state FROM growth_items")
        self.assertEqual(len(items), 3)
        self.assertTrue(all(i["state"] == "pending" for i in items))
        jobs = self.sql("SELECT * FROM agent_jobs WHERE job<>?", ("discovery",))
        self.assertTrue(all(j["state"] == "needs_approval" for j in jobs))

    def test_legacy_campaign_does_not_start_new_paid_outputs(self):
        automation.claim(server, "bim", "2026-10-15", "discovery")
        automation.finish(server, "bim", "2026-10-15", "discovery", "done", {"lead_ids": []})
        with patch.object(draft_outputs, "generate") as generate:
            automation.tick(server, datetime(2026, 10, 15, 8, tzinfo=timezone.utc))
            generate.assert_not_called()

    def test_room_refresh_uses_real_updates_without_looping_after_apply(self):
        day = "2026-10-15"
        item = self.room()
        with closing(server.connect()) as db, db:
            item = growth.save_item(db, server.run, item["id"], {"action": "approve", "revision": item["revision"]})
            draft_outputs.apply_room(db, server.run, {"item_id": item["id"], "revision": item["revision"], "room_updated_at": ""})
        self.assertEqual(draft_outputs.room_candidates(server, "bim", day), [])
        with closing(server.connect()) as db, db:
            growth.save_lead(db, server.run, self.lead["id"], {"service": "bim", "stage": "proposal", "owner": "Team", "room_notes": "A real scope question was recorded."})
        candidates = draft_outputs.room_candidates(server, "bim", day)
        self.assertEqual([c["id"] for c in candidates], [self.lead["id"]])
        with patch.object(draft_outputs, "generate", return_value=GOOD) as generate:
            refreshed = draft_outputs.create(server, "bim", "room", self.lead["id"], day=day)
            self.assertEqual(generate.call_args.args[2]["recorded_stage"], "proposal")
        self.assertNotEqual(refreshed["id"], item["id"])
        self.assertEqual(self.sql("SELECT room_notes FROM growth_leads")[0]["room_notes"], "A real scope question was recorded.")


if __name__ == "__main__":
    unittest.main()
