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


def extract_beatmap(audio_path: str | Path,
                    difficulty: str = "medium",
                    lane_pattern: list[int] | None = None,
                    num_lanes: int = 4) -> Beatmap:
    """Try librosa beat tracking. Fall back to a BPM-only procedural map.

    `lane_pattern` lets the caller route beats to specific fingers. Default
    rotates through index, middle, ring, little (with both hands woven
    together when num_lanes is 8)."""
    p = Path(audio_path)
    try:
        import librosa
        y, sr = librosa.load(str(p), mono=True)
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
        bpm = _coerce_scalar(tempo)
        times = librosa.frames_to_time(beats, sr=sr).tolist()
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
