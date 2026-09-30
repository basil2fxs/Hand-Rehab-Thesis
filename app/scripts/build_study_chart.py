"""Freeze the study's Rhythm chart as a file, its notes on the music's
attacks.

The battery plays one song, Easy_Lemon.mp3 at medium. The game used to
build that chart from the mp3 at the start of every block, with
whatever librosa the installer bundled, and logged only the note count
and tempo, so nothing on record showed two blocks heard the same chart.
This script builds it once with the game's own extract_beatmap and
moves every note onto the music's attack.

Why move them: librosa's beat times sit late. Its onset envelope comes
in 23.2 ms frames shifted by three frames, so a beat lands a median
26 ms after an ideal click and 33 to 37 ms after this song's drum
attacks (Rhythm research of 1 October 2026). The game sounds its lane
tone and buzz on the chart's time, so both came about 35 ms after the
song's own hit. Each note's attack is found the way the research found
it: the song high-passed above 2 kHz, a 2 ms RMS envelope, and the
point where the steepest rise between 150 ms before the note and 60 ms
after it reaches 20 percent of the way from its floor to its peak. A
note whose attack cannot be found, or sits outside 0 to 80 ms before
it, moves by the median lag instead.

Each note keeps where it came from: the tracker's time, its lag, and
whether it sits on the song's quarter-note beat (the composer's 82 BPM,
phase fitted to the percussive onsets) or between. The game loads the
file for the battery step (beatmap.study_chart); the block summary
records its hash, and scripts/check_sitting.py flags a Rhythm block
that played anything else.

Run from app/ (needs librosa and scipy):
    python3 scripts/build_study_chart.py [--track Easy_Lemon.mp3]
        [--difficulty medium] [--bpm 82]
Writes assets/charts/<track stem>_<difficulty>.json.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import numpy as np  # noqa: E402

from finger_rehab.audio.beatmap import (  # noqa: E402
    CHART_DIR, chart_sha, extract_beatmap)

ATTACK_BAND_HZ = 2000.0
ATTACK_RMS_S = 0.002
ATTACK_FRACTION = 0.2
SEARCH_BEFORE_S = 0.150
SEARCH_AFTER_S = 0.060
LAG_OK_MS = (0.0, 80.0)


def attack_times(x: np.ndarray, fs: int, times) -> np.ndarray:
    """The attack before each time: the research's high-band detector."""
    import scipy.signal as ss
    b, a = ss.butter(4, ATTACK_BAND_HZ / (fs / 2), "high")
    sig = ss.filtfilt(b, a, x)
    w = max(1, int(fs * ATTACK_RMS_S))
    env = np.sqrt(np.convolve(sig ** 2, np.ones(w) / w, mode="same"))
    out = []
    for t in times:
        i0 = max(0, int((t - SEARCH_BEFORE_S) * fs))
        i1 = int((t + SEARCH_AFTER_S) * fs)
        seg = env[i0:i1]
        if len(seg) < int(0.05 * fs):
            out.append(np.nan)
            continue
        level = 20 * np.log10(seg + 1e-9)
        step = int(0.003 * fs)
        k = int(np.argmax(level[step:] - level[:-step]))
        peak = k + int(np.argmax(seg[k:k + int(0.04 * fs)]))
        floor = float(np.min(seg[max(0, k - int(0.02 * fs)):k + 1]))
        thr = floor + ATTACK_FRACTION * (seg[peak] - floor)
        c = (k + int(np.argmax(seg[k:peak + 1] >= thr))) if peak > k else k
        out.append((i0 + c) / fs)
    return np.asarray(out, dtype=float)


def beat_phase(y: np.ndarray, sr: int, period_s: float) -> float:
    """Where the quarter-note grid sits: the phase that puts the most
    percussive onset flux on the beat, at a fixed period."""
    import librosa
    _yh, yp = librosa.effects.hpss(y)
    hop = 64
    spec = np.abs(librosa.stft(yp, n_fft=512, hop_length=hop, center=True))
    db = librosa.amplitude_to_db(spec, ref=np.max)
    flux = np.concatenate([[0.0], np.maximum(0, np.diff(db, axis=1))
                           .mean(axis=0)])
    frame_s = hop / sr
    best = (-1.0, 0.0)
    for ph in np.arange(0.0, period_s, 0.002):
        idx = np.round((ph + np.arange(0.0, len(flux) * frame_s, period_s))
                       / frame_s).astype(int)
        idx = idx[idx < len(flux)]
        score = float(flux[idx].sum())
        if score > best[0]:
            best = (score, float(ph))
    return best[1]


def build(track: Path, difficulty: str, bpm: float) -> dict:
    import librosa
    bm = extract_beatmap(str(track), difficulty=difficulty, num_lanes=4)
    t0 = np.array([n.t for n in bm.notes])
    x, fs = librosa.load(str(track), sr=None, mono=True)
    att = attack_times(x.astype(float), int(fs), t0)
    lag = (t0 - att) * 1000.0
    good = np.isfinite(lag) & (lag >= LAG_OK_MS[0]) & (lag <= LAG_OK_MS[1])
    median_lag = float(np.median(lag[good]))
    used = np.where(good, lag, median_lag)
    period = 60.0 / bpm
    y22, sr22 = librosa.load(str(track), sr=22050, mono=True)
    phase = beat_phase(y22, sr22, period)
    notes = []
    for n, orig, lg, ok in zip(bm.notes, t0, used, good):
        t = float(orig - lg / 1000.0)
        pos = ((t - phase) / period) % 1.0
        beat = ("on" if pos < 0.125 or pos > 0.875
                else "off" if 0.375 <= pos <= 0.625 else "between")
        notes.append({"t": round(t, 4), "lane": int(n.lane),
                      "t_tracker": round(float(orig), 4),
                      "attack_lag_ms": round(float(lg), 1),
                      "lag_measured": bool(ok), "beat": beat})
    chart = {
        "title": bm.title, "bpm": bm.bpm, "song": track.name,
        "difficulty": difficulty,
        "track_sha256": hashlib.sha256(track.read_bytes()).hexdigest(),
        "built_with": {"librosa": librosa.__version__},
        "tempo_bpm_composer": bpm,
        "beat_phase_s": round(phase, 4),
        "aligned_to": ("the music's attack: above 2 kHz, 2 ms RMS, 20 "
                       "percent of the rise"),
        "median_lag_ms": round(median_lag, 1),
        "n_notes": len(notes),
        "notes": notes,
    }
    chart["chart_sha"] = chart_sha(chart["notes"])
    return chart


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--track", default="Easy_Lemon.mp3")
    ap.add_argument("--difficulty", default="medium")
    ap.add_argument("--bpm", type=float, default=82.0,
                    help="the composer's tempo, for the on-beat labels")
    args = ap.parse_args(argv)
    track = APP / "assets" / "music" / args.track
    chart = build(track, args.difficulty, args.bpm)
    out = CHART_DIR / f"{track.stem}_{args.difficulty}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(chart, indent=1) + "\n", encoding="utf-8")
    lags = [n["attack_lag_ms"] for n in chart["notes"] if n["lag_measured"]]
    beats = [n["beat"] for n in chart["notes"]]
    print(f"wrote {out.relative_to(APP)}: {chart['n_notes']} notes, "
          f"median lag {chart['median_lag_ms']} ms "
          f"(IQR {np.percentile(lags, 25):.1f} to "
          f"{np.percentile(lags, 75):.1f}, {len(lags)} measured), "
          f"{beats.count('on')} on the beat, {beats.count('off')} off, "
          f"{beats.count('between')} between")
    return 0


if __name__ == "__main__":
    sys.exit(main())
