"""Tests for finger_rehab/analytics/signal.py.

Each filter is exercised with a synthetic input where the expected
spectral behaviour is computable from the cutoff alone: a sine in
the passband must survive, a sine in the stopband must be heavily
attenuated, and an impulse / linear ramp must keep its DC component.
The tests use power ratios rather than exact amplitude matches so
they survive small float-precision differences across scipy
versions.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _power(x: np.ndarray) -> float:
    """Total signal power (mean square). Used to compare before /
    after a filter without caring about exact amplitudes."""
    return float(np.mean(np.square(x)))


class ButterLowpassForceTests(unittest.TestCase):

    FS = 200.0     # firmware sample rate per spec.

    def _sine(self, freq: float, n: int = 800) -> np.ndarray:
        t = np.arange(n) / self.FS
        return np.sin(2 * np.pi * freq * t)

    def test_passband_5hz_survives(self) -> None:
        # 5 Hz sits well inside the 20 Hz passband, so the output
        # should keep at least 80% of the input power.
        from finger_rehab.analytics.signal import butter_lowpass_force
        x = self._sine(5.0)
        y = butter_lowpass_force(x, self.FS)
        self.assertGreater(_power(y), 0.8 * _power(x))

    def test_stopband_60hz_attenuated(self) -> None:
        # 60 Hz is 3x the cutoff. With a 2nd-order Butterworth applied
        # twice (filtfilt -> effective 4th-order) the attenuation at
        # 3x is enormous; require at least 10x power reduction.
        from finger_rehab.analytics.signal import butter_lowpass_force
        x = self._sine(60.0)
        y = butter_lowpass_force(x, self.FS)
        self.assertLess(_power(y), 0.1 * _power(x))

    def test_noise_high_frequency_attenuated(self) -> None:
        # 5 Hz passband sine + a noisy 60 Hz stopband sine. After
        # filtering the 5 Hz signal should dominate the residual.
        from finger_rehab.analytics.signal import butter_lowpass_force
        signal_5 = self._sine(5.0)
        noise_60 = self._sine(60.0)
        x = signal_5 + noise_60
        y = butter_lowpass_force(x, self.FS)
        # Residual high-frequency content (energy above 30 Hz, via a
        # simple diff-of-filter check): the filter output should be
        # much closer to the clean 5 Hz sine than to the noisy input.
        clean_dist = _power(y - signal_5)
        dirty_dist = _power(x - signal_5)
        self.assertLess(clean_dist, dirty_dist * 0.1)

    def test_same_length_output(self) -> None:
        from finger_rehab.analytics.signal import butter_lowpass_force
        x = self._sine(5.0, n=500)
        y = butter_lowpass_force(x, self.FS)
        self.assertEqual(len(y), len(x))


class ButterLowpassDforceTests(unittest.TestCase):
    """dForce filter uses a tighter 10 Hz cutoff because differentiating
    amplifies high-frequency noise."""

    FS = 200.0

    def _sine(self, freq: float, n: int = 800) -> np.ndarray:
        t = np.arange(n) / self.FS
        return np.sin(2 * np.pi * freq * t)

    def test_passband_3hz_survives(self) -> None:
        from finger_rehab.analytics.signal import butter_lowpass_dforce
        x = self._sine(3.0)
        y = butter_lowpass_dforce(x, self.FS)
        self.assertGreater(_power(y), 0.8 * _power(x))

    def test_15hz_attenuated_more_than_force_filter(self) -> None:
        # 15 Hz sits between the two cutoffs (20 Hz force, 10 Hz
        # dforce). The dforce filter must hit it harder than the
        # force filter does.
        from finger_rehab.analytics.signal import (
            butter_lowpass_force, butter_lowpass_dforce,
        )
        x = self._sine(15.0)
        y_force = butter_lowpass_force(x, self.FS)
        y_dforce = butter_lowpass_dforce(x, self.FS)
        self.assertLess(_power(y_dforce), _power(y_force))


class SavgolTests(unittest.TestCase):

    def test_smooths_random_noise(self) -> None:
        from finger_rehab.analytics.signal import savgol
        rng = np.random.default_rng(seed=42)
        x = rng.normal(0.0, 1.0, size=200)
        y = savgol(x)
        # 11-window savgol smooths random noise -> variance drops.
        self.assertLess(float(np.var(y)), float(np.var(x)))

    def test_preserves_linear_ramp(self) -> None:
        # Polyorder=3 reproduces any polynomial up to degree 3
        # exactly. A linear ramp must survive unchanged.
        from finger_rehab.analytics.signal import savgol
        x = np.linspace(0.0, 10.0, 100)
        y = savgol(x)
        # Interior samples (away from edge effects) should match
        # within float precision.
        np.testing.assert_allclose(y[20:80], x[20:80], atol=1e-9)

    def test_same_length_output(self) -> None:
        from finger_rehab.analytics.signal import savgol
        x = np.zeros(50)
        self.assertEqual(len(savgol(x)), len(x))


class DerivativeTests(unittest.TestCase):

    def test_constant_signal_zero_derivative(self) -> None:
        from finger_rehab.analytics.signal import derivative
        x = np.full(20, 7.5)
        y = derivative(x, fs=100.0)
        np.testing.assert_allclose(y, np.zeros_like(x))

    def test_linear_ramp_constant_derivative(self) -> None:
        # f(t) = a * t with a = 2/sample. With fs=100 -> dF/dt should
        # be 2 * fs = 200 per sample after the prepend boundary
        # condition stabilises (sample 0 returns 0 because of the
        # prepend trick - that's documented behaviour).
        from finger_rehab.analytics.signal import derivative
        x = np.arange(10, dtype=float) * 2.0   # 0, 2, 4, ...
        y = derivative(x, fs=100.0)
        # sample 0: diff(0 - 0) * 100 = 0 (prepend boundary).
        self.assertAlmostEqual(y[0], 0.0)
        # samples 1..n: diff = 2, *100 = 200.
        np.testing.assert_allclose(y[1:], 200.0)

    def test_same_length_output(self) -> None:
        from finger_rehab.analytics.signal import derivative
        x = np.arange(50, dtype=float)
        self.assertEqual(len(derivative(x, fs=100.0)), len(x))


def _press_trace(onset_idx: int = 120,
                 rise_per_sample: float = 15.0,
                 plateau: float = 300.0,
                 noise_std: float = 2.0,
                 n: int = 250,
                 drift_per_sample: float = 0.0,
                 seed: int = 7) -> np.ndarray:
    """Synthetic press in ADC counts: flat noisy baseline, a linear
    rise starting at `onset_idx`, clipped at `plateau`. Optional slow
    drift under everything, which is the failure mode the look-back
    zeroing exists for."""
    rng = np.random.default_rng(seed=seed)
    x = rng.normal(0.0, noise_std, size=n)
    ramp = np.minimum(np.maximum(0.0, np.arange(n) - onset_idx)
                      * rise_per_sample, plateau)
    return x + ramp + np.arange(n) * drift_per_sample


class TeasdaleOnsetTests(unittest.TestCase):
    """The canonical detector (the exact port of Rayan's reference
    file) on synthetic presses in ADC counts at the firmware's
    200 Hz."""

    FS = 200.0

    def test_picks_ramp_onset_within_tolerance(self) -> None:
        from finger_rehab.analytics.signal import teasdale_onset
        idx, force_lp, dforce = teasdale_onset(
            _press_trace(onset_idx=120), fs=self.FS)
        self.assertIsNotNone(idx)
        # Zero-phase filtering smears the edge a little both ways;
        # accept anything within +/- 15 samples (75 ms) of truth.
        self.assertLess(abs(idx - 120), 15)
        # The filtered traces come back for plotting, dforce one
        # sample shorter because the difference is not padded.
        self.assertEqual(len(force_lp), 250)
        self.assertEqual(len(dforce), 249)

    def test_returns_none_when_rise_is_below_min_rise(self) -> None:
        # An 80-count minimum rise is the reference's floor for
        # "a press happened at all". A 40-count wiggle is not one.
        from finger_rehab.analytics.signal import teasdale_onset
        trace = _press_trace(onset_idx=120, rise_per_sample=2.0,
                             plateau=40.0)
        idx, _, _ = teasdale_onset(trace, fs=self.FS)
        self.assertIsNone(idx)

    def test_returns_none_on_pure_noise(self) -> None:
        from finger_rehab.analytics.signal import teasdale_onset
        rng = np.random.default_rng(seed=1)
        idx, _, _ = teasdale_onset(rng.normal(0.0, 2.0, size=250),
                                   fs=self.FS)
        self.assertIsNone(idx)

    def test_returns_none_on_short_input(self) -> None:
        from finger_rehab.analytics.signal import teasdale_onset
        idx, force_lp, dforce = teasdale_onset(np.zeros(5), fs=self.FS)
        self.assertIsNone(idx)
        self.assertIsNone(force_lp)
        self.assertIsNone(dforce)

    def test_search_window_bounds_are_respected(self) -> None:
        # A press outside the search window is not this trial's
        # press. Search only the first 100 samples of a trace whose
        # rise starts at 150: nothing should be found.
        from finger_rehab.analytics.signal import teasdale_onset
        trace = _press_trace(onset_idx=150, n=300)
        idx, _, _ = teasdale_onset(trace, fs=self.FS,
                                   search_from=0, search_to=100)
        self.assertIsNone(idx)

    def test_onset_lands_before_the_force_peak(self) -> None:
        # The whole point over a threshold crossing: the onset is
        # where force STARTS moving, well before the peak.
        from finger_rehab.analytics.signal import teasdale_onset
        trace = _press_trace(onset_idx=100)
        idx, _, _ = teasdale_onset(trace, fs=self.FS)
        self.assertIsNotNone(idx)
        self.assertLess(idx, int(np.argmax(trace)))


class TeasdaleOnsetMatchesReferenceTests(unittest.TestCase):
    """The package function claims to be an exact port of Rayan's
    process_force_peaks.py. Run both over a grid of synthetic traces
    and require identical answers, so any 'tidy-up' that changes the
    numbers fails here instead of quietly diverging from the results
    Welber already has."""

    FS = 200.0
    REFERENCE = (Path(__file__).resolve().parents[1] / "docs" / "research"
                 / "rayan" / "process_force_peaks.py")

    def _reference_onset(self):
        import importlib.util
        self.assertTrue(self.REFERENCE.exists(),
                        f"reference file missing: {self.REFERENCE}")
        spec = importlib.util.spec_from_file_location(
            "rayan_process_force_peaks", self.REFERENCE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.teasdale_onset

    def test_identical_onsets_across_a_grid(self) -> None:
        from finger_rehab.analytics.signal import teasdale_onset
        ref = self._reference_onset()
        cases = []
        for onset in (40, 100, 150):
            for slope in (5.0, 15.0):
                for seed in (3, 11):
                    cases.append(_press_trace(onset_idx=onset,
                                              rise_per_sample=slope,
                                              seed=seed))
        # Drifting baseline and a no-press trace exercise the min-rise
        # gate and the fallback path, not just the happy path.
        cases.append(_press_trace(onset_idx=100, drift_per_sample=0.2))
        rng = np.random.default_rng(seed=5)
        cases.append(rng.normal(0.0, 2.0, size=250))
        for trace in cases:
            ours, _, _ = teasdale_onset(trace, fs=self.FS)
            theirs, _, _ = ref(trace, fs=self.FS)
            self.assertEqual(ours, theirs)

    def test_identical_onsets_with_explicit_search_window(self) -> None:
        from finger_rehab.analytics.signal import teasdale_onset
        ref = self._reference_onset()
        trace = _press_trace(onset_idx=120)
        for lo, hi in ((0, 240), (0, 100), (50, 200)):
            ours, _, _ = teasdale_onset(trace, fs=self.FS,
                                        search_from=lo, search_to=hi)
            theirs, _, _ = ref(trace, fs=self.FS,
                               search_from=lo, search_to=hi)
            self.assertEqual(ours, theirs)


class LookbackBaselineTests(unittest.TestCase):
    """The 250 ms / 50-sample look-back zero from Rayan's drift
    analysis, ported as lookback_baseline."""

    def test_mean_of_the_previous_window(self) -> None:
        from finger_rehab.analytics.signal import lookback_baseline
        values = np.arange(200, dtype=float)
        # Samples 100..149 have mean 124.5.
        self.assertAlmostEqual(lookback_baseline(values, 150, window=50),
                               124.5)

    def test_excludes_the_sample_itself(self) -> None:
        # The reference averages rows start..idx-1: the press sample
        # must not zero itself away.
        from finger_rehab.analytics.signal import lookback_baseline
        values = np.zeros(100)
        values[60] = 500.0
        self.assertAlmostEqual(lookback_baseline(values, 60), 0.0)

    def test_truncates_at_the_start(self) -> None:
        from finger_rehab.analytics.signal import lookback_baseline
        values = np.full(200, 7.0)
        # idx=10 leaves only 10 samples of history; the reference
        # clamps to the start rather than failing.
        self.assertAlmostEqual(lookback_baseline(values, 10), 7.0)

    def test_skips_nan_inside_the_window(self) -> None:
        from finger_rehab.analytics.signal import lookback_baseline
        values = np.full(100, 4.0)
        values[70:75] = np.nan
        self.assertAlmostEqual(lookback_baseline(values, 80), 4.0)

    def test_nan_when_no_history_exists(self) -> None:
        from finger_rehab.analytics.signal import lookback_baseline
        self.assertTrue(np.isnan(lookback_baseline(np.arange(50.0), 0)))

    def test_window_parameter_is_honoured(self) -> None:
        from finger_rehab.analytics.signal import lookback_baseline
        values = np.concatenate([np.full(90, 100.0), np.full(10, 0.0)])
        # A 10-sample window sees only the zeros right before idx.
        self.assertAlmostEqual(
            lookback_baseline(values, 100, window=10), 0.0)


if __name__ == "__main__":
    unittest.main()
