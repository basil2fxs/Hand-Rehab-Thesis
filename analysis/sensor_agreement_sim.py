"""Would an uncalibrated pad time presses as the calibrated pads did?

The study's pads are SingleTact's calibrated 10 N parts (AUD 192 each with
their board). The standard part, sold uncalibrated with its own board for
AUD 115, is given a 10 percent accuracy class by the maker, and the
comparison planned for it (OV4) needed the bench and the pads, which went
back with the device. Here the study's own presses stand in for the
calibrated pad, and the same force is read again through a model of an
uncalibrated one: its counts per newton off by up to 10 percent either
way, a curve of up to 10 percent of full scale, its own zero, and half as
much noise again. Each pad is calibrated as the device calibrates (rest
and a light press, the trigger at 30 percent of the gap, never under 12
counts) and counted by the game's own detector.

What agrees, press by press: the time each press is counted, and its
peak as a share of that finger's light press. What does not: the peak in
newtons, which the uncalibrated pad gets wrong by its gain.

    cd analysis
    python3 sensor_agreement_sim.py [--json out.json] LABEL=BLOCK_FOLDER ...
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from finger_rehab.hardware.calibration_profile import MIN_DELTA_COUNTS  # noqa: E402
from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402
from stuck_pad_replay import load  # noqa: E402

FULL_SCALE = 512.0            # counts at the rated 10 N
N_PER_COUNT = 10.0 / 512.0


class UncalibratedPad:
    """Counts as an uncalibrated pad would give them for the same force."""

    def __init__(self, rng, zero: float) -> None:
        self.gain = rng.uniform(0.9, 1.1)
        self.curve = rng.uniform(-0.1, 0.1)          # of full scale, at full scale
        self.zero = zero + rng.uniform(-8.0, 8.0)
        self.noise = 0.6                             # added to the pad's own 1.2 to 1.5

    def counts(self, x: np.ndarray, empty: float, rng) -> np.ndarray:
        f = np.asarray(x, float) - empty             # force, in the calibrated pad's counts
        u = self.gain * f + self.curve * f * f / FULL_SCALE
        return np.round(self.zero + u + rng.normal(0.0, self.noise, np.shape(f)))

    def level(self, x: float, empty: float) -> float:
        f = x - empty
        return self.zero + self.gain * f + self.curve * f * f / FULL_SCALE


def detect(samples: list, resting: list, on: list, off: list, fsr: dict) -> list:
    c = Calibration(num_sensors=4, baseline_alpha=float(fsr["baseline_alpha"]),
                    value_alpha=float(fsr["value_alpha"]), on_delta=list(on), off_delta=list(off),
                    abs_on_min=[0] * 4, abs_off_max=[4095] * 4,
                    debounce_ms=int(fsr["debounce_ms"]), count_on="raw", count_samples=2)
    det = FSRDetector(c)
    det.baseline = [float(x) for x in resting]
    out: list = []
    det.on_press = lambda e: out.append([e.t_perf, e.lane, None])
    det.on_release = lambda e: out and next(
        (p.__setitem__(2, e.peak_minus_baseline) for p in reversed(out)
         if p[1] == e.lane and p[2] is None), None)
    for t, vals in samples:
        det.feed(t, vals)
    return [p for p in out if p[2] is not None]


def thresholds(gap: list[float]) -> tuple[list[int], list[int]]:
    on = [int(round(max(MIN_DELTA_COUNTS, 0.3 * g))) for g in gap]
    off = [int(round(max(1.0, min(0.2 * g, o - 10, o * 0.6)))) for g, o in zip(gap, on)]
    return on, off


def one(folder: Path, rng) -> dict:
    fsr, cal, samples, _stims, _logged, _w = load(folder)
    empty, resting, press = cal["empty"], cal["resting"], cal["press"]
    pads = [UncalibratedPad(rng, empty[i]) for i in range(4)]
    t = [s for s, _ in samples]
    raw = np.array([v for _, v in samples], dtype=float)
    unc = np.column_stack([pads[i].counts(raw[:, i], empty[i], rng) for i in range(4)]).astype(int)
    gap_c = [press[i] - resting[i] for i in range(4)]
    rest_u = [pads[i].level(resting[i], empty[i]) for i in range(4)]
    gap_u = [pads[i].level(press[i], empty[i]) - rest_u[i] for i in range(4)]
    on_c, off_c = thresholds(gap_c)
    on_u, off_u = thresholds(gap_u)
    a = detect(samples, resting, on_c, off_c, fsr)
    b = detect(list(zip(t, map(tuple, unc))), rest_u, on_u, off_u, fsr)
    used: set[int] = set()
    dt, pct_c, pct_u, n_c, n_u = [], [], [], [], []
    for ta, lane, pk in a:
        near = [(abs(tb - ta), k) for k, (tb, lb, _) in enumerate(b)
                if lb == lane and k not in used and abs(tb - ta) < 0.05]
        if not near:
            continue
        _, k = min(near)
        used.add(k)
        dt.append((b[k][0] - ta) * 1000.0)
        pct_c.append(100.0 * pk / gap_c[lane])
        pct_u.append(100.0 * b[k][2] / gap_u[lane])
        n_c.append(pk * N_PER_COUNT)
        n_u.append(b[k][2] * N_PER_COUNT)
    dt, dp = np.array(dt), np.array(pct_u) - np.array(pct_c)
    ratio = np.array(n_u) / np.array(n_c)
    return {"presses": len(a), "matched": len(dt), "unmatched_calibrated": len(a) - len(dt),
            "unmatched_uncalibrated": len(b) - len(used),
            "gains": [round(p.gain, 3) for p in pads],
            "timing_ms": {"bias": float(dt.mean()), "loa": [float(dt.mean() - 1.96 * dt.std(ddof=1)),
                                                            float(dt.mean() + 1.96 * dt.std(ddof=1))]},
            "percent_of_light_press": {"bias": float(dp.mean()),
                                       "loa": [float(dp.mean() - 1.96 * dp.std(ddof=1)),
                                               float(dp.mean() + 1.96 * dp.std(ddof=1))]},
            "newtons_ratio": {"median": float(np.median(ratio)), "range": [float(ratio.min()), float(ratio.max())]}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("blocks", nargs="+", help="LABEL=BLOCK_FOLDER")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--pads", type=int, default=5, help="uncalibrated pad sets drawn per block")
    args = ap.parse_args(argv)
    rng = np.random.default_rng(2026)
    res = {}
    for spec in args.blocks:
        label, folder = spec.split("=", 1)
        res[label] = [one(Path(folder), rng) for _ in range(args.pads)]
        for r in res[label]:
            print(f"{label} gains {r['gains']}: {r['matched']} of {r['presses']} presses matched "
                  f"({r['unmatched_uncalibrated']} extra); count {r['timing_ms']['bias']:+.1f} ms "
                  f"(95% limits {r['timing_ms']['loa'][0]:+.1f} to {r['timing_ms']['loa'][1]:+.1f}); "
                  f"percent of the light press {r['percent_of_light_press']['bias']:+.1f} "
                  f"({r['percent_of_light_press']['loa'][0]:+.1f} to {r['percent_of_light_press']['loa'][1]:+.1f}); "
                  f"newtons x{r['newtons_ratio']['median']:.2f} "
                  f"({r['newtons_ratio']['range'][0]:.2f} to {r['newtons_ratio']['range'][1]:.2f})")
    if args.json:
        args.json.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
