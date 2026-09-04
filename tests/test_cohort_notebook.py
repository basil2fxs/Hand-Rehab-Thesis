"""The cohort chapter of the notebook, driven end to end on a synthetic
cohort the REAL engine wrote.

Five participant codes play ONE sitting each on the keyboard source,
through the REAL battery machinery with a shortened preset: a reaction
block per hand and a bilateral echo block, every step carrying
phase "battery" and no block repeated, which is the design of
4 September 2026. A named person, a code with no visit and one
free-play block with no battery phase are mixed into the same tree to
prove the selection leaves them where they belong. The folders are
then handed to the real notebook functions (build_catalogue,
sec_cohort_selection and the sections after it), the same path
tests/test_force_pilot_notebook_levels.py walks.

Each reaction block carries an injected WITHIN-BLOCK warm-up: the
first trials run slower and the block settles, which is the only
progress signal a single pass has and the thing
sec_cohort_within_block has to recover.

What this pins: the long table's shape, phase and hand roles, the
normative table and its refusal to print percentiles at this n, the
paired hand comparison, the within-block first-against-last contrast
and its slopes, internal consistency inside one block, the feasibility
numbers, the validity verdicts including the DROPPED rows and W1 to
W6, the CSVs and the report on disk, the small-n refusal, that no name
ever reaches an output, and that the per-session report still leaves
the cohort sections out.
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
TRIALS_PER_REACTION_BLOCK = 12
# The sitting, shortened. The shipped preset is eleven blocks, one per
# mode and hand; three blocks is enough to exercise every path in the
# chapter and still runs in seconds. Every step carries the one phase
# word the one-pass preset writes, and no mode and hand repeats.
SHORT_ORDER = [
    {"mode": "reaction", "hand": "hand1", "phase": "battery"},
    {"mode": "reaction", "hand": "hand2", "phase": "battery",
     "rest_before": True},
    {"mode": "echo", "hand": "both", "phase": "battery"},
]
BLOCKS_PER_SITTING = len(SHORT_ORDER)
# The WITHIN-BLOCK warm-up injected into every reaction block: the
# first trial runs WARMUP_MS slower than the last and the penalty
# decays to nothing by trial WARMUP_TRIALS. With no repeated block this
# is the only improvement signal in the tree, and the within-block
# chapter has to find it with the right sign.
WARMUP_MS = 60.0
WARMUP_TRIALS = 6


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
    # The REAL battery machinery on a shortened order. Both cells run
    # the same three steps, so every code's sitting is the same shape
    # and the phase stamping is the shipped one, not a hand-written
    # stub.
    preset = cfg.data["protocol"]["presets"]["study_battery"]
    preset["orders"] = {"A": [dict(s) for s in SHORT_ORDER],
                        "B": [dict(s) for s in SHORT_ORDER]}
    # No config overrides: this rig drives the modes by hand, so the
    # study's short forms and frozen ladders would only get in the way
    # of the numbers the assertions below pin.
    preset["overrides"] = {}
    eng = GameEngine(cfg, KeyboardOnlySource())
    eng._screens = eng._build_screens()
    return eng


def _warmup_ms(i: int) -> float:
    """The injected within-block penalty on trial i, zero-based."""
    return WARMUP_MS * max(0.0, 1.0 - i / float(WARMUP_TRIALS))


def _drive_reaction(eng, hand: str, base_ms: float, rng: random.Random,
                    n_trials: int = TRIALS_PER_REACTION_BLOCK) -> None:
    """Play an OPEN reaction block: every trial answered on the cued
    finger about base_ms after the stimulus, driven the way
    tests/test_reaction_mode.py drives the mode, with the within-block
    warm-up on top."""
    mode = eng.mode
    t = 100.0
    for i in range(n_trials):
        mode._begin_trial(now=t)
        mode._fire(now=t + 2.0)
        target = mode.active.lane
        rt = (base_ms + _warmup_ms(i)
              + rng.uniform(-25.0, 25.0)) / 1000.0
        mode._handle_press(_press(target, t + 2.0 + rt, hand),
                           now=t + 2.0 + rt)
        t += 4.0


def _play_reaction(eng, hand: str, base_ms: float, rng: random.Random,
                   n_trials: int = TRIALS_PER_REACTION_BLOCK) -> Path:
    """One free-pick reaction block, opened and closed here."""
    assert eng.begin_game("reaction", hand), f"reaction refused on {hand}"
    folder = Path(eng.session_paths.root)
    _drive_reaction(eng, hand, base_ms, rng, n_trials)
    eng.finish_block()
    return folder


def _drive_echo(eng, fail_from: int) -> None:
    """Play an OPEN echo block on a stepped clock: perfect replay up to
    length fail_from - 1, then a wrong first press at every longer
    length, so the game ends and the span is fail_from - 1."""
    with patched_clock() as clock:
        mode = eng.mode
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


def _play_echo(eng, fail_from: int) -> Path:
    """One free-pick echo block, opened and closed by the engine's own
    end-of-block path."""
    assert eng.begin_game("echo", "both"), "echo refused on both"
    folder = Path(eng.session_paths.root)
    _drive_echo(eng, fail_from)
    return folder


def _play_battery(eng, dom: str, base: float, rng: random.Random,
                  fail_from: int) -> None:
    """Run the shortened battery, playing every block for real.

    The engine opens each step; this drives the mode the way the
    per-mode tests do, closes the block and takes the next step off the
    NEXT UP card, exactly as an RA would.
    """
    assert eng.start_battery(), "the battery refused to start"
    for _ in range(BLOCKS_PER_SITTING * 2):
        if not eng.block_is_running():
            break
        mode_name = str(eng.current_block)
        if mode_name == "reaction":
            hand = str(eng.hand_mode)
            slow = 30.0 if hand != dom else 0.0
            _drive_reaction(eng, hand, base + slow, rng)
        elif mode_name == "echo":
            _drive_echo(eng, fail_from)
        if eng.block_is_running():
            # Echo ends its own block when the game is over; reaction
            # is driven trial by trial and has to be closed here.
            eng.finish_block()
        if eng.pending_protocol_step() is None:
            break
        assert eng.continue_protocol(), "the battery would not continue"


def write_synthetic_cohort(root: Path) -> None:
    """Five codes, one sitting each, through the real battery.

    Every code plays the three steps of SHORT_ORDER in one session, so
    each block carries battery.phase and battery.position and every
    trial row carries the phase column. A named person, a code with no
    visit and one free-play block with no battery phase go into the
    same tree: the first two must be dropped by the selection, the
    third must reach the export and stay out of every analysis table.
    """
    import pygame
    pygame.init()
    eng = None
    try:
        eng = _engine(root)
        rng = random.Random(7)
        for i, code in enumerate(CODES):
            dom = DOMINANT[code]
            eng.begin_session(
                code, str(22 + i),
                sex="female" if i % 2 else "male",
                dominant_hand=dom,
                edinburgh_lq="80" if dom == "right" else "-70",
                visit="1", hand_length_mm=str(180 + 3 * i),
                hand_breadth_mm="82")
            # A fake rig has no calibration behind it; the guard would
            # put a question up. The clinician has answered it here.
            eng._uncal_ack = {"left", "right"}
            # The echo ladder runs to at least 9 lengths so its own
            # fine series clears the eight scorable trials the
            # within-block contrast needs. Under that floor the design
            # does not compute the contrast at all, which is the point
            # of the floor and not something to test around.
            _play_battery(eng, dom, 250.0 + 15.0 * i, rng,
                          fail_from=9 + i)
            if code == CODES[0]:
                # One free pick after the battery: no battery stamp, so
                # phase is empty and every analysis table must ignore it.
                _play_reaction(eng, dom, 400.0, rng)
            eng.end_session()
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
            cls.within = ra.keep(cls.ctx, "cohort_within_block",
                                 ra.sec_cohort_within_block(cls.cohort))
            cls.consistency = ra.keep(
                cls.ctx, "cohort_consistency",
                ra.sec_cohort_consistency(cls.cohort))
            cls.feasible = ra.keep(
                cls.ctx, "cohort_feasibility",
                ra.sec_cohort_feasibility(cls.cohort))
            cls.validity = ra.keep(
                cls.ctx, "cohort_validity",
                ra.sec_cohort_validity(cls.cohort, cls.within))
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
        # Three battery blocks each, plus P01's one free pick.
        self.assertEqual(len(sel), len(CODES) * BLOCKS_PER_SITTING + 1)
        dropped = self.cohort["dropped"]
        self.assertEqual(dropped["name_not_code"], 1)
        self.assertEqual(dropped["no_visit"], 1)
        people = self.cohort["people"]
        # One sitting per code, so there is no visit count and no retest
        # interval to carry.
        self.assertNotIn("visits", people.columns)
        self.assertNotIn("interval_days", people.columns)
        self.assertIn("days", people.columns)
        self.assertEqual(
            people.set_index("participant").loc["P03", "dominant_hand"],
            "left")
        self.assertIn("ONE sitting per code", self.out)

    def test_every_battery_step_carries_the_one_phase_word(self) -> None:
        sel = self.cohort["sel"]
        battery = sel[sel["phase"] != ""]
        self.assertEqual(set(battery["phase"]), {self.ra.COHORT_PHASE})
        self.assertEqual(len(battery), len(CODES) * BLOCKS_PER_SITTING)
        # The free pick carries no phase and is not dropped.
        free = sel[sel["phase"] == ""]
        self.assertEqual(len(free), 1)
        self.assertEqual(free["participant"].iloc[0], CODES[0])
        for who, g in battery.groupby("participant"):
            positions = sorted(int(v) for v in g["battery_position"])
            self.assertEqual(positions,
                             list(range(1, BLOCKS_PER_SITTING + 1)), who)
        # No mode and hand is played twice: that is the design.
        twice = battery.groupby(["participant", "mode", "hand"]).size()
        self.assertEqual(int(twice.max()), 1)

    def test_the_free_play_block_stays_out_of_every_analysis_table(self):
        long = self.cohort["long"]
        blank = long[long["phase"] == ""]
        self.assertFalse(blank.empty)
        self.assertEqual(set(blank["participant"]), {CODES[0]})
        self.assertIn("no battery phase", self.out)
        # It is in the export...
        import pandas as pd
        back = pd.read_csv(Path(self.cohort["out_dir"])
                           / "cohort_metrics.csv")
        self.assertTrue((back["phase"].fillna("") == "").any())
        # ...and cohort_battery_rows is what keeps it out of the rest.
        battery = self.ra.cohort_battery_rows(long)
        self.assertEqual(set(battery["phase"]), {self.ra.COHORT_PHASE})
        self.assertLess(len(battery), len(long))

    def test_long_table_shape_and_hand_roles(self) -> None:
        long = self.cohort["long"]
        self.assertEqual(list(long.columns), self.ra.COHORT_LONG_COLS)
        self.assertEqual(set(long["participant"]), set(CODES))
        self.assertEqual(set(long["mode"]), {"reaction", "echo"})
        self.assertEqual(set(long["visit"]), {"1"})
        self.assertEqual(set(long["phase"]),
                         {self.ra.COHORT_PHASE, ""})
        battery = self.ra.cohort_battery_rows(long)
        self.assertTrue((battery["position"] >= 1).all())
        self.assertTrue((battery["position"] <= BLOCKS_PER_SITTING).all())
        self.assertTrue((long["n_trials"] > 0).all())
        self.assertTrue(long["value"].map(lambda v: v == v).all())
        rx = battery[battery["mode"] == "reaction"]
        self.assertEqual(set(rx["hand_role"]), {"dominant", "nondominant"})
        p03 = rx[(rx["participant"] == "P03") & (rx["hand"] == "left")]
        self.assertEqual(set(p03["hand_role"]), {"dominant"})
        self.assertIn("median_rt_ms", set(rx["metric"]))
        self.assertIn("false_start_rate", set(rx["metric"]))
        echo = battery[battery["mode"] == "echo"]
        self.assertEqual(set(echo["hand_role"]), {"both"})
        spans = echo[echo["metric"] == "span"]
        self.assertEqual(
            spans.set_index("participant")["value"].to_dict(),
            {code: float(8 + i) for i, code in enumerate(CODES)})
        # Every block ran under the same config, so one hash per mode.
        self.assertEqual(long.groupby("mode")["config_hash"].nunique()
                         .max(), 1)
        self.assertEqual(set(long["day"]), {time.strftime("%Y-%m-%d")})

    def test_the_cohort_pick_word_selects_codes(self) -> None:
        sel = self.ra.resolve("cohort", self.cat)
        self.assertEqual(set(sel["who"]), set(CODES) | {"P09"})

    # ---- descriptives ------------------------------------------------
    def test_normative_table_prints_the_range_not_a_percentile(self):
        self.assertIn("normative table", self.out)
        d = self.desc[(self.desc["mode"] == "reaction")
                      & (self.desc["metric"] == "median_rt_ms")]
        self.assertEqual(set(d["hand_role"]), {"dominant", "nondominant"})
        self.assertEqual(list(d["n"]), [len(CODES)] * 2)
        row = d[d["hand_role"] == "dominant"].iloc[0]
        self.assertLessEqual(row["min"], row["median"])
        self.assertLessEqual(row["median"], row["max"])
        self.assertLessEqual(row["q1"], row["median"])
        self.assertLessEqual(row["median"], row["q3"])
        # Five people cannot support a 5th or a 95th percentile, and
        # cannot support a distribution-free median interval either.
        self.assertTrue(row["p5"] != row["p5"])
        self.assertTrue(row["p95"] != row["p95"])
        self.assertTrue(row["med_lo"] != row["med_lo"])
        self.assertIn("That needs n = 20", self.out.replace(
            "that needs n = 20", "That needs n = 20"))

    def test_the_median_interval_is_the_order_statistic_pair(self) -> None:
        lo, hi, cover = self.ra.median_order_ci(10)
        self.assertEqual((lo, hi), (2, 9))
        self.assertAlmostEqual(cover, 0.9785, places=3)
        self.assertEqual(self.ra.median_order_ci(4)[0], None)

    # ---- dominant against non-dominant -------------------------------
    def test_hand_comparison_finds_the_built_in_advantage(self) -> None:
        h = self.hands[(self.hands["mode"] == "reaction")
                       & (self.hands["metric"] == "median_rt_ms")].iloc[0]
        self.assertEqual(h["n"], len(CODES))
        self.assertLess(h["diff"], 0)          # dominant faster
        self.assertLess(h["ci_hi"], 0)
        self.assertLess(h["dz"], -1.0)
        self.assertEqual(h["alternative"], "less")
        self.assertEqual(h["test"], "wilcoxon")  # n under 20
        self.assertIn("non-dominant higher than dominant", h["direction"])
        self.assertIn("so dominant is better", h["direction"])
        self.assertNotIn("phase", self.hands.columns)
        self.assertIn("in words", self.out)
        # Accuracy is 1.0 on every block, so its row says so instead
        # of printing a NaN p and a NaN dz.
        acc = self.hands[self.hands["metric"] == "accuracy"].iloc[0]
        self.assertEqual(acc["test"], "no variation")
        self.assertIn("accuracy: dominant equals non-dominant; n 5, "
                      "no variation between the pairs", self.out)
        self.assertNotIn("p nan", self.out)
        self.assertNotIn("dz +nan", self.out)

    # ---- the within-block chapter ------------------------------------
    def test_the_within_block_contrast_recovers_the_injected_warmup(self):
        ends = self.within["ends"]
        self.assertFalse(ends.empty, "no first-against-last contrast")
        rx = ends[(ends["mode"] == "reaction")
                  & (ends["hand_role"] == "dominant")]
        self.assertEqual(len(rx), 1)
        row = rx.iloc[0]
        self.assertEqual(row["gate"], "reported")
        self.assertEqual(int(row["n"]), len(CODES))
        self.assertLess(row["diff"], 0)        # the block got faster
        self.assertLess(row["ci_hi"], 0)
        self.assertTrue(row["dz_lo"] <= row["dz"] <= row["dz_hi"])
        self.assertEqual(row["in_words"], "faster")
        self.assertEqual(int(row["n_improving"]), len(CODES))
        self.assertLessEqual(row["share_lo"], row["share_improving"])
        self.assertLessEqual(row["share_improving"], row["share_hi"])
        self.assertGreaterEqual(int(row["trials_per_third"]), 2)
        self.assertEqual(row["reading"], "anchor")
        self.assertIn("IMPROVEMENT INSIDE ONE BLOCK", self.out)

    def test_the_harder_modes_are_never_read_as_improvement(self) -> None:
        reading = self.ra.COHORT_WITHIN_BLOCK_READING
        self.assertEqual(reading["echo"][0], "harder")
        ends = self.within["ends"]
        echo = ends[ends["mode"] == "echo"]
        self.assertTrue(len(echo))
        self.assertEqual(set(echo["reading"]), {"harder"})
        self.assertIn("NOT read as improvement", self.out)

    def test_slopes_are_fitted_per_person_and_hand(self) -> None:
        slopes = self.within["slopes"]
        self.assertFalse(slopes.empty)
        rx = slopes[slopes["mode"] == "reaction"]
        self.assertEqual(set(rx["participant"]), set(CODES))
        self.assertEqual(set(rx["hand_role"]),
                         {"dominant", "nondominant"})
        self.assertEqual(set(rx["better"]), {"lower"})
        self.assertTrue((rx["n_points"] >= 4).all())
        finite = rx.dropna(subset=["slope", "slope_lo", "slope_hi"])
        self.assertTrue(len(finite))
        self.assertTrue(((finite["slope_lo"] <= finite["slope"])
                         & (finite["slope"] <= finite["slope_hi"])).all())
        summary = self.within["summary"]
        row = summary[(summary["mode"] == "reaction")
                      & (summary["hand_role"] == "dominant")].iloc[0]
        self.assertLess(row["median_slope"], 0)
        self.assertLessEqual(row["q1"], row["median_slope"])
        self.assertLessEqual(row["median_slope"], row["q3"])
        self.assertEqual(row["gate"], "reported")
        self.assertIn("Heathcote", self.out)
        self.assertIn("anchor", self.out.lower())

    def test_the_chapter_states_what_it_cannot_say(self) -> None:
        low = self.out.lower()
        self.assertIn("warm-up", low)
        self.assertIn("no noise floor", low)
        self.assertIn("kantak and winstein 2012", low)
        self.assertIn("what this chapter cannot say", low)

    def test_the_fine_series_is_exported_for_every_block(self) -> None:
        series = self.within["series"]
        self.assertFalse(series.empty)
        self.assertEqual(list(series.columns),
                         ["participant", "hand_role", "mode", "index",
                          "value", "better", "reading"])
        rx = series[(series["mode"] == "reaction")
                    & (series["participant"] == "P01")
                    & (series["hand_role"] == "dominant")]
        self.assertEqual(list(rx["index"]),
                         list(range(1, len(rx) + 1)))
        import pandas as pd
        back = pd.read_csv(Path(self.cohort["out_dir"])
                           / "cohort_series.csv")
        self.assertEqual(len(back), len(series))

    # ---- internal consistency ----------------------------------------
    def test_split_half_runs_where_the_trials_exist_and_says_so_where_not(
            self) -> None:
        c = self.consistency
        rx = c[(c["mode"] == "reaction")
               & (c["metric"] == "median_rt_ms")
               & (c["hand_role"] == "dominant")].iloc[0]
        self.assertEqual(rx["gate"], "reported")
        self.assertTrue(-1.0 <= rx["r_split"] <= 1.0)
        self.assertLessEqual(rx["lo"], rx["r_split"])
        self.assertLessEqual(rx["r_split"], rx["hi"])
        span = c[(c["mode"] == "echo") & (c["metric"] == "span")].iloc[0]
        self.assertEqual(span["gate"], "no per-trial series")
        self.assertTrue(span["r_split"] != span["r_split"])   # NaN
        self.assertIn("nothing to split", span["note"])
        self.assertIn("nothing to split", self.out)
        self.assertIn("INTERNAL CONSISTENCY, WITHIN ONE BLOCK", self.out)

    def test_no_reliability_number_is_turned_into_an_mdc(self) -> None:
        # Nothing is computed twice, so none of these can appear as a
        # number. The words "SEM" and "MDC95" DO appear, in the
        # sentences that say why neither is computed.
        for banned in ("ICC(2,1)", "ICC(3,1)", "Bland-Altman",
                       "limits of agreement", "responders",
                       "post minus pre", "pre-against-post"):
            self.assertNotIn(banned, self.out, banned)
        self.assertIn("no SEM", self.out)
        self.assertIn("no MDC95 follow from it", self.out)
        self.assertIn("too tight", self.out)
        for name in ("consistency", "within_block_summary"):
            tbl = self.cohort["tables"][name]
            for col in ("icc21", "icc31", "sem", "mdc95", "bias",
                        "loa_lo", "loa_hi"):
                self.assertNotIn(col, tbl.columns, f"{name}.{col}")

    # ---- feasibility -------------------------------------------------
    def test_feasibility_counts_the_sitting_against_the_plan(self) -> None:
        tbl = self.feasible["per_participant"]
        self.assertEqual(set(tbl["participant"]), set(CODES))
        self.assertEqual(set(tbl["battery_blocks"]), {BLOCKS_PER_SITTING})
        self.assertEqual(set(tbl["of_planned"]), {BLOCKS_PER_SITTING})
        p01 = tbl[tbl["participant"] == CODES[0]].iloc[0]
        self.assertEqual(int(p01["free_play_blocks"]), 1)
        self.assertTrue((tbl["playing_min"] >= 0).all())
        self.assertIn("modes_missing", tbl.columns)
        self.assertTrue(tbl["modes_missing"].str.contains("chords").all())
        self.assertIn("COHORT: FEASIBILITY", self.out)
        self.assertIn("finished all", self.out)
        self.assertIn("chassis fit", self.out)
        # Whether the rig found its ports or had them written in by
        # hand depends on the laptop, so what is pinned is that the
        # chapter says which of the two happened.
        self.assertIn("serial port", self.out)

    # ---- validity ----------------------------------------------------
    def test_validity_verdicts_are_plain_and_decided(self) -> None:
        v = self.validity.set_index("id")
        for cid in ("R1", "R2", "P1", "P3", "C1", "C2", "C3",
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
        self.assertIn("R2  pass", self.out)
        self.assertIn("not testable", self.out)

    def test_the_two_dropped_checks_say_why(self) -> None:
        v = self.validity.set_index("id")
        for cid in ("R3", "P2"):
            self.assertEqual(v.loc[cid, "verdict"], "dropped", cid)
            self.assertIn("twice", str(v.loc[cid, "detail"]), cid)
            self.assertIn("DROPPED", str(v.loc[cid, "criterion"]), cid)
        self.assertIn("dropped", self.out)

    def test_the_learning_rows_are_gone_and_the_w_rows_replace_them(self):
        ids = set(self.validity["id"])
        for cid in ("L1", "L2", "L3", "L3b", "L4", "L5", "L6", "L7",
                    "L7b", "L8"):
            self.assertNotIn(cid, ids, f"{cid} outlived the one pass")
        for cid in ("W1", "W2", "W3", "W4", "W5", "W6"):
            self.assertIn(cid, ids, f"{cid} has no verdict row")
        v = self.validity.set_index("id")
        # W1 is the anchor: a number with an interval, never a test.
        self.assertEqual(v.loc["W1", "verdict"], "reported")
        self.assertLess(v.loc["W1", "value"], 0)
        self.assertLessEqual(v.loc["W1", "ci_lo"], v.loc["W1", "value"])
        self.assertLessEqual(v.loc["W1", "value"], v.loc["W1", "ci_hi"])
        self.assertIn("not tested", str(v.loc["W1", "criterion"]))
        # W3 is P1 under its Table 2 id, the same statistic.
        self.assertEqual(v.loc["W3", "mode"], "pattern")
        self.assertIn("P1", str(v.loc["W3", "check"]))
        # Modes with no blocks here still get a row rather than silence.
        self.assertEqual(v.loc["W2", "verdict"], "not testable")

    def test_the_validity_table_has_the_three_added_rows(self) -> None:
        ids = set(self.validity["id"])
        for cid in ("C5", "Rh3", "B5"):
            self.assertIn(cid, ids, f"{cid} has no verdict row")

    def test_echo_e2_is_the_hebb_row(self) -> None:
        rows = self.validity.set_index("id")
        self.assertIn("E2", rows.index)
        self.assertIn("E2p", rows.index)
        self.assertNotIn("E2b", rows.index)
        self.assertIn("Hebb", str(rows.loc["E2", "check"]))

    def test_the_once_played_modes_have_builders_and_rows(self) -> None:
        """Adaptive and syllables are described and never claimed on.
        Without a builder and a registry row the cohort cannot report
        them at all, which is what the audit found."""
        self.assertIn("adaptive", self.ra.COHORT_BUILDERS)
        self.assertIn("syllables", self.ra.COHORT_BUILDERS)
        for mode in ("adaptive", "syllables"):
            rows = {m for (md, m) in self.ra.COHORT_METRICS if md == mode}
            self.assertTrue(rows, f"{mode} has no registry rows")

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
        for name in ("describe", "hands", "consistency", "series",
                     "within_block_ends", "within_block_slopes",
                     "within_block_summary", "feasibility", "validity"):
            self.assertTrue((out_dir / f"cohort_{name}.csv").exists(), name)
        self.assertEqual(self.report, out_dir / "report.html")
        page = self.report.read_text(encoding="utf-8")
        self.assertIn("IMPROVEMENT INSIDE ONE BLOCK", page)
        self.assertIn("KNOWN-EFFECT VALIDITY CHECKS", page)
        self.assertIn("data:image/png;base64", page)
        self.assertIn(f"{len(CODES)} participant(s)", page)

    def test_no_mdc_file_is_written(self) -> None:
        out_dir = Path(self.cohort["out_dir"])
        self.assertFalse((out_dir / "progress_mdc.yaml").exists())
        self.assertIn("No progress_mdc.yaml", self.out)
        self.assertIn("never writes config/user_settings.yaml", self.out)

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
            within = ra.sec_cohort_within_block(cohort)
            ra.sec_cohort_hands(cohort)
            ra.sec_cohort_consistency(cohort)
            val = ra.sec_cohort_validity(cohort, within)
        out = buf.getvalue()
        import matplotlib.pyplot as plt
        plt.close("all")
        self.assertIn("the design analyses 28", out)
        self.assertIn("no statistic is printed", out)
        self.assertEqual(set(within["ends"]["gate"]),
                         {"under the design minimum of 28"})
        decided = set(val["verdict"]) - {"dropped"}
        self.assertEqual(decided, {"not testable"})
        self.assertIn("n under the design minimum", set(val["detail"]))

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
        self.assertNotIn("IMPROVEMENT INSIDE ONE BLOCK", page)
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
        # Three battery blocks plus the one free pick.
        self.assertEqual(len(ctx["folders"]), BLOCKS_PER_SITTING + 1)
        summary = (self.root / "individual_patient_results" / "P01"
                   / "summary.html")
        self.assertTrue(summary.exists(), buf.getvalue())
        self.assertIn("P01", summary.read_text(encoding="utf-8"))
        self.assertTrue(str(here).startswith(str(self.root)))
        after = ({p.name for p in default.iterdir()}
                 if default.is_dir() else set())
        self.assertEqual(after - before, set())

    def test_icc_ci_is_kept_and_unused(self) -> None:
        """Design Section 4.8f: icc_ci computes nothing in this study
        and stays in the notebook for the test-retest study that
        follows. It is pinned to the Shrout and Fleiss worked example so
        it is still correct when that study picks it up."""
        import numpy as np
        sf = np.array([[9, 2, 5, 8], [6, 1, 3, 2], [8, 4, 6, 8],
                       [7, 1, 2, 6], [10, 5, 6, 9], [6, 2, 4, 7]], float)
        icc = self.ra.icc_ci(sf)
        self.assertAlmostEqual(icc["icc21"], 0.29, places=2)
        self.assertAlmostEqual(icc["lo21"], 0.019, places=3)
        self.assertAlmostEqual(icc["hi21"], 0.761, places=3)
        self.assertAlmostEqual(icc["icc31"], 0.715, places=3)
        self.assertAlmostEqual(self.ra.icc_two_one(sf), icc["icc21"],
                               places=9)
        # And no cohort section calls it.
        self.assertNotIn("icc_ci(", self.out)


class CohortStatisticsHelperTests(unittest.TestCase):
    """The helpers the one-pass design leans on, on inputs whose
    answers are known without any session data."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.ra = _load_notebook()

    def test_split_half_interval_contains_a_known_correlation(self):
        import numpy as np
        rng = np.random.default_rng(11)
        # Twelve people, each with 40 trials drawn around their own
        # mean: the split-half of a stable per-person mean is high.
        by_person = {f"P{i:02d}": (200.0 + 20.0 * i
                                   + rng.normal(0, 15.0, 40)).tolist()
                     for i in range(12)}
        r, lo, hi = self.ra.split_half(by_person, n_splits=200)
        self.assertTrue(lo <= r <= hi)
        self.assertGreater(r, 0.8)
        self.assertLessEqual(hi, 1.0000001)
        # Under three people there is nothing to correlate.
        self.assertTrue(all(v != v for v in
                            self.ra.split_half({"a": [1, 2, 3, 4]})))

    def test_tost_says_equivalent_at_five_ms_and_not_at_forty(self):
        import numpy as np
        rng = np.random.default_rng(3)
        base = 300.0 + rng.normal(0, 10.0, 30)
        close = base + 5.0 + rng.normal(0, 2.0, 30)
        far = base + 40.0 + rng.normal(0, 2.0, 30)
        _p, ok = self.ra.tost_paired(base, close, 20.0)
        self.assertTrue(ok)
        _p, ok = self.ra.tost_paired(base, far, 20.0)
        self.assertFalse(ok)

    def test_wilson_stays_inside_zero_to_one_at_the_edges(self) -> None:
        for k, n in ((0, 10), (10, 10), (1, 3)):
            share, lo, hi = self.ra.wilson_ci(k, n)
            self.assertAlmostEqual(share, k / n)
            self.assertGreaterEqual(lo, 0.0)
            self.assertLessEqual(hi, 1.0)
            self.assertLessEqual(lo, share)
            self.assertLessEqual(share, hi)
        self.assertTrue(all(v != v for v in self.ra.wilson_ci(0, 0)))

    def test_log_linear_slope_is_negative_on_a_falling_series(self):
        import numpy as np
        y = [300.0 - 30.0 * np.log(i + 1) for i in range(1, 21)]
        slope, se, n = self.ra.log_linear_slope(y)
        self.assertEqual(n, 20)
        self.assertLess(slope, 0)
        self.assertGreaterEqual(se, 0)
        lo, hi = self.ra._slope_ci(slope, se, n)
        self.assertLessEqual(lo, slope)
        self.assertLessEqual(slope, hi)
        self.assertTrue(all(v != v for v in
                            self.ra.log_linear_slope([1.0, 2.0])[:2]))

    def test_exp_fit_recovers_a_known_rate(self) -> None:
        import numpy as np
        a, b, c = 200.0, 120.0, 0.25
        y = [a + b * np.exp(-c * x) for x in range(20)]
        fa, fb, fc, ok = self.ra.exp_fit(y)
        self.assertTrue(ok)
        self.assertAlmostEqual(fc, c, delta=0.2 * c)
        self.assertAlmostEqual(fa, a, delta=0.05 * a)
        # Too few points: no fit is attempted and it says so.
        self.assertFalse(self.ra.exp_fit(y[:4])[3])

    def test_the_median_interval_widens_with_a_smaller_sample(self) -> None:
        for n, want in ((6, (1, 6)), (10, (2, 9)), (20, (6, 15))):
            lo, hi, cover = self.ra.median_order_ci(n)
            self.assertEqual((lo, hi), want, n)
            self.assertGreaterEqual(cover, 0.95)

    def test_the_notebook_phase_matches_the_shipped_preset(self) -> None:
        from finger_rehab.config import Config
        cfg = Config.load()
        preset = cfg.get("protocol.presets.study_battery") or {}
        orders = (preset.get("orders") or {}).values()
        phases = {str(step.get("phase") or "").strip().lower()
                  for order in orders for step in order}
        self.assertEqual(set(self.ra.COHORT_PHASES), phases)
        self.assertEqual(len(phases), 1)
        # The one pass plays every mode and hand once, which is what
        # makes every test-retest quantity uncomputable.
        for name, order in (preset.get("orders") or {}).items():
            seen = [(s.get("mode"), s.get("hand")) for s in order]
            self.assertEqual(len(seen), len(set(seen)),
                             f"order {name} repeats a block")


if __name__ == "__main__":
    unittest.main()
