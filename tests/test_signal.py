"""Tests for rehab/analytics/signal.py.

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
        from rehab.analytics.signal import butter_lowpass_force
        x = self._sine(5.0)
        y = butter_lowpass_force(x, self.FS)
        self.assertGreater(_power(y), 0.8 * _power(x))

    def test_stopband_60hz_attenuated(self) -> None:
        # 60 Hz is 3x the cutoff. With a 2nd-order Butterworth applied
        # twice (filtfilt -> effective 4th-order) the attenuation at
        # 3x is enormous; require at least 10x power reduction.
        from rehab.analytics.signal import butter_lowpass_force
        x = self._sine(60.0)
        y = butter_lowpass_force(x, self.FS)
        self.assertLess(_power(y), 0.1 * _power(x))

    def test_noise_high_frequency_attenuated(self) -> None:
        # 5 Hz passband sine + a noisy 60 Hz stopband sine. After
        # filtering the 5 Hz signal should dominate the residual.
        from rehab.analytics.signal import butter_lowpass_force
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
        from rehab.analytics.signal import butter_lowpass_force
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
        from rehab.analytics.signal import butter_lowpass_dforce
        x = self._sine(3.0)
        y = butter_lowpass_dforce(x, self.FS)
        self.assertGreater(_power(y), 0.8 * _power(x))

    def test_15hz_attenuated_more_than_force_filter(self) -> None:
        # 15 Hz sits between the two cutoffs (20 Hz force, 10 Hz
        # dforce). The dforce filter must hit it harder than the
        # force filter does.
        from rehab.analytics.signal import (
            butter_lowpass_force, butter_lowpass_dforce,
        )
        x = self._sine(15.0)
        y_force = butter_lowpass_force(x, self.FS)
        y_dforce = butter_lowpass_dforce(x, self.FS)
        self.assertLess(_power(y_dforce), _power(y_force))


class SavgolTests(unittest.TestCase):

    def test_smooths_random_noise(self) -> None:
        from rehab.analytics.signal import savgol
        rng = np.random.default_rng(seed=42)
        x = rng.normal(0.0, 1.0, size=200)
        y = savgol(x)
        # 11-window savgol smooths random noise -> variance drops.
        self.assertLess(float(np.var(y)), float(np.var(x)))

    def test_preserves_linear_ramp(self) -> None:
        # Polyorder=3 reproduces any polynomial up to degree 3
        # exactly. A linear ramp must survive unchanged.
        from rehab.analytics.signal import savgol
        x = np.linspace(0.0, 10.0, 100)
        y = savgol(x)
        # Interior samples (away from edge effects) should match
        # within float precision.
        np.testing.assert_allclose(y[20:80], x[20:80], atol=1e-9)

    def test_same_length_output(self) -> None:
        from rehab.analytics.signal import savgol
        x = np.zeros(50)
        self.assertEqual(len(savgol(x)), len(x))


class DerivativeTests(unittest.TestCase):

    def test_constant_signal_zero_derivative(self) -> None:
        from rehab.analytics.signal import derivative
        x = np.full(20, 7.5)
        y = derivative(x, fs=100.0)
        np.testing.assert_allclose(y, np.zeros_like(x))

    def test_linear_ramp_constant_derivative(self) -> None:
        # f(t) = a * t with a = 2/sample. With fs=100 -> dF/dt should
        # be 2 * fs = 200 per sample after the prepend boundary
        # condition stabilises (sample 0 returns 0 because of the
        # prepend trick - that's documented behaviour).
        from rehab.analytics.signal import derivative
        x = np.arange(10, dtype=float) * 2.0   # 0, 2, 4, ...
        y = derivative(x, fs=100.0)
        # sample 0: diff(0 - 0) * 100 = 0 (prepend boundary).
        self.assertAlmostEqual(y[0], 0.0)
        # samples 1..n: diff = 2, *100 = 200.
        np.testing.assert_allclose(y[1:], 200.0)

    def test_same_length_output(self) -> None:
        from rehab.analytics.signal import derivative
        x = np.arange(50, dtype=float)
        self.assertEqual(len(derivative(x, fs=100.0)), len(x))


class TeasdaleOnsetTests(unittest.TestCase):
    """Onset detection on a synthetic trace: 100 samples of baseline
    noise followed by a sharp ramp. The detector should pick the
    ramp start, not the noise spikes."""

    FS = 200.0

    def _trace(self, onset_idx: int = 100,
                ramp_slope: float = 0.5,
                noise_std: float = 0.02,
                n: int = 200,
                seed: int = 7) -> np.ndarray:
        rng = np.random.default_rng(seed=seed)
        x = rng.normal(0.0, noise_std, size=n)
        # Linear ramp starting at `onset_idx`.
        ramp = np.maximum(0.0, np.arange(n) - onset_idx) * ramp_slope
        return x + ramp

    def test_picks_ramp_onset_within_tolerance(self) -> None:
        from rehab.analytics.signal import detect_onset_teasdale
        trace = self._trace(onset_idx=120)
        idx = detect_onset_teasdale(trace, fs=self.FS,
                                      baseline_window=80, k=3.0)
        self.assertIsNotNone(idx)
        # Filter group delay + savgol smoothing shift the detected
        # onset by a few samples; accept anything within +/- 15
        # samples of the truth.
        self.assertLess(abs(idx - 120), 15)

    def test_returns_none_when_no_press(self) -> None:
        # Pure noise, no ramp -> the threshold is never crossed for
        # two consecutive samples.
        from rehab.analytics.signal import detect_onset_teasdale
        rng = np.random.default_rng(seed=1)
        trace = rng.normal(0.0, 0.01, size=200)
        # Use a high k so noise can't sneak past the threshold.
        idx = detect_onset_teasdale(trace, fs=self.FS,
                                      baseline_window=80, k=10.0)
        self.assertIsNone(idx)

    def test_returns_none_on_short_input(self) -> None:
        from rehab.analytics.signal import detect_onset_teasdale
        self.assertIsNone(detect_onset_teasdale(
            np.zeros(5), fs=self.FS))


if __name__ == "__main__":
    unittest.main()
