"""Newtons from the SingleTact CS8-10N calibration.

What is pinned here:

  - the shipped constant is rating / full scale (10 / 512), so the
    three fsr keys cannot drift apart
  - a real engine on the shipped config reports force_unit "N" and
    scales a known press on a real detector by the constant: peak
    and impulse both, through the same accessors log_trial uses
  - a completed block's metadata carries the unit and the three keys
    in its config snapshot
  - a config without the key (every session recorded before
    September 2026) still reports counts, unscaled
  - the notebook converts on a session's own snapshot when it has
    one and on the 10 N fallback when it does not
  - scripts/force_check.py's fit and acceptance on synthetic data: a
    true 10 N part passes, a 45 N part is a part mismatch, a pad with
    6 percent hysteresis fails and is named
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

N_PER_COUNT = 10.0 / 512.0
RESTING = 100
PRESSED = 300


def _detector():
    """A detector on the shipped thresholds, resting at RESTING and
    then pressed to PRESSED on lane 0: the smoothed value converges
    well inside the sample counts used, so the running peak is
    PRESSED - RESTING above the frozen rising-edge baseline."""
    from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector
    det = FSRDetector(Calibration(num_sensors=4, baseline_alpha=0.0005,
                                  value_alpha=0.35,
                                  on_delta=[20, 13, 15, 46],
                                  off_delta=[10, 3, 5, 23],
                                  abs_on_min=[0, 0, 0, 0],
                                  abs_off_max=[1000] * 4,
                                  debounce_ms=100),
                      hand="right")
    t = 100.0
    for _ in range(400):
        det.feed(t, (RESTING,) * 4)
        t += 0.005
    for _ in range(200):
        det.feed(t, (PRESSED, RESTING, RESTING, RESTING))
        t += 0.005
    assert det.pressed[0]
    return det


class _Rig:
    """A board that never delivers a sample: the detector under test
    is fed by hand, and a plain object (not a mock) keeps the metadata
    snapshot serialisable."""
    provides_samples = True
    is_connected = True
    name = "fake-board"
    hand_modes_available = {"right", "left", "both"}

    def start(self) -> None: ...
    def stop(self) -> None: ...

    def get_sample(self, timeout: float = 0.0):
        return None

    def send_command(self, cmd: str) -> bool:
        return True


def _engine(cfg):
    from finger_rehab.game.engine import GameEngine
    src = _Rig()
    cfg.data["audio"]["enabled"] = False
    cfg.data["report"] = {"enabled": False}
    eng = GameEngine(cfg, src)
    eng._screens = eng._build_screens()
    return eng


class ConstantTests(unittest.TestCase):
    def test_shipped_constant_is_rating_over_full_scale(self) -> None:
        from finger_rehab.config import Config
        cfg = Config.load()
        n = float(cfg.get("fsr.force_calibration_n_per_count"))
        rating = float(cfg.get("fsr.sensor_rating_n"))
        full = float(cfg.get("fsr.counts_full_scale"))
        self.assertEqual(rating, 10.0)
        self.assertEqual(full, 512.0)
        self.assertAlmostEqual(n, rating / full, delta=1e-6)
        self.assertAlmostEqual(1.0 / n, 51.2, delta=0.01)


class EngineRoundTripTests(unittest.TestCase):
    def test_shipped_config_scales_a_known_press_to_newtons(self) -> None:
        from finger_rehab.config import Config
        cfg = Config.load()
        eng = _engine(cfg)
        eng.set_hand_mode("right")
        det = _detector()
        eng.detectors = {"right": det}
        self.assertEqual(eng._force_unit(), "N")
        _raw, above = det.current_peak(0)
        # The baseline EMA creeps a few hundredths of a count up the
        # rise before the on threshold trips and freezes it.
        self.assertAlmostEqual(above, PRESSED - RESTING, delta=0.1)
        n = float(cfg.get("fsr.force_calibration_n_per_count"))
        self.assertAlmostEqual(eng._peak_force_for_lane(0), above * n,
                               places=9)
        self.assertAlmostEqual(eng._peak_force_for_lane(0),
                               200 * N_PER_COUNT, delta=0.01)
        _raw_imp, imp_above = det.current_impulse(0)
        self.assertGreater(imp_above, 0.0)
        self.assertAlmostEqual(eng._impulse_for_lane(0), imp_above * n,
                               places=9)
        # A lane that is not pressed reports nothing, in either unit.
        self.assertIsNone(eng._peak_force_for_lane(1))

    def test_without_the_key_the_same_press_reads_counts(self) -> None:
        from finger_rehab.config import Config
        cfg = Config.load()
        cfg.data["fsr"].pop("force_calibration_n_per_count")
        eng = _engine(cfg)
        eng.set_hand_mode("right")
        det = _detector()
        eng.detectors = {"right": det}
        self.assertEqual(eng._force_unit(), "counts")
        _raw, above = det.current_peak(0)
        self.assertAlmostEqual(eng._peak_force_for_lane(0), above, places=9)
        _raw_imp, imp_above = det.current_impulse(0)
        self.assertAlmostEqual(eng._impulse_for_lane(0), imp_above, places=9)

    def test_a_completed_block_records_the_unit_and_the_keys(self) -> None:
        from finger_rehab.config import Config
        with tempfile.TemporaryDirectory() as td:
            cfg = Config.load()
            cfg.data["session"]["data_dir"] = td
            eng = _engine(cfg)
            eng.begin_session("Newton Test", "30")
            eng._uncal_ack = {"left", "right"}
            eng.set_hand_mode("right")
            eng.begin_reaction_block()
            folder = Path(eng.session_paths.root)
            eng.finish_block()
            meta = json.loads((folder / "metadata.json").read_text(
                encoding="utf-8"))
            self.assertEqual(meta["block_summary"]["force_unit"], "N")
            snap = meta["config_snapshot"]["fsr"]
            self.assertAlmostEqual(snap["force_calibration_n_per_count"],
                                   N_PER_COUNT, delta=1e-6)
            self.assertEqual(snap["sensor_rating_n"], 10.0)
            self.assertEqual(snap["counts_full_scale"], 512)
            eng.end_session()


def _load_notebook():
    """The notebook's definitions as a namespace, the pattern
    tests/test_echo_notebook_span.py uses."""
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_force_units"
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


class NotebookUnitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        import matplotlib
        matplotlib.use("Agg")
        cls.ra = _load_notebook()

    def test_fallback_constant_is_the_10n_part(self) -> None:
        self.assertEqual(self.ra.SENSOR_RATING_N, 10.0)
        self.assertEqual(self.ra.COUNTS_FULL_SCALE, 512.0)
        self.assertAlmostEqual(self.ra.N_PER_COUNT, N_PER_COUNT, delta=1e-9)
        self.assertAlmostEqual(self.ra.counts_to_newtons(51.2), 1.0,
                               delta=1e-6)

    def test_old_session_without_the_key_converts_as_counts(self) -> None:
        old = {"block_summary": {"force_unit": "counts"},
               "config_snapshot": {"fsr": {"on_delta": [20, 13, 15, 46]}}}
        self.assertIsNone(self.ra.snapshot_n_per_count(old))
        cs = self.ra.calibration_factors({"2026-08-12/old_reaction": old})
        self.assertEqual(cs.counts_per_unit["2026-08-12/old_reaction"], 1.0)
        self.assertAlmostEqual(
            cs.newtons_per_unit["2026-08-12/old_reaction"], N_PER_COUNT,
            delta=1e-9)
        # A logged 200-count peak is 3.9 N on the 10 N fallback, not
        # the 17.6 N the old 45 N assumption gave.
        self.assertAlmostEqual(cs.newtons(200.0, "2026-08-12/old_reaction"),
                               3.906, delta=0.01)

    def test_new_session_converts_on_its_own_snapshot(self) -> None:
        new = {"block_summary": {"force_unit": "N"},
               "config_snapshot": {"fsr": {
                   "force_calibration_n_per_count": 0.019531,
                   "sensor_rating_n": 10.0, "counts_full_scale": 512}}}
        self.assertAlmostEqual(self.ra.snapshot_n_per_count(new), 0.019531,
                               delta=1e-9)
        cs = self.ra.calibration_factors({"2026-09-03/new_reaction": new})
        self.assertAlmostEqual(cs.counts_per_unit["2026-09-03/new_reaction"],
                               1.0 / 0.019531, delta=1e-6)
        self.assertEqual(cs.newtons_per_unit["2026-09-03/new_reaction"], 1.0)
        # A rig whose snapshot names another part converts on that
        # part, not on the module fallback.
        other = {"block_summary": {"force_unit": "counts"},
                 "config_snapshot": {"fsr": {"sensor_rating_n": 45.0,
                                             "counts_full_scale": 512}}}
        self.assertAlmostEqual(self.ra.snapshot_n_per_count(other),
                               45.0 / 512.0, delta=1e-9)


def _force_check():
    spec = importlib.util.spec_from_file_location(
        "force_check", ROOT / "scripts" / "force_check.py")
    mod = importlib.util.module_from_spec(spec)
    # The script's dataclasses carry string annotations (from
    # __future__), which dataclasses resolves through sys.modules, so
    # the module has to be registered before it runs.
    sys.modules["force_check"] = mod
    spec.loader.exec_module(mod)
    return mod


class ForceCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.fc = _force_check()

    def _pad(self, counts_per_n: float, hysteresis_counts: float = 0.0,
             drift: float = 0.0):
        fc = self.fc
        pad = fc.PadResult(finger="index", tare_counts=250.0)
        masses = list(fc.DEFAULT_MASSES_G)
        for m in masses:
            pad.points.append(fc.Point(
                mass_g=m, direction="up",
                mean_counts=fc.newtons(m) * counts_per_n, sd_counts=1.0,
                return_counts=0.5))
        for m in reversed(masses):
            pad.points.append(fc.Point(
                mass_g=m, direction="down",
                mean_counts=fc.newtons(m) * counts_per_n + hysteresis_counts,
                sd_counts=1.0, return_counts=-0.5))
        pad.drift_counts = drift
        return fc.assess(pad)

    def test_expected_counts_match_the_research_table(self) -> None:
        fc = self.fc
        self.assertAlmostEqual(fc.expected_counts(100), 50.2, delta=0.1)
        self.assertAlmostEqual(fc.expected_counts(500), 251.1, delta=0.1)
        self.assertAlmostEqual(fc.expected_counts(1000), 502.3, delta=0.1)
        rows = {r["mass_g"]: r for r in fc.expectation_table([500, 1000])}
        self.assertAlmostEqual(rows[500.0]["counts_45N"], 55.8, delta=0.1)
        self.assertAlmostEqual(rows[1000.0]["counts_45N"], 111.6, delta=0.1)

    def test_a_true_10n_part_passes(self) -> None:
        pad = self._pad(51.2)
        self.assertEqual(pad.verdict, "PASS", pad.failures)
        self.assertAlmostEqual(pad.slope_counts_per_n, 51.2, delta=1e-6)
        self.assertAlmostEqual(pad.implied_rating_n, 10.0, delta=1e-6)
        self.assertAlmostEqual(self.fc.n_per_count_from([pad]), N_PER_COUNT,
                               delta=1e-9)

    def test_a_45n_part_is_a_mismatch_not_a_failure(self) -> None:
        pad = self._pad(512.0 / 45.0)
        self.assertEqual(pad.verdict, "PART MISMATCH")
        self.assertTrue(any("45 N part" in f for f in pad.failures),
                        pad.failures)
        self.assertIsNone(self.fc.n_per_count_from([pad]))

    def test_six_percent_hysteresis_fails_and_names_the_pad(self) -> None:
        pad = self._pad(51.2, hysteresis_counts=0.06 * 512.0)
        self.assertEqual(pad.verdict, "FAIL")
        self.assertTrue(any(f.startswith("index:") and "ascending against "
                            "descending" in f for f in pad.failures),
                        pad.failures)

    def test_drift_and_slope_limits_bind(self) -> None:
        drifted = self._pad(51.2, drift=15.0)
        self.assertEqual(drifted.verdict, "FAIL")
        self.assertTrue(any("drifted" in f for f in drifted.failures))
        # 3 percent off the nominal slope is past the 2 percent
        # linearity band and every point is inside the 20-count band
        # only at the light masses, so the slope line has to bind.
        off = self._pad(51.2 * 1.03)
        self.assertEqual(off.verdict, "FAIL")
        self.assertTrue(any("slope" in f for f in off.failures))

    def test_write_slope_refuses_the_user_settings_file(self) -> None:
        with self.assertRaises(SystemExit):
            self.fc.write_slope(N_PER_COUNT,
                                ROOT / "config" / "user_settings.yaml")


if __name__ == "__main__":
    unittest.main()
