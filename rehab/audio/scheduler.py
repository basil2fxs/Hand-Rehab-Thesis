"""Beat scheduler. Turns song time into a stream of due notes + upcoming notes
for the falling-notes visualiser."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .beatmap import Beatmap, Note


@dataclass
class ScheduledNote:
    index: int
    note: Note
    fired: bool = False
    hit_at: float | None = None
    early_late_ms: float | None = None


class BeatScheduler:
    def __init__(self, beatmap: Beatmap) -> None:
        self.beatmap = beatmap
        self._sched = [
            ScheduledNote(index=i, note=n) for i, n in enumerate(beatmap.notes)
        ]
        self._next = 0

    def reset(self) -> None:
        for s in self._sched:
            s.fired = False
            s.hit_at = None
            s.early_late_ms = None
        self._next = 0

    @property
    def scheduled(self) -> list[ScheduledNote]:
        return self._sched

    @property
    def total(self) -> int:
        return len(self._sched)

    def notes_due(self, song_t: float) -> Iterator[ScheduledNote]:
        # Yield each note exactly once, in order, when its t has elapsed.
        while self._next < len(self._sched):
            s = self._sched[self._next]
            if s.note.t <= song_t:
                if not s.fired:
                    s.fired = True
                    yield s
                self._next += 1
            else:
                return

    def upcoming(self, song_t: float, ahead_s: float = 1.5,
                 max_count: int = 32) -> list[ScheduledNote]:
        out: list[ScheduledNote] = []
        for s in self._sched[self._next:]:
            if s.note.t > song_t + ahead_s:
                break
            out.append(s)
            if len(out) >= max_count:
                break
        return out

    def all_done(self, song_t: float) -> bool:
        return self._next >= len(self._sched) and song_t > self.beatmap.duration_s
