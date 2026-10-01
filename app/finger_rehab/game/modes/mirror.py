"""Mirror mode. Same-finger bilateral synchronous pressing.

Both hands' copies of the same finger fire at once and the trial
only counts when both presses arrive inside the timing window AND
within max_async_ms of each other. The RT used for scoring is the
LATER of the two presses, because the signal wanted is "did the
player produce the bilateral movement together" rather than "how
fast was the strong side".

WHAT IT IS. Simultaneous bilateral training of homologous fingers:
both hands do the same thing at the same time, independently, which
is the Cochrane definition (Coupar et al. 2010). It is NOT mirror
therapy. Mirror therapy needs the mirror: in Ramachandran and
Rogers-Ramachandran (1996) a patient making mirror-symmetric
movements with his eyes shut felt the phantom stay frozen, and it
moved only when he looked in the mirror, so that paper is the origin
of mirror therapy and not a source for "the unaffected hand drags
the affected one along". That idea is the bilateral-training
rationale (McCombe Waller and Whitall 2008). Mirror is in fact the
comparison condition in mirror-therapy trials: against the same
movements with both limbs in view, mirror therapy's effect was not
significant (Thieme et al. 2018). Bilateral arm training itself was
no better than usual care or one-arm training in the Cochrane review
and overview (Coupar et al. 2010; Pollock et al. 2014), and BATRAC
was not superior to dose-matched exercise in a 111-person trial
(Whitall et al. 2011). So the mode measures bimanual synchrony and
delivers bilateral practice; no therapeutic effect is claimed (the
Mirror deep review of 1 October 2026, docs/research/deep/mirror.md).

HEALTHY TIMING. Healthy hands press about 19 to 24 ms apart on a
1 kHz glove (Bonzano et al. 2008, 2013), and no hand is known to
lead in discrete presses (a group mean of -0.7 ms in bimanual
tapping, Helmuth and Ivry 1996; individual leads both ways, Shen and
Franz 2005), so the 350 ms gate below is nearly inert for a healthy
pair (0.4 percent of simulated trials) and catches only a pair that
landed nowhere near together.

Internally this mode runs the same challenge-point adaptive engine
that AdaptiveMode uses, in 4-finger space: the same finger fires on
both hands every trial, so the hands are equal by construction and
only the finger split needs managing. The pace speeds up when the
pair keeps landing and slows when it does not, and the next finger
is a weakness-weighted pick over finger PAIRS (a pair failing
because one hand is weak is cued more, but nothing targets a hand).
Because the rest after a trial is capped at 1 s from its close, the
pace here mainly sets the press WINDOW (0.9 of 60/BPM), not the cue
rate: at the 24 BPM start the window is 2.25 s and cues come about
1.5 s apart. A faster pace drops the widest pairs as one-sided
misses, so the gap shrinks without the hands changing (simulation),
which is why the window and the one-sided count travel with every
gap.

Rules shared with Adaptive since 1 October 2026: a press under
ANTICIPATION_MS after the cue is not a response to it on either
hand; a press on the finished trial's finger before the next cue is
that trial's late answer, logged and not charged as an idle press; a
pair cut short because a board dropped is the rig's (device_drop)
and never reaches the pace controller.
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
    # Under 100 ms after the cue nothing has been perceived, so a press
    # there is not a response to it (Reaction's and Adaptive's rule).
    ANTICIPATION_MS = 100.0

    def __init__(self, engine: "GameEngine",
                 pattern: list[int], repeat_count: int,
                 trigger_interval_s: float, timeout_s: float,
                 early_window_s: float, score_cfg: ScoreConfig,
                 adaptive_cfg: AdaptiveConfig | None = None,
                 start_bpm: float = 24.0,
                 seed: int = 0,
                 min_finger_share: float = 0.15,
                 max_async_ms: float = 350.0) -> None:
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
        self.seed = int(seed)
        self.rng = random.Random(seed)
        self._floor = None
        self.min_finger_share = min_finger_share
        # Fixed-ms (not BPM-scaled) bound on how far apart the two
        # presses may land and still count as a synchronised hit. The
        # press WINDOW is BPM-derived and widens to 5.4 s at the BPM
        # floor, which is exactly when a struggling patient needs the
        # togetherness bound most, so this second, fixed gate is what
        # actually enforces the docstring's "forces synchronous
        # bimanual movement" claim. 350 ms sits comfortably above
        # normal bimanual asynchrony (tens of ms) while still catching
        # a pair that landed nowhere near together.
        self.max_async_ms = max_async_ms
        # Trial budget: DISTINCT finger count times repeat count, not
        # raw pattern length. _pick_finger already reduces to
        # sorted(set(self.pattern)) -- the weakness-weighted picker has
        # no concept of "this finger appears twice in the config list",
        # unlike classic mode's pattern * repeat_count sequence, where
        # a repeated entry directly weights that finger. Before this
        # fix, pattern=[0, 0, 1, 2] silently bought a longer block
        # (4 * repeat_count trials) with zero extra weighting toward
        # finger 0, since the picker only ever draws from {0, 1, 2}.
        # Therapists who set repeat_count=8 with the 4-finger default
        # still get a 32-trial block, just in random order instead of
        # 0, 1, 2, 3 four times over.
        self._total_trials = len(set(self.pattern)) * repeat_count
        self.completed = 0
        self.active: PendingMirrorTrial | None = None
        self.last_trigger_t = -1.0
        # Perf-counter time the previous trial FINISHED (both presses in,
        # or timed out). The inter-trial rest is measured from here, not
        # from stim onset, so a patient who completes a trial quickly at a
        # slow BPM isn't left waiting out the rest of the cadence with
        # empty lanes. None means no trial has finished yet.
        self._last_finish_t: float | None = None
        self.trial_counter = 0
        self._presses: deque[PressEvent] = deque()
        # What the block did, for block_stats and the analysis.
        self.start_bpm = float(self.adapter.bpm)
        self._prev_finger: int | None = None
        self._bpm_trace: list[float] = []
        self._window_trace_ms: list[float] = []
        self._cues = [0, 0, 0, 0]
        self._hits = [0, 0, 0, 0]
        self._one_sided = 0
        self._gated = 0
        self._late_presses = 0
        self._anticipations = 0
        self._dropped = 0
        self._recoveries = 0
        self._last_recovery = bool(getattr(self.adapter, "in_recovery",
                                           False))
        self._peaks = {"right": [], "left": []}

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
        # Slide the finish anchor too so the inter-trial rest doesn't
        # elapse during the pause and snap a new stim up the instant
        # the patient resumes.
        if self._last_finish_t is not None:
            self._last_finish_t += pause_dur

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
                t_perf = time.perf_counter()
                self.queue_press(PressEvent(
                    lane=lane, t_perf=t_perf,
                    value=0, baseline=0.0,
                    hand=self.engine.hand_mode,
                ))
                # Keyboard presses bypass engine._on_press (the FSR
                # detector path), which is the only place raw.csv
                # normally gets a "press" event, so a keyboard-only
                # mirror session's raw.csv had zero press/release rows
                # -- a false-start / anticipatory press between trials
                # was invisible to the data. detail="keyboard" marks
                # it as coming from this fallback path rather than a
                # detector, in case a session ever mixes both (Arduino
                # attached, keyboard kept live as backup).
                raw_logger = getattr(self.engine, "raw_logger", None)
                if raw_logger:
                    raw_logger.queue_event(
                        "press", lane=lane, t_perf=t_perf,
                        hand=self.engine.hand_mode, detail="keyboard")

    # Hard cap on the rest between finishing one trial and the next
    # stim appearing. BPM-derived cadence can be several seconds at the
    # slow end (recovery mode parks BPM near bpm_min), which used to
    # leave the patient staring at empty lanes long after they'd
    # completed the previous trial. Capping the rest keeps the next
    # stim coming promptly regardless of pace. The press WINDOW still
    # tracks BPM (see current_timeout_s), so difficulty is unaffected.
    MAX_REST_S = 1.0

    def update(self, dt: float) -> None:
        now = time.perf_counter()
        while self._presses:
            self._handle_press(self._presses.popleft(), now)
        # Rest before the next stim, measured from when the previous
        # trial finished. The BPM cadence still shortens it when the
        # patient is on a fast pace, but it's capped so a slow pace
        # never produces a long dead gap. Falls back to firing
        # immediately on the very first trial (nothing has finished).
        # max(1.0, bpm) so a silly config can't divide by zero.
        cadence = 60.0 / max(1.0, self.adapter.bpm)
        rest = min(cadence, self.MAX_REST_S)
        if self.active is None and self.completed < self.total_trials:
            if (self._last_finish_t is None
                    or (now - self._last_finish_t) >= rest):
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
        """Weakness-weighted pick over the eligible fingers from `pattern`,
        with a floor so no finger is starved.

        Both hands fire together on every trial, so the hands are equal by
        construction here and only the finger split needs managing. Straight
        weighting could leave a strong finger with a handful of trials across
        a block, too few to support an average, which would show up in the
        analysis as an unreliable number rather than as an easy finger.

        The floor scheduler keeps the weighting and only forces a pick when a
        finger has fallen a whole trial behind its guaranteed rate.
        """
        eligible = sorted(set(self.pattern))
        if len(eligible) < 2:
            return eligible[0] if eligible else 0
        if self._floor is None:
            from ..scheduling import FloorWeightedScheduler
            self._floor = FloorWeightedScheduler(
                len(eligible), min_share=self.min_finger_share, rng=self.rng)
        # Weights restricted to the eligible fingers, in their sorted order.
        w = self.adapter.lane_weights()
        sub = [w[f] if 0 <= f < len(w) else 0.0 for f in eligible]
        return eligible[self._floor.next(sub)]

    def _fire(self, now: float) -> None:
        finger = self._pick_finger()
        self._bpm_trace.append(float(self.adapter.bpm))
        self._window_trace_ms.append(float(self.current_timeout_s) * 1000.0)
        if 0 <= finger < len(self._cues):
            self._cues[finger] += 1
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

    def _raw(self, event: str, lane: int | None, t_perf: float,
             detail: str) -> None:
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(event, lane=lane, t_perf=t_perf, detail=detail,
                            hand=self.engine.hand_mode)

    def _handle_press(self, ev: PressEvent, now: float) -> None:
        if self.active is None:
            prev = self._prev_finger
            if prev is not None and ev.lane in (prev, prev + 4):
                # The finished trial's finger before the next cue: that
                # trial's late answer (its window had closed), logged
                # and not charged (Mirror review, 1 October 2026: 5.8
                # idle-press charges a simulated healthy block).
                self._late_presses += 1
                self._raw("late_press", ev.lane, ev.t_perf,
                          f"trial_id={self.trial_counter}")
                return
            # Between-trial spam costs the idle press penalty, same
            # rule as classic / adaptive.
            self.engine.apply_idle_press_penalty()
            return
        finger = self.active.finger
        right_target = finger
        left_target = finger + 4
        since_ms = (ev.t_perf - self.active.stim_t_perf) * 1000.0
        if (ev.lane in (right_target, left_target)
                and 0.0 <= since_ms < self.ANTICIPATION_MS):
            # Not a response to this cue: logged, and that hand's slot
            # stays open for its real press.
            self._anticipations += 1
            self._raw("anticipation_press", ev.lane, ev.t_perf,
                      f"trial_id={self.active.trial_id};"
                      f"after_cue_ms={since_ms:.1f}")
            return
        self.active.keys_pressed.append(ev.lane)
        # Correct side handling: record the press timestamp on the
        # right or left slot. If a side already had a press, ignore
        # the duplicate so a patient who taps twice doesn't trigger
        # the "wrong press" branch.
        if ev.lane == right_target:
            if self.active.right_press_t is None:
                self.active.right_press_t = ev.t_perf
                self.engine.eeg_hand_press(self.active.trial_id, ev.lane,
                                           ev.t_perf)
        elif ev.lane == left_target:
            if self.active.left_press_t is None:
                self.active.left_press_t = ev.t_perf
                self.engine.eeg_hand_press(self.active.trial_id, ev.lane,
                                           ev.t_perf)
        else:
            # Wrong finger on either hand. Same per-press penalty
            # rule as classic / adaptive: every wrong press costs
            # something so spamming doesn't pay.
            self.active.incorrect_presses.append((ev.lane, ev.t_perf))
            self.engine.eeg_wrong_press(self.active.incorrect_presses)
            self.engine.apply_wrong_press_penalty()
            return
        # Both sides in? Finish the trial now. The RT used for
        # classify is the LATER of the two presses so the score
        # reflects synchronisation quality, not just the strong-side
        # reaction.
        if (self.active.right_press_t is not None
                and self.active.left_press_t is not None):
            self._finish(now)

    # Same quality table AdaptiveMode uses (Perfect included for the
    # same reason: classify() returns "Perfect" for the fastest presses,
    # and without an entry here it silently fell through the .get(...,
    # 0.0) default and scored the same as a Miss). A Great press counts
    # as full credit toward the lane's hit-rate EMA, a Late only counts
    # a quarter so a session of all-Lates doesn't fool the controller
    # into thinking the patient is coping fine.
    _QUALITY = {
        "Perfect": 1.0,
        "Great": 1.0,
        "Good":  0.75,
        "Late":  0.25,
        "Early": 0.0,
        "Miss":  0.0,
    }

    def _hands_dropped(self, hands: list[str]) -> bool:
        """Whether any of these hands' boards is down right now, or the
        whole source is: a pair cut short by the rig, not the player.
        Keyboard sessions never drop."""
        src = getattr(self.engine, "source", None)
        if src is None or getattr(src, "provides_samples", False) is not True:
            return False
        if getattr(src, "is_connected", True) is False:
            return True
        down = getattr(self.engine, "_hands_down", None)
        return isinstance(down, set) and any(h in down for h in hands)

    def _peak(self, lane: int) -> float | None:
        fn = getattr(self.engine, "_peak_force_for_lane", None)
        if not callable(fn):
            return None
        try:
            v = fn(lane)
        except Exception:
            return None
        return float(v) if isinstance(v, (int, float)) else None

    def _finish(self, now: float) -> None:
        if self.active is None:
            return
        missing = [h for h, t in (("right", self.active.right_press_t),
                                  ("left", self.active.left_press_t))
                   if t is None]
        if (missing and not self.active.incorrect_presses
                and self._hands_dropped(missing)):
            # A board dropped under the pair: the rig's, so the pace
            # controller never sees it (Adaptive's guard; without it a
            # dropped board drove the pace to the floor).
            self._finish_dropped(now)
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
        # Each side's OWN latency, independent of the shared later-press
        # RT above. This is what makes a hand's press attributable after
        # the fact: the scored RT alone can never say whether the right
        # or the left hand was the slow one on a given trial, only that
        # the pair landed inside the window or didn't.
        right_rt_ms = (None if self.active.right_press_t is None
                       else (self.active.right_press_t
                             - self.active.stim_t_perf) * 1000.0)
        left_rt_ms = (None if self.active.left_press_t is None
                      else (self.active.left_press_t
                            - self.active.stim_t_perf) * 1000.0)
        outcome = classify(rt_ms, self.score_cfg)
        # Cap the Perfect tier at Great. The inter-trial rest is a
        # deterministic function of BPM (fixed cadence, no jitter --
        # see MAX_REST_S / update()), so stim timing is fully
        # predictable and a patient who anticipates the cadence rather
        # than reacting to the stim can land a sub-perfect_ms pair.
        # The notebook's own analysis throws any press under
        # ANTICIPATION_MS (100 ms) away as "anticipation, not a
        # response", so paying it the TOP reward tier in-game
        # disagreed with what the analysis will keep. Great still
        # rewards a genuinely fast synchronised pair; only the
        # anticipation-range top tier is removed. Finger identity
        # stays unpredictable (weakness-weighted random pick), so this
        # does not fully remove the incentive to anticipate, only caps
        # what it pays out.
        if outcome.label == "Perfect":
            from ..scoring import TrialResult
            outcome = TrialResult(label="Great",
                                   points=self.score_cfg.great_points,
                                   rt_ms=rt_ms)
        # Synchrony gate: the BPM-derived press window is the only
        # thing classify() sees, and it grows to 5.4 s at the BPM
        # floor -- exactly when a struggling patient's asynchrony
        # matters most. A pair that both landed inside the window but
        # far apart from EACH OTHER is not a synchronised bimanual
        # movement, so it downgrades to Miss regardless of how fast
        # the later press was.
        async_gap_ms = (None if right_rt_ms is None or left_rt_ms is None
                         else abs(right_rt_ms - left_rt_ms))
        asynchronous = (async_gap_ms is not None
                         and async_gap_ms > self.max_async_ms)
        # Wrong-press trials downgrade to Miss, matching classic /
        # adaptive's clean-trial-signal behaviour.
        if self.active.incorrect_presses or asynchronous:
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
        one_sided = (len(missing) == 1
                     and not self.active.incorrect_presses)
        if one_sided:
            self._one_sided += 1
        if asynchronous and not self.active.incorrect_presses:
            self._gated += 1
            self._late_hand_line(right_rt_ms, left_rt_ms)
        if outcome.label != "Miss" and 0 <= finger < len(self._hits):
            self._hits[finger] += 1
        peak_r = self._peak(finger) if right_rt_ms is not None else None
        peak_l = self._peak(finger + 4) if left_rt_ms is not None else None
        if peak_r is not None and peak_l is not None:
            self._peaks["right"].append(peak_r)
            self._peaks["left"].append(peak_l)
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
        # Both hands moved, so the after-press confirmation buzz goes to
        # both copies of the finger, not just the right-hand lane the
        # log row is keyed on. log_trial only fires it on a correct
        # press, so a one-handed trial never reaches this.
        #
        # correct_lanes carries BOTH required lanes. Without it the row
        # defaulted to correct_keys=[right lane] and every downstream
        # single-target filter (the notebook's individuation index,
        # pooled crosstalk cells) read the left hand's INSTRUCTED press
        # as spillover, driving the enslavement index toward 0.5 on
        # every clean hardware mirror hit.
        #
        # error_type "async": a pair downgraded by the synchrony gate
        # is not a timeout (both presses landed inside the window at
        # known times) and not a wrong finger; without the override the
        # row claimed error_type=timeout, breaking the row schema's
        # promise that only a no-press Miss is a timeout.
        # error_type "one_sided": one hand pressed and the window closed
        # on the other, which is neither a no-press timeout nor a wrong
        # finger (Mirror review, 1 October 2026).
        if self.active.incorrect_presses:
            error_type = None
        elif asynchronous:
            error_type = "async"
        elif one_sided:
            error_type = "one_sided"
        else:
            error_type = None
        self.engine.log_trial(log_obj, outcome, now,
                               cue_lanes=[finger, finger + 4],
                               correct_lanes=[finger, finger + 4],
                               mirror_hand_rts=(right_rt_ms, left_rt_ms),
                               error_type=error_type)
        self._state_event(now, finger, peak_r, peak_l)
        self.active = None
        self.completed += 1
        self._prev_finger = finger
        # Stamp the finish time so the inter-trial rest in update() is
        # measured from here (trial completion) rather than stim onset.
        self._last_finish_t = now

    def _finish_dropped(self, now: float) -> None:
        from ..scoring import TrialResult
        from .classic import PendingTrial as _LogTrial
        trial = self.active
        self._dropped += 1
        outcome = TrialResult(label="Miss",
                              points=self.score_cfg.miss_points,
                              rt_ms=None)
        right_rt = (None if trial.right_press_t is None
                    else (trial.right_press_t - trial.stim_t_perf) * 1000.0)
        left_rt = (None if trial.left_press_t is None
                   else (trial.left_press_t - trial.stim_t_perf) * 1000.0)
        self.engine.log_trial(
            _LogTrial(trial_id=trial.trial_id, lane=trial.lane(),
                      stim_t_perf=trial.stim_t_perf,
                      keys_pressed=list(trial.keys_pressed),
                      incorrect_presses=list(trial.incorrect_presses)),
            outcome, now, cue_lanes=[trial.finger, trial.finger + 4],
            correct_lanes=[trial.finger, trial.finger + 4],
            mirror_hand_rts=(right_rt, left_rt), error_type="device_drop")
        self.active = None
        self.completed += 1
        self._prev_finger = trial.finger
        self._last_finish_t = now

    def _late_hand_line(self, right_rt_ms, left_rt_ms) -> None:
        """A gated pair names the hand that came in behind, the bank's
        rule for direction and next action. Words only in the
        encouraging style: the lab's neutral style shows rings."""
        if right_rt_ms is None or left_rt_ms is None:
            return
        if getattr(self.engine, "feedback_style", "encouraging") == "neutral":
            return
        from ...ui import feedback_bank
        hand = "Left" if left_rt_ms > right_rt_ms else "Right"
        text = feedback_bank.phrase_via(self.engine, "late_hand",
                                        mode="mirror", target=hand)
        gp = (getattr(self.engine, "_screens", {}) or {}).get("gameplay")
        if text and gp is not None and hasattr(gp, "set_message"):
            try:
                gp.set_message(text, 1.4)
            except Exception:
                pass

    def _state_event(self, now: float, finger: int, peak_r, peak_l) -> None:
        """The controller's state after this trial, and each hand's
        peak force (the row's force columns read the right hand only),
        for the analysis."""
        in_rec = bool(getattr(self.adapter, "in_recovery", False))
        if in_rec and not self._last_recovery:
            self._recoveries += 1
        self._last_recovery = in_rec
        d = dict(getattr(self.adapter, "last_decision", None) or {})
        d.update(bpm=round(float(self.adapter.bpm), 1),
                 window_ms=round(float(self.current_timeout_s) * 1000.0),
                 recovery=int(in_rec))
        if peak_r is not None:
            d["peak_r"] = round(peak_r, 3)
        if peak_l is not None:
            d["peak_l"] = round(peak_l, 3)
        self._raw("mirror_state", finger, now,
                  f"trial_id={self.trial_counter};"
                  + ";".join(f"{k}={v}" for k, v in d.items()))

    def block_stats(self) -> dict:
        """What the block did, for metadata.json (Mirror review, 1
        October 2026): the pace and the window at every cue, recovery
        entries, one-sided and gated pairs, late presses after a window
        closed, presses under 100 ms, pairs a board drop cut short, cues
        and hits per finger, and each hand's mean peak force on pairs
        where both registered."""
        def _mean(xs):
            return round(sum(xs) / len(xs), 3) if xs else None
        return {
            "seed": self.seed,
            "start_bpm": self.start_bpm,
            "max_async_ms": self.max_async_ms,
            "bpm_trace": [round(b, 1) for b in self._bpm_trace],
            "window_trace_ms": [round(w) for w in self._window_trace_ms],
            "window_min_ms": (round(min(self._window_trace_ms))
                              if self._window_trace_ms else None),
            "window_max_ms": (round(max(self._window_trace_ms))
                              if self._window_trace_ms else None),
            "recovery_entries": self._recoveries,
            "n_one_sided": self._one_sided,
            "n_gated": self._gated,
            "late_presses": self._late_presses,
            "anticipations": self._anticipations,
            "device_drops": self._dropped,
            "cues_per_finger": list(self._cues),
            "hits_per_finger": list(self._hits),
            "peak_force_right_mean": _mean(self._peaks["right"]),
            "peak_force_left_mean": _mean(self._peaks["left"]),
        }
