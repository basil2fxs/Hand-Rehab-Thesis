"""Muscle Memory after the deep research of 1 October 2026.

A battery block takes its probe riffs from the participant seed, so the
60 minute sitting's second block plays the ones the first did not; a
press between cues is logged with what it pressed; the GET READY card
and the run sheet give the usual serial reaction time instruction; no
sitting puts Muscle Memory straight after a game that ends in sequence
recall; a paper awareness check sits before the debrief; and the
notebook reads the check, the old riff intruding into probe errors,
four sensitivity scores, each probe alone and a stratified split-half.
"""
from __future__ import annotations

import os
import random
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_pattern_mode import _build_mode, _press, _seg_index  # noqa: E402

APP = Path(__file__).resolve().parents[1]


def _probes(mode):
    return {s.soc_id for s in mode.segments if s.kind == "probe"}


class ProbeTests(unittest.TestCase):

    def test_the_second_block_plays_the_unused_probes(self):
        _e, one = _build_mode(battery_phase="pass1", block_seed=1)
        _e, two = _build_mode(battery_phase="pass2", block_seed=2)
        self.assertEqual(len(one.probes), 4)
        self.assertEqual(len(_probes(one)), 2)
        self.assertEqual(_probes(one) & _probes(two), set())
        # The first block's choice no longer depends on the block seed.
        _e, again = _build_mode(battery_phase="pass1", block_seed=77)
        self.assertEqual(_probes(again), _probes(one))
        self.assertEqual(one.block_stats()["battery_phase"], "pass1")

    def test_free_play_still_draws_from_the_block_seed(self):
        _e, mode = _build_mode(block_seed=5)
        want = random.Random(5).randrange(len(mode.probes))
        self.assertEqual(mode.probe_offset, want)

    def test_the_trained_successor_follows_the_cycle(self):
        from finger_rehab.game.modes.pattern import trained_successor
        _e, mode = _build_mode()
        cyc = mode.trained
        n = len(cyc)
        for j in range(n):
            self.assertEqual(trained_successor(cyc, cyc[j], cyc[(j + 1) % n]),
                             cyc[(j + 2) % n])
        self.assertIsNone(trained_successor(cyc, cyc[0], cyc[0]))


class BetweenCuePressTests(unittest.TestCase):

    def _at(self, kind, i):
        engine, mode = _build_mode()
        mode.phase = "play"
        mode._seg_idx = _seg_index(mode, kind)
        mode._seg_announced = True
        mode._trial_in_seg = i
        mode.active = None
        return engine, mode, mode.segments[mode._seg_idx]

    def test_a_press_on_the_coming_finger_is_counted(self):
        engine, mode, seg = self._at("seq", 3)
        coming = mode.lanes[seg.fingers[3]]
        mode._handle_press(_press(lane=coming, t=1.0), now=1.0)
        self.assertEqual(mode._rsi_presses[mode._seg_idx], 1)
        self.assertEqual(mode._rsi_match_next[mode._seg_idx], 1)
        args, kwargs = engine.raw_logger.queue_event.call_args
        self.assertEqual(args[0], "pattern_rsi_press")
        self.assertIn(f"coming={coming}", kwargs["detail"])
        seg.n_done = 1          # a take enters per_take once it has run
        per_take = mode.block_stats()["per_take"]
        take = next(d for d in per_take if d["block"] == seg.label)
        self.assertEqual(take["n_rsi_match_next"], 1)

    def test_a_probe_press_on_the_trained_next_finger_is_counted(self):
        from finger_rehab.game.modes.pattern import trained_successor
        engine, mode, seg = self._at("probe", 2)
        succ = trained_successor(mode.trained, seg.fingers[0],
                                 seg.fingers[1])
        self.assertNotEqual(succ, seg.fingers[2])
        mode._handle_press(_press(lane=mode.lanes[succ], t=1.0), now=1.0)
        self.assertEqual(mode._rsi_trained_next[mode._seg_idx], 1)
        self.assertNotIn(mode._seg_idx, mode._rsi_match_next)


class WordingTests(unittest.TestCase):

    def test_the_card_and_the_run_sheet_give_the_instruction(self):
        from finger_rehab.ui.screens import GameplayScreen
        self.assertEqual(" ".join(GameplayScreen.GET_READY_LINES["pattern"]),
                         "Press each finger as it lights up, as quickly "
                         "and accurately as you can.")
        sheet = (APP / "docs" / "study_day" / "run_sheet.md").read_text(
            encoding="utf-8")
        self.assertIn('Muscle Memory: "Press each finger as it lights up',
                      sheet)
        check = sheet.index("Muscle Memory check, BEFORE the debrief")
        self.assertLess(check, sheet.index("Read the [debrief]"))
        self.assertIn("Write\n      24 finger numbers", sheet)

    def test_the_intake_sheet_carries_the_check(self):
        tpl = (APP / "docs" / "study_day" / "intake_sheet_template.csv") \
            .read_text(encoding="utf-8").strip().split(",")
        for col in ("pattern_noticed", "pattern_report",
                    "pattern_generation"):
            self.assertIn(col, tpl)
        sheet = (APP / "docs" / "study_day" / "intake_sheet.md").read_text(
            encoding="utf-8")
        self.assertIn("## Muscle Memory check", sheet)

    def test_the_contradicted_claims_are_gone(self):
        text = (APP / "finger_rehab" / "game" / "modes" / "pattern.py") \
            .read_text(encoding="utf-8")
        self.assertNotIn("one of the most replicated", text)
        self.assertNotIn("fades in minutes", text)
        self.assertIn("Steel et al 2016", text)
        self.assertIn("stayed above zero", text)
        self.assertNotIn("flashes the outcome tier", text)


class OrderTests(unittest.TestCase):

    def test_muscle_memory_never_follows_a_sequence_recall_game(self):
        from finger_rehab.config import Config
        from finger_rehab.game.battery import load_preset
        cfg = Config.load()
        for preset in ("study_battery", "trial_30", "trial_60"):
            orders = load_preset(cfg, preset)["orders"]
            for name, steps in orders.items():
                modes = [s["mode"] for s in steps]
                for i, m in enumerate(modes):
                    if m == "pattern" and i:
                        self.assertNotIn(modes[i - 1],
                                         ("buzz_hunt", "echo"),
                                         f"{preset} {name} step {i + 1}")
        a = [s["mode"] for s in load_preset(cfg)["orders"]["A"]]
        self.assertEqual(a[5:8], ["buzz_hunt", "adaptive", "pattern"])
        b = [s["mode"] for s in load_preset(cfg)["orders"]["B"]]
        self.assertEqual(b[5:8], ["rhythm", "pattern", "echo"])


def _rows(spec):
    """Pattern rows from (take, kind, lane, wrong) tuples, 1-based lanes,
    wrong None for a clean press."""
    import pandas as pd
    out = []
    for i, (take, kind, lane, wrong) in enumerate(spec, start=1):
        out.append({"mode": "pattern", "game": "g1", "session": "s1",
                    "trial": i, "lane": lane,
                    "stimulus": f"{kind};b={take};soc=p0;pos=0",
                    "early_late": "Miss" if wrong else "Good",
                    "time_difference_ms": 400.0,
                    "first_incorrect_lane": wrong, "error_type": "",
                    "pattern_trial": kind == "seq"})
    return pd.DataFrame(out)


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_the_generation_score_sets_recall_against_chance(self):
        ra = self.ra
        trained = ra.pattern_lanes("2,1,3,1,4,2,4,3,2,3,4,1")
        self.assertEqual(trained[:3], [1, 0, 2])
        full = ra.pattern_generation_score(trained, trained * 2, draws=800)
        self.assertEqual(full["triplet_share"], 1.0)
        self.assertTrue(full["above_chance"])
        self.assertGreaterEqual(full["longest_run"], 24)
        self.assertAlmostEqual(full["chance_mean"], 1 / 3, delta=0.05)
        self.assertAlmostEqual(full["chance_p95"], 0.5, delta=0.08)
        probe = ra.pattern_lanes("3,2,1,4,3,1,2,4,1,3,4,2")
        none = ra.pattern_generation_score(trained, probe * 2, draws=800)
        self.assertEqual(none["triplet_share"], 0.0)
        self.assertFalse(none["above_chance"])

    def test_the_awareness_columns_are_read(self):
        ra = self.ra
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "intake_sheet.csv").write_text(
                "participant,edinburgh_lq,music_years,pattern_noticed,"
                "pattern_report,pattern_generation\n"
                "p01,80,0,yes,a repeat,213142432341\n"
                "P02,75,2,no,,\n", encoding="utf-8")
            aw = ra.cohort_intake_awareness(td)
        self.assertEqual(list(aw), ["P01"])
        self.assertTrue(aw["P01"]["noticed"])
        self.assertEqual(aw["P01"]["presses"][:3], [1, 0, 2])

    def test_the_old_riff_intrudes_into_probe_errors(self):
        ra = self.ra
        trained = [1, 0, 2, 0, 3, 1, 3, 2, 1, 2, 3, 0]
        # Probe cues on fingers 0 then 1: the trained riff's next finger
        # after that pair is succ, so a wrong press there intrudes.
        succ = ra.pattern_successor(trained, 0, 1)
        target = next(f for f in range(4) if f not in (succ, 1))
        spec = [("5", "probe", 1, None), ("5", "probe", 2, None),
                ("5", "probe", target + 1, succ + 1)]
        got = ra.pattern_intrusions(_rows(spec), trained)
        self.assertEqual((got["probe_n"], got["probe_k"]), (1, 1))
        # A wrong press on another finger counts but does not intrude.
        other = next(f for f in range(4) if f not in (succ, target))
        spec[2] = ("5", "probe", target + 1, other + 1)
        got = ra.pattern_intrusions(_rows(spec), trained)
        self.assertEqual((got["probe_n"], got["probe_k"]), (1, 0))

    def test_the_take_table_can_leave_reversals_out(self):
        ra = self.ra
        spec = [("3", "seq", lane, None) for lane in (1, 2, 1, 3, 4, 3)]
        full = ra.pattern_take_table(_rows(spec))
        norev = ra.pattern_take_table(_rows(spec), drop_reversals=True)
        self.assertEqual(int(full["n_rt"].iloc[0]), 6)
        # Trials 3 (1-2-1) and 6 (3-4-3) are reversals.
        self.assertEqual(int(norev["n_rt"].iloc[0]), 4)

    def test_the_probe_interval_matches_the_point_estimate(self):
        import numpy as np
        ra = self.ra
        rng = np.random.default_rng(1)
        probe = 450 + rng.normal(0, 30, 20)
        fl = [400 + rng.normal(0, 30, 20), 410 + rng.normal(0, 30, 5)]
        lo, hi = ra._mean_of_means_ci(probe, fl)
        point = probe.mean() - np.mean([f.mean() for f in fl])
        self.assertLess(lo, point)
        self.assertGreater(hi, point)

    def test_p2_under_the_minimum_prints_each_person(self):
        import pandas as pd
        ra = self.ra
        cols = ra.COHORT_LONG_COLS
        rows = []
        for who, a, b in (("P01", 20.0, 31.0), ("P02", 15.0, 9.0)):
            for phase, v in (("pass1", a), ("pass2", b)):
                r = {c: None for c in cols}
                r.update(participant=who, phase=phase, hand="right",
                         hand_role="dominant", mode="pattern",
                         metric="learning_score_ms", value=v, n_trials=2)
                rows.append(r)
        long = pd.DataFrame(rows, columns=cols)
        frames = {"pattern_probes": [("P01", "pass1", ["p0", "p1"]),
                                     ("P01", "pass2", ["p1", "p2"]),
                                     ("P02", "pass1", ["p0", "p1"]),
                                     ("P02", "pass2", ["p2", "p3"])]}
        row = ra._p2_row(long, 8, frames)
        self.assertIn("P01 +11", row["detail"])
        self.assertIn("P02 -6", row["detail"])
        self.assertIn("repeated between the blocks for P01", row["detail"])

    def test_p3i_is_an_exploratory_row(self):
        ra = self.ra
        frames = {"pattern_intrusions": [
            (f"P{i:02d}", "pass1", {"probe_n": 5, "probe_k": 3,
                                    "random_n": 6, "random_k": 2})
            for i in range(10)]}
        row = ra._pattern_intrusion_row(frames, 8)
        self.assertEqual(row["id"], "P3i")
        self.assertEqual(row["family"], "exploratory")
        self.assertAlmostEqual(row["value"], 0.6)
        self.assertEqual(row["verdict"], "pass")
        self.assertIn("random take 20 of 60", row["detail"])

    def test_the_split_half_needs_four_people(self):
        ra = self.ra
        self.assertIsNone(ra.pattern_split_half({"sel": None,
                                                 "trials": None}))

    def test_the_literature_rows_carry_the_new_anchors(self):
        ra = self.ra
        spec = {s["id"]: s for s in ra.MODE_LIT["pattern"]}
        self.assertIn("Stark-Inbar", spec["P1"]["source"])
        self.assertIn("10 to 30 ms", spec["P1"]["reference"])
        limits = " ".join(ra.MODE_CLAIM_LIMITS["pattern"])
        self.assertIn("stayed above zero", limits)
        self.assertNotIn("helps serial learning", limits)


if __name__ == "__main__":
    unittest.main()
