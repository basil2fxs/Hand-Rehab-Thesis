"""The press-count rule of 3 November 2026 replayed over the sequence task's
force streams: does counting on the second raw sample in a row at or above
the trigger count the presses the smoothed rule counted, how far behind the
raw crossing is each count, and what does it do to each learning score?

Each session is replayed twice through the game's own detector with the
rules it ran (count_lag.py checks that this reproduces every logged press),
once counting on the smoothed value as it did and once on the raw stream.
A raw count is matched to the smoothed count on the same finger within
50 ms. The learning score is rescored from each set of presses by the
laboratory's planned rule (stuck_pad_replay.rescore). Press to log adds
each session's latest sample stamp (press_check.json) to the slowest count.

    cd analysis
    python3 count_rule_replay.py --press-check PRESS_CHECK.json --out DIR LABEL=BLOCK_FOLDER ...

Writes DIR/count_rule_replay.json.
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
from stuck_pad_replay import load, rescore  # noqa: E402

# the development laptop's USB adapter hands samples over in bursts of up
# to about 21 ms (Table 16 of the thesis); the laboratory computer's own
# stamps come from press_check.json
LAPTOP_BURST_MS = 21.0


def replay(fsr: dict, cal: dict, samples: list, count_on: str) -> list:
    """Every press as (time, lane, samples since the raw force crossed the
    trigger it was counted against), under the rules the session ran but
    for the count rule."""
    c = Calibration(num_sensors=4, baseline_alpha=float(fsr["baseline_alpha"]),
                    value_alpha=float(fsr["value_alpha"]),
                    on_delta=list(cal["on_delta"]), off_delta=list(cal["off_delta"]),
                    abs_on_min=list(fsr["abs_on_min"]), abs_off_max=list(fsr["abs_off_max"]),
                    debounce_ms=int(fsr["debounce_ms"]), release_frac=0.0, rest_release_s=0.0,
                    hold_max_s=0.0, baseline_down_alpha=float(fsr["baseline_alpha"]),
                    count_on=count_on, count_samples=2)
    det = FSRDetector(c)
    det.baseline = [float(x) for x in cal["resting"]]   # primed as the engine primes it
    fired: list = []
    det.on_press = lambda e: fired.append((e.t_perf, e.lane))
    above, crossed, out = [False] * 4, [None] * 4, []
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
            out.append((tp, lane, None if crossed[lane] is None else n - crossed[lane]))
    return out


def match(old: list, new: list, within_s: float = 0.05) -> tuple[list, int, int]:
    """Pair each smoothed count with the nearest unpaired raw count on its
    finger within 50 ms: the raw count's lead in ms, the presses the raw
    rule loses and those it adds."""
    used: set[int] = set()
    lead, lost = [], 0
    for t, lane, _ in old:
        near = [(abs(t2 - t), k) for k, (t2, l2, _) in enumerate(new)
                if l2 == lane and k not in used and abs(t2 - t) < within_s]
        if near:
            _, k = min(near)
            used.add(k)
            lead.append((t - new[k][0]) * 1000.0)
        else:
            lost += 1
    return lead, lost, len(new) - len(used)


def person(folder: Path, stamp_max_ms: float) -> dict:
    fsr, cal, samples, stims, logged, window_s = load(folder)
    old = replay(fsr, cal, samples, "smoothed")
    new = replay(fsr, cal, samples, "raw")
    step_ms = float(np.median(np.diff([t for t, _ in samples]))) * 1000.0
    reproduced = sum(1 for (t, lane, _) in old if any(abs(t - tl) < 0.01 and lane == ll for tl, ll in logged))
    lead, lost, added = match(old, new)
    # the counted press of each flash, as count_lag.py reads it: the first
    # press after the flash and before the next (a re-press held back by the
    # 100 ms debounce is counted late under either rule, so is left out here)
    stims = sorted(stims)

    def per_flash(events: list) -> np.ndarray:
        times = np.array([t for t, _, _ in events])
        out = []
        for i, (ts, _) in enumerate(stims):
            t_end = stims[i + 1][0] if i + 1 < len(stims) else ts + 3.0
            k = int(np.searchsorted(times, ts, side="right"))
            if k < len(events) and events[k][0] < t_end and events[k][2] is not None:
                out.append(events[k][2] * step_ms)
        return np.array(out)

    lag_old, lag_new = per_flash(old), per_flash(new)
    s_old = rescore(folder, stims, [(t, lane) for t, lane, _ in old], window_s)
    s_new = rescore(folder, stims, [(t, lane) for t, lane, _ in new], window_s)
    return {"logged": len(logged), "old_reproduces_logged": reproduced,
            "old": len(old), "new": len(new), "matched": len(lead), "lost": lost, "added": added,
            "lead_ms": {"median": float(np.median(lead)), "p95": float(np.percentile(lead, 95)),
                        "max": float(np.max(lead))},
            "lag_old_ms": {"median": float(np.median(lag_old)), "max": float(lag_old.max())},
            "lag_new_ms": {"median": float(np.median(lag_new)), "max": float(lag_new.max()),
                           "share_one_sample": float(np.mean(np.isclose(lag_new, step_ms, atol=0.6)))},
            "score_old_ms": s_old["score"], "score_new_ms": s_new["score"],
            "score_new_ci": s_new["ci"],
            "log_lab_old_ms": float(lag_old.max() + stamp_max_ms),
            "log_lab_new_ms": float(lag_new.max() + stamp_max_ms),
            "log_laptop_new_ms": float(lag_new.max() + LAPTOP_BURST_MS)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("blocks", nargs="+", help="LABEL=BLOCK_FOLDER")
    ap.add_argument("--press-check", type=Path, required=True, help="press_check.json of the same blocks")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    pc = json.loads(args.press_check.read_text(encoding="utf-8"))
    people = {}
    for spec in args.blocks:
        label, folder = spec.split("=", 1)
        p = people[label] = person(Path(folder), pc[label]["stamp_late_ms"]["max"])
        print(f"{label}: smoothed {p['old']} presses ({p['old_reproduces_logged']} of {p['logged']} logged), "
              f"raw {p['new']}: {p['matched']} matched, {p['lost']} lost, {p['added']} added; "
              f"raw count leads by a median {p['lead_ms']['median']:.1f} ms (max {p['lead_ms']['max']:.1f}); "
              f"behind the raw crossing {p['lag_old_ms']['median']:.1f} -> {p['lag_new_ms']['median']:.1f} ms "
              f"(max {p['lag_old_ms']['max']:.1f} -> {p['lag_new_ms']['max']:.1f}); "
              f"score {p['score_old_ms']:.1f} -> {p['score_new_ms']:.1f} ms")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "count_rule_replay.json").write_text(json.dumps(people, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
