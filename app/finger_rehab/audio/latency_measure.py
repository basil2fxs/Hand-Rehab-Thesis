"""Measure this computer's sound and buzz delays and save them for the
game: rhythm.audio_offset_ms, rhythm.metronome_offset_ms,
latency.tone_ms and latency.buzzer_ms.

Two front ends share this module: Settings, Setup, Audio delay (so a new
computer needs nothing installed), and scripts/audio_latency.py.

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
     same round trip within 4 ms). Where CoreAudio cannot say
     (Windows), fingernail taps on the index pad time it instead: a
     tap is heard and felt at the same instant, and the board's time
     for it is known to a few ms.
  2. The song path: the study track through the game's own mixer,
     recorded, and lined up with the decoded file on its attacks. Less
     the microphone's delay it is the play call to the speaker:
     rhythm.audio_offset_ms.
  3. The short-sound path: a click through a Sound channel, lined up
     on its waveform: latency.tone_ms and rhythm.metronome_offset_ms.
  4. The motor, when the board is plugged in: every motor pulsed ten
     times, the buzz's sound envelope averaged over the pulses and its
     onset read where it first clears 5 SD of the averaged noise,
     which sits at a few percent of the full buzz, the same point the
     motor datasheets call the lag (0.08 G). Less the microphone's
     delay it is the STIM command to motion: latency.buzzer_ms.

The result is saved to config/latency_profile.yaml (per machine, never
committed), which the game lays over default.yaml at every start and
records in every block's config snapshot, so the analysis can see the
numbers were measured. A CSV of every take lands in config/calibration/.
"""
from __future__ import annotations

import csv
import logging
import os
import statistics
import sys
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)

SR = 44100
CHUNK = 512
TRACK = "assets/music/Easy_Lemon.mp3"
MAX_LAG_S = 0.6
# Host receive time of a board sample, after the physical event: the
# USB and 115200-baud line (about 1 ms) and half a 5 ms sample period.
BOARD_DELAY_MS = 3.5

NOT_SAVED = ("Not saved: the song or the click had too few clear takes. "
             "A quieter room and a little more volume, then measure "
             "again.")
NO_MIC = ("The microphone's own delay is unknown: this computer does not "
          "report it, so it is timed from taps on the index pad. Plug "
          "the board in and measure again.")


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
            raise RuntimeError("no microphone found; plug one in (a "
                               "webcam or headset microphone works)")
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
        if self._th.is_alive():
            self._th.join(timeout=1)
        try:
            self.s.write(b"STOP\n")
        except Exception:
            pass
        self.s.close()


def run_tap(port: str | None, seconds: float, say=print) -> float | None:
    """The microphone's delay by hand: a fingernail tap on the index
    pad is heard and felt at the same instant, and the board's time
    for it is known to a few ms."""
    import numpy as np
    board = Board(port)
    say(f"Board on {board.port}. Starting up...")
    board.boot()
    rec = Recorder()
    rec.start()
    say(f"Tap the INDEX pad firmly with a fingernail, about once a "
        f"second, until it says stop ({seconds:.0f} s).")
    time.sleep(seconds)
    data, anchor = rec.stop()
    board.close()
    say("Stop tapping.")
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
    say(f"{len(presses)} taps, {len(sounds)} sounds, {len(diffs)} paired")
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
def run_sound(track: Path, takes: int, seconds: float, volume: float,
              say=print) -> list[dict]:
    import numpy as np
    import pygame
    from .beatmap import decode_mono
    song, _ = decode_mono(Path(track), sr=SR)
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
                pygame.mixer.music.load(str(track))
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
            say(f"  {path:5s} take {take}: "
                + (f"{lag:6.1f} ms to the microphone" if ok else
                   f"no clear alignment (strength {strength:.1f})"))
            time.sleep(0.4)
    return rows


# ---- one whole measurement --------------------------------------------------
def result_values(rows: list[dict], mic_ms: float,
                  motors: dict[int, float]) -> tuple[dict, dict]:
    """The config values and the notes behind them, from the takes. A
    path with fewer than three usable takes gives no value."""
    def med(path):
        vals = [r["to_mic_ms"] for r in rows if r["path"] == path
                and r["usable"]]
        return statistics.median(vals) if len(vals) >= 3 else None

    song, click = med("song"), med("click")
    values: dict = {}
    detail: dict = {"microphone_delay_ms": round(mic_ms, 1)}
    if song is not None:
        values["audio_offset_ms"] = round(song - mic_ms)
        detail["song_to_mic_median_ms"] = round(song, 1)
    if click is not None:
        values["tone_ms"] = round(click - mic_ms)
        values["metronome_offset_ms"] = values["tone_ms"]
        detail["click_to_mic_median_ms"] = round(click, 1)
    if motors:
        onset = statistics.median(motors.values())
        values["buzzer_ms"] = round(onset - mic_ms)
        detail["motor_onsets_to_mic_ms"] = {k: round(v, 1)
                                            for k, v in motors.items()}
    return values, detail


def savable(values: dict) -> bool:
    return {"audio_offset_ms", "tone_ms"} <= set(values)


def summary(values: dict) -> str:
    """The saved delays in one line, for the screen."""
    parts = []
    if "audio_offset_ms" in values:
        parts.append(f"song {values['audio_offset_ms']} ms")
    if "tone_ms" in values:
        parts.append(f"short sounds {values['tone_ms']} ms")
    if "buzzer_ms" in values:
        parts.append(f"buzz {values['buzzer_ms']} ms")
    return ", ".join(parts)


def measure(track: Path, port: str | None, say=print, *, takes: int = 5,
            seconds: float = 8.0, volume: float = 0.4, pulses: int = 10,
            tap: bool = False, tap_seconds: float = 20.0,
            find_board: bool = False) -> dict:
    """Every step, in order. Returns {"mic_ms", "method", "parts",
    "rows", "motors", "values", "detail", "problem"}; problem is "" when
    the values can be saved. With no port, the board steps are skipped
    unless find_board lets Board pick the first serial port (the
    script does; the app always passes the port it holds)."""
    use_board = port is not None or find_board
    out = {"mic_ms": None, "method": "", "parts": {}, "rows": [],
           "motors": {}, "values": {}, "detail": {}, "problem": ""}
    mic_ms, parts = coreaudio_input_ms()
    method = "CoreAudio fixed input latency"
    if tap or mic_ms is None:
        method = "fingernail taps on the index pad"
        mic_ms = None
        if use_board:
            try:
                mic_ms = run_tap(port, tap_seconds, say)
            except Exception as e:
                say(f"Taps skipped: {e}")
    out.update(mic_ms=mic_ms, method=method, parts=parts)
    if mic_ms is None:
        out["problem"] = NO_MIC
        return out
    say(f"Microphone delay: {mic_ms:.1f} ms ({method}).")
    say("Sound: the song, then a click, five times each.")
    rows = run_sound(track, takes, seconds, volume, say)
    motors: dict[int, float] = {}
    if use_board:
        say(f"Buzz: each finger {pulses} times.")
        try:
            motors = run_motors(port, pulses)
        except Exception as e:
            say(f"Buzz skipped: {e}")
    values, detail = result_values(rows, mic_ms, motors)
    detail["microphone_method"] = method
    detail["visual_ms"] = ("not measured here (needs a photodiode); it "
                           "moves only where the falling note is drawn, "
                           "never a score")
    out.update(rows=rows, motors=motors, values=values, detail=detail)
    if not savable(values):
        out["problem"] = NOT_SAVED
    return out


# ---- saving -------------------------------------------------------------------
def write_takes(rows: list[dict]) -> Path | None:
    """Every take as a CSV in config/calibration/."""
    if not rows:
        return None
    from .. import config as cfgmod
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = cfgmod.USER_ROOT / "config" / "calibration" / \
        f"audio_latency_{stamp}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return out


def write_profile(values: dict, detail: dict) -> Path:
    import yaml
    from .. import config as cfgmod
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
    header = ("# This computer's measured delays, written by Settings, "
              "Audio delay\n# (or scripts/audio_latency.py). Laid over "
              "default.yaml at every start\n# (config.LATENCY_PROFILE); "
              "per machine, never committed.\n")
    body = yaml.safe_dump(doc, sort_keys=False)
    notes = "".join(f"# {k}: {v}\n" for k, v in detail.items())
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(header + notes + body, encoding="utf-8")
    os.replace(tmp, path)
    return path


def apply(cfg, values: dict) -> None:
    """Put saved values into a running config, so the next block uses
    them without a restart. Every reader takes them from cfg at use."""
    lat = cfg.data.setdefault("latency", {})
    rhy = cfg.data.setdefault("rhythm", {})
    lat["measured"] = True
    lat["measured_on"] = time.strftime("%Y-%m-%d")
    for k in ("buzzer_ms", "tone_ms"):
        if k in values:
            lat[k] = values[k]
    for k in ("audio_offset_ms", "metronome_offset_ms"):
        if k in values:
            rhy[k] = values[k]


class LatencyJob:
    """One measurement on its own thread, for the Settings dialog.

    The thread never touches the engine: the screen hands the board's
    port over before start() and takes it back once `done` is set, on
    the main thread, as the firmware jobs do. `lines` is the progress
    the dialog shows.
    """

    def __init__(self, track: Path, port: str | None, **kw) -> None:
        self.track = Path(track)
        self.port = port
        self.kw = kw
        self.lines: list[str] = []
        self.done = False
        self.ok = False
        self.message = ""
        self.values: dict = {}

    def say(self, text: str) -> None:
        self.lines.append(str(text).strip())

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True,
                         name="audio-delay").start()

    def _run(self) -> None:
        try:
            res = measure(self.track, self.port, say=self.say, **self.kw)
            write_takes(res["rows"])
            if res["problem"]:
                self.message = res["problem"]
            else:
                write_profile(res["values"], res["detail"])
                self.values = res["values"]
                self.ok = True
                self.message = "Saved: " + summary(res["values"]) + "."
        except Exception as e:
            log.exception("Audio delay measurement failed")
            self.message = f"Measurement failed: {e}"
        finally:
            self.done = True
