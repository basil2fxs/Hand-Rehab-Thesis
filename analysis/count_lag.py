"""How long after the raw force crosses the trigger does the detector count
a press? The smoothing makes the count wait until the smoothed force
crosses too. This replays a session's force stream through the detector
under the rules that ran (stuck_pad_replay checks that this reproduces the
logged presses) and, for the counted press of every flash, measures the
samples from the raw stream's last upward crossing of the press threshold
to the count, against the same threshold the detector used at that sample.

    cd analysis
    python3 count_lag.py --out DIR LABEL=BLOCK_FOLDER [LABEL=BLOCK_FOLDER ...]

Writes DIR/count_lag.json.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402
from sequence_task import SEGMENTS, script_table  # noqa: E402
from stuck_pad_replay import load  # noqa: E402


def replay_lags(fsr: dict, cal: dict, samples: list) -> list:
    """Every press of the replay as (time, lane, samples from the raw
    crossing to the count)."""
    c = Calibration(num_sensors=4, baseline_alpha=float(fsr["baseline_alpha"]),
                    value_alpha=float(fsr["value_alpha"]),
                    on_delta=list(cal["on_delta"]), off_delta=list(cal["off_delta"]),
                    abs_on_min=list(fsr["abs_on_min"]), abs_off_max=list(fsr["abs_off_max"]),
                    debounce_ms=int(fsr["debounce_ms"]), release_frac=0.0, rest_release_s=0.0,
                    hold_max_s=0.0, baseline_down_alpha=float(fsr["baseline_alpha"]))
    det = FSRDetector(c)
    det.baseline = [float(x) for x in cal["resting"]]   # primed as the engine primes it
    fired = []
    det.on_press = lambda e: fired.append((e.t_perf, e.lane))
    above = [False] * 4
    crossed = [None] * 4
    out = []
    for n, (t, vals) in enumerate(samples):
        fired.clear()
        det.feed(t, vals)
        for i in range(4):
            base = det.baseline[i] if det.baseline[i] is not None else 0.0
            now = vals[i] >= max(base + c.on_delta[i], c.abs_on_min[i])
            if now and not above[i]:
                crossed[i] = n
            above[i] = now
        for tp, lane in fired:
            if crossed[lane] is not None:
                out.append((tp, lane, n - crossed[lane]))
    return out


def board_period(folder: Path) -> float:
    """The board's sample interval in s, from its grid as press_check reads
    it (arrival stamps less their lateness), not from the stamps alone."""
    from finger_rehab.hardware.eeg_trigger import read_force_streams
    st = next(iter(read_force_streams(folder / "raw.csv").values()))
    d = np.diff(st["t"] - st["late"] / 1000.0)
    return float(np.median(d[np.isfinite(d) & (d > 0) & (d < 0.02)]))


def person(folder: Path) -> dict:
    fsr, cal, samples, stims, logged, _ = load(folder)
    lags = replay_lags(fsr, cal, samples)
    step = board_period(folder)
    s = script_table(folder).reset_index(drop=True)
    stims = sorted(stims)
    assert len(s) == len(stims), (len(s), len(stims))
    seg = np.where(s.phase == "learning", "Sequence " + s.block.astype(str),
                   np.where(s.phase == "practice", "Practice", "Post-test"))
    # the counted press of each flash: the first press after it, before the next flash
    times = np.array([t for t, _, _ in lags])
    per = []
    for i, (ts, _) in enumerate(stims):
        t_end = stims[i + 1][0] if i + 1 < len(stims) else ts + 3.0
        k = int(np.searchsorted(times, ts, side="right"))
        if k < len(lags) and lags[k][0] < t_end:
            per.append((seg[i], lags[k][2] * step * 1000.0))
    ms = np.array([x for _, x in per])
    by_seg = {name: float(np.median([x for g, x in per if g == name])) for name in SEGMENTS
              if any(g == name for g, _ in per)}
    matched = sum(1 for (t, lane, _) in lags if any(abs(t - tl) < 0.01 and lane == ll for tl, ll in logged))
    return {"replayed_presses": len(lags), "logged_presses": len(logged), "matched_logged": matched,
            "sample_ms": step * 1000.0, "counted": int(len(ms)),
            "lag_ms": {"p5": float(np.percentile(ms, 5)), "p25": float(np.percentile(ms, 25)),
                       "median": float(np.median(ms)), "p75": float(np.percentile(ms, 75)),
                       "p95": float(np.percentile(ms, 95)), "max": float(ms.max())},
            "by_segment_median_ms": by_seg}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("blocks", nargs="+", help="LABEL=BLOCK_FOLDER")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    people = {}
    for spec in args.blocks:
        label, folder = spec.split("=", 1)
        p = people[label] = person(Path(folder))
        q = p["lag_ms"]
        print(f"{label}: replay {p['replayed_presses']} presses, {p['matched_logged']} of {p['logged_presses']} logged "
              f"matched; {p['counted']} counted presses, raw crossing to count median {q['median']:.1f} ms "
              f"(IQR {q['p25']:.1f} to {q['p75']:.1f}, 95th percentile {q['p95']:.1f}, max {q['max']:.1f})")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "count_lag.json").write_text(json.dumps(people, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
