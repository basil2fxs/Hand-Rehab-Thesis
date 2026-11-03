"""The adaptive controller against its 65 to 80 percent band, measured on
the headless player the band-keeping tests use: pace and trailing hit rate
trial by trial for a 280 ms hand under the old 140 BPM ceiling, the 180
BPM ceiling the study ran, and the controller of 3 November 2026 (an
opening climb of 20 percent a hit until the first miss, and a 240 BPM
ceiling), one real Adaptive block laid over them, and a sweep of player
speeds giving each hand's hit rate over a 40-trial block, the study's
block length, as the study ran and as now. The trailing measure of
settle_trial is kept for the tests' 53, but the climb's overshoot can
put misses inside its window, so the block's own hit rate is the one
plotted. Panel (c) reads the 32 trials after the first miss, the
progress report's block length: the climb ends at that miss, so the
window leaves out its near-certain opening hits. The sweep is run again
with the hand's trials varying by 45, 60 and 94 ms (SD), the last the
spread of a real player's single trials in the mixed model, and the
94 ms hand is drawn beside the 25 ms one.

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


def drive(mean_rt: float, sd: float, seed: int, bpm_max: float, n_trials: int = 300,
          gain: float = 1.0):
    """The AdaptiveMode loop headless, as test_adaptive.py drives it: record
    then next_bpm once per trial, the shipped settings but for the ceiling
    and the opening climb (gain 1.0 is the controller the study ran), a hand
    pressing at mean_rt (sd, clipped to 2.4 sd below and 3.2 sd above the
    mean, which is -60 to +80 ms at the tests' 25 ms, and never under 120 ms)."""
    rng = random.Random(seed)
    eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2, bpm_min=10.0, bpm_max=bpm_max, bpm_step=10.0,
                                            fast_start_gain=gain))
    eng.bpm = 30.0
    hits, bpm = [], []
    for i in range(n_trials):
        window_ms = eng.current_timeout_s * 1000.0
        rt = min(mean_rt + 3.2 * sd, max(mean_rt - 2.4 * sd, rng.gauss(mean_rt, sd)))
        rt = max(120.0, rt)
        hit = rt <= window_ms
        q = 1.0 if rt <= 350.0 else 0.75
        bpm.append(eng.bpm)
        eng.record(i % 4, hit=hit, rt_ms=(rt if hit else None), quality=(q if hit else 0.0))
        eng.next_bpm()
        hits.append(1 if hit else 0)
    return np.array(hits), np.array(bpm)


def after_climb(hits: np.ndarray, n: int = 32) -> float:
    """Hit rate over the n trials after the first miss, where the climb ends."""
    first = int(np.argmax(hits == 0)) if (hits == 0).any() else len(hits)
    return float(hits[first + 1:first + 1 + n].mean())


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

    # the controllers: the Semester 1 ceiling, the study's, and the one of 3 November 2026
    ctl = {"cap 140": (140.0, 1.0), "cap 180 (study)": (180.0, 1.0),
           "climb, cap 240 (now)": (240.0, 1.2)}
    runs = {name: drive(280.0, 25.0, 7, cap, gain=g) for name, (cap, g) in ctl.items()}
    for name, (hits, bpm) in runs.items():
        tr = trailing(hits)
        print(f"280 ms hand, {name}: settles at trial {settle_trial(hits)}, first 40 trials {hits[:40].mean():.2f}, "
              f"last 100 trials {hits[-100:].mean():.2f}, highest 30-trial rate after trial 40 {tr[39:].max():.2f} "
              f"(trial {int(tr[39:].argmax()) + 40}), pace at the end {bpm[-1]:.0f} BPM")
    speeds = list(range(250, 501, 50))
    seeds = tuple(range(1, 11))
    sweep = {}
    for key, (cap, g) in (("study", (180.0, 1.0)), ("now", (240.0, 1.2))):
        sweep[key] = {}
        for mean_rt in speeds:
            rows = []
            for seed in seeds:
                hits, bpm = drive(float(mean_rt), 25.0, seed, cap, gain=g)
                rows.append((settle_trial(hits), after_climb(hits), hits[-100:].mean(), bpm[-1], hits[:40].mean()))
            sweep[key][mean_rt] = rows
            f40 = [r[1] for r in rows]
            print(f"{key}, {mean_rt} ms: 32 trials after the first miss {np.mean(f40):.2f} ({min(f40):.2f} to {max(f40):.2f}); "
                  f"first 40 {np.mean([r[4] for r in rows]):.2f}; "
                  f"last 100 {np.mean([r[2] for r in rows]):.2f} ({min(r[2] for r in rows):.2f} to "
                  f"{max(r[2] for r in rows):.2f}); settles at trials {[r[0] for r in rows]}; pace at the end "
                  f"{np.mean([r[3] for r in rows]):.0f} BPM")

    noisy = {}
    for sd in (45.0, 60.0, 94.0):
        noisy[sd] = {}
        for mean_rt in speeds:
            rows = [drive(float(mean_rt), sd, seed, 240.0, gain=1.2)[0] for seed in seeds]
            noisy[sd][mean_rt] = rows
        f40 = [np.mean([after_climb(h) for h in noisy[sd][m]]) for m in speeds]
        l100 = [np.mean([h[-100:].mean() for h in noisy[sd][m]]) for m in speeds]
        print(f"now, trial SD {sd:.0f} ms: 32 trials after the first miss {min(f40):.2f} to {max(f40):.2f} by hand; "
              f"last 100 {min(l100):.2f} to {max(l100):.2f}")

    # canvas = print width (13.8 cm thesis), every text element at 10 pt (8 pt small)
    fs = 8.0 if args.small else 10.0
    plt.rcParams.update({"font.family": "Times New Roman", "font.size": fs, "axes.labelsize": fs,
                         "xtick.labelsize": fs, "ytick.labelsize": fs, "legend.fontsize": fs})
    fig, axes = plt.subplots(1, 3, figsize=(3.4, 1.7) if args.small else (5.43, 2.4),
                             gridspec_kw={"width_ratios": [1.2, 1.2, 1.15]})
    a, b, c = axes
    colours = {"cap 140": "0.6", "cap 180 (study)": "#1f4e8c", "climb, cap 240 (now)": "#2e8b57"}
    for name, (hits, bpm) in runs.items():
        a.plot(np.arange(1, 301), trailing(hits), color=colours[name], lw=1.3, label=name)
        b.plot(np.arange(1, 301), bpm, color=colours[name], lw=1.3)
    if args.real:
        rh, rb = real_block(Path(args.real))
        a.plot(np.arange(1, len(rh) + 1), trailing(rh), color="#c0392b", lw=1.5, label=f"Person 5 ({len(rh)} trials)")
        b.plot(np.arange(1, len(rb) + 1), rb, color="#c0392b", lw=1.5)
    a.axhspan(0.65, 0.80, color="#d9ead3", lw=0, label="65 to 80% band")
    a.set_ylim(0.3, 1.02)
    a.set_ylabel("Hit rate, trailing 30 trials")
    a.set_title("(a) Hit rate", loc="left", fontsize=fs)
    b.set_ylabel("Pace (BPM)")
    b.set_title("(b) Pace", loc="left", fontsize=fs)
    b.set_yticks([50, 100, 140, 180, 240])
    for ax in (a, b):
        ax.set_xlabel("Trial")
        ax.set_xlim(0, 300)
    c.axhspan(0.65, 0.80, color="#d9ead3", lw=0)
    for key, colour, mfc, dx in (("study", "#1f4e8c", "white", -7), ("now", "#2e8b57", "#2e8b57", 7)):
        xs, ys = [], []
        for mean_rt, rows in sweep[key].items():
            jit = np.random.default_rng(mean_rt).uniform(-3, 3, len(rows))
            xs += list(mean_rt + dx + jit)
            ys += [r[1] for r in rows]
        c.plot(xs, ys, marker="o", ls="none", color=colour, mfc=mfc, ms=3.0, alpha=0.8)
        c.plot(speeds, [np.mean([r[1] for r in sweep[key][s]]) for s in speeds], color=colour, lw=1.2)
    xs, ys = [], []
    for mean_rt, rows in noisy[94.0].items():
        jit = np.random.default_rng(mean_rt + 1).uniform(-3, 3, len(rows))
        xs += list(mean_rt + jit)
        ys += [after_climb(h) for h in rows]
    c.plot(xs, ys, marker="^", ls="none", color="#b45309", ms=3.0, alpha=0.8)
    c.plot(speeds, [np.mean([after_climb(h) for h in noisy[94.0][s]]) for s in speeds], color="#b45309", lw=1.2,
           label="climb, trials SD 94 ms (c)")
    c.set_xlabel("Hand's RT (ms)")
    c.set_ylabel("Hit rate, 32 trials")
    c.set_title("(c) After the climb", loc="left", fontsize=fs)
    c.set_ylim(0.5, 1.02)
    c.set_xticks([250, 350, 450])
    for ax in axes:
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    h, l = a.get_legend_handles_labels()
    hc, lc = c.get_legend_handles_labels()
    h, l = h + hc, l + lc
    # the legend row must stay inside the canvas width, or the tight bounding box widens the
    # saved image and the print shrinks everything with it
    fig.legend(h, l, loc="lower center", ncol=3, frameon=False, fontsize=fs,
               columnspacing=1.0, handlelength=1.4, bbox_to_anchor=(0.5, 0.0))
    fig.tight_layout(rect=(0, 0.2, 1, 1), w_pad=0.8)
    fig.savefig(args.out, dpi=500)
    w_in = plt.imread(args.out).shape[1] / 250
    print(f"saved width {w_in:.2f} in (canvas {fig.get_figwidth():.2f})")
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
