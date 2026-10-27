"""Does the device read each press where it happened? A check on the
laboratory's sequence task, asked for by the Curtin EEG laboratory
(22 October 2026).

The game counts a press when the smoothed force crosses a threshold part
way up the push. Two things would make its reaction times wrong. The
detection could lag the real start of the push by an amount that changes
as the player speeds up, and then reaction times measured at the
detection and at the force onset would drift apart across the blocks
instead of running parallel. Or a light touch could cross the threshold,
fall back and be followed by the real push, so the reaction time would be
taken from the touch. For every flash this takes the counted press (the
first press before the next flash), finds where its push began on the
board's own force stream with the software's onset detector (the one
self_tests.py uses), and records how long the press was held and whether
the same finger pressed again straight after it. It also records how late
the computer stamped the force samples, the USB part of a reaction time,
and how fast each push rose (its peak over the time from onset to peak),
since a threshold on a steeper rise is crossed sooner.

    cd analysis
    python3 press_check.py --out DIR LABEL=BLOCK_FOLDER [LABEL=BLOCK_FOLDER ...]

Writes DIR/press_check.json and DIR/press_check.png.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sequence_task import SEGMENTS, lab_kept, script_table  # noqa: E402

REPRESS_S = 0.3        # the same finger again this soon after letting go
WEAK_SHARE = 0.5       # a first press below half the person's usual peak


def presses(folder: Path) -> pd.DataFrame:
    """One row per flash: the counted press, its onset on the board's
    sample grid, how long it was held, its peak force above rest, and
    whether the same finger pressed again within REPRESS_S of letting go."""
    from finger_rehab.analytics.signal import TIMING_RUN_GAP_S, press_onset
    from finger_rehab.hardware.eeg_trigger import PRESS_STAMP_TOL_S, read_force_streams
    meta = json.loads((folder / "metadata.json").read_text(encoding="utf-8"))
    resting = (meta.get("calibration") or {}).get("resting") or [0.0] * 8
    ev = pd.read_csv(folder / "raw.csv", usecols=["event", "lane", "t_perf"], low_memory=False)
    ev = ev[ev.event.isin(["stim", "press", "release"])].dropna(subset=["t_perf"]).reset_index(drop=True)
    st = next(iter(read_force_streams(folder / "raw.csv").values()))
    t, grid = st["t"], st["t"] - st["late"] / 1000.0
    breaks = np.flatnonzero(np.diff(t) > TIMING_RUN_GAP_S) + 1
    stims = ev[ev.event == "stim"].reset_index(drop=True)
    rows = []
    for i, s in stims.iterrows():
        t_end = stims.t_perf[i + 1] if i + 1 < len(stims) else s.t_perf + 3.0
        win = ev[(ev.t_perf > s.t_perf) & (ev.t_perf < t_end)]
        pr = win[win.event == "press"]
        row = {"trial": i, "lane": np.nan, "lag_ms": np.nan, "held_ms": np.nan, "peak": np.nan,
               "rise_ms": np.nan, "repress": False, "repress_peak": np.nan}
        if len(pr):
            p = pr.iloc[0]
            lane = int(p.lane)
            row["lane"] = lane
            rel = ev[(ev.event == "release") & (ev.lane == lane) & (ev.t_perf > p.t_perf)]
            t_rel = float(rel.t_perf.iloc[0]) if len(rel) else np.nan
            row["held_ms"] = (t_rel - p.t_perf) * 1000.0
            x = st["fsr"][:, lane] - float(resting[lane] if lane < len(resting) else 0.0)
            j = int(np.searchsorted(t, p.t_perf))
            k = min((q for q in (j - 1, j) if 0 <= q < len(t)), key=lambda q: abs(t[q] - p.t_perf))
            if abs(t[k] - p.t_perf) < PRESS_STAMP_TOL_S:
                a = int(breaks[breaks <= k].max()) if (breaks <= k).any() else 0
                b = int(breaks[breaks > k].min()) if (breaks > k).any() else len(t)
                on = None
                if t[b - 1] > t[a]:
                    fs = (b - 1 - a) / (t[b - 1] - t[a])
                    on = press_onset(x[a:b], k - a, fs)
                    if on is not None:
                        row["lag_ms"] = float((grid[k] - grid[a + on]) * 1000.0)
                e = int(np.searchsorted(t, t_rel)) if np.isfinite(t_rel) else k + 40
                held = x[k:max(e, k + 1)]
                row["peak"] = float(np.nanmax(held))
                if on is not None and np.isfinite(held).any():
                    top = k + int(np.nanargmax(held))
                    row["rise_ms"] = float((grid[top] - grid[a + on]) * 1000.0)
                again = ev[(ev.event == "press") & (ev.lane == lane) & (ev.t_perf > p.t_perf)]
                if np.isfinite(t_rel) and len(again) and again.t_perf.iloc[0] - t_rel < REPRESS_S:
                    row["repress"] = True
                    k2 = int(np.searchsorted(t, again.t_perf.iloc[0]))
                    row["repress_peak"] = float(np.nanmax(x[k2:k2 + 60]))
        rows.append(row)
    return pd.DataFrame(rows)


def stamp_lateness(late) -> dict:
    """How late the force samples were stamped by the computer that ran
    the block, in ms against the board's own 5 ms grid
    (sample_grid_lateness): mean, SD, 99th percentile and maximum. A
    serial adapter that hands samples over in bursts stamps them up to a
    burst late; one that passes each sample on at once stamps them within
    a millisecond or two."""
    late = np.asarray(late, dtype=float)
    late = late[np.isfinite(late)]
    return {"samples": int(len(late)), "mean": float(late.mean()), "sd": float(late.std()),
            "p99": float(np.percentile(late, 99)), "max": float(late.max())}


def person(folder: Path) -> dict:
    from finger_rehab.hardware.eeg_trigger import read_force_streams
    s = script_table(folder).reset_index(drop=True)
    p = presses(folder)
    t = s.join(p.drop(columns=["trial"]), how="left")
    t["rt_ms"] = pd.to_numeric(t.rt_ms, errors="coerce")
    t["rt_onset_ms"] = t.rt_ms - t.lag_ms
    t["seg"] = np.where(t.phase == "learning", "Sequence " + t.block.astype(str),
                        np.where(t.phase == "practice", "Practice", "Post-test"))
    ok = lab_kept(t) & t.rt_onset_ms.notna()          # the trials the learning score reads
    usual = float(np.nanmedian(t.peak[t.accuracy == "correct"]))
    weak_first = t.repress & (t.peak < WEAK_SHARE * usual) & (t.repress_peak > t.peak)
    seg = []
    for name in SEGMENTS:
        g = t[ok & (t.seg == name)]
        # counts per ms from the onset to the peak
        rate = g.peak / g.rise_ms.where(g.rise_ms > 0)
        seg.append({"segment": name, "n": int(len(g)), "rt_press_ms": float(g.rt_ms.median()),
                    "rt_onset_ms": float(g.rt_onset_ms.median()), "lag_ms": float(g.lag_ms.median()),
                    "rise_rate": float(rate.median())})
    seg = pd.DataFrame(seg)
    pressed = t.held_ms.notna()
    return {"trials": int(len(t)), "counted_presses": int(pressed.sum()),
            "onset_found": int(t.lag_ms.notna().sum()),
            "onset_share": float(t.lag_ms.notna().sum() / max(1, t.lane.notna().sum())),
            "lag_ms": [float(np.nanpercentile(t.lag_ms, q)) for q in (25, 50, 75)],
            "r_press_onset": float(np.corrcoef(t.rt_ms[ok], t.rt_onset_ms[ok])[0, 1]),
            "lag_vs_segment_spread_ms": float(seg.lag_ms.max() - seg.lag_ms.min()),
            "held_ms_p1": float(np.nanpercentile(t.held_ms, 1)),
            "held_under_60ms": int((t.held_ms < 60).sum()),
            "repress": int(t.repress.sum()), "weak_first_then_real": int(weak_first.sum()),
            "genuine_share": float(1 - weak_first.sum() / max(1, pressed.sum())),
            "stamp_late_ms": stamp_lateness(np.concatenate(
                [st["late"] for st in read_force_streams(folder / "raw.csv").values()])),
            "segments": seg.to_dict(orient="records")}


def figure(people: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(2, 2, figsize=(7.0, 4.6), sharex=True)
    xs = np.arange(len(SEGMENTS))
    for ax, (label, p), c in zip(axes.flat, people.items(), ("C0", "C1", "C2", "C3")):
        seg = pd.DataFrame(p["segments"]).set_index("segment").reindex(SEGMENTS)
        for x0 in (0, len(SEGMENTS) - 1):
            ax.axvspan(x0 - 0.45, x0 + 0.45, color="#fee2e2", zorder=0)
        ax.plot(xs, seg.rt_press_ms, color=c, lw=1.6, marker="o", ms=3, label="at the counted press")
        ax.plot(xs, seg.rt_onset_ms, color=c, lw=1.4, ls=":", marker="o", ms=3, mfc="white",
                label="at the force onset")
        ax.set_title(f"{label}: lag {p['lag_ms'][1]:.0f} ms (IQR {p['lag_ms'][0]:.0f} to {p['lag_ms'][2]:.0f}), "
                     f"r = {p['r_press_onset']:.3f}", fontsize=8.5)
        ax.tick_params(labelsize=7)
        ax.set_xticks(xs)
        ax.set_xticklabels(["Rnd"] + [str(i) for i in range(1, 9)] + ["Rnd"], fontsize=7)
    for ax in axes[:, 0]:
        ax.set_ylabel("Median RT (ms)", fontsize=8)
    for ax in axes[1, :]:
        ax.set_xlabel("Random practice, sequence blocks 1 to 8, random post-test", fontsize=7.5)
    axes[0, 0].legend(fontsize=7, frameon=False, loc="lower left")
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("blocks", nargs="+", help="LABEL=BLOCK_FOLDER")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    people = {}
    for spec in args.blocks:
        label, folder = spec.split("=", 1)
        people[label] = person(Path(folder))
        p = people[label]
        print(f"{label}: onset found {p['onset_found']} of {p['counted_presses']} presses; lag median "
              f"{p['lag_ms'][1]:.1f} ms (IQR {p['lag_ms'][0]:.1f} to {p['lag_ms'][2]:.1f}); r = {p['r_press_onset']:.4f}; "
              f"lag range across segments {p['lag_vs_segment_spread_ms']:.1f} ms; held under 60 ms "
              f"{p['held_under_60ms']}; same finger again within 0.3 s {p['repress']}, of which a weak first "
              f"touch then the real push {p['weak_first_then_real']}; genuine {p['genuine_share']:.3f}")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "press_check.json").write_text(json.dumps(people, indent=1, default=float), encoding="utf-8")
    figure(people, args.out / "press_check.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
