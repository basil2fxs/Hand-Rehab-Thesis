"""The marker checks (analysis/eeg/checks.py): counts against the log,
gaps between markers, reaction times from the recording against the
log's, and the trial-by-trial match that catches a shifted pairing.
Plain Python, so it runs here without MNE."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ANALYSIS = Path(__file__).resolve().parents[2] / "analysis"
sys.path.insert(0, str(ANALYSIS))

from eeg.checks import counts, gaps, order, rt_match  # noqa: E402

SF = 512.0


def _trials() -> pd.DataFrame:
    """Six trials in two blocks: flashes 0.8 s apart inside a block, a
    press 0.28 s after each flash, and a long break between blocks."""
    flash_s = np.array([1.0, 1.8, 2.6, 10.0, 10.8, 11.6])
    rt_ms = np.full(6, 280.0)
    keys = ["v", "b", "n", "m", "v", "b"]
    return pd.DataFrame({
        "phase": ["practice"] * 3 + ["learning"] * 3, "block": [1, 1, 1, 1, 1, 1],
        "flash_sample": np.round(flash_s * SF), "press_sample": np.round((flash_s + 0.28) * SF),
        "onset_s": flash_s, "rt_ms": rt_ms,
        "outcome": ["correct", "error", "correct", "correct", "anticipation", "miss"],
        "response_key": keys,
        "resp_code": [100, 111, 102, 103, 120, 130],
    })


class CountTests(unittest.TestCase):

    def test_each_marker_type_is_counted_against_the_log(self):
        t = _trials()
        codes = [213, 30, 100, 30, 111, 30, 102, 30, 103, 30, 120, 30, 130, 233]
        buzz = pd.DataFrame({"catch": [False, True, False]})
        rows = {name: (eeg, log) for name, eeg, log in counts(t, codes, buzz, [210, 38, 38, 230])}
        self.assertEqual(rows["Flashes"], (6, 6))
        self.assertEqual(rows["Correct presses"], (3, 3))
        self.assertEqual(rows["Wrong finger"], (1, 1))
        self.assertEqual(rows["Early presses"], (1, 1))
        self.assertEqual(rows["Misses"], (1, 1))
        self.assertEqual(rows["Buzzes"], (2, 2))     # the catch trial has no buzz

    def test_a_lost_flash_shows(self):
        t = _trials()
        rows = {name: (eeg, log) for name, eeg, log in
                counts(t, [30] * 5, pd.DataFrame({"catch": []}), [])}
        self.assertEqual(rows["Flashes"], (5, 6))


class GapTests(unittest.TestCase):

    def test_gaps_stay_inside_their_block(self):
        t = _trials()
        buzz = pd.DataFrame({"stage": ["loc"] * 3, "buzz_sample": [SF * 5, SF * 11, SF * 17]})
        g = gaps(t, SF, buzz)
        np.testing.assert_allclose(g["flash_flash"], 0.8, atol=0.003)
        self.assertEqual(len(g["flash_flash"]), 4)           # the break is left out
        np.testing.assert_allclose(g["press_next"], 0.52, atol=0.003)
        np.testing.assert_allclose(g["buzz_buzz"], 6.0)
        np.testing.assert_allclose(g["flash_vs_log_ms"], 0.0, atol=2.0)

    def test_no_press_to_flash_gap_after_a_miss(self):
        t = _trials()
        t.loc[3, "outcome"] = "miss"
        g = gaps(t, SF, pd.DataFrame({"stage": [], "buzz_sample": []}))
        self.assertEqual(len(g["press_next"]), 1)


class ReactionTimeTests(unittest.TestCase):

    def test_the_recording_gives_the_log_reaction_times(self):
        t = _trials()
        t["rt_ms"] = [250.0, 300.0, 270.0, 320.0, 240.0, np.nan]
        t["press_sample"] = t.flash_sample + np.round(t.rt_ms.fillna(0) / 1000 * SF)
        byte = t.press_sample + np.round(0.007 * SF)
        rt = rt_match(t, byte, SF)
        self.assertEqual(rt["n"], 5)                        # the miss has no press
        self.assertGreater(rt["r"], 0.999)
        self.assertLess(abs(rt["offset_ms"]), 2.0)
        self.assertAlmostEqual(rt["byte_late_ms"][1], 7.8, delta=1.0)


class OrderTests(unittest.TestCase):

    def test_matching_lanes_and_bands(self):
        t = _trials()
        o = order(t, np.zeros(5))
        self.assertEqual(o["lanes"], (5, 5))
        self.assertEqual(o["bands"], (6, 6))

    def test_a_pairing_shifted_by_one_trial_is_caught(self):
        t = _trials()
        t["resp_code"] = np.roll(t.resp_code.to_numpy(), 1)
        o = order(t, np.zeros(5))
        self.assertLess(o["lanes"][0], o["lanes"][1])
        self.assertLess(o["bands"][0], o["bands"][1])


if __name__ == "__main__":
    unittest.main()
