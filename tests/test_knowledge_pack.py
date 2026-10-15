"""Knowledge pack: sourced facts reach every BIM draft prompt; held and withdrawn facts never do."""
import copy
import gc
import io
import json
import os
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

import ai_draft
import automation
import draft_outputs
import growth
import knowledge
import rhythm_engine
import server



def gemini_reply(answer):
    response = {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]}
    return io.BytesIO(json.dumps(response).encode())


class KnowledgePackTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(server, "DB_PATH", Path(self.temp.name) / "test.db"),
                        patch.dict(os.environ, {"GEMINI_API_KEY": "test", "VOXEL1_MONTHLY_GEMINI_REQUESTS": "50"})]
        for p in self.patches:
            p.start()
        server.init_db()
        with closing(server.connect()) as db, db:
            self.lead = growth.add_company(db, server.run, {"service": "bim", "company": "Example Contracting", "website": "https://example.test",
                                                            "email": "a@example.test", "country": "Saudi Arabia"}, server.log_event)
            server.run(db, "UPDATE leads SET ai_screened=1 WHERE id=?", (self.lead["id"],))
            self.config = {"objective": "Scan-to-BIM in Saudi Arabia", "start": "2026-10-01", "end": "", "search_time": "06:00", "draft_time": "09:00",
                           "accept_budget": True, "service_focus": "Scan-to-BIM",
                           "targeting": {"name": "BIM", "countries": ["Saudi Arabia"], "categories": ["engineering"]}}
            automation.save(server, db, "bim", self.config)

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        knowledge._cache.clear()
        gc.collect()
        self.temp.cleanup()

    def lead_row(self):
        with closing(server.connect()) as db:
            return dict(server.run(db, "SELECT * FROM leads WHERE id=?", (self.lead["id"],)).fetchone())

    def assert_no_held_facts(self, text):
        held = [f["text"] for f in knowledge.load("bim")["facts"] if not f["use"]]
        self.assertTrue(held)
        for fact in held:
            self.assertNotIn(fact, text)
        # Distinctive details of held facts must not appear in any form either.
        for marker in ("stadium", "concert hall", "hospital", "Mumbai", "Hyderabad", "Bengaluru", "8,000-seat"):
            self.assertNotIn(marker, text, marker)

    def test_pack_is_sourced_and_lists_missing_facts(self):
        pack = knowledge.load("bim")
        for fact in pack["facts"]:
            self.assertIn(fact["status"], ("website_published", "owner_approved", "withdrawn"), fact["id"])
            self.assertTrue(fact["source"].startswith("https://voxel1.com/"), fact["id"])
            if not fact["use"]:
                self.assertTrue(fact.get("hold_reason"), fact["id"])  # Every held fact says why.
        self.assertTrue(any(m["id"] == "scan_capture" and m["priority"] == "high" for m in pack["missing"]))
        self.assertIsNone(knowledge.load("training"))  # No Training pack yet: nothing is invented.

    def test_held_facts_never_selected_for_any_draft(self):
        for use in ("outreach", "post", "room"):
            for focus in ("", "Scan-to-BIM", "portfolio, testimonial, location, gcc"):
                facts = knowledge.facts_for("bim", use, focus)
                self.assertTrue(facts)
                self.assert_no_held_facts(" ".join(facts))
        self.assertEqual(knowledge.facts_for("training", "outreach"), [])

    def test_focus_puts_matching_capabilities_first(self):
        facts = knowledge.facts_for("bim", "outreach", "Scan-to-BIM")
        self.assertIn("Scan to BIM", facts[0])
        self.assertLessEqual(len(facts), knowledge.LIMIT)

    def test_withdrawn_fact_is_not_used(self):
        pack = copy.deepcopy(knowledge.load("bim"))
        for fact in pack["facts"]:
            if fact["id"] == "engagement_nda_scope":
                fact["status"] = "withdrawn"
        with patch.dict(knowledge._cache, {"bim": pack}):
            self.assertFalse(any("NDA" in f for f in knowledge.facts_for("bim", "outreach")))

    def test_email_prompt_carries_pack_facts_and_rules(self):
        answer = {"subject": "Scan-to-BIM support", "body": "Hello,\n\nWould a short Scan-to-BIM call help?\n\nThe Voxel1 team"}
        with patch("urllib.request.urlopen", return_value=gemini_reply(answer)) as urlopen:
            draft = ai_draft.write_draft(self.lead_row(), "bim", "First contact", service_focus="Scan-to-BIM")
        prompt = json.loads(urlopen.call_args.args[0].data)["contents"][0]["parts"][0]["text"]
        self.assertIn("voxel1_company_facts", prompt)
        self.assertIn("Scan to BIM and CAD to BIM", prompt)
        self.assertIn("only statements you may make about Voxel1", prompt)
        self.assert_no_held_facts(prompt)
        self.assertEqual(draft["knowledge_pack"], knowledge.version("bim"))

    def test_training_email_prompt_has_no_pack(self):
        answer = {"subject": "BIM training", "body": "Hello,\n\nWould a short call help?\n\nThe Voxel1 team"}
        with patch("urllib.request.urlopen", return_value=gemini_reply(answer)) as urlopen:
            draft = ai_draft.write_draft({**self.lead_row(), "service": "training"}, "training", "First contact")
        prompt = json.loads(urlopen.call_args.args[0].data)["contents"][0]["parts"][0]["text"]
        self.assertNotIn("voxel1_company_facts", prompt)
        self.assertEqual(draft["knowledge_pack"], "")

    def test_rhythm_message_and_post_prompts_carry_pack(self):
        answer = {"title": "Scan-to-BIM", "body": "A short Scan-to-BIM note."}
        lead = rhythm_engine.leads(server, "bim")[0]
        with patch("urllib.request.urlopen", return_value=gemini_reply(answer)) as urlopen:
            item = rhythm_engine.message(server, "bim", self.config, "2026-10-15", lead, "linkedin_message", "LinkedIn", "First contact")
        prompt = json.loads(urlopen.call_args.args[0].data)["contents"][0]["parts"][0]["text"]
        self.assertIn("voxel1_company_facts", prompt)
        self.assert_no_held_facts(prompt)
        self.assertEqual(item["state"], "pending")
        with patch("urllib.request.urlopen", return_value=gemini_reply(answer)) as urlopen:
            post = draft_outputs.create(server, "bim", "linkedin", day="2026-10-15")
        prompt = json.loads(urlopen.call_args.args[0].data)["contents"][0]["parts"][0]["text"]
        self.assertIn("voxel1_company_facts", prompt)
        self.assertNotIn("Example Contracting", prompt)  # Public posts never see lead data.
        self.assert_no_held_facts(prompt)
        self.assertEqual(post["state"], "pending")

    def test_room_gets_pack_without_changing_its_fingerprint(self):
        with closing(server.connect()) as db:
            lead = server.run(db, "SELECT * FROM leads WHERE id=?", (self.lead["id"],)).fetchone()
            facts, digest, _, _ = draft_outputs.room_context(server, db, lead, "bim", "2026-10-15")
            self.assertTrue(facts["voxel1_company_facts"])
            with patch.object(knowledge, "facts_for", return_value=["A different pack version."]):
                _, digest_after_pack_change, _, _ = draft_outputs.room_context(server, db, lead, "bim", "2026-10-15")
        self.assertEqual(digest, digest_after_pack_change)  # A pack update must not trigger mass room redrafts.

    def test_drafts_record_pack_version_and_stay_pending(self):
        answer = {"subject": "Scan-to-BIM support", "body": "Hello,\n\nWould a short Scan-to-BIM call help?\n\nThe Voxel1 team"}
        with patch("urllib.request.urlopen", return_value=gemini_reply(answer)):
            item = server.ai_draft_lead("bim", self.lead["id"], {"purpose": "First contact"})
        self.assertEqual(item["state"], "pending")
        with closing(server.connect()) as db:
            detail = json.loads(server.run(db, "SELECT detail FROM growth_events WHERE event='ai_drafted'").fetchone()["detail"])
        self.assertEqual(detail["knowledge_pack"], knowledge.version("bim"))

    def test_snapshot_reports_missing_facts_without_held_text(self):
        summary = knowledge.summary("bim")
        self.assertEqual(summary["version"], knowledge.version("bim"))
        self.assertGreater(summary["held"], 0)
        self.assertTrue(summary["missing"])
        self.assert_no_held_facts(json.dumps(summary))
        self.assertEqual(knowledge.summary("training")["version"], "")


if __name__ == "__main__":
    unittest.main()
