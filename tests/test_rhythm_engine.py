import gc
import json
import os
import tempfile
import unittest
import xml.etree.ElementTree as ET
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import automation
import draft_outputs
import growth
import provider_search
import rhythm_engine
import server

OUTPUT = {"title": "BIM planning discussion", "body": "Review the recorded requirements and confirm the next step.", "model": "test-model"}


class RhythmEngineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        env = {"GEMINI_API_KEY": "test", "BRAVE_SEARCH_API_KEY": "test", "BRAVE_SEARCH_STORAGE_ALLOWED": "1",
               "VOXEL1_MONTHLY_GEMINI_REQUESTS": "200", "VOXEL1_MONTHLY_BRAVE_REQUESTS": "100",
               "VOXEL1_MONTHLY_APOLLO_REQUESTS": "100", "VOXEL1_MONTHLY_SEARCH_LIMIT": "20"}
        self.patches = [patch.object(server, "DB_PATH", Path(self.temp.name) / "test.db"),
                        patch.object(server, "PUBLIC_NO_AUTH", False), patch.dict(os.environ, env)]
        for p in self.patches:
            p.start()
        server.init_db()
        self.instant = datetime(2026, 10, 15, 14, tzinfo=timezone.utc)  # after all IST slots

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

    def configure(self, service):
        with closing(server.connect()) as db, db:
            lead = growth.add_company(db, server.run, {"service": service, "company": "Example College" if service == "training" else "Example Consultant", "email": f"{service}@example.test", "category": "education" if service == "training" else "engineering"}, server.log_event)
            server.run(db, "UPDATE leads SET ai_screened=1, contact_name='Recorded contact', contact_title='BIM Manager' WHERE id=?", (lead["id"],))
            growth.save_lead(db, server.run, lead["id"], {"service": service, "stage": "won", "owner": "Team", "room_notes": ""})
            sent = growth.save_item(db, server.run, None, {"service": service, "kind": "outreach", "lead_id": lead["id"], "channel": "Email", "title": "Recorded earlier email", "body": "Earlier message"})
            server.run(db, "UPDATE growth_items SET state='done', updated_at='2026-10-10T00:00:00+00:00' WHERE id=?", (sent["id"],))
            config = {"objective": "BIM support", "start": "2026-10-01", "end": "", "search_time": "06:00", "draft_time": "09:00",
                      "targeting": {"name": "Target", "countries": ["Saudi Arabia"], "categories": ["engineering"]}, "accept_budget": True,
                      "goal": 4, "quarter": "2026-Q4", "strategy": "Evidence-led outreach", "full_rhythm": True,
                      "content_targets": {"LinkedIn": 1, "Instagram": 1, "Facebook": 1}, "partner_accounts": lead["company"],
                      "existing_clients": lead["company"], "approved_proof": "A trainee completed a model-review exercise.", "proof_consent": True}
            automation.save(server, db, service, config)
        return lead, sent

    def test_both_complete_rhythms_generate_outputs_once_and_never_send(self):
        self.configure("bim")
        self.configure("training")
        results = {"web": {"results": [{"url": "https://publisher.example.test/news", "title": "Publisher announcement", "description": "A public search match, not a verified project."}]}}
        with patch.object(automation, "discovery", return_value={"lead_ids": []}), patch.object(provider_search, "request_json", return_value=results) as search, patch.object(draft_outputs, "generate", return_value=OUTPUT) as generate, patch.object(server.outlook, "send") as send:
            automation.tick(server, self.instant)
            calls = generate.call_count
            search_calls = search.call_count
            automation.tick(server, self.instant)
            self.assertEqual(generate.call_count, calls)
            self.assertEqual(search.call_count, search_calls)
            send.assert_not_called()
        slots = self.sql("SELECT * FROM agent_jobs WHERE job LIKE ?", ("rhythm:%",))
        self.assertEqual(len(slots), 16)
        self.assertTrue(all(j["state"] == "needs_review" for j in slots), slots)
        channels = {r["channel"] for r in self.sql("SELECT channel FROM growth_items WHERE kind='outreach' AND state='pending'")}
        self.assertEqual(channels, {"Email", "LinkedIn", "WhatsApp"})
        social = self.sql("SELECT * FROM growth_items WHERE kind='content'")
        self.assertEqual(len(social), 6)
        self.assertTrue(all(i["state"] == "pending" for i in social))
        self.assertEqual(len(self.sql("SELECT * FROM research_snapshots")), 4)
        self.assertEqual(len(self.sql("SELECT * FROM growth_items WHERE label='Daily summary'")), 2)

    def test_every_generation_kind_counts_toward_the_same_budget(self):
        self.configure("bim")
        with patch.dict(os.environ, {"VOXEL1_MONTHLY_GEMINI_REQUESTS": "2"}), patch.object(draft_outputs, "generate", return_value=OUTPUT) as generate:
            draft_outputs.create(server, "bim", "linkedin")
            draft_outputs.create(server, "bim", "instagram")
            with self.assertRaises(server.BudgetBlocked):
                draft_outputs.create(server, "bim", "facebook")
            self.assertEqual(generate.call_count, 2)
            with closing(server.connect()) as db:
                self.assertEqual(server.budget_status(db)["used"]["gemini"], 2)

    def test_daily_summary_does_not_report_itself_as_still_running(self):
        for service, job in (("bim", "rhythm:9"), ("training", "summary")):
            self.configure(service)
            day = "2026-10-15"
            self.assertTrue(automation.claim(server, service, day, job))
            result = rhythm_engine.summary(server, service, day)
            saved = self.sql("SELECT body FROM growth_items WHERE id=?", (result["item_ids"][0],))[0]
            self.assertNotIn(f"- {job}: running", saved["body"])

    def test_research_rights_missing_makes_no_network_request_or_retained_result(self):
        self.configure("bim")
        with patch.dict(os.environ, {"BRAVE_SEARCH_STORAGE_ALLOWED": "0"}), patch.object(provider_search, "request_json") as search:
            rhythm_engine.tick(server, self.instant, phase="research")
            search.assert_not_called()
        states = self.sql("SELECT state FROM agent_jobs")
        self.assertTrue(all(r["state"] == "needs_input" for r in states))
        self.assertEqual(self.sql("SELECT * FROM research_snapshots"), [])

    def test_research_respects_search_cap_and_records_actual_brave_usage(self):
        self.configure("bim")
        with patch.dict(os.environ, {"VOXEL1_MONTHLY_SEARCH_LIMIT": "1"}), patch.object(provider_search, "request_json", return_value={"web": {"results": []}}) as search:
            rhythm_engine.tick(server, self.instant, phase="research")
            self.assertEqual(search.call_count, 1)
        states = {r["state"] for r in self.sql("SELECT state FROM agent_jobs")}
        self.assertEqual(states, {"needs_review", "needs_budget"})
        with closing(server.connect()) as db:
            status = server.budget_status(db)
        self.assertEqual((status["used"]["brave"], status["searches_used"]), (1, 1))

    def test_pause_and_future_schedule_start_no_jobs(self):
        self.configure("bim")
        self.sql("UPDATE growth_settings SET paused=1 WHERE service='global'")
        with patch.object(draft_outputs, "generate") as generate, patch.object(provider_search, "request_json") as search:
            rhythm_engine.tick(server, self.instant, phase="research")
            rhythm_engine.tick(server, self.instant)
            generate.assert_not_called()
            search.assert_not_called()
        self.assertEqual(self.sql("SELECT * FROM agent_jobs"), [])

    def test_missing_partner_and_customer_are_explicit_not_invented(self):
        lead, sent = self.configure("bim")
        self.sql("UPDATE growth_leads SET stage='new'")
        config = json.loads(self.sql("SELECT config FROM agent_campaigns")[0]["config"])
        config.update(partner_accounts="", existing_clients="")
        with self.assertRaises(rhythm_engine.MissingInput):
            rhythm_engine.partner(server, "bim", config, "2026-10-15")
        with self.assertRaises(rhythm_engine.MissingInput):
            rhythm_engine.clients(server, "bim", config, "2026-10-15")

    def test_disabled_partner_activity_needs_no_partner_or_provider_call(self):
        self.configure("bim")
        config = json.loads(self.sql("SELECT config FROM agent_campaigns WHERE service='bim'")[0]["config"])
        config.update(partner_enabled=False, partner_accounts="", accept_budget=True)
        with closing(server.connect()) as db, db:
            saved = automation.save(server, db, "bim", config)
        self.assertIs(saved["partner_enabled"], False)
        with patch.object(draft_outputs, "generate") as generate:
            result = rhythm_engine.partner(server, "bim", saved, "2026-10-15")
        self.assertTrue(result["no_action"])
        generate.assert_not_called()

    def test_approved_unsent_message_does_not_trigger_followup(self):
        lead, sent = self.configure("bim")
        self.sql("UPDATE growth_items SET state='approved'")
        self.sql("UPDATE growth_leads SET stage='new'")
        config = json.loads(self.sql("SELECT config FROM agent_campaigns")[0]["config"])
        with patch.object(draft_outputs, "generate") as generate:
            result = rhythm_engine.followups(server, "bim", config, "2026-10-15")
            self.assertTrue(result["no_action"])
            generate.assert_not_called()

    def test_graphic_is_original_svg_and_escapes_untrusted_text(self):
        svg = draft_outputs.graphic_svg('</text><script>alert(1)</script>', 'A & B <image href="https://evil.test"/>')
        root = ET.fromstring(svg)
        self.assertEqual(root.attrib["width"], "1080")
        self.assertNotIn("<script", svg)
        self.assertNotIn("<image", svg)
        self.assertIn("&amp;", svg)

    def test_sixty_named_accounts_are_batched_within_query_and_budget_limits(self):
        self.configure("bim")
        config = json.loads(self.sql("SELECT config FROM agent_campaigns")[0]["config"])
        config["target_accounts"] = "\n".join(f"Company {n}" for n in range(60))
        with patch.object(provider_search, "request_json", return_value={"web": {"results": []}}) as search:
            result = rhythm_engine.research(server, "bim", config, "2026-10-15", "awards")
            self.assertEqual(search.call_count, 12)
            for call in search.call_args_list:
                query = call.args[3]["q"]
                self.assertLessEqual(len(query), 600)
                self.assertLessEqual(len(query.split()), 75)
        self.assertIn("60 of 60", result["message"])
        with closing(server.connect()) as db:
            self.assertEqual(server.budget_status(db)["used"]["brave"], 12)

    def test_saving_resolved_inputs_releases_blocked_slots_but_not_completed_work(self):
        self.configure("bim")
        today = datetime.now(timezone.utc).astimezone(growth.IST).replace(hour=19, minute=0)
        day = today.date().isoformat()
        automation.claim(server, "bim", day, "already-completed")
        automation.finish(server, "bim", day, "already-completed", "done", {"message": "Preserve this result"})
        with patch.dict(os.environ, {"BRAVE_SEARCH_STORAGE_ALLOWED": "0"}):
            rhythm_engine.tick(server, today, phase="research")
        config = json.loads(self.sql("SELECT config FROM agent_campaigns")[0]["config"])
        config["accept_budget"] = True
        with closing(server.connect()) as db, db:
            automation.save(server, db, "bim", config)
        with patch.object(provider_search, "request_json", return_value={"web": {"results": []}}) as search:
            rhythm_engine.tick(server, today, phase="research")
            self.assertEqual(search.call_count, 2)
        self.assertEqual(self.sql("SELECT state FROM agent_jobs WHERE job='already-completed'")[0]["state"], "done")


if __name__ == "__main__":
    unittest.main()
