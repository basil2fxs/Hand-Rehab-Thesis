"""Find the press threshold that separates a deliberate press from a
hand simply resting on the device.

This is the failure mode a plain press-only calibration misses. A
patient rests their fingers on the pads between trials, and that
resting load is not zero. If the trigger sits below it, the game fires
phantom presses continuously. If it sits too far above it, a weak
finger can never reach it. The usable threshold lives in the gap
between the two, and this measures that gap directly.

Three phases:
  1. Hand completely OFF the device       -> true zero
  2. Hand RESTING naturally on the pads   -> the false-positive floor
  3. A deliberate SOFT press per finger   -> the detection ceiling

It then reports the separation per finger and picks a threshold in
between, or warns loudly if rest and press overlap (which means the
hand position or sensor placement needs fixing, not the software).

    python3 tools/calibrate_rest_vs_press.py

Nothing is written to the Arduino: the port is opened read-only.
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rehab.config import Config                                # noqa: E402
from rehab.hardware.serial_source import (                     # noqa: E402
    _LINE_RE, discover_ports,
)

try:
    import serial
except ImportError:
    print("pyserial missing. Run: pip install -r requirements.txt")
    raise SystemExit(1)


FINGERS = ("index", "middle", "ring", "pinky")
N = 4
BAUD = 115200
RESET_WAIT_S = 2.2


def pick_port(cfg: Config) -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    found = discover_ports(cfg.get("serial.vendor_ids"), max_ports=8)
    if not found:
        print("No Arduino detected. Plug the device in, or pass the port:")
        print("    python3 tools/calibrate_rest_vs_press.py /dev/cu.usbserial-130")
        raise SystemExit(1)
    return found[0]


def grab(ser, seconds: float) -> list[list[int]]:
    out: list[list[int]] = [[] for _ in range(N)]
    end = time.time() + seconds
    while time.time() < end:
        m = _LINE_RE.search(ser.readline())
        if not m:
            continue
        for i in range(N):
            g = m.group(i + 1)
            if g is not None:
                out[i].append(int(g))
    return out


def countdown(msg: str, secs: int = 3) -> None:
    for n in range(secs, 0, -1):
        print(f"   {msg} in {n}... ", end="\r", flush=True)
        time.sleep(1)
    print(" " * 70, end="\r")


def main() -> int:
    cfg = Config.load()
    port = pick_port(cfg)
    print("=" * 62)
    print("REST vs PRESS CALIBRATION")
    print("=" * 62)
    print(f"port: {port}\n")
    try:
        ser = serial.Serial(port, BAUD, timeout=1)
    except Exception as e:
        print(f"Could not open {port}: {e}")
        print("Is the game still running? Close it first, the port only "
              "allows one program at a time.")
        return 1

    try:
        time.sleep(RESET_WAIT_S)
        ser.reset_input_buffer()

        # --- phase 1: nothing touching -----------------------------
        print("STEP 1 of 3: take your hand COMPLETELY OFF the device.")
        countdown("measuring empty device")
        empty = grab(ser, 3.0)
        if not empty[0]:
            print("No data arriving. Check the device is streaming.")
            return 1
        zero = [statistics.mean(v) for v in empty]
        noise = [statistics.pstdev(v) if len(v) > 1 else 0.0 for v in empty]
        print("   empty-device reading:")
        for i in range(N):
            print(f"     {FINGERS[i]:7} {zero[i]:7.1f}   noise sd {noise[i]:.2f}")

        # --- phase 2: resting hand ---------------------------------
        print("\nSTEP 2 of 3: REST your hand on the device the way a")
        print("patient would between presses. Fingers touching the pads,")
        print("relaxed, NOT pressing.")
        countdown("measuring resting hand", 4)
        resting = grab(ser, 4.0)
        rest = [statistics.mean(v) for v in resting]
        rest_hi = [max(v) if v else 0 for v in resting]
        print("   resting-hand load above empty device:")
        for i in range(N):
            print(f"     {FINGERS[i]:7} mean +{rest[i]-zero[i]:6.1f}   "
                  f"peak +{rest_hi[i]-zero[i]:6.1f}")

        # --- phase 3: soft deliberate press ------------------------
        print("\nSTEP 3 of 3: a deliberate but GENTLE press on each finger.")
        print("Press as softly as you would still call a real press.")
        soft = []
        for i in range(N):
            print(f"\n   press {FINGERS[i].upper()} gently and hold")
            countdown("recording", 3)
            w = grab(ser, 3.0)
            pk = max(w[i]) if w[i] else 0
            soft.append(pk)
            print(f"     peak +{pk-zero[i]:.0f} above empty, "
                  f"+{pk-rest[i]:.0f} above resting")
            print("     release")
            time.sleep(1.0)

        # --- verdict ------------------------------------------------
        print("\n" + "=" * 62)
        print("SEPARATION between resting and pressing")
        print("=" * 62)
        on_delta, problems = [], []
        for i in range(N):
            rest_load = rest_hi[i] - zero[i]      # worst-case resting
            press_load = soft[i] - zero[i]        # gentle press
            gap = press_load - rest_load
            # Put the trigger 40% of the way from resting peak to the
            # gentle press: clear of resting load, still reachable by a
            # weaker press than the one just demonstrated.
            thr = rest_load + gap * 0.40
            # Never allow a threshold under 8x the sensor noise.
            floor = max(8.0, noise[i] * 8)
            thr = max(thr, floor)
            on_delta.append(int(round(thr)))
            status = "OK"
            if gap < 10:
                status = "TOO CLOSE"
                problems.append(FINGERS[i])
            print(f"  {FINGERS[i]:7} resting +{rest_load:6.1f}   "
                  f"gentle press +{press_load:6.1f}   gap {gap:6.1f}   "
                  f"trigger +{on_delta[i]:3}   {status}")

        off_delta = [max(4, int(round(d * 0.5))) for d in on_delta]
        print(f"\n  on_delta:  {on_delta}")
        print(f"  off_delta: {off_delta}")

        if problems:
            print("\n  WARNING: " + ", ".join(problems) +
                  " show almost no gap between resting and pressing.")
            print("  That is a hardware/positioning issue, not a software")
            print("  one: the finger is likely already loading the pad at")
            print("  rest. Reposition the hand or the sensor and re-run.")

        cur = list(cfg.get("fsr.on_delta") or [])
        print(f"\n  current setting in use: {cur}")

        ans = input("\nWrite these to config/user_settings.yaml? [y/N] ")
        if ans.strip().lower().startswith("y"):
            cfg.save_user_overrides({
                "fsr.on_delta": on_delta,
                "fsr.off_delta": off_delta,
            })
            print("Saved. Takes effect next time the game starts.")
        else:
            print("Not saved, nothing changed.")
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
