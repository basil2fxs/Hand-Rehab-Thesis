"""Mirror mode. Same-finger bilateral training.

Both hands' copies of the same finger fire at once and the trial
only counts when both presses arrive inside the timing window. The
RT used for scoring is the LATER of the two presses, because the
clinical signal we want is "did the patient produce the bilateral
movement together" rather than "how fast was the strong side".

Mirror therapy literature (Ramachandran 1995, Altschuler 1999) says
the unaffected hand drags the affected one along via shared motor
representations, so the protocol wants synchronous bimanual movement.
This mode forces that pattern.

Internally this mode runs the same challenge-point adaptive engine
that AdaptiveMode uses, just in 4-finger space (the same finger
fires on both hands so there's no need to address the 8-lane
bilateral space). That means the cadence speeds up when the patient
is acing the bimanual coordination, slows down when they struggle,
and biases the next finger pick toward the weaker side so weak
fingers get more reps. Order of which finger fires next is random
(weakness-weighted), not the old deterministic index, middle, ring,
little sweep.
"""
from __future__ import annotations

import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from ...analytics.adaptive import AdaptiveConfig, AdaptiveEngine
from ...hardware.fsr_detector import PressEvent
from ..scoring import ScoreConfig, classify
from ._keys import keymap_for_hand, resolve_key

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


@dataclass
class PendingMirrorTrial:
    """One mirror trial: two target lanes, two presses required.
    finger is the within-hand finger index (0..3). The target lane
    pair is (finger, finger + 4) on the engine's global numbering."""
    trial_id: int
    finger: int
    stim_t_perf: float
    # Per-side press timestamps. None until that side has come in.
    right_press_t: float | None = None
    left_press_t: float | None = None
    # Each side's record of presses (used for the incorrect-press
    # bookkeeping when the patient hits a neighbouring finger first).
    keys_pressed: list[int] = field(default_factory=list)
    incorrect_presses: list[tuple[int, float]] = field(default_factory=list)

    def lane(self) -> int:
        """Engine-format primary lane (right-hand copy). log_trial
        keys per-lane stats on this so the per-finger histogram on
        Results still works in mirror mode."""
        return self.finger


class MirrorMode:
    """Bilateral training driven by the adaptive challenge-point engine.

    Both same-finger lanes light up together. Cadence + timeout are
    derived from the adapter's BPM so the game speeds up when the
    patient is acing the bimanual coordination and slows down when
    they're struggling. Finger order is weakness-weighted random:
    the patient's weaker fingers come up more often so they get more
    reps, not the deterministic 1, 2, 3, 4 sweep the original mirror
    mode used.

    `trigger_interval_s` and `timeout_s` are kept on the signature so
    test callers that don't set up an adapter still get fixed timing.
    When `adaptive_cfg` is provided (the engine's default path), they
    are used as the floor on the first trial and after that the
    adapter takes over.
    """

    name = "Mirror"

    def __init__(self, engine: "GameEngine",
                 pattern: list[int], repeat_count: int,
                 trigger_interval_s: float, timeout_s: float,
                 early_window_s: float, score_cfg: ScoreConfig,
                 adaptive_cfg: AdaptiveConfig | None = None,
                 start_bpm: float = 24.0,
                 seed: int = 0) -> None:
        # Pattern is a list of within-hand finger indices (0..3), not
        # global lanes, because mirror always targets both hands.
        # Anything outside 0..3 is dropped at construction time so a
        # config typo doesn't crash mid-block.
        self.engine = engine
        self.pattern = [int(f) for f in pattern if 0 <= int(f) <= 3]
        if not self.pattern:
            # Fall back to the default index, middle, ring, little
            # sweep if the config left us with nothing usable.
            self.pattern = [0, 1, 2, 3]
        self.repeat_count = repeat_count
        # Static fallbacks used when no adaptive engine is configured
        # (some test paths). With an adapter the live values are read
        # from adapter.bpm + adapter.current_timeout_s.
        self.trigger_interval = trigger_interval_s
        self.timeout = timeout_s
        self.early_window = early_window_s
        self.score_cfg = score_cfg
        # Adapter operates in 4-finger space because mirror always
        # fires the same finger on both hands. We do NOT use the full
        # 8-lane bilateral space here: there's nothing meaningful for
        # the weakness bias to learn about lane 4 vs lane 0, since
        # they fire together every trial.
        self.adapter = AdaptiveEngine(
            num_lanes=4, cfg=adaptive_cfg or AdaptiveConfig(),
        )
        self.adapter.bpm = max(self.adapter.cfg.bpm_min,
                                min(self.adapter.cfg.bpm_max, start_bpm))
        self.rng = random.Random(seed)
        # Trial budget stays the same as the old contract: pattern
        # length times repeat count. Therapists who set repeat_count=8
        # with the 4-finger default still get a 32-trial block, just
        # in random order instead of 0, 1, 2, 3 four times over.
        self._total_trials = len(self.pattern) * repeat_count
        self.completed = 0
        self.active: PendingMirrorTrial | None = None
        self.last_trigger_t = -1.0
        self.trial_counter = 0
        self._presses: deque[PressEvent] = deque()

    @property
    def total_trials(self) -> int:
        # Used by the gameplay HUD's progress bar.
        return self._total_trials

    @property
    def current_timeout_s(self) -> float:
        """Engine reads this when arming the lane's timing bar so the
        bar length tracks the adapter's current press window. Falls
        back to the fixed timeout if the adapter hasn't started yet."""
        try:
            return self.adapter.current_timeout_s
        except Exception:
            return self.timeout

    def queue_press(self, ev: PressEvent) -> None:
        self._presses.append(ev)

    def on_resume(self, pause_dur: float) -> None:
        # Slide every in-flight timestamp forward so a pause doesn't
        # time out the active trial or make the next stim look
        # overdue. Same logic as classic.py.
        if self.active is not None:
            self.active.stim_t_perf += pause_dur
            if self.active.right_press_t is not None:
                self.active.right_press_t += pause_dur
            if self.active.left_press_t is not None:
                self.active.left_press_t += pause_dur
        if self.last_trigger_t > 0:
            self.last_trigger_t += pause_dur

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type != pygame.KEYDOWN:
            return
        # Mirror always runs with hand_mode="both", so the bilateral
        # keymap covers both hands.
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
        # Cadence is BPM-derived: faster adapter BPM = shorter gap
        # between stims. Falls back to the fixed trigger_interval when
        # the adapter is absent (test paths). max(1.0, bpm) so a
        # silly config can't divide by zero.
        cadence = 60.0 / max(1.0, self.adapter.bpm)
        if self.active is None and self.completed < self.total_trials:
            if (self.last_trigger_t < 0
                    or (now - self.last_trigger_t) >= cadence):
                self._fire(now)
        # Time out the in-flight trial. Press window also tracks BPM:
        # slower pace = more time per press. If one or both sides
        # never arrived, _finish with ev=None gets a Miss outcome.
        if self.active is not None:
            window = self.current_timeout_s
            if (now - self.active.stim_t_perf) > window:
                self._finish(now)
        # Block done when the budget is exhausted and no trial is
        # still waiting on a press.
        if self.completed >= self.total_trials and self.active is None:
            self.engine.finish_block()

    def _pick_finger(self) -> int:
        """Weakness-weighted random pick constrained to the eligible
        finger pool from `pattern`. The adapter's pick_lane returns
        any of 0..3 weighted by hit-rate EMA; if it picks a finger
        that's not in `pattern` (therapist asked for a subset like
        [0, 1] only), we retry up to a few times then fall back to a
        uniform pick over the eligible set."""
        eligible = set(self.pattern)
        for _ in range(8):
            pick = self.adapter.pick_lane(self.rng)
            if pick in eligible:
                return pick
        # Uniform fallback. Happens when the pattern is a small subset
        # AND the adapter heavily weights an excluded finger.
        return self.rng.choice(list(eligible))

    def _fire(self, now: float) -> None:
        finger = self._pick_finger()
        self.trial_counter += 1
        self.active = PendingMirrorTrial(
            trial_id=self.trial_counter,
            finger=finger,
            stim_t_perf=now,
        )
        self.last_trigger_t = now
        # Fire both same-finger lanes simultaneously. Right=finger,
        # left=finger+4 under the engine's global lane numbering.
        right_lane = finger
        left_lane = finger + 4
        self.engine.on_stim_multi(
            [right_lane, left_lane],
            self.trial_counter,
            now,
        )

    def _handle_press(self, ev: PressEvent, now: float) -> None:
        if self.active is None:
            # Between-trial spam costs the idle press penalty, same
            # rule as classic / adaptive.
            self.engine.apply_idle_press_penalty()
            return
        self.active.keys_pressed.append(ev.lane)
        finger = self.active.finger
        right_target = finger
        left_target = finger + 4
        # Correct side handling: record the press timestamp on the
        # right or left slot. If a side already had a press, ignore
        # the duplicate so a patient who taps twice doesn't trigger
        # the "wrong press" branch.
        if ev.lane == right_target:
            if self.active.right_press_t is None:
                self.active.right_press_t = ev.t_perf
        elif ev.lane == left_target:
            if self.active.left_press_t is None:
                self.active.left_press_t = ev.t_perf
        else:
            # Wrong finger on either hand. Same per-press penalty
            # rule as classic / adaptive: every wrong press costs
            # something so spamming doesn't pay.
            self.active.incorrect_presses.append((ev.lane, ev.t_perf))
            self.engine.apply_wrong_press_penalty()
            return
        # Both sides in? Finish the trial now. The RT used for
        # classify is the LATER of the two presses so the score
        # reflects synchronisation quality, not just the strong-side
        # reaction.
        if (self.active.right_press_t is not None
                and self.active.left_press_t is not None):
            self._finish(now)

    # Same quality table AdaptiveMode uses. A Great press counts as
    # full credit toward the lane's hit-rate EMA, a Late only counts
    # a quarter so a session of all-Lates doesn't fool the controller
    # into thinking the patient is coping fine.
    _QUALITY = {
        "Great": 1.0,
        "Good":  0.75,
        "Late":  0.25,
        "Early": 0.0,
        "Miss":  0.0,
    }

    def _finish(self, now: float) -> None:
        if self.active is None:
            return
        # Both sides in -> RT = later press minus stim. One side
        # missing -> rt_ms = None -> classify returns Miss.
        if (self.active.right_press_t is not None
                and self.active.left_press_t is not None):
            later_t = max(self.active.right_press_t,
                           self.active.left_press_t)
            rt_ms = (later_t - self.active.stim_t_perf) * 1000.0
        else:
            rt_ms = None
        outcome = classify(rt_ms, self.score_cfg)
        # Wrong-press trials downgrade to Miss, matching classic /
        # adaptive's clean-trial-signal behaviour.
        if self.active.incorrect_presses:
            from ..scoring import TrialResult
            outcome = TrialResult(
                label="Miss",
                points=self.score_cfg.miss_points,
                rt_ms=rt_ms,
            )
        # Feed the adapter then immediately recompute BPM so the next
        # trial uses the new pace. Same pattern AdaptiveMode follows.
        # The adapter sees finger-space lane (0..3) which matches what
        # _pick_finger draws from, so the weakness bias stays
        # consistent with how trials are scheduled.
        finger = self.active.finger
        quality = self._QUALITY.get(outcome.label, 0.0)
        self.adapter.record(
            finger, outcome.label != "Miss", rt_ms, quality=quality,
        )
        self.adapter.next_bpm()
        # log_trial expects an object with .lane, .stim_t_perf,
        # .keys_pressed, .incorrect_presses. Build a lightweight
        # adapter so the existing logging path works without
        # special-casing mirror mode in the engine.
        from .classic import PendingTrial as _LogTrial
        log_obj = _LogTrial(
            trial_id=self.active.trial_id,
            lane=self.active.lane(),
            stim_t_perf=self.active.stim_t_perf,
            keys_pressed=list(self.active.keys_pressed),
            incorrect_presses=list(self.active.incorrect_presses),
        )
        self.engine.log_trial(log_obj, outcome, now)
        self.active = None
        self.completed += 1
