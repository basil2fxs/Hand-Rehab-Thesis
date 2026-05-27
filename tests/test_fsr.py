"""Tests for the FSR press detector. Covers the algorithm edge cases:
short sample tuples, callback failures, debounce, hysteresis, baseline
behaviour during a press, and calibration padding."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _settle_baseline(det, baseline_val: int = 50,
                      n_samples: int = 40, dt: float = 0.005,
                      t0: float = 100.0) -> float:
    """Feed steady idle samples to let the baseline EMA converge.
    Returns the t_perf reached so the caller can continue from there."""
    n = det.cal.num_sensors
    for i in range(n_samples):
        det.feed(t0 + i * dt, (baseline_val,) * n)
    return t0 + n_samples * dt


class FsrFeedRobustnessTests(unittest.TestCase):
    """feed() must not crash on degenerate inputs that the firmware
    or upstream layers might send (short tuples, empty tuples, extra
    values, etc.)."""

    def test_short_vals_tuple_treats_missing_as_zero(self) -> None:
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        det = FSRDetector(Calibration(num_sensors=4))
        # Only 2 values for a 4-sensor detector.
        det.feed(100.0, (200, 300))
        # No exception. last_value for missing sensors stays at 0.
        self.assertEqual(det.last_value[2], 0)
        self.assertEqual(det.last_value[3], 0)

    def test_empty_vals_tuple_doesnt_crash(self) -> None:
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        det = FSRDetector(Calibration(num_sensors=4))
        det.feed(100.0, ())
        for v in det.last_value:
            self.assertEqual(v, 0)

    def test_excess_vals_ignored(self) -> None:
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        det = FSRDetector(Calibration(num_sensors=4))
        # 8 values for a 4-sensor detector. First 4 are read.
        det.feed(100.0, (10, 20, 30, 40, 99, 99, 99, 99))
        self.assertEqual(det.last_value, [10, 20, 30, 40])


class CallbackErrorIsolationTests(unittest.TestCase):
    """If on_press / on_release raises, the failure must NOT skip
    subsequent sensors in the same feed batch. Otherwise a single
    flaky callback would silently dead-zone half the patient's hand."""

    def test_press_callback_raise_does_not_skip_later_sensors(self) -> None:
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        det = FSRDetector(Calibration(num_sensors=4, debounce_ms=10))
        seen: list[int] = []

        def on_press(ev):
            seen.append(ev.lane)
            if ev.lane == 0:
                raise RuntimeError("boom")
        det.on_press = on_press

        # Settle baseline first so thresholds are sane.
        _settle_baseline(det, 50)
        # Press ALL four lanes hard. We don't care about the exact
        # ordering (sensor 1 has a higher on_delta so its smoothed
        # value crosses threshold a few samples later) - the point
        # is that lane 0 raising does NOT prevent lanes 1, 2, 3 from
        # ever firing.
        for i in range(60):
            det.feed(101.0 + i * 0.005, (600, 600, 600, 600))
        self.assertEqual(set(seen), {0, 1, 2, 3},
            "callback raise on lane 0 must not block lanes 1-3 from firing")

    def test_release_callback_raise_does_not_skip_later_sensors(self) -> None:
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        det = FSRDetector(Calibration(num_sensors=4, debounce_ms=10))
        rel_seen: list[int] = []

        def on_release(ev):
            rel_seen.append(ev.lane)
            if ev.lane == 0:
                raise RuntimeError("boom")
        det.on_release = on_release

        # Press then release all four.
        _settle_baseline(det, 50)
        for i in range(40):
            det.feed(101.0 + i * 0.005, (600, 600, 600, 600))
        for i in range(80):
            det.feed(102.0 + i * 0.005, (50, 50, 50, 50))
        self.assertEqual(sorted(rel_seen), [0, 1, 2, 3])


class DebounceTests(unittest.TestCase):
    """Within debounce_ms of a press event, a second event MUST NOT
    fire. This protects against signal chatter at the threshold."""

    def test_rapid_repeat_within_debounce_is_suppressed(self) -> None:
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        # 100 ms debounce.
        det = FSRDetector(Calibration(num_sensors=4, debounce_ms=100))
        presses = []
        det.on_press = lambda ev: presses.append(ev)

        _settle_baseline(det, 50)
        t = 101.0
        # Step 1: trigger a press (one strong sample, then a few more).
        for _ in range(10):
            det.feed(t, (600, 50, 50, 50))
            t += 0.005
        n_after_first = len(presses)
        self.assertEqual(n_after_first, 1)
        # Now release and immediately re-press WITHIN 100 ms. The
        # second press should be suppressed by debounce.
        for _ in range(2):
            det.feed(t, (50, 50, 50, 50))
            t += 0.005
        for _ in range(5):
            det.feed(t, (600, 50, 50, 50))
            t += 0.005
        # The repeat must not have produced another press event since
        # less than 100 ms elapsed since the last event.
        self.assertEqual(len(presses), 1,
            f"debounce failed: got {len(presses)} presses inside the gate")


class HysteresisTests(unittest.TestCase):
    """on_thr must always exceed off_thr by a safety margin so a
    value sitting near the boundary doesn't oscillate press/release."""

    def test_hysteresis_keeps_off_below_on(self) -> None:
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        # Bad config: abs_on_min == abs_off_max could collapse the
        # window. The detector should still keep off < on - 10.
        cal = Calibration(
            num_sensors=1,
            on_delta=[50], off_delta=[50],
            abs_on_min=[400], abs_off_max=[400],
            debounce_ms=10,
        )
        det = FSRDetector(cal)
        events: list[str] = []
        det.on_press = lambda ev: events.append("P")
        det.on_release = lambda ev: events.append("R")
        _settle_baseline(det, 50, n_samples=40)
        # Press hard, then sit right at the boundary for a while.
        t = 101.0
        for _ in range(20):
            det.feed(t, (600,))
            t += 0.005
        # Now hover the value near the threshold band.
        for _ in range(50):
            det.feed(t, (395,))    # just below abs_on_min
            t += 0.005
        # We should see at most one P, possibly one R, never P/R/P/R.
        n_press = events.count("P")
        n_release = events.count("R")
        self.assertEqual(n_press, 1,
            f"expected exactly 1 press, got {n_press}: {events}")
        self.assertLessEqual(n_release, 1,
            f"expected at most 1 release, got {n_release}: {events}")


class BaselineBehaviourTests(unittest.TestCase):
    """The baseline EMA must NOT drift toward the pressed value while
    pressed, otherwise the off-threshold creeps up and the release is
    missed."""

    def test_baseline_frozen_during_press(self) -> None:
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        det = FSRDetector(Calibration(num_sensors=1, debounce_ms=10))
        det.on_press = lambda ev: None
        det.on_release = lambda ev: None
        _settle_baseline(det, 50, n_samples=60)
        base_before = det.baseline[0]
        # Hold a press for a long time.
        t = 101.0
        for _ in range(200):
            det.feed(t, (700,))
            t += 0.005
        base_during = det.baseline[0]
        # Baseline should have moved very little (perhaps the first
        # sample before pressed=True changed it slightly).
        self.assertLess(abs(base_during - base_before), 20.0,
            f"baseline drifted during press: {base_before} -> {base_during}")

    def test_press_during_startup_self_corrects_after_release(self) -> None:
        # If the patient is already pressing when the detector starts,
        # the initial baseline anchors to the high value and the press
        # gets missed. After release, baseline drifts back down and
        # subsequent presses register normally. This documents the
        # known behaviour so a future change knows to consider it.
        from rehab.hardware.fsr_detector import Calibration, FSRDetector
        det = FSRDetector(Calibration(num_sensors=1, debounce_ms=10,
                                        baseline_alpha=0.3))
        presses: list[int] = []
        det.on_press = lambda ev: presses.append(ev.value)
        # Held high from sample 0.
        t = 100.0
        for _ in range(20):
            det.feed(t, (600,))
            t += 0.005
        # Release back to baseline.
        for _ in range(80):
            det.feed(t, (50,))
            t += 0.005
        # Now do a fresh press.
        for _ in range(40):
            det.feed(t, (600,))
            t += 0.005
        # We expect the SECOND press to fire (the first one was
        # absorbed into the baseline init).
        self.assertGreaterEqual(len(presses), 1,
            "fresh press after release should register normally")


class CalibrationPaddingTests(unittest.TestCase):
    """Calibration is read from YAML / JSON which a human might edit.
    Short arrays must be padded to num_sensors so feed() doesn't index
    out of bounds."""

    def test_calibration_pads_short_arrays(self) -> None:
        from rehab.hardware.fsr_detector import Calibration
        cal = Calibration(num_sensors=4,
                           on_delta=[60], off_delta=[40],
                           abs_on_min=[300], abs_off_max=[350])
        self.assertEqual(len(cal.on_delta), 4)
        self.assertEqual(len(cal.off_delta), 4)
        self.assertEqual(len(cal.abs_on_min), 4)
        self.assertEqual(len(cal.abs_off_max), 4)
        # First entry preserved, rest filled from defaults.
        self.assertEqual(cal.on_delta[0], 60)

    def test_calibration_clamps_zero_sensors_to_one(self) -> None:
        from rehab.hardware.fsr_detector import Calibration
        cal = Calibration(num_sensors=0)
        self.assertGreaterEqual(cal.num_sensors, 1)
        self.assertEqual(len(cal.on_delta), cal.num_sensors)


class CalibrationPadCoercionTests(unittest.TestCase):
    """Regression: _pad used to trust list entries as ints. A YAML
    typo like `on_delta: \"45\"` would flow through as ['4','5'] and
    crash FSRDetector.feed mid-block. _pad now coerces each entry to
    int and falls back to the default on failure."""

    def test_pad_coerces_strings_to_int(self) -> None:
        from rehab.hardware.fsr_detector import _pad
        # All strings that parse as ints.
        out = _pad(["10", "20", "30", "40"], 4, [1, 2, 3, 4])
        self.assertEqual(out, [10, 20, 30, 40])

    def test_pad_falls_back_on_non_numeric(self) -> None:
        from rehab.hardware.fsr_detector import _pad
        # Mix of garbage and good values - garbage gets replaced by
        # defaults at the same index, good values are preserved.
        out = _pad(["a", 20, None, "x"], 4, [1, 2, 3, 4])
        self.assertEqual(out, [1, 20, 3, 4])

    def test_pad_handles_string_list_disaster(self) -> None:
        # The pathological case that motivated this fix: someone wrote
        # the config as fsr.on_delta: "weird" instead of a list, the
        # engine called list("weird") and got chars. Every char fails
        # int() so we should end up with all defaults.
        from rehab.hardware.fsr_detector import _pad
        out = _pad(list("weird"), 4, [11, 22, 33, 44])
        self.assertEqual(out, [11, 22, 33, 44])

    def test_calibration_post_init_survives_bad_lists(self) -> None:
        # End-to-end: build a Calibration with a list-of-chars and
        # make sure __post_init__ produces sane int values.
        from rehab.hardware.fsr_detector import Calibration
        cal = Calibration(num_sensors=4,
                           on_delta=list("xxxx"),
                           off_delta=["1", "2", "3", "4"])
        # Bad entries replaced from defaults; good string-ints coerced.
        self.assertTrue(all(isinstance(v, int) for v in cal.on_delta))
        self.assertEqual(cal.off_delta, [1, 2, 3, 4])


class CalibrationPersistenceTests(unittest.TestCase):
    """Round-trip + atomicity + malformed-file recovery for the JSON
    that holds therapist-tuned thresholds."""

    def test_save_then_load_round_trips(self) -> None:
        import tempfile
        from pathlib import Path
        from rehab.hardware.fsr_detector import Calibration
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "calib.json"
            cal = Calibration(num_sensors=4, on_delta=[60, 60, 60, 60],
                               debounce_ms=150, note="patient A")
            cal.save(path)
            loaded = Calibration.load(path)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(loaded.on_delta, [60, 60, 60, 60])
            self.assertEqual(loaded.debounce_ms, 150)
            self.assertEqual(loaded.note, "patient A")

    def test_save_leaves_no_tmp_file(self) -> None:
        import tempfile
        from pathlib import Path
        from rehab.hardware.fsr_detector import Calibration
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "calib.json"
            Calibration(num_sensors=4).save(path)
            tmps = list(Path(td).glob("*.tmp"))
            self.assertEqual(tmps, [])

    def test_failed_save_preserves_prior_file(self) -> None:
        # Atomic-write regression: if json.dumps blows up, the previously
        # saved calibration must stay intact - losing it forces the
        # therapist to re-tune every sensor from scratch.
        import tempfile
        from pathlib import Path
        from unittest import mock
        from rehab.hardware import fsr_detector
        from rehab.hardware.fsr_detector import Calibration
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "calib.json"
            Calibration(num_sensors=4, on_delta=[1, 2, 3, 4]).save(path)
            prior = path.read_text()
            with mock.patch.object(fsr_detector.json, "dumps",
                                    side_effect=RuntimeError("disk hates us")):
                with self.assertRaises(RuntimeError):
                    Calibration(num_sensors=4, on_delta=[9, 9, 9, 9]).save(path)
            self.assertEqual(path.read_text(), prior)

    def test_load_returns_none_on_missing(self) -> None:
        from pathlib import Path
        from rehab.hardware.fsr_detector import Calibration
        self.assertIsNone(Calibration.load(Path("/tmp/this-does-not-exist.json")))

    def test_load_returns_none_on_corrupt_json(self) -> None:
        import tempfile
        from pathlib import Path
        from rehab.hardware.fsr_detector import Calibration
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "calib.json"
            path.write_text("{not valid json")
            self.assertIsNone(Calibration.load(path))

    def test_load_returns_none_on_malformed_field(self) -> None:
        # Regression: a hand-edited file with a non-numeric num_sensors
        # used to crash the engine because ValueError wasn't caught.
        # Now load returns None so the engine falls back to defaults.
        import tempfile
        from pathlib import Path
        from rehab.hardware.fsr_detector import Calibration
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "calib.json"
            path.write_text('{"num_sensors": "four", "debounce_ms": 100}')
            self.assertIsNone(Calibration.load(path))


if __name__ == "__main__":
    unittest.main()
