"""Universal soft-press thresholds and the Settings live readout.

Thresholds are set from the sensor noise floor rather than from how
hard a healthy person presses, so a weak or slow finger still registers
without any per-participant calibration. Two failure modes are guarded
here:

  1. A threshold scaled to a firm press excludes the weak hands the
     study is about.
  2. A fast baseline tracker chases a slowly-building press upward so
     the signal never crosses the threshold at all, which no amount of
     threshold lowering fixes.
"""
from __future__ import annotations

import os
import random
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

NOISE_SD = 1.1          # measured on the real device, 29 July 2026


def _cal():
    from rehab.config import Config
    from rehab.hardware.fsr_detector import Calibration
    c = Config.load()
    return Calibration(
        num_sensors=4,
        baseline_alpha=float(c.get("fsr.baseline_alpha")),
        value_alpha=float(c.get("fsr.value_alpha")),
        on_delta=list(c.get("fsr.on_delta")),
        off_delta=list(c.get("fsr.off_delta")),
        abs_on_min=list(c.get("fsr.abs_on_min")),
        abs_off_max=list(c.get("fsr.abs_off_max")),
        debounce_ms=int(c.get("fsr.debounce_ms")),
    )


def _press(rise: float, secs: float, base: float = 250.0, seed: int = 3,
            lane: int = 0):
    """Ramp a press on `lane` and return (pressed, released)."""
    from rehab.hardware.fsr_detector import FSRDetector
    det = FSRDetector(_cal(), hand="right")
    p, r = [], []
    det.on_press = lambda ev: p.append(1)
    det.on_release = lambda ev: r.append(1)
    rng = random.Random(seed)
    t, k = 100.0, 0

    def feed(v0):
        nonlocal k
        vals = [int(base + rng.gauss(0, NOISE_SD)) for _ in range(4)]
        vals[lane] = int(v0 + rng.gauss(0, NOISE_SD))
        det.feed(t + k * 0.005, tuple(vals))
        k += 1

    for _ in range(800):
        feed(base)
    n = max(1, int(secs / 0.005))
    for j in range(n):
        feed(base + rise * (j + 1) / n)
    for _ in range(160):
        feed(base + rise)
    for j in range(n):
        feed(base + rise * (1 - (j + 1) / n))
    for _ in range(300):
        feed(base)
    return bool(p), bool(r)


# Measured on the device with a hand present, 29 July 2026, in counts
# above the empty-device reading. The gentle press is what a relaxed
# adult produced when asked for the softest thing still worth calling a
# press. See tools/calibrate_rest_vs_press.py.
RESTING = (2.5, 8.9, 11.5, 30.7)
GENTLE = (51.5, 40.9, 41.5, 145.7)


class SoftPressDetectionTests(unittest.TestCase):
    """A gentle press must register on every finger, and it must still
    register when made slowly (the case a fast baseline tracker
    silently swallows)."""

    def test_gentle_press_detected_on_every_finger(self) -> None:
        for lane in range(4):
            with self.subTest(finger=lane):
                p, r = _press(GENTLE[lane], 0.30, lane=lane)
                self.assertTrue(p, "gentle press not detected")
                self.assertTrue(r, "release not detected")

    def test_gentle_press_detected_when_made_slowly(self) -> None:
        for lane in range(4):
            with self.subTest(finger=lane):
                p, _ = _press(GENTLE[lane], 1.50, lane=lane)
                self.assertTrue(p, "slow gentle press not detected")

    def test_firm_press_detected(self) -> None:
        self.assertEqual(_press(94, 0.15), (True, True))

    def test_press_just_over_threshold_detected(self) -> None:
        # Weakest press the configured threshold admits, with a small
        # margin. Anything at or above this must register.
        from rehab.config import Config
        deltas = Config.load().get("fsr.on_delta")
        for lane in range(4):
            with self.subTest(finger=lane):
                p, _ = _press(deltas[lane] + 6, 0.40, lane=lane)
                self.assertTrue(p)


class RestingHandTests(unittest.TestCase):
    """A hand resting on the pads must never register as a press. This
    is the failure an empty-device calibration cannot see: the pinky
    pad carries about 30 counts at rest, which sat above the earlier
    uniform threshold and fired phantom presses continuously."""

    def test_resting_hand_never_triggers(self) -> None:
        from rehab.config import Config
        from rehab.hardware.fsr_detector import FSRDetector
        det = FSRDetector(_cal(), hand="right")
        fired: list[int] = []
        det.on_press = lambda ev: fired.append(ev.lane)
        rng = random.Random(19)
        base, t = 250.0, 100.0
        # Hand lands on the device and stays there for 60 s.
        for k in range(int(60 / 0.005)):
            vals = tuple(int(base + RESTING[i] + rng.gauss(0, NOISE_SD))
                          for i in range(4))
            det.feed(t + k * 0.005, vals)
        self.assertEqual(fired, [], f"resting hand fired presses: {fired}")

    def test_every_threshold_clears_its_resting_load(self) -> None:
        from rehab.config import Config
        deltas = Config.load().get("fsr.on_delta")
        for i, d in enumerate(deltas):
            self.assertGreater(
                d, RESTING[i],
                f"finger {i} trigger +{d} is below its resting load "
                f"+{RESTING[i]}, a resting hand would false-trigger")

    def test_every_threshold_is_reachable_by_a_gentle_press(self) -> None:
        from rehab.config import Config
        deltas = Config.load().get("fsr.on_delta")
        for i, d in enumerate(deltas):
            self.assertLess(
                d, GENTLE[i],
                f"finger {i} trigger +{d} exceeds a gentle press "
                f"+{GENTLE[i]}, a weak finger could never reach it")


class NoFalsePressTests(unittest.TestCase):
    """Sensitivity must not come at the cost of phantom presses."""

    def _false_presses(self, minutes: float, drift_per_min: float,
                        noise_sd: float) -> int:
        from rehab.hardware.fsr_detector import FSRDetector
        det = FSRDetector(_cal(), hand="right")
        fired: list[int] = []
        det.on_press = lambda ev: fired.append(1)
        rng = random.Random(11)
        base, t = 250.0, 100.0
        for k in range(int(minutes * 60 / 0.005)):
            drift = drift_per_min * (k * 0.005 / 60.0)
            det.feed(t + k * 0.005, tuple(
                int(base + drift + rng.gauss(0, noise_sd))
                for _ in range(4)))
        return len(fired)

    def test_no_false_press_at_measured_noise(self) -> None:
        self.assertEqual(self._false_presses(3, 0, NOISE_SD), 0)

    def test_no_false_press_with_drift(self) -> None:
        self.assertEqual(self._false_presses(3, 20, NOISE_SD), 0)

    def test_no_false_press_at_triple_noise(self) -> None:
        self.assertEqual(self._false_presses(3, 0, NOISE_SD * 3), 0)


class BaselineTrackerTests(unittest.TestCase):
    def test_baseline_slow_enough_not_to_chase_a_press(self) -> None:
        # At 200 Hz the EMA time constant is 1/(alpha*200) seconds. It
        # must be far longer than a press takes to build, or slow
        # presses vanish into the baseline.
        from rehab.config import Config
        alpha = float(Config.load().get("fsr.baseline_alpha"))
        tau = 1.0 / (alpha * 200.0)
        self.assertGreater(tau, 5.0, f"baseline tau {tau:.2f}s too fast")

    def test_release_threshold_below_press_threshold(self) -> None:
        # Thresholds are per-finger now, set from each sensor's own
        # measured resting load and press range rather than shared.
        # Hysteresis must still hold on every finger.
        from rehab.config import Config
        c = Config.load()
        for on_d, off_d in zip(c.get("fsr.on_delta"),
                                c.get("fsr.off_delta")):
            self.assertLess(off_d, on_d)

    def test_absolute_floor_never_blocks_a_real_baseline(self) -> None:
        # Real resting values are 235-260. The floor is a broken-sensor
        # guard and must sit below them, or it silently governs instead
        # of the delta and no press registers.
        from rehab.config import Config
        c = Config.load()
        for floor in c.get("fsr.abs_on_min"):
            self.assertLess(floor, 235)


class SettingsLiveFeedbackTests(unittest.TestCase):
    """The Settings screen must show live press feedback. The engine
    pump drains the sample queue, so the screen cannot call get_sample
    itself: it reads detector state instead."""

    def test_pump_feeds_the_diagnostics_screen(self) -> None:
        import inspect
        from rehab.game.engine import GameEngine
        src = inspect.getsource(GameEngine._pump_source)
        self.assertIn("diagnostics", src)

    def test_settings_update_does_not_consume_samples(self) -> None:
        # Calling get_sample() here would race the pump and starve the
        # detectors of data. Comments are stripped first so the note
        # explaining this rule doesn't trip the check itself.
        import inspect
        from rehab.ui.screens import DiagnosticsScreen
        src = inspect.getsource(DiagnosticsScreen.update)
        code = "\n".join(
            line.split("#", 1)[0] for line in src.splitlines())
        self.assertNotIn("get_sample", code)

    def test_tile_lights_when_detector_reports_press(self) -> None:
        import pygame
        pygame.init()
        pygame.font.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.ui.screens import DiagnosticsScreen
        from rehab.ui.theme import get as get_theme
        from rehab.ui.widgets import Layout

        e = GameEngine.__new__(GameEngine)
        e.cfg = Config.load()
        e.layout = Layout(1280, 800, 1.0)
        e.theme = get_theme("clinical")
        e.hand_mode = "right"
        e.audio = None
        e.detectors = {}
        src = MagicMock()
        src.provides_samples = True
        src.name = "MultiSerial"
        src.is_connected = True
        src.has_recent_data = lambda t=1.5: True
        e.source = src
        e._build_detectors()
        e._ensure_both_detectors()
        screen = DiagnosticsScreen(e)

        det = e.detectors["right"]
        rng = random.Random(5)
        base, t = 250.0, 100.0
        for k in range(400):                       # settle
            det.feed(t + k * 0.005,
                      tuple(int(base + rng.gauss(0, NOISE_SD))
                            for _ in range(4)))
        screen.update(0.016)
        right = sorted([l for l in screen.lanes if l.hand == "right"],
                        key=lambda l: l.finger)
        self.assertFalse(any(l.active for l in right), "lit while idle")

        for k in range(400, 560):                  # press the ring finger
            vals = [int(base + rng.gauss(0, NOISE_SD)) for _ in range(4)]
            vals[2] = int(base + 40)
            det.feed(t + k * 0.005, tuple(vals))
        screen.update(0.016)
        right = sorted([l for l in screen.lanes if l.hand == "right"],
                        key=lambda l: l.finger)
        self.assertTrue(right[2].active, "pressed finger did not light")
        self.assertFalse(right[0].active or right[1].active
                          or right[3].active, "wrong finger lit")


if __name__ == "__main__":
    unittest.main()
