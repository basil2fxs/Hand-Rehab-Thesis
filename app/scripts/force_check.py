"""Bench check of the newton scale with known masses.

The game reports force in newtons from the SingleTact factory
calibration: the pads are CS8-10N (calibrated 8 mm, 10 N), the manual
gives Load (N) = (counts - baseline) / 512 x rating, so one count is
10 / 512 = 0.01953 N and a newton is 51.2 counts. That constant is
config fsr.force_calibration_n_per_count. This script puts known
masses on each pad and checks that the board's counts agree with it,
so the thesis can say the newton figures were verified on this rig
rather than taken from a datasheet.

    python3 scripts/force_check.py                  every pad, report only
    python3 scripts/force_check.py --pad index      one pad
    python3 scripts/force_check.py --masses 100,200,500,1000
    python3 scripts/force_check.py --port /dev/cu.usbserial-140
    python3 scripts/force_check.py --warmup 0       skip the settle wait
    python3 scripts/force_check.py --write-slope --config-out my_rig.yaml

WHAT YOU NEED
  Calibration weights if the lab has them, otherwise any objects
  weighed on a kitchen scale to +/- 1 g (1 g is 0.01 N, half a
  count). The load must reach the pad through a rigid flat puck no
  wider than the 8 mm sensing area (a printed 7 mm disc or the head
  of a flat-ended M6 bolt), otherwise part of the mass lands on the
  housing and the pad reads low. Nothing over 2 kg: the maker's
  overload limit is three times full scale.

WHAT IT DOES, per pad
  1. Warm-up, 60 s unloaded. The sensor registers its own baseline
     unloaded at power-on and its drift (2 percent of full scale per
     minute at half load) settles.
  2. Tare: a 5 s mean of the unloaded pad.
  3. Each mass ascending: place, 3 s settle, 2 s average (400
     samples, mean and SD), remove, 2 s, record the return to tare.
  4. The same masses descending, for hysteresis.
  5. A 60 s hold at the drift mass (500 g) for drift.

ACCEPTANCE, from the CS8-10N product page limits
  every point within +/- 20 counts of expected (4 percent of full
  scale, 0.4 N); least-squares slope within +/- 2 percent of 51.2
  counts per newton; ascending against descending at 500 g within 20
  counts; drift over the 60 s hold at most 10 counts; return to tare
  within 10 counts. A slope near 11.4 counts per newton is the
  signature of a 45 N part and is reported as a part mismatch rather
  than a failure.

OUTPUT
  A printed table and verdict per pad, and a JSON record in
  config/calibration/force_check_<date>.json. Nothing is written
  under sessions/ and config/user_settings.yaml is never touched:
  --write-slope only writes the yaml you name with --config-out.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FINGERS = ("index", "middle", "ring", "pinky")
BAUD = 115200
G = 9.81                       # m/s^2; Perth is 0.2 percent under, below the linearity spec
SENSOR_RATING_N = 10.0
COUNTS_FULL_SCALE = 512.0
NOMINAL_N_PER_COUNT = SENSOR_RATING_N / COUNTS_FULL_SCALE
NOMINAL_COUNTS_PER_N = 1.0 / NOMINAL_N_PER_COUNT      # 51.2
MISMATCH_RATING_N = 45.0       # the other common SingleTact rating

# Acceptance band, counts unless stated.
POINT_TOL_COUNTS = 20.0        # 4 percent of full scale, 0.4 N
SLOPE_TOL_FRAC = 0.02          # the maker's linearity figure
HYSTERESIS_TOL_COUNTS = 20.0   # under the maker's 4 percent
DRIFT_TOL_COUNTS = 10.0        # 2 percent of full scale
RETURN_TOL_COUNTS = 10.0

DEFAULT_MASSES_G = (100.0, 200.0, 500.0, 1000.0)
DRIFT_MASS_G = 500.0
SAMPLE_HZ = 200.0


# ---------------------------------------------------------------- maths

def newtons(mass_g: float) -> float:
    return float(mass_g) / 1000.0 * G


def expected_counts(mass_g: float,
                    counts_per_n: float = NOMINAL_COUNTS_PER_N) -> float:
    """Counts above tare a mass should produce on a pad of this slope."""
    return newtons(mass_g) * counts_per_n


@dataclass
class Point:
    mass_g: float
    direction: str            # "up" or "down"
    mean_counts: float        # above tare
    sd_counts: float = 0.0
    return_counts: float | None = None   # unloaded reading after removal, above tare


@dataclass
class PadResult:
    finger: str
    tare_counts: float
    points: list[Point] = field(default_factory=list)
    drift_counts: float | None = None    # end minus start over the hold
    drift_mass_g: float = DRIFT_MASS_G
    slope_counts_per_n: float | None = None
    intercept_counts: float | None = None
    implied_rating_n: float | None = None
    verdict: str = ""
    failures: list[str] = field(default_factory=list)


def fit_slope(masses_g, counts) -> tuple[float, float]:
    """Ordinary least squares of counts on newtons. The intercept is
    diagnostic only (a tare that moved between the tare and the
    masses shows up there); acceptance reads the slope."""
    xs = [newtons(m) for m in masses_g]
    ys = [float(c) for c in counts]
    n = len(xs)
    if n < 2:
        raise ValueError("need at least two masses to fit a slope")
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        raise ValueError("masses must differ to fit a slope")
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx
    return slope, my - slope * mx


def assess(pad: PadResult,
           nominal_counts_per_n: float = NOMINAL_COUNTS_PER_N) -> PadResult:
    """Fill in the fit, the implied part rating and the verdict.

    Verdicts: PASS, PART MISMATCH (the slope says the pad is not a
    10 N part, so the constant is wrong in kind, not in degree), or
    FAIL with every failing figure named.
    """
    pad.failures = []
    up = [p for p in pad.points if p.direction == "up"]
    if len(up) < 2:
        pad.verdict = "FAIL"
        pad.failures.append("fewer than two ascending masses recorded")
        return pad
    slope, intercept = fit_slope([p.mass_g for p in up],
                                 [p.mean_counts for p in up])
    pad.slope_counts_per_n = slope
    pad.intercept_counts = intercept
    pad.implied_rating_n = (COUNTS_FULL_SCALE / slope if slope > 0
                            else None)
    if pad.implied_rating_n is not None and abs(
            pad.implied_rating_n - MISMATCH_RATING_N) <= 0.10 * MISMATCH_RATING_N:
        pad.verdict = "PART MISMATCH"
        pad.failures.append(
            f"{pad.finger}: slope {slope:.1f} counts/N implies a "
            f"{pad.implied_rating_n:.0f} N part, not the 10 N part the "
            f"config assumes")
        return pad
    if abs(slope - nominal_counts_per_n) > SLOPE_TOL_FRAC * nominal_counts_per_n:
        pad.failures.append(
            f"{pad.finger}: slope {slope:.2f} counts/N is "
            f"{100 * (slope / nominal_counts_per_n - 1):+.1f} percent from "
            f"{nominal_counts_per_n:.1f} (limit +/- {100 * SLOPE_TOL_FRAC:.0f})")
    for p in pad.points:
        exp = expected_counts(p.mass_g, nominal_counts_per_n)
        if abs(p.mean_counts - exp) > POINT_TOL_COUNTS:
            pad.failures.append(
                f"{pad.finger}: {p.mass_g:.0f} g {p.direction} read "
                f"{p.mean_counts:.1f} counts, expected {exp:.1f} "
                f"(limit +/- {POINT_TOL_COUNTS:.0f})")
        if p.return_counts is not None and abs(
                p.return_counts) > RETURN_TOL_COUNTS:
            pad.failures.append(
                f"{pad.finger}: after {p.mass_g:.0f} g {p.direction} the "
                f"pad returned to {p.return_counts:+.1f} counts of tare "
                f"(limit +/- {RETURN_TOL_COUNTS:.0f})")
    by_mass_up = {p.mass_g: p.mean_counts for p in up}
    for p in pad.points:
        if p.direction != "down" or p.mass_g not in by_mass_up:
            continue
        gap = abs(p.mean_counts - by_mass_up[p.mass_g])
        if gap > HYSTERESIS_TOL_COUNTS:
            pad.failures.append(
                f"{pad.finger}: {p.mass_g:.0f} g reads {gap:.1f} counts "
                f"apart ascending against descending "
                f"(limit {HYSTERESIS_TOL_COUNTS:.0f})")
    if pad.drift_counts is not None and abs(
            pad.drift_counts) > DRIFT_TOL_COUNTS:
        pad.failures.append(
            f"{pad.finger}: drifted {pad.drift_counts:+.1f} counts over the "
            f"{pad.drift_mass_g:.0f} g hold (limit +/- {DRIFT_TOL_COUNTS:.0f})")
    pad.verdict = "FAIL" if pad.failures else "PASS"
    return pad


def n_per_count_from(pads) -> float | None:
    """One constant for the rig: the mean slope of the pads that
    passed, as newtons per count. None when nothing passed."""
    slopes = [p.slope_counts_per_n for p in pads
              if p.verdict == "PASS" and p.slope_counts_per_n]
    if not slopes:
        return None
    return 1.0 / (sum(slopes) / len(slopes))


def expectation_table(masses_g) -> list[dict]:
    """What each mass should read on a 10 N part and on a 45 N part,
    so the part-number question is answered at a glance."""
    rows = []
    for m in masses_g:
        rows.append({
            "mass_g": float(m),
            "newtons": round(newtons(m), 3),
            "counts_10N": round(expected_counts(m), 1),
            "counts_45N": round(expected_counts(
                m, COUNTS_FULL_SCALE / MISMATCH_RATING_N), 1),
        })
    return rows


# ------------------------------------------------------------- hardware

def open_source(port: str | None):
    """The board through the same discovery the game uses."""
    from finger_rehab.config import Config
    from finger_rehab.hardware.serial_source import (SerialSource,
                                                    discover_ports)
    cfg = Config.load()
    if not port:
        found = discover_ports(cfg.get("serial.vendor_ids"), max_ports=1)
        if not found:
            raise SystemExit("no board found; pass --port")
        port = found[0]
    src = SerialSource(port, baud=int(cfg.get("serial.baud", BAUD)),
                       num_sensors=int(cfg.get("fsr.num_sensors_per_hand", 4)))
    src.start()
    deadline = time.time() + 8.0
    while time.time() < deadline and src.get_sample(timeout=0.2) is None:
        pass
    if not src.is_connected:
        src.stop()
        raise SystemExit(f"{port} opened but no FSR lines arrived")
    print(f"board on {port}")
    return src


def average(src, idx: int, seconds: float) -> tuple[float, float, int]:
    """Mean and SD of one pad's raw counts over a window."""
    vals = []
    end = time.time() + seconds
    while time.time() < end:
        s = src.get_sample(timeout=0.05)
        if s is None or idx >= len(s.values):
            continue
        vals.append(float(s.values[idx]))
    if len(vals) < 2:
        raise SystemExit("the stream went quiet; check the cable")
    return statistics.fmean(vals), statistics.stdev(vals), len(vals)


def wait(seconds: float, label: str) -> None:
    for n in range(int(seconds), 0, -1):
        print(f"      {label} {n:3d} s ", end="\r", flush=True)
        time.sleep(1)
    print(" " * 60, end="\r")


def prompt(msg: str) -> None:
    input(f"   {msg}  [Enter] ")


def run_pad(src, finger: str, masses_g, warmup_s: float,
            drift_s: float) -> PadResult:
    idx = FINGERS.index(finger)
    print(f"\n{finger.upper()} pad")
    prompt("Nothing on the pad.")
    if warmup_s > 0:
        wait(warmup_s, "warm-up")
    tare, tare_sd, _n = average(src, idx, 5.0)
    print(f"   tare {tare:.1f} counts (SD {tare_sd:.2f})")
    pad = PadResult(finger=finger, tare_counts=tare)
    order = [(m, "up") for m in masses_g] + [(m, "down")
                                            for m in reversed(masses_g)]
    for mass, direction in order:
        prompt(f"Place {mass:.0f} g on the {finger} pad through the puck.")
        wait(3.0, "settle")
        mean, sd, n = average(src, idx, 2.0)
        prompt(f"Remove the {mass:.0f} g.")
        wait(2.0, "settle")
        ret, _sd, _n = average(src, idx, 1.0)
        point = Point(mass_g=float(mass), direction=direction,
                      mean_counts=mean - tare, sd_counts=sd,
                      return_counts=ret - tare)
        pad.points.append(point)
        print(f"   {mass:6.0f} g {direction:4s}  {point.mean_counts:7.1f} "
              f"counts above tare  (SD {sd:.2f}, n {n}, expected "
              f"{expected_counts(mass):.1f}, back to {point.return_counts:+.1f})")
    if drift_s > 0:
        prompt(f"Place {DRIFT_MASS_G:.0f} g for the {drift_s:.0f} s drift hold.")
        wait(3.0, "settle")
        start, _sd, _n = average(src, idx, 2.0)
        wait(max(0.0, drift_s - 4.0), "hold")
        end, _sd, _n = average(src, idx, 2.0)
        pad.drift_counts = end - start
        prompt(f"Remove the {DRIFT_MASS_G:.0f} g.")
        print(f"   drift over {drift_s:.0f} s at {DRIFT_MASS_G:.0f} g: "
              f"{pad.drift_counts:+.1f} counts")
    return assess(pad)


# --------------------------------------------------------------- output

def print_report(pads: list[PadResult], masses_g) -> None:
    print("\nExpected counts above tare (g = 9.81):")
    print("   mass      N    10 N part   45 N part")
    for r in expectation_table(masses_g):
        print(f"   {r['mass_g']:5.0f} g  {r['newtons']:5.2f}   "
              f"{r['counts_10N']:8.1f}   {r['counts_45N']:8.1f}")
    print()
    for pad in pads:
        slope = pad.slope_counts_per_n
        print(f"{pad.finger:7s} {pad.verdict:14s} slope "
              f"{slope:.2f} counts/N" if slope else
              f"{pad.finger:7s} {pad.verdict}")
        if slope:
            print(f"        {100 * (slope / NOMINAL_COUNTS_PER_N - 1):+.1f} "
                  f"percent from nominal 51.2; implied rating "
                  f"{pad.implied_rating_n:.1f} N; intercept "
                  f"{pad.intercept_counts:+.1f} counts")
        for f in pad.failures:
            print(f"        {f}")
    const = n_per_count_from(pads)
    if const is not None:
        print(f"\nFitted constant from the passing pads: {const:.6f} N per "
              f"count ({1 / const:.2f} counts/N); config ships "
              f"{NOMINAL_N_PER_COUNT:.6f}.")
    else:
        print("\nNo pad passed, so no fitted constant is offered.")


def write_json(pads: list[PadResult], masses_g, port: str | None) -> Path:
    out_dir = ROOT / "config" / "calibration"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = date.today().isoformat()
    path = out_dir / f"force_check_{stamp}.json"
    record = {
        "date": stamp,
        "port": port,
        "g": G,
        "nominal_n_per_count": NOMINAL_N_PER_COUNT,
        "masses_g": [float(m) for m in masses_g],
        "expected": expectation_table(masses_g),
        "pads": [asdict(p) for p in pads],
        "fitted_n_per_count": n_per_count_from(pads),
    }
    path.write_text(json.dumps(record, indent=2), encoding="utf-8")
    return path


def write_slope(const: float, config_out: Path) -> None:
    """Write the fitted constant into a yaml Basil names. Refuses the
    user settings file by name: that file is the Settings screen's
    and nothing a script runs may write it."""
    import yaml
    target = Path(config_out).resolve()
    if target.name == "user_settings.yaml":
        raise SystemExit("refusing to write config/user_settings.yaml; "
                         "name another file with --config-out")
    data = {}
    if target.exists():
        data = yaml.safe_load(target.read_text(encoding="utf-8")) or {}
    data.setdefault("fsr", {})["force_calibration_n_per_count"] = round(
        const, 6)
    target.write_text(yaml.safe_dump(data, sort_keys=False),
                      encoding="utf-8")
    print(f"wrote fsr.force_calibration_n_per_count = {const:.6f} to {target}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", default=None)
    ap.add_argument("--pad", choices=FINGERS, default=None,
                    help="one pad instead of all four")
    ap.add_argument("--masses", default=",".join(
        f"{m:.0f}" for m in DEFAULT_MASSES_G),
        help="grams, ascending, comma separated")
    ap.add_argument("--warmup", type=float, default=60.0,
                    help="unloaded settle before the tare, seconds")
    ap.add_argument("--drift", type=float, default=60.0,
                    help="hold at 500 g for drift, seconds (0 skips)")
    ap.add_argument("--write-slope", action="store_true",
                    help="write the fitted constant to --config-out")
    ap.add_argument("--config-out", default=None,
                    help="yaml to receive fsr.force_calibration_n_per_count")
    args = ap.parse_args(argv)
    masses = sorted(float(m) for m in args.masses.split(",") if m.strip())
    if max(masses) > 2000.0:
        raise SystemExit("nothing over 2 kg: overload is three times "
                         "full scale")
    if args.write_slope and not args.config_out:
        raise SystemExit("--write-slope needs --config-out <path>")
    src = open_source(args.port)
    pads: list[PadResult] = []
    try:
        for finger in ([args.pad] if args.pad else FINGERS):
            pads.append(run_pad(src, finger, masses, args.warmup,
                                args.drift))
    finally:
        src.stop()
    print_report(pads, masses)
    path = write_json(pads, masses, args.port)
    print(f"record: {path}")
    const = n_per_count_from(pads)
    if args.write_slope:
        if const is None:
            print("nothing written: no pad passed")
        else:
            write_slope(const, Path(args.config_out))
    return 0 if all(p.verdict == "PASS" for p in pads) else 1


if __name__ == "__main__":
    sys.exit(main())
