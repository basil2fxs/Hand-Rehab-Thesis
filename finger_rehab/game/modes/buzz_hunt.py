"""Buzz Hunt: the vibrotactile perception suite. The vibration motors
stop being a cue channel and become the stimulus itself: a pulse fires
on one finger and the player presses the finger that buzzed, then the
suite tightens the screws with shorter pulses, cross-hand distractors,
buzz sequences to replay, and one-buzz-or-two gap trials.

WHY THIS DESIGN. Roughly half of stroke survivors carry a
somatosensory deficit, and the one intervention with RCT support is
graded discrimination training just above threshold, with attention,
feedback and progression:

- Carey L, Macdonell R, Matyas TA (2011). SENSe: Study of the
  Effectiveness of Neurorehabilitation on Sensation: A Randomized
  Controlled Trial. Neurorehabilitation and Neural Repair
  25(4):304-313. n = 50 chronic stroke; 10 hours of somatosensory
  discrimination training beat exposure to the same stimuli, and the
  gains held at 6 months. The training principles named in that trial
  are this mode's skeleton: staircases keep every trial just above
  threshold, the near-empty screen forces attention onto the hand,
  feedback comes after every response, and the stages progress.
- Zeuner KE, et al (2002). Sensory training for patients with focal
  hand dystonia. Annals of Neurology (doi 10.1002/ana.10174). Eight
  weeks of braille reading improved spatial discrimination AND the
  Fahn dystonia scale, and the sensory gains correlated with the
  motor gains. Pure sensory discrimination training moved a motor
  outcome, which is the licence for a sensory-only game mode on a
  motor rehab rig.

Supporting, verified by the research cluster: Weber 2023 (Journal of
Neurophysiology 130(5):1126-1141) measured touch localisation after
nerve repair and found misreferrals where touch on one digit is felt
on another; this mode's per-finger confusion matrix is the digital
analogue of their measure and is the core log output. Vikstrom 2017
(Journal of Hand Therapy) found locognosia is the modality that
responded to home training at 1.5 and 3 years after nerve repair.
Auld 2014 names the evidence gap in children with unilateral cerebral
palsy: no proven tactile intervention exists for them. Duration
staircases are legitimate psychophysics (duration difference limens
follow Weber's law, PMC4439551), which matters because the motors
have fixed intensity and duration is the only stimulus dimension this
host can vary.

WHAT THIS MODE CANNOT CLAIM, said plainly:
- The ERM motors have a mechanical rise and stop time around 20 ms
  that is UNCHARACTERISED on this rig. Every duration and gap
  threshold inherits that bias, so thresholds here are within-person
  measures for tracking change, never comparable to published
  electrical-stimulus norms, until an accelerometer characterisation
  of the motors is done. The software adds its own floor on top:
  requests below GameEngine.MIN_PULSE_MS (20 ms) are clamped, each
  delivered pulse stretches by up to about one display frame, so the
  staircases here step by at least 17 ms and stop at a 40 ms floor
  (the measured region where levels stop being distinguishable).
- For carpal tunnel syndrome this suite is MEASUREMENT, not therapy:
  the definitive RCT of sensory relearning after carpal tunnel
  release was negative on tactile outcomes (Jerosch-Herold 2016,
  Journal of Hand Surgery European, n = 104).
- In-game scores are gameplay. Research numbers come from the
  notebook re-scoring the logged trials offline.

CUES AND CHANNELS. This mode BYPASSES the cue.* switches for its
stimuli BY DESIGN: the buzz is not a cue announcing a target, the
buzz IS the stimulus, so it goes out through engine.pulse_motor
whatever the before-press switches say (the Settings screen says so
next to those switches). Nothing on screen may identify the target
finger, ever, in any cue configuration: the screen holds a calm
focus point and the answer lives in the hand, so cue_target_shown is
FALSE on every trial row. After-press feedback cues are ordinary
feedback, not stimuli, and they still respect the toggles: a correct
response fires the shared confirmation cue only if cue.buzz_after or
cue.sound_after says to.

STAGES, in play order. One block runs the suite as a fixed ladder;
counts come from buzz_hunt.* in the config.

  LOCALISATION   hands flat, eyes on the focus point. One pulse on
                 one finger; press the finger that buzzed. About one
                 trial in ten is a catch trial: no buzz fires, and
                 the right response is to wait, which prices guessing
                 (the false-alarm rate for d-prime lives here). Pulse
                 duration runs a 2-down 1-up staircase per hand,
                 converging on the 70.7 percent point; every reversal
                 is logged. One staircase per HAND, interleaved
                 across that hand's fingers, not one per finger: a
                 per-finger staircase cannot collect enough trials to
                 converge inside one session, and the per-finger
                 spatial story is carried by the confusion matrix
                 instead.
  DISTRACTOR     bilateral sessions only. A distractor pulse fires on
                 a finger of the OTHER hand just before the target
                 pulse; press where the LAST buzz was. The distractor
                 must sit on the other hand because each hand has one
                 motor driver, so within-hand stimuli are strictly
                 sequential; only cross-hand pulses can overlap in
                 time, and the overlap is what makes the distractor
                 hard to gate out. These trials hold the duration at
                 the staircase's current level and do not move it, so
                 they measure selective attention at a fixed,
                 just-above-threshold intensity (the SENSe grading
                 principle) rather than folding two conditions into
                 one threshold.
  SEQUENCE SPAN  the pads play a buzz sequence; replay it in order.
                 Span grows by one after each correct replay and
                 shrinks by one after a miss. Every third span trial
                 secretly replays the SAME sequence for that length,
                 derived from the participant name exactly the way
                 pattern mode derives its trained sequence (SHA-256
                 of the trimmed, case-folded name with a version
                 tag), so the Hebb repetition-learning slope can be
                 read across sessions without the player ever being
                 told a sequence repeats. Within-hand pulses are
                 sequential by hardware; the docstring's constraint
                 is also the paradigm's: a span sequence is
                 sequential by definition.
  GAP DETECTION  one long buzz, or two short buzzes separated by a
                 silent gap, on one finger; tap that finger once for
                 one, twice for two. The long buzz lasts exactly two
                 shorts plus the gap, so total duration never gives
                 the answer away. Gap length runs a 2-down 1-up
                 staircase per hand with every reversal logged. The
                 literature's version answers on separate response
                 buttons; this rig has no spare response channel in
                 single-hand play, so the tap-count mapping is used
                 in BOTH hand modes to keep the measure comparable,
                 and the response window only opens after the
                 stimulus ends so tapping cannot collide with the
                 buzzing.

HANDS. A single-hand session runs that hand's four fingers; both
hands means all eight fingers with the stimulus order balanced per
hand and per finger by the paired scheduler, and the confusion
matrix gains its cross-hand cells. The distractor stage only exists
bilaterally, because it needs an other hand.

PACING. Two rules keep the block from going on too long while still
getting hard quickly (both measured on a headless simulated block at
the shipped settings). The staircases open with the standard
accelerated approach (single-correct steps at double size until the
first reversal, then plain 2-down 1-up; Levitt 1971, Leek 2001):
without it the first third of the localisation stage ran at 200-300
ms, trivially easy for an ordinary hand, and the unilateral gap
stage often closed with too few reversals for any threshold
estimate at all. And the whole block sits under
buzz_hunt.session_cap_min (shipped 15 minutes), enforced only
between trials so a trial in flight always finishes: the measured
worst case was 9.9 minutes for one hand but 19.7 bilaterally, and
past a quarter hour of sustained tactile attention the tail trials
measure fatigue more than perception. A capped block keeps
everything already played and writes end_reason time_cap.

LOGGING. Localisation and distractor rows: waveform "buzz",
waveform_params carrying the target lane, requested duration, catch
flag and any distractor lane / lead, and segment_times bracketing
the stimulus and the response window in raw-stream seconds. Span
rows: waveform "buzz_seq" with the full sequence packed in params
plus the hebb flag. Gap rows: waveform "buzz_gap" with kind, short
length and gap. pulses_from_params rebuilds the exact pulse train
(lane, onset, duration) from any of these rows without this module's
rng, which is the notebook contract; the raw log's pulse_motor
events, one per delivered pulse, are the cross-check. Requested
durations are logged as the stimulus level; the delivered duration
is the request stretched by up to about a frame plus the motor's
mechanical response, which is the honest uncertainty statement.
Staircase reversals are logged as buzz_hunt_reversal events as they
happen. Catch outcomes go through engine.log_reaction_event exactly
like reaction mode's, so a survived catch never inflates the hit
counters. cue_target_shown is FALSE on every row (nothing on screen
names the finger); cue_flags records the block's switch state as
ever.
"""
from __future__ import annotations

import hashlib
import logging
import random
import time
from collections import deque
from typing import TYPE_CHECKING

from ...data.logger import ContinuousTrialLog
from ...hardware.eeg_trigger import CODES as EEG_CODES
from ..rest_skip import WaitSkip
from ..scheduling import BalancedScheduler, PairedBalancedScheduler
from ..scoring import ScoreConfig, TrialResult, classify
from .classic import PendingTrial
from .force_pilot import FINGER_WORDS

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


# The measured floor of distinguishable pulse levels on this rig: the
# 20 ms command floor plus one-frame stretch means requests under
# about 40 ms all deliver much the same buzz, so no staircase is
# allowed below it (foundation contract, measured 2026-08).
LEVEL_FLOOR_MS = 40.0
# Frame quantisation on the early-STOP path: steps below one display
# frame ask for differences the hardware cannot express.
MIN_STEP_MS = 17.0


# ---- participant-stable material -------------------------------------------
def participant_hebb_seed(name: str) -> int:
    """Deterministic Hebb-sequence seed from the participant name.
    Same convention as pattern mode's participant_seed: trimmed and
    case-folded so "Basil " and "basil" share material, version-tagged
    so a future generator change cannot silently rewrite an existing
    participant's hidden sequences."""
    norm = (name or "").strip().lower() or "anonymous"
    digest = hashlib.sha256(f"{norm}|buzzhunt_v1".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def hebb_sequence(p_seed: int, length: int, lanes: list[int]) -> list[int]:
    """The participant's hidden repeating sequence for one span
    length. Deterministic from (participant seed, length, lane pool),
    so it is identical every session the same participant plays the
    same hand selection, which is what makes the Hebb learning slope
    readable across sessions. No immediate repeats: two pulses on the
    same finger back to back read as one long buzz."""
    pool = sorted(int(x) for x in lanes)
    rng = random.Random((int(p_seed) << 8) ^ (int(length) * 0x9E3779B1)
                        ^ len(pool))
    out: list[int] = []
    while len(out) < int(length):
        pick = pool[rng.randrange(len(pool))]
        if out and pick == out[-1] and len(pool) > 1:
            continue
        out.append(pick)
    return out


def draw_sequence(seed: int, length: int, lanes: list[int]) -> list[int]:
    """A fresh (non-Hebb) span sequence from the trial seed. Same
    no-immediate-repeat rule as the Hebb generator so the two kinds of
    trial differ only in whether the material repeats."""
    pool = sorted(int(x) for x in lanes)
    rng = random.Random(int(seed))
    out: list[int] = []
    while len(out) < int(length):
        pick = pool[rng.randrange(len(pool))]
        if out and pick == out[-1] and len(pool) > 1:
            continue
        out.append(pick)
    return out


def pack_lanes(seq: list[int]) -> str:
    """Lane sequence as one params-safe token ("2-5-1", global
    0-based lanes). "-" because "=" and ";" are the params
    separators."""
    return "-".join(str(int(x)) for x in seq)


def parse_lanes(token) -> list[int]:
    return [int(float(p)) for p in str(token).split("-") if p != ""]


# ---- pure stimulus reconstruction ------------------------------------------
# The notebook contract: every trial row's pulse train must rebuild
# from (waveform, params) alone, as (lane, onset_s, duration_ms)
# relative to the stimulus start. The mode plays from this same
# function, so what was played and what is logged cannot drift apart.


def pulses_from_params(waveform: str,
                       p: dict) -> list[tuple[int, float, float]]:
    if waveform == "buzz":
        if int(round(float(p.get("catch", 0)))):
            return []
        out = []
        lead_s = 0.0
        if "distractor_lane" in p:
            lead_s = float(p["distractor_lead_ms"]) / 1000.0
            out.append((int(float(p["distractor_lane"])), 0.0,
                        float(p["distractor_ms"])))
        out.append((int(float(p["lane"])), lead_s, float(p["dur_ms"])))
        return out
    if waveform == "buzz_seq":
        seq = parse_lanes(p["seq"])
        ioi = float(p["ioi_ms"]) / 1000.0
        dur = float(p["pulse_ms"])
        return [(lane, i * ioi, dur) for i, lane in enumerate(seq)]
    if waveform == "buzz_gap":
        lane = int(float(p["lane"]))
        short = float(p["short_ms"])
        gap = float(p["gap_ms"])
        if int(round(float(p["two"]))):
            return [(lane, 0.0, short),
                    (lane, (short + gap) / 1000.0, short)]
        return [(lane, 0.0, 2.0 * short + gap)]
    raise ValueError(f"unknown buzz waveform {waveform!r}")


def stimulus_span_s(waveform: str, p: dict) -> float:
    """Stimulus length from first onset to last offset, seconds."""
    pulses = pulses_from_params(waveform, p)
    if not pulses:
        return 0.0
    return max(on + d / 1000.0 for _lane, on, d in pulses)


# ---- the 2-down 1-up staircase ---------------------------------------------
class Staircase:
    """Transformed up-down staircase, 2-down 1-up, converging on the
    70.7 percent correct point (Levitt 1971's rule). Additive steps:
    the foundation floor makes the usable range narrow enough that
    log steps buy nothing, and an additive step is what the frame
    quantisation argument is stated in. Every reversal is recorded;
    the threshold estimate is the mean of the last few reversals,
    which is the standard readout.

    `fast_start` prepends the standard accelerated approach (Levitt
    1971 section IV; Leek 2001 review): until the FIRST reversal a
    single correct steps down and the step is doubled, so the level
    reaches the threshold region in a handful of trials instead of
    burning a third of the stage getting there. From the first error
    on, the rule above takes over at the base step. Measured on the
    shipped localisation stage with a simulated 90 ms observer, the
    plain rule dealt its first eight trials at a mean of 240 ms (well
    above threshold, trivially easy) and put 6 of 28 staircased
    trials within 1.5x of the observer's threshold; fast_start put
    the approach inside the first four trials and roughly tripled the
    time spent near threshold. The up-step after the first error uses
    the base step (a doubled recovery step would overshoot the region
    the descent just found)."""

    def __init__(self, start: float, step: float, floor: float,
                 ceiling: float, fast_start: bool = False) -> None:
        self.level = float(start)
        self.step = max(MIN_STEP_MS, float(step))
        self.floor = float(floor)
        self.ceiling = max(float(ceiling), self.floor)
        self.level = min(max(self.level, self.floor), self.ceiling)
        self.reversals: list[float] = []
        self._run = 0                 # consecutive correct at this level
        self._direction = 0           # -1 falling, +1 rising, 0 unmoved
        self._fast = bool(fast_start)  # accelerated approach phase

    def record(self, correct: bool) -> bool:
        """Apply one response. Returns True when this response caused
        a reversal (the caller logs it)."""
        move = 0
        if correct:
            self._run += 1
            if self._run >= (1 if self._fast else 2):
                self._run = 0
                move = -1
        else:
            self._run = 0
            move = +1
        if move == 0:
            return False
        reversal = self._direction != 0 and move != self._direction
        if reversal:
            self.reversals.append(self.level)
            # The first reversal ends the accelerated approach; the
            # up-step it triggers already runs at the base step.
            self._fast = False
        step = self.step * (2.0 if self._fast else 1.0)
        self._direction = move
        self.level = min(max(self.level + move * step, self.floor),
                         self.ceiling)
        return reversal

    def estimate(self, last_n: int) -> float | None:
        """Mean of the last n reversal levels; None until there are at
        least two reversals to average."""
        if len(self.reversals) < 2:
            return None
        tail = self.reversals[-max(2, int(last_n)):]
        return sum(tail) / len(tail)


class BuzzHuntMode(WaitSkip):
    name = "Buzz Hunt"

    # Reward for correctly waiting out a catch trial. Small on
    # purpose, same reasoning as reaction mode: waiting is right and
    # needs acknowledging, but it must never rival a real hit.
    CATCH_REWARD = 1
    # Points per correctly replayed span item, on top of the outcome.
    SPAN_ITEM_POINTS = 2
    # Fingers must be quiet this long before a trial's wait starts, so
    # a lingering press cannot read as a lightning response.
    REST_GATE_S = 0.5
    # Second tap in a gap trial must land within this of the first to
    # read as a deliberate double tap; the window close is the real
    # judge, this only shapes the on-screen tap dots.
    STAGE_ORDER = ("loc", "distractor", "span", "gap")
    STAGE_TITLES = {
        "loc": "FIND THE BUZZ",
        "distractor": "IGNORE THE DECOY",
        "span": "REPLAY THE PATTERN",
        "gap": "ONE BUZZ OR TWO?",
    }

    def __init__(self, engine: "GameEngine",
                 lanes_by_hand: dict[str, list[int]],
                 participant_seed: int,
                 loc_trials_per_hand: int,
                 catch_rate: float,
                 start_ms: float,
                 step_ms: float,
                 floor_ms: float,
                 ceil_ms: float,
                 threshold_reversals: int,
                 distractor_trials_per_hand: int,
                 distractor_lead_ms: float,
                 span_trials: int,
                 span_start: int,
                 span_pulse_ms: float,
                 span_ioi_ms: float,
                 hebb_every: int,
                 gap_trials_per_hand: int,
                 gap_start_ms: float,
                 gap_step_ms: float,
                 gap_floor_ms: float,
                 gap_short_ms: float,
                 wait_lo_s: float,
                 wait_hi_s: float,
                 response_window_s: float,
                 replay_item_s: float,
                 announce_s: float,
                 rest_s: float,
                 stage_intro_s: float,
                 score_cfg: ScoreConfig,
                 seed: int = 0,
                 demo_trials: int | None = None,
                 session_cap_min: float = 15.0) -> None:
        self.engine = engine
        self.hands = {h: list(v)[:4] for h, v in lanes_by_hand.items() if v}
        if not self.hands:
            self.hands = {"right": [0, 1, 2, 3]}
        self.hand_names = list(self.hands)
        self.bilateral = len(self.hand_names) > 1
        self.p_seed = int(participant_seed)
        self.catch_rate = min(max(float(catch_rate), 0.0), 0.5)
        # Duration staircase knobs, clamped to what the hardware can
        # honestly express (see the docstring's claim limits).
        self.floor_ms = max(LEVEL_FLOOR_MS, float(floor_ms))
        self.ceil_ms = max(self.floor_ms, float(ceil_ms))
        self.start_ms = min(max(float(start_ms), self.floor_ms),
                            self.ceil_ms)
        self.step_ms = max(MIN_STEP_MS, float(step_ms))
        self.threshold_reversals = max(2, int(threshold_reversals))
        self.distractor_lead_ms = max(0.0, float(distractor_lead_ms))
        self.span_start = max(2, int(span_start))
        self.span_pulse_ms = max(LEVEL_FLOOR_MS, float(span_pulse_ms))
        self.span_ioi_ms = max(self.span_pulse_ms + 100.0,
                               float(span_ioi_ms))
        self.hebb_every = max(2, int(hebb_every))
        self.gap_short_ms = max(LEVEL_FLOOR_MS, float(gap_short_ms))
        self.gap_floor_ms = max(MIN_STEP_MS * 2, float(gap_floor_ms))
        self.gap_start_ms = max(self.gap_floor_ms, float(gap_start_ms))
        self.gap_step_ms = max(MIN_STEP_MS, float(gap_step_ms))
        self.wait_lo_s = max(0.3, float(wait_lo_s))
        self.wait_hi_s = max(self.wait_lo_s, float(wait_hi_s))
        self.response_window_s = max(1.0, float(response_window_s))
        self.replay_item_s = max(0.5, float(replay_item_s))
        self.announce_s = max(0.5, float(announce_s))
        self.rest_s = max(0.5, float(rest_s))
        self.stage_intro_s = max(self.announce_s, float(stage_intro_s))
        # Hard wall-clock cap on the block, enforced between trials
        # only (a trial in flight always finishes and is scored).
        # Sustained tactile discrimination is attention-heavy, and the
        # measured shipped envelope ran to ~20 minutes bilaterally in
        # the worst case; past the cap the tail trials measure fatigue
        # more than perception. Everything already played is kept and
        # summarised; end_reason says time_cap.
        self.session_cap_s = max(60.0, float(session_cap_min) * 60.0)
        self.score_cfg = score_cfg
        self.rng = random.Random(int(seed))
        self.demo = demo_trials is not None

        n_hands = len(self.hand_names)
        n_loc = max(1, int(loc_trials_per_hand)) * n_hands
        n_dis = (max(0, int(distractor_trials_per_hand)) * n_hands
                 if self.bilateral else 0)
        n_span = max(0, int(span_trials))
        n_gap = max(0, int(gap_trials_per_hand)) * n_hands
        if self.demo:
            # Test Mode: a taste of every stage inside a minute or
            # two. The trial SHAPE stays intact (a catch still waits,
            # a span still replays) so the demo shows the real thing.
            cap = max(2, int(demo_trials))
            n_loc = max(2, cap // 3)
            n_dis = 1 if self.bilateral else 0
            n_span = 2
            n_gap = 2
            self.wait_lo_s = min(self.wait_lo_s, 0.5)
            self.wait_hi_s = min(self.wait_hi_s, 1.0)
            self.response_window_s = min(self.response_window_s, 2.5)
            self.announce_s = min(self.announce_s, 1.2)
            self.rest_s = min(self.rest_s, 1.5)
            self.stage_intro_s = min(self.stage_intro_s, 2.0)
        self._stage_counts = {"loc": n_loc, "distractor": n_dis,
                              "span": n_span, "gap": n_gap}
        self._stage_plan: list[str] = []
        for stage in self.STAGE_ORDER:
            self._stage_plan += [stage] * self._stage_counts[stage]
        self.total_trials = len(self._stage_plan)

        # Stimulus-order balance, per the brief: fingers stay equal
        # within a hand and hands stay equal across the block.
        def _sched():
            if self.bilateral:
                return PairedBalancedScheduler(self.hands, self.rng)
            return BalancedScheduler(self.hands[self.hand_names[0]],
                                     self.rng)

        self._loc_sched = _sched()
        self._dis_sched = _sched() if self.bilateral else None
        self._gap_sched = _sched()
        # One-buzz-or-two dealt from a balanced bag so a run of "two"
        # answers cannot teach a response bias the staircase then
        # misreads.
        self._gap_kind_bag = BalancedScheduler([0, 1], self.rng,
                                               avoid_repeats=False)

        # Per-hand staircases. Duration starts where the previous
        # block in this app session ended (near threshold), which the
        # engine carries the same way it carries the other modes'
        # levels; a restart falls back to the config start.
        carried = getattr(engine, "_buzz_hunt_start_ms", None)
        self._dur_stair: dict[str, Staircase] = {}
        self._gap_stair: dict[str, Staircase] = {}
        self._dur_start: dict[str, float] = {}
        for hand in self.hand_names:
            start = self.start_ms
            if isinstance(carried, dict) and hand in carried:
                try:
                    start = min(max(float(carried[hand]), self.floor_ms),
                                self.ceil_ms)
                except (TypeError, ValueError):
                    start = self.start_ms
            self._dur_start[hand] = start
            # fast_start on both stairs: the accelerated approach is
            # what makes a 32-trial stage spend its trials near
            # threshold instead of on the descent (see Staircase).
            self._dur_stair[hand] = Staircase(
                start, self.step_ms, self.floor_ms, self.ceil_ms,
                fast_start=True)
            self._gap_stair[hand] = Staircase(
                self.gap_start_ms, self.gap_step_ms, self.gap_floor_ms,
                self.gap_start_ms * 2, fast_start=True)

        # Phase machine:
        #   no_input -> (parked; the buzz needs the hardware)
        #   stage -> announce -> trial(wait -> play -> respond) ->
        #   feedback -> announce ... -> done
        self.phase = "init"
        self.end_reason: str | None = None
        self._t0: float | None = None
        self._phase_until: float | None = None
        self._presses: deque = deque()

        # Trial state.
        self.trial_counter = 0
        self.trials_done = 0
        self.stage = "loc"
        self.stage_shown: str | None = None
        self.sub = "wait"
        self.hand: str = self.hand_names[0]
        self.lane: int = self.hands[self.hand][0]
        self.trial_seed = 0
        self.params: dict = {}
        self.waveform = "buzz"
        self.catch = False
        self.sequence: list[int] = []
        self.span_len = self.span_start
        self.is_hebb = False
        self.gap_two = False
        self.active: PendingTrial | None = None
        self.trial_t0: float | None = None
        self._wait_s = 1.0
        self._quiet_since: float | None = None
        self._pulse_plan: list[tuple[int, float, float]] = []
        self._pulse_idx = 0
        self._stim_seg_open = False
        self._stim_delivered: bool | None = None
        self._play_t0: float | None = None
        self._respond_t0: float | None = None
        self._target_on: float | None = None
        self._resp_presses: list[tuple[int, float]] = []
        self._last_result: dict | None = None
        self.stage_msg = ""

        # Aggregates. _confusion is localisation only (the Weber 2023
        # analogue); distractor lures are counted separately, not
        # pooled into it (audit finding #95).
        self._confusion: dict[str, dict[str, int]] = {}
        self._distractor_confusion: dict[str, dict[str, int]] = {}
        self._loc_records: list[dict] = []
        self._dis_records: list[dict] = []
        self._span_records: list[dict] = []
        self._gap_records: list[dict] = []
        self._catch_n = 0
        self._catch_fa = 0
        # Keyed by self.stage at the moment the early press landed
        # (loc/distractor/span/gap), not a single block-wide count: an
        # early press during a DISTRACTOR trial was previously folded
        # into block_stats()['loc']['early_presses'] even when zero loc
        # trials had run yet, misattributing it to the wrong stage.
        self._early_presses: dict[str, int] = {}
        self._span_max_correct = 0

    # ---- plumbing shared with the other modes ------------------------------
    def queue_press(self, ev) -> None:
        self._presses.append(ev)

    def handle_event(self, e) -> None:
        # No keyboard fallback by design: a keyboard cannot buzz a
        # finger, so there is nothing to localise. The screen says so.
        return

    @property
    def current_timeout_s(self) -> float:
        return self.response_window_s

    def on_resume(self, pause_dur: float) -> None:
        for attr in ("_t0", "_phase_until", "_quiet_since", "_play_t0",
                     "_respond_t0", "_target_on", "trial_t0"):
            v = getattr(self, attr)
            if v is not None:
                setattr(self, attr, v + pause_dur)
        if self.phase == "trial":
            # A pause interrupts the pulse train or the response
            # window, so the trial is unscoreable: restart it. Nothing
            # was logged for it yet; the orphaned segment markers are
            # tied off by a trial_restart event so the notebook can
            # discard them. The material is REDRAWN, not replayed:
            # the player may have heard part (or all) of the stimulus
            # before pausing, and replaying it would grant a second
            # exposure the score treats as one, which for a gap trial
            # hands over the answer (the Esc chip made this a
            # repeatable exploit). Hebb spans keep their hidden
            # sequence by design; _redraw_interrupted_material only
            # changes novel spans and gap kinds.
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "trial_restart", lane=self.lane,
                    detail=f"trial_id={self.trial_counter}",
                    hand=self.engine.hand_mode)
            self.engine.stop_all_motors()
            self._redraw_interrupted_material()
            self._enter_announce(time.perf_counter())

    # ---- main tick ---------------------------------------------------------
    def update(self, dt: float) -> None:
        self._tick(time.perf_counter())

    def _tick(self, now: float) -> None:
        if self._t0 is None:
            self._t0 = now
            self._start(now)
        if self.phase in ("done", "no_input"):
            self._presses.clear()
            return
        # Session cap, checked only between trials (stage card, ready
        # card, result card) so a trial in flight always finishes and
        # is scored. It also fires on a block parked on a card with
        # nobody at the pads, the same lesson chords learnt: a cap
        # that only ticks at trial closes never fires when no trial
        # ever closes.
        if (self.phase in ("stage", "announce", "feedback")
                and (now - self._t0) > self.session_cap_s):
            self._end("time_cap")
            return
        if self.phase in ("stage", "announce"):
            self._presses.clear()
            if self._phase_until is not None and now >= self._phase_until:
                if self.phase == "stage":
                    self._enter_announce(now)
                else:
                    self._start_trial(now)
            return
        if self.phase == "feedback":
            self._presses.clear()
            if self._phase_until is not None and now >= self._phase_until:
                self._next_or_end(now)
            return
        if self.phase == "trial":
            self._trial_frame(now)

    def _start(self, now: float) -> None:
        source = getattr(self.engine, "source", None)
        if source is not None and not getattr(source, "provides_samples",
                                              True):
            # A keyboard rig has no motors, so there is no stimulus to
            # deliver. The screen explains; Esc leaves.
            self.phase = "no_input"
            return
        self._prepare_trial()
        self._enter_stage(now)

    # ---- trial selection ---------------------------------------------------
    def _lane_owner(self, lane: int) -> tuple[str, int]:
        for hand, lanes in self.hands.items():
            if lane in lanes:
                return hand, lanes.index(lane)
        return self.hand_names[0], 0

    def _next_lane(self, sched) -> int:
        if self.bilateral:
            return sched.next()[1]
        return sched.next()

    def _other_hand_lane(self, hand: str) -> int:
        others = [h for h in self.hand_names if h != hand]
        pool = self.hands[others[0]] if others else self.hands[hand]
        return pool[self.rng.randrange(len(pool))]

    def _active_lanes(self) -> list[int]:
        return [ln for h in self.hand_names for ln in self.hands[h]]

    def _prepare_trial(self) -> None:
        """Draw the next trial's whole plan into self.params. The
        params dict is the single source of truth: playback runs from
        pulses_from_params on it and the CSV row logs it verbatim."""
        self.stage = (self._stage_plan[self.trials_done]
                      if self.trials_done < len(self._stage_plan)
                      else "loc")
        self.trial_counter += 1
        self.trial_seed = self.rng.randrange(2 ** 32)
        draw = random.Random(self.trial_seed)
        self._wait_s = draw.uniform(self.wait_lo_s, self.wait_hi_s)
        self.catch = False
        self.is_hebb = False
        self.sequence = []
        self.gap_two = False
        if self.stage == "loc":
            self.waveform = "buzz"
            self.catch = draw.random() < self.catch_rate
            if self.catch:
                self._catch_n += 1
                self.lane = -1
                # No real lane fires on a catch, but in bilateral play
                # it still logically stands in for one hand's worth of
                # waiting. Drawing that hand fairly (instead of always
                # hand_names[0]) means a false alarm can be charged to
                # the hand it happened for, so neither hand's FA rate
                # is silently undercounted.
                self.hand = (draw.choice(self.hand_names)
                             if self.bilateral else self.hand_names[0])
                self.params = {"catch": 1,
                               "window_ms": self.response_window_s * 1000.0}
            else:
                self.lane = self._next_lane(self._loc_sched)
                self.hand, _f = self._lane_owner(self.lane)
                self.params = {
                    "catch": 0, "lane": self.lane,
                    "dur_ms": self._dur_stair[self.hand].level,
                    "window_ms": self.response_window_s * 1000.0,
                }
        elif self.stage == "distractor":
            self.waveform = "buzz"
            self.lane = self._next_lane(self._dis_sched or self._loc_sched)
            self.hand, _f = self._lane_owner(self.lane)
            self.params = {
                "catch": 0, "lane": self.lane,
                "dur_ms": self._dur_stair[self.hand].level,
                "distractor_lane": self._other_hand_lane(self.hand),
                "distractor_ms": self._dur_stair[self.hand].level,
                "distractor_lead_ms": self.distractor_lead_ms,
                "window_ms": self.response_window_s * 1000.0,
            }
        elif self.stage == "span":
            self.waveform = "buzz_seq"
            lanes = self._active_lanes()
            span_done = len(self._span_records)
            self.is_hebb = (span_done + 1) % self.hebb_every == 0
            if self.is_hebb:
                self.sequence = hebb_sequence(self.p_seed, self.span_len,
                                              lanes)
            else:
                self.sequence = draw_sequence(self.trial_seed,
                                              self.span_len, lanes)
            self.lane = self.sequence[0]
            self.hand, _f = self._lane_owner(self.lane)
            self.params = {
                "seq": pack_lanes(self.sequence),
                "len": self.span_len,
                "pulse_ms": self.span_pulse_ms,
                "ioi_ms": self.span_ioi_ms,
                "hebb": 1 if self.is_hebb else 0,
            }
        else:                                  # gap
            self.waveform = "buzz_gap"
            self.lane = self._next_lane(self._gap_sched)
            self.hand, _f = self._lane_owner(self.lane)
            self.gap_two = bool(self._gap_kind_bag.next())
            self.params = {
                "lane": self.lane, "two": 1 if self.gap_two else 0,
                "short_ms": self.gap_short_ms,
                "gap_ms": self._gap_stair[self.hand].level,
                "window_ms": self.response_window_s * 1000.0,
            }
        self._pulse_plan = pulses_from_params(self.waveform, self.params)

    # ---- phase entries -----------------------------------------------------
    def _enter_stage(self, now: float) -> None:
        self.phase = "stage"
        self.stage_shown = self.stage
        self._phase_until = now + self.stage_intro_s
        # The stage card explains what the next stretch of trials is
        # asking for. A patient who has read it, or a researcher on
        # their fifth run, can move on; nothing measures how long the
        # card was up.
        self.arm_wait("stage", self._phase_until, self._enter_announce,
                      started_at=now)

    def _enter_announce(self, now: float) -> None:
        self.phase = "announce"
        self._phase_until = now + self.announce_s
        self.arm_wait("announce", self._phase_until, self._start_trial,
                      started_at=now)
        self.sub = "wait"
        self._quiet_since = None
        self._pulse_idx = 0
        self._stim_seg_open = False
        self._play_t0 = None
        self._respond_t0 = None
        self._target_on = None
        self._resp_presses = []
        self._presses.clear()

    def _start_trial(self, now: float) -> None:
        self.phase = "trial"
        self.sub = "wait"
        self._phase_until = None
        # The pre-buzz wait inside a trial is NOT armed. It is the
        # foreperiod: a jittered, unpredictable delay is what stops
        # the buzz from being anticipated, and a button that cuts it
        # short would hand the patient the onset time. It is part of
        # the stimulus, not a rest.
        self.clear_wait()
        self.trial_t0 = now
        self._quiet_since = None
        self.active = PendingTrial(
            trial_id=self.trial_counter, lane=max(self.lane, 0),
            stim_t_perf=now, keys_pressed=[], incorrect_presses=[])
        # Per-trial CSV stamps. No on_stim fires in this mode, so the
        # row's cue context is set here: the switch state for the
        # record, target NEVER shown on screen (the whole design), and
        # the response window as the RT censoring limit.
        cues = self.engine.cue_settings()
        self.engine._last_cue_code = cues.code
        self.engine._last_target_shown = False
        # The row's timeout_ms is documented as the RT censoring
        # limit, so it must be THIS stage's real window: a span trial
        # extends the base window by replay time per item, and
        # stamping the bare response_window_s made a 4-item span row
        # claim 3000 ms when the actual window was 9000 ms. The
        # material is already drawn by _prepare_trial, so
        # _respond_window_s answers correctly here.
        self.engine._last_stim_timeout_ms = (
            self._respond_window_s() * 1000.0)
        # Delivery tracking for this trial's pulse train: None means
        # no pulse is expected (a catch trial), True until a
        # pulse_motor call reports failure, then sticky False. Set
        # here rather than left over from the previous trial so a
        # dropout on trial N cannot be misread on trial N+1.
        self._stim_delivered = None if not self._pulse_plan else True
        self.engine._last_stim_delivered = self._stim_delivered
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "buzz_hunt_trial", lane=max(self.lane, 0), t_perf=now,
                detail=(f"trial_id={self.trial_counter};"
                        f"stage={self.stage};seed={self.trial_seed};"
                        f"waveform={self.waveform}"),
                hand=self.engine.hand_mode)

    # ---- the trial frame ---------------------------------------------------
    def _fingers_down(self) -> bool:
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

    def _trial_frame(self, now: float) -> None:
        if self.sub == "wait":
            self._wait_frame(now)
        elif self.sub == "play":
            self._play_frame(now)
        elif self.sub == "respond":
            self._respond_frame(now)

    def _wait_frame(self, now: float) -> None:
        # Quiet gate, then the drawn wait. A press during either
        # restarts the wait gently: it cannot be a response to a
        # stimulus that has not fired, and letting it stand would
        # contaminate the false-alarm bookkeeping.
        if self._presses:
            self._presses.clear()
            self._early_presses[self.stage] = (
                self._early_presses.get(self.stage, 0) + 1)
            self._quiet_since = None
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "buzz_hunt_early", lane=max(self.lane, 0),
                    detail=f"trial_id={self.trial_counter};sub=wait",
                    hand=self.engine.hand_mode)
            return
        if self._fingers_down():
            self._quiet_since = None
            return
        if self._quiet_since is None:
            self._quiet_since = now
            return
        if now - self._quiet_since >= self.REST_GATE_S + self._wait_s:
            self._begin_play(now)

    def _begin_play(self, now: float) -> None:
        self.sub = "play"
        self._play_t0 = now
        self._pulse_idx = 0
        span = stimulus_span_s(self.waveform, self.params)
        # Response opens at target onset for localisation (a fast
        # press mid-buzz is a legitimate response) and at stimulus end
        # for sequences and gap counts (the answer needs the whole
        # stimulus). Catch trials have no pulses: the window opens now
        # and correct behaviour is silence.
        if self.waveform == "buzz":
            lead = (float(self.params.get("distractor_lead_ms", 0.0))
                    / 1000.0 if "distractor_lane" in self.params else 0.0)
            self._target_on = now + lead
            self._respond_t0 = self._target_on
        else:
            self._target_on = now
            self._respond_t0 = now + span
        if self.active is not None:
            self.active.stim_t_perf = self._target_on
        self.engine.log_segment_start("stim", self.trial_counter,
                                      max(self.lane, 0), now)
        self._stim_seg_open = True
        if not self._pulse_plan:
            # Catch trial: no stimulus, straight to the silent window.
            self._close_stim_marker(now)
            self.sub = "respond"
            self.engine.log_segment_start("respond", self.trial_counter,
                                          max(self.lane, 0), now)

    def _close_stim_marker(self, now: float) -> None:
        """End the raw-stream stim marker exactly once. Needed as a
        helper because in localisation the response window overlaps
        the tail of the buzz, so the marker can close either during
        the respond frames or, on a very fast press, at trial close."""
        if self._stim_seg_open:
            self._stim_seg_open = False
            self.engine.log_segment_end("stim", self.trial_counter,
                                        max(self.lane, 0), now)

    def _redraw_interrupted_material(self) -> None:
        """A press during span or gap PLAYBACK means the player heard
        only part of the stimulus before the trial restarted; simply
        replaying the exact same material (same seed, same sequence
        or gap kind) would give an extra, uncounted exposure to a
        memory or threshold-adjacent stimulus, and the retried trial
        then scores as an ordinary single-exposure trial. Draw fresh
        material for the same trial slot instead. A Hebb span trial
        keeps its deterministic hidden sequence either way (that is
        the point of it being derived from the participant, not the
        trial seed), so this only ever changes what a NOVEL span
        trial or a gap trial's kind presents on the retry."""
        self.trial_seed = self.rng.randrange(2 ** 32)
        if self.waveform == "buzz_seq" and not self.is_hebb:
            lanes = self._active_lanes()
            self.sequence = draw_sequence(self.trial_seed, self.span_len,
                                          lanes)
            self.lane = self.sequence[0]
            self.hand, _f = self._lane_owner(self.lane)
            self.params["seq"] = pack_lanes(self.sequence)
        elif self.waveform == "buzz_gap":
            draw = random.Random(self.trial_seed)
            self.gap_two = draw.random() < 0.5
            self.params["two"] = 1 if self.gap_two else 0
        self._pulse_plan = pulses_from_params(self.waveform, self.params)

    def _play_frame(self, now: float) -> None:
        t = now - (self._play_t0 or now)
        while (self._pulse_idx < len(self._pulse_plan)
               and t >= self._pulse_plan[self._pulse_idx][1]):
            lane, _on, dur = self._pulse_plan[self._pulse_idx]
            # Timing guard for the pulses AFTER the first: a frame
            # stall longer than the planned inter-pulse gap dispatches
            # the overdue STOP and the next STIM in the same frame,
            # collapsing a gap trial's silent gap to ~0 (one merged
            # buzz) while the row still logs the requested gap and the
            # staircase moves on a stimulus that never was two buzzes.
            # Half the planned spacing is the tolerance: past that the
            # delivered timing no longer resembles the plan, so the
            # trial is voided like a dropped pulse (stim_delivered
            # FALSE keeps it out of every scored aggregate).
            #
            # SAME BOARD ONLY. The guard protects silence on a shared
            # motor driver; a distractor trial's two pulses sit on
            # DIFFERENT boards, overlap on purpose (the overlap is
            # what makes the decoy hard to gate out) and their
            # planned silence shrinks below one display frame as the
            # staircase approaches 150 ms duration, at which point
            # this guard voided the trial on every ordinary 60 Hz
            # frame (measured: half the distractor stage voided at
            # just-above-threshold levels, exactly the trials the
            # stage exists for). A frame-late target pulse distorts
            # the fixed 150 ms lead by about a tenth, is recorded in
            # the raw pulse_motor events either way, and moves no
            # staircase, so cross-board plans skip the void.
            if self._pulse_idx > 0 and self._lane_owner(lane)[0] == \
                    self._lane_owner(self._pulse_plan[
                        self._pulse_idx - 1][0])[0]:
                prev_lane, prev_on, prev_dur = self._pulse_plan[
                    self._pulse_idx - 1]
                spacing = max(0.0, _on - (prev_on + prev_dur / 1000.0))
                late_s = t - _on
                if spacing > 0 and late_s > 0.5 * spacing:
                    self._stim_delivered = False
                    self.engine._last_stim_delivered = False
                    raw = getattr(self.engine, "raw_logger", None)
                    if raw:
                        raw.queue_event(
                            "stim_late_pulse", lane=lane,
                            detail=(f"late_s={late_s:.3f};"
                                    f"spacing_s={spacing:.3f}"),
                            hand=self.engine.hand_mode)
            ok = self.engine.pulse_motor(lane, dur)
            if self._pulse_idx == 0:
                # EEG buzz-as-stimulus marker (38). Anchored to the
                # moment the STIM byte left for the Arduino, because
                # here the buzz IS the stimulus; there is no flip to
                # anchor to. Motor mechanical rise (20-50 ms for ERM
                # motors) is a constant offset the bench measurement
                # supplies. Its own code keeps perception trials out
                # of the cued-response averages.
                send = getattr(self.engine, "_eeg_send", None)
                if callable(send):
                    send(EEG_CODES["stim_buzz_hunt"], lane=lane,
                         t_event=now)
            if not ok:
                # Sticky: one dropped pulse in a sequence or gap
                # train marks the whole trial's stimulus as
                # undelivered, matching the cue path's stim_delivered
                # convention (engine.py's on_stim_multi).
                self._stim_delivered = False
            self.engine._last_stim_delivered = self._stim_delivered
            self._pulse_idx += 1
        # Presses during playback (before the response opens) restart
        # the wait: for a sequence they mean the replay started early,
        # for a gap trial they collide with the stimulus itself.
        #
        # A distractor trial is the one exception: the window before
        # the response opens IS the decoy pulse (respond opens at
        # target onset, which sits distractor_lead_ms after play
        # starts). A press ON THE DECOY LANE in that window is the
        # patient falling for the decoy -- the natural, most likely
        # failure mode this stage exists to measure -- not a false
        # start on nothing. A silent same-trial retry would erase
        # that failure entirely: it never reaches the distractor
        # tallies and a clean retry afterward reports as a
        # lured-free 100% hit.
        if (self._presses and now < (self._respond_t0 or now)
                and self.waveform == "buzz"
                and "distractor_lane" in self.params
                and self._presses[0].lane == int(
                    self.params["distractor_lane"])):
            ev = self._presses.popleft()
            self._presses.clear()
            self._resp_presses.append((ev.lane, ev.t_perf))
            self.engine.stop_all_motors()
            self._close_stim_marker(now)
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "buzz_hunt_early", lane=max(self.lane, 0),
                    detail=(f"trial_id={self.trial_counter};"
                            f"sub=play;lured_early=True"),
                    hand=self.engine.hand_mode)
            self.sub = "respond"
            self.engine.log_segment_start("respond", self.trial_counter,
                                          max(self.lane, 0), now)
            self._close_buzz(now, responded=True)
            return
        # Any OTHER lane pressed during that same decoy window is a
        # guess made before the target has fired at all -- including
        # a lucky press on the finger that is about to become the
        # target. It must never be scored as a response to that
        # target (it would carry a negative RT and could read as a
        # Perfect hit) and it must not count toward distractor
        # accuracy either way, so it is logged as an anticipation
        # event, exactly like a reaction-mode catch false start, and
        # the trial closes without ever reaching classify() or
        # _dis_records.
        if (self._presses and now < (self._respond_t0 or now)
                and self.waveform == "buzz"
                and "distractor_lane" in self.params):
            ev = self._presses.popleft()
            self._presses.clear()
            self.engine.stop_all_motors()
            self._close_stim_marker(now)
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "buzz_hunt_early", lane=max(self.lane, 0),
                    detail=(f"trial_id={self.trial_counter};"
                            f"sub=play;anticipation=True"),
                    hand=self.engine.hand_mode)
            self._early_presses[self.stage] = (
                self._early_presses.get(self.stage, 0) + 1)
            self.engine.log_reaction_event(
                trial_id=self.trial_counter, lane=self.lane,
                label="Early", error_type="anticipation",
                pressed_lane=ev.lane,
                stimulus="distractor;anticipation",
                # Nothing on this mode's screen ever names a finger.
                target_shown=False,
                hand=self.hand)
            self.active = None
            self._finish_trial(now)
            return
        if self._presses and now < (self._respond_t0 or now):
            self._presses.clear()
            self._early_presses[self.stage] = (
                self._early_presses.get(self.stage, 0) + 1)
            self.engine.stop_all_motors()
            self._close_stim_marker(now)
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "buzz_hunt_early", lane=max(self.lane, 0),
                    detail=f"trial_id={self.trial_counter};sub=play",
                    hand=self.engine.hand_mode)
            self._redraw_interrupted_material()
            self.sub = "wait"
            self._quiet_since = None
            return
        stim_end = ((self._play_t0 or now)
                    + stimulus_span_s(self.waveform, self.params))
        open_at = self._respond_t0 or now
        if now >= open_at:
            self.sub = "respond"
            if now >= stim_end:
                self._close_stim_marker(now)
            self.engine.log_segment_start("respond", self.trial_counter,
                                          max(self.lane, 0), now)
            self._respond_frame(now)

    def _respond_window_s(self) -> float:
        if self.waveform == "buzz_seq":
            return self.response_window_s + self.replay_item_s * len(
                self.sequence)
        return self.response_window_s

    def _respond_frame(self, now: float) -> None:
        # For localisation the buzz may still be sounding while the
        # window is open; close its raw marker the frame it ends.
        if self._stim_seg_open:
            stim_end = ((self._play_t0 or now)
                        + stimulus_span_s(self.waveform, self.params))
            if now >= stim_end:
                self._close_stim_marker(stim_end)
        while self._presses:
            ev = self._presses.popleft()
            self._resp_presses.append((ev.lane, ev.t_perf))
            if self.waveform == "buzz":
                self._close_buzz(now, responded=True)
                return
            if (self.waveform == "buzz_seq"
                    and len(self._resp_presses) >= len(self.sequence)):
                self._close_span(now)
                return
        if now - (self._respond_t0 or now) >= self._respond_window_s():
            if self.waveform == "buzz":
                self._close_buzz(now, responded=False)
            elif self.waveform == "buzz_seq":
                self._close_span(now)
            else:
                self._close_gap(now)

    # ---- closing: localisation and distractor ------------------------------
    def _segments(self, now: float) -> list[tuple[str, float, float]]:
        play_t0 = self._play_t0 or now
        stim_end = play_t0 + stimulus_span_s(self.waveform, self.params)
        segs = [("stim", play_t0, min(stim_end, now))]
        if self._respond_t0 is not None:
            segs.append(("respond", self._respond_t0, now))
        return segs

    def _bump_confusion(self, stim_key: str, resp_key: str) -> None:
        row = self._confusion.setdefault(stim_key, {})
        row[resp_key] = row.get(resp_key, 0) + 1

    def _close_buzz(self, now: float, responded: bool) -> None:
        trial = self.active
        self.active = None
        self._close_stim_marker(now)
        self.engine.log_segment_end("respond", self.trial_counter,
                                    max(self.lane, 0), now)
        if self.catch:
            self._close_catch(now, responded)
            return
        press_lane, press_t = (self._resp_presses[0]
                               if self._resp_presses else (None, None))
        rt_ms = (None if press_t is None or self._target_on is None
                 else (press_t - self._target_on) * 1000.0)
        # If the hardware never delivered the buzz, nothing about this
        # trial says anything about the patient's perception: a press
        # is a guess, silence is not a felt-nothing report. Void it
        # rather than reading it as a real Miss (or, worse, a lucky
        # correct guess) and pushing the staircase on hardware noise.
        stim_failed = self._stim_delivered is False
        if stim_failed:
            self.engine._block_stim_failures += 1
            log.warning("Buzz Hunt stimulus not delivered for trial "
                         "%s. Check the Arduino connection.",
                         self.trial_counter)
        # Belt-and-braces: a press timestamped before the target
        # actually fired can only reach here through the lured-decoy
        # path above (where it is scored as a miss, not a hit), but
        # nothing else in this function may ever classify a negative
        # RT as a correct response to a target that has not sounded.
        correct = (not stim_failed and responded and press_lane == self.lane
                  and (rt_ms is None or rt_ms >= 0))
        stair = self._dur_stair[self.hand]
        distractor = "distractor_lane" in self.params
        lured = (distractor and press_lane is not None
                 and press_lane == int(self.params["distractor_lane"]))
        if not stim_failed:
            resp_key = "none" if press_lane is None else str(press_lane)
            if distractor:
                # A distractor press is a designed decoy-lure error,
                # an attention failure the player was told to expect
                # and gate out -- a different mechanism from the
                # uncued localisation confusion matrix this feeds
                # (Weber 2023's misreferral measure). Pooling the two
                # inflates cross-hand cells and dilutes the
                # adjacent-finger structure the loc-only matrix is
                # meant to show (audit finding #95), so distractor
                # presses get their own matrix.
                row = self._distractor_confusion.setdefault(
                    str(self.lane), {})
                row[resp_key] = row.get(resp_key, 0) + 1
            else:
                self._bump_confusion(str(self.lane), resp_key)
        if stim_failed or distractor:
            # Distractor trials run AT the staircase level but do not
            # move it (see the docstring): they measure attention at a
            # fixed just-above-threshold duration. A failed delivery
            # never moves the staircase either, for the reason above.
            reversal = False
        else:
            reversal = stair.record(correct)
        if reversal:
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "buzz_hunt_reversal", lane=self.lane,
                    detail=(f"stair=duration;hand={self.hand};"
                            f"level_ms={stair.reversals[-1]:.0f};"
                            f"n={len(stair.reversals)}"),
                    hand=self.engine.hand_mode)
        if correct:
            outcome = classify(rt_ms, self.score_cfg)
        else:
            outcome = TrialResult(label="Miss",
                                  points=self.score_cfg.miss_points,
                                  rt_ms=None)
        if trial is not None:
            if press_lane is not None:
                trial.keys_pressed.append(press_lane)
                if press_lane != self.lane and rt_ms is not None:
                    trial.incorrect_presses.append((press_lane, press_t))
            stimulus = (
                f"{self.stage};hand={self.hand};"
                f"finger={FINGER_WORDS[self.lane % 4].lower()};"
                f"dur_ms={float(self.params['dur_ms']):.0f};"
                f"stair_ms={stair.level:.0f};reversal={reversal};"
                f"lured={lured};stim_failed={stim_failed}")
            info = ContinuousTrialLog(waveform="buzz", params=self.params,
                                      seed=self.trial_seed,
                                      segments=self._segments(now))
            # A voided stim-failure trial where the patient DID press
            # gets its own error_type: the derived 'timeout' next to a
            # non-empty keys_pressed was internally inconsistent, and
            # any error_type=='timeout' filter silently pulled these
            # hardware rows in.
            self.engine.log_trial(trial, outcome, now, stimulus=stimulus,
                                  correct_lanes=[self.lane],
                                  continuous=info,
                                  error_type=("stim_failed"
                                              if stim_failed
                                              and outcome.label == "Miss"
                                              else None))
        if not stim_failed:
            # A trial whose buzz never fired is not a perception
            # sample: it must not water down (or, on a lucky guess,
            # inflate) localisation or distractor accuracy. The row
            # above still exists for the notebook to cross-check
            # against the raw pulse_motor delivered=NO events.
            rec = {"hand": self.hand, "lane": self.lane,
                   "dur_ms": float(self.params["dur_ms"]),
                   "correct": correct, "rt_ms": rt_ms,
                   "press_lane": press_lane, "lured": lured}
            (self._dis_records if distractor
             else self._loc_records).append(rec)
        self._last_result = {
            "stage": self.stage, "label": outcome.label,
            "correct": correct, "responded": responded,
            "hand": self.hand, "lane": self.lane,
            "press_lane": press_lane, "rt_ms": rt_ms,
            "dur_ms": float(self.params["dur_ms"]), "lured": lured,
            "stim_failed": stim_failed,
        }
        self._finish_trial(now)

    def _close_catch(self, now: float, responded: bool) -> None:
        press_lane, press_t = (self._resp_presses[0]
                               if self._resp_presses else (None, None))
        if responded and press_lane is not None:
            self._catch_fa += 1
            self._bump_confusion("none", str(press_lane))
            self.engine.log_reaction_event(
                trial_id=self.trial_counter, lane=None,
                label="Early", error_type="catch_false_start",
                pressed_lane=press_lane,
                stimulus="loc;catch",
                # Nothing on this mode's screen ever names a finger,
                # whatever the show_target toggle says.
                target_shown=False,
                # Without this, log_reaction_event falls back to the
                # session-level hand_mode ("both" in bilateral play),
                # which is not a hand at all and would silently drop
                # this false alarm out of either hand's FA rate.
                hand=self.hand)
            self._last_result = {"stage": "loc", "label": "FalseAlarm",
                                 "catch": True, "correct": False,
                                 "press_lane": press_lane}
        else:
            self.engine.log_reaction_event(
                trial_id=self.trial_counter, lane=None,
                label="CatchOk", error_type="",
                points=self.CATCH_REWARD,
                stimulus="loc;catch",
                target_shown=False,
                hand=self.hand)
            try:
                self.engine.score += self.CATCH_REWARD
                self.engine._last_gained = self.CATCH_REWARD
            except TypeError:
                pass
            self._last_result = {"stage": "loc", "label": "CatchOk",
                                 "catch": True, "correct": True,
                                 "press_lane": None}
        self._finish_trial(now)

    # ---- closing: span -----------------------------------------------------
    def _close_span(self, now: float) -> None:
        trial = self.active
        self.active = None
        self._close_stim_marker(now)
        self.engine.log_segment_end("respond", self.trial_counter,
                                    max(self.lane, 0), now)
        pressed = [lane for lane, _t in self._resp_presses]
        stim_failed = self._stim_delivered is False
        if stim_failed:
            self.engine._block_stim_failures += 1
            log.warning("Buzz Hunt stimulus not delivered for trial "
                         "%s. Check the Arduino connection.",
                         self.trial_counter)
        correct = (not stim_failed) and pressed == self.sequence
        n_right = sum(1 for a, b in zip(pressed, self.sequence) if a == b)
        if correct:
            points = (self.score_cfg.great_points
                      + self.SPAN_ITEM_POINTS * len(self.sequence))
            outcome = TrialResult(label="Great", points=points, rt_ms=None)
            self._span_max_correct = max(self._span_max_correct,
                                         len(self.sequence))
        else:
            outcome = TrialResult(label="Miss",
                                  points=self.score_cfg.miss_points,
                                  rt_ms=None)
        if trial is not None:
            trial.keys_pressed.extend(pressed)
            stimulus = (
                f"span;len={len(self.sequence)};"
                f"hebb={1 if self.is_hebb else 0};"
                f"played={pack_lanes(self.sequence)};"
                f"pressed={pack_lanes(pressed)};"
                f"stim_failed={stim_failed}")
            info = ContinuousTrialLog(waveform="buzz_seq",
                                      params=self.params,
                                      seed=self.trial_seed,
                                      segments=self._segments(now))
            self.engine.log_trial(trial, outcome, now, stimulus=stimulus,
                                  correct_lanes=list(self.sequence),
                                  continuous=info,
                                  error_type=("stim_failed"
                                              if stim_failed
                                              and outcome.label == "Miss"
                                              else None))
        if not stim_failed:
            # A sequence that never played is not a memory sample: it
            # must not enter the span curve or the Hebb slope.
            self._span_records.append({
                "len": len(self.sequence), "hebb": self.is_hebb,
                "correct": correct, "n_right": n_right,
            })
        self._last_result = {
            "stage": "span", "label": outcome.label, "correct": correct,
            "len": len(self.sequence), "hebb": self.is_hebb,
            "pressed": pressed, "played": list(self.sequence),
            "stim_failed": stim_failed,
        }
        # Span ladder: up one on success, down one on a miss, floor 2.
        # A failed delivery leaves the ladder where it was, the same
        # no-move rule as a failed localisation staircase.
        if not stim_failed:
            self.span_len = (self.span_len + 1 if correct
                             else max(2, self.span_len - 1))
        self._finish_trial(now)

    # ---- closing: gap ------------------------------------------------------
    def _close_gap(self, now: float) -> None:
        trial = self.active
        self.active = None
        self._close_stim_marker(now)
        self.engine.log_segment_end("respond", self.trial_counter,
                                    self.lane, now)
        taps = len(self._resp_presses)
        answered_two = taps >= 2
        responded = taps > 0
        stim_failed = self._stim_delivered is False
        if stim_failed:
            self.engine._block_stim_failures += 1
            log.warning("Buzz Hunt stimulus not delivered for trial "
                         "%s. Check the Arduino connection.",
                         self.trial_counter)
        correct = ((not stim_failed) and responded
                  and answered_two == self.gap_two)
        stair = self._gap_stair[self.hand]
        # A no-response says nothing about the percept, so the
        # staircase holds still rather than reading silence as
        # "cannot feel the gap"; a failed delivery holds it for the
        # same reason (nothing was there to detect, felt or not).
        reversal = (stair.record(correct)
                    if responded and not stim_failed else False)
        if reversal:
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "buzz_hunt_reversal", lane=self.lane,
                    detail=(f"stair=gap;hand={self.hand};"
                            f"level_ms={stair.reversals[-1]:.0f};"
                            f"n={len(stair.reversals)}"),
                    hand=self.engine.hand_mode)
        if correct:
            outcome = TrialResult(label="Great",
                                  points=self.score_cfg.great_points,
                                  rt_ms=None)
        else:
            outcome = TrialResult(label="Miss",
                                  points=self.score_cfg.miss_points,
                                  rt_ms=None)
        if trial is not None:
            trial.keys_pressed.extend(l for l, _t in self._resp_presses)
            stimulus = (
                f"gap;hand={self.hand};"
                f"finger={FINGER_WORDS[self.lane % 4].lower()};"
                f"two={1 if self.gap_two else 0};"
                f"gap_ms={float(self.params['gap_ms']):.0f};"
                f"taps={taps};stair_ms={stair.level:.0f};"
                f"reversal={reversal};stim_failed={stim_failed}")
            info = ContinuousTrialLog(waveform="buzz_gap",
                                      params=self.params,
                                      seed=self.trial_seed,
                                      segments=self._segments(now))
            self.engine.log_trial(trial, outcome, now, stimulus=stimulus,
                                  correct_lanes=[self.lane],
                                  continuous=info,
                                  error_type=("stim_failed"
                                              if stim_failed
                                              and outcome.label == "Miss"
                                              else None))
        if not stim_failed:
            # A stimulus that never played is not a gap-detection
            # sample: it must not enter the gap accuracy or the
            # psychometric fit.
            self._gap_records.append({
                "hand": self.hand, "lane": self.lane,
                "gap_ms": float(self.params["gap_ms"]),
                "two": self.gap_two, "taps": taps,
                "responded": responded, "correct": correct,
            })
        self._last_result = {
            "stage": "gap", "label": outcome.label, "correct": correct,
            "responded": responded, "two": self.gap_two, "taps": taps,
            "hand": self.hand, "lane": self.lane,
            "gap_ms": float(self.params["gap_ms"]),
            "stim_failed": stim_failed,
        }
        self._finish_trial(now)

    # ---- shared close ------------------------------------------------------
    def _finish_trial(self, now: float) -> None:
        self.trials_done += 1
        self.phase = "feedback"
        self._phase_until = now + self.rest_s
        self._presses.clear()
        self.arm_wait("feedback", self._phase_until, self._next_or_end,
                      started_at=now)

    def _next_or_end(self, now: float) -> None:
        self.clear_wait()
        if self.trials_done >= self.total_trials:
            self._end("completed")
            return
        # Same cap as _tick's between-trial check; here it also covers
        # the skip button's direct route out of the result card, which
        # never passes through the phase check above.
        if self._t0 is not None and (now - self._t0) > self.session_cap_s:
            self._end("time_cap")
            return
        prev_stage = self.stage
        self._prepare_trial()
        if self.stage != prev_stage:
            self._enter_stage(now)
        else:
            self._enter_announce(now)

    def _end(self, reason: str) -> None:
        self.phase = "done"
        self.end_reason = reason
        # The next block this app session starts its duration
        # staircases where these ended (near threshold), same carry
        # pattern as the other modes' levels; a restart resets to the
        # config start, which fails in the safe (easy) direction.
        self.engine._buzz_hunt_start_ms = {
            hand: stair.level for hand, stair in self._dur_stair.items()}
        self.engine.finish_block()

    # ---- block summary -----------------------------------------------------
    def block_stats(self) -> dict:
        """What finish_block folds into metadata.json and the results
        screen reads: localisation accuracy and the confusion matrix,
        per-hand duration thresholds with their reversals, catch-trial
        false alarms, distractor accuracy, span and Hebb splits, and
        the gap thresholds."""
        def _acc(records):
            if not records:
                return None
            return round(sum(1 for r in records if r["correct"])
                         / len(records), 3)

        def _median(vals):
            vals = sorted(v for v in vals if v is not None)
            if not vals:
                return None
            mid = len(vals) // 2
            m = (vals[mid] if len(vals) % 2
                 else (vals[mid - 1] + vals[mid]) / 2.0)
            return round(m, 1)

        per_lane: dict[str, dict] = {}
        for lane in sorted({r["lane"] for r in self._loc_records}):
            rs = [r for r in self._loc_records if r["lane"] == lane]
            per_lane[str(lane)] = {
                "n": len(rs),
                "correct": sum(1 for r in rs if r["correct"]),
                "accuracy": _acc(rs),
                "median_rt_ms": _median([r["rt_ms"] for r in rs
                                         if r["correct"]]),
            }
        thresholds: dict[str, dict] = {}
        for hand, stair in self._dur_stair.items():
            thresholds[hand] = {
                "start_ms": round(self._dur_start.get(hand,
                                                      self.start_ms), 1),
                "final_ms": round(stair.level, 1),
                "estimate_ms": (round(est, 1) if (est := stair.estimate(
                    self.threshold_reversals)) is not None else None),
                "n_reversals": len(stair.reversals),
                "reversals_ms": [round(r, 1) for r in stair.reversals],
            }
        gap_thresholds: dict[str, dict] = {}
        for hand, stair in self._gap_stair.items():
            gap_thresholds[hand] = {
                "final_ms": round(stair.level, 1),
                "estimate_ms": (round(est, 1) if (est := stair.estimate(
                    self.threshold_reversals)) is not None else None),
                "n_reversals": len(stair.reversals),
                "reversals_ms": [round(r, 1) for r in stair.reversals],
            }
        hebb = [r for r in self._span_records if r["hebb"]]
        novel = [r for r in self._span_records if not r["hebb"]]
        return {
            "hands": self.hand_names,
            "stages": dict(self._stage_counts),
            "loc": {
                "trials": len(self._loc_records),
                "accuracy": _acc(self._loc_records),
                "median_rt_ms": _median([r["rt_ms"]
                                         for r in self._loc_records
                                         if r["correct"]]),
                "per_lane": per_lane,
                "catch": {
                    "n": self._catch_n,
                    "false_alarms": self._catch_fa,
                    "fa_rate": (round(self._catch_fa / self._catch_n, 3)
                                if self._catch_n else None),
                },
                "early_presses": self._early_presses.get("loc", 0),
            },
            "confusion": {k: dict(v) for k, v in self._confusion.items()},
            "threshold": thresholds,
            "distractor": {
                "trials": len(self._dis_records),
                "accuracy": _acc(self._dis_records),
                "lured": sum(1 for r in self._dis_records if r["lured"]),
                "early_presses": self._early_presses.get("distractor", 0),
                "confusion": {k: dict(v) for k, v
                             in self._distractor_confusion.items()},
            },
            "span": {
                "trials": len(self._span_records),
                "start": self.span_start,
                "final": self.span_len,
                "max_correct": self._span_max_correct,
                "hebb": {"n": len(hebb), "accuracy": _acc(hebb)},
                "novel": {"n": len(novel), "accuracy": _acc(novel)},
                "early_presses": self._early_presses.get("span", 0),
            },
            "gap": {
                "trials": len(self._gap_records),
                "accuracy": _acc([r for r in self._gap_records
                                  if r["responded"]]),
                "no_response": sum(1 for r in self._gap_records
                                   if not r["responded"]),
                "threshold": gap_thresholds,
                "early_presses": self._early_presses.get("gap", 0),
            },
            "demo": self.demo,
            "end_reason": self.end_reason,
            **self.wait_skip_stats(),
        }
