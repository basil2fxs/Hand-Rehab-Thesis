"""Beatmap = a list of (time, lane) notes for rhythm mode.

If librosa is available we extract beats from a real audio file. If not we fall
back to a procedural BPM-driven beatmap so the game still plays without the
audio dependency.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Iterable


log = logging.getLogger(__name__)


@dataclass
class Note:
    t: float            # song time in seconds when the user should press
    lane: int           # 0..3
    kind: str = "tap"

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Beatmap:
    title: str = "Untitled"
    bpm: float = 80.0
    song: str | None = None             # path to audio file, None for click track
    difficulty: str = "medium"          # easy | medium | hard
    notes: list[Note] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.notes:
            self.notes = sorted(self.notes, key=lambda n: n.t)

    @property
    def duration_s(self) -> float:
        return self.notes[-1].t + 1.0 if self.notes else 0.0

    @classmethod
    def load(cls, path: str | Path) -> "Beatmap":
        p = Path(path)
        with p.open("r", encoding="utf-8") as f:
            raw = json.load(f)
        known = {"t", "lane", "kind"}
        notes: list[Note] = []
        for n in raw.get("notes", []):
            if not isinstance(n, dict) or "t" not in n or "lane" not in n:
                continue
            try:
                notes.append(Note(**{k: v for k, v in n.items() if k in known}))
            except (TypeError, ValueError):
                continue
        return cls(
            title=str(raw.get("title", p.stem)),
            bpm=float(raw.get("bpm", 80.0)),
            song=raw.get("song"),
            difficulty=str(raw.get("difficulty", "medium")),
            notes=sorted(notes, key=lambda n: n.t),
        )

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("w", encoding="utf-8") as f:
            json.dump({
                "title": self.title,
                "bpm": self.bpm,
                "song": self.song,
                "difficulty": self.difficulty,
                "notes": [n.to_dict() for n in self.notes],
            }, f, indent=2)


_DIFFICULTY_STRIDE = {"easy": 4, "medium": 2, "hard": 1}

# Fraction of detected beats kept per difficulty after onset-strength
# ranking. Easy keeps only the strongest 22% (sparse, big-hit feel);
# medium keeps roughly every other beat; hard keeps most beats so the
# tempo carries the track. Tuned against the bundled Kevin MacLeod
# tracks - lower easy figures left songs with awkwardly long gaps;
# higher hard figures filled in syncopated off-beats that don't read
# as satisfying. These are the keeper percentages; everything below
# is dropped.
_DIFFICULTY_KEEP_FRAC = {
    "easy":   0.22,
    "medium": 0.55,
    "hard":   0.85,
}

# Minimum gap between consecutive notes per difficulty (seconds).
# Stops onset clustering (a kick + cymbal hit ~30 ms apart) from
# producing two notes the patient can't physically separate. Higher
# gaps on easy = friendlier pace; lower gaps on hard let dense
# percussion through.
_DIFFICULTY_MIN_GAP_S = {
    "easy":   0.55,
    "medium": 0.30,
    "hard":   0.18,
}


def _default_pattern(num_lanes: int) -> list[int]:
    if num_lanes >= 8:
        # Bilateral default: weave through both hands so the patient has to
        # alternate between them. Right index, left index, right middle,
        # left middle, ... keeps both hands engaged.
        return [0, 4, 1, 5, 2, 6, 3, 7, 1, 5, 2, 6]
    return [0, 1, 2, 3, 1, 2, 0, 3]


def _assign_lanes(beat_times: Iterable[float],
                  pattern: list[int] | None = None,
                  num_lanes: int = 4) -> list[Note]:
    """Spread beats across lanes using a repeating pattern. `num_lanes` tells
    us whether this is a unilateral (4-lane) or bilateral (8-lane) session
    when no explicit pattern is supplied."""
    pat = pattern or _default_pattern(num_lanes)
    notes: list[Note] = []
    for i, t in enumerate(beat_times):
        lane = pat[i % len(pat)]
        if 0 <= lane < num_lanes:
            notes.append(Note(t=float(t), lane=lane))
    return notes


def _coerce_scalar(x) -> float:
    """Coerce a librosa-returned tempo (which can be a 0-d or 1-d ndarray,
    or a plain float) into a single float."""
    if hasattr(x, "item"):
        try:
            return float(x.item())
        except (TypeError, ValueError):
            pass
    try:
        return float(x)
    except (TypeError, ValueError):
        return float(x[0])


def _select_strong_beats(beat_times: list[float],
                          beat_strengths: list[float],
                          keep_frac: float,
                          min_gap_s: float) -> list[float]:
    """Pick the subset of beats whose onset strength is in the top
    `keep_frac` of the song, then enforce a minimum gap so two beats
    that landed within `min_gap_s` of each other don't both survive.

    The strength threshold is derived from the percentile, so a song
    with uniformly punchy beats keeps most of them while a sparse
    track with one big drop keeps that drop and prunes the filler.
    """
    if not beat_times:
        return []
    if len(beat_times) != len(beat_strengths):
        # Length mismatch should never happen, but if it does just
        # return the raw beats so the player still has something to
        # press to.
        return list(beat_times)
    # Compute the strength threshold: anything below it is dropped.
    # numpy is already a librosa dep so we can use it freely here.
    import numpy as np
    strengths = np.array(beat_strengths, dtype=float)
    if strengths.size == 0 or float(strengths.max()) <= 0.0:
        # Onset envelope was flat (silent track, or onset detection
        # failed). Pretend every beat is equally strong and let the
        # stride logic do the work.
        return list(beat_times)
    # Percentile such that exactly keep_frac of beats survive. e.g.
    # keep_frac=0.55 -> threshold = 45th percentile, keep top 55%.
    pct = max(0.0, min(100.0, 100.0 * (1.0 - keep_frac)))
    threshold = float(np.percentile(strengths, pct))
    # Pair (time, strength) and keep those above threshold, sorted
    # in chronological order.
    candidates = [
        (t, s) for t, s in zip(beat_times, beat_strengths)
        if s >= threshold
    ]
    candidates.sort(key=lambda ts: ts[0])
    # Greedy gap enforcement: walk left-to-right, drop any beat that
    # lands within min_gap_s of the most recently accepted beat. If
    # two near-each-other beats arrive, the stronger one wins (we
    # back-substitute the weaker for the stronger).
    chosen: list[tuple[float, float]] = []
    for t, s in candidates:
        if not chosen:
            chosen.append((t, s))
            continue
        prev_t, prev_s = chosen[-1]
        if t - prev_t >= min_gap_s:
            chosen.append((t, s))
        elif s > prev_s:
            # Replace the previous weaker beat with this stronger one
            # so the kept set stays anchored to the loudest hits.
            chosen[-1] = (t, s)
    return [t for t, _ in chosen]


def extract_beatmap(audio_path: str | Path,
                    difficulty: str = "medium",
                    lane_pattern: list[int] | None = None,
                    num_lanes: int = 4) -> Beatmap:
    """Detect the song's beats and pick the strongest ones (kicks,
    snares, downbeats) for the patient to press to. Falls back to a
    procedural BPM-only map if librosa or the audio file is missing.

    The two-pass approach: first librosa.beat.beat_track gives the
    tempo grid (uniform pulses at the song's BPM); then we look up
    each beat's onset strength in the percussive envelope and keep
    only the top `keep_frac` by strength. Result: notes line up with
    the kicks and snares the listener already feels as "the beat" -
    not the in-between sixteenths nobody taps along to.

    `lane_pattern` lets the caller route beats to specific fingers.
    Default rotates through index, middle, ring, little (with both
    hands woven together when num_lanes is 8).
    """
    p = Path(audio_path)
    try:
        import librosa
        y, sr = librosa.load(str(p), mono=True)
        # Onset envelope (energy of percussive hits over time).
        # Computed once and shared between beat-track + strength
        # ranking so beat_track follows the same percussive cues we
        # use to filter.
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        tempo, beats = librosa.beat.beat_track(
            onset_envelope=onset_env, sr=sr,
        )
        bpm = _coerce_scalar(tempo)
        times = librosa.frames_to_time(beats, sr=sr).tolist()
        # Per-beat onset strength. We look up the envelope value at
        # each beat frame; that single number captures "how much hit
        # is happening here" relative to neighbouring beats. Window
        # +/- 1 frame so a beat that's a few ms early of the kick
        # still picks up the kick's strength.
        if onset_env.size > 0 and beats.size > 0:
            beat_strengths: list[float] = []
            for f in beats:
                lo = max(0, int(f) - 1)
                hi = min(int(onset_env.size), int(f) + 2)
                if hi > lo:
                    beat_strengths.append(float(onset_env[lo:hi].max()))
                else:
                    beat_strengths.append(0.0)
        else:
            beat_strengths = [1.0] * len(times)

        keep_frac = _DIFFICULTY_KEEP_FRAC.get(difficulty, 0.55)
        min_gap_s = _DIFFICULTY_MIN_GAP_S.get(difficulty, 0.30)
        subset = _select_strong_beats(
            times, beat_strengths,
            keep_frac=keep_frac, min_gap_s=min_gap_s,
        )
        # Floor: if filtering left fewer than ~1 note per 4 seconds
        # of song the patient runs out of things to press, so we
        # fall back to the every-Nth-beat stride for that case.
        # Compares against the half-keep_frac equivalent so it kicks
        # in only when ranking REALLY dropped too much (not just a
        # naturally sparse song).
        if times and len(subset) < max(8, len(times) * keep_frac * 0.5):
            log.info("Strong-beat filter dropped too much (%d/%d); "
                      "using stride fallback", len(subset), len(times))
            stride = _DIFFICULTY_STRIDE.get(difficulty, 2)
            subset = times[::stride]
        notes = _assign_lanes(subset, lane_pattern, num_lanes=num_lanes)
        return Beatmap(
            title=p.stem,
            bpm=bpm,
            song=str(p),
            difficulty=difficulty,
            notes=notes,
        )
    except Exception as e:
        # librosa missing or audio unreadable. Make a procedural map.
        log.warning("librosa beat-track failed (%s); using procedural map", e)
        return procedural_beatmap(bpm=80.0, beats=64, difficulty=difficulty,
                                  title=p.stem, song=str(p),
                                  lane_pattern=lane_pattern,
                                  num_lanes=num_lanes)


def procedural_beatmap(bpm: float, beats: int, difficulty: str = "medium",
                       title: str = "Procedural", song: str | None = None,
                       lane_pattern: list[int] | None = None,
                       num_lanes: int = 4) -> Beatmap:
    if bpm <= 0:
        raise ValueError(f"bpm must be > 0, got {bpm}")
    if beats <= 0:
        raise ValueError(f"beats must be > 0, got {beats}")
    stride = _DIFFICULTY_STRIDE.get(difficulty, 2)
    period = 60.0 / bpm
    times = [(i + 1) * period for i in range(beats)][::stride]
    notes = _assign_lanes(times, lane_pattern, num_lanes=num_lanes)
    return Beatmap(
        title=title, bpm=bpm, song=song, difficulty=difficulty, notes=notes,
    )
