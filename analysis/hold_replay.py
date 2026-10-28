"""Replay the sequence-task force streams with the resting-level hold
(Calibration.baseline_hold) off and on, and run slow ramps through it:
what a hold counts that the study's detector did not, and what it costs.
Section 4.8.4 quotes both.

For each session: the presses counted with the hold off (the detector as
it now ships, with its rest and hold rules) and with each hold, the
presses a hold adds or loses, how far a matched press moves, and the
learning score rescored as the game scores it (stuck_pad_replay.rescore).
For the ramps: the slowest linear rise to each peak that is still counted,
with the trigger at 30 percent of the peak as in detector_lag_vs_rise.py.

    python3 hold_replay.py "L1=/path/to/session" "L2=/path/to/session" [--holds 5 15]
    python3 hold_replay.py --ramps-only
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import stuck_pad_replay as sp  # noqa: E402
from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402

FS = 200.0
REST = 255
PEAKS = [40, 70, 150]
RISES_S = np.round(np.arange(0.5, 3.0001, 0.05), 2)


def replay(fsr: dict, cal: dict, samples: list, hold: float, hold_s: float) -> list:
    c = Calibration(num_sensors=4, baseline_alpha=float(fsr["baseline_alpha"]),
                    value_alpha=float(fsr["value_alpha"]),
                    on_delta=list(cal["on_delta"]), off_delta=list(cal["off_delta"]),
                    abs_on_min=list(fsr["abs_on_min"]), abs_off_max=list(fsr["abs_off_max"]),
                    debounce_ms=int(fsr["debounce_ms"]), rest_release_s=1.5, hold_max_s=2.0,
                    baseline_hold=hold, baseline_hold_s=hold_s)
    det = FSRDetector(c)
    det.baseline = [float(x) for x in cal["resting"]]   # primed as the engine primes it
    events: list = []
    det.on_press = lambda e: events.append((e.t_perf, e.lane))
    for t, vals in samples:
        det.feed(t, vals)
    return events


def match(off: list, on: list, within_s: float = 0.3) -> tuple[list, int, int]:
    """Pair each hold-off press with the nearest unpaired hold-on press on its
    lane within 0.3 s: the shifts in ms, the presses lost and those added."""
    used: set[int] = set()
    shifts, lost = [], 0
    for t, lane in off:
        near = [(abs(t2 - t), k) for k, (t2, l2) in enumerate(on)
                if l2 == lane and k not in used and abs(t2 - t) < within_s]
        if near:
            _, k = min(near)
            used.add(k)
            shifts.append((on[k][0] - t) * 1000.0)
        else:
            lost += 1
    return shifts, lost, len(on) - len(used)


def counted(rise_s: float, peak: int, hold: float, hold_s: float) -> bool:
    on = max(1, int(round(0.3 * peak)))
    cal = Calibration(on_delta=[on] * 4, off_delta=[max(1, on - 10)] * 4,
                      abs_on_min=[0] * 4, abs_off_max=[4095] * 4,
                      baseline_hold=hold, baseline_hold_s=hold_s)
    det = FSRDetector(cal)
    hits: list = []
    det.on_press = lambda e: hits.append(e.t_perf)
    t0 = 2.0
    for k in range(int((t0 + rise_s + 1.0) * FS)):
        t = k / FS
        v = REST if t < t0 else REST + peak * min(1.0, (t - t0) / rise_s)
        det.feed(t, (int(round(v)), REST, REST, REST))
    return bool(hits)


def slowest(peak: int, hold: float, hold_s: float) -> float | None:
    """The slowest rise on the grid that is counted, every faster one counted too."""
    best = None
    for r in RISES_S:
        if not counted(float(r), peak, hold, hold_s):
            break
        best = float(r)
    return best


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sessions", nargs="*", help="KEY=path to a session folder")
    ap.add_argument("--holds", type=float, nargs="+", default=[5.0, 15.0], help="hold levels in counts")
    ap.add_argument("--hold-s", type=float, default=3.0, help="baseline_hold_s, the longest hold")
    ap.add_argument("--ramps-only", action="store_true")
    args = ap.parse_args(argv)
    print(f"Slowest counted rise, trigger at 30 percent of the peak (grid {RISES_S[0]} to {RISES_S[-1]} s):")
    for peak in PEAKS:
        row = [f"off {slowest(peak, 0.0, args.hold_s) or '-'} s"]
        row += [f"hold {h:g} {slowest(peak, h, args.hold_s) or '-'} s" for h in args.holds]
        print(f"  peak {peak:3d} counts: " + ", ".join(row))
    if args.ramps_only:
        return 0
    for item in args.sessions:
        key, _, path = item.partition("=")
        fsr, cal, samples, stims, logged, window_s = sp.load(Path(path))
        off = replay(fsr, cal, samples, 0.0, args.hold_s)
        base = sp.rescore(Path(path), stims, off, window_s)["score"]
        print(f"\n{key}: hold off {len(off)} presses, learning score {base:+.1f} ms")
        for h in args.holds:
            on = replay(fsr, cal, samples, h, args.hold_s)
            shifts, lost, added = match(off, on)
            s = np.array(shifts)
            sc = sp.rescore(Path(path), stims, on, window_s)["score"]
            print(f"  hold {h:g}: {len(on)} presses, {added} added, {lost} lost; a matched press moved "
                  f"median {np.median(s):+.1f} ms ({s.min():+.1f} to {s.max():+.1f}); "
                  f"learning score {sc:+.1f} ms ({sc - base:+.1f})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
