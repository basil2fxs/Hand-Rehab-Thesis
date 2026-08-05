"""Full hardware check for the hand rehabilitation device.

Run this whenever the device has been rebuilt, rewired, or has not been
used for a while, and before any participant session. It works through
every part of the chain and finishes with a plain pass or fail per item,
so nothing gets assumed.

    python3 tools/test_device.py

What it checks:

  1. Serial link      the board is found, opens, and streams
  2. Data rate        samples arrive near the expected 200 Hz
  3. Sensor health    every sensor sits in a sane resting range and is
                      not stuck, flatlined or reading zero
  4. Buttons          pressing each finger moves the RIGHT sensor, which
                      catches sensors wired to the wrong finger
  5. Buzzers          each motor is felt on the finger the software
                      thinks it is
  6. Thresholds       a normal press actually crosses the configured
                      trigger, using the real detector

Buttons and buzzers are separate steps, so the button test still gives a
useful result while the motors are out of action.

Nothing is written to the Arduino beyond the STIM and STOP commands the
firmware already accepts, and no config is changed unless you ask for it
at the end.
"""
from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rehab.config import Config                                # noqa: E402
from rehab.hardware.fsr_detector import Calibration, FSRDetector  # noqa: E402
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
FIRMWARE_STIM_MS = 150      # fixed in the sketch, cannot be changed from here

RESULTS: list[tuple[str, bool | None, str]] = []


def record(name: str, ok: bool | None, detail: str = "") -> None:
    RESULTS.append((name, ok, detail))
    mark = {True: "PASS", False: "FAIL", None: "SKIP"}[ok]
    print(f"   [{mark}] {name}" + (f"   {detail}" if detail else ""))


def grab(ser, seconds: float):
    """Collect parsed samples. Returns (per-sensor lists, line count)."""
    out = [[] for _ in range(N)]
    lines = 0
    end = time.time() + seconds
    while time.time() < end:
        m = _LINE_RE.search(ser.readline())
        if not m:
            continue
        lines += 1
        for i in range(N):
            g = m.group(i + 1)
            if g is not None:
                out[i].append(int(g))
    return out, lines


def countdown(msg: str, secs: int = 3) -> None:
    for n in range(secs, 0, -1):
        print(f"      {msg} in {n}... ", end="\r", flush=True)
        time.sleep(1)
    print(" " * 70, end="\r")


def ask(prompt: str, options: tuple[str, ...]) -> str:
    while True:
        a = input(prompt).strip().lower()
        if a in options:
            return a
        print(f"      answer one of: {', '.join(options)}")


def main() -> int:
    cfg = Config.load()
    print("=" * 64)
    print("  DEVICE TEST")
    print("=" * 64)

    # ---- 1. serial link ---------------------------------------
    print("\n1. SERIAL LINK")
    port = (sys.argv[1] if len(sys.argv) > 1 else None)
    if port is None:
        found = discover_ports(cfg.get("serial.vendor_ids"), max_ports=8)
        if not found:
            record("board detected", False,
                   "no Arduino-family port found")
            print("\n   Plug the device in and try again, or pass the port:")
            print("      python3 tools/test_device.py /dev/cu.usbserial-130")
            return 1
        port = found[0]
        record("board detected", True, port)
    else:
        record("board detected", True, f"{port} (given on the command line)")

    try:
        ser = serial.Serial(port, BAUD, timeout=1)
    except Exception as e:
        record("port opens", False, str(e))
        print("\n   If the game is running, close it first. The port only")
        print("   allows one program at a time.")
        return 1
    record("port opens", True, f"{BAUD} baud")

    try:
        time.sleep(RESET_WAIT_S)          # board resets on open
        ser.reset_input_buffer()

        # ---- 2. data rate -------------------------------------
        print("\n2. DATA STREAM")
        samples, lines = grab(ser, 3.0)
        rate = lines / 3.0
        if lines == 0:
            record("samples arriving", False, "nothing parsed in 3 s")
            print("\n   The port is open but no FSR lines are arriving.")
            print("   Check the sketch is running and sending 'FSR: a,b,c,d'.")
            return 1
        record("samples arriving", True, f"{lines} lines in 3 s")
        ok_rate = 150 <= rate <= 260
        record("sample rate near 200 Hz", ok_rate, f"{rate:.0f} Hz")

        # ---- 3. sensor health ---------------------------------
        print("\n3. SENSOR HEALTH  (hands off the device)")
        rest = [statistics.mean(v) for v in samples]
        noise = [statistics.pstdev(v) if len(v) > 1 else 0.0 for v in samples]
        for i in range(N):
            detail = f"rest {rest[i]:.0f}, noise {noise[i]:.2f}"
            if rest[i] <= 1:
                record(f"{FINGERS[i]} sensor", False,
                       detail + "  reads zero, likely an I2C fault")
            elif noise[i] == 0:
                record(f"{FINGERS[i]} sensor", False,
                       detail + "  perfectly flat, likely stuck")
            elif not (100 <= rest[i] <= 900):
                record(f"{FINGERS[i]} sensor", False,
                       detail + "  resting value looks wrong")
            else:
                record(f"{FINGERS[i]} sensor", True, detail)

        # ---- 4. buttons ---------------------------------------
        print("\n4. BUTTONS  (press each finger when asked)")
        print("   This catches a sensor wired to the wrong finger.")
        wrong_sensor = []
        for i in range(N):
            print(f"\n   press and hold the {FINGERS[i].upper()} finger")
            countdown("recording")
            w, _ = grab(ser, 2.5)
            rises = [max(w[j]) - rest[j] if w[j] else 0 for j in range(N)]
            best = max(range(N), key=lambda j: rises[j])
            mine = rises[i]
            if mine < 10:
                record(f"{FINGERS[i]} button", False,
                       f"barely moved ({mine:+.0f} counts)")
            elif best != i:
                wrong_sensor.append((i, best))
                record(f"{FINGERS[i]} button", False,
                       f"moved the {FINGERS[best]} sensor most "
                       f"({rises[best]:+.0f} vs {mine:+.0f})")
            else:
                record(f"{FINGERS[i]} button", True,
                       f"{mine:+.0f} counts on its own sensor")
            print("      release")
            time.sleep(0.8)

        # ---- 5. thresholds ------------------------------------
        print("\n5. TRIGGER THRESHOLDS")
        print("   Does a normal press actually cross the configured trigger?")
        cal = Calibration(
            num_sensors=N,
            baseline_alpha=float(cfg.get("fsr.baseline_alpha", 0.0005)),
            value_alpha=float(cfg.get("fsr.value_alpha", 0.35)),
            on_delta=list(cfg.get("fsr.on_delta")),
            off_delta=list(cfg.get("fsr.off_delta")),
            abs_on_min=list(cfg.get("fsr.abs_on_min")),
            abs_off_max=list(cfg.get("fsr.abs_off_max")),
            debounce_ms=int(cfg.get("fsr.debounce_ms", 100)),
        )
        det = FSRDetector(cal, hand="right")
        fired: list[int] = []
        det.on_press = lambda ev: fired.append(ev.lane)
        print("\n   press each finger once, in order, at a normal strength")
        countdown("recording all four", 3)
        t0 = time.perf_counter()
        end = time.time() + 12.0
        while time.time() < end:
            m = _LINE_RE.search(ser.readline())
            if m:
                vals = tuple(int(m.group(i + 1)) for i in range(N))
                det.feed(time.perf_counter(), vals)
        seen = set(fired)
        for i in range(N):
            record(f"{FINGERS[i]} crosses trigger", i in seen,
                   f"on_delta +{cal.on_delta[i]}"
                   + ("" if i in seen else "  never registered"))

        # ---- 6. buzzers ---------------------------------------
        print("\n6. BUZZERS")
        print("   Each motor buzzes in turn. Say which finger you felt.")
        buzz_ok, buzz_wrong, buzz_none = [], [], []
        for i in range(N):
            input(f"\n   ready to buzz motor {i+1} "
                  f"(should be {FINGERS[i].upper()}), press Enter")
            cmd = f"STIM:{i+1}\n".encode()
            # Hold it on for the configured cue length by re-arming.
            cue_ms = int(cfg.get("motor.cue_ms", 250))
            ser.write(cmd); ser.flush()
            waited = 0
            while waited + FIRMWARE_STIM_MS < cue_ms:
                time.sleep(0.12); waited += 120
                ser.write(cmd); ser.flush()
            time.sleep(0.3)
            a = ask("      which finger? [i]ndex [m]iddle [r]ing "
                    "[p]inky [n]othing: ", ("i", "m", "r", "p", "n"))
            got = {"i": 0, "m": 1, "r": 2, "p": 3}.get(a)
            if a == "n":
                buzz_none.append(i)
                record(f"{FINGERS[i]} buzzer", False, "nothing felt")
            elif got == i:
                buzz_ok.append(i)
                record(f"{FINGERS[i]} buzzer", True, "felt on the right finger")
            else:
                buzz_wrong.append((i, got))
                record(f"{FINGERS[i]} buzzer", False,
                       f"felt on the {FINGERS[got]} instead")
        ser.write(b"STOP\n"); ser.flush()

    finally:
        try:
            ser.write(b"STOP\n"); ser.flush()
        except Exception:
            pass
        ser.close()

    # ---- summary ----------------------------------------------
    print("\n" + "=" * 64)
    print("  SUMMARY")
    print("=" * 64)
    passed = sum(1 for _, ok, _ in RESULTS if ok is True)
    failed = [n for n, ok, _ in RESULTS if ok is False]
    print(f"   {passed} passed, {len(failed)} failed\n")
    if not failed:
        print("   Everything checks out. The device is ready for a session.")
        return 0

    print("   Failed:")
    for n in failed:
        print(f"     - {n}")

    print("\n   What to do about it:")
    if any("sensor" in n for n in failed):
        print("     Sensors reading zero or flat usually means an I2C")
        print("     problem. Run the ADDRESS.ino sketch from the handover")
        print("     folder to check all four addresses 0x05 to 0x08 answer.")
    if wrong_sensor:
        print("     A press moving the wrong sensor means those two sensors")
        print("     are swapped in the loom. Fix the wiring rather than the")
        print("     software, or the lane numbers in the CSVs will be wrong.")
    if any("crosses trigger" in n for n in failed):
        print("     A finger that never crosses its trigger needs the")
        print("     threshold re-measured. Run:")
        print("       python3 tools/calibrate_rest_vs_press.py")
    if buzz_none:
        print("     No buzz felt at all. The motor pins in the flashed")
        print("     sketch have to")
        print("     match where the motors are physically wired. Check the")
        print("     wiring first, then the four #define lines in the sketch.")
    if buzz_wrong:
        print("     A buzz on the wrong finger means the motor leads are")
        print("     swapped. Fix it in hardware so the recorded lane numbers")
        print("     keep matching the sensors.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
