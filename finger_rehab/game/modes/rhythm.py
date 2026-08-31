"""Rhythm mode (Thread 2). Falling notes synced to music or a metronome.

This is the RAS (Rhythmic Auditory Stimulation) arm of the fixed-cadence
versus RAS comparative study the progress report commits to (classic.py
is the fixed-cadence control). RAS entrains movement timing to an
external auditory beat and is a well-established gait and upper-limb
rehab technique after stroke (Thaut, McIntosh and Rice 1997, Journal of
the Neurological Sciences). Unlike classic's cue-then-react loop, the
patient can see and hear the beat coming, so the task is synchronisation,
not reaction: presses land close to the beat in either direction, and a
small negative mean asynchrony (anticipating the beat by tens of ms) is
the norm in the sensorimotor-synchronisation literature, not an error
(Repp 2005, Psychonomic Bulletin and Review; Repp and Su 2013).

TIMING WINDOWS. perfect_ms/great_ms/good_ms/miss_ms (default
50/100/175/300) are a game-feel graded scoring ladder, not a published
synchronisation-accuracy criterion; they exist to give the patient
step-wise feedback and a difficulty knob, not to define what counts as
"in time" for research purposes. The signed offset logged per hit is
the number to use for any synchronisation analysis (see
analysis/session_analysis.ipynb, sec_rhythm).

CLAIM LIMITS. This mode is a within-person timing measurement, not a
validated RAS therapy protocol: note density, tempo range and windows
are this project's design choices, tuned for a short at-home session
rather than derived from a clinical RAS dosing study. Treat cross-
session offset trends as an engagement/entrainment signal, not a
therapy outcome.

CUES LAND ON THE BEAT. In RAS the pacing stimulus IS the beat: the
patient synchronises movement to it, so the cue must mark the moment
the press is due, not follow it (Thaut 1997; the sensorimotor-
synchronisation paradigm of Repp 2005 defines asynchrony against the
pacing stimulus onset). The moment the press is due in this mode is
the SCORED ZERO: _score_press subtracts the audio-path latency
(rhythm.audio_offset_ms while a song plays, metronome_offset_ms on
the click track) so a press made on the audible beat scores 0 ms.
Cue dispatch used to ignore that compensation and fire on the first
frame after the raw note time, which put the command out one frame
AFTER the scheduled beat (measured on a fake wire at 60 Hz: mean
+9 to +11 ms, never early, range +0.7..+24.5) and a full audio
offset away from the scored zero (mean -31 ms for a song, -1 ms for
the metronome: the tactile cue and the audible beat disagreed, and
the disagreement changed sign with the audio source). Both cue
paths (tone and buzzer) and the EEG stimulus marker ride on_stim,
so all of them now dispatch against the scored zero: the marker
stays on the cue the patient responds to, and the buzz agrees with
the beat they hear. Dispatch is frame-centred (fires on the frame
closest to the target, half a measured frame early rather than
always a full frame late), so the residual is jitter around zero
instead of one-sided lag. Measured after the change on the same
fake wire: mean -0.1 ms against the scored zero for a song, +1.5 ms
for the metronome, range about -11..+14 either way. The
motor's own mechanical rise (~20 ms for these ERM motors,
uncharacterised on this rig) still sits on top as a constant;
rhythm.buzz_rise_comp_ms ships 0 and exists for a rig that has
bench-measured it.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import TYPE_CHECKING

import pygame

from ...audio.beatmap import Beatmap
from ...audio.scheduler import BeatScheduler, ScheduledNote
from ...hardware.fsr_detector import PressEvent
from ..rest_skip import WaitSkip
from ..scoring import ScoreConfig, RhythmWindows, classify_offset
from ._keys import keymap_for_hand, resolve_key

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


class RhythmMode(WaitSkip):
    name = "Rhythm"

    def __init__(self, engine: "GameEngine", beatmap: Beatmap,
                 windows: RhythmWindows, score_cfg: ScoreConfig) -> None:
        self.engine = engine
        self.beatmap = beatmap
        self.windows = windows
        self.score_cfg = score_cfg
        self._presses: deque[PressEvent] = deque()
        self._countdown_done = False
        self._t_start = time.perf_counter()
        # The ONE pre-play prep every mode runs, welded to the front of
        # the note-fall timeline here (song_time counts up through it),
        # reading the same key as the GET READY card on the other
        # screens so a therapist changes the prep once for every mode.
        try:
            self._countdown_s = float(
                engine.cfg.get("game.start_countdown_s", 3.0))
        except (TypeError, ValueError):
            # Test fixtures pass a MagicMock cfg.get; keep the shipped
            # 3 s rather than crash the block start.
            self._countdown_s = 3.0
        # Extra silent ramp AFTER the 3-2-1-GO countdown but BEFORE the
        # audio plays and the first beat is due. Falling notes slide
        # into view during this window so the patient gets a clear
        # visual lead-in. All beat times in the beatmap are pushed
        # forward by this amount so audio + beats stay synced (audio
        # starts at song_t = pre_song_lead_s and a beat that originally
        # sat at audio_t = T now sits at song_t = pre_song_lead_s + T).
        try:
            self._pre_song_lead_s = float(
                engine.cfg.get("rhythm.pre_song_lead_s", 2.0)
            )
        except (TypeError, ValueError):
            # Test fixtures often pass a MagicMock for cfg.get that
            # returns something non-numeric. Fall back to 2 s default.
            self._pre_song_lead_s = 2.0
        if self._pre_song_lead_s > 0 and beatmap.notes:
            for n in beatmap.notes:
                n.t = n.t + self._pre_song_lead_s
        self.scheduler = BeatScheduler(beatmap)
        # Running estimate of the frame interval, for frame-centred cue
        # dispatch (CUES LAND ON THE BEAT in the module docstring):
        # firing on the first frame at-or-after a deadline is always
        # late by up to one frame, so the dispatch leads the target by
        # half the measured interval and the residual becomes jitter
        # around zero. Seeded at 60 Hz; clamped when updated so a
        # stalled frame cannot fire cues far ahead of the beat.
        self._frame_s = 1.0 / 60.0
        # Bench-measured motor rise compensation, subtracted from the
        # tactile cue target. Ships 0: the ERM rise (~20 ms) is
        # uncharacterised on this rig, and shipping a guess would move
        # the cue by an unverified constant. A rig that has measured
        # its motors sets this to that number.
        try:
            self._buzz_rise_comp_s = float(
                engine.cfg.get("rhythm.buzz_rise_comp_ms", 0.0)) / 1000.0
        except (TypeError, ValueError):
            self._buzz_rise_comp_s = 0.0
        # True once audio.play_song / start_metronome has been kicked off.
        self._audio_started = False
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
        # Always use the perf_counter clock so the timeline stays
        # continuous through the countdown -> pre-song-lead -> audio
        # transition. Audio playback is timed off perf_counter inside
        # AudioEngine anyway so we don't lose anything by not switching
        # to audio.song_time().
        return time.perf_counter() - self._t_start - self._countdown_s

    def _skip_lead_in(self, now: float) -> None:
        """Jump straight to the downbeat. Pulling _t_start back by
        whatever is left of the countdown and the silent lead moves
        song_time to zero-plus-lead in one step, which is exactly
        where the timer would have taken it: the audio start and every
        beat are read off song_time, so they stay in sync with each
        other. A frozen (paused) clock is left alone; there is nothing
        counting down to skip."""
        if self._frozen_song_t is not None:
            return
        remaining = (self._pre_song_lead_s - self.song_time)
        if remaining > 0:
            self._t_start -= remaining

    def _song_time_for(self, t_perf: float) -> float:
        """Convert a press's own detection time (PressEvent.t_perf) into
        song time, using the same mapping `song_time` uses. Every other
        cadence mode scores RT from the press's own timestamp
        (classic.py: ev.t_perf - stim_t_perf); rhythm must too, or a
        press queued at t_perf but not drained by update() until later
        (whatever the frame gap happens to be) gets scored against
        self.song_time read at DRAIN time, fabricating lateness that is
        pure processing delay, never the patient's. While paused the
        song clock is frozen, so a press event (which should not occur
        mid-pause) falls back to the frozen snapshot."""
        if self._frozen_song_t is not None:
            return self._frozen_song_t
        return t_perf - self._t_start - self._countdown_s

    @property
    def countdown_remaining_s(self) -> float:
        if self._countdown_done:
            return 0.0
        return max(0.0, -self.song_time)

    def queue_press(self, ev: PressEvent) -> None:
        # A press made during the countdown (screen explicitly says
        # don't press yet) must not survive to be drained the instant
        # the countdown ends -- that used to score as an unmatched
        # spurious press (penalty, red flash, miss thunk) against the
        # first note, purely for pressing during "3... 2... 1...".
        # The pause path already clears the queue on pause; this is
        # the same idea for the countdown.
        if not self._countdown_done:
            return
        # Same rule for the silent pre-song lead: the GET READY card
        # is gone but the audio has not started and no note is inside
        # its matching window yet, so a press here used to be
        # penalised as a wrong-finger spurious press (-3, red flash,
        # miss thunk) with nothing on screen saying pressing was still
        # premature. Dropped, not penalised, until the first note's
        # own matching window opens (a genuine Early on the first
        # note still gets through).
        if not self._audio_started:
            first = min((s.note.t for s in self.scheduler.scheduled
                         if s.hit_at is None), default=None)
            if (first is None or self.song_time
                    < first - self.windows.miss_ms / 1000.0):
                return
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
                    t_perf = time.perf_counter()
                    self.queue_press(PressEvent(
                        lane=lane, t_perf=t_perf,
                        value=0, baseline=0.0,
                        hand=self.engine.hand_mode,
                    ))
                    # Keyboard presses bypass engine._on_press (the FSR
                    # detector path), which is the only place raw.csv
                    # normally gets a "press" event (audit finding #112,
                    # generalising the mirror-mode fix for #75 to every
                    # mode): without this a keyboard-injected press in a
                    # mixed session (Arduino attached, keyboard kept
                    # live as backup) was indistinguishable from a real
                    # FSR press. detail="keyboard" marks the source.
                    raw_logger = getattr(self.engine, "raw_logger", None)
                    if raw_logger:
                        raw_logger.queue_event(
                            "press", lane=lane, t_perf=t_perf,
                            hand=self.engine.hand_mode, detail="keyboard")

    def update(self, dt: float) -> None:
        now = self.song_time
        # Frame-interval EMA for the frame-centred cue dispatch below.
        # Ignore the degenerate values a paused loop or a test driving
        # update(0) produces, and clamp the estimate so a stall cannot
        # widen the dispatch lead past a real display frame.
        if 0.0 < dt < 0.25:
            self._frame_s += 0.2 * (min(dt, 0.025) - self._frame_s)
        # Arm the one wait this mode has: the 3-2-1 countdown welded
        # to the front of the note-fall timeline plus the silent lead
        # that follows it. Both are pre-play ramp, not measurement:
        # every beat time is relative to the song, so pulling the
        # whole timeline forward changes when play starts and nothing
        # else. The song has not begun and no note is scoreable yet.
        if now < self._pre_song_lead_s:
            self.refresh_wait(
                "prep",
                self._t_start + self._countdown_s + self._pre_song_lead_s,
                on_skip=self._skip_lead_in,
                started_at=self._t_start,
                label="Skip countdown")
        else:
            self.clear_wait()
        # End of the visual countdown. Notes can now appear on screen
        # (they were filtered out by `upcoming` while song_time was
        # negative) but audio + first press are still pre_song_lead_s
        # away so the patient gets a clear visual ramp.
        if not self._countdown_done and now >= 0:
            self._countdown_done = True
        # Start audio once we've cleared the pre-song lead. The
        # beatmap has been shifted forward by pre_song_lead_s, so a
        # beat that originally sat at audio_t=T now sits at
        # song_t=pre_song_lead_s + T, perfectly synced with the song.
        if (self._countdown_done
                and not self._audio_started
                and now >= self._pre_song_lead_s):
            self._audio_started = True
            if self.engine.audio:
                if self.beatmap.song:
                    if not self.engine.audio.play_song(self.beatmap.song):
                        self.engine.audio.start_metronome(self.beatmap.bpm)
                else:
                    self.engine.audio.start_metronome(self.beatmap.bpm)
        if not self._countdown_done:
            return

        # Fire the cue for notes whose CUE TIME has been reached. The
        # cue time is the scored zero, note.t plus the audio-path
        # latency, so the buzz, the tone and the EEG marker land on
        # the beat the patient hears and is scored against, not on
        # the silent scheduled time a frame late (CUES LAND ON THE
        # BEAT in the module docstring). Dispatch is frame-centred:
        # firing on the frame closest to the target (half a frame of
        # lead) turns the old one-sided frame lag into jitter around
        # zero. The timestamp handed to on_stim is the scheduled cue
        # moment itself, so raw.csv's stim rows carry the cue time
        # rather than whichever frame happened to dispatch it.
        cue_shift = self._audio_latency_s(predict=True) \
            - self._buzz_rise_comp_s
        for due in self.scheduler.notes_due(
                now - cue_shift + 0.5 * self._frame_s):
            self.engine.on_stim(
                due.note.lane, due.index,
                self._t_start + self._countdown_s + due.note.t
                + cue_shift)

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

    def _audio_latency_s(self, predict: bool = False) -> float:
        """The audio-path latency between song_time and what the
        patient hears: rhythm.audio_offset_ms while a song plays,
        metronome_offset_ms on the click track, 0 with no audible
        beat (pygame mixer buffer + OS audio path; see the config
        comments). Scoring subtracts it from the press so a press on
        the AUDIBLE beat scores 0; cue dispatch adds it to the note
        so the tactile pulse and tone land on that same moment (CUES
        LAND ON THE BEAT in the module docstring). `predict` covers
        dispatch of the first beat, which is decided on the same
        frame that starts the audio: the live flags are not set yet,
        so the choice falls back to what update() is about to start.
        Scoring never predicts: a press can only be compensated for
        latency that was really in its path."""
        audio = self.engine.audio
        if audio is None:
            return 0.0
        song_playing = getattr(audio, "_song_path", None) is not None
        metronome_running = getattr(
            audio, "_metronome_period", None) is not None
        if predict and not (song_playing or metronome_running) \
                and not self._audio_started:
            song_playing = self.beatmap.song is not None
            metronome_running = not song_playing
        key = None
        if song_playing:
            key = ("rhythm.audio_offset_ms", 40)
        elif metronome_running:
            key = ("rhythm.metronome_offset_ms", 12)
        if key is None:
            return 0.0
        try:
            return float(self.engine.cfg.get(*key)) / 1000.0
        except (TypeError, ValueError):
            return 0.0

    def _score_press(self, ev: PressEvent) -> None:
        # song_time is wall-clock-since-play_song, but the audible music
        # lags that by ~20-50 ms (pygame mixer buffer + OS audio path).
        # Without compensating, a press that lands on the AUDIBLE beat
        # registers as ~40 ms Late. Subtract the configured offset so
        # the patient's reference frame (what they hear) lines up with
        # ours (when beats were scheduled). Only meaningful when sound
        # is actually reaching the patient's ears: a keyboard-only or
        # audio-disabled session has no playback latency to compensate
        # for, and the click-track metronome (512-sample buffer, ~12 ms)
        # has a far smaller latency than a decoded song file, so it gets
        # its own, smaller constant rather than borrowing the song one.
        offset_s = self._audio_latency_s()
        now = self._song_time_for(ev.t_perf) - offset_s
        miss_radius_s = self.windows.miss_ms / 1000.0
        best: ScheduledNote | None = None
        best_d = float("inf")
        for s in self.scheduler.scheduled:
            if s.hit_at is not None or getattr(s, "_miss_logged", False):
                continue
            if s.note.lane != ev.lane:
                continue
            d = now - s.note.t
            # Early floor is -miss_ms so the documented Early tier
            # (-miss_ms..-good_ms, 1 point) is actually reachable: with
            # a -good_ms floor an anticipation at -250 ms was penalised
            # as a spurious wrong-finger press and the note then missed,
            # truncating the logged offset distribution asymmetrically
            # (early cut at -good_ms, late kept to +miss_ms) and biasing
            # the mean asynchrony positive. Anticipating the beat is the
            # norm in sensorimotor synchronisation, not an error (Repp
            # 2005). A press earlier than -miss_ms still never consumes
            # a future note, and nearest-|d| matching still lets a
            # closer resolved-side note win.
            if d < -miss_radius_s or d > miss_radius_s * 2:
                continue
            ad = abs(d)
            if ad < best_d:
                best_d = ad
                best = s
        if best is None:
            self.engine.log_rhythm_unmatched(ev.lane, now,
                                             t_press_perf=ev.t_perf)
            return
        offset_ms = (now - best.note.t) * 1000.0
        best.hit_at = now
        best.early_late_ms = offset_ms
        label, points = classify_offset(offset_ms, self.windows, self.score_cfg)
        self.engine.log_rhythm_hit(best, offset_ms, label, points, now,
                                   t_press_perf=ev.t_perf)
