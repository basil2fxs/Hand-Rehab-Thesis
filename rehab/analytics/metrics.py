"""Pure metric functions for the per-block research summary.

Each function takes raw lists or arrays and returns a dict or scalar.
No side effects, no file IO. The engine calls these at finish_block
and stashes the results in session.json's block_summary so a
researcher can read the numbers straight off disk without reloading
the trial CSV.

I kept the formulas line-for-line with what's in my thesis methods
section. Picked sample stdev (n-1) over population stdev because
that's the rehab-stats convention and it matches what SPSS would
output for the same data.
"""
from __future__ import annotations

import bisect
import math
from typing import Sequence


def rt_stats(rt_values: Sequence[float]) -> dict:
    """Mean, sample stdev, and coefficient of variation of an RT list.
    The caller is expected to pre-filter to the hit-only RTs (miss
    trials have no RT, and a mixed list would skew the std).

    Returns a dict with keys rt_mean, rt_std, rt_cv. Each value is None
    when undefined: empty input -> all None, single value -> std + cv
    None (sample stdev needs n >= 2), zero mean -> cv None.
    """
    n = len(rt_values)
    if n == 0:
        return {"rt_mean": None, "rt_std": None, "rt_cv": None}
    mean = sum(rt_values) / n
    if n < 2:
        return {"rt_mean": mean, "rt_std": None, "rt_cv": None}
    variance = sum((x - mean) ** 2 for x in rt_values) / (n - 1)
    std = math.sqrt(variance)
    cv = std / mean if mean > 0 else None
    return {"rt_mean": mean, "rt_std": std, "rt_cv": cv}


def outcome_rates(outcomes: Sequence[str],
                   hit_labels: tuple[str, ...] = ("hit",),
                   misclick_labels: tuple[str, ...] = ("misclick",),
                   timeout_labels: tuple[str, ...] = ("timeout",)) -> dict:
    """Hit / misclick / timeout proportions of an outcome list.
    Defaults assume the outcomes are already normalised to the three
    canonical labels. The label-set arguments let a caller using the
    game's native labels (Perfect/Great/Good/Late/Miss) map their
    vocabulary without pre-translating.
    """
    n = len(outcomes)
    if n == 0:
        return {"hit_rate": 0.0, "misclick_rate": 0.0, "timeout_rate": 0.0}
    hits = sum(1 for o in outcomes if o in hit_labels)
    misclicks = sum(1 for o in outcomes if o in misclick_labels)
    timeouts = sum(1 for o in outcomes if o in timeout_labels)
    return {
        "hit_rate": hits / n,
        "misclick_rate": misclicks / n,
        "timeout_rate": timeouts / n,
    }


def fatigue_slope(per_block_values: Sequence[float]) -> float | None:
    """Linear-regression slope of value-vs-block-index. Use it on a
    list of per-block mean RTs (positive slope -> patient slowing as
    blocks accumulate) or per-block mean peak forces (negative slope
    -> force fading). Returns None for fewer than 2 blocks because the
    slope is mathematically undefined there.
    """
    if len(per_block_values) < 2:
        return None
    import numpy as np
    xs = np.arange(len(per_block_values), dtype=float)
    ys = np.array(per_block_values, dtype=float)
    return float(np.polyfit(xs, ys, 1)[0])


def asymmetry_index(left_val: float | None,
                     right_val: float | None) -> float | None:
    """|L - R| / mean(L, R). Standard bilateral-rehab index where
    0 means symmetric and 1 means one hand contributes nothing.
    Returns None if either side is missing, or both are zero (the
    mean denominator would be zero too).
    """
    if left_val is None or right_val is None:
        return None
    s = float(left_val) + float(right_val)
    if s == 0:
        return None
    return abs(float(left_val) - float(right_val)) / (s / 2.0)


def beat_offset_stats(press_times_s: Sequence[float],
                       beat_times_s: Sequence[float]) -> dict:
    """For each press, find the nearest beat and compute the signed
    offset in milliseconds. Negative means the press came before the
    beat, positive means after. Returns mean offset (tells you if
    the patient drifts early or late), sample stdev (timing
    consistency from press to press), and absolute mean (raw timing
    error ignoring direction).
    """
    if not press_times_s or not beat_times_s:
        return {
            "beat_offset_mean_ms": None,
            "beat_offset_std_ms": None,
            "beat_offset_abs_mean_ms": None,
        }
    beats_sorted = sorted(beat_times_s)
    offsets_ms: list[float] = []
    for pt in press_times_s:
        # bisect_left + neighbour comparison gives O(log n) nearest
        # without building a full distance matrix.
        i = bisect.bisect_left(beats_sorted, pt)
        if i == 0:
            nearest = beats_sorted[0]
        elif i == len(beats_sorted):
            nearest = beats_sorted[-1]
        else:
            before = beats_sorted[i - 1]
            after = beats_sorted[i]
            nearest = before if (pt - before) <= (after - pt) else after
        offsets_ms.append((pt - nearest) * 1000.0)
    n = len(offsets_ms)
    mean = sum(offsets_ms) / n
    abs_mean = sum(abs(o) for o in offsets_ms) / n
    if n < 2:
        std = None
    else:
        var = sum((o - mean) ** 2 for o in offsets_ms) / (n - 1)
        std = math.sqrt(var)
    return {
        "beat_offset_mean_ms": mean,
        "beat_offset_std_ms": std,
        "beat_offset_abs_mean_ms": abs_mean,
    }


def drift_slope(timestamps_min: Sequence[float],
                 baseline_values: Sequence[float]) -> float | None:
    """Slope of `baseline ~ time` in baseline-units per minute. Used
    to flag sensors that drift over a session (e.g. an FSR settling
    after warm-up). Returns None below the 2-sample regression floor
    or when the inputs have mismatched lengths.
    """
    if (len(timestamps_min) < 2
            or len(timestamps_min) != len(baseline_values)):
        return None
    import numpy as np
    xs = np.array(timestamps_min, dtype=float)
    ys = np.array(baseline_values, dtype=float)
    return float(np.polyfit(xs, ys, 1)[0])


def inter_hand_correlation(left_series: Sequence[float],
                            right_series: Sequence[float]) -> float | None:
    """Pearson r between two equal-length, time-aligned force series.
    Spec uses 0-lag - the caller is expected to resample both hands
    onto a common time grid before calling this. Returns None when
    one series is constant (correlation undefined) or when shapes
    don't match.
    """
    if (len(left_series) < 2
            or len(left_series) != len(right_series)):
        return None
    from scipy.stats import pearsonr
    import numpy as np
    L = np.asarray(left_series, dtype=float)
    R = np.asarray(right_series, dtype=float)
    if L.std() == 0 or R.std() == 0:
        return None
    r, _p = pearsonr(L, R)
    return float(r)


def tap_variability_cv(tap_times_s: Sequence[float]) -> float | None:
    """Coefficient of variation of the inter-tap intervals (ITIs).
    Different from the rt_stats CV which measures reaction-time
    consistency; this measures rhythm consistency. Standard metric
    in tremor / Parkinson's tapping studies and applies to stroke
    rehab too. Returns None when fewer than three taps (you need
    two intervals to compute a stdev).
    """
    n = len(tap_times_s)
    if n < 3:
        return None
    itis = [tap_times_s[i + 1] - tap_times_s[i] for i in range(n - 1)]
    mean_iti = sum(itis) / len(itis)
    if mean_iti <= 0:
        return None
    var = (sum((x - mean_iti) ** 2 for x in itis)
           / (len(itis) - 1))
    return math.sqrt(var) / mean_iti


def tempo_entrainment_index(rt_ms_list: Sequence[float],
                              beat_offset_ms_list: Sequence[float]
                              ) -> float | None:
    """Pearson r between per-trial RT and beat-phase offset. A
    correlated patient drifts their RT to follow shifts in beat
    phase (they're tracking the beat); an uncorrelated patient
    just lands near the beat without anticipating it. The two
    lists must be aligned trial-by-trial and equal length. Returns
    None when fewer than two trials or when one series is constant.
    """
    if (len(rt_ms_list) < 2
            or len(rt_ms_list) != len(beat_offset_ms_list)):
        return None
    from scipy.stats import pearsonr
    import numpy as np
    rts = np.asarray(rt_ms_list, dtype=float)
    offsets = np.asarray(beat_offset_ms_list, dtype=float)
    if rts.std() == 0 or offsets.std() == 0:
        return None
    r, _p = pearsonr(rts, offsets)
    return float(r)


def force_individuation_index(target_series: Sequence[float],
                                neighbour_series: Sequence[Sequence[float]]
                                ) -> float | None:
    """How well the target finger fired without dragging the
    others along. Computes mean |Pearson r| between target_series
    and each neighbour, then returns 1 - mean. A score of 1 means
    the patient pressed the target cleanly (no co-activation); 0
    means every finger moved together (stroke-typical mass action).

    Inputs are force traces (or any per-sample amplitude proxy)
    over the press window. The caller picks the press window and
    splits the 8-stream sample into target + 7 neighbours. Returns
    None when fewer than two samples on the target, when no
    neighbours are supplied, or when the target series is constant.
    """
    if len(target_series) < 2 or not neighbour_series:
        return None
    import numpy as np
    from scipy.stats import pearsonr
    target = np.asarray(target_series, dtype=float)
    if target.std() == 0:
        return None
    rs: list[float] = []
    for n_seq in neighbour_series:
        if len(n_seq) != len(target):
            continue
        n_arr = np.asarray(n_seq, dtype=float)
        if n_arr.std() == 0:
            # Flat neighbour - no co-activation by definition.
            rs.append(0.0)
            continue
        r, _p = pearsonr(target, n_arr)
        rs.append(abs(float(r)))
    if not rs:
        return None
    mean_abs_r = sum(rs) / len(rs)
    return 1.0 - mean_abs_r
