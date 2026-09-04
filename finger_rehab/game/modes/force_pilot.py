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
- runs of 13 to 16 s: shorter than the 20 to 30 s the pre-ladder plan
  used, because a run is now one shape rather than six, and twelve of
  them have to fit inside a battery block. Lodha held 20 s and
  Davidson tracked 32 s trials, so a single run is thinner for a
  spectral estimate than theirs; the notebook pools a level's runs
  across plays rather than reading one run's spectrum on its own.
- ramps at 4, 5 and 12 percent of max per second (Tide, Hills, Dunes):
  Naik 2011's lower rates for the climbs, with Dunes deliberately
  three times faster on the way down, since release is the half
  Davidson 2026 found impaired in Parkinson's.
- component frequencies 0.12 to 0.5 Hz: the Lodha analysis bands plus
  Davidson's 0.2 Hz tracking sine, and inside the tracking bandwidth
  argued in THE LADDER below. The multisine levels are non-harmonic
  so they cannot be predicted from one cycle, and every frequency,
  amplitude and phase is logged for exact offline reconstruction.
- corridor half-widths 8 / 6 / 5 / 4 percent across the ladder: the
  corridor is one of the four difficulty axes (Section THE LADDER
  below). A narrower corridor mechanically lowers time in corridor
  for the same tracking quality, so time in corridor is comparable
  WITHIN a level and never across levels; mean absolute error, RMSE
  and the force-target correlation are the across-level measures.
- no staircase. The ladder is fixed, so nothing promotes or demotes
  and no difficulty state carries between blocks. What replaced it is
  in THE LADDER below.
- visual gain 1.0 by default: gain magnifies the DISPLAYED error only
  (craft shows target + gain x error). Archer 2017 shows gain shifts
  patient error substantially, so it is a per-block config lever, is
  logged in every run's waveform_params, and must be held constant
  within any comparison.

THE LADDER. Twelve named waves in a fixed order, the same order for
every participant on every play, from a slow breath to an open-sea
storm. Basil's brief: familiar shapes from the world at the start,
harder as they go, and the same levels in the same order every time
so repeated play measures learning of THESE waves.

- Difficulty rises on four axes, and the table below names which axis
  each step turns: predictability (one sine, then ramps and steps,
  then a harmonic pair, then non-harmonic sums), top frequency (0.15
  up to 0.5 Hz), corridor width (8, 6, 5, 4 percent) and amplitude
  range (up to 31 percent of max).
- The top frequency is 0.5 Hz because that is where tracking of an
  UNPREDICTABLE target falls apart: visually guided force corrections
  are issued about once a second (Slifkin AB, Vaillancourt DE, Newell
  KM 2000, Journal of Neurophysiology 84(4):1708-1718) and the
  operator's effective delay on an unpredictable signal is 250 to
  350 ms (McRuer DT and Jex HR 1967, IEEE Transactions on Human
  Factors in Electronics HFE-8(3):231-249, cited through Drop FM et
  al 2016, IFAC-PapersOnLine 49(19):177-182). A predictable sine can
  be followed far higher because the mover generates the rhythm and
  synchronises to it (Cathers I, O'Dwyer N, Neilson P 1996,
  Experimental Brain Research 111(3):437-446), which is why the
  early, periodic levels are the easy ones and the multisines are the
  hard ones.
- The multisine levels are the standard way to build a target that
  cannot be memorised: non-harmonic components with fixed phases and
  amplitudes falling as 1/f, the coloured-noise force targets of
  Sosnoff JJ and Newell KM 2008, Journals of Gerontology Series B
  63(6):P344-P352.
- Level 12 (Uncharted) has the SAME statistics as level 11 (Storm)
  with its eight phases redrawn each block. That pair is the control
  that separates "learned these waves" from "got used to the pad":
  waveform-specific learning shows as improvement on the repeated
  target beyond the improvement on a novel target of matched
  difficulty (Yang L, Wan F, Nan W, Zhu F, Hu Y 2017, Scientific
  Reports 7:12333, which detected exactly that in a continuous
  tracking task; the variability-of-practice line behind it is Wulf G
  and Schmidt RA 1997, Journal of Experimental Psychology: Learning,
  Memory, and Cognition 23(4):987-1006). It is the one place the
  "identical every time" brief is deliberately broken, and the
  analysis says so.
- One run = one level = one finger, from a fixed finger table (index
  plays 4 levels including both storms, middle 3, ring 3, little 2).
  A per-finger result is therefore a (level, finger) result and is
  reported that way; the Storm / Uncharted pair is the same finger or
  the comparison would be a finger comparison.
- Step edges (Stairs) carry a grace window: the target jumps in zero
  time and the finger cannot, so the first step_grace_s after each
  edge is not scored at all. Scoring the jump would score reaction
  time, which Reaction mode already measures.

FLOW. Session max press probes run first (the shared foundation flow:
MaxPressProbe per finger, median of maximal presses, stored via
engine.record_max_press) for every playing hand whose stored max is
missing or older than six hours. Every force target afterwards is
percent of THAT number, never raw counts. Then the ladder: level 1 to
level 12, one run each, and in a both-hands block each level is flown
by the first hand then the second so the hand comparison is within a
level and the resting hand recovers while the other flies. Leaving
the corridor stalls the craft and buzzes the working finger; rings on
the centreline reward time-in-corridor.

Gaps are deliberately short (Basil's brief: not much time between
runs). One card of announce_s carries the last run's numbers and the
next wave's name, and the only other wait is one rest of mid_rest_s
after level 6. Massed practice with short rests is what the motor
learning literature uses for a task of this length (Lee TD and
Genovese ED 1988, Research Quarterly for Exercise and Sport
59(4):277-287, on massed versus distributed practice), and the
notebook's fatigue check (levels 7 to 9 against 4 to 6) is the
evidence that the dose held.

CUES AND CHANNELS. This mode never calls on_stim: there is no hidden
target to cue, because a visuomotor tracking task must show the
target (the corridor IS the stimulus), so cue.show_target does not
apply and every trial row records cue_target_shown TRUE. The corridor
exit buzz is tactile error feedback, not a target cue; it rides the
cue.buzz_after switch so a block run without it is distinguishable in
the CSV (cue_flags), and each buzz is delivered through
engine.pulse_motor, which logs a raw pulse_motor event per buzz.

LOGGING. One trial row per run. waveform is "corridor";
waveform_params carries the run's whole section list explicitly (one
group of keys per section: name, kind, duration, levels and every
oscillator component's frequency, amplitude and phase) plus the
header keys ladder, lvl, wave, pass, fixed, hw_pct, gain, span_pct,
base_pct, grace_s and max_press_counts. The notebook rebuilds the
target from that cell alone through sections_from_params, without
importing this module and without needing the seed. waveform_seed
still carries the block seed; only level 12's phases consume it, and
they are logged like every other number, so the row stays sufficient
on its own. Params from before the ladder (a seven-section
hold / ramp / hold / release / sine / approach / assessment plan with
no n_sec key) rebuild through the legacy branch, so old sessions
re-score unchanged. segment_times brackets every section in
raw-stream t_perf seconds under the wave's own section names, and
segment_start / segment_end events mark the same bounds inside
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

The ladder adds four limits of its own, and they belong next to any
result that uses it. "Familiar wave" is a naming device: no study has
measured whether a shape named after breathing or tides is easier
because it is familiar. What the literature supports is that
predictable, periodic, few-component targets are tracked better, and
the ladder is ordered on those properties, not on the names. A fixed
order confounds level with time on task: level 12 is always last and
always after 23 runs, so part of any level effect is fatigue and
attention; the mid rest and the notebook's fatigue check bound that,
they do not remove it. Time in corridor is not comparable across
levels, by construction. And per-finger conclusions across levels are
confounded with the finger table (index plays four rungs, little
two), so every per-finger number is reported per (level, finger).
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
from ..rest_skip import WaitSkip
from ..scoring import ScoreConfig, TrialResult
from .classic import PendingTrial

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


# On-screen finger names, matching the hand picker's "index to little".
FINGER_WORDS = ("INDEX", "MIDDLE", "RING", "LITTLE")

# LEGACY constants: the band floors and the run-length ceiling of the
# pre-ladder random plan. Kept because draw_run_params below is kept,
# and that is kept so sessions recorded before September 2026 still
# rebuild. The ladder uses neither.
SINE_FREQ_FLOOR_HZ = 0.2
SOS_FREQ_FLOOR_HZ = 0.1
RUN_CAP_S = 30.0

# Plain-words labels for the LEGACY seven-section plan (sessions
# recorded before the wave ladder). Ladder sections carry their own
# names; section_label() below handles both.
SECTION_LABELS = {
    "hold_in": "low hold",
    "ramp_up": "press ramp",
    "hold_top": "high hold",
    "release": "release ramp",
    "sine": "waves",
    "pre_assess": "approach",
    "assess_sos": "assessment",
}

# Plain words for the ladder's own section names. A name with a trailing
# repeat number ("beat2", "up1") falls back to its stem plus the number.
LADDER_SECTION_LABELS = {
    "settle": "settle",
    "low": "low water",
    "flood": "flood tide",
    "slack": "slack water",
    "ebb": "ebb tide",
    "low2": "low water",
    "breath": "breath",
    "swell": "swell",
    "s0": "bottom step",
    "s": "step",
    "up": "climb",
    "down": "descent",
    "waves": "waves",
    "rest0": "rest",
    "rest": "rest",
    "beat": "beat",
    "windward": "slow climb",
    "slipface": "fast drop",
    "end": "settle",
    "chop": "chop",
    "approach": "approach",
    "ocean": "open ocean",
    "storm": "storm",
    "uncharted": "uncharted water",
}


def section_label(name: str) -> str:
    """Plain words for a section name, for the results summary and the
    on-screen band. Ladder sections repeat with a trailing index
    (beat1, beat2...); those read as one label so 'best section' does
    not split a wave into its repeats."""
    text = str(name or "")
    if text in SECTION_LABELS:
        return SECTION_LABELS[text]
    if text in LADDER_SECTION_LABELS:
        return LADDER_SECTION_LABELS[text]
    stem = text.rstrip("0123456789")
    if stem in LADDER_SECTION_LABELS:
        return LADDER_SECTION_LABELS[stem]
    return text.replace("_", " ")


# ---- the wave ladder -------------------------------------------------------
# Fixed, in this order, for every participant on every play. The table
# lives in code and not in the yaml on purpose: a config edit must not
# be able to change the thesis levels quietly. Levels are written as
# offsets from the configured base_pct so the resting altitude stays
# one knob; at the shipped base of 8 percent the envelope runs 8 to
# about 31 percent of the finger's max press, inside the 0 to 40
# altitude span.

LADDER_ID = "waves_v1"

# The 1/f multisine that levels 11 and 12 fly: eight non-harmonic
# components from 0.08 to 0.50 Hz with amplitudes proportional to 1/f,
# summing to 12.01 percent. Hard-coded rather than regenerated from an
# RNG so the numbers in the thesis cannot move under a library change.
STORM_COMPONENTS = (
    (0.08, 3.78, 4.910),
    (0.13, 2.33, 1.698),
    (0.19, 1.59, 6.253),
    (0.25, 1.21, 4.978),
    (0.31, 0.98, 3.030),
    (0.37, 0.82, 1.541),
    (0.44, 0.69, 2.096),
    (0.50, 0.61, 3.172),
)
# Level 10: three non-harmonic components, fixed phases, same total
# amplitude as the storm so only the component count differs.
OCEAN_COMPONENTS = (
    (0.12, 6.0, 0.7),
    (0.29, 3.5, 3.9),
    (0.47, 2.5, 2.2),
)
# Level 12 redraws the storm's eight phases from the block seed. The
# constant keeps that draw off any other seed stream in the block.
UNCHARTED_SEED_XOR = 0x5A5A5A5A


@dataclass(frozen=True)
class WaveLevel:
    """One rung of the ladder. `finger` is 0 index to 3 little;
    `hw_pct` is the corridor half-width; `steps` marks a level whose
    target jumps between holds and therefore earns the step-edge
    grace window."""

    lvl: int
    slug: str
    name: str
    finger: int
    hw_pct: float
    coach: str
    steps: bool = False


LADDER: tuple[WaveLevel, ...] = (
    WaveLevel(1, "slow_breath", "Slow breath", 0, 8.0,
              "breathe with it"),
    WaveLevel(2, "tide", "Tide", 1, 8.0, "rise, hold, ease off"),
    WaveLevel(3, "swell", "Swell", 2, 8.0, "ride the swell"),
    WaveLevel(4, "stairs", "Stairs", 3, 6.0,
              "step up, settle, step down", steps=True),
    WaveLevel(5, "hills", "Hills", 0, 6.0, "up and over, twice"),
    WaveLevel(6, "beach_waves", "Beach waves", 1, 6.0,
              "keep the rhythm"),
    WaveLevel(7, "heartbeat", "Heartbeat", 2, 5.0, "squeeze on the beat"),
    WaveLevel(8, "dunes", "Dunes", 3, 5.0, "climb slowly, drop fast"),
    WaveLevel(9, "chop", "Chop", 1, 5.0, "two waves at once"),
    WaveLevel(10, "open_ocean", "Open ocean", 2, 4.0,
              "no pattern, just follow"),
    WaveLevel(11, "storm", "Storm", 0, 4.0, "hold your line"),
    WaveLevel(12, "uncharted", "Uncharted", 0, 4.0, "new water, same sea"),
)

LADDER_BY_LVL = {w.lvl: w for w in LADDER}


def _hold(name: str, dur: float, a: float) -> dict:
    return {"nm": name, "k": "h", "d": float(dur), "a": round(float(a), 4)}


def _ramp(name: str, dur: float, a: float, b: float) -> dict:
    return {"nm": name, "k": "r", "d": float(dur), "a": round(float(a), 4),
            "b": round(float(b), 4)}


def _osc(name: str, dur: float, mid: float, comps) -> dict:
    return {"nm": name, "k": "o", "d": float(dur), "a": round(float(mid), 4),
            "comps": tuple((float(f), float(m), round(float(p), 4))
                           for f, m, p in comps)}


def _trough_sine(name: str, dur: float, f: float, amp: float,
                 mid: float) -> dict:
    """One sine starting at its trough (phase -pi/2), so the wave opens
    at the level the section before it ended on and nothing jumps."""
    return _osc(name, dur, mid, ((f, amp, -math.pi / 2.0),))


def _pulse(name: str, width_s: float, lo: float, hi: float) -> dict:
    """One raised-cosine pulse from lo up to hi and back down over
    width_s: a single sine cycle starting and ending at its trough."""
    amp = (hi - lo) / 2.0
    return _osc(name, width_s, lo + amp,
                ((1.0 / width_s, amp, -math.pi / 2.0),))


def _multisine(name: str, dur: float, base: float, comps,
               approach_s: float = 1.0) -> list[dict]:
    """A sum-of-sines section plus the ramp that walks the target from
    the resting level to wherever the phases put the sum at t = 0, so
    the run still opens without a jump."""
    mid = round(base + sum(m for _f, m, _p in comps), 4)
    v0 = mid + sum(m * math.sin(p) for _f, m, p in comps)
    return [_ramp("approach", approach_s, base, v0),
            _osc(name, dur, mid, comps)]


def level_sections(level: WaveLevel, base_pct: float,
                   phases: tuple = ()) -> list[dict]:
    """The section specs for one ladder level, in plain dicts.

    Every level is built from the three section kinds the logging
    contract already carries (hold, ramp, osc), so the trial row
    rebuilds the target bit-exactly and the notebook re-scores it
    offline with no new maths. `phases` is used by level 12 only.
    """
    b = float(base_pct)
    slug = level.slug
    if slug == "slow_breath":
        # 0.15 Hz is a 6.7 s cycle: inside the slow-breathing range
        # reviewed by Russo MA, Santarelli DM, O'Rourke D (2017),
        # Breathe 13(4):298-309, which is why the coach line works.
        return [_hold("settle", 1.5, b),
                _trough_sine("breath", 13.3333, 0.15, 6.0, b + 6.0)]
    if slug == "tide":
        # 5 percent of max per second, the slower of the two ramp
        # rates Naik 2011 scored, up and back down again.
        return [_hold("low", 1.5, b),
                _ramp("flood", 4.0, b, b + 20.0),
                _hold("slack", 3.0, b + 20.0),
                _ramp("ebb", 4.0, b + 20.0, b),
                _hold("low2", 1.0, b)]
    if slug == "swell":
        return [_hold("settle", 1.0, b),
                _trough_sine("swell", 15.0, 0.2, 9.0, b + 9.0)]
    if slug == "stairs":
        # Six step edges, each holding 2.2 s. The first grace_s after
        # every edge is unscored (see grace_windows).
        treads = (6.0, 12.0, 18.0, 12.0, 6.0, 0.0)
        return [_hold("s0", 1.5, b)] + [
            _hold(f"s{i}", 2.2, b + off)
            for i, off in enumerate(treads, 1)]
    if slug == "hills":
        out = [_hold("settle", 1.0, b)]
        for i in (1, 2):
            out.append(_ramp(f"up{i}", 3.2, b, b + 16.0))
            out.append(_ramp(f"down{i}", 3.2, b + 16.0, b))
        return out
    if slug == "beach_waves":
        return [_hold("settle", 1.0, b),
                _trough_sine("waves", 12.0, 0.3333, 7.0, b + 7.0)]
    if slug == "heartbeat":
        # Four 2 s pulses with 1 s of rest between them: force pulses
        # rather than continuous tracking, the regime Vaillancourt DE
        # et al 2007 (NeuroImage 36(3):793-803) studied.
        out = [_hold("rest0", 1.5, b + 2.0)]
        for i in (1, 2, 3, 4):
            out.append(_pulse(f"beat{i}", 2.0, b + 2.0, b + 17.0))
            out.append(_hold(f"rest{i}", 1.0, b + 2.0))
        return out
    if slug == "dunes":
        # Slow rise (4 percent/s), fast release (12 percent/s): release
        # is the half Davidson 2026 found impaired in Parkinson's, and
        # here it is asked for three times faster than the climb.
        out = [_hold("settle", 1.0, b)]
        for i in (1, 2):
            out.append(_ramp(f"windward{i}", 4.5, b, b + 18.0))
            out.append(_ramp(f"slipface{i}", 1.5, b + 18.0, b))
        out.append(_hold("end", 1.0, b))
        return out
    if slug == "chop":
        # Harmonic pair (3:1), so the whole shape repeats every 6.67 s
        # and can still be learnt inside one run.
        return [_hold("settle", 1.0, b),
                _osc("chop", 13.3333, b + 9.0,
                     ((0.15, 6.0, -math.pi / 2.0),
                      (0.45, 3.0, -math.pi / 2.0)))]
    if slug == "open_ocean":
        return _multisine("ocean", 14.0, b, OCEAN_COMPONENTS)
    if slug == "storm":
        return _multisine("storm", 14.0, b, STORM_COMPONENTS)
    if slug == "uncharted":
        ph = tuple(phases) or tuple(p for _f, _m, p in STORM_COMPONENTS)
        comps = tuple((f, m, ph[i % len(ph)])
                      for i, (f, m, _p) in enumerate(STORM_COMPONENTS))
        return _multisine("uncharted", 14.0, b, comps)
    raise ValueError(f"unknown ladder level {slug!r}")


def uncharted_phases(block_seed: int, pass_idx: int = 1) -> tuple:
    """Level 12's eight phases: drawn from the block seed, logged with
    the run, and never the same two blocks running. Rounded to four
    decimals so the number in the CSV is exactly the number flown."""
    rng = random.Random((int(block_seed) ^ UNCHARTED_SEED_XOR)
                        + max(0, int(pass_idx) - 1))
    return tuple(round(rng.uniform(0.0, 2.0 * math.pi), 4)
                 for _ in STORM_COMPONENTS)


def params_from_level(level: WaveLevel, pass_idx: int, base_pct: float,
                      span_pct: float, gain: float,
                      max_press_counts: float, grace_s: float = 0.0,
                      phases: tuple = ()) -> dict:
    """The loggable params dict for one ladder run.

    The section list is written out key by key rather than left
    implicit in a generator, so the row rebuilds without this module
    and a level's maths can never drift away from what was flown: the
    mode itself flies sections_from_params(this dict).
    """
    secs = level_sections(level, base_pct, phases)
    p = {
        "ladder": LADDER_ID,
        "lvl": int(level.lvl),
        "wave": level.slug,
        "pass": int(pass_idx),
        "fixed": 0 if level.slug == "uncharted" else 1,
        "hw_pct": float(level.hw_pct),
        "gain": float(gain),
        "span_pct": float(span_pct),
        "base_pct": float(base_pct),
        "max_press_counts": float(max_press_counts),
        "grace_s": float(grace_s) if level.steps else 0.0,
        "n_sec": len(secs),
    }
    for i, s in enumerate(secs, 1):
        p[f"s{i}_nm"] = s["nm"]
        p[f"s{i}_k"] = s["k"]
        p[f"s{i}_d"] = float(s["d"])
        p[f"s{i}_a"] = float(s["a"])
        if s["k"] == "r":
            p[f"s{i}_b"] = float(s["b"])
        elif s["k"] == "o":
            comps = s["comps"]
            p[f"s{i}_n"] = len(comps)
            for j, (f, m, ph) in enumerate(comps, 1):
                p[f"s{i}_f{j}"] = float(f)
                p[f"s{i}_m{j}"] = float(m)
                p[f"s{i}_p{j}"] = float(ph)
    return p


# ---- pure trajectory generation --------------------------------------------
# The rule from the logging contract: the exact target the patient saw
# must be rebuildable offline. Three pure layers deliver that.
#   params_from_level(level, ...)  the flat dict logged as
#                                  waveform_params for one ladder rung.
#   sections_from_params(p)        deterministic plan from that dict;
#                                  the notebook carries a copy and
#                                  never needs the seed or this
#                                  module's rng.
#   target_pct(sections, t)        evaluates the target at any time.
# The mode plays sections_from_params(self.params), so what flew and
# what was logged cannot drift apart. draw_run_params below belongs to
# the pre-ladder plan and is kept only so sessions recorded before
# September 2026 still rebuild.


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
    """LEGACY: the pre-ladder run draw, kept so sessions recorded
    before September 2026 (and the tests that pin their rebuild) still
    produce the params dict those rows carry. The mode no longer calls
    it; params_from_level builds a ladder run.

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
    a hundredth of a percent of max).

    Two shapes. A ladder run carries n_sec and writes its sections out
    explicitly; a run recorded before the ladder (September 2026)
    carries the seven-section draw and is rebuilt by the legacy branch
    below, unchanged, so old sessions still re-score."""
    if "n_sec" in p:
        return _ladder_sections_from_params(p)
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


def _ladder_sections_from_params(p: dict) -> list[RunSection]:
    """Rebuild a ladder run's sections from the explicit key groups
    params_from_level wrote. Pure and self-contained: the notebook
    carries the same twenty lines."""
    out: list[RunSection] = []
    t = 0.0
    for i in range(1, int(round(float(p["n_sec"]))) + 1):
        name = str(p[f"s{i}_nm"])
        kind = str(p[f"s{i}_k"])
        dur = float(p[f"s{i}_d"])
        a = float(p[f"s{i}_a"])
        if kind == "r":
            out.append(RunSection(name=name, kind="ramp", start_s=t,
                                  dur_s=dur, a_pct=a,
                                  b_pct=float(p[f"s{i}_b"])))
        elif kind == "o":
            n = int(round(float(p[f"s{i}_n"])))
            out.append(RunSection(
                name=name, kind="osc", start_s=t, dur_s=dur, a_pct=a,
                freqs_hz=tuple(float(p[f"s{i}_f{j}"])
                               for j in range(1, n + 1)),
                amps_pct=tuple(float(p[f"s{i}_m{j}"])
                               for j in range(1, n + 1)),
                phases_rad=tuple(float(p[f"s{i}_p{j}"])
                                 for j in range(1, n + 1))))
        else:
            out.append(RunSection(name=name, kind="hold", start_s=t,
                                  dur_s=dur, a_pct=a))
        t += dur
    return out


def grace_windows(sections: list[RunSection],
                  grace_s: float) -> list[tuple[float, float]]:
    """Unscored windows after a step edge, as (start, end) run times.

    A step edge is a hold that follows a hold at a different level:
    the target moves in zero time and no finger can. Scoring that
    window would score reaction time, which Reaction mode measures
    properly, so it is dropped from time in corridor, from the error
    integral, from stall detection and from ring placement, in the
    game and again in the offline re-score. Derived from the sections
    alone, so the notebook finds the same windows from the same row.
    """
    if grace_s <= 0.0 or len(sections) < 2:
        return []
    out = []
    for prev, sec in zip(sections, sections[1:]):
        if (prev.kind == "hold" and sec.kind == "hold"
                and abs(sec.a_pct - prev.a_pct) > 1e-9):
            out.append((sec.start_s, sec.start_s + float(grace_s)))
    return out


def in_grace(windows: list[tuple[float, float]], t: float) -> bool:
    return any(a <= t < b for a, b in windows)


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
    """What one completed run contributes to block_stats. `level` is
    the ladder position and `wave` its slug; the pair is what the
    per-level tables and the notebook's learning curves group on."""

    hand: str
    finger: int
    lane: int
    level: int
    wave: str
    pass_idx: int
    scored_s: float
    tic_frac: float
    mae_pct: float
    press_mae_pct: float | None
    release_mae_pct: float | None
    stalls: int
    rings_collected: int
    rings_total: int
    section_mae: dict = field(default_factory=dict)


class ForcePilotMode(WaitSkip):
    name = "Force Pilot"
    # Which ladder this block flew. Stamped on block_stats so a later
    # ladder version can never be pooled with this one by accident.
    ladder_id = LADDER_ID

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
                 span_pct: float,
                 base_pct: float,
                 visual_gain: float,
                 ring_interval_s: float,
                 ring_points: int,
                 exit_buzz_ms: float,
                 exit_buzz_cooldown_s: float,
                 probe_presses: int,
                 probe_floor_counts: float,
                 probe_max_age_s: float,
                 announce_s: float,
                 mid_rest_s: float,
                 step_grace_s: float,
                 passes: int,
                 score_cfg: ScoreConfig,
                 seed: int = 0,
                 demo_trials: int | None = None,
                 demo_levels: list[int] | None = None,
                 levels: list[int] | None = None,
                 hand_order: list[str] | None = None
                 ) -> None:
        self.engine = engine
        self.hands = {h: list(v)[:4] for h, v in lanes_by_hand.items() if v}
        if not self.hands:
            self.hands = {"right": [0, 1, 2, 3]}
        self.hand_names = list(self.hands)
        self.span_pct = float(span_pct)
        self.base_pct = float(base_pct)
        self.visual_gain = float(visual_gain)
        self.ring_interval_s = max(0.5, float(ring_interval_s))
        self.ring_points = int(ring_points)
        self.exit_buzz_ms = float(exit_buzz_ms)
        self.exit_buzz_cooldown_s = float(exit_buzz_cooldown_s)
        self.probe_presses = max(2, int(probe_presses))
        self.probe_floor_counts = float(probe_floor_counts)
        self.probe_max_age_s = float(probe_max_age_s)
        self.announce_s = max(0.5, float(announce_s))
        self.mid_rest_s = max(0.0, float(mid_rest_s))
        self.step_grace_s = max(0.0, float(step_grace_s))
        self.passes = max(1, int(passes))
        self.score_cfg = score_cfg
        # The block seed, logged on every run. Only level 12 spends it.
        self.seed = int(seed)
        self.demo = demo_trials is not None

        # The ladder for this block. Fixed order, fixed fingers; the
        # only thing a caller may change is WHICH rungs play, and only
        # Test Mode and the tests do that.
        wanted = list(levels) if levels else None
        if wanted is None and self.demo:
            wanted = list(demo_levels or [1, 4, 7, 12])
        self.levels: list[WaveLevel] = [
            LADDER_BY_LVL[int(n)] for n in (wanted or [w.lvl for w in LADDER])
            if int(n) in LADDER_BY_LVL]
        if not self.levels:
            self.levels = list(LADDER)
        # Hand order inside a level: the study's first hand flies, then
        # the other. Same order every play for one participant, so the
        # hand comparison is within a level and the resting hand
        # recovers while the other works.
        self.hand_order = [h for h in (hand_order or self._study_hand_order())
                           if h in self.hands]
        if not self.hand_order:
            self.hand_order = list(self.hand_names)
        if self.demo:
            # Test Mode: four rungs on one hand so a supervisor demo
            # reaches Results inside a couple of minutes. The waves
            # themselves are untouched, so the demo shows the real
            # thing rather than a compressed imitation of it.
            self.hand_order = self.hand_order[:1]
            self.announce_s = min(self.announce_s, 1.0)
            self.mid_rest_s = 0.0
            self.probe_presses = 2

        # The whole block as a list of runs, decided here and never
        # touched again: (ladder level, hand, pass). Nothing adapts,
        # so the plan a participant flies is the plan every other
        # participant flies.
        self._plan: list[tuple[WaveLevel, str, int]] = []
        for p_idx in range(1, self.passes + 1):
            for lvl in self.levels:
                for hand in self.hand_order:
                    self._plan.append((lvl, hand, p_idx))
        if self.demo and demo_trials is not None:
            self._plan = self._plan[:max(1, int(demo_trials))]
        self.total_runs = len(self._plan)
        # One rest, halfway through each pass, plus one between passes.
        # Everything else is a 1.8 s card: Basil asked for little time
        # between runs, and the fingers rotate through the ladder
        # anyway, so no one finger works twice in a row for long.
        per_pass = len(self.levels) * len(self.hand_order)
        self._rest_after: set[int] = set()
        if self.mid_rest_s > 0:
            for p_idx in range(self.passes):
                start = p_idx * per_pass
                half = start + (len(self.levels) // 2) * len(self.hand_order)
                if 0 < half < len(self._plan):
                    self._rest_after.add(half - 1)
                if p_idx + 1 < self.passes:
                    self._rest_after.add(start + per_pass - 1)
        # Level 12's phases, drawn once per pass from the block seed
        # and logged with the run. Everything else in the ladder is
        # identical every block.
        self._uncharted_phases = {
            p_idx: uncharted_phases(self.seed, p_idx)
            for p_idx in range(1, self.passes + 1)}
        # What this block flew, worked out once: block_stats stamps it
        # on the session so a later ladder version can never be pooled
        # with this one, and the results screen reads it per frame.
        self.ladder_info = {
            "id": LADDER_ID,
            "passes": self.passes,
            "hand_order": list(self.hand_order),
            "levels": [
                {"lvl": w.lvl, "wave": w.slug, "name": w.name,
                 "finger": w.finger, "hw_pct": w.hw_pct,
                 "dur_s": round(run_duration_s(sections_from_params(
                     params_from_level(
                         w, 1, self.base_pct, self.span_pct,
                         self.visual_gain, 0.0,
                         grace_s=self.step_grace_s,
                         phases=self._uncharted_phases[1]))), 4)}
                for w in self.levels],
        }

        self.view = ForceView(engine)

        # Probe queue: every finger of every playing hand whose stored
        # session max is missing or stale. Order is hands as selected,
        # index to little within each hand.
        self._probe_queue: list[tuple[str, int]] = []
        self._probe_maxes: dict[str, list[float]] = {}
        profiles = getattr(engine, "calibration_profiles", None) or {}
        # The participant name makes the staleness gate an identity
        # gate too: a stored max from another patient (skip-path
        # inheritance of the on-disk profile) must be re-probed, or
        # every percent target in this block is a percentage of
        # somebody else's strength.
        who = str(getattr(getattr(engine, "session", None),
                          "participant", "") or "")
        token = getattr(engine, "_session_token", None)
        for hand in self.hand_names:
            if needs_max_press_probe(profiles.get(hand),
                                     max_age_s=self.probe_max_age_s,
                                     participant=who,
                                     session_token=token):
                self._probe_maxes[hand] = [0.0] * 4
                self._probe_queue.extend((hand, f) for f in range(4))

        # Phase machine. Phases:
        #   no_input -> (nothing; the source cannot feed this mode)
        #   probe_gap -> probe (per finger) ... -> announce -> run ->
        #   announce -> run ... -> rest (once) -> ... -> done
        # "announce" is one card carrying both halves of the old pair:
        # how the run just flown went, and which wave comes next.
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
        self.hand: str = self.hand_order[0]
        self.finger: int = self.levels[0].finger
        self.lane: int = self.hands[self.hand][self.finger]
        self.run_seed: int = self.seed
        self.params: dict = {}
        self.sections: list[RunSection] = []
        self.duration_s: float = 0.0
        # The rung playing right now, mirrored as scalars because the
        # screen and the trial row read them that way.
        self.wave: WaveLevel = self.levels[0]
        self.level: int = self.wave.lvl
        self.pass_idx: int = 1
        self.corridor_hw = self.wave.hw_pct
        self.grace: list[tuple[float, float]] = []
        self._plan_idx = -1
        self._next_idx = 0
        self.run_t0: float | None = None
        self.active: PendingTrial | None = None
        self.ring_times: list[float] = []
        self.ring_state: list[bool | None] = []
        self._last_result: dict | None = None
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
        # Signal-starved runs: total for block_stats, and the
        # consecutive streak that decides when a slot is given up.
        self._no_signal_runs = 0
        self._no_signal_streak = 0
        self._abs_err_int = 0.0
        self._in_c_s = 0.0
        self._grace_s = 0.0
        self._sec_acc: dict[str, list[float]] = {}
        # Ramp error split by direction, not by section name: every
        # ramp level (Tide, Hills, Dunes) feeds the same two buckets,
        # so press and release stay comparable across the ladder.
        self._press_acc = [0.0, 0.0]
        self._release_acc = [0.0, 0.0]
        self._stalls = 0
        self._rings_collected = 0
        self._ring_idx = 0
        self._was_in = True
        self._last_buzz_t: float | None = None

    # ---- who flies first ---------------------------------------------------
    def _study_hand_order(self) -> list[str]:
        """Hand order inside a level: the study's first hand, then the
        other. The battery's counterbalancing cell decides which hand
        that is (data/intake.cell_for against the login's main hand),
        so a participant's order is the same every play and matches
        the order the rest of the battery used. No main hand on the
        login means the hands play as selected."""
        if len(self.hand_names) < 2:
            return list(self.hand_names)
        sess = getattr(self.engine, "session", None)
        dom = str(getattr(sess, "dominant_hand", "") or "").strip().lower()
        if dom not in ("left", "right"):
            return list(self.hand_names)
        try:
            from ...data.intake import cell_for
            first_word = str(cell_for(
                str(getattr(sess, "participant", "") or ""))["hand_first"])
        except Exception:
            first_word = "dominant"
        other = "left" if dom == "right" else "right"
        first = dom if first_word == "dominant" else other
        return [first, "left" if first == "right" else "right"]

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
        elif self.phase == "rest":
            if self._phase_until is not None and now >= self._phase_until:
                self._after_mid_rest(now)

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
        # Pure pacing between max-press probes; the tare below is what
        # the gap is for, and it lands the moment the gap opens.
        self.arm_wait("gap", self._phase_until, self._enter_probe,
                      started_at=now)
        # The hand is resting between probes: re-tare so the probe
        # measures counts above the actual resting level, not above
        # whatever drift the last press left behind.
        self.view.rebaseline([self.hands[self.probe_hand]
                              [self.probe_finger]])

    # A probe finger that banks nothing for this long ends the block
    # gently instead of sitting on MAX PRESS CHECK forever: the probe
    # state machine only leaves rest/press on force crossings, so a
    # finger that cannot reach the floor (or a dead pad) used to hang
    # the block with Esc-abandon as the only exit.
    PROBE_STALL_S = 25.0

    # A probed max under this many multiples of the floor makes the
    # whole 0-40% target span comparable to sensor noise: the block
    # would be unplayable and read as severe impairment. Warned and
    # logged so the researcher can reposition the pad.
    LOW_MAX_FLOOR_MULT = 5.0

    def _enter_probe(self, now: float) -> None:
        self.clear_wait()
        self.phase = "probe"
        self._phase_until = None
        self.probe = MaxPressProbe(n_presses=self.probe_presses,
                                   floor_counts=self.probe_floor_counts)
        self.probe_counts = 0.0
        self._probe_progress_t = now
        self._probe_banked_seen = 0

    def _probe_frame(self, now: float) -> None:
        lane = self.hands[self.probe_hand][self.probe_finger]
        reading = self.view.read(lane)
        self.signal_waiting = reading is None
        if reading is None or self.probe is None:
            return
        self.probe_counts = reading.counts
        self.probe.update(now, reading.counts)
        if self.probe.state != "done":
            banked = len(self.probe.peaks)
            if banked != getattr(self, "_probe_banked_seen", 0):
                self._probe_banked_seen = banked
                self._probe_progress_t = now
            if (now - (getattr(self, "_probe_progress_t", now) or now)
                    > self.PROBE_STALL_S):
                log.warning(
                    "max-press probe stalled on %s finger %d (no attempt "
                    "banked for %.0f s); ending the block gently",
                    self.probe_hand, self.probe_finger,
                    self.PROBE_STALL_S)
                self._end("probe_timeout")
            return
        result = self.probe.result() or 0.0
        if result < self.LOW_MAX_FLOOR_MULT * self.probe_floor_counts:
            log.warning(
                "probed max for %s finger %d is only %.0f counts "
                "(under %.0fx the %.0f-count floor): percent targets "
                "sit inside sensor noise; check the pad placement",
                self.probe_hand, self.probe_finger, result,
                self.LOW_MAX_FLOOR_MULT, self.probe_floor_counts)
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "max_press_low", lane=lane,
                    detail=(f"hand={self.probe_hand};"
                            f"finger={self.probe_finger};"
                            f"max_counts={result:.1f};"
                            f"floor_counts={self.probe_floor_counts:.1f}"),
                    hand=self.probe_hand)
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
    def _prepare_run(self) -> None:
        """Take the next rung off the fixed plan and build its run.

        No choosing happens here any more: the level, its finger, its
        corridor and the hand were all decided when the block opened,
        so two participants on the same hand selection fly the same
        24 runs in the same order."""
        idx = min(self._next_idx, len(self._plan) - 1)
        self._plan_idx = idx
        self._next_idx = idx + 1
        wave, hand, pass_idx = self._plan[idx]
        self.wave = wave
        self.level = wave.lvl
        self.pass_idx = pass_idx
        self.hand = hand if hand in self.hands else self.hand_names[0]
        self.finger = wave.finger
        self.lane = self.hands[self.hand][self.finger]
        self.trial_counter += 1
        # The seed is the block's, logged once; only level 12 spends
        # it, and the phases it drew ride the row like every other
        # number so the seed is never needed to rebuild a target.
        self.run_seed = self.seed
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
        self.corridor_hw = self.wave.hw_pct
        self.params = params_from_level(
            self.wave, self.pass_idx, base_pct=self.base_pct,
            span_pct=self.span_pct, gain=self.visual_gain,
            max_press_counts=self._finger_max_counts(),
            grace_s=self.step_grace_s,
            phases=self._uncharted_phases.get(self.pass_idx, ()))
        # The mode flies exactly what it logged: the sections come
        # back out of the params dict, not from the table directly.
        self.sections = sections_from_params(self.params)
        self.duration_s = run_duration_s(self.sections)
        self.grace = grace_windows(self.sections,
                                   float(self.params.get("grace_s", 0.0)))
        self.ring_times = []
        t = self.RING_LEAD_S
        while t < self.duration_s - 0.5:
            # No ring inside a step-edge grace window: the window is
            # not scored, so a checkpoint sitting in it would reward
            # or punish nothing.
            if not in_grace(self.grace, t):
                self.ring_times.append(t)
            t += self.ring_interval_s
        self.ring_state = [None] * len(self.ring_times)

    def _enter_announce(self, now: float, reuse_run: bool = False) -> None:
        """The one card between runs: how the last run went and which
        wave is next. Announce and feedback used to be two cards
        totalling 12.5 s; the brief asked for little time between
        runs, so they are one card of announce_s (1.8 s shipped) and
        the only other wait in the block is the mid-ladder rest. The
        card is still long enough for the rest tare below, which the
        notebook reads from 1.0 s to 0.05 s before a run starts."""
        if not reuse_run:
            pass  # the run was prepared by the caller
        self.phase = "announce"
        self._phase_until = now + self.announce_s
        # Skippable: the tare runs on entry, not over the card's
        # lifetime, so shortening the card takes nothing from the run.
        self.arm_wait("announce", self._phase_until, self._start_run,
                      started_at=now)
        # Rest tare: the working hand is off the pads or resting during
        # the announcement, which is the moment to absorb drift.
        self.view.rebaseline([self.lane])
        self._reset_run_scoring()

    def _enter_mid_rest(self, now: float) -> None:
        """The one real rest in the block, halfway up the ladder (and
        between passes when a block runs the ladder twice). Long
        enough to draw the skip chip, which the 1.8 s cards are not:
        somebody who wants to keep going can, and the skip is counted
        in block_stats like every other."""
        self.phase = "rest"
        self._phase_until = now + self.mid_rest_s
        self.arm_wait("rest", self._phase_until, self._after_mid_rest,
                      started_at=now)
        self.view.rebaseline([self.lane])

    def _after_mid_rest(self, now: float) -> None:
        self.clear_wait()
        self._enter_announce(now)

    def _reset_run_scoring(self) -> None:
        self._sec_idx = 0
        self._scored_s = 0.0
        self._abs_err_int = 0.0
        self._in_c_s = 0.0
        self._grace_s = 0.0
        self._sec_acc = {s.name: [0.0, 0.0, 0.0] for s in self.sections}
        self._press_acc = [0.0, 0.0]
        self._release_acc = [0.0, 0.0]
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
        self.clear_wait()
        self.phase = "run"
        self._phase_until = None
        self.run_t0 = now
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
                        f"wave={self.wave.slug};pass={self.pass_idx};"
                        f"hand={self.hand};finger={self.finger + 1}"),
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
            # a signal the patient may well be producing. Rings due
            # DURING the dropout still need to be retired here as
            # unjudged (no points): leaving _ring_idx untouched let
            # every ring inside the gap get judged in one shot on the
            # first frame after recovery, using that single frame's
            # in-corridor state, which could bank several rings' worth
            # of points for a stretch with no force signal at all
            # (audit finding #81). This does not touch _scored_s /
            # _in_c_s, so time-in-corridor is unaffected by the gap.
            self._gutter_due_rings(t_run)
            self.force_pct_now = None
            return
        pct = float(reading.percent)
        self._score_frame(t_run, pct, dt, now)

    def _gutter_due_rings(self, t_run: float) -> None:
        """Retire every ring whose pass-time has arrived without
        judging it in-corridor: used while the signal is stale, where
        there is no reading to score a ring against."""
        while (self._ring_idx < len(self.ring_times)
               and self.ring_times[self._ring_idx] <= t_run):
            self.ring_state[self._ring_idx] = False
            self._ring_idx += 1

    def _score_frame(self, t_run: float, pct: float, dt: float,
                     now: float | None = None) -> None:
        """One scored frame: accumulate error, corridor time, section
        buckets, stalls and rings. Split out from _run_frame so the
        scoring can be driven with synthetic traces in tests."""
        target = target_pct(self.sections, t_run)
        self.target_now = target
        err = pct - target
        in_c = abs(err) <= self.corridor_hw
        idx = min(self._sec_idx, len(self.sections) - 1)
        if in_grace(self.grace, t_run):
            # Step-edge grace: the target has just jumped and the
            # finger physically cannot be there yet. Nothing about
            # this window is scored -- no corridor time, no error, no
            # stall, no buzz -- and the same window is dropped again
            # in the offline re-score. _was_in stays True so the first
            # frame AFTER the window that is still outside counts as
            # a fresh stall rather than being swallowed.
            self._grace_s += dt
            self._was_in = True
            self.force_pct_now = pct
            shown = target + self.visual_gain * err
            self.craft_display_pct = max(0.0, min(self.span_pct, shown))
            self.in_corridor_now = in_c
            self.stalled = False
            return
        self._scored_s += dt
        self._abs_err_int += abs(err) * dt
        if in_c:
            self._in_c_s += dt
        sec = self.sections[idx]
        if sec.kind == "ramp":
            bucket = (self._press_acc if sec.b_pct >= sec.a_pct
                      else self._release_acc)
            bucket[0] += abs(err) * dt
            bucket[1] += dt
        acc = self._sec_acc.get(sec.name)
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
        # The EEG spec's 141 for this mode is DEFINED as the corridor-
        # exit buzz (negative feedback onset for FRN work). pulse_motor
        # has no marker hook, and the engine's generic trial-close
        # feedback markers are suppressed for continuous rows, so the
        # mode emits it here, gated the same way as every other
        # feedback marker.
        if getattr(self.engine, "_eeg_feedback_markers", False):
            try:
                from ...hardware import eeg_trigger
                self.engine._eeg_send(
                    eeg_trigger.CODES["feedback_negative"], t_event=now)
            except Exception as e:
                log.warning("exit-buzz EEG marker failed: %s", e)
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

    @staticmethod
    def _bucket_mae(acc: list[float]) -> float | None:
        return (acc[0] / acc[1]) if acc and acc[1] > 0 else None

    def _close_run(self, now: float) -> None:
        trial = self.active
        self.active = None
        scored = self._scored_s
        # Coverage floor: a run whose force signal covered under half
        # the plan is hardware evidence, not tracking. Scoring it fell
        # back to tic=0 / mae=0.0, which read as a PERFECT error in
        # the per-finger tables, showed the patient 'ROUGH RIDE ...
        # Mean error 0.0% of max', and demoted the staircase because
        # the device dropped, not because the patient tracked badly.
        plan_s = float(self.duration_s or 0.0)
        if plan_s > 0 and scored < 0.5 * plan_s:
            self._close_run_no_signal(trial, now, scored, plan_s)
            return
        self._no_signal_streak = 0
        tic = (self._in_c_s / scored) if scored > 0 else 0.0
        mae = (self._abs_err_int / scored) if scored > 0 else 0.0
        press_mae = self._bucket_mae(self._press_acc)
        release_mae = self._bucket_mae(self._release_acc)
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
            level=self.level, wave=self.wave.slug, pass_idx=self.pass_idx,
            scored_s=scored, tic_frac=tic, mae_pct=mae,
            press_mae_pct=press_mae, release_mae_pct=release_mae,
            stalls=self._stalls, rings_collected=self._rings_collected,
            rings_total=rings_total, section_mae=section_mae)
        self._records.append(rec)

        def _fmt(v):
            return "" if v is None else f"{v:.2f}"

        stimulus = (
            f"corridor;lvl={self.level};wave={self.wave.slug};"
            f"pass={self.pass_idx};hand={self.hand};"
            f"finger={FINGER_WORDS[self.finger].lower()};"
            f"tic={tic:.3f};mae={mae:.2f};"
            f"press_mae={_fmt(press_mae)};release_mae={_fmt(release_mae)};"
            f"rings={self._rings_collected}/{rings_total};"
            f"stalls={self._stalls};scored_s={scored:.2f};"
            f"grace_s={self._grace_s:.2f}")
        segments = [(s.name, (self.run_t0 or 0.0) + s.start_s,
                     (self.run_t0 or 0.0) + s.end_s)
                    for s in self.sections]
        info = ContinuousTrialLog(waveform="corridor", params=self.params,
                                  seed=self.run_seed, segments=segments)
        if trial is not None:
            # A Miss here means the run played to completion and time
            # in corridor came in under GOOD_TIC -- nothing timed out,
            # there is no stim deadline in a continuous tracking run,
            # and the row's own timeout_ms stays empty. The engine's
            # generic "no incorrect press -> timeout" derivation would
            # otherwise mislabel every low-tracking run this way, which
            # pulls clean-but-poor runs into cross-mode error_type=
            # "timeout" filters that mean "no press before the
            # deadline". This mode has no wrong-finger concept either,
            # so the override is unconditional, not just for Miss.
            self.engine.log_trial(trial, outcome, now, stimulus=stimulus,
                                  correct_lanes=[self.lane],
                                  continuous=info,
                                  error_type=("low_tracking"
                                              if label == "Miss" else None))

        self._last_result = {
            "label": label, "tic": tic, "mae": mae,
            "press_mae": press_mae, "release_mae": release_mae,
            "rings": self._rings_collected, "rings_total": rings_total,
            "stalls": self._stalls,
            "hand": self.hand, "finger": self.finger,
            "level": self.level, "wave": self.wave.name,
        }
        self.runs_done += 1
        if self.runs_done >= self.total_runs:
            self._end("completed")
            return
        rest_due = self._plan_idx in self._rest_after
        self._prepare_run()
        if rest_due:
            self._enter_mid_rest(now)
        else:
            self._enter_announce(now)

    # How many consecutive signal-starved closes of the same run slot
    # replay it before the slot is abandoned. Keeps a permanently dead
    # device from looping one run forever while still giving a brief
    # glitch a second chance.
    MAX_NO_SIGNAL_RETRIES = 2

    def _close_run_no_signal(self, trial, now: float, scored: float,
                             plan_s: float) -> None:
        """Close a signal-starved run as hardware loss: its own
        error_type, no RunRecord (so no per-level MAE dilution), and
        the run replays like a pause restart. After
        MAX_NO_SIGNAL_RETRIES consecutive starved closes the rung is
        given up, the ladder moves on, and the gap shows in the
        notebook as a missing level rather than as bad tracking."""
        stimulus = (
            f"corridor;lvl={self.level};wave={self.wave.slug};"
            f"pass={self.pass_idx};hand={self.hand};"
            f"finger={FINGER_WORDS[self.finger].lower()};"
            f"tic=;mae=;press_mae=;release_mae=;rings=0/0;"
            f"stalls={self._stalls};scored_s={scored:.2f};"
            f"grace_s={self._grace_s:.2f};"
            f"plan_s={plan_s:.2f};no_signal=True")
        segments = [(s.name, (self.run_t0 or 0.0) + s.start_s,
                     (self.run_t0 or 0.0) + s.end_s)
                    for s in self.sections]
        info = ContinuousTrialLog(waveform="corridor", params=self.params,
                                  seed=self.run_seed, segments=segments)
        outcome = TrialResult(label="Miss", points=0, rt_ms=None)
        if trial is not None:
            self.engine.log_trial(trial, outcome, now, stimulus=stimulus,
                                  correct_lanes=[self.lane],
                                  continuous=info,
                                  error_type="no_signal")
        self._no_signal_runs += 1
        self._no_signal_streak += 1
        self._last_result = {
            "label": "NoSignal", "tic": None, "mae": None,
            "press_mae": None, "release_mae": None,
            "rings": 0, "rings_total": 0, "stalls": self._stalls,
            "hand": self.hand, "finger": self.finger,
            "level": self.level, "wave": self.wave.name,
        }
        if self._no_signal_streak <= self.MAX_NO_SIGNAL_RETRIES:
            # Replay the same rung (same level, same phases), like the
            # pause path: the slot produced no evidence yet.
            self._enter_announce(now, reuse_run=True)
            return
        # Give the rung up and move the ladder on.
        self._no_signal_streak = 0
        self.runs_done += 1
        if self.runs_done >= self.total_runs:
            self._end("completed")
            return
        rest_due = self._plan_idx in self._rest_after
        self._prepare_run()
        if rest_due:
            self._enter_mid_rest(now)
        else:
            self._enter_announce(now)

    # ---- end of block ------------------------------------------------------
    def _end(self, reason: str) -> None:
        self.phase = "done"
        self.end_reason = reason
        # Nothing carries between blocks any more. The ladder is fixed,
        # so a second block is the same twelve waves in the same order,
        # which is the whole point: play index, not difficulty state,
        # is what changes between plays. The engine still clears
        # _force_pilot_levels on a session end; leaving it empty here
        # keeps a stale carry from an older build out of a new block.
        self.engine._force_pilot_levels = {}
        self.engine.finish_block()

    # ---- block summary -----------------------------------------------------
    def block_stats(self) -> dict:
        """What finish_block folds into metadata.json, and what the
        results screen reads: per-finger and per-level tracking
        quality, the pooled per-section errors and the best section in
        plain words.

        Everything is broken out by ladder level as well as by lane. A
        run at level 1 and a run at level 12 are not the same
        measurement: the corridor is twice as wide at the bottom of
        the ladder, so time in corridor falls as the ladder climbs
        whether or not tracking got worse. `ladder` records which
        rungs this block ran and in which hand order, so a later
        ladder version can never be pooled with this one by accident."""
        def _mean(vals):
            vals = [v for v in vals if v is not None]
            return round(sum(vals) / len(vals), 3) if vals else None

        per_lane: dict[str, dict] = {}
        for lane in sorted({r.lane for r in self._records}):
            rs = [r for r in self._records if r.lane == lane]
            by_level: dict[str, dict] = {}
            for lvl in sorted({r.level for r in rs}):
                lrs = [r for r in rs if r.level == lvl]
                by_level[str(lvl)] = {
                    "runs": len(lrs),
                    "mae_pct": _mean([r.mae_pct for r in lrs]),
                    "time_in_corridor": _mean([r.tic_frac for r in lrs]),
                    "press_mae_pct": _mean([r.press_mae_pct for r in lrs]),
                    "release_mae_pct": _mean([r.release_mae_pct
                                              for r in lrs]),
                }
            per_lane[str(lane)] = {
                "runs": len(rs),
                "mae_pct": _mean([r.mae_pct for r in rs]),
                "time_in_corridor": _mean([r.tic_frac for r in rs]),
                "press_mae_pct": _mean([r.press_mae_pct for r in rs]),
                "release_mae_pct": _mean([r.release_mae_pct for r in rs]),
                "by_level": by_level,
            }
        names: list[str] = []
        for r in self._records:
            for name in r.section_mae:
                if name not in names:
                    names.append(name)
        section_mae: dict[str, float | None] = {}
        for name in names:
            vals = [r.section_mae.get(name) for r in self._records]
            section_mae[name] = _mean(vals)
        section_mae_by_level: dict[str, dict] = {}
        for lvl in sorted({r.level for r in self._records}):
            lrs = [r for r in self._records if r.level == lvl]
            lnames = [n for n in names
                      if any(n in r.section_mae for r in lrs)]
            section_mae_by_level[str(lvl)] = {
                name: _mean([r.section_mae.get(name) for r in lrs])
                for name in lnames
            }
        best = None
        scored_secs = {n: v for n, v in section_mae.items()
                       if v is not None}
        if scored_secs:
            best = section_label(min(scored_secs, key=scored_secs.get))

        def _level_row(rs):
            return {
                "runs": len(rs),
                "mae_pct": _mean([r.mae_pct for r in rs]),
                "time_in_corridor": _mean([r.tic_frac for r in rs]),
                "rings": sum(r.rings_collected for r in rs),
                "stalls": sum(r.stalls for r in rs),
            }

        # Per ladder position, pooled over hands and then split by
        # hand. This is the table the ladder exists for: time in
        # corridor is only comparable WITHIN a level (the corridor
        # narrows as the ladder climbs), so nothing here pools levels.
        per_level = {
            str(lvl): _level_row([r for r in self._records
                                  if r.level == lvl])
            for lvl in sorted({r.level for r in self._records})}
        per_level_by_hand: dict[str, dict] = {}
        for hand in self.hand_names:
            rows = {
                str(lvl): _level_row([r for r in self._records
                                      if r.level == lvl and r.hand == hand])
                for lvl in sorted({r.level for r in self._records
                                   if r.hand == hand})}
            if rows:
                per_level_by_hand[hand] = rows
        return {
            "ladder": dict(self.ladder_info),
            "per_level": per_level,
            "per_level_by_hand": per_level_by_hand,
            "step_grace_s": self.step_grace_s,
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
            "section_mae_pct_by_level": section_mae_by_level,
            "best_section": best,
            # Signal-starved runs (coverage under half the plan):
            # logged with error_type no_signal, kept out of every
            # aggregate above, counted here so the analysis can see
            # the hardware trouble instead of inferring it.
            "no_signal_runs": self._no_signal_runs,
            "demo": self.demo,
            "end_reason": self.end_reason,
            **self.wait_skip_stats(),
        }
