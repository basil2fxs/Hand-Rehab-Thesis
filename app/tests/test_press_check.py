"""The press check's USB part (analysis/press_check.py): how late the
computer stamped each force sample, read from the arrival times alone."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "analysis"))
sys.path.insert(0, str(ROOT / "app"))

from finger_rehab.analytics.signal import sample_grid_lateness  # noqa: E402
from press_check import stamp_lateness  # noqa: E402


def arrivals(burst_ms: float, n: int = 4000, seed: int = 3) -> np.ndarray:
    """A board sampling every 5 ms whose samples reach the computer at the
    end of each burst_ms window, or one at a time when burst_ms is 0, with
    up to 0.5 ms of jitter."""
    rng = np.random.default_rng(seed)
    sampled = np.arange(n) * 0.005
    if burst_ms:
        w = burst_ms / 1000
        stamped = (np.floor(sampled / w) + 1) * w
    else:
        stamped = sampled + 0.0005
    return stamped + rng.uniform(0, 0.0005, n)


class StampLatenessTests(unittest.TestCase):
    def test_a_bursting_adapter_stamps_samples_up_to_a_burst_late(self):
        out = stamp_lateness(sample_grid_lateness(arrivals(20.0)))
        self.assertGreater(out["mean"], 5.0)
        self.assertGreater(out["p99"], 12.0)
        self.assertLessEqual(out["max"], 21.0)

    def test_samples_passed_on_singly_are_stamped_within_a_millisecond(self):
        out = stamp_lateness(sample_grid_lateness(arrivals(0.0)))
        self.assertLess(out["mean"], 1.0)
        self.assertLess(out["p99"], 1.0)
        self.assertEqual(out["samples"], 4000)


if __name__ == "__main__":
    unittest.main()
