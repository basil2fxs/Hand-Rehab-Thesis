"""Adaptive mode (Thread 1). Regenerates the sequence + BPM from the
AdaptiveEngine every block_size trials."""
from __future__ import annotations

import logging
import random
import time
from collections import deque
from typing import TYPE_CHECKING

import pygame

from ...analytics.adaptive import AdaptiveConfig, AdaptiveEngine
from ...hardware.fsr_detector import PressEvent
from ..scoring import ScoreConfig, classify
from .classic import PendingTrial
from ._keys import keymap_for_hand, resolve_key

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


class AdaptiveMode:
    name = "Adaptive"

    def __init__(self, engine: "GameEngine", total_trials: int,
                 block_size: int, score_cfg: ScoreConfig,
                 timeout_s: float, early_window_s: float,
                 num_lanes: int = 4,
                 min_finger_share: float = 0.15,
                 start_bpm: float = 80.0,
                 adaptive_cfg: AdaptiveConfig | None = None,
                 seed: int = 0) -> None:
        self.engine = engine
        self.score_cfg = score_cfg
        self.timeout = timeout_s
        # Stored for constructor-signature parity with the other cadence
        # modes (engine.begin_adaptive_block passes game.early_window_s
        # through), but nothing in this mode reads it. Unlike classic/
        # reaction there is no "pressed before the cue but inside a
        # grace window" check here -- an early press just falls into
        # _handle_press's active-is-None branch and eats the idle-press
        # penalty like any other between-trial press. Kept as a stored
        # (unused) field rather than dropped so a future early-window
        # gate has a natural home, and so this does not silently start
        # accepting an arbitrary kwarg.
        self.early_window = early_window_s
        self.total_trials = total_trials
        self.block_size = block_size
        # num_lanes is 4 for unilateral, 8 for bilateral. AdaptiveEngine
        # generates sequences of those indices.
        self.adapter = AdaptiveEngine(
            num_lanes=num_lanes, cfg=adaptive_cfg or AdaptiveConfig(),
            min_finger_share=min_finger_share,
            # 8 lanes means two hands, so the scheduler keeps them equal.
            hands_split=(num_lanes >= 8),
        )
        self.adapter.bpm = start_bpm
        self.rng = random.Random(seed)
        self.sequence = self.adapter.generate_sequence(block_size, self.rng)
        self.seq_idx = 0
        self.completed = 0
        self.trial_counter = 0
        self.active: PendingTrial | None = None
        self.last_trigger_t = -1.0
        self._presses: deque[PressEvent] = deque()
        # Tracked so _finish can tell a recovery entry/exit apart from
        # "still in recovery" or "still not in recovery" -- see the
        # regen-on-transition note there.
        self._last_recovery = self.adapter.in_recovery

    def queue_press(self, ev: PressEvent) -> None:
        self._presses.append(ev)

    @property
    def current_timeout_s(self) -> float:
        # Engine reads this when arming the lane's timing bar so the bar
        # length matches the actual press window the adapter is using.
        return self.adapter.current_timeout_s

    def on_resume(self, pause_dur: float) -> None:
        # Slide active trial and cadence timestamps forward by the pause length.
        if self.active is not None:
            self.active.stim_t_perf += pause_dur
        if self.last_trigger_t > 0:
            self.last_trigger_t += pause_dur

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN:
            # Keyboard is always-on as a backup, even with an Arduino
            # active. See classic.py for the reasoning. The keymap pick
            # is hand-aware: right -> JKL;, left -> FDSA, both -> the
            # bilateral 8-key map.
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
        now = time.perf_counter()
        while self._presses:
            self._handle_press(self._presses.popleft(), now)

        if self.active is None and self.completed < self.total_trials:
            # Cadence comes from the current BPM. When the engine slowed
            # the patient down it'll widen automatically. Floor at the
            # adapter's own configured bpm_min, not a stale literal --
            # config/default.yaml sets bpm_min=10 for a 6 s crawl gap
            # for severely impaired patients; clamping to 20 here cut
            # that floor in half and made the logged bpm_at_trial (10)
            # lie about the cadence actually presented (20 BPM).
            cadence = 60.0 / max(self.adapter.cfg.bpm_min, self.adapter.bpm)
            if self.last_trigger_t < 0 or (now - self.last_trigger_t) >= cadence:
                self._fire(now)

        if self.active is not None:
            # Timeout shrinks at fast BPM and grows at slow BPM so a slow
            # pace doesn't punish patients who genuinely need more time.
            current_timeout = self.adapter.current_timeout_s
            if (now - self.active.stim_t_perf) > current_timeout:
                self._finish(None, now)

        if self.completed >= self.total_trials and self.active is None:
            self.engine.finish_block()

    def _fire(self, now: float) -> None:
        # Regenerate when current block is exhausted. next_bpm() is NOT
        # called here -- _finish already calls it once per trial, right
        # after adapter.record(), so BPM is current the moment the last
        # trial of a sequence closes. Calling it again here doubled up
        # right at every block_size boundary (two next_bpm() calls
        # between two consecutive stims, on no new data the second
        # time), diluting the "single sample can't yank BPM around"
        # rate limit next_bpm() documents for itself.
        if self.seq_idx >= len(self.sequence):
            self.sequence = self.adapter.generate_sequence(self.block_size, self.rng)
            self.seq_idx = 0
            log.info("Adaptive block: bpm=%.0f weights=%s",
                     self.adapter.bpm,
                     [f"{w:.2f}" for w in self.adapter.lane_weights()])
        lane = self.sequence[self.seq_idx]
        self.trial_counter += 1
        self.active = PendingTrial(
            trial_id=self.trial_counter,
            lane=lane,
            stim_t_perf=now,
            keys_pressed=[],
            incorrect_presses=[],
        )
        self.seq_idx += 1
        self.last_trigger_t = now
        self.engine.on_stim(lane, self.trial_counter, now)

    def _handle_press(self, ev: PressEvent, now: float) -> None:
        if self.active is None:
            # Between-trial spam still costs the idle-press penalty so
            # mashing between stims isn't free. See classic.py for the
            # rationale; same mechanism here.
            self.engine.apply_idle_press_penalty()
            # apply_idle_press_penalty only bumps a per-block COUNT
            # (_block_idle_presses); no lane or timestamp for any one
            # idle press reaches trials.csv or raw.csv, so a press just
            # before a stim (anticipation) is indistinguishable from
            # one mid-gap (mashing) after the fact. Queue the raw event
            # here where the lane/time are actually known.
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "idle_press", lane=ev.lane, t_perf=ev.t_perf,
                    detail=f"trial_id={self.trial_counter}",
                    hand=ev.hand)
            return
        self.active.keys_pressed.append(ev.lane)
        if ev.lane == self.active.lane:
            self._finish(ev, now)
        else:
            # Every wrong press costs - see classic.py for why we
            # changed from first-only to per-press penalties (it was
            # the dominant strategy: mash everything, eat one small
            # penalty, take the hit).
            self.active.incorrect_presses.append((ev.lane, ev.t_perf))
            self.engine.apply_wrong_press_penalty()

    # Quality weights tell the adapter how good a press was, not just hit/miss.
    # A Perfect or a Great is full-credit (classify() returns "Perfect"
    # for the fastest presses, checked before "Great" -- missing it here
    # let the .get(..., 0.0) default score the best possible press the
    # same as a Miss, throttling BPM for a patient who was doing great).
    # A Late only counts a quarter so it doesn't trick the system into
    # thinking the patient's coping fine.
    _QUALITY = {
        "Perfect": 1.0,
        "Great": 1.0,
        "Good":  0.75,
        "Late":  0.25,
        "Early": 0.0,
        "Miss":  0.0,
    }

    # classify() (shared across every cadence mode) has no lower RT
    # bound, so a sub-cut press reads as a clean Perfect exactly like a
    # genuinely fast, accurate one. Reaction mode screens these out
    # before they're even scored (its own anticipation_cut_ms, default
    # 100ms, Basner and Dinges 2011: a press that fast cannot be a
    # response to the stimulus). The label/score/rt_ms this mode logs
    # stay as classify() said -- the notebook's own exclusion_flags
    # already drops sub-100ms cued rows from every headline stat by
    # time_difference_ms, so the CSV needs the real number kept intact.
    # What must not happen is the adapter treating a mash-speed press
    # as a quality=1.0 "acing it" signal: that is exactly the reading
    # that would speed the pace up off blind mashing.
    ANTICIPATION_MS = 100.0

    def _quality_for(self, outcome_label: str, rt_ms: float | None) -> float:
        if rt_ms is not None and rt_ms < self.ANTICIPATION_MS:
            return 0.0
        return self._QUALITY.get(outcome_label, 0.0)

    def _finish(self, ev: PressEvent | None, now: float) -> None:
        if self.active is None:
            return
        rt_ms = None
        if ev is not None:
            rt_ms = (ev.t_perf - self.active.stim_t_perf) * 1000.0
        outcome = classify(rt_ms, self.score_cfg)
        # Wrong-press => Miss. Critical for adaptive mode in particular:
        # the adapter weights weak fingers by their MISS rate, so a
        # fumble-then-correct trial currently masked the struggle and
        # the engine never picked that finger more often. Now the
        # adapter sees the miss, the lane gets weakness bias on the
        # next sequence, and the patient is helped through it.
        if self.active.incorrect_presses:
            from ..scoring import TrialResult
            outcome = TrialResult(
                label="Miss",
                points=self.score_cfg.miss_points,
                rt_ms=rt_ms,
            )
        quality = self._quality_for(outcome.label, rt_ms)
        # Feed the adapter then immediately recompute BPM so the next trial
        # already reflects whether this was a hit or a miss. Without this
        # the system only reacted once per block (every 4 trials) which
        # felt sluggish.
        self.adapter.record(self.active.lane, outcome.label != "Miss",
                             rt_ms, quality=quality)
        self.adapter.next_bpm()
        # engine.log_trial runs _update_streak, which is what actually
        # calls adapter.enter_recovery()/exit_recovery() (3 consecutive
        # misses in, 1 hit out). Check for the transition straight
        # after, not just at a block_size boundary.
        self.engine.log_trial(self.active, outcome, now)
        self.active = None
        self.completed += 1
        now_recovery = self.adapter.in_recovery
        if now_recovery != self._last_recovery:
            # enter_recovery's own docstring promises biasing "the next
            # lane pick" toward the strongest finger, and exit_recovery
            # promises returning to normal weighting -- both mean NOW,
            # not whenever the current 4-trial sequence happens to run
            # out. Discard whatever is left of it so the next _fire()
            # regenerates from the weights that are current as of this
            # trial closing.
            self.seq_idx = len(self.sequence)
            self._last_recovery = now_recovery
