"""Measure the real FSR sensors and write matching press thresholds.

Why this exists: the shipped fsr.* defaults were tuned for the 2025
analogRead hardware, where values ran 0..1023. The SingleTact I2C
sensors on the current device rest around 235..255, so the absolute
floors (abs_on_min 320, 400 for the middle finger) sit above anything a
press can reach and no press ever registers. Rather than guess new
numbers, this measures the actual hardware and computes them.

Run it with the device plugged in:

    python3 tools/calibrate_fsr.py

It records a resting baseline, then asks for a firm press on each
finger in turn, then prints the thresholds and offers to write them
into config/user_settings.yaml (the same override file the Settings
screen uses, so nothing in default.yaml is touched).

Read-only as far as the Arduino is concerned: it opens the serial port
and listens, and never sends anything except an optional STIM test.
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rehab.config import Config                       # noqa: E402
from rehab.hardware.serial_source import (            # noqa: E402
    _LINE_RE, discover_ports,
)

try:
    import serial
except ImportError:
    print("pyserial is not installed. Run: pip install -r requirements.txt")
    raise SystemExit(1)


N_FINGERS = 4
FINGER_NAMES = ("index", "middle", "ring", "pinky")
BAUD = 115200
# The board resets when the port opens (DTR); nothing it sends before
# this has elapsed is trustworthy.
RESET_WAIT_S = 2.2


def pick_port(cfg: Config) -> str:
    """Command-line port, else the first auto-detected board."""
    if len(sys.argv) > 1:
        return sys.argv[1]
    found = discover_ports(cfg.get("serial.vendor_ids"), max_ports=8)
    if not found:
        print("No Arduino-family serial port detected.")
        print("Plug the device in, or pass the port explicitly:")
        print("    python3 tools/calibrate_fsr.py /dev/cu.usbserial-130")
        raise SystemExit(1)
    if len(found) > 1:
        print(f"Several ports found: {found}")
        print(f"Using the first one. Pass a port to override.")
    return found[0]


def read_window(ser, seconds: float) -> list[list[int]]:
    """Collect parsed samples for `seconds`. Returns one list per
    sensor. Uses the software's own line regex so what we measure is
    exactly what the game would see."""
    out: list[list[int]] = [[] for _ in range(N_FINGERS)]
    end = time.time() + seconds
    while time.time() < end:
        line = ser.readline()
        m = _LINE_RE.search(line)
        if not m:
            continue
        for i in range(N_FINGERS):
            g = m.group(i + 1)
            if g is not None:
                out[i].append(int(g))
    return out


def countdown(msg: str, seconds: int = 3) -> None:
    for n in range(seconds, 0, -1):
        print(f"  {msg} in {n}...", end="\r", flush=True)
        time.sleep(1)
    print(" " * 60, end="\r")


def main() -> int:
    cfg = Config.load()
    port = pick_port(cfg)
    print(f"Opening {port} at {BAUD}")
    try:
        ser = serial.Serial(port, BAUD, timeout=1)
    except Exception as e:
        print(f"Could not open {port}: {e}")
        return 1

    try:
        print(f"Waiting {RESET_WAIT_S}s for the board to reset...")
        time.sleep(RESET_WAIT_S)
        ser.reset_input_buffer()

        # ---- resting baseline ------------------------------------
        print("\nSTEP 1: hands OFF the device.")
        countdown("measuring rest")
        rest = read_window(ser, 4.0)
        if not rest[0]:
            print("No data arriving. Check the device is sending FSR: lines.")
            return 1
        base = [statistics.mean(v) for v in rest]
        noise = [statistics.pstdev(v) if len(v) > 1 else 0.0 for v in rest]
        print("Resting values:")
        for i in range(N_FINGERS):
            print(f"  {FINGER_NAMES[i]:7}: mean={base[i]:6.1f}  "
                  f"noise_sd={noise[i]:.2f}")

        # ---- per-finger press ------------------------------------
        peaks: list[float] = []
        for i in range(N_FINGERS):
            print(f"\nSTEP {i + 2}: press the {FINGER_NAMES[i].upper()} "
                  f"finger firmly and HOLD until told to stop.")
            countdown("recording")
            window = read_window(ser, 3.0)
            peak = max(window[i]) if window[i] else 0
            peaks.append(peak)
            rise = peak - base[i]
            print(f"  peak={peak}  rise above rest={rise:+.0f} counts")
            if rise < 5:
                print("  WARNING: barely moved. Was the right finger "
                      "pressed? Re-run if this looks wrong.")
            print("  release.")
            time.sleep(1.0)

        # ---- compute thresholds ----------------------------------
        # Press must clear a good margin over noise, and release must
        # fall back below a lower bar (hysteresis) so a finger resting
        # near the edge cannot chatter. 40% of the observed rise to
        # trigger, 20% to release, with a noise-based floor so a
        # near-silent sensor still cannot false-trigger.
        on_delta, off_delta = [], []
        for i in range(N_FINGERS):
            rise = max(0.0, peaks[i] - base[i])
            noise_floor = max(6.0, noise[i] * 8)
            on_d = max(noise_floor, rise * 0.40)
            off_d = max(noise_floor * 0.5, rise * 0.20)
            on_delta.append(int(round(on_d)))
            off_delta.append(int(round(off_d)))

        # Absolute floors: keep them as a safety net just below the
        # computed trigger point rather than the old 320/400 which sit
        # above anything these sensors produce.
        abs_on_min = [int(round(base[i] + on_delta[i] * 0.8))
                      for i in range(N_FINGERS)]
        abs_off_max = [int(round(base[i] + off_delta[i] * 1.5))
                       for i in range(N_FINGERS)]

        print("\n" + "=" * 58)
        print("MEASURED THRESHOLDS")
        print("=" * 58)
        for i in range(N_FINGERS):
            print(f"  {FINGER_NAMES[i]:7}: rest={base[i]:6.1f}  "
                  f"peak={peaks[i]:5}  on=+{on_delta[i]}  off=+{off_delta[i]}")
        print(f"\n  on_delta:    {on_delta}")
        print(f"  off_delta:   {off_delta}")
        print(f"  abs_on_min:  {abs_on_min}")
        print(f"  abs_off_max: {abs_off_max}")

        if min(peaks[i] - base[i] for i in range(N_FINGERS)) < 5:
            print("\nAt least one finger barely registered. Fix the wiring "
                  "or sensor placement and re-run before saving.")

        ans = input("\nWrite these into config/user_settings.yaml? [y/N] ")
        if ans.strip().lower().startswith("y"):
            cfg.save_user_overrides({
                "fsr.on_delta": on_delta,
                "fsr.off_delta": off_delta,
                "fsr.abs_on_min": abs_on_min,
                "fsr.abs_off_max": abs_off_max,
            })
            print("Saved. The game picks these up next launch.")
        else:
            print("Not saved. Nothing changed.")
        return 0
    finally:
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
