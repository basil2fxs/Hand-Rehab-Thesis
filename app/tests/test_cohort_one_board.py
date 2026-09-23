"""The cohort chapter on the shipped design: ONE board, the right-hand
device, and TWO passes.

Six codes play one sitting each through the REAL battery machinery on
the keyboard source, with the one-board preset shortened to three
steps: Reaction and Echo in pass 1, then Reaction again in pass 2
after the rest. Five codes are right-handed and one is left-handed,
so the left-hander's blocks are all on the non-dominant hand. The
folders go through the real notebook functions.

What this pins: pass 2 stays out of every first-pass table; the
left-hander stays out of the pooled numbers and appears in the
handedness table; the two-hand checks print as DROPPED with the
one-board reason; R3 reads pass 2 against pass 1; E1 uses the
four-lane band; and the reliability chapter pairs the passes and
writes its table and figures.
"""
from __future__ import annotations

import contextlib
import io
import random
import sys
import tempfile
import unittest
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tests.test_cohort_notebook import (_drive_echo, _drive_reaction,  # noqa: E402
                                        _load_notebook)

CODES = ("P01", "P02", "P03", "P04", "P05", "P06")
DOMINANT = {"P01": "right", "P02": "right", "P03": "right",
            "P04": "right", "P05": "right", "P06": "left"}
ONE_BOARD_ORDER = [
    {"mode": "reaction", "hand": "right", "phase": "pass1"},
    {"mode": "echo", "hand": "right", "phase": "pass1"},
    {"mode": "reaction", "hand": "right", "phase": "pass2",
     "rest_before": True},
]
# A small practice effect in pass 2, well inside R3's 20 ms margin.
PASS2_SHIFT_MS = -6.0


def _engine(root: Path):
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["session"]["data_dir"] = str(root)
    cfg.data["audio"]["enabled"] = False
    cfg.data["report"] = {"enabled": False}
    cfg.data.setdefault("reaction", {}).update({"seed": 1234,
                                                "catch_rate": 0.0})
    preset = cfg.data["protocol"]["presets"]["study_battery"]
    preset["orders"] = {"A": [dict(s) for s in ONE_BOARD_ORDER],
                        "B": [dict(s) for s in ONE_BOARD_ORDER]}
    preset["overrides"] = {}
    eng = GameEngine(cfg, KeyboardOnlySource())
    eng._screens = eng._build_screens()
    return eng


def write_one_board_cohort(root: Path) -> None:
    import pygame
    pygame.init()
    eng = None
    try:
        eng = _engine(root)
        rng = random.Random(11)
        for i, code in enumerate(CODES):
            dom = DOMINANT[code]
            eng.begin_session(code, str(21 + i), sex="female",
                              dominant_hand=dom,
                              edinburgh_lq="80" if dom == "right" else "-70",
                              visit="1", hand_length_mm="185",
                              hand_breadth_mm="82")
            eng._uncal_ack = {"left", "right"}
            assert eng.start_battery(), "the battery refused to start"
            base = 240.0 + 25.0 * i
            for _ in range(len(ONE_BOARD_ORDER) * 2):
                if not eng.block_is_running():
                    break
                mode = str(eng.current_block)
                if mode == "reaction":
                    shift = (PASS2_SHIFT_MS if eng._current_phase == "pass2"
                             else 0.0)
                    _drive_reaction(eng, str(eng.hand_mode), base + shift,
                                    rng)
                elif mode == "echo":
                    _drive_echo(eng, fail_from=6 + i % 3)
                if eng.block_is_running():
                    eng.finish_block()
                if eng.pending_protocol_step() is None:
                    break
                assert eng.continue_protocol()
            eng.end_session()
    finally:
        if eng is not None:
            try:
                eng._close_loggers()
            except Exception:
                pass
        pygame.quit()


class OneBoardTwoPassCohortTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory()
        cls.root = Path(cls._td.name)
        write_one_board_cohort(cls.root)
        ra = cls.ra = _load_notebook()
        cat = ra.build_catalogue(root=cls.root)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cls.ctx = ra.prepare("latest", root=cls.root)
            cls.cohort = ra.sec_cohort_selection(cat, root=cls.root,
                                                 min_n=3)
            cls.desc = ra.sec_cohort_describe(cls.cohort)
            cls.hands = ra.sec_cohort_hands(cls.cohort)
            cls.within = ra.sec_cohort_within_block(cls.cohort)
            cls.reliability = ra.sec_cohort_reliability(cls.cohort)
            cls.validity = ra.sec_cohort_validity(cls.cohort, cls.within)
            cls.written = ra.sec_cohort_export(cls.cohort)
        cls.out = buf.getvalue()
        import matplotlib.pyplot as plt
        plt.close("all")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def test_the_tree_is_one_board_and_two_passes(self) -> None:
        sel = self.cohort["sel"]
        self.assertTrue(self.ra.cohort_one_board(self.cohort))
        self.assertEqual(set(sel["hand"]), {"right"})
        self.assertEqual(set(sel["phase"]), {"pass1", "pass2"})
        self.assertEqual(len(sel), len(CODES) * len(ONE_BOARD_ORDER))
        self.assertIn("ONE board", self.out)

    def test_pass2_stays_out_of_the_first_pass_tables(self) -> None:
        long = self.cohort["long"]
        self.assertEqual(set(long["phase"]), {"pass1", "pass2"})
        first = self.ra.cohort_battery_rows(long)
        self.assertEqual(set(first["phase"]), {"pass1"})
        # One value per right-hander, not a two-block mean.
        rt = self.ra.cohort_values(long, "reaction", "median_rt_ms")
        self.assertEqual(len(rt), 5)
        p1 = long[(long["phase"] == "pass1") & (long["mode"] == "reaction")
                  & (long["metric"] == "median_rt_ms")].set_index(
                      "participant")["value"]
        for who, v in rt.items():
            self.assertAlmostEqual(v, p1.loc[who])
        self.assertNotIn("more than one battery block", self.out)

    def test_the_left_hander_is_described_not_pooled(self) -> None:
        long = self.cohort["long"]
        self.assertNotIn("P06", self.ra.cohort_primary_people(long))
        self.assertIn("P06", self.out)
        self.assertNotIn("P06", set(
            self.ra.cohort_values(long, "echo", "span").index))
        tbl = self.hands.set_index(["mode", "metric"])
        row = tbl.loc[("reaction", "median_rt_ms")]
        self.assertEqual(row["n_dominant"], 5)
        self.assertEqual(row["n_nondominant"], 1)

    def test_the_two_hand_checks_are_dropped_with_the_reason(self) -> None:
        v = self.validity.set_index("id")
        for cid in ("R2", "C4", "C5", "Rh3", "M1", "M2", "W2", "E3"):
            self.assertEqual(v.loc[cid, "verdict"], "dropped", cid)
            self.assertIn("one-board", str(v.loc[cid, "criterion"]), cid)
        self.assertEqual(v.loc["P2", "verdict"], "dropped")
        # One Rh1 row at most: the dominant hand.
        self.assertLessEqual(int((self.validity["id"] == "Rh1").sum()), 1)

    def test_r3_reads_pass_two_against_pass_one(self) -> None:
        r3 = self.validity.set_index("id").loc["R3"]
        self.assertNotEqual(r3["verdict"], "dropped")
        self.assertEqual(r3["n"], 5)
        self.assertLess(r3["value"], 0)       # the injected practice
        self.assertGreater(r3["value"], -20)
        self.assertEqual(r3["reference"], 20.0)
        self.assertIn("TOST", str(r3["detail"]))

    def test_e1_uses_the_four_lane_band(self) -> None:
        e1 = self.validity.set_index("id").loc["E1"]
        self.assertEqual(tuple(e1["reference"]), (5.0, 9.0))
        self.assertIn("four lanes", e1["check"])

    def test_the_reliability_chapter_pairs_the_passes(self) -> None:
        rel = self.reliability.set_index("id")
        t1 = rel.loc["T1"]
        self.assertEqual(t1["n"], 5)
        self.assertTrue(0.0 < t1["icc21"] <= 1.0)
        self.assertTrue(t1["lo21"] <= t1["icc21"] <= t1["hi21"])
        self.assertLess(t1["bias"], 0)
        self.assertTrue(t1["loa_lo"] < t1["bias"] < t1["loa_hi"])
        self.assertGreater(t1["mdc95"], t1["sem"])
        self.assertIn(t1["reading"], ("as predicted",
                                      "below the prediction",
                                      "above the prediction"))
        # Force Pilot and Chords were not played in this short tree.
        self.assertEqual(rel.loc["T2", "reading"], "no data")
        out_dir = Path(self.cohort["out_dir"])
        self.assertTrue((out_dir / "cohort_reliability.csv").is_file())
        figs = out_dir / "figures"
        self.assertTrue((figs / "cohort_reliability_icc.png").is_file())
        self.assertTrue(
            (figs / "cohort_reliability_bland_altman.png").is_file())
        self.assertIn("UPPER bound on", self.out)

    def test_the_per_session_phase_view_does_not_pool_the_passes(self):
        import pandas as pd
        trials = pd.DataFrame({"participant": ["P01"] * 4,
                               "phase": ["pass1", "pass1", "pass2",
                                         "pass2"]})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            got = self.ra.sec_phase(trials)
        self.assertIsNone(got)
        self.assertIn("cohort reliability chapter", buf.getvalue())


if __name__ == "__main__":
    unittest.main()
