"""Buzz every finger on a timer, for as long as you leave it running.

This exists for one bug in particular. The firmware stored each motor's
switch-off deadline in a 16-bit variable while millis() is 32-bit, so it
only held the first 65536 ms of uptime. Past 65.5 seconds the deadline
could no longer represent the real time, the switch-off test was true the
moment it was looked at, and every motor was cut microseconds after being
told to turn on. The buzzers stopped about a minute after boot, with no
error anywhere, and came back only because reopening the serial port
resets the board and restarts millis() from zero.

The host cannot tell whether a motor actually moved. Nothing comes back
over the wire for a STIM, and the current draw is lost in the sensor
noise. So this is a thing you feel, not a thing it measures: rest your
hand on the pads, leave it running, and it tells you which finger it is
buzzing and how long the board has been up. If a finger stops being felt
somewhere past a minute, that bug is back.

    python3 tools/buzz_soak.py                     five minutes, all fingers
    python3 tools/buzz_soak.py --minutes 10
    python3 tools/buzz_soak.py --finger pinky
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FINGERS = ("index", "middle", "ring", "pinky")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=None,
                    help="serial port, discovered if not given")
    ap.add_argument("--minutes", type=float, default=5.0)
    ap.add_argument("--every", type=float, default=6.0,
                    help="seconds between buzzes")
    ap.add_argument("--finger", choices=FINGERS, default=None,
                    help="just one finger, instead of all four in turn")
    args = ap.parse_args()

    try:
        import serial
    except ImportError:
        print("pyserial is not installed. pip install pyserial")
        return 2

    port = args.port
    if not port:
        from rehab.hardware.serial_source import discover_ports
        found = discover_ports(None)
        if not found:
            print("No Arduino found. Pass --port /dev/cu.something")
            return 2
        port = found[0]

    print(f"Opening {port}")
    try:
        s = serial.Serial(port, 115200, timeout=0.2)
    except serial.SerialException as e:
        print(f"Could not open {port}: {e}")
        return 2

    # Opening resets the board. It buzzes each motor once as a self-test
    # and prints a banner before it starts streaming, which takes about
    # 2.6 s. That first round of buzzing is the firmware checking itself.
    print("Waiting for the board to boot (it self-tests the motors first)")
    time.sleep(3.0)
    s.reset_input_buffer()
    boot = time.time()

    lanes = ([FINGERS.index(args.finger)] if args.finger
             else list(range(len(FINGERS))))
    print()
    print("Rest your hand on the pads. Each line below is a real buzz.")
    print("If one stops being felt past about a minute of uptime, the")
    print("16-bit deadline bug is back.")
    print()
    print(f"{'uptime':>8}  finger   sent")
    print("-" * 34)

    end = boot + args.minutes * 60
    i = 0
    try:
        while time.time() < end:
            lane = lanes[i % len(lanes)]
            i += 1
            up = time.time() - boot
            ok = True
            try:
                # Re-arm across the firmware's 150 ms hold so the buzz
                # runs about half a second and is easy to feel.
                for _ in range(4):
                    s.write(f"STIM:{lane + 1}\n".encode())
                    s.flush()
                    time.sleep(0.13)
            except (serial.SerialException, OSError) as e:
                ok = False
                print(f"{up:7.0f}s  {FINGERS[lane]:8} WRITE FAILED: {e}")
            if ok:
                past = "  <- past the old 65.5 s wrap" if up > 66 else ""
                print(f"{up:7.0f}s  {FINGERS[lane]:8} STIM:{lane + 1}{past}")
            # Drain whatever arrived so the buffer cannot fill up.
            s.reset_input_buffer()
            time.sleep(max(0.0, args.every - 0.6))
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        try:
            s.write(b"STOP\n")
            s.flush()
        except Exception:
            pass
        s.close()
    print()
    print("Every finger still felt at the end means the fix holds.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
