"""Where the calibration store lives, and why a headless run moves it.

Force Pilot probes the maximum press at the top of a block and saves
the profile back through GameEngine.record_max_press. The store is
config/calibration, which is tracked, so every headless timing or
simulation run started from a checkout used to rewrite
config/calibration/current_<hand>.json and leave a diff behind for
somebody to commit by accident.

session.calibration_dir moves the whole store, reads and writes
together. What is pinned here:

  - the default is still config/calibration, so a clinic restart finds
    the profile it measured;
  - an override moves the write AND the read, so a run that saves a
    profile is the run that picks it back up;
  - a REAL Force Pilot probe on a real Config with the override set
    writes into the override and leaves every byte under the
    checkout's config/calibration alone;
  - both headless scripts set the override in build_engine.
"""
from __future__ import annotations

import hashlib
import os
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_force_pilot import _engine, _mode  # noqa: E402

STORE = ROOT / "config" / "calibration"


def _real_cfg(calibration_dir=None):
    from finger_rehab.config import Config
    cfg = Config.load()
    cfg.data.setdefault("session", {})["calibration_dir"] = (
        str(calibration_dir) if calibration_dir else None)
    return cfg


def _store_fingerprint() -> dict:
    """Name, size and content hash of every file in the checkout's
    calibration store, so a test can prove nothing under it moved."""
    out = {}
    if not STORE.exists():
        return out
    for p in sorted(STORE.rglob("*")):
        if p.is_file():
            data = p.read_bytes()
            out[str(p.relative_to(STORE))] = (len(data),
                                              hashlib.sha256(data)
                                              .hexdigest())
    return out


def _profile(hand="right"):
    from finger_rehab.hardware.calibration_profile import CalibrationProfile
    # A profile the engine's own usable() gate accepts: a real empty
    # capture, a real resting load and enough travel to set a
    # threshold on.
    return CalibrationProfile(hand=hand, participant="T",
                              empty=[20.0] * 4, empty_noise=[2.0] * 4,
                              resting=[25.0] * 4, press=[300.0] * 4)


class PathTests(unittest.TestCase):
    def test_the_default_store_is_the_config_folder(self) -> None:
        cfg = _real_cfg()
        p = cfg.calibration_path("current_right.json")
        self.assertEqual(p.parent.name, "calibration")
        self.assertEqual(p.parent.parent.name, "config")
        self.assertEqual(p.name, "current_right.json")

    def test_an_override_moves_the_whole_store(self) -> None:
        with TemporaryDirectory() as td:
            cfg = _real_cfg(td)
            cur = cfg.calibration_path("current_left.json")
            hist = cfg.calibration_path("history/20260905T101010.json")
            self.assertEqual(cur, Path(td).resolve() / "current_left.json")
            self.assertEqual(hist.parent,
                             Path(td).resolve() / "history")

    def test_an_absolute_name_is_left_alone(self) -> None:
        with TemporaryDirectory() as td:
            target = Path(td) / "elsewhere.json"
            self.assertEqual(_real_cfg(td).calibration_path(target),
                             target)

    def test_an_empty_override_reads_as_no_override(self) -> None:
        # A blank string in a yaml is a typo, not a directory named "".
        cfg = _real_cfg("   ")
        self.assertEqual(cfg.calibration_path("current_right.json").parent
                         .name, "calibration")


class EngineRoundTripTests(unittest.TestCase):
    """The write and the read move together, through the real engine."""

    def test_a_max_press_saved_under_the_override_is_read_back(self) -> None:
        from finger_rehab.hardware.calibration_profile import (
            CalibrationProfile)
        with TemporaryDirectory() as td:
            before = _store_fingerprint()
            e = _engine()
            e.cfg = _real_cfg(td)
            e.calibration_profiles["right"] = _profile()
            e.record_max_press("right", [210.0, 190.0, 160.0, 130.0])
            saved = Path(td) / "current_right.json"
            self.assertTrue(saved.exists(),
                            "the override directory got no profile")
            back = CalibrationProfile.load(saved)
            self.assertEqual(back.max_press,
                             [210.0, 190.0, 160.0, 130.0])
            # The engine's own reader finds the same file, so a run
            # that saves is the run that picks it up again.
            self.assertIsNotNone(e._usable_saved_profile("right"))
            self.assertEqual(_store_fingerprint(), before,
                             "the checkout's calibration store changed")


class ProbeTests(unittest.TestCase):
    """The real Force Pilot probe gate, on a real Config."""

    def _press(self, m, t, peak=400.0):
        for frac, dt in ((0.4, 0.05), (1.0, 0.05)):
            m.view.counts = peak * frac
            t += dt
            m._tick(t)
        for _ in range(8):
            t += 0.05
            m._tick(t)
        m.view.counts = 0.0
        for _ in range(12):
            t += 0.05
            m._tick(t)
        return t

    def test_a_probe_writes_to_the_override_not_the_checkout(self) -> None:
        with TemporaryDirectory() as td:
            before = _store_fingerprint()
            e = _engine()
            e.cfg = _real_cfg(td)
            m = _mode(e)
            t = 0.0
            m._tick(t)
            self.assertEqual(m.phase, "probe_gap")
            for _ in range(4):
                t += 1.3
                m._tick(t)
                self.assertEqual(m.phase, "probe")
                for peak in (390.0, 400.0, 410.0):
                    t = self._press(m, t, peak)
            saved = Path(td) / "current_right.json"
            self.assertTrue(saved.exists(),
                            "the probe saved no profile at all")
            self.assertEqual(e.calibration_profiles["right"].max_press,
                             [400.0] * 4)
            self.assertEqual(_store_fingerprint(), before,
                             "a Force Pilot probe rewrote the tracked "
                             "calibration store")


class HeadlessScriptTests(unittest.TestCase):
    """Both scripts that play real blocks without a screen move the
    store off the checkout before the first block opens."""

    def _load(self, name):
        import importlib.util
        path = ROOT / "scripts" / f"{name}.py"
        spec = importlib.util.spec_from_file_location(
            f"_script_{name}", path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_measure_battery_moves_the_store(self) -> None:
        mb = self._load("measure_battery")
        with TemporaryDirectory() as td:
            before = _store_fingerprint()
            data_dir = Path(td) / "sessions"
            eng = mb.build_engine("P01", "right", data_dir, mb.FakeRig())
            try:
                got = eng.cfg.calibration_path("current_right.json")
                self.assertTrue(str(got).startswith(str(Path(td).resolve())),
                                f"{got} is not under the temp tree")
                self.assertEqual(_store_fingerprint(), before)
            finally:
                eng.end_session()

    def test_simulate_cohort_moves_the_store(self) -> None:
        sc = self._load("simulate_cohort")
        with TemporaryDirectory() as td:
            before = _store_fingerprint()
            truth = sc.make_truth(1, 0)["P01"]
            data_dir = Path(td) / "sessions"
            eng = sc.build_engine("P01", truth, data_dir, sc.mb.FakeRig())
            try:
                got = eng.cfg.calibration_path("current_left.json")
                self.assertTrue(str(got).startswith(str(Path(td).resolve())),
                                f"{got} is not under the temp tree")
                self.assertEqual(_store_fingerprint(), before)
            finally:
                eng.end_session()


if __name__ == "__main__":
    unittest.main()
