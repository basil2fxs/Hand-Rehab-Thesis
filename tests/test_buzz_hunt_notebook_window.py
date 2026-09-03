"""The Buzz Hunt notebook chapter on a 2026-09 block, driven end to
end on a real session: localisation at the fixed 150 ms pulse with
the response-window ladder, played through the real engine on a
sample-providing fake rig (real detectors, real taps) and handed to
the real notebook functions.

What this pins is the changed threshold semantics: the chapter reads
the ladder (accuracy and RT by level, the top level per hand) from
the level= and window_ms= stamps on the rows, says plainly that no
duration psychometric function exists for a fixed-pulse block, does
not invent a threshold from the absent staircase, and the cohort
emitter reports window_top_level and the median RT instead of
threshold_final_ms. Same path test_echo_notebook_span.py walks for
Echo.
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

from tests.test_echo_mode import (RESTING, _Pump, _WireRig, patched_clock,
                                  setUpModule, tearDownModule)

__all__ = ["setUpModule", "tearDownModule"]

LOC_TRIALS = 12


def _load_ra():
    """Exec every notebook cell's definitions into one standalone
    module namespace (the test_echo_notebook_span pattern)."""
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_buzz_hunt_window"
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


def _make_engine(data_dir: str, clock):
    """The real engine on a _WireRig, configured for a localisation
    only block short enough to drive: twelve trials, no catch, no
    other stage, the shipped pulse and ladder, quick waits."""
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.calibration_profile import CalibrationProfile
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data.setdefault("session", {})["data_dir"] = data_dir
    cfg.data["session"]["participant"] = "BuzzWindow"
    cfg.data.setdefault("report", {})["enabled"] = False
    cfg.data.setdefault("audio", {})["enabled"] = False
    cfg.data["eeg"] = {"enabled": False}
    cfg.data.setdefault("quick_cal", {})["enabled"] = False
    cfg.data.setdefault("serial", {})["watch_ports"] = False
    cfg.data["game"]["test_mode_enabled"] = False
    cfg.data["buzz_hunt"].update({
        "loc_trials_per_hand": LOC_TRIALS, "catch_rate": 0.0,
        "distractor_trials_per_hand": 0, "span_trials": 0,
        "gap_trials_per_hand": 0, "wait_lo_s": 0.3, "wait_hi_s": 0.4,
        "announce_s": 0.5, "rest_s": 0.5, "stage_intro_s": 0.5,
        "seed": 5,
    })
    rig = _WireRig(clock)
    eng = GameEngine(cfg, rig)
    eng._screens = eng._build_screens()
    eng.show_results = lambda: None
    eng.begin_session("BuzzWindow", "30", dominant_hand="right", visit="1")
    prof = CalibrationProfile(hand="right", participant="BuzzWindow",
                              resting=[RESTING] * 4,
                              press=[RESTING + 60] * 4)
    prof.set_max_press([RESTING + 300] * 4)
    prof.session_token = str(getattr(eng, "_session_token", ""))
    eng.apply_calibration(prof)
    eng._uncal_ack = {"left", "right"}
    return eng, rig


def _write_session(td: str, clock):
    """One real block: every localisation trial answered correctly
    on the pads, so the ladder promotes after the sixth trial and
    the last six rows run at level 1."""
    eng, rig = _make_engine(td, clock)
    pump = _Pump(eng, rig, clock)
    pump.until(lambda: eng.detectors.get("right") is not None
               and eng.detectors["right"].baseline[0] is not None, 300)
    eng.begin_buzz_hunt_block()
    mode = eng.mode
    answered: set[int] = set()
    for _ in range(60000):
        if eng.trial_logger is None:
            break
        pump.frame()
        if (mode.phase == "trial" and mode.sub == "respond"
                and mode.trial_counter not in answered):
            answered.add(mode.trial_counter)
            pump.tap(int(mode.lane), 0.10)
    assert eng.trial_logger is None, "the block never ended"
    return eng, mode


class BuzzHuntNotebookWindowTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory()
        with patched_clock() as clock:
            cls.eng, cls.mode = _write_session(cls._td.name, clock)
        cls.stats = cls.mode.block_stats()
        cls.ra = _load_ra()
        cat = cls.ra.build_catalogue(root=cls._td.name)
        cls.folders = [Path(p) for p in cat["folder"]]
        cls.trials = cls.ra.load_games(cls.folders, cat)
        cls.metas = cls.ra.load_metas(cls.folders)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cls.result = cls.ra.sec_tactile(cls.folders, cls.trials,
                                            cls.metas)
        cls.out = buf.getvalue()

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def test_the_block_itself_climbed_at_the_fixed_pulse(self) -> None:
        # The engine-side truth the chapter must reproduce.
        self.assertEqual(self.stats["pulse_ms"], 150.0)
        self.assertEqual(self.stats["threshold"], {})
        right = self.stats["window"]["per_hand"]["right"]
        self.assertEqual(right["trace"], [0] * 6 + [1] * 6)
        # The twelfth correct answer earned level 2, but nothing was
        # played there: top_level is the highest level PLAYED (what
        # the rows carry), final_level where the ladder stands.
        self.assertEqual(right["top_level"], 1)
        self.assertEqual(right["final_level"], 2)
        self.assertEqual(self.stats["loc"]["accuracy"], 1.0)

    def test_the_chapter_reads_the_ladder_from_the_rows(self) -> None:
        self.assertIsNotNone(self.result)
        self.assertIn("RESPONSE-WINDOW LADDER", self.out)
        self.assertIn("fixed pulse of 150 ms", self.out)
        rows = self.result["rows"]
        levels = sorted({int(float(kv["level"])) for kv in rows["kv"]
                         if "level" in kv})
        self.assertEqual(levels, [0, 1])
        windows = sorted({float(kv["window_ms"]) for kv in rows["kv"]
                          if "window_ms" in kv})
        self.assertEqual(windows, [2000.0, 3000.0])

    def test_no_threshold_is_invented_for_a_fixed_pulse_block(
            self) -> None:
        self.assertEqual(self.result["thresholds"], [])
        self.assertIn("localisation ran at a fixed pulse", self.out)
        self.assertIn("No duration", self.out)
        self.assertNotIn("logistic psychometric fits", self.out)
        self.assertIn("expected for a 2026-09 block", self.out)

    def test_stored_summary_cross_check_carries_the_window(self) -> None:
        # The chapter prints the on-device cross-check, and what the
        # block stored in metadata.json is the ladder, not a
        # threshold (the printed frame elides wide columns, so the
        # stored dict is read back through the notebook's own reader).
        self.assertIn("block_summary.buzz_hunt", self.out)
        stored = self.ra.stored_mode_stats(self.metas, "buzz_hunt")
        self.assertEqual(len(stored), 1)
        d = next(iter(stored.values()))
        self.assertEqual(d["pulse_ms"], 150.0)
        self.assertEqual(d["threshold"], {})
        self.assertTrue(d["window"]["active"])
        self.assertEqual(d["window"]["per_hand"]["right"]["top_level"], 1)
        self.assertEqual(d["window"]["per_hand"]["right"]["final_level"], 2)
        self.assertEqual(d["loc"]["per_hand"]["right"]["by_level"]["1"]["n"],
                         6)

    def test_cohort_emits_the_window_level_not_a_threshold(self) -> None:
        game = next(iter(self.metas))
        meta = self.metas[game]
        block = {"game": game, "folder": self.folders[0], "meta": meta,
                 "bs": meta.get("block_summary", {}) or {},
                 "rows": self.trials[self.trials["game"] == game],
                 "hand": str(meta.get("hand", "?")),
                 "calset": None, "extra": {}}
        out = self.ra._cohort_buzz_hunt(block)
        metrics = {(h, m): (v, n) for h, m, v, n in out}
        self.assertEqual(metrics[("right", "window_top_level")],
                         (1.0, LOC_TRIALS))
        self.assertIn(("right", "loc_median_rt_ms"), metrics)
        self.assertEqual(metrics[("right", "loc_accuracy")][0], 1.0)
        self.assertFalse(any(m in ("threshold_final_ms", "at_floor")
                             for _h, m in metrics))
        self.assertIn(("buzz_hunt", "window_top_level"),
                      self.ra.COHORT_METRICS)


if __name__ == "__main__":
    unittest.main()
