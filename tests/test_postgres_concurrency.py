"""Concurrency checks that only mean something on PostgreSQL (run with tests/postgres_runner.py).

They model two worker processes (for example, a deploy overlap) acting on the same database
at the same moment. Skipped on SQLite.
"""
import os
import threading
import unittest
from contextlib import closing
from datetime import datetime, timezone
from unittest.mock import patch

import automation
import draft_outputs
import growth
import rhythm_engine
import server

GOOD = {"title": "Scan-to-BIM discussion", "body": "Would a short Scan-to-BIM call help?", "model": "test-model"}


def together(count, work):
    """Run work(n) in `count` threads released at the same instant; return their results."""
    start, results, errors = threading.Barrier(count), [None] * count, []

    def runner(n):
        start.wait()
        try:
            results[n] = work(n)
        except Exception as exc:  # Collected so the test reports it.
            errors.append(exc)
    threads = [threading.Thread(target=runner, args=(n,)) for n in range(count)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(60)
    return results, errors


@unittest.skipUnless(os.environ.get("VOXEL1_TEST_DATABASE_URL"), "PostgreSQL-only; run tests/postgres_runner.py")
class PostgresConcurrencyTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"GEMINI_API_KEY": "test", "VOXEL1_MONTHLY_GEMINI_REQUESTS": "5",
                                           "VOXEL1_MONTHLY_SEARCH_LIMIT": "3", "VOXEL1_MONTHLY_BRAVE_REQUESTS": "100",
                                           "VOXEL1_MONTHLY_APOLLO_REQUESTS": "100"})
        self.env.start()
        self.assertTrue(server.DATABASE_URL.startswith("postgresql"))
        server.init_db()

    def tearDown(self):
        self.env.stop()

    def sql(self, statement, values=()):
        with closing(server.connect()) as db, db:
            cursor = server.run(db, statement, values)
            return [dict(r) for r in cursor] if cursor.description else []

    def test_only_one_worker_claims_a_job(self):
        results, errors = together(8, lambda n: automation.claim(server, "bim", "2026-10-15", "rhythm:4"))
        self.assertEqual(errors, [])
        self.assertEqual(results.count(True), 1)
        self.assertEqual(len(self.sql("SELECT * FROM agent_jobs WHERE job='rhythm:4'")), 1)

    def test_concurrent_gemini_reservations_never_exceed_the_cap(self):
        def reserve(n):
            try:
                server.reserve_ai_draft(operation="concurrency")
                return "reserved"
            except server.BudgetBlocked:
                return "blocked"
        results, errors = together(12, reserve)
        self.assertEqual(errors, [])
        self.assertEqual(results.count("reserved"), 5)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM provider_usage WHERE provider='gemini'")[0]["n"], 5)

    def test_concurrent_search_reservations_never_exceed_the_cap(self):
        def reserve(n):
            try:
                server.reserve_search("bim", {"apollo": 0, "brave": 1, "gemini": 0})
                return "reserved"
            except server.BudgetBlocked:
                return "blocked"
        results, errors = together(10, reserve)
        self.assertEqual(errors, [])
        self.assertEqual(results.count("reserved"), 3)
        self.assertEqual(self.sql("SELECT COUNT(*) AS n FROM search_runs")[0]["n"], 3)

    def test_two_workers_running_the_rhythm_together_create_no_duplicates(self):
        with closing(server.connect()) as db, db:
            lead = growth.add_company(db, server.run, {"service": "bim", "company": "Example Consultant", "category": "engineering"}, server.log_event)
            server.run(db, "UPDATE leads SET ai_screened=1 WHERE id=?", (lead["id"],))
            automation.save(server, db, "bim", {
                "objective": "Scan-to-BIM", "start": "2026-10-01", "end": "", "search_time": "06:00", "draft_time": "09:00",
                "accept_budget": True, "goal": 1, "quarter": "2026-Q4", "strategy": "", "full_rhythm": True,
                "service_focus": "Scan-to-BIM", "content_targets": {"LinkedIn": 1},
                "targeting": {"name": "T", "countries": ["Saudi Arabia"], "categories": ["engineering"]}})
        instant = datetime(2026, 10, 15, 14, tzinfo=timezone.utc)  # 19:30 IST: every slot is due.
        with patch.dict(os.environ, {"VOXEL1_MONTHLY_GEMINI_REQUESTS": "100"}), \
             patch.object(draft_outputs, "generate", return_value=GOOD) as generate:
            _, errors = together(2, lambda n: rhythm_engine.tick(server, instant, phase="drafts"))
            calls = generate.call_count
        self.assertEqual(errors, [])
        jobs = self.sql("SELECT job, COUNT(*) AS n FROM agent_jobs GROUP BY job HAVING COUNT(*) > 1")
        self.assertEqual(jobs, [])
        summaries = self.sql("SELECT COUNT(*) AS n FROM growth_items WHERE label='Daily summary'")[0]["n"]
        self.assertEqual(summaries, 1)
        # Each generated output was claimed once: one call per saved AI draft.
        saved = self.sql("SELECT COUNT(*) AS n FROM growth_items WHERE kind IN ('outreach','content')")[0]["n"]
        self.assertGreater(saved, 0)
        self.assertEqual(calls, saved)

    def test_heartbeat_upsert_from_two_workers(self):
        _, errors = together(6, lambda n: server.record_heartbeat("" if n % 2 else f"step failed {n}"))
        self.assertEqual(errors, [])
        rows = self.sql("SELECT * FROM worker_heartbeat")
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["last_tick"])


if __name__ == "__main__":
    unittest.main()
