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
    # The leading tactile pulse, dispatched ahead of the beat by the
    # rhythm mode's buzz lead. Its own flag because it runs on its own
    # cursor: the lead for note N+1 can be due before the beat of note
    # N on a fast chart, so one shared cursor would fire it late.
    lead_fired: bool = False
    # The cue tone, sent ahead of the beat by its own output delay so
    # it is heard on the scored zero; its own cursor for the same
    # reason as the lead.
    tone_fired: bool = False
    # The scored zero on the perf_counter clock, stamped at dispatch,
    # so the engine can tell whether a board was away over the note.
    stim_t_perf: float | None = None
    hit_at: float | None = None
    early_late_ms: float | None = None


class BeatScheduler:
    def __init__(self, beatmap: Beatmap) -> None:
        self.beatmap = beatmap
        self._sched = [
            ScheduledNote(index=i, note=n) for i, n in enumerate(beatmap.notes)
        ]
        self._next = 0
        self._next_lead = 0
        self._next_tone = 0

    def reset(self) -> None:
        for s in self._sched:
            s.fired = False
            s.lead_fired = False
            s.tone_fired = False
            s.stim_t_perf = None
            s.hit_at = None
            s.early_late_ms = None
        self._next = 0
        self._next_lead = 0
        self._next_tone = 0

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

    def leads_due(self, song_t: float) -> Iterator[ScheduledNote]:
        """Notes whose LEADING BUZZ is due, each yielded once, in
        order. The caller passes the song time already shifted by the
        lead, so this is the same rule as notes_due on a separate
        cursor. Independent of notes_due on purpose: the cursors move
        at different offsets and neither may skip a note the other
        has not reached."""
        while self._next_lead < len(self._sched):
            s = self._sched[self._next_lead]
            if s.note.t <= song_t:
                if not s.lead_fired:
                    s.lead_fired = True
                    yield s
                self._next_lead += 1
            else:
                return

    def tones_due(self, song_t: float) -> Iterator[ScheduledNote]:
        """Notes whose cue TONE is due, each yielded once, in order,
        on a third cursor: the caller passes the song time shifted by
        the tone's own output delay."""
        while self._next_tone < len(self._sched):
            s = self._sched[self._next_tone]
            if s.note.t <= song_t:
                if not s.tone_fired:
                    s.tone_fired = True
                    yield s
                self._next_tone += 1
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
