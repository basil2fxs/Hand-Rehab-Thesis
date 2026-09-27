"""Buzz Hunt faults from the 27 September 2026 code review, each
reproduced before it was fixed.

Game side: every localisation RT ran from the frame before the STIM
command; catch trials were drawn per trial inside the count, so a
fifth of blocks had none and the real trials ran 9 to 16; a catch
counted before it was played; a catch row named no hand; a no-press
close during a board drop moved the ladder; the window level carried
into a retry after a fault; and a gap threshold was reported for a
stage that never ran.

Notebook side: voided and wall-forced rows scored as misses in the
cohort rows; W5 could only ever be decided on the people who missed
most; B2 was met by pure guessing half the time; and the Hebb half of
B4 compared a first exposure with three other lengths.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_buzz_hunt import (_answer_loc, _attach_detectors,  # noqa: E402
                                  _engine, _mode, _next_trial,
                                  _only_stage, _run_frames, _to_respond,
                                  _to_trial)

FRAME = 1.0 / 60.0


class RtAnchorTests(unittest.TestCase):

    def test_rt_runs_from_the_frame_the_stim_command_leaves(self):
        e = _engine()
        _attach_detectors(e)
        starts = []
        orig_start = e.log_segment_start
        e.log_segment_start = lambda name, tid, lane, t: (
            starts.append((name, t)), orig_start(name, tid, lane, t))
        m = _only_stage(_mode(e, catch_rate=0.0), "loc", 2)
        t = _to_trial(m)
        seen = {}

        def hook(mode, now):
            if mode.sub == "play" and "begin" not in seen:
                seen["begin"] = now       # the frame after _begin_play
            if mode.sub == "play" and mode._pulse_idx == 0 \
                    and "dispatch" not in seen:
                seen["dispatch"] = now    # this tick sends the STIM
            return None

        _run_frames(m, t, 3.0, dt=FRAME, hook=hook)
        self.assertIn("dispatch", seen)
        # The hook runs before each step, so the tick that sends the
        # STIM is one frame after the time it recorded. The anchor is
        # that dispatch frame, not the wait frame that planned it.
        dispatch = seen["dispatch"] + FRAME
        self.assertAlmostEqual(m._target_on, dispatch, places=9)
        self.assertAlmostEqual(m._respond_t0, dispatch, places=9)
        self.assertAlmostEqual(m.active.stim_t_perf, dispatch, places=9)
        stim_starts = [t for name, t in starts if name == "stim"]
        self.assertTrue(stim_starts)
        self.assertAlmostEqual(stim_starts[-1], dispatch, places=9)


class CatchDealTests(unittest.TestCase):

    def test_a_fixed_number_of_catch_trials_on_top_of_the_real_ones(self):
        for seed in range(1, 21):
            e = _engine()
            m = _mode(e, loc_trials_per_hand=16, catch_rate=0.1, seed=seed)
            self.assertEqual(m.n_loc_real, 16)
            self.assertEqual(m.n_catch_planned, 2)
            self.assertEqual(m._stage_counts["loc"], 18)
            self.assertEqual(len(m._catch_slots), 2)
            self.assertTrue(all(0 <= p < 18 for p in m._catch_slots))
        st = m.block_stats()
        self.assertEqual(st["catch_planned"], 2)
        self.assertEqual(st["loc_real_planned"], 16)

    def test_a_catch_is_counted_when_it_closes_and_names_its_hand(self):
        e = _engine()
        _attach_detectors(e)
        e.finish_block = lambda: None
        m = _mode(e, loc_trials_per_hand=4, catch_rate=0.25, seed=3)
        m = _only_stage(m, "loc", 5)
        self.assertEqual(len(m._catch_slots), 1)
        t = _to_trial(m)
        for i in range(5):
            t = _to_respond(m, t)
            if m.catch:
                self.assertEqual(m._catch_n, 0)
                t = _run_frames(m, t, m.response_window_s + 0.3, dt=FRAME)
            else:
                t = _answer_loc(m, t)
            if i < 4:
                t = _next_trial(m, t)
        # The last trial's feedback runs out and the block ends.
        t += m.rest_s + 0.05
        m._tick(t)
        self.assertEqual(m.phase, "done")
        st = m.block_stats()
        self.assertEqual(st["loc"]["catch"]["n"], 1)
        self.assertEqual(st["loc"]["trials"], 4)
        catch_rows = [r for r in e.trial_logger.rows
                      if "catch" in str(r.get("stimulus", ""))]
        self.assertEqual(len(catch_rows), 1)
        self.assertIn("hand=right", catch_rows[0]["stimulus"])


class DropVoidTests(unittest.TestCase):

    def test_a_no_press_close_during_a_drop_moves_nothing(self):
        e = _engine()
        _attach_detectors(e)
        e._drop_overlaps = lambda hand, t_from, t_to: True
        m = _only_stage(_mode(e, catch_rate=0.0), "loc", 2)
        t = _to_trial(m)
        t = _to_respond(m, t)
        level = m._window["right"].level
        history = list(m._window["right"]._history)
        _run_frames(m, t, m.response_window_s + 0.3, dt=FRAME)
        self.assertEqual(m._loc_records, [])
        self.assertEqual(m._window["right"].level, level)
        self.assertEqual(list(m._window["right"]._history), history)
        self.assertEqual(e.trial_logger.rows[-1]["error_type"],
                         "device_drop")


class CarryTests(unittest.TestCase):

    def test_the_level_carries_only_after_a_completed_block(self):
        e = _engine()
        e.finish_block = lambda: None
        m = _mode(e, catch_rate=0.0)
        m._window["right"].level = 2
        m._end("stim_lost")
        self.assertIsNone(e._buzz_hunt_window_level)
        m2 = _mode(e, catch_rate=0.0)
        self.assertEqual(m2._window["right"].level, 0)
        m2._window["right"].level = 1
        m2._end("completed")
        self.assertEqual(e._buzz_hunt_window_level, {"right": 1})


class GapThresholdTests(unittest.TestCase):

    def test_no_gap_stage_means_no_gap_threshold(self):
        e = _engine()
        m = _mode(e, gap_trials_per_hand=0, catch_rate=0.0)
        st = m.block_stats()
        self.assertEqual(st["gap"]["trials"], 0)
        self.assertEqual(st["gap"]["threshold"], {})


# ---- notebook ------------------------------------------------------------


def _loc_row(i, level=0, correct=True, err="", delivered="TRUE",
             rt=350.0, forced="", lane=1, press=None, game="g1"):
    press = lane if press is None else press
    return dict(mode="buzz_hunt", game=game, session="s1", trial=i,
                lane=lane, keys_pressed=str(press) if not err else
                (str(press) if press else ""),
                stimulus=(f"loc;hand=right;finger=index;dur_ms=150;"
                          f"window_ms=3000;level={level};lured=False;"
                          f"stim_failed={err == 'stim_failed'};"
                          f"wall_forced={forced}"),
                early_late="Good" if correct else "Miss",
                error_type=err, time_difference_ms=rt if correct else None,
                waveform_params="", stim_delivered=delivered,
                participant="P01")


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_voided_rows_are_not_misses(self):
        import pandas as pd
        rows = [_loc_row(i) for i in range(1, 10)]
        rows.append(_loc_row(10, correct=False, err="stim_failed",
                             delivered="FALSE", press=""))
        rows.append(_loc_row(11, correct=False, err="device_drop", press=""))
        bf = self.ra.bh_frame(pd.DataFrame(rows))
        self.assertEqual(int(bf["voided"].sum()), 2)
        block = {"game": "g1", "folder": Path("."), "meta": {},
                 "bs": {"buzz_hunt": {}}, "rows": pd.DataFrame(rows),
                 "hand": "right", "calset": None, "extra": {}}
        emitted = {m: (v, n) for _h, m, v, n
                   in self.ra._cohort_buzz_hunt(block)}
        self.assertAlmostEqual(emitted["loc_accuracy"][0], 1.0)
        self.assertEqual(emitted["loc_accuracy"][1], 9)

    def test_no_gap_threshold_and_no_hebb_half_from_the_battery(self):
        import pandas as pd
        st = {"gap": {"trials": 0,
                      "threshold": {"right": {"final_ms": 320.0,
                                              "n_reversals": 0}}},
              "span": {"trials": 4, "max_correct": 4,
                       "hebb": {"n": 1, "accuracy": 1.0},
                       "novel": {"n": 3, "accuracy": 0.67}}}
        block = {"game": "g1", "folder": Path("."), "meta": {},
                 "bs": {"buzz_hunt": st}, "rows": pd.DataFrame(),
                 "hand": "right", "calset": None, "extra": {}}
        metrics = {m for _h, m, _v, _n in self.ra._cohort_buzz_hunt(block)}
        self.assertNotIn("gap_threshold_ms", metrics)
        self.assertNotIn("gap_at_floor", metrics)
        self.assertNotIn("hebb_minus_novel_acc", metrics)
        self.assertIn("span_max_correct", metrics)

    def test_b2_is_tested_against_chance(self):
        import pandas as pd
        ra = self.ra
        cols = ra.COHORT_LONG_COLS

        def long(share, n_err, people=10):
            rows = []
            for i in range(people):
                rows.append({c: None for c in cols})
                rows[-1].update(participant=f"P{i:02d}", phase="pass1",
                                hand="right", hand_role="dominant",
                                mode="buzz_hunt",
                                metric="adjacent_error_share",
                                value=share, n_trials=n_err)
            return pd.DataFrame(rows, columns=cols)

        guessing = ra._b2_binomial_row(long(0.5, 4), 3)
        self.assertEqual(guessing["verdict"], ra._verdict(False))
        clustered = ra._b2_binomial_row(long(0.9, 4), 3)
        self.assertEqual(clustered["verdict"], ra._verdict(True))
        self.assertLess(clustered["p"], 0.05)

    def test_w5_carries_the_level_as_a_covariate(self):
        import pandas as pd
        ra = self.ra
        rows = []
        # Sixteen hits, the ladder promoting after six: RT falls with
        # trial number inside each level, and each level is faster.
        for i in range(1, 17):
            level = 0 if i <= 6 else 1 if i <= 12 else 2
            rt = 400.0 - 10.0 * i - 40.0 * level
            rows.append(_loc_row(i, level=level, rt=rt))
        trials = pd.DataFrame(rows)
        trials["game"] = "g1"
        sel = pd.DataFrame([{"participant": "P01", "phase": "pass1",
                             "mode": "buzz_hunt", "folder": "g1",
                             "dominant_hand": "right", "visit": "1",
                             "day": "2026-08-10"}])
        cohort = {"sel": sel, "trials": trials,
                  "long": pd.DataFrame(columns=ra.COHORT_LONG_COLS)}
        g = ra._bh_level_adjusted_series.__globals__
        real_key = g["game_key"]
        g["game_key"] = lambda f: "g1"
        try:
            adj = ra._bh_level_adjusted_series(cohort)
            fixed = ra._bh_fixed_level_series(cohort)
        finally:
            g["game_key"] = real_key
        self.assertIn("P01", adj)
        self.assertEqual(len(adj["P01"]), 16)
        # Within each level the centred RTs still fall.
        self.assertGreater(adj["P01"][0], adj["P01"][5])
        # The fixed-level series has only the six trials at level 0,
        # under the eight it needs, so it decides nothing.
        self.assertNotIn("P01", fixed)


if __name__ == "__main__":
    unittest.main()
