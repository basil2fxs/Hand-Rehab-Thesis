"""The per-mode literature chapters, driven on blocks the REAL engine
wrote.

Every one of the ten live modes has to answer four questions in the
notebook: what does the literature predict, what did this hand do, what
does it look like per finger and per hand, and what can the numbers NOT
be used to say. Mirror and adaptive had no chapter at all before this;
the rest had the numbers but not the verdicts.

The blocks here are played headless through the real GameEngine on the
fake-board rig tests/test_hand_support.py uses, then handed to the real
notebook functions. Force Pilot and Buzz Hunt need a force trace and a
motor, so they are covered by their own notebook tests
(tests/test_force_pilot_notebook_levels.py,
tests/test_buzz_hunt_notebook_window.py); what is pinned for them here
is that their chapter still prints every check with its reference when
the selection holds no such block, which is what lets the thesis cite
the check whether or not this pick has the data.
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

from tests.test_hand_support import (make_engine, drive, patched_clock,
                                     _press)

MODES = ("reaction", "pattern", "chords", "syllables", "adaptive",
         "rhythm", "mirror", "force_pilot", "buzz_hunt", "echo")


def setUpModule() -> None:
    import pygame
    pygame.init()
    pygame.display.set_mode((1280, 800))


def tearDownModule() -> None:
    import pygame
    pygame.quit()


def _load_notebook():
    """Every notebook cell's definitions in one namespace, the pattern
    the other per-chapter tests use."""
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_mode_checks"
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
    return SimpleNamespace(**{k: v for k, v in ns.items()
                              if not k.startswith("__")})


def _cadence(eng, hand_mode, seed=11):
    """Press whatever was cued, about a fifth of a second later.

    The latency is jittered on a seeded generator on purpose: a driver
    that answers every cue at exactly the same delay gives a reaction
    block with zero RT variance, and a correlation against the
    foreperiod is then undefined rather than near zero, so R1 could
    never be decided on a synthetic block.
    """
    import random
    rng = random.Random(seed)
    seen = {"n": 0}

    def respond(clock):
        record = eng._stim_record
        while seen["n"] < len(record):
            lanes = record[seen["n"]]
            seen["n"] += 1
            for lane in lanes:
                hand = ("left" if hand_mode == "both" and lane >= 4
                        else hand_mode if hand_mode != "both" else "right")
                if eng.mode is not None:
                    eng.mode.queue_press(
                        _press(lane, clock.t + rng.uniform(0.16, 0.32),
                               hand=hand))
    return respond


def _cue_block(root, hand_mode, starter, trials, want, tweak=None):
    with patched_clock() as clock:
        eng = make_engine(hand_mode, str(root))
        eng.cfg.data["game"]["test_mode_enabled"] = True
        eng.cfg.data["game"]["test_mode_trials"] = trials
        if tweak is not None:
            tweak(eng.cfg.data)
        starter(eng)
        drive(eng, clock, responder=_cadence(eng, hand_mode),
              stop=lambda: (len(eng._stim_record) >= want
                            or eng.trial_logger is None))
        if eng.trial_logger is not None:
            eng.finish_block()


def _rhythm_block(root, hand_mode):
    from finger_rehab.audio.beatmap import procedural_beatmap
    with patched_clock() as clock:
        eng = make_engine(hand_mode, str(root))
        eng.cfg.data["game"]["test_mode_enabled"] = True
        eng.cfg.data["game"]["test_mode_trials"] = 24
        bm = procedural_beatmap(bpm=110, beats=24, difficulty="hard",
                                num_lanes=eng.total_lanes)
        eng.begin_rhythm_block(bm)
        drive(eng, clock, responder=_cadence(eng, hand_mode),
              stop=lambda: (len(eng._stim_record) >= 20
                            or eng.trial_logger is None))
        if eng.trial_logger is not None:
            eng.finish_block()


def _echo_block(root, hand_mode, fail_from=5):
    with patched_clock() as clock:
        eng = make_engine(hand_mode, str(root))
        eng.cfg.data.setdefault("echo", {})["seed"] = 977
        eng.begin_echo_block()
        mode = eng.mode
        answered = {"n": 0}

        def respond(clk):
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

        drive(eng, clock, responder=respond, max_steps=40000,
              stop=lambda: eng.trial_logger is None)
        if eng.trial_logger is not None:
            eng.finish_block()


class ModeChecksTests(unittest.TestCase):
    """One tree, seven modes played, every chapter run once."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory()
        cls.root = Path(cls._td.name)
        _cue_block(cls.root, "both",
                   lambda e: e.begin_reaction_block(), 16, 14)
        _cue_block(cls.root, "right",
                   lambda e: e.begin_adaptive_block(), 16, 14)
        # A pattern block short enough to drive but long enough to
        # reach a PROBE take: the accuracy rebound is a
        # probe-minus-flankers contrast, so a block that never gets
        # past its first trained take has nothing to score. The shape
        # is the shipped one, just with one cycle per take.
        _cue_block(cls.root, "right",
                   lambda e: e.begin_pattern_block(), 400, 380,
                   tweak=lambda cfg: cfg["pattern"].update(
                       {"short_session": True, "warmup_trials": 4,
                        "random_block_trials": 8,
                        "soc_cycles_per_block": 1, "rest_min_s": 0,
                        "long_rest_s": 0}))
        _cue_block(cls.root, "both",
                   lambda e: e.begin_chords_block(), 14, 12)
        _cue_block(cls.root, "both",
                   lambda e: e.begin_mirror_block(), 14, 12)
        _rhythm_block(cls.root, "both")
        _echo_block(cls.root, "both")
        cls.ra = ra = _load_notebook()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cls.ctx = ra.prepare("all", root=cls.root)
            t = cls.ctx["trials"]
            m = cls.ctx["metas"]
            f = cls.ctx["folders"]
            cs = cls.ctx["calset"]
            cls.out = {}
            for label, call in (
                    ("reaction", lambda: ra.sec_reaction_checks(t, m)),
                    ("pattern", lambda: ra.sec_pattern_checks(t, m)),
                    ("chords", lambda: ra.sec_chords_checks(t, m, cs)),
                    ("syllables", lambda: ra.sec_syllables_checks(t, m)),
                    ("adaptive", lambda: ra.sec_adaptive(t, m)),
                    ("rhythm", lambda: ra.sec_rhythm_checks(t, m)),
                    ("mirror", lambda: ra.sec_mirror(t, m)),
                    ("force_pilot",
                     lambda: ra.sec_force_pilot_checks(f, t, m)),
                    ("buzz_hunt",
                     lambda: ra.sec_buzz_hunt_checks(f, t, m)),
                    ("echo", lambda: ra.sec_echo_checks(t, m))):
                one = io.StringIO()
                with contextlib.redirect_stdout(one):
                    cls.out[label] = {"result": call()}
                cls.out[label]["text"] = one.getvalue()
        import matplotlib.pyplot as plt
        plt.close("all")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    # ---- every mode, whether or not this pick has its data -----------

    def test_every_mode_prints_its_checks_with_the_reference(self) -> None:
        for mode in MODES:
            text = self.out[mode]["text"]
            with self.subTest(mode=mode):
                self.assertIn(f"LITERATURE CHECKS, {mode}", text)
                for spec in self.ra.MODE_LIT[mode]:
                    self.assertIn(spec["id"], text)
                    self.assertIn(spec["reference"], text)
                    self.assertIn(spec["source"], text)

    def test_every_mode_prints_its_claim_limits(self) -> None:
        for mode in MODES:
            with self.subTest(mode=mode):
                self.assertIn(f"WHAT THE {mode.upper()} NUMBERS CANNOT SAY",
                              self.out[mode]["text"])

    def test_a_mode_with_no_block_says_so_and_still_cites(self) -> None:
        """Force Pilot and Buzz Hunt are not in this tree. Their
        chapters still have to name every check and its source, so the
        thesis can cite them from a pick that lacks the block."""
        for mode in ("force_pilot", "buzz_hunt"):
            text = self.out[mode]["text"]
            with self.subTest(mode=mode):
                self.assertIn("not testable", text)
                self.assertIn("no data", text)
                self.assertIn(self.ra.MODE_LIT[mode][0]["source"], text)

    # ---- the modes this tree does hold -------------------------------

    def test_reaction_decides_r1_and_cuts_by_finger(self) -> None:
        res = self.out["reaction"]["result"]
        ids = set(res["checks"]["id"])
        self.assertIn("R1", ids)
        row = res["checks"].set_index("id").loc["R1"]
        self.assertIn("rho", str(row["value"]))
        self.assertNotEqual(row["verdict"], "not testable")
        pf = res["per_finger"]
        self.assertFalse(pf.empty, "no per-finger table")
        self.assertIn("finger", pf.columns)
        self.assertIn("side", pf.columns)

    def test_mirror_has_a_chapter_with_the_kelso_anchor(self) -> None:
        res = self.out["mirror"]["result"]
        text = self.out["mirror"]["text"]
        self.assertGreater(res["n_clean_pairs"], 0)
        self.assertIsNotNone(res["mean_gap_ms"])
        self.assertIsNotNone(res["hit_rate"])
        # The two numbers the design says to read the gap against.
        self.assertIn("60 ms", text)
        self.assertIn("350 ms", text)
        self.assertIn("clean pair", text)
        # The claim limits the mode's own docstring insists on.
        self.assertIn("Whitall", text)
        self.assertIn("contested", text)
        self.assertFalse(res["per_finger"].empty)

    def test_mirror_reports_the_pace_the_gap_was_measured_at(self) -> None:
        row = self.out["mirror"]["result"]["checks"].set_index("id")
        self.assertIn("M3", row.index)
        self.assertIn("BPM", str(row.loc["M3", "value"]))

    def test_adaptive_reports_the_cap_not_just_the_band(self) -> None:
        res = self.out["adaptive"]["result"]
        self.assertIsNotNone(res["bpm_cap"])
        self.assertIsNotNone(res["bpm_max_seen"])
        row = res["checks"].set_index("id")
        self.assertIn("A3", row.index)
        self.assertIn("cap", str(row.loc["A3", "value"]))
        self.assertTrue(res["lane_rates"], "no per-lane hit rates")

    def test_rhythm_splits_the_two_hands(self) -> None:
        ph = self.out["rhythm"]["result"]["per_hand"]
        self.assertFalse(ph.empty)
        self.assertEqual(set(ph["hand"]), {"left", "right"})
        for col in ("mean_asyn_ms", "sd_asyn_ms", "ci_lo", "ci_hi",
                    "lag1"):
            self.assertIn(col, ph.columns)
        # The pooled bias a bilateral block used to print is not what
        # this chapter reports: each hand carries its own.
        self.assertEqual(len(ph), 2)

    def test_rhythm_names_repp_rose_and_thaut(self) -> None:
        text = self.out["rhythm"]["text"]
        for name in ("Repp 2005", "Rose", "Thaut"):
            self.assertIn(name, text)

    def test_pattern_rescores_the_accuracy_rebound_offline(self) -> None:
        """P3 used to be read straight out of block_stats, so the
        notebook had no independent check on it. It is scored here from
        the take table with the same flanker rule the RT learning score
        uses: probe minus the mean of the trained takes either side.
        """
        import pandas as pd
        takes = pd.DataFrame([
            {"game": "g", "session": "s", "take": "1", "kind": "seq",
             "soc": "", "order": 1.0, "n": 12, "accuracy": 1.00,
             "rt_ms": 300.0, "n_rt": 12},
            {"game": "g", "session": "s", "take": "2", "kind": "probe",
             "soc": "b", "order": 2.0, "n": 12, "accuracy": 0.80,
             "rt_ms": 380.0, "n_rt": 12},
            {"game": "g", "session": "s", "take": "3", "kind": "seq",
             "soc": "", "order": 3.0, "n": 12, "accuracy": 0.90,
             "rt_ms": 305.0, "n_rt": 12},
        ])
        reb = self.ra.pattern_accuracy_rebound(takes)
        self.assertEqual(len(reb), 1)
        row = reb.iloc[0]
        self.assertEqual(row["n_flankers"], 2)
        self.assertAlmostEqual(row["probe_accuracy"], 0.80)
        self.assertAlmostEqual(row["trained_accuracy"], 0.95)
        # Positive means accuracy FELL on the fresh material, which is
        # the direction the design predicts.
        self.assertAlmostEqual(row["accuracy_rebound_pct"], 15.0)
        # A probe with no trained take beside it is not scored at all.
        alone = takes[takes["kind"] == "probe"]
        self.assertTrue(self.ra.pattern_accuracy_rebound(alone).empty)

    def test_the_pattern_chapter_returns_a_rebound_frame(self) -> None:
        res = self.out["pattern"]["result"]
        self.assertIn("rebound", res)
        for col in ("probe_accuracy", "trained_accuracy",
                    "accuracy_rebound_pct"):
            if len(res["rebound"]):
                self.assertIn(col, res["rebound"].columns)

    def test_chords_reports_c5_as_a_null(self) -> None:
        row = self.out["chords"]["result"]["checks"].set_index("id")
        self.assertIn("C5", row.index)
        self.assertIn(row.loc["C5", "verdict"],
                      ("reported", "not testable"))

    def test_echo_numbers_hebb_as_e2(self) -> None:
        checks = self.out["echo"]["result"]["checks"].set_index("id")
        self.assertIn("E2", checks.index)
        self.assertIn("E2p", checks.index)
        self.assertNotIn("E2b", checks.index)

    def test_echo_cuts_by_lane(self) -> None:
        table = self.out["echo"]["result"]["per_lane"]
        self.assertFalse(table.empty, "no per-lane table")
        self.assertIn("side", table.columns)
        self.assertIn("finger", table.columns)

    def test_the_verdict_words_are_the_four_we_allow(self) -> None:
        # "dropped" joined the four in September: a check the shipped
        # battery cannot produce (E2 needs echo's ladder rule) says so
        # instead of printing "no data" at a reader who then goes
        # looking for a file that was never going to exist.
        allowed = {"pass", "fail", "reported", "not testable", "dropped"}
        for mode in MODES:
            checks = self.out[mode]["result"].get("checks")
            if checks is None or checks.empty:
                continue
            with self.subTest(mode=mode):
                self.assertTrue(set(checks["verdict"]) <= allowed,
                                set(checks["verdict"]))


if __name__ == "__main__":
    unittest.main()
