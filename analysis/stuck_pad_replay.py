"""Replay a session's force stream through the press detector with and
without the resting-finger rules (Calibration.release_frac,
rest_release_s, hold_max_s) and score each cue as the game did: the
first press from 100 ms before the cue to the end of its response window
answers it. The old rules must reproduce the session's logged presses,
which is the check that the replay is faithful.

    python3 stuck_pad_replay.py "L1=/path/to/session" "L2=/path/to/session"
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402

LANES = ["index", "middle", "ring", "little"]


def load(session: Path):
    meta = json.loads((session / "metadata.json").read_text(encoding="utf-8"))
    fsr = meta["config_snapshot"]["fsr"]
    cal = meta["calibration"]
    samples, stims, presses = [], [], []
    with (session / "raw.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r["event"] == "stim":
                stims.append((float(r["t_perf"]), int(r["lane"])))
            elif r["event"] == "press":
                presses.append((float(r["t_perf"]), int(r["lane"])))
            elif r["event"] == "" and r["sample_idx"]:
                samples.append((float(r["t_perf"]),
                                tuple(int(float(r[f"fsr{k}"])) for k in range(1, 5))))
    samples.sort()
    with (session / "trials.csv").open(encoding="utf-8") as fh:
        first = next(csv.DictReader(fh))
    window_s = float(first.get("timeout_ms") or 2600) / 1000.0
    return fsr, cal, samples, stims, presses, window_s


def replay(fsr: dict, cal: dict, samples: list, old: bool,
           rest_s: float = 0.3, hold_s: float = 2.0) -> tuple[list, Counter]:
    rules = (dict(release_frac=0.0, rest_release_s=0.0, hold_max_s=0.0,
                  baseline_down_alpha=float(fsr["baseline_alpha"]))
             if old else dict(rest_release_s=rest_s, hold_max_s=hold_s))
    c = Calibration(num_sensors=4, baseline_alpha=float(fsr["baseline_alpha"]),
                    value_alpha=float(fsr["value_alpha"]),
                    on_delta=list(cal["on_delta"]), off_delta=list(cal["off_delta"]),
                    abs_on_min=list(fsr["abs_on_min"]), abs_off_max=list(fsr["abs_off_max"]),
                    debounce_ms=int(fsr["debounce_ms"]), **rules)
    det = FSRDetector(c)
    det.baseline = [float(x) for x in cal["resting"]]   # primed as the engine primes it
    events, reasons = [], Counter()
    det.on_press = lambda e: events.append((e.t_perf, e.lane))
    det.on_release = lambda e: reasons.update([e.reason])
    for t, vals in samples:
        det.feed(t, vals)
    return events, reasons


def score(stims: list, presses: list, window_s: float) -> dict:
    """Per cued lane: answered on that lane, answered on another lane (by
    lane), unanswered. The first unassigned press from 0.1 s before the cue
    to the end of the window answers it."""
    presses = sorted(presses)
    used = [False] * len(presses)
    out = {k: {"right": 0, "other": Counter(), "missed": 0} for k in range(4)}
    j = 0
    for t, lane in sorted(stims):
        while j < len(presses) and presses[j][0] < t - 0.1:
            j += 1
        k = j
        while k < len(presses) and presses[k][0] <= t + window_s and used[k]:
            k += 1
        if k < len(presses) and presses[k][0] <= t + window_s:
            used[k] = True
            if presses[k][1] == lane:
                out[lane]["right"] += 1
            else:
                out[lane]["other"][presses[k][1]] += 1
        else:
            out[lane]["missed"] += 1
    return out


def rescore(session: Path, stims: list, presses: list, window_s: float) -> dict:
    """The learning score read from a set of press events, by the sequence
    task's own rules (sequence_task.lab_kept and learning): each cue is
    answered by the first unassigned press from 0.1 s before it to the end
    of its window, which sets the trial's RT and whether it was correct.
    The script's own rt_ms must be reproduced by the logged presses."""
    import numpy as np
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sequence_task as st
    t = st.script_table(session)
    stims = sorted(stims)
    assert len(t) == len(stims), (len(t), len(stims))
    presses = sorted(presses)
    used = [False] * len(presses)
    j = 0
    rt_ms, acc = [], []
    for (ts, lane) in stims:
        while j < len(presses) and presses[j][0] < ts - 0.1:
            j += 1
        k = j
        while k < len(presses) and presses[k][0] <= ts + window_s and used[k]:
            k += 1
        if k < len(presses) and presses[k][0] <= ts + window_s:
            used[k] = True
            rt = (presses[k][0] - ts) * 1000.0
            rt_ms.append(rt)
            # a press before the flash is the script's anticipation, which the
            # laboratory's kept-trial rule leaves out
            acc.append(("anticipatory_" if rt < 0 else "") + ("correct" if presses[k][1] == lane else "incorrect"))
        else:
            rt_ms.append(np.nan)
            acc.append("miss")
    gap = float(np.nanmedian(np.abs(np.array(rt_ms) - t.rt_ms.to_numpy(float))))
    t = t.copy()
    t["rt_ms"] = rt_ms
    t["accuracy"] = acc
    keep = st.lab_kept(t)
    out = st.learning(t, keep, np.random.default_rng(st.SEED))
    return {"score": out["post_minus_block8_ms"], "post": out["post_ms"], "block8": out["block8_ms"],
            "rt_match_ms": gap, "kept": int(keep.sum())}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sessions", nargs="+", help="KEY=path to a session folder")
    ap.add_argument("--rest", type=float, default=1.5, help="rest_release_s for the new rules")
    ap.add_argument("--hold", type=float, default=2.0, help="hold_max_s for the new rules")
    args = ap.parse_args(argv)
    for item in args.sessions:
        key, _, path = item.partition("=")
        fsr, cal, samples, stims, logged, window_s = load(Path(path))
        old_events, _ = replay(fsr, cal, samples, old=True)
        new_events, reasons = replay(fsr, cal, samples, old=False, rest_s=args.rest, hold_s=args.hold)
        matched = sum(1 for (t, l) in old_events
                      if any(abs(t - tl) < 0.01 and l == ll for tl, ll in logged))
        print(f"\n{key}: {len(samples)} samples, {len(stims)} cues, logged presses {len(logged)}")
        print(f"  old rules replay: {len(old_events)} presses, {matched} match a logged press within 10 ms")
        changed = len(new_events) - sum(1 for e in new_events if e in set(old_events))
        print(f"  new rules (rest {args.rest} s, hold {args.hold} s): {len(new_events)} presses, {changed} not in the old set; releases by reason {dict(reasons)}")
        for name, ev in (("old", old_events), ("new", new_events)):
            sc = rescore(Path(path), stims, ev, window_s)
            print(f"  {name} learning score (post-test minus block 8): {sc['score']:+.0f} ms "
                  f"(medians {sc['post']:.0f} and {sc['block8']:.0f}, {sc['kept']} kept trials; "
                  f"replay RT against the script's rt_ms, median gap {sc['rt_match_ms']:.1f} ms)")
            s = score(stims, ev, window_s)
            for lane in range(4):
                o = s[lane]
                other = ", ".join(f"{LANES[k]} {n}" for k, n in sorted(o["other"].items()))
                print(f"  {name} {LANES[lane]:6s} cues: right {o['right']:3d}, missed {o['missed']:3d}, "
                      f"other {sum(o['other'].values()):3d} ({other})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
