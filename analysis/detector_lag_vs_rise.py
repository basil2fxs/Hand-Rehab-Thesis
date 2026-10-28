"""How far behind the raw force the press detector counts a press, against
the press's rise time.

The detector of app/finger_rehab/hardware/fsr_detector.py is fed linear
ramps from a resting level to a peak, sampled at 200 Hz, with the trigger
at 30 percent of the gap as the study ran it. The raw crossing is the
first sample at or above rest plus the trigger; the count is the
detector's press event. Their difference is the lag the thesis quotes
(12 ms at a 100 ms rise, 20 ms at 200 ms, 57 ms at 400 ms and about
285 ms at 700 ms, against 5 to 10 ms on real presses), and this script
draws it for Section 3.3.2. From about 0.8 s no ramp is counted at all:
the baseline follows the signal until a press is counted, so a slow
push is taken into it before it reaches the trigger (Calibration.
baseline_hold is the fix the pilot tunes; tests/test_baseline_hold.py).

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
RISES = [10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 250, 300, 350, 400,
         450, 500, 550, 600, 650, 700, 750, 775, 800, 900, 1000]
PEAKS = [40, 70, 150]
PHASES = np.linspace(0.0, 1.0 / FS, 20, endpoint=False)


def one_press(rise_ms: float, peak: int, phase_s: float, trigger_frac: float = 0.3) -> float:
    on = max(1, int(round(trigger_frac * peak)))
    cal = Calibration(on_delta=[on] * 4, off_delta=[max(1, on - 10)] * 4,
                      abs_on_min=[0] * 4, abs_off_max=[4095] * 4)
    det = FSRDetector(cal)
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
        if raw_cross is None and v >= REST + on:
            raw_cross = t
        det.feed(t, (v, REST, REST, REST))
    if not counted or raw_cross is None:
        return float("nan")
    return (counted[0] - raw_cross) * 1000.0


def table() -> dict[int, dict[int, float]]:
    """Mean lag over the phases per peak and rise; nan where no phase of
    that ramp was counted."""
    out: dict[int, dict[int, float]] = {}
    for peak in PEAKS:
        out[peak] = {}
        for rise in RISES:
            lags = np.array([one_press(rise, peak, ph) for ph in PHASES])
            out[peak][rise] = float(np.mean(lags[np.isfinite(lags)])) if np.isfinite(lags).any() else float("nan")
    return out


def draw(out: dict[int, dict[int, float]], path: Path, small: bool = False) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
                         "font.size": 8 if small else 10})
    # canvas = print width: 13.8 cm in the thesis (10 pt), 8.8 cm in the paper (8 pt)
    fig, ax = plt.subplots(figsize=(3.45, 2.0) if small else (5.43, 1.55))
    colours = {40: "#94a3b8", 70: "#2563eb", 150: "#0f172a"}
    for peak in PEAKS:
        xs = [r for r in RISES if np.isfinite(out[peak][r])]
        ys = [out[peak][r] for r in xs]
        label = {40: "peak 40", 70: "70", 150: "150 counts"}[peak]
        ax.plot(xs, ys, "-o", ms=2.4, lw=1.1, color=colours[peak], label=label)
    # from the first ramp no peak's press is counted, the band runs to the edge
    never = min(r for r in RISES if all(not np.isfinite(out[p][r]) for p in PEAKS))
    edge = max(r for r in RISES if r < never)
    ax.axvspan((edge + never) / 2, 1050, color="#cbd5e1", alpha=0.55, lw=0)
    ax.text(915, 22, "never\ncounted", ha="center", va="center", fontsize=8 if small else 10, color="#0f172a")
    ax.set_xlabel("rise time, rest to peak (ms)")
    ax.set_ylabel("count lag (ms)")
    ax.set_yscale("log")
    ax.set_yticks([5, 10, 20, 50, 100, 200, 500])
    ax.set_yticklabels(["5", "10", "20", "50", "100", "200", "500"])
    ax.set_xlim(0, 1050)
    ax.set_ylim(4, 700)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    # one row across the top left, where every curve is still under 100 ms
    ax.legend(frameon=False, fontsize=8 if small else 10, loc="upper left", bbox_to_anchor=(0.0, 1.04),
              ncol=3, handlelength=1.4, columnspacing=0.9, handletextpad=0.4)
    fig.tight_layout(pad=0.3)
    fig.savefig(path, dpi=500)
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--small", action="store_true")
    a = ap.parse_args()
    out = table()
    print("rise ms  " + "  ".join(f"peak {p:>3}" for p in PEAKS))
    for rise in RISES:
        print(f"{rise:>7}  " + "  ".join(f"{out[p][rise]:8.1f}" for p in PEAKS))
    if a.out:
        draw(out, a.out, a.small)
        print("wrote", a.out)
