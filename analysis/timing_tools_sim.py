"""The timing tools on recordings and clips with a delay planted in them.

The delays the study could not time on its own computers, the laboratory
computer's sound and the screen, are each read by a tool: the microphone
loopback of app/finger_rehab/audio/latency_measure.py for the sound, and
app/scripts/clip_delay.py on a 240 fps phone clip for the screen. Here
each tool is given a signal whose delay is known and has to read it back.

Sound: the study track and the click are passed through a speaker (a band
pass), a room (a decaying echo 6 dB below the direct sound, the same room
for a measurement's five takes) and a microphone (noise at 10 to 30 dB
below the sound), delayed by the speaker path plus the microphone's own
delay, and lined up by the loopback's own _lag. Motor: ten buzzes whose
sound starts a known time after each command, read by averaged_onset_ms.
Screen: a clip at 240 fps, each frame exposed for the whole frame, of an
LED that lights at each command and a tile that turns white a known time
later, coded by ffmpeg as a phone would, read by clip_delay.

    cd analysis
    python3 timing_tools_sim.py [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
from scipy.signal import butter, fftconvolve, lfilter

APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
from finger_rehab.audio.beatmap import decode_mono  # noqa: E402
from finger_rehab.audio.latency_measure import SR, _lag, averaged_onset_ms  # noqa: E402
import clip_delay  # noqa: E402

TRACK = APP / "assets" / "music" / "Easy_Lemon.mp3"
MIC_MS = 20.0          # the microphone's own delay, which the profile subtracts
LEAD_S = 0.6           # the recorder runs this long before the play call, as run_sound does


def room(rng) -> np.ndarray:
    """A room's echo after the direct sound: a 50 ms decay whose energy is
    a quarter of the direct sound's (6 dB below it), about what a microphone
    an arm's length from a computer's speaker hears."""
    n_ir = int(0.25 * SR)
    ir = rng.normal(0.0, 1.0, n_ir) * np.exp(-np.arange(n_ir) / (0.05 * SR)) * 0.015
    ir[0] = 1.0
    return ir


def through_room(x: np.ndarray, delay_ms: float, snr_db: float, rng, ir: np.ndarray) -> np.ndarray:
    """A recording of x played at t = LEAD_S: speaker band, room echo,
    the delay, the microphone's noise."""
    nyq = SR / 2.0
    b, a = butter(2, [150.0 / nyq, 6000.0 / nyq], btype="band")
    y = lfilter(b, a, x)
    y = fftconvolve(y, ir)[: len(y)]
    pre = int(LEAD_S * SR) + int(round(delay_ms / 1000.0 * SR))
    rec = np.concatenate([np.zeros(pre), y, np.zeros(int(0.8 * SR))])
    noise_sd = np.sqrt(np.mean(y ** 2)) / 10 ** (snr_db / 20.0)
    return (rec + rng.normal(0.0, noise_sd, len(rec))).astype(np.float32)


def sound_paths(seeds: int = 5) -> dict:
    song = decode_mono(TRACK, sr=SR)[0][: 8 * SR]      # (samples, rate), as librosa.load
    t = np.arange(int(0.03 * SR)) / SR
    click = (0.8 * np.sin(2 * np.pi * 1000 * t) * np.exp(-t / 0.008)).astype(np.float32)
    out = {}
    for name, ref, env in (("song", song, True), ("click", click, False)):
        errs, dropped = [], 0
        for planted in (40.0, 87.0, 150.0, 300.0):
            for snr in (10.0, 20.0, 30.0):
                # one measurement is five takes; run_sound drops a take whose
                # alignment is weak (strength under 6) and the profile keeps
                # the median of the rest
                for s in range(seeds):
                    takes = []
                    ir = room(np.random.default_rng(500 + s))           # one room a measurement
                    for k in range(5):
                        rng = np.random.default_rng(10000 * s + 100 * k + int(planted) + int(snr))
                        rec = through_room(ref, planted + MIC_MS, snr, rng, ir)
                        lag, strength = _lag(rec, ref, 0.0, LEAD_S, envelope=env)
                        if strength >= 6.0 and lag == lag:
                            takes.append(lag)
                        else:
                            dropped += 1
                    if takes:
                        errs.append(float(np.median(takes)) - MIC_MS - planted)
        e = np.abs(errs)
        out[name] = {"measurements": len(errs), "takes_dropped": dropped,
                     "median_abs_err_ms": float(np.median(e)), "max_abs_err_ms": float(e.max())}
    return out


def motor_onset(seeds: int = 5) -> dict:
    """Ten buzzes a second apart whose sound starts planted ms after each
    command and grows over 30 ms, as a coin motor spins up."""
    errs = []
    for planted in (50.0, 74.0, 100.0):
        for s in range(seeds):
            rng = np.random.default_rng(7 + s + int(planted))
            dur = 12.0
            n = int(dur * SR)
            x = np.zeros(n)
            cmds = [1.0 + k for k in range(10)]
            tt = np.arange(int(0.3 * SR)) / SR
            ramp = np.clip(tt / 0.03, 0, 1) * np.where(tt < 0.15, 1.0, np.exp(-(tt - 0.15) / 0.03))
            buzz = ramp * (np.sin(2 * np.pi * 190 * tt) + 0.4 * np.sin(2 * np.pi * 380 * tt))
            for c in cmds:
                i = int((c + planted / 1000.0) * SR)
                x[i:i + len(buzz)] += 0.3 * buzz
            x += rng.normal(0.0, 0.01, n)
            got = averaged_onset_ms(x, 0.0, cmds)
            errs.append(got - planted)
    e = np.array(errs)
    return {"runs": len(errs), "median_err_ms": float(np.median(e)), "range_ms": [float(e.min()), float(e.max())]}


def synthetic_clip(path: Path, delay_ms: float, rng, fps: float = 240.0, pulses: int = 12) -> None:
    """A clip of an LED lit 20 ms at each command and a tile white from
    delay_ms after it until 300 ms after it, each frame the mean light over
    its whole exposure, with sensor noise, coded with x264 as a phone does."""
    w, h = 96, 64
    n = int((pulses + 1.5) * fps)
    cmds = [0.5 + k + rng.uniform(0.0, 1.0 / fps) for k in range(pulses)]
    sub = 16                                             # light sampled 16 times a frame
    tt = (np.arange(n * sub) + 0.5) / (fps * sub)
    led = np.zeros_like(tt)
    tile = np.zeros_like(tt)
    for c in cmds:
        led[(tt >= c) & (tt < c + 0.020)] = 1.0
        tile[(tt >= c + delay_ms / 1000.0) & (tt < c + 0.300 + delay_ms / 1000.0)] = 1.0
    led_f = led.reshape(n, sub).mean(axis=1)
    tile_f = tile.reshape(n, sub).mean(axis=1)
    frames = np.full((n, h, w), 30.0)
    frames[:, 8:16, 8:16] += 200.0 * led_f[:, None, None]
    frames[:, 16:48, 48:80] += 200.0 * tile_f[:, None, None]
    frames += rng.normal(0.0, 3.0, frames.shape)
    raw = np.clip(frames, 0, 255).astype(np.uint8).tobytes()
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "gray", "-s", f"{w}x{h}",
                    "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "12", "-pix_fmt", "yuv420p",
                    str(path)], input=raw, check=True)


def screen_clips(seeds: int = 3) -> dict:
    errs = []
    with tempfile.TemporaryDirectory() as d:
        for planted in (8.0, 23.0, 40.0, 75.0):
            for s in range(seeds):
                rng = np.random.default_rng(40 + s + int(planted))
                p = Path(d) / f"clip_{int(planted)}_{s}.mp4"
                synthetic_clip(p, planted, rng)
                got = clip_delay.delays_ms(clip_delay.patch_brightness(p, (8, 8, 8, 8)),
                                           clip_delay.patch_brightness(p, (48, 16, 32, 32)), 240.0)
                errs.append(float(np.median(got)) - planted)
    e = np.abs(errs)
    return {"clips": len(errs), "median_abs_err_ms": float(np.median(e)), "max_abs_err_ms": float(e.max()),
            "frame_ms": 1000.0 / 240.0}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    res = {"sound": sound_paths(), "motor": motor_onset(), "screen": screen_clips()}
    for k in ("song", "click"):
        r = res["sound"][k]
        print(f"loopback, {k}: {r['measurements']} measurements of five takes ({r['takes_dropped']} takes dropped), "
              f"planted 40 to 300 ms at 10 to 30 dB, "
              f"read within {r['median_abs_err_ms']:.2f} ms (median), {r['max_abs_err_ms']:.2f} ms at most")
    m = res["motor"]
    print(f"motor onset: {m['runs']} sets of ten buzzes, read {m['median_err_ms']:.1f} ms late "
          f"(median; {m['range_ms'][0]:.1f} to {m['range_ms'][1]:.1f})")
    c = res["screen"]
    print(f"screen clip: {c['clips']} clips at 240 fps, planted 8 to 75 ms, read within "
          f"{c['median_abs_err_ms']:.2f} ms (median), {c['max_abs_err_ms']:.2f} ms at most "
          f"(a frame is {c['frame_ms']:.1f} ms)")
    if args.json:
        args.json.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
