"""Draw the resting middle finger of Section 4.3.2: the pad's raw stream
through the late blocks of the sequence task, the resting level the detector
held, its release margin, the stretches it kept the finger down under the
old rules, and where the rest and hold rules now release it.

    python3 stuck_pad_figure.py "L1=/path/to/session" --out fig.png [--blocks 6 8] [--small]
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from stuck_pad_replay import load  # noqa: E402
from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402

LANE = 1  # the middle finger


def trace(fsr: dict, cal: dict, samples: list, old: bool, rest_s=1.5, hold_s=2.0):
    """Feed the stream and keep, per sample, the detector's baseline, release
    threshold and pressed state for the middle lane, plus every release."""
    rules = (dict(release_frac=0.0, rest_release_s=0.0, hold_max_s=0.0,
                  baseline_down_alpha=float(fsr["baseline_alpha"]))
             if old else dict(rest_release_s=rest_s, hold_max_s=hold_s))
    c = Calibration(num_sensors=4, baseline_alpha=float(fsr["baseline_alpha"]),
                    value_alpha=float(fsr["value_alpha"]),
                    on_delta=list(cal["on_delta"]), off_delta=list(cal["off_delta"]),
                    abs_on_min=list(fsr["abs_on_min"]), abs_off_max=list(fsr["abs_off_max"]),
                    debounce_ms=int(fsr["debounce_ms"]), **rules)
    det = FSRDetector(c)
    det.baseline = [float(x) for x in cal["resting"]]
    releases, presses = [], []
    det.on_press = lambda e: presses.append(e.t_perf) if e.lane == LANE else None
    det.on_release = lambda e: releases.append((e.t_perf, e.reason)) if e.lane == LANE else None
    base, down = [], []
    for t, vals in samples:
        det.feed(t, vals)
        base.append(float(det.baseline[LANE]))
        down.append(bool(det.pressed[LANE]))
    return np.array(base), np.array(down), presses, releases, float(cal["off_delta"][LANE])


def block_bounds(session: Path, stims: list) -> dict:
    """Start and end time of each sub-block from the trial tags, placed on the
    stim events in order (one stim per trial)."""
    with (session / "trials.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    tags = []
    for r in rows:
        parts = r["stimulus"].split(";")
        tags.append(parts[1] + ("" if parts[1] != "learning" else " " + parts[2].replace("b=", "")))
    assert len(tags) == len(stims), (len(tags), len(stims))
    stims = sorted(stims)
    bounds = {}
    for (t, _lane), tag in zip(stims, tags):
        lo, hi = bounds.get(tag, (t, t))
        bounds[tag] = (min(lo, t), max(hi, t))
    return bounds


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("session", help="KEY=path to the session folder")
    ap.add_argument("--out", required=True)
    ap.add_argument("--blocks", nargs=2, type=int, default=(6, 8))
    ap.add_argument("--small", action="store_true", help="paper size")
    ap.add_argument("--nolegend", action="store_true", help="the caption carries the key")
    args = ap.parse_args(argv)
    session = Path(args.session.partition("=")[2])
    fsr, cal, samples, stims, logged, window_s = load(session)
    t = np.array([s[0] for s in samples])
    raw = np.array([s[1][LANE] for s in samples], dtype=float)
    base_old, down_old, _p, rel_old, off = trace(fsr, cal, samples, old=True)
    base_new, down_new, _p, rel_new, _ = trace(fsr, cal, samples, old=False)
    bounds = block_bounds(session, stims)
    t0 = bounds[f"learning {args.blocks[0]}"][0] - 2.0
    t1 = bounds[f"learning {args.blocks[1]}"][1] + 2.0
    sel = (t >= t0) & (t <= t1)
    x = (t[sel] - t0) / 60.0
    # the stretches the old rules held the finger down
    spans = []
    start = None
    for ti, d in zip(t[sel], down_old[sel]):
        if d and start is None:
            start = ti
        elif not d and start is not None:
            spans.append((start, ti))
            start = None
    if start is not None:
        spans.append((start, t[sel][-1]))
    long = [(a, b) for a, b in spans if b - a >= 2.0]
    print(f"{args.blocks[0]} to {args.blocks[1]}: {len(spans)} held stretches, {len(long)} of 2 s or more, "
          f"longest {max((b - a) for a, b in spans):.1f} s; new-rule releases in the window: "
          f"{sum(1 for r, _ in rel_new if t0 <= r <= t1)} ({ {k: sum(1 for r, why in rel_new if t0 <= r <= t1 and why == k) for k in ('lift', 'rest', 'hold')} })")

    fs = 8.5 if args.small else 11.5
    plt.rcParams.update({"font.family": "Times New Roman", "font.size": fs, "axes.labelsize": fs,
                         "xtick.labelsize": fs, "ytick.labelsize": fs, "legend.fontsize": fs - 0.5})
    # the paper prints it 8.0 cm wide, so a 3.25 in canvas keeps its 8.5 pt text near 8 pt
    fig, ax = plt.subplots(figsize=((3.25, 1.6) if args.nolegend else (3.4, 1.95)) if args.small else (6.6, 2.9))
    resting = float(cal["resting"][LANE])
    ax.plot(x, raw[sel], color="0.55", lw=0.6, label="raw counts")
    ax.plot(x, base_old[sel] + off, color="#1f4e8c", lw=1.0, ls="--", label="release margin (old rules)")
    ax.axhline(resting, color="k", lw=0.8, ls=":", label="resting level at calibration")
    for k, (a, b) in enumerate(long):
        ax.axvspan((a - t0) / 60.0, (b - t0) / 60.0, color="#d8a7a7", alpha=0.55, lw=0,
                   label="held down 2 s or more (old rules)" if k == 0 else None)
    rel = [(r - t0) / 60.0 for r, why in rel_new if t0 <= r <= t1 and why in ("rest", "hold")]
    ax.plot(rel, [resting - 0.06 * (raw[sel].max() - resting)] * len(rel), marker="^", ls="none",
            color="#c0392b", ms=4 if args.small else 5, label="released by the new rules")
    for tag, (a, b) in bounds.items():
        if tag.startswith("learning") and args.blocks[0] <= int(tag.split()[1]) <= args.blocks[1]:
            ax.annotate(f"block {tag.split()[1]}", xy=(((a + b) / 2 - t0) / 60.0, 1.0), xycoords=("data", "axes fraction"),
                        ha="center", va="bottom", fontsize=fs - 1)
            ax.axvline((a - t0) / 60.0, color="0.85", lw=0.6)
    ax.set_xlim(0, (t1 - t0) / 60.0)
    ax.set_ylim(resting - 25, max(resting + 60, np.percentile(raw[sel], 99.5) + 10))
    ax.set_xlabel("Time from the start of block %d (minutes)" % args.blocks[0])
    ax.set_ylabel("Counts")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    if not args.nolegend:
        # a legend row wider than the canvas widens the saved image and shrinks the print
        h, l = ax.get_legend_handles_labels()
        fig.legend(h, l, loc="lower center", ncol=2 if args.small else 3, frameon=False, fontsize=fs - 1.5,
                   handlelength=1.6, columnspacing=1.2, bbox_to_anchor=(0.5, -0.12))
    fig.tight_layout()
    fig.savefig(args.out, dpi=500, bbox_inches="tight")
    w_in = plt.imread(args.out).shape[1] / 250
    print(f"saved width {w_in:.2f} in (canvas {fig.get_figwidth():.2f})")
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
