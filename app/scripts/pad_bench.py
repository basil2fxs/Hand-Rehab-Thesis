"""Bench the four force pads with known masses. Two modes.

The quick check, before a collection day. Force Pilot's targets are
percentages of each finger's own maximum, which only means the same
thing on every pad if every pad turns force into counts the same way
and holds a load without drifting (force_pilot.py names this check as
its precondition). It walks through each pad empty, then with each
mass, then a 30 s hold of the heaviest mass for the drift, prints
counts per gram, how straight the line is, the noise at rest and the
drift, and flags a pad that reads unlike the others.

    python3 app/scripts/pad_bench.py                     50, 100, 200 g
    python3 app/scripts/pad_bench.py --masses 31.1 62.2 155.5

The characterisation, once per sensor set, for the sensor comparison
(thesis Section 4.3). Each pad is loaded from empty up through the
masses and back down, then pad 1 holds half the rated load for ten
minutes. It reports each pad's slope in counts per newton against the
nominal 51.2, its linearity error and hysteresis in percent of full
scale, and its noise at rest, then the drift at one minute and at the
end of the hold. The label names the set, so both sets' files sit side
by side.

    python3 app/scripts/pad_bench.py --characterise --label calibrated
    python3 app/scripts/pad_bench.py --characterise --label uncalibrated

Anything of known weight works. Australian coins are exact: a 50c
piece is 15.55 g, a $1 coin 9.00 g, a $2 coin 6.60 g, so ten 50c
pieces stacked in a small cup are 155.5 g. The characterisation goes
to 1 kg: stand each mass on a coin centred on the pad, so the load
lands on the sensing area the same way every time, and weigh mass and
coin together on a kitchen scale. Keep hands off the frame while it
reads. The results land in config/calibration/ as CSV. Nothing else
runs while this does: close the game first.
"""
from __future__ import annotations

import argparse
import csv
import statistics
import sys
import threading
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
FINGERS = ("index", "middle", "ring", "little")
READ_S = 3.0
DRIFT_S = 30.0

# The characterisation. The pads are the 10 N part, which spreads its
# rating over 512 counts: 51.2 counts per newton. Full scale output is
# a pad's own slope times the rated load, the figure the datasheet's
# percentages are of (SingleTact spec sheet V8.0: linearity under 2
# percent, hysteresis under 4, drift 2 percent at one minute and 4 at
# ten minutes at half load).
G = 9.80665
RATED_N = 10.0
NOMINAL_COUNTS_PER_N = 51.2
CHAR_MASSES_G = (100.0, 250.0, 500.0, 1000.0)
HOLD_G = 500.0
HOLD_MIN = 10.0
SPEC = {"slope_counts_per_n": "51.2", "linearity_pct_fs": "under 2",
        "hysteresis_pct_fs": "under 4", "rest_sd_counts": "",
        "drift_1min_pct_fs": "2", "drift_end_pct_fs": "4 at 10 min"}


class Board:
    def __init__(self, port: str | None) -> None:
        import serial
        from serial.tools import list_ports
        if port is None:
            found = [p.device for p in list_ports.comports()
                     if "usbserial" in p.device or "usbmodem" in p.device
                     or p.device.upper().startswith("COM")]
            if not found:
                raise SystemExit("No board found. Plug it in, or pass "
                                 "--port.")
            port = found[0]
        self.port = port
        self.s = serial.Serial(port, 115200, timeout=0.05)
        self.latest: list[int] | None = None
        self.samples: list[tuple[float, list[int]]] = []
        self.recording = False
        self._stop = threading.Event()
        t_end = time.time() + 8
        while time.time() < t_end:
            if b"Setup Complete" in self.s.readline():
                break
        self._th = threading.Thread(target=self._read, daemon=True)
        self._th.start()

    def _read(self) -> None:
        while not self._stop.is_set():
            line = self.s.readline()
            if not line.startswith(b"FSR:"):
                continue
            try:
                vals = [int(x) for x in line[4:].split(b",")]
            except ValueError:
                continue
            self.latest = vals
            if self.recording:
                self.samples.append((time.perf_counter(), vals))

    def read(self, seconds: float) -> list[tuple[float, list[int]]]:
        self.samples = []
        self.recording = True
        time.sleep(seconds)
        self.recording = False
        return list(self.samples)

    def close(self) -> None:
        self._stop.set()
        self._th.join(timeout=1)
        self.s.close()


def _fit(xs, ys):
    """Least-squares slope and intercept, and R squared."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    sxy = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    slope = sxy / sxx if sxx else 0.0
    icpt = my - slope * mx
    ss_tot = sum((y - my) ** 2 for y in ys)
    ss_res = sum((y - (icpt + slope * x)) ** 2 for x, y in zip(xs, ys))
    return slope, icpt, (1 - ss_res / ss_tot) if ss_tot else 0.0


def newtons(grams: float) -> float:
    return grams / 1000.0 * G


def load_order(masses) -> list[tuple[str, float]]:
    """Empty, up through the masses, and back down to empty: the way
    down gives the hysteresis at every mass below the top one."""
    up = sorted(masses)
    return ([("load", 0.0)] + [("load", g) for g in up]
            + [("unload", g) for g in reversed(up[:-1])]
            + [("unload", 0.0)])


def characterise_pad(points, rated_n: float = RATED_N) -> dict | None:
    """One pad's bench figures from its readings.

    points: (grams, phase, mean_counts, sd_counts), phase "load" on the
    way up (empty first) and "unload" on the way down. The slope is the
    least-squares line through the loading points, in counts per
    newton. The linearity error is the largest distance of a loading
    point from that line, the hysteresis the largest gap between the
    unloading and loading readings at one mass, both in percent of full
    scale (the slope times the rated load). The noise at rest is the
    SD of the empty reading. None when there are too few points or the
    pad does not respond to load.
    """
    load = [(newtons(g), m) for g, ph, m, _sd in points if ph == "load"]
    if len(load) < 3:
        return None
    slope, icpt, _r2 = _fit([x for x, _ in load], [y for _, y in load])
    fso = slope * rated_n
    if fso <= 0:
        return None
    lin = max(abs(y - (icpt + slope * x)) for x, y in load)
    up = {round(g, 3): m for g, ph, m, _sd in points if ph == "load"}
    gaps = [abs(m - up[round(g, 3)]) for g, ph, m, _sd in points
            if ph == "unload" and round(g, 3) in up]
    rest = [sd for g, ph, _m, sd in points if ph == "load" and g == 0]
    return {"slope_counts_per_n": slope,
            "linearity_pct_fs": 100.0 * lin / fso,
            "hysteresis_pct_fs": (100.0 * max(gaps) / fso) if gaps else None,
            "rest_sd_counts": rest[0] if rest else None,
            "full_scale_counts": fso}


def drift_pct(samples, slope: float, at_s, rated_n: float = RATED_N,
              window_s: float = 2.0) -> dict:
    """Drift under a held load, in percent of full scale: the mean of
    the window ending at each time in at_s, less the mean of the first
    window. samples: (seconds since the hold began, counts)."""
    fso = slope * rated_n
    first = [c for t, c in samples if t < window_s]
    if not first or fso <= 0:
        return {}
    base = statistics.mean(first)
    out = {}
    for at in at_s:
        win = [c for t, c in samples if at - window_s <= t <= at]
        if win:
            out[at] = 100.0 * (statistics.mean(win) - base) / fso
    return out


def _reading(board, pad: int, prompt: str):
    input(prompt)
    time.sleep(0.5)
    got = board.read(READ_S)
    vals = [v[pad] for _t, v in got]
    if not vals:
        print("  no samples: is the board still connected?")
        return None
    mean, sd = statistics.mean(vals), statistics.pstdev(vals)
    print(f"  {mean:7.1f} counts (sd {sd:.1f}, {len(vals)} samples)")
    return mean, sd, len(vals)


def _write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def run_check(board, masses) -> int:
    rows = []
    per_pad = {}
    for pad in range(4):
        name = FINGERS[pad]
        pts = []
        for grams in [0.0] + masses:
            what = "nothing on it" if grams == 0 else f"{grams:g} g"
            got = _reading(board, pad, f"\nPad {pad + 1} ({name}): {what}. "
                                       f"Press Enter, then hands off...")
            if got is None:
                continue
            mean, sd, n = got
            pts.append((grams, mean, sd))
            rows.append({"pad": pad + 1, "finger": name, "grams": grams,
                         "mean_counts": round(mean, 2),
                         "sd_counts": round(sd, 2), "n": n,
                         "phase": "step"})
        if len(pts) >= 3:
            slope, icpt, r2 = _fit([p[0] for p in pts], [p[1] for p in pts])
            per_pad[pad] = {"slope": slope, "r2": r2, "rest": pts[0][1],
                            "rest_sd": pts[0][2]}
    heavy = masses[-1]
    input(f"\nDrift: put {heavy:g} g on pad 1 (index) and press Enter. "
          f"Hands off for {DRIFT_S:.0f} s...")
    time.sleep(0.5)
    got = board.read(DRIFT_S)
    drift = None
    if got:
        t0 = got[0][0]
        first = [v[0] for t, v in got if t - t0 < 2.0]
        last = [v[0] for t, v in got if t - t0 > DRIFT_S - 2.0]
        if first and last:
            drift = statistics.mean(last) - statistics.mean(first)
            for t, v in got[:: max(1, len(got) // 60)]:
                rows.append({"pad": 1, "finger": "index", "grams": heavy,
                             "mean_counts": v[0], "sd_counts": "",
                             "n": 1, "phase": f"drift_{t - t0:.1f}s"})
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = APP / "config" / "calibration" / f"pad_bench_{stamp}.csv"
    _write(out, rows)
    print(f"\nreadings -> {out}\n")
    slopes = [d["slope"] for d in per_pad.values() if d["slope"] > 0]
    med = statistics.median(slopes) if slopes else 0.0
    flags = 0
    for pad, d in sorted(per_pad.items()):
        note = []
        if d["r2"] < 0.98:
            note.append("not a straight line")
        if med and abs(d["slope"] - med) > 0.25 * med:
            note.append(f"{d['slope'] / med:.0%} of the other pads' gain")
        if d["slope"] <= 0:
            note.append("does not respond to load")
        flags += bool(note)
        print(f"  pad {pad + 1} {FINGERS[pad]:6s} {d['slope']:.3f} counts/g, "
              f"R2 {d['r2']:.3f}, rest {d['rest']:.0f} (sd "
              f"{d['rest_sd']:.1f})" + (f"   CHECK: {'; '.join(note)}"
                                        if note else ""))
    if drift is not None and per_pad.get(0, {}).get("slope"):
        load = per_pad[0]["slope"] * heavy
        share = drift / load if load else 0.0
        bad = abs(share) > 0.05
        flags += bad
        print(f"  drift over {DRIFT_S:.0f} s with {heavy:g} g: {drift:+.1f} "
              f"counts, {share:+.1%} of the load"
              + ("   CHECK: over 5 percent" if bad else ""))
    print("\n" + ("All four pads read alike and hold a load: fine for the "
                  "study." if not flags else
                  f"{flags} item(s) to check: reseat the pad flat and run "
                  f"this again."))
    return 0 if not flags else 1


def run_characterise(board, masses, hold_g: float, hold_min: float,
                     label: str) -> int:
    rows = []
    summary = []
    figures = {}
    for pad in range(4):
        name = FINGERS[pad]
        pts = []
        for phase, grams in load_order(masses):
            what = "nothing on it" if grams == 0 else f"{grams:g} g"
            way = "up" if phase == "load" else "down"
            got = _reading(board, pad, f"\nPad {pad + 1} ({name}), on the "
                                       f"way {way}: {what}. Press Enter, "
                                       f"then hands off...")
            if got is None:
                continue
            mean, sd, n = got
            pts.append((grams, phase, mean, sd))
            rows.append({"label": label, "pad": pad + 1, "finger": name,
                         "grams": grams, "newtons": round(newtons(grams), 4),
                         "phase": phase, "mean_counts": round(mean, 2),
                         "sd_counts": round(sd, 2), "n": n})
        figures[pad] = characterise_pad(pts)
    hold_s = hold_min * 60.0
    input(f"\nDrift: stand {hold_g:g} g on pad 1 (index) and press Enter. "
          f"Hands off for {hold_min:g} min...")
    time.sleep(0.5)
    got = board.read(hold_s)
    drift = {}
    if got and figures.get(0):
        t0 = got[0][0]
        held = [(t - t0, v[0]) for t, v in got]
        drift = drift_pct(held, figures[0]["slope_counts_per_n"],
                          (60.0, hold_s))
        for t, c in held[:: max(1, len(held) // 120)]:
            rows.append({"label": label, "pad": 1, "finger": "index",
                         "grams": hold_g,
                         "newtons": round(newtons(hold_g), 4),
                         "phase": f"hold_{t:.1f}s", "mean_counts": c,
                         "sd_counts": "", "n": 1})
    for pad, fig in sorted(figures.items()):
        if not fig:
            continue
        for key in ("slope_counts_per_n", "linearity_pct_fs",
                    "hysteresis_pct_fs", "rest_sd_counts"):
            if fig[key] is not None:
                summary.append({"label": label, "pad": pad + 1,
                                "finger": FINGERS[pad], "measure": key,
                                "value": round(fig[key], 3),
                                "datasheet": SPEC[key]})
    for key, at in (("drift_1min_pct_fs", 60.0),
                    ("drift_end_pct_fs", hold_s)):
        if at in drift:
            summary.append({"label": label, "pad": 1, "finger": "index",
                            "measure": key, "value": round(drift[at], 3),
                            "datasheet": SPEC[key]})
    stamp = time.strftime("%Y%m%d_%H%M%S")
    base = APP / "config" / "calibration" / f"pad_bench_{label}_{stamp}"
    _write(base.with_suffix(".csv"), rows)
    if not summary:
        print("\nNo pad gave enough readings for its figures.")
        return 1
    _write(Path(f"{base}_summary.csv"), summary)
    print(f"\nreadings -> {base}.csv\nfigures  -> {base}_summary.csv\n")
    print(f"  {label}: pad, counts per N (nominal "
          f"{NOMINAL_COUNTS_PER_N:g}), linearity and hysteresis in % of "
          f"full scale, noise at rest")
    for pad, fig in sorted(figures.items()):
        if not fig:
            print(f"  pad {pad + 1} {FINGERS[pad]:6s} too few readings")
            continue
        hyst = ("" if fig["hysteresis_pct_fs"] is None
                else f"{fig['hysteresis_pct_fs']:.2f}")
        print(f"  pad {pad + 1} {FINGERS[pad]:6s} "
              f"{fig['slope_counts_per_n']:6.2f}   "
              f"{fig['linearity_pct_fs']:.2f}   {hyst}   "
              f"sd {fig['rest_sd_counts']:.2f}")
    for at in sorted(drift):
        print(f"  drift at {at / 60.0:g} min with {hold_g:g} g on pad 1: "
              f"{drift[at]:+.2f} % of full scale")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--masses", type=float, nargs="+", default=None,
                    help="grams (50 100 200 for the check, 100 250 500 "
                         "1000 for the characterisation)")
    ap.add_argument("--port", default=None)
    ap.add_argument("--characterise", action="store_true",
                    help="the sensor comparison's figures for one set")
    ap.add_argument("--label", default="set",
                    help="the set, for example calibrated or uncalibrated")
    ap.add_argument("--hold-g", type=float, default=HOLD_G)
    ap.add_argument("--hold-min", type=float, default=HOLD_MIN)
    args = ap.parse_args()
    default = CHAR_MASSES_G if args.characterise else (50.0, 100.0, 200.0)
    masses = sorted(args.masses or default)
    print("Starting the board (it buzzes each finger as it boots)...")
    board = Board(args.port)
    time.sleep(1.0)
    if board.latest is None:
        print("The board sent nothing. Check the cable and try again.")
        board.close()
        return 1
    try:
        if args.characterise:
            return run_characterise(board, masses, args.hold_g,
                                    args.hold_min, args.label)
        return run_check(board, masses)
    finally:
        board.close()


if __name__ == "__main__":
    sys.exit(main())
