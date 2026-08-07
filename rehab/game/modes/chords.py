"""Chords mode: two to four fingers pressed together, with the fingers
that were NOT asked scored on how quiet they stayed.

WHY TRAIN CHORDS. When one finger presses, force leaks onto the others.
Zatsiorsky, Li and Latash (2000, Exp Brain Res 131) named this
enslaving, showed it is largest between neighbouring fingers, and
formalised the interfinger connection matrix this mode's probe trials
reconstruct. Healthy hands leak roughly 5-15 percent of the instructed
force at light effort (Cuadra and Latash 2021, J Neurophysiol, read via
PMC7814910: 8-10 percent at about 25 percent MVC). Stroke raises the
leak and lowers individuation (Lang and Schieber 2003/2004,
J Neurophysiol), and Xu et al. (2017, J Neurophysiol 118, n=54) showed
individuation recovers partly separately from strength, so control
needs its own training target. Individuation is trainable with
feedback: Chiang, Slobounov and Ray (2004, Clin Neurophysiol) reduced
enslaving in 12 sessions of accuracy training, and Thielbar et al.
(2014, J NeuroEng Rehabil 11:171) got modest gains post-stroke from
game training that included multi-finger combinations. Direct evidence
that CHORD practice specifically reduces enslaving is thin; the mode is
an instrumented test of that idea, not an established therapy.

DIFFICULTY ORDER. Chord hardness is computed, not guessed, from two
replicated facts: enslaving is strongest between adjacent fingers
(Zatsiorsky 2000) and fingers differ in how enslavable they are, ring
worst, then middle and pinky, index best of the four (Hager-Ross and
Schieber 2000, J Neurosci 20; Chiang 2004 call the ring the most
enslaved). With enslavability weights index 1, middle 2, ring 3,
pinky 2, a chord's difficulty D is the sum over QUIET fingers of
weight times the number of ACTIVE neighbours, plus 1.5 per finger
above two because per-finger force and timing degrade as chord size
grows (Li, Latash and Zatsiorsky 1998, Exp Brain Res 119). The ladder
that falls out (I=index, M=middle, R=ring, P=pinky):

    Tier 1  RP (D=2),  IM (3)
    Tier 2  MRP (2.5), MR (3), IMRP (3, no quiet fingers, pure timing)
    Tier 3  IMR (3.5), IP (5), IRP (5.5)
    Tier 4  IR (6),  MP (7),  IMP (7.5)

The hardest chords are exactly the ones that enclose a quiet finger
between two active neighbours (M quiet in IR; R quiet in MP and IMP),
which is what the adjacency literature predicts. Within a tier the
chords are dealt by a shuffle bag (BalancedScheduler) so counts stay
equal and the order unpredictable.

THE TRIAL. The hand must be quiet (no finger past its press threshold)
for baseline_quiet_ms before a chord fires; enslaving is measured from
rest or it is not enslaving. The stimulus lights ALL target fingers at
once through the shared cue path, and with the buzzer channel on the
haptic cue is an ARPEGGIO: one firmware pulse per target finger in
fixed index-to-pinky order, onsets spaced a full pulse plus a gap
apart, because the four motors on a board share one driver and can
only run one at a time. The fixed order says WHICH fingers; the screen
says WHEN, and because the order never varies it cannot be mistaken
for a required press order (press order is logged so any order bias is
checkable). The first target press opens the synchrony window W: the
chord counts as together only if every target's onset lands within W
of the first. Then all targets must stay down for hold_ms, kept short
(200 ms) because enslaving drifts upward about 50 percent over a 15 s
hold (Cuadra and Latash 2021), so long holds train the wrong signal.

SYNCHRONY WINDOW. Skilled pianists land chord tones within about 30 ms
(Goebl 2001, JASA 110); perceptual simultaneity is 20-50 ms (Rasch
1979/1988). No stroke value exists in the literature, so W is a
defended design choice: it starts at 250 ms (about 8x expert) and
tightens through 200 and 150 to a floor of 100 ms (about 3x expert),
which demands genuine co-articulation rather than fast sequencing. At
the device's 200 Hz sample rate onsets resolve to 5 ms, twenty times
finer than the floor, so every window here is honestly checkable.

CROSS-TALK SCORE. Per-trial leak comes from the per-finger peaks the
engine's force window already records (baseline-subtracted, all eight
sensors). Each finger's peak is normalised by its own calibrated
light-press gap, and the trial enslaving ratio ER is the mean
normalised quiet-finger leak divided by the mean normalised target
press, the same shape as the individuation slope of Xu 2017. Scoring
pays the two things separately: completion 6 points (scaled by targets
hit), togetherness 2 points (linear in span against W, only on a full
chord), quiet hand 2 points (full at ER 0, zero at ER 0.5; healthy
sits under about 0.15, so the scale has room to show impairment and
improvement). A quiet finger that crosses its own press threshold is a
wrong press and the trial downgrades to Miss, the suite convention. A
measured leak at or past 25 percent of the mean target press (2-3x the
healthy ratio, so clearly worse than healthy rather than noise) marks
the trial leak_fail in the block summary and zeroes the quiet points.

LIGHT PRESSES ONLY. Enslaving scales with instructed force and fatigue
inflates both enslaving and the force deficit (Danion, Latash, Li and
Zatsiorsky 2000/2001: four-finger MVC dropped about 43 percent after
fatiguing exercise), so nothing in this mode ever asks for a hard
press. The press threshold is the calibrated light-press trigger, a
peak past 2.5x the calibrated light press is flagged over_force with a
"press lighter" prompt (never a reward), and holds are capped at
200 ms. Peaks inside 0.5-1.5x the calibrated press earn a no-points
star flag in the block summary.

PROGRESSION. Challenge-point staircase in the style of the FINGER
robot's success-rate control (Taheri et al. 2014, JNER 11:10; Rowe et
al. 2017 RCT support adaptive challenge): of the last 10 chord trials
at the current level, 8 or more clean hits move up a level, 5 or fewer
move down. Levels run the four tiers at W=250, then again at 200, 150,
100: sixteen levels, floor and ceiling clamped. Levels reset to the
easiest each block, the safe direction to fail.

SESSION SHAPE AND DOSE. One engine block is one session: 8 probe
trials (2 per finger, single-finger, through the same trial loop),
5 sub-blocks of 20 chords with an enforced 30 s rest between them
(self-paced past the floor), then 8 closing probes. That is 100 chords
or roughly 250-300 individual finger presses, matching the
300-repetitions-per-session feasibility benchmark for stroke
(Birkenmeier, Prager and Lang 2010, Neurorehabil Neural Repair), with
a 30 minute hard cap. The probes are what let the analysis build a
true enslaving matrix (leak on each finger while one is instructed) at
the start AND end of the session, separating trained-task gains from
transfer, the standard criticism of game training (Zondervan et al.
2016: MusicGlove task gains without superior functional transfer).

FATIGUE GUARD. Fatigue corrupts exactly what this mode trains (Danion
2000/2001), so after each sub-block: a clean-hit rate 30 or more
percentage points below the session's first sub-block, or a median RT
30 percent above it, forces a 2 minute rest and drops one level; a
second trigger ends the session gracefully with the data kept.

WHAT THIS MODE CANNOT CLAIM. No functional-outcome claim (Zondervan
2016 found high-dose game training not superior to conventional
exercise on its primary outcome). No claim that chord practice
specifically reduces enslaving (Chiang 2004 is feedback practice in
healthy adults, Thielbar 2014 a pilot; musician evidence is
cross-sectional only). ER and the probe matrices are device- and
posture-specific: literature values are order-of-magnitude context,
never validation. Calibration in a stroke hand is contaminated by
synergies and spasticity, so normalised leak inherits that noise; raw
counts stay in the CSV (force_window_peaks) alongside. The synchrony
windows and the difficulty weights are defended design choices, not
literature constants. Verify the Cuadra and Latash 2021 citation
details before the thesis reference list.

DEVIATIONS FROM THE RESEARCH BRIEF, where the plumbing wins:
- Cue and go are one moment, like every mode in this suite: the shared
  stim path lights the fingers, plays the tone and starts the arpeggio
  together, and RT runs from that instant. The brief's separate cue
  phase, jittered go and false_start class do not exist here; the
  arpeggio therefore overlaps the first part of the response window.
  Its order is fixed and press order is logged, so cue-order bias in
  responses stays detectable.
- The arpeggio pulse is the firmware's fixed 150 ms hold with a 40 ms
  gap (motor.arpeggio_gap_ms), not the brief's 80/40: the sketch
  exposes no shorter pulse. A four-finger cue spans about 720 ms.
- Forces are normalised by each finger's calibrated light-press gap
  (CalibrationProfile.gap), not percent MVC: no per-finger maximum
  exists in this app, and demanding maximal presses to measure one
  would fight the fatigue rules above. ER stays a dimensionless ratio.
- The leak window is the engine's existing force window, a fixed 1 s
  from stimulus onset, not first-onset to hold-end plus 100 ms. Trials
  answered slower than that window lose their cross-talk measure for
  that trial (ER logs as missing, quiet points are not withheld).
- The per-trial baseline is the detector's primed baseline EMA rather
  than a fresh 500 ms mean; the 500 ms quiet requirement is enforced
  on the detectors' live press state instead.
- Press onset is the calibrated per-finger press trigger (about 40
  percent of the demonstrated light press), not 10 percent MVC, and
  the hold check reads live sensor state, so in the keyboard fallback
  the hold is skipped and leak is only visible as wrong presses.
- Trial points are on the suite's 0-10 scale (6 completion, 2
  together, 2 quiet), mirroring the brief's 60/20/20 split so scores
  stay comparable across modes on the results screen.
- Span, ER, outcome class and the probe matrices live in the block
  summary (metadata.json) and are recoverable from raw.csv; the trial
  CSV's fixed schema carries the chord in `stimulus` ("1+3+4"), the
  target set in `correct_keys` and the peaks in force_window_peaks.
- Two-board bimanual chords are out of scope, as the brief itself
  flags (no literature basis found); with both hands connected the
  mode plays the affected side, like Patterns.
"""
from __future__ import annotations

import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from ...hardware.fsr_detector import PressEvent
from ..scheduling import BalancedScheduler
from ..scoring import ScoreConfig, TrialResult, classify
from ._keys import keymap_for_hand, resolve_key
from .classic import PendingTrial

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


FINGER_LETTERS = ("I", "M", "R", "P")
# Enslavability weights from the independence ranking of Hager-Ross and
# Schieber (2000): ring least independent, then middle and pinky, index
# best of the four sensor fingers.
ENSLAVABILITY = (1.0, 2.0, 3.0, 2.0)
# Physical neighbours on the hand (I-M, M-R, R-P).
ADJACENT = {0: (1,), 1: (0, 2), 2: (1, 3), 3: (2,)}
# Cost per finger above two, for the force deficit and timing spread
# that grow with chord size (Li 1998).
SIZE_PENALTY = 1.5


def chord_difficulty(fingers: tuple[int, ...]) -> float:
    """Predicted hardness D of a chord: for each QUIET finger, its
    enslavability weight times how many ACTIVE neighbours pull on it,
    plus the size penalty. High D means the chord demands keeping a
    strongly-enslaved finger still right next to moving ones."""
    active = set(int(f) for f in fingers)
    d = 0.0
    for f in range(4):
        if f in active:
            continue
        n_adj = sum(1 for a in ADJACENT[f] if a in active)
        d += ENSLAVABILITY[f] * n_adj
    d += SIZE_PENALTY * max(0, len(active) - 2)
    return d


def chord_label(fingers: tuple[int, ...]) -> str:
    return "".join(FINGER_LETTERS[f] for f in sorted(fingers))


# The ladder, tiers ordered by D. Kept explicit rather than derived at
# import time so a marker can read the progression straight off the
# file; the tests recompute every D and pin the ordering to the
# formula above.
CHORD_TIERS: list[list[tuple[int, ...]]] = [
    [(2, 3), (0, 1)],                       # RP, IM
    [(1, 2, 3), (1, 2), (0, 1, 2, 3)],      # MRP, MR, IMRP
    [(0, 1, 2), (0, 3), (0, 2, 3)],         # IMR, IP, IRP
    [(0, 2), (1, 3), (0, 1, 3)],            # IR, MP, IMP
]


@dataclass
class PendingChordTrial:
    """One chord trial: several target lanes, one press per target.
    `targets` are engine-global lane numbers in ascending order.
    `onsets` records the FIRST press time per target lane; duplicates
    are ignored so a double-tap cannot look like a wrong press."""
    trial_id: int
    kind: str                       # "probe" | "chord"
    fingers: tuple[int, ...]        # within-hand finger indices 0..3
    targets: tuple[int, ...]        # engine-global lanes, ascending
    stim_t_perf: float
    tier: int | None                # 0-based tier, None for probes
    w_ms: float
    onsets: dict[int, float] = field(default_factory=dict)
    keys_pressed: list[int] = field(default_factory=list)
    incorrect_presses: list[tuple[int, float]] = field(default_factory=list)
    settle_ms: float | None = None


class ChordsMode:
    name = "Chords"

    # Scoring split, mirroring the brief's 60/20/20 on the suite's
    # 0-10 trial scale so chord blocks stay comparable to the other
    # modes on the results screen.
    COMPLETION_POINTS = 6
    TOGETHER_POINTS = 2
    QUIET_POINTS = 2
    # Quiet points fall linearly to zero at this ER. Healthy light-force
    # enslaving sits under about 0.15 (Cuadra and Latash 2021), so the
    # scale has room to show stroke-level impairment improving.
    ER_ZERO = 0.5
    # A single quiet finger leaking at or past this fraction of the mean
    # target press marks the trial leak_fail: 2-3x the healthy ratio, so
    # a fail means clearly worse than healthy, not measurement noise.
    LEAK_FAIL_RATIO = 0.25
    # Peaks past this multiple of the calibrated light press flag
    # over_force. The calibrated press is a light one by design, so 2.5x
    # is a firm press, nowhere near maximal, flagged not punished.
    OVER_FORCE_RATIO = 2.5
    # No-points star when every target peak lands near the calibrated
    # light press: the patient produced the chord without over-pressing.
    LIGHT_BAND = (0.5, 1.5)
    # Staircase: of the last 10 chord trials at this level, 8+ clean
    # hits promote, 5 or fewer demote (Taheri 2014 style success-rate
    # control around a roughly 70 percent challenge point).
    STAIRCASE_WINDOW = 10
    PROMOTE_HITS = 8
    DEMOTE_HITS = 5
    # Fatigue guard thresholds against the session's first sub-block
    # (Danion 2000/2001: fatigue inflates the very thing being trained).
    FATIGUE_HIT_DROP = 0.30
    FATIGUE_RT_RISE = 0.30
    # Last-resort per-finger reference (counts) when neither a
    # calibration profile nor a readable config exists: the shipped
    # fsr.on_delta defaults divided by the 0.40 trigger fraction, i.e.
    # the light press those triggers were measured from.
    FALLBACK_REF = (50.0, 32.5, 37.5, 115.0)
    # Throttles for the settle / rest prompts so the screen explains a
    # hold-up without flickering a fresh message every frame.
    PROMPT_EVERY_S = 1.5
    # Lead-in after leaving a rest before the quiet gate can fire.
    REST_LEAD_S = 1.0

    def __init__(self, engine: "GameEngine",
                 hand: str, lanes: list[int],
                 timeout_s: float, sync_windows_ms: list[float],
                 hold_ms: float, baseline_quiet_ms: float,
                 settle_prompt_s: float,
                 iti_min_s: float, iti_max_s: float,
                 trials_per_subblock: int, subblocks: int,
                 probe_trials_per_finger: int,
                 rest_between_s: float, fatigue_rest_s: float,
                 session_cap_min: float, score_cfg: ScoreConfig,
                 seed: int = 0,
                 demo_trials: int | None = None) -> None:
        self.engine = engine
        self.hand = hand
        # The playing hand's four lanes, indexed by finger 0..3, same
        # contract as Patterns. Chords are generated over fingers and
        # mapped through this so either hand can play.
        self.lanes = list(lanes)[:4]
        while len(self.lanes) < 4:
            self.lanes.append(len(self.lanes))
        self._lane_offset = self.lanes[0]
        self.score_cfg = score_cfg
        self.timeout = float(timeout_s)
        # Window ladder, widest first. Guard an empty config list so a
        # stripped user_settings cannot leave the mode with no windows.
        self.windows_ms = [float(w) for w in sync_windows_ms
                           if float(w) > 0] or [250.0, 200.0, 150.0, 100.0]
        self.hold_s = max(0.0, float(hold_ms)) / 1000.0
        self.baseline_quiet_s = max(0.0, float(baseline_quiet_ms)) / 1000.0
        self.settle_prompt_s = float(settle_prompt_s)
        self.iti_min = float(iti_min_s)
        self.iti_max = max(float(iti_min_s), float(iti_max_s))
        self.rest_between = float(rest_between_s)
        self.fatigue_rest = float(fatigue_rest_s)
        self.session_cap_s = float(session_cap_min) * 60.0
        self.demo_trials = demo_trials
        self.rng = random.Random(seed)

        # Session layout counters. Demo (Test Mode) shrinks to a
        # miniature that still writes both trial kinds to the CSV:
        # two probes then a handful of tier-1 chords, rests trimmed.
        if demo_trials is not None:
            n = max(2, int(demo_trials))
            self._probe_left_start = min(2, n)
            self._probe_left_end = 0
            self.trials_per_subblock = max(1, n - self._probe_left_start)
            self.subblocks = 1
            self.rest_between = min(self.rest_between, 2.0)
            self.fatigue_rest = min(self.fatigue_rest, 2.0)
        else:
            per = max(0, int(probe_trials_per_finger))
            self._probe_left_start = 4 * per
            self._probe_left_end = 4 * per
            self.trials_per_subblock = max(1, int(trials_per_subblock))
            self.subblocks = max(1, int(subblocks))
        self._sub_idx = 0
        self._sub_done = 0
        self._probes_planned = self._probe_left_start + self._probe_left_end
        self._probe_sched = BalancedScheduler([0, 1, 2, 3], self.rng)

        # Difficulty state. Level = tier + window combined, easiest
        # first; resets each block, the safe direction to fail.
        self.level = 0
        self.max_level = 4 * len(self.windows_ms) - 1
        self.highest_level = 0
        self._chord_sched: BalancedScheduler | None = None
        self._sched_tier: int | None = None
        self._stair: deque[bool] = deque(maxlen=self.STAIRCASE_WINDOW)

        # Trial state machine: settle -> stim [-> hold] -> settle ...
        # with rest between sub-blocks and done at the end.
        self.phase = "settle"
        self.active: PendingChordTrial | None = None
        self.trial_counter = 0
        self.completed = 0
        self._next_ok_t: float | None = None
        self._quiet_since: float | None = None
        self._settle_t0: float | None = None
        self._prompt_t = 0.0
        self._hold_until: float | None = None
        self._rest_until: float | None = None
        self._rest_kind = "between"          # between | fatigue
        self._t0: float | None = None        # session clock for the cap
        self._presses: deque[PressEvent] = deque()

        # Live FSR data is what makes the hold and the quiet gate real;
        # the keyboard fallback only sees discrete key events, so those
        # checks relax there (documented in the deviations above).
        try:
            self._fsr = bool(getattr(engine.source, "provides_samples",
                                     False))
        except Exception:
            self._fsr = False

        # Fatigue bookkeeping: per-sub-block clean-hit rate and median
        # RT, judged against the session's first sub-block.
        self._sub_stats: list[dict] = []
        self._sub_hits = 0
        self._sub_rts: list[float] = []
        self._fatigue_triggers = 0
        self.end_reason: str | None = None

        # Per-trial records for block_stats: span, ER and outcome class
        # cannot ride the fixed CSV schema, so the block summary is
        # their home (raw.csv keeps the underlying events regardless).
        self._records: list[dict] = []

    # ---- properties the engine reads ---------------------------------------
    @property
    def total_trials(self) -> int:
        # HUD progress bar. The plan for the whole session; an early
        # end (cap, fatigue) simply leaves the bar unfilled.
        return (self._probes_planned
                + self.trials_per_subblock * self.subblocks)

    @property
    def current_timeout_s(self) -> float:
        # Engine reads this to arm the timing bar and log timeout_ms.
        return self.timeout

    @property
    def current_w_ms(self) -> float:
        return self.windows_ms[min(self.level // 4,
                                   len(self.windows_ms) - 1)]

    @property
    def current_tier(self) -> int:
        return self.level % 4

    # ---- plumbing shared with the other cadence modes ----------------------
    def queue_press(self, ev: PressEvent) -> None:
        self._presses.append(ev)

    def on_resume(self, pause_dur: float) -> None:
        # Slide every in-flight deadline forward so a pause cannot time
        # a trial out, break a hold, eat a rest or burn cap time.
        if self.active is not None:
            self.active.stim_t_perf += pause_dur
            for lane in list(self.active.onsets):
                self.active.onsets[lane] += pause_dur
        for attr in ("_next_ok_t", "_quiet_since", "_settle_t0",
                     "_hold_until", "_rest_until", "_t0"):
            v = getattr(self, attr)
            if v is not None:
                setattr(self, attr, v + pause_dur)

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN:
            # Keyboard fallback stays wired even with an Arduino
            # connected, same reasoning as classic.py: a busted
            # auto-detect must never leave the therapist with no
            # working input. j k l ; are lanes 0..3 on the right hand.
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

    # ---- live sensor state -------------------------------------------------
    def _hand_detector(self):
        dets = getattr(self.engine, "detectors", None)
        if not isinstance(dets, dict):
            return None
        return dets.get(self.hand)

    def _hand_quiet(self) -> bool:
        """No finger of the playing hand past its press threshold. The
        keyboard fallback has no live state, so it is always quiet and
        the gate reduces to the inter-trial wait."""
        det = self._hand_detector()
        pressed = getattr(det, "pressed", None)
        try:
            return pressed is None or not any(pressed)
        except TypeError:
            return True

    def _lane_pressed(self, lane: int) -> bool:
        det = self._hand_detector()
        pressed = getattr(det, "pressed", None)
        try:
            return bool(pressed[lane - self._lane_offset])
        except (TypeError, IndexError, KeyError):
            return False

    # ---- per-finger normalisation ------------------------------------------
    def _reference_counts(self, lane: int) -> float:
        """This finger's calibrated light-press gap in counts, the
        normaliser for every force in this mode. Falls back to the
        shipped thresholds (trigger / 0.40) when no in-app calibration
        has been run, and to the same numbers hard-coded when even the
        config cannot be read (test doubles)."""
        finger = max(0, min(3, lane - self._lane_offset))
        profs = getattr(self.engine, "calibration_profiles", None)
        if isinstance(profs, dict):
            prof = profs.get(self.hand)
            try:
                g = float(prof.gap()[finger])
                if g > 0:
                    return g
            except (AttributeError, TypeError, IndexError, ValueError):
                pass
        try:
            on_delta = list(self.engine.cfg.get("fsr.on_delta") or [])
            v = float(on_delta[finger]) / 0.40
            if v > 0:
                return v
        except (AttributeError, TypeError, IndexError, ValueError):
            pass
        return self.FALLBACK_REF[finger]

    def _window_peaks(self) -> dict[int, float] | None:
        """The engine's per-finger force peaks for the trial in flight,
        or None when no FSR samples reached the window (keyboard mode,
        or a response slower than the window). Read BEFORE log_trial,
        which closes and clears the window."""
        peaks = getattr(self.engine, "_force_window_peak", None)
        if not isinstance(peaks, dict):
            return None
        if getattr(self.engine, "_force_window_saw_samples", False) \
                is not True:
            return None
        return dict(peaks)

    # ---- main tick ---------------------------------------------------------
    def update(self, dt: float) -> None:
        now = time.perf_counter()
        if self._t0 is None:
            self._t0 = now
        while self._presses:
            self._handle_press(self._presses.popleft(), now)
        if self.phase == "done":
            return
        if self.phase == "rest":
            self._update_rest(now)
            return
        if self.phase == "hold":
            self._update_hold(now)
            return
        if self.phase == "stim":
            if (self.active is not None
                    and (now - self.active.stim_t_perf) > self.timeout):
                self._finish(now, hold_achieved=None)
            return
        self._update_settle(now)

    # ---- settle gate -------------------------------------------------------
    def _update_settle(self, now: float) -> None:
        if self._next_ok_t is not None and now < self._next_ok_t:
            return
        if self._settle_t0 is None:
            self._settle_t0 = now
        # The quiet clock restarts whenever any finger is down, so the
        # chord always launches from a genuinely resting hand.
        if self._hand_quiet():
            if self._quiet_since is None:
                self._quiet_since = now
        else:
            self._quiet_since = None
        if (self._quiet_since is None
                or (now - self._quiet_since) < self.baseline_quiet_s):
            if ((now - self._settle_t0) > self.settle_prompt_s
                    and (now - self._prompt_t) > self.PROMPT_EVERY_S):
                self._prompt_t = now
                self._set_message("Relax your hand", 1.2)
            return
        self._fire(now)

    # ---- firing ------------------------------------------------------------
    def _next_targets(self) -> tuple[str, tuple[int, ...]]:
        """What the next trial asks for: a single-finger probe at the
        session's edges, otherwise a chord from the current tier."""
        if self._probe_left_start > 0:
            return "probe", (self._probe_sched.next(),)
        if self._in_training():
            tier = self.current_tier
            if self._chord_sched is None or self._sched_tier != tier:
                # Fresh shuffle bag whenever the tier changes so the
                # chords of the new tier get equal counts from here.
                self._chord_sched = BalancedScheduler(
                    list(range(len(CHORD_TIERS[tier]))), self.rng)
                self._sched_tier = tier
            return "chord", CHORD_TIERS[tier][self._chord_sched.next()]
        return "probe", (self._probe_sched.next(),)

    def _in_training(self) -> bool:
        return self._sub_idx < self.subblocks

    def _fire(self, now: float) -> None:
        kind, fingers = self._next_targets()
        targets = tuple(sorted(self.lanes[f] for f in fingers))
        self.trial_counter += 1
        settle_ms = None
        if self._settle_t0 is not None:
            settle_ms = (now - self._settle_t0) * 1000.0
        self.active = PendingChordTrial(
            trial_id=self.trial_counter,
            kind=kind,
            fingers=tuple(sorted(fingers)),
            targets=targets,
            stim_t_perf=now,
            tier=None if kind == "probe" else self.current_tier,
            w_ms=self.current_w_ms,
            settle_ms=settle_ms,
        )
        self.phase = "stim"
        self._quiet_since = None
        self._settle_t0 = None
        # ALL target fingers light at once; with the buzzer channel on,
        # the engine turns a same-board multi-lane stim into the
        # arpeggio (see engine.on_stim_multi).
        self.engine.on_stim_multi(list(targets), self.trial_counter, now)

    # ---- presses -----------------------------------------------------------
    def _handle_press(self, ev: PressEvent, now: float) -> None:
        if self.phase == "rest":
            # Rests are self-paced past the floor: any finger advances.
            if self._rest_until is not None and now >= self._rest_until:
                self._leave_rest(now)
            return
        if self.active is None:
            # Between-trial spam still costs the idle-press penalty so
            # mashing while the hand should be settling is not free.
            # It also restarts the quiet clock via the live press
            # state, so the chord cannot fire off a moving hand.
            self.engine.apply_idle_press_penalty()
            return
        self.active.keys_pressed.append(ev.lane)
        if ev.lane in self.active.targets:
            # First onset per target only; a double-tap on a finger
            # already down must not read as a wrong press.
            if ev.lane not in self.active.onsets:
                self.active.onsets[ev.lane] = ev.t_perf
            if len(self.active.onsets) == len(self.active.targets):
                if self._fsr and self.hold_s > 0:
                    self.phase = "hold"
                    self._hold_until = now + self.hold_s
                else:
                    self._finish(now, hold_achieved=None)
        else:
            # A quiet finger crossing its own press threshold is the
            # loudest possible leak. Suite convention: every wrong
            # press costs points and the trial downgrades to Miss.
            self.active.incorrect_presses.append((ev.lane, ev.t_perf))
            self.engine.apply_wrong_press_penalty()

    # ---- hold --------------------------------------------------------------
    def _update_hold(self, now: float) -> None:
        if self.active is None:
            self.phase = "settle"
            return
        if not all(self._lane_pressed(l) for l in self.active.targets):
            # A finger slipped off before the hold ended. Short hold on
            # purpose (enslaving drifts up during sustained holds), but
            # it does have to be met for a clean hit.
            self._finish(now, hold_achieved=False)
            return
        if self._hold_until is not None and now >= self._hold_until:
            self._finish(now, hold_achieved=True)

    # ---- trial close -------------------------------------------------------
    def _finish(self, now: float, hold_achieved: bool | None) -> None:
        trial = self.active
        if trial is None:
            return
        self.active = None
        self._hold_until = None
        n_targets = len(trial.targets)
        n_pressed = len(trial.onsets)
        full = n_pressed == n_targets
        w_ms = trial.w_ms

        span_ms = None
        rt_ms = None
        if full:
            first = min(trial.onsets.values())
            last = max(trial.onsets.values())
            span_ms = (last - first) * 1000.0
            rt_ms = (last - trial.stim_t_perf) * 1000.0
        together = full and span_ms is not None and span_ms <= w_ms

        # Cross-talk from the engine's force window, normalised per
        # finger by the calibrated light press. Read before log_trial
        # closes the window.
        peaks = self._window_peaks()
        er = None
        max_leak_ratio = None
        over_force = False
        light_press = False
        leak_norms: dict[int, float] = {}
        mean_press = 0.0
        if peaks is not None:
            hand_lanes = list(self.lanes)
            norms = {l: max(0.0, peaks.get(l, 0.0))
                     / self._reference_counts(l) for l in hand_lanes}
            press_norms = [norms[l] for l in trial.targets]
            leak_norms = {l: norms[l] for l in hand_lanes
                          if l not in trial.targets}
            mean_press = (sum(press_norms) / len(press_norms)
                          if press_norms else 0.0)
            if mean_press > 0:
                if leak_norms:
                    er = sum(leak_norms.values()) / len(leak_norms) \
                        / mean_press
                    max_leak_ratio = max(leak_norms.values()) / mean_press
                light_press = all(
                    self.LIGHT_BAND[0] <= p <= self.LIGHT_BAND[1]
                    for p in press_norms)
            over_force = any(v >= self.OVER_FORCE_RATIO
                             for v in norms.values())

        # Outcome class, mutually exclusive, precedence documented in
        # the docstring. IMRP has no quiet fingers, so er stays None
        # there and the quiet component is vacuously earned.
        wrong = bool(trial.incorrect_presses)
        if not full:
            cls = "partial"
        elif wrong or (max_leak_ratio is not None
                       and max_leak_ratio >= self.LEAK_FAIL_RATIO):
            cls = "leak_fail"
        elif over_force:
            cls = "over_force"
        elif not together:
            cls = "late_chord"
        elif hold_achieved is False:
            cls = "no_hold"
        else:
            cls = "hit"

        # Points: completion, togetherness and quiet paid separately.
        quiet_frac = (1.0 if er is None
                      else max(0.0, 1.0 - min(1.0, er / self.ER_ZERO)))
        if wrong:
            # Suite convention: a fumbled trial is a Miss row and the
            # per-press penalties already docked the score.
            outcome = TrialResult(label="Miss",
                                  points=self.score_cfg.miss_points,
                                  rt_ms=rt_ms)
        elif not full:
            # Timeout with some fingers landed: completion is scaled by
            # what arrived, so a three-of-four chord is not scored like
            # a frozen hand.
            pts = int(round(self.COMPLETION_POINTS
                            * n_pressed / n_targets))
            outcome = TrialResult(label="Miss", points=pts, rt_ms=None)
        else:
            pts = self.COMPLETION_POINTS
            if together and w_ms > 0:
                pts += int(round(self.TOGETHER_POINTS
                                 * (1.0 - span_ms / w_ms)))
            if not (max_leak_ratio is not None
                    and max_leak_ratio >= self.LEAK_FAIL_RATIO):
                pts += int(round(self.QUIET_POINTS * quiet_frac))
            label = (classify(rt_ms, self.score_cfg).label
                     if together else "Late")
            outcome = TrialResult(label=label, points=pts, rt_ms=rt_ms)

        # The CSV row. stimulus carries the chord as lane numbers
        # ("1+3+4"), correct_keys the full target set; the row is keyed
        # on the lowest target lane so per-lane charts stay populated
        # (a chord's RT lands on its lowest finger, a known
        # simplification the block summary does not share).
        log_obj = PendingTrial(
            trial_id=trial.trial_id,
            lane=trial.targets[0],
            stim_t_perf=trial.stim_t_perf,
            keys_pressed=list(trial.keys_pressed),
            incorrect_presses=list(trial.incorrect_presses),
        )
        stim = "+".join(str(l + 1) for l in trial.targets)
        self.engine.log_trial(log_obj, outcome, now,
                              stimulus=stim,
                              correct_lanes=list(trial.targets))
        self._set_message(self._feedback_text(trial, cls, over_force,
                                              light_press), 0.9)

        self._records.append({
            "trial": trial.trial_id,
            "kind": trial.kind,
            "chord": chord_label(trial.fingers),
            "tier": None if trial.tier is None else trial.tier + 1,
            "d": chord_difficulty(trial.fingers),
            "w_ms": w_ms,
            "level": self.level,
            "class": cls,
            "span_ms": None if span_ms is None else round(span_ms, 1),
            "rt_ms": None if rt_ms is None else round(rt_ms, 1),
            "er": None if er is None else round(er, 4),
            # Probe rows keep the raw material for the enslaving
            # matrix: the instructed finger's normalised press and
            # every quiet finger's normalised leak.
            "press_norm": (round(mean_press, 4)
                           if trial.kind == "probe" and mean_press > 0
                           else None),
            "leaks": ({str(l - self._lane_offset): round(v, 4)
                       for l, v in leak_norms.items()}
                      if trial.kind == "probe" and leak_norms else None),
            "hold": hold_achieved,
            "over_force": over_force,
            "light": light_press,
            "settle_ms": (None if trial.settle_ms is None
                          else round(trial.settle_ms, 1)),
            "subblock": (self._sub_idx + 1
                         if trial.kind == "chord" else None),
        })
        self.completed += 1

        if trial.kind == "chord":
            self._sub_hits += 1 if cls == "hit" else 0
            if rt_ms is not None:
                self._sub_rts.append(rt_ms)
            self._staircase(cls == "hit")
        self._advance(now, trial.kind)

    def _feedback_text(self, trial: PendingChordTrial, cls: str,
                       over_force: bool, light: bool) -> str:
        if over_force:
            return "Too hard, press lighter"
        if cls == "hit":
            return ("Chord! *" if light and trial.kind == "chord"
                    else "Chord!")
        if cls == "late_chord":
            return "Nearly together"
        if cls == "no_hold":
            return "Hold it a beat longer"
        if cls == "leak_fail":
            quiet = [f for f in range(4) if f not in trial.fingers]
            names = ("Index", "Middle", "Ring", "Pinky")
            if trial.incorrect_presses:
                f = trial.incorrect_presses[0][0] - self._lane_offset
                if 0 <= f <= 3:
                    return f"{names[f]} leaked"
            return "Quiet fingers leaked" if quiet else "Leaked"
        return "Fingers missing"

    # ---- progression -------------------------------------------------------
    def _staircase(self, hit: bool) -> None:
        self._stair.append(hit)
        if len(self._stair) < self.STAIRCASE_WINDOW:
            return
        hits = sum(1 for h in self._stair if h)
        if hits >= self.PROMOTE_HITS and self.level < self.max_level:
            self.level += 1
            self.highest_level = max(self.highest_level, self.level)
            self._stair.clear()
            self._set_message("Level up", 1.2)
        elif hits <= self.DEMOTE_HITS and self.level > 0:
            self.level -= 1
            self._stair.clear()

    # ---- session flow ------------------------------------------------------
    def _advance(self, now: float, kind: str) -> None:
        # Hard session cap, checked at trial close so it never cuts a
        # trial in half.
        if (self._t0 is not None
                and (now - self._t0) > self.session_cap_s):
            self._set_message("Session complete", 2.0)
            self._end("time_cap")
            return
        if kind == "probe":
            if self._probe_left_start > 0:
                self._probe_left_start -= 1
            else:
                self._probe_left_end -= 1
                if self._probe_left_end <= 0:
                    self._end("completed")
                    return
        else:
            self._sub_done += 1
            if self._sub_done >= self.trials_per_subblock:
                self._close_subblock(now)
                return
        self._arm_next(now)

    def _arm_next(self, now: float) -> None:
        self.phase = "settle"
        self._next_ok_t = now + self.rng.uniform(self.iti_min,
                                                 self.iti_max)
        self._quiet_since = None
        self._settle_t0 = None

    def _close_subblock(self, now: float) -> None:
        n = max(1, self._sub_done)
        rts = sorted(self._sub_rts)
        median_rt = rts[len(rts) // 2] if rts else None
        stats = {"subblock": self._sub_idx + 1,
                 "hit_rate": round(self._sub_hits / n, 3),
                 "median_rt_ms": (None if median_rt is None
                                  else round(median_rt, 1)),
                 "level_at_end": self.level}
        self._sub_stats.append(stats)
        self._sub_idx += 1
        self._sub_done = 0
        self._sub_hits = 0
        self._sub_rts = []
        fatigued = self._fatigue_check(stats)
        if fatigued and self._fatigue_triggers >= 2:
            self._set_message("Great effort. Session done", 2.0)
            self._end("fatigue")
            return
        if not self._in_training():
            # Straight into the closing probes; the enforced rest
            # belongs between training sub-blocks.
            if self._probe_left_end <= 0:
                self._end("completed")
            else:
                self._arm_next(now)
            return
        if fatigued:
            self.level = max(0, self.level - 1)
            self._stair.clear()
            self._enter_rest(now, self.fatigue_rest, "fatigue",
                             "Take a longer breather")
        else:
            self._enter_rest(now, self.rest_between, "between",
                             "Rest your hand")

    def _fatigue_check(self, stats: dict) -> bool:
        """Judge this sub-block against the session's first. Both
        triggers point the same way: the hand is tiring, and a tired
        hand trains the wrong signal."""
        if len(self._sub_stats) < 2:
            return False
        first = self._sub_stats[0]
        dropped = (first["hit_rate"] - stats["hit_rate"]
                   >= self.FATIGUE_HIT_DROP)
        slowed = (first["median_rt_ms"] is not None
                  and stats["median_rt_ms"] is not None
                  and stats["median_rt_ms"] >= first["median_rt_ms"]
                  * (1.0 + self.FATIGUE_RT_RISE))
        if dropped or slowed:
            self._fatigue_triggers += 1
            return True
        return False

    def _enter_rest(self, now: float, floor_s: float, kind: str,
                    msg: str) -> None:
        self.phase = "rest"
        self._rest_kind = kind
        self._rest_until = now + max(0.0, floor_s)
        self._prompt_t = now
        self._set_message(msg, min(3.0, max(1.5, floor_s)))
        self._clear_lanes()

    def _update_rest(self, now: float) -> None:
        if (self._rest_until is not None and now >= self._rest_until
                and (now - self._prompt_t) > self.PROMPT_EVERY_S):
            self._prompt_t = now
            self._set_message("Press any finger when ready", 1.2)

    def _leave_rest(self, now: float) -> None:
        self._rest_until = None
        self.phase = "settle"
        self._next_ok_t = now + self.REST_LEAD_S
        self._quiet_since = None
        self._settle_t0 = None

    def _end(self, reason: str) -> None:
        self.phase = "done"
        self.end_reason = reason
        self.engine.finish_block()

    # ---- screen helpers ----------------------------------------------------
    def _gameplay_screen(self):
        screens = getattr(self.engine, "_screens", None)
        if not isinstance(screens, dict):
            return None
        return screens.get("gameplay")

    def _set_message(self, text: str, duration_s: float) -> None:
        gp = self._gameplay_screen()
        if gp is not None and hasattr(gp, "set_message"):
            gp.set_message(text, duration_s)

    def _clear_lanes(self) -> None:
        gp = self._gameplay_screen()
        if gp is None or not hasattr(gp, "lanes"):
            return
        for ls in gp.lanes:
            ls.clear_timing()
            ls.active = False

    # ---- block summary -----------------------------------------------------
    @staticmethod
    def _probe_matrix(records: list[dict]) -> list[list[float | None]]:
        """4x4 enslaving matrix from probe records: row i, column j is
        finger j's normalised leak as a percentage of finger i's
        normalised press, mean over that finger's probes. Diagonal and
        unmeasured cells are None. Comparable in shape to the matrices
        of Zatsiorsky 2000 and the individuation slope of Xu 2017, but
        device-specific: context, never validation."""
        cells: dict[tuple[int, int], list[float]] = {}
        for r in records:
            if (r["kind"] != "probe" or not r.get("leaks")
                    or not r.get("press_norm")):
                continue
            i = FINGER_LETTERS.index(r["chord"])
            press = float(r["press_norm"])
            for j_str, leak in r["leaks"].items():
                j = int(j_str)
                cells.setdefault((i, j), []).append(leak / press)
        out: list[list[float | None]] = [[None] * 4 for _ in range(4)]
        for (i, j), vals in cells.items():
            if i != j and vals:
                out[i][j] = round(100.0 * sum(vals) / len(vals), 1)
        return out

    def block_stats(self) -> dict:
        """What finish_block folds into metadata.json: the ladder
        position reached, per-chord difficulty validation numbers,
        cross-talk aggregates, the start and end probe matrices, the
        fatigue trajectory and the per-trial detail the fixed CSV
        schema cannot carry."""
        chords = [r for r in self._records if r["kind"] == "chord"]
        probes = [r for r in self._records if r["kind"] == "probe"]
        # Probes before the first chord are the start set; the rest are
        # the end set. Demo blocks have no end set.
        first_chord = chords[0]["trial"] if chords else None
        probes_start = [r for r in probes
                        if first_chord is None or r["trial"] < first_chord]
        probes_end = [r for r in probes
                      if first_chord is not None
                      and r["trial"] > first_chord]

        per_chord: dict[str, dict] = {}
        for r in chords:
            d = per_chord.setdefault(r["chord"], {
                "d": r["d"], "n": 0, "hits": 0,
                "spans": [], "ers": []})
            d["n"] += 1
            d["hits"] += 1 if r["class"] == "hit" else 0
            if r["span_ms"] is not None:
                d["spans"].append(r["span_ms"])
            if r["er"] is not None:
                d["ers"].append(r["er"])

        def _median(vals: list[float]) -> float | None:
            if not vals:
                return None
            s = sorted(vals)
            return round(s[len(s) // 2], 3)

        chord_table = [{
            "chord": name,
            "d": v["d"],
            "n": v["n"],
            "hit_rate": round(v["hits"] / v["n"], 3) if v["n"] else None,
            "median_span_ms": _median(v["spans"]),
            "median_er": _median(v["ers"]),
        } for name, v in sorted(per_chord.items(),
                                key=lambda kv: kv[1]["d"])]

        classes: dict[str, int] = {}
        for r in self._records:
            classes[r["class"]] = classes.get(r["class"], 0) + 1

        return {
            "hand": self.hand,
            "demo": self.demo_trials is not None,
            "windows_ms": self.windows_ms,
            "level_final": self.level,
            "level_highest": self.highest_level,
            "w_final_ms": self.current_w_ms,
            "tier_final": self.current_tier + 1,
            "n_chords": len(chords),
            "n_probes": len(probes),
            "outcome_classes": classes,
            "median_er": _median([r["er"] for r in chords
                                  if r["er"] is not None]),
            "median_span_ms": _median([r["span_ms"] for r in chords
                                       if r["span_ms"] is not None]),
            "median_settle_ms": _median([r["settle_ms"]
                                         for r in self._records
                                         if r["settle_ms"] is not None]),
            "over_force_trials": sum(1 for r in self._records
                                     if r["over_force"]),
            "light_press_trials": sum(1 for r in chords if r["light"]),
            "per_chord": chord_table,
            "subblocks": self._sub_stats,
            "fatigue_triggers": self._fatigue_triggers,
            "end_reason": self.end_reason,
            "enslaving_matrix_start": self._probe_matrix(probes_start),
            "enslaving_matrix_end": self._probe_matrix(probes_end),
            "trials": self._records,
        }
