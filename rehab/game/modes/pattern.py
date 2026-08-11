"""Patterns mode: motor sequence learning on the serial reaction time
task (SRTT) design. The patient plays "takes" of a piano riff; hidden
inside most takes is a repeating 12-item finger sequence, and learning
is measured as the reaction-time jump when a take secretly switches to
unfamiliar material.

WHY THIS DESIGN. Nissen and Bullemer (1987, Cognitive Psychology) had
people respond to a cue in one of four positions with one finger per
position while a 10-item sequence repeated underneath; mean RT fell
from 327 ms to 163 ms, and swapping in a random block bounced RT back
up. That rebound, sequence-block RT subtracted from probe-block RT, is
the learning index used here and one of the most replicated measures
in cognitive psychology (Robertson 2007, J Neurosci, for review). The
pattern_trial column in trials.csv carries the trained/untrained label
for every trial, so the index falls straight out of a groupby.

SEQUENCES. Simple sequences let people learn "which finger comes up
often" rather than the sequence, so Reed and Johnson (1994, JEP:LMC)
introduced second-order conditional (SOC) sequences: 12 items over 4
fingers where every finger appears exactly 3 times, no finger repeats
back to back, and all 12 possible finger-to-finger transitions occur
exactly once per cycle, so only the two-back structure separates
trained from control material. Formally an SOC is an Eulerian circuit
on the complete directed graph over the four fingers; the generator
walks that graph with seeded randomised backtracking, which is
deterministic given the seed.

BOTH HANDS. With both boards connected the trained material spans all
EIGHT fingers. Bimanual serial reaction time tasks are established
(Verwey's discrete sequence production work is bimanual, and many
SRTT variants map positions across both hands), so the sequence
simply grows: a 24-item cycle over the eight lanes in which every
lane appears exactly 3 times, no lane repeats back to back, and no
lane-to-lane transition occurs twice, so within a cycle every first
order transition is equally (once-)frequent, the Reed and Johnson
property at the size K8 admits. Each cycle gives each hand exactly 12
trials, so hand balance holds at every cycle boundary. Probes are
built to a stricter standard than fresh random cycles: each probe
REUSES the trained cycle's own 24 transitions in a different Eulerian
order, so trained and probe material have IDENTICAL location and
first-order transition frequencies and differ only in the two-back
structure, which is the Reed and Johnson logic carried to eight
lanes. When a seed's transition graph admits no fully disjoint
re-ordering, the generator falls back to fresh cycles sharing zero
(then minimally few) triplets, and the block summary records the
material either way. Takes run 3 cycles (72 trials) instead of the
unilateral 5 x 12, keeping take length inside the standard 50 to 100
trial envelope. Single-hand play is untouched: one hand selected
still runs the 12-item four-finger SOC, and a participant's
unilateral and bimanual material are derived from the same name seed
through different generators, so starting one never changes the
other.

SEED AND STABILITY. The trained sequence must be the same one every
time a participant sits down, or cross-session learning curves are
meaningless. The seed is derived from the participant name (SHA-256 of
the lower-cased, trimmed name plus a version tag), so the sequence
survives app restarts and machine changes with no state file to lose.
The cost is that the name must be typed consistently; the trim and
case-fold absorb the common slips.

PROBES. Probe takes use untrained SOC sequences that share not one
second-order transition with the trained sequence: for every pair of
consecutive fingers, the trained follow-up never applies, so trained
knowledge cannot help. Sharing zero transitions with a FIXED sequence
is achievable (measured feasible for every seed tested); the research
brief's pool of four probes pairwise disjoint from each other as well
is mathematically impossible (each finger pair has only three possible
successors, so at most three sequences can disagree everywhere), so
probes are allowed to overlap each other, only never the trained
material, and the pool keeps up to four distinct rotation classes
(some trained sequences admit only three; the pool then holds three).
Which pool members a session uses rotates on a fresh per-block seed,
so probe material stays fresh across blocks while remaining perfectly
frequency-matched to the trained sequence, which is the Reed and
Johnson logic.

BLOCK LAYOUT, one engine block = one session of takes:
    W    warm-up, 20 balanced-random trials, excluded from analysis
    B1   64 random trials (general-speed baseline, tracked across days;
         a multiple of 8 so bimanual hand balance holds exactly)
    B2-4 trained sequence, 5 cycles each (60 trials per take)
    B5   PROBE, untrained SOC, then a mandatory 60 s rest
    B6-8 trained sequence
    B9   PROBE
    B10  trained sequence (retention anchor for the next session)
Probes sit at fixed positions 5 and 9 so sessions line up across days,
and each probe is scored against its two flanking trained takes. Every
take starts the sequence at cycle position 0 so takes align too. The
short-session variant (pattern.short_session) is 8 takes: random,
three trained, probe, trained, probe, trained, keeping both probes
flanked because the flanker subtraction IS the measurement. Counts sit
inside the standard SRTT envelope (blocks of 50 to 100 trials, 400 to
800 sequence trials per session; Nissen and Bullemer found learning
within 4 blocks of 100). Five training sessions on separate days is
the intended dose: Savion-Lemieux and Penhune (2005, Exp Brain Res)
found distribution across days matters more than amount per day.

TRIAL LOOP. One key lights; the cue stays until the correct finger
presses or 2 s passes (headroom for stroke-slowed RTs plus
corrections); the next cue follows 500 ms after the response, the
response-to-stimulus interval Nissen and Bullemer used. Both intervals
are fixed for a participant because any timing change confounds the RT
contrast that is the outcome; the only progression is dosage across
days. Wrong presses follow the Classic convention: the trial closes as
a Miss with had_incorrect_press TRUE and the first wrong press in
first_incorrect_ms, and RT aggregates use correct trials only. Presses
under 100 ms stay in the accuracy count but leave RT stats (they
cannot be stimulus-driven), and correct RTs past mean + 2.5 SD within
a take are trimmed from aggregates, both standard SRTT hygiene; raw
rows log unfiltered. A press that lands in the RSI gap between trials
(no cue lit yet) is not penalised and writes no trial row -- there is
no trial to attach it to -- but is counted per take as
n_rsi_presses in block_stats, so anticipatory pressing is at least
visible in metadata.json even though it cannot be recovered from
trials.csv.

WHAT THE PATIENT SEES. Takes and stars, never the word sequence:
Boyd and Winstein (2003 Physical Therapy; 2004 Learning and Memory)
found explicit knowledge of the sequence IMPAIRS implicit motor
learning after stroke, so nothing on screen or in this mode's messages
mentions that a pattern exists, probe takes render identically to
trained takes, and between-take stars reward accuracy only (3 stars at
95 percent, 2 at 85, 1 at 70). RT numbers are never shown.

SAFETY. Rests between takes are self-paced with a 15 s floor plus the
60 s rest after B5; five consecutive timeouts inside one non-probe
take force a rest, a second such run ends the session gracefully
(probe takes are exempt so expected probe slowing is not punished);
and a 30 min cap ends the session at the next trial close. Presses
are the calibrated light-press threshold only.

WHAT THIS MODE CANNOT CLAIM. Implicit sequence learning after stroke
is demonstrated for the less-affected hand (Kal et al 2016, PLoS ONE
meta-analysis: 69 ms mean probe rebound) but NOT for the affected
hand (pooled effect null), so affected-side use is measurement, not
proven therapy. A single-session rebound can be temporary adaptation
that fades in minutes (Trofimova et al 2020, Neurobiol Learn Mem);
only multi-session and retention data support memory claims. There is
no evidence this training transfers to untrained hand tasks. And with
a 60 Hz display the stimulus onset is quantised to 16.7 ms, so
single-trial differences are noise; block means are the unit of
analysis.

DEVIATIONS FROM THE RESEARCH BRIEF, where the plumbing wins:
- The four "piano keys" are the existing lane tiles, and cues run
  through the shared cue system (cue.* switches, logged per trial in
  cue_flags) rather than a bespoke piano renderer.
- With cue.sound_before on, the per-lane cue tones (C E G C) turn the
  sequence into an audible melody, which invites explicit discovery.
  The brief's uniform-click option does not exist in the shared audio
  path; run research blocks with sound_before off, or accept the
  melody and note the cue_flags value. Either way it is logged.
- engine.log_trial flashes the outcome tier (Perfect/Great/Good/Late)
  like every other mode. That is a speed hint but not an RT number;
  accepted for consistency across the suite. The Perfect tier's point
  value is capped down to the Good tier's (engine.begin_pattern_block
  builds a mode-specific ScoreConfig for this) because Perfect's
  sub-100 ms window is exactly ANTICIPATION_CUT_MS, the region the RT
  stats already exclude as non-stimulus-driven; without the cap the
  score would reward the fastest possible guess more than an honest
  response. The tier LABEL still shows "Perfect" on a fast press
  (the flash is accepted above) -- only the points are levelled.
- RT is logged for the CORRECT press (time_difference_ms), with the
  first wrong press in first_incorrect_ms, rather than first-press RT
  in one column; both are recoverable from the row.
- Probe rotation across sessions uses a fresh per-block seed instead
  of a persisted profile file: no cross-session state exists in this
  app, and a random rotation cannot drift or be lost.
- The awareness check (free generation after the final session) and
  the retention-session schedule are protocol, run by the researcher,
  not modes of this software.
- The shipped cue defaults buzz the target finger and play the cue
  tone on every stimulus, so the RTs here are responses to an
  audio-tactile-visual cue, not a visual one. The probe-minus-flanker
  contrast survives because trained and probe material get the
  identical cue mix, but the mix must stay fixed for a participant
  across all sessions, and cue_flags on every trial row is how the
  analysis verifies it did and splits blocks where it did not.
- Stimulus onset is timestamped at the update tick that fires it
  (PendingTrial.stim_t_perf), not at the next pygame flip; no flip
  time or flip-tick delta is logged. This gives every RT an
  unmeasurable 0 to 16.7 ms early-reference bias on top of the 60 Hz
  quantisation already named above, and the display-timing sanity
  check the research brief specifies cannot be run from these logs.
  The probe-minus-flanker contrast survives because trained and probe
  trials share the same bias, so this does not change the headline,
  but it should not be claimed as flip-measured RT.
"""
from __future__ import annotations

import hashlib
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


# ---- sequence generation ---------------------------------------------------
def participant_seed(name: str) -> int:
    """Deterministic sequence seed from the participant name. Trimmed
    and case-folded so "Basil " and "basil" get the same trained
    sequence; the version tag lets a future generator change without
    silently changing existing participants' material."""
    norm = (name or "").strip().lower() or "anonymous"
    digest = hashlib.sha256(f"{norm}|srtt_v1".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def generate_soc(rng: random.Random) -> list[int]:
    """One 12-item second-order conditional cycle over fingers 0..3:
    every ordered pair of distinct fingers appears exactly once as a
    consecutive pair when the cycle wraps, which also forces each
    finger to appear exactly 3 times with no back-to-back repeats.
    Randomised backtracking over the Eulerian-circuit graph; a few
    microseconds per draw, fully determined by the rng state."""
    start = rng.randrange(4)
    path = [start]
    used: set[tuple[int, int]] = set()

    def extend() -> bool:
        if len(used) == 12:
            return path[-1] == start
        options = [b for b in range(4)
                   if b != path[-1] and (path[-1], b) not in used]
        rng.shuffle(options)
        for b in options:
            used.add((path[-1], b))
            path.append(b)
            if extend():
                return True
            path.pop()
            used.discard((path[-1], b))
        return False

    if not extend():                      # cannot happen on K4, guard anyway
        raise RuntimeError("SOC backtracking failed")
    return path[:-1]


# Bimanual material size: 8 lanes, each appearing this many times per
# cycle, so one cycle is 24 trials and each hand gets exactly 12.
CYCLE8_LANES = 8
CYCLE8_REPEATS = 3


def generate_cycle8(rng: random.Random) -> list[int]:
    """One 24-item cycle over the eight lanes of both hands: every
    lane appears exactly 3 times, no lane repeats back to back, and no
    ordered lane-to-lane transition occurs twice (wrap included), so
    every first-order transition inside the cycle is equally frequent.
    K8 has 56 ordered pairs and the cycle uses 24 of them; which 24 is
    the seed's draw, and the probe builder reuses exactly that set so
    trained and probe stay first-order matched. Same randomised
    backtracking as generate_soc, deterministic given the rng."""
    n, reps = CYCLE8_LANES, CYCLE8_REPEATS
    length = n * reps
    start = rng.randrange(n)
    path = [start]
    counts = [0] * n
    counts[start] = 1
    used: set[tuple[int, int]] = set()

    def extend() -> bool:
        if len(path) == length:
            return (path[-1] != start
                    and (path[-1], start) not in used)
        options = [b for b in range(n)
                   if b != path[-1]
                   and (path[-1], b) not in used
                   and counts[b] < reps]
        rng.shuffle(options)
        for b in options:
            used.add((path[-1], b))
            counts[b] += 1
            path.append(b)
            if extend():
                return True
            path.pop()
            counts[b] -= 1
            used.discard((path[-1], b))
        return False

    if not extend():
        raise RuntimeError("bimanual cycle backtracking failed")
    return path


def reorder_cycle(trained: list[int], rng: random.Random,
                  forbid: dict | None = None) -> list[int] | None:
    """A different Eulerian ordering of `trained`'s own transitions:
    the same 24 ordered pairs walked in a new order, so location and
    first-order transition frequencies match the trained cycle
    EXACTLY and only the two-back structure differs. `forbid` maps
    (a, b) -> successor to avoid, normally the trained cycle's own
    triplet map, so the result shares zero second-order transitions.
    Returns None when the graph admits no such ordering from this
    draw."""
    edges: dict[int, list[int]] = {}
    n = len(trained)
    for i in range(n):
        edges.setdefault(trained[i], []).append(trained[(i + 1) % n])
    start = rng.choice(trained)
    remaining = {a: list(bs) for a, bs in edges.items()}
    path = [start]
    forbid = forbid or {}

    def extend() -> bool:
        if len(path) == n + 1:
            return path[-1] == start
        here = path[-1]
        options = sorted(set(remaining.get(here, [])))
        rng.shuffle(options)
        for b in options:
            if len(path) >= 2:
                pair = (path[-2], path[-1])
                if forbid.get(pair) == b:
                    continue
            remaining[here].remove(b)
            path.append(b)
            if extend():
                return True
            path.pop()
            remaining[here].append(b)
        return False

    if not extend():
        return None
    cycle = path[:-1]
    # The wrap pairs also carry forbidden triplets; check them here
    # rather than complicating the recursion's boundary cases.
    if forbid and shared_triplets(cycle, trained) != 0:
        return None
    return cycle


def _triplet_map(seq: list[int]) -> dict[tuple[int, int], int]:
    n = len(seq)
    return {(seq[i], seq[(i + 1) % n]): seq[(i + 2) % n] for i in range(n)}


def shared_triplets(a: list[int], b: list[int]) -> int:
    """How many finger pairs the two cycles follow up the same way.
    Zero means knowing one sequence tells you nothing two-back about
    the other, which is what a probe needs against the trained one."""
    ma, mb = _triplet_map(a), _triplet_map(b)
    return sum(1 for k, v in ma.items() if mb.get(k) == v)


def _canonical_rotation(seq: list[int]) -> tuple[int, ...]:
    """Rotation-invariant form. Two rotations of one cycle are the
    same material to a learner, so probes must differ under this."""
    return min(tuple(seq[i:] + seq[:i]) for i in range(len(seq)))


# Draw budgets for the probe search. Deterministic given the seed, so
# the same participant always gets the same pool. The primary budget
# finds zero-overlap probes for every seed tested (worst case a few
# hundred draws at microseconds each); the fallback exists so a
# pathological seed still yields at least two usable probes rather
# than an infinite loop.
_PROBE_DRAWS = 6000
_PROBE_FALLBACK_DRAWS = 2000
_PROBE_FALLBACK_MAX_SHARED = 2


def build_sequences(seed: int,
                    probe_pool_size: int = 4,
                    n_lanes: int = 4,
                    ) -> tuple[list[int], list[list[int]]]:
    """The participant's trained cycle plus their probe pool, all from
    one seed. Probes share zero second-order transitions with the
    trained sequence and are pairwise distinct rotation classes. Some
    trained sequences only admit three zero-overlap classes, so the
    pool can come back one short of the ask; a session needs two.

    n_lanes=4 is the unilateral 12-item SOC and its draw order is
    byte-identical to what it always was, so existing participants'
    material never changes. n_lanes=8 is the bimanual 24-item cycle;
    its probes reuse the trained cycle's own transition set in a new
    Eulerian order where the graph allows it (perfect first-order
    match), falling back to fresh zero-overlap cycles, then to minimal
    overlap, so a block start can never freeze on a pathological
    seed."""
    rng = random.Random(int(seed))
    if int(n_lanes) >= CYCLE8_LANES:
        return _build_sequences8(rng, probe_pool_size)
    trained = generate_soc(rng)
    want = max(2, int(probe_pool_size))
    pool: list[list[int]] = []
    seen: set[tuple[int, ...]] = {_canonical_rotation(trained)}
    for _ in range(_PROBE_DRAWS):
        if len(pool) >= want:
            break
        cand = generate_soc(rng)
        if shared_triplets(cand, trained) != 0:
            continue
        canon = _canonical_rotation(cand)
        if canon in seen:
            continue
        seen.add(canon)
        pool.append(cand)
    # Fallback: accept minimal overlap rather than come back with too
    # few probes to alternate between. Never observed in testing, but
    # a frozen block start is worse than a 2-triplet overlap.
    for _ in range(_PROBE_FALLBACK_DRAWS):
        if len(pool) >= 2:
            break
        cand = generate_soc(rng)
        if shared_triplets(cand, trained) > _PROBE_FALLBACK_MAX_SHARED:
            continue
        canon = _canonical_rotation(cand)
        if canon in seen:
            continue
        seen.add(canon)
        pool.append(cand)
    if len(pool) < 2:
        raise RuntimeError("probe pool generation failed")
    return trained, pool


# Same budgets, bimanual: the re-ordering search is cheap (24 edges)
# and nearly always lands inside a handful of draws.
_REORDER_DRAWS = 400


def _build_sequences8(rng: random.Random, probe_pool_size: int
                      ) -> tuple[list[int], list[list[int]]]:
    trained = generate_cycle8(rng)
    forbid = _triplet_map(trained)
    want = max(2, int(probe_pool_size))
    pool: list[list[int]] = []
    seen: set[tuple[int, ...]] = {_canonical_rotation(trained)}

    def take(cand: list[int] | None) -> None:
        if cand is None:
            return
        canon = _canonical_rotation(cand)
        if canon in seen:
            return
        seen.add(canon)
        pool.append(cand)

    # First choice: the trained cycle's own transitions in a new
    # order, sharing zero triplets. Identical first-order statistics.
    for _ in range(_REORDER_DRAWS):
        if len(pool) >= want:
            break
        take(reorder_cycle(trained, rng, forbid))
    # Second: fresh cycles sharing zero triplets (location frequencies
    # still match exactly; first-order pairs may differ).
    for _ in range(_PROBE_DRAWS):
        if len(pool) >= want:
            break
        cand = generate_cycle8(rng)
        if shared_triplets(cand, trained) == 0:
            take(cand)
    # Last resort: minimal overlap beats a frozen block start.
    for _ in range(_PROBE_FALLBACK_DRAWS):
        if len(pool) >= 2:
            break
        cand = generate_cycle8(rng)
        if shared_triplets(cand, trained) <= _PROBE_FALLBACK_MAX_SHARED:
            take(cand)
    if len(pool) < 2:
        raise RuntimeError("bimanual probe pool generation failed")
    return trained, pool


# ---- session layout --------------------------------------------------------
@dataclass
class Segment:
    """One take: a run of trials of a single material type."""
    kind: str                 # warmup | random | seq | probe
    label: str                # "W", "1".."10"; shown in take messages
    fingers: list[int]        # finger index (0..3) per trial, in order
    soc_id: str               # "trained", "p0".."p3", "" for non-SOC
    long_rest_after: bool = False
    # Filled during play, read by block_stats and the star display.
    n_done: int = field(default=0)
    n_correct: int = field(default=0)


class PatternMode:
    name = "Patterns"

    # RTs under this cannot be responses to the stimulus (standard SRTT
    # practice); such trials keep their accuracy but leave RT stats.
    ANTICIPATION_CUT_MS = 100.0
    # Within-take trim for RT aggregates: correct RTs past
    # mean + 2.5 SD are excluded (common SRTT trim). Raw rows keep all.
    OUTLIER_SD = 2.5
    # Gap between the take-start message and its first stimulus, so the
    # patient reads "Take 3" before the first key lights.
    SEGMENT_LEAD_S = 1.5
    # Throttle for the "press any finger" prompt during a rest.
    REST_PROMPT_EVERY_S = 1.5

    def __init__(self, engine: "GameEngine",
                 lanes: list[int],
                 p_seed: int, block_seed: int,
                 soc_cycles_per_block: int, warmup_trials: int,
                 random_block_trials: int, probe_pool_size: int,
                 rsi_s: float, timeout_s: float,
                 rest_min_s: float, long_rest_s: float,
                 fatigue_timeout_run: int, session_cap_min: float,
                 short_session: bool, score_cfg: ScoreConfig,
                 demo_trials: int | None = None) -> None:
        self.engine = engine
        # The lanes in play, indexed by sequence position: one hand's
        # four fingers, or with both boards connected all eight (right
        # 0..3 then left 4..7, the engine's global numbering).
        # Sequences are generated over these indices and mapped
        # through this list, so the same trained material drives
        # whichever side the lanes belong to.
        if len(lanes) >= CYCLE8_LANES:
            self.lanes = list(lanes)[:CYCLE8_LANES]
        else:
            self.lanes = list(lanes)[:4]
            while len(self.lanes) < 4:
                self.lanes.append(len(self.lanes))
        self.n_fingers = len(self.lanes)
        self.p_seed = int(p_seed)
        self.block_seed = int(block_seed)
        self.score_cfg = score_cfg
        self.rsi = float(rsi_s)
        self.timeout = float(timeout_s)
        self.rest_min = float(rest_min_s)
        self.long_rest = float(long_rest_s)
        self.fatigue_run = max(1, int(fatigue_timeout_run))
        self.session_cap_s = float(session_cap_min) * 60.0
        self.short_session = bool(short_session)
        self.demo_trials = demo_trials

        # Participant-stable material from the name-derived seed;
        # per-block freshness (random orders, probe rotation) from the
        # block seed, which is drawn fresh unless pattern.seed pins it.
        self.trained, self.probes = build_sequences(
            self.p_seed, probe_pool_size, n_lanes=self.n_fingers)
        self.cycle_len = len(self.trained)
        self.block_rng = random.Random(self.block_seed)
        self.probe_offset = self.block_rng.randrange(len(self.probes))
        # Bimanual cycles are twice as long, so a take runs about half
        # as many of them to keep take length inside the standard 50 to
        # 100 trial envelope (5 x 12 unilateral, 3 x 24 bimanual).
        if self.n_fingers >= CYCLE8_LANES:
            soc_cycles_per_block = max(
                1, (int(soc_cycles_per_block) + 1) // 2)

        if demo_trials is not None:
            # Test Mode: a two-take miniature (trained then probe) so a
            # demo still writes both pattern_trial values to the CSV,
            # with rests cut to keep the demo under a minute.
            n = max(2, int(demo_trials))
            n_seq = max(1, (2 * n) // 3)
            n_probe = max(1, n - n_seq)
            self.rest_min = min(self.rest_min, 2.0)
            self.long_rest = min(self.long_rest, 2.0)
            probe = self.probes[self.probe_offset]
            cyc = self.cycle_len
            self.segments = [
                Segment("seq", "1",
                        [self.trained[i % cyc] for i in range(n_seq)],
                        "trained"),
                Segment("probe", "2",
                        [probe[i % cyc] for i in range(n_probe)],
                        f"p{self.probe_offset}"),
            ]
        else:
            self.segments = self._build_layout(
                soc_cycles_per_block, warmup_trials, random_block_trials)
        self.n_takes = sum(1 for s in self.segments if s.kind != "warmup")

        # Trial state machine: play -> rest -> play ... -> done.
        self.phase = "play"
        self.active: PendingTrial | None = None
        self.trial_counter = 0
        self._seg_idx = 0
        self._trial_in_seg = 0
        self._seg_announced = False
        self._next_stim_due: float | None = None
        self._rest_min_until: float | None = None
        self._rest_kind = "between"      # between | forced
        self._rest_msg_t = 0.0
        self._t0: float | None = None    # session clock for the hard cap
        self._presses: deque[PressEvent] = deque()

        # Fatigue guard: consecutive timeouts within the current
        # non-probe take. Reset by any press and at take boundaries.
        self._timeout_run = 0
        self._fatigue_triggers = 0
        self.end_reason: str | None = None

        # Per-trial record for block_stats: (segment index, correct,
        # rt_ms of the correct press or None).
        self._trials: list[tuple[int, bool, float | None]] = []
        # RSI presses are not penalised (see _handle_press) but they
        # were vanishing entirely -- not logged, not counted anywhere
        # -- so a keyboard-only session left no trace of anticipatory
        # pressing at all. Counted per take here and folded into
        # block_stats so it is at least recoverable from metadata.json
        # even though no trial row exists for it (audit finding #12).
        self._rsi_presses: dict[int, int] = {}

    # ---- layout ------------------------------------------------------------
    def _build_layout(self, cycles: int, warmup_n: int,
                      random_n: int) -> list[Segment]:
        segs: list[Segment] = []

        def random_fingers(n: int, kind: str = "random",
                          warn: bool = True) -> list[int]:
            # Shuffle-bag over every finger in play: equal counts, no
            # back-to-back repeats, fresh order every block. Balanced
            # per lane, which in bimanual play balances the hands too
            # ONLY when n divides evenly by n_fingers: BalancedScheduler
            # guarantees lane counts within 1 of each other, but which
            # lanes get the extra trial is a property of the shuffle,
            # not of the count, so a remainder can land unevenly across
            # the two hands. The shipped defaults are clean multiples
            # of both 4 and 8; a config change that breaks that gets
            # flagged here rather than silently trusted. `warn` is off
            # for the warmup block: it is excluded from analysis, so a
            # lopsided warmup does not matter, and crying wolf about it
            # trains the researcher to ignore the same warning firing
            # about B1, where it does.
            if warn and n % self.n_fingers != 0:
                log.warning(
                    "pattern %s block: %d trials does not divide "
                    "evenly across %d lanes; per-lane counts stay "
                    "within 1 of each other but hand balance is no "
                    "longer guaranteed", kind, n, self.n_fingers)
            return BalancedScheduler(
                list(range(self.n_fingers)), self.block_rng).sequence(n)

        def soc_block(soc: list[int]) -> list[int]:
            # Always starts at cycle position 0 so takes align across
            # blocks and sessions.
            cyc = len(soc)
            return [soc[i % cyc] for i in range(cyc * max(1, cycles))]

        if warmup_n > 0:
            segs.append(Segment(
                "warmup", "W",
                random_fingers(warmup_n, kind="warmup", warn=False), ""))
        # Take kinds in order. The standard session puts probes at
        # positions 5 and 9 with trained takes either side; the short
        # session keeps both probes flanked (the flanker subtraction is
        # the measurement) at the cost of the fixed probe positions.
        if self.short_session:
            kinds = ["random", "seq", "seq", "seq", "probe",
                     "seq", "probe", "seq"]
        else:
            kinds = ["random", "seq", "seq", "seq", "probe",
                     "seq", "seq", "seq", "probe", "seq"]
        probe_i = 0
        for i, kind in enumerate(kinds):
            label = str(i + 1)
            if kind == "random":
                segs.append(Segment("random", label,
                                    random_fingers(random_n), ""))
            elif kind == "seq":
                segs.append(Segment("seq", label,
                                    soc_block(self.trained), "trained"))
            else:
                pi = (self.probe_offset + probe_i) % len(self.probes)
                probe_i += 1
                seg = Segment("probe", label,
                              soc_block(self.probes[pi]), f"p{pi}")
                # The mandatory long rest follows the first probe
                # (B5 in the standard layout).
                seg.long_rest_after = (probe_i == 1)
                segs.append(seg)
        return segs

    # ---- plumbing shared with the other cadence modes ----------------------
    def queue_press(self, ev: PressEvent) -> None:
        self._presses.append(ev)

    @property
    def current_timeout_s(self) -> float:
        # Engine reads this to arm the timing bar and log timeout_ms.
        return self.timeout

    def on_resume(self, pause_dur: float) -> None:
        # Slide every in-flight deadline forward so a pause cannot time
        # a trial out, fire a stim early, or eat rest or cap time.
        if self.active is not None:
            self.active.stim_t_perf += pause_dur
        for attr in ("_next_stim_due", "_rest_min_until", "_t0"):
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
        if self._t0 is None:
            self._t0 = now
        while self._presses:
            self._handle_press(self._presses.popleft(), now)
        if self.phase == "done":
            return
        if self.phase == "rest":
            self._update_rest(now)
            return
        # play
        if not self._seg_announced:
            self._begin_segment(now)
        if self.active is not None:
            if (now - self.active.stim_t_perf) > self.timeout:
                self._close(None, now)
            return
        seg = self.segments[self._seg_idx]
        if self._trial_in_seg >= len(seg.fingers):
            self._after_segment(now)
            return
        if self._next_stim_due is not None and now >= self._next_stim_due:
            self._fire(now)

    def _begin_segment(self, now: float) -> None:
        self._seg_announced = True
        self._trial_in_seg = 0
        self._timeout_run = 0
        seg = self.segments[self._seg_idx]
        self._set_message(self._segment_title(seg), 1.2)
        self._next_stim_due = now + self.SEGMENT_LEAD_S

    def _segment_title(self, seg: Segment) -> str:
        # Take numbering never distinguishes probe takes from trained
        # ones: the patient must not be able to tell them apart.
        if seg.kind == "warmup":
            return "Warm-up"
        return f"Take {seg.label} of {self.n_takes}"

    def _fire(self, now: float) -> None:
        seg = self.segments[self._seg_idx]
        finger = seg.fingers[self._trial_in_seg]
        lane = self.lanes[finger]
        self.trial_counter += 1
        self.active = PendingTrial(
            trial_id=self.trial_counter,
            lane=lane,
            stim_t_perf=now,
            keys_pressed=[],
            incorrect_presses=[],
        )
        self._next_stim_due = None
        self.engine.on_stim_multi([lane], self.trial_counter, now)

    def eeg_stim_code(self) -> int | None:
        """Sequence status rides the marker byte in this mode: the
        N2b/P3b deviance analysis epochs on trained-versus-random
        items, and cue condition is fixed within a block (recoverable
        from cue_flags), so the byte carries what varies. Warm-up and
        probe material counts as random, matching the pattern_trial
        CSV column."""
        if not 0 <= self._seg_idx < len(self.segments):
            return None
        return (EEG_CODES["stim_pattern_sequence"]
                if self.segments[self._seg_idx].kind == "seq"
                else EEG_CODES["stim_pattern_random"])

    # ---- presses -----------------------------------------------------------
    def _handle_press(self, ev: PressEvent, now: float) -> None:
        if self.phase == "rest":
            # Rests are self-paced past the floor: any finger advances.
            if (self._rest_min_until is not None
                    and now >= self._rest_min_until):
                self._leave_rest(now)
            return
        if self.phase != "play":
            return
        if self.active is None:
            # A press in the half-second before the next cue is the
            # patient anticipating what comes next, which is exactly
            # what expressing sequence knowledge looks like. Penalising
            # it (classic's idle-press deduction) would punish the
            # thing this mode exists to grow, so RSI presses pass with
            # no penalty and no trial row; the next cue lands within
            # the RSI anyway. Still counted per take (not per trial --
            # there is no trial to attach it to) so the analysis can at
            # least see how often it happened.
            self._rsi_presses[self._seg_idx] = (
                self._rsi_presses.get(self._seg_idx, 0) + 1)
            return
        self.active.keys_pressed.append(ev.lane)
        self._timeout_run = 0
        if ev.lane == self.active.lane:
            self._close(ev, now)
        else:
            # Cue stays lit until the correct finger lands or the
            # timeout passes (Nissen and Bullemer required correct
            # responses). Per-press penalty as in classic: spamming
            # must not be the winning strategy.
            self.active.incorrect_presses.append((ev.lane, ev.t_perf))
            self.engine.apply_wrong_press_penalty()

    def _close(self, ev: PressEvent | None, now: float) -> None:
        trial = self.active
        if trial is None:
            return
        self.active = None
        seg = self.segments[self._seg_idx]
        rt_ms = None
        if ev is not None:
            rt_ms = (ev.t_perf - trial.stim_t_perf) * 1000.0
        outcome = classify(rt_ms, self.score_cfg)
        if trial.incorrect_presses:
            # Classic convention: a fumbled-then-correct trial is a
            # Miss row with the wrong press in first_incorrect_ms, so
            # RT aggregates (correct trials only) stay clean.
            outcome = TrialResult(label="Miss",
                                  points=self.score_cfg.miss_points,
                                  rt_ms=rt_ms)
        correct = outcome.label != "Miss"
        seg.n_done += 1
        if correct:
            seg.n_correct += 1
        self._trials.append(
            (self._seg_idx, correct, rt_ms if correct else None))
        # THE measurement column: TRUE only for trained-sequence
        # trials. Warm-up, random baseline and probes are all FALSE.
        pattern_trial = (seg.kind == "seq")
        stim = f"{seg.kind};b={seg.label}"
        if seg.soc_id:
            pos = self._trial_in_seg % self.cycle_len
            stim += f";soc={seg.soc_id};pos={pos}"
        self.engine.log_trial(trial, outcome, now,
                              stimulus=stim, pattern_trial=pattern_trial)
        self._trial_in_seg += 1
        self._next_stim_due = now + self.rsi
        # Hard session cap: end at a trial close, never mid-trial.
        if (self._t0 is not None
                and (now - self._t0) > self.session_cap_s):
            self._set_message("Session complete", 2.0)
            self._end("time_cap")
            return
        # Fatigue guard, non-probe takes only: probe slowing is the
        # expected result, not exhaustion.
        if ev is None and seg.kind != "probe":
            self._timeout_run += 1
            if self._timeout_run >= self.fatigue_run:
                self._timeout_run = 0
                self._fatigue_triggers += 1
                if self._fatigue_triggers >= 2:
                    self._set_message("Great effort. Session done", 2.0)
                    self._end("fatigue")
                else:
                    self._enter_rest(now, self.rest_min, "forced",
                                     "Take a breather")

    # ---- segment and rest flow ---------------------------------------------
    def _after_segment(self, now: float) -> None:
        if self._seg_idx >= len(self.segments) - 1:
            self._end("completed")
            return
        seg = self.segments[self._seg_idx]
        stars = self._stars(seg)
        title = ("Warm-up done" if seg.kind == "warmup"
                 else f"Take {seg.label} done")
        msg = f"{title}  {stars}".rstrip()
        dur = self.long_rest if seg.long_rest_after else self.rest_min
        self._enter_rest(now, dur, "between", msg)

    @staticmethod
    def _stars(seg: Segment) -> str:
        # Accuracy only, per the Boyd and Winstein constraint: speed
        # feedback would push the patient to hunt for the pattern.
        if seg.n_done <= 0:
            return ""
        acc = seg.n_correct / seg.n_done
        if acc >= 0.95:
            return "***"
        if acc >= 0.85:
            return "**"
        if acc >= 0.70:
            return "*"
        return ""

    def _enter_rest(self, now: float, min_s: float, kind: str,
                    msg: str) -> None:
        self.phase = "rest"
        # EEG rest markers bracket the take breaks so alpha-trend
        # analysis can separate task time from rest time.
        send = getattr(self.engine, "_eeg_send", None)
        if callable(send):
            send(EEG_CODES["rest_start"], t_event=now)
        self._rest_kind = kind
        self._rest_min_until = now + max(0.0, min_s)
        self._rest_msg_t = now
        self._set_message(msg, min(3.0, max(1.5, min_s)))
        self._clear_lanes()

    def _update_rest(self, now: float) -> None:
        if (self._rest_min_until is not None
                and now >= self._rest_min_until
                and now - self._rest_msg_t > self.REST_PROMPT_EVERY_S):
            self._rest_msg_t = now
            self._set_message("Press any finger when ready", 1.2)

    def _leave_rest(self, now: float) -> None:
        self.phase = "play"
        send = getattr(self.engine, "_eeg_send", None)
        if callable(send):
            send(EEG_CODES["rest_end"], t_event=now)
        self._rest_min_until = None
        if self._rest_kind == "between":
            self._seg_idx += 1
            self._seg_announced = False
        else:
            # Forced rest resumes the same take where it left off.
            self._next_stim_due = now + self.SEGMENT_LEAD_S
            self._set_message("Ready", 1.0)

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
    def _segment_rt_stats(self, seg_idx: int) -> dict:
        """Accuracy plus the trimmed correct-RT mean for one take, with
        every exclusion counted so attrition is reportable."""
        rows = [t for t in self._trials if t[0] == seg_idx]
        n = len(rows)
        n_correct = sum(1 for _, c, _ in rows if c)
        rts = [r for _, c, r in rows if c and r is not None]
        kept = [r for r in rts if r >= self.ANTICIPATION_CUT_MS]
        n_anticipation = len(rts) - len(kept)
        n_outlier = 0
        if len(kept) >= 3:
            m = sum(kept) / len(kept)
            sd = (sum((r - m) ** 2 for r in kept)
                  / (len(kept) - 1)) ** 0.5
            cut = m + self.OUTLIER_SD * sd
            trimmed = [r for r in kept if r <= cut]
            n_outlier = len(kept) - len(trimmed)
            kept = trimmed
        mean_rt = (sum(kept) / len(kept)) if kept else None
        return {
            "n": n,
            "accuracy": round(n_correct / n, 3) if n else None,
            "mean_rt_ms": round(mean_rt, 1) if mean_rt is not None else None,
            "n_rt_used": len(kept),
            "n_anticipation": n_anticipation,
            "n_rt_outliers": n_outlier,
        }

    def _flanker_indices(self, probe_idx: int) -> list[int]:
        """The nearest trained take on each side of a probe. One side
        can be missing in an abandoned or short run; the score then
        rests on whichever flanker exists."""
        out = []
        for step in (-1, 1):
            i = probe_idx + step
            while 0 <= i < len(self.segments):
                if self.segments[i].kind == "seq":
                    out.append(i)
                    break
                i += step
        return out

    def block_stats(self) -> dict:
        """What finish_block folds into metadata.json so a session is
        readable without trials.csv: the material actually used (the
        analysis needs the sequences), per-take aggregates, and the
        classic probe-minus-flankers learning score."""
        per_take = []
        stats_by_idx: dict[int, dict] = {}
        for i, seg in enumerate(self.segments):
            if seg.n_done <= 0:
                continue
            st = self._segment_rt_stats(i)
            stats_by_idx[i] = st
            per_take.append({
                "block": seg.label,
                "kind": seg.kind,
                "soc": seg.soc_id or None,
                "n_rsi_presses": self._rsi_presses.get(i, 0),
                **st,
            })
        learning = []
        for i, seg in enumerate(self.segments):
            if seg.kind != "probe" or i not in stats_by_idx:
                continue
            probe_rt = stats_by_idx[i]["mean_rt_ms"]
            probe_acc = stats_by_idx[i]["accuracy"]
            fl = [stats_by_idx[j] for j in self._flanker_indices(i)
                  if j in stats_by_idx]
            fl_rts = [f["mean_rt_ms"] for f in fl
                      if f["mean_rt_ms"] is not None]
            fl_accs = [f["accuracy"] for f in fl
                       if f["accuracy"] is not None]
            score = None
            if probe_rt is not None and fl_rts:
                score = round(probe_rt - sum(fl_rts) / len(fl_rts), 1)
            rebound = None
            if probe_acc is not None and fl_accs:
                rebound = round(
                    (sum(fl_accs) / len(fl_accs) - probe_acc) * 100.0, 1)
            learning.append({
                "block": seg.label,
                "soc": seg.soc_id,
                "learning_score_ms": score,
                "accuracy_rebound_pct": rebound,
                "n_flankers": len(fl_rts),
            })
        scores = [d["learning_score_ms"] for d in learning
                  if d["learning_score_ms"] is not None]
        session_score = (round(sum(scores) / len(scores), 1)
                         if scores else None)

        def seq_str(seq: list[int]) -> str:
            # 1-indexed fingers, matching the lane column convention.
            return ",".join(str(f + 1) for f in seq)

        return {
            "participant_seed": self.p_seed,
            "block_seed": self.block_seed,
            "n_lanes": self.n_fingers,
            "cycle_len": self.cycle_len,
            "trained_soc": seq_str(self.trained),
            "probe_pool": [seq_str(p) for p in self.probes],
            "probe_offset": self.probe_offset,
            "layout": ",".join(s.kind for s in self.segments),
            "short_session": self.short_session,
            "demo": self.demo_trials is not None,
            "rsi_ms": round(self.rsi * 1000.0),
            "timeout_ms": round(self.timeout * 1000.0),
            "n_trials": len(self._trials),
            "fatigue_rests": self._fatigue_triggers,
            "end_reason": self.end_reason,
            "per_take": per_take,
            "probe_scores": learning,
            "session_learning_score_ms": session_score,
        }
