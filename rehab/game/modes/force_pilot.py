"""Force Pilot mode: visuomotor force tracking. One finger's force
flies a craft through a scrolling corridor; the 200 Hz analogue force
signal is the game input, not a threshold crossing.

WHY THIS DESIGN. Continuous force control is impaired across stroke,
Parkinson's disease, multiple sclerosis, carpal tunnel syndrome and
normal ageing in ways threshold logic cannot see, and the deficits are
measurable from exactly the trace this rig already streams:

- Lodha N, Misra G, Coombes SA, Christou EA, Cauraugh JH (2013).
  Increased Force Variability in Chronic Stroke: Contributions of
  Force Modulation below 1 Hz. PLOS ONE 8(12):e83468. Isometric holds
  at 5 / 25 / 50 percent MVC; paretic-hand variability was elevated
  and its frequency structure (more normalised power 0.1 to 0.3 Hz,
  less 0.5 to 0.8 Hz) explained about 80 percent of it. That spectral
  shift is a ready-made notebook biomarker, and it is why this mode's
  sine and assessment sections live in the 0.1 to 0.6 Hz band.
- Pennati GV, Plantin J, et al (2020). Recovery and Prediction of
  Dynamic Precision Grip Force Control After Stroke. Stroke
  51(3):944-951. 80 first-ever stroke patients over 6 months: force
  control metrics stayed sensitive where clinical scales saturated,
  which is the case for tracking a rehab cohort session by session.
- Taud B, et al (2021). Frontiers in Neurology, randomised controlled
  trial: visuomotor grip-force tracking training itself drove motor
  recovery after stroke, so the tracking task is the candidate active
  ingredient, not just the measurement.

Supporting, verified by the research cluster: Kurillo 2005 (Technology
and Health Care) is the build template (force sensor plus screen
tracking as assessment and training); Archer 2017 (NeuroImage:
Clinical) showed visual feedback gain moves stroke tracking error by
an order of magnitude, which is why gain is a config lever here and
defaults to 1.0; Naik 2011 (Exp Brain Res 211:1-15) scored ramp
generation and release at 5 to 20 percent MVC per second, the rates
this mode's ramps use; Davidson 2026 (Exp Brain Res 244(4):46) found
Parkinson's disease disproportionately impairs force RELEASE during
0.2 Hz sine tracking, which is why the ramp-down half of every run is
scored as its own segment.

PARAMETER DEFENCES, in config order:
- 0 to 40 percent of the session max press mapped to altitude: the
  ranked brief's span. The cited deficits live at low force (5 to 25
  percent MVC in Lodha 2013 and the Camacho-Villa 2025 steadiness
  meta-analysis), and staying under half of max keeps 20 to 30 s runs
  repeatable without strength fatigue dominating the trace.
- runs of 20 to 30 s per finger: Lodha held 20 s, Davidson tracked
  32 s trials; long enough for sub-1 Hz spectral estimates, short
  enough to repeat per finger.
- ramps at 5 or 10 percent of max per second: Naik 2011's lower two
  rates. The drawn rate is logged per run.
- sines 0.2 to 0.6 Hz and a sum-of-sines assessment inside 0.1 to
  0.6 Hz: the Lodha analysis bands plus Davidson's 0.2 Hz tracking
  sine. The assessment section is pseudorandom (non-harmonic
  frequencies, random phases) so it cannot be memorised, and its seed
  and drawn parameters are logged for exact offline reconstruction.
- corridor half-widths 8 / 6 / 4 percent and waveform bandwidth per
  level: the two difficulty axes the brief names. Moves are announced
  plainly on screen and logged (force_pilot_level raw event).
- promotion at 80 percent time-in-corridor over two runs, demotion
  under 40 percent: the app's challenge-point convention (adaptive
  mode holds a 65 to 80 percent band); no published staircase exists
  for corridor tracking, so this is a design choice and says so.
- visual gain 1.0 by default: gain magnifies the DISPLAYED error only
  (craft shows target + gain x error). Archer 2017 shows gain shifts
  patient error substantially, so it is a per-block config lever, is
  logged in every run's waveform_params, and must be held constant
  within any comparison.

FLOW. Session max press probes run first (the shared foundation flow:
MaxPressProbe per finger, median of maximal presses, stored via
engine.record_max_press) for every playing hand whose stored max is
missing or older than six hours. Every force target afterwards is
percent of THAT number, never raw counts. Then runs: one finger flies
per run, the corridor scrolls right to left through hold, ramp up,
hold, ramp down (release), sine, then the sum-of-sines assessment.
Leaving the corridor stalls the craft and buzzes the working finger;
rings on the centreline reward time-in-corridor. The weakest fingers
(highest mean tracking error so far) get extra runs through the
existing FloorWeightedScheduler, floored so every finger stays
analysable. One hand selected: its four fingers. Both hands: all
eight fingers, runs alternating between hands on a balanced bag, and
the active hand and finger are named on screen throughout.

CUES AND CHANNELS. This mode never calls on_stim: there is no hidden
target to cue, because a visuomotor tracking task must show the
target (the corridor IS the stimulus), so cue.show_target does not
apply and every trial row records cue_target_shown TRUE. The corridor
exit buzz is tactile error feedback, not a target cue; it rides the
cue.buzz_after switch so a block run without it is distinguishable in
the CSV (cue_flags), and each buzz is delivered through
engine.pulse_motor, which logs a raw pulse_motor event per buzz.

LOGGING. One trial row per run. waveform is "corridor";
waveform_seed plus the force_pilot config rebuild the run's section
plan bit-exactly through draw_run_params; waveform_params also
carries every DRAWN number (ramp rate, sine frequency and cycles,
sum-of-sines frequencies, amplitudes and phases, corridor half-width,
gain, the finger's max_press_counts) so the notebook can rebuild the
target from the row alone via sections_from_params without importing
this module, to the 6-significant-digit precision of the packed cell.
segment_times brackets every section (hold_in, ramp_up, hold_top,
release, sine, pre_assess, assess_sos) in raw-stream t_perf seconds,
and segment_start / segment_end events mark the same bounds inside
raw.csv. The in-game score (time-in-corridor, mean absolute error at
frame rate) is feedback; the analysis notebook re-scores offline from
the 200 Hz raw samples between the logged bounds.

WHAT THIS MODE CANNOT CLAIM. SingleTact accuracy and drift at very
low force is uncharacterised on this rig: a bench characterisation
(known masses, drift over hold durations) must precede any patient
data collection, and the thesis instrumentation section owns that.
The probe measures a maximal flat-finger press on a pad, not the grip
or pinch MVC of the cited protocols, so percent-of-max matches those
studies in construct rather than in newtons. Frame-rate scoring here
is for gameplay only; every research number comes from the notebook's
offline scoring of the raw stream. Training benefit rests on Taud
2021 and the Kurillo lineage, in grip tracking after stroke; for the
other populations this mode is measurement plus practice, not a
proven therapy. There is no keyboard fallback by design: a keyboard
cannot produce a continuous force signal, and the mode says so on
screen instead of pretending.
"""
from __future__ import annotations

import logging
import math
import random
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ...data.logger import ContinuousTrialLog
from ..force_stream import ForceView, MaxPressProbe, needs_max_press_probe
from ..scheduling import BalancedScheduler, FloorWeightedScheduler
from ..scoring import ScoreConfig, TrialResult
from .classic import PendingTrial

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


# On-screen finger names, matching the hand picker's "index to little".
FINGER_WORDS = ("INDEX", "MIDDLE", "RING", "LITTLE")

# Waveform band floors. Ceilings come from the level's bandwidth knob;
# the floors stay put so the sine keeps inside the brief's 0.2 to
# 0.6 Hz and the assessment can reach down into the 0.1 to 0.3 Hz band
# the Lodha biomarker lives in.
SINE_FREQ_FLOOR_HZ = 0.2
SOS_FREQ_FLOOR_HZ = 0.1

# Hard ceiling on a run's planned length: the brief's 20 to 30 s
# window. The sine's whole-cycle rounding is trimmed against this so
# a slow ramp draw cannot push the plan past it.
RUN_CAP_S = 30.0

# Plain-words labels for the scored sections, used by the results
# summary ("best section") and the run feedback card.
SECTION_LABELS = {
    "hold_in": "low hold",
    "ramp_up": "press ramp",
    "hold_top": "high hold",
    "release": "release ramp",
    "sine": "waves",
    "pre_assess": "approach",
    "assess_sos": "assessment",
}


# ---- pure trajectory generation --------------------------------------------
# The rule from the logging contract: the exact target the patient saw
# must be rebuildable offline. Two pure layers deliver that.
#   draw_run_params(seed, ...)  draws every random number ONCE and
#                               returns the flat dict that is logged as
#                               waveform_params (seed in waveform_seed).
#   sections_from_params(p)     deterministic plan from that dict; the
#                               notebook carries a copy and never needs
#                               the seed or this module's rng.
#   target_pct(sections, t)     evaluates the target at any time.
# The mode uses the same three functions to play the run it logs.


@dataclass(frozen=True)
class RunSection:
    """One piece of the corridor. `a_pct` is the level (holds), the
    start level (ramps) or the centre (sine / sum-of-sines); `b_pct`
    is the ramp end level. Oscillators carry their component tuples."""

    name: str
    kind: str                  # "hold" | "ramp" | "osc"
    start_s: float
    dur_s: float
    a_pct: float
    b_pct: float = 0.0
    freqs_hz: tuple = ()
    amps_pct: tuple = ()
    phases_rad: tuple = ()

    @property
    def end_s(self) -> float:
        return self.start_s + self.dur_s


def draw_run_params(seed: int, level: int, freq_ceiling_hz: float,
                    corridor_hw_pct: float, gain: float, span_pct: float,
                    base_pct: float, plateau_pct: float,
                    ramp_rates_pct_s: list, sine_amp_pct: float,
                    sine_s: float, sos_amps_pct: list, sos_s: float,
                    hold_in_s: float, hold_top_s: float,
                    pre_assess_s: float,
                    max_press_counts: float) -> dict:
    """Draw a run's random numbers and return the loggable params dict.

    Pure: the same seed and knobs always return the same dict, which
    is what makes waveform_seed sufficient for bit-exact rebuilds.
    Keys are short because the dict is packed into one CSV cell.
    """
    rng = random.Random(int(seed))
    rate = float(rng.choice(list(ramp_rates_pct_s)))
    sine_f = rng.uniform(SINE_FREQ_FLOOR_HZ, max(SINE_FREQ_FLOOR_HZ,
                                                 float(freq_ceiling_hz)))
    # Whole cycles so the sine ends where it began (the base level) and
    # the plan stays continuous into the next section. The cycle count
    # is then trimmed against RUN_CAP_S: a slow ramp draw plus a
    # rounded-up sine could otherwise push the run past the brief's
    # 30 s ceiling.
    sine_cycles = max(1, round(sine_s * sine_f))
    ramp_s = (float(plateau_pct) - float(base_pct)) / max(0.1, rate)
    fixed_s = (float(hold_in_s) + float(hold_top_s) + 2.0 * ramp_s
               + float(pre_assess_s) + float(sos_s))
    sine_room_s = RUN_CAP_S - fixed_s
    if sine_room_s > 0:
        sine_cycles = max(1, min(sine_cycles,
                                 int(sine_room_s * sine_f)))
    # Assessment: three non-harmonic components, one drawn from each
    # third of the band so they cannot collapse onto each other, with
    # free phases. Non-harmonic spacing is what makes the sum look
    # pseudorandom to the patient while staying a closed-form target.
    lo = SOS_FREQ_FLOOR_HZ
    hi = max(lo + 0.05, float(freq_ceiling_hz))
    third = (hi - lo) / 3.0
    sos_f = [rng.uniform(lo + i * third + 0.1 * third,
                         lo + (i + 1) * third - 0.1 * third)
             for i in range(3)]
    sos_p = [rng.uniform(0.0, 2.0 * math.pi) for _ in range(3)]
    amps = [float(a) for a in list(sos_amps_pct)[:3]]
    while len(amps) < 3:
        amps.append(1.0)
    p = {
        "lvl": int(level),
        "gain": float(gain),
        "hw_pct": float(corridor_hw_pct),
        "span_pct": float(span_pct),
        "base_pct": float(base_pct),
        "plateau_pct": float(plateau_pct),
        "ramp_rate_pct_s": rate,
        "hold_in_s": float(hold_in_s),
        "hold_top_s": float(hold_top_s),
        "sine_amp_pct": float(sine_amp_pct),
        "sine_freq_hz": sine_f,
        "sine_cycles": sine_cycles,
        "pre_assess_s": float(pre_assess_s),
        "sos_s": float(sos_s),
        "max_press_counts": float(max_press_counts),
    }
    for i in range(3):
        p[f"sos_f{i + 1}_hz"] = sos_f[i]
        p[f"sos_a{i + 1}_pct"] = amps[i]
        p[f"sos_p{i + 1}_rad"] = sos_p[i]
    return p


def sections_from_params(p: dict) -> list[RunSection]:
    """The deterministic section plan for one run. No randomness: every
    number comes from the params dict, so the notebook can rebuild the
    plan from the logged cell alone (parse_waveform_params gives floats
    at 6 significant digits, which bounds the rebuild error well under
    a hundredth of a percent of max)."""
    base = float(p["base_pct"])
    plateau = float(p["plateau_pct"])
    rate = float(p["ramp_rate_pct_s"])
    ramp_s = max(0.1, (plateau - base) / max(0.1, rate))
    sine_amp = float(p["sine_amp_pct"])
    sine_f = float(p["sine_freq_hz"])
    sine_dur = max(1, int(round(float(p["sine_cycles"])))) / sine_f
    sos_amps = tuple(float(p[f"sos_a{i}_pct"]) for i in (1, 2, 3))
    sos_freqs = tuple(float(p[f"sos_f{i}_hz"]) for i in (1, 2, 3))
    sos_phases = tuple(float(p[f"sos_p{i}_rad"]) for i in (1, 2, 3))
    # Oscillator centres sit one amplitude-sum above base so the wave
    # floor never drops below the run's resting level.
    sine_mid = base + sine_amp
    sos_mid = base + sum(sos_amps)
    # The assessment starts wherever its phases put it; the approach
    # ramp walks the target there from base so the plan never jumps.
    sos_v0 = sos_mid + sum(a * math.sin(ph)
                           for a, ph in zip(sos_amps, sos_phases))
    out: list[RunSection] = []
    t = 0.0

    def add(name, kind, dur, a, b=0.0, freqs=(), amps=(), phases=()):
        nonlocal t
        out.append(RunSection(name=name, kind=kind, start_s=t,
                              dur_s=float(dur), a_pct=float(a),
                              b_pct=float(b), freqs_hz=tuple(freqs),
                              amps_pct=tuple(amps),
                              phases_rad=tuple(phases)))
        t += float(dur)

    add("hold_in", "hold", float(p["hold_in_s"]), base)
    add("ramp_up", "ramp", ramp_s, base, plateau)
    add("hold_top", "hold", float(p["hold_top_s"]), plateau)
    add("release", "ramp", ramp_s, plateau, base)
    # Sine starts at its trough (the base level) so the release lands
    # straight onto it: phase -pi/2 puts sin at -1 at t = 0.
    add("sine", "osc", sine_dur, sine_mid,
        freqs=(sine_f,), amps=(sine_amp,), phases=(-math.pi / 2.0,))
    add("pre_assess", "ramp", float(p["pre_assess_s"]), base, sos_v0)
    add("assess_sos", "osc", float(p["sos_s"]), sos_mid,
        freqs=sos_freqs, amps=sos_amps, phases=sos_phases)
    return out


def run_duration_s(sections: list[RunSection]) -> float:
    return sections[-1].end_s if sections else 0.0


def target_pct(sections: list[RunSection], t: float) -> float:
    """The corridor centreline at run time t, in percent of max.
    Clamped to the plan's ends so lookahead rendering past the final
    section holds the last value instead of extrapolating."""
    if not sections:
        return 0.0
    if t <= 0.0:
        t = 0.0
    last = sections[-1]
    if t >= last.end_s:
        t = last.end_s
    for sec in sections:
        if t <= sec.end_s or sec is last:
            tt = t - sec.start_s
            if sec.kind == "hold":
                return sec.a_pct
            if sec.kind == "ramp":
                frac = 0.0 if sec.dur_s <= 0 else min(1.0, tt / sec.dur_s)
                return sec.a_pct + (sec.b_pct - sec.a_pct) * frac
            return sec.a_pct + sum(
                a * math.sin(2.0 * math.pi * f * tt + ph)
                for f, a, ph in zip(sec.freqs_hz, sec.amps_pct,
                                    sec.phases_rad))
    return last.a_pct


# ---- per-run bookkeeping ---------------------------------------------------


@dataclass
class RunRecord:
    """What one completed run contributes to block_stats and to the
    weakest-finger weighting."""

    hand: str
    finger: int
    lane: int
    level: int
    scored_s: float
    tic_frac: float
    mae_pct: float
    press_mae_pct: float | None
    release_mae_pct: float | None
    stalls: int
    rings_collected: int
    rings_total: int
    section_mae: dict = field(default_factory=dict)


class ForcePilotMode:
    name = "Force Pilot"

    # A force reading older than this is a source dropout: scoring
    # pauses rather than judging a flat line the patient is not
    # producing (a few frames at 60 Hz).
    SAMPLE_STALE_S = 0.25
    # Outcome tiers on time-in-corridor. Design constants, not
    # published thresholds; the notebook re-scores offline anyway.
    GREAT_TIC = 0.8
    GOOD_TIC = 0.5
    # Rings start after the opening settle and stop just short of the
    # end so the last ring is scoreable.
    RING_LEAD_S = 2.0

    def __init__(self, engine: "GameEngine",
                 lanes_by_hand: dict[str, list[int]],
                 level: int,
                 corridor_hw_by_level: list[float],
                 freq_ceiling_by_level: list[float],
                 runs_per_finger: int,
                 min_finger_share: float,
                 span_pct: float,
                 base_pct: float,
                 plateau_pct: float,
                 ramp_rates_pct_s: list[float],
                 sine_amp_pct: float,
                 sine_s: float,
                 sos_amps_pct: list[float],
                 sos_s: float,
                 hold_in_s: float,
                 hold_top_s: float,
                 pre_assess_s: float,
                 visual_gain: float,
                 ring_interval_s: float,
                 ring_points: int,
                 exit_buzz_ms: float,
                 exit_buzz_cooldown_s: float,
                 promote_frac: float,
                 demote_frac: float,
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
        self.corridor_hw_by_level = [float(x) for x in corridor_hw_by_level]
        self.freq_ceiling_by_level = [float(x) for x in freq_ceiling_by_level]
        self.max_level = min(len(self.corridor_hw_by_level),
                             len(self.freq_ceiling_by_level))
        self.level = max(1, min(int(level), self.max_level))
        self.level_start = self.level
        self.span_pct = float(span_pct)
        self.base_pct = float(base_pct)
        self.plateau_pct = float(plateau_pct)
        self.ramp_rates_pct_s = [float(r) for r in ramp_rates_pct_s]
        self.sine_amp_pct = float(sine_amp_pct)
        self.sine_s = float(sine_s)
        self.sos_amps_pct = [float(a) for a in sos_amps_pct]
        self.sos_s = float(sos_s)
        self.hold_in_s = float(hold_in_s)
        self.hold_top_s = float(hold_top_s)
        self.pre_assess_s = float(pre_assess_s)
        self.visual_gain = float(visual_gain)
        self.ring_interval_s = max(0.5, float(ring_interval_s))
        self.ring_points = int(ring_points)
        self.exit_buzz_ms = float(exit_buzz_ms)
        self.exit_buzz_cooldown_s = float(exit_buzz_cooldown_s)
        self.promote_frac = float(promote_frac)
        self.demote_frac = float(demote_frac)
        self.probe_presses = max(2, int(probe_presses))
        self.probe_floor_counts = float(probe_floor_counts)
        self.probe_max_age_s = float(probe_max_age_s)
        self.announce_s = max(0.5, float(announce_s))
        self.rest_s = max(1.0, float(rest_s))
        self.score_cfg = score_cfg
        self.rng = random.Random(int(seed))
        self.demo = demo_trials is not None

        n_fingers = 4 * len(self.hand_names)
        self.total_runs = max(1, int(runs_per_finger)) * n_fingers
        if self.demo:
            # Test Mode: a couple of short runs so a supervisor demo
            # reaches Results inside a minute or two. The run SHAPE
            # stays intact (every section still appears) so the demo
            # shows the real thing, just compressed.
            self.total_runs = min(self.total_runs, max(1, int(demo_trials)))
            self.hold_in_s = min(self.hold_in_s, 1.2)
            self.hold_top_s = min(self.hold_top_s, 1.2)
            self.sine_s = min(self.sine_s, 3.0)
            self.sos_s = min(self.sos_s, 3.0)
            self.pre_assess_s = min(self.pre_assess_s, 1.0)
            self.rest_s = min(self.rest_s, 2.0)
            self.announce_s = min(self.announce_s, 1.5)
            self.probe_presses = 2
            # The fastest configured ramp keeps the demo run short.
            self.ramp_rates_pct_s = [max(self.ramp_rates_pct_s)]

        self.view = ForceView(engine)
        # Weakest-finger weighting: hands alternate on a balanced bag
        # (both hands get equal run counts), and within a hand the
        # floor-weighted scheduler gives struggling fingers extra runs
        # without starving any finger below its guaranteed share.
        self._hand_bag = BalancedScheduler(
            list(range(len(self.hand_names))), self.rng,
            avoid_repeats=False)
        self._finger_sched = {
            h: FloorWeightedScheduler(4, min_share=float(min_finger_share),
                                      rng=self.rng)
            for h in self.hand_names}
        self._mae_by_hf: dict[tuple[str, int], list[float]] = {}

        # Probe queue: every finger of every playing hand whose stored
        # session max is missing or stale. Order is hands as selected,
        # index to little within each hand.
        self._probe_queue: list[tuple[str, int]] = []
        self._probe_maxes: dict[str, list[float]] = {}
        profiles = getattr(engine, "calibration_profiles", None) or {}
        for hand in self.hand_names:
            if needs_max_press_probe(profiles.get(hand),
                                     max_age_s=self.probe_max_age_s):
                self._probe_maxes[hand] = [0.0] * 4
                self._probe_queue.extend((hand, f) for f in range(4))

        # Phase machine. Phases:
        #   no_input -> (nothing; the source cannot feed this mode)
        #   probe_gap -> probe (per finger) ... -> announce -> run ->
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

        # Run state (populated by _prepare_run).
        self.trial_counter = 0
        self.runs_done = 0
        self.hand: str = self.hand_names[0]
        self.finger: int = 0
        self.lane: int = self.hands[self.hand][0]
        self.run_seed: int = 0
        self.params: dict = {}
        self.sections: list[RunSection] = []
        self.duration_s: float = 0.0
        self.corridor_hw = self.corridor_hw_by_level[self.level - 1]
        self.run_t0: float | None = None
        self.active: PendingTrial | None = None
        self.ring_times: list[float] = []
        self.ring_state: list[bool | None] = []
        self.level_msg: str = ""
        self._last_result: dict | None = None
        self._level_trace: list[int] = [self.level]
        self._recent_tic: list[float] = []
        self._records: list[RunRecord] = []

        # Live readouts the screen draws from.
        self.target_now: float = self.base_pct
        self.force_pct_now: float | None = None
        self.craft_display_pct: float = self.base_pct
        self.in_corridor_now = False
        self.stalled = False
        self.signal_stale = False

        # Per-run scoring accumulators.
        self._sec_idx = 0
        self._scored_s = 0.0
        self._abs_err_int = 0.0
        self._in_c_s = 0.0
        self._sec_acc: dict[str, list[float]] = {}
        self._stalls = 0
        self._rings_collected = 0
        self._ring_idx = 0
        self._was_in = True
        self._last_buzz_t: float | None = None

    # ---- plumbing shared with the other modes ------------------------------
    def queue_press(self, ev) -> None:
        # Presses are not this mode's input; the continuous force is.
        # Swallowing them keeps the engine's shared press path happy.
        return

    def handle_event(self, e) -> None:
        # No keyboard fallback by design: a keyboard cannot produce a
        # continuous force signal (see the docstring's claim limits).
        return

    def on_resume(self, pause_dur: float) -> None:
        for attr in ("_t0", "_phase_until", "_last_tick"):
            v = getattr(self, attr)
            if v is not None:
                setattr(self, attr, v + pause_dur)
        if self.phase == "run":
            # A pause mid-run breaks the trace being scored: the target
            # would freeze while the hand did whatever it did. Restart
            # the same run (same seed, same plan); nothing was logged
            # for it yet, and the orphaned segment markers are tied off
            # by a run_restart event so the notebook can discard them.
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "run_restart", lane=self.lane,
                    detail=f"trial_id={self.trial_counter}",
                    hand=self.engine.hand_mode)
            self._enter_announce(time.perf_counter(), reuse_run=True)

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
        if self.phase in ("done", "no_input"):
            return
        if self.phase == "probe_gap":
            if self._phase_until is not None and now >= self._phase_until:
                self._enter_probe(now)
        elif self.phase == "probe":
            self._probe_frame(now)
        elif self.phase == "announce":
            if self._phase_until is not None and now >= self._phase_until:
                self._start_run(now)
        elif self.phase == "run":
            self._run_frame(now, dt)
        elif self.phase == "feedback":
            if self._phase_until is not None and now >= self._phase_until:
                self._next_run(now)

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
            self._prepare_run()
            self._enter_announce(now)

    # ---- max-press probes --------------------------------------------------
    def _enter_probe_gap(self, now: float) -> None:
        self.phase = "probe_gap"
        self.probe_hand, self.probe_finger = self._probe_queue[0]
        self._phase_until = now + 1.2
        # The hand is resting between probes: re-tare so the probe
        # measures counts above the actual resting level, not above
        # whatever drift the last press left behind.
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
            self._prepare_run()
            self._enter_announce(now)

    # ---- run selection and setup -------------------------------------------
    def _mean_mae(self, hand: str, finger: int) -> float | None:
        vals = self._mae_by_hf.get((hand, finger))
        if not vals:
            return None
        return sum(vals) / len(vals)

    def _prepare_run(self) -> None:
        """Pick the next hand and finger, then draw the run plan."""
        if self.bilateral:
            self.hand = self.hand_names[self._hand_bag.next()]
        else:
            self.hand = self.hand_names[0]
        weights = [self._mean_mae(self.hand, f) for f in range(4)]
        if any(w is not None and w > 0 for w in weights):
            use = [w if w is not None else 0.0 for w in weights]
            # A finger with no data yet weighs in at the current worst,
            # so it cannot be starved just for being unmeasured.
            worst = max(w for w in use)
            use = [w if w > 0 else worst for w in use]
        else:
            use = None
        self.finger = self._finger_sched[self.hand].next(use)
        self.lane = self.hands[self.hand][self.finger]
        self.trial_counter += 1
        self.run_seed = self.rng.randrange(2 ** 32)
        self._build_run_plan()

    def _finger_max_counts(self) -> float:
        profiles = getattr(self.engine, "calibration_profiles", None) or {}
        prof = profiles.get(self.hand)
        try:
            if prof is not None and prof.has_max_press():
                return float(prof.max_press[self.finger])
        except (AttributeError, IndexError, TypeError):
            pass
        return 0.0

    def _build_run_plan(self) -> None:
        self.corridor_hw = self.corridor_hw_by_level[self.level - 1]
        self.params = draw_run_params(
            seed=self.run_seed, level=self.level,
            freq_ceiling_hz=self.freq_ceiling_by_level[self.level - 1],
            corridor_hw_pct=self.corridor_hw, gain=self.visual_gain,
            span_pct=self.span_pct, base_pct=self.base_pct,
            plateau_pct=self.plateau_pct,
            ramp_rates_pct_s=self.ramp_rates_pct_s,
            sine_amp_pct=self.sine_amp_pct, sine_s=self.sine_s,
            sos_amps_pct=self.sos_amps_pct, sos_s=self.sos_s,
            hold_in_s=self.hold_in_s, hold_top_s=self.hold_top_s,
            pre_assess_s=self.pre_assess_s,
            max_press_counts=self._finger_max_counts())
        self.sections = sections_from_params(self.params)
        self.duration_s = run_duration_s(self.sections)
        self.ring_times = []
        t = self.RING_LEAD_S
        while t < self.duration_s - 0.5:
            self.ring_times.append(t)
            t += self.ring_interval_s
        self.ring_state = [None] * len(self.ring_times)

    def _enter_announce(self, now: float, reuse_run: bool = False) -> None:
        if not reuse_run:
            pass  # the run was prepared by the caller
        self.phase = "announce"
        self._phase_until = now + self.announce_s
        # Rest tare: the working hand is off the pads or resting during
        # the announcement, which is the moment to absorb drift.
        self.view.rebaseline([self.lane])
        self._reset_run_scoring()

    def _reset_run_scoring(self) -> None:
        self._sec_idx = 0
        self._scored_s = 0.0
        self._abs_err_int = 0.0
        self._in_c_s = 0.0
        self._sec_acc = {s.name: [0.0, 0.0, 0.0] for s in self.sections}
        self._stalls = 0
        self._rings_collected = 0
        self._ring_idx = 0
        self.ring_state = [None] * len(self.ring_times)
        self._was_in = True
        self._last_buzz_t = None
        self.run_t0 = None
        self.target_now = target_pct(self.sections, 0.0)
        self.craft_display_pct = self.target_now
        self.force_pct_now = None
        self.in_corridor_now = False
        self.stalled = False
        self.signal_stale = False

    def _start_run(self, now: float) -> None:
        self.phase = "run"
        self._phase_until = None
        self.run_t0 = now
        self.level_msg = ""
        self.active = PendingTrial(
            trial_id=self.trial_counter, lane=self.lane,
            stim_t_perf=now, keys_pressed=[], incorrect_presses=[])
        # No on_stim fires in this mode, so the per-trial stamps the
        # CSV row reads are set here: the corridor always names the
        # working finger (a tracking task must), and no RT censoring
        # window exists for a run.
        cues = self.engine.cue_settings()
        self.engine._last_cue_code = cues.code
        self.engine._last_target_shown = True
        self.engine._last_stim_timeout_ms = None
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "force_pilot_run", lane=self.lane, t_perf=now,
                detail=(f"trial_id={self.trial_counter};"
                        f"seed={self.run_seed};lvl={self.level};"
                        f"finger={self.finger + 1}"),
                hand=self.engine.hand_mode)
        self.engine.log_segment_start(self.sections[0].name,
                                      self.trial_counter, self.lane, now)

    # ---- the run itself ----------------------------------------------------
    def _advance_segments(self, t_run: float) -> None:
        """Cross section boundaries on the model clock, not the frame
        clock: markers carry run_t0 + boundary, so the logged bounds
        are exact even though the frame noticed them late."""
        while (self._sec_idx < len(self.sections)
               and t_run >= self.sections[self._sec_idx].end_s):
            sec = self.sections[self._sec_idx]
            t_mark = (self.run_t0 or 0.0) + sec.end_s
            self.engine.log_segment_end(sec.name, self.trial_counter,
                                        self.lane, t_mark)
            self._sec_idx += 1
            if self._sec_idx < len(self.sections):
                nxt = self.sections[self._sec_idx]
                self.engine.log_segment_start(nxt.name, self.trial_counter,
                                              self.lane, t_mark)

    def _run_frame(self, now: float, dt: float) -> None:
        if self.run_t0 is None:
            return
        t_run = now - self.run_t0
        self._advance_segments(t_run)
        if t_run >= self.duration_s:
            self._close_run(now)
            return
        self.target_now = target_pct(self.sections, t_run)
        reading = self.view.read(self.lane)
        age = self.view.sample_age_s(self.lane, now)
        self.signal_stale = (reading is None or reading.percent is None
                            or age is None or age > self.SAMPLE_STALE_S)
        if self.signal_stale:
            # Dropout: hold the craft, pause scoring, never stall-buzz
            # a signal the patient may well be producing.
            self.force_pct_now = None
            return
        pct = float(reading.percent)
        self._score_frame(t_run, pct, dt, now)

    def _score_frame(self, t_run: float, pct: float, dt: float,
                     now: float | None = None) -> None:
        """One scored frame: accumulate error, corridor time, section
        buckets, stalls and rings. Split out from _run_frame so the
        scoring can be driven with synthetic traces in tests."""
        target = target_pct(self.sections, t_run)
        self.target_now = target
        err = pct - target
        in_c = abs(err) <= self.corridor_hw
        self._scored_s += dt
        self._abs_err_int += abs(err) * dt
        if in_c:
            self._in_c_s += dt
        idx = min(self._sec_idx, len(self.sections) - 1)
        acc = self._sec_acc.get(self.sections[idx].name)
        if acc is not None:
            acc[0] += abs(err) * dt
            acc[1] += dt
            if in_c:
                acc[2] += dt
        if self._was_in and not in_c:
            self._stalls += 1
            self._exit_buzz(now if now is not None else t_run)
        self._was_in = in_c
        while (self._ring_idx < len(self.ring_times)
               and self.ring_times[self._ring_idx] <= t_run):
            self.ring_state[self._ring_idx] = in_c
            if in_c:
                self._rings_collected += 1
            self._ring_idx += 1
        self.force_pct_now = pct
        shown = target + self.visual_gain * err
        self.craft_display_pct = max(0.0, min(self.span_pct, shown))
        self.in_corridor_now = in_c
        self.stalled = not in_c

    def _exit_buzz(self, now: float) -> None:
        """Tactile error feedback on corridor exit. Rides the
        cue.buzz_after switch so a no-buzz block stays separable in
        the CSV, with a cooldown so a wobble along the corridor edge
        cannot turn into a motor drone."""
        cues = self.engine.cue_settings()
        if not cues.buzz_after:
            return
        if (self._last_buzz_t is not None
                and now - self._last_buzz_t < self.exit_buzz_cooldown_s):
            return
        self._last_buzz_t = now
        try:
            self.engine.pulse_motor(self.lane, self.exit_buzz_ms)
        except Exception as e:
            log.warning("exit buzz failed: %s", e)

    # ---- closing a run -----------------------------------------------------
    def _sec_mae(self, name: str) -> float | None:
        acc = self._sec_acc.get(name)
        if not acc or acc[1] <= 0:
            return None
        return acc[0] / acc[1]

    def _close_run(self, now: float) -> None:
        trial = self.active
        self.active = None
        scored = self._scored_s
        tic = (self._in_c_s / scored) if scored > 0 else 0.0
        mae = (self._abs_err_int / scored) if scored > 0 else 0.0
        press_mae = self._sec_mae("ramp_up")
        release_mae = self._sec_mae("release")
        section_mae = {n: self._sec_mae(n) for n in self._sec_acc}
        rings_total = len(self.ring_times)

        if tic >= self.GREAT_TIC:
            label, base = "Great", self.score_cfg.great_points
        elif tic >= self.GOOD_TIC:
            label, base = "Good", self.score_cfg.good_points
        else:
            label, base = "Miss", self.score_cfg.miss_points
        outcome = TrialResult(
            label=label,
            points=base + self._rings_collected * self.ring_points,
            rt_ms=None)

        rec = RunRecord(
            hand=self.hand, finger=self.finger, lane=self.lane,
            level=self.level, scored_s=scored, tic_frac=tic, mae_pct=mae,
            press_mae_pct=press_mae, release_mae_pct=release_mae,
            stalls=self._stalls, rings_collected=self._rings_collected,
            rings_total=rings_total, section_mae=section_mae)
        self._records.append(rec)
        if scored > 0:
            self._mae_by_hf.setdefault((self.hand, self.finger),
                                       []).append(mae)

        def _fmt(v):
            return "" if v is None else f"{v:.2f}"

        stimulus = (
            f"corridor;lvl={self.level};hand={self.hand};"
            f"finger={FINGER_WORDS[self.finger].lower()};"
            f"tic={tic:.3f};mae={mae:.2f};"
            f"press_mae={_fmt(press_mae)};release_mae={_fmt(release_mae)};"
            f"rings={self._rings_collected}/{rings_total};"
            f"stalls={self._stalls};scored_s={scored:.2f}")
        segments = [(s.name, (self.run_t0 or 0.0) + s.start_s,
                     (self.run_t0 or 0.0) + s.end_s)
                    for s in self.sections]
        info = ContinuousTrialLog(waveform="corridor", params=self.params,
                                  seed=self.run_seed, segments=segments)
        if trial is not None:
            self.engine.log_trial(trial, outcome, now, stimulus=stimulus,
                                  correct_lanes=[self.lane],
                                  continuous=info)

        self._last_result = {
            "label": label, "tic": tic, "mae": mae,
            "press_mae": press_mae, "release_mae": release_mae,
            "rings": self._rings_collected, "rings_total": rings_total,
            "stalls": self._stalls,
            "hand": self.hand, "finger": self.finger,
        }
        self.runs_done += 1
        self._move_level(tic)
        if self.runs_done >= self.total_runs:
            self._end("completed")
            return
        self.phase = "feedback"
        self._phase_until = now + self.rest_s
        self._prepare_run()

    def _move_level(self, tic: float) -> None:
        """Difficulty on the brief's two axes at once: the level index
        picks both the corridor half-width and the waveform bandwidth.
        Announced plainly (level_msg shows on the rest and announce
        screens) and logged, so no run's difficulty is ever implicit."""
        self._recent_tic.append(tic)
        moved = 0
        if (len(self._recent_tic) >= 2
                and min(self._recent_tic[-2:]) >= self.promote_frac
                and self.level < self.max_level):
            moved = 1
        elif tic < self.demote_frac and self.level > 1:
            moved = -1
        if not moved:
            return
        self.level += moved
        self._recent_tic.clear()
        self._level_trace.append(self.level)
        hw = self.corridor_hw_by_level[self.level - 1]
        word = "narrows" if moved > 0 else "widens"
        self.level_msg = (f"Corridor {word}: level {self.level} of "
                          f"{self.max_level} ({hw:.0f}% wide each side)")
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "force_pilot_level",
                detail=(f"level={self.level} hw_pct={hw} "
                        f"runs_done={self.runs_done}"),
                hand=self.engine.hand_mode)

    def _next_run(self, now: float) -> None:
        self._enter_announce(now)

    # ---- end of block ------------------------------------------------------
    def _end(self, reason: str) -> None:
        self.phase = "done"
        self.end_reason = reason
        # Next block this app session starts where this one ended,
        # like reaction's window level; a restart resets to config.
        self.engine._force_pilot_level = self.level
        self.engine.finish_block()

    # ---- block summary -----------------------------------------------------
    def block_stats(self) -> dict:
        """What finish_block folds into metadata.json, and what the
        results screen reads: per-finger tracking quality, the pooled
        per-section errors and the best section in plain words."""
        def _mean(vals):
            vals = [v for v in vals if v is not None]
            return round(sum(vals) / len(vals), 3) if vals else None

        per_lane: dict[str, dict] = {}
        for lane in sorted({r.lane for r in self._records}):
            rs = [r for r in self._records if r.lane == lane]
            per_lane[str(lane)] = {
                "runs": len(rs),
                "mae_pct": _mean([r.mae_pct for r in rs]),
                "time_in_corridor": _mean([r.tic_frac for r in rs]),
                "press_mae_pct": _mean([r.press_mae_pct for r in rs]),
                "release_mae_pct": _mean([r.release_mae_pct for r in rs]),
            }
        section_mae: dict[str, float | None] = {}
        for name in SECTION_LABELS:
            vals = [r.section_mae.get(name) for r in self._records]
            section_mae[name] = _mean(vals)
        best = None
        scored_secs = {n: v for n, v in section_mae.items()
                       if v is not None}
        if scored_secs:
            best = SECTION_LABELS[min(scored_secs, key=scored_secs.get)]
        return {
            "levels": {"start": self.level_start, "final": self.level,
                       "trace": list(self._level_trace)},
            "visual_gain": self.visual_gain,
            "hands": self.hand_names,
            "runs": len(self._records),
            "per_lane": per_lane,
            "overall": {
                "mae_pct": _mean([r.mae_pct for r in self._records]),
                "time_in_corridor": _mean([r.tic_frac
                                           for r in self._records]),
                "release_mae_pct": _mean([r.release_mae_pct
                                          for r in self._records]),
                "press_mae_pct": _mean([r.press_mae_pct
                                        for r in self._records]),
                "stalls": sum(r.stalls for r in self._records),
                "rings_collected": sum(r.rings_collected
                                       for r in self._records),
                "rings_total": sum(r.rings_total for r in self._records),
            },
            "section_mae_pct": section_mae,
            "best_section": best,
            "demo": self.demo,
            "end_reason": self.end_reason,
        }
