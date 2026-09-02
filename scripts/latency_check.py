"""Bench the stimulus delays the game cannot see, for config latency.*.

The software knows when it SENT a buzz or flipped a frame. It cannot
know when the pad started moving or the pixels changed, and those are
the moments a patient reacts to and an EEG epoch should lock to. This
script drives the rig on a fixed schedule so a phone camera or a piezo
disc can measure the gap, and writes every send time to a CSV so the
recording can be lined up with the commands afterwards.

    python3 scripts/latency_check.py                 20 pulses, 300 ms, 2 s apart
    python3 scripts/latency_check.py --reps 30 --pulse 300 --every 2
    python3 scripts/latency_check.py --finger ring
    python3 scripts/latency_check.py --display       flip a white tile with each STIM
    python3 scripts/latency_check.py --out my.csv

Nothing but STIM and STOP goes to the board, so every flash of the
Nano's RX LED is one of these commands. The CSV lands in
config/calibration/ (never under sessions/).

WHAT TO MEASURE, and where each number goes

A. Motor, phone at 240 fps (4.2 ms per frame).
   Tape a 5 mm paper flag to the motor or the pad. Frame the Nano's RX
   LED and the flag together. Run this script. In the slow-motion clip
   count frames from the LED flash to the first flag motion (lag), to
   the flag reaching a steady blur (rise), and from the STOP flash to
   the flag standing still (stop). Median of the reps for each.
     latency.buzzer_ms   = lag, in ms (frames x 4.17)
   Rise and stop are for the thesis methods and Buzz Hunt's gap floor;
   the game only shifts by the lag.

B. Motor, piezo disc.
   A piezo disc taped to the pad into the laptop's mic input (Audacity,
   44.1 kHz), with the phone clip of the RX LED as the time reference,
   or a phototransistor across the RX LED on the second channel if a
   stereo input is there. Onset is the first excursion above 3 SD of
   the noise floor; report lag, 50 percent rise and stop. Same keys as
   A. This is the accelerometer-style characterisation the Buzz Hunt
   docstring has been waiting for.

C. Display.
   Phone at 240 fps framing a screen tile and the RX LED while this
   script runs with --display: it fills a tile white on the same frame
   it sends the STIM and black with the STOP. Frames from the LED
   flash to the tile changing is the display lag relative to the
   command; do it with the tile at the top, middle and bottom of the
   screen to see the scan. The game's marker is written straight
   after the flip, so
     latency.visual_ms   = tile change minus flip, mid-screen, in ms
   which is the LED-to-tile figure minus the command-to-flip gap this
   script prints (it flips first, then writes, so that gap is under
   1 ms here).

D. Audio.
   Loopback from the headphone jack into the mic input with the cue
   tone playing; the tone's own onset against the marker gives
   latency.tone_ms, and a song's beat against its beatmap gives
   rhythm.audio_offset_ms. Not driven by this script.

Then in config/default.yaml (or user_settings.yaml) set the numbers,
latency.measured: true and latency.measured_on to the date, and rerun
the rhythm block: the buzz lead and the falling notes read them.
"""
from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

FINGERS = ("index", "middle", "ring", "pinky")
BAUD = 115200
BOOT_WAIT_S = 3.0


def run_pulses(port, reps: int, every_s: float, pulse_ms: float,
               channel: int, clock=time.perf_counter, sleep=time.sleep,
               on_stim=None, on_stop=None) -> list[dict]:
    """Send `reps` STIM/STOP pairs on a fixed schedule and return one
    row per pulse with the perf_counter time of each write.

    `port` needs only write(bytes). `on_stim` and `on_stop` run just
    BEFORE the matching write (the display tile flips there, so the
    pixels and the command share a frame). Clock and sleep are
    injectable so the schedule can be tested without waiting.
    """
    rows: list[dict] = []
    stim = f"STIM:{int(channel)}\n".encode()
    stop = b"STOP\n"
    t0 = clock()
    for i in range(int(reps)):
        due = t0 + i * float(every_s)
        wait = due - clock()
        if wait > 0:
            sleep(wait)
        if on_stim is not None:
            on_stim()
        t_stim = clock()
        port.write(stim)
        t_stim_done = clock()
        wait = (t_stim + float(pulse_ms) / 1000.0) - clock()
        if wait > 0:
            sleep(wait)
        if on_stop is not None:
            on_stop()
        t_stop = clock()
        port.write(stop)
        rows.append({
            "rep": i + 1,
            "t_stim": f"{t_stim:.6f}",
            "t_stim_written": f"{t_stim_done:.6f}",
            "t_stop": f"{t_stop:.6f}",
            "requested_pulse_ms": f"{float(pulse_ms):.1f}",
            "achieved_pulse_ms": f"{(t_stop - t_stim) * 1000.0:.2f}",
        })
    return rows


def default_out_path(root: Path) -> Path:
    return root / "config" / "calibration" / (
        f"latency_check_{date.today().isoformat()}.csv")


class _Tile:
    """A pygame window with one tile that goes white on STIM and black
    on STOP, flipped before the command is written."""

    def __init__(self, size: tuple[int, int], tile_frac: float) -> None:
        import pygame
        pygame.init()
        self.pygame = pygame
        self.screen = pygame.display.set_mode(size)
        pygame.display.set_caption("latency check")
        w, h = size
        side = int(min(w, h) * 0.25)
        # tile_frac places the tile down the screen: 0 top, 0.5
        # middle, 1 bottom, so the scan can be seen.
        y = int((h - side) * max(0.0, min(1.0, tile_frac)))
        self.rect = pygame.Rect((w - side) // 2, y, side, side)
        self._paint((0, 0, 0))

    def _paint(self, colour) -> None:
        self.screen.fill((0, 0, 0))
        self.pygame.draw.rect(self.screen, colour, self.rect)
        self.pygame.display.flip()
        # Let the OS process window events so the window stays alive.
        self.pygame.event.pump()

    def on(self) -> None:
        self._paint((255, 255, 255))

    def off(self) -> None:
        self._paint((0, 0, 0))

    def close(self) -> None:
        self.pygame.quit()


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Drive the rig on a fixed schedule for a latency "
                    "bench (phone at 240 fps or piezo); see the module "
                    "docstring for the procedure.")
    ap.add_argument("--port", default=None,
                    help="serial port, discovered if not given")
    ap.add_argument("--reps", type=int, default=20)
    ap.add_argument("--pulse", type=float, default=300.0,
                    help="ms from STIM to STOP")
    ap.add_argument("--every", type=float, default=2.0,
                    help="seconds between pulses")
    ap.add_argument("--finger", choices=FINGERS, default="index")
    ap.add_argument("--display", action="store_true",
                    help="open a window and flip a white tile with "
                         "each STIM (procedure C)")
    ap.add_argument("--tile", type=float, default=0.5,
                    help="tile position down the screen, 0 top to 1 "
                         "bottom (with --display)")
    ap.add_argument("--out", default=None,
                    help="CSV of send times; default "
                         "config/calibration/latency_check_<date>.csv")
    args = ap.parse_args()

    try:
        import serial
    except ImportError:
        print("pyserial is not installed. pip install pyserial")
        return 2

    root = Path(__file__).resolve().parents[1]
    from finger_rehab.config import Config
    cfg = Config.load()
    channel_map = list(cfg.get("motor.channel_map", [1, 2, 3, 4]) or
                       [1, 2, 3, 4])
    finger = FINGERS.index(args.finger)
    channel = int(channel_map[finger]) if finger < len(channel_map) \
        else finger + 1

    port_name = args.port
    if not port_name:
        from finger_rehab.hardware.serial_source import discover_ports
        found = discover_ports(None)
        if not found:
            print("No Arduino found. Pass --port /dev/cu.something")
            return 2
        port_name = found[0]

    out = Path(args.out) if args.out else default_out_path(root)
    if "sessions" in out.resolve().parts:
        print(f"Refusing to write under sessions/: {out}")
        return 2

    print(f"Opening {port_name}")
    try:
        port = serial.Serial(port_name, BAUD, timeout=0.2)
    except serial.SerialException as e:
        print(f"Could not open {port_name}: {e}")
        return 2

    print("Waiting for the board to boot (it self-tests the motors first)")
    time.sleep(BOOT_WAIT_S)
    port.reset_input_buffer()

    tile = None
    on_stim = on_stop = None
    if args.display:
        res = cfg.get("ui.resolution", [1280, 800]) or [1280, 800]
        tile = _Tile((int(res[0]), int(res[1])), args.tile)
        on_stim, on_stop = tile.on, tile.off

    print()
    print(f"{args.reps} pulses of {args.pulse:.0f} ms on the "
          f"{args.finger} (STIM:{channel}), {args.every:.1f} s apart.")
    print("Start the camera or the recording now; every RX LED flash is "
          "one of these commands.")
    print()
    try:
        rows = run_pulses(port, args.reps, args.every, args.pulse, channel,
                          on_stim=on_stim, on_stop=on_stop)
    finally:
        try:
            port.write(b"STOP\n")
            port.close()
        except Exception:
            pass
        if tile is not None:
            tile.close()

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows
                           else ["rep"])
        w.writeheader()
        for r in rows:
            w.writerow(r)
    achieved = [float(r["achieved_pulse_ms"]) for r in rows]
    if achieved:
        achieved.sort()
        print(f"Sent {len(rows)} pulses; host-side pulse "
              f"{achieved[0]:.1f} to {achieved[-1]:.1f} ms "
              f"(requested {args.pulse:.0f}).")
    print(f"Send times written to {out}")
    print("Now count frames in the clip (procedure A or C in the "
          "docstring) and put the medians in config latency.*.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
