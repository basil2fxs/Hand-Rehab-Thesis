"""Reaction mode: press as fast as you can after a randomised wait.

This replaces Classic as the baseline block, so every cross-session
comparison in the thesis rests on the number it produces. The design is
the psychomotor vigilance tradition adapted to this device, and each
decision below names the work it stands on.

WHY A RANDOMISED WAIT. With a fixed or uniformly distributed foreperiod
the probability of the stimulus arriving rises as time passes, so the
patient learns to time the wait and reaction times fall at long waits
for the wrong reason (Niemi and Naatanen 1981, Psychological Bulletin).
An exponential foreperiod keeps that hazard constant, so expectancy
stays flat and the press is a response, not a prediction (Naatanen
1971, Acta Psychologica). The exponential draw is truncated at fp_max
for practical block length, which mildly ages the extreme tail; the
per-trial foreperiod is logged (stimulus column) so the analysis can
check RT against foreperiod and confirm the control worked.

TWO SUB-MODES. Simple RT (one designated finger every trial) measures
detection plus motor initiation; choice RT over the four fingers adds
discrimination and response selection, and the two age and impair
differently (Der and Deary 2006, Psychology and Aging, n=7130). Choice
RT grows with the log of the number of alternatives (Hick 1952; Hyman
1953), so four equiprobable fingers is a 2-bit choice. Choice is the
default here because it exercises all four fingers; `reaction.sub_mode:
simple` switches to the clean single-finger loop.

WHAT THE NUMBER MEASURES. The shipped cue defaults play the buzzer
and the cue tone alongside the screen highlight on every stimulus, so
under them this mode measures audio-tactile-visual reaction time, not
visual reaction time. Auditory and tactile RTs run systematically
faster than visual, so the channel mix changes what the number means,
not just its noise. Those defaults are a whole-suite choice and are
never overridden here; a block that needs the brief's screen-only
measure turns the channels off in Settings, and the cue_flags column
on every trial row is how the analysis separates blocks run under
different mixes instead of pooling them blindly.

ANTICIPATIONS AND CATCH TRIALS. Responses under 100 ms are not
physiologically plausible visual reaction times and are scored as false
starts, never as hits (Luce 1986, Response Times; Basner and Dinges
2011, Sleep; Whelan 2008, The Psychological Record). A press during the
foreperiod is likewise a false start; the trial aborts gently ("Too
soon", no penalty sound, no score loss) and a fresh attempt follows, so
false starts never consume scorable slots. On a fraction of trials
(catch_rate) no stimulus ever comes; surviving the wait earns a small
reward. Catch trials are the standard second anticipation control from
the PVT tradition (Dinges and Powell 1985), kept at 10 percent because
higher rates inflate RT and frustrate patients.

LAPSES AND BLOCK LENGTH. RTs at or over 500 ms are lapses (the PVT
convention, Basner and Dinges 2011). A block is 25 scorable trials with
attempts capped at 35 so a bad run still ends; that lands near the
validated 3-minute PVT-B (Basner, Mollicone and Dinges 2011) and well
short of the 10-minute time-on-task decline documented for the full
PVT. Displayed block score is the median RT because RT distributions
are right-skewed and means mislead (Ratcliff 1993; Whelan 2008).

PROGRESSION. RT has no natural force or amplitude difficulty axis and
raising the press threshold would contaminate the measure, so the only
lever is the response window: 2.0 s, then 1.5 s, then 1.2 s. Step up
after two consecutive blocks with a lapse-or-miss rate under 10
percent, step down after one block over 30 percent. Level and session
bests live on the engine for the length of the login session: they
are cleared when the session ends, so the next patient on the same
app run starts at level 1 with no inherited best.

WHAT THIS MODE CANNOT CLAIM. Within-task improvement is expected
(practice effects appear in nearly every repeated-RT study) but
transfer beyond this task is unproven; Owen et al. (2010, Nature,
n=11430) found no transfer even to closely related trained tasks.
Absolute RTs from this device are not comparable to published
button-press norms: the clock stops at a force-threshold crossing on a
60 Hz screen with unmeasured panel latency, and labs differ by over
100 ms for exactly these reasons (Woods et al. 2015, Frontiers in
Human Neuroscience; Plant and Turner 2009, Behavior Research Methods).
Only within-device comparisons are valid, and single-trial differences
under about 20 ms are noise, though block medians and session trends
remain legitimate because quantisation error averages out (Ulrich and
Giray 1989). This is not a validated PVT and produces no clinical
vigilance scores; the false-start and lapse cuts are borrowed
conventions, not a claim of equivalence. After stroke, RT is slowed in
BOTH hands (Dean et al. 2012), so the unaffected hand is a
within-patient comparator, not a healthy baseline.

DEVIATIONS FROM THE RESEARCH BRIEF, where the codebase plumbing wins:
- The stimulus is the existing lane cue (tile highlight, optional
  buzzer and tone via the cue.* switches), not a full-screen luminance
  flip with a running millisecond counter. Cue configuration is logged
  per trial (cue_flags), so blocks run under different cue settings can
  be split in analysis. The brief's screen-only default is therefore a
  Settings choice here, not hard-coded.
- Stimulus onset is timestamped when the mode arms the cue, up to one
  frame before the display flip; per-frame flip intervals are not
  logged. Both fold into the constant device offset already declared
  above, and the raw 200 Hz stream plus stim events in raw.csv allow
  offline re-scoring.
- The scheduler forbids ANY immediate repeat of a finger (existing
  BalancedScheduler behaviour), stricter than the brief's cap of three
  consecutive repeats.
- Choice unlock after simple-RT proficiency needs state that survives
  across sessions, which this app does not keep; the sub-mode is a
  config switch instead and level progression is within-session only.
- The rest gate reads the FSR detectors' live pressed state; in the
  keyboard fallback it can only see discrete key events, so a held key
  does not block arming there.

LOGGING MAP. Scorable trials go through engine.log_trial exactly like
Classic: time_difference_ms carries the RT, early_late carries the
Perfect/Great/Good/Late/Miss tier (with scoring.good_ms at its default
500 ms the Late tier IS the lapse band), and a wrong finger in choice
mode follows the Classic convention of a Miss row with
had_incorrect_press TRUE and the wrong press in first_incorrect_ms.
Events that never became a scorable trial (foreperiod false starts,
sub-cut anticipations, wrong fingers in simple mode, catch outcomes)
go through engine.log_reaction_event, which writes the same CSV with
error_type set to false_start / anticipation / wrong_finger /
catch_false_start ("" for a survived catch, early_late "CatchOk") and
deliberately skips the hit counters, streak and confirmation cues:
those would reward a press the protocol says gets neutral feedback.
The stimulus column records the sub-mode and the scheduled foreperiod
("choice;fp=2.314", "simple;catch") so the anticipation diagnostic can
run from trials.csv alone.
"""
from __future__ import annotations

import logging
import random
import time
from collections import deque
from typing import TYPE_CHECKING

import pygame

from ...hardware.eeg_trigger import CODES as EEG_CODES
from ...hardware.fsr_detector import PressEvent
from ..rest_skip import WaitSkip
from ..scheduling import BalancedScheduler, PairedBalancedScheduler
from ..scoring import ScoreConfig, TrialResult, classify
from ._keys import keymap_for_hand, resolve_key
from .classic import PendingTrial

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


class ReactionMode(WaitSkip):
    name = "Reaction"

    # Points for surviving a catch trial. Small on purpose: waiting is
    # the correct behaviour and needs acknowledging, but it must never
    # rival the reward for an actual fast press.
    CATCH_REWARD = 1

    def __init__(self, engine: "GameEngine",
                 lanes_by_hand: dict[str, list[int]],
                 sub_mode: str, srt_finger: int,
                 scorable_trials: int, attempt_cap: int,
                 fp_min_s: float, fp_mean_extra_s: float, fp_max_s: float,
                 fp_mode: str,
                 catch_rate: float, catch_wait_s: float,
                 anticipation_cut_ms: float, lapse_ms: float,
                 response_window_s: float,
                 level: int, max_level: int,
                 level_up_lapse_rate: float, level_down_lapse_rate: float,
                 rest_gate_s: float, feedback_s: float,
                 false_start_feedback_s: float, inter_trial_gap_s: float,
                 score_cfg: ScoreConfig, seed: int = 0,
                 fp_fixed_s: float | None = None) -> None:
        self.engine = engine
        self.sub_mode = "simple" if sub_mode == "simple" else "choice"
        self.score_cfg = score_cfg
        self.total_trials = max(1, int(scorable_trials))
        self.attempt_cap = max(self.total_trials, int(attempt_cap))
        self.fp_min = float(fp_min_s)
        self.fp_mean_extra = float(fp_mean_extra_s)
        self.fp_max = max(float(fp_max_s), self.fp_min)
        self.fp_mode = "uniform" if fp_mode == "uniform" else "exponential"
        self.catch_rate = min(max(float(catch_rate), 0.0), 1.0)
        self.catch_wait = float(catch_wait_s)
        self.anticipation_cut = float(anticipation_cut_ms)
        self.lapse_ms = float(lapse_ms)
        self.response_window = float(response_window_s)
        self.level = int(level)
        self.max_level = max(1, int(max_level))
        self.level_up_rate = float(level_up_lapse_rate)
        self.level_down_rate = float(level_down_lapse_rate)
        self.rest_gate = float(rest_gate_s)
        self.feedback_s = float(feedback_s)
        self.false_start_feedback_s = float(false_start_feedback_s)
        self.inter_trial_gap = float(inter_trial_gap_s)
        # EEG variant: a constant foreperiod instead of the exponential
        # draw. The exponential keeps the hazard flat so the wait
        # cannot be timed, which is right for behaviour and wrong for
        # the CNV: a flat hazard suppresses the expectancy ramp the
        # CNV is. None (the shipping default) changes nothing.
        self.fp_fixed_s = (float(fp_fixed_s)
                           if fp_fixed_s and float(fp_fixed_s) > 0
                           else None)
        self.seed = int(seed)
        # One seeded generator drives the foreperiod draws, the catch
        # decisions AND the lane order, so a block is reproducible from
        # the seed recorded in raw.csv at block start.
        self.rng = random.Random(self.seed)

        # Lane pool. Simple mode narrows each hand to its designated
        # finger; choice keeps all four. Either way the balanced
        # schedulers guarantee equal counts per finger (and per hand in
        # bilateral play), which every cross-finger comparison needs.
        by_hand: dict[str, list[int]] = {}
        for hand, lanes in (lanes_by_hand or {}).items():
            if not lanes:
                continue
            if self.sub_mode == "simple":
                idx = min(max(0, int(srt_finger)), len(lanes) - 1)
                by_hand[hand] = [lanes[idx]]
            else:
                by_hand[hand] = list(lanes)
        if not by_hand:
            by_hand = {"right": [0] if self.sub_mode == "simple"
                       else [0, 1, 2, 3]}
        if len(by_hand) > 1:
            self._sched = PairedBalancedScheduler(by_hand, self.rng)
            self._next_lane = self._sched.next_lane
        else:
            self._sched = BalancedScheduler(
                next(iter(by_hand.values())), self.rng)
            self._next_lane = self._sched.next

        # Phase machine: arm -> (foreperiod | catch) -> stim -> rest ->
        # arm again, until the scorable target or the attempt cap ends
        # the block. "done" latches so finish_block fires exactly once.
        self._phase = "arm"
        self.active: PendingTrial | None = None
        self.completed = 0            # scorable trials closed
        self.trial_counter = 0        # every attempt, capped
        self._stim_due: float | None = None
        self._fp_scheduled: float = 0.0
        self._catch_until: float | None = None
        # When the go signal WOULD have fired on the current catch
        # trial, for the stimulus-free preparation marker (25).
        self._catch_virtual_due: float | None = None
        self._rest_until: float | None = None
        self._last_activity_t: float | None = None
        self._rest_msg_t = 0.0
        self._presses: deque[PressEvent] = deque()

        # Outcome tallies for block_stats and level progression.
        self.n_valid = 0
        self.n_lapse = 0
        self.n_miss = 0
        self.n_wrong_choice = 0
        self.n_wrong_finger = 0
        self.n_false_start = 0
        self.n_anticipation = 0
        self.n_catch = 0
        self.n_catch_ok = 0
        self.n_catch_false_start = 0
        # Per-valid-trial parallel lists for the median / slope /
        # anticipation diagnostics in block_stats.
        self._valid_rts: list[float] = []
        self._valid_fps: list[float] = []
        self._valid_idx: list[int] = []

    # ---- plumbing shared with the other cadence modes ----------------------
    def queue_press(self, ev: PressEvent) -> None:
        self._presses.append(ev)

    @property
    def current_timeout_s(self) -> float:
        # The engine reads this when arming the lane's timing bar and
        # when logging timeout_ms, so the bar length and the CSV both
        # match the level's response window.
        return self.response_window

    def on_resume(self, pause_dur: float) -> None:
        # Slide every in-flight deadline forward so a pause cannot fire
        # a stim, expire a catch wait, or time a trial out on resume.
        if self.active is not None:
            self.active.stim_t_perf += pause_dur
        for attr in ("_stim_due", "_catch_until", "_catch_virtual_due",
                     "_rest_until", "_last_activity_t"):
            v = getattr(self, attr)
            if v is not None:
                setattr(self, attr, v + pause_dur)

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN:
            # Keyboard fallback stays wired even with an Arduino
            # connected, same reasoning as classic.py: a busted
            # auto-detect must never leave the therapist with no
            # working input.
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

    # ---- main tick ---------------------------------------------------------
    def update(self, dt: float) -> None:
        now = time.perf_counter()
        while self._presses:
            self._handle_press(self._presses.popleft(), now)
        if self._phase == "done":
            return
        if (self.active is None and self._phase in ("arm", "rest")
                and (self.completed >= self.total_trials
                     or self.trial_counter >= self.attempt_cap)):
            self._end_block()
            return
        if self._phase == "rest":
            if self._rest_until is not None and now >= self._rest_until:
                self.clear_wait()
                self._leave_rest(now)
            return
        if self._phase == "arm":
            self._update_arm(now)
            return
        if self._phase == "foreperiod":
            if self._stim_due is not None and now >= self._stim_due:
                self._fire(now)
            return
        if self._phase == "catch":
            # Stimulus-free preparation marker: the instant the go
            # signal would have fired had this not been a catch trial.
            # Gives the CNV analysis epochs with identical preparation
            # and no stimulus response mixed in.
            if (self._catch_virtual_due is not None
                    and now >= self._catch_virtual_due):
                self._catch_virtual_due = None
                self._eeg(EEG_CODES["prep_catch_onset"], now)
            if self._catch_until is not None and now >= self._catch_until:
                self._catch_survived(now)
            return
        if self._phase == "stim" and self.active is not None:
            if (now - self.active.stim_t_perf) > self.response_window:
                self._close_scorable(None, now)

    # ---- arming and the rest gate ------------------------------------------
    def _fingers_down(self) -> bool:
        """Whether any FSR is currently held past its press threshold.
        The isinstance guard keeps test doubles (MagicMock engines)
        from exploding this check."""
        dets = getattr(self.engine, "detectors", None)
        if not isinstance(dets, dict):
            return False
        for det in dets.values():
            pressed = getattr(det, "pressed", None)
            try:
                if pressed is not None and any(pressed):
                    return True
            except TypeError:
                continue
        return False

    def _update_arm(self, now: float) -> None:
        # Stability gate: the foreperiod only starts once every finger
        # has been at rest for rest_gate seconds. Without it a lingering
        # press bleeds into the foreperiod and reads as a false start
        # the patient never made.
        if self._last_activity_t is None:
            self._last_activity_t = now
        if self._fingers_down():
            self._last_activity_t = now
        if (now - self._last_activity_t) < self.rest_gate:
            # The stability gate DOES protect a measurement: a finger
            # still down when the foreperiod opens reads as a false
            # start the patient never made. It stays skippable so a
            # twitchy hand cannot trap the block, but the trial it
            # releases is flagged, because that trial's false-start
            # class is exactly what the gate was guarding. Held on
            # screen past its due time: a gate that keeps restarting
            # is when somebody wants the button.
            self.refresh_wait("settle",
                              self._last_activity_t + self.rest_gate,
                              on_skip=self._force_arm,
                              started_at=now,
                              protects="still fingers before the wait",
                              hold_when_due=True)
            if now - self._rest_msg_t > 0.6:
                self._rest_msg_t = now
                self._set_message("Rest your fingers", 0.7)
            return
        self.clear_wait()
        self._begin_trial(now)

    def _force_arm(self, now: float) -> None:
        """Release the stability gate now. Backdating the activity
        clock keeps the trial on the ordinary path, so it still picks
        up the flag on its way through _begin_trial."""
        self._last_activity_t = now - self.rest_gate

    def _begin_trial(self, now: float) -> None:
        self.trial_counter += 1
        # Carried onto this trial's row: True when the stability gate
        # was cut short, so a false start here can be read as the
        # gate's absence rather than as anticipation.
        self._trial_gate_skipped = (self.take_skip_flag() == "settle")
        if self._trial_gate_skipped:
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "rest_gate_skipped",
                    detail=f"trial_id={self.trial_counter}",
                    t_perf=now,
                    hand=getattr(self.engine, "hand_mode", "right"))
            self.n_gate_skipped = getattr(self, "n_gate_skipped", 0) + 1
        if self.catch_rate > 0.0 and self.rng.random() < self.catch_rate:
            self.n_catch += 1
            self._catch_until = now + self.catch_wait
            # The catch trial is armed exactly like a real one (same
            # S1 marker, same ready cue) or the patient could tell
            # them apart. The virtual go instant uses the fixed
            # foreperiod when set, else the exponential draw's mean;
            # deliberately NOT a draw from self.rng, which would shift
            # the seeded wait sequence and break reproducibility of
            # previously recorded seeds.
            self._eeg(EEG_CODES["prep_foreperiod"], now)
            self._show_ready_cue()
            self._catch_virtual_due = now + (
                self.fp_fixed_s or (self.fp_min + self.fp_mean_extra))
            self._phase = "catch"
            return
        self._fp_scheduled = self._draw_foreperiod()
        self._stim_due = now + self._fp_scheduled
        # CNV S1: the wait is armed. The marker fires in every config;
        # the visible ready cue only in the fixed-foreperiod EEG
        # variant, so the shipping game's screen stays as it was.
        self._eeg(EEG_CODES["prep_foreperiod"], now)
        self._show_ready_cue()
        self._phase = "foreperiod"

    def _eeg(self, code: int, t_event: float) -> None:
        """Marker doorway; inert unless the engine carries an active
        MarkerWriter (the engine helper does the guarding)."""
        send = getattr(self.engine, "_eeg_send", None)
        if callable(send):
            send(code, t_event=t_event)

    def _show_ready_cue(self) -> None:
        """Visible S1 for the CNV epochs. Only in the EEG variant: the
        CNV is defined S1-to-S2, and without a visible S1 the 21
        marker would be an invisible bookmark, not a cue the brain can
        prepare from."""
        if self.fp_fixed_s is not None:
            self._set_message("Ready", 0.8)

    def _draw_foreperiod(self) -> float:
        """One foreperiod in seconds. Exponential above fp_min keeps
        the stimulus hazard flat so the wait cannot be timed; draws
        past fp_max are redrawn (the truncation the docstring owns up
        to). The uniform option exists for PVT-comparable blocks. The
        fixed option (fp_fixed_s, the EEG variant) trades the flat
        hazard for the predictable wait CNV epochs need."""
        if self.fp_fixed_s is not None:
            return self.fp_fixed_s
        if self.fp_mode == "uniform":
            # The PVT's 2-10 s inter-stimulus range (Dinges and Powell
            # 1985), independent of fp_min / fp_max on purpose.
            return self.rng.uniform(2.0, 10.0)
        if self.fp_mean_extra <= 0.0:
            return self.fp_min
        while True:
            fp = self.fp_min + self.rng.expovariate(1.0 / self.fp_mean_extra)
            if fp <= self.fp_max:
                return fp

    def _fire(self, now: float) -> None:
        lane = self._next_lane()
        self.active = PendingTrial(
            trial_id=self.trial_counter,
            lane=lane,
            stim_t_perf=now,
            keys_pressed=[],
            incorrect_presses=[],
        )
        self._phase = "stim"
        self._stim_due = None
        self.engine.on_stim_multi([lane], self.trial_counter, now)

    def _hand_for_lane(self, lane: int) -> str:
        """Which board a lane sits on, for the trial row's hand column.

        A both-hands block runs with engine.hand_mode == "both" for
        the whole block, but every single trial only ever cues ONE
        board, right or left, from lanes_by_hand's own 0..3 / 4..7
        split. Reusing the engine's lane->hand resolver (the same one
        pulse_motor uses to send a STOP at the right board) instead of
        the block-level hand_mode is what lets a bilateral block's RT
        median, p10, histogram and foreperiod trend be split by hand
        downstream, in the notebook or anywhere else that reads
        trials.csv directly."""
        return self.engine._lane_hand(lane) or self.engine.hand_mode

    # ---- presses -----------------------------------------------------------
    def _handle_press(self, ev: PressEvent, now: float) -> None:
        # Every press, whatever the phase, restarts the rest gate: a
        # patient still moving is not at rest.
        self._last_activity_t = now
        if self._phase == "foreperiod":
            self._false_start(ev, now)
            return
        if self._phase == "catch":
            self._catch_false_start(ev, now)
            return
        if self._phase == "stim" and self.active is not None:
            self._press_on_stim(ev, now)
            return
        # arm / rest / done: no penalty, unlike classic's idle-press
        # deduction. The gate already makes fidgeting cost time, and
        # false starts are expected when response inhibition is
        # impaired after stroke; punishing them invites pressing
        # harder out of stress.

    def _false_start(self, ev: PressEvent, now: float) -> None:
        self.n_false_start += 1
        self.engine.log_reaction_event(
            trial_id=self.trial_counter, lane=None,
            label="Early", error_type="false_start",
            pressed_lane=ev.lane, press_t_perf=ev.t_perf,
            stimulus=f"{self.sub_mode};fp={self._fp_scheduled:.3f}",
            # No cued lane to derive a side from (the stimulus never
            # fired), but the PRESSING lane did happen and resolves to
            # a board via _lane_hand, so a both-hands block still gets
            # a real right/left attribution instead of "both".
            hand=self._hand_for_lane(ev.lane),
        )
        self._stim_due = None
        self._set_message("Too soon", self.false_start_feedback_s,
                          kind="warn")
        self._enter_rest(now, self.false_start_feedback_s)

    def _catch_false_start(self, ev: PressEvent, now: float) -> None:
        self.n_catch_false_start += 1
        self.engine.log_reaction_event(
            trial_id=self.trial_counter, lane=None,
            label="Early", error_type="catch_false_start",
            pressed_lane=ev.lane, press_t_perf=ev.t_perf,
            stimulus=f"{self.sub_mode};catch",
            hand=self._hand_for_lane(ev.lane),
        )
        self._catch_until = None
        self._set_message("Too soon", self.false_start_feedback_s,
                          kind="warn")
        self._enter_rest(now, self.false_start_feedback_s)

    def _catch_survived(self, now: float) -> None:
        self.n_catch_ok += 1
        self.engine.log_reaction_event(
            trial_id=self.trial_counter, lane=None,
            label="CatchOk", error_type="",
            points=self.CATCH_REWARD,
            stimulus=f"{self.sub_mode};catch",
        )
        # Reward the waiting directly; log_reaction_event touches no
        # counters so the score bump happens here.
        try:
            self.engine.score += self.CATCH_REWARD
            self.engine._last_gained = self.CATCH_REWARD
        except TypeError:
            pass
        self._catch_until = None
        self._set_message(f"Good waiting +{self.CATCH_REWARD}",
                          self.feedback_s, kind="success")
        self._enter_rest(now, self.feedback_s)

    def _press_on_stim(self, ev: PressEvent, now: float) -> None:
        trial = self.active
        if trial is None:
            return
        rt_ms = (ev.t_perf - trial.stim_t_perf) * 1000.0
        # update() pops the whole press queue before it checks the
        # phase=='stim' timeout, so a press that lands after the
        # response window but before the next tick reaches here
        # instead of the timeout branch. Close it the same way the
        # timeout would (a scorable Miss, no RT), so no row's own
        # rt_ms ever exceeds the timeout_ms it was censored against.
        # The press itself is still RECORDED on the row (keys_pressed,
        # first_incorrect_ms, error_type late_press): clinically a
        # response at window+100 ms is an extreme lapse, not an
        # absence of response, and the old row was byte-identical to
        # never pressing at all.
        if rt_ms > self.response_window * 1000.0:
            trial.keys_pressed.append(ev.lane)
            trial.incorrect_presses.append((ev.lane, ev.t_perf))
            self._close_scorable(None, now, late_press=True)
            return
        # Sub-cut presses are anticipations whichever finger fired: a
        # press that fast cannot be a response to the stimulus, so the
        # finger carries no information (Basner and Dinges 2011).
        if rt_ms < self.anticipation_cut:
            self.n_anticipation += 1
            self.active = None
            self.engine.log_reaction_event(
                trial_id=trial.trial_id, lane=trial.lane,
                label="Early", error_type="anticipation",
                rt_ms=rt_ms, pressed_lane=ev.lane,
                press_t_perf=ev.t_perf,
                stimulus=f"{self.sub_mode};fp={self._fp_scheduled:.3f}",
                hand=self._hand_for_lane(trial.lane),
            )
            self._clear_lanes()
            self._set_message("Too soon", self.false_start_feedback_s,
                              kind="warn")
            self._enter_rest(now, self.false_start_feedback_s)
            return
        if ev.lane == trial.lane:
            trial.keys_pressed.append(ev.lane)
            self._close_scorable(ev, now)
            return
        if self.sub_mode == "choice":
            # A wrong choice stops the clock and consumes the trial;
            # accuracy is a headline metric for choice RT. Follows the
            # Classic convention: a Miss row with had_incorrect_press
            # TRUE and the wrong press latency in first_incorrect_ms.
            trial.keys_pressed.append(ev.lane)
            trial.incorrect_presses.append((ev.lane, ev.t_perf))
            self.n_wrong_choice += 1
            self.completed += 1
            self.active = None
            outcome = TrialResult(label="Miss",
                                  points=self.score_cfg.miss_points,
                                  rt_ms=None)
            self.engine.log_trial(
                trial, outcome, now,
                stimulus=f"{self.sub_mode};fp={self._fp_scheduled:.3f}",
                hand=self._hand_for_lane(trial.lane))
            self._set_message("Wrong finger", self.feedback_s, kind="warn")
            self._enter_rest(now, self.feedback_s)
            return
        # Simple mode: a different finger is logged and the attempt is
        # retried, because the designated finger's RT is the measure
        # and a wrong press is not an RT at all.
        self.n_wrong_finger += 1
        self.active = None
        self.engine.log_reaction_event(
            trial_id=trial.trial_id, lane=trial.lane,
            label="Wrong", error_type="wrong_finger",
            pressed_lane=ev.lane, press_offset_ms=rt_ms,
            press_t_perf=ev.t_perf,
            stimulus=f"{self.sub_mode};fp={self._fp_scheduled:.3f}",
            hand=self._hand_for_lane(trial.lane),
        )
        self._clear_lanes()
        self._set_message("Wrong finger", self.feedback_s, kind="warn")
        self._enter_rest(now, self.feedback_s)

    def _close_scorable(self, ev: PressEvent | None, now: float,
                        late_press: bool = False) -> None:
        """Close a trial that consumes a scorable slot: a valid press
        or a timeout miss. Goes through engine.log_trial so scoring,
        streaks, cues and the trial CSV behave exactly as in Classic
        and time_difference_ms keeps its meaning downstream.

        `late_press` marks a Miss whose press arrived AFTER the
        response window: scored and gated exactly like a timeout (no
        RT, points 0), but the row says late_press so a slow-but-
        present response stays distinguishable from total absence
        without re-scoring raw.csv."""
        trial = self.active
        if trial is None:
            return
        self.active = None
        self.completed += 1
        rt_ms = None
        if ev is not None:
            rt_ms = (ev.t_perf - trial.stim_t_perf) * 1000.0
        outcome = classify(rt_ms, self.score_cfg)
        if rt_ms is None:
            self.n_miss += 1
        else:
            self.n_valid += 1
            if rt_ms >= self.lapse_ms:
                self.n_lapse += 1
            self._valid_rts.append(rt_ms)
            self._valid_fps.append(self._fp_scheduled)
            self._valid_idx.append(self.completed)
        self.engine.log_trial(
            trial, outcome, now,
            stimulus=f"{self.sub_mode};fp={self._fp_scheduled:.3f}",
            hand=self._hand_for_lane(trial.lane),
            error_type=("late_press" if late_press else None))
        if rt_ms is not None:
            self._show_rt_feedback(rt_ms)
            self._enter_rest(now, self.feedback_s)
        else:
            # log_trial already flashed "Miss"; give it the false-start
            # display length so the patient can register what happened.
            self._enter_rest(now, self.false_start_feedback_s)

    # ---- feedback ----------------------------------------------------------
    def _show_rt_feedback(self, rt_ms: float) -> None:
        """The game hook: the number IS the feedback (the PVT's
        self-motivating loop), plus the session best so "faster" has a
        target. Bests are kept per sub-mode and hand on the engine so
        they survive across blocks within one login session; the
        engine clears them at end_session."""
        store = getattr(self.engine, "_reaction_best_ms", None)
        if not isinstance(store, dict):
            store = {}
            try:
                self.engine._reaction_best_ms = store
            except Exception:
                pass
        key = (self.sub_mode, getattr(self.engine, "hand_mode", "?"))
        prev = store.get(key)
        is_best = prev is None or rt_ms < prev
        if is_best:
            store[key] = rt_ms
        # The kind picks the chip colour on screen: gold for a new
        # best, amber for a lapse, green for an ordinary valid press.
        if rt_ms >= self.lapse_ms:
            msg = f"{rt_ms:.0f} ms  too slow"
            kind = "warn"
        elif is_best and prev is not None:
            msg = f"{rt_ms:.0f} ms  NEW BEST"
            kind = "best"
        elif prev is not None:
            msg = f"{rt_ms:.0f} ms  best {prev:.0f}"
            kind = "success"
        else:
            msg = f"{rt_ms:.0f} ms"
            kind = "success"
        self._set_message(msg, self.feedback_s, kind=kind)

    def session_best_ms(self) -> float | None:
        store = getattr(self.engine, "_reaction_best_ms", None)
        if not isinstance(store, dict):
            return None
        return store.get(
            (self.sub_mode, getattr(self.engine, "hand_mode", "?")))

    def _enter_rest(self, now: float, feedback_dur: float) -> None:
        self._phase = "rest"
        self._rest_until = now + feedback_dur + self.inter_trial_gap
        # Feedback display plus breathing room. Neither shapes the
        # next reaction time: the stability gate in _update_arm is
        # what protects the foreperiod, and it runs after this
        # regardless of how long this lasted.
        self.arm_wait("feedback", self._rest_until, self._leave_rest,
                      started_at=now)

    def _leave_rest(self, now: float) -> None:
        self._rest_until = None
        self._phase = "arm"

    def _gameplay_screen(self):
        screens = getattr(self.engine, "_screens", None)
        if not isinstance(screens, dict):
            return None
        return screens.get("gameplay")

    def _set_message(self, text: str, duration_s: float,
                     kind: str = "info") -> None:
        gp = self._gameplay_screen()
        if gp is not None and hasattr(gp, "set_message"):
            try:
                gp.set_message(text, duration_s, kind=kind)
            except TypeError:
                # Older screen doubles take (text, duration) only.
                gp.set_message(text, duration_s)

    def _clear_lanes(self) -> None:
        """Drop the target highlight and timing bar after a trial that
        closes outside log_trial (which clears them itself)."""
        gp = self._gameplay_screen()
        if gp is None or not hasattr(gp, "lanes"):
            return
        for ls in gp.lanes:
            ls.clear_timing()
            ls.active = False

    # ---- block end ---------------------------------------------------------
    def _end_block(self) -> None:
        self._phase = "done"
        self._update_level_progression()
        self.engine.finish_block()

    def _lapse_like_rate(self) -> float | None:
        """Lapses, misses and wrong-finger presses over scorable trials.
        Misses are counted with lapses because a timeout is the extreme
        lapse, and a window that only ever times out should widen, not
        shrink. Wrong-finger presses in choice sub-mode are counted too:
        a block of fast-but-wrong presses is not a clean block, and must
        not be treated as one when deciding whether to level up.

        None when no scorable trial completed: a block that ended at
        the attempt cap on nothing but false starts produced no
        evidence, and reporting 0.0 would read downstream as a clean
        block from exactly the impulse-impaired patient the window
        exists to protect."""
        if self.completed <= 0:
            return None
        return ((self.n_lapse + self.n_miss + self.n_wrong_choice)
                / self.completed)

    def _update_level_progression(self) -> None:
        """Two clean blocks step the response window down a level; one
        bad block steps it back up. State lives on the engine so it
        spans blocks within a login session; a restart or session end
        re-opens at level 1, which is the safe direction to fail in."""
        eng = self.engine
        lvl = getattr(eng, "_reaction_level", 1)
        clean = getattr(eng, "_reaction_clean_blocks", 0)
        if not isinstance(lvl, int) or lvl < 1:
            lvl = 1
        if not isinstance(clean, int) or clean < 0:
            clean = 0
        rate = self._lapse_like_rate()
        # A clean block needs evidence: at least half the planned
        # scorable trials must have completed before a low rate can
        # count toward a level-up. Without the floor, two blocks that
        # ended at the attempt cap on nothing but false starts (rate
        # None, or a handful of clean presses among a wall of
        # wrong-finger retries) would tighten the window on the
        # patients least able to handle it. A low-evidence block is
        # neutral: the clean streak neither grows nor resets.
        min_evidence = max(1, self.total_trials // 2)
        if rate is None:
            pass
        elif rate > self.level_down_rate:
            lvl = max(1, lvl - 1)
            clean = 0
        elif rate < self.level_up_rate:
            if self.completed >= min_evidence:
                clean += 1
                if clean >= 2:
                    lvl = min(self.max_level, lvl + 1)
                    clean = 0
        else:
            clean = 0
        try:
            eng._reaction_level = lvl
            eng._reaction_clean_blocks = clean
        except Exception:
            pass

    # ---- block summary -----------------------------------------------------
    @staticmethod
    def _least_squares_slope(xs: list[float],
                             ys: list[float]) -> float | None:
        n = len(xs)
        if n < 3 or n != len(ys):
            return None
        mx = sum(xs) / n
        my = sum(ys) / n
        varx = sum((x - mx) ** 2 for x in xs)
        if varx <= 0.0:
            return None
        cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
        return cov / varx

    @classmethod
    def _spearman_rho(cls, xs: list[float],
                      ys: list[float]) -> float | None:
        """Rank correlation without scipy: Pearson on midranks. Used
        for the anticipation diagnostic (RT against foreperiod), where
        near zero is the healthy result under a non-aging foreperiod
        (Niemi and Naatanen 1981)."""
        n = len(xs)
        if n < 3 or n != len(ys):
            return None

        def ranks(vals: list[float]) -> list[float]:
            order = sorted(range(len(vals)), key=lambda i: vals[i])
            out = [0.0] * len(vals)
            i = 0
            while i < len(order):
                j = i
                while (j + 1 < len(order)
                       and vals[order[j + 1]] == vals[order[i]]):
                    j += 1
                mid = (i + j) / 2.0 + 1.0
                for k in range(i, j + 1):
                    out[order[k]] = mid
                i = j + 1
            return out

        rx = ranks(xs)
        ry = ranks(ys)
        mx = sum(rx) / n
        my = sum(ry) / n
        cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
        vx = sum((a - mx) ** 2 for a in rx)
        vy = sum((b - my) ** 2 for b in ry)
        if vx <= 0.0 or vy <= 0.0:
            return None
        return cov / (vx * vy) ** 0.5

    def block_stats(self) -> dict:
        """The reaction-specific aggregates finish_block folds into
        metadata.json, so a block is readable without trials.csv. The
        median is the headline (Ratcliff 1993; Whelan 2008); the
        Spearman rho against foreperiod is the anticipation check."""
        rts = sorted(self._valid_rts)
        n = len(rts)
        median = None
        mean = None
        sd = None
        p10 = None
        if n:
            mid = n // 2
            median = rts[mid] if n % 2 else (rts[mid - 1] + rts[mid]) / 2.0
            mean = sum(rts) / n
            if n > 1:
                sd = (sum((r - mean) ** 2 for r in rts) / (n - 1)) ** 0.5
            p10 = rts[int(0.1 * (n - 1))]
        accuracy = None
        if self.sub_mode == "choice":
            denom = self.n_valid + self.n_wrong_choice
            if denom > 0:
                accuracy = self.n_valid / denom
        slope = self._least_squares_slope(
            [float(i) for i in self._valid_idx], self._valid_rts)
        rho = self._spearman_rho(self._valid_fps, self._valid_rts)
        best = self.session_best_ms()

        def _r(v, nd=1):
            return None if v is None else round(v, nd)

        return {
            "sub_mode": self.sub_mode,
            "level": self.level,
            "response_window_s": self.response_window,
            "n_rest_gate_skipped": getattr(self, "n_gate_skipped", 0),
            **self.wait_skip_stats(),
            "fp_mode": self.fp_mode,
            "seed": self.seed,
            "n_scorable": self.completed,
            "n_attempts": self.trial_counter,
            "n_valid": self.n_valid,
            "n_lapse": self.n_lapse,
            "n_miss": self.n_miss,
            "n_wrong_choice": self.n_wrong_choice,
            "n_wrong_finger": self.n_wrong_finger,
            # All anticipation-type errors, then the split. The
            # combined figure is the false-start rate the notebook
            # flags at 10 percent.
            "n_false_start_total": (self.n_false_start
                                    + self.n_anticipation
                                    + self.n_catch_false_start),
            "n_false_start_foreperiod": self.n_false_start,
            "n_anticipation": self.n_anticipation,
            "n_catch": self.n_catch,
            "n_catch_ok": self.n_catch_ok,
            "n_catch_false_start": self.n_catch_false_start,
            # None (not 0.0) when nothing completed: the metadata must
            # not claim a clean block that never produced a trial.
            "lapse_like_rate": _r(self._lapse_like_rate(), 3),
            "median_rt_ms": _r(median),
            "mean_rt_ms": _r(mean),
            "sd_rt_ms": _r(sd),
            "p10_rt_ms": _r(p10),
            "max_rt_ms": _r(rts[-1] if rts else None),
            "accuracy": _r(accuracy, 3),
            "slope_rt_ms_per_trial": _r(slope, 3),
            "spearman_rho_rt_vs_fp": _r(rho, 3),
            "session_best_ms": _r(best),
        }
