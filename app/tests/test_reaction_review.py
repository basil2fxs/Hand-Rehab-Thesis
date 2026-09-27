"""The Reaction faults a code review found on 27 September 2026, before
any participant, each pinned so it cannot come back.

1. A board drop mid-trial was voided by the engine but still counted
   by the mode as a miss, so lapse_like_rate read a hardware fault as a
   lapse. A press whose window a drop overlapped was kept as a clean RT.
2. The cue order was dealt four at a time, so the fourth cue of every
   bag was the one finger not yet seen: a quarter of the cues could be
   predicted from the three before them.
3. The session best carried from pass 1 into the pass 2 retest block,
   a comparison the design leaves out of the sitting.
4. A late press on the cued finger was logged as a wrong finger.
5. Two fingers crossing on one sample were read in lane order, so a
   neighbour below the cued finger always won the tie.
6. The skipped stability gate was meant to be flagged on the row and
   never was.
7. fp_max at or under fp_min hung the block in the redraw loop.
8. The vs-last chip compared simple against choice RT.
"""
from __future__ import annotations

import math
import os
import random
import sys
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_reaction_mode import _build_mode, _press


class DeviceDropTests(unittest.TestCase):

    def _dropped_engine_mode(self, **kw):
        engine, mode = _build_mode(**kw)
        engine._drop_overlaps = MagicMock(return_value=True)
        return engine, mode

    def test_a_dropped_timeout_is_voided_not_a_miss(self) -> None:
        engine, mode = self._dropped_engine_mode()
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        mode._close_scorable(None, now=14.5)
        self.assertEqual(mode.n_miss, 0)
        self.assertEqual(mode.completed, 0)
        self.assertEqual(mode.n_device_drop, 1)
        self.assertEqual(
            engine.log_trial.call_args.kwargs.get("error_type"),
            "device_drop")
        self.assertIsNone(mode._lapse_like_rate())
        self.assertEqual(mode.block_stats()["n_device_drop"], 1)

    def test_a_press_inside_a_dropped_window_is_not_a_valid_rt(self) -> None:
        engine, mode = self._dropped_engine_mode()
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        lane = mode.active.lane
        mode._handle_press(_press(lane=lane, t=13.2), now=13.2)
        self.assertEqual(mode.n_valid, 0)
        self.assertEqual(mode.n_lapse, 0)
        self.assertEqual(mode._valid_rts, [])
        self.assertEqual(
            engine.log_trial.call_args.kwargs.get("error_type"),
            "device_drop")

    def test_no_drop_keeps_the_ordinary_miss(self) -> None:
        engine, mode = _build_mode()
        engine._drop_overlaps = MagicMock(return_value=False)
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        mode._close_scorable(None, now=14.5)
        self.assertEqual(mode.n_miss, 1)
        self.assertEqual(mode.completed, 1)
        self.assertEqual(mode.n_device_drop, 0)


def _cond_entropy(seqs, k):
    ctx = defaultdict(Counter)
    for s in seqs:
        for i in range(k, len(s)):
            ctx[tuple(s[i - k:i])][s[i]] += 1
    total = sum(sum(c.values()) for c in ctx.values())
    h = 0.0
    for c in ctx.values():
        n = sum(c.values())
        h += n / total * -sum(v / n * math.log2(v / n) for v in c.values())
    return h


class CueOrderTests(unittest.TestCase):

    def test_a_block_is_balanced_with_no_repeat(self) -> None:
        for seed in range(200):
            _, mode = _build_mode(scorable_trials=20, attempt_cap=35,
                                  seed=seed)
            lanes = [mode._next_lane() for _ in range(20)]
            self.assertEqual(Counter(lanes), Counter({0: 5, 1: 5, 2: 5, 3: 5}))
            self.assertTrue(all(a != b for a, b in zip(lanes, lanes[1:])))

    def test_three_cues_do_not_predict_the_fourth(self) -> None:
        # Under the no-repeat rule the most a next cue can hold is
        # log2(3) = 1.585 bits whatever came before. The old bag of
        # four measured 1.41 with three cues of context, because the
        # fourth cue of every bag was forced.
        seqs = []
        for seed in range(2000):
            _, mode = _build_mode(scorable_trials=20, attempt_cap=35,
                                  seed=seed)
            seqs.append([mode._next_lane() for _ in range(20)])
        self.assertGreater(_cond_entropy(seqs, 3), 1.55)

    def test_one_copy_keeps_every_earlier_order(self) -> None:
        # The other modes' seeded orders must not move.
        from finger_rehab.game.scheduling import BalancedScheduler
        a = BalancedScheduler([0, 1, 2, 3], random.Random(9)).sequence(24)
        b = BalancedScheduler([0, 1, 2, 3], random.Random(9),
                              copies=1).sequence(24)
        self.assertEqual(a, b)


class SessionBestTests(unittest.TestCase):

    def test_pass_2_does_not_see_the_pass_1_best(self) -> None:
        engine, mode = _build_mode()
        engine._current_phase = "pass1"
        mode._show_rt_feedback(250.0)
        self.assertEqual(mode.session_best_ms(), 250.0)
        engine._current_phase = "pass2"
        self.assertIsNone(mode.session_best_ms())
        mode._show_rt_feedback(310.0)
        self.assertEqual(mode.session_best_ms(), 310.0)

    def test_outside_a_battery_the_best_carries_across_blocks(self) -> None:
        engine, mode = _build_mode()
        engine._current_phase = ""
        mode._show_rt_feedback(280.0)
        _, later = _build_mode()
        later.engine = engine
        self.assertEqual(later.session_best_ms(), 280.0)


class ResultsCardTests(unittest.TestCase):

    def _hidden(self, progress):
        from finger_rehab.ui.screens import ResultsScreen
        screen = ResultsScreen.__new__(ResultsScreen)
        screen.engine = MagicMock()
        screen.engine.battery_progress = MagicMock(return_value=progress)
        return screen._pass_comparisons_hidden()

    def test_hidden_while_the_battery_runs(self) -> None:
        self.assertTrue(self._hidden({"finished": False, "done": 10,
                                      "of": 12}))

    def test_shown_once_the_battery_is_done_or_outside_one(self) -> None:
        self.assertFalse(self._hidden({"finished": True, "done": 12,
                                       "of": 12}))
        self.assertFalse(self._hidden(None))


class PressTieAndGateTests(unittest.TestCase):

    def test_the_cued_finger_wins_a_same_sample_tie(self) -> None:
        engine, mode = _build_mode()
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        # The neighbour BELOW the cued finger: the detector reports a
        # sample's presses in lane order, so it arrives first.
        mode.active.lane = cued = 2
        other = 1
        mode._phase = "stim"
        t = 12.3
        mode.queue_press(_press(lane=other, t=t))
        mode.queue_press(_press(lane=cued, t=t))
        engine._drop_overlaps = MagicMock(return_value=False)
        import time as _time
        real = _time.perf_counter
        _time.perf_counter = lambda: 12.31
        try:
            mode.update(0.0)
        finally:
            _time.perf_counter = real
        self.assertEqual(mode.n_valid, 1)
        self.assertEqual(mode.n_wrong_choice, 0)
        stim = engine.log_trial.call_args.kwargs.get("stimulus")
        self.assertIn(f";co_press={other}", stim)

    def test_a_skipped_gate_is_written_on_the_false_start_row(self) -> None:
        engine, mode = _build_mode()
        mode.take_skip_flag = MagicMock(return_value="settle")
        mode._begin_trial(now=10.0)
        mode._handle_press(_press(lane=0, t=10.5), now=10.5)
        stim = engine.log_reaction_event.call_args.kwargs.get("stimulus")
        self.assertTrue(stim.endswith(";gate_skipped"))
        self.assertEqual(mode.block_stats()["n_false_start_gate_skipped"], 1)


class ForeperiodGuardTests(unittest.TestCase):

    def test_no_room_above_the_floor_returns_the_floor(self) -> None:
        _, mode = _build_mode(fp_min_s=1.5, fp_max_s=1.0,
                              fp_mean_extra_s=2.5)
        self.assertEqual(mode._draw_foreperiod(), 1.5)

    def test_a_narrow_window_still_draws_inside_it(self) -> None:
        _, mode = _build_mode(fp_min_s=1.5, fp_max_s=1.5001,
                              fp_mean_extra_s=50.0)
        for _ in range(20):
            fp = mode._draw_foreperiod()
            self.assertGreaterEqual(fp, 1.5)
            self.assertLessEqual(fp, 1.5001 + 1e-9)


class VsLastVariantTests(unittest.TestCase):

    def test_simple_and_choice_are_different_variants(self) -> None:
        from finger_rehab.data.history import variant_key
        simple = {"reaction": {"sub_mode": "simple", "fp_mode": "exponential"}}
        choice = {"reaction": {"sub_mode": "choice", "fp_mode": "exponential"}}
        self.assertNotEqual(variant_key("reaction", simple),
                            variant_key("reaction", choice))
        self.assertIsNone(variant_key("chords", choice))


if __name__ == "__main__":
    unittest.main()


class NotebookReactionTests(unittest.TestCase):
    """The notebook side of the same review."""

    @classmethod
    def setUpClass(cls) -> None:
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_cohort_notebook import _load_notebook
        cls.ra = _load_notebook()

    def test_r1_reads_the_median_of_the_signed_rhos(self) -> None:
        # Twelve blocks whose rhos scatter both ways around zero, as a
        # working foreperiod gives at 20 trials: the median of |rho| is
        # 0.17, the median rho is about zero. R1 must pass.
        import contextlib
        import io
        import pandas as pd
        rhos = [0.18, -0.17, 0.16, -0.15, 0.20, -0.19,
                0.12, -0.14, 0.17, -0.16, 0.15, -0.18]
        rows = []
        for i, r in enumerate(rhos):
            for metric, val in (("rho_rt_vs_fp", r),
                                ("false_start_rate", 0.02)):
                rows.append(dict(participant=f"P{i + 1:02d}", phase="pass1",
                                 position=1, visit="1", day="d",
                                 hand="right", hand_role="dominant",
                                 mode="reaction", metric=metric, value=val,
                                 n_trials=20, block_folder="x",
                                 config_hash="h"))
        cohort = {"long": pd.DataFrame(rows), "min_n": 3, "frames": {},
                  "people": pd.DataFrame(), "sel": pd.DataFrame(),
                  "trials": pd.DataFrame(), "metas": {}, "dropped": {},
                  "tables": {}}
        with contextlib.redirect_stdout(io.StringIO()):
            v = self.ra.sec_cohort_validity(cohort, None)
        r1 = v[v["id"] == "R1"].iloc[0]
        self.assertEqual(r1["verdict"], "pass")
        self.assertLess(abs(r1["value"]), 0.05)

    def test_generic_rt_pool_leaves_out_reaction_events(self) -> None:
        import pandas as pd
        trials = pd.DataFrame([
            dict(mode="reaction", time_difference_ms=300.0,
                 early_late="Good", error_type=""),
            dict(mode="reaction", time_difference_ms=40.0,
                 early_late="Early", error_type="anticipation"),
            dict(mode="reaction", time_difference_ms=-20.0,
                 early_late="Early", error_type="false_start"),
            dict(mode="reaction", time_difference_ms=410.0,
                 early_late="Good", error_type="device_drop"),
        ])
        rts = self.ra.reaction_times(trials)
        self.assertEqual(list(rts), [300.0])

    def test_p10_is_the_apps_definition(self) -> None:
        engine, mode = _build_mode()
        rts = [312.0, 280.0, 305.0, 290.0, 330.0, 270.0, 350.0, 299.0,
               301.0, 287.0, 276.0, 318.0, 322.0, 295.0, 284.0, 309.0,
               340.0, 265.0, 303.0, 292.0]
        mode._valid_rts = list(rts)
        mode._valid_fps = [2.0] * len(rts)
        mode._valid_idx = list(range(1, len(rts) + 1))
        self.assertEqual(mode.block_stats()["p10_rt_ms"],
                         round(self.ra.reaction_p10(rts), 1))
