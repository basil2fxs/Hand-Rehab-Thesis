"""Adaptive after the deep research of 1 October 2026.

A press on the previous trial's finger just after the next cue is that
trial's late answer, not a wrong finger on the new one; a press under
100 ms is not a response to the cue; the battery block cannot sink
below its 30 BPM start; the GET READY card and the run sheet say what
the game asks; the block records what the controller did; and the
notebook reads the steady pace beside the peak, the hit rate after the
climb, and A6 as a feasibility check.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_adaptive import _mode, _press  # noqa: E402

APP = Path(__file__).resolve().parents[1]


def _events(engine):
    return [c.args[0] for c in engine.raw_logger.queue_event.call_args_list]


class LatePressTests(unittest.TestCase):

    def _two_trials(self):
        engine, mode = _mode()
        engine.raw_logger = MagicMock()
        mode.sequence = [0, 2, 1, 3]
        mode.seq_idx = 0
        mode._fire(now=0.0)
        mode._finish(None, now=1.8)          # trial 1 timed out
        mode._fire(now=2.0)                  # trial 2 cues finger 2
        return engine, mode

    def test_a_late_answer_is_not_a_wrong_finger(self):
        engine, mode = self._two_trials()
        mode._handle_press(_press(0, 2.05), now=2.05)
        self.assertEqual(mode.active.incorrect_presses, [])
        self.assertEqual(mode._late_presses, 1)
        self.assertIn("late_press", _events(engine))
        engine.apply_wrong_press_penalty.assert_not_called()

    def test_past_the_carry_window_it_is_a_wrong_finger(self):
        engine, mode = self._two_trials()
        mode._handle_press(_press(0, 2.2), now=2.2)
        self.assertEqual(len(mode.active.incorrect_presses), 1)
        self.assertEqual(mode._late_presses, 0)

    def test_a_press_under_100_ms_is_not_a_response(self):
        engine, mode = self._two_trials()
        mode._handle_press(_press(3, 2.04), now=2.04)
        self.assertEqual(mode.active.incorrect_presses, [])
        self.assertEqual(mode._anticipations, 1)
        self.assertIn("anticipation_press", _events(engine))


class LoggingTests(unittest.TestCase):

    def test_the_controller_state_and_the_block_stats(self):
        engine, mode = _mode()
        engine.raw_logger = MagicMock()
        t = 0.0
        for _i in range(24):
            mode._fire(now=t)
            mode._handle_press(_press(mode.active.lane, t + 0.3), now=t + 0.3)
            t += 2.0
        self.assertIn("adaptive_state", _events(engine))
        self.assertIn("pressure", mode.adapter.last_decision)
        st = mode.block_stats()
        self.assertEqual(len(st["bpm_trace"]), 24)
        self.assertEqual(st["bpm_peak"], max(st["bpm_trace"]))
        self.assertIsNotNone(st["steady_pace_bpm"])
        self.assertEqual(sum(st["cues_per_finger"]), 24)
        self.assertEqual(sum(st["hits_per_finger"]), 24)
        self.assertEqual(st["carry_ms"], 150.0)
        self.assertEqual(st["bpm_next"], round(mode.adapter.bpm, 1))

    def test_the_results_card_shows_the_last_cue_pace(self):
        from types import SimpleNamespace
        from finger_rehab.ui.screens import ResultsScreen
        mode = SimpleNamespace(_bpm_trace=[30.0, 40.0, 52.0],
                               adapter=SimpleNamespace(bpm=60.0))
        eng = SimpleNamespace(current_block="adaptive", session=None,
                              mode=mode, _block_bpm_max=52.0,
                              _block_bpm_min=30.0)
        got = ResultsScreen._adaptive_summary(SimpleNamespace(engine=eng))
        self.assertEqual(got["bpm_final"], 52.0)
        self.assertLessEqual(got["bpm_final"], got["bpm_max"])


class ConfigTests(unittest.TestCase):

    def test_the_battery_floor_and_the_carry_window(self):
        from finger_rehab.config import Config
        from finger_rehab.game.battery import resolved_overrides
        cfg = Config.load()
        self.assertEqual(cfg.get("adaptive.carry_ms"), 150)
        self.assertEqual(cfg.get("adaptive.bpm_min"), 10)
        for preset in ("study_battery", "trial_60", "trial_30"):
            self.assertEqual(resolved_overrides(cfg, preset)["adaptive"]
                             ["bpm_min"], 30, preset)

    def test_the_card_and_the_run_sheet_say_what_the_game_asks(self):
        from finger_rehab.ui.feedback_bank import offending
        from finger_rehab.ui.screens import GameplayScreen
        line = " ".join(GameplayScreen.GET_READY_LINES["adaptive"])
        self.assertEqual(line, "Press the finger that lights up, before its "
                               "bar runs out. Keep up and it speeds up; it "
                               "eases off when you need it.")
        self.assertEqual(offending(line), [])
        sheet = (APP / "docs" / "study_day" / "run_sheet.md").read_text(
            encoding="utf-8")
        self.assertIn('Adaptive: "Press the finger that lights up', sheet)

    def test_the_cap_comment_no_longer_rests_on_a_280_ms_hand(self):
        text = (APP / "finger_rehab" / "analytics" / "adaptive.py") \
            .read_text(encoding="utf-8")
        self.assertIn("a guard\n    # that healthy hands do not reach", text)
        self.assertIn("Hodges and Lohse 2022", text)


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_the_pace_fit_finds_the_hand(self):
        import numpy as np
        ra = self.ra
        rng = np.random.default_rng(4)
        w0 = 420.0
        windows = rng.uniform(300, 700, 400)
        p = 0.98 / (1 + np.exp(-0.03 * (windows - w0)))
        hits = (rng.random(400) < p).astype(float)
        pace = ra.adaptive_pace_at_target(windows, hits)
        w_t = 0.9 * 60000.0 / pace
        want = w0 - np.log(0.98 / 0.725 - 1) / 0.03
        self.assertLess(abs(w_t - want), 25.0)
        self.assertTrue(np.isnan(ra.adaptive_pace_at_target(windows,
                                                            np.ones(400))))

    def test_the_controller_rows_carry_the_steady_pace(self):
        import pandas as pd
        ra = self.ra
        bpm = [30 + 4 * i for i in range(20)] + [100.0] * 20
        rows = pd.DataFrame({
            "trial": range(1, 41), "bpm_at_trial": bpm,
            "early_late": ["Good"] * 20 + ["Good", "Miss"] * 10,
            "time_difference_ms": [300.0] * 40,
            "in_recovery": [False] * 40, "lane": [1, 2, 3, 4] * 10,
            "first_incorrect_lane": [None] * 40,
            "first_incorrect_ms": [None] * 40,
            "mode": "adaptive", "error_type": "", "game": "g1"})
        got = ra.adaptive_controller_rows(rows)
        self.assertEqual(got["steady_pace_bpm"], 100.0)
        self.assertAlmostEqual(got["post_climb_hit_rate"], 0.5)
        self.assertEqual(got["pace_below_start"], 0.0)
        self.assertEqual(got["fast_hits"], 0.0)

    def test_a6_is_a_feasibility_check_and_the_text_is_corrected(self):
        ra = self.ra
        self.assertIn("too easy", ra.band_side(0.95))
        self.assertNotIn("nothing to learn", ra.band_side.__doc__)
        spec = {s["id"]: s for s in ra.MODE_LIT["adaptive"]}
        self.assertIn("Al-Fawakhiri", spec["A2"]["source"])
        self.assertIn("22 to 34", spec["A3"]["source"])
        limits = " ".join(ra.MODE_CLAIM_LIMITS["adaptive"])
        self.assertIn("overshoots", limits)
        self.assertNotIn("Read the peak.", limits)
        have = {(m, k) for m, k, _u in ra.COHORT_SECOND_GO_METRICS}
        self.assertIn(("adaptive", "steady_pace_bpm"), have)


if __name__ == "__main__":
    unittest.main()
