"""Regressions for the live-verification report, section F (H1-H3, M1-M4, M6, L5)."""
import gc
import io
import json
import os
import re
import tempfile
import unittest
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import ai_draft
import automation
import draft_outputs
import growth
import provider_search
import rhythm_engine
import server

GOOD = {"title": "Scan-to-BIM support", "body": "Hello,\n\nWould a short call about Scan-to-BIM be useful?\n\nThe Voxel1 team", "model": "test-model"}
SCREENING = "Holds an ISO 19650 certification and is expanding its digital team."


class AuditFixesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(server, "DB_PATH", Path(self.temp.name) / "test.db"),
                        patch.dict(os.environ, {"GEMINI_API_KEY": "test", "VOXEL1_MONTHLY_GEMINI_REQUESTS": "50"})]
        for p in self.patches:
            p.start()
        server.init_db()
        with closing(server.connect()) as db, db:
            self.lead = growth.add_company(db, server.run, {"service": "bim", "company": "Dar Example", "website": "https://www.dar.com.sa",
                                                            "email": "ahmed@othergroup.com", "country": "Saudi Arabia"}, server.log_event)
            server.run(db, "UPDATE leads SET ai_screened=1, ai_reason=?, contact_name='Ahmed Ali', contact_title='BIM Manager' WHERE id=?",
                       (SCREENING, self.lead["id"]))
            self.config = {"objective": "Sell Scan-to-BIM", "start": "2026-10-01", "end": "", "search_time": "06:00", "draft_time": "09:00",
                           "accept_budget": True, "targeting": {"name": "BIM", "countries": ["Saudi Arabia"], "categories": ["engineering"],
                                                                "keywords": "BIM coordination, Revit modelling"},
                           "service_focus": "Scan-to-BIM"}
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

    def lead_row(self):
        return self.sql("SELECT * FROM leads WHERE id=?", (self.lead["id"],))[0]

    # F-H3 ---------------------------------------------------------------
    def test_outbound_facts_omit_screening_note_and_carry_service_focus(self):
        facts = ai_draft.lead_facts(self.lead_row(), "bim", "", [], ai_draft.campaign_focus(self.config))
        self.assertNotIn(SCREENING, json.dumps(facts))
        self.assertEqual(facts["campaign_service_focus"], "Scan-to-BIM")

    def test_write_draft_prompt_has_focus_but_not_screening_note(self):
        answer = {"subject": "Scan-to-BIM", "body": "Hello,\n\nWould a call about Scan-to-BIM help?\n\nThe Voxel1 team"}
        response = {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]}
        with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as urlopen:
            ai_draft.write_draft(self.lead_row(), "bim", "First contact", service_focus="Scan-to-BIM")
        prompt = json.loads(urlopen.call_args.args[0].data)["contents"][0]["parts"][0]["text"]
        self.assertNotIn(SCREENING, prompt)
        self.assertIn("Scan-to-BIM", prompt)

    def test_outbound_prompts_mark_strategy_as_internal(self):
        # Live WhatsApp draft told a prospect Voxel1 would "help win repeat work" (the default BIM strategy).
        strategy = "Find project teams that need BIM delivery support, and win repeat work from each client."
        def prompt_for(call):
            response = {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]}
            with patch("urllib.request.urlopen", return_value=io.BytesIO(json.dumps(response).encode())) as urlopen:
                call()
            return json.loads(urlopen.call_args.args[0].data)["contents"][0]["parts"][0]["text"]
        answer = {"title": "Hi", "body": "Would a call about Scan-to-BIM help?"}
        for kind in ("linkedin_message", "whatsapp_message", "partner"):
            self.assertIn(ai_draft.INTERNAL_GUIDANCE, prompt_for(lambda: draft_outputs.generate(kind, "bim", {"campaign_service_focus": "Scan-to-BIM"}, strategy)))
        # Public posts and internal rooms keep their own wording.
        self.assertNotIn(ai_draft.INTERNAL_GUIDANCE, prompt_for(lambda: draft_outputs.generate("room", "bim", {}, strategy)))
        answer = {"subject": "Scan-to-BIM", "body": "Hello,\n\nWould a call about Scan-to-BIM help?\n\nThe Voxel1 team"}
        self.assertIn(ai_draft.INTERNAL_GUIDANCE, prompt_for(lambda: ai_draft.write_draft(self.lead_row(), "bim", "First contact", guidance=strategy, service_focus="Scan-to-BIM")))

    def test_service_focus_in_title_alone_cannot_pass_email_or_channel_drafts(self):
        def reply(answer):
            return io.BytesIO(json.dumps({"candidates": [{"finishReason": "STOP", "content": {"parts": [{"text": json.dumps(answer)}]}}]}).encode())
        body = "Hello, would a short call about our services help?"
        with patch("urllib.request.urlopen", return_value=reply({"subject":"Scan-to-BIM", "body":body})), self.assertRaisesRegex(provider_search.ProviderError, "service focus"):
            ai_draft.write_draft(self.lead_row(), "bim", "First contact", service_focus="Scan-to-BIM")
        for kind in ("linkedin_message", "whatsapp_message", "partner", "academic", "followup", "cross_sell"):
            with self.subTest(kind=kind), patch("urllib.request.urlopen", return_value=reply({"title":"Scan-to-BIM", "body":body})), self.assertRaisesRegex(provider_search.ProviderError, "service focus"):
                draft_outputs.generate(kind, "bim", {"campaign_service_focus":"Scan-to-BIM"}, "")

    def test_draft_missing_service_focus_is_discarded(self):
        # Regression: Scan-to-BIM was requested in the prompt but never checked in the output.
        def reply(answer):
            response = {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]}
            return io.BytesIO(json.dumps(response).encode())
        generic = {"subject": "BIM delivery support", "body": "Hello,\n\nWe offer BIM modelling. Would a short call help?\n\nThe Voxel1 team"}
        with patch("urllib.request.urlopen", return_value=reply(generic)), self.assertRaisesRegex(server.provider_search.ProviderError, "service focus"):
            ai_draft.write_draft(self.lead_row(), "bim", "First contact", service_focus="Scan-to-BIM, point cloud")
        spaced = {"subject": "Scan to BIM support", "body": "Hello,\n\nWould a short call about Scan to BIM help?\n\nThe Voxel1 team"}
        with patch("urllib.request.urlopen", return_value=reply(spaced)):
            self.assertEqual(ai_draft.write_draft(self.lead_row(), "bim", "First contact", service_focus="Scan-to-BIM")["title"], "Scan to BIM support")
        message = {"title": "Hello", "body": "Would a call about BIM modelling help?"}
        facts = {"company": "Dar Example", "campaign_service_focus": "Scan-to-BIM"}
        with patch("urllib.request.urlopen", return_value=reply(message)), self.assertRaisesRegex(server.provider_search.ProviderError, "service focus"):
            draft_outputs.generate("linkedin_message", "bim", facts, "")
        # Internal call preparation is exempt.
        with patch("urllib.request.urlopen", return_value=reply(message)):
            self.assertEqual(draft_outputs.generate("proposal", "bim", facts, "")["title"], "Hello")

    def test_generic_search_keyword_cannot_satisfy_required_focus(self):
        # Reproduced case: search keywords "Scan-to-BIM, BIM coordination" served as the focus,
        # so a draft about generic "BIM coordination" passed a Scan-to-BIM campaign.
        def reply(answer):
            response = {"candidates": [{"content": {"parts": [{"text": json.dumps(answer)}]}}]}
            return io.BytesIO(json.dumps(response).encode())
        config = {**self.config, "targeting": {**self.config["targeting"], "keywords": "Scan-to-BIM, BIM coordination"}, "service_focus": "Scan-to-BIM"}
        with closing(server.connect()) as db, db:
            saved = automation.save(server, db, "bim", config)
        self.assertEqual((saved["service_focus"], saved["targeting"]["keywords"]), ("Scan-to-BIM", "Scan-to-BIM, BIM coordination"))
        focus = ai_draft.campaign_focus(saved)
        self.assertEqual(focus, "Scan-to-BIM")
        generic = {"subject": "BIM coordination support", "body": "Hello,\n\nWould a call about BIM coordination help?\n\nThe Voxel1 team"}
        with patch("urllib.request.urlopen", return_value=reply(generic)), self.assertRaisesRegex(server.provider_search.ProviderError, "service focus"):
            ai_draft.write_draft(self.lead_row(), "bim", "First contact", service_focus=focus)
        with patch("urllib.request.urlopen", return_value=reply({"title": "Hi", "body": "Our BIM coordination team can help."})), \
             self.assertRaisesRegex(server.provider_search.ProviderError, "service focus"):
            draft_outputs.generate("whatsapp_message", "bim", {"campaign_service_focus": focus}, "")
        # Search keywords alone never become a drafting requirement.
        self.assertEqual(ai_draft.campaign_focus({"targeting": {"keywords": "Scan-to-BIM, BIM coordination"}}), "")
        # Several required phrases must all appear; one is not enough.
        self.assertTrue(ai_draft.focus_missing("Scan-to-BIM support", "Scan-to-BIM, point cloud"))
        self.assertFalse(ai_draft.focus_missing("Scan to BIM from point-cloud surveys", "Scan-to-BIM, point cloud"))
        self.assertTrue(ai_draft.focus_missing("BIM support", "Scan-to-BIM"))
        # Saving without the field keeps the earlier focus; clearing it removes the requirement.
        with closing(server.connect()) as db, db:
            kept = automation.save(server, db, "bim", {k: v for k, v in config.items() if k != "service_focus"})
            cleared = automation.save(server, db, "bim", {**config, "service_focus": ""})
        self.assertEqual((kept["service_focus"], cleared["service_focus"]), ("Scan-to-BIM", ""))

    def test_scheduled_email_draft_gets_campaign_keywords(self):
        with patch.object(ai_draft, "write_draft", return_value=GOOD) as write:
            server.ai_draft_lead("bim", self.lead["id"], {"purpose": "First contact"})
        self.assertEqual(write.call_args.args[6], "Scan-to-BIM")

    def test_rhythm_messages_get_focus_without_screening_note(self):
        lead = rhythm_engine.leads(server, "bim")[0]
        with patch.object(draft_outputs, "generate", return_value=GOOD) as generate:
            rhythm_engine.message(server, "bim", self.config, "2026-10-15", lead, "linkedin_message", "LinkedIn", "First contact")
        facts = generate.call_args.args[2]
        self.assertNotIn(SCREENING, json.dumps(facts))
        self.assertEqual(facts["campaign_service_focus"], "Scan-to-BIM")

    # F-H2 ---------------------------------------------------------------
    def test_contact_domain_mismatch(self):
        cases = [("a@dar.com.sa", "https://www.dar.com.sa", False), ("a@mail.dar.com.sa", "dar.com.sa", False),
                 ("a@example.co.uk", "https://example.co.uk/about", False), ("a@othergroup.com", "https://www.dar.com.sa", True),
                 ("a@dar.com", "https://dar.com.sa", True), ("", "https://dar.com.sa", False), ("a@dar.com", "", False)]
        for email, website, expected in cases:
            self.assertEqual(ai_draft.contact_domain_mismatch({"email": email, "website": website}), expected, (email, website))

    def test_shared_domain_prefix_does_not_imply_affiliation(self):
        # Reproduced case: a name prefix was treated as proof of a group company, so an
        # unrelated firm's contact (acme.com at acmesteelworks.com) was named in drafts.
        cases = [("a@acme.com", "http://www.acmesteelworks.com", True),
                 ("a@khansaheb.com", "http://www.khansahebcivilengineering.com", True),
                 ("a@darengineering.com", "http://www.dar.com", True),
                 ("a@el-seif.com.sa", "http://www.el-seif.com.sa", False),
                 ("a@mail.el-seif.com.sa", "https://el-seif.com.sa", False),
                 ("a@afdb.org", "http://www.dar-engineering.com", True),
                 ("a@gmail.com", "http://www.gmailer-consult.com", True)]
        for email, website, expected in cases:
            self.assertEqual(ai_draft.contact_domain_mismatch({"email": email, "website": website}), expected, (email, website))
        lead = {**self.lead_row(), "email": "ahmed@acme.com", "website": "http://www.acmesteelworks.com"}
        facts = ai_draft.lead_facts(lead, "bim", "", [])
        self.assertNotIn("contact_name", facts)
        self.assertNotIn("contact_title", facts)

    def test_browser_domain_check_mirrors_server(self):
        import shutil, subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node is not installed")
        source = (Path(server.ROOT) / "web" / "app.js").read_text(encoding="utf-8")
        start = source.index("const FREE_MAIL")
        end = source.index("const esc =")
        cases = [["a@khansaheb.com", "http://www.khansahebcivilengineering.com"], ["a@acme.com", "http://www.acmesteelworks.com"],
                 ["a@el-seif.com.sa", "http://www.el-seif.com.sa"], ["a@afdb.org", "http://www.dar-engineering.com"],
                 ["a@gmail.com", "http://www.gmailer-consult.com"], ["a@mail.dar.com.sa", "dar.com.sa"], ["a@dar.com", "http://www.darengineering.com"]]
        script = source[start:end] + f"\nconsole.log(JSON.stringify({json.dumps(cases)}.map(([email, website]) => domainMismatch({{email, website}}))));"
        result = json.loads(subprocess.run([node, "-e", script], capture_output=True, text=True, check=True).stdout)
        self.assertEqual(result, [ai_draft.contact_domain_mismatch({"email": e, "website": w}) for e, w in cases])

    def test_mismatched_contact_is_not_named_in_drafts(self):
        facts = ai_draft.lead_facts(self.lead_row(), "bim", "", [])
        self.assertNotIn("contact_name", facts)
        self.assertNotIn("contact_title", facts)
        matched = {**self.lead_row(), "email": "ahmed@dar.com.sa"}
        self.assertEqual(ai_draft.lead_facts(matched, "bim", "", [])["contact_name"], "Ahmed Ali")

    # F-M1 ---------------------------------------------------------------
    def research(self, day, hits):
        self.sql("INSERT INTO research_snapshots (id, service, day, kind, query, findings) VALUES (?, 'bim', ?, 'awards', 'q', ?)",
                 (f"bim:{day}", day, json.dumps(hits)))

    def apply_latest_room(self):
        item = self.sql("SELECT * FROM growth_items WHERE kind='room' AND state='pending'")[0]
        with closing(server.connect()) as db, db:
            item = growth.save_item(db, server.run, item["id"], {"action": "approve", "revision": item["revision"]})
            current = server.run(db, "SELECT updated_at FROM growth_leads WHERE lead_id=?", (self.lead["id"],)).fetchone()
            draft_outputs.apply_room(db, server.run, {"item_id": item["id"], "revision": item["revision"],
                                                      "room_updated_at": current["updated_at"] if current else ""})

    def test_applied_room_is_not_redrafted_daily_as_search_hits_change(self):
        hit_a = {"url": "https://news.test/a", "title": "Dar Example wins award", "excerpt": "Dar Example project"}
        hit_b = {"url": "https://news.test/b", "title": "Dar Example tender", "excerpt": "Dar Example hiring"}
        noise = {"url": "https://news.test/z", "title": "Unrelated", "excerpt": "Other firm"}
        days = {"2026-10-15": [hit_a], "2026-10-16": [hit_a, noise], "2026-10-17": [], "2026-10-18": [noise]}
        drafts = 0
        for day, hits in days.items():
            self.research(day, hits)
            if draft_outputs.room_candidates(server, "bim", day):
                with patch.object(draft_outputs, "generate", return_value=GOOD):
                    draft_outputs.create(server, "bim", "room", self.lead["id"], day=day)
                drafts += 1
                self.apply_latest_room()
        self.assertEqual(drafts, 1)
        # A genuinely new lead-specific signal prompts a refresh, but not within 7 days of the last draft.
        self.research("2026-10-19", [hit_a, hit_b])
        self.assertEqual(draft_outputs.room_candidates(server, "bim", "2026-10-19"), [])
        self.research("2026-10-22", [hit_a, hit_b])
        self.assertEqual([c["id"] for c in draft_outputs.room_candidates(server, "bim", "2026-10-22")], [self.lead["id"]])

    def test_new_search_urls_refresh_room_at_most_weekly(self):
        # Regression: a new unverified URL every day redrafted the room every day.
        drafts = []
        for n in range(15):
            day = f"2026-10-{15 + n:02d}"
            self.research(day, [{"url": f"https://news.test/{n}", "title": f"Dar Example update {n}", "excerpt": "Dar Example"}])
            if draft_outputs.room_candidates(server, "bim", day):
                with patch.object(draft_outputs, "generate", return_value=GOOD):
                    draft_outputs.create(server, "bim", "room", self.lead["id"], day=day)
                drafts.append(day)
                self.apply_latest_room()
        self.assertEqual(drafts, ["2026-10-15", "2026-10-22", "2026-10-29"])

    def test_team_update_refreshes_room_without_waiting(self):
        self.research("2026-10-15", [])
        with patch.object(draft_outputs, "generate", return_value=GOOD):
            draft_outputs.create(server, "bim", "room", self.lead["id"], day="2026-10-15")
        self.apply_latest_room()
        with closing(server.connect()) as db, db:
            growth.save_lead(db, server.run, self.lead["id"], {"service": "bim", "stage": "meeting", "owner": "", "room_notes": "Met the BIM team"})
        self.assertEqual([c["id"] for c in draft_outputs.room_candidates(server, "bim", "2026-10-16")], [self.lead["id"]])

    def test_legacy_room_digest_does_not_trigger_mass_redraft(self):
        self.sql("INSERT INTO growth_events (service, item_id, lead_id, event, detail, created_at) VALUES ('bim', NULL, ?, 'ai_output_drafted', ?, 'x')",
                 (self.lead["id"], json.dumps({"kind": "room", "context_digest": "old-scheme"})))
        self.assertEqual(draft_outputs.room_candidates(server, "bim", "2026-10-15"), [])
        with closing(server.connect()) as db, db:
            growth.save_lead(db, server.run, self.lead["id"], {"service": "bim", "stage": "meeting", "owner": "", "room_notes": ""})
        self.assertEqual(len(draft_outputs.room_candidates(server, "bim", "2026-10-15")), 1)

    # F-M2 ---------------------------------------------------------------
    def assert_fits(self, svg):
        for size, weight, text in re.findall(r'font-size="(\d+)" font-weight="(\d+)"[^>]*>([^<]*)</text>', svg):
            right = draft_outputs.TEXT_LEFT + draft_outputs.text_width(text.replace("&amp;", "&"), int(size), weight == "700")
            self.assertLessEqual(right, 1080 - 88, text)

    def test_graphic_headline_fits_width_and_marks_truncation(self):
        upper = "SCAN TO BIM FOR HERITAGE " * 6
        svg = draft_outputs.graphic_svg(upper, "Body " * 100)
        self.assert_fits(svg)
        headings = re.findall(r'font-weight="700" fill="#FFFFFF">([^<]*)</text>', svg)
        self.assertEqual(len(headings), 4)
        self.assertTrue(headings[-1].endswith("…"))
        self.assertTrue(re.findall(r'font-size="34"[^>]*>([^<]*)</text>', svg)[-1].endswith("…"))
        # A single 25-character all-caps/wide word used to overflow at x=1090.
        self.assert_fits(draft_outputs.graphic_svg("W" * 25, "Short body."))
        self.assert_fits(draft_outputs.graphic_svg("ＢＩＭ設計支援サービス" * 3, "全角テキスト" * 20))
        self.assertGreater(draft_outputs.text_width("MMMMMMMMMMMMMMMMMMMMMMMMM", 62, True), 1090 - 88)

    def test_short_graphic_text_is_unchanged(self):
        svg = draft_outputs.graphic_svg("BIM basics", "One paragraph.")
        self.assertIn(">BIM basics</text>", svg)
        self.assertNotIn("…", svg)

    # F-M3 ---------------------------------------------------------------
    def test_recorded_sent_outreach_cannot_be_reopened_or_edited(self):
        with closing(server.connect()) as db, db:
            item = growth.save_item(db, server.run, None, {"service": "bim", "kind": "outreach", "lead_id": self.lead["id"],
                                                          "title": "Hello", "body": "Text", "channel": "Email", "label": "First contact"})
            item = growth.save_item(db, server.run, item["id"], {"action": "approve", "revision": item["revision"]})
            item = growth.save_item(db, server.run, item["id"], {"action": "complete", "revision": item["revision"]})
        self.assertEqual(item["state"], "done")
        for payload in ({"action": "reopen"}, {"title": "Changed", "body": "Changed", "channel": "Email", "label": "First contact"}):
            with self.assertRaises(ValueError):
                with closing(server.connect()) as db, db:
                    growth.save_item(db, server.run, item["id"], {**payload, "revision": item["revision"]})
        self.assertEqual(self.sql("SELECT state, title FROM growth_items WHERE id=?", (item["id"],)), [{"state": "done", "title": "Hello"}])

    def test_ui_hides_reopen_for_recorded_sent_outreach(self):
        source = (Path(server.ROOT) / "web" / "app.js").read_text(encoding="utf-8")
        self.assertIn('} else if (i.kind === "outreach" && i.state === "done") {', source)

    # F-M4 ---------------------------------------------------------------
    def test_missing_input_is_needs_input_not_needs_you(self):
        config = {**self.config, "full_rhythm": True, "content_targets": {"LinkedIn": 1}, "goal": 4, "quarter": "2026-Q4"}
        with closing(server.connect()) as db, db:
            automation.save(server, db, "bim", config)
        quiet = {"message": "ok"}
        blocked = rhythm_engine.MissingInput("Research needs a Brave plan granting result-storage rights.")
        with patch.object(rhythm_engine, "research", side_effect=blocked),              patch.multiple(rhythm_engine, mapping=lambda *a: quiet, outreach=lambda *a: quiet, followups=lambda *a: quiet,
                            clients=lambda *a: quiet, partner=lambda *a, **k: quiet),              patch.object(draft_outputs, "create", return_value={"id": 99}):
            rhythm_engine.tick(server, datetime(2026, 10, 15, 14, tzinfo=timezone.utc), phase="drafts")
        states = {r["job"]: r["state"] for r in self.sql("SELECT job, state FROM agent_jobs WHERE service='bim'")}
        self.assertEqual(states["rhythm:8"], "needs_input")  # social drafts ready; consented proof missing
        self.assertEqual(states["rhythm:9"], "needs_input")  # evening research blocked by plan rights

    def test_goal_save_does_not_rerun_jobs_that_already_saved_outputs(self):
        # Regression: needs_input slots with outputs (social drafts, daily summary) were
        # released by a Sales Goal save and re-run, duplicating the daily summary.
        local = datetime.now(timezone.utc).astimezone(growth.IST)
        evening = local.replace(hour=18, minute=10, second=0, microsecond=0)
        config = {**self.config, "full_rhythm": True, "content_targets": {"LinkedIn": 1}, "goal": 4, "quarter": "2026-Q4"}
        with closing(server.connect()) as db, db:
            automation.save(server, db, "bim", config)
        blocked = rhythm_engine.MissingInput("Research needs a Brave plan granting result-storage rights.")
        with patch.object(rhythm_engine, "research", side_effect=blocked), \
             patch.object(draft_outputs, "generate", return_value=GOOD) as generate:
            rhythm_engine.tick(server, evening, phase="drafts")
            summaries = lambda: len(self.sql("SELECT id FROM growth_items WHERE service='bim' AND label='Daily summary'"))
            calls = generate.call_count
            self.assertEqual(summaries(), 1)
            states = {r["job"]: r["state"] for r in self.sql("SELECT job, state FROM agent_jobs WHERE service='bim'")}
            self.assertEqual((states["rhythm:8"], states["rhythm:9"], states["rhythm:5"]), ("needs_input", "needs_input", "needs_input"))
            with closing(server.connect()) as db, db:
                automation.save(server, db, "bim", {**config, "strategy": "Edited strategy"})
            states = {r["job"]: r["state"] for r in self.sql("SELECT job, state FROM agent_jobs WHERE service='bim'")}
            # Jobs with saved outputs stay put; a blocked job with no output is still released.
            self.assertEqual((states["rhythm:8"], states["rhythm:9"], states["rhythm:5"]), ("needs_input", "needs_input", "retry_ready"))
            rhythm_engine.tick(server, evening.replace(minute=20), phase="drafts")
            self.assertEqual(summaries(), 1)
            self.assertEqual(generate.call_count, calls)

    def test_provider_failure_in_social_is_still_needs_you(self):
        config = {**self.config, "content_targets": {"LinkedIn": 1}, "approved_proof": "x", "proof_consent": True}
        with patch.object(draft_outputs, "create", side_effect=OSError("down")), self.assertLogs(level="ERROR"):
            result = rhythm_engine.social(server, "bim", config, "2026-10-15")
        self.assertTrue(result["partial"])
        self.assertFalse(result["input_needed"])

    def test_reused_draft_is_not_reported_as_drafted(self):
        config = {**self.config, "partner_accounts": "Dar Example"}
        with patch.object(draft_outputs, "generate", return_value=GOOD) as generate:
            first = rhythm_engine.partner(server, "bim", config, "2026-10-15")
            again = rhythm_engine.partner(server, "bim", config, "2026-10-16")
        self.assertEqual(generate.call_count, 1)
        self.assertIn("drafted", first["message"])
        self.assertEqual(again["message"], rhythm_engine.REUSED)
        self.assertEqual(again["item_ids"], first["item_ids"])

    # F-M6 ---------------------------------------------------------------
    def login_handler(self, forwarded):
        handler = object.__new__(server.Handler)
        handler.client_address = ("10.0.0.1", 1234)
        handler.headers = {"X-Forwarded-For": forwarded} if forwarded else {}
        return handler

    def test_login_limiter_uses_trusted_forwarded_hop(self):
        with patch.dict(os.environ, {"RENDER": "true"}):
            self.assertEqual(self.login_handler("203.0.113.9").client_ip(), "203.0.113.9")
            # A client-supplied spoofed entry on the left is ignored.
            self.assertEqual(self.login_handler("1.2.3.4, 203.0.113.9").client_ip(), "203.0.113.9")
            self.assertEqual(self.login_handler("").client_ip(), "10.0.0.1")
        with patch.dict(os.environ, {"RENDER": "", "VOXEL1_TRUSTED_PROXY_HOPS": ""}):
            self.assertEqual(self.login_handler("203.0.113.9").client_ip(), "10.0.0.1")  # header untrusted without a proxy

    def test_one_users_failures_do_not_lock_out_another(self):
        server.failed_logins.clear()
        def attempt(ip):
            data = json.dumps({"username": "x", "password": "wrong"}).encode()
            handler = object.__new__(server.Handler)
            handler.path, handler.client_address = "/api/login", ("10.0.0.1", 1)
            handler.headers = {"Content-Length": str(len(data)), "X-Forwarded-For": ip}
            handler.rfile, handler.wfile = io.BytesIO(data), io.BytesIO()
            handler.send_response = lambda code: setattr(handler, "response_code", code)
            handler.send_header = lambda name, value: None
            handler.end_headers = lambda: None
            handler.same_origin_write = lambda: True
            handler.do_POST()
            return handler.response_code
        with patch.dict(os.environ, {"RENDER": "true"}), patch.object(server, "AUTH_USER", "admin"), patch.object(server, "AUTH_PASSWORD", "secret"):
            codes = [attempt("198.51.100.1") for _ in range(6)]
            self.assertEqual(codes[-1], 429)
            self.assertEqual(attempt("198.51.100.2"), 401)
        server.failed_logins.clear()

    # F-L5 ---------------------------------------------------------------
    def test_briefs_cannot_be_completed(self):
        with closing(server.connect()) as db, db:
            brief = growth.save_item(db, server.run, None, {"service": "bim", "kind": "brief", "title": "Research", "body": "Notes", "label": "Research"})
            with self.assertRaises(ValueError):
                growth.save_item(db, server.run, brief["id"], {"action": "complete", "revision": brief["revision"]})
            brief = growth.save_item(db, server.run, brief["id"], {"action": "approve", "revision": brief["revision"]})
            with self.assertRaises(ValueError):
                growth.save_item(db, server.run, brief["id"], {"action": "complete", "revision": brief["revision"]})


    # F-H1 ---------------------------------------------------------------
    def test_worker_logs_traceback_and_records_heartbeat(self):
        with patch.object(automation, "tick", side_effect=RuntimeError("db exploded")), self.assertLogs(level="ERROR") as logs:
            server.worker_tick()
        self.assertIn("automation.tick", logs.output[0])
        self.assertIn("Traceback", "\n".join(logs.output))
        beat = self.sql("SELECT * FROM worker_heartbeat")[0]
        self.assertIn("db exploded", beat["last_error"])
        self.assertEqual(beat["last_ok"], "")
        with patch.object(automation, "tick"):
            server.worker_tick()
        beat = self.sql("SELECT * FROM worker_heartbeat")[0]
        self.assertTrue(beat["last_ok"])
        self.assertIn("db exploded", beat["last_error"])  # kept for diagnosis; the UI compares timestamps
        self.assertEqual(beat["last_ok"], beat["last_tick"])

    def test_failed_job_is_logged_with_context(self):
        automation.claim(server, "bim", "2026-10-15", "draft:1")
        with self.assertLogs(level="ERROR") as logs:
            try:
                raise OSError("disk")
            except OSError:
                automation.finish(server, "bim", "2026-10-15", "draft:1", "needs_you", {"message": "failed"})
        self.assertIn("draft:1", logs.output[0])
        self.assertIn("OSError: disk", logs.output[0])

    def get(self, path, authorized=True):
        handler = object.__new__(server.Handler)
        handler.path = path
        handler.headers = {}
        handler.wfile = io.BytesIO()
        handler.send_response = lambda code: setattr(handler, "response_code", code)
        handler.send_header = lambda name, value: None
        handler.end_headers = lambda: None
        handler.authorized = lambda: authorized
        handler.do_GET()
        return handler.response_code, json.loads(handler.wfile.getvalue() or b"{}")

    def test_version_endpoint_and_worker_status_in_snapshot(self):
        with patch.object(server, "_commit", "abc1234"):
            self.assertEqual(self.get("/api/version", authorized=False), (200, {"commit": "abc1234"}))
            server.record_heartbeat()
            code, snapshot = self.get("/api/growth")
        self.assertEqual(code, 200)
        self.assertEqual(snapshot["worker"]["commit"], "abc1234")
        self.assertTrue(snapshot["worker"]["last_tick"])


if __name__ == "__main__":
    unittest.main()
