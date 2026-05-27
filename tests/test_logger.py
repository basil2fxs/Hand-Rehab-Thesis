"""Tests for TrialLogger / RawLogger. Both touch the filesystem, so
each test uses a TemporaryDirectory and never reaches user data."""
from __future__ import annotations

import csv
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TrialLoggerBasicTests(unittest.TestCase):

    def test_write_creates_file_with_header(self) -> None:
        from rehab.data.logger import TrialLogger, TRIAL_COLUMNS
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trials.csv"
            tl = TrialLogger(path)
            tl.write({"trial": "1", "lane": "0"})
            tl.close()
            with path.open() as f:
                rows = list(csv.reader(f))
            # Header + one data row.
            self.assertEqual(rows[0], TRIAL_COLUMNS)
            self.assertEqual(len(rows), 2)

    def test_missing_keys_default_to_empty_string(self) -> None:
        from rehab.data.logger import TrialLogger, TRIAL_COLUMNS
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trials.csv"
            tl = TrialLogger(path)
            tl.write({"trial": "1"})  # only trial supplied
            tl.close()
            with path.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["trial"], "1")
            self.assertEqual(rows[0]["lane"], "")
            self.assertEqual(rows[0]["points"], "")
            # Every column present.
            for col in TRIAL_COLUMNS:
                self.assertIn(col, rows[0])


class TrialLoggerCloseTruncationRegressionTests(unittest.TestCase):
    """Regression: write-after-close used to reopen the CSV in 'w' mode,
    which truncated everything written during the block."""

    def test_write_after_close_does_not_truncate_file(self) -> None:
        from rehab.data.logger import TrialLogger
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trials.csv"
            tl = TrialLogger(path)
            tl.write({"trial": "1", "lane": "0"})
            tl.write({"trial": "2", "lane": "1"})
            tl.close()
            # Late write that previously would have nuked the file.
            tl.write({"trial": "99", "lane": "7"})
            with path.open() as f:
                rows = list(csv.DictReader(f))
            # Both original rows still present, late row dropped.
            trial_nums = [r["trial"] for r in rows]
            self.assertEqual(trial_nums, ["1", "2"])
            self.assertNotIn("99", trial_nums)

    def test_close_is_idempotent(self) -> None:
        from rehab.data.logger import TrialLogger
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trials.csv"
            tl = TrialLogger(path)
            tl.write({"trial": "1"})
            tl.close()
            tl.close()  # must not raise

    def test_close_before_any_write_is_safe(self) -> None:
        # If a block is abandoned before any trial completes, close()
        # gets called on a logger that never opened the file. Must not
        # raise and must not create a stray empty CSV.
        from rehab.data.logger import TrialLogger
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trials.csv"
            tl = TrialLogger(path)
            tl.close()
            self.assertFalse(path.exists())


class RawLoggerBasicTests(unittest.TestCase):

    def test_queue_sample_flushes_to_disk(self) -> None:
        from rehab.data.logger import RawLogger, RAW_COLUMNS
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "raw.csv"
            rl = RawLogger(path)
            rl.start()
            try:
                rl.queue_sample(1.23, (10, 20, 30, 40))
                # Flusher loop runs every 50 ms, give it a couple of ticks.
                time.sleep(0.15)
            finally:
                rl.stop()
            with path.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["fsr1"], "10")
            self.assertEqual(rows[0]["fsr4"], "40")
            # Bilateral slots default to zero for a 4-value sample.
            self.assertEqual(rows[0]["fsr5"], "0")
            self.assertEqual(rows[0]["fsr8"], "0")
            # Every documented column is present.
            for col in RAW_COLUMNS:
                self.assertIn(col, rows[0])

    def test_queue_event_records_event_columns(self) -> None:
        from rehab.data.logger import RawLogger
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "raw.csv"
            rl = RawLogger(path)
            rl.start()
            try:
                rl.queue_event("stim", lane=2, detail="trial_id=7", t_perf=2.0)
                time.sleep(0.15)
            finally:
                rl.stop()
            with path.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["event"], "stim")
            self.assertEqual(rows[0]["lane"], "2")
            self.assertEqual(rows[0]["detail"], "trial_id=7")

    def test_stop_drains_pending_queue(self) -> None:
        # Anything still queued when stop() runs must end up on disk -
        # the final drain inside stop() is the only guarantee against
        # losing the last batch.
        from rehab.data.logger import RawLogger
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "raw.csv"
            rl = RawLogger(path)
            rl.start()
            # Push items and immediately stop - some will still be queued.
            for i in range(20):
                rl.queue_sample(float(i), (i, 0, 0, 0))
            rl.stop()
            with path.open() as f:
                rows = list(csv.reader(f))
            # Header + 20 data rows.
            self.assertEqual(len(rows), 21)


class RawLoggerHungThreadRegressionTests(unittest.TestCase):
    """Regression: when the flusher thread doesn't exit in time, stop()
    used to early-return without closing the file or draining the queue.
    Now both happen anyway, on a best-effort basis."""

    def test_stop_closes_file_even_when_thread_hangs(self) -> None:
        from rehab.data.logger import RawLogger
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "raw.csv"
            rl = RawLogger(path)

            # Replace the flusher with one that never honours _stop.
            hang_release = threading.Event()

            def _hang_loop() -> None:
                # Burn time until the test releases us. join(timeout=2)
                # will give up first, and stop() must NOT leak the file.
                hang_release.wait(timeout=5.0)

            rl.path.parent.mkdir(parents=True, exist_ok=True)
            rl._file = rl.path.open("w", newline="", encoding="utf-8")
            rl._writer = csv.writer(rl._file)
            from rehab.data.logger import RAW_COLUMNS
            rl._writer.writerow(RAW_COLUMNS)
            rl._file.flush()
            rl._thread = threading.Thread(target=_hang_loop, daemon=True)
            rl._thread.start()

            rl.queue_sample(1.0, (1, 2, 3, 4))
            try:
                rl.stop()
                # File handle must be released even though the worker
                # is still alive.
                self.assertIsNone(rl._file)
                self.assertIsNone(rl._writer)
                # And the queued sample must have made it to disk via
                # the best-effort final drain.
                with path.open() as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), 1)
                self.assertEqual(rows[0]["fsr1"], "1")
            finally:
                hang_release.set()


if __name__ == "__main__":
    unittest.main()
