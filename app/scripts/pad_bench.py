"""Bench-check the four force pads with known masses, before the study.

Force Pilot's targets are percentages of each finger's own maximum,
which only means the same thing on every pad if every pad turns force
into counts the same way and holds a load without drifting
(force_pilot.py names this check as its precondition). This walks you
through it with the board plugged in: each pad empty, then with each
mass, then a 30 s hold of the heaviest mass for the drift. It prints
counts per gram, how straight the line is, the noise at rest and the
drift, and flags a pad that reads unlike the others.

    python3 app/scripts/pad_bench.py                     50, 100, 200 g
    python3 app/scripts/pad_bench.py --masses 31.1 62.2 155.5

Anything of known weight works. Australian coins are exact: a 50c
piece is 15.55 g, a $1 coin 9.00 g, a $2 coin 6.60 g, so ten 50c
pieces stacked in a small cup are 155.5 g. Set the mass in the middle
of the pad, the same way each time, and keep hands off the frame
while it reads. The results land in config/calibration/ as a CSV.
Nothing else runs while this does: close the game first.
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--masses", type=float, nargs="+",
                    default=[50.0, 100.0, 200.0], help="grams")
    ap.add_argument("--port", default=None)
    args = ap.parse_args()
    masses = sorted(args.masses)
    print("Starting the board (it buzzes each finger as it boots)...")
    board = Board(args.port)
    time.sleep(1.0)
    if board.latest is None:
        print("The board sent nothing. Check the cable and try again.")
        return 1
    rows = []
    per_pad = {}
    for pad in range(4):
        name = FINGERS[pad]
        pts = []
        for grams in [0.0] + masses:
            what = "nothing on it" if grams == 0 else f"{grams:g} g"
            input(f"\nPad {pad + 1} ({name}): {what}. Press Enter, then "
                  f"hands off...")
            time.sleep(0.5)
            got = board.read(READ_S)
            vals = [v[pad] for _t, v in got]
            if not vals:
                print("  no samples: is the board still connected?")
                continue
            mean = statistics.mean(vals)
            sd = statistics.pstdev(vals)
            pts.append((grams, mean, sd))
            rows.append({"pad": pad + 1, "finger": name, "grams": grams,
                         "mean_counts": round(mean, 2),
                         "sd_counts": round(sd, 2), "n": len(vals),
                         "phase": "step"})
            print(f"  {mean:7.1f} counts (sd {sd:.1f}, {len(vals)} samples)")
        if len(pts) >= 3:
            slope, icpt, r2 = _fit([p[0] for p in pts], [p[1] for p in pts])
            per_pad[pad] = {"slope": slope, "r2": r2, "rest": pts[0][1],
                            "rest_sd": pts[0][2]}
    heavy = masses[-1]
    input(f"\nDrift: put {heavy:g} g on pad 1 (index) and press Enter. "
          f"Hands off for {DRIFT_S:.0f} s...")
    time.sleep(0.5)
    got = board.read(DRIFT_S)
    board.close()
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
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
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


if __name__ == "__main__":
    sys.exit(main())
