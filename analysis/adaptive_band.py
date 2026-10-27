"""The adaptive controller against its 65 to 80 percent band, measured on
the headless player the band-keeping tests use: pace and trailing hit rate
trial by trial for a 280 ms hand under the old 140 BPM ceiling and the 180
BPM ceiling, one real Adaptive block laid over them, and a sweep of player
speeds giving the trial at which each settles back into the band.

    python3 adaptive_band.py --real /path/to/P01_..._adaptive --out fig.png [--small]
"""
from __future__ import annotations

import argparse
import csv
import random
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine  # noqa: E402

WINDOW = 30  # trials in the trailing hit rate, as the band-keeping tests read it


def drive(mean_rt: float, sd: float, seed: int, bpm_max: float, n_trials: int = 300):
    """The AdaptiveMode loop headless, as test_adaptive.py drives it: record
    then next_bpm once per trial, the shipped settings, a hand pressing at
    mean_rt (sd, clipped to mean -60 to +80 ms)."""
    rng = random.Random(seed)
    eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2, bpm_min=10.0, bpm_max=bpm_max, bpm_step=10.0))
    eng.bpm = 30.0
    hits, bpm = [], []
    for i in range(n_trials):
        window_ms = eng.current_timeout_s * 1000.0
        rt = min(mean_rt + 80.0, max(mean_rt - 60.0, rng.gauss(mean_rt, sd)))
        hit = rt <= window_ms
        q = 1.0 if rt <= 350.0 else 0.75
        bpm.append(eng.bpm)
        eng.record(i % 4, hit=hit, rt_ms=(rt if hit else None), quality=(q if hit else 0.0))
        eng.next_bpm()
        hits.append(1 if hit else 0)
    return np.array(hits), np.array(bpm)


def trailing(hits: np.ndarray, w: int = WINDOW) -> np.ndarray:
    return np.array([hits[max(0, j - w + 1):j + 1].mean() for j in range(len(hits))])


def settle_trial(hits: np.ndarray) -> int | None:
    """Trials played before the trailing rate is at or under 0.85 with the
    rest of the run averaging at or under 0.87 (the tests' criterion, which
    reads 53 for the 280 ms hand at the 180 ceiling)."""
    tr = trailing(hits)
    for j in range(WINDOW, len(hits)):
        if tr[j] <= 0.85 and hits[j:].mean() <= 0.87:
            return j
    return None


def real_block(folder: Path):
    with (folder / "trials.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    hits = np.array([1 if r["feedback"] != "Miss" else 0 for r in rows])
    bpm = np.array([float(r["bpm_at_trial"]) for r in rows])
    return hits, bpm


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--real", help="a real Adaptive block folder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--small", action="store_true")
    args = ap.parse_args(argv)

    runs = {cap: drive(280.0, 25.0, 7, cap) for cap in (140.0, 180.0)}
    for cap, (hits, bpm) in runs.items():
        print(f"280 ms hand, ceiling {cap:.0f}: settles at trial {settle_trial(hits)}, last 100 trials {hits[-100:].mean():.2f}, "
              f"pace at the end {bpm[-1]:.0f} BPM")
    speeds = list(range(250, 501, 50))
    seeds = (1, 2, 3, 4, 5)
    sweep = {}
    for mean_rt in speeds:
        rows = []
        for seed in seeds:
            hits, bpm = drive(float(mean_rt), 25.0, seed, 180.0)
            rows.append((settle_trial(hits), hits[-100:].mean(), bpm[-1]))
        sweep[mean_rt] = rows
        s = [r[0] for r in rows]
        print(f"{mean_rt} ms: settles at trials {s}; last-100 hit rate {np.mean([r[1] for r in rows]):.2f} "
              f"({min(r[1] for r in rows):.2f} to {max(r[1] for r in rows):.2f}); pace at the end {np.mean([r[2] for r in rows]):.0f} BPM")

    # canvas = print width (13.8 cm thesis), every text element at 10 pt (8 pt small)
    fs = 8.0 if args.small else 10.0
    plt.rcParams.update({"font.family": "Times New Roman", "font.size": fs, "axes.labelsize": fs,
                         "xtick.labelsize": fs, "ytick.labelsize": fs, "legend.fontsize": fs})
    fig, axes = plt.subplots(1, 3, figsize=(3.4, 1.7) if args.small else (5.43, 2.4),
                             gridspec_kw={"width_ratios": [1.2, 1.2, 1.15]})
    a, b, c = axes
    colours = {140.0: "0.5", 180.0: "#1f4e8c"}
    for cap, (hits, bpm) in runs.items():
        a.plot(np.arange(1, 301), trailing(hits), color=colours[cap], lw=1.3, label=f"280 ms hand, cap {cap:.0f}")
        b.plot(np.arange(1, 301), bpm, color=colours[cap], lw=1.3)
    if args.real:
        rh, rb = real_block(Path(args.real))
        a.plot(np.arange(1, len(rh) + 1), trailing(rh), color="#c0392b", lw=1.5, label=f"Person 5, {len(rh)} trials, {rh.mean():.2f} overall")
        b.plot(np.arange(1, len(rb) + 1), rb, color="#c0392b", lw=1.5)
    a.axhspan(0.65, 0.80, color="#d9ead3", lw=0, label="65 to 80 percent band")
    a.set_ylim(0.3, 1.02)
    a.set_ylabel("Hit rate, last 30 trials")
    a.set_title("(a) Hit rate", loc="left", fontsize=fs)
    b.set_ylabel("Pace (BPM)")
    b.set_title("(b) Pace", loc="left", fontsize=fs)
    for ax in (a, b):
        ax.set_xlabel("Trial")
        ax.set_xlim(0, 300)
    xs, ys = [], []
    for mean_rt, rows in sweep.items():
        for st, _tail, _bpm in rows:
            if st is not None:
                xs.append(mean_rt + np.random.default_rng(mean_rt).uniform(-6, 6))
                ys.append(st)
    c.plot(xs, ys, marker="o", ls="none", color="#1f4e8c", ms=3.5, alpha=0.8)
    med = [np.median([r[0] for r in sweep[s] if r[0] is not None]) if any(r[0] is not None for r in sweep[s]) else np.nan for s in speeds]
    c.plot(speeds, med, color="k", lw=1.2)
    c.set_xlabel("Hand's RT (ms)")
    c.set_ylabel("Trials to settle in band")
    c.set_title("(c) Settling, cap 180", loc="left", fontsize=fs)
    c.set_ylim(0, max(ys) * 1.15 if ys else 100)
    for ax in axes:
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    h, l = a.get_legend_handles_labels()
    # the legend row must stay inside the canvas width, or the tight bounding box widens the
    # saved image and the print shrinks everything with it
    fig.legend(h, l, loc="lower center", ncol=2, frameon=False, fontsize=fs,
               columnspacing=1.2, handlelength=1.6, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.17, 1, 1), w_pad=0.8)
    fig.savefig(args.out, dpi=500)
    w_in = plt.imread(args.out).shape[1] / 250
    print(f"saved width {w_in:.2f} in (canvas {fig.get_figwidth():.2f})")
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
