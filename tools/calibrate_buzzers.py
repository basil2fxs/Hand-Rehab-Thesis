"""Check the buzzers are on the right fingers and pick a cue length.

The buzzer's job in this software is to tell the patient WHICH finger
to press. That only works if motor 1 is actually under the index
finger, motor 2 under the middle, and so on. A miswired or repositioned
motor would cue the wrong finger every trial and the resulting data
would be quietly wrong rather than obviously broken, so this checks the
mapping by asking which finger you actually felt.

The game now has this built in: Calibrate on the title screen runs the
same check as step 5 of its flow, and saves the result the same way.
Use this script when you want to test the motors without starting the
game, or to tune the cue length, which the in-app flow does not cover.

It then plays several cue lengths so you can pick one that is easy to
feel without being unpleasant.

    python3 tools/calibrate_buzzers.py

About strength: the firmware (Arduino_20251111.ino) drives the motors
at a fixed STIM_PWM = 200 and accepts only "STIM:n" and "STOP". There
is no command to change vibration amplitude, and the board is not being
reflashed. Duration is therefore the only property the host can vary,
which is what this tool sets. Each STIM re-arms the motor for 150 ms,
so longer cues are produced by repeating the pulse.

Default is 250 ms, chosen because about 30 ms is the floor for a
vibration to register as a vibration at all, published cueing studies
use bursts across roughly 25-400 ms, and stroke patients need markedly
more stimulation on the affected hand for the same perception.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rehab.config import Config                                # noqa: E402
from rehab.hardware.serial_source import discover_ports        # noqa: E402

try:
    import serial
except ImportError:
    print("pyserial missing. Run: pip install -r requirements.txt")
    raise SystemExit(1)


FINGERS = ("index", "middle", "ring", "pinky")
N = 4
BAUD = 115200
RESET_WAIT_S = 2.2
FIRMWARE_STIM_MS = 150          # fixed hold per STIM, set in the sketch
PULSE_GAP_MS = 120              # must stay under the hold to run smooth


def pick_port(cfg: Config) -> str:
    if len(sys.argv) > 1:
        return sys.argv[1]
    found = discover_ports(cfg.get("serial.vendor_ids"), max_ports=8)
    if not found:
        print("No Arduino detected. Plug the device in, or pass the port:")
        print("    python3 tools/calibrate_buzzers.py /dev/cu.usbserial-130")
        raise SystemExit(1)
    return found[0]


def buzz(ser, lane: int, cue_ms: int) -> None:
    """Buzz one motor (0-indexed) for roughly cue_ms, by re-arming the
    firmware's fixed-length pulse as many times as needed."""
    cmd = f"STIM:{lane + 1}\n".encode()
    ser.write(cmd)
    ser.flush()
    elapsed = 0.0
    while elapsed + FIRMWARE_STIM_MS < cue_ms:
        time.sleep(PULSE_GAP_MS / 1000.0)
        elapsed += PULSE_GAP_MS
        ser.write(cmd)
        ser.flush()
    time.sleep(max(0.0, (cue_ms - elapsed)) / 1000.0)


def ask(prompt: str, options: tuple[str, ...]) -> str:
    while True:
        a = input(prompt).strip().lower()
        if a in options:
            return a
        print(f"   please answer one of: {', '.join(options)}")


def main() -> int:
    cfg = Config.load()
    port = pick_port(cfg)
    print("=" * 62)
    print("BUZZER CALIBRATION")
    print("=" * 62)
    print(f"port: {port}")
    print("Put your hand on the device so every finger touches its pad.\n")
    try:
        ser = serial.Serial(port, BAUD, timeout=1)
    except Exception as e:
        print(f"Could not open {port}: {e}")
        print("Is the game still running? Close it first.")
        return 1

    try:
        time.sleep(RESET_WAIT_S)
        cue_ms = int(cfg.get("motor.cue_ms", 250))

        # --- part 1: is each motor under the finger we think? -------
        print("PART 1: checking each motor is under the right finger.")
        print("For each buzz, say which finger you felt it on.\n")
        wrong = []
        felt_nothing = []
        # channel_map[finger] = the STIM channel that reaches it.
        channel_map = list(range(1, N + 1))
        for i in range(N):
            input(f"  ready to buzz motor {i + 1} "
                  f"(should be {FINGERS[i].upper()}) - press Enter")
            buzz(ser, i, cue_ms)
            a = ask("   which finger felt it? "
                    "[i]ndex [m]iddle [r]ing [p]inky [n]othing: ",
                    ("i", "m", "r", "p", "n"))
            got = {"i": 0, "m": 1, "r": 2, "p": 3}.get(a)
            if a == "n":
                felt_nothing.append(i)
                print(f"   -> nothing felt on motor {i + 1}")
            elif got == i:
                channel_map[got] = i + 1
                print("   -> correct")
            else:
                wrong.append((i, got))
                channel_map[got] = i + 1
                print(f"   -> channel {i + 1} drives the "
                      f"{FINGERS[got]}, not the {FINGERS[i]}")

        print("\n" + "-" * 62)
        if wrong:
            print("WIRING DOES NOT MATCH THE SKETCH'S CHANNEL ORDER:")
            for motor, actual in wrong:
                print(f"  channel {motor + 1} reaches the {FINGERS[actual]}, "
                      f"not the {FINGERS[motor]}")
            print("\nThis does NOT need the Arduino reflashed.")
            print("Arduino_20251111.ino is final and maps STIM:1..4 onto")
            print("pins 3,4,5,6 in that order. The host can simply send")
            print("whichever channel actually reaches the finger it means,")
            print("which is what motor.channel_map below does.")
            print(f"\n  to buzz index  send STIM:{channel_map[0]}")
            print(f"  to buzz middle send STIM:{channel_map[1]}")
            print(f"  to buzz ring   send STIM:{channel_map[2]}")
            print(f"  to buzz pinky  send STIM:{channel_map[3]}")
        elif felt_nothing:
            names = ", ".join(FINGERS[i] for i in felt_nothing)
            print(f"NO BUZZ FELT ON: {names}")
            print("Check the motor wiring and that the finger is in")
            print("contact with the motor.")
        else:
            print("All four motors are on the correct fingers.")
        print("-" * 62)

        # --- part 2: pick a comfortable cue length ------------------
        print("\nPART 2: choosing how long the cue buzzes.")
        print("Strength is fixed in the firmware, so length is what makes")
        print("a cue easy or hard to notice. You will feel each option on")
        print("the index finger.\n")
        options = (150, 250, 350, 450)
        for ms in options:
            input(f"  press Enter to feel {ms} ms")
            buzz(ser, 0, ms)
            time.sleep(0.3)
        print("\n  150 = one firmware pulse, shortest possible")
        print("  250 = default, allows for reduced sensation")
        print("  350 = clearly noticeable")
        print("  450 = long, may overlap the patient's own response")
        while True:
            raw = input("\nwhich length do you want? [150/250/350/450]: ").strip()
            if raw.isdigit() and 100 <= int(raw) <= 600:
                chosen = int(raw)
                break
            print("   enter a number between 100 and 600")

        print(f"\n  testing {chosen} ms on every finger in turn...")
        for i in range(N):
            print(f"    {FINGERS[i]}")
            buzz(ser, i, chosen)
            time.sleep(0.35)

        ser.write(b"STOP\n")
        ser.flush()

        print(f"\n  chosen cue length: {chosen} ms")
        print(f"  currently in use  : {cfg.get('motor.cue_ms')} ms")
        print(f"  channel map       : {channel_map}")
        print(f"  currently in use  : {cfg.get('motor.channel_map')}")
        a = input("\nWrite to config/user_settings.yaml? [y/N] ")
        if a.strip().lower().startswith("y"):
            cfg.save_user_overrides({
                "motor.cue_ms": chosen,
                "motor.channel_map": channel_map,
            })
            print("Saved. Takes effect next time the game starts.")
        else:
            print("Not saved, nothing changed.")
        return 0
    finally:
        try:
            ser.write(b"STOP\n")
            ser.flush()
        except Exception:
            pass
        ser.close()


if __name__ == "__main__":
    raise SystemExit(main())
