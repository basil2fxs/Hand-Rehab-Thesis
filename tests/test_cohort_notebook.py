"""The cohort chapter of the notebook, driven end to end on a synthetic
cohort the REAL engine wrote.

Five participant codes play ONE sitting each on the keyboard source,
through the REAL battery machinery with a shortened preset: a reaction
block per hand and a bilateral echo block early (phase pre), the same
three again late (phase post), with a rest scheduled before the first
post block. A named person, a code with no visit and one free-play
block with no battery phase are mixed into the same tree to prove the
selection and the pre-against-post tables leave them where they
belong. The folders are then handed to the real notebook functions
(build_catalogue, sec_cohort_selection and the sections after it), the
same path tests/test_force_pilot_notebook_levels.py walks.

What this pins: the long table's shape, phases, positions and hand
roles, the within-session reliability path (split-half, ICC interval,
SEM, MDC), the pre-to-post change and its responder count, the
learning-curve fits, the validity verdicts including the L rows, the
CSVs, progress_mdc.yaml and the report on disk, the small-n refusal,
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
TRIALS_PER_REACTION_BLOCK = 12
# The sitting, shortened. The shipped preset is twenty blocks; three
# modes twice is enough to exercise every pre-against-post path and
# still runs in seconds. rest_before on the first POST block is what
# gives metadata battery.rest_before_s, which the post-rest contrast
# reads.
SHORT_ORDER = [
    {"mode": "reaction", "hand": "hand1", "phase": "pre"},
    {"mode": "reaction", "hand": "hand2", "phase": "pre"},
    {"mode": "echo", "hand": "both", "phase": "pre"},
    {"mode": "reaction", "hand": "hand1", "phase": "post",
     "rest_before": True},
    {"mode": "reaction", "hand": "hand2", "phase": "post"},
    {"mode": "echo", "hand": "both", "phase": "post"},
]
BLOCKS_PER_SITTING = len(SHORT_ORDER)
# The gain injected between the two goes: the POST reaction blocks run
# 20 ms faster, which the learning table has to recover with the right
# sign and the right word.
POST_GAIN_MS = 20.0


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
    # the same six steps, so every code's sitting is the same shape and
    # the phase stamping is the shipped one, not a hand-written stub.
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


def _drive_reaction(eng, hand: str, base_ms: float, rng: random.Random,
                    n_trials: int = TRIALS_PER_REACTION_BLOCK) -> None:
    """Play an OPEN reaction block: every trial answered on the cued
    finger about base_ms after the stimulus, driven the way
    tests/test_reaction_mode.py drives the mode."""
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
        phase = str(eng._current_phase)
        if mode_name == "reaction":
            hand = str(eng.hand_mode)
            slow = 30.0 if hand != dom else 0.0
            gain = POST_GAIN_MS if phase == "post" else 0.0
            _drive_reaction(eng, hand, base + slow - gain, rng)
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

    Every code plays the six steps of SHORT_ORDER in one session, so
    each block carries battery.phase and battery.position and every
    trial row carries the phase column. A named person, a code with no
    visit and one free-play block with no battery phase go into the
    same tree: the first two must be dropped by the selection, the
    third must reach the export and stay out of every pre-against-post
    table.
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
                visit="1", hand_length_mm="185",
                hand_breadth_mm="82")
            # A fake rig has no calibration behind it; the guard would
            # put a question up. The clinician has answered it here.
            eng._uncal_ack = {"left", "right"}
            _play_battery(eng, dom, 250.0 + 15.0 * i, rng,
                          fail_from=4 + i)
            if code == CODES[0]:
                # One free pick after the battery: no battery stamp, so
                # phase is empty and the pre-post tables must ignore it.
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
            cls.within = ra.keep(cls.ctx, "cohort_within_session",
                                 ra.sec_cohort_within_session(cls.cohort))
            cls.retest = cls.within["table"]
            cls.learning = ra.keep(
                cls.ctx, "cohort_learning",
                ra.sec_cohort_learning(cls.cohort, cls.within))
            cls.curves = ra.keep(cls.ctx, "cohort_curves",
                                 ra.sec_cohort_curves(cls.cohort))
            cls.one_pass = ra.keep(cls.ctx, "cohort_one_pass",
                                   ra.sec_cohort_one_pass(cls.cohort))
            cls.validity = ra.keep(cls.ctx, "cohort_validity",
                                   ra.sec_cohort_validity(cls.cohort))
            cls.written = ra.keep(
                cls.ctx, "cohort_export",
                ra.sec_cohort_export(cls.cohort, cls.within,
                                     cls.learning))
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
        # Six battery blocks each, plus P01's one free pick.
        self.assertEqual(len(sel), len(CODES) * BLOCKS_PER_SITTING + 1)
        dropped = self.cohort["dropped"]
        self.assertEqual(dropped["name_not_code"], 1)
        self.assertEqual(dropped["no_visit"], 1)
        people = self.cohort["people"]
        self.assertEqual(list(people["visits"]), [1] * len(CODES))
        self.assertEqual(
            people.set_index("participant").loc["P03", "dominant_hand"],
            "left")

    def test_the_phase_and_the_position_come_off_the_battery(self) -> None:
        sel = self.cohort["sel"]
        battery = sel[sel["phase"] != ""]
        self.assertEqual(set(battery["phase"]), {"pre", "post"})
        self.assertEqual(len(battery), len(CODES) * BLOCKS_PER_SITTING)
        # The free pick carries no phase and is not dropped.
        free = sel[sel["phase"] == ""]
        self.assertEqual(len(free), 1)
        self.assertEqual(free["participant"].iloc[0], CODES[0])
        for who, g in battery.groupby("participant"):
            positions = sorted(int(v) for v in g["battery_position"])
            self.assertEqual(positions,
                             list(range(1, BLOCKS_PER_SITTING + 1)), who)

    def test_the_free_play_block_stays_out_of_the_paired_tables(self):
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
        # ...and out of every pre-against-post row.
        for tbl in (self.retest, self.learning["table"]):
            self.assertNotIn("", set(tbl.get("phase", [])))

    def test_long_table_shape_and_hand_roles(self) -> None:
        long = self.cohort["long"]
        self.assertEqual(list(long.columns), self.ra.COHORT_LONG_COLS)
        self.assertEqual(set(long["participant"]), set(CODES))
        self.assertEqual(set(long["mode"]), {"reaction", "echo"})
        self.assertEqual(set(long["visit"]), {"1"})
        self.assertEqual(set(long["phase"]), {"pre", "post", ""})
        battery = long[long["phase"] != ""]
        self.assertTrue((battery["position"] >= 1).all())
        self.assertTrue((battery["position"] <= BLOCKS_PER_SITTING).all())
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
        spans = echo[(echo["metric"] == "span") & (echo["phase"] == "pre")]
        self.assertEqual(
            spans.set_index("participant")["value"].to_dict(),
            {code: float(3 + i) for i, code in enumerate(CODES)})
        # Every block ran under the same config, so one hash per mode.
        self.assertEqual(long.groupby("mode")["config_hash"].nunique()
                         .max(), 1)
        self.assertEqual(set(long["day"]), {time.strftime("%Y-%m-%d")})

    def test_the_cohort_pick_word_selects_codes(self) -> None:
        sel = self.ra.resolve("cohort", self.cat)
        self.assertEqual(set(sel["who"]), set(CODES) | {"P09"})

    # ---- descriptives ------------------------------------------------
    def test_normative_table_prints_at_the_minimum(self) -> None:
        self.assertIn("normative table, the PRE go", self.out)
        d = self.desc[(self.desc["mode"] == "reaction")
                      & (self.desc["metric"] == "median_rt_ms")
                      & (self.desc["phase"] == "pre")]
        self.assertEqual(set(d["hand_role"]), {"dominant", "nondominant"})
        self.assertEqual(list(d["n"]), [len(CODES)] * 2)
        row = d[d["hand_role"] == "dominant"].iloc[0]
        self.assertLessEqual(row["p5"], row["median"])
        self.assertLessEqual(row["median"], row["p95"])

    # ---- dominant against non-dominant -------------------------------
    def test_hand_comparison_finds_the_built_in_advantage(self) -> None:
        h = self.hands[(self.hands["mode"] == "reaction")
                       & (self.hands["metric"] == "median_rt_ms")
                       & (self.hands["phase"] == "pre")].iloc[0]
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
                         & (self.hands["phase"] == "pre")].iloc[0]
        self.assertEqual(acc["test"], "no variation")
        self.assertIn("accuracy: dominant equals non-dominant; n 5, "
                      "no variation between the pairs", self.out)
        self.assertNotIn("p nan", self.out)
        self.assertNotIn("dz +nan", self.out)

    # ---- within-session reliability ----------------------------------
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
        self.assertIn("WITHIN SESSION, SAME SITTING", self.out)
        figs = Path(self.cohort["out_dir"]) / "figures"
        self.assertTrue((figs / "cohort_icc_forest.png").exists())
        self.assertTrue((figs / "cohort_bland_altman_within.png").exists())

    def test_split_half_runs_where_the_trials_exist_and_says_so_where_not(
            self) -> None:
        r = self.retest
        rx = r[(r["mode"] == "reaction")
               & (r["metric"] == "median_rt_ms")
               & (r["hand_role"] == "dominant")].iloc[0]
        self.assertEqual(rx["split_note"], "")
        self.assertTrue(-1.0 <= rx["r_split"] <= 1.0)
        self.assertLessEqual(rx["r_split_lo"], rx["r_split"])
        self.assertLessEqual(rx["r_split"], rx["r_split_hi"])
        span = r[(r["mode"] == "echo")
                 & (r["metric"] == "span")].iloc[0]
        self.assertTrue(span["r_split"] != span["r_split"])   # NaN
        self.assertIn("nothing to split", span["split_note"])
        self.assertIn("nothing to split", self.out)

    def test_the_mdc_map_is_keyed_by_mode_and_metric(self) -> None:
        mdc = self.within["mdc"]
        self.assertIn(("reaction", "median_rt_ms"), mdc)
        self.assertGreater(mdc[("reaction", "median_rt_ms")], 0)

    # ---- change from the first go to the last ------------------------
    def test_learning_table_recovers_the_injected_gain(self) -> None:
        tbl = self.learning["table"]
        p = tbl[(tbl["mode"] == "reaction")
                & (tbl["metric"] == "median_rt_ms")
                & (tbl["hand_role"] == "dominant")]
        self.assertEqual(len(p), 1)
        self.assertEqual(int(p["n"].iloc[0]), len(CODES))
        self.assertLess(p["diff"].iloc[0], 0)          # post faster
        self.assertAlmostEqual(float(p["diff"].iloc[0]), -POST_GAIN_MS,
                               delta=15.0)
        self.assertEqual(p["in_words"].iloc[0], "faster")
        self.assertIn("pre", p["direction"].iloc[0])
        self.assertIn("faster: pre higher than post", self.out)
        self.assertIn("CHANGE FROM THE FIRST GO TO THE LAST", self.out)
        self.assertIn("Kantak and Winstein 2012", self.out)

    def test_responders_are_counted_against_this_tables_own_mdc(self):
        resp = self.learning["responders"]
        row = resp[(resp["mode"] == "reaction")
                   & (resp["metric"] == "median_rt_ms")
                   & (resp["hand_role"] == "dominant")].iloc[0]
        self.assertEqual(int(row["n"]), len(CODES))
        self.assertEqual(float(row["mdc95"]),
                         self.within["mdc"][("reaction", "median_rt_ms")])
        self.assertGreaterEqual(int(row["responders"]), 0)
        self.assertLessEqual(int(row["responders"]), len(CODES))
        self.assertLessEqual(row["ci_lo"], row["share"])
        self.assertLessEqual(row["share"], row["ci_hi"])
        self.assertTrue(0.0 <= row["ci_lo"] <= 1.0)
        self.assertTrue(0.0 <= row["ci_hi"] <= 1.0)
        # A metric with no MDC gets no count and says why.
        blank = resp[resp["responders"].isna()]
        self.assertTrue(len(blank))
        self.assertTrue((blank["note"].str.len() > 0).all())

    def test_the_post_rest_contrast_names_the_short_rests(self) -> None:
        self.assertIn("post-rest contrast", self.out)
        self.assertIn("under 120 s", self.out)

    # ---- learning curves ---------------------------------------------
    def test_curves_fit_per_person_and_carry_the_direction(self) -> None:
        slopes = self.curves["slopes"]
        self.assertFalse(slopes.empty)
        self.assertEqual(set(slopes["mode"]), {"reaction", "echo"})
        rx = slopes[slopes["mode"] == "reaction"]
        self.assertEqual(set(rx["participant"]), set(CODES))
        self.assertEqual(set(rx["better"]), {"lower"})
        self.assertTrue((rx["n_pre"] > 0).all())
        self.assertTrue((rx["n_post"] > 0).all())
        echo = slopes[slopes["mode"] == "echo"]
        self.assertEqual(set(echo["better"]), {"higher"})
        self.assertIn("LEARNING CURVES", self.out)
        self.assertIn("Heathcote", self.out)

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
        # The learning table (Section 4.6 table 2) rides in the same
        # frame. L1 is the anchor: reaction is expected NOT to move
        # across the sitting, tested as equivalence.
        for cid in ("L1", "L2", "L3", "L4", "L5", "L6", "L7", "L8"):
            self.assertIn(cid, v.index, cid)
        self.assertIn("equivalence", " ".join(
            str(x) for x in v.loc[["R3", "L1"], "criterion"]).lower()
            + str(v.loc["L1", "criterion"]))
        self.assertIn("+/- 20", str(v.loc["L1", "criterion"]))
        self.assertEqual(v.loc["L8", "verdict"], "not testable")
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
        for name in ("describe", "hands", "within_session", "learning",
                     "responders", "slopes", "validity"):
            self.assertTrue((out_dir / f"cohort_{name}.csv").exists(), name)
        self.assertEqual(self.report, out_dir / "report.html")
        page = self.report.read_text(encoding="utf-8")
        self.assertIn("WITHIN-SESSION RELIABILITY, SEM AND MDC", page)
        self.assertIn("KNOWN-EFFECT VALIDITY CHECKS", page)
        self.assertIn("data:image/png;base64", page)
        self.assertIn(f"{len(CODES)} participant(s)", page)

    def test_progress_mdc_yaml_is_written_and_parses(self) -> None:
        import yaml
        path = Path(self.cohort["out_dir"]) / "progress_mdc.yaml"
        self.assertIn(path, self.written)
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        value = data["progress"]["mdc"]["reaction"]["median_rt_ms"]
        self.assertIsInstance(float(value), float)
        self.assertGreater(float(value), 0.0)
        # One key per mode, not one per metric row.
        self.assertEqual(len(data["progress"]["mdc"]),
                         len(set(data["progress"]["mdc"])))
        self.assertIn("never writes that file itself",
                      path.read_text(encoding="utf-8"))

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
        # The simulated player never times out, so n_omissions is zero
        # for everyone in both phases: reported as undefined with the
        # reason, never as a bare NaN. (n_omissions rather than the old
        # hebb_minus_novel_acc: the shipped echo rule is Simon, which
        # has no hidden repeats to score, so that metric only exists
        # for a legacy ladder block.)
        r = self.retest
        row = r[(r["mode"] == "echo")
                & (r["metric"] == "n_omissions")].iloc[0]
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
            within = ra.sec_cohort_within_session(cohort)
            tbl = within["table"]
            ra.sec_cohort_hands(cohort)
            val = ra.sec_cohort_validity(cohort)
        out = buf.getvalue()
        import matplotlib.pyplot as plt
        plt.close("all")
        self.assertIn("the design analyses 28", out)
        self.assertIn("no statistic is printed", out)
        self.assertNotIn("ICC(2,1) is two-way random", out)
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
        self.assertNotIn("WITHIN-SESSION RELIABILITY", page)
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
        # Six battery blocks plus the one free pick.
        self.assertEqual(len(ctx["folders"]), BLOCKS_PER_SITTING + 1)
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
        v1 = spans[spans["phase"] == "pre"].set_index("participant")["value"]
        copy = long.copy()
        mask = (copy["mode"] == "echo") & (copy["metric"] == "span")
        copy.loc[mask, "value"] = copy.loc[mask, "participant"].map(v1)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            r = self.ra.sec_cohort_within_session(
                dict(self.cohort, long=copy, tables={}))["table"]
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

    # ---- the ONE PASS chapter ---------------------------------------
    # The design's amendment drops every POST block, and with it every
    # test-retest statistic. What survives has to be in the notebook
    # and has to be labelled for what it is: the curve inside a single
    # block with an interval, the first third of that block against
    # its last, and split-half reliability on the PRE block alone.

    def test_the_chapter_says_what_one_pass_cannot_give(self) -> None:
        self.assertIn("COHORT: WHAT ONE PASS CAN SAY", self.out)
        low = self.out.lower()
        self.assertIn("no test-retest coefficient", low)
        self.assertIn("internal consistency", low)

    def test_the_within_block_curve_carries_an_interval(self) -> None:
        curves = self.one_pass["curves"]
        self.assertFalse(curves.empty, "no within-block curve at all")
        for col in ("mode", "slice", "n", "mean", "ci_lo", "ci_hi",
                    "better"):
            self.assertIn(col, curves.columns)
        rows = curves.dropna(subset=["ci_lo", "ci_hi"])
        self.assertTrue(len(rows))
        self.assertTrue(
            ((rows["ci_lo"] <= rows["mean"])
             & (rows["mean"] <= rows["ci_hi"])).all())

    def test_first_against_last_is_paired_with_an_effect_size(self) -> None:
        ends = self.one_pass["ends"]
        self.assertFalse(ends.empty, "no first-against-last contrast")
        for col in ("mode", "n", "first_third", "last_third", "diff",
                    "dz", "dz_lo", "dz_hi", "test", "improved", "gate"):
            self.assertIn(col, ends.columns)
        reaction = ends[ends["mode"] == "reaction"]
        self.assertTrue(len(reaction), "reaction has no contrast")
        row = reaction.iloc[0]
        self.assertEqual(row["gate"], "reported")
        self.assertTrue(row["dz_lo"] <= row["dz"] <= row["dz_hi"])

    def test_split_half_is_computed_without_a_post_block(self) -> None:
        sh = self.one_pass["split_half"]
        self.assertFalse(sh.empty, "no split-half rows")
        self.assertIn(("reaction", "median_rt_ms"),
                      set(zip(sh["mode"], sh["metric"])))
        for _i, r in sh[sh["gate"] == "reported"].iterrows():
            self.assertTrue(-1.0 <= float(r["r_split"]) <= 1.0)

    def test_the_checks_that_need_a_repeated_block_are_named(self) -> None:
        needs = self.ra.COHORT_NEEDS_POST
        for cid in ("R3", "P2", "L1", "L8"):
            self.assertIn(cid, needs)

    def test_the_once_played_modes_have_builders_and_rows(self) -> None:
        """Adaptive and syllables are played once in the middle pass.
        Without a builder and a registry row the cohort cannot report
        them at all, which is what the audit found."""
        self.assertIn("adaptive", self.ra.COHORT_BUILDERS)
        self.assertIn("syllables", self.ra.COHORT_BUILDERS)
        for mode in ("adaptive", "syllables"):
            rows = {m for (md, m) in self.ra.COHORT_METRICS if md == mode}
            self.assertTrue(rows, f"{mode} has no registry rows")

    def test_a_descriptive_metric_never_reaches_the_reliability_table(
            self) -> None:
        table = self.within["table"]
        if len(table):
            self.assertEqual(
                set(table["mode"]) & {"adaptive", "syllables"}, set())

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


class CohortStatisticsHelperTests(unittest.TestCase):
    """The four helpers the single-session design added, on inputs
    whose answers are known without any session data."""

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

    def test_the_notebook_phases_match_the_shipped_preset(self) -> None:
        from finger_rehab.config import Config
        cfg = Config.load()
        preset = cfg.get("protocol.presets.study_battery") or {}
        phases = {str(step.get("phase") or "").strip().lower()
                  for order in (preset.get("orders") or {}).values()
                  for step in order}
        self.assertEqual(set(self.ra.COHORT_PHASES), phases)
        self.assertEqual(set(self.ra.COHORT_PAIR_PHASES), {"pre", "post"})


if __name__ == "__main__":
    unittest.main()
