"""Signal-processing primitives for the force-stream analytics.

Pure functions that take a 1D numpy array of samples plus the
sample rate (Hz) and return a same-length array. The peak-force
analyser uses them on raw FSR traces; offline force-profile work
can pull them in too without dragging the whole engine.

Cutoff values are hardcoded so the thesis methods section can quote
exact numbers and anyone re-running the analysis lands on the same
filter shape. If a future tuning pass needs different cutoffs, swap
them here and document why.
"""
from __future__ import annotations

import numpy as np


def butter_lowpass_force(x: np.ndarray, fs: float) -> np.ndarray:
    """Zero-phase 2nd-order Butterworth low-pass at 20 Hz. Strips
    high-frequency sensor noise from a raw force trace while keeping
    the press onset / release shape intact. filtfilt is the
    zero-phase variant - applying the same filter forwards and
    backwards cancels the group delay, so the filtered peak time
    still lines up with the raw peak time.
    """
    from scipy.signal import butter, filtfilt
    b, a = butter(N=2, Wn=20.0 / (fs / 2.0), btype="low")
    return filtfilt(b, a, np.asarray(x, dtype=float))


def butter_lowpass_dforce(x: np.ndarray, fs: float) -> np.ndarray:
    """Zero-phase 2nd-order Butterworth low-pass at 10 Hz. The
    derivative of a force trace amplifies high-frequency noise, so
    we use a tighter cutoff than the force filter (10 Hz vs 20 Hz)
    to keep dF/dt readable.
    """
    from scipy.signal import butter, filtfilt
    b, a = butter(N=2, Wn=10.0 / (fs / 2.0), btype="low")
    return filtfilt(b, a, np.asarray(x, dtype=float))


def savgol(x: np.ndarray) -> np.ndarray:
    """Savitzky-Golay smoothing with an 11-sample window and order-3
    polynomial. I went with these over a Butterworth here because
    savgol keeps the transient shape of a short press intact, where
    Butterworth would round off the edges."""
    from scipy.signal import savgol_filter
    return savgol_filter(np.asarray(x, dtype=float),
                          window_length=11, polyorder=3)


def derivative(x: np.ndarray, fs: float) -> np.ndarray:
    """First-difference derivative with `prepend=x[0]` so the output
    is the same length as the input. Multiplied by `fs` so the units
    come out in (signal units) per second instead of per sample - dF/dt
    in newtons-per-second if `x` is in newtons.
    """
    arr = np.asarray(x, dtype=float)
    return np.diff(arr, prepend=arr[0]) * fs


def detect_onset_teasdale(force: np.ndarray, fs: float,
                            baseline_window: int = 50,
                            k: float = 3.0) -> int | None:
    """Teasdale 1993 onset detection.

    Press onset is the first sample where the smoothed force
    velocity exceeds `mean(baseline_velocity) + k * std(baseline_velocity)`.
    Citable to Teasdale et al. (1993) "On the measurement of motor
    initiation" - the standard biomechanics technique for picking
    the moment a force trace stops being noise and starts being a
    deliberate press.

    Steps:
      1. Smooth the raw force with the Butterworth low-pass.
      2. Take the derivative to get force velocity (dF/dt).
      3. Smooth the velocity with Savitzky-Golay.
      4. Compute the noise floor (mean + k*std) from the first
         `baseline_window` samples - assumed to be pre-press idle.
      5. Return the first sample index where the smoothed
         velocity stays above that threshold for two consecutive
         samples (single-sample crossings would be triggered by
         residual noise).

    Returns None when the input is too short or the velocity
    never crosses the threshold.
    """
    arr = np.asarray(force, dtype=float)
    if arr.size < baseline_window + 4:
        return None
    smoothed = butter_lowpass_force(arr, fs)
    velocity = derivative(smoothed, fs)
    velocity = savgol(velocity)
    base = velocity[:baseline_window]
    threshold = float(base.mean() + k * base.std())
    above_prev = False
    for i in range(baseline_window, len(velocity)):
        above = bool(velocity[i] > threshold)
        if above and above_prev:
            # Onset = the FIRST of the two consecutive samples
            # above threshold, so the patient's perceived press
            # start aligns with the first detected acceleration.
            return i - 1
        above_prev = above
    return None
