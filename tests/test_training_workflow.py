"""Training fixtures exercise the full draft-only flow without real business data."""
import io
import json
import os
import unittest
from contextlib import closing
from unittest.mock import patch

import ai_draft
import automation
import draft_outputs
import provider_search
import server


class TrainingWorkflowTest(unittest.TestCase):
    def test_training_goal_to_rooms_messages_content_and_summary_is_repeatable(self):
        from test_rhythm_engine import RhythmEngineTest
        fixture = RhythmEngineTest()
        fixture.setUp()
        try:
            lead, _ = fixture.configure("training")
            fixture.sql("UPDATE leads SET contact_title='Head of Department' WHERE id=?", (lead["id"],))
            config = json.loads(fixture.sql("SELECT config FROM agent_campaigns WHERE service='training'")[0]["config"])
            config.update(objective="BIM and Revit training for college students and faculty", service_focus="BIM training", auto_rooms=True, accept_budget=True)
            with closing(server.connect()) as db, db:
                automation.save(server, db, "training", config)
            output = {"title":"BIM training discussion", "body":"Would a call about BIM training for students and faculty be useful?", "model":"fixture"}
            with patch.object(automation, "discovery", return_value={"lead_ids":[]}), \
                 patch.object(provider_search, "request_json", return_value={"web":{"results":[]}}), \
                 patch.object(draft_outputs, "generate", return_value=output) as generate, \
                 patch.object(ai_draft, "write_draft", return_value=output), \
                 patch.object(server.outlook, "send") as send:
                automation.tick(server, fixture.instant)
                count = generate.call_count
                automation.tick(server, fixture.instant)
                self.assertEqual(generate.call_count, count)
                send.assert_not_called()
            items = fixture.sql("SELECT kind,channel,state,label FROM growth_items WHERE service='training'")
            self.assertTrue(any(i["kind"] == "room" and i["state"] == "pending" for i in items))
            self.assertEqual({i["channel"] for i in items if i["kind"] == "outreach" and i["state"] == "pending"}, {"Email","LinkedIn","WhatsApp"})
            self.assertEqual({i["channel"] for i in items if i["kind"] == "content"}, {"LinkedIn","Instagram","Facebook"})
            self.assertTrue(any(i["label"] == "Daily summary" for i in items))
            self.assertEqual(fixture.sql("SELECT id FROM growth_items WHERE service='bim'"), [])
        finally:
            fixture.tearDown()

    def test_training_shared_draft_prompts_use_training_offer(self):
        answer = {"title":"BIM training", "body":"Would a brief call about BIM training be useful?"}
        reply = {"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":json.dumps(answer)}]}}]}
        for kind in ("room", "linkedin_message", "whatsapp_message", "linkedin"):
            with self.subTest(kind=kind), patch.dict(os.environ,{"GEMINI_API_KEY":"mock"}), patch.object(draft_outputs.urllib.request,"urlopen",return_value=io.BytesIO(json.dumps(reply).encode())) as opened:
                draft_outputs.generate(kind,"training",{"campaign_service_focus":"BIM training"},"")
                prompt = json.loads(opened.call_args.args[0].data)["contents"][0]["parts"][0]["text"]
                self.assertIn(ai_draft.OFFER["training"],prompt)
                self.assertNotIn("a BIM company based in India",prompt)

    def test_training_email_prompt_uses_training_offer(self):
        reply = {"candidates":[{"finishReason":"STOP","content":{"parts":[{"text":json.dumps({"subject":"BIM training", "body":"Would a brief call about BIM training be useful?"})}]}}]}
        class Response(io.BytesIO):
            def __enter__(self): return self
            def __exit__(self, *args): pass
        with patch.dict(os.environ,{"GEMINI_API_KEY":"mock"}), patch.object(ai_draft.urllib.request,"urlopen",return_value=Response(json.dumps(reply).encode())) as opened:
            ai_draft.write_draft({"company":"Example College"},"training","First contact",service_focus="BIM training")
        prompt = json.loads(opened.call_args.args[0].data)["contents"][0]["parts"][0]["text"]
        self.assertIn(ai_draft.OFFER["training"],prompt)
        self.assertNotIn("a BIM company based in India",prompt)
