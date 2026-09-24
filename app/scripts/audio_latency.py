"""Measure this laptop's sound and buzz delays and save them for the
game: rhythm.audio_offset_ms, rhythm.metronome_offset_ms,
latency.tone_ms and latency.buzzer_ms.

Rhythm scores a tap against song_time, which starts the moment the
game calls mixer.music.play (audio/engine.py). The song reaches the ear
later than that, and the game subtracts rhythm.audio_offset_ms to make
up for it; in the study block the buzz and the falling note are timed
to the same corrected beat (rhythm.tactile_mode on_beat), less the
motor's own lag, latency.buzzer_ms. Wrong values move every
participant's mean asynchrony, which Rh1 tests, and pull the sound,
the touch and the sight of a beat apart.

How it measures, with nobody at the rig:

  1. The built-in microphone's own delay, from CoreAudio: the fixed
     input latency the HAL reports, device latency plus stream
     latency plus safety offset, the sum PortAudio's CoreAudio host
     uses (pa_mac_core.c, CalculateFixedDeviceLatency). The buffer
     does not add: each recorded sample is timed from the earliest
     buffer to arrive, which cancels the wait for a buffer to fill
     (checked: capture chunks of 256, 512 and 2048 frames gave the
     same round trip within 4 ms).
  2. The song path: the study track through the game's own mixer
     settings (44.1 kHz, 512-sample buffer), recorded, and lined up
     with the decoded file on its attacks. Less the microphone's delay
     it is the play call to the speaker: rhythm.audio_offset_ms.
  3. The short-sound path: a click through a Sound channel, lined up
     on its waveform: latency.tone_ms and rhythm.metronome_offset_ms.
  4. The motor, when the board is plugged in: every motor pulsed ten
     times, the buzz's sound envelope averaged over the pulses and its
     onset read where it first clears 5 SD of the averaged noise,
     which sits at a few percent of the full buzz, the same point the
     motor datasheets call the lag (0.08 G). Less the microphone's
     delay it is the STIM command to motion: latency.buzzer_ms.

    python3 app/scripts/audio_latency.py            measure and print
    python3 app/scripts/audio_latency.py --write    and save for the game
    python3 app/scripts/audio_latency.py --tap      time the microphone
                                                    by fingernail taps on
                                                    the index pad instead
                                                    (any OS; you tap)

--write saves app/config/latency_profile.yaml (per machine, never
committed), which the game lays over default.yaml at every start and
records in every block's config snapshot, so the analysis can see the
numbers were measured. Keep the room quiet and the volume where a
participant would have it; allow microphone access if macOS asks.
Re-run it on any other laptop, or after changing the audio output.
A CSV of every take lands in config/calibration/.
"""
from __future__ import annotations

import argparse
import csv
import os
import statistics
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
# Host receive time of a board sample, after the physical event: the
# USB and 115200-baud line (about 1 ms) and half a 5 ms sample period.
BOARD_DELAY_MS = 3.5


# ---- the microphone's own delay ------------------------------------------
def coreaudio_input_ms() -> tuple[float | None, dict]:
    """The default input device's fixed latency in ms, and the parts,
    from CoreAudio. None off macOS or when the HAL will not say."""
    if sys.platform != "darwin":
        return None, {}
    try:
        import ctypes
        import ctypes.util
        import struct
        ca = ctypes.cdll.LoadLibrary(ctypes.util.find_library("CoreAudio"))
    except Exception:
        return None, {}

    def fcc(s: str) -> int:
        return struct.unpack(">I", s.encode())[0]

    class Addr(ctypes.Structure):
        _fields_ = [("sel", ctypes.c_uint32), ("scope", ctypes.c_uint32),
                    ("elem", ctypes.c_uint32)]

    get = ca.AudioObjectGetPropertyData
    get.argtypes = [ctypes.c_uint32, ctypes.POINTER(Addr), ctypes.c_uint32,
                    ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32),
                    ctypes.c_void_p]
    size = ca.AudioObjectGetPropertyDataSize
    size.argtypes = [ctypes.c_uint32, ctypes.POINTER(Addr), ctypes.c_uint32,
                     ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32)]
    glob, inp = fcc("glob"), fcc("inpt")

    def u32(obj, sel, scope):
        v, n = ctypes.c_uint32(0), ctypes.c_uint32(4)
        ok = get(obj, ctypes.byref(Addr(fcc(sel), scope, 0)), 0, None,
                 ctypes.byref(n), ctypes.byref(v)) == 0
        return v.value if ok else None

    dev = u32(1, "dIn ", glob)
    if not dev:
        return None, {}
    rate, n = ctypes.c_double(0), ctypes.c_uint32(8)
    if get(dev, ctypes.byref(Addr(fcc("nsrt"), glob, 0)), 0, None,
           ctypes.byref(n), ctypes.byref(rate)) != 0 or rate.value <= 0:
        return None, {}
    a, n = Addr(fcc("stm#"), inp, 0), ctypes.c_uint32(0)
    streams = []
    if size(dev, ctypes.byref(a), 0, None, ctypes.byref(n)) == 0 and n.value:
        arr = (ctypes.c_uint32 * (n.value // 4))()
        if get(dev, ctypes.byref(a), 0, None, ctypes.byref(n), arr) == 0:
            streams = list(arr)
    parts = {"device_frames": u32(dev, "ltnc", inp) or 0,
             "safety_frames": u32(dev, "saft", inp) or 0,
             "stream_frames": (u32(streams[0], "ltnc", glob) or 0)
             if streams else 0,
             "buffer_frames": u32(dev, "fsiz", inp) or 0,
             "rate_hz": rate.value}
    fixed = (parts["device_frames"] + parts["safety_frames"]
             + parts["stream_frames"])
    return fixed / rate.value * 1000.0, parts


# ---- recording ------------------------------------------------------------
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
    sample i sits at t_rec0 + i / SR. A song is matched on its
    envelope, whose attacks survive a speaker, a room and a microphone;
    a click on its waveform, which no room echo outranks."""
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


def averaged_onset_ms(data, t0: float, cmd_times: list[float],
                      thresh_sd: float = 5.0) -> float | None:
    """Onset of a repeated sound, ms after its command: the 1 ms
    envelope averaged over every pulse, read where it first clears
    thresh_sd of the averaged pre-command noise. Averaging is what
    lets a buzz's first few percent show above a room's noise."""
    import numpy as np
    env = np.convolve(np.abs(data), np.ones(44) / 44, mode="same")
    pre, post = int(0.1 * SR), int(0.4 * SR)
    segs = []
    for tc in cmd_times:
        i = int(round((tc - t0) * SR))
        if i - pre >= 0 and i + post < len(env):
            segs.append(env[i - pre:i + post])
    if len(segs) < 3:
        return None
    m = np.mean(segs, axis=0)
    base = m[:pre - int(0.005 * SR)]
    mu, sd = float(base.mean()), float(base.std())
    after = m[pre:]
    # Ignore the first 20 ms: nothing mechanical moves that fast, and
    # the USB write itself can tick the microphone.
    lo = int(0.02 * SR)
    hit = np.where(after[lo:] > mu + thresh_sd * max(sd, 1e-12))[0]
    if not len(hit):
        return None
    return (lo + int(hit[0])) / SR * 1000.0


# ---- the board --------------------------------------------------------------
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
                raise RuntimeError("no hand board found")
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


def run_tap(port: str | None, seconds: float) -> float | None:
    """The microphone's delay by hand: a fingernail tap on the index
    pad is heard and felt at the same instant, and the board's time
    for it is known to a few ms."""
    import numpy as np
    board = Board(port)
    print(f"Board on {board.port}. Starting up...")
    board.boot()
    rec = Recorder()
    rec.start()
    print(f"\nTap the INDEX pad firmly with a fingernail, about once a "
          f"second, until it says stop ({seconds:.0f} s).")
    time.sleep(seconds)
    data, anchor = rec.stop()
    board.close()
    print("stop.")
    t = np.array(board.t)
    v = np.array([row[0] for row in board.v], dtype=float)
    if len(v) < 100 or anchor is None:
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
    print(f"{len(presses)} taps, {len(sounds)} sounds, {len(diffs)} paired")
    if len(diffs) < 5:
        return None
    return statistics.median(diffs)


def run_motors(port: str | None, pulses: int) -> dict[int, float]:
    """Command-to-audible-onset per motor, to the microphone."""
    board = Board(port)
    board.boot()
    rec = Recorder()
    rec.start()
    time.sleep(1.5)
    cmds: dict[int, list[float]] = {1: [], 2: [], 3: [], 4: []}
    for _ in range(pulses):
        for ch in (1, 2, 3, 4):
            cmds[ch].append(board.stim(ch))
            time.sleep(0.8)
    data, anchor = rec.stop()
    board.close()
    out = {}
    for ch, times in cmds.items():
        on = averaged_onset_ms(data, anchor, times) if anchor else None
        if on is not None:
            out[ch] = on
    return out


# ---- the sound paths --------------------------------------------------------
def run_sound(takes: int, seconds: float, volume: float):
    import numpy as np
    import pygame
    from finger_rehab.audio.beatmap import decode_mono
    song, _ = decode_mono(TRACK, sr=SR)
    song = song[: int(seconds * SR)]
    t = np.arange(int(0.03 * SR)) / SR
    click = (0.8 * np.sin(2 * np.pi * 1000 * t)
             * np.exp(-t / 0.008)).astype(np.float32)
    snd = pygame.sndarray.make_sound(
        (np.column_stack([click, click]) * 32767).astype(np.int16))
    rows = []
    for path in ("song", "click"):
        for take in range(1, takes + 1):
            rec = Recorder()
            rec.start()
            time.sleep(0.6)
            if path == "song":
                pygame.mixer.music.load(str(TRACK))
                pygame.mixer.music.set_volume(volume)
                t_play = time.perf_counter()
                pygame.mixer.music.play()
                time.sleep(seconds + MAX_LAG_S + 0.3)
                pygame.mixer.music.stop()
                ref = song
            else:
                snd.set_volume(volume)
                t_play = time.perf_counter()
                snd.play()
                time.sleep(MAX_LAG_S + 0.6)
                ref = click
            data, anchor = rec.stop()
            lag, strength = (_lag(data, ref, anchor, t_play,
                                  envelope=(path == "song"))
                             if anchor is not None else (float("nan"), 0))
            ok = strength >= 6.0 and lag == lag
            rows.append({"path": path, "take": take,
                         "to_mic_ms": round(lag, 2) if lag == lag else "",
                         "strength": round(strength, 1), "usable": ok})
            print(f"  {path:5s} take {take}: "
                  + (f"{lag:6.1f} ms to the microphone" if ok else
                     f"no clear alignment (strength {strength:.1f})"))
            time.sleep(0.4)
    return rows


def write_profile(values: dict, detail: dict) -> Path:
    import yaml
    from finger_rehab import config as cfgmod
    path = cfgmod.LATENCY_PROFILE
    path.parent.mkdir(parents=True, exist_ok=True)
    doc = {
        "latency": {"measured": True,
                    "measured_on": time.strftime("%Y-%m-%d"),
                    **{k: v for k, v in values.items()
                       if k in ("buzzer_ms", "tone_ms")}},
        "rhythm": {k: v for k, v in values.items()
                   if k in ("audio_offset_ms", "metronome_offset_ms")},
    }
    header = ("# This laptop's measured delays, written by "
              "scripts/audio_latency.py.\n# Laid over default.yaml at "
              "every start (config.LATENCY_PROFILE); per machine,\n# never "
              "committed. Re-run the script on another laptop.\n")
    body = yaml.safe_dump(doc, sort_keys=False)
    notes = "".join(f"# {k}: {v}\n" for k, v in detail.items())
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(header + notes + body, encoding="utf-8")
    os.replace(tmp, path)
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--takes", type=int, default=5)
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--volume", type=float, default=0.4)
    ap.add_argument("--pulses", type=int, default=10,
                    help="per motor")
    ap.add_argument("--port", default=None, help="the hand board's port")
    ap.add_argument("--tap", action="store_true",
                    help="time the microphone by fingernail taps")
    ap.add_argument("--tap-seconds", type=float, default=20.0)
    ap.add_argument("--write", action="store_true",
                    help="save the result for the game")
    args = ap.parse_args()
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.mixer.pre_init(SR, -16, 2, CHUNK)
    pygame.init()
    pygame.mixer.init()

    mic_ms, parts = coreaudio_input_ms()
    method = "CoreAudio fixed input latency"
    if args.tap or mic_ms is None:
        method = "fingernail taps on the index pad"
        mic_ms = run_tap(args.port, args.tap_seconds)
    if mic_ms is None:
        print("The microphone's own delay is unknown (no CoreAudio figure "
              "and no usable taps), so nothing is saved.")
        return 1
    print(f"microphone delay: {mic_ms:.1f} ms ({method}"
          + (f": device {parts['device_frames']} + stream "
             f"{parts['stream_frames']} + safety {parts['safety_frames']} "
             f"frames at {parts['rate_hz']:.0f} Hz" if parts and
             method.startswith("CoreAudio") else "") + ")")

    print("\nsound paths:")
    rows = run_sound(args.takes, args.seconds, args.volume)
    motors: dict[int, float] = {}
    try:
        print(f"\nmotors (the board buzzes each finger {args.pulses} "
              f"times):")
        motors = run_motors(args.port, args.pulses)
    except Exception as e:
        print(f"  skipped: {e}")
    pygame.quit()

    def med(path):
        vals = [r["to_mic_ms"] for r in rows if r["path"] == path
                and r["usable"]]
        return statistics.median(vals) if len(vals) >= 3 else None

    song, click = med("song"), med("click")
    values, detail = {}, {"microphone_delay_ms": round(mic_ms, 1),
                          "microphone_method": method,
                          "visual_ms": "not measured here (needs a "
                                       "photodiode); it moves only where "
                                       "the falling note is drawn, never "
                                       "a score"}
    print("\nresult (play call or STIM command to the sound leaving the "
          "device):")
    if song is not None:
        values["audio_offset_ms"] = round(song - mic_ms)
        detail["song_to_mic_median_ms"] = round(song, 1)
        print(f"  rhythm.audio_offset_ms      {values['audio_offset_ms']:4d} "
              f"(song to microphone {song:.0f}, less {mic_ms:.0f})")
    if click is not None:
        values["tone_ms"] = round(click - mic_ms)
        values["metronome_offset_ms"] = values["tone_ms"]
        detail["click_to_mic_median_ms"] = round(click, 1)
        print(f"  latency.tone_ms             {values['tone_ms']:4d} "
              f"(click to microphone {click:.0f}, less {mic_ms:.0f})")
        print(f"  rhythm.metronome_offset_ms  {values['tone_ms']:4d} "
              f"(the same short-sound path)")
    if motors:
        onset = statistics.median(motors.values())
        values["buzzer_ms"] = round(onset - mic_ms)
        detail["motor_onsets_to_mic_ms"] = {k: round(v, 1)
                                            for k, v in motors.items()}
        print(f"  latency.buzzer_ms           {values['buzzer_ms']:4d} "
              f"(motor onsets to microphone "
              + ", ".join(f"{k}: {v:.0f}" for k, v in motors.items())
              + f", median less {mic_ms:.0f})")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = APP / "config" / "calibration" / f"audio_latency_{stamp}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"\ntakes -> {out}")
    if args.write:
        if not {"audio_offset_ms", "tone_ms"} <= set(values):
            print("Not saved: the song or the click path had too few "
                  "usable takes. Quieter room, a little more volume.")
            return 1
        print(f"saved -> {write_profile(values, detail)}")
    else:
        print("Nothing saved; run with --write to save it for the game.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
