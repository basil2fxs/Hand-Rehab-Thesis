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


def teasdale_onset(force, fs, min_rise=80.0, vmax_min=30.0,
                   first_slope_min=25.0, first_step_min=12.0,
                   slope_frac=0.18, step_s=0.05,
                   search_from=0, search_to=None, prefer_first=True):
    """Movement onset on one force segment, Teasdale-style.

    Exact port of the reference implementation Rayan sent
    (docs/research/rayan/process_force_peaks.py), the detector
    Welber's earlier sessions were processed with, so onsets from
    this function are directly comparable with that work. The
    technique is citable to Teasdale, Bard, Fleury, Young and
    Proteau (1993), "Determining movement onsets from temporal
    series", Journal of Motor Behavior 25(2), 97-106. An earlier
    version of this module carried a paraphrase (velocity over
    mean + k*sd of a baseline window); it and the notebook's own
    third variant are gone so there is exactly one onset detector.

    The same function text lives in analysis/session_analysis.ipynb,
    which travels without this package. Tests pin the two copies to
    each other and this one to Rayan's file.

    Steps, defaults as in the reference file:
      1. Low-pass the raw segment (2nd order Butterworth, 20 Hz,
         filtfilt so the filter delay does not shift the onset).
      2. Velocity = first difference times fs, then Savitzky-Golay
         (11/3) and a 10 Hz low-pass, because differentiating
         amplifies exactly the noise the first filter removed.
      3. Give up unless the segment rises at least `min_rise` counts
         over the mean of its first 20 samples: below that there is
         no press to time.
      4. First pass: the earliest sample where velocity clears
         max(first_slope_min, slope_frac * vmax) AND the force
         itself rises by at least `first_step_min` counts over the
         next `step_s` seconds. The step check is what stops one
         noisy velocity spike reading as an onset.
      5. Fallback (prefer_first False, or nothing passed step 4):
         walk back from the velocity peak to where velocity drops
         below 10 percent of that peak minus one sd, the backward
         search the 1993 paper describes.

    Returns (onset_idx, force_lp, dforce): the onset sample index
    within `force` (None when nothing convincing happened), plus the
    filtered force and velocity for callers that plot them.
    `search_from` and `search_to` are sample indices bounding the
    search; note dforce is one sample shorter than force_lp because
    the difference is not padded, exactly as in the reference.
    """
    from scipy.signal import butter, filtfilt, savgol_filter
    if force is None or len(force) < 20:
        return None, None, None
    x = np.asarray(force, dtype=float)
    baseline = np.mean(x[:min(20, len(x))])

    wn = min(max(20.0 / (fs / 2.0), 1e-6), 0.999999)
    b, a = butter(2, wn, btype="low")
    try:
        force_lp = filtfilt(b, a, x)
    except ValueError:
        return None, None, None

    dforce = np.diff(force_lp) * fs
    if len(dforce) > 11:
        dforce = savgol_filter(dforce, 11, 3)
    wn_d = min(max(10.0 / (fs / 2.0), 1e-6), 0.999999)
    bd, ad = butter(2, wn_d, btype="low")
    if len(dforce) > 20:
        dforce = filtfilt(bd, ad, dforce)

    if (np.max(force_lp) - baseline) < min_rise:
        return None, force_lp, dforce

    lo = max(0, int(search_from))
    hi = len(force_lp) if search_to is None else max(lo + 5, int(search_to))
    hi = min(hi, len(force_lp))
    if hi - lo < 8 or len(dforce) < 5:
        return None, force_lp, dforce

    if prefer_first:
        d_seg = dforce[lo:hi - 1]
        vmax = float(np.max(d_seg)) if len(d_seg) else 0.0
        thr = max(first_slope_min, slope_frac * vmax)
        step_k = max(1, int(step_s * fs))
        for j in range(len(d_seg) - step_k):
            i = lo + j
            if d_seg[j] >= thr:
                if (force_lp[i + step_k] - force_lp[i]) >= first_step_min:
                    return int(i), force_lp, dforce

    vmax_ind = lo + int(np.argmax(dforce[lo:max(lo + 1, hi - 1)]))
    vmax = float(dforce[vmax_ind])
    if vmax <= 0 or vmax < vmax_min:
        return None, force_lp, dforce

    d_int = dforce[:vmax_ind + 1]
    d_rev = d_int[::-1]
    s_level = vmax * 0.1
    below = np.where(d_rev < s_level)[0]
    s_ind = int(below[0]) if len(below) else 0
    if len(d_int) - s_ind > 0:
        sd = float(np.std(d_int[:len(d_int) - s_ind]))
        if not np.isfinite(sd) or sd == 0:
            sd = 1.0
    else:
        sd = 1.0
    candidates = np.where(d_rev[s_ind:] < (s_level - sd))[0]
    if len(candidates):
        onset = len(d_int) - int(s_ind + candidates[0])
    else:
        onset = vmax_ind
    onset_idx = int(max(0, min(onset, len(force_lp) - 1)))
    if not (lo <= onset_idx < hi):
        return None, force_lp, dforce
    return onset_idx, force_lp, dforce


def lookback_baseline(values, idx, window=50):
    """Mean of the `window` samples immediately before `values[idx]`.

    The 250 ms look-back zero from Rayan's baseline drift analysis
    (docs/research/rayan/analyze_baseline_drift_modified_newtons.R):
    at 200 Hz, 50 samples is the quarter second before a press, so
    subtracting this mean re-zeroes each press against the level the
    sensor was actually resting at, instead of against one session
    constant the baseline has long since drifted away from. The same
    function text lives in the analysis notebook; tests pin the two
    copies to each other.

    Truncates at the start of the array rather than failing, matching
    the reference (start_idx = max(1, row_idx - window)). NaN inside
    the window is skipped like the reference's na.rm = TRUE, and NaN
    comes back when nothing finite sits in the window, so a press at
    sample zero cannot be zeroed against thin air.
    """
    arr = np.asarray(values, dtype=float)
    stop = int(idx)
    start = max(0, stop - int(window))
    seg = arr[start:stop]
    seg = seg[np.isfinite(seg)]
    if seg.size == 0:
        return float("nan")
    return float(seg.mean())
