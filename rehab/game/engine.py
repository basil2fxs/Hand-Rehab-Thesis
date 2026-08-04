"""Pygame main loop. Owns the screen registry, source pump, loggers, and
per-hand FSR detectors (Thread 3 bilateral)."""
from __future__ import annotations

import copy
import logging
import random
import os
import subprocess
import sys
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
        # One calibration profile per hand. Kept here rather than in the
        # config so the two hands never share a set of thresholds.
        self.calibration_profiles: dict = {}
        self.detectors: dict[str, FSRDetector] = {}
        self._build_detectors()

        self.session = Session(
            participant=str(cfg.get("session.participant") or "NA"),
            age=str(cfg.get("session.age") or ""),
            hand=self.hand_mode,
            source_name=getattr(source, "name", "?"),
            # Participant details, set in user_settings.yaml before the
            # session. Blank for an ordinary test run.
            affected_side=str(cfg.get("session.affected_side", "") or ""),
            dominant_hand=str(cfg.get("session.dominant_hand", "") or ""),
            impairment_score=str(cfg.get("session.impairment_score", "") or ""),
            hand_length_mm=str(cfg.get("session.hand_length_mm", "") or ""),
            hand_breadth_mm=str(cfg.get("session.hand_breadth_mm", "") or ""),
            config_snapshot=copy.deepcopy(cfg.data),
        )
        # Fallbacks here MUST match config/default.yaml + ScoreConfig defaults.
        # In particular miss_points / early_penalty default to 0 so the score
        # never goes negative when a custom config omits these keys.
        # Default points (10/6/3/1) deliberately spread wider than the
        # original 3/2/1: a Perfect press is 10x a Late one so the
        # patient can FEEL the difference between a fast and a slow
        # press in the score readout.
        self.score_cfg = ScoreConfig(
            perfect_ms=int(cfg.get("scoring.perfect_ms", 100)),
            perfect_points=int(cfg.get("scoring.perfect_points", 10)),
            great_ms=int(cfg.get("scoring.great_ms", 200)),
            great_points=int(cfg.get("scoring.great_points", 6)),
            good_ms=int(cfg.get("scoring.good_ms", 500)),
            good_points=int(cfg.get("scoring.good_points", 3)),
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
        # Per-lane stats. Initialised here AND in _begin_block so the
        # Results screen can render even if it's somehow shown before
        # the first block fires (the dicts are empty -> charts just
        # render zero bars, no AttributeError).
        self._per_lane_rts: dict[int, list[float]] = {}
        self._per_lane_misses: dict[int, int] = {}
        self._per_lane_wrong: dict[int, int] = {}
        # Per-lane peak-force samples for the block summary's
        # peak_force_mean aggregate. Each entry is in the same unit
        # the trial CSV's peak_force_n column uses (newtons if a
        # calibration constant is set, raw ADC counts otherwise).
        self._per_lane_peak_force: dict[int, list[float]] = {}
        self._per_lane_impulse: dict[int, list[float]] = {}
        # Per-block mean RT + mean peak force, appended at finish_block,
        # used by the fatigue-slope computation in
        # metrics.fatigue_slope. Survives across blocks within a single
        # app session.
        self._across_blocks_mean_rt: list[float] = []
        self._across_blocks_mean_peak: list[float] = []
        # Per-sensor baseline drift samples. Key = (hand, sensor_idx),
        # value = list of (t_minutes_since_block_start, baseline_value)
        # tuples. The mainloop samples this every 30 s; finish_block
        # feeds it to drift_slope.
        self._drift_samples: dict[tuple[str, int], list[tuple[float, float]]] = {}
        # perf_counter timestamp of the last drift sample we took, so
        # the mainloop knows when 30 s has elapsed.
        self._last_drift_sample_t: float | None = None
        # Press timestamps + nearest-beat alignment for rhythm-mode
        # beat-offset stats. Populated in log_rhythm_hit; finish_block
        # feeds it through metrics.beat_offset_stats.
        self._rhythm_press_times_s: list[float] = []
        self._rhythm_beat_times_s: list[float] = []
        self._rhythm_signed_offsets_ms: list[float] = []
        # Pretest / main / aftertest protocol state. `_protocol_steps`
        # is the list parsed from cfg.protocol.blocks at session
        # start; `_protocol_index` is which step we're currently on.
        # `_protocol_active` is True only when finish_block should
        # auto-advance to the next step instead of going to Results.
        # The current phase ("pretest" / "main" / "aftertest" or
        # empty) is what gets written into the trial CSV's `phase`
        # column.
        self._protocol_steps: list[tuple[str, str]] = []
        self._protocol_index: int = 0
        self._protocol_active: bool = False
        self._current_phase: str = ""
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
        # ---- Miss-force metric -------------------------------------------
        # For each trial, track every finger's peak reading above baseline
        # over a fixed window after the go stimulus. On a MISSED trial,
        # log_trial sums those peaks across all fingers into
        # _miss_force_total (and bumps _miss_force_count), so the Results
        # screen can show how much total force the patient was applying
        # across the whole hand when they failed the trial. Units are raw
        # sensor counts (no newton calibration); reads 0 in keyboard mode
        # (no FSR data). Reset per block in _begin_block, alongside misses.
        self._force_window_ms = float(
            self.cfg.get("metrics.miss_force_window_ms", 1000))
        self._force_window_start: float | None = None
        self._force_window_end: float | None = None
        self._force_window_peak: dict[int, float] = {}
        self._miss_force_total: float = 0.0
        self._miss_force_count: int = 0
        # ---- Programmatic loudness variation -----------------------------
        # A fraction of trials, spread evenly across the block, play the
        # cue + feedback slightly louder so the patient doesn't habituate
        # to a constant level. Deterministic (every Nth trial) so the loud
        # count is exact and the spacing uniform. _trials_fired counts
        # stims; the boost is applied via audio.set_trial_gain at on_stim
        # and reset to 1.0 at log_trial.
        self._loud_trial_fraction = float(
            self.cfg.get("audio.loud_trial.fraction", 0.10))
        self._loud_trial_boost = float(
            self.cfg.get("audio.loud_trial.boost", 1.35))
        self._trials_fired = 0
        # Which trial ids played loud, so the trial CSV can record the
        # flag exactly (the boost is a stimulus property and must be
        # controllable in analysis). Also a per-block loud counter for
        # the block summary, the response window of the latest stim
        # (the RT censoring limit, logged per trial), and whether any
        # FSR samples landed in the current force window (distinguishes
        # "no data" from "zero force" in the CSV).
        self._loud_trials_by_id: dict[int, bool] = {}
        self._block_loud_trials = 0
        self._last_stim_timeout_ms: float | None = None
        self._force_window_saw_samples = False
        self._force_window_trial_id: int | None = None
        # Whether the buzzer cue for the current trial reached the
        # hardware (None = motors disabled). Counted per block so the
        # summary can flag a session where cues silently stopped.
        self._last_stim_delivered: bool | None = None
        self._block_stim_failures = 0
        # Cue modality for the current trial, logged per row.
        self._last_cue_mode = "both"
        # Pause bookkeeping for the block summary: how many times the
        # block was paused and the total time spent paused, so an
        # analyst can subtract it from the block duration.
        self._block_pause_count = 0
        self._block_paused_s = 0.0
        # Pending buzzer repeat-pulses as (lane, due_perf_counter).
        self._motor_queue: list[tuple[int, float]] = []

    # ---- bilateral plumbing ------------------------------------------------
    def _build_detectors(self) -> None:
        # FSR threshold defaults, one entry per finger in the order
        # [index, middle, ring, little]. Middle finger uses the higher
        # values (90 / 70 / 400 / 450) because the middle sensor pad
        # in the v1 chassis sits closer to the support arch and reads
        # more baseline pressure than the others; the elevated
        # thresholds keep its press / release detection consistent
        # with the other three. Numbers are in raw ADC counts.
        n = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
        cal_kwargs = dict(
            num_sensors=n,
            baseline_alpha=float(self.cfg.get("fsr.baseline_alpha", 0.02)),
            value_alpha=float(self.cfg.get("fsr.value_alpha", 0.35)),
            # delta thresholds (counts above baseline) to trigger a
            # press (on) and confirm a release (off). Hysteresis: on
            # > off so a finger sitting near the edge can't chatter.
            on_delta=list(self.cfg.get("fsr.on_delta", [45, 90, 45, 45])),
            off_delta=list(self.cfg.get("fsr.off_delta", [35, 70, 35, 35])),
            # Absolute floor / ceiling on the smoothed signal. Belt
            # and braces alongside the delta thresholds: a sensor
            # whose baseline drifted unusually low could otherwise
            # trip on_delta without a real press.
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
        # First N values are the right hand, next N are the left hand
        # (when present). Feed every detector that exists, even if
        # the current hand_mode is unilateral. The Diagnostics screen
        # builds both detectors on entry so the Settings page can
        # always live-read all 8 sensors; this loop honours that
        # without changing the game-time hand_mode contract.
        right_vals = tuple(vals[:n])
        left_vals = (tuple(vals[n:n * 2])
                     if len(vals) >= n * 2 else (0,) * n)
        right_det = self.detectors.get("right")
        left_det = self.detectors.get("left")
        if right_det is not None:
            right_det.feed(t_perf, right_vals)
        if left_det is not None:
            left_det.feed(t_perf, left_vals)
        # Old single-hand fallback: if a hand_mode is set that isn't
        # right or left (e.g. "both") the right/left covers it. The
        # legacy unilateral path only built one detector under the
        # hand_mode key, so this guards for that case too.
        if (self.hand_mode not in ("right", "left", "both")
                and self.hand_mode in self.detectors):
            self.detectors[self.hand_mode].feed(t_perf, right_vals)
        # Miss-force window: while a trial's window is open, update each
        # finger's running peak (reading minus baseline). log_trial sums
        # these across all fingers on a miss. A handful of max() per
        # sample. on_stim opens the window; log_trial closes + records it.
        # getattr-guarded: the Settings screen pumps samples through an
        # engine that may not have run a block yet, and test fixtures
        # build engines via __new__.
        start = getattr(self, "_force_window_start", None)
        end = getattr(self, "_force_window_end", None)
        if (start is not None and end is not None
                and start <= t_perf <= end):
            self._track_force_peaks(right_det, right_vals,
                                     left_det, left_vals, n)

    # ---- miss-force + loudness helpers -------------------------------------
    def _track_force_peaks(self, right_det, right_vals,
                            left_det, left_vals, n: int) -> None:
        """Update the per-finger peak (reading minus baseline) for the
        fingers in play this hand_mode. Lane numbering matches the game:
        right hand 0..n-1, left hand 0..n-1 unilateral or n..2n-1 in
        bilateral. Negative deltas clamp to 0 (a finger sitting below its
        baseline isn't pressing)."""
        # Mark that real FSR data reached this window, so the trial CSV
        # can tell "no data" (keyboard mode / dropout -> empty cell)
        # apart from "data flowed but no finger rose" (-> 0.000).
        self._force_window_saw_samples = True
        peak = self._force_window_peak

        def _add(det, svals, lane_base):
            if det is None:
                return
            for i in range(n):
                base = det.baseline_value(i)
                base = 0.0 if base is None else float(base)
                delta = float(svals[i]) - base
                if delta < 0.0:
                    delta = 0.0
                lane = lane_base + i
                if delta > peak.get(lane, 0.0):
                    peak[lane] = delta

        if self.hand_mode == "both":
            _add(right_det, right_vals, 0)
            _add(left_det, left_vals, n)
        elif self.hand_mode == "left":
            _add(left_det, left_vals, 0)
        else:  # "right" or a legacy single-hand mode
            _add(right_det, right_vals, 0)

    def _open_force_window(self, t_perf: float,
                            trial_id: int | None = None) -> None:
        """Start a fresh miss-force window at the go stimulus. Clears the
        previous trial's peaks and arms _feed_detectors to accumulate for
        _force_window_ms milliseconds. `trial_id` tags the window so the
        rhythm path (where notes can overlap in flight) only banks a miss
        against the window that actually belongs to that note."""
        self._force_window_start = t_perf
        self._force_window_end = t_perf + self._force_window_ms / 1000.0
        self._force_window_peak = {}
        self._force_window_saw_samples = False
        self._force_window_trial_id = trial_id

    def _close_force_window(self, was_miss: bool
                             ) -> tuple[float | None, dict[int, float]]:
        """Finish the current trial's window. On a miss, add the summed
        per-finger peak to the running total so the Results screen can
        report it. Returns (sum, per-lane peaks) for the trial CSV row;
        sum is None when no FSR samples reached the window (keyboard
        mode), so the CSV cell stays empty rather than lying with a 0.
        Then disarms the window until the next stim."""
        peaks = dict(self._force_window_peak)
        saw = self._force_window_saw_samples
        window_sum: float | None = sum(peaks.values()) if saw else None
        if was_miss and self._force_window_start is not None:
            self._miss_force_total += sum(peaks.values())
            self._miss_force_count += 1
        self._force_window_start = None
        self._force_window_end = None
        self._force_window_peak = {}
        self._force_window_saw_samples = False
        self._force_window_trial_id = None
        return window_sum, peaks

    @staticmethod
    def _format_force_window(window_sum: float | None,
                              peaks: dict[int, float]) -> tuple[str, str]:
        """CSV cells for the force-window columns: ("", "") when no data
        reached the window, else the sum plus a "lane:peak;..." breakdown
        (1-indexed lanes, only fingers that rose above baseline)."""
        if window_sum is None:
            return "", ""
        peaks_str = ";".join(
            f"{lane + 1}:{val:.3f}"
            for lane, val in sorted(peaks.items()) if val > 0.0)
        return f"{window_sum:.3f}", peaks_str

    def _ensure_metric_state(self) -> None:
        """Backfill miss-force + loud-trial state for engines built via
        __new__ in tests (which skip __init__). Mirrors the hasattr guards
        the per-lane logging already uses in log_trial."""
        if not hasattr(self, "_force_window_ms"):
            self._force_window_ms = 1000.0
        if not hasattr(self, "_force_window_start"):
            self._force_window_start = None
        if not hasattr(self, "_force_window_end"):
            self._force_window_end = None
        if not hasattr(self, "_force_window_peak"):
            self._force_window_peak = {}
        if not hasattr(self, "_miss_force_total"):
            self._miss_force_total = 0.0
        if not hasattr(self, "_miss_force_count"):
            self._miss_force_count = 0
        if not hasattr(self, "_loud_trial_fraction"):
            self._loud_trial_fraction = 0.0
        if not hasattr(self, "_loud_trial_boost"):
            self._loud_trial_boost = 1.0
        if not hasattr(self, "_trials_fired"):
            self._trials_fired = 0
        if not hasattr(self, "_loud_trials_by_id"):
            self._loud_trials_by_id = {}
        if not hasattr(self, "_block_loud_trials"):
            self._block_loud_trials = 0
        if not hasattr(self, "_last_stim_timeout_ms"):
            self._last_stim_timeout_ms = None
        if not hasattr(self, "_force_window_saw_samples"):
            self._force_window_saw_samples = False
        if not hasattr(self, "_force_window_trial_id"):
            self._force_window_trial_id = None
        if not hasattr(self, "_last_stim_delivered"):
            self._last_stim_delivered = None
        if not hasattr(self, "_block_stim_failures"):
            self._block_stim_failures = 0
        if not hasattr(self, "_last_cue_mode"):
            self._last_cue_mode = "both"
        if not hasattr(self, "_block_pause_count"):
            self._block_pause_count = 0
        if not hasattr(self, "_block_paused_s"):
            self._block_paused_s = 0.0
        if not hasattr(self, "_motor_queue"):
            self._motor_queue = []

    def _is_loud_trial(self, trial_number: int) -> bool:
        """True if this 1-indexed trial should play louder. Loud trials
        are spread evenly at the configured fraction (0.10 = about 1 in
        10). Deterministic so the loud count is exact and the spacing
        uniform rather than clustered: trial n is loud when the running
        count of loud trials (floor(n x fraction)) ticks up from n-1."""
        frac = self._loud_trial_fraction
        if frac <= 0.0 or trial_number < 1:
            return False
        return int(trial_number * frac) > int((trial_number - 1) * frac)

    def _all_rts(self) -> list[float]:
        """Flatten the per-lane reaction-time lists into one list across
        all fingers. getattr-guarded so a __new__-built engine in tests
        doesn't blow up. Used by the Results screen for the overall
        average + best-press cards."""
        out: list[float] = []
        for vals in (getattr(self, "_per_lane_rts", {}) or {}).values():
            out.extend(vals)
        return out

    def overall_mean_rt(self) -> float:
        """Mean reaction time (ms) across every logged press this block,
        or 0.0 if none. In rhythm mode the per-lane lists hold signed
        beat offsets, so the absolute value is used there (mean distance
        off the beat, not a net early/late bias that cancels out)."""
        rts = self._all_rts()
        if not rts:
            return 0.0
        if getattr(self, "current_block", None) == "rhythm":
            rts = [abs(x) for x in rts]
        return sum(rts) / len(rts)

    def overall_best_rt(self) -> float:
        """The patient's best single press this block (ms), or 0.0 if
        none. In a cadence mode that's the fastest reaction; in rhythm
        it's the press landing tightest to the beat (smallest absolute
        offset). Shown game-style as a personal best."""
        rts = self._all_rts()
        if not rts:
            return 0.0
        if getattr(self, "current_block", None) == "rhythm":
            return min(abs(x) for x in rts)
        return min(rts)

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
        # Boot fullscreen by default (the app runs as a kiosk-style
        # clinical tool). F10 toggles to a windowed view at runtime.
        self._fullscreen = bool(self.cfg.get("ui.fullscreen", True))
        screen = self._open_display(self._fullscreen)
        if screen is None:
            # Most common cause: no display available (headless / SSH session
            # without X). _open_display already logged the detail.
            pygame.quit()
            return 4
        self._screen = screen
        pygame.display.set_caption("Finger Rehab")
        # Window / dock icon. resolve_path routes into the PyInstaller
        # bundle when frozen. Purely cosmetic, so any failure (missing
        # file, headless SDL) is ignored.
        try:
            icon_path = self.cfg.resolve_path("assets/icons/app_icon_256.png")
            if Path(icon_path).exists():
                pygame.display.set_icon(pygame.image.load(str(icon_path)))
        except Exception as e:
            log.debug("window icon skipped: %s", e)
        clock = pygame.time.Clock()
        # Initialise self.audio BEFORE any startup step that could raise.
        # Without this, if _build_screens / show_title / source.start raised
        # below, the finally block's `if self.audio:` check would
        # AttributeError because self.audio was never assigned, masking the
        # original startup failure with a confusing secondary error.
        self.audio = None
        try:
            # _build_screens, show_title, source.start and _build_audio used
            # to live outside this try/finally. If any of them raised (e.g.
            # a missing font during ScreenInit, a port that vanished between
            # discover and open, a borked audio device), pygame would stay
            # initialised, the source could be left half-started, and we'd
            # leak handles back to the user's OS. Putting them inside the
            # try means the finally always tears everything back down.
            self._screens = self._build_screens()
            # Reuse the calibration taken last time so the device
            # behaves the same across restarts.
            try:
                self.load_saved_calibration()
            except Exception as e:
                log.warning("could not load saved calibration: %s", e)
            self.show_title()
            self.source.start()
            self.audio = self._build_audio()
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
                # Buzzer cue repeat-pulses. Cheap no-op when nothing is
                # queued; runs outside the paused branch so a cue can't
                # keep firing while the block is frozen.
                self._drain_motor_queue()

                # Global events (Esc, P, F2, QUIT) always go through. Screen-
                # specific events (button clicks, key presses for lanes) are
                # gated on paused so the pause overlay truly blocks input.
                for e in pygame.event.get():
                    # The window may be larger than the logical surface
                    # (supersampling), so rewrite mouse positions into
                    # logical space before any screen hit-tests them.
                    if e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                                  pygame.MOUSEBUTTONUP) and hasattr(e, "pos"):
                        e.dict["pos"] = self._to_logical(e.pos)
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
                    # Draw always so the pause overlay shows. Read the
                    # surface off self each frame so an F10 fullscreen
                    # toggle (which re-opens the display) takes effect
                    # without a stale surface reference.
                    self.screen_obj.draw(self._screen)
                self._draw_hud(self._screen, clock)
                # Scale the logical surface up onto the window and flip.
                self._present()
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
        self.stop_all_motors()
        # Record the pause. Without it a long break mid-block is
        # invisible in the data: block duration looks inflated and
        # reaction times either side are not comparable.
        if self.raw_logger:
            self.raw_logger.queue_event("pause", detail=self.current_block,
                                         hand=self.hand_mode)
        self._block_pause_count += 1
        log.info("Block paused")

    def _resume_now(self) -> None:
        if not self.paused or self._pause_started_at is None:
            self.paused = False
            return
        pause_dur = time.perf_counter() - self._pause_started_at
        if self.raw_logger:
            self.raw_logger.queue_event(
                "resume", detail=f"paused_s={pause_dur:.3f}",
                hand=self.hand_mode)
        self._block_paused_s += pause_dur
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
        from ..ui.calibration_screen import CalibrationScreen
        return {
            "title": TitleScreen(self),
            "mode_select": ModeSelectScreen(self),
            "setup": SetupScreen(self),
            "rhythm_setup": RhythmSetupScreen(self),
            "gameplay": GameplayScreen(self),
            "rhythm": RhythmScreen(self),
            "results": ResultsScreen(self),
            "diagnostics": DiagnosticsScreen(self),
            "calibration": CalibrationScreen(self),
        }

    def _build_audio(self) -> AudioEngine | None:
        if not self.cfg.get("audio.enabled", True):
            return None
        a = AudioEngine(
            master_volume=float(self.cfg.get("audio.master_volume", 0.8)),
            cue_volume=float(self.cfg.get("audio.cue_volume", 1.0)),
            feedback_volume=float(self.cfg.get("audio.feedback_volume", 1.0)),
        )
        a.init()
        return a

    # Supersample factor for the on-screen window. The whole UI is drawn
    # to a fixed 1280x800 logical surface, then scaled up to the window
    # for display. On a Retina/HiDPI panel a 1280-wide image left to the
    # OS gets stretched with a cheap blur, which is what made text and
    # edges look soft and jagged. Drawing the window itself at SS x the
    # logical size and doing one high-quality smoothscale per frame gives
    # native-sharp pixels instead. Mouse events are translated back to
    # logical coordinates in _to_logical(), so no layout or hit-testing
    # math changes. 2 -> a 2560x1600 backing (crisp on any modern panel);
    # 1 disables supersampling for a low-power host.
    SUPERSAMPLE = 2

    def _open_display(self, fullscreen: bool):
        """Open the on-screen window and the off-screen logical surface.

        The window is opened at the highest sensible physical resolution:
        the monitor's native size in fullscreen, or SUPERSAMPLE x the
        logical size in windowed mode. All screens still draw to a fixed
        1280x800 logical surface (self._render_surf); _present() scales
        that surface onto the window once per frame.

        Returns the *logical* surface for screens to draw to, or None if
        the window cannot be opened.
        """
        lw, lh = self.layout.width, self.layout.height
        ss = max(1, int(self.SUPERSAMPLE))
        # One render path for both modes: open the window as large as the
        # mode allows, draw the UI to a fixed 1280x800 logical surface, and
        # smoothscale that onto the window each frame in _present(). The
        # bigger the window's framebuffer, the sharper the result, so the
        # windowed window is opened at SS x the logical size (a true high-
        # density backing) and fullscreen fills the monitor.
        if fullscreen:
            win_size = (0, 0)              # native desktop size
            flags = pygame.FULLSCREEN
        else:
            win_size = (lw * ss, lh * ss)  # e.g. 2560x1600 backing
            flags = 0
        try:
            window = pygame.display.set_mode(win_size, flags, vsync=1)
        except pygame.error as e:
            log.warning("set_mode %s failed (%s); retrying plain at %dx%d",
                         "fullscreen" if fullscreen else "windowed",
                         e, lw, lh)
            try:
                window = pygame.display.set_mode(
                    (lw, lh), pygame.FULLSCREEN if fullscreen else 0)
            except pygame.error as e2:
                log.error("Could not open the game window: %s", e2)
                return None
        self._window = window
        # Off-screen surface every screen draws into, always logical size.
        self._render_surf = pygame.Surface((lw, lh)).convert()
        return self._render_surf

    def _present(self) -> None:
        """Scale the logical render surface onto the window and flip.

        smoothscale gives a clean bilinear upscale, far sharper than the
        OS stretching a 1x surface across a Retina backing. When the
        window already matches the logical size (SUPERSAMPLE 1, plain
        windowed) it is a cheap straight blit."""
        win = self._window
        if win.get_size() == self._render_surf.get_size():
            win.blit(self._render_surf, (0, 0))
        else:
            pygame.transform.smoothscale(self._render_surf,
                                          win.get_size(), win)
        pygame.display.flip()

    def _to_logical(self, pos: tuple[int, int]) -> tuple[int, int]:
        """Map a window-space mouse position back to logical coordinates
        so button hit-testing keeps working under supersampling.

        Returns the position unchanged if the window and logical surfaces
        have not been opened yet (e.g. headless tests that build screens
        and feed synthetic events without a real display)."""
        window = getattr(self, "_window", None)
        render = getattr(self, "_render_surf", None)
        if window is None or render is None:
            return pos
        win_w, win_h = window.get_size()
        lw, lh = render.get_size()
        if (win_w, win_h) == (lw, lh):
            return pos
        return (int(pos[0] * lw / win_w), int(pos[1] * lh / win_h))

    def _toggle_fullscreen(self) -> None:
        """F10: flip between fullscreen and a windowed view. The logical
        render size stays 1280x800 either way (SCALED upscales), so the
        layout never shifts. On failure the flag is rolled back so the
        stored state matches what's actually on screen."""
        target = not getattr(self, "_fullscreen", True)
        surf = self._open_display(target)
        if surf is not None:
            self._screen = surf
            self._fullscreen = target
            log.info("Display switched to %s",
                      "fullscreen" if target else "windowed")
        else:
            log.warning("Fullscreen toggle to %s failed; staying as-is",
                         "fullscreen" if target else "windowed")

    def _handle_global_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.QUIT:
            self._abandon_if_in_block()
            self.running = False
        elif e.type == pygame.KEYDOWN:
            if e.key == pygame.K_ESCAPE:
                self._handle_escape()
            elif e.key == pygame.K_F2:
                self._show_fps = not self._show_fps
            elif e.key == pygame.K_F10:
                self._toggle_fullscreen()
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
            # Clear the participant name AND age so the title screen
            # comes up blank for the next patient. Without clearing
            # age too, a researcher running back-to-back patients
            # could accidentally tag patient B with patient A's age.
            self.session.participant = "NA"
            self.session.age = ""
            self.cfg.data.setdefault("session", {})["participant"] = None
            self.cfg.data["session"]["age"] = None
            self.show_title()
            return
        # Diagnostics returns straight to title without abandoning any
        # block (none could be in-flight on this screen).
        if self.screen_obj in (self._screens.get("diagnostics"),
                               self._screens.get("calibration")):
            self.stop_all_motors()
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
        # Per-block drift sampler. Cheap enough to call every frame -
        # the interval check inside short-circuits when 30 s hasn't
        # elapsed yet. Sits at the top of pump so even a frame with
        # no new FSR samples still ticks the timer.
        if self.current_block != "(none)":
            self._maybe_sample_drift()
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
            # "diagnostics" is included so the Settings screen shows a
            # live readout when the hardware is plugged in. This pump
            # drains the sample queue every frame, so a screen that
            # tried to call get_sample() itself would almost always get
            # nothing: the values have to be pushed from here.
            # Calibration needs every sample, not the once-per-frame
            # slice the lane strips get: it averages a whole step.
            cal_sc = self._screens.get("calibration")
            if cal_sc is not None and self.screen_obj is cal_sc:
                cal_sc.on_sample(s.t_perf, s.values)
            for key in ("gameplay", "rhythm", "diagnostics"):
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
                                # Drive the lane-strip press visual
                                # from the detector's live pressed[]
                                # state. set_pressed latches a short
                                # minimum-visible window so a quick
                                # press-release still flashes the tile
                                # rather than blinking for a single
                                # frame.
                                ls.set_pressed(bool(det.pressed[local]),
                                                s.t_perf)

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

    def _pattern_is_configured(self) -> bool:
        """Whether game.pattern was actually set by someone, as opposed to
        falling back to the built-in default."""
        try:
            game = (self.cfg.data or {}).get("game") or {}
            return bool(game.get("pattern"))
        except (AttributeError, TypeError):
            return False

    def lanes_by_hand(self) -> dict:
        """Which lane numbers belong to which hand. Lanes are global, so in
        bilateral mode the right hand owns 0..3 and the left owns 4..7."""
        n = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
        if self.hand_mode == "both":
            return {"right": list(range(n)), "left": list(range(n, 2 * n))}
        return {self.hand_mode: list(range(n))}

    def build_balanced_sequence(self, n_trials: int,
                                lanes: list[int] | None = None) -> list[int]:
        """A trial order that cues every finger the same number of times,
        and in bilateral mode every hand too, without being predictable.

        Every cross-finger comparison in the analysis assumes the fingers got
        a comparable number of attempts. A finger cued half as often has an
        average built from half the samples, so the difference between
        fingers reports how often each was asked rather than anything about
        the hand.

        Returns an empty list when balancing is switched off, which leaves
        the caller on its previous behaviour.
        """
        if not bool(self.cfg.get("game.balance_targets", True)):
            return []
        from .scheduling import BalancedScheduler, PairedBalancedScheduler
        by_hand = self.lanes_by_hand()
        if lanes:
            # Keep only the requested lanes, grouped by the hand they belong
            # to, so a narrowed pattern still balances hands when it spans
            # both.
            want = set(lanes)
            by_hand = {h: [ln for ln in v if ln in want]
                       for h, v in by_hand.items()}
            by_hand = {h: v for h, v in by_hand.items() if v}
            if not by_hand:
                return []
        rng = random.Random()
        if len(by_hand) > 1:
            sched = PairedBalancedScheduler(by_hand, rng)
            return [sched.next()[1] for _ in range(max(0, n_trials))]
        only = next(iter(by_hand.values()))
        return BalancedScheduler(only, rng).sequence(max(0, n_trials))

    def show_calibration(self) -> None:
        """Open the guided calibration. Reachable from the menu before a
        session so a therapist never has to touch a config file."""
        self._ensure_both_detectors()
        self.reapply_calibrations()
        cs = self._screens.get("calibration")
        if cs is None:
            return
        # The screen is built once and reused, so without this the next
        # participant opens straight onto the previous participant's review
        # table, where the only buttons are Done and Back and there is no way
        # to start a fresh measurement.
        if hasattr(cs, "reset"):
            cs.reset()
        self.screen_obj = cs

    def load_saved_calibration(self) -> bool:
        """Pick up the calibration taken last time, if there is one, so
        the device behaves the same across restarts without anyone
        having to redo it."""
        from ..hardware.calibration_profile import CalibrationProfile
        loaded = False
        for hand in ("right", "left"):
            for name in (f"current_{hand}.json", "current.json"):
                try:
                    path = self.cfg.resolve_path(f"config/calibration/{name}")
                except Exception:
                    continue
                prof = CalibrationProfile.load(path)
                if prof is None:
                    continue
                # current.json is the older single-file layout; only take it
                # for the hand it says it was measured on.
                if name == "current.json" and \
                        (getattr(prof, "hand", "right") or "right") != hand:
                    continue
                ok, problems = prof.usable()
                if not ok:
                    log.warning("saved %s calibration looks wrong, ignoring "
                                "it: %s", hand, "; ".join(problems))
                    break
                self.apply_calibration(prof)
                log.info("loaded %s calibration taken %s", hand,
                         prof.created_at)
                loaded = True
                break
        return loaded

    def apply_calibration(self, profile) -> None:
        """Take a freshly measured profile into use.

        Two things happen. The detectors get the new thresholds, and
        their baselines are primed to the measured resting level so
        there is no settling window at the start of a block where a
        hand simply resting on the pads could trip the trigger. That
        priming is what lets the thresholds be set from the
        resting-to-press gap instead of from absolute counts, which is
        what keeps a heavily preloaded pad (the pinky on this build)
        usable by a weak finger.

        The profile is also held so every session recorded from now on
        writes down which calibration it ran under.
        """
        self.calibration_profile = profile
        if not hasattr(self, "calibration_profiles"):
            self.calibration_profiles = {}
        on_d = profile.on_delta()
        off_d = profile.off_delta()
        # A profile describes ONE hand's pads. Writing it onto both
        # detectors would push the calibrated hand's thresholds onto the
        # other hand's differently-placed sensors, where the same numbers
        # mean a different fraction of that hand's travel. Each hand is
        # calibrated in its own run.
        hand = getattr(profile, "hand", "right") or "right"
        det = (self.detectors or {}).get(hand)
        targets = [det] if det is not None else list(
            (self.detectors or {}).values())
        for det in targets:
            cal = getattr(det, "cal", None)
            if cal is None:
                continue
            n = cal.num_sensors
            for i in range(min(n, len(on_d))):
                cal.on_delta[i] = on_d[i]
                cal.off_delta[i] = off_d[i]
        # Deliberately NOT written into cfg.fsr. Detectors get rebuilt from
        # the config (mirror mode forces hand_mode to "both" and rebuilds
        # both sides), so writing one hand's thresholds there would hand them
        # to the other hand as well. On a bilateral rig that means the
        # affected hand runs on the unaffected hand's numbers, which it
        # cannot reach, and every one of its trials is scored a miss.
        #
        # Instead each hand's profile is kept here and re-applied after any
        # rebuild, so the two hands stay independent.
        self.calibration_profiles[hand] = profile
        self._prime_baselines()

    def _prime_baselines(self) -> None:
        """Seed each detector's baseline from the calibrated resting level.

        This is what lets thresholds be set from the resting-to-press gap
        instead of from absolute counts, because there is no window where a
        hand simply resting on the pads sits above an untared baseline.
        Called after apply_calibration and again after every block-start
        reset, since reset() clears the baseline.
        """
        for hand, prof in (getattr(self, "calibration_profiles", None) or {}).items():
            if prof is None or not getattr(prof, "resting", None):
                continue
            det = (self.detectors or {}).get(hand)
            if det is None:
                continue
            try:
                n = det.cal.num_sensors
                for i in range(min(n, len(prof.resting))):
                    det.baseline[i] = float(prof.resting[i])
            except (AttributeError, TypeError, ValueError) as e:
                log.warning("could not prime baselines for %s: %s", hand, e)

    def reapply_calibrations(self) -> None:
        """Push every stored per-hand profile back onto its detector.

        Detectors are rebuilt from the config in several places, and a
        rebuilt detector comes back with the config's default thresholds.
        Calling this after any rebuild keeps each hand on the calibration
        that was actually measured for it, without the two hands sharing a
        single set of numbers through the config.
        """
        for prof in list((getattr(self, "calibration_profiles", None) or {}).values()):
            if prof is not None:
                self.apply_calibration(prof)

    def show_diagnostics(self) -> None:
        # Settings always shows 8 sensors, so make sure both
        # detectors exist even when the game-time hand_mode is
        # unilateral. _feed_detectors picks up the new detector on
        # the next sample without any further wiring. Done BEFORE
        # the screen-existence check so a partially-built engine
        # (in some test paths) still gets the detectors created.
        self._ensure_both_detectors()
        ds = self._screens.get("diagnostics")
        if ds is None:
            return
        # Rebuild lanes so they match the currently configured hand
        # mode (which the user might have changed since the screens
        # were first built).
        if hasattr(ds, "rebuild_lanes"):
            ds.rebuild_lanes()
        self.screen_obj = ds

    def _ensure_both_detectors(self) -> None:
        """Build whichever of the right / left FSRDetectors is
        missing. Used by show_diagnostics so the Settings screen can
        live-read all 8 sensors regardless of the active session's
        hand_mode. Cheap to call repeatedly; existing detectors are
        left as they are so any in-flight baseline state isn't
        clobbered."""
        if not hasattr(self, "detectors") or self.detectors is None:
            self.detectors = {}
        n = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
        cal_kwargs = dict(
            num_sensors=n,
            baseline_alpha=float(self.cfg.get("fsr.baseline_alpha", 0.02)),
            value_alpha=float(self.cfg.get("fsr.value_alpha", 0.35)),
            on_delta=list(self.cfg.get("fsr.on_delta",
                                          [45, 90, 45, 45])),
            off_delta=list(self.cfg.get("fsr.off_delta",
                                           [35, 70, 35, 35])),
            abs_on_min=list(self.cfg.get("fsr.abs_on_min",
                                            [320, 400, 320, 320])),
            abs_off_max=list(self.cfg.get("fsr.abs_off_max",
                                             [350, 450, 350, 350])),
            debounce_ms=int(self.cfg.get("fsr.debounce_ms", 100)),
        )
        for hand in ("right", "left"):
            if hand in self.detectors:
                continue
            det = FSRDetector(Calibration(**cal_kwargs), hand=hand)
            det.on_press = self._on_press
            det.on_release = self._on_release
            self.detectors[hand] = det

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
    def _test_mode_trials(self) -> int | None:
        """Return the trial cap when Test Mode is on, else None.
        Test Mode is a supervisor-demo shortcut: a normal classic / adaptive
        block is 40-48 trials (~2 minutes of play), which is too long to
        walk through during a 10-minute meeting. With Test Mode on every
        mode is capped at ~6 trials so the full pipeline (mode select ->
        setup -> gameplay -> results screen) fits a 60-second demo.
        Researcher mode (Test Mode OFF) keeps the normal counts so a real
        session still produces statistically useful data.
        """
        if bool(self.cfg.get("game.test_mode_enabled", False)):
            return max(2, int(self.cfg.get("game.test_mode_trials", 6)))
        return None

    def begin_classic_block(self) -> None:
        from .modes.classic import ClassicMode
        pattern = self._parse_pattern(
            self.cfg.get("game.pattern", "2,1,3,2,4,1"),
            self.total_lanes,
        )
        repeat_count = int(self.cfg.get("game.repeat_count", 8))
        # Test Mode caps repeat_count so the total trials (= repeats x
        # pattern length) lands at roughly the demo target. Ceil so a
        # demo never runs SHORTER than asked - a researcher who set 6
        # trials and got 4 would think the build was broken.
        cap = self._test_mode_trials()
        if cap is not None and pattern:
            from math import ceil
            repeat_count = max(1, ceil(cap / len(pattern)))
        # Restrict to the pattern's fingers ONLY when someone actually set
        # game.pattern. A narrowed pattern is a deliberate drill (index and
        # middle only, say) and balancing over every lane would quietly put
        # back the fingers it excluded.
        #
        # The fallback "2,1,3,2,4,1" is not a choice, it is a leftover from
        # the old fixed-order code. Honouring it would name lanes 1 to 4
        # only, which in bilateral mode is the right hand, and the left hand
        # would never be cued: exactly the bug the balancing exists to fix.
        explicit = self._pattern_is_configured()
        sequence = self.build_balanced_sequence(
            len(pattern) * repeat_count,
            lanes=pattern if explicit else None)
        self.mode = ClassicMode(
            engine=self,
            pattern=pattern,
            repeat_count=repeat_count,
            sequence=sequence,
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
        # Test Mode overrides total_trials to the demo cap. block_size
        # is left alone (4 trials per adapter re-tune is fine even in a
        # short demo - shows the BPM adjusting at least once).
        total_trials = int(self.cfg.get("game.total_trials", 40))
        cap = self._test_mode_trials()
        if cap is not None:
            total_trials = cap
        self.mode = AdaptiveMode(
            engine=self,
            num_lanes=self.total_lanes,
            # Floor under every finger so the weighting cannot starve a
            # strong one down to a handful of trials. Weak fingers still get
            # the most practice; every finger still ends up analysable.
            min_finger_share=float(
                self.cfg.get("adaptive.min_finger_share", 0.15)),
            total_trials=total_trials,
            block_size=int(self.cfg.get("adaptive.block_size", 4)),
            score_cfg=self.score_cfg,
            timeout_s=float(self.cfg.get("game.timeout_s", 1.0)),
            early_window_s=float(self.cfg.get("game.early_window_s", 0.1)),
            # Default mirrors config/default.yaml: 30 BPM = 2 s
            # between stimuli, a comfortable opener for impaired
            # patients. The adapter will speed up if the hit rate
            # holds above target_high (0.80).
            start_bpm=float(self.cfg.get("adaptive.start_bpm", 30)),
            adaptive_cfg=ac,
        )
        self._begin_block("adaptive")
        self.screen_obj = self._screens["gameplay"]

    def begin_mirror_block(self) -> None:
        """Mirror therapy mode. Both hands' same finger fire at once;
        the patient has to land both presses in the timing window
        for the trial to count. Forces hand_mode="both" because
        single-hand mirror training doesn't exist.

        Cadence + finger order are driven by the challenge-point
        adaptive engine just like AdaptiveMode: weakness-weighted
        random picks, BPM speeds up or down based on hit rate +
        press quality + RT utilisation. Starts slower than the
        unimanual modes because synchronised bilateral movement is
        harder to sustain.
        """
        from .modes.mirror import MirrorMode
        from ..analytics.adaptive import AdaptiveConfig
        # Force bilateral. If the patient came in with a unilateral
        # config we override and rebuild the detectors + lane strips
        # so the gameplay screen shows all 8 tiles.
        if self.hand_mode != "both":
            self.hand_mode = "both"
            self.cfg.data.setdefault("bilateral", {})["hand"] = "both"
            self.session.hand = "both"
            self._build_detectors()
            for key in ("gameplay", "rhythm"):
                sc = self._screens.get(key)
                if sc and hasattr(sc, "rebuild_lanes"):
                    sc.rebuild_lanes()
        # Pattern reuses game.pattern (a list of within-hand finger
        # indices). For mirror this acts as the eligible-finger pool
        # the adapter draws from. A therapist who narrows the pattern
        # to [0, 1] gets random index-or-middle trials instead of all
        # four fingers. max_lanes=4 because mirror addresses fingers
        # on a single hand (the same finger fires on BOTH hands), not
        # the full bilateral 0..7 lane space.
        finger_pattern = self._parse_pattern(
            self.cfg.get("game.pattern", "1,2,3,4"),
            max_lanes=4,
        )
        if not finger_pattern:
            finger_pattern = [0, 1, 2, 3]
        repeat_count = int(self.cfg.get("game.repeat_count", 8))
        cap = self._test_mode_trials()
        if cap is not None and finger_pattern:
            from math import ceil
            repeat_count = max(1, ceil(cap / len(finger_pattern)))
        # Mirror gets its own adaptive config so a therapist can tune
        # the bilateral-coordination pace independently of the unimanual
        # adaptive mode. Falls back to the regular adaptive.* keys, so
        # a config that doesn't set mirror.* still works.
        ac = AdaptiveConfig(
            target_low=float(self.cfg.get("adaptive.target_low", 0.65)),
            target_high=float(self.cfg.get("adaptive.target_high", 0.80)),
            bpm_min=float(self.cfg.get("adaptive.bpm_min", 10.0)),
            bpm_max=float(self.cfg.get("adaptive.bpm_max", 140.0)),
            bpm_step=float(self.cfg.get("adaptive.bpm_step", 10.0)),
            weakness_bias=float(self.cfg.get("adaptive.weakness_bias", 2.5)),
            min_trials=int(self.cfg.get("adaptive.min_trials", 2)),
        )
        # Mirror starts slower than adaptive (24 BPM = 2.5 s gap
        # vs adaptive's 30 BPM = 2 s) because the patient has to
        # coordinate both hands on every trial. Adapter speeds up
        # once the patient is landing the bimanual pair reliably.
        start_bpm = float(self.cfg.get("mirror.start_bpm", 24.0))
        # Fallback timing knobs for the rare case where the adapter
        # path can't be used (math safety net only - the live mode
        # always reads from the adapter).
        trigger = float(self.cfg.get("game.trigger_interval_s", 1.2)) + 0.3
        timeout = float(self.cfg.get("game.timeout_s", 1.0)) + 0.3
        self.mode = MirrorMode(
            engine=self,
            min_finger_share=float(
                self.cfg.get("adaptive.min_finger_share", 0.15)),
            pattern=finger_pattern,
            repeat_count=repeat_count,
            trigger_interval_s=trigger,
            timeout_s=timeout,
            early_window_s=float(self.cfg.get("game.early_window_s", 0.1)),
            score_cfg=self.score_cfg,
            adaptive_cfg=ac,
            start_bpm=start_bpm,
        )
        self._begin_block("mirror")
        self.screen_obj = self._screens["gameplay"]

    def begin_rhythm_block(self, beatmap) -> None:
        from .modes.rhythm import RhythmMode
        rw = RhythmWindows(
            perfect_ms=float(self.cfg.get("rhythm.perfect_ms", 50)),
            great_ms=float(self.cfg.get("rhythm.great_ms", 100)),
            good_ms=float(self.cfg.get("rhythm.good_ms", 175)),
            miss_ms=float(self.cfg.get("rhythm.miss_ms", 300)),
        )
        # Test Mode trims the beatmap to its first N notes so the song
        # demo finishes quickly. The audio still plays the full track,
        # but the rhythm trial loop ends after the last beat in the
        # trimmed beatmap - so the supervisor sees the full pipeline
        # (countdown -> falling notes -> hits -> results) in under
        # a minute without sitting through a 3-minute song.
        cap = self._test_mode_trials()
        if (cap is not None and getattr(beatmap, "notes", None)
                and len(beatmap.notes) > cap):
            beatmap.notes = beatmap.notes[:cap]
        self.mode = RhythmMode(
            engine=self, beatmap=beatmap, windows=rw, score_cfg=self.score_cfg,
        )
        self._begin_block("rhythm")
        self.screen_obj = self._screens["rhythm"]
        # Remember the beatmap so the Retry button on results can
        # rebuild this exact session. Storing the source song path +
        # difficulty rather than the mutated beatmap object so the
        # pre_song_lead time-shift doesn't compound on each retry.
        self._last_rhythm_song = beatmap.song
        self._last_rhythm_difficulty = beatmap.difficulty
        self._last_rhythm_title = beatmap.title

    def retry_last_block(self) -> None:
        """Re-run the most recent block (same mode, same config, same
        rhythm track if applicable). Called from the Retry button on
        the results screen. Falls through to mode select if we can't
        figure out what to re-run."""
        kind = getattr(self, "current_block", None)
        if kind == "classic":
            self.begin_classic_block()
            return
        if kind == "adaptive":
            self.begin_adaptive_block()
            return
        if kind == "mirror":
            self.begin_mirror_block()
            return
        if kind == "rhythm":
            song = getattr(self, "_last_rhythm_song", None)
            difficulty = getattr(self, "_last_rhythm_difficulty", "medium")
            if song:
                # Rebuild the beatmap fresh so the pre_song_lead shift
                # applies to clean note times. extract_beatmap falls
                # back to a procedural metronome map if librosa can't
                # parse the file, so this is safe even if the audio
                # file is gone.
                from ..audio.beatmap import extract_beatmap
                bm = extract_beatmap(
                    song,
                    difficulty=difficulty,
                    num_lanes=self.total_lanes,
                )
                self.begin_rhythm_block(bm)
                return
        # Unknown / no prior block. Drop back to mode select so the
        # user can pick something concretely.
        self.show_mode_select()

    def _begin_block(self, name: str) -> None:
        self.current_block = name
        # Pre-start "GET READY" countdown on the cadence modes (classic /
        # adaptive / mirror), all of which render through the gameplay
        # screen. Rhythm is excluded: it has its own musical lead-in.
        # Test mode trims the countdown so quick demos stay quick.
        if name in ("classic", "adaptive", "mirror"):
            secs = float(self.cfg.get("game.start_countdown_s", 5.0))
            if self._test_mode_trials() is not None:
                secs = min(secs, 1.5)
            gp = self._screens.get("gameplay")
            if gp is not None and hasattr(gp, "start_countdown"):
                gp.start_countdown(secs)
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
        # Idle-press counter: presses that landed in classic / adaptive
        # while NO trial was active (between stims). Counts only when
        # an idle penalty actually applied. Useful for the thesis stats:
        # a high number alongside a low hit rate signals the patient
        # was trying to game the system.
        self._block_idle_presses = 0
        # Per-lane stats accumulated over the current block, surfaced
        # on the Results screen as two bar charts (mean RT per lane,
        # miss + wrong-press count per lane). The Results screen
        # reads these directly so the engine is the single source of
        # truth and the screen doesn't have to re-parse the trial CSV.
        # Keys are lane indices (0..3 unilateral, 0..7 bilateral).
        self._per_lane_rts: dict[int, list[float]] = {}
        self._per_lane_misses: dict[int, int] = {}
        # `wrong` here means "this lane was the target but the patient
        # missed OR pressed a wrong finger first". Sum of per-trial
        # wrong-press events plus timeout misses gives a clean "how
        # often did THIS finger let the patient down" count.
        self._per_lane_wrong: dict[int, int] = {}
        # Per-lane peak-force samples for the block summary. Same keys
        # as the other per-lane dicts.
        self._per_lane_peak_force: dict[int, list[float]] = {}
        self._per_lane_impulse: dict[int, list[float]] = {}
        # Miss-force + loud-trial counters reset per block so the Results
        # screen reports THIS block, matching how hits / misses reset
        # above. The audio gain is forced back to normal in case the
        # previous block ended mid-loud-trial.
        self._force_window_start = None
        self._force_window_end = None
        self._force_window_peak = {}
        self._force_window_saw_samples = False
        self._force_window_trial_id = None
        self._miss_force_total = 0.0
        self._miss_force_count = 0
        self._trials_fired = 0
        self._block_stim_failures = 0
        self._last_stim_delivered = None
        self._block_pause_count = 0
        self._block_paused_s = 0.0
        self._loud_trials_by_id = {}
        self._block_loud_trials = 0
        self._last_stim_timeout_ms = None
        if self.audio is not None:
            self.audio.set_trial_gain(1.0)
        # Drift-sampler bookkeeping. Across-block lists stay populated
        # for the lifetime of the session (so fatigue_slope can run on
        # block N looking back at blocks 1..N-1). The drift-samples
        # dict is per-block so each block reports its own drift slope.
        self._drift_samples: dict[tuple[str, int], list[tuple[float, float]]] = {}
        self._last_drift_sample_t = None
        self._rhythm_press_times_s = []
        self._rhythm_beat_times_s = []
        self._open_loggers()
        # Reset detectors at block start so old baselines don't leak in.
        for d in self.detectors.values():
            d.reset()
        # reset() clears the baseline to None, which would undo the priming
        # apply_calibration did and hand back the settling window it exists
        # to remove. Without this, a block that starts with the hand off the
        # pads seeds the baseline from the empty device; the hand landing
        # then reads as a rise, and until the EMA catches up (about 10 s at
        # the shipped alpha) the effective trigger is the resting load lower
        # than intended. The first trials of the block would run under a
        # different threshold from the rest.
        self._prime_baselines()

    def _open_loggers(self) -> None:
        data_dir = self.cfg.resolve_path(self.cfg.get("session.data_dir", "sessions"))
        Path(data_dir).mkdir(parents=True, exist_ok=True)
        self.session_paths = SessionPaths.for_session(
            Path(data_dir), self.session.participant,
            mode=self.current_block,
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

    def _stamp_calibration(self) -> None:
        """Record which calibration this block ran under. Written into
        metadata.json so the analysis can convert counts to force and
        state the thresholds without guessing."""
        prof = getattr(self, "calibration_profile", None)
        if prof is None:
            self.session.calibration = {}
            return
        try:
            self.session.calibration = prof.summary()
        except Exception as e:
            log.warning("could not summarise calibration: %s", e)
            self.session.calibration = {}

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
            # Idle / between-trial presses in classic / adaptive that
            # cost the patient points. Provides a quick "did the
            # patient try to game the scoring" signal for the thesis.
            "idle_presses": getattr(self, "_block_idle_presses", 0),
        }
        # Miss-force capture, persisted so the analysis never depends
        # on someone photographing the results screen. Same unit
        # context as peak_force_n (see force_unit below).
        mf_total = getattr(self, "_miss_force_total", 0.0)
        mf_count = getattr(self, "_miss_force_count", 0)
        summary["miss_force"] = {
            "window_ms": getattr(self, "_force_window_ms", None),
            "total": round(mf_total, 3),
            "n_misses": mf_count,
            "mean_per_miss": (round(mf_total / mf_count, 3)
                               if mf_count > 0 else None),
        }
        # Loudness-variation bookkeeping: how many trials actually
        # played boosted this block, next to the configured schedule,
        # so an analyst can verify the manipulation ran as intended.
        # Buzzer cue delivery. Non-zero means the hardware stopped
        # accepting stim commands mid-block, so some trials had no
        # vibration cue and must not be read as ordinary misses.
        summary["stim_cue_failures"] = getattr(
            self, "_block_stim_failures", 0)
        # Pauses. duration_s above is wall-clock including any pause,
        # so subtract paused_total_s for actual time on task.
        summary["pauses"] = getattr(self, "_block_pause_count", 0)
        summary["paused_total_s"] = round(
            getattr(self, "_block_paused_s", 0.0), 3)
        summary["loud_trials"] = {
            "n": getattr(self, "_block_loud_trials", 0),
            "configured_fraction": getattr(
                self, "_loud_trial_fraction", None),
            "boost": getattr(self, "_loud_trial_boost", None),
        }
        # Which track a rhythm block actually played. Config records
        # the difficulty default but not the runtime song choice.
        if self.current_block == "rhythm":
            bm = getattr(self.mode, "beatmap", None) if self.mode else None
            n_notes = None
            bpm_val = None
            if bm is not None:
                try:
                    n_notes = len(getattr(bm, "notes", []) or [])
                    raw_bpm = getattr(bm, "bpm", None)
                    bpm_val = (round(float(raw_bpm), 1)
                               if raw_bpm is not None else None)
                except (TypeError, ValueError):
                    pass
            summary["song"] = {
                "title": (getattr(bm, "title", None)
                           or getattr(self, "_last_rhythm_title", None)),
                "difficulty": (getattr(bm, "difficulty", None)
                                or getattr(self,
                                           "_last_rhythm_difficulty",
                                           None)),
                "bpm": bpm_val,
                "n_notes": n_notes,
                "song_path": (str(getattr(bm, "song", "") or "")
                               or None),
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
        # Research aggregates (per-lane stats, peak force, fatigue,
        # beat offset, asymmetry, drift, startup latency). Build them
        # defensively so a None from an early-abandoned block or a
        # half-built test engine doesn't lose the rest of the summary.
        self._populate_research_summary(summary)
        return summary

    # ---- block-end research summary --------------------------------------
    def _populate_research_summary(self, summary: dict) -> None:
        """Add the per-block research aggregates onto the summary dict
        in place. Pure read of the per-lane state accumulated during
        the block. The metrics import sits inside the function because
        it pulls in numpy and scipy, and the headless test path runs
        a lot faster if those don't get imported until the moment a
        block actually finishes."""
        from ..analytics import metrics
        # Per-lane RT stats, outcome rates, and peak-force means.
        per_lane: dict[str, dict] = {}
        all_lanes = sorted(set(
            list(self._per_lane_rts.keys())
            + list(self._per_lane_misses.keys())
            + list(self._per_lane_wrong.keys())
            + list(self._per_lane_peak_force.keys())
        ))
        for lane in all_lanes:
            rts = self._per_lane_rts.get(lane, [])
            stats = metrics.rt_stats(rts)
            # Hit count comes from the RT list because only hit trials
            # log a reaction time. Wrong-press trials reclassify as
            # Miss earlier in the pipeline, so they show up under
            # timeouts here. The misclick counter is kept separately
            # because it counts events (not trials) and is useful as
            # an event rate per trial.
            hits = len(rts)
            timeouts = self._per_lane_misses.get(lane, 0)
            misclicks = self._per_lane_wrong.get(lane, 0)
            n_total = hits + timeouts
            rates = {
                "hit_rate": (hits / n_total) if n_total > 0 else 0.0,
                "timeout_rate": (timeouts / n_total) if n_total > 0 else 0.0,
                # Misclicks are events not unique trials; expose them
                # as a normalised count alongside hit/timeout.
                "misclick_rate": (misclicks / n_total) if n_total > 0 else 0.0,
            }
            peaks = self._per_lane_peak_force.get(lane, [])
            peak_mean = (sum(peaks) / len(peaks)) if peaks else None
            impulses = getattr(self, "_per_lane_impulse",
                                 {}).get(lane, [])
            impulse_mean = ((sum(impulses) / len(impulses))
                              if impulses else None)
            per_lane[str(lane)] = {
                "rt_mean_ms": (round(stats["rt_mean"], 2)
                                if stats["rt_mean"] is not None else None),
                "rt_std_ms": (round(stats["rt_std"], 2)
                                if stats["rt_std"] is not None else None),
                "rt_cv": (round(stats["rt_cv"], 4)
                            if stats["rt_cv"] is not None else None),
                "hit_rate": round(rates["hit_rate"], 3),
                "timeout_rate": round(rates["timeout_rate"], 3),
                "misclick_rate": round(rates["misclick_rate"], 3),
                "peak_force_mean": (round(peak_mean, 3)
                                      if peak_mean is not None else None),
                # Impulse units are the same as peak (newton-seconds
                # when a calibration is set, ADC-count-seconds
                # otherwise). force_unit in the summary records which.
                "impulse_mean": (round(impulse_mean, 4)
                                   if impulse_mean is not None else None),
                "n_trials": n_total,
            }
        summary["per_lane"] = per_lane
        summary["force_unit"] = self._force_unit()
        # Across-block fatigue slopes. Need at least 2 blocks of
        # history; the current block's mean is appended FIRST so the
        # slope returned includes this block.
        rt_count = getattr(self, "_block_rt_count", 0)
        if rt_count > 0:
            self._across_blocks_mean_rt.append(
                self._block_rt_sum / rt_count)
        all_peaks = [p for lane_peaks in self._per_lane_peak_force.values()
                      for p in lane_peaks]
        if all_peaks:
            self._across_blocks_mean_peak.append(
                sum(all_peaks) / len(all_peaks))
        summary["fatigue_slope_rt_ms_per_block"] = metrics.fatigue_slope(
            self._across_blocks_mean_rt)
        summary["fatigue_slope_force_per_block"] = metrics.fatigue_slope(
            self._across_blocks_mean_peak)
        # Beat-offset stats for rhythm mode only.
        if self.current_block == "rhythm" and self._rhythm_press_times_s:
            bo = metrics.beat_offset_stats(
                self._rhythm_press_times_s,
                self._rhythm_beat_times_s,
            )
            summary["beat_offset_stats"] = {
                k: (round(v, 3) if v is not None else None)
                for k, v in bo.items()
            }
            # Tempo entrainment via lag-1 autocorrelation of signed
            # offsets. r > 0 = patient tracks the tempo (consecutive
            # offsets are similar). r ~= 0 = independent presses
            # (landing near the beat by luck, not tracking).
            offsets = getattr(self, "_rhythm_signed_offsets_ms", [])
            if len(offsets) >= 3:
                entr = metrics.tempo_entrainment_index(
                    offsets[1:], offsets[:-1])
                summary["beat_offset_stats"]["entrainment_lag1_r"] = (
                    round(entr, 4) if entr is not None else None)
            # Tap variability CV (rhythm mode only). Inter-tap-interval
            # consistency, distinct from RT CV. Standard metric in
            # rhythmic-tapping studies (tremor, Parkinson's, stroke).
            # Only meaningful when the patient is meant to tap to a
            # beat; in random-cadence modes it would conflate patient
            # inconsistency with stimulus inconsistency.
            tap_cv = metrics.tap_variability_cv(self._rhythm_press_times_s)
            summary["tap_variability_cv"] = (
                round(tap_cv, 4) if tap_cv is not None else None)
        # Session-level outcome rates (rolled up from the per-lane
        # counts above). Mirrors metrics.outcome_rates on a flat trial
        # list, but built from cached counts so the rollup matches the
        # per-lane totals exactly.
        total_hits = sum(len(rts) for rts
                          in self._per_lane_rts.values())
        total_timeouts = sum(self._per_lane_misses.values())
        total_misclicks = sum(self._per_lane_wrong.values())
        denom = total_hits + total_timeouts
        if denom > 0:
            summary["outcome_rates_overall"] = {
                "hit_rate": round(total_hits / denom, 4),
                "timeout_rate": round(total_timeouts / denom, 4),
                "misclick_rate": round(total_misclicks / denom, 4),
                "n_trials": denom,
            }
        else:
            summary["outcome_rates_overall"] = {
                "hit_rate": 0.0,
                "timeout_rate": 0.0,
                "misclick_rate": 0.0,
                "n_trials": 0,
            }
        # Bilateral asymmetry + cross-correlation. Only meaningful in
        # both-hand mode. Cross-correlation is computed on resampled
        # force series; we don't keep the raw streams in memory so
        # this falls back to None unless an external resampler has
        # populated `self._block_force_resampled` (placeholder for a
        # future hook - see ThesisBChanges if it ever lands).
        if self.hand_mode == "both":
            n_per_hand = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
            right_peaks = [
                p for lane in range(n_per_hand)
                for p in self._per_lane_peak_force.get(lane, [])
            ]
            left_peaks = [
                p for lane in range(n_per_hand, 2 * n_per_hand)
                for p in self._per_lane_peak_force.get(lane, [])
            ]
            right_mean = (sum(right_peaks) / len(right_peaks)
                            if right_peaks else None)
            left_mean = (sum(left_peaks) / len(left_peaks)
                            if left_peaks else None)
            right_rts = [rt for lane in range(n_per_hand)
                         for rt in self._per_lane_rts.get(lane, [])]
            left_rts = [rt for lane in range(n_per_hand, 2 * n_per_hand)
                        for rt in self._per_lane_rts.get(lane, [])]
            right_rt_mean = (sum(right_rts) / len(right_rts)
                              if right_rts else None)
            left_rt_mean = (sum(left_rts) / len(left_rts)
                              if left_rts else None)
            asym = {
                "peak_force": metrics.asymmetry_index(
                    left_mean, right_mean),
                "rt_mean": metrics.asymmetry_index(
                    left_rt_mean, right_rt_mean),
            }
            summary["asymmetry_index"] = {
                k: (round(v, 4) if v is not None else None)
                for k, v in asym.items()
            }
            # Inter-hand correlation needs time-aligned streams; not
            # available from per-trial peak lists. Placeholder for a
            # future force-stream capture hook - reported as None so
            # the schema is stable.
            summary["inter_hand_correlation"] = None
        # Per-sensor drift slope.
        drift: dict[str, float | None] = {}
        for (hand, idx), samples in self._drift_samples.items():
            xs = [t for t, _ in samples]
            ys = [v for _, v in samples]
            slope = metrics.drift_slope(xs, ys)
            drift[f"{hand}_{idx}"] = (round(slope, 4)
                                       if slope is not None else None)
        summary["drift_units_per_min"] = drift
        # Per-sensor baseline at block end. Complements the drift slope
        # (rate of change) with the absolute level, so a sensor that
        # started weird - not just drifted - is visible without
        # re-processing raw.csv.
        baseline_end: dict[str, float | None] = {}
        for hand, det in (getattr(self, "detectors", {}) or {}).items():
            n_sensors = len(getattr(det, "last_value", []) or [])
            for i in range(n_sensors):
                try:
                    b = det.baseline_value(i)
                except Exception:
                    b = None
                baseline_end[f"{hand}_{i}"] = (
                    round(float(b), 2) if b is not None else None)
        summary["baseline_end"] = baseline_end
        # Startup latency per port. Read from the source every time
        # the summary builds (rather than caching at block start),
        # because the source might learn the first-sample timestamp
        # after the block has already started.
        get_lat = getattr(self.source, "get_startup_latency", None)
        if callable(get_lat):
            try:
                summary["startup_latency_ms"] = get_lat()
            except Exception:
                summary["startup_latency_ms"] = None

    def start_protocol(self) -> bool:
        """Kick off the pretest / main / aftertest sequence defined by
        cfg.protocol.blocks. Returns True if a protocol started, False
        if no protocol is configured (caller falls back to single-
        block flow). Each step is a (mode, phase) tuple; mode picks
        which begin_*_block to call, phase becomes the trial CSV's
        `phase` column for that block. Rhythm in a protocol isn't
        supported here because rhythm needs a beatmap picked first;
        if a researcher really wants rhythm in a protocol they can
        rerun rhythm manually."""
        steps_raw = self.cfg.get("protocol.blocks") or []
        if not steps_raw:
            return False
        parsed: list[tuple[str, str]] = []
        for entry in steps_raw:
            if isinstance(entry, dict):
                mode = str(entry.get("mode") or "").lower()
                phase = str(entry.get("phase") or "").lower()
            elif (isinstance(entry, (list, tuple))
                    and len(entry) >= 2):
                mode = str(entry[0]).lower()
                phase = str(entry[1]).lower()
            else:
                continue
            if mode in ("classic", "adaptive", "mirror"):
                parsed.append((mode, phase))
        if not parsed:
            return False
        self._protocol_steps = parsed
        self._protocol_index = 0
        self._protocol_active = True
        self._begin_next_protocol_step()
        return True

    def _begin_next_protocol_step(self) -> None:
        """Start the protocol step at `_protocol_index`. Called from
        start_protocol for the first block and from finish_block when
        the previous block ends. Falls back to results / mode-select
        when the protocol has run out of steps."""
        if (not self._protocol_active
                or self._protocol_index >= len(self._protocol_steps)):
            self._protocol_active = False
            self._current_phase = ""
            return
        mode, phase = self._protocol_steps[self._protocol_index]
        self._current_phase = phase
        self._protocol_index += 1
        if mode == "classic":
            self.begin_classic_block()
        elif mode == "adaptive":
            self.begin_adaptive_block()
        elif mode == "mirror":
            self.begin_mirror_block()
        else:
            # Shouldn't reach here; start_protocol filters by mode.
            self._protocol_active = False
            self._current_phase = ""

    def _generate_session_report(self) -> None:
        """Build the researcher outputs (report.html, summary.csv,
        charts/) inside the finished session folder and append this
        block to sessions_index.csv. Runs AFTER the loggers close so
        the report reads complete CSVs. Fully guarded: the raw data is
        already safe on disk, so a report failure only logs a warning."""
        if not self.session_paths:
            return
        if not bool(self.cfg.get("report.enabled", True)):
            return
        from ..analytics import report
        root = self.session_paths.root
        try:
            report.generate(root)
        except Exception as e:
            log.warning("Session report generation failed: %s", e)
        try:
            summary = self.session.block_summary or {}
            data_dir = Path(self.cfg.resolve_path(
                self.cfg.get("session.data_dir", "sessions")))
            # Day-relative path (e.g. 2026-07-02/Pat_143005_adaptive)
            # so the index row points straight at the folder from the
            # sessions/ root. Falls back to the bare name for a root
            # that isn't under data_dir (tests, odd configs).
            try:
                folder_rel = str(root.relative_to(data_dir))
            except ValueError:
                folder_rel = root.name
            finished = self.session.finished_at or ""
            report.append_index(data_dir, {
                "date": finished[:10],
                "finished_at": finished,
                "participant": self.session.participant,
                "age": self.session.age,
                "mode": summary.get("block", self.current_block),
                "hand": self.hand_mode,
                "status": summary.get("status", ""),
                "trials": summary.get("trials", ""),
                "hit_rate": summary.get("hit_rate", ""),
                "avg_rt_ms": summary.get("avg_rt_ms", ""),
                "final_score": summary.get("final_score", ""),
                "folder": folder_rel,
            })
        except Exception as e:
            log.warning("sessions_index.csv update failed: %s", e)

    # ---- buzzer cue -------------------------------------------------------
    # The firmware holds a motor on for a fixed 150 ms per STIM command
    # and its drive strength is a compile-time constant, so the only
    # dimension the host can vary is how long the buzz lasts. Sending
    # another STIM before the previous one expires re-arms the motor,
    # which is how a cue_ms longer than 150 ms is produced.
    FIRMWARE_STIM_MS = 150

    def _stim_channel(self, lane: int) -> int:
        """Which STIM channel actually reaches this finger.

        The firmware maps STIM:1..4 onto fixed pins, so a motor wired
        elsewhere would buzz the wrong finger. motor.channel_map holds
        the real correspondence, discovered by the buzzer calibration,
        so the sketch never has to change. Falls back to
        straight-through if the map is missing or malformed.
        """
        n_per_hand = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
        finger = lane % n_per_hand           # 0..3 within the hand
        # Lane numbers stay GLOBAL (1..8 in bilateral mode). multi_serial
        # is what splits them across the two boards, so the hand offset
        # has to be preserved here or the left hand gets sent to the
        # right board. Only the finger part is remapped.
        hand_offset = lane - finger
        try:
            cmap = list(self.cfg.get("motor.channel_map") or [])
            ch = int(cmap[finger])
            if 1 <= ch <= n_per_hand:
                return hand_offset + ch
        except (TypeError, ValueError, IndexError):
            pass
        return lane + 1

    def _send_stim(self, lane: int) -> bool:
        """Fire one STIM pulse for the finger on `lane` (0-indexed).
        Returns whether the hardware accepted it."""
        try:
            return bool(self.source.send_command(
                f"STIM:{self._stim_channel(lane)}"))
        except Exception as e:
            log.warning("STIM send failed on lane %d: %s", lane, e)
            return False

    def _schedule_cue_pulses(self, lane: int) -> None:
        """Queue the repeat pulses needed to stretch this lane's cue out
        to motor.cue_ms. The caller has already sent the first pulse, so
        this only schedules the follow-ups."""
        if not hasattr(self, "_motor_queue"):
            self._motor_queue = []
        cue_ms = float(self.cfg.get("motor.cue_ms",
                                     self.FIRMWARE_STIM_MS))
        if cue_ms <= self.FIRMWARE_STIM_MS:
            return
        gap_ms = float(self.cfg.get("motor.pulse_interval_ms", 120))
        # Keep the gap under the firmware hold or the motor stutters.
        gap_ms = max(20.0, min(gap_ms, self.FIRMWARE_STIM_MS - 10))
        now = time.perf_counter()
        due = gap_ms
        # Re-arm until the final pulse's own 150 ms tail carries the
        # buzz past cue_ms.
        while due + self.FIRMWARE_STIM_MS < cue_ms + gap_ms:
            self._motor_queue.append((lane, now + due / 1000.0))
            due += gap_ms
            if len(self._motor_queue) > 64:      # runaway guard
                break

    def _drain_motor_queue(self) -> None:
        """Send any cue repeat-pulses that have come due. Called once
        per frame from the main loop."""
        q = getattr(self, "_motor_queue", None)
        if not q:
            return
        now = time.perf_counter()
        still = []
        for lane, due in q:
            if now >= due:
                self._send_stim(lane)
            else:
                still.append((lane, due))
        self._motor_queue = still

    def stop_all_motors(self) -> None:
        """Drop pending cue pulses and tell the hardware to stop, so a
        queued pulse cannot buzz after the block has ended."""
        self._motor_queue = []
        try:
            self.source.send_command("STOP")
        except Exception:
            pass

    def open_sessions_folder(self) -> bool:
        """Open the TOP-LEVEL sessions folder (the one holding every
        day directory and sessions_index.csv) in Finder / Explorer.
        Wired to the Settings screen so the researcher can reach all
        recorded data at any time, not just after a block."""
        try:
            data_dir = Path(self.cfg.resolve_path(
                self.cfg.get("session.data_dir", "sessions")))
            data_dir.mkdir(parents=True, exist_ok=True)
            return self._reveal_in_file_manager(str(data_dir))
        except Exception as e:
            log.warning("Could not open sessions folder: %s", e)
            return False

    @staticmethod
    def _reveal_in_file_manager(path: str) -> bool:
        """Show a folder in the OS file manager. Shared by the Settings
        and Results buttons."""
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", path])
            return True
        except Exception as e:
            log.warning("Could not open %s: %s", path, e)
            return False

    def open_last_session_folder(self) -> bool:
        """Open the most recent session folder in Finder / Explorer /
        the Linux file manager. Wired to the results screen's Open
        data folder button so a researcher can reach the CSVs and the
        report without hunting through the filesystem."""
        path = self.last_session_root
        if not path or not Path(path).exists():
            log.warning("No session folder to open")
            return False
        try:
            if sys.platform == "darwin":
                subprocess.Popen(["open", path])
            elif os.name == "nt":
                os.startfile(path)  # type: ignore[attr-defined]
            else:
                subprocess.Popen(["xdg-open", path])
            return True
        except Exception as e:
            log.warning("Could not open session folder: %s", e)
            return False

    def finish_block(self) -> None:
        # Kill any queued cue pulse so the device cannot buzz after the
        # block is over.
        self.stop_all_motors()
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
        self._stamp_calibration()
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
        # Researcher outputs: report.html + summary.csv + charts in the
        # session folder, plus a line in sessions_index.csv. After the
        # loggers close so the CSVs are complete.
        self._generate_session_report()
        self.session_paths = None
        # If a protocol is running, auto-advance to the next step
        # instead of bouncing to the Results screen between blocks.
        # The final Results screen still shows after the LAST step
        # finishes (no more entries -> _protocol_active flips False).
        if (self._protocol_active
                and self._protocol_index < len(self._protocol_steps)):
            self._begin_next_protocol_step()
            return
        # Protocol just finished its final step -> clear the phase
        # so subsequent free-play blocks aren't labelled "aftertest".
        if self._protocol_active:
            self._protocol_active = False
            self._current_phase = ""
        self.show_results()

    def _abandon_if_in_block(self) -> None:
        """Esc / QUIT mid-block. Marks the metadata as abandoned so we still
        keep the partial CSV and a record of what happened."""
        if not self.session_paths:
            return
        log.info("Abandoning in-progress block")
        self.stop_all_motors()
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
        self._stamp_calibration()
        self.session.block_summary = self._build_block_summary("abandoned")
        # Record the path before attempting save so the CSV root is
        # still recoverable even if the JSON write blows up.
        self.last_session_root = str(self.session_paths.root)
        try:
            self.session.save(self.session_paths.metadata_json)
        except Exception as e:
            log.warning("Could not save abandoned metadata: %s", e)
        self._close_loggers()
        # Partial blocks still get the researcher outputs; the report's
        # status field says "abandoned" so nobody mistakes it for a
        # complete block.
        self._generate_session_report()
        self.session_paths = None
        self.mode = None

    # ---- per-outcome colour --------------------------------------------------
    # Three tiers so the patient knows roughly how well they did at a
    # glance:
    #   red    = Miss (didn't press the right lane in time)
    #   orange = Late / Early (pressed the right lane but timing off)
    #   green  = Great / Good (pressed in time)
    #   gold   = Perfect (sub-perfect_ms reaction, biggest reward)
    # Same map drives the lane-flash AND the floating popup text so they
    # always agree.
    _ORANGE_CLOSE = (235, 130, 50)
    _GOLD = (255, 196, 0)

    def _outcome_colour(self, label: str,
                        mode_hint: str | None = None) -> tuple[int, int, int]:
        """Colour for the lane / ring flash on a trial outcome.

        Rhythm mode uses a softer red->orange mapping for "Miss" because
        red is reserved there for genuinely-wrong presses (wrong-lane
        click logged via log_rhythm_unmatched). Classic + adaptive keep
        the original red for Miss since wrong-lane there is logged
        inside the same trial via incorrect_presses, not as a separate
        flash event.
        """
        key = label.lower() if label else ""
        if mode_hint is None:
            mode_hint = getattr(self, "current_block", None)
        if key == "miss":
            if mode_hint == "rhythm":
                return self._ORANGE_CLOSE    # rhythm: miss = orange
            return self.theme.lane_miss      # classic / adaptive: red
        if key in ("late", "early"):
            return self._ORANGE_CLOSE        # orange (close but off)
        if key == "perfect":
            # Gold flash makes a Perfect feel distinctly bigger than a
            # Great. Same gold the Results screen uses for an S grade,
            # so the visual reward language is consistent.
            return self._GOLD
        # Great / Good fall through to the normal hit green.
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
        # Combo bonus tuned to reward consistency without distorting
        # the per-block totals: +0.1x per hit on the streak, capped
        # at +0.5x once the streak reaches 5. The cap keeps a single
        # exceptional run from dominating the comparison between
        # patients or between visits - a session's max possible
        # score is bounded at 1.5x the unboosted total.
        return 1.0 + min(self.hit_streak * 0.1, 0.5)

    def _score_for(self, base_points: int, label: str) -> int:
        # Misses skip the bonus path entirely so we don't accidentally
        # multiply a negative.
        if label == "Miss" or base_points <= 0:
            return base_points
        boost = self._pace_multiplier() * self._streak_multiplier()
        return int(round(base_points * boost))

    def apply_wrong_press_penalty(self) -> int:
        """Subtract the configured wrong-press penalty from the score.
        Called by mode handlers on every wrong-finger press during a
        trial (classic / adaptive) AND per unmatched press in rhythm.
        Applying it every wrong press (not just the first) is what
        makes finger-spamming a net-negative strategy for the patient
        rather than a free side bet on top of the correct press.
        Floors the result at zero so the score never displays negative.
        Returns the amount actually subtracted, useful for UI feedback.
        """
        penalty = int(self.cfg.get("scoring.wrong_press_penalty", 0))
        if penalty <= 0:
            return 0
        new_score = max(0, self.score - penalty)
        actually = self.score - new_score
        self.score = new_score
        # Mirror via _last_gained so the HUD popup reads as a deduction.
        if actually > 0:
            self._last_gained = -actually
        return actually

    def apply_idle_press_penalty(self) -> int:
        """Subtract a (typically smaller) penalty for presses that
        happen OUTSIDE any active trial in classic / adaptive. Without
        this, a patient could machine-gun the keys between stims with
        zero cost, since the trial handler short-circuits when no
        trial is pending. The detector's debounce_ms (defaults to
        100 ms) already rate-limits these at the hardware level, so
        we don't need our own cooldown here.

        Returns the points actually subtracted.
        """
        penalty = int(self.cfg.get("scoring.idle_press_penalty", 0))
        if penalty <= 0:
            return 0
        new_score = max(0, self.score - penalty)
        actually = self.score - new_score
        self.score = new_score
        if actually > 0:
            self._last_gained = -actually
            # Bump the spam counter so end-of-block stats record how
            # often this patient was pressing between stims. Useful
            # signal for the thesis: high counts may mean the pace is
            # too slow, or the patient is gaming the system.
            self._block_idle_presses = getattr(
                self, "_block_idle_presses", 0) + 1
        return actually

    # ---- force + drift helpers --------------------------------------------
    def _resolve_lane_to_detector(self, lane: int
                                    ) -> tuple[str, int] | None:
        """Map an engine-global lane index (0..3 unilateral, 0..7
        bilateral) to a (hand, sensor_idx) pair the detector dict
        understands. Returns None if the mapping can't be resolved
        (no detector for that hand, or lane out of range, or a
        __new__-built test engine without cfg)."""
        if not hasattr(self, "cfg") or self.cfg is None:
            return None
        try:
            n_per_hand = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
        except (AttributeError, TypeError, ValueError):
            return None
        if self.hand_mode == "both":
            if 0 <= lane < n_per_hand:
                return ("right", lane)
            if n_per_hand <= lane < 2 * n_per_hand:
                return ("left", lane - n_per_hand)
            return None
        # Unilateral: the lane is the within-hand sensor index.
        if 0 <= lane < n_per_hand:
            return (self.hand_mode, lane)
        return None

    def _peak_force_for_lane(self, lane: int) -> float | None:
        """Live peak force on a lane's target sensor, calibrated to
        newtons if `fsr.force_calibration_n_per_count` is configured.
        Returns None when the sensor isn't currently pressed (a Miss
        trial, or a fake source that never produced an FSR press)."""
        mapped = self._resolve_lane_to_detector(lane)
        if mapped is None:
            return None
        hand, idx = mapped
        det = self.detectors.get(hand)
        if det is None:
            return None
        peak = det.current_peak(idx)
        if peak is None:
            return None
        _peak_raw, peak_minus_baseline = peak
        cal = self.cfg.get("fsr.force_calibration_n_per_count", None)
        if cal is None:
            # Raw ADC counts. session.json records this fact under
            # block_summary.force_unit so the analyst knows the column
            # isn't in newtons.
            return float(peak_minus_baseline)
        try:
            return float(peak_minus_baseline) * float(cal)
        except (TypeError, ValueError):
            return float(peak_minus_baseline)

    def _impulse_for_lane(self, lane: int) -> float | None:
        """Live force-time integral on a lane's target sensor. Same
        unit conventions as _peak_force_for_lane: newton-seconds if
        a force calibration is configured, otherwise ADC-count-
        seconds. Returns None when the sensor isn't currently
        pressed."""
        mapped = self._resolve_lane_to_detector(lane)
        if mapped is None:
            return None
        hand, idx = mapped
        det = self.detectors.get(hand)
        if det is None:
            return None
        imp = det.current_impulse(idx)
        if imp is None:
            return None
        _raw, minus_baseline = imp
        cal = self.cfg.get("fsr.force_calibration_n_per_count", None)
        if cal is None:
            return float(minus_baseline)
        try:
            return float(minus_baseline) * float(cal)
        except (TypeError, ValueError):
            return float(minus_baseline)

    def _force_unit(self) -> str:
        """Return 'N' if a calibration constant is present, else
        'counts'. Stored in block_summary so the trial CSV's
        peak_force_n column is interpretable downstream."""
        cal = self.cfg.get("fsr.force_calibration_n_per_count", None)
        return "N" if cal is not None else "counts"

    # Cadence for the per-block drift sampler. Set to 30 s as a
    # compromise: long enough that the baseline-tracking EMA has
    # settled between samples (alpha=0.02 has roughly a 50-sample
    # half-life at 200 Hz, so well under 30 s), short enough that a
    # 5-block session still gives ~10 samples per sensor for the
    # `drift_units_per_min` slope.
    DRIFT_SAMPLE_INTERVAL_S = 30.0

    def _maybe_sample_drift(self) -> None:
        """Sample each sensor's live baseline every 30 s during the
        block. Called once per mainloop frame; the interval check
        keeps it cheap. finish_block feeds the accumulated samples
        to metrics.drift_slope to compute units-per-minute drift per
        sensor."""
        now = time.perf_counter()
        if self._last_drift_sample_t is None:
            self._last_drift_sample_t = now
            return
        if (now - self._last_drift_sample_t) < self.DRIFT_SAMPLE_INTERVAL_S:
            return
        self._last_drift_sample_t = now
        t_min = (now - self._block_t0) / 60.0
        n_per_hand = int(self.cfg.get("fsr.num_sensors_per_hand", 4))
        for hand, det in self.detectors.items():
            for idx in range(n_per_hand):
                base = det.baseline_value(idx)
                if base is None:
                    continue
                self._drift_samples.setdefault(
                    (hand, idx), []).append((t_min, float(base)))

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
        # Single-lane wrapper for the multi-lane path. Mirror mode
        # uses on_stim_multi to light up both hands at once; classic,
        # adaptive, and rhythm all hit one finger at a time and go
        # through this convenience wrapper.
        self.on_stim_multi([lane], trial_id, t_perf)

    def on_stim_multi(self, lanes: list[int], trial_id: int,
                       t_perf: float) -> None:
        # Light up every lane in `lanes` and arm timing bars on the
        # gameplay screen. Mirror mode passes two same-finger lanes
        # (e.g. right index + left index) so the patient sees both
        # tiles go active at the same moment. In bilateral mode the
        # lane numbering is global (0..7) and each strip's enumerate
        # index matches that.
        targets = set(int(l) for l in lanes)
        # Which cue the patient gets. "visual" suppresses the buzzer,
        # "vibration" suppresses the on-screen reveal so the finger has
        # to be identified by touch alone.
        cue_mode = str(self.cfg.get("game_cue.mode", "both") or "both").lower()
        if cue_mode not in ("both", "visual", "vibration"):
            cue_mode = "both"
        self._last_cue_mode = cue_mode
        show_on_screen = cue_mode in ("both", "visual")
        # Loudness variation + miss-force window both key off the stimulus.
        # Bump the trial counter, raise the audio gain on a loud trial (so
        # the cue played just below AND the feedback chime at log_trial are
        # louder), and open the force window so _feed_detectors starts
        # tracking each finger's peak from this instant.
        self._ensure_metric_state()
        self._trials_fired += 1
        is_loud = self._is_loud_trial(self._trials_fired)
        if self.audio is not None:
            self.audio.set_trial_gain(
                self._loud_trial_boost if is_loud else 1.0)
        else:
            # No audio engine -> no boost was actually heard, so the
            # trial CSV must not claim this trial played loud.
            is_loud = False
        # Record the flag by trial id so the CSV row (written at trial
        # close, possibly after the NEXT stim fired in rhythm) still
        # reports the right trial's loudness.
        self._loud_trials_by_id[trial_id] = is_loud
        if is_loud:
            self._block_loud_trials += 1
        self._open_force_window(t_perf, trial_id)
        # Rhythm mode has its own timeout window logic; the others
        # share game.timeout_s with a current_timeout_s hook for
        # adaptive's slow-down branch.
        if self.mode is not None and hasattr(self.mode, "current_timeout_s"):
            timeout_s = float(self.mode.current_timeout_s)
        else:
            timeout_s = float(self.cfg.get("game.timeout_s", 1.0))
        # The trial's response window is the RT censoring limit; the CSV
        # logs it per trial because adaptive varies it with the cadence.
        self._last_stim_timeout_ms = timeout_s * 1000.0
        for key in ("gameplay", "rhythm"):
            sc = self._screens.get(key)
            if sc and hasattr(sc, "lanes"):
                for i, ls in enumerate(sc.lanes):
                    if key == "gameplay":
                        # Target lanes get the active fill + timing
                        # bar so the patient sees which fingers to
                        # press. Everyone else clears.
                        # In vibration-only the tile must not reveal
                        # which finger to press, but the timing bar
                        # still runs so the patient can see how long
                        # they have left.
                        ls.active = (i in targets) and show_on_screen
                        if i in targets:
                            ls.arm_timing(t_perf, timeout_s)
                        else:
                            ls.clear_timing()
                    else:
                        # Rhythm uses falling notes + target rings
                        # for "press this" cues, so lane tiles never
                        # go to their active colour mid-stream.
                        ls.active = False
        # Buzzer / vibration cue. Record whether each command was
        # actually accepted by the hardware: if the Arduino drops out
        # mid-block the patient stops feeling the cue, and without this
        # the trials would look like ordinary misses instead of a
        # hardware failure. None = motors disabled for this session.
        self._last_stim_delivered = None
        if self.cfg.get("motor.enabled", True) and cue_mode != "visual":
            # Buzz the TARGET finger so the patient feels which one to
            # press. One STIM command per target lane; the Arduino
            # numbers motors 1..N matching the global lane.
            delivered = True
            for lane in sorted(targets):
                ok = self._send_stim(lane)
                if not ok:
                    delivered = False
                if self.raw_logger:
                    self.raw_logger.queue_event(
                        "stim_motor", lane=lane, t_perf=t_perf,
                        detail=f"delivered={'yes' if ok else 'NO'}",
                        hand=self.hand_mode)
                # Hold the motor on for the configured cue length. The
                # firmware runs a fixed 150 ms per command, so anything
                # longer is built by re-arming it before it expires.
                self._schedule_cue_pulses(lane)
            self._last_stim_delivered = delivered
            if not delivered:
                self._block_stim_failures += 1
                log.warning("Buzzer cue not delivered for trial %s. "
                             "Check the Arduino connection.", trial_id)
        # Per-lane stim tone for the cadence-driven modes (classic,
        # adaptive, mirror). Skipped in rhythm so the cue tone
        # doesn't fight the music. play_stim only fires for the
        # lowest target lane in a multi-lane stim so two finger tones
        # don't pile into one beat in mirror mode.
        if (self.audio is not None
                and self.cfg.get("audio.stim_tone_enabled", True)
                and self.current_block in ("classic", "adaptive", "mirror")):
            try:
                self.audio.play_stim(min(targets))
            except Exception:
                pass
        if self.raw_logger:
            # One raw-log line per lane so an analyst running the
            # mirror-mode raw CSV doesn't lose the second-hand stim.
            for lane in sorted(targets):
                self.raw_logger.queue_event("stim", lane=lane,
                                             t_perf=t_perf,
                                             detail=f"trial_id={trial_id}",
                                             hand=self.hand_mode)

    def log_trial(self, trial, outcome: TrialResult, now: float) -> None:
        self._ensure_metric_state()
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
        # Chime on a non-Miss press; otherwise the soft thunk so the
        # patient hears something either way (matches rhythm mode).
        if self.audio:
            try:
                if outcome.label != "Miss":
                    self.audio.play_hit(combo=self.hit_streak)
                elif self.hit_streak > 0:
                    # Only thunk if the miss BREAKS a real streak. A
                    # single isolated miss with no streak just gets
                    # the visual feedback so the audio doesn't nag.
                    self.audio.play_miss()
            except Exception:
                pass
            # A loud trial has now played its feedback at the boosted
            # gain; drop it back so the next non-loud trial is normal.
            self.audio.set_trial_gain(1.0)
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
        # Close the miss-force window: on a miss, bank the summed
        # per-finger peak into the running total; either way disarm the
        # window and keep the snapshot for this trial's CSV row.
        fw_sum, fw_peaks = self._close_force_window(
            outcome.label == "Miss")
        # Block-summary aggregates: RT + wrong-press trial count.
        if outcome.rt_ms is not None:
            self._block_rt_sum += float(outcome.rt_ms)
            self._block_rt_count += 1
        if trial.incorrect_presses:
            self._block_wrong_press_trials += 1
        # Per-lane stats for the Results-screen histograms. Each
        # trial's RT goes onto the TARGET lane's list (so the mean
        # answers "how fast does the patient press finger N when it's
        # the target"). Misses + wrong presses against the target are
        # counted separately so the misclick chart shows where the
        # patient struggled. setdefault-on-self lets test fixtures
        # that build the engine via __new__ (skipping __init__) still
        # call log_trial without an AttributeError.
        if not hasattr(self, "_per_lane_rts"):
            self._per_lane_rts = {}
        if not hasattr(self, "_per_lane_misses"):
            self._per_lane_misses = {}
        if not hasattr(self, "_per_lane_wrong"):
            self._per_lane_wrong = {}
        if not hasattr(self, "_per_lane_peak_force"):
            self._per_lane_peak_force = {}
        if outcome.rt_ms is not None:
            self._per_lane_rts.setdefault(trial.lane, []).append(
                float(outcome.rt_ms))
        if outcome.label == "Miss":
            self._per_lane_misses[trial.lane] = (
                self._per_lane_misses.get(trial.lane, 0) + 1)
        # Each wrong-finger press on this trial counts against the
        # target lane (it's the lane that didn't get hit on time, the
        # patient hit a neighbour by mistake).
        for _wrong_lane, _t in trial.incorrect_presses:
            self._per_lane_wrong[trial.lane] = (
                self._per_lane_wrong.get(trial.lane, 0) + 1)
        # Capture peak force + impulse for the trial. Both are live
        # (finger still down at log_trial time) so we sample the
        # detector's running values. None on a Miss because there's
        # no rising edge.
        peak_force_n_value = self._peak_force_for_lane(trial.lane)
        if peak_force_n_value is not None:
            self._per_lane_peak_force.setdefault(
                trial.lane, []).append(peak_force_n_value)
        impulse_n_value = self._impulse_for_lane(trial.lane)
        if impulse_n_value is not None:
            if not hasattr(self, "_per_lane_impulse"):
                self._per_lane_impulse = {}
            self._per_lane_impulse.setdefault(
                trial.lane, []).append(impulse_n_value)
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
                "age": self.session.age,
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
                "peak_force_n": (
                    f"{peak_force_n_value:.3f}"
                    if peak_force_n_value is not None else ""
                ),
                "impulse_n": (
                    f"{impulse_n_value:.4f}"
                    if impulse_n_value is not None else ""
                ),
                # Protocol phase (pretest/main/aftertest) or empty
                # when no protocol is running. Empty rows don't break
                # parsers that ignore unknown columns.
                "phase": getattr(self, "_current_phase", "") or "",
            }
            # Capture-completeness fields: loudness flag (stimulus
            # property), response window (RT censoring limit), and the
            # all-finger force window for this trial.
            fw_sum_str, fw_peaks_str = self._format_force_window(
                fw_sum, fw_peaks)
            loud = self._loud_trials_by_id.get(trial.trial_id)
            row["loud_trial"] = ("" if loud is None
                                  else ("TRUE" if loud else "FALSE"))
            row["timeout_ms"] = (
                f"{self._last_stim_timeout_ms:.0f}"
                if self._last_stim_timeout_ms is not None else "")
            row["force_window_sum"] = fw_sum_str
            row["force_window_peaks"] = fw_peaks_str
            row["cue_mode"] = getattr(self, "_last_cue_mode", "both")
            sd = getattr(self, "_last_stim_delivered", None)
            row["stim_delivered"] = ("" if sd is None
                                      else ("TRUE" if sd else "FALSE"))
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
        self._ensure_metric_state()
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
        # Hit chime on a real press; combo pitches up with the streak.
        # On a Miss that breaks an existing streak we play the soft
        # thunk so the patient hears the combo-break.
        if self.audio:
            try:
                if label != "Miss":
                    self.audio.play_hit(combo=self.hit_streak)
                elif self.hit_streak > 0:
                    self.audio.play_miss()
            except Exception:
                pass
        if label in ("Miss",):
            self.misses += 1
        else:
            self.hits += 1
        # Per-lane stats for the Results-screen histograms. In rhythm
        # mode `offset_ms` is the signed offset from the beat; we take
        # its absolute value as the "RT" sample since the chart shows
        # press accuracy, not press direction. Misses (note scrolled
        # past without a hit) count against the lane that was meant
        # to be pressed. hasattr guard so __new__-built test engines
        # don't crash here.
        if not hasattr(self, "_per_lane_rts"):
            self._per_lane_rts = {}
        if not hasattr(self, "_per_lane_misses"):
            self._per_lane_misses = {}
        lane = sched_note.note.lane
        if label != "Miss":
            self._per_lane_rts.setdefault(lane, []).append(abs(float(offset_ms)))
            # Capture press time + nearest beat time for the
            # beat_offset_stats summary at finish_block. press_t_s is
            # reconstructed from the note time + offset (offset is
            # press - note, so press = note + offset/1000).
            if not hasattr(self, "_rhythm_press_times_s"):
                self._rhythm_press_times_s = []
                self._rhythm_beat_times_s = []
                self._rhythm_signed_offsets_ms = []
            note_t = float(sched_note.note.t)
            press_t = note_t + (float(offset_ms) / 1000.0)
            self._rhythm_press_times_s.append(press_t)
            self._rhythm_beat_times_s.append(note_t)
            # Signed offset (negative = before the beat, positive =
            # after). Used by the lag-1 autocorrelation that drives
            # the rhythm-mode tempo entrainment index in the summary.
            self._rhythm_signed_offsets_ms.append(float(offset_ms))
        else:
            self._per_lane_misses[lane] = (
                self._per_lane_misses.get(lane, 0) + 1)
        # Close this note's force window and, on a miss, bank the
        # all-finger peak sum (same metric as classic / adaptive). The
        # trial-id guard matters here: at fast tempos the NEXT note's
        # stim may already have re-armed the window by the time this
        # note resolves, in which case the window isn't ours - leave it
        # for the newer note and log empty force cells for this row.
        fw_sum: float | None = None
        fw_peaks: dict[int, float] = {}
        if self._force_window_trial_id == sched_note.index:
            fw_sum, fw_peaks = self._close_force_window(label == "Miss")
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
                "age": self.session.age,
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
                # Peak force on the lane's sensor during the press.
                # None on a no-press Miss (was_pressed=False).
                "peak_force_n": (
                    f"{self._peak_force_for_lane(lane):.3f}"
                    if was_pressed and
                    self._peak_force_for_lane(lane) is not None
                    else ""
                ),
                # Force-time integral over the press window.
                "impulse_n": (
                    f"{self._impulse_for_lane(lane):.4f}"
                    if was_pressed and
                    self._impulse_for_lane(lane) is not None
                    else ""
                ),
                # Protocol phase, matching the classic / adaptive log
                # path. Rhythm typically isn't in a protocol but the
                # column lives in the same trial CSV either way.
                "phase": getattr(self, "_current_phase", "") or "",
            }
            # Capture-completeness fields, mirroring log_trial. The
            # response window in rhythm is the miss_ms classify
            # boundary (offsets beyond it grade as Miss).
            loud = self._loud_trials_by_id.get(sched_note.index)
            row["loud_trial"] = ("" if loud is None
                                  else ("TRUE" if loud else "FALSE"))
            w = getattr(self.mode, "windows", None) if self.mode else None
            miss_ms = getattr(w, "miss_ms", None) if w is not None else None
            row["timeout_ms"] = (f"{float(miss_ms):.0f}"
                                  if miss_ms is not None else "")
            fw_sum_str, fw_peaks_str = self._format_force_window(
                fw_sum, fw_peaks)
            row["force_window_sum"] = fw_sum_str
            row["force_window_peaks"] = fw_peaks_str
            row["cue_mode"] = getattr(self, "_last_cue_mode", "both")
            sd = getattr(self, "_last_stim_delivered", None)
            row["stim_delivered"] = ("" if sd is None
                                      else ("TRUE" if sd else "FALSE"))
            row.update(self._trial_context(streak_before,
                                            song_time_s=song_time))
            self.trial_logger.write(row)
        # Per-lane peak-force + impulse series for the rhythm block
        # summary's force aggregates.
        if was_pressed and label != "Miss":
            if not hasattr(self, "_per_lane_peak_force"):
                self._per_lane_peak_force = {}
            if not hasattr(self, "_per_lane_impulse"):
                self._per_lane_impulse = {}
            imp = self._impulse_for_lane(lane)
            if imp is not None:
                self._per_lane_impulse.setdefault(lane, []).append(imp)
            p = self._peak_force_for_lane(lane)
            if p is not None:
                self._per_lane_peak_force.setdefault(lane, []).append(p)
        self._maybe_resave_metadata()

    def log_rhythm_unmatched(self, lane: int, now: float) -> None:
        # Block-summary counter so the analyst sees wrong-finger
        # activity without scanning raw.csv.
        self._block_rhythm_spurious_presses += 1
        # Per-lane misclick chart counts unmatched presses against
        # the lane the patient pressed. So if they keep pressing
        # the middle finger when there's no note for it, the chart
        # will show a big spike on middle. hasattr guard same as
        # log_trial's, for __new__-built test fixtures.
        if not hasattr(self, "_per_lane_wrong"):
            self._per_lane_wrong = {}
        self._per_lane_wrong[lane] = (
            self._per_lane_wrong.get(lane, 0) + 1)
        if self.raw_logger:
            self.raw_logger.queue_event("rhythm_spurious_press", lane=lane,
                                         t_perf=now, hand=self.hand_mode)
        # Score penalty for the wrong-lane press in rhythm mode. Each
        # unmatched press costs `scoring.wrong_press_penalty` (floored
        # at zero so the score never goes negative).
        self.apply_wrong_press_penalty()
        # Audio: combo-break thunk so a wrong-lane press has a
        # distinct aural cue without being harsh.
        if self.audio:
            try:
                self.audio.play_miss()
            except Exception:
                pass
        # Visual feedback: flash the lane red so the patient can see
        # exactly which finger fired wrong.
        rs = self._screens.get("rhythm")
        if rs and hasattr(rs, "flash_lane"):
            try:
                rs.flash_lane(lane, self.theme.lane_miss, 0.5, now)
            except Exception:
                pass

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
