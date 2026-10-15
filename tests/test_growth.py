import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import provider_search
import server
import growth
import automation
from datetime import datetime, timezone
from contextlib import closing

KEYS = {"APOLLO_API_KEY": "test", "BRAVE_SEARCH_API_KEY": "test"}
LIMITS = {"VOXEL1_MONTHLY_SEARCH_LIMIT": "10", "VOXEL1_MONTHLY_APOLLO_REQUESTS": "200", "VOXEL1_MONTHLY_BRAVE_REQUESTS": "200"}
CONFIRM = {"confirmed": True, "estimate": {"apollo": 11, "brave": 10, "gemini": 0}}


class GrowthTest(unittest.TestCase):
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

    def company(self, service="training", name="Example Engineering"):
        code, lead = self.request("POST", "/api/growth/companies", {"service": service, "company": name, "website": "https://example.test", "country": "India"})
        self.assertEqual(code, 200, lead)
        return lead

    def item(self, **fields):
        body = {"service": "training", "kind": "task", "title": "Call the L&D head", **fields}
        code, item = self.request("POST", "/api/growth/items", body)
        self.assertEqual(code, 200, item)
        return item

    def act(self, item, action, revision=None):
        return self.request("PATCH", f"/api/growth/items/{item['id']}", {"action": action, "revision": item["revision"] if revision is None else revision})

    def test_workspace_starts_empty_with_zero_goals(self):
        code, snap = self.request("GET", "/api/growth")
        self.assertEqual(code, 200)
        settings = {row["service"]: row for row in snap["settings"]}
        self.assertEqual({key: settings[key]["goal"] for key in ("training", "bim", "global")}, {"training": 0, "bim": 0, "global": 0})
        self.assertEqual(snap["items"], [])
        self.assertEqual(snap["connections"], {"email": False, "social": False, "calendar": False})
        self.assertIn("Sales", snap["choices"]["labels"]["task"])
        server.init_db()  # Repeatable without duplicating defaults.
        self.assertEqual(len(self.request("GET", "/api/growth")[1]["settings"]), 3)

    def test_rhythm_manual_generation_is_persistent_and_service_scoped(self):
        self.assertEqual(self.request("POST", "/api/growth/rhythm/bim", {})[1]["created"], 10)
        server.init_db()
        self.assertEqual(self.request("POST", "/api/growth/rhythm/bim", {})[1]["created"], 0)
        self.assertEqual(self.request("POST", "/api/growth/rhythm/training", {})[1]["created"], 6)
        snap = self.request("GET", "/api/growth")[1]
        self.assertEqual(len(snap["items"]), 16)
        self.assertTrue(all(i["state"] == "pending" and "IST" in i["body"] for i in snap["items"]))
        self.assertEqual(self.request("PUT", "/api/growth/rhythm/bim", {"enabled": "yes"})[0], 400)

    def test_rhythm_weekdays_ist_pause_and_no_backfill(self):
        def tick(iso):
            with server.connect() as db:
                growth.tick_rhythms(db, server.run, datetime.fromisoformat(iso))
        with server.connect() as db:
            server.run(db, "UPDATE growth_rhythm_settings SET enabled=1 WHERE service='bim'")
        tick("2026-10-15T00:29:00+00:00")  # 05:59 IST
        self.assertEqual(len(self.request("GET", "/api/growth")[1]["items"]), 0)
        tick("2026-10-15T00:30:00+00:00")
        tick("2026-10-15T14:00:00+00:00")
        self.assertEqual(len(self.request("GET", "/api/growth")[1]["items"]), 10)
        self.request("PUT", "/api/growth/settings/global", {"paused": True})
        tick("2026-10-16T01:00:00+00:00")
        self.request("PUT", "/api/growth/settings/global", {"paused": False})
        tick("2026-10-17T01:00:00+00:00")  # Saturday
        self.assertEqual(len(self.request("GET", "/api/growth")[1]["items"]), 10)
        tick("2026-10-19T01:00:00+00:00")
        snap = self.request("GET", "/api/growth")[1]
        self.assertEqual(len(snap["items"]), 20)
        self.assertEqual({i["due"] for i in snap["items"]}, {"2026-10-15", "2026-10-19"})

    def test_rhythm_rolls_back_claims_on_failure(self):
        instant = datetime(2026, 10, 15, 1, tzinfo=timezone.utc)
        with self.assertRaises(RuntimeError):
            with closing(server.connect()) as db:
                with db, patch.object(growth, "save_item", side_effect=RuntimeError("Interrupted")):
                    growth.generate_rhythm(db, server.run, "bim", instant)
        with server.connect() as db:
            self.assertEqual(growth.generate_rhythm(db, server.run, "bim", instant)["created"], 10)

    def campaign(self):
        config = {"objective": "Find Scan-to-BIM buyers", "start": "2026-10-01", "end": "",
                  "search_time": "06:00", "draft_time": "09:00", "accept_budget": True,
                  "targeting": {"name": "BIM campaign", "countries": ["Saudi Arabia"], "categories": ["engineering"], "keywords": "Scan to BIM"}}
        code, result = self.request("PUT", "/api/growth/campaign/bim", config)
        self.assertEqual(code, 200, result)
        return config

    def test_agent_runs_on_weekend_once_and_drafts_wait_for_approval(self):
        self.campaign()
        lead = self.company("bim")
        with closing(server.connect()) as db, db:
            server.run(db, "UPDATE leads SET ai_screened=1 WHERE id=?", (lead["id"],))
        instant = datetime(2026, 10, 17, 5, tzinfo=timezone.utc)
        def draft(service, lead_id, payload):
            return self.item(service=service, lead_id=lead_id, kind="outreach", body="Hello", channel="Email", label="First contact")
        with patch.object(automation, "discovery", return_value={"found": 1, "added": 1, "lead_ids": [lead["id"]]}) as discover, patch.object(server, "ai_draft_lead", side_effect=draft) as writer:
            automation.tick(server, instant)
            automation.tick(server, instant)
            discover.assert_called_once()
            writer.assert_called_once()
        snap = self.request("GET", "/api/growth")[1]
        self.assertEqual(snap["items"][0]["state"], "pending")
        self.assertEqual({j["state"] for j in snap["jobs"]}, {"done", "needs_approval"})

    def test_agent_pause_and_recovery_do_not_repeat_paid_jobs(self):
        self.campaign()
        instant = datetime(2026, 10, 15, 2, tzinfo=timezone.utc)
        self.request("PUT", "/api/growth/settings/bim", {"paused": True})
        with patch.object(automation, "discovery", return_value={"lead_ids": []}) as discover:
            automation.tick(server, instant)
            discover.assert_not_called()
            self.request("PUT", "/api/growth/settings/bim", {"paused": False})
            self.assertTrue(automation.claim(server, "bim", "2026-10-15", "discovery"))
            automation.recover(server)
            automation.tick(server, instant)
            discover.assert_not_called()
        self.assertEqual(self.request("GET", "/api/growth")[1]["jobs"][0]["state"], "interrupted")

    def test_agent_budget_failure_is_visible_and_not_retried(self):
        self.campaign()
        instant = datetime(2026, 10, 15, 5, tzinfo=timezone.utc)
        with patch.dict(os.environ, {**KEYS, "GEMINI_API_KEY": "test"}), patch.object(server, "reserve_search", side_effect=server.BudgetBlocked("Monthly cap reached")), patch.object(provider_search, "discover") as discover:
            automation.tick(server, instant)
            automation.tick(server, instant)
            discover.assert_not_called()
        jobs = self.request("GET", "/api/growth")[1]["jobs"]
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["state"], "needs_you")
        self.assertIn("Monthly cap", jobs[0]["result"])

    def test_agent_uses_saved_targeting_and_metered_search(self):
        config = self.campaign()
        def discover(profile, service, meter, skip):
            self.assertEqual(profile["countries"], ["Saudi Arabia"])
            self.assertEqual(profile["keywords"], "Scan to BIM")
            meter.charge("apollo", "search")
            return {"companies": [], "coverage": [], "warnings": []}
        env = {**KEYS, **LIMITS, "GEMINI_API_KEY": "test", "VOXEL1_MONTHLY_GEMINI_REQUESTS": "200"}
        with patch.dict(os.environ, env), patch.object(provider_search, "discover", side_effect=discover):
            automation.tick(server, datetime(2026, 10, 15, 2, tzinfo=timezone.utc))
        with closing(server.connect()) as db:
            self.assertEqual(server.run(db, "SELECT COUNT(*) AS n FROM provider_usage").fetchone()["n"], 1)
        self.assertEqual(self.request("GET", "/api/growth")[1]["jobs"][0]["state"], "done")

    def test_task_lifecycle_and_stale_revision(self):
        task = self.item(label="Sales", due="2026-10-15", due_time="09:30", owner="You")
        self.assertEqual((task["state"], task["revision"], task["label"], task["due_time"]), ("pending", 1, "Sales", "09:30"))
        code, done = self.act(task, "complete")
        self.assertEqual((code, done["state"], done["revision"]), (200, "done", 2))
        code, body = self.act(task, "reopen")  # Revision 1 is stale now.
        self.assertEqual(code, 409)
        self.assertIn("changed", body["error"])
        code, reopened = self.act(done, "reopen")
        self.assertEqual((code, reopened["state"]), (200, "pending"))
        code, _ = self.act(reopened, "approve")
        self.assertEqual(code, 400)  # Tasks are completed, not approved.

    def test_draft_approval_rules_and_edit_invalidates_approval(self):
        draft = self.item(kind="content", title="Clash-free coordination", channel="LinkedIn", label="Proof")
        self.assertEqual(self.act(draft, "approve")[0], 400)  # No text yet.
        code, draft = self.request("PATCH", f"/api/growth/items/{draft['id']}", {**draft, "body": "How weekly coordination runs.", "revision": draft["revision"]})
        self.assertEqual(code, 200)
        self.assertEqual(self.act(draft, "complete")[0], 400)  # Must be approved before recording it as posted.
        code, approved = self.act(draft, "approve")
        self.assertEqual((code, approved["state"]), (200, "approved"))
        code, edited = self.request("PATCH", f"/api/growth/items/{draft['id']}", {**approved, "body": "Changed text.", "revision": approved["revision"]})
        self.assertEqual((code, edited["state"]), (200, "pending"))
        code, approved = self.act(edited, "approve")
        code, posted = self.act(approved, "complete")
        self.assertEqual((code, posted["state"]), (200, "done"))

    def test_validation_and_service_isolation(self):
        bim_lead = self.company("bim", "BIM Client")
        code, body = self.request("POST", "/api/growth/items", {"service": "training", "kind": "outreach", "title": "Hello", "lead_id": bim_lead["id"]})
        self.assertEqual(code, 400)
        self.assertIn("belonging to this service", body["error"])
        for bad in ({"kind": "rocket"}, {"channel": "Fax"}, {"label": "Proof"}, {"due": "2026-13-40"}, {"due_time": "25:00"}, {"title": ""}, {"service": "design"}):
            code, _ = self.request("POST", "/api/growth/items", {"service": "training", "kind": "task", "title": "T", **bad})
            self.assertEqual(code, 400, bad)
        self.assertEqual(self.request("PUT", f"/api/growth/leads/{bim_lead['id']}", {"service": "training", "stage": "won"})[0], 400)
        self.assertEqual(self.request("PUT", "/api/growth/settings/training", {"goal": -1})[0], 400)
        self.assertEqual(self.request("PUT", "/api/growth/settings/training", {"paused": "yes"})[0], 400)
        self.assertEqual(self.request("POST", "/api/growth/nothing", {"service": "bim"})[0], 404)
        self.assertEqual(self.request("POST", "/api/growth/companies", {"service": "bim", "company": "X", "website": "javascript:alert(1)"})[0], 400)

    def test_manual_company_and_lead_room_history(self):
        lead = self.company()
        self.assertTrue(lead["source_id"].startswith("manual/"))
        self.assertIn("Added manually", lead["match_reason"])
        self.assertEqual(lead["review_decision"], "active")
        code, room = self.request("PUT", f"/api/growth/leads/{lead['id']}", {"service": "training", "stage": "meeting", "owner": "Training head", "room_notes": "Ramp-up plan"})
        self.assertEqual((code, room["stage"], room["owner"]), (200, "meeting", "Training head"))
        task = self.item(lead_id=lead["id"], title="Prepare batch dates")
        self.act(task, "complete")
        _, history = self.request("GET", f"/api/services/training/leads/{lead['id']}/history")
        self.assertEqual({item["event"] for item in history}, {"discovered", "lead_room_updated", "created", "complete"})
        _, snap = self.request("GET", "/api/growth")
        self.assertEqual(snap["lead_details"][0]["stage"], "meeting")

    def test_pause_blocks_search_and_decisions_but_not_editing(self):
        draft = self.item(kind="outreach", title="Intro", body="Hello")
        for scope in ("training", "global"):
            self.request("PUT", f"/api/growth/settings/{scope}", {"paused": True})
            with patch.dict(os.environ, {**KEYS, **LIMITS}, clear=True), patch.object(provider_search, "request_json") as call:
                code, body = self.request("POST", "/api/services/training/discover", CONFIRM)
            self.assertEqual(code, 409)
            self.assertIn("paused", body["error"])
            call.assert_not_called()
            self.assertEqual(self.act(draft, "approve")[0], 400)
            code, draft = self.request("PATCH", f"/api/growth/items/{draft['id']}", {**draft, "body": "Hello again", "revision": draft["revision"]})
            self.assertEqual(code, 200)
            self.request("PUT", f"/api/growth/settings/{scope}", {"paused": False})
        with server.connect() as db:
            self.assertEqual(server.run(db, "SELECT COUNT(*) AS n FROM search_runs").fetchone()["n"], 0)
        # Pausing BIM does not pause Training.
        self.request("PUT", "/api/growth/settings/bim", {"paused": True})
        self.assertEqual(self.act(draft, "approve")[0], 200)

    def test_existing_leads_survive_growth_tables(self):
        lead = self.company()
        self.request("PATCH", f"/api/services/training/leads/{lead['id']}/review", {"decision": "archived", "reason": "no_current_need"})
        server.init_db()
        _, leads = self.request("GET", "/api/services/training/leads")
        self.assertEqual((leads[0]["company"], leads[0]["review_decision"]), ("Example Engineering", "archived"))


if __name__ == "__main__":
    unittest.main()
