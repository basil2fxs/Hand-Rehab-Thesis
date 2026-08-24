"""Chords mode: two to four fingers pressed together, with the fingers
that were NOT asked scored on how quiet they stayed.

WHY TRAIN CHORDS. When one finger presses, force leaks onto the others.
Zatsiorsky, Li and Latash (2000, Exp Brain Res 131) named this
enslaving, showed it is largest between neighbouring fingers, and
formalised the interfinger connection matrix this mode's probe trials
reconstruct. Healthy hands leak roughly 5-15 percent of the instructed
force at light effort (Abolins, Stremoukhov, Walter and Latash 2020, J Neurophysiol, read via
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
of the first. A target that lifts again before the chord completes
loses its onset and must land again, so a chord only ever completes
off fingers that are down together; without that rule a stale onset
let the last finger complete a chord an earlier finger had already
left, and the hold below failed on the same frame with nothing the
patient could do about it. Once the chord is down, all targets stay
down for hold_ms, kept short (200 ms) because enslaving drifts upward
about 50 percent over a 15 s hold (Abolins et al. 2020), so long
holds train the wrong signal. The hold is visible while it runs: a
ring fills on the held tiles and completes exactly at hold_ms (a
single centred bar when the screen may not name the target), because
feedback that only arrives after the trial closes cannot be acted on.
A broken hold forfeits the together bonus and the feedback names the
finger that lifted; late and missing fingers are named the same way.

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

OUTCOME CLASS PRECEDENCE. The block-summary class is mutually
exclusive; a trial can only match one, checked in this order:
partial (a target never landed) > leak_fail (a wrong press, or a
measured leak past the threshold above) > over_force > late_chord
(completed outside the window) > no_hold (broken before hold_ms) >
hit.

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

THE WARM-UP IS ANNOUNCED AND CAPPED. The opening probes are eight
single-finger presses (sixteen with both hands), and played cold they
read as the game itself: a patient who quits or demos early has seen
nothing BUT single fingers and concludes chords mode never asks for a
chord. Three rules keep the probes a warm-up rather than the game.
First, the screen says so: a persistent WARM-UP banner with a counter
runs over every opening probe, a WIND-DOWN banner over the closing
set, and the first chord is announced when it arrives. Second, probes
run on their own short fixed gap (warmup_iti_s) instead of the
chord trials' jittered ITI: the jitter exists so a chord cannot be
timed rather than reacted to, but a probe is an instructed press
whose measurement (leak while pressing) does not care whether the
patient saw it coming. Third, a hard budget (warmup_cap_s) bounds the
time to the first chord: if the opening probes are still running when
it expires (a hand that will not settle, repeated timeouts), the
remainder move to the closing set, the block summary records
warmup_capped, and the chords start. The start matrix then has fewer
probes behind it, which the analysis can see and say; a session whose
first minutes are all warm-up is the worse failure, because the
patient stops playing before the training content ever appears.

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
literature constants. The citation was verified against PubMed
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
- The leak window is the engine's force window, stretched to cover the
  mode's own timeout plus hold (about 3.2 s), not the brief's
  first-onset to hold-end plus 100 ms. Every in-time trial keeps its
  ER: the window is open from stimulus onset to trial close, so it
  also catches any activity before the first target lands, which the
  brief's onset-anchored window would exclude.
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

BOTH HANDS. With both boards connected a WITHIN-hand chord is still
drawn inside one hand, because enslaving is a within-hand quantity
(cross-hand enslaving is negligible next to within-hand: Li, Danion,
Latash, Li and Zatsiorsky 2000, J Appl Biomech 16; Li et al. 2001,
Exp Brain Res 141), and the two hands alternate under the suite's
paired balance rules: a shuffle bag over the hands keeps their trial
counts equal (never apart by more than one) while each hand's own
shuffle bag keeps its chords equally dealt, the same two-axis
balancing PairedBalancedScheduler applies elsewhere. Single-finger
probes run per hand (2 per finger per hand at each session edge), so
the analysis gets a clean start and end enslaving matrix for EACH
hand, and every per-trial record carries its hand. The within-hand
staircase level is shared across the hands: both climb the same
ladder, so the weaker hand sets the pace, which errs in the safe
direction. On screen the chord's fingers light inside that hand's own
tile block (left block left of centre, right block right, mirrored
finger order), and a "Left hand" / "Right hand" chip names the side
at each stim; both of those visual identifications are suppressed
when cue.show_target is off, where no visual may name the target.
Quiet-finger leak is always measured against the chord's own hand
only.

CROSS-HAND CHORDS. Bilateral sessions also deal chords that SPAN the
hands, and those measure a different thing: not individuation but
bimanual coordination, the yoking of the two hands into one
functional unit (Kelso, Southard and Goodman 1979, Science 203;
Swinnen 2002, Nat Rev Neurosci 3). The replicated fact the tier
ladder is built on is the symmetry advantage: mirror-symmetric
simultaneous action is the stable default (Kelso 1984; Haken, Kelso
and Bunz 1985) and the bias is spatial-perceptual (Mechsner et al.
2001, Nature 414), so with both palms down on the boards homologous
fingers are the mirrored ones and mirror chords are the easy tier.
Non-mirror chords demand active suppression of that default
coupling, exactly the interhemispheric machinery that is disturbed
after stroke (Murase et al. 2004, Ann Neurol 55), and asymmetric
two-hand tasks are where cross-hand interaction effects actually
appear (Li 2001). Kantak, Jax and Wittenberg (2017, Restor Neurol
Neurosci 35) argue bimanual coordination is its own rehab target
that unilateral practice does not cover; the bilateral training
lineage (Whitall 2000; Luft 2004; Cauraugh 2010 meta, contested)
supports repetitive coupled bilateral work without settling
efficacy, so the mode's stance stays measurement plus mechanism.

The cross-hand difficulty formula reuses the within-hand machinery:
D_cross is the within-hand D of each hand's fingers (each hand still
has quiet fingers to keep still), plus the same 1.5 size penalty per
finger above two on TOTAL chord size, plus 1.5 per unit of mirror
distance (each active finger's distance to the nearest active finger
of the other hand in mirror coordinates, summed): zero for mirror
chords, growing with spatial asymmetry. The 1.5 weights are defended
design choices, like the within-hand weights. The ladder
(left-of-bar = left hand):

    Tier XB1  mirror singles:   I|I (4),  P|P (6),  M|M (8), R|R (8)
    Tier XB2  mirror doubles:   RP|RP (7), IM|IM (9), MR|MR (9)
    Tier XB3  neighbour shifts: I|M, M|I (9), R|P, P|R (10),
                                M|R, R|M (11)
    Tier XB4  far and uneven:   I|R (12), I|MR (12.5), I|P (14),
                                IM|RP (17)

Scheduling is scope-pure: of the five training sub-blocks the third
and fifth deal cross-hand chords, the rest within-hand, in a FIXED
order so fatigue trends stay comparable across sessions and the EEG
layer gets clean block-level contrasts. Cross-hand chords run on
their own staircase (level_cross, same tier-within-window ladder
shape and the same W values) so a cross-hand artefact can never
drive the within-hand level or the reverse. In Test Mode's bilateral
miniature the two scopes simply alternate so a demo shows both.

Cross-hand measurement, logged per trial in the block summary:
per-hand ER (each hand's leak against its OWN targets and quiet
fingers, never pooled with within-hand ER: the other hand moving is
a coupling confound), mirror flag and mirror-distance (asym),
lead hand and lag (first-onset difference between the hands, the
temporal coupling measure), and per-hand press levels so mirror
singles can be compared against the same finger's unimanual probe
press for the bilateral deficit ratio (Li 2000/2001). Within-hand
chords in bilateral play additionally log mirror_leak: the resting
hand's loudest normalised peak against the chord's mean press, the
silent mirror-force measure (Cincotta and Ziemann 2008), free
because the other board is instrumented and quiet. The trial CSV
separates the scopes in the stimulus descriptor itself: a
within-hand chord stays "1+3+4", a cross-hand chord is written
"x:1+5", so no analysis can mistake one for the other. On screen a
cross-hand chord lights its fingers in BOTH tile blocks with the
shared baseline glow joining them across the divider, and the side
chip reads "Both hands"; a same-instant buzz on the two boards is
fine (one motor per board at a time is the only constraint), so a
1+1 cross chord cues both hands simultaneously while a within-hand
multi-finger cue arpeggiates. Cue span therefore differs between
scopes, a known confound when comparing RT across scopes, which is
why cross RT is never pooled with within RT anywhere.

What cross-hand chords do NOT cover: anti-phase rhythmic
coordination. That is Load Split's job; the two modes measure
different halves of the bimanual literature.
- With the shipped cue defaults the go moment is audio-tactile-visual:
  highlight, tone and arpeggio land together, so chord RT and span are
  responses to that mix, not to a visual flash alone. The defaults are
  a whole-suite choice and are not overridden here; cue_flags records
  the mix on every trial row so blocks run under different settings
  never pool silently.
"""
from __future__ import annotations

import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from ...hardware.eeg_trigger import CODES as EEG_CODES
from ...hardware.fsr_detector import PressEvent
from ..scheduling import BalancedScheduler
from ..scoring import ScoreConfig, TrialResult, classify
from ._keys import keymap_for_hand, resolve_key
from .classic import PendingTrial

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


FINGER_LETTERS = ("I", "M", "R", "P")
FINGER_NAMES = ("Index", "Middle", "Ring", "Pinky")
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

# Weight per unit of mirror distance in a cross-hand chord: zero for
# mirror-symmetric chords, growing with spatial asymmetry (the
# symmetry advantage: Kelso 1984; Mechsner 2001). A defended design
# choice, the same status as SIZE_PENALTY.
CROSS_ASYM_WEIGHT = 1.5


def cross_mirror_distance(left: tuple[int, ...],
                          right: tuple[int, ...]) -> float:
    """Spatial asymmetry of a cross-hand chord: each active finger's
    distance to the NEAREST active finger of the other hand in mirror
    coordinates (I=0 M=1 R=2 P=3, both palms down), summed over every
    active finger. Zero exactly when the pattern is mirror-symmetric."""
    d = 0.0
    for f in left:
        d += min(abs(int(f) - int(g)) for g in right)
    for g in right:
        d += min(abs(int(g) - int(f)) for f in left)
    return d


def chord_difficulty_cross(left: tuple[int, ...],
                           right: tuple[int, ...]) -> float:
    """Predicted hardness of a chord spanning both hands: each hand's
    own within-hand D (its quiet fingers still have to stay still),
    the size penalty on TOTAL chord size, and the mirror-distance
    cost for spatial asymmetry."""
    return (chord_difficulty(left) + chord_difficulty(right)
            + SIZE_PENALTY * max(0, len(left) + len(right) - 2)
            + CROSS_ASYM_WEIGHT * cross_mirror_distance(left, right))


def cross_label(left: tuple[int, ...], right: tuple[int, ...]) -> str:
    """Left of the bar is the left hand: I|M means left index with
    right middle."""
    return f"{chord_label(left)}|{chord_label(right)}"


# The cross-hand ladder, (left fingers, right fingers) per chord,
# tiers ordered by D_cross medians: mirror singles, mirror doubles,
# neighbour shifts, far shifts and uneven counts. Explicit for the
# same reason as CHORD_TIERS; the tests recompute every D_cross.
CROSS_TIERS: list[list[tuple[tuple[int, ...], tuple[int, ...]]]] = [
    [((0,), (0,)), ((3,), (3,)), ((1,), (1,)), ((2,), (2,))],
    [((2, 3), (2, 3)), ((0, 1), (0, 1)), ((1, 2), (1, 2))],
    [((0,), (1,)), ((1,), (0,)), ((2,), (3,)), ((3,), (2,)),
     ((1,), (2,)), ((2,), (1,))],
    [((0,), (2,)), ((0,), (1, 2)), ((0,), (3,)), ((0, 1), (2, 3))],
]


@dataclass
class PendingChordTrial:
    """One chord trial: several target lanes, one press per target.
    `targets` are engine-global lane numbers in ascending order.
    `onsets` records the press time per target lane for the CURRENT
    down-state: with live sensors and a hold required, a target that
    lifts before the chord completes loses its onset and must land
    again, so a chord only ever completes off fingers that are really
    down together. A repeat press on a finger still down is ignored,
    so a double-tap cannot look like a wrong press. `hold_released`
    is which targets lifted during the hold, for feedback that names
    the finger. `hand` is the side a within-hand chord belongs to; a
    cross-hand chord (scope "cross") spans both hands, carries
    hand="both" and keeps each side's fingers in `fingers_left` /
    `fingers_right` (its `fingers` tuple stays empty)."""
    trial_id: int
    kind: str                       # "probe" | "chord"
    fingers: tuple[int, ...]        # within-hand finger indices 0..3
    targets: tuple[int, ...]        # engine-global lanes, ascending
    stim_t_perf: float
    tier: int | None                # 0-based tier, None for probes
    w_ms: float
    hand: str = "right"
    scope: str = "within"           # "within" | "cross"
    fingers_left: tuple[int, ...] = ()
    fingers_right: tuple[int, ...] = ()
    onsets: dict[int, float] = field(default_factory=dict)
    keys_pressed: list[int] = field(default_factory=list)
    incorrect_presses: list[tuple[int, float]] = field(default_factory=list)
    settle_ms: float | None = None
    hold_released: list[int] = field(default_factory=list)


class ChordsMode:
    name = "Chords"

    # Scoring split, mirroring the brief's 60/20/20 on the suite's
    # 0-10 trial scale so chord blocks stay comparable to the other
    # modes on the results screen.
    COMPLETION_POINTS = 6
    TOGETHER_POINTS = 2
    QUIET_POINTS = 2
    # Quiet points fall linearly to zero at this ER. Healthy light-force
    # enslaving sits under about 0.15 (Abolins et al. 2020), so the
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
    # Minimum trials between level moves. The window slides (see
    # _staircase), so without a cooldown one hot 10-trial stretch
    # would promote on every subsequent hit.
    LEVEL_CHANGE_COOLDOWN = 4
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
                 demo_trials: int | None = None,
                 lanes_by_hand: dict[str, list[int]] | None = None,
                 warmup_iti_s: float = 0.8,
                 warmup_cap_s: float = 60.0,
                 ) -> None:
        self.engine = engine
        self.hand = hand
        # Which hands play, each with its four lanes indexed by finger
        # 0..3, same per-hand contract as Patterns. One hand plays
        # exactly as it always did; `lanes_by_hand` with both hands
        # makes the hands alternate under the paired balance rules
        # while every chord stays within one hand (see docstring).
        if lanes_by_hand and len([h for h, v in lanes_by_hand.items()
                                  if v]) > 1:
            self.hands = {h: list(v)[:4]
                          for h, v in lanes_by_hand.items() if v}
        else:
            four = list(lanes)[:4]
            while len(four) < 4:
                four.append(len(four))
            self.hands = {hand: four}
        self.hand_names = list(self.hands)
        self.bilateral = len(self.hand_names) > 1
        self.hand_label = "both" if self.bilateral else self.hand_names[0]
        # Kept for the single-hand paths and any older caller: the
        # first (or only) hand's lanes.
        self.lanes = self.hands[self.hand_names[0]]
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
        # Probes pace themselves: a short fixed gap (predictability is
        # harmless for an instructed press) and a hard budget on the
        # whole opening warm-up so the first chord is never more than
        # warmup_cap_s away (see THE WARM-UP IS ANNOUNCED AND CAPPED).
        self.warmup_iti = max(0.0, float(warmup_iti_s))
        self.warmup_cap_s = max(0.0, float(warmup_cap_s))
        self.rest_between = float(rest_between_s)
        self.fatigue_rest = float(fatigue_rest_s)
        self.session_cap_s = float(session_cap_min) * 60.0
        self.demo_trials = demo_trials
        self.rng = random.Random(seed)

        # Session layout counters. Demo (Test Mode) shrinks to a
        # miniature where the CHORDS are the demo: one probe per hand
        # so both trial kinds still land in the CSV, then chords for
        # every remaining trial, rests trimmed. The old miniature gave
        # the probes 2 per hand, which in a bilateral 6-trial demo made
        # two thirds of the whole session single-finger presses: a
        # supervisor (or Basil) walked away believing chords mode never
        # asks for a chord.
        # Probes in a full session scale with the hands in play: 2 per
        # finger PER HAND, so a bilateral session's matrices cover both
        # hands.
        n_hands = len(self.hand_names)
        if demo_trials is not None:
            n = max(2, int(demo_trials))
            self._probe_left_start = min(n_hands, n - 1)
            self._probe_left_end = 0
            self.trials_per_subblock = max(1, n - self._probe_left_start)
            self.subblocks = 1
            self.rest_between = min(self.rest_between, 2.0)
            self.fatigue_rest = min(self.fatigue_rest, 2.0)
        else:
            per = max(0, int(probe_trials_per_finger))
            self._probe_left_start = 4 * per * n_hands
            self._probe_left_end = 4 * per * n_hands
            self.trials_per_subblock = max(1, int(trials_per_subblock))
            self.subblocks = max(1, int(subblocks))
        self._sub_idx = 0
        self._sub_done = 0
        self._probes_planned = self._probe_left_start + self._probe_left_end
        # Warm-up bookkeeping: the planned opening and closing counts
        # (the banner's "3 of 16"), whether the opening budget ran out,
        # and which one-off announcements have fired.
        self._probes_start_planned = self._probe_left_start
        self._probes_end_planned = self._probe_left_end
        self._warmup_capped = False
        self._announced: set[str] = set()
        # Two-axis balance, the PairedBalancedScheduler shape: which
        # hand goes next is its own shuffle bag (counts never drift
        # apart by more than one), and within each hand the fingers or
        # chords are dealt from that hand's own bag.
        self._probe_sched = {h: BalancedScheduler([0, 1, 2, 3], self.rng)
                             for h in self.hand_names}
        self._probe_hand_order = BalancedScheduler(
            list(range(n_hands)), self.rng, avoid_repeats=False)
        self._chord_hand_order = BalancedScheduler(
            list(range(n_hands)), self.rng, avoid_repeats=False)

        # Difficulty state. Level = tier + window combined, easiest
        # first; resets each block, the safe direction to fail. The
        # level is shared across the hands in bilateral play (the
        # weaker hand sets the pace, the safe direction).
        self.level = 0
        self.max_level = 4 * len(self.windows_ms) - 1
        self.highest_level = 0
        self._chord_sched: dict[str, BalancedScheduler] = {}
        self._sched_tier: int | None = None
        self._stair: deque[bool] = deque(maxlen=self.STAIRCASE_WINDOW)
        self._since_level_change = 0
        # Cross-hand chords climb their OWN ladder: pooling hit rates
        # across scopes would let a cross-hand artefact drive the
        # within-hand level (or the reverse), and the two ladders
        # measure different things. Same shape: 4 tiers per window.
        self.level_cross = 0
        self.max_level_cross = 4 * len(self.windows_ms) - 1
        self.highest_level_cross = 0
        self._cross_sched: BalancedScheduler | None = None
        self._cross_sched_tier: int | None = None
        self._stair_cross: deque[bool] = deque(
            maxlen=self.STAIRCASE_WINDOW)
        self._since_level_change_cross = 0
        # Scope-pure sub-blocks in bilateral play: of each five, the
        # third and fifth deal cross-hand chords, in a FIXED order so
        # fatigue trends stay comparable across sessions and the EEG
        # layer gets clean block-level contrasts. A short custom
        # config still gets at least one cross sub-block whenever it
        # has two or more. Unilateral play is all within, unchanged.
        self._scope_seq = self._plan_scope_sequence()

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
        self._hold_t0: float | None = None
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

        # Quiet-fingers reward state the gameplay screen reads: the
        # lanes that stayed still through the last clean chord, and
        # when that chord closed. None until the first hit.
        self._quiet_tick_lanes: list[int] = []
        self._quiet_tick_t: float | None = None

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

    @property
    def current_w_cross_ms(self) -> float:
        return self.windows_ms[min(self.level_cross // 4,
                                   len(self.windows_ms) - 1)]

    @property
    def current_tier_cross(self) -> int:
        return self.level_cross % 4

    def _plan_scope_sequence(self) -> list[str]:
        """One scope per training sub-block, fixed for the session."""
        if not self.bilateral:
            return ["within"] * self.subblocks
        template = ["within", "within", "cross", "within", "cross"]
        seq = [template[i % len(template)] for i in range(self.subblocks)]
        if self.subblocks >= 2 and "cross" not in seq:
            seq[-1] = "cross"
        return seq

    @property
    def current_scope(self) -> str:
        """Which scope the next chord draws from. The Test Mode
        miniature has one sub-block, so bilateral demos alternate the
        scopes per chord instead: a 60 second demo must show both."""
        if not self.bilateral:
            return "within"
        if self.demo_trials is not None:
            return "cross" if self._sub_done % 2 else "within"
        idx = min(self._sub_idx, len(self._scope_seq) - 1)
        return self._scope_seq[idx] if self._scope_seq else "within"

    def warmup_state(self) -> tuple[str, int, int] | None:
        """("warmup" | "winddown", done, planned) while the probe sets
        run, None during the chords. The gameplay screen draws this as
        a persistent banner so the single-finger stretch is visibly a
        warm-up and not the game."""
        if self._probe_left_start > 0:
            done = self._probes_start_planned - self._probe_left_start
            return ("warmup", done, self._probes_start_planned)
        if (not self._in_training() and self._probe_left_end > 0
                and self._probes_end_planned > 0
                and self.phase != "done"):
            done = self._probes_end_planned - self._probe_left_end
            return ("winddown", done, self._probes_end_planned)
        return None

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
                     "_hold_t0", "_hold_until", "_rest_until", "_t0",
                     "_quiet_tick_t"):
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

    # ---- lane-to-hand resolution -------------------------------------------
    def _hand_of_lane(self, lane: int) -> str:
        for h, lanes in self.hands.items():
            if lane in lanes:
                return h
        return self.hand_names[0]

    def _finger_of_lane(self, lane: int) -> int:
        lanes = self.hands.get(self._hand_of_lane(lane), self.lanes)
        try:
            return max(0, min(3, lanes.index(lane)))
        except ValueError:
            return max(0, min(3, lane - lanes[0]))

    # ---- live sensor state -------------------------------------------------
    def _hand_detector(self, hand: str | None = None):
        dets = getattr(self.engine, "detectors", None)
        if not isinstance(dets, dict):
            return None
        return dets.get(hand or self.hand_names[0])

    def _hand_quiet(self) -> bool:
        """No finger of ANY playing hand past its press threshold: in
        bilateral play the whole device must be at rest before a chord
        fires, or the resting hand's fidgeting leaks into the next
        trial's baseline. The keyboard fallback has no live state, so
        it is always quiet and the gate reduces to the inter-trial
        wait."""
        for h in self.hand_names:
            det = self._hand_detector(h)
            pressed = getattr(det, "pressed", None)
            try:
                if pressed is not None and any(pressed):
                    return False
            except TypeError:
                continue
        return True

    def _lane_pressed(self, lane: int) -> bool:
        det = self._hand_detector(self._hand_of_lane(lane))
        pressed = getattr(det, "pressed", None)
        try:
            return bool(pressed[self._finger_of_lane(lane)])
        except (TypeError, IndexError, KeyError):
            return False

    # ---- per-finger normalisation ------------------------------------------
    def _reference_counts(self, lane: int) -> float:
        """This finger's calibrated light-press gap in counts, the
        normaliser for every force in this mode, from the lane's own
        hand's profile so the two hands never share thresholds. Falls
        back to the shipped thresholds (trigger / 0.40) when no in-app
        calibration has been run, and to the same numbers hard-coded
        when even the config cannot be read (test doubles)."""
        finger = self._finger_of_lane(lane)
        profs = getattr(self.engine, "calibration_profiles", None)
        if isinstance(profs, dict):
            prof = profs.get(self._hand_of_lane(lane))
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

    def _reference_basis(self) -> dict[str, dict]:
        """Per hand, where _reference_counts gets its normaliser:
        basis 'profile' with the profile's creation stamp and
        participant, or 'config_fallback' when no usable profile is
        applied. Recorded in block_stats so the analysis can tell a
        session normalised by this patient's own light press from one
        running on inherited or default numbers."""
        out: dict[str, dict] = {}
        profs = getattr(self.engine, "calibration_profiles", None)
        for hand in self.hand_names:
            prof = profs.get(hand) if isinstance(profs, dict) else None
            usable = False
            try:
                usable = prof is not None and any(
                    float(g) > 0 for g in prof.gap())
            except (AttributeError, TypeError, ValueError):
                usable = False
            if usable:
                out[hand] = {
                    "basis": "profile",
                    "created_at": str(getattr(prof, "created_at", "")),
                    "participant": str(getattr(prof, "participant",
                                               "") or ""),
                }
            else:
                out[hand] = {"basis": "config_fallback"}
        return out

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

    # ---- pre-play prep -----------------------------------------------------
    def prep_tick(self, dt: float) -> None:
        """Called by the gameplay screen each frame of the 3 s get
        ready countdown, while update() is held back. The baseline
        quiet requirement runs INSIDE the prep instead of after it:
        the quiet clock accumulates here, so a hand that settled
        during the countdown fires its first chord the moment play
        starts rather than stacking a second wait on top."""
        now = time.perf_counter()
        if self._hand_quiet():
            if self._quiet_since is None:
                self._quiet_since = now
        else:
            self._quiet_since = None

    # ---- live hold state ---------------------------------------------------
    @property
    def hold_required(self) -> bool:
        """True when this block really enforces the hold: live sensor
        state plus a configured hold time. The screen keys the hold
        visuals off this so keyboard play, which skips the hold, never
        shows a progress ring it will not honour."""
        return bool(self._fsr and self.hold_s > 0)

    def hold_progress(self) -> float | None:
        """0..1 while a hold is in flight, None otherwise. The screen
        draws this as a ring filling on the held tiles, so the patient
        watches the hold complete WHILE pressing. It exists because the
        first build's only hold feedback was a message after the trial
        had closed, when there was nothing left to act on."""
        if self.phase != "hold" or self.active is None:
            return None
        if self._hold_t0 is None or self._hold_until is None:
            return None
        total = self._hold_until - self._hold_t0
        if total <= 0:
            return 1.0
        frac = (time.perf_counter() - self._hold_t0) / total
        return max(0.0, min(1.0, frac))

    def _drop_lifted_onsets(self) -> None:
        """Withdraw the onset of any target that pressed and lifted
        again before the chord completed. Without this, a stale onset
        let the LAST finger complete a chord an earlier finger had
        already left: the hold check then failed on that same frame,
        so the trial closed at the instant of the press with a hold
        message the patient could do nothing about (the confusion
        Basil reported). With the withdrawal, a chord only completes
        off fingers that are down together, and the hold can always
        be satisfied by simply staying down. Keyboard play has no
        live press state, so onsets stand as pressed there."""
        if self.active is None or not self.hold_required:
            return
        for lane in list(self.active.onsets):
            if not self._lane_pressed(lane):
                del self.active.onsets[lane]

    # ---- main tick ---------------------------------------------------------
    def update(self, dt: float) -> None:
        now = time.perf_counter()
        if self._t0 is None:
            self._t0 = now
        # Withdrawals run BEFORE the press queue drains: a queued
        # last-finger press must complete the chord against the live
        # down-state, not against onsets a finger already left.
        if self.phase == "stim":
            self._drop_lifted_onsets()
        while self._presses:
            self._handle_press(self._presses.popleft(), now)
        if self.phase == "done":
            return
        # The session cap must fire even when no trial ever closes: a
        # hand that never settles (or a dropped device that never
        # reconnects) used to loop 'Relax your hand' forever while the
        # cap expired silently. Trials in flight still finish first
        # (stim/hold phases skip this), so the cap never cuts a trial
        # in half.
        if (self.phase in ("settle", "rest")
                and self._t0 is not None
                and (now - self._t0) > self.session_cap_s):
            self._set_message("Session complete", 2.0)
            self._end("time_cap")
            return
        if self.phase == "rest":
            self._update_rest(now)
            return
        if self.phase == "hold":
            # Drop check FIRST: the engine clears the pressed latches
            # on disconnect, so without it a mid-hold drop read as
            # every finger lifting at once and the patient was told a
            # finger 'lifted too soon'.
            if self.active is not None and self._source_dropped():
                self._finish_device_drop(now)
                return
            self._update_hold(now)
            return
        if self.phase == "stim":
            if self.active is not None and self._source_dropped():
                self._finish_device_drop(now)
                return
            if (self.active is not None
                    and (now - self.active.stim_t_perf) > self.timeout):
                self._finish(now, hold_achieved=None)
            return
        self._update_settle(now)

    def _source_dropped(self) -> bool:
        """Whether the hardware behind the active trial's hand(s) is
        gone right now. A whole-source drop counts, and so does a
        one-board drop of a hand the trial needs (engine._hands_down,
        maintained by the per-frame connection check)."""
        if not self._fsr:
            return False
        src = getattr(self.engine, "source", None)
        if src is None:
            return False
        if not getattr(src, "is_connected", True):
            return True
        down = getattr(self.engine, "_hands_down", None)
        if not isinstance(down, set):
            down = set()
        if not down or self.active is None:
            return False
        if self.active.scope == "cross":
            return bool(down & set(self.hand_names))
        return self.active.hand in down

    def _finish_device_drop(self, now: float) -> None:
        """Close the in-flight trial as hardware loss, not patient
        failure. Before this, the disconnect handler's latch clear
        made a mid-hold drop close as class no_hold with feedback
        naming a finger that 'lifted too soon', and a sustained drop
        produced a run of partial misses that demoted the staircase
        and could end the session labelled as patient fatigue. A
        device_drop record moves nothing: no staircase step, no
        sub-block hit rate entry, no fatigue comparison; the trial is
        re-dealt once the settle gate sees a live, quiet hand."""
        trial = self.active
        if trial is None:
            return
        self.active = None
        self._hold_t0 = None
        self._hold_until = None
        outcome = TrialResult(label="Miss", points=0, rt_ms=None)
        log_obj = PendingTrial(
            trial_id=trial.trial_id,
            lane=trial.targets[0],
            stim_t_perf=trial.stim_t_perf,
            keys_pressed=list(trial.keys_pressed),
            incorrect_presses=list(trial.incorrect_presses),
        )
        stim = "+".join(str(l + 1) for l in trial.targets)
        if trial.scope == "cross":
            stim = "x:" + stim
        self.engine.log_trial(log_obj, outcome, now,
                              stimulus=stim + ";device_drop",
                              correct_lanes=list(trial.targets),
                              hand=(None if trial.scope == "cross"
                                    else trial.hand),
                              error_type="device_drop")
        cross = trial.scope == "cross"
        self._records.append({
            "trial": trial.trial_id,
            "kind": trial.kind,
            "scope": trial.scope,
            "hand": "both" if cross else trial.hand,
            "chord": (cross_label(trial.fingers_left,
                                  trial.fingers_right) if cross
                      else chord_label(trial.fingers)),
            "tier": None if trial.tier is None else trial.tier + 1,
            "d": None,
            "w_ms": trial.w_ms,
            "level": self.level_cross if cross else self.level,
            "class": "device_drop",
            "span_ms": None, "rt_ms": None, "complete_ms": None,
            "er": None, "press_norm": None, "leaks": None,
            "hold": None, "over_force": False, "light": False,
            "wrong": False, "settle_ms": None, "subblock": None,
        })
        self._set_message("Sensor connection lost", 1.5, kind="warn")
        # Re-deal rather than advance: the trial produced no evidence
        # about the patient, and the settle gate will hold until the
        # hardware is back and the hand is genuinely resting. A probe
        # budget or sub-block count consumed here would silently
        # shrink the session's real material.
        self._arm_next(now)

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
                # A dropped sensor connection is not something
                # relaxing the hand can fix; say so instead of
                # repeating advice that cannot help (audit finding
                # #27). engine.detectors' pressed state is cleared on
                # disconnect (GameEngine._check_source_connection), so
                # this prompt is reachable again rather than the gate
                # freezing on a stale press latch.
                src = getattr(self.engine, "source", None)
                if (self._fsr and src is not None
                        and getattr(src, "provides_samples", False)
                        and not getattr(src, "is_connected", True)):
                    self._set_message("Sensor connection lost", 1.2,
                                      kind="warn")
                else:
                    self._set_message("Relax your hand", 1.2)
            return
        self._fire(now)

    # ---- firing ------------------------------------------------------------
    def _next_targets(self) -> tuple[str, str, str,
                                     tuple[int, ...], tuple[int, ...]]:
        """What the next trial asks for, as (kind, scope, hand,
        fingers, fingers_right): a single-finger probe at the
        session's edges, otherwise a chord from the current scope's
        tier. For probes and within-hand chords `fingers` is the
        chord within `hand` and `fingers_right` is empty; for a
        cross-hand chord hand is "both", `fingers` is the LEFT hand's
        share and `fingers_right` the right's. In bilateral play the
        within-hand side comes off its own shuffle bag so the hands'
        trial counts never drift apart by more than one, while each
        hand's chords or probe fingers come off that hand's own bag;
        cross-hand chords need no hand bag (every trial uses both) so
        one bag per tier deals them."""
        if self._probe_left_start > 0 or not self._in_training():
            hand = self.hand_names[self._probe_hand_order.next()]
            return "probe", "within", hand, (
                self._probe_sched[hand].next(),), ()
        if self.current_scope == "cross":
            tier = self.current_tier_cross
            if self._cross_sched_tier != tier:
                self._cross_sched = BalancedScheduler(
                    list(range(len(CROSS_TIERS[tier]))), self.rng)
                self._cross_sched_tier = tier
            left, right = CROSS_TIERS[tier][self._cross_sched.next()]
            return "chord", "cross", "both", left, right
        tier = self.current_tier
        if self._sched_tier != tier:
            # Fresh shuffle bags whenever the tier changes so the
            # chords of the new tier get equal counts from here, per
            # hand.
            self._chord_sched = {
                h: BalancedScheduler(
                    list(range(len(CHORD_TIERS[tier]))), self.rng)
                for h in self.hand_names}
            self._sched_tier = tier
        hand = self.hand_names[self._chord_hand_order.next()]
        return ("chord", "within", hand,
                CHORD_TIERS[tier][self._chord_sched[hand].next()], ())

    def _in_training(self) -> bool:
        return self._sub_idx < self.subblocks

    def _fire(self, now: float) -> None:
        kind, scope, hand, fingers, fingers_right = self._next_targets()
        if scope == "cross":
            targets = tuple(sorted(
                [self.hands["left"][f] for f in fingers]
                + [self.hands["right"][f] for f in fingers_right]))
            w_ms = self.current_w_cross_ms
            tier = self.current_tier_cross
        else:
            hand_lanes = self.hands[hand]
            targets = tuple(sorted(hand_lanes[f] for f in fingers))
            w_ms = self.current_w_ms
            tier = None if kind == "probe" else self.current_tier
        self.trial_counter += 1
        settle_ms = None
        if self._settle_t0 is not None:
            settle_ms = (now - self._settle_t0) * 1000.0
        self.active = PendingChordTrial(
            trial_id=self.trial_counter,
            kind=kind,
            fingers=(() if scope == "cross"
                     else tuple(sorted(fingers))),
            targets=targets,
            stim_t_perf=now,
            tier=tier,
            w_ms=w_ms,
            hand=hand,
            scope=scope,
            fingers_left=(tuple(sorted(fingers))
                          if scope == "cross" else ()),
            fingers_right=(tuple(sorted(fingers_right))
                           if scope == "cross" else ()),
            settle_ms=settle_ms,
        )
        self.phase = "stim"
        self._quiet_since = None
        self._settle_t0 = None
        self._announce(kind, scope, hand)
        # ALL target fingers light at once; with the buzzer channel on,
        # the engine turns a same-board multi-lane stim into the
        # arpeggio (see engine.on_stim_multi). A cross-hand chord is
        # two boards, and two boards buzz together.
        self.engine.on_stim_multi(list(targets), self.trial_counter, now)

    def _announce(self, kind: str, scope: str, hand: str) -> None:
        """The words that keep the session legible: warm-up and
        wind-down probes say they are probes (with a counter, so the
        patient can see the warm-up ending), the first chord announces
        the game proper, and in bilateral play each chord names its
        side. Side naming is suppressed when the screen may not name
        the target: a hand label is half the answer. The warm-up
        wording itself names no finger, so it always shows."""
        show_target = True
        try:
            show_target = bool(self.engine.cue_settings().show_target)
        except Exception:
            pass
        if kind == "probe":
            state = self.warmup_state()
            if state is not None:
                word = ("Warm-up" if state[0] == "warmup"
                        else "Wind-down")
                if state[0] == "winddown" and "winddown" not in \
                        self._announced:
                    self._announced.add("winddown")
                    self._set_message(
                        "Chords done. Single fingers to finish", 1.8)
                else:
                    label = f"{word} {state[1] + 1} of {state[2]}"
                    if self.bilateral and show_target:
                        label += f": {hand} hand"
                    self._set_message(label, 1.1)
            return
        if "chords" not in self._announced:
            self._announced.add("chords")
            self._set_message("Warm-up done. Chords: press together",
                              1.8, kind="best")
            return
        if self.bilateral and show_target:
            self._set_message("Both hands" if scope == "cross"
                              else f"{hand.title()} hand", 0.9)

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
            # One onset per down-state: a repeat event on a finger
            # still down must not read as a wrong press, while a
            # finger that lifted (onset withdrawn) records a fresh
            # onset when it lands again.
            if ev.lane not in self.active.onsets:
                self.active.onsets[ev.lane] = ev.t_perf
            # Completion only from the stim phase: once the hold is
            # running, a stray duplicate press must not restart the
            # hold clock.
            if (self.phase == "stim"
                    and len(self.active.onsets)
                    == len(self.active.targets)):
                if self.hold_required:
                    self.phase = "hold"
                    # The hold runs from the last finger's own press
                    # edge, not from the frame that drained the event
                    # queue, so queue latency is credited to the
                    # patient rather than added to the hold.
                    self._hold_t0 = ev.t_perf
                    self._hold_until = ev.t_perf + self.hold_s
                    # Words for the ring that starts filling now; the
                    # outcome message replaces this at trial close.
                    self._set_message("Keep holding",
                                      max(0.6, self.hold_s))
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
            self._hold_t0 = None
            self._hold_until = None
            return
        lifted = [l for l in self.active.targets
                  if not self._lane_pressed(l)]
        if lifted:
            # A finger slipped off before the hold ended. Short hold on
            # purpose (enslaving drifts up during sustained holds), but
            # it does have to be met for a clean hit. Record WHICH
            # fingers lifted so the feedback can name them instead of
            # lecturing about the beat.
            self.active.hold_released = lifted
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
        self._hold_t0 = None
        self._hold_until = None
        n_targets = len(trial.targets)
        n_pressed = len(trial.onsets)
        full = n_pressed == n_targets
        w_ms = trial.w_ms

        span_ms = None
        rt_ms = None
        complete_ms = None
        if full:
            first = min(trial.onsets.values())
            last = max(trial.onsets.values())
            span_ms = (last - first) * 1000.0
            # rt_ms is the brief's RT (first target onset minus go), not
            # chord completion: classify()'s speed tiers and the results
            # screen's RT cards are built for a single-press latency, and
            # feeding them the last-finger time made a slow chord read as
            # a fast press. Completion time is kept separately below
            # (complete_ms) for anyone who wants it.
            rt_ms = (first - trial.stim_t_perf) * 1000.0
            complete_ms = (last - trial.stim_t_perf) * 1000.0
        together = full and span_ms is not None and span_ms <= w_ms

        # Cross-talk from the engine's force window, normalised per
        # finger by the calibrated light press. Read before log_trial
        # closes the window. For a within-hand chord, leak is measured
        # against the chord's OWN hand only: cross-talk is a
        # within-hand quantity, and the other hand resting has its own
        # trials to speak on (its silence is logged separately as
        # mirror_leak below). A cross-hand chord is scored per hand,
        # each hand's leak against its OWN targets and quiet fingers,
        # and the two ER values stay separate all the way to the
        # summary (Li 2001: pooling them hides exactly the asymmetric
        # interaction the tiers exist to show).
        peaks = self._window_peaks()
        er = None
        er_by_hand: dict[str, float | None] = {}
        press_by_hand: dict[str, float] = {}
        max_leak_ratio = None
        max_leak_lane = None
        over_force = False
        light_press = False
        leak_norms: dict[int, float] = {}
        mean_press = 0.0
        mirror_leak = None
        if peaks is not None:
            if trial.scope == "cross":
                scored_hands = list(self.hand_names)
            else:
                scored_hands = [trial.hand]
            all_lanes = [l for h in scored_hands
                         for l in self.hands[h]]
            norms = {l: max(0.0, peaks.get(l, 0.0))
                     / self._reference_counts(l) for l in all_lanes}
            press_norms = [norms[l] for l in trial.targets]
            mean_press = (sum(press_norms) / len(press_norms)
                          if press_norms else 0.0)
            # ER only exists on a COMPLETE response: the denominator
            # averages over every target, so a freeze-partial (one of
            # two targets landed) halves it and mechanically doubles
            # er. A hand with a true 0.05 leak recorded er 0.10 on a
            # 1-of-2 partial, scaling with chord size, and those
            # inflated values flowed into median_er, the per-chord
            # table and the across-session ER curve, where early
            # freeze-heavy sessions read as worse enslaving and later
            # completer sessions as improvement that was really
            # response completeness. Partial trials keep their class
            # and leak evidence; they just carry no er.
            response_complete = full
            for h in scored_hands:
                h_lanes = list(self.hands[h])
                h_press = [norms[l] for l in trial.targets
                           if l in h_lanes]
                h_leaks = {l: norms[l] for l in h_lanes
                           if l not in trial.targets}
                hp = (sum(h_press) / len(h_press)) if h_press else 0.0
                press_by_hand[h] = hp
                if response_complete and hp > 0 and h_leaks:
                    er_by_hand[h] = (sum(h_leaks.values())
                                     / len(h_leaks) / hp)
                    worst = max(h_leaks.values()) / hp
                    if max_leak_ratio is None or worst > max_leak_ratio:
                        max_leak_ratio = worst
                        max_leak_lane = max(h_leaks,
                                            key=h_leaks.get)
                else:
                    er_by_hand[h] = None
                leak_norms.update(h_leaks)
            if trial.scope == "cross":
                # Scoring uses the WORST hand's ER; the per-hand
                # values are what the analysis reads. er itself stays
                # None on cross records so no within-hand ER aggregate
                # can swallow a cross trial by accident.
                measured = [v for v in er_by_hand.values()
                            if v is not None]
                er = max(measured) if measured else None
            else:
                er = er_by_hand.get(trial.hand)
                # Silent mirror force: the resting hand's loudest
                # normalised peak against this chord's mean press.
                # Only meaningful with both boards live.
                if self.bilateral and mean_press > 0:
                    other = [h for h in self.hand_names
                             if h != trial.hand]
                    other_lanes = [l for h in other
                                   for l in self.hands[h]]
                    other_norms = [
                        max(0.0, peaks.get(l, 0.0))
                        / self._reference_counts(l)
                        for l in other_lanes]
                    if other_norms:
                        mirror_leak = max(other_norms) / mean_press
            if mean_press > 0:
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
            # The together bonus is forfeited when the hold broke: a
            # chord that fell apart before hold_ms did not stay
            # together, and paying full marks anyway is what made the
            # old hold message read as nonsense next to a 10-point
            # "Good".
            if together and w_ms > 0 and hold_achieved is not False:
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
        # simplification the block summary does not share). A
        # cross-hand chord writes "x:1+5" instead: the scope lives in
        # the stimulus descriptor itself, so no lane arithmetic can
        # ever mistake a cross chord for a within one (the notebook's
        # chord parser maps lanes mod 4, under which "1+5" would read
        # as a single-finger probe).
        log_obj = PendingTrial(
            trial_id=trial.trial_id,
            lane=trial.targets[0],
            stim_t_perf=trial.stim_t_perf,
            keys_pressed=list(trial.keys_pressed),
            incorrect_presses=list(trial.incorrect_presses),
        )
        stim = "+".join(str(l + 1) for l in trial.targets)
        if trial.scope == "cross":
            stim = "x:" + stim
        self.engine.log_trial(log_obj, outcome, now,
                              stimulus=stim,
                              correct_lanes=list(trial.targets),
                              hand=(None if trial.scope == "cross"
                                    else trial.hand))
        self._set_message(self._feedback_text(trial, cls, over_force,
                                              light_press, max_leak_lane),
                          0.9,
                          kind="success" if cls == "hit" else "warn")
        # Quiet-fingers reward moment: a clean chord leaves the
        # untargeted fingers wearing a brief tick on the gameplay
        # screen: its own hand's for a within chord, both hands' for a
        # cross chord (the whole device had to stay quiet). State
        # only; the screen draws and fades it.
        if trial.scope == "cross":
            own_lanes = [l for h in self.hand_names
                         for l in self.hands[h]]
        else:
            own_lanes = list(self.hands[trial.hand])
        if cls == "hit" and len(trial.targets) < len(own_lanes):
            self._quiet_tick_lanes = [l for l in own_lanes
                                      if l not in trial.targets]
            self._quiet_tick_t = now

        # Temporal coupling on a full cross chord: which hand led, and
        # by how much (first onset to first onset). The coupling
        # literature's yoking measure (Kelso 1979; Swinnen 2002).
        lead_hand = None
        lag_ms = None
        if trial.scope == "cross" and full:
            firsts: dict[str, float] = {}
            for h in self.hand_names:
                h_on = [t for l, t in trial.onsets.items()
                        if l in self.hands[h]]
                if h_on:
                    firsts[h] = min(h_on)
            if len(firsts) == 2:
                lead_hand = min(firsts, key=firsts.get)
                trail = max(firsts, key=firsts.get)
                lag_ms = (firsts[trail] - firsts[lead_hand]) * 1000.0

        cross = trial.scope == "cross"
        rec = {
            "trial": trial.trial_id,
            "kind": trial.kind,
            "scope": trial.scope,
            "hand": "both" if cross else trial.hand,
            "chord": (cross_label(trial.fingers_left,
                                  trial.fingers_right) if cross
                      else chord_label(trial.fingers)),
            "tier": None if trial.tier is None else trial.tier + 1,
            "d": (chord_difficulty_cross(trial.fingers_left,
                                         trial.fingers_right) if cross
                  else chord_difficulty(trial.fingers)),
            "w_ms": w_ms,
            "level": self.level_cross if cross else self.level,
            "class": cls,
            "span_ms": None if span_ms is None else round(span_ms, 1),
            "rt_ms": None if rt_ms is None else round(rt_ms, 1),
            "complete_ms": (None if complete_ms is None
                            else round(complete_ms, 1)),
            # er stays a WITHIN-hand number: cross trials leave it
            # empty and carry per-hand values instead, so no
            # within-hand aggregate can swallow a cross trial.
            "er": (None if cross or er is None else round(er, 4)),
            # Probe rows keep the raw material for the enslaving
            # matrix: the instructed finger's normalised press and
            # every quiet finger's normalised leak, keyed by the
            # finger's index within the trial's own hand.
            "press_norm": (round(mean_press, 4)
                           if trial.kind == "probe" and mean_press > 0
                           else None),
            "leaks": ({str(self._finger_of_lane(l)): round(v, 4)
                       for l, v in leak_norms.items()}
                      if trial.kind == "probe" and leak_norms else None),
            "hold": hold_achieved,
            "over_force": over_force,
            "light": light_press,
            # A wrong-finger press is a RESPONSE error, not enslaving:
            # the flag lets the probe matrices (and any offline
            # consumer) keep cue-misread probes out of the transfer
            # measure without discarding the genuine-leak leak_fails.
            "wrong": bool(trial.incorrect_presses),
            "settle_ms": (None if trial.settle_ms is None
                          else round(trial.settle_ms, 1)),
            "subblock": (self._sub_idx + 1
                         if trial.kind == "chord" else None),
        }
        if cross:
            rec.update({
                "chord_left": chord_label(trial.fingers_left),
                "chord_right": chord_label(trial.fingers_right),
                "mirror": trial.fingers_left == trial.fingers_right,
                "asym": cross_mirror_distance(trial.fingers_left,
                                              trial.fingers_right),
                "er_left": (None if er_by_hand.get("left") is None
                            else round(er_by_hand["left"], 4)),
                "er_right": (None if er_by_hand.get("right") is None
                             else round(er_by_hand["right"], 4)),
                "press_left": (round(press_by_hand["left"], 4)
                               if press_by_hand.get("left") else None),
                "press_right": (round(press_by_hand["right"], 4)
                                if press_by_hand.get("right")
                                else None),
                "lead_hand": lead_hand,
                "lag_ms": (None if lag_ms is None
                           else round(lag_ms, 1)),
            })
        elif self.bilateral and trial.kind == "chord":
            # Silent mirror force on the resting hand, the free
            # measure bilateral within-hand chords carry.
            rec["mirror_leak"] = (None if mirror_leak is None
                                  else round(mirror_leak, 4))
        self._records.append(rec)
        self.completed += 1

        if trial.kind == "chord":
            self._sub_hits += 1 if cls == "hit" else 0
            if rt_ms is not None:
                self._sub_rts.append(rt_ms)
            if cross:
                self._staircase_cross(cls == "hit")
            else:
                self._staircase(cls == "hit")
        self._advance(now, trial.kind)

    def _finger_name(self, trial: PendingChordTrial, lane: int) -> str:
        """The finger's name for feedback, hand-prefixed in bilateral
        play so "Ring" can never mean the wrong hand. The prefix is
        the LANE's own hand, which for a within-hand chord is the
        trial's hand and for a cross-hand chord is whichever side the
        named finger sits on."""
        f = max(0, min(3, self._finger_of_lane(lane)))
        name = FINGER_NAMES[f]
        if self.bilateral:
            return f"{self._hand_of_lane(lane).title()} {name.lower()}"
        return name

    def _feedback_text(self, trial: PendingChordTrial, cls: str,
                       over_force: bool, light: bool,
                       max_leak_lane: int | None = None) -> str:
        """Failure wording says the ACTION, never the mechanism: which
        finger lifted, which landed late, which never landed. The old
        "Hold it a beat longer" always arrived after the trial had
        closed, so there was nothing to hold; the live ring now covers
        the during-the-press half of that job."""
        if over_force:
            return "Too hard, press lighter"
        if cls == "hit":
            return ("Chord! *" if light and trial.kind == "chord"
                    else "Chord!")
        if cls == "late_chord":
            # Name the finger that closed the span.
            if trial.onsets:
                last = max(trial.onsets, key=lambda l: trial.onsets[l])
                return (f"{self._finger_name(trial, last)} was late, "
                        "press together")
            return "Press together"
        if cls == "no_hold":
            lifted = list(trial.hold_released)
            if len(lifted) == 1:
                return (f"{self._finger_name(trial, lifted[0])} "
                        "lifted too soon")
            return "Released too soon"
        if cls == "leak_fail":
            quiet = [f for f in range(4) if f not in trial.fingers]
            if trial.incorrect_presses:
                lane = trial.incorrect_presses[0][0]
                return f"{self._finger_name(trial, lane)} leaked"
            if max_leak_lane is not None:
                return f"{self._finger_name(trial, max_leak_lane)} leaked, keep it still"
            return "Quiet fingers leaked" if quiet else "Leaked"
        # partial: a target was missing when the trial timed out.
        missing = [l for l in trial.targets if l not in trial.onsets]
        if missing and all(l in trial.keys_pressed for l in missing):
            # Every missing finger DID land at some point but lifted
            # again before the chord formed: the failure is
            # togetherness, not reach.
            return "Press together and keep them down"
        if len(missing) == 1:
            return f"{self._finger_name(trial, missing[0])} never landed"
        return "Fingers missing"

    # ---- progression -------------------------------------------------------
    def _staircase(self, hit: bool) -> None:
        """8-of-10 sliding window with a short cooldown after any
        level move, instead of the old clear-on-promote. Clearing
        meant at most one promotion per 10 trials, and with levels
        reset to 0 every block a flawless player topped out at level
        10 of 15 unilaterally (6 within / 4 cross bilaterally): the
        top half of both ladders, including the W=100 ms floor the
        docstring defends, was unreachable content, and a patient at
        ceiling repeated the same easy tiers every session. The
        criterion is unchanged (8 of the last 10 clean hits up, 5 or
        fewer down); only the evidence window now slides, and the
        cooldown stops one hot streak cascading through several
        levels in as many trials."""
        self._stair.append(hit)
        self._since_level_change += 1
        if len(self._stair) < self.STAIRCASE_WINDOW:
            return
        if self._since_level_change < self.LEVEL_CHANGE_COOLDOWN:
            return
        hits = sum(1 for h in self._stair if h)
        if hits >= self.PROMOTE_HITS and self.level < self.max_level:
            self.level += 1
            self.highest_level = max(self.highest_level, self.level)
            self._since_level_change = 0
            self._set_message("Level up", 1.2, kind="best")
        elif hits <= self.DEMOTE_HITS and self.level > 0:
            self.level -= 1
            self._since_level_change = 0

    def _staircase_cross(self, hit: bool) -> None:
        """The cross-hand ladder's own staircase, same rule, separate
        state: within and cross hit rates must never pool (see the
        constructor comment)."""
        self._stair_cross.append(hit)
        self._since_level_change_cross += 1
        if len(self._stair_cross) < self.STAIRCASE_WINDOW:
            return
        if self._since_level_change_cross < self.LEVEL_CHANGE_COOLDOWN:
            return
        hits = sum(1 for h in self._stair_cross if h)
        if (hits >= self.PROMOTE_HITS
                and self.level_cross < self.max_level_cross):
            self.level_cross += 1
            self.highest_level_cross = max(self.highest_level_cross,
                                           self.level_cross)
            self._since_level_change_cross = 0
            self._set_message("Level up", 1.2, kind="best")
        elif hits <= self.DEMOTE_HITS and self.level_cross > 0:
            self.level_cross -= 1
            self._since_level_change_cross = 0

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
                # The warm-up budget: when the opening probes are
                # still running past warmup_cap_s of session time, the
                # remainder move to the closing set and the chords
                # start. The start matrix gets fewer probes behind it,
                # which the summary records; the alternative is a
                # session whose first minutes are all warm-up.
                if (self._probe_left_start > 0
                        and self._probe_left_end > 0
                        and self._t0 is not None
                        and (now - self._t0) > self.warmup_cap_s):
                    self._warmup_capped = True
                    self._probe_left_end += self._probe_left_start
                    self._probes_end_planned += self._probe_left_start
                    self._probe_left_start = 0
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
        # Probes pace themselves on the short fixed warm-up gap; the
        # jittered ITI belongs to the chords, whose timing is the
        # thing being measured (a chord must be reacted to, a probe is
        # an instructed press).
        if self._probe_left_start > 0 or not self._in_training():
            self._next_ok_t = now + self.warmup_iti
        else:
            self._next_ok_t = now + self.rng.uniform(self.iti_min,
                                                     self.iti_max)
        self._quiet_since = None
        self._settle_t0 = None

    def _close_subblock(self, now: float) -> None:
        n = max(1, self._sub_done)
        rts = sorted(self._sub_rts)
        median_rt = rts[len(rts) // 2] if rts else None
        scope = self.current_scope
        stats = {"subblock": self._sub_idx + 1,
                 "scope": scope,
                 "hit_rate": round(self._sub_hits / n, 3),
                 "median_rt_ms": (None if median_rt is None
                                  else round(median_rt, 1)),
                 "level_at_end": (self.level_cross if scope == "cross"
                                  else self.level)}
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
            # Ease the ladder the fatigued sub-block was climbing.
            if stats.get("scope") == "cross":
                self.level_cross = max(0, self.level_cross - 1)
                self._stair_cross.clear()
                self._since_level_change_cross = 0
            else:
                self.level = max(0, self.level - 1)
                self._stair.clear()
                self._since_level_change = 0
            self._enter_rest(now, self.fatigue_rest, "fatigue",
                             "Take a longer breather")
        else:
            self._enter_rest(now, self.rest_between, "between",
                             "Rest your hand")

    def _fatigue_check(self, stats: dict) -> bool:
        """Judge this sub-block against the session's first sub-block
        OF THE SAME SCOPE. Both triggers point the same way: the hand
        is tiring, and a tired hand trains the wrong signal. Cross
        sub-blocks are judged against the first cross sub-block only,
        because cross-hand chords are legitimately harder and a scope
        difference must not read as fatigue."""
        if len(self._sub_stats) < 2:
            return False
        scope = stats.get("scope", "within")
        earlier = [s for s in self._sub_stats[:-1]
                   if s.get("scope", "within") == scope]
        if not earlier:
            return False
        first = earlier[0]
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
        # EEG rest markers bracket sub-block and fatigue rests so
        # alpha-trend analysis can separate task time from rest time.
        send = getattr(self.engine, "_eeg_send", None)
        if callable(send):
            send(EEG_CODES["rest_start"], t_event=now)
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
        send = getattr(self.engine, "_eeg_send", None)
        if callable(send):
            send(EEG_CODES["rest_end"], t_event=now)
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
            # A probe where the WRONG finger pressed is a response
            # error (cue misread), not enslaving: its full press on a
            # non-instructed finger wrote a ~100% cell into the
            # matrix, so a start matrix inflated by early cue errors
            # made start-to-end improvement overstate individuation
            # gains. The notebook's crosstalk section already excludes
            # wrong-press trials for exactly this reason; the mode's
            # own matrix follows the same rule.
            if r.get("wrong"):
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
        cross-talk aggregates, the start and end probe matrices (per
        hand: enslaving_matrices carries every playing hand, and the
        legacy single-hand keys stay for unilateral blocks so older
        analyses keep reading), the fatigue trajectory and the
        per-trial detail the fixed CSV schema cannot carry."""
        # device_drop records are hardware evidence, not performance:
        # they stay out of every performance aggregate below and are
        # surfaced separately (outcome_classes and n_device_drops).
        scored = [r for r in self._records
                  if r.get("class") != "device_drop"]
        all_chords = [r for r in scored if r["kind"] == "chord"]
        # Scope is a first-class label: every aggregate below consumes
        # exactly one scope. `chords` (within-hand) keeps its old name
        # so the summary keys older analyses read stay unchanged.
        chords = [r for r in all_chords
                  if r.get("scope", "within") == "within"]
        cross = [r for r in all_chords if r.get("scope") == "cross"]
        probes = [r for r in scored if r["kind"] == "probe"]
        # Probes before the first chord are the start set; the rest are
        # the end set. Demo blocks have no end set.
        first_chord = all_chords[0]["trial"] if all_chords else None
        probes_start = [r for r in probes
                        if first_chord is None or r["trial"] < first_chord]
        probes_end = [r for r in probes
                      if first_chord is not None
                      and r["trial"] > first_chord]

        # Per-chord table, split by hand AND by synchrony window: the
        # level ladder interleaves tier and window (level = window*4 +
        # tier), so an easy chord is met at wide windows and a hard one
        # first met at the tightest, and pooling their hit rates lets a
        # window artefact masquerade as the enslaving pattern the
        # difficulty rank test is meant to read off (see docstring
        # CROSS-TALK SCORE and the DIFFICULTY ORDER section above).
        per_chord: dict[tuple[str, str, float], dict] = {}
        for r in chords:
            d = per_chord.setdefault((r["hand"], r["chord"], r["w_ms"]), {
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
            "hand": hand,
            "chord": name,
            "w_ms": w_ms,
            "d": v["d"],
            "n": v["n"],
            "hit_rate": round(v["hits"] / v["n"], 3) if v["n"] else None,
            "median_span_ms": _median(v["spans"]),
            "median_er": _median(v["ers"]),
        } for (hand, name, w_ms), v in sorted(per_chord.items(),
                                              key=lambda kv: (kv[0][0],
                                                              kv[1]["d"],
                                                              kv[0][2]))]

        def _class_counts(rows: list[dict]) -> dict[str, int]:
            counts: dict[str, int] = {}
            for r in rows:
                counts[r["class"]] = counts.get(r["class"], 0) + 1
            return counts

        classes = _class_counts(self._records)

        matrices = {
            h: {
                "start": self._probe_matrix(
                    [r for r in probes_start if r["hand"] == h]),
                "end": self._probe_matrix(
                    [r for r in probes_end if r["hand"] == h]),
            }
            for h in self.hand_names
        }
        per_hand = {
            h: {
                "n_chords": sum(1 for r in chords if r["hand"] == h),
                "median_er": _median([r["er"] for r in chords
                                      if r["hand"] == h
                                      and r["er"] is not None]),
                "median_span_ms": _median([r["span_ms"] for r in chords
                                           if r["hand"] == h
                                           and r["span_ms"] is not None]),
                # Silent mirror force on the OTHER hand while this
                # hand's within-hand chords ran (bilateral only).
                "median_mirror_leak": _median(
                    [r["mirror_leak"] for r in chords
                     if r["hand"] == h
                     and r.get("mirror_leak") is not None]),
            }
            for h in self.hand_names
        }

        # Cross-hand aggregates: the per-pair table (scope-pure, so it
        # cannot pollute the within-hand per_chord consumers), and the
        # summary contrasts the bimanual analysis reads: mirror vs
        # non-mirror, lead-lag, and the bilateral deficit ratio from
        # mirror singles against the same finger's unimanual probes.
        per_cross: dict[tuple[str, float], dict] = {}
        for r in cross:
            d = per_cross.setdefault((r["chord"], r["w_ms"]), {
                "d": r["d"], "mirror": bool(r.get("mirror")),
                "asym": r.get("asym"), "n": 0, "hits": 0,
                "spans": [], "lags": []})
            d["n"] += 1
            d["hits"] += 1 if r["class"] == "hit" else 0
            if r["span_ms"] is not None:
                d["spans"].append(r["span_ms"])
            if r.get("lag_ms") is not None:
                d["lags"].append(r["lag_ms"])
        cross_table = [{
            "chord": name,
            "w_ms": w_ms,
            "d": v["d"],
            "mirror": v["mirror"],
            "asym": v["asym"],
            "n": v["n"],
            "hit_rate": round(v["hits"] / v["n"], 3) if v["n"] else None,
            "median_span_ms": _median(v["spans"]),
            "median_lag_ms": _median(v["lags"]),
        } for (name, w_ms), v in sorted(per_cross.items(),
                                        key=lambda kv: (kv[1]["d"],
                                                        kv[0][1]))]

        def _rate(rows: list[dict]) -> float | None:
            if not rows:
                return None
            return round(sum(1 for r in rows
                             if r["class"] == "hit") / len(rows), 3)

        mirror_rows = [r for r in cross if r.get("mirror")]
        nonmirror_rows = [r for r in cross if not r.get("mirror")]
        lead_counts = {h: sum(1 for r in cross
                              if r.get("lead_hand") == h)
                       for h in self.hand_names}
        lag_by_lead = {h: _median([r["lag_ms"] for r in cross
                                   if r.get("lead_hand") == h
                                   and r.get("lag_ms") is not None])
                       for h in self.hand_names}
        # Bilateral deficit per hand and finger (Li 2000/2001): the
        # finger's press in mirror singles over the same finger's
        # unimanual probe press, both normalised the same way. Only
        # mirror singles qualify: one finger per hand, so the per-hand
        # press IS that finger's press.
        deficit: dict[str, dict[str, float]] = {}
        for h, key in (("left", "press_left"), ("right", "press_right")):
            if h not in self.hand_names:
                continue
            for f in range(4):
                letter = FINGER_LETTERS[f]
                mirror_presses = [
                    r[key] for r in mirror_rows
                    if r.get("chord_left") == letter
                    and r.get("chord_right") == letter
                    and r.get(key) is not None]
                probe_presses = [
                    r["press_norm"] for r in probes
                    if r["hand"] == h and r["chord"] == letter
                    and r.get("press_norm")]
                m_bi = _median(mirror_presses)
                m_uni = _median(probe_presses)
                if m_bi is not None and m_uni:
                    deficit.setdefault(h, {})[letter] = round(
                        m_bi / m_uni, 3)

        out = {
            "hand": self.hand_label,
            "hands": self.hand_names,
            "demo": self.demo_trials is not None,
            "windows_ms": self.windows_ms,
            "level_final": self.level,
            "level_highest": self.highest_level,
            "w_final_ms": self.current_w_ms,
            "tier_final": self.current_tier + 1,
            # n_chords stays the WITHIN-hand count, matching every
            # other aggregate at this level (median_er, per_chord);
            # the cross section carries its own counts.
            "n_chords": len(chords),
            "n_probes": len(probes),
            "outcome_classes": classes,
            # Scope-pure class counts for the results card: the
            # near-guaranteed single-finger probes and the cross-scope
            # chords (their own ladder) diluted a CLEAN HIT RATE
            # computed over every record, so the patient's headline
            # number moved with the session's probe:chord mix rather
            # than with skill.
            "chord_outcome_classes": _class_counts(chords),
            "cross_outcome_classes": _class_counts(cross),
            "n_device_drops": sum(1 for r in self._records
                                  if r.get("class") == "device_drop"),
            # Which normaliser each hand's forces ran under: a fresh
            # or saved calibration profile (its creation stamp and
            # participant), or the config fallback. Every force
            # quantity in this mode (ER, leak bands, probe matrices)
            # divides by it, so the C5 across-session ER curve needs
            # to be able to exclude or flag a mis-referenced session
            # instead of guessing from the metadata calibration stamp.
            "reference_basis": self._reference_basis(),
            "median_er": _median([r["er"] for r in chords
                                  if r["er"] is not None]),
            "median_span_ms": _median([r["span_ms"] for r in chords
                                       if r["span_ms"] is not None]),
            "median_settle_ms": _median([r["settle_ms"]
                                         for r in self._records
                                         if r["settle_ms"] is not None]),
            "over_force_trials": sum(1 for r in self._records
                                     if r["over_force"]),
            "light_press_trials": sum(1 for r in all_chords
                                      if r["light"]),
            "warmup_capped": self._warmup_capped,
            "scope_sequence": self._scope_seq,
            "per_chord": chord_table,
            "per_chord_cross": cross_table,
            "per_hand": per_hand,
            "cross": {
                "n_chords": len(cross),
                "level_final": self.level_cross,
                "level_highest": self.highest_level_cross,
                "w_final_ms": self.current_w_cross_ms,
                "tier_final": self.current_tier_cross + 1,
                "hit_rate_mirror": _rate(mirror_rows),
                "hit_rate_nonmirror": _rate(nonmirror_rows),
                "median_span_mirror_ms": _median(
                    [r["span_ms"] for r in mirror_rows
                     if r["span_ms"] is not None]),
                "median_span_nonmirror_ms": _median(
                    [r["span_ms"] for r in nonmirror_rows
                     if r["span_ms"] is not None]),
                "median_lag_ms": _median(
                    [r["lag_ms"] for r in cross
                     if r.get("lag_ms") is not None]),
                "lead_hand_counts": lead_counts,
                "median_lag_by_lead_ms": lag_by_lead,
                "median_er_left": _median(
                    [r["er_left"] for r in cross
                     if r.get("er_left") is not None]),
                "median_er_right": _median(
                    [r["er_right"] for r in cross
                     if r.get("er_right") is not None]),
                "bilateral_deficit": deficit,
            },
            "subblocks": self._sub_stats,
            "fatigue_triggers": self._fatigue_triggers,
            "end_reason": self.end_reason,
            "enslaving_matrices": matrices,
            "trials": self._records,
        }
        if not self.bilateral:
            # The shapes older sessions wrote, so anything reading the
            # single-hand keys keeps working unchanged.
            only = matrices[self.hand_names[0]]
            out["enslaving_matrix_start"] = only["start"]
            out["enslaving_matrix_end"] = only["end"]
        return out
