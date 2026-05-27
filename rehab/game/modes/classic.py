"""Classic fixed-cadence mode. Press the lit lane within the timeout window."""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

import pygame

from ...hardware.fsr_detector import PressEvent
from ..scoring import ScoreConfig, classify
from ._keys import keymap_for_hand, resolve_key

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


@dataclass
class PendingTrial:
    trial_id: int
    lane: int
    stim_t_perf: float
    keys_pressed: list[int]
    incorrect_presses: list[tuple[int, float]]   # (wrong_lane, t_perf)


class ClassicMode:
    name = "Classic"

    def __init__(self, engine: "GameEngine",
                 pattern: list[int], repeat_count: int,
                 trigger_interval_s: float, timeout_s: float,
                 early_window_s: float, score_cfg: ScoreConfig) -> None:
        self.engine = engine
        self.pattern = pattern
        self.repeat_count = repeat_count
        self.trigger_interval = trigger_interval_s
        self.timeout = timeout_s
        self.early_window = early_window_s
        self.score_cfg = score_cfg
        # Build full sequence by repeating the pattern.
        self.sequence = (pattern * repeat_count)
        self.idx = 0
        self.active: PendingTrial | None = None
        self.last_trigger_t = -1.0
        self.trial_counter = 0
        self._presses: deque[PressEvent] = deque()

    def queue_press(self, ev: PressEvent) -> None:
        self._presses.append(ev)

    def on_resume(self, pause_dur: float) -> None:
        # Slide every in-flight timestamp forward so a pause doesn't make
        # the active trial instantly time out or the next stim look overdue.
        if self.active is not None:
            self.active.stim_t_perf += pause_dur
        if self.last_trigger_t > 0:
            self.last_trigger_t += pause_dur

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN:
            # Keyboard always accepts presses as a backup, even when an
            # Arduino is plugged in. The old `not provides_samples`
            # guard meant a busted auto-detect (e.g. Mac picking
            # /dev/cu.Bluetooth-Incoming-Port as if it were an Arduino)
            # left the therapist with no working input. Now FDSA / JKL;
            # are wired in either way and the FSR detector's press
            # events come in alongside via _on_press.
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

        if self.active is None and self.idx < len(self.sequence):
            if self.last_trigger_t < 0 or (now - self.last_trigger_t) >= self.trigger_interval:
                self._fire(now)

        if self.active is not None:
            if (now - self.active.stim_t_perf) > self.timeout:
                self._finish(None, now)

        if self.idx >= len(self.sequence) and self.active is None:
            self.engine.finish_block()

    def _fire(self, now: float) -> None:
        lane = self.sequence[self.idx]
        self.trial_counter += 1
        self.active = PendingTrial(
            trial_id=self.trial_counter,
            lane=lane,
            stim_t_perf=now,
            keys_pressed=[],
            incorrect_presses=[],
        )
        self.idx += 1
        self.last_trigger_t = now
        self.engine.on_stim(lane, self.trial_counter, now)

    def _handle_press(self, ev: PressEvent, now: float) -> None:
        if self.active is None:
            return
        self.active.keys_pressed.append(ev.lane)
        if ev.lane == self.active.lane:
            self._finish(ev, now)
        else:
            # Score penalty fires only on the FIRST wrong press of the
            # trial. Subsequent wrong presses still get logged for
            # analysis but don't keep subtracting (otherwise a patient
            # mashing all four fingers would dig themselves into a hole
            # they can't recover from).
            first_wrong = not self.active.incorrect_presses
            self.active.incorrect_presses.append((ev.lane, ev.t_perf))
            if first_wrong:
                self.engine.apply_wrong_press_penalty()

    def _finish(self, ev: PressEvent | None, now: float) -> None:
        if self.active is None:
            return
        rt_ms = None
        if ev is not None:
            rt_ms = (ev.t_perf - self.active.stim_t_perf) * 1000.0
        outcome = classify(rt_ms, self.score_cfg)
        self.engine.log_trial(self.active, outcome, now)
        self.active = None
