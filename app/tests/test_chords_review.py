"""Chords faults from the 27 September 2026 code review, each
reproduced before it was fixed.

Game side: forces divided newtons by counts, so over-force and the
light band never fired; the row label followed the first finger's
speed rather than the outcome class; a partial chord was logged as a
timeout with byte 130; cue-misread chords fed median_er; the medians
were upper medians; an exact 30-point drop missed the fatigue guard;
countdown test presses were booked as idle presses; the quiet gate
fired chords into a dead board and never dealt the voided chord
again; and a skip of the gate did nothing while a finger was down.

Notebook side: clean_hit_rate was a speed rate; chord_frame counted
partial and wrong-press chords as enslaving; C2 made up the
four-finger chord's ER and hid its ER half behind a hit rate at
ceiling; C3 pooled trials rather than people; W4 read thirds of the
ER series instead of the design's sub-block contrast; and
over_force_rate was never emitted.
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_chords_mode import (_build_mode, _complete_chord,  # noqa: E402
                                    _force_pair, _press)

N_PER_COUNT = 0.019531
REFS = {0: 50.0, 1: 32.5, 2: 37.5, 3: 115.0}


def _pair(**over):
    engine, mode = _build_mode(**over)
    mode._reference_counts = lambda lane: REFS[lane]
    _force_pair(mode)
    mode._fire(5.0)
    targets = list(mode.active.targets)
    quiet = [l for l in mode.lanes if l not in targets]
    return engine, mode, targets, quiet


def _peaks_in_newtons(engine, peaks_counts):
    engine._force_cal_n_per_count = lambda: N_PER_COUNT
    engine._force_window_peak = {l: v * N_PER_COUNT
                                 for l, v in peaks_counts.items()}
    engine._force_window_saw_samples = True


class ForceUnitTests(unittest.TestCase):

    def test_a_press_at_the_light_press_reads_one(self):
        engine, mode, targets, _q = _pair()
        _peaks_in_newtons(engine, {l: REFS[l] for l in targets})
        _complete_chord(mode, 5.4, gap_s=0.01)
        rec = mode._records[-1]
        self.assertAlmostEqual(rec["press_norm"], 1.0, places=3)
        self.assertTrue(rec["light"])
        self.assertFalse(rec["over_force"])

    def test_three_times_the_light_press_is_over_force(self):
        engine, mode, targets, _q = _pair()
        _peaks_in_newtons(engine, {l: 3.0 * REFS[l] for l in targets})
        _complete_chord(mode, 5.4, gap_s=0.01)
        rec = mode._records[-1]
        self.assertTrue(rec["over_force"])
        self.assertEqual(rec["class"], "over_force")


class LabelFollowsClassTests(unittest.TestCase):

    def test_a_slow_clean_chord_is_a_full_hit(self):
        engine, mode, targets, _q = _pair()
        _complete_chord(mode, 5.0 + 0.62, gap_s=0.01)
        rec = mode._records[-1]
        self.assertEqual(rec["class"], "hit")
        outcome = engine.log_trial.call_args[0][1]
        self.assertIn(outcome.label, ("Perfect", "Great", "Good"))
        self.assertIsNone(engine.log_trial.call_args.kwargs["error_type"])

    def test_a_chord_that_landed_but_is_not_clean_reads_late(self):
        engine, mode, targets, quiet = _pair()
        peaks = {l: REFS[l] for l in targets}
        peaks[quiet[0]] = 0.5 * REFS[quiet[0]]
        engine._force_window_peak = peaks
        engine._force_window_saw_samples = True
        _complete_chord(mode, 5.3, gap_s=0.01)
        self.assertEqual(mode._records[-1]["class"], "leak_fail")
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Late")
        self.assertEqual(engine.log_trial.call_args.kwargs["error_type"],
                         "leak_fail")


class PartialChordTests(unittest.TestCase):

    def test_a_partial_chord_is_not_a_timeout(self):
        engine, mode, targets, _q = _pair()
        sent = []
        engine._eeg_send = lambda code, lane=None, t_event=None: \
            sent.append((code, lane, t_event))
        mode._handle_press(_press(targets[0], 5.4), 5.4)
        mode._finish(9.0, hold_achieved=None)
        kw = engine.log_trial.call_args.kwargs
        self.assertEqual(kw["error_type"], "partial")
        self.assertAlmostEqual(kw["response_t_perf"], 5.4)
        self.assertEqual(sent, [(100 + targets[0], targets[0], 5.4)])

    def test_a_chord_with_no_press_stays_a_timeout(self):
        engine, mode, _t, _q = _pair()
        mode._finish(9.0, hold_achieved=None)
        kw = engine.log_trial.call_args.kwargs
        self.assertIsNone(kw["error_type"])
        self.assertIsNone(kw["response_t_perf"])


class WrongPressErTests(unittest.TestCase):

    def test_a_cue_misread_chord_has_no_er(self):
        engine, mode, targets, quiet = _pair()
        peaks = {l: REFS[l] for l in targets}
        peaks[quiet[0]] = REFS[quiet[0]]          # the quiet finger pressed
        engine._force_window_peak = peaks
        engine._force_window_saw_samples = True
        mode._handle_press(_press(quiet[0], 5.2), 5.2)
        _complete_chord(mode, 5.3, gap_s=0.01)
        rec = mode._records[-1]
        self.assertTrue(rec["wrong"])
        self.assertIsNone(rec["er"])


class MedianTests(unittest.TestCase):

    def test_block_medians_are_true_medians(self):
        engine, mode = _build_mode()
        mode._reference_counts = lambda lane: REFS[lane]
        t = 5.0
        ers = []
        for leak in (0.02, 0.06):
            _force_pair(mode)
            mode._fire(t)
            targets = list(mode.active.targets)
            quiet = [l for l in mode.lanes if l not in targets]
            peaks = {l: REFS[l] for l in targets}
            for q in quiet:
                peaks[q] = leak * REFS[q]
            engine._force_window_peak = peaks
            engine._force_window_saw_samples = True
            _complete_chord(mode, t + 0.3, gap_s=0.01)
            ers.append(mode._records[-1]["er"])
            t += 5.0
        stats = mode.block_stats()
        self.assertAlmostEqual(stats["median_er"],
                               round((ers[0] + ers[1]) / 2, 3), places=3)


class FatigueBoundaryTests(unittest.TestCase):

    def test_an_exact_thirty_point_drop_is_flagged(self):
        _engine, mode = _build_mode()
        mode._sub_stats = [
            {"subblock": 1, "scope": "within", "hit_rate": 0.7,
             "median_rt_ms": 500.0},
            {"subblock": 2, "scope": "within", "hit_rate": 0.4,
             "median_rt_ms": 500.0}]
        self.assertTrue(mode._fatigue_check(mode._sub_stats[-1]))


class CountdownPressTests(unittest.TestCase):

    def test_test_presses_in_the_countdown_are_not_idle_presses(self):
        engine, mode = _build_mode()
        for i in range(3):
            mode.queue_press(_press(i, 1.0 + i * 0.2))
        mode.prep_tick(1.0 / 60.0)
        mode.update(1.0 / 60.0)
        engine.apply_idle_press_penalty.assert_not_called()


class SettleGateTests(unittest.TestCase):

    def _fsr_mode(self):
        engine, mode = _build_mode(iti_min_s=0.0, iti_max_s=0.0)
        mode._fsr = True
        det = MagicMock()
        det.pressed = [False, False, False, False]
        mode._hand_detector = lambda hand: det
        engine.source.is_connected = True
        engine._hands_down = set()
        return engine, mode, det

    def test_the_gate_holds_while_the_board_is_away(self):
        engine, mode, _det = self._fsr_mode()
        mode._arm_next(0.0)
        engine.source.is_connected = False
        for i in range(1200):
            mode._update_settle(i / 60.0)
        self.assertIsNone(mode.active)
        self.assertEqual(mode.trial_counter, 0)

    def test_a_dropped_chord_is_dealt_again(self):
        engine, mode, _det = self._fsr_mode()
        mode._arm_next(0.0)
        mode._update_settle(0.0)
        mode._update_settle(1.0)
        first = mode.active
        self.assertIsNotNone(first)
        mode._finish_device_drop(1.5)
        mode._update_settle(2.0)
        mode._update_settle(3.0)
        again = mode.active
        self.assertIsNotNone(again)
        self.assertEqual(again.targets, first.targets)
        self.assertEqual(again.kind, first.kind)

    def test_a_skip_releases_the_gate_with_a_finger_down(self):
        engine, mode, det = self._fsr_mode()
        mode._arm_next(0.0)
        det.pressed = [False, True, False, False]
        mode._update_settle(0.5)
        self.assertIsNone(mode.active)
        mode._force_settle(1.0)
        mode._update_settle(1.02)
        self.assertIsNotNone(mode.active)


# ---- notebook ------------------------------------------------------------


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def _rows(self):
        import pandas as pd
        base = dict(mode="chords", game="g1", session="s1",
                    hand_mode="right", side="right",
                    correct_keys="1,2", error_type="")
        rows = [
            # A clean chord, slow: Good under the new labels.
            dict(base, stimulus="1+2", early_late="Good",
                 had_incorrect_press=False,
                 force_window_peaks="1:10;2:10;3:0.5;4:0.2"),
            # A partial: Miss, no ER.
            dict(base, stimulus="1+2", early_late="Miss",
                 had_incorrect_press=False, error_type="partial",
                 force_window_peaks="1:10;2:0.4;3:0.4;4:0.2"),
            # The ring finger pressed in error: no ER.
            dict(base, stimulus="1+2", early_late="Miss",
                 had_incorrect_press=True,
                 force_window_peaks="1:10;2:10;3:10;4:0.2"),
            # Landed, not clean.
            dict(base, stimulus="1+2", early_late="Late",
                 had_incorrect_press=False, error_type="no_hold",
                 force_window_peaks="1:10;2:10;3:0.6;4:0.2"),
        ]
        return pd.DataFrame(rows)

    def test_chord_frame_keeps_partials_and_misreads_out_of_er(self):
        cf = self.ra.chord_frame(self._rows())
        self.assertEqual(len(cf), 4)
        self.assertTrue(math.isfinite(cf.iloc[0]["er"]))
        self.assertTrue(math.isnan(cf.iloc[1]["er"]))
        self.assertTrue(math.isnan(cf.iloc[2]["er"]))
        self.assertEqual(cf["clean"].tolist(), [True, False, False, False])

    def test_c2_is_decided_on_the_hit_half(self):
        # Since 1 October 2026 the hit half decides and the ER half is
        # printed as exploratory: at the study's light presses ER does
        # not measure enslaving.
        import pandas as pd
        ra = self.ra
        d = [2.0, 3.0, 2.5, 3.0, 3.0, 3.5, 5.0, 5.5, 6.0, 7.0, 7.5]
        er = [0.02, 0.03, 0.025, 0.03, None, 0.035, 0.05, 0.055, 0.06,
              0.07, 0.075]
        table = pd.DataFrame({"d": d, "hit_rate": [1.0] * 11,
                              "median_er": er})
        verdict, detail, r_hit, r_er, p = ra.chord_c2_halves(table)
        self.assertTrue(math.isnan(r_hit))
        self.assertGreater(r_er, 0.9)
        self.assertEqual(verdict, "no variation")
        self.assertIn("EXPLORATORY", detail)
        self.assertIn("over 10 chord types", detail)
        hits = [1.0, 0.95, 1.0, 0.9, 0.95, 0.9, 0.8, 0.75, 0.7, 0.6, 0.55]
        falling = pd.DataFrame({"d": d, "hit_rate": hits,
                                "median_er": er})
        verdict, _detail, r_hit, _r_er, p = ra.chord_c2_halves(falling)
        self.assertLess(r_hit, -0.9)
        self.assertIs(verdict, True)
        self.assertLess(p, 0.05)

    def _recs(self, n_people=4):
        """Records as block_summary.chords.trials carries them: the
        ring finger leaks most, and one misread cue per person pressed
        the index at full force."""
        people = {}
        for p in range(n_people):
            recs = []
            for sub in (1, 2):
                for k in range(10):
                    leaks = {"2": 0.06 if sub == 1 else 0.04,
                             "3": 0.03}
                    recs.append({"kind": "chord", "scope": "within",
                                 "hand": "right", "class": "hit",
                                 "subblock": sub, "wrong": False,
                                 "over_force": k == 0,
                                 "er": (0.05 if sub == 1 else 0.03)
                                 + 0.001 * p,
                                 "press_norms": {"0": 1.0, "1": 1.0},
                                 "leaks": leaks})
            recs.append({"kind": "chord", "scope": "within",
                         "hand": "right", "class": "leak_fail",
                         "subblock": 1, "wrong": True, "er": None,
                         "over_force": False,
                         "press_norms": {"1": 1.0, "2": 1.0},
                         "leaks": {"0": 1.0, "3": 0.02}})
            people[f"P{p + 1}"] = recs
        return people

    def _frames(self, people):
        return {"chord_records": [(who, "pass1", recs)
                                  for who, recs in people.items()]}

    def test_c3_reads_the_cohort_mean_matrix(self):
        ra = self.ra
        people = self._recs()
        m = ra.chord_conditioned_matrix(people["P1"])
        self.assertTrue(math.isnan(m[1, 0]))       # the misread is out
        self.assertAlmostEqual(m[0, 2], 0.05, places=6)
        c3 = ra._chords_c3_row(self._frames(people), 3)
        self.assertEqual(c3["n"], 4)
        # Reported, not tested, since 1 October 2026.
        self.assertEqual(c3["verdict"], ra._verdict("reported"))
        self.assertEqual(c3["family"], "exploratory")
        self.assertIn("largest on Ring", c3["detail"])
        self.assertAlmostEqual(c3["value"], 0.05, places=6)
        self.assertIsNone(ra._chords_c3_row({}, 3))

    def test_w4_is_the_sub_block_contrast(self):
        ra = self.ra
        # One misread cue per person in sub-block 1: the clean rate
        # rises by 1/11 and ER falls by 0.02 for everyone.
        w4 = ra._chords_w4_row(self._frames(self._recs()), 3)
        self.assertEqual(w4["id"], "W4")
        self.assertEqual(w4["n"], 4)
        # The clean hit rate decides since 1 October 2026; the median
        # ER half is reported beside it.
        self.assertAlmostEqual(w4["value"], 1.0 / 11.0, places=6)
        self.assertEqual(w4["verdict"], ra._verdict(True))
        self.assertIn("clean hit rate +0.09091", w4["detail"])
        self.assertIn("median ER (reported) -0.02", w4["detail"])
        # Every chord clean in both sub-blocks: the deciding half has
        # no variation, and the ER half does not stand in for it.
        clean = {who: [t for t in recs if not t["wrong"]]
                 for who, recs in self._recs().items()}
        w4 = ra._chords_w4_row(self._frames(clean), 3)
        self.assertEqual(w4["verdict"], ra._verdict("no variation"))
        self.assertIn("clean hit rate: no variation", w4["detail"])

    def test_the_cohort_rows_carry_both_rates(self):
        ra = self.ra
        recs = self._recs(1)["P1"]
        block = {"game": "g1", "folder": Path("."), "meta": {},
                 "bs": {"chords": {"trials": recs}},
                 "rows": ra.pd.DataFrame(), "hand": "right",
                 "calset": None, "extra": {}}
        emitted = {m: v for _h, m, v, _n in ra._cohort_chords(block)}
        self.assertAlmostEqual(emitted["clean_hit_rate"], 20 / 21)
        self.assertAlmostEqual(emitted["over_force_rate"], 2 / 21)
        self.assertEqual(len(block["extra"]["chord_records"]), 21)


if __name__ == "__main__":
    unittest.main()
