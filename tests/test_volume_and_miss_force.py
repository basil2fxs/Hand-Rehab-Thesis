"""Tests for the audio volume controls, the programmatic loud-trial
schedule, and the miss-force metric.

Three features sit behind these tests:

  1. Three volume levels (master / cue / feedback) plus a transient
     per-trial gain. Final volume of a sound is
     master x category x trial_gain x a fixed per-sound factor, clamped
     to the 0..1 range pygame's set_volume expects.
  2. A deterministic loud-trial schedule that picks an even spread of
     trials (the configured fraction) to play louder.
  3. A miss-force metric: each finger's peak above baseline is tracked
     over a window after the go stimulus, and on a miss the per-finger
     peaks are summed and accumulated.

The volume maths and the engine helpers are all pure enough to test
without opening a real audio device or display.
"""
from __future__ import annotations

import os
import sys
import types
import unittest
from pathlib import Path


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class VolumeMathTests(unittest.TestCase):
    """master / cue / feedback / trial_gain combine as documented and
    clamp to 0..1."""

    def _engine(self, master=0.8, cue=1.0, feedback=1.0):
        from rehab.audio.engine import AudioEngine
        return AudioEngine(master_volume=master, cue_volume=cue,
                           feedback_volume=feedback)

    def test_cue_and_feedback_scale_independently(self) -> None:
        a = self._engine(master=0.8, cue=0.5, feedback=1.0)
        self.assertAlmostEqual(a._cue_vol(0.6), 0.8 * 0.5 * 1.0 * 0.6)
        self.assertAlmostEqual(a._feedback_vol(0.5), 0.8 * 1.0 * 1.0 * 0.5)

    def test_trial_gain_multiplies_both_categories(self) -> None:
        a = self._engine(master=0.8, cue=1.0, feedback=1.0)
        a.set_trial_gain(1.35)
        self.assertAlmostEqual(a._cue_vol(0.6), 0.8 * 1.0 * 1.35 * 0.6)
        self.assertAlmostEqual(a._feedback_vol(0.5), 0.8 * 1.0 * 1.35 * 0.5)

    def test_volume_clamped_to_unit_interval(self) -> None:
        a = self._engine(master=1.0, cue=1.0, feedback=1.0)
        a.set_trial_gain(3.0)
        self.assertEqual(a._feedback_vol(1.0), 1.0)
        self.assertEqual(a._cue_vol(1.0), 1.0)

    def test_negative_trial_gain_floored(self) -> None:
        a = self._engine()
        a.set_trial_gain(-5.0)
        self.assertEqual(a.trial_gain, 0.0)

    def test_set_volumes_updates_and_clamps(self) -> None:
        a = self._engine()
        a.set_volumes(master=0.5, cue=0.25, feedback=0.75)
        self.assertEqual(
            (a.master_volume, a.cue_volume, a.feedback_volume),
            (0.5, 0.25, 0.75))
        a.set_volumes(master=2.0, cue=-1.0)
        self.assertEqual(a.master_volume, 1.0)
        self.assertEqual(a.cue_volume, 0.0)
        # feedback untouched when not passed.
        self.assertEqual(a.feedback_volume, 0.75)


def _bare_engine():
    """GameEngine via __new__ with just the metric state backfilled."""
    from rehab.game.engine import GameEngine
    e = GameEngine.__new__(GameEngine)
    e._ensure_metric_state()
    e.hand_mode = "right"
    e.current_block = "adaptive"
    e.audio = None
    return e


class LoudTrialScheduleTests(unittest.TestCase):
    """_is_loud_trial spreads the configured fraction evenly and the
    count comes out exact."""

    def test_even_spacing_at_one_in_ten(self) -> None:
        e = _bare_engine()
        e._loud_trial_fraction = 0.10
        loud = [n for n in range(1, 51) if e._is_loud_trial(n)]
        self.assertEqual(loud, [10, 20, 30, 40, 50])

    def test_quarter_fraction(self) -> None:
        e = _bare_engine()
        e._loud_trial_fraction = 0.25
        loud = [n for n in range(1, 21) if e._is_loud_trial(n)]
        self.assertEqual(loud, [4, 8, 12, 16, 20])

    def test_zero_fraction_disables(self) -> None:
        e = _bare_engine()
        e._loud_trial_fraction = 0.0
        self.assertFalse(any(e._is_loud_trial(n) for n in range(1, 100)))

    def test_count_matches_fraction(self) -> None:
        e = _bare_engine()
        e._loud_trial_fraction = 0.10
        loud = sum(1 for n in range(1, 101) if e._is_loud_trial(n))
        self.assertEqual(loud, 10)


class _Det:
    """Minimal detector stand-in: every sensor reads the same baseline."""

    def __init__(self, base: float) -> None:
        self._b = base
        self.fed: list[tuple] = []

    def baseline_value(self, i: int) -> float:
        return self._b

    def feed(self, t_perf: float, vals: tuple) -> None:
        # _feed_detectors's own job (press/release detection) is not
        # under test here; recording the call is enough so callers can
        # drive _track_force_peaks with the same values afterward.
        self.fed.append((t_perf, vals))


class MissForceTests(unittest.TestCase):
    """The window tracks each finger's peak above baseline and sums it
    across all fingers, but only banks it on a miss."""

    def _engine_with_det(self, base=300.0):
        e = _bare_engine()
        e.detectors = {"right": _Det(base)}
        return e, e.detectors["right"]

    def test_peak_per_finger_summed_on_miss(self) -> None:
        e, det = self._engine_with_det()
        e._open_force_window(0.0)
        # deltas above 300: 10, 60, 0, 200
        e._track_force_peaks(det, (310, 360, 300, 500), None, (0, 0, 0, 0), 4)
        # deltas: 50, 0, 0, 100 -> per-finger max keeps 50, 60, 0, 200
        e._track_force_peaks(det, (350, 300, 300, 400), None, (0, 0, 0, 0), 4)
        e._close_force_window(was_miss=True)
        self.assertEqual(e._miss_force_total, 50 + 60 + 0 + 200)
        self.assertEqual(e._miss_force_count, 1)

    def test_hit_does_not_accumulate(self) -> None:
        e, det = self._engine_with_det()
        e._open_force_window(0.0)
        e._track_force_peaks(det, (400, 400, 400, 400), None, (0, 0, 0, 0), 4)
        e._close_force_window(was_miss=False)
        self.assertEqual(e._miss_force_total, 0.0)
        self.assertEqual(e._miss_force_count, 0)

    def test_readings_below_baseline_clamp_to_zero(self) -> None:
        e, det = self._engine_with_det()
        e._open_force_window(0.0)
        e._track_force_peaks(det, (200, 250, 290, 300), None, (0, 0, 0, 0), 4)
        e._close_force_window(was_miss=True)
        # Nothing above baseline, but the miss still counts.
        self.assertEqual(e._miss_force_total, 0.0)
        self.assertEqual(e._miss_force_count, 1)

    def test_window_disarmed_after_close(self) -> None:
        e, det = self._engine_with_det()
        e._open_force_window(0.0)
        e._close_force_window(was_miss=True)
        self.assertIsNone(e._force_window_start)
        self.assertEqual(e._force_window_peak, {})

    def test_bilateral_sums_both_hands(self) -> None:
        e = _bare_engine()
        e.hand_mode = "both"
        right, left = _Det(300.0), _Det(300.0)
        e.detectors = {"right": right, "left": left}
        e._open_force_window(0.0)
        # right deltas 100,0,0,0 (lanes 0..3); left deltas 0,0,0,50 (lanes 4..7)
        e._track_force_peaks(right, (400, 300, 300, 300),
                             left, (300, 300, 300, 350), 4)
        e._close_force_window(was_miss=True)
        self.assertEqual(e._miss_force_total, 150)


class _ModeWithTimeout:
    """Stand-in for a mode that exposes current_timeout_s/hold_s, the
    hooks _open_force_window reads to size the window to the mode's own
    timeout rather than the shared metrics.miss_force_window_ms default."""

    def __init__(self, timeout_s: float, hold_s: float = 0.0) -> None:
        self.current_timeout_s = timeout_s
        self.hold_s = hold_s


class ForceWindowSizingTests(unittest.TestCase):
    """A mode whose own timeout allows a slower-but-still-valid press
    (chords.timeout_s = 3.0s against the shared 1.0s default window)
    must get a window at least that long, or a legitimate late press
    (and any leak concurrent with it) never registers and the trial
    reads as textbook-clean purely because of the window/timeout
    mismatch."""

    def test_window_widens_to_mode_timeout_plus_hold(self) -> None:
        e = _bare_engine()
        e._force_window_ms = 1000.0
        e.mode = _ModeWithTimeout(timeout_s=3.0, hold_s=0.2)
        e._open_force_window(10.0)
        self.assertAlmostEqual(e._force_window_end, 10.0 + 3.2)

    def test_window_keeps_default_when_mode_timeout_is_shorter(self) -> None:
        e = _bare_engine()
        e._force_window_ms = 1000.0
        e.mode = _ModeWithTimeout(timeout_s=0.5)
        e._open_force_window(10.0)
        self.assertAlmostEqual(e._force_window_end, 10.0 + 1.0)

    def test_window_keeps_default_when_mode_has_no_timeout_hook(self) -> None:
        e = _bare_engine()
        e._force_window_ms = 1000.0
        e.mode = None
        e._open_force_window(10.0)
        self.assertAlmostEqual(e._force_window_end, 10.0 + 1.0)

    def test_a_press_after_the_default_window_but_inside_mode_timeout_is_captured(self) -> None:
        """The end-to-end shape of the reported bug: a chord fires,
        finger 0 is caught fast (inside the old 1s window), finger 1's
        legitimate, timeout-compliant press lands at 1.3s -- past the
        old window's close but well inside the mode's own 3.0s timeout.
        _feed_detectors gates samples on start<=t_perf<=end, so with the
        window sized to the mode's timeout both presses' peaks are
        tracked instead of the late one vanishing."""
        e = _bare_engine()
        det = _Det(300.0)
        e.detectors = {"right": det}
        e.cfg = types.SimpleNamespace(
            get=lambda k, d=None: {"fsr.num_sensors_per_hand": 4}.get(k, d))
        e.mode = _ModeWithTimeout(timeout_s=3.0, hold_s=0.2)
        e._open_force_window(0.0)
        e._feed_detectors(0.30, (330, 300, 300, 300))  # finger 0
        e._feed_detectors(1.30, (300, 340, 300, 300))  # finger 1, late
        self.assertIn(0, e._force_window_peak)
        self.assertIn(1, e._force_window_peak)


class RtAggregationTests(unittest.TestCase):
    """overall_mean_rt / overall_best_rt flatten the per-lane lists and
    treat rhythm offsets by absolute value."""

    def _eng(self, rts, block="adaptive"):
        from rehab.game.engine import GameEngine
        e = GameEngine.__new__(GameEngine)
        e._per_lane_rts = rts
        e.current_block = block
        return e

    def test_mean_and_best_cadence(self) -> None:
        e = self._eng({0: [200.0, 300.0], 2: [150.0]})
        self.assertAlmostEqual(e.overall_mean_rt(), (200 + 300 + 150) / 3)
        self.assertEqual(e.overall_best_rt(), 150.0)

    def test_empty_returns_zero(self) -> None:
        e = self._eng({})
        self.assertEqual(e.overall_mean_rt(), 0.0)
        self.assertEqual(e.overall_best_rt(), 0.0)

    def test_rhythm_uses_absolute_offset(self) -> None:
        # Signed offsets: 120 early, 40 late, 10 early.
        e = self._eng({0: [-120.0, 40.0], 1: [-10.0]}, block="rhythm")
        self.assertAlmostEqual(e.overall_mean_rt(), (120 + 40 + 10) / 3)
        # Best = tightest to the beat, not the most negative.
        self.assertEqual(e.overall_best_rt(), 10.0)


class ConfigDefaultsTests(unittest.TestCase):
    """The new config keys are present and in range after a default
    load (covers a typo'd YAML key silently falling back)."""

    def test_audio_and_metric_defaults(self) -> None:
        from rehab.config import Config
        cfg = Config.load()
        for key in ("audio.cue_volume", "audio.feedback_volume",
                    "audio.loud_trial.fraction", "audio.loud_trial.boost"):
            self.assertIsNotNone(cfg.get(key), key)
        self.assertGreaterEqual(cfg.get("audio.loud_trial.boost"), 1.0)
        self.assertEqual(int(cfg.get("metrics.miss_force_window_ms")), 1000)


if __name__ == "__main__":
    unittest.main()
