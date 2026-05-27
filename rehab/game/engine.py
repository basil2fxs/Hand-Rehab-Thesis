"""Pygame main loop. Owns the screen registry, source pump, loggers, and
per-hand FSR detectors (Thread 3 bilateral)."""
from __future__ import annotations

import copy
import logging
import time
from pathlib import Path

import pygame

from ..audio.engine import AudioEngine
from ..data.logger import RawLogger, SessionPaths, TrialLogger
from ..data.session import Session
from ..hardware.fsr_detector import (
    Calibration, FSRDetector, PressEvent, ReleaseEvent,
)
from ..hardware.source import Source
from ..ui.theme import get as get_theme
from ..ui.widgets import Layout
from .scoring import ScoreConfig, RhythmWindows, TrialResult


log = logging.getLogger(__name__)


class GameEngine:
    def __init__(self, cfg, source: Source) -> None:
        self.cfg = cfg
        self.source = source
        self.theme = get_theme(cfg.get("ui.theme", "clinical"))
        w, h = cfg.get("ui.resolution", [1280, 800])
        self.layout = Layout(w, h, float(cfg.get("ui.font_scale", 1.0)))

        # Bilateral: one detector per hand. Number of sensors per hand is fixed
        # at 4, so for "both" we have 8 total sensors split into two detectors.
        self.hand_mode = str(cfg.get("bilateral.hand", "right"))
        self.detectors: dict[str, FSRDetector] = {}
        self._build_detectors()

        self.session = Session(
            participant=str(cfg.get("session.participant") or "NA"),
            hand=self.hand_mode,
            source_name=getattr(source, "name", "?"),
            config_snapshot=copy.deepcopy(cfg.data),
        )
        # Fallbacks here MUST match config/default.yaml + ScoreConfig defaults.
        # In particular miss_points / early_penalty default to 0 so the score
        # never goes negative when a custom config omits these keys.
        self.score_cfg = ScoreConfig(
            great_ms=int(cfg.get("scoring.great_ms", 200)),
            great_points=int(cfg.get("scoring.great_points", 3)),
            good_ms=int(cfg.get("scoring.good_ms", 500)),
            good_points=int(cfg.get("scoring.good_points", 2)),
            late_points=int(cfg.get("scoring.late_points", 1)),
            miss_points=int(cfg.get("scoring.miss_points", 0)),
            early_penalty=int(cfg.get("scoring.early_penalty", 0)),
        )

        self.audio: AudioEngine | None = None
        self.mode = None
        self.screen_obj = None
        self.running = True
        self.score = 0
        self.hits = 0
        self.misses = 0
        # `hit_streak` counts consecutive hits in a row. We fire an
        # encouragement popup when it hits one of the thresholds below.
        # `miss_streak` is the opposite - when it hits the recovery
        # threshold the adaptive mode kicks into recovery mode (slow + easy).
        self.hit_streak = 0
        self.miss_streak = 0
        self._streak_thresholds = (3, 5, 8, 12, 20, 30, 50)
        self._streak_fired: set[int] = set()
        # Three missed trials in a row drops the patient into recovery so
        # they get an easy hit to rebuild momentum.
        self._recovery_threshold = 3
        # Most recent points gained on a press. The HUD shows the current
        # multiplier so the patient sees why their score jumped.
        self._last_gained = 0
        self.current_block = "(none)"
        self.session_paths: SessionPaths | None = None
        self.last_session_root: str | None = None
        self.trial_logger: TrialLogger | None = None
        self.raw_logger: RawLogger | None = None
        self._screens: dict = {}
        self._show_fps = bool(cfg.get("ui.show_fps", False))
        self.paused = False
        self._pause_started_at: float | None = None
        # When the user paused a rhythm block we need to remember the song
        # path so we can resume it, since audio.stop() clears _song_path.
        self._paused_song_path: str | None = None
        self._paused_song_time: float = 0.0
        # Tracks whether the source was connected on the last frame, so
        # we only log a "disconnected" warning ONCE when the Arduino
        # drops out mid-block instead of spamming every frame.
        self._source_was_connected = True

    # ---- bilateral plumbing ------------------------------------------------
    def _build_detectors(self) -> None:
        n = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
        cal_kwargs = dict(
            num_sensors=n,
            baseline_alpha=float(self.cfg.get("fsr.baseline_alpha", 0.02)),
            value_alpha=float(self.cfg.get("fsr.value_alpha", 0.35)),
            on_delta=list(self.cfg.get("fsr.on_delta", [45, 90, 45, 45])),
            off_delta=list(self.cfg.get("fsr.off_delta", [35, 70, 35, 35])),
            abs_on_min=list(self.cfg.get("fsr.abs_on_min", [320, 400, 320, 320])),
            abs_off_max=list(self.cfg.get("fsr.abs_off_max", [350, 450, 350, 350])),
            debounce_ms=int(self.cfg.get("fsr.debounce_ms", 100)),
        )
        if self.hand_mode == "both":
            self.detectors["right"] = FSRDetector(Calibration(**cal_kwargs), hand="right")
            self.detectors["left"] = FSRDetector(Calibration(**cal_kwargs), hand="left")
        else:
            self.detectors[self.hand_mode] = FSRDetector(
                Calibration(**cal_kwargs), hand=self.hand_mode,
            )
        for det in self.detectors.values():
            det.on_press = self._on_press
            det.on_release = self._on_release

    def _on_press(self, ev: PressEvent) -> None:
        # In bilateral mode we want the mode to see one big 0..7 lane space,
        # not two independent 0..3 spaces. Left-hand presses shift up by
        # num_sensors_per_hand so left index becomes lane 4, left little = 7.
        if self.hand_mode == "both" and ev.hand == "left":
            n_per_hand = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
            ev = PressEvent(
                lane=ev.lane + n_per_hand,
                t_perf=ev.t_perf,
                value=ev.value,
                baseline=ev.baseline,
                hand=ev.hand,
            )
        if self.mode and hasattr(self.mode, "queue_press"):
            self.mode.queue_press(ev)
        if self.raw_logger:
            self.raw_logger.queue_event("press", lane=ev.lane,
                                         t_perf=ev.t_perf, hand=ev.hand)

    @property
    def total_lanes(self) -> int:
        """How many lanes the active mode addresses: 4 unilateral, 8 bilateral."""
        n = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
        return n * 2 if self.hand_mode == "both" else n

    def _on_release(self, ev: ReleaseEvent) -> None:
        if self.raw_logger:
            self.raw_logger.queue_event("release", lane=ev.lane,
                                         t_perf=ev.t_perf, hand=ev.hand)

    def _feed_detectors(self, t_perf: float, vals: tuple[int, ...]) -> None:
        n = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
        if self.hand_mode == "both":
            # First N values are the right hand, next N are the left hand.
            right_vals = tuple(vals[:n])
            left_vals = tuple(vals[n:n * 2]) if len(vals) >= n * 2 else (0,) * n
            self.detectors["right"].feed(t_perf, right_vals)
            self.detectors["left"].feed(t_perf, left_vals)
        else:
            self.detectors[self.hand_mode].feed(t_perf, tuple(vals[:n]))

    # ---- main loop ---------------------------------------------------------
    def run(self) -> int:
        try:
            pygame.init()
        except pygame.error as e:
            log.error("pygame.init failed: %s", e)
            return 3
        # pygame.init usually pulls in the font module, but on some odd
        # configs (stripped pygame-ce builds, headless CI) it doesn't, so
        # we call it explicitly and treat any pygame.error here as a fatal
        # startup problem rather than letting the screen-render crash later.
        try:
            pygame.font.init()
        except (pygame.error, NotImplementedError) as e:
            log.error("pygame.font failed to init: %s. "
                       "Install pygame-ce on Py 3.14.", e)
            pygame.quit()
            return 3
        flags = pygame.FULLSCREEN if self.cfg.get("ui.fullscreen", False) else 0
        try:
            screen = pygame.display.set_mode(
                (self.layout.width, self.layout.height), flags,
            )
        except pygame.error as e:
            # Most common cause: no display available (headless / SSH session
            # without X). Spell it out instead of letting the traceback land
            # on the patient.
            log.error("Could not open the game window at %dx%d: %s",
                       self.layout.width, self.layout.height, e)
            pygame.quit()
            return 4
        pygame.display.set_caption("Finger Rehab")
        clock = pygame.time.Clock()
        self._screens = self._build_screens()
        self.show_title()
        self.source.start()
        self.audio = self._build_audio()
        try:
            last = time.perf_counter()
            while self.running:
                now = time.perf_counter()
                dt = now - last
                last = now
                # Cap dt so an alt-tab stall doesn't burst-fire timeouts on resume.
                if dt > 0.1:
                    dt = 0.1

                if self.paused:
                    # Drain and discard samples so the queue doesn't pile up
                    # during a long pause (otherwise on resume we'd flood
                    # the detectors with stale data).
                    while self.source.get_sample(timeout=0) is not None:
                        pass
                else:
                    self._pump_source()

                # Global events (Esc, P, F2, QUIT) always go through. Screen-
                # specific events (button clicks, key presses for lanes) are
                # gated on paused so the pause overlay truly blocks input.
                for e in pygame.event.get():
                    self._handle_global_event(e)
                    if self.screen_obj and not self.paused:
                        self.screen_obj.handle_event(e)
                    elif self.screen_obj and self.paused:
                        # Still let buttons on pause-friendly screens (results,
                        # menus) work. Only block the gameplay/rhythm screens.
                        if self.screen_obj not in (
                            self._screens.get("gameplay"),
                            self._screens.get("rhythm"),
                        ):
                            self.screen_obj.handle_event(e)

                if not self.paused:
                    if self.audio:
                        self.audio.tick()
                    if self.screen_obj:
                        self.screen_obj.update(dt)
                if self.screen_obj:
                    # Draw always so the pause overlay shows.
                    self.screen_obj.draw(screen)
                self._draw_hud(screen, clock)
                pygame.display.flip()
                clock.tick(120)
            return 0
        except KeyboardInterrupt:
            log.info("Interrupted by user (Ctrl+C)")
            return 130
        finally:
            # If we exited the loop while a block was running (Ctrl+C, window
            # close, crash), still save partial metadata so the data isn't lost.
            try:
                self._abandon_if_in_block()
            except Exception as e:
                log.warning("abandon-on-exit: %s", e)
            try:
                self.source.stop()
            except Exception as e:
                log.warning("source.stop: %s", e)
            if self.audio:
                try:
                    self.audio.shutdown()
                except Exception as e:
                    log.warning("audio.shutdown: %s", e)
            try:
                self._close_loggers()
            except Exception as e:
                log.warning("close loggers: %s", e)
            try:
                pygame.quit()
            except Exception as e:
                log.warning("pygame.quit: %s", e)

    def request_quit(self) -> None:
        self.running = False

    # ---- pause / resume ----------------------------------------------------
    def _pause_now(self) -> None:
        """Freeze the active block. Drops queued presses, stops audio,
        remembers the song state so we can resume in the right place."""
        if self.paused:
            return
        self.paused = True
        self._pause_started_at = time.perf_counter()
        # Remember where the song was up to (only meaningful for rhythm mode).
        if self.audio and self.audio.is_playing:
            self._paused_song_path = getattr(self.audio, "_song_path", None)
            self._paused_song_time = self.audio.song_time()
        else:
            self._paused_song_path = None
            self._paused_song_time = 0.0
        # Tell the mode it's been paused. Rhythm mode uses this to snapshot
        # its song clock so the falling notes freeze on screen.
        if self.mode and hasattr(self.mode, "on_pause"):
            try:
                self.mode.on_pause()
            except Exception as e:
                log.warning("mode.on_pause failed: %s", e)
        if self.audio:
            self.audio.stop()
        # Drop any presses the mode queued up just before pause so we don't
        # process them on resume.
        if self.mode and hasattr(self.mode, "_presses"):
            self.mode._presses.clear()
        log.info("Block paused")

    def _resume_now(self) -> None:
        if not self.paused or self._pause_started_at is None:
            self.paused = False
            return
        pause_dur = time.perf_counter() - self._pause_started_at
        # Tell the mode to shift any in-flight timestamps forward so the
        # active trial doesn't instantly time out and the next-trigger
        # interval doesn't think it's overdue by an entire pause.
        if self.mode and hasattr(self.mode, "on_resume"):
            try:
                self.mode.on_resume(pause_dur)
            except Exception as e:
                log.warning("mode.on_resume failed: %s", e)
        # Rhythm mode: try to resume the song roughly where we paused so the
        # visuals stay in sync. play_song(start_s=...) uses pygame's seek
        # which works for OGG/WAV; for MP3 it usually still works but may
        # snap to the nearest frame.
        if self.audio and self.screen_obj is self._screens.get("rhythm"):
            bm = getattr(self.mode, "beatmap", None)
            resume_at = self._paused_song_time
            song = self._paused_song_path or (bm.song if bm else None)
            if song:
                if not self.audio.play_song(song, start_s=resume_at):
                    if bm:
                        self.audio.start_metronome(bm.bpm)
            elif bm:
                self.audio.start_metronome(bm.bpm)
        self.paused = False
        self._pause_started_at = None
        log.info("Block resumed after %.2fs", pause_dur)

    def _build_screens(self) -> dict:
        from ..ui.screens import (
            DiagnosticsScreen, TitleScreen, SetupScreen, GameplayScreen,
            RhythmScreen, RhythmSetupScreen, ResultsScreen,
            ModeSelectScreen,
        )
        return {
            "title": TitleScreen(self),
            "mode_select": ModeSelectScreen(self),
            "setup": SetupScreen(self),
            "rhythm_setup": RhythmSetupScreen(self),
            "gameplay": GameplayScreen(self),
            "rhythm": RhythmScreen(self),
            "results": ResultsScreen(self),
            "diagnostics": DiagnosticsScreen(self),
        }

    def _build_audio(self) -> AudioEngine | None:
        if not self.cfg.get("audio.enabled", True):
            return None
        a = AudioEngine(master_volume=float(self.cfg.get("audio.master_volume", 0.8)))
        a.init()
        return a

    def _handle_global_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.QUIT:
            self._abandon_if_in_block()
            self.running = False
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self._handle_escape()
            elif e.key == pygame.K_F2:
                self._show_fps = not self._show_fps
            elif e.key == pygame.K_p:
                on_block = self.screen_obj in (
                    self._screens.get("gameplay"),
                    self._screens.get("rhythm"),
                )
                if on_block:
                    if not self.paused:
                        self._pause_now()
                    else:
                        self._resume_now()

    def _handle_escape(self) -> None:
        """Two-step exit so a therapist can run several blocks for the
        same patient without retyping the name.

        - Esc on title -> quit the app
        - Esc on mode-select -> back to title AND clear the participant
          name so the next patient enters their own
        - Esc on setup / rhythm-setup / results -> back to mode-select
          (name persists)
        - Esc during a block (gameplay / rhythm) -> abandon, save partial
          data, then back to mode-select (name persists)
        """
        title = self._screens.get("title")
        mode_select = self._screens.get("mode_select")
        # Whatever screen we're on, clear pause + stop audio first so we
        # never land somewhere with a stale "PAUSED" overlay or music
        # still playing into a menu.
        self.paused = False
        self._pause_started_at = None
        if self.audio:
            try:
                self.audio.stop()
            except Exception as e:
                log.warning("audio.stop on Esc: %s", e)
        rs = self._screens.get("rhythm_setup")
        if rs and hasattr(rs, "_stop_preview"):
            try:
                rs._stop_preview()
            except Exception:
                pass

        if self.screen_obj is title:
            self.running = False
            return
        if self.screen_obj is mode_select:
            # Clear the participant name so the title screen comes up
            # blank for the next patient.
            self.session.participant = "NA"
            self.cfg.data.setdefault("session", {})["participant"] = None
            self.show_title()
            return
        # Diagnostics returns straight to title without abandoning any
        # block (none could be in-flight on this screen).
        if self.screen_obj is self._screens.get("diagnostics"):
            self.show_title()
            return
        # Anything else (setup, rhythm_setup, gameplay, rhythm, results)
        # drops back to mode-select, abandoning any in-flight block.
        self._abandon_if_in_block()
        self.show_mode_select()

    def _check_source_connection(self) -> None:
        """Warn-once if a source that's meant to provide samples loses
        its connection mid-block. The mainloop keeps ticking either
        way (so Esc still works to abandon) but the therapist needs to
        see SOMETHING happened, otherwise the patient just looks unable
        to press anything."""
        if not self.source.provides_samples:
            return  # Keyboard fallback doesn't connect/disconnect.
        connected = self.source.is_connected
        if self._source_was_connected and not connected:
            log.warning("Source %s disconnected mid-session. Presses will "
                         "stop registering until it reconnects.",
                         getattr(self.source, "name", "?"))
            if self.raw_logger:
                try:
                    self.raw_logger.queue_event(
                        "source_disconnected",
                        detail=getattr(self.source, "name", "?"),
                        hand=self.hand_mode,
                    )
                except Exception:
                    pass
        elif (not self._source_was_connected) and connected:
            log.info("Source %s reconnected.",
                      getattr(self.source, "name", "?"))
        self._source_was_connected = connected

    def _pump_source(self) -> None:
        self._check_source_connection()
        while True:
            s = self.source.get_sample(timeout=0)
            if s is None:
                break
            self._feed_detectors(s.t_perf, s.values)
            if self.raw_logger:
                # In "both" mode the first 4 values are right, next 4 are left.
                # We log them all in the raw row, the hand column is "both".
                self.raw_logger.queue_sample(s.t_perf, s.values, hand=self.hand_mode)
            # Push to lane strips for live readout.
            for key in ("gameplay", "rhythm"):
                sc = self._screens.get(key)
                if sc and hasattr(sc, "lanes"):
                    n_per_hand = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
                    for i, ls in enumerate(sc.lanes):
                        # Lane strip may belong to either hand. We just walk the
                        # full sample vector left-to-right.
                        if i < len(s.values):
                            ls.value = s.values[i]
                            hand = ls.hand
                            det = self.detectors.get(hand)
                            if det:
                                # Lane index within this hand wraps every n_per_hand.
                                local = i % n_per_hand
                                b = det.baseline[local]
                                ls.baseline = b if b is not None else 0.0

    def _draw_hud(self, screen, clock) -> None:
        if not self._show_fps:
            return
        from ..ui.widgets import draw_text
        fps = clock.get_fps()
        draw_text(screen, f"FPS {fps:.0f}",
                  (self.layout.width - 10, self.layout.height - 10),
                  self.theme, self.layout, pt=12, colour=self.theme.muted)

    # ---- screen helpers ----------------------------------------------------
    def show_title(self) -> None:
        ts = self._screens["title"]
        # Refresh the name input so a cleared participant (from Esc on
        # mode-select) actually shows up blank, instead of the stale
        # text from whatever the previous patient typed.
        if hasattr(ts, "refresh"):
            ts.refresh()
        self.screen_obj = ts

    def show_diagnostics(self) -> None:
        ds = self._screens.get("diagnostics")
        if ds is None:
            return
        # Rebuild lanes so they match the currently configured hand
        # mode (which the user might have changed since the screens
        # were first built).
        if hasattr(ds, "rebuild_lanes"):
            ds.rebuild_lanes()
        self.screen_obj = ds

    def show_mode_select(self) -> None:
        self.screen_obj = self._screens["mode_select"]

    def show_setup(self) -> None:
        self.screen_obj = self._screens["setup"]

    def show_rhythm_setup(self) -> None:
        rs = self._screens["rhythm_setup"]
        # Rescan the music folder every time we land on this screen so
        # files dropped in mid-session show up without restarting.
        if hasattr(rs, "refresh"):
            rs.refresh()
        self.screen_obj = rs

    def show_results(self) -> None:
        self.screen_obj = self._screens["results"]

    # ---- block lifecycle ---------------------------------------------------
    def begin_classic_block(self) -> None:
        from .modes.classic import ClassicMode
        pattern = self._parse_pattern(
            self.cfg.get("game.pattern", "2,1,3,2,4,1"),
            self.total_lanes,
        )
        self.mode = ClassicMode(
            engine=self,
            pattern=pattern,
            repeat_count=int(self.cfg.get("game.repeat_count", 8)),
            trigger_interval_s=float(self.cfg.get("game.trigger_interval_s", 0.6)),
            timeout_s=float(self.cfg.get("game.timeout_s", 1.0)),
            early_window_s=float(self.cfg.get("game.early_window_s", 0.1)),
            score_cfg=self.score_cfg,
        )
        self._begin_block("classic")
        self.screen_obj = self._screens["gameplay"]

    def begin_adaptive_block(self) -> None:
        from .modes.adaptive import AdaptiveMode
        from ..analytics.adaptive import AdaptiveConfig
        # Fallbacks must mirror config/default.yaml so a stripped-down user
        # config inherits the same behaviour the YAML claims it does.
        ac = AdaptiveConfig(
            target_low=float(self.cfg.get("adaptive.target_low", 0.65)),
            target_high=float(self.cfg.get("adaptive.target_high", 0.80)),
            bpm_min=float(self.cfg.get("adaptive.bpm_min", 10.0)),
            bpm_max=float(self.cfg.get("adaptive.bpm_max", 140.0)),
            bpm_step=float(self.cfg.get("adaptive.bpm_step", 10.0)),
            weakness_bias=float(self.cfg.get("adaptive.weakness_bias", 2.5)),
            min_trials=int(self.cfg.get("adaptive.min_trials", 2)),
        )
        self.mode = AdaptiveMode(
            engine=self,
            num_lanes=self.total_lanes,
            total_trials=int(self.cfg.get("game.total_trials", 40)),
            block_size=int(self.cfg.get("adaptive.block_size", 4)),
            score_cfg=self.score_cfg,
            timeout_s=float(self.cfg.get("game.timeout_s", 1.0)),
            early_window_s=float(self.cfg.get("game.early_window_s", 0.1)),
            start_bpm=float(self.cfg.get("adaptive.start_bpm", 60)),
            adaptive_cfg=ac,
        )
        self._begin_block("adaptive")
        self.screen_obj = self._screens["gameplay"]

    def begin_rhythm_block(self, beatmap) -> None:
        from .modes.rhythm import RhythmMode
        rw = RhythmWindows(
            perfect_ms=float(self.cfg.get("rhythm.perfect_ms", 50)),
            great_ms=float(self.cfg.get("rhythm.great_ms", 100)),
            good_ms=float(self.cfg.get("rhythm.good_ms", 175)),
            miss_ms=float(self.cfg.get("rhythm.miss_ms", 300)),
        )
        self.mode = RhythmMode(
            engine=self, beatmap=beatmap, windows=rw, score_cfg=self.score_cfg,
        )
        self._begin_block("rhythm")
        self.screen_obj = self._screens["rhythm"]

    def _begin_block(self, name: str) -> None:
        self.current_block = name
        self.session.started_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.score = 0
        self.hits = 0
        self.misses = 0
        # Fresh streak per block so encouragement popups fire again and a
        # leftover miss streak from the previous block doesn't trigger
        # recovery mode on the first trial.
        self.hit_streak = 0
        self.miss_streak = 0
        self._streak_fired.clear()
        # Performance-counter anchor so log_trial can compute the
        # block-relative time for each trial without re-parsing
        # started_at (which is wall-clock and resolution-limited).
        self._block_t0 = time.perf_counter()
        # Block-summary aggregates that get written into metadata.json
        # at finish_block so the analyst has a quick read of the block
        # alongside the raw trial / sample CSVs.
        self._block_peak_streak = 0
        self._block_rt_sum = 0.0
        self._block_rt_count = 0
        self._block_bpm_min: float | None = None
        self._block_bpm_max: float | None = None
        # Wrong-finger press counters. classic / adaptive count any trial
        # whose `had_incorrect_press` is TRUE. Rhythm counts every
        # spurious press logged by log_rhythm_unmatched (presses on a
        # lane that had no scheduled note in the press window).
        self._block_wrong_press_trials = 0
        self._block_rhythm_spurious_presses = 0
        self._open_loggers()
        # Reset detectors at block start so old baselines don't leak in.
        for d in self.detectors.values():
            d.reset()

    def _open_loggers(self) -> None:
        data_dir = self.cfg.resolve_path(self.cfg.get("session.data_dir", "sessions"))
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        self.session_paths = SessionPaths.for_session(
            Path(data_dir), self.session.participant,
        )
        self.trial_logger = TrialLogger(self.session_paths.trials_csv)
        n_total = (8 if self.hand_mode == "both"
                   else int(self.cfg.get("fsr.num_sensors_per_hand", 4)))
        self.raw_logger = RawLogger(self.session_paths.raw_csv, num_sensors=n_total)
        self.raw_logger.start()
        self.raw_logger.queue_event("block_start", detail=self.current_block,
                                     hand=self.hand_mode)
        # Make last_session_root available immediately so a crash mid-
        # block still leaves a recoverable path. Note that this also
        # means the results screen has a path to show even when the
        # save itself failed downstream.
        self.last_session_root = str(self.session_paths.root)
        # Write an initial metadata.json so a hard kill mid-block still
        # leaves a recoverable record. The file is rewritten at
        # finish_block or _abandon_if_in_block. notes describes the
        # current state so a researcher reading the folder knows whether
        # the session was abandoned, crashed, or completed.
        self.session.notes = "block in progress (auto-save)"
        self.session.finished_at = ""
        try:
            self.session.save(self.session_paths.metadata_json)
        except Exception as e:
            log.warning("Could not write initial metadata: %s", e)
        log.info("Saving session to: %s", self.session_paths.root)

    def _close_loggers(self) -> None:
        if self.raw_logger:
            try:
                self.raw_logger.stop()
            except Exception:
                pass
            self.raw_logger = None
        if self.trial_logger:
            try:
                self.trial_logger.close()
            except Exception:
                pass
            self.trial_logger = None

    def _build_block_summary(self, status: str) -> dict:
        """Aggregates that go into metadata.json so an analyst can grok
        a block at a glance without loading trials.csv. `status` is
        "completed" or "abandoned"."""
        n = self.hits + self.misses
        hit_rate = (self.hits / n) if n > 0 else 0.0
        duration_s = None
        t0 = getattr(self, "_block_t0", None)
        if t0 is not None:
            duration_s = round(time.perf_counter() - t0, 3)
        rt_count = getattr(self, "_block_rt_count", 0)
        avg_rt_ms = None
        if rt_count > 0:
            avg_rt_ms = round(self._block_rt_sum / rt_count, 1)
        summary: dict = {
            "block": self.current_block,
            "status": status,
            "trials": n,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 3),
            "final_score": self.score,
            "peak_streak": getattr(self, "_block_peak_streak", 0),
            "avg_rt_ms": avg_rt_ms,
            "duration_s": duration_s,
            # Wrong-finger activity. classic / adaptive: trials where a
            # non-target lane was pressed. rhythm: total spurious
            # presses (presses with no nearby scheduled note). Both
            # zero is the "no wrong-finger errors" outcome.
            "wrong_press_trials": getattr(
                self, "_block_wrong_press_trials", 0),
            "rhythm_spurious_presses": getattr(
                self, "_block_rhythm_spurious_presses", 0),
        }
        # Adaptive-only context.
        bpm_min = getattr(self, "_block_bpm_min", None)
        bpm_max = getattr(self, "_block_bpm_max", None)
        if bpm_min is not None or bpm_max is not None:
            summary["bpm_min"] = (round(bpm_min, 1)
                                    if bpm_min is not None else None)
            summary["bpm_max"] = (round(bpm_max, 1)
                                    if bpm_max is not None else None)
            adapter = getattr(self.mode, "adapter", None) if self.mode else None
            if adapter is not None:
                summary["bpm_final"] = round(float(adapter.bpm), 1)
        return summary

    def finish_block(self) -> None:
        if self.raw_logger:
            self.raw_logger.queue_event("block_end", detail=self.current_block,
                                         hand=self.hand_mode)
        # Silence music / metronome / stim sounds before showing results.
        # Otherwise a track that didn't naturally end keeps playing into
        # the results screen, and the last click of the metronome tail
        # can still be queued in a channel.
        if self.audio:
            try:
                self.audio.stop()
            except Exception as e:
                log.warning("audio.stop on finish_block: %s", e)
        self.session.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.session.block_summary = self._build_block_summary("completed")
        self.session.notes = "block completed"
        # Wrap the metadata save: if the JSON write fails (disk full,
        # permission denied, weird path) we still need to drop the
        # loggers so the raw-CSV thread + open file handle don't leak.
        if self.session_paths:
            self.last_session_root = str(self.session_paths.root)
            try:
                self.session.save(self.session_paths.metadata_json)
            except Exception as e:
                log.warning("Could not save metadata on finish: %s", e)
        self._close_loggers()
        self.session_paths = None
        self.show_results()

    def _abandon_if_in_block(self) -> None:
        """Esc / QUIT mid-block. Marks the metadata as abandoned so we still
        keep the partial CSV and a record of what happened."""
        if not self.session_paths:
            return
        log.info("Abandoning in-progress block")
        if self.audio:
            try:
                self.audio.stop()
            except Exception:
                pass
        if self.raw_logger:
            try:
                self.raw_logger.queue_event(
                    "block_abandoned", detail=self.current_block,
                    hand=self.hand_mode,
                )
            except Exception:
                pass
        self.session.finished_at = time.strftime("%Y-%m-%dT%H:%M:%S")
        self.session.notes = f"abandoned mid-block ({self.current_block})"
        # Capture whatever we have on the abandon path so a partial
        # block still has aggregates a researcher can use.
        self.session.block_summary = self._build_block_summary("abandoned")
        # Record the path before attempting save so the CSV root is
        # still recoverable even if the JSON write blows up.
        self.last_session_root = str(self.session_paths.root)
        try:
            self.session.save(self.session_paths.metadata_json)
        except Exception as e:
            log.warning("Could not save abandoned metadata: %s", e)
        self._close_loggers()
        self.session_paths = None
        self.mode = None

    # ---- per-outcome colour --------------------------------------------------
    # Three tiers so the patient knows roughly how well they did at a
    # glance:
    #   red    = Miss (didn't press the right lane in time)
    #   orange = Late / Early (pressed the right lane but timing off)
    #   green  = Perfect / Great / Good (pressed in time)
    # Same map drives the lane-flash AND the floating popup text so they
    # always agree.
    _ORANGE_CLOSE = (235, 130, 50)

    def _outcome_colour(self, label: str) -> tuple[int, int, int]:
        key = label.lower() if label else ""
        if key == "miss":
            return self.theme.lane_miss      # red
        if key in ("late", "early"):
            return self._ORANGE_CLOSE        # orange (close but off)
        # Everything else (Perfect / Great / Good) is a clean correct press.
        return self.theme.lane_hit           # green

    # ---- score multipliers ---------------------------------------------------
    # Hits should be worth more when the patient is working at a faster pace
    # AND when they're on a streak. Encourages effort + consistency without
    # punishing slower modes (pace_mult clamped at 1.0 for slow tempos).
    def _pace_multiplier(self) -> float:
        bpm = None
        if self.mode is not None and hasattr(self.mode, "adapter"):
            bpm = getattr(self.mode.adapter, "bpm", None)
        elif self.mode is not None:
            bm = getattr(self.mode, "beatmap", None)
            if bm is not None:
                bpm = getattr(bm, "bpm", None)
        if not bpm or bpm <= 0:
            return 1.0
        # Normalised against 60 BPM. At 120 BPM hits are worth 2x.
        return max(1.0, bpm / 60.0)

    def _streak_multiplier(self) -> float:
        # Combo bonus that caps so the score doesn't explode on long runs.
        # +0.1x per streak step, max +0.5x at streak 5+.
        return 1.0 + min(self.hit_streak * 0.1, 0.5)

    def _score_for(self, base_points: int, label: str) -> int:
        # Misses skip the bonus path entirely so we don't accidentally
        # multiply a negative.
        if label == "Miss" or base_points <= 0:
            return base_points
        boost = self._pace_multiplier() * self._streak_multiplier()
        return int(round(base_points * boost))

    # ---- encouragement popups ---------------------------------------------
    _ENCOURAGEMENT = {
        3:  "Nice!",
        5:  "Keep going!",
        8:  "Great job!",
        12: "Smooth!",
        20: "You're flying!",
        30: "Incredible!",
        50: "Unstoppable!",
    }

    def _update_streak(self, was_hit: bool, screen_key: str) -> None:
        # Misses break the streak. The thresholds we already fired for this
        # block stay locked in so we don't keep popping the same message.
        adapter = getattr(self.mode, "adapter", None) if self.mode else None
        if not was_hit:
            self.hit_streak = 0
            self.miss_streak += 1
            # Three misses in a row drops the adaptive engine into recovery
            # (slower BPM + easy lane bias).
            if (adapter is not None
                    and hasattr(adapter, "enter_recovery")
                    and self.miss_streak >= self._recovery_threshold):
                adapter.enter_recovery()
            return
        # Hit: any in-progress recovery is over. Adapter can resume its
        # normal lane weighting + speed up if the patient keeps cruising.
        self.miss_streak = 0
        if adapter is not None and hasattr(adapter, "exit_recovery"):
            adapter.exit_recovery()
        self.hit_streak += 1
        if self.hit_streak not in self._ENCOURAGEMENT:
            return
        if self.hit_streak in self._streak_fired:
            return
        self._streak_fired.add(self.hit_streak)
        text = self._ENCOURAGEMENT[self.hit_streak]
        sc = self._screens.get(screen_key)
        if sc and hasattr(sc, "add_encouragement"):
            sc.add_encouragement(text)

    # ---- mode callbacks ----------------------------------------------------
    def on_stim(self, lane: int, trial_id: int, t_perf: float) -> None:
        # Light up the exact lane that fired. In bilateral mode `lane` is a
        # global index 0..7; each strip's enumerate index matches that.
        # Also arm a timing bar so the patient can see how long they've got
        # to press. Rhythm mode already has its own timing visualisation
        # (falling notes), so we only arm for the gameplay screen.
        # Adaptive mode exposes its own timeout via current_timeout_s so the
        # bar shrinks at the right speed even after the adapter slowed
        # things down.
        if self.mode is not None and hasattr(self.mode, "current_timeout_s"):
            timeout_s = float(self.mode.current_timeout_s)
        else:
            timeout_s = float(self.cfg.get("game.timeout_s", 1.0))
        for key in ("gameplay", "rhythm"):
            sc = self._screens.get(key)
            if sc and hasattr(sc, "lanes"):
                for i, ls in enumerate(sc.lanes):
                    if key == "gameplay":
                        # Classic / adaptive: target lane gets the
                        # active (darker) fill + a shrinking timing bar
                        # so the patient sees what to press.
                        ls.active = (i == lane)
                        if i == lane:
                            ls.arm_timing(t_perf, timeout_s)
                        else:
                            ls.clear_timing()
                    else:
                        # Rhythm: falling notes + target rings already
                        # show the patient what to press, so the lane
                        # never goes to its "active" colour. Boxes only
                        # change colour after a press (green / orange /
                        # red flash). Keep them in their idle pastel
                        # state otherwise.
                        ls.active = False
        if self.cfg.get("motor.enabled", True):
            # Arduino motors are numbered 1..N matching the global lane.
            self.source.send_command(f"STIM:{lane + 1}")
        # Per-lane stim tone (C, E, G, C, repeating on bilateral) plays
        # on every stim for classic + adaptive, matching Aiden's game
        # behaviour. Skipped for rhythm so the cue tone doesn't clash
        # with the music. The hit chime (audio.play_hit) on correct
        # presses still fires from log_trial / log_rhythm_hit.
        if (self.audio is not None
                and self.cfg.get("audio.stim_tone_enabled", True)
                and self.current_block in ("classic", "adaptive")):
            try:
                self.audio.play_stim(lane)
            except Exception:
                pass
        if self.raw_logger:
            self.raw_logger.queue_event("stim", lane=lane, t_perf=t_perf,
                                         detail=f"trial_id={trial_id}",
                                         hand=self.hand_mode)

    def log_trial(self, trial, outcome: TrialResult, now: float) -> None:
        gp = self._screens.get("gameplay")
        if gp and hasattr(gp, "set_message"):
            # Flash colour matches the outcome tier so the screen tells the
            # patient at a glance how well they did. Green = Great, yellow
            # = Good, orange = Late/Early, red = Miss.
            colour = self._outcome_colour(outcome.label)
            gp.flash_lane(trial.lane, colour, 0.4, now)
            gp.set_message(outcome.label, 0.8)
            # Clear the timing bar + deactivate every strip now that the
            # trial is done. The next stim will re-arm the right lane.
            for ls in gp.lanes:
                ls.clear_timing()
                ls.active = False
        # Only chime on a non-Miss press. Doing it from one spot keeps the
        # behaviour consistent across classic / adaptive.
        if outcome.label != "Miss" and self.audio:
            try:
                self.audio.play_hit()
            except Exception:
                pass
        # Capture streak BEFORE _update_streak runs so the trial row
        # records what the patient came IN with, not what they leave
        # with. Used by motor-learning analysis.
        streak_before = self.hit_streak
        # Score uses pace + streak multipliers. Multipliers are computed
        # BEFORE _update_streak so the first hit of a run gets 1.0x and
        # subsequent hits earn the combo bonus.
        gained = self._score_for(outcome.points, outcome.label)
        self.score += gained
        self._last_gained = gained         # used by the HUD popup
        self._update_streak(outcome.label != "Miss", "gameplay")
        if outcome.label == "Miss":
            self.misses += 1
        else:
            self.hits += 1
        # Block-summary aggregates: RT + wrong-press trial count.
        if outcome.rt_ms is not None:
            self._block_rt_sum += float(outcome.rt_ms)
            self._block_rt_count += 1
        if trial.incorrect_presses:
            self._block_wrong_press_trials += 1
        keys = ",".join(str(k + 1) for k in trial.keys_pressed)
        had_incorrect = bool(trial.incorrect_presses)
        first_inc_ms = ""
        first_inc_lane = ""
        if had_incorrect:
            first_inc_ms = f"{(trial.incorrect_presses[0][1] - trial.stim_t_perf) * 1000.0:.1f}"
            # First wrong-finger lane (1-indexed) so the analyst can see
            # exactly which finger fired instead of the target. Adjacent-
            # finger errors (e.g. ring instead of middle) are common in
            # rehab patients and worth analysing separately from
            # "completely wrong hand" errors.
            first_inc_lane = str(trial.incorrect_presses[0][0] + 1)
        if self.trial_logger:
            row = {
                "participant": self.session.participant,
                "hand": self.hand_mode,
                "block": self.current_block,
                "trial": trial.trial_id,
                "lane": trial.lane + 1,
                "time_difference_ms": "" if outcome.rt_ms is None else f"{outcome.rt_ms:.1f}",
                "early_late": outcome.label,
                "points": outcome.points,
                "feedback": outcome.label,
                "error_type": "" if outcome.label != "Miss" else "timeout",
                "keys_pressed": keys,
                "correct_keys": str(trial.lane + 1),
                "num_presses": len(trial.keys_pressed),
                "had_incorrect_press": "TRUE" if had_incorrect else "FALSE",
                "first_incorrect_ms": first_inc_ms,
                "first_incorrect_lane": first_inc_lane,
            }
            row.update(self._trial_context(streak_before))
            self.trial_logger.write(row)
        self._maybe_resave_metadata()

    def _trial_context(self, streak_before: int,
                        song_time_s: float | None = None) -> dict:
        """Per-trial research-context fields. Block-relative time, engine
        BPM if adaptive, hit streak entering the trial, recovery flag,
        song position for rhythm. Empty strings for fields that don't
        apply to the current mode so the CSV stays self-describing."""
        bpm = ""
        in_recovery = ""
        adapter = getattr(self.mode, "adapter", None) if self.mode else None
        if adapter is not None:
            bpm_val = getattr(adapter, "bpm", None)
            if bpm_val is not None:
                bpm = f"{float(bpm_val):.1f}"
                # Track BPM range for the block summary.
                if (self._block_bpm_min is None
                        or float(bpm_val) < self._block_bpm_min):
                    self._block_bpm_min = float(bpm_val)
                if (self._block_bpm_max is None
                        or float(bpm_val) > self._block_bpm_max):
                    self._block_bpm_max = float(bpm_val)
            ir = getattr(adapter, "in_recovery", None)
            if ir is not None:
                in_recovery = "TRUE" if ir else "FALSE"
        # Block-relative time from the perf_counter anchor.
        t0 = getattr(self, "_block_t0", None)
        block_t = f"{time.perf_counter() - t0:.3f}" if t0 else ""
        # Update running block summary aggregates.
        if streak_before > self._block_peak_streak:
            self._block_peak_streak = streak_before
        st = f"{song_time_s:.3f}" if song_time_s is not None else ""
        return {
            "iso_ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "block_t_s": block_t,
            "bpm_at_trial": bpm,
            "streak_at_trial": str(streak_before),
            "in_recovery": in_recovery,
            "song_time_s": st,
        }

    def _maybe_resave_metadata(self) -> None:
        """Periodically re-write metadata.json with up-to-date score /
        hits / misses so a hard crash mid-block leaves something
        useful behind, not just the initial in-progress marker. Runs
        every 10 trials so the IO cost stays negligible."""
        if not self.session_paths:
            return
        n = self.hits + self.misses
        if n <= 0 or n % 10 != 0:
            return
        try:
            self.session.notes = (
                f"block in progress: trial {n}, "
                f"score {self.score}, hits {self.hits}/{n}"
            )
            self.session.save(self.session_paths.metadata_json)
        except Exception as e:
            log.warning("periodic metadata save failed: %s", e)

    def log_rhythm_hit(self, sched_note, offset_ms: float, label: str,
                       points: int, now: float,
                       was_pressed: bool = True) -> None:
        """Log a rhythm trial row.

        `was_pressed` distinguishes the two ways a note can end up as
        a "Miss":
          - True (default): the patient pressed something. The press
            might have landed within the hit/late/early window (a real
            hit or near-miss), or it might have been further than
            miss_ms away (label='Miss' from classify_offset).
          - False: the note scrolled past its miss window without ANY
            press from the patient. This call comes from rhythm.py's
            window-expiry path; keys_pressed must be empty and
            num_presses must be 0 to stay consistent with how classic
            and adaptive log a real no-press miss.
        """
        # Snapshot the streak going INTO this trial before _update_streak
        # mutates it. Used by the trial context for motor-learning analysis.
        streak_before = self.hit_streak
        gained = self._score_for(points, label)
        self.score += gained
        self._last_gained = gained
        # Update streak + maybe spawn an encouragement popup. Rhythm misses
        # come through here too so we can reset the streak in one place.
        self._update_streak(label != "Miss", "rhythm")
        rs = self._screens.get("rhythm")
        if rs and hasattr(rs, "flash_lane"):
            colour = self._outcome_colour(label)
            rs.set_message(label, 0.6)
            # Bolder flash for rhythm: 0.6 s so the green / orange / red
            # has time to register against fast falling notes.
            rs.flash_lane(sched_note.note.lane, colour, 0.6, now)
        # Hit chime only on a real press (Miss = note scrolled past without
        # a press, so we stay silent).
        if label != "Miss" and self.audio:
            try:
                self.audio.play_hit()
            except Exception:
                pass
        if label in ("Miss",):
            self.misses += 1
        else:
            self.hits += 1
        if self.trial_logger:
            # Song position is critical for RAS (Rhythmic Auditory
            # Stimulation) analysis - the researcher needs to see WHEN
            # in the music a hit / miss occurred (e.g. did the patient
            # align better during the chorus than the verse?).
            song_time = None
            mode = self.mode
            if mode is not None:
                st = getattr(mode, "song_time", None)
                if st is not None:
                    try:
                        song_time = float(st)
                    except (TypeError, ValueError):
                        song_time = None
            row = {
                "participant": self.session.participant,
                "hand": self.hand_mode,
                "block": self.current_block,
                "trial": sched_note.index + 1,
                "lane": sched_note.note.lane + 1,
                "time_difference_ms": f"{offset_ms:.1f}",
                "early_late": label,
                "points": points,
                "feedback": label,
                "error_type": "" if label != "Miss" else "missed_note",
                # keys_pressed reflects what the patient ACTUALLY did.
                # On a no-press miss it must stay empty - logging the
                # expected lane would tell a researcher the patient
                # pressed it when they didn't.
                "keys_pressed": (str(sched_note.note.lane + 1)
                                  if was_pressed else ""),
                "correct_keys": str(sched_note.note.lane + 1),
                "num_presses": 1 if was_pressed else 0,
                "had_incorrect_press": "FALSE",
                "first_incorrect_ms": "",
                "first_incorrect_lane": "",
            }
            row.update(self._trial_context(streak_before,
                                            song_time_s=song_time))
            self.trial_logger.write(row)
        self._maybe_resave_metadata()

    def log_rhythm_unmatched(self, lane: int, now: float) -> None:
        # Block-summary counter so the analyst sees wrong-finger
        # activity without scanning raw.csv.
        self._block_rhythm_spurious_presses += 1
        if self.raw_logger:
            self.raw_logger.queue_event("rhythm_spurious_press", lane=lane,
                                         t_perf=now, hand=self.hand_mode)

    @staticmethod
    def _parse_pattern(s: str, max_lanes: int) -> list[int]:
        # Accept comma-separated lane numbers 1..max_lanes. In bilateral mode
        # this means 1..8 are all valid; in unilateral only 1..4. Anything
        # out of range is dropped silently.
        out: list[int] = []
        for tok in s.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                n = int(tok)
            except ValueError:
                continue
            if 1 <= n <= max_lanes:
                out.append(n - 1)
        return out or list(range(max_lanes))
