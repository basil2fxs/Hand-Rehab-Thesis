"""Lighthouse mode: precision hold with feedback fade, plus blind
force reproduction. One finger holds a low force to keep a lantern
lit; at higher levels the room goes dark mid-hold and the hold
continues by feel alone, and echo trials ask the finger to reproduce
a remembered force after a delay.

WHY THIS DESIGN. The core mechanic is a published clinical contrast
turned into a game: how much worse does a low-force hold get when the
visual feedback disappears?

- Li K, Evans PJ, Seitz WH Jr, Li ZM (2015). Carpal tunnel syndrome
  impairs sustained precision pinch performance. Clinical
  Neurophysiology 126(1):194-201. With visual feedback, CTS patients
  held a target force as well as controls; with the feedback removed,
  their error and variability rose sharply (p < 0.001) while controls
  barely moved. Feedback masks the deficit; feedback withdrawal
  exposes it. The lit-versus-dark error delta of this mode is exactly
  that contrast, run per finger, per session.
- Camacho-Villa MA, et al (2025). Relationship Between Force
  Steadiness and Functionality in Older Adults: A Systematic Review
  With Meta-Analysis. Scandinavian Journal of Medicine and Science in
  Sports 35(4):e70040. Pooled upper-limb force steadiness correlated
  with everyday function at r = 0.58, with the included tasks holding
  5 to 25 percent of MVC. That is why this mode's targets live in the
  5 to 25 percent band and why lit steadiness (CoV) is reported as an
  outcome in its own right, not just as a game score.

Supporting, verified by the research cluster: a 2024 Journal of Hand
Therapy home program improved pinch force perception in older adults
(about a third off the reproduction error in six weeks), so force
sense is trainable at home; pinch force-sense reproduction shows
test-retest ICCs around 0.6 to 0.9, so the echo numbers are stable
enough to track; Lima 2017 (Neuroscience Letters 659:54-59) found
grip force control impaired with strength preserved in diabetic
peripheral neuropathy, the same dissociation this mode measures; and
Peters 2016 (Cochrane CD004158) found the rehabilitation evidence
after carpal tunnel release thin across the board, which makes a
cheap objective tracker of force control a defensible contribution
on its own.

PARAMETER DEFENCES, in config order:
- targets drawn from 5 to 25 percent of the session max press: the
  Camacho-Villa band, and low enough that a 15 to 20 s hold repeats
  across fingers without strength fatigue dominating the trace.
- holds of 15 to 20 s: long enough for a steadiness estimate and at
  least one dark window with lit time around it, short enough to
  repeat per finger (the ranked brief's window).
- feedback fade by level: level 1 is fully lit, then the dark share
  of each hold grows per level. Every hold keeps a lit lead-in (a
  steady baseline must exist before the first darkness), lit gaps
  between dark windows and a lit tail (the relight that reveals the
  drift). No published staircase exists for feedback fade, so the
  ladder is a design choice and says so; every move is announced on
  screen in plain words and logged.
- the ladder moves on the lit-dark error delta, the Li 2015
  discriminator, not on the game score. Level 1 has no dark data, so
  it promotes on lit accuracy alone.
- echo trials: match a shown force for 3 s, wait 2 to 15 s, then
  reproduce it with no feedback. Active reproduction after a delay
  is the standard force-sense paradigm, and the delay length is the
  memory load; constant and variable error split by delay is the
  standard analysis. With both hands connected the echo goes
  cross-hand (one hand studies the force, the other reproduces it),
  which is the between-hands matching variant of the same paradigm.
- tolerance +/- 3 percent of max for the in-band tiers and the
  ignite band: a design constant, wide enough that entry is not the
  hard part of the trial, narrow enough that the band means steady.

FLOW. Session max press probes run first where needed (the shared
foundation flow), because every target here is a percentage of that
probed max, never raw counts. Then trials: hold trials and echo
trials interleaved on a shuffled bag. A hold trial ignites (bring
the flame into the band and keep it there briefly), then holds for
the planned duration while the lantern's flame answers the force:
size tracks the signed error, flicker tracks the fluctuation, both
smoothed well under the 3 Hz limit. At the planned moments the room
darkens and the flame burns unseen; at each relight the drift that
accumulated in the dark is revealed on screen and scored. One hand
selected means its four fingers rotate; both hands means all eight
fingers, held to equal counts by the paired scheduler. Failure is
gentle by design: a hold that never ignites just gutters and moves
on. There is no keyboard fallback: a keyboard cannot produce a
held force, and the mode says so on screen instead of pretending.

CUES AND CHANNELS. This mode never buzzes during a trial: no
on_stim, no pulse_motor, no error buzz, no success tick mid-hold. A
buzz inside a hold would hand the patient a tactile reference at
exactly the moment the design removes the visual one, and the dark
windows are the measurement. The only motor event is the engine's
standard after-press confirmation at trial close, which every mode
shares and which rides the cue.buzz_after switch; it fires after
the scored windows are over, and a block that wants strict tactile
silence turns that switch off, with cue_flags recording either way.
Failure is silent on the motors in all cases (log_trial only cues
non-Miss outcomes), which is also the child-safe register: the
flame gutters, nothing blares. The lantern always names the working
finger on screen (a hold task must say which finger holds), so
every trial row records cue_target_shown TRUE.

LOGGING. One trial row per hold or echo. waveform is "hold" or
"reproduce". waveform_seed plus the lighthouse config rebuild the
trial plan bit-exactly through draw_hold_params / draw_echo_params,
and waveform_params carries every drawn number (target, dark window
onsets and length, delay, the finger's max_press_counts) so the
notebook rebuilds the plan from the row alone via
hold_segments_from_params without importing this module.
segment_times brackets ignite and every lit / dark window (or
enter / study / delay / reproduce) in raw-stream t_perf seconds,
with matching segment_start / segment_end events inside raw.csv.
The in-game numbers are feedback; the analysis notebook re-scores
offline from the 200 Hz raw samples between the logged bounds:
CoV and RMSE per lit and dark window, post-fade drift rate and
direction, the lit-dark delta as headline, and constant plus
variable reproduction error by delay.

WHAT THIS MODE CANNOT CLAIM. The CTS literature behind the core
contrast is thumb-finger precision pinch; this rig measures the
normal force of a flat finger pressing a pad. Same sensorimotor
loop, different grip geometry, and the thesis must say so plainly
rather than borrowing the pinch numbers. Sensory relearning after
carpal tunnel release failed its definitive RCT (Jerosch-Herold
2016), so for CTS this mode is measurement and motor-control
practice, never a claimed treatment. SingleTact accuracy and drift
at very low force is uncharacterised on this rig; the bench
characterisation must precede patient data. And the frame-rate
scores are gameplay only; every research number comes from the
notebook's offline scoring of the raw stream.
"""
from __future__ import annotations

import logging
import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...data.logger import ContinuousTrialLog
from ..force_stream import ForceView, MaxPressProbe, needs_max_press_probe
from ..scheduling import BalancedScheduler, PairedBalancedScheduler
from ..scoring import ScoreConfig, TrialResult
from .classic import PendingTrial
from .force_pilot import FINGER_WORDS

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


# A dark window shorter than this cannot show a drift worth scoring
# (the finger barely has time to move), so the planner drops windows
# rather than shrinking them below it.
MIN_DARK_S = 1.5


# ---- pure trial planning ---------------------------------------------------
# The logging contract's rule: the exact plan the patient played must
# be rebuildable offline from (waveform, params, seed) alone.
#   draw_hold_params / draw_echo_params  draw every random number ONCE
#       and return the flat dict logged as waveform_params.
#   hold_segments_from_params            deterministic lit / dark
#       windows from that dict; the notebook carries a copy.
#   feedback_lit                         whether the lantern shows
#       feedback at hold time t, straight from the same dict.
# The mode plays from these functions and logs the same dict.


def draw_hold_params(seed: int, level: int, target_lo_pct: float,
                     target_hi_pct: float, hold_s: float, n_dark: int,
                     dark_frac: float, lit_lead_s: float, lit_gap_s: float,
                     lit_tail_s: float, tol_pct: float,
                     max_press_counts: float) -> dict:
    """Draw one hold trial's plan and return the loggable params dict.

    Pure: the same seed and knobs always return the same dict. The
    dark share of the hold is split into equal windows placed with a
    guaranteed lit lead, lit gaps and a lit tail; leftover lit time is
    spread between them from the seed so the darkness cannot be
    anticipated by the clock. Windows that will not fit (short demo
    holds) are dropped rather than shrunk below MIN_DARK_S.
    """
    rng = random.Random(int(seed))
    lo = min(float(target_lo_pct), float(target_hi_pct))
    hi = max(float(target_lo_pct), float(target_hi_pct))
    target = rng.uniform(lo, hi)
    hold_s = max(1.0, float(hold_s))
    n = max(0, int(n_dark))
    dark_total = max(0.0, min(0.9, float(dark_frac))) * hold_s
    dark_len = (dark_total / n) if n else 0.0
    while n > 0:
        fixed = (float(lit_lead_s) + float(lit_tail_s)
                 + (n - 1) * float(lit_gap_s))
        room = hold_s - fixed
        if room >= n * MIN_DARK_S:
            dark_len = max(MIN_DARK_S, min(dark_len, room / n))
            break
        n -= 1
        dark_len = (dark_total / n) if n else 0.0
    p = {
        "lvl": int(level),
        "target_pct": target,
        "hold_s": hold_s,
        "tol_pct": float(tol_pct),
        "n_dark": n,
        "dark_s": dark_len if n else 0.0,
        "max_press_counts": float(max_press_counts),
    }
    if n:
        fixed = (float(lit_lead_s) + float(lit_tail_s)
                 + (n - 1) * float(lit_gap_s))
        slack = max(0.0, hold_s - fixed - n * dark_len)
        weights = [rng.random() for _ in range(n + 1)]
        wsum = sum(weights) or 1.0
        extras = [slack * w / wsum for w in weights]
        base_lit = ([float(lit_lead_s)]
                    + [float(lit_gap_s)] * (n - 1))
        t = 0.0
        for i in range(n):
            t += base_lit[i] + extras[i]
            p[f"d{i + 1}_on_s"] = t
            t += dark_len
    return p


def hold_segments_from_params(p: dict) -> list[tuple[str, float, float]]:
    """The lit / dark windows of one hold, relative to the hold start.
    Deterministic from the params dict alone, so the notebook can cut
    the raw trace from the logged cell without this module's rng."""
    hold_s = float(p["hold_s"])
    n = int(round(float(p.get("n_dark", 0))))
    dark = float(p.get("dark_s", 0.0))
    ons = sorted(float(p[f"d{i + 1}_on_s"]) for i in range(n))
    out: list[tuple[str, float, float]] = []
    t = 0.0
    for i, on in enumerate(ons):
        out.append((f"lit{i + 1}", t, on))
        out.append((f"dark{i + 1}", on, on + dark))
        t = on + dark
    out.append((f"lit{n + 1}", t, hold_s))
    # A zero-length lit stretch (dark window flush against the end)
    # would log a degenerate segment; drop it rather than write it.
    return [(name, a, b) for name, a, b in out if b - a > 1e-9]


def feedback_lit(p: dict, t: float) -> bool:
    """Whether the lantern shows feedback at hold time t. True outside
    every dark window; pure, so the fade schedule is testable."""
    n = int(round(float(p.get("n_dark", 0))))
    dark = float(p.get("dark_s", 0.0))
    for i in range(n):
        on = float(p[f"d{i + 1}_on_s"])
        if on <= t < on + dark:
            return False
    return True


def draw_echo_params(seed: int, target_lo_pct: float, target_hi_pct: float,
                     show_s: float, delay_s: float, reproduce_s: float,
                     settle_s: float, tol_pct: float, cross: bool,
                     set_lane: int, max_press_counts: float) -> dict:
    """Draw one echo trial's plan. Only the target is random; the
    delay is picked by the mode's balanced delay bag and passed in so
    every delay length gets equal trials."""
    rng = random.Random(int(seed))
    lo = min(float(target_lo_pct), float(target_hi_pct))
    hi = max(float(target_lo_pct), float(target_hi_pct))
    return {
        "target_pct": rng.uniform(lo, hi),
        "show_s": float(show_s),
        "delay_s": float(delay_s),
        "reproduce_s": float(reproduce_s),
        "settle_s": float(settle_s),
        "tol_pct": float(tol_pct),
        "cross": 1 if cross else 0,
        "set_lane": int(set_lane),
        "max_press_counts": float(max_press_counts),
    }


# ---- per-trial bookkeeping -------------------------------------------------


@dataclass
class HoldRecord:
    """What one finished hold contributes to block_stats."""

    hand: str
    finger: int
    lane: int
    level: int
    target_pct: float
    guttered: bool
    tib_frac: float
    lit_mae_pct: float | None
    lit_cov: float | None
    dark_mae_pct: float | None
    delta_pct: float | None
    drifts_pct: list = field(default_factory=list)
    drift_rate_pct_s: float | None = None


@dataclass
class EchoRecord:
    """What one finished echo trial contributes to block_stats."""

    hand: str
    finger: int
    lane: int
    set_lane: int
    cross: bool
    delay_s: float
    target_pct: float
    guttered: bool
    signed_err_pct: float | None
    abs_err_pct: float | None


class LighthouseMode:
    name = "Lighthouse"

    # A force reading older than this is a source dropout: scoring
    # pauses rather than judging a flat line the patient is not
    # producing (a few frames at 60 Hz).
    SAMPLE_STALE_S = 0.25
    # Outcome tiers on time-in-band across the scored hold. Design
    # constants, not published thresholds; the notebook re-scores
    # offline anyway.
    GREAT_TIB = 0.8
    GOOD_TIB = 0.5
    # A reproduce press below this percent of max has not started yet;
    # above it the reproduce clock runs. Kept small so a weak blind
    # press still counts as an attempt.
    ENTRY_FLOOR_PCT = 2.0
    # The standard force-sense paradigm needs a real release between
    # encode and reproduce; this is how long the reproduce lane must
    # sit below ENTRY_FLOOR_PCT during the delay before the trial
    # counts as released. Short: a genuine let-go reads as a plain
    # dip, not a held pause.
    RELEASE_QUIET_S = 0.3
    # How long the post-dark drift reveal stays on screen. Steady text,
    # no flashing.
    REVEAL_S = 2.5
    # Display smoothing time constants (seconds). Flame size follows
    # the error at ~4 Hz bandwidth-equivalent smoothing and the
    # flicker follows the fluctuation more slowly, so nothing the
    # screen draws from these can approach the 3 Hz flash limit.
    ERR_TAU_S = 0.25
    FLICKER_TAU_S = 0.6

    def __init__(self, engine: "GameEngine",
                 lanes_by_hand: dict[str, list[int]],
                 level: int,
                 dark_windows_by_level: list[int],
                 dark_frac_by_level: list[float],
                 holds_per_finger: int,
                 echoes_per_finger: int,
                 target_lo_pct: float,
                 target_hi_pct: float,
                 hold_s: float,
                 tol_pct: float,
                 lit_lead_s: float,
                 lit_gap_s: float,
                 lit_tail_s: float,
                 ignite_hold_s: float,
                 ignite_timeout_s: float,
                 echo_show_s: float,
                 echo_delays_s: list[float],
                 echo_reproduce_s: float,
                 echo_settle_s: float,
                 promote_lit_mae_pct: float,
                 promote_delta_pct: float,
                 demote_delta_pct: float,
                 dark_bonus_points: int,
                 probe_presses: int,
                 probe_floor_counts: float,
                 probe_max_age_s: float,
                 announce_s: float,
                 rest_s: float,
                 score_cfg: ScoreConfig,
                 seed: int = 0,
                 demo_trials: int | None = None) -> None:
        self.engine = engine
        self.hands = {h: list(v)[:4] for h, v in lanes_by_hand.items() if v}
        if not self.hands:
            self.hands = {"right": [0, 1, 2, 3]}
        self.hand_names = list(self.hands)
        self.bilateral = len(self.hand_names) > 1
        self.dark_windows_by_level = [int(x) for x in dark_windows_by_level]
        self.dark_frac_by_level = [float(x) for x in dark_frac_by_level]
        self.max_level = min(len(self.dark_windows_by_level),
                             len(self.dark_frac_by_level))
        self.level = max(1, min(int(level), self.max_level))
        self.level_start = self.level
        self.target_lo_pct = float(target_lo_pct)
        self.target_hi_pct = float(target_hi_pct)
        self.hold_s = float(hold_s)
        self.tol_pct = float(tol_pct)
        self.lit_lead_s = float(lit_lead_s)
        self.lit_gap_s = float(lit_gap_s)
        self.lit_tail_s = float(lit_tail_s)
        self.ignite_hold_s = max(0.1, float(ignite_hold_s))
        self.ignite_timeout_s = max(2.0, float(ignite_timeout_s))
        self.echo_show_s = float(echo_show_s)
        self.echo_delays_s = [float(d) for d in echo_delays_s] or [2.0]
        self.echo_reproduce_s = float(echo_reproduce_s)
        self.echo_settle_s = min(float(echo_settle_s),
                                 float(echo_reproduce_s))
        self.promote_lit_mae_pct = float(promote_lit_mae_pct)
        self.promote_delta_pct = float(promote_delta_pct)
        self.demote_delta_pct = float(demote_delta_pct)
        self.dark_bonus_points = int(dark_bonus_points)
        self.probe_presses = max(2, int(probe_presses))
        self.probe_floor_counts = float(probe_floor_counts)
        self.probe_max_age_s = float(probe_max_age_s)
        self.announce_s = max(0.5, float(announce_s))
        self.rest_s = max(1.0, float(rest_s))
        self.score_cfg = score_cfg
        self.rng = random.Random(int(seed))
        self.demo = demo_trials is not None

        n_fingers = 4 * len(self.hand_names)
        n_holds = max(1, int(holds_per_finger)) * n_fingers
        n_echo = max(0, int(echoes_per_finger)) * n_fingers
        if self.demo:
            # Test Mode: a couple of short trials so a supervisor demo
            # reaches Results inside a minute or two. The trial SHAPE
            # stays intact (a hold still darkens if the level says so,
            # an echo still waits its delay) so the demo shows the
            # real thing, just compressed.
            cap = max(1, int(demo_trials))
            self.hold_s = min(self.hold_s, 6.0)
            self.lit_lead_s = min(self.lit_lead_s, 1.5)
            self.lit_gap_s = min(self.lit_gap_s, 1.0)
            self.lit_tail_s = min(self.lit_tail_s, 1.0)
            self.echo_show_s = min(self.echo_show_s, 2.0)
            self.echo_delays_s = [min(d, 3.0) for d in self.echo_delays_s]
            self.echo_reproduce_s = min(self.echo_reproduce_s, 3.0)
            self.echo_settle_s = min(self.echo_settle_s,
                                     self.echo_reproduce_s)
            self.ignite_timeout_s = min(self.ignite_timeout_s, 6.0)
            self.announce_s = min(self.announce_s, 1.5)
            self.rest_s = min(self.rest_s, 2.0)
            self.probe_presses = 2
            n_holds = min(n_holds, max(1, cap - (1 if n_echo else 0)))
            n_echo = min(n_echo, max(0, cap - n_holds))
        # A hold_s too short to fit even one MIN_DARK_S window leaves
        # draw_hold_params silently dropping all darkness at any level
        # with dark_frac > 0 (audit finding #87): the top strip and
        # the announce line now read the drawn params rather than this
        # config, so they cannot lie about it, but the level ladder
        # above 1 still can't move without any dark data. Warn once so
        # a misconfigured hold_s (defaults are unaffected) is visible
        # in the log rather than only showing up as a stuck ladder.
        for lvl in range(1, self.max_level + 1):
            n = self.dark_windows_by_level[lvl - 1]
            frac = self.dark_frac_by_level[lvl - 1]
            if n <= 0 or frac <= 0.0:
                continue
            fixed = (self.lit_lead_s + self.lit_tail_s
                     + (n - 1) * self.lit_gap_s)
            if self.hold_s - fixed < n * MIN_DARK_S:
                log.warning(
                    "lighthouse: hold_s=%.1f cannot fit %d dark "
                    "window(s) of at least %.1fs at level %d "
                    "(lit_lead_s=%.1f, lit_gap_s=%.1f, lit_tail_s="
                    "%.1f); the planner will drop darkness there and "
                    "the level cannot promote past it on dark data",
                    self.hold_s, n, MIN_DARK_S, lvl, self.lit_lead_s,
                    self.lit_gap_s, self.lit_tail_s)
        # Interleave the two trial kinds on a shuffled bag so a block
        # is not all holds then all echoes; the per-kind schedulers
        # below keep each kind balanced across fingers regardless of
        # the interleave order.
        self._kind_bag = ["hold"] * n_holds + ["echo"] * n_echo
        self.rng.shuffle(self._kind_bag)
        self.total_trials = len(self._kind_bag)

        self.view = ForceView(engine)
        # Paired balancing, per the brief: hold counts stay equal per
        # finger AND per hand; echo match-lanes balance the same way.
        # There is no weakness weighting here on purpose: the lit-dark
        # delta comparison needs equal data per finger.
        if self.bilateral:
            self._hold_sched = PairedBalancedScheduler(self.hands, self.rng)
            self._echo_sched = PairedBalancedScheduler(self.hands, self.rng)
        else:
            only = self.hands[self.hand_names[0]]
            self._hold_sched = BalancedScheduler(only, self.rng)
            self._echo_sched = BalancedScheduler(only, self.rng)
        self._delay_bag = BalancedScheduler(
            list(range(len(self.echo_delays_s))), self.rng,
            avoid_repeats=False)

        # Probe queue: every finger of every playing hand whose stored
        # session max is missing or stale (the shared foundation flow).
        self._probe_queue: list[tuple[str, int]] = []
        self._probe_maxes: dict[str, list[float]] = {}
        profiles = getattr(engine, "calibration_profiles", None) or {}
        for hand in self.hand_names:
            if needs_max_press_probe(profiles.get(hand),
                                     max_age_s=self.probe_max_age_s):
                self._probe_maxes[hand] = [0.0] * 4
                self._probe_queue.extend((hand, f) for f in range(4))

        # Phase machine:
        #   no_input -> (parked; the source cannot feed this mode)
        #   probe_gap -> probe (per finger) ... -> announce -> trial ->
        #   feedback -> announce ... -> done
        self.phase = "init"
        self.end_reason: str | None = None
        self._t0: float | None = None
        self._last_tick: float | None = None
        self._phase_until: float | None = None

        # Probe state.
        self.probe: MaxPressProbe | None = None
        self.probe_hand: str = self.hand_names[0]
        self.probe_finger: int = 0
        self.probe_counts: float = 0.0
        self.signal_waiting = False

        # Trial state (populated by _prepare_trial).
        self.trial_counter = 0
        self.trials_done = 0
        self.kind: str = "hold"
        self.sub: str = "ignite"
        self.hand: str = self.hand_names[0]
        self.finger: int = 0
        self.lane: int = self.hands[self.hand][0]
        self.set_hand: str = self.hand
        self.set_finger: int = 0
        self.set_lane: int = self.lane
        self.cross: bool = False
        self.trial_seed: int = 0
        self.params: dict = {}
        self.hold_windows: list[tuple[str, float, float]] = []
        self.delay_s: float = self.echo_delays_s[0]
        self.active: PendingTrial | None = None
        self.trial_t0: float | None = None
        self.hold_t0: float | None = None
        self.level_msg: str = ""
        self._last_result: dict | None = None
        self._level_trace: list[int] = [self.level]
        self._recent_lit_mae: list[float] = []
        self._recent_delta: list[float] = []
        self._holds: list[HoldRecord] = []
        self._echoes: list[EchoRecord] = []

        # Live readouts the screen draws from.
        self.target_pct: float = 0.0
        self.force_pct_now: float | None = None
        self.in_band_now = False
        self.lit_now = True
        self.flame_frac = 0.5        # 0.5 = on target
        self.flicker_frac = 0.0
        self.pressing_now = False
        self.delay_left_s = 0.0
        self.reveal_msg = ""
        self.signal_stale = False

        # Per-trial scoring scratch.
        self._ignite_acc_s = 0.0
        self._win_idx = 0
        self._win_acc: dict[str, list[float]] = {}
        self._dark_entry_pct: dict[str, float] = {}
        self._dark_exit_pct: dict[str, float] = {}
        self._last_pct: float | None = None
        self._err_smooth = 0.0
        self._flut_smooth = 0.0
        self._study_t0: float | None = None
        self._delay_t0: float | None = None
        self._repro_prompt_t: float | None = None
        self._press_t0: float | None = None
        self._released = False
        self._release_quiet_s = 0.0
        self._repro_samples: deque[tuple[float, float]] = deque(maxlen=2048)
        self._reveal_until: float | None = None

    # ---- plumbing shared with the other modes ------------------------------
    def queue_press(self, ev) -> None:
        # Presses are not this mode's input; the continuous force is.
        # Swallowing them keeps the engine's shared press path happy.
        return

    def handle_event(self, e) -> None:
        # No keyboard fallback by design: a keyboard cannot produce a
        # held force (see the docstring's claim limits).
        return

    def on_resume(self, pause_dur: float) -> None:
        for attr in ("_t0", "_phase_until", "_last_tick"):
            v = getattr(self, attr)
            if v is not None:
                setattr(self, attr, v + pause_dur)
        if self.phase == "trial":
            # A pause mid-trial breaks the trace being scored: the
            # lantern froze while the hand did whatever it did.
            # Restart the same trial (same seed, same plan); nothing
            # was logged for it yet, and the orphaned segment markers
            # are tied off by a trial_restart event so the notebook
            # can discard them.
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "trial_restart", lane=self.lane,
                    detail=f"trial_id={self.trial_counter}",
                    hand=self.engine.hand_mode)
            self._enter_announce(time.perf_counter())

    # ---- main tick ---------------------------------------------------------
    def update(self, dt: float) -> None:
        self._tick(time.perf_counter())

    def _tick(self, now: float) -> None:
        if self._t0 is None:
            self._t0 = now
            self._last_tick = now
            self._start(now)
        dt = min(0.1, max(0.0, now - (self._last_tick or now)))
        self._last_tick = now
        if self._reveal_until is not None and now >= self._reveal_until:
            self.reveal_msg = ""
            self._reveal_until = None
        if self.phase in ("done", "no_input"):
            return
        if self.phase == "probe_gap":
            if self._phase_until is not None and now >= self._phase_until:
                self._enter_probe(now)
        elif self.phase == "probe":
            self._probe_frame(now)
        elif self.phase == "announce":
            if self._phase_until is not None and now >= self._phase_until:
                self._start_trial(now)
        elif self.phase == "trial":
            if self.kind == "hold":
                self._hold_frame(now, dt)
            else:
                self._echo_frame(now, dt)
        elif self.phase == "feedback":
            if self._phase_until is not None and now >= self._phase_until:
                self._enter_announce(now)

    def _start(self, now: float) -> None:
        source = getattr(self.engine, "source", None)
        if source is not None and not getattr(source, "provides_samples",
                                              True):
            # The screen tells the researcher plainly; Esc leaves.
            self.phase = "no_input"
            return
        if self._probe_queue:
            self._enter_probe_gap(now)
        else:
            self._prepare_trial()
            self._enter_announce(now)

    # ---- max-press probes --------------------------------------------------
    def _enter_probe_gap(self, now: float) -> None:
        self.phase = "probe_gap"
        self.probe_hand, self.probe_finger = self._probe_queue[0]
        self._phase_until = now + 1.2
        # The hand is resting between probes: re-tare so the probe
        # measures counts above the actual resting level.
        self.view.rebaseline([self.hands[self.probe_hand]
                              [self.probe_finger]])

    def _enter_probe(self, now: float) -> None:
        self.phase = "probe"
        self._phase_until = None
        self.probe = MaxPressProbe(n_presses=self.probe_presses,
                                   floor_counts=self.probe_floor_counts)
        self.probe_counts = 0.0

    def _probe_frame(self, now: float) -> None:
        lane = self.hands[self.probe_hand][self.probe_finger]
        reading = self.view.read(lane)
        self.signal_waiting = reading is None
        if reading is None or self.probe is None:
            return
        self.probe_counts = reading.counts
        self.probe.update(now, reading.counts)
        if self.probe.state != "done":
            return
        result = self.probe.result() or 0.0
        self._probe_maxes[self.probe_hand][self.probe_finger] = result
        self._probe_queue.pop(0)
        done_hand = all(h != self.probe_hand
                        for h, _f in self._probe_queue)
        if done_hand:
            self.engine.record_max_press(
                self.probe_hand, list(self._probe_maxes[self.probe_hand]))
        if self._probe_queue:
            self._enter_probe_gap(now)
        else:
            self._prepare_trial()
            self._enter_announce(now)

    # ---- trial selection and setup -----------------------------------------
    def _lane_owner(self, lane: int) -> tuple[str, int]:
        for hand, lanes in self.hands.items():
            if lane in lanes:
                return hand, lanes.index(lane)
        return self.hand_names[0], 0

    def _mirror_lane(self, lane: int) -> int:
        """The same finger on the other hand, for cross-hand echoes."""
        hand, finger = self._lane_owner(lane)
        others = [h for h in self.hand_names if h != hand]
        if not others:
            return lane
        return self.hands[others[0]][finger]

    def _finger_max_counts(self, hand: str, finger: int) -> float:
        profiles = getattr(self.engine, "calibration_profiles", None) or {}
        prof = profiles.get(hand)
        try:
            if prof is not None and prof.has_max_press():
                return float(prof.max_press[finger])
        except (AttributeError, IndexError, TypeError):
            pass
        return 0.0

    def _prepare_trial(self) -> None:
        """Pick the next trial kind, hand and finger, then draw the
        plan. The kind bag was shuffled at construction; the per-kind
        schedulers keep fingers and hands at equal counts."""
        self.kind = (self._kind_bag[self.trials_done]
                     if self.trials_done < len(self._kind_bag) else "hold")
        if self.bilateral:
            _hand, lane = self._hold_sched.next() \
                if self.kind == "hold" else self._echo_sched.next()
        else:
            sched = (self._hold_sched if self.kind == "hold"
                     else self._echo_sched)
            lane = sched.next()
        self.lane = lane
        self.hand, self.finger = self._lane_owner(lane)
        self.cross = self.kind == "echo" and self.bilateral
        if self.cross:
            self.set_lane = self._mirror_lane(lane)
            self.set_hand, self.set_finger = self._lane_owner(self.set_lane)
        else:
            self.set_lane = lane
            self.set_hand, self.set_finger = self.hand, self.finger
        self.trial_counter += 1
        self.trial_seed = self.rng.randrange(2 ** 32)
        if self.kind == "hold":
            self.params = draw_hold_params(
                seed=self.trial_seed, level=self.level,
                target_lo_pct=self.target_lo_pct,
                target_hi_pct=self.target_hi_pct,
                hold_s=self.hold_s,
                n_dark=self.dark_windows_by_level[self.level - 1],
                dark_frac=self.dark_frac_by_level[self.level - 1],
                lit_lead_s=self.lit_lead_s, lit_gap_s=self.lit_gap_s,
                lit_tail_s=self.lit_tail_s, tol_pct=self.tol_pct,
                max_press_counts=self._finger_max_counts(self.hand,
                                                         self.finger))
            self.hold_windows = hold_segments_from_params(self.params)
        else:
            self.delay_s = self.echo_delays_s[self._delay_bag.next()]
            self.params = draw_echo_params(
                seed=self.trial_seed,
                target_lo_pct=self.target_lo_pct,
                target_hi_pct=self.target_hi_pct,
                show_s=self.echo_show_s, delay_s=self.delay_s,
                reproduce_s=self.echo_reproduce_s,
                settle_s=self.echo_settle_s, tol_pct=self.tol_pct,
                cross=self.cross, set_lane=self.set_lane,
                max_press_counts=self._finger_max_counts(self.hand,
                                                         self.finger))
            self.hold_windows = []
        self.target_pct = float(self.params["target_pct"])

    def _enter_announce(self, now: float) -> None:
        self.phase = "announce"
        self._phase_until = now + self.announce_s
        # Rest tare: the working hand rests during the announcement,
        # which is the moment to absorb drift. Cross-hand echoes tare
        # both the studying and the matching finger.
        lanes = [self.lane]
        if self.set_lane != self.lane:
            lanes.append(self.set_lane)
        self.view.rebaseline(lanes)
        self._reset_trial_scoring()

    def _reset_trial_scoring(self) -> None:
        self.sub = "ignite" if self.kind == "hold" else "enter"
        self.trial_t0 = None
        self.hold_t0 = None
        self._ignite_acc_s = 0.0
        self._win_idx = 0
        self._win_acc = {name: [0.0, 0.0, 0.0, 0.0, 0.0]
                         for name, _a, _b in self.hold_windows}
        self._dark_entry_pct = {}
        self._dark_exit_pct = {}
        self._last_pct = None
        self._err_smooth = 0.0
        self._flut_smooth = 0.0
        self._study_t0 = None
        self._delay_t0 = None
        self._repro_prompt_t = None
        self._press_t0 = None
        self._released = False
        self._release_quiet_s = 0.0
        self._repro_samples.clear()
        self.reveal_msg = ""
        self._reveal_until = None
        self.force_pct_now = None
        self.in_band_now = False
        self.lit_now = True
        self.flame_frac = 0.5
        self.flicker_frac = 0.0
        self.pressing_now = False
        self.delay_left_s = 0.0
        self.signal_stale = False

    def _start_trial(self, now: float) -> None:
        self.phase = "trial"
        self._phase_until = None
        self.trial_t0 = now
        self.level_msg = ""
        self.active = PendingTrial(
            trial_id=self.trial_counter, lane=self.lane,
            stim_t_perf=now, keys_pressed=[], incorrect_presses=[])
        # No on_stim fires in this mode, so the per-trial stamps the
        # CSV row reads are set here: the lantern always names the
        # working finger (a hold task must), and no RT censoring
        # window exists for a hold.
        cues = self.engine.cue_settings()
        self.engine._last_cue_code = cues.code
        self.engine._last_target_shown = True
        self.engine._last_stim_timeout_ms = None
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "lighthouse_trial", lane=self.lane, t_perf=now,
                detail=(f"trial_id={self.trial_counter};"
                        f"kind={self.kind};seed={self.trial_seed};"
                        f"lvl={self.level};finger={self.finger + 1}"),
                hand=self.engine.hand_mode)
        first = "ignite" if self.kind == "hold" else "enter"
        self.engine.log_segment_start(first, self.trial_counter,
                                      self.lane if self.kind == "hold"
                                      else self.set_lane, now)

    # ---- hold trials -------------------------------------------------------
    def _read_lane(self, lane: int, now: float) -> float | None:
        reading = self.view.read(lane)
        age = self.view.sample_age_s(lane, now)
        self.signal_stale = (reading is None or reading.percent is None
                            or age is None or age > self.SAMPLE_STALE_S)
        if self.signal_stale:
            self.force_pct_now = None
            return None
        pct = float(reading.percent)
        self.force_pct_now = pct
        return pct

    def _update_flame(self, err: float, dt: float) -> None:
        """Smooth the display drivers. Flame size follows the signed
        error, flicker follows the error's rate of change; both are
        EMAs so the screen can never blink at the frame rate."""
        if dt <= 0:
            return
        a_err = min(1.0, dt / self.ERR_TAU_S)
        prev = self._err_smooth
        self._err_smooth += (err - self._err_smooth) * a_err
        rate = abs(self._err_smooth - prev) / dt
        a_fl = min(1.0, dt / self.FLICKER_TAU_S)
        self._flut_smooth += (rate - self._flut_smooth) * a_fl
        span = max(0.5, 2.0 * self.tol_pct)
        self.flame_frac = max(0.0, min(
            1.0, 0.5 + self._err_smooth / (2.0 * span)))
        self.flicker_frac = max(0.0, min(1.0, self._flut_smooth / span))

    def _hold_frame(self, now: float, dt: float) -> None:
        if self.trial_t0 is None:
            return
        pct = self._read_lane(self.lane, now)
        if self.sub == "ignite":
            self.lit_now = True
            if pct is not None:
                self.in_band_now = abs(pct - self.target_pct) <= self.tol_pct
                self._update_flame(pct - self.target_pct, dt)
                self._ignite_acc_s = (self._ignite_acc_s + dt
                                      if self.in_band_now else 0.0)
                if self._ignite_acc_s >= self.ignite_hold_s:
                    self._begin_hold(now)
                    return
            if now - self.trial_t0 >= self.ignite_timeout_s:
                self._close_hold(now, guttered=True)
            return
        # sub == "hold"
        t_h = now - (self.hold_t0 or now)
        self._advance_hold_windows(t_h)
        if t_h >= float(self.params["hold_s"]):
            self._close_hold(now)
            return
        self.lit_now = feedback_lit(self.params, t_h)
        if pct is None:
            return
        self._last_pct = pct
        self.in_band_now = abs(pct - self.target_pct) <= self.tol_pct
        if self.lit_now:
            self._update_flame(pct - self.target_pct, dt)
        idx = min(self._win_idx, len(self.hold_windows) - 1)
        name = self.hold_windows[idx][0]
        acc = self._win_acc.get(name)
        if acc is not None:
            err = pct - self.target_pct
            acc[0] += abs(err) * dt
            acc[1] += dt
            if self.in_band_now:
                acc[2] += dt
            acc[3] += pct * dt
            acc[4] += pct * pct * dt

    def _begin_hold(self, now: float) -> None:
        self.sub = "hold"
        self.hold_t0 = now
        self._win_idx = 0
        self.engine.log_segment_end("ignite", self.trial_counter,
                                    self.lane, now)
        first = self.hold_windows[0][0]
        self.engine.log_segment_start(first, self.trial_counter,
                                      self.lane, now)

    def _advance_hold_windows(self, t_h: float) -> None:
        """Cross lit / dark boundaries on the model clock, not the
        frame clock, so the logged bounds are exact. Dark entries and
        exits capture the last known force so each window's drift is
        the force change across it."""
        while (self._win_idx < len(self.hold_windows)
               and t_h >= self.hold_windows[self._win_idx][2]):
            name, _a, b = self.hold_windows[self._win_idx]
            t_mark = (self.hold_t0 or 0.0) + b
            self.engine.log_segment_end(name, self.trial_counter,
                                        self.lane, t_mark)
            if name.startswith("dark") and self._last_pct is not None:
                self._dark_exit_pct[name] = self._last_pct
                entry = self._dark_entry_pct.get(name)
                if entry is not None:
                    drift = self._last_pct - entry
                    # The relight reveal: the drift that accumulated
                    # unseen, said plainly and left up long enough to
                    # read (steady text, no flashing).
                    self.reveal_msg = (
                        f"In the dark your hold drifted {drift:+.1f}% "
                        f"of max")
                    self._reveal_until = ((self.hold_t0 or 0.0) + b
                                          + self.REVEAL_S)
            self._win_idx += 1
            if self._win_idx < len(self.hold_windows):
                nxt = self.hold_windows[self._win_idx][0]
                self.engine.log_segment_start(nxt, self.trial_counter,
                                              self.lane, t_mark)
                if nxt.startswith("dark") and self._last_pct is not None:
                    self._dark_entry_pct[nxt] = self._last_pct

    # ---- closing a hold ----------------------------------------------------
    @staticmethod
    def _pool(accs: list[list[float]]) -> tuple[float, float, float] | None:
        """Pool window accumulators into (mae, cov, in_band_frac).
        None when no time was scored (a full dropout)."""
        t = sum(a[1] for a in accs)
        if t <= 0:
            return None
        mae = sum(a[0] for a in accs) / t
        mean = sum(a[3] for a in accs) / t
        var = max(0.0, sum(a[4] for a in accs) / t - mean * mean)
        cov = (math.sqrt(var) / mean) if mean > 1e-9 else 0.0
        tib = sum(a[2] for a in accs) / t
        return mae, cov, tib

    def _close_hold(self, now: float, guttered: bool = False) -> None:
        trial = self.active
        self.active = None
        lit_accs = [self._win_acc[n] for n, _a, _b in self.hold_windows
                    if n.startswith("lit")]
        dark_accs = [self._win_acc[n] for n, _a, _b in self.hold_windows
                     if n.startswith("dark")]
        lit = None if guttered else self._pool(lit_accs)
        dark = None if guttered else self._pool(dark_accs)
        lit_mae, lit_cov = (lit[0], lit[1]) if lit else (None, None)
        dark_mae = dark[0] if dark else None
        delta = (dark_mae - lit_mae
                 if dark_mae is not None and lit_mae is not None else None)
        scored_t = sum(a[1] for a in self._win_acc.values())
        tib = (sum(a[2] for a in self._win_acc.values()) / scored_t
               if scored_t > 0 else 0.0)
        drifts = [self._dark_exit_pct[n] - self._dark_entry_pct[n]
                  for n in self._dark_entry_pct
                  if n in self._dark_exit_pct]
        dark_s = float(self.params.get("dark_s", 0.0))
        drift_rate = (sum(abs(d) for d in drifts) / len(drifts) / dark_s
                      if drifts and dark_s > 0 else None)

        if guttered:
            label, base = "Miss", self.score_cfg.miss_points
        elif tib >= self.GREAT_TIB:
            label, base = "Great", self.score_cfg.great_points
        elif tib >= self.GOOD_TIB:
            label, base = "Good", self.score_cfg.good_points
        else:
            label, base = "Miss", self.score_cfg.miss_points
        # dark_bonus_points rewards staying ACCURATE in the dark, not
        # merely staying wherever the finger happened to land. A window
        # is "steady" only if the finger was already within tolerance
        # of the target when the room went dark (entry) AND did not
        # drift outside tolerance from there (exit close to entry).
        # Scoring drift alone (exit - entry, with no reference to
        # target) let a hold that ignited correctly then drifted to and
        # sat steady at target+8% -- completely off-target, zero time
        # in band -- collect the same bonus as genuinely accurate
        # steadiness, which could out-score a real "Good" hold.
        steady_darks = sum(
            1 for n in self._dark_entry_pct
            if n in self._dark_exit_pct
            and abs(self._dark_entry_pct[n] - self.target_pct) <= self.tol_pct
            and abs(self._dark_exit_pct[n] - self._dark_entry_pct[n])
                <= self.tol_pct
        )
        bonus = steady_darks * self.dark_bonus_points
        points = base + bonus
        # However the bonus is earned, it must never let a lower-tier
        # outcome out-score the tier above it: a Miss must stay below
        # every Good, a Good below every Great.
        if label == "Miss":
            points = min(points, self.score_cfg.good_points - 1)
        elif label == "Good":
            points = min(points, self.score_cfg.great_points - 1)
        outcome = TrialResult(label=label, points=points, rt_ms=None)

        rec = HoldRecord(
            hand=self.hand, finger=self.finger, lane=self.lane,
            level=self.level, target_pct=self.target_pct,
            guttered=guttered, tib_frac=tib, lit_mae_pct=lit_mae,
            lit_cov=lit_cov, dark_mae_pct=dark_mae, delta_pct=delta,
            drifts_pct=drifts, drift_rate_pct_s=drift_rate)
        self._holds.append(rec)

        def _fmt(v):
            return "" if v is None else f"{v:.3f}"

        stimulus = (
            f"hold;lvl={self.level};hand={self.hand};"
            f"finger={FINGER_WORDS[self.finger].lower()};"
            f"target={self.target_pct:.2f};guttered={guttered};"
            f"tib={tib:.3f};lit_mae={_fmt(lit_mae)};"
            f"lit_cov={_fmt(lit_cov)};dark_mae={_fmt(dark_mae)};"
            f"delta={_fmt(delta)};darks={len(drifts)}")
        segments = [("ignite", self.trial_t0 or now,
                     self.hold_t0 if self.hold_t0 is not None else now)]
        if self.hold_t0 is not None:
            segments += [(n, self.hold_t0 + a, self.hold_t0 + b)
                         for n, a, b in self.hold_windows]
        else:
            # A gutter never reached the hold: close the dangling
            # ignite marker so raw.csv stays balanced.
            self.engine.log_segment_end("ignite", self.trial_counter,
                                        self.lane, now)
        info = ContinuousTrialLog(waveform="hold", params=self.params,
                                  seed=self.trial_seed, segments=segments)
        if trial is not None:
            # A hold is always one hand's finger, even in a both-hands
            # block; the row-level hand must say which (audit finding
            # #86), not fall back to the block's "both".
            self.engine.log_trial(trial, outcome, now, stimulus=stimulus,
                                  correct_lanes=[self.lane],
                                  continuous=info, hand=self.hand)

        self._last_result = {
            "kind": "hold", "label": label, "guttered": guttered,
            "tib": tib, "lit_mae": lit_mae, "lit_cov": lit_cov,
            "dark_mae": dark_mae, "delta": delta,
            "drifts": drifts, "hand": self.hand, "finger": self.finger,
            "target": self.target_pct,
        }
        if not guttered:
            self._move_level(lit_mae, delta)
        self._finish_trial(now)

    def _move_level(self, lit_mae: float | None,
                    delta: float | None) -> None:
        """The ladder moves on the lit-dark delta (Li 2015's
        discriminator). Level 1 has no dark windows, so it promotes on
        lit accuracy alone; guttered holds never move the ladder.
        Every move is announced in plain words and logged."""
        moved = 0
        if self.level == 1:
            if lit_mae is not None:
                self._recent_lit_mae.append(lit_mae)
                if (len(self._recent_lit_mae) >= 2
                        and max(self._recent_lit_mae[-2:])
                        <= self.promote_lit_mae_pct
                        and self.level < self.max_level):
                    moved = 1
        else:
            if delta is not None:
                self._recent_delta.append(delta)
                if delta >= self.demote_delta_pct:
                    moved = -1
                elif (len(self._recent_delta) >= 2
                        and max(self._recent_delta[-2:])
                        <= self.promote_delta_pct
                        and self.level < self.max_level):
                    moved = 1
        if not moved:
            return
        self.level += moved
        self._recent_lit_mae.clear()
        self._recent_delta.clear()
        self._level_trace.append(self.level)
        frac = self.dark_frac_by_level[self.level - 1]
        if moved > 0:
            self.level_msg = (
                f"The room darkens longer: level {self.level} of "
                f"{self.max_level} (dark {frac * 100:.0f}% of each hold)")
        else:
            self.level_msg = (
                f"More light returns: level {self.level} of "
                f"{self.max_level} (dark {frac * 100:.0f}% of each hold)")
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "lighthouse_level",
                detail=(f"level={self.level} dark_frac={frac} "
                        f"trials_done={self.trials_done}"),
                hand=self.engine.hand_mode)

    # ---- echo trials -------------------------------------------------------
    def _echo_frame(self, now: float, dt: float) -> None:
        if self.trial_t0 is None:
            return
        p = self.params
        if self.sub == "enter":
            pct = self._read_lane(self.set_lane, now)
            self.lit_now = True
            if pct is not None:
                self.in_band_now = abs(pct - self.target_pct) <= self.tol_pct
                self._update_flame(pct - self.target_pct, dt)
                self._ignite_acc_s = (self._ignite_acc_s + dt
                                      if self.in_band_now else 0.0)
                if self._ignite_acc_s >= self.ignite_hold_s:
                    self.sub = "study"
                    self._study_t0 = now
                    self.engine.log_segment_end(
                        "enter", self.trial_counter, self.set_lane, now)
                    self.engine.log_segment_start(
                        "study", self.trial_counter, self.set_lane, now)
                    return
            if now - self.trial_t0 >= self.ignite_timeout_s:
                self._close_echo(now, guttered=True)
            return
        if self.sub == "study":
            pct = self._read_lane(self.set_lane, now)
            self.lit_now = True
            if pct is not None:
                self.in_band_now = abs(pct - self.target_pct) <= self.tol_pct
                self._update_flame(pct - self.target_pct, dt)
            if now - (self._study_t0 or now) >= float(p["show_s"]):
                self.sub = "delay"
                self._delay_t0 = now
                self.lit_now = False
                self.engine.log_segment_end(
                    "study", self.trial_counter, self.set_lane, now)
                self.engine.log_segment_start(
                    "delay", self.trial_counter, self.lane, now)
            return
        if self.sub == "delay":
            self.lit_now = False
            self.force_pct_now = None
            # The standard force-sense paradigm needs a real release
            # between encode and reproduce: a finger that rests on the
            # pad through the delay carries a live tactile anchor into
            # a window the design means to make blind. Read the
            # reproduce lane directly (not through _read_lane, which
            # drives the on-screen force_pct_now the delay deliberately
            # blanks) and require it below the entry floor for
            # RELEASE_QUIET_S at some point during the delay.
            rel = self.view.read(self.lane)
            if rel is not None and rel.percent is not None:
                if rel.percent < self.ENTRY_FLOOR_PCT:
                    self._release_quiet_s += dt
                else:
                    self._release_quiet_s = 0.0
                if self._release_quiet_s >= self.RELEASE_QUIET_S:
                    self._released = True
            elapsed = now - (self._delay_t0 or now)
            self.delay_left_s = max(0.0, float(p["delay_s"]) - elapsed)
            if self.delay_left_s <= 0.0:
                if self._released:
                    self.sub = "reproduce"
                    self._repro_prompt_t = now
                    self.engine.log_segment_end(
                        "delay", self.trial_counter, self.lane, now)
                elif elapsed >= float(p["delay_s"]) + self.ignite_timeout_s:
                    # Held straight through the delay and the grace
                    # window on top of it: no blind reproduction is
                    # possible from here, so the trial closes gently
                    # rather than let a held force masquerade as a
                    # perfect echo (audit finding #84). self.sub is
                    # still "delay", so _close_echo's own gutter path
                    # ties off the open marker; do not close it twice.
                    self._close_echo(now, guttered=True)
                # else: still waiting for the release inside the grace
                # window; the delay clock holds at zero rather than
                # arming reproduce on a held force.
            return
        # sub == "reproduce". The scored window starts at the press,
        # not at the prompt, so a slow blind start does not eat into
        # the settled window the notebook scores.
        pct = self._read_lane(self.lane, now)
        self.lit_now = False
        self.pressing_now = pct is not None and pct >= self.ENTRY_FLOOR_PCT
        if self._press_t0 is None:
            if self.pressing_now:
                self._press_t0 = now
                self.engine.log_segment_start(
                    "reproduce", self.trial_counter, self.lane, now)
            elif (now - (self._repro_prompt_t or now)
                    >= self.ignite_timeout_s):
                self._close_echo(now, guttered=True)
            return
        if pct is not None:
            self._repro_samples.append((now, pct))
        if now - self._press_t0 >= float(p["reproduce_s"]):
            self._close_echo(now)

    def _close_echo(self, now: float, guttered: bool = False) -> None:
        trial = self.active
        self.active = None
        p = self.params
        made: float | None = None
        if not guttered and self._press_t0 is not None:
            settle_from = (self._press_t0 + float(p["reproduce_s"])
                           - float(p["settle_s"]))
            settled = [v for t, v in self._repro_samples
                       if t >= settle_from]
            if settled:
                made = sum(settled) / len(settled)
        signed = (made - self.target_pct) if made is not None else None
        abs_err = abs(signed) if signed is not None else None

        if guttered or abs_err is None:
            label, base = "Miss", self.score_cfg.miss_points
            guttered = True
        elif abs_err <= self.tol_pct:
            label, base = "Great", self.score_cfg.great_points
        elif abs_err <= 2.0 * self.tol_pct:
            label, base = "Good", self.score_cfg.good_points
        else:
            label, base = "Miss", self.score_cfg.miss_points
        outcome = TrialResult(label=label, points=base, rt_ms=None)

        rec = EchoRecord(
            hand=self.hand, finger=self.finger, lane=self.lane,
            set_lane=self.set_lane, cross=self.cross,
            delay_s=float(p["delay_s"]), target_pct=self.target_pct,
            guttered=guttered, signed_err_pct=signed,
            abs_err_pct=abs_err)
        self._echoes.append(rec)

        def _fmt(v):
            return "" if v is None else f"{v:.3f}"

        stimulus = (
            f"echo;hand={self.hand};"
            f"finger={FINGER_WORDS[self.finger].lower()};"
            f"cross={self.cross};delay_s={float(p['delay_s']):.1f};"
            f"target={self.target_pct:.2f};made={_fmt(made)};"
            f"err={_fmt(signed)};guttered={guttered};"
            f"released={self._released}")
        segments = [("enter", self.trial_t0 or now,
                     self._study_t0 if self._study_t0 is not None else now)]
        if self._study_t0 is not None:
            segments.append(("study", self._study_t0,
                             self._delay_t0 if self._delay_t0 is not None
                             else now))
        if self._delay_t0 is not None:
            segments.append(("delay", self._delay_t0,
                             self._repro_prompt_t
                             if self._repro_prompt_t is not None else now))
        if self._press_t0 is not None:
            segments.append(("reproduce", self._press_t0, now))
            self.engine.log_segment_end("reproduce", self.trial_counter,
                                        self.lane, now)
        elif guttered and self.sub in ("enter", "study", "delay"):
            # Tie off whichever marker was left open by the gutter. A
            # gutter while waiting for the reproduce press has nothing
            # open: delay already closed and reproduce never started.
            open_lane = (self.set_lane if self.sub in ("enter", "study")
                         else self.lane)
            self.engine.log_segment_end(self.sub, self.trial_counter,
                                        open_lane, now)
        info = ContinuousTrialLog(waveform="reproduce", params=p,
                                  seed=self.trial_seed, segments=segments)
        if trial is not None:
            # A plain echo is one hand's finger, same as a hold (audit
            # finding #86); a cross echo genuinely uses both hands (one
            # studies, the other reproduces), so "both" stays the
            # honest row-level answer there.
            row_hand = "both" if self.cross else self.hand
            self.engine.log_trial(trial, outcome, now, stimulus=stimulus,
                                  correct_lanes=[self.lane],
                                  continuous=info, hand=row_hand)

        self._last_result = {
            "kind": "echo", "label": label, "guttered": guttered,
            "delay_s": float(p["delay_s"]), "target": self.target_pct,
            "made": made, "signed_err": signed, "cross": self.cross,
            "hand": self.hand, "finger": self.finger,
            "set_hand": self.set_hand,
        }
        self._finish_trial(now)

    # ---- shared trial close ------------------------------------------------
    def _finish_trial(self, now: float) -> None:
        self.trials_done += 1
        if self.trials_done >= self.total_trials:
            self._end("completed")
            return
        self.phase = "feedback"
        self._phase_until = now + self.rest_s
        self._prepare_trial()

    def _end(self, reason: str) -> None:
        self.phase = "done"
        self.end_reason = reason
        # Next block this app session starts where this one ended,
        # like Force Pilot's level carry; a restart resets to config.
        self.engine._lighthouse_level = self.level
        self.engine.finish_block()

    # ---- block summary -----------------------------------------------------
    def block_stats(self) -> dict:
        """What finish_block folds into metadata.json and the results
        screen reads: lit steadiness, dark drift, the lit-dark delta
        headline, and reproduction error by delay."""
        def _mean(vals):
            vals = [v for v in vals if v is not None]
            return round(sum(vals) / len(vals), 3) if vals else None

        def _sd(vals):
            vals = [v for v in vals if v is not None]
            if len(vals) < 2:
                return None
            m = sum(vals) / len(vals)
            return round(math.sqrt(sum((v - m) ** 2 for v in vals)
                                   / (len(vals) - 1)), 3)

        holds = [h for h in self._holds if not h.guttered]
        # The lit-dark delta grows with dark duration (drift
        # accumulates), and the ladder is global and moves mid-block,
        # so pooling a lane's delta across every level it happened to
        # hold at compares fingers on different amounts of darkness,
        # not on the fingers (audit finding #85). Report the per-lane
        # delta from the highest level EVERY played lane has at least
        # one hold at, so every finger's number comes off the same
        # dark exposure; if no single level has full coverage yet
        # (early in a block), fall back to pooling across levels for
        # that lane rather than showing nothing.
        lanes_with_holds = {h.lane for h in holds}
        common_level: int | None = None
        for lvl in sorted({h.level for h in holds}, reverse=True):
            if {h.lane for h in holds if h.level == lvl} >= lanes_with_holds:
                common_level = lvl
                break
        per_lane: dict[str, dict] = {}
        for lane in sorted({h.lane for h in self._holds}):
            hs = [h for h in holds if h.lane == lane]
            hs_delta = ([h for h in hs if h.level == common_level]
                        if common_level is not None else hs)
            per_lane[str(lane)] = {
                "holds": len([h for h in self._holds if h.lane == lane]),
                "lit_cov": _mean([h.lit_cov for h in hs]),
                "lit_mae_pct": _mean([h.lit_mae_pct for h in hs]),
                "dark_mae_pct": _mean([h.dark_mae_pct for h in hs]),
                "delta_pct": _mean([h.delta_pct for h in hs_delta]),
                "delta_level": common_level,
                "drift_rate_pct_s": _mean([h.drift_rate_pct_s
                                           for h in hs]),
            }
        all_drifts = [d for h in holds for d in h.drifts_pct]
        echoes = [e for e in self._echoes if not e.guttered]
        by_delay: dict[str, dict] = {}
        for d in sorted({e.delay_s for e in self._echoes}):
            es = [e for e in echoes if e.delay_s == d]
            by_delay[f"{d:g}"] = {
                "n": len(es),
                "constant_err_pct": _mean([e.signed_err_pct for e in es]),
                "variable_err_pct": _sd([e.signed_err_pct for e in es]),
                "abs_err_pct": _mean([e.abs_err_pct for e in es]),
            }
        return {
            "levels": {"start": self.level_start, "final": self.level,
                       "trace": list(self._level_trace)},
            "hands": self.hand_names,
            "holds": len(self._holds),
            "echo_trials": len(self._echoes),
            "gutters": (len([h for h in self._holds if h.guttered])
                        + len([e for e in self._echoes if e.guttered])),
            "per_lane": per_lane,
            "overall": {
                "lit_cov": _mean([h.lit_cov for h in holds]),
                "lit_mae_pct": _mean([h.lit_mae_pct for h in holds]),
                "dark_mae_pct": _mean([h.dark_mae_pct for h in holds]),
                "lit_dark_delta_pct": _mean([h.delta_pct for h in holds]),
                "dark_drift_pct": _mean([abs(d) for d in all_drifts])
                if all_drifts else None,
                "drift_rate_pct_s": _mean([h.drift_rate_pct_s
                                           for h in holds]),
                "time_in_band": _mean([h.tib_frac for h in holds]),
            },
            "echo": {
                "cross_hand": self.bilateral,
                "by_delay": by_delay,
                "overall": {
                    "constant_err_pct": _mean([e.signed_err_pct
                                               for e in echoes]),
                    "variable_err_pct": _sd([e.signed_err_pct
                                             for e in echoes]),
                    "abs_err_pct": _mean([e.abs_err_pct for e in echoes]),
                },
            },
            "demo": self.demo,
            "end_reason": self.end_reason,
        }
