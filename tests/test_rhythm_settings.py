"""The rhythm's times and on/off are saved with the Sales Goal and respected by the planner and the engine."""
import gc
import json
import os
import tempfile
import unittest
from contextlib import closing
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import automation
import growth
import rhythm_engine
import server


class RhythmSettingsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(server, "DB_PATH", Path(self.temp.name) / "test.db"), patch.dict(os.environ, {"DATABASE_URL": ""})]
        for p in self.patches:
            p.start()
        server.init_db()
        self.config = {"objective": "Sell Scan-to-BIM", "start": "2026-10-01", "end": "", "search_time": "06:00", "draft_time": "09:00",
                       "accept_budget": True, "full_rhythm": True,
                       "targeting": {"name": "BIM", "countries": ["Saudi Arabia"], "categories": ["engineering"], "keywords": "BIM"}}

    def tearDown(self):
        for p in reversed(self.patches):
            p.stop()
        gc.collect()
        self.temp.cleanup()

    def plan(self, **changes):
        rows = [{"time": time, "on": True} for time, _, _, _ in growth.RHYTHMS["bim"]]
        for index, entry in changes.items():
            rows[int(index[1:])].update(entry)
        return rows

    def save(self, **payload):
        with closing(server.connect()) as db, db:
            automation.save(server, db, "bim", {**self.config, **payload})
            return json.loads(server.run(db, "SELECT config FROM agent_campaigns WHERE service='bim'").fetchone()["config"])

    def test_saved_times_and_off_switches_are_kept(self):
        config = self.save(rhythm=self.plan(s0={"on": False}, s2={"time": "08:15"}))
        plan = growth.rhythm_plan("bim", config)
        self.assertFalse(plan[0][4])
        self.assertEqual(plan[2][0], "08:15")
        self.assertTrue(plan[1][4])
        # A later save that does not send the rhythm keeps it.
        self.assertEqual(self.save()["rhythm"], config["rhythm"])

    def test_without_saved_rhythm_every_activity_is_on_at_its_default_time(self):
        plan = growth.rhythm_plan("bim", {})
        self.assertEqual([p[0] for p in plan], [r[0] for r in growth.RHYTHMS["bim"]])
        self.assertTrue(all(p[4] for p in plan))

    def test_invalid_rhythm_is_refused(self):
        for bad in (self.plan()[:-1], self.plan(s1={"time": "25:00"}), self.plan(s1={"on": "yes"})):
            with self.assertRaises(ValueError):
                self.save(rhythm=bad)

    def test_planner_skips_off_activities_and_uses_saved_times(self):
        self.save(rhythm=self.plan(s0={"on": False}, s1={"time": "06:45"}))
        instant = datetime.fromisoformat("2026-10-19T03:00:00+00:00")
        with closing(server.connect()) as db, db:
            created = growth.generate_rhythm(db, server.run, "bim", instant)["created"]
            tasks = {r["title"]: r["due_time"] for r in server.run(db, "SELECT title, due_time FROM growth_items WHERE kind='task'")}
        self.assertEqual(created, len(growth.RHYTHMS["bim"]) - 1)
        self.assertNotIn(growth.RHYTHMS["bim"][0][2], tasks)
        self.assertEqual(tasks[growth.RHYTHMS["bim"][1][2]], "06:45")

    def test_engine_does_not_run_off_activities(self):
        self.save(rhythm=self.plan(s0={"on": False}, s1={"on": False}))
        with patch.object(rhythm_engine, "research", side_effect=AssertionError("an off activity ran")):
            rhythm_engine.tick(server, datetime.fromisoformat("2026-10-19T06:00:00+00:00"), phase="research")
        with closing(server.connect()) as db:
            jobs = [r["job"] for r in server.run(db, "SELECT job FROM agent_jobs WHERE service='bim'")]
        self.assertNotIn("rhythm:0", jobs)
        self.assertNotIn("rhythm:1", jobs)


if __name__ == "__main__":
    unittest.main()
