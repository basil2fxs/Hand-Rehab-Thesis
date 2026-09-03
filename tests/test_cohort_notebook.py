"""The cohort chapter of the notebook, driven end to end on a synthetic
cohort the REAL engine wrote.

Five participant codes play two visits each on the keyboard source:
a reaction block per hand (dominant first, then the other hand) and
one bilateral echo block, with a named person and a code-less visit
mixed into the same tree to prove the selection leaves them out. The
folders are then handed to the real notebook functions
(build_catalogue, sec_cohort_selection and the sections after it),
the same path tests/test_force_pilot_notebook_levels.py walks.

What this pins: the long table's shape and hand roles, the ICC path
(interval, SEM, MDC), the paired hand comparison and its wording, the
validity verdicts, the CSV and report on disk, the small-n refusal,
that no name ever reaches an output, and that the per-session report
still leaves the cohort sections out.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import random
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import ModuleType

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import matplotlib
matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_echo_mode import patched_clock

CODES = ("P01", "P02", "P03", "P04", "P05")
DOMINANT = {"P01": "right", "P02": "right", "P03": "left", "P04": "right",
            "P05": "right"}
VISIT_ONE_DAY = "2026-08-20"
TRIALS_PER_REACTION_BLOCK = 12


def _press(lane: int, t: float, hand: str = "right"):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=600, baseline=50.0,
                      hand=hand)


def _engine(root: Path):
    """A real GameEngine on the keyboard source, screens built, reports
    and audio off, writing into `root`."""
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["session"]["data_dir"] = str(root)
    cfg.data["audio"]["enabled"] = False
    cfg.data["report"] = {"enabled": False}
    # No catch trials: every trial the driver fires is answered.
    cfg.data.setdefault("reaction", {}).update({"seed": 1234,
                                                "catch_rate": 0.0})
    eng = GameEngine(cfg, KeyboardOnlySource())
    eng._screens = eng._build_screens()
    return eng


def _play_reaction(eng, hand: str, base_ms: float, rng: random.Random,
                   n_trials: int = TRIALS_PER_REACTION_BLOCK) -> Path:
    """One reaction block: every trial answered on the cued finger
    about base_ms after the stimulus, driven the way
    tests/test_reaction_mode.py drives the mode."""
    assert eng.begin_game("reaction", hand), f"reaction refused on {hand}"
    mode = eng.mode
    t = 100.0
    for _ in range(n_trials):
        mode._begin_trial(now=t)
        mode._fire(now=t + 2.0)
        target = mode.active.lane
        rt = (base_ms + rng.uniform(-25.0, 25.0)) / 1000.0
        mode._handle_press(_press(target, t + 2.0 + rt, hand),
                           now=t + 2.0 + rt)
        t += 4.0
    folder = Path(eng.session_paths.root)
    eng.finish_block()
    return folder


def _play_echo(eng, fail_from: int) -> Path:
    """One bilateral echo block on a stepped clock: perfect replay up
    to length fail_from - 1, then a wrong first press at every longer
    length, so the ladder ends and the span is fail_from - 1."""
    with patched_clock() as clock:
        assert eng.begin_game("echo", "both"), "echo refused on both"
        mode = eng.mode
        folder = Path(eng.session_paths.root)
        answered = {"n": 0}

        def respond(clk) -> None:
            if mode.phase != "respond" or mode.active is None:
                return
            if mode.trial_counter == answered["n"]:
                return
            answered["n"] = mode.trial_counter
            seq = list(mode.sequence)
            if len(seq) >= fail_from:
                wrong = next(l for l in mode.lanes if l != seq[0])
                mode.queue_press(_press(wrong, clk.t,
                                        "left" if wrong >= 4 else "right"))
                return
            for i, lane in enumerate(seq):
                mode.queue_press(_press(lane, clk.t + 0.3 * i,
                                        "left" if lane >= 4 else "right"))

        for _ in range(40000):
            if eng.trial_logger is None:
                break
            clock.t += 0.05
            mode.update(0.05)
            respond(clock)
        else:
            raise AssertionError("the echo block never ended")
    return folder


def write_synthetic_cohort(root: Path) -> None:
    """Five codes, two visits, on one engine. Visit 1 lands in today's
    day folder and is renamed to VISIT_ONE_DAY afterwards, so visit 2
    gets today's folder and the two visits sit on different days the
    way real ones do. The metadata visit field is what the chapter
    reads; the folder day is the retest interval it reports."""
    import pygame
    pygame.init()
    eng = None
    try:
        eng = _engine(root)
        rng = random.Random(7)
        today = time.strftime("%Y-%m-%d")
        for visit in ("1", "2"):
            for i, code in enumerate(CODES):
                dom = DOMINANT[code]
                other = "left" if dom == "right" else "right"
                eng.begin_session(
                    code, str(22 + i),
                    sex="female" if i % 2 else "male",
                    dominant_hand=dom,
                    edinburgh_lq="80" if dom == "right" else "-70",
                    visit=visit, hand_length_mm="185",
                    hand_breadth_mm="82")
                # Dominant hand faster by 30 ms for everyone, visit 2
                # 8 ms faster than visit 1: small, consistent effects
                # the chapter should find and word correctly.
                base = 250.0 + 15.0 * i - (8.0 if visit == "2" else 0.0)
                _play_reaction(eng, dom, base, rng)
                _play_reaction(eng, other, base + 30.0, rng)
                _play_echo(eng, fail_from=4 + i)
                eng.end_session()
            if visit == "1":
                (root / today).rename(root / VISIT_ONE_DAY)
        # A named person with no visit, and a code with no visit:
        # neither is a study participant.
        eng.begin_session("Mara", "40", dominant_hand="right", visit="")
        _play_reaction(eng, "right", 300.0, rng)
        eng.end_session()
        eng.begin_session("P09", "31", dominant_hand="right", visit="")
        _play_reaction(eng, "right", 300.0, rng)
        eng.end_session()
    finally:
        if eng is not None:
            try:
                eng._close_loggers()
            except Exception:
                pass
        pygame.quit()


class _Live:
    """Attribute access straight into the notebook module's dict, so a
    function re-bound by _wrap_sections (which prepare() does) is the
    one a test calls."""

    def __init__(self, ns: dict) -> None:
        self.__dict__ = ns


def _load_notebook() -> _Live:
    """Exec every notebook cell's definitions into one module
    namespace, the tests/test_echo_notebook_span.py pattern."""
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_cohort"
    module = ModuleType(name)
    module.__file__ = str(ROOT / "analysis" / "session_analysis.ipynb")
    sys.modules[name] = module
    ns = module.__dict__
    try:
        for index, lines in _code_cells():
            source = _definitions(index, lines)
            code = compile(source, f"session_analysis.ipynb cell {index}",
                           "exec", flags=FUTURE_FLAGS, dont_inherit=True)
            exec(code, ns)
    finally:
        sys.modules.pop(name, None)
    ns["FIGDIR"] = Path(tempfile.mkdtemp())
    return _Live(ns)


class CohortNotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory()
        cls.root = Path(cls._td.name)
        write_synthetic_cohort(cls.root)
        ra = cls.ra = _load_notebook()
        cls.cat = ra.build_catalogue(root=cls.root)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cls.ctx = ra.prepare("latest", root=cls.root)
            cls.cohort = ra.keep(
                cls.ctx, "cohort_selection",
                ra.sec_cohort_selection(cls.cat, root=cls.root, min_n=3))
            cls.desc = ra.keep(cls.ctx, "cohort_describe",
                               ra.sec_cohort_describe(cls.cohort))
            cls.hands = ra.keep(cls.ctx, "cohort_hands",
                                ra.sec_cohort_hands(cls.cohort))
            cls.retest = ra.keep(cls.ctx, "cohort_retest",
                                 ra.sec_cohort_retest(cls.cohort))
            cls.practice = ra.keep(cls.ctx, "cohort_practice",
                                   ra.sec_cohort_practice(cls.cohort))
            cls.validity = ra.keep(cls.ctx, "cohort_validity",
                                   ra.sec_cohort_validity(cls.cohort))
            cls.written = ra.keep(cls.ctx, "cohort_export",
                                  ra.sec_cohort_export(cls.cohort))
            cls.report = ra.write_cohort_report(cls.ctx, cls.cohort)
        cls.out = buf.getvalue()
        import matplotlib.pyplot as plt
        plt.close("all")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    # ---- selection and the long table --------------------------------
    def test_selection_keeps_codes_with_visits_only(self) -> None:
        sel = self.cohort["sel"]
        self.assertEqual(set(sel["participant"]), set(CODES))
        self.assertEqual(len(sel), len(CODES) * 2 * 3)
        dropped = self.cohort["dropped"]
        self.assertEqual(dropped["name_not_code"], 1)
        self.assertEqual(dropped["no_visit"], 1)
        people = self.cohort["people"]
        self.assertEqual(list(people["visits"]), [2] * len(CODES))
        self.assertTrue((people["interval_days"] > 0).all())
        self.assertEqual(
            people.set_index("participant").loc["P03", "dominant_hand"],
            "left")

    def test_long_table_shape_and_hand_roles(self) -> None:
        long = self.cohort["long"]
        self.assertEqual(list(long.columns), self.ra.COHORT_LONG_COLS)
        self.assertEqual(set(long["participant"]), set(CODES))
        self.assertEqual(set(long["mode"]), {"reaction", "echo"})
        self.assertEqual(set(long["visit"]), {"1", "2"})
        self.assertTrue((long["n_trials"] > 0).all())
        self.assertTrue(long["value"].map(lambda v: v == v).all())
        rx = long[long["mode"] == "reaction"]
        self.assertEqual(set(rx["hand_role"]), {"dominant", "nondominant"})
        p03 = rx[(rx["participant"] == "P03") & (rx["hand"] == "left")]
        self.assertEqual(set(p03["hand_role"]), {"dominant"})
        self.assertIn("median_rt_ms", set(rx["metric"]))
        self.assertIn("false_start_rate", set(rx["metric"]))
        echo = long[long["mode"] == "echo"]
        self.assertEqual(set(echo["hand_role"]), {"both"})
        spans = echo[(echo["metric"] == "span") & (echo["visit"] == "1")]
        self.assertEqual(
            spans.set_index("participant")["value"].to_dict(),
            {code: float(3 + i) for i, code in enumerate(CODES)})
        # Every block ran under the same config, so one hash per mode.
        self.assertEqual(long.groupby("mode")["config_hash"].nunique()
                         .max(), 1)
        self.assertEqual(set(long["day"]),
                         {VISIT_ONE_DAY, time.strftime("%Y-%m-%d")})

    def test_the_cohort_pick_word_selects_codes(self) -> None:
        sel = self.ra.resolve("cohort", self.cat)
        self.assertEqual(set(sel["who"]), set(CODES) | {"P09"})

    # ---- descriptives ------------------------------------------------
    def test_normative_table_prints_at_the_minimum(self) -> None:
        self.assertIn("normative table, visit 1", self.out)
        d = self.desc[(self.desc["mode"] == "reaction")
                      & (self.desc["metric"] == "median_rt_ms")
                      & (self.desc["visit"] == "1")]
        self.assertEqual(set(d["hand_role"]), {"dominant", "nondominant"})
        self.assertEqual(list(d["n"]), [len(CODES)] * 2)
        row = d[d["hand_role"] == "dominant"].iloc[0]
        self.assertLessEqual(row["p5"], row["median"])
        self.assertLessEqual(row["median"], row["p95"])

    # ---- dominant against non-dominant -------------------------------
    def test_hand_comparison_finds_the_built_in_advantage(self) -> None:
        h = self.hands[(self.hands["mode"] == "reaction")
                       & (self.hands["metric"] == "median_rt_ms")
                       & (self.hands["visit"] == "1")].iloc[0]
        self.assertEqual(h["n"], len(CODES))
        self.assertLess(h["diff"], 0)          # dominant faster
        self.assertLess(h["ci_hi"], 0)
        self.assertLess(h["dz"], -1.0)
        self.assertEqual(h["alternative"], "less")
        self.assertEqual(h["test"], "wilcoxon")  # n under 20
        self.assertIn("non-dominant higher than dominant", h["direction"])
        self.assertIn("so dominant is better", h["direction"])
        self.assertIn("in words", self.out)
        # Accuracy is 1.0 on every block, so its row says so instead
        # of printing a NaN p and a NaN dz.
        acc = self.hands[(self.hands["metric"] == "accuracy")
                         & (self.hands["visit"] == "1")].iloc[0]
        self.assertEqual(acc["test"], "no variation")
        self.assertIn("accuracy: dominant equals non-dominant; n 5, "
                      "no variation between the pairs", self.out)
        self.assertNotIn("p nan", self.out)
        self.assertNotIn("dz +nan", self.out)

    # ---- test-retest -------------------------------------------------
    def test_icc_path_computes_with_interval_sem_and_mdc(self) -> None:
        r = self.retest
        row = r[(r["mode"] == "reaction") & (r["metric"] == "median_rt_ms")
                & (r["hand_role"] == "dominant")].iloc[0]
        self.assertEqual(row["n"], len(CODES))
        for col in ("icc21", "ci_lo", "ci_hi", "icc31", "sem", "mdc95",
                    "mdc_over_sd1", "bias", "loa_lo", "loa_hi"):
            self.assertTrue(row[col] == row[col], f"{col} is NaN")
        self.assertLessEqual(row["ci_lo"], row["icc21"])
        self.assertLessEqual(row["icc21"], row["ci_hi"])
        self.assertGreater(row["icc21"], 0.5)   # 15 ms steps, 25 ms jitter
        self.assertGreater(row["mdc95"], 0)
        self.assertIn(row["band"], ("moderate", "good", "excellent"))
        echo = r[(r["mode"] == "echo") & (r["metric"] == "span")]
        self.assertEqual(list(echo["hand_role"]), ["both"])
        self.assertEqual(int(echo["n"].iloc[0]), len(CODES))
        self.assertIn("ICC(2,1)", self.out)
        figs = Path(self.cohort["out_dir"]) / "figures"
        self.assertTrue((figs / "cohort_icc_forest.png").exists())
        self.assertTrue((figs / "cohort_bland_altman.png").exists())

    def test_practice_effect_reads_visit_two_against_visit_one(self) -> None:
        p = self.practice[(self.practice["mode"] == "reaction")
                          & (self.practice["metric"] == "median_rt_ms")
                          & (self.practice["hand_role"] == "dominant")]
        self.assertEqual(len(p), 1)
        self.assertEqual(int(p["n"].iloc[0]), len(CODES))
        self.assertLess(p["diff"].iloc[0], 0)   # visit 2 faster
        self.assertIn("visit 1", p["direction"].iloc[0])

    # ---- validity ----------------------------------------------------
    def test_validity_verdicts_are_plain_and_decided(self) -> None:
        v = self.validity.set_index("id")
        for cid in ("R1", "R2", "R3", "P1", "P2", "P3", "C1", "C2", "C3",
                    "C4", "Rh2", "M1", "M2", "F1", "F2", "F3", "F4",
                    "B1", "B2", "B3", "B4", "E1", "E2", "E3"):
            self.assertIn(cid, v.index, cid)
        self.assertEqual(v.loc["R2", "verdict"], "pass")
        self.assertLess(v.loc["R2", "value"], 0)
        self.assertEqual(v.loc["R1", "verdict"], "pass")
        self.assertIn(v.loc["E1", "verdict"], ("pass", "fail"))
        self.assertEqual(v.loc["E1", "n"], len(CODES))
        # Modes with no blocks are not testable, and say so.
        self.assertEqual(v.loc["P1", "verdict"], "not testable")
        self.assertEqual(v.loc["P1", "detail"], "no data")
        # The retired Lighthouse checks L1 to L3 are gone, not "not
        # testable": a row for a mode the app no longer has would be a
        # verdict on nothing.
        self.assertNotIn("L1", v.index)
        self.assertIn("R2  pass", self.out)
        self.assertIn("reference 0.0", self.out)
        self.assertIn("not testable", self.out)

    # ---- outputs -----------------------------------------------------
    def test_csv_and_report_land_in_the_cohort_folder(self) -> None:
        out_dir = Path(self.cohort["out_dir"])
        self.assertEqual(out_dir, self.root / "cohort_results")
        csv_path = out_dir / "cohort_metrics.csv"
        self.assertIn(csv_path, self.written)
        import pandas as pd
        back = pd.read_csv(csv_path)
        self.assertEqual(list(back.columns), self.ra.COHORT_LONG_COLS)
        self.assertEqual(len(back), len(self.cohort["long"]))
        for name in ("describe", "hands", "retest", "practice",
                     "validity"):
            self.assertTrue((out_dir / f"cohort_{name}.csv").exists(), name)
        self.assertEqual(self.report, out_dir / "report.html")
        page = self.report.read_text(encoding="utf-8")
        self.assertIn("TEST-RETEST, SEM AND MDC", page)
        self.assertIn("KNOWN-EFFECT VALIDITY CHECKS", page)
        self.assertIn("data:image/png;base64", page)
        self.assertIn(f"{len(CODES)} participant(s)", page)

    def test_an_empty_cohort_writes_no_folder(self) -> None:
        # No participants means no report and, above all, no stray
        # cohort folder planted beside the notebook.
        nowhere = self.root / "must_not_exist"
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            here = self.ra.write_cohort_report(
                self.ctx, {"sel": None, "out_dir": nowhere})
        self.assertIsNone(here)
        self.assertFalse(nowhere.exists())
        self.assertIn("no cohort report is written", buf.getvalue())

    def test_undefined_icc_carries_its_reason(self) -> None:
        # Echo spans repeat exactly at visit 2 for four of five people,
        # and hebb_minus_novel_acc is zero everywhere: both are
        # reported as undefined with the reason, never as a bare NaN.
        r = self.retest
        row = r[(r["mode"] == "echo")
                & (r["metric"] == "hebb_minus_novel_acc")].iloc[0]
        self.assertTrue(row["icc21"] != row["icc21"])
        self.assertIn("ICC undefined", row["note"])
        self.assertIn("no variance", row["note"])

    def test_no_name_reaches_any_output(self) -> None:
        for text, where in ((self.out, "printed output"),
                            (self.report.read_text(encoding="utf-8"),
                             "report"),
                            ((Path(self.cohort["out_dir"])
                              / "cohort_metrics.csv").read_text(), "csv"),
                            ((Path(self.cohort["out_dir"])
                              / "cohort_participants.csv").read_text(),
                             "participants csv")):
            self.assertNotIn("Mara", text, where)
        self.assertEqual(set(self.cohort["long"]["participant"]),
                         set(CODES))

    def test_small_n_refusal_names_the_design_number(self) -> None:
        ra = self.ra
        cohort = dict(self.cohort, min_n=28, tables={})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            tbl = ra.sec_cohort_retest(cohort)
            ra.sec_cohort_hands(cohort)
            val = ra.sec_cohort_validity(cohort)
        out = buf.getvalue()
        import matplotlib.pyplot as plt
        plt.close("all")
        self.assertIn("the design analyses 28", out)
        self.assertIn("no statistic is printed", out)
        self.assertNotIn("ICC(2,1): two-way random", out)
        self.assertFalse(tbl.empty)
        self.assertEqual(set(val["verdict"]), {"not testable"})
        self.assertIn("n under the design minimum",
                      set(val["detail"]))

    def test_per_session_report_leaves_the_cohort_out(self) -> None:
        ra = self.ra
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ra.keep(self.ctx, "on_task",
                    ra.sec_overview(self.ctx["trials"], self.ctx["folders"],
                                    self.ctx["metas"]))
            here = ra.write_report(self.ctx)
        import matplotlib.pyplot as plt
        plt.close("all")
        self.assertIsNotNone(here)
        page = Path(here).read_text(encoding="utf-8")
        self.assertIn("Overview", page)
        self.assertNotIn("TEST-RETEST, SEM AND MDC", page)
        self.assertNotIn("cohort_", page)
        self.assertNotIn("not captured", buf.getvalue())
        # The per-session report went beside its own session, not
        # into the cohort folder.
        self.assertNotIn("cohort_results", str(here))

    def test_a_full_read_of_one_code_lands_its_summary_in_this_tree(self):
        """The standing summary goes under the sessions tree the run
        READ, not the one found beside the notebook at import. A run
        over a copy of the tree (or a test's temp tree) used to plant
        individual_patient_results in the default tree instead."""
        # A notebook namespace of its own: prepare() resets the capture
        # and output folder the other tests read from setUpClass.
        ra = _load_notebook()
        default = Path(ra.SESSIONS_DIR) / "individual_patient_results"
        before = ({p.name for p in default.iterdir()}
                  if default.is_dir() else set())
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            ctx = ra.prepare("P01", root=self.root)
            ra.keep(ctx, "on_task",
                    ra.sec_overview(ctx["trials"], ctx["folders"],
                                    ctx["metas"]))
            here = ra.write_report(ctx)
        import matplotlib.pyplot as plt
        plt.close("all")
        self.assertEqual(len(ctx["folders"]), 6)      # every P01 game
        summary = (self.root / "individual_patient_results" / "P01"
                   / "summary.html")
        self.assertTrue(summary.exists(), buf.getvalue())
        self.assertIn("P01", summary.read_text(encoding="utf-8"))
        self.assertTrue(str(here).startswith(str(self.root)))
        after = ({p.name for p in default.iterdir()}
                 if default.is_dir() else set())
        self.assertEqual(after - before, set())

    def test_shrout_fleiss_example_through_the_notebook_copy(self) -> None:
        import numpy as np
        sf = np.array([[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8],
                       [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]], float)
        icc = self.ra.icc_ci(sf)
        self.assertAlmostEqual(icc["icc21"], 0.29, places=2)
        self.assertAlmostEqual(icc["lo21"], 0.019, places=3)
        self.assertAlmostEqual(icc["hi21"], 0.761, places=3)
        self.assertAlmostEqual(icc["icc31"], 0.715, places=3)
        self.assertAlmostEqual(icc["lo31"], 0.342, places=3)
        self.assertAlmostEqual(icc["hi31"], 0.946, places=3)
        self.assertAlmostEqual(self.ra.icc_two_one(sf), icc["icc21"],
                               places=9)

    def test_exact_repeats_give_an_exact_icc_not_a_missing_one(self) -> None:
        """A coarse integer metric (a span) can repeat exactly for
        everyone. That is perfect agreement, and reporting it as
        undefined reads as unreliable to anyone skimming the table.
        The coefficients are 1 with the interval at its zero-error
        limit; a uniform shift between visits keeps ICC(3,1) at 1 and
        pulls ICC(2,1) below it with a finite interval."""
        import numpy as np
        same = np.array([[4, 4], [6, 6], [5, 5], [7, 7], [6, 6]], float)
        icc = self.ra.icc_ci(same)
        self.assertEqual((icc["icc21"], icc["lo21"], icc["hi21"]),
                         (1.0, 1.0, 1.0))
        self.assertEqual((icc["icc31"], icc["lo31"], icc["hi31"]),
                         (1.0, 1.0, 1.0))
        self.assertIn("exactly", icc["reason"])
        shifted = same.copy()
        shifted[:, 1] += 1
        icc = self.ra.icc_ci(shifted)
        self.assertEqual((icc["icc31"], icc["lo31"], icc["hi31"]),
                         (1.0, 1.0, 1.0))
        self.assertLess(icc["icc21"], 1.0)
        self.assertGreater(icc["icc21"], 0.5)
        self.assertTrue(np.isfinite(icc["lo21"]) and np.isfinite(icc["hi21"]))
        self.assertLessEqual(icc["lo21"], icc["icc21"])
        self.assertLessEqual(icc["icc21"], icc["hi21"])
        # The retest table carries the exact case as a note on a
        # number, never as an "undefined" on a blank.
        long = self.cohort["long"]
        spans = long[(long["mode"] == "echo") & (long["metric"] == "span")]
        v1 = spans[spans["visit"] == "1"].set_index("participant")["value"]
        copy = long.copy()
        mask = (copy["mode"] == "echo") & (copy["metric"] == "span")
        copy.loc[mask, "value"] = copy.loc[mask, "participant"].map(v1)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = self.ra.sec_cohort_retest(dict(self.cohort, long=copy,
                                               tables={}))
        import matplotlib.pyplot as plt
        plt.close("all")
        # The section redrew the cohort figures outside keep(); they
        # are not the next captured section's to file.
        self.ra._CAPTURE["figs"] = self.ra._fig_state()
        row = r[(r["mode"] == "echo") & (r["metric"] == "span")].iloc[0]
        self.assertEqual(row["icc21"], 1.0)
        self.assertEqual(row["band"], "excellent")
        self.assertIn("ICC exact", row["note"])
        self.assertNotIn("undefined", row["note"])


if __name__ == "__main__":
    unittest.main()
