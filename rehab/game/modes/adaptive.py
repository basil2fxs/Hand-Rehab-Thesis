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
                 start_bpm: float = 80.0,
                 adaptive_cfg: AdaptiveConfig | None = None,
                 seed: int = 0) -> None:
        self.engine = engine
        self.score_cfg = score_cfg
        self.timeout = timeout_s
        self.early_window = early_window_s
        self.total_trials = total_trials
        self.block_size = block_size
        # num_lanes is 4 for unilateral, 8 for bilateral. AdaptiveEngine
        # generates sequences of those indices.
        self.adapter = AdaptiveEngine(
            num_lanes=num_lanes, cfg=adaptive_cfg or AdaptiveConfig(),
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
                    self.queue_press(PressEvent(
                        lane=lane, t_perf=time.perf_counter(),
                        value=0, baseline=0.0,
                        hand=self.engine.hand_mode,
                    ))

    def update(self, dt: float) -> None:
        now = time.perf_counter()
        while self._presses:
            self._handle_press(self._presses.popleft(), now)

        if self.active is None and self.completed < self.total_trials:
            # Cadence comes from the current BPM. When the engine slowed
            # the patient down it'll widen automatically.
            cadence = 60.0 / max(20.0, self.adapter.bpm)
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
        # Regenerate when current block is exhausted.
        if self.seq_idx >= len(self.sequence):
            self.adapter.next_bpm()
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
            return
        self.active.keys_pressed.append(ev.lane)
        if ev.lane == self.active.lane:
            self._finish(ev, now)
        else:
            # See classic.py for why we only penalise the FIRST wrong
            # press per trial.
            first_wrong = not self.active.incorrect_presses
            self.active.incorrect_presses.append((ev.lane, ev.t_perf))
            if first_wrong:
                self.engine.apply_wrong_press_penalty()

    # Quality weights tell the adapter how good a press was, not just hit/miss.
    # A Great is a full-credit press, a Late only counts a quarter so it
    # doesn't trick the system into thinking the patient's coping fine.
    _QUALITY = {
        "Great": 1.0,
        "Good":  0.75,
        "Late":  0.25,
        "Early": 0.0,
        "Miss":  0.0,
    }

    def _finish(self, ev: PressEvent | None, now: float) -> None:
        if self.active is None:
            return
        rt_ms = None
        if ev is not None:
            rt_ms = (ev.t_perf - self.active.stim_t_perf) * 1000.0
        outcome = classify(rt_ms, self.score_cfg)
        quality = self._QUALITY.get(outcome.label, 0.0)
        # Feed the adapter then immediately recompute BPM so the next trial
        # already reflects whether this was a hit or a miss. Without this
        # the system only reacted once per block (every 4 trials) which
        # felt sluggish.
        self.adapter.record(self.active.lane, outcome.label != "Miss",
                             rt_ms, quality=quality)
        self.adapter.next_bpm()
        self.engine.log_trial(self.active, outcome, now)
        self.active = None
        self.completed += 1
