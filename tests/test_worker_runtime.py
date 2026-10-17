"""A busy worker is distinct from a missing completed heartbeat."""
import threading
import unittest
from unittest.mock import patch

import server


class WorkerRuntimeTest(unittest.TestCase):
    def test_runtime_reports_busy_during_tick_and_stopped_after_shutdown(self):
        entered, release, stop = threading.Event(), threading.Event(), threading.Event()

        def tick():
            entered.set()
            release.wait(3)

        with patch.object(server, "worker_tick", side_effect=tick):
            worker = threading.Thread(target=server.rhythm_worker, args=(stop,))
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                with server.worker_runtime_lock:
                    status = dict(server.worker_runtime)
                self.assertTrue(status["running"])
                self.assertTrue(status["busy"])
                self.assertTrue(status["started_at"])
            finally:
                stop.set()
                release.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertFalse(server.worker_runtime["running"])
        self.assertFalse(server.worker_runtime["busy"])

    def test_failed_tick_does_not_leave_busy_state(self):
        stop = threading.Event()

        def fail():
            stop.set()
            raise RuntimeError("fixture failure")

        with patch.object(server, "worker_tick", side_effect=fail), self.assertLogs(level="ERROR"):
            server.rhythm_worker(stop)
        self.assertFalse(server.worker_runtime["running"])
        self.assertFalse(server.worker_runtime["busy"])
