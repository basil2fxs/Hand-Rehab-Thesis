"""Measure how late the laptop's sound is, for rhythm.audio_offset_ms
and latency.tone_ms.

Rhythm scores a tap against song_time, which starts the moment the
game calls mixer.music.play (audio/engine.py). The song reaches the ear
later than that by the audio output delay, and the game subtracts
rhythm.audio_offset_ms (40, a typical figure, never measured on this
laptop) to make up for it. A wrong offset moves every participant's
mean asynchrony by the same amount: Rh2 (the SD) is untouched, Rh1
(the sign of the mean) is read against it.

This plays the study track through the game's own mixer settings
(44.1 kHz, 512-sample buffer) while the built-in microphone records,
and lines the recording up against the decoded song. It does the same
for a short click through the Sound channel, the path the cue tone
and the metronome take. Nothing but the laptop is needed: the speaker
and the microphone are in the same case.

    python3 scripts/audio_latency.py              3 takes of each path
    python3 scripts/audio_latency.py --takes 5 --volume 0.4
    python3 scripts/audio_latency.py --with-board   and the mic and motor

--with-board also times the microphone itself (you tap the index pad
with a fingernail for 15 s: the pad and the microphone feel and hear
the same instant) and the index motor's buzz, so the song and click
figures come out as true output delays and the motor as
latency.buzzer_ms.

Without --with-board every figure includes the microphone's own
input delay, so it is an UPPER bound on the output delay. The first run may ask for microphone access; allow it, or every
take reads as silence and the script says so. Keep the room quiet and
the volume where a participant would have it. A CSV of every take
lands in config/calibration/ (never under sessions/).
"""
from __future__ import annotations

import argparse
import csv
import os
import sys
import threading
import time
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

SR = 44100
CHUNK = 512
TRACK = APP / "assets" / "music" / "Easy_Lemon.mp3"
MAX_LAG_S = 0.6


class Recorder:
    """The built-in microphone through SDL, with the perf_counter time
    of each sample worked out from the callback times: the earliest
    callback (least scheduling delay) anchors the stream."""

    def __init__(self) -> None:
        import pygame._sdl2.audio as sa
        self.chunks: list = []
        self.anchor: float | None = None
        self.n = 0
        self._lock = threading.Lock()
        names = sa.get_audio_device_names(True)
        if not names:
            raise SystemExit("No microphone found.")
        self.dev = sa.AudioDevice(
            devicename=names[0], iscapture=True, frequency=SR,
            audioformat=sa.AUDIO_F32, numchannels=1, chunksize=CHUNK,
            allowed_changes=0, callback=self._cb)
        self.name = names[0]

    def _cb(self, _dev, mem) -> None:
        import numpy as np
        now = time.perf_counter()
        data = np.frombuffer(bytes(mem), dtype=np.float32).copy()
        with self._lock:
            self.n += len(data)
            start = now - self.n / SR
            if self.anchor is None or start < self.anchor:
                self.anchor = start
            self.chunks.append(data)

    def start(self) -> None:
        self.dev.pause(0)

    def stop(self):
        import numpy as np
        self.dev.pause(1)
        self.dev.close()
        with self._lock:
            return np.concatenate(self.chunks) if self.chunks else \
                np.zeros(0, dtype=np.float32), self.anchor


def _envelope(x, w: int = 220):
    """Rising edges of the smoothed amplitude: what a room and a laptop
    microphone leave of a song, and what lines up with it."""
    import numpy as np
    e = np.convolve(np.abs(x), np.ones(w) / w, mode="same")
    d = np.diff(e, prepend=e[0])
    d[d < 0] = 0
    return d


def _lag(rec, ref, t_rec0: float, t_play: float,
         envelope: bool = True) -> tuple[float, float]:
    """(delay in ms from the play call to the sound in the recording,
    peak strength against the correlation's spread). The recording's
    sample i sits at t_rec0 + i / SR. Matched on the envelopes: the
    raw waveform through a speaker, a room and a microphone correlates
    weakly with the file, the attacks do not."""
    import numpy as np
    from scipy.signal import correlate
    start = int(round((t_play - t_rec0) * SR))
    seg = rec[max(0, start):max(0, start) + len(ref) + int(MAX_LAG_S * SR)]
    if len(seg) < len(ref) // 2 or not np.any(seg):
        return float("nan"), 0.0
    if envelope:
        seg, ref = _envelope(seg), _envelope(ref)
    c = correlate(seg - seg.mean(), ref - ref.mean(), mode="valid",
                  method="fft")
    c = np.abs(c[: int(MAX_LAG_S * SR)])
    k = int(np.argmax(c))
    strength = float(c[k] / (np.median(c) + 1e-12))
    offset = max(0, start) - start
    return (k - offset) / SR * 1000.0, strength


# Host receive time of a board sample, after the physical event: the
# USB and 115200-baud line (about 1 ms) and half a 5 ms sample period.
BOARD_DELAY_MS = 3.5


class Board:
    """The hand board on its serial port, every FSR line stamped with
    perf_counter as it arrives."""

    def __init__(self, port: str | None) -> None:
        import serial
        from serial.tools import list_ports
        if port is None:
            found = [p.device for p in list_ports.comports()
                     if "usbserial" in p.device or "usbmodem" in p.device
                     or p.device.upper().startswith("COM")]
            if not found:
                raise SystemExit("No hand board found. Plug it in, or "
                                 "pass --port.")
            port = found[0]
        self.port = port
        self.s = serial.Serial(port, 115200, timeout=0.05)
        self.t: list = []
        self.v: list = []
        self._stop = threading.Event()
        self._th = threading.Thread(target=self._read, daemon=True)

    def boot(self) -> None:
        t_end = time.time() + 8
        while time.time() < t_end:
            if b"Setup Complete" in self.s.readline():
                break
        time.sleep(0.6)
        self.s.reset_input_buffer()
        self._th.start()

    def _read(self) -> None:
        while not self._stop.is_set():
            line = self.s.readline()
            if line.startswith(b"FSR:"):
                try:
                    vals = [int(x) for x in line[4:].split(b",")]
                except ValueError:
                    continue
                self.t.append(time.perf_counter())
                self.v.append(vals)

    def stim(self, channel: int) -> float:
        self.s.write(f"STIM:{channel}\n".encode())
        return time.perf_counter()

    def close(self) -> None:
        self._stop.set()
        self._th.join(timeout=1)
        try:
            self.s.write(b"STOP\n")
        except Exception:
            pass
        self.s.close()


def _mic_onsets(data, t0: float, thresh_sd: float = 8.0,
                refractory_s: float = 0.3) -> list[float]:
    """perf_counter times of sharp sound onsets in a recording."""
    import numpy as np
    e = np.convolve(np.abs(data), np.ones(44) / 44, mode="same")
    base = np.median(e)
    spread = np.median(np.abs(e - base)) * 1.4826 + 1e-9
    above = np.where(e > base + thresh_sd * spread)[0]
    out, last = [], -1e9
    for i in above:
        if i - last > refractory_s * SR:
            out.append(t0 + i / SR)
        last = i if i - last > refractory_s * SR else last
    return out


def run_tap(args) -> float | None:
    """The microphone's own delay: a fingernail tap on the index pad is
    heard and felt at the same instant, and the board's time for it is
    known to a few ms. Returns the delay in ms, or None."""
    import numpy as np
    board = Board(args.port)
    print(f"Board on {board.port}. Starting up...")
    board.boot()
    rec = Recorder()
    rec.start()
    print(f"\nTap the INDEX pad firmly with a fingernail, about once a "
          f"second, until it says stop ({args.tap_seconds:.0f} s). Keep "
          f"the rest of the room quiet.")
    time.sleep(args.tap_seconds)
    data, anchor = rec.stop()
    board.close()
    print("stop.")
    t = np.array(board.t)
    v = np.array([row[0] for row in board.v], dtype=float)
    if len(v) < 100 or anchor is None:
        print("No board or microphone data.")
        return None
    base = np.median(v)
    spread = np.median(np.abs(v - base)) * 1.4826 + 1.0
    hits = np.where(np.abs(v - base) > max(15.0, 6 * spread))[0]
    presses, last = [], -1e9
    for i in hits:
        if t[i] - last > 0.3:
            presses.append(t[i])
        last = t[i] if t[i] - last > 0.3 else last
    sounds = _mic_onsets(data, anchor)
    diffs = []
    for tp in presses:
        near = [ts - tp for ts in sounds if -0.03 < ts - tp < 0.2]
        if near:
            diffs.append(min(near, key=abs) * 1000.0 + BOARD_DELAY_MS)
    print(f"{len(presses)} taps on the pad, {len(sounds)} sounds, "
          f"{len(diffs)} paired")
    if len(diffs) < 5:
        print("Too few paired taps for a figure: tap harder, one at a "
              "time.")
        return None
    diffs.sort()
    med = diffs[len(diffs) // 2]
    print(f"microphone delay: median {med:.1f} ms, range {diffs[0]:.1f} "
          f"to {diffs[-1]:.1f}")
    return med


def run_motor(args, mic_ms: float | None) -> float | None:
    """The buzz: STIM on the index motor, heard by the microphone. With
    the microphone's delay known this is the command-to-motion lag,
    latency.buzzer_ms."""
    board = Board(args.port)
    print(f"Board on {board.port}. Starting up...")
    board.boot()
    rec = Recorder()
    rec.start()
    time.sleep(0.8)
    cmds = []
    for _ in range(args.takes * 3):
        cmds.append(board.stim(1))
        time.sleep(1.2)
    data, anchor = rec.stop()
    board.close()
    if anchor is None:
        return None
    sounds = _mic_onsets(data, anchor, thresh_sd=6.0)
    lags = []
    for tc in cmds:
        near = [ts - tc for ts in sounds if 0.0 < ts - tc < 0.3]
        if near:
            lags.append(min(near) * 1000.0 - (mic_ms or 0.0))
    if len(lags) < 3:
        print("The buzz was not heard clearly enough.")
        return None
    lags.sort()
    med = lags[len(lags) // 2]
    what = "command to buzz" if mic_ms is not None else \
        "command to buzz, microphone delay NOT removed"
    print(f"{what}: median {med:.1f} ms over {len(lags)} pulses, range "
          f"{lags[0]:.1f} to {lags[-1]:.1f}")
    return med


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--takes", type=int, default=3)
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--volume", type=float, default=0.5)
    ap.add_argument("--port", default=None, help="the hand board's port")
    ap.add_argument("--with-board", action="store_true",
                    help="also time the microphone with fingernail taps on "
                         "the index pad (you tap) and the index motor's "
                         "buzz, so every figure comes out as the true "
                         "delay")
    ap.add_argument("--tap-only", action="store_true",
                    help="only the fingernail-tap timing of the "
                         "microphone")
    ap.add_argument("--tap-seconds", type=float, default=15.0)
    args = ap.parse_args()
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    if args.tap_only:
        import pygame
        pygame.init()
        run_tap(args)
        pygame.quit()
        return 0
    import numpy as np
    import pygame
    from finger_rehab.audio.beatmap import decode_mono
    pygame.mixer.pre_init(SR, -16, 2, CHUNK)
    pygame.init()
    pygame.mixer.init()
    song, _ = decode_mono(TRACK, sr=SR)
    song = song[: int(args.seconds * SR)]
    t = np.arange(int(0.03 * SR)) / SR
    click = (0.8 * np.sin(2 * np.pi * 1000 * t)
             * np.exp(-t / 0.008)).astype(np.float32)
    snd = pygame.sndarray.make_sound(
        (np.column_stack([click, click]) * 32767).astype(np.int16))
    rows = []
    for path in ("song", "click"):
        for take in range(1, args.takes + 1):
            rec = Recorder()
            rec.start()
            time.sleep(0.6)
            if path == "song":
                pygame.mixer.music.load(str(TRACK))
                pygame.mixer.music.set_volume(args.volume)
                t_play = time.perf_counter()
                pygame.mixer.music.play()
                time.sleep(args.seconds + MAX_LAG_S + 0.3)
                pygame.mixer.music.stop()
                ref = song
            else:
                snd.set_volume(args.volume)
                t_play = time.perf_counter()
                snd.play()
                time.sleep(MAX_LAG_S + 0.6)
                ref = click
            data, anchor = rec.stop()
            # The song on its attacks, the click on its waveform: a
            # room echo can outrank a click's envelope, never its
            # 1 kHz ring.
            lag, strength = (_lag(data, ref, anchor, t_play,
                                  envelope=(path == "song"))
                             if anchor is not None else (float("nan"), 0))
            ok = strength >= 6.0 and lag == lag
            rows.append({"path": path, "take": take,
                         "delay_ms": round(lag, 2) if lag == lag else "",
                         "strength": round(strength, 1), "usable": ok})
            print(f"  {path:5s} take {take}: "
                  + (f"{lag:6.1f} ms (peak {strength:.0f}x)" if ok else
                     f"no clear peak (strength {strength:.1f})"))
            time.sleep(0.5)
    mic_ms = motor_ms = None
    if args.with_board:
        mic_ms = run_tap(args)
        motor_ms = run_motor(args, mic_ms)
        rows.append({"path": "mic_input", "take": 0,
                     "delay_ms": "" if mic_ms is None else round(mic_ms, 2),
                     "strength": "", "usable": mic_ms is not None})
        rows.append({"path": "motor", "take": 0,
                     "delay_ms": "" if motor_ms is None
                     else round(motor_ms, 2),
                     "strength": "", "usable": motor_ms is not None
                     and mic_ms is not None})
    pygame.quit()
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = APP / "config" / "calibration" / f"audio_latency_{stamp}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\ntakes -> {out}")
    for path, key, now in (("song", "rhythm.audio_offset_ms", 40),
                           ("click", "latency.tone_ms", 12)):
        good = sorted(r["delay_ms"] for r in rows
                      if r["path"] == path and r["usable"])
        if not good:
            print(f"{path}: no usable take. Microphone access denied, the "
                  f"volume too low, or the room too loud.")
            continue
        med = good[len(good) // 2]
        if mic_ms is not None:
            print(f"{path}: {med - mic_ms:.0f} ms from the play call to the "
                  f"speaker ({med:.0f} to the microphone, less its "
                  f"{mic_ms:.0f} ms), over {len(good)} take(s). {key} is "
                  f"{now}.")
        else:
            print(f"{path}: median {med:.0f} ms over {len(good)} take(s), "
                  f"range {good[0]:.0f} to {good[-1]:.0f}, to the "
                  f"microphone. {key} is {now}. The true output delay is "
                  f"this less the microphone's own delay: run again with "
                  f"--with-board to measure that.")
    if motor_ms is not None and mic_ms is not None:
        print(f"motor: {motor_ms:.0f} ms from STIM to an audible buzz. "
              f"latency.buzzer_ms is 45.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
