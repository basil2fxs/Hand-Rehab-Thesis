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
from stuck_pad_replay import count_rule, load  # noqa: E402
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
                    debounce_ms=int(fsr["debounce_ms"]), **rules, **count_rule(fsr))
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

    # canvas = print width (13.8 cm thesis at 10 pt; 8.0 cm paper at 8 pt), every text element at that size
    fs = 8.0 if args.small else 10.0
    ink, muted, rule = "#111827", "#6b7280", "#d1d5db"
    held, released = "#f2a9a9", "#c0392b"
    plt.rcParams.update({"font.family": "Times New Roman", "font.size": fs, "axes.labelsize": fs,
                         "xtick.labelsize": fs, "ytick.labelsize": fs, "legend.fontsize": fs,
                         "axes.edgecolor": muted, "axes.labelcolor": ink, "xtick.color": muted,
                         "ytick.color": muted, "axes.linewidth": 0.6, "xtick.major.width": 0.6,
                         "ytick.major.width": 0.6})
    fig = plt.figure(figsize=((3.15, 1.85) if args.nolegend else (3.4, 2.2)) if args.small else (5.43, 2.55))
    # the pad's reading on top; below it, on its own strip, what the detector decided under each
    # rule set, so no shading or text sits on the reading
    grid = fig.add_gridspec(2, 1, height_ratios=[3.6, 1.0], hspace=0.14)
    ax = fig.add_subplot(grid[0])
    state = fig.add_subplot(grid[1], sharex=ax)
    resting = float(cal["resting"][LANE])
    ax.plot(x, raw[sel], color="#8a8f98", lw=0.5, zorder=2)
    margin, = ax.plot(x, base_old[sel] + off, color="#1f4e8c", lw=1.0, ls=(0, (4, 2)), zorder=3)
    rest_line = ax.axhline(resting, color=ink, lw=0.7, ls=(0, (1, 1.5)), zorder=3)
    rel = [(r - t0) / 60.0 for r, why in rel_new if t0 <= r <= t1 and why in ("rest", "hold")]
    for a, b in long:
        state.add_patch(plt.Rectangle(((a - t0) / 60.0, 0.68), (b - a) / 60.0, 0.64, facecolor=held,
                                      edgecolor="none", zorder=2))
    marks, = state.plot(rel, [0.0] * len(rel), marker="^", ls="none", color=released,
                        ms=3.6 if args.small else 4.4, mew=0, zorder=3)
    for tag, (a, b) in bounds.items():
        if tag.startswith("learning") and args.blocks[0] <= int(tag.split()[1]) <= args.blocks[1]:
            # each block named above the panel, a few points clear of the press peaks cut at its top
            ax.annotate(f"Block {tag.split()[1]}", xy=(((a + b) / 2 - t0) / 60.0, 1.0),
                        xycoords=("data", "axes fraction"), xytext=(0, 4), textcoords="offset points",
                        ha="center", va="bottom", fontsize=fs, color=ink)
            for panel in (ax, state):
                panel.axvline((a - t0) / 60.0, color=rule, lw=0.6, zorder=1)
    ax.set_xlim(0, (t1 - t0) / 60.0)
    # the axis stops 50 counts above rest, so the resting level and the release margin fill the panel
    ax.set_ylim(resting - 13, resting + 50.0)
    # short enough to stay beside its own panel, clear of the strip's row names
    ax.set_ylabel("Reading (counts)")
    ax.tick_params(axis="x", labelbottom=False, length=0)
    state.set_ylim(-0.6, 1.6)
    state.set_yticks([1.0, 0.0], ["Old rules", "New rules"])
    state.tick_params(axis="y", length=0)
    state.set_xlabel("Time from the start of block %d (minutes)" % args.blocks[0])
    for panel in (ax, state):
        for s in ("top", "right"):
            panel.spines[s].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    state.spines["left"].set_visible(False)
    if not args.nolegend:
        from matplotlib.patches import Patch
        handles = [margin, rest_line, Patch(facecolor=held, edgecolor="none"), marks]
        labels = ["release threshold (old rules)", "resting level at calibration",
                  "finger held down 2 s or more", "finger released"]
        fig.legend(handles, labels, loc="lower center", ncol=2, frameon=False, fontsize=fs,
                   handlelength=1.6, columnspacing=1.6, handletextpad=0.5, bbox_to_anchor=(0.5, 0.0))
    fig.subplots_adjust(left=0.155 if not args.small else 0.22, right=0.985, top=0.9,
                        bottom=0.08 if args.nolegend else 0.385)
    fig.savefig(args.out, dpi=500)
    w_in = plt.imread(args.out).shape[1] / 250
    print(f"saved width {w_in:.2f} in (canvas {fig.get_figwidth():.2f})")
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
