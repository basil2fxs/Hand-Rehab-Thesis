"""Buzz Hunt after the deep research of 1 October 2026.

The battery plays one 2.0 s response window and three catch trials;
a same-sample tie goes to the finger that buzzed, with the other
finger logged as a co-press; the stage card asks for speed and says
to keep still when nothing buzzes; B2 is exploratory, judged against
the chance its stimulated fingers give and not estimable under five
errors, with everyone who played counted towards its minimum; B3
carries the pooled false alarms with an exact bound; B5 is dropped;
no per-person d-prime; and the claims the research contradicted are
corrected.
"""
from __future__ import annotations

import os
import sys
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_buzz_hunt import (_engine, _mode, _only_stage,  # noqa: E402
                                  _press_event, _to_respond, _to_trial)

APP = Path(__file__).resolve().parents[1]


class TieTests(unittest.TestCase):

    def _loc(self):
        return _only_stage(_mode(_engine(), catch_rate=0.0), "loc", 2)

    def test_the_target_wins_a_same_sample_tie(self):
        m = self._loc()
        t = _to_respond(m, _to_trial(m))
        target = m.lane
        other = target - 1 if target > 0 else target + 1
        # The detector reports one sample's presses in lane order, so
        # the neighbour arrives first in the queue.
        m.queue_press(_press_event(other, t + 0.3))
        m.queue_press(_press_event(target, t + 0.3))
        m._tick(t + 0.31)
        self.assertEqual(m.phase, "feedback")
        self.assertTrue(m._loc_records[0]["correct"])
        row = m.engine.trial_logger.rows[0]
        self.assertNotEqual(row["early_late"], "Miss")
        self.assertIn(f"co_press={other}", row["stimulus"])

    def test_a_lone_wrong_finger_is_still_wrong(self):
        m = self._loc()
        t = _to_respond(m, _to_trial(m))
        target = m.lane
        other = target - 1 if target > 0 else target + 1
        m.queue_press(_press_event(other, t + 0.3))
        m._tick(t + 0.31)
        self.assertFalse(m._loc_records[0]["correct"])
        row = m.engine.trial_logger.rows[0]
        self.assertEqual(row["early_late"], "Miss")
        self.assertIn("co_press=none", row["stimulus"])

    def test_a_later_press_is_not_a_tie(self):
        m = self._loc()
        t = _to_respond(m, _to_trial(m))
        target = m.lane
        other = target - 1 if target > 0 else target + 1
        m.queue_press(_press_event(other, t + 0.3))
        m.queue_press(_press_event(target, t + 0.305))
        m._tick(t + 0.31)
        self.assertFalse(m._loc_records[0]["correct"])


class BatteryTests(unittest.TestCase):

    def test_the_battery_plays_one_window_and_three_catch_trials(self):
        from finger_rehab.config import Config
        from finger_rehab.game.battery import resolved_overrides
        cfg = Config.load()
        for preset in ("study_battery", "trial_60", "trial_30",
                       "trial_15"):
            bh = resolved_overrides(cfg, preset)["buzz_hunt"]
            self.assertEqual(bh["window_levels_s"], [2.0], preset)
            self.assertEqual(bh["catch_rate"], 0.2, preset)
        full = _mode(_engine(), loc_trials_per_hand=16, catch_rate=0.2)
        self.assertEqual(full.n_catch_planned, 3)
        short = _mode(_engine(), loc_trials_per_hand=8, catch_rate=0.2)
        self.assertEqual(short.n_catch_planned, 2)

    def test_a_one_rung_window_never_moves(self):
        from finger_rehab.game.modes.buzz_hunt import WindowLadder
        ladder = WindowLadder([2.0])
        for _i in range(16):
            self.assertIsNone(ladder.record(True))
        self.assertEqual(ladder.level, 0)
        self.assertEqual(ladder.summary()["top_level"], 0)


class WordingTests(unittest.TestCase):

    def test_the_card_asks_for_speed_and_stillness(self):
        from finger_rehab.ui.buzz_hunt_screen import STAGE_LINES
        head, body = STAGE_LINES["loc"]
        self.assertEqual(head, "One finger will buzz. Press that finger "
                               "as fast as you can.")
        self.assertEqual(body, "Rest your fingertips on the pads and your "
                               "eyes on the dot. Sometimes nothing "
                               "buzzes: then keep still.")
        sheet = (APP / "docs" / "study_day" / "run_sheet.md").read_text(
            encoding="utf-8")
        self.assertIn('Buzz Hunt: "When a finger buzzes, press that '
                      'finger as fast as', sheet)

    def test_a_long_card_line_wraps_at_a_sentence(self):
        import pygame
        pygame.init()
        from finger_rehab.ui.buzz_hunt_screen import STAGE_LINES, _wrap
        from finger_rehab.ui.widgets import FONT_BODY, Layout
        font = Layout(1280, 800, 1.25).font(FONT_BODY)
        lines = _wrap(font, STAGE_LINES["loc"][1], 1160)
        self.assertEqual(lines, ["Rest your fingertips on the pads and "
                                 "your eyes on the dot.",
                                 "Sometimes nothing buzzes: then keep "
                                 "still."])
        self.assertEqual(len(_wrap(Layout(1280, 800).font(FONT_BODY),
                                   STAGE_LINES["loc"][1], 1160)), 1)

    def test_the_contradicted_claims_are_gone(self):
        bh = (APP / "finger_rehab" / "game" / "modes" / "buzz_hunt.py") \
            .read_text(encoding="utf-8")
        self.assertNotIn("reaches full amplitude, and it sits", bh)
        self.assertNotIn("Roughly half of stroke survivors", bh)
        self.assertNotIn("digital\nanalogue", bh)
        self.assertNotIn("caps far below visual span", bh)
        self.assertIn("Connell, Lincoln and Radford 2008", bh)
        cfg = (APP / "config" / "default.yaml").read_text(encoding="utf-8")
        self.assertNotIn("rise to\n  # full amplitude 87 ms", cfg)
        self.assertNotIn("about 130 ms to reach full amplitude", cfg)
        eng = (APP / "finger_rehab" / "game" / "engine.py").read_text(
            encoding="utf-8")
        self.assertNotIn("87 ms to\n    # reach full amplitude", eng)
        self.assertNotIn("syllables' and buzz_hunt's is spawn-to-press", eng)


class MotorSpectrumTests(unittest.TestCase):
    """The bench reads each motor's strongest sound frequency and its
    level above the room from the pulses it already times."""

    def _buzz(self, hz):
        import numpy as np
        from finger_rehab.audio import latency_measure as lm
        sr = lm.SR
        rng = np.random.default_rng(5)
        data = rng.normal(0, 0.01, 12 * sr)
        t0, cmds = 50.0, []
        for k in range(10):
            tc = 1.0 + k * 1.0
            cmds.append(t0 + tc)
            i = int((tc + 0.075) * sr)
            n = int(0.19 * sr)
            data[i:i + n] += 0.2 * np.sin(2 * np.pi * hz * np.arange(n) / sr)
        return lm.pulse_spectrum(data, t0, cmds)

    def test_the_peak_and_the_level(self):
        for hz in (180.0, 240.0):
            got = self._buzz(hz)
            self.assertAlmostEqual(got["peak_hz"], hz, delta=4.0)
            self.assertGreater(got["above_room_db"], 15.0)

    def test_the_measure_step_saves_the_spectra(self):
        from finger_rehab.audio import latency_measure as lm
        rows = [{"path": "song", "to_mic_ms": v, "usable": True}
                for v in (100, 102, 98)]
        rows += [{"path": "click", "to_mic_ms": v, "usable": True}
                 for v in (90, 92, 88)]

        def fake_motors(_port, _pulses, spectra=None):
            if spectra is not None:
                spectra.update({1: {"peak_hz": 200.0, "above_room_db": 20.0},
                                4: {"peak_hz": 230.0,
                                    "above_room_db": 24.0}})
            return {1: 93, 2: 95, 3: 95, 4: 99}

        with unittest.mock.patch.object(lm, "coreaudio_input_ms",
                                        return_value=(20.0, {})), \
                unittest.mock.patch.object(lm, "run_sound",
                                           return_value=rows), \
                unittest.mock.patch.object(lm, "run_motors", fake_motors):
            res = lm.measure(Path("song.mp3"), "COM3", say=lambda _s: None)
        self.assertEqual(res["detail"]["motor_sound_peak_hz"],
                         {1: 200.0, 4: 230.0})
        self.assertEqual(res["detail"]["motor_sound_above_room_db"][4], 24.0)


def _long(ra, people):
    """people: participant -> {metric: (value, n)}."""
    import pandas as pd
    cols = ra.COHORT_LONG_COLS
    rows = []
    for who, metrics in people.items():
        for metric, (value, n) in metrics.items():
            r = {c: None for c in cols}
            r.update(participant=who, phase="pass1", hand="right",
                     hand_role="dominant", mode="buzz_hunt", metric=metric,
                     value=value, n_trials=n)
            rows.append(r)
    return pd.DataFrame(rows, columns=cols)


def _errors(n, adjacent, p):
    return [{"adjacent": i < adjacent, "p_adjacent": p, "co_press": False}
            for i in range(n)]


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_chance_follows_the_finger_that_buzzed(self):
        ra = self.ra
        lanes = [0, 1, 2, 3]
        self.assertAlmostEqual(ra.bh_neighbour_chance(0, lanes), 1 / 3)
        self.assertAlmostEqual(ra.bh_neighbour_chance(1, lanes), 2 / 3)
        self.assertAlmostEqual(ra.bh_neighbour_chance(2, lanes), 2 / 3)
        self.assertAlmostEqual(ra.bh_neighbour_chance(3, lanes), 1 / 3)
        # Averaged over the four fingers, the registered 0.5.
        self.assertAlmostEqual(sum(ra.bh_neighbour_chance(s, lanes)
                                   for s in lanes) / 4, 0.5)

    def test_the_exact_tails_and_bounds(self):
        ra = self.ra
        self.assertAlmostEqual(ra.poisson_binomial_tail([0.5] * 5, 5),
                               1 / 32)
        self.assertAlmostEqual(ra.poisson_binomial_tail([1 / 3, 2 / 3], 2),
                               2 / 9)
        self.assertEqual(ra.poisson_binomial_tail([0.4], 0), 1.0)
        self.assertAlmostEqual(ra.clopper_pearson_upper(0, 20), 0.1391,
                               places=4)
        self.assertAlmostEqual(ra.clopper_pearson_upper(0, 29), 0.0981,
                               places=4)
        self.assertAlmostEqual(ra.clopper_pearson_upper(0, 30), 0.0950,
                               places=4)
        try:
            from scipy import stats
        except ImportError:
            return
        self.assertAlmostEqual(ra.clopper_pearson_upper(2, 30),
                               float(stats.beta.ppf(0.95, 3, 28)), places=5)

    def test_b2_counts_everyone_and_is_not_estimable_under_five(self):
        ra = self.ra
        people = {f"P{i:02d}": {"wrong_finger_errors": (0, 16)}
                  for i in range(10)}
        people["P01"] = {"wrong_finger_errors": (1, 16)}
        people["P02"] = {"wrong_finger_errors": (1, 16)}
        frames = {"bh_errors": [(w, "pass1", []) for w in people]}
        frames["bh_errors"][1] = ("P01", "pass1", _errors(1, 1, 2 / 3))
        frames["bh_errors"][2] = ("P02", "pass1", _errors(1, 1, 1 / 3))
        row = ra._b2_binomial_row(_long(ra, people), 8, frames)
        self.assertEqual(row["n"], 10)
        self.assertEqual(row["verdict"], "not testable")
        self.assertIn("not estimable", row["detail"])
        self.assertEqual(row["family"], "exploratory")
        self.assertNotIn("B2", ra.COHORT_PRESPECIFIED)

    def test_b2_reads_the_conditional_chance(self):
        ra = self.ra
        people = {f"P{i:02d}": {"wrong_finger_errors": (0, 16)}
                  for i in range(10)}
        # Twelve errors, every one after a middle or ring target, ten of
        # them on a neighbour: what random wrong fingers give there.
        frames = {"bh_errors": [("P00", "pass1",
                                 _errors(12, 10, 2 / 3))]}
        people["P00"] = {"wrong_finger_errors": (12, 16)}
        row = ra._b2_binomial_row(_long(ra, people), 8, frames)
        self.assertAlmostEqual(row["reference"], 2 / 3, places=3)
        self.assertEqual(row["verdict"], "fail")
        self.assertAlmostEqual(row["p"], 0.1811, places=3)
        # The registered flat 0.5 would have called it a pass.
        self.assertIn("against the registered flat 0.5, binomial p 0.019",
                      row["detail"])
        # Twelve of twelve beats even the conditional chance.
        frames = {"bh_errors": [("P00", "pass1",
                                 _errors(12, 12, 2 / 3))]}
        row = ra._b2_binomial_row(_long(ra, people), 8, frames)
        self.assertEqual(row["verdict"], "pass")
        self.assertAlmostEqual(row["p"], (2 / 3) ** 12, places=6)

    def test_b3_carries_the_pooled_bound(self):
        ra = self.ra
        people = {f"P{i:02d}": {"catch_fa_count": (0, 3),
                                "catch_fa_rate": (0.0, 3)}
                  for i in range(10)}
        text = ra._bh_pooled_fa_text(_long(ra, people))
        self.assertIn("pooled 0 false alarm(s) in 30 catch trials", text)
        self.assertIn("9.5 percent", text)

    def test_b5_is_dropped_and_the_sources_are_re_anchored(self):
        ra = self.ra
        row = ra._dropped_row("B5")
        self.assertEqual(row["verdict"], "dropped")
        spec = {s["id"]: s for s in ra.MODE_LIT["buzz_hunt"]}
        self.assertIn("absent", spec["B5"])
        self.assertIn("Levi and Heled 2024", spec["B4"]["source"])
        self.assertIn("rated best", spec["B6"]["claim"])
        self.assertNotIn("actually deliver", spec["B6"]["claim"])
        self.assertIn("exploratory", spec["B2"]["claim"])
        self.assertEqual(ra.COHORT_WITHIN_BLOCK_READING["buzz_hunt"][0],
                         "clean")
        self.assertNotIn(("buzz_hunt", "d_prime"), ra.COHORT_METRICS)

    def test_the_cohort_rows_split_misses_and_drop_d_prime(self):
        import pandas as pd
        from tests.test_buzz_hunt_review import _loc_row
        ra = self.ra
        rows = [_loc_row(i, rt=300.0 + 10 * i) for i in range(1, 9)]
        rows.append(_loc_row(9, rt=150.0))                 # too fast
        miss = _loc_row(10, correct=False, lane=1, press=2)
        miss["first_incorrect_ms"] = 420.0
        rows.append(miss)                                  # a neighbour
        rows.append(_loc_row(11, correct=False, press=""))  # no press
        rows.append(dict(_loc_row(12), stimulus="loc;catch",
                         early_late="CatchOk", keys_pressed="",
                         time_difference_ms=None))
        rows.append(dict(_loc_row(13), stimulus=(
            "span;len=3;hebb=0;played=0-1-2;pressed=0-1-3;"
            "stim_failed=False;wall_forced="), early_late="Miss",
            time_difference_ms=None))
        rows.append(dict(_loc_row(14), stimulus=(
            "span;len=2;hebb=0;played=0-1;pressed=0-1;"
            "stim_failed=False;wall_forced="), early_late="Great",
            time_difference_ms=None))
        bs = {"buzz_hunt": {
            "loc": {"early_presses": 3, "per_hand": {
                "right": {"median_rt_ms": 999.0, "trials": 11}}},
            "window": {"active": True, "levels_s": [2.0],
                       "per_hand": {"right": {"top_level": 0,
                                              "trace": [0] * 11}}},
            "span": {"trials": 2, "max_correct": 2}}}
        block = {"game": "g1", "folder": None, "meta": {}, "bs": bs,
                 "rows": pd.DataFrame(rows), "hand": "right",
                 "calset": None, "extra": {}}
        out = {m: (v, n) for _h, m, v, n in ra._cohort_buzz_hunt(block)}
        self.assertEqual(out["wrong_finger_errors"], (1.0, 11))
        self.assertEqual(out["adjacent_errors"][0], 1.0)
        self.assertEqual(out["loc_omissions"], (1.0, 11))
        self.assertAlmostEqual(out["loc_accuracy_answered"][0], 9 / 10)
        self.assertEqual(out["loc_error_rt_ms"][0], 420.0)
        self.assertEqual(out["loc_fast_hits"], (1.0, 9))
        # The median comes from the rows, not block_stats' 999.
        self.assertEqual(out["loc_median_rt_ms"][0], 340.0)
        self.assertEqual(out["loc_median_rt_ms_no_fast"][0], 345.0)
        self.assertNotIn("d_prime", out)
        self.assertNotIn("window_top_level", out)
        self.assertAlmostEqual(out["early_press_rate"][0], 3 / 12)
        self.assertAlmostEqual(out["span_item_accuracy"][0],
                               (2 / 3 + 1.0) / 2)
        err = block["extra"]["bh_errors"]
        self.assertEqual(len(err), 1)
        self.assertAlmostEqual(err[0]["p_adjacent"], 1 / 3)
        self.assertEqual([(x["len"], x["correct"])
                          for x in block["extra"]["bh_span"]],
                         [(3, False), (2, True)])

    def test_the_pooled_span_fit_finds_the_midpoint(self):
        import numpy as np
        ra = self.ra
        rng = np.random.default_rng(3)
        recs = []
        for who in range(40):
            for length in (2, 3, 4, 5, 6, 7):
                p = 1.0 / (1.0 + np.exp((length - 4.5) / 0.6))
                recs.append((f"P{who}", length, bool(rng.random() < p)))
        fit = ra.bh_span_fit(recs, n_boot=60)
        self.assertLess(abs(fit["l50"] - 4.5), 0.4)
        self.assertLess(fit["l79"], fit["l50"])
        self.assertLessEqual(fit["l50_ci"][0], fit["l50"])
        self.assertIsNone(ra.bh_span_fit([("P1", 2, True)] * 30))


if __name__ == "__main__":
    unittest.main()
