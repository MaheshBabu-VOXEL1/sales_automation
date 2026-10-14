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
