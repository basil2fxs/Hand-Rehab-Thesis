"""How far behind the raw force the press detector counts a press, against
the press's rise time.

The detector of app/finger_rehab/hardware/fsr_detector.py is fed linear
ramps from a resting level to a peak, sampled at 200 Hz, with the trigger
at 30 percent of the gap as the study ran it. The raw crossing is the
first sample at or above rest plus the trigger, the trigger as it stood
before the push; the count is the detector's press event. Their
difference is the count lag, which includes the baseline creeping up
behind a slow push.

Two detectors are drawn, each as a line for a 70-count gap over the
band its 40, 70 and 150-count gaps span. A band steps where the creeping
trigger passes a whole count, since the raw force must then reach the next
one. The study's: the count on the smoothed value
and a baseline time constant of about 10 s (baseline_alpha 0.0005, the
config every session ran), whose lag grows from 10 ms at a 100 ms rise
to about 20 ms at 1 s and 36 to 86 ms at 2 to 3 s; every ramp is
counted. And the count since 3 November: the second raw sample in a row
over the trigger, one sample after the raw force crosses it, though on a
slow rise the creeping baseline still lifts the trigger. The
table also prints the code's default baseline_alpha of 0.02 (0.25 s),
which the config overrides: on it the baseline follows a slow push up
and no ramp over 0.8 s is counted, which is why a test now holds the
code's defaults to the config.

Run from the repository root:
    python3 analysis/detector_lag_vs_rise.py [--out figure.png] [--small]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "app"))
from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402

FS = 200.0
REST = 255
RISES = [10, 20, 30, 50, 75, 100, 150, 200, 300, 400, 500, 600, 700, 750, 800, 900, 1000,
         1250, 1500, 1750, 2000, 2500, 3000]
PEAKS = [40, 70, 150]
PHASES = np.linspace(0.0, 1.0 / FS, 20, endpoint=False)
# the three detectors: (rule, baseline_alpha)
DETECTORS = {"study": ("smoothed", 0.0005), "old default": ("smoothed", 0.02), "now": ("raw", 0.0005)}


def one_press(rise_ms: float, peak: int, phase_s: float, rule: str = "smoothed",
              alpha: float = 0.0005, trigger_frac: float = 0.3) -> float:
    on = max(1, int(round(trigger_frac * peak)))
    cal = Calibration(on_delta=[on] * 4, off_delta=[max(1, on - 10)] * 4,
                      abs_on_min=[0] * 4, abs_off_max=[4095] * 4,
                      baseline_alpha=alpha, count_on=rule)
    det = FSRDetector(cal)
    det.baseline = [float(REST)] * 4
    counted: list[float] = []
    det.on_press = lambda e: counted.append(e.t_perf)
    t0 = 2.0 + phase_s
    rise_s = rise_ms / 1000.0
    n = int((t0 + rise_s + 0.5) * FS) + 1
    raw_cross = None
    for k in range(n):
        t = k / FS
        if t < t0:
            v = REST
        elif t < t0 + rise_s:
            v = REST + peak * (t - t0) / rise_s
        else:
            v = REST + peak
        v = int(round(v))
        # the crossing of the trigger as it stood at rest: the baseline
        # creeping up behind a slow push delays the count past it, which is
        # the delay a slow press meets
        if raw_cross is None and v >= REST + on:
            raw_cross = t
        det.feed(t, (v, REST, REST, REST))
        if counted:
            break
    if not counted or raw_cross is None:
        return float("nan")
    return (counted[0] - raw_cross) * 1000.0


def table() -> dict[str, dict[int, dict[int, float]]]:
    """Mean lag over the phases per detector, peak and rise; nan where no
    phase of that ramp was counted."""
    out: dict[str, dict[int, dict[int, float]]] = {}
    for name, (rule, alpha) in DETECTORS.items():
        out[name] = {}
        for peak in PEAKS:
            out[name][peak] = {}
            for rise in RISES:
                lags = np.array([one_press(rise, peak, ph, rule, alpha) for ph in PHASES])
                ok = np.isfinite(lags)
                out[name][peak][rise] = float(np.mean(lags[ok])) if ok.any() else float("nan")
    return out


def draw(out: dict, path: Path, small: bool = False) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fs = 8 if small else 10
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
                         "font.size": fs})
    # canvas = print width: 13.8 cm in the thesis (10 pt), 8.8 cm in the paper (8 pt)
    fig, ax = plt.subplots(figsize=(3.45, 2.0) if small else (5.43, 1.55))
    xs = np.array(RISES, dtype=float)
    lo = np.nanmin([[out["study"][p][r] for r in RISES] for p in PEAKS], axis=0)
    hi = np.nanmax([[out["study"][p][r] for r in RISES] for p in PEAKS], axis=0)
    band_s = ax.fill_between(xs, lo, hi, color="#93c5fd", alpha=0.6, lw=0)
    line_s, = ax.plot(xs, [out["study"][70][r] for r in RISES], "-", lw=1.4, color="#1d4ed8")
    lo_n = np.nanmin([[out["now"][p][r] for r in RISES] for p in PEAKS], axis=0)
    hi_n = np.nanmax([[out["now"][p][r] for r in RISES] for p in PEAKS], axis=0)
    band_n = ax.fill_between(xs, lo_n, hi_n, color="#86efac", alpha=0.45, lw=0)
    line_n, = ax.plot(xs, [out["now"][70][r] for r in RISES], "-", lw=1.4, color="#15803d")
    ax.set_xlabel("rise time, rest to peak (ms)")
    ax.set_ylabel("count lag (ms, log)")
    ax.set_yscale("log")
    # four labels, so the log axis stays readable at 1.55 in
    ax.set_yticks([5, 10, 30, 100])
    ax.set_yticklabels(["5", "10", "30", "100"])
    ax.yaxis.set_minor_locator(matplotlib.ticker.NullLocator())
    ax.set_xlim(0, 3050)
    ax.set_ylim(3.5, 260)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    # one row across the top, above every curve; each key is the line over its band
    ax.legend([(band_s, line_s), (band_n, line_n)], ["as the study ran", "two raw samples (now)"], frameon=False, fontsize=fs, loc="upper left", bbox_to_anchor=(0.0, 1.08),
              ncol=2, handlelength=1.6, handletextpad=0.5, columnspacing=1.2)
    fig.tight_layout(pad=0.3)
    fig.savefig(path, dpi=500)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--small", action="store_true")
    a = ap.parse_args()
    out = table()
    for name in DETECTORS:
        print(name)
        print("  rise ms  " + "  ".join(f"peak {p:>3}" for p in PEAKS))
        for rise in RISES:
            print(f"  {rise:>7}  " + "  ".join(f"{out[name][p][rise]:8.1f}" for p in PEAKS))
    if a.out:
        draw(out, a.out, a.small)
        print("wrote", a.out)
