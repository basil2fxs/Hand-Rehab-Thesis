"""The Echo notebook chapter, driven end to end on a real session.

What this pins is the chapter's measurement contract, the pieces the
thesis numbers depend on: span_novel really excludes the hidden Hebb
trials (the inflation guard, reported next to span rather than
silently replacing it), the error taxonomy reads the logged lane
lists correctly (a wrong press of an item that IS in the sequence is
a transposition, not an intrusion), and the claim-limit text that
keeps these spans away from Corsi norms actually prints. The session
folder is written by the REAL GameEngine and EchoMode through the
real TrialLogger, then handed to the REAL notebook functions
(build_catalogue / load_games / load_metas / echo_frame / sec_echo),
the same path test_force_pilot_notebook_levels.py walks for Force Pilot.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import matplotlib
matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_echo_mode import (_make_engine, _press, patched_clock,
                                  setUpModule, tearDownModule)

__all__ = ["setUpModule", "tearDownModule"]


def _load_ra():
    """Exec every notebook cell's definitions into one standalone
    module namespace, the test_force_pilot_notebook_levels pattern
    (a unittest.TestCase cannot request the pytest fixture)."""
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_echo_span"
    cells = _code_cells()
    module = ModuleType(name)
    module.__file__ = str(ROOT / "analysis" / "session_analysis.ipynb")
    sys.modules[name] = module
    ns = module.__dict__
    try:
        for index, lines in cells:
            source = _definitions(index, lines)
            code = compile(source, f"session_analysis.ipynb cell {index}",
                           "exec", flags=FUTURE_FLAGS, dont_inherit=True)
            exec(code, ns)
    finally:
        sys.modules.pop(name, None)
    ns["FIGDIR"] = Path(tempfile.mkdtemp())
    return SimpleNamespace(**{k: v for k, v in ns.items()
                             if not k.startswith("__")})


def _write_session(td: str, clock) -> None:
    """One real Echo demo block on the LEGACY LADDER rule (the fixed
    2, 3, 3 climb): trial 1 (novel, length 2) replayed right, trial 2
    (novel, length 3) failed with a TRANSPOSITION (the wrong press is
    an item of the sequence in the wrong place), trial 3 (the hidden
    Hebb trial, length 3) replayed right. That makes span 3 but
    span_novel 2, the exact case the notebook's inflation guard
    exists for.

    The rule is pinned here rather than left to the config: the
    shipped rule is Simon now, which has no hidden trials at all, and
    this chapter's ladder half must keep being exercised for as long
    as ladder sessions exist on disk. The Simon half of the chapter
    is pinned separately."""
    eng = _make_engine(td)
    eng.cfg.data.setdefault("echo", {})["rule"] = "ladder"
    eng.cfg.data["echo"]["start_len"] = 2
    eng.cfg.data["echo"]["max_len"] = 9
    eng.begin_echo_block()
    mode = eng.mode
    answered = {"n": 0}

    def respond(clk) -> None:
        if mode.phase != "respond" or mode.active is None:
            return
        if mode.trial_counter == answered["n"]:
            return
        answered["n"] = mode.trial_counter
        seq = mode.sequence
        if mode.trial_counter == 2:
            # First item right, then the sequence's own first lane
            # again: in the list, wrong position, so a transposition
            # (never equal to seq[1]: no back-to-back repeats).
            mode.queue_press(_press(seq[0], clk.t))
            mode.queue_press(_press(seq[0], clk.t + 0.3))
            return
        for i, lane in enumerate(seq):
            mode.queue_press(_press(lane, clk.t + 0.3 * i))

    for _ in range(6000):
        if eng.trial_logger is None:
            return
        clock.t += 0.05
        mode.update(0.05)
        respond(clock)


def _write_simon_session(td: str, clock) -> None:
    """One real Simon demo block. Trial 1 (length 1) and trial 2
    (length 2) come back right; trial 3 (length 3) fails on the
    sequence's own second lane played out of place, a TRANSPOSITION at
    serial position 3; the spare life replays the same three items and
    they come back right. Span 3, life spent at 3, recovered."""
    eng = _make_engine(td)
    eng.begin_echo_block()
    mode = eng.mode
    answered = {"n": 0}

    def respond(clk) -> None:
        if mode.phase != "respond" or mode.active is None:
            return
        if mode.trial_counter == answered["n"]:
            return
        answered["n"] = mode.trial_counter
        seq = mode.sequence
        if len(seq) == 3 and not mode.life_trial:
            # Two right, then the SECOND item again: in the list,
            # wrong place, so a transposition at position 3. It must
            # be seq[1] and not seq[0]: no back-to-back repeats means
            # seq[1] can never equal seq[2], while seq[0] sometimes
            # does, which would make the third press correct.
            mode.queue_press(_press(seq[0], clk.t))
            mode.queue_press(_press(seq[1], clk.t + 0.3))
            mode.queue_press(_press(seq[1], clk.t + 0.6))
            return
        for i, lane in enumerate(seq):
            mode.queue_press(_press(lane, clk.t + 0.3 * i))

    for _ in range(6000):
        if eng.trial_logger is None:
            return
        clock.t += 0.05
        mode.update(0.05)
        respond(clock)


class EchoNotebookChapterTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory()
        with patched_clock() as clock:
            _write_session(cls._td.name, clock)
        cls.ra = _load_ra()
        cat = cls.ra.build_catalogue(root=cls._td.name)
        folders = [Path(p) for p in cat["folder"]]
        cls.trials = cls.ra.load_games(folders, cat)
        cls.metas = cls.ra.load_metas(folders)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cls.result = cls.ra.sec_echo(cls.trials, cls.metas)
        cls.out = buf.getvalue()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def test_span_novel_excludes_the_hidden_trials(self) -> None:
        self.assertIsNotNone(self.result)
        pg = self.result["per_game"]
        self.assertEqual(len(pg), 1)
        self.assertEqual(int(pg["span"].iloc[0]), 3)
        self.assertEqual(int(pg["span_novel"].iloc[0]), 2)
        # And the divergence is said out loud, not left to be noticed.
        self.assertIn("span and span_novel differ", self.out)

    def test_wrong_press_of_a_sequence_item_is_a_transposition(
            self) -> None:
        rows = self.result["rows"]
        errs = rows.loc[~rows["hit"], "echo_error"].tolist()
        self.assertEqual(errs, ["transposition"])
        self.assertIn("transposition: 1", self.out)

    def test_partial_credit_is_positional(self) -> None:
        # The failed length-3 trial entered one right item then a
        # wrong one: 1 of 3 positions correct, and the edit-distance
        # score must sit at or above the positional score (a
        # transposition costs Levenshtein less than a scramble).
        rows = self.result["rows"]
        bad = rows[~rows["hit"]].iloc[0]
        self.assertAlmostEqual(bad["partial"], 1.0 / 3.0, places=3)
        self.assertGreaterEqual(bad["edit_score"], bad["partial"] - 1e-9)

    def test_the_kessels_numbers_reach_the_table(self) -> None:
        pg = self.result["per_game"]
        self.assertEqual(int(pg["correct"].iloc[0]), 2)
        self.assertEqual(int(pg["product"].iloc[0]), 6)  # span 3 x 2
        self.assertEqual(int(pg["n_lanes"].iloc[0]), 4)

    def test_claim_limits_print_with_the_numbers(self) -> None:
        # The chapter must never hand out a span without the guard
        # rails: no Corsi-norm comparison, and no therapy claim.
        self.assertIn("never read against Corsi norms", self.out)
        self.assertIn("no therapy or transfer claim", self.out)

    def test_stored_block_summary_cross_check_appears(self) -> None:
        self.assertIn("block_summary.", self.out)
        self.assertIn("echo", self.out)


class EchoSimonChapterTests(unittest.TestCase):
    """The shipped rule: one sequence per game, one item longer per
    trial, one spare life. Scored on its own terms and never pooled
    with a ladder span."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory()
        with patched_clock() as clock:
            _write_simon_session(cls._td.name, clock)
        cls.ra = _load_ra()
        cat = cls.ra.build_catalogue(root=cls._td.name)
        folders = [Path(p) for p in cat["folder"]]
        cls.trials = cls.ra.load_games(folders, cat)
        cls.metas = cls.ra.load_metas(folders)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cls.result = cls.ra.sec_echo(cls.trials, cls.metas)
        cls.out = buf.getvalue()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()
        import matplotlib.pyplot as plt
        plt.close("all")

    def test_the_simon_game_table_reports_span_and_the_life(self) -> None:
        pg = self.result["simon"]["per_game"]
        self.assertEqual(len(pg), 1)
        self.assertEqual(int(pg["span"].iloc[0]), 3)
        self.assertEqual(float(pg["life_used_at"].iloc[0]), 3.0)
        self.assertTrue(bool(pg["recovered"].iloc[0]))
        self.assertEqual(int(pg["n_lanes"].iloc[0]), 4)

    def test_the_miss_is_a_transposition_at_position_three(self) -> None:
        miss = self.result["simon"]["misses"]
        self.assertEqual(len(miss), 1)
        self.assertEqual(miss["class"].iloc[0], "transposition")
        self.assertEqual(float(miss["pos"].iloc[0]), 3.0)
        self.assertTrue(bool(miss["new_item_miss"].iloc[0]))
        self.assertAlmostEqual(float(miss["rel_pos"].iloc[0]), 1.0)

    def test_the_row_and_the_notebook_agree_on_the_error_class(self):
        # The mode writes miss= on the row and the notebook recomputes
        # echo_error from the lane lists. They must never disagree.
        rows = self.ra.echo_frame(self.trials)
        self.assertEqual(set(rows["rule"]), {"simon"})
        bad = rows[~rows["hit"]]
        self.assertTrue(len(bad))
        for _i, r in bad.iterrows():
            self.assertEqual(r["miss"], r["echo_error"])

    def test_ladder_numbers_do_not_appear_for_a_simon_block(self) -> None:
        self.assertTrue(self.result["per_game"].empty)
        self.assertIsNone(self.result["hebb_slope"])
        self.assertIn("Echo (Simon rule)", self.out)

    def test_claim_limits_print_with_the_numbers(self) -> None:
        self.assertIn("not a Corsi span", self.out)
        self.assertIn("no therapy or transfer claim", self.out)
        self.assertIn("test-retest", self.out)

    def test_the_schedule_anchor_is_the_length_the_ladder_opened_at(self):
        # A Simon game starts at length 1, which is on schedule at the
        # same 800 ms the ladder always opened at.
        self.assertEqual(self.ra.ECHO_SCHEDULE["anchor_len"], 2)
        self.assertEqual(self.ra.echo_schedule_ioi_ms(1), 800.0)
        self.assertEqual(self.ra.echo_schedule_ioi_ms(2), 800.0)
        self.assertEqual(self.ra.echo_schedule_ioi_ms(3), 750.0)
        pg = self.result["simon"]["per_game"]
        self.assertEqual(int(pg["off_schedule"].iloc[0]), 0)


if __name__ == "__main__":
    unittest.main()
