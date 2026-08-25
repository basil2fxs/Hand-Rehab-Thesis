"""A stuck sample producer must not be able to fill the disk.

engine._pump_source drains `while True` until the source returns None, so
a source that never empties queues raw rows in an unbounded loop. Nothing
downstream bounded that: one harness session left running overnight wrote
a 243 GB raw.csv of all-zero rows (3.49 billion of them) and came within
hours of filling the volume. RawLogger now refuses rows past MAX_RAW_ROWS,
which turns a silent disk-fill into a bounded file plus one logged error.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finger_rehab.data.logger import MAX_RAW_ROWS, RawLogger


class RawLoggerRowCapTests(unittest.TestCase):

    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="rawcap-"))

    def _rows(self, path: Path) -> int:
        return len(path.read_text().splitlines()) - 1   # minus header

    def test_runaway_producer_is_capped(self) -> None:
        """Queueing far past the ceiling writes at most `max_rows` rows."""
        path = self.tmp / "raw.csv"
        rl = RawLogger(path, num_sensors=4, max_rows=100)
        rl.start()
        for i in range(50_000):
            rl.queue_sample(float(i), (0, 0, 0, 0), hand="right")
        rl.stop()
        self.assertLessEqual(self._rows(path), 100)

    def test_events_are_capped_too(self) -> None:
        """The ceiling covers queue_event, not just queue_sample - a stuck
        mode can emit events in a loop just as easily as samples."""
        path = self.tmp / "raw.csv"
        rl = RawLogger(path, num_sensors=4, max_rows=50)
        rl.start()
        for i in range(5_000):
            rl.queue_event("press", lane=1, detail="x", t_perf=float(i))
        rl.stop()
        self.assertLessEqual(self._rows(path), 50)

    def test_cap_logs_once_not_per_row(self) -> None:
        """A runaway reaches the cap at loop speed; logging every call
        would just trade a huge CSV for a huge log."""
        path = self.tmp / "raw.csv"
        rl = RawLogger(path, num_sensors=4, max_rows=10)
        rl.start()
        with self.assertLogs("finger_rehab.data.logger", "ERROR") as cm:
            for i in range(1_000):
                rl.queue_sample(float(i), (0, 0, 0, 0))
        rl.stop()
        self.assertEqual(len(cm.output), 1)

    def test_normal_session_loses_nothing(self) -> None:
        """A realistic session is far below the ceiling and must be
        written in full - the guard is a backstop, not a sampler."""
        path = self.tmp / "raw.csv"
        rl = RawLogger(path, num_sensors=4)      # default ceiling
        rl.start()
        for i in range(5_000):
            rl.queue_sample(float(i), (12, 34, 56, 78), hand="right")
        rl.queue_event("block_start", detail="reaction")
        rl.stop()
        self.assertEqual(self._rows(path), 5_001)

    def test_default_ceiling_clears_a_real_session(self) -> None:
        """200 Hz x 30 min session_cap_min is ~360k rows; the default
        ceiling must sit well above that so it never fires in the lab."""
        worst_case_rows = 200 * 60 * 30
        self.assertGreater(MAX_RAW_ROWS, worst_case_rows * 10)


if __name__ == "__main__":
    unittest.main()
