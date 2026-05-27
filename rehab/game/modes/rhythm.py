"""Rhythm mode (Thread 2). Falling notes synced to music or a metronome."""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import TYPE_CHECKING

import pygame

from ...audio.beatmap import Beatmap
from ...audio.scheduler import BeatScheduler, ScheduledNote
from ...hardware.fsr_detector import PressEvent
from ..scoring import ScoreConfig, RhythmWindows, classify_offset
from ._keys import keymap_for_hand, resolve_key

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


class RhythmMode:
    name = "Rhythm"

    def __init__(self, engine: "GameEngine", beatmap: Beatmap,
                 windows: RhythmWindows, score_cfg: ScoreConfig) -> None:
        self.engine = engine
        self.beatmap = beatmap
        self.scheduler = BeatScheduler(beatmap)
        self.windows = windows
        self.score_cfg = score_cfg
        self._presses: deque[PressEvent] = deque()
        self._countdown_done = False
        self._t_start = time.perf_counter()
        self._countdown_s = 3.0
        # Snapshot of song_time at the moment we paused. While paused the
        # property returns this fixed value so the falling notes don't keep
        # scrolling across the screen during the pause.
        self._frozen_song_t: float | None = None

    @property
    def song_time(self) -> float:
        # If we're paused, hold the song clock at the snapshot we took on
        # pause so the falling notes / strike line don't keep moving while
        # the music is silent.
        if self._frozen_song_t is not None:
            return self._frozen_song_t
        # Prefer the audio clock when active so visuals and music stay locked.
        if self.engine.audio and self.engine.audio.is_playing:
            return self.engine.audio.song_time()
        return time.perf_counter() - self._t_start - self._countdown_s

    @property
    def countdown_remaining_s(self) -> float:
        if self._countdown_done:
            return 0.0
        return max(0.0, -self.song_time)

    def queue_press(self, ev: PressEvent) -> None:
        self._presses.append(ev)

    def on_pause(self) -> None:
        # Lock the song clock to the moment we paused. The drawing code
        # asks for song_time every frame; with the snapshot in place the
        # notes appear frozen mid-fall.
        self._frozen_song_t = self.song_time

    def on_resume(self, pause_dur: float) -> None:
        # Shift the perf_counter-based clock forward. The audio engine's
        # song_time also restarts from 0 when the song is replayed, so
        # we only adjust the fallback clock here. Scheduler progress is
        # preserved because it tracks _next_idx, not absolute time.
        self._t_start += pause_dur
        # Drop the snapshot so song_time goes back to live time.
        self._frozen_song_t = None

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN:
            # Keyboard is always-on as a backup, even with an Arduino
            # active. See classic.py for the reasoning.
            km = self.engine.cfg.get(
                keymap_for_hand(self.engine.hand_mode), {},
            )
            for key_name, lane in km.items():
                kc = resolve_key(key_name)
                if kc and e.key == kc:
                    self.queue_press(PressEvent(
                        lane=lane, t_perf=time.perf_counter(),
                        value=0, baseline=0.0,
                        hand=self.engine.hand_mode,
                    ))

    def update(self, dt: float) -> None:
        now = self.song_time
        # Start music or click track after the countdown elapses.
        if not self._countdown_done and now >= 0:
            self._countdown_done = True
            if self.engine.audio:
                if self.beatmap.song:
                    if not self.engine.audio.play_song(self.beatmap.song):
                        self.engine.audio.start_metronome(self.beatmap.bpm)
                else:
                    self.engine.audio.start_metronome(self.beatmap.bpm)
        if not self._countdown_done:
            return

        # Fire stim events for notes whose target time has been reached.
        for due in self.scheduler.notes_due(now):
            self.engine.on_stim(due.note.lane, due.index, time.perf_counter())

        # Score any queued press inputs.
        while self._presses:
            ev = self._presses.popleft()
            self._score_press(ev)

        # Log notes whose miss-window has closed without a hit. Pass
        # was_pressed=False so the trial row records num_presses=0 and
        # an empty keys_pressed - the patient didn't press anything here.
        miss_radius_s = self.windows.miss_ms / 1000.0
        for s in self.scheduler.scheduled:
            if s.hit_at is not None or getattr(s, "_miss_logged", False):
                continue
            if now > s.note.t + miss_radius_s:
                s._miss_logged = True
                self.engine.log_rhythm_hit(s, 0.0, "Miss",
                                            self.score_cfg.miss_points, now,
                                            was_pressed=False)

        if self.scheduler.all_done(now):
            self.engine.finish_block()

    def upcoming(self, ahead_s: float = 1.5) -> list[ScheduledNote]:
        return self.scheduler.upcoming(self.song_time, ahead_s)

    def _score_press(self, ev: PressEvent) -> None:
        # song_time is wall-clock-since-play_song, but the audible music
        # lags that by ~20-50 ms (pygame mixer buffer + OS audio path).
        # Without compensating, a press that lands on the AUDIBLE beat
        # registers as ~40 ms Late. Subtract the configured offset so
        # the patient's reference frame (what they hear) lines up with
        # ours (when beats were scheduled).
        try:
            offset_s = float(self.engine.cfg.get(
                "rhythm.audio_offset_ms", 40)) / 1000.0
        except (TypeError, ValueError):
            offset_s = 0.0
        now = self.song_time - offset_s
        best: ScheduledNote | None = None
        best_d = float("inf")
        for s in self.scheduler.scheduled:
            if s.hit_at is not None:
                continue
            if s.note.lane != ev.lane:
                continue
            d = abs(s.note.t - now)
            if d > self.windows.miss_ms / 1000.0 * 2:
                continue
            if d < best_d:
                best_d = d
                best = s
        if best is None:
            self.engine.log_rhythm_unmatched(ev.lane, now)
            return
        offset_ms = (now - best.note.t) * 1000.0
        best.hit_at = now
        best.early_late_ms = offset_ms
        label, points = classify_offset(offset_ms, self.windows, self.score_cfg)
        self.engine.log_rhythm_hit(best, offset_ms, label, points, now)
