"""How far behind the raw force the press detector counts a press, against
the press's rise time.

The detector of app/finger_rehab/hardware/fsr_detector.py is fed linear
ramps from a resting level to a peak, sampled at 200 Hz, with the trigger
at 30 percent of the gap as the study ran it. The raw crossing is the
first sample at or above rest plus the trigger; the count is the
detector's press event. Their difference is the lag the thesis quotes
(12 ms at a 100 ms rise, 20 ms at 200 ms and 57 ms at 400 ms, against
10 to 15 ms on real presses), and this script draws it for Section 3.3.2.

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
RISES = [10, 15, 20, 25, 30, 40, 50, 60, 75, 100, 125, 150, 200, 250, 300, 350, 400]
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
    out: dict[int, dict[int, float]] = {}
    for peak in PEAKS:
        out[peak] = {}
        for rise in RISES:
            lags = [one_press(rise, peak, ph) for ph in PHASES]
            out[peak][rise] = float(np.nanmean(lags))
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
        xs = RISES
        ys = [out[peak][r] for r in xs]
        ax.plot(xs, ys, "-o", ms=3, lw=1.1, color=colours[peak], label=f"peak {peak} counts")
    ax.set_xlabel("rise time, rest to peak (ms)")
    ax.set_ylabel("count lag (ms)")
    ax.set_xlim(0, 410)
    ax.set_ylim(0, None)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    # top left, where every curve is still under 15 ms
    ax.legend(frameon=False, fontsize=8 if small else 10, loc="upper left", bbox_to_anchor=(0.01, 1.02))
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
