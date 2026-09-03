"""Echo mode: the explicit visuospatial span game. The rig plays a
growing sequence on the lanes (tile light plus a buzz on that finger),
the patient plays it back in order, and the longest echo they can hold
is the block's headline. Simon says, scored like a span test.

WHY THIS DESIGN. The parent paradigm is the Corsi block-tapping task
(Corsi 1972, McGill PhD thesis; Milner 1971), the standard visuospatial
span measure and the nonverbal twin of digit span. Kessels, van
Zandvoort, Postma, Kappelle and de Haan (2000, Applied Neuropsychology
7:252-258) is the standardisation everyone implements, and its skeleton
agrees with WAIS digit span administration, which is why Echo adopts it
rather than the arcade rule:

  - sequence length starts at 2, TWO trials (different sequences) per
    length, both always administered;
  - length advances by one while at least one of the two is correct;
    the ladder ends when BOTH trials at a length fail;
  - ceiling 9 (the Corsi ceiling; far above expected spans on four
    lanes anyway);
  - span = longest length with a correct reproduction; the Kessels
    total score is span x number of correct sequences, a compound
    with a better distribution than span alone.

Berch, Krikorian and Huha (1998, Brain and Cognition 38:317-338)
reviewed 25 years of Corsi use and found administration parameters
(tapping rate, discontinuance rule, scoring) varied so much across labs
that results could not be compared. That is why every presentation
parameter here is pinned in config, logged per trial and in
block_stats, and never depends on how the player is doing: the classic
Simon toy speeds up as you survive, and that acceleration is exactly
the kind of drift Berch catalogued.

PRESENTATION RATE. One item per second is the standard administration
(Kessels 2000; WAIS digit span); eCorsi (Brunetti, Del Gatto and Delogu
2014, Frontiers in Psychology 5:939) pins the digital timing that turns
into: 500 ms on, 1000 ms onset to onset. That rate is the SLOW end of
what this mode plays. Played on the rig at the standard rate the game
was reported as slow and stale (2026-09 testing), so the shipped
schedule sits between the standard rate and the hardware floor: the
item stays lit and buzzing for echo.item_on_ms, the onset-to-onset
interval starts at echo.ioi_ms for the shortest sequence and shrinks
by echo.ioi_step_ms per extra item of length, never below
echo.ioi_floor_ms. Two things keep this honest against Berch. First,
the rate is a pinned function of SEQUENCE LENGTH, identical for every
player at every length under the same config; it is not a function of
success within a length, both trials at a length run at the same
rate, and a block with ioi_step_ms 0 is the fixed-rate protocol again.
Second, every trial row carries the ioi it actually ran at (params
ioi_ms) and block_stats carries the whole schedule, so blocks under
different schedules are separable and are never pooled. The floor is
the motor's, not a psychological number: a 10 mm coin ERM of the
class on this rig reaches full amplitude about 130 ms after current
on and spins down for about 115 ms after current off (Precision
Microdrives 310-103 datasheet values; latency.* in the config), so
the item must stay on long enough to reach amplitude and the next
item must not start until the previous finger has stopped, which is
MOTOR_CLEAR_S after the light goes off. No verified source supports
a SLOWER presentation for motor-impaired players (searched for and
not found; the honest gap is named in the research notes), and the
literature puts the load of motor impairment on the RESPONSE side:
Corsi recall is untimed by convention and ran under standard
presentation in Kessels' own cerebral-lesion sample. So REPRODUCTION
is self-paced up to a generous idle timeout and reproduction speed is
never scored. A config deviation (say for paediatric use, where
presentation pacing measurably moves performance: Simpson 2021,
PMC8366059) is allowed but lands in block_stats so the analysis can
split those blocks out.

BIMODAL PRESENTATION. Each playback item lights the lane tile AND
buzzes that finger with simultaneous onset: spatially and temporally
congruent multisensory stimulation aids encoding and learning relative
to unisensory input (Shams and Seitz 2008, Trends in Cognitive Sciences
12:411-417), and multisensory protocols are an active strand of
post-stroke cognitive rehab (Cheng 2022, J Clin Med 11:6324; Johansson
2012). Two honest limits: no study directly compares light-plus-buzz
against light-only in a span game, so the bimodal choice rests on the
general multisensory-learning literature, not a task-level trial; and
the ERM motors' mechanical rise time on this rig is a datasheet class
value, not a bench measurement (latency.measured), so onset
simultaneity is nominal. The buzz REINFORCES the light here;
buzz_hunt's SEQUENCE SPAN stage is where the tactile channel is tested
ALONE (tactile-only span caps out around 4 items in healthy adults,
far under the visual 6.2), and the two modes must not be collapsed:
that stage measures whether the hand can READ the buzzes, Echo
measures how much explicit sequence the player can HOLD. Both
docstrings say so.

THE MOTORS ARE SHOW-PHASE ONLY (2026-09). The rig buzzes during
playback and at no other time in a trial: a correct press during
reproduction gets a flash on its tile and nothing on its finger, the
trial close fires no confirmation buzz whatever cue.buzz_after says
(the engine's after-press cue is declined for every echo row), and no
feedback buzz exists. The tester's report was that a motor firing
under the finger being pressed reads as the rig answering back, not as
confirmation, and it muddles the one thing the buzz is for here, which
is marking the items to be remembered. The tone channel is untouched.

REPRODUCTION INPUT. Nothing in this mode asks for a held press: the
press detector reports a press at its rising edge and the mode scores
that event, so a tap of any length counts, on the sensors and on the
keyboard alike. Reproduction opens the moment the last item's light
goes off (its offset on the presentation grid), so a fast reply that
starts while the "Your turn" prompt is still appearing is a reply,
not a discarded playback press; presses that land while an item is
still being shown are logged as playback presses and let go, as
before.

SEQUENCE MATERIAL. Uniform random over the lanes in play with no
back-to-back repeats (a doubled item is indistinguishable from a
bounce-detected double press, and Corsi sequences never repeat a block
consecutively). Lane REVISITS within a sequence are allowed and
necessary above length 4: the stock SIMON toy has four lanes and
usable spans around 7 (Gendle and Ransom 2006, J Behav Neurosci Res
4:1-7), so revisiting material works as span material. This is a named
deviation from Corsi's nine distinct blocks, one more reason these
spans are within-person numbers only. Fresh sequences every trial:
SIMON grows ONE sequence by appending, so every prefix is rehearsed
many times before it fails, which inflates span and mixes repetition
learning into the measure. The ladder keeps the Simon feel; the
appending does not. (echo.cumulative turns classic appending back on
for play value; it is logged loudly and its numbers are not comparable
to ladder blocks.)

HEBB REPETITION. Every third trial secretly replays the participant's
hidden sequence (Hebb 1961; visuospatial confirmation Couture and
Tremblay 2007), the same schedule and name-seed recipe as buzz_hunt's
span stage (tag "echo_v1"), so the two modes' repetition-learning
slopes are comparable. Unlike buzz_hunt's per-length draws, the hidden
material here is PREFIX-STABLE: one fixed participant stream, and the
length-L hidden sequence is its first L items, so repeated material
keeps accumulating exposure as the ladder climbs and across sessions.
Repetition learning needs items to keep their serial positions and
neighbours (the chunking literature), which a prefix-stable stream
preserves and per-length redraws would not. Hebb trials render
identically to novel ones and count equally for the ladder; the
notebook separates them (span_all against span_novel) so the learned
sequence cannot silently inflate the span trajectory.

RELATION TO PATTERN MODE. pattern.py actively SUPPRESSES explicit
sequence knowledge (Boyd and Winstein: explicit knowledge impairs
implicit motor learning after stroke). Echo is the opposite task:
explicit memorisation IS the job. Keeping them separate modes is what
protects pattern's implicit measure; neither should ever be folded
into the other.

HANDS. One hand selected: that hand's four lanes. Both boards:
sequences draw over all EIGHT lanes (right 0..3 then left 4..7, the
engine's global numbering), crossing hands mid-sequence. That is a
bimanual span, a different and harder construct than unilateral span;
block_stats records n_lanes and the notebook never pools the two. If
the clinical question is per-hand span, the protocol answer is two
unilateral blocks, not one bilateral block. Hand balance in bilateral
material is soft: short random sequences cannot balance hands within a
trial, and forcing balance would make material predictable, so balance
is checked in analysis, not in generation.

SCORING AND FEEL. Points per correctly reproduced item plus a bonus
for a completed sequence; accuracy and completion only, never
reproduction speed (untimed-recall convention, and the same OPTIMAL
guard rail pattern mode enforces). A wrong press ends the attempt (the
sequence is either reproduced or it is not; playing on after an error
would change the task) but the wrong press is logged with its position
so the notebook can tell a transposition from an intrusion. Feedback
stays warm and stays on the screen: a correct-so-far press flashes its
tile, a correct echo gets a cheerful card, a wrong one gets a neutral
"almost" card, and a longest-echo banner marks new bests.

WHAT THIS MODE CANNOT CLAIM. Not a Corsi test: four or eight lanes
with revisits, bimodal presentation, press response instead of
pointing. Spans here are within-person tracking numbers and must never
be read against Kessels 2000 or Farrell Pagulayan 2006 norms. Span
games measure; they are not proven therapy, and no transfer claim is
made (working-memory training transfer is a contested literature). In
motor-impaired players a wrong press can be a motor slip rather than a
memory error; the calibrated light-press threshold and the self-paced
reproduction reduce that confound, and the logged inter-press
intervals and omission counts make it visible, but nothing removes it.
Display timing is 60 Hz quantised as everywhere in this app.
"""
from __future__ import annotations

import hashlib
import logging
import random
import time
from collections import deque
from typing import TYPE_CHECKING

import pygame

from ...data.logger import ContinuousTrialLog
from ...hardware.eeg_trigger import (CODES as EEG_CODES, response_code,
                                     stim_code)
from ...hardware.fsr_detector import PressEvent
from ..rest_skip import WaitSkip
from ..scoring import ScoreConfig, TrialResult
from ._keys import keymap_for_hand, resolve_key
from .buzz_hunt import pack_lanes
from .classic import PendingTrial

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


# ---- participant-stable material -------------------------------------------
def participant_echo_seed(name: str) -> int:
    """Deterministic hidden-sequence seed from the participant name.
    Same convention as pattern's participant_seed and buzz_hunt's
    participant_hebb_seed: trimmed and case-folded so "Basil " and
    "basil" share material, version-tagged so a future generator
    change cannot silently rewrite an existing participant's hidden
    stream."""
    norm = (name or "").strip().lower() or "anonymous"
    digest = hashlib.sha256(f"{norm}|echo_v1".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big")


def echo_stream(p_seed: int, lanes: list[int], length: int) -> list[int]:
    """The first `length` items of the participant's ONE hidden
    stream over this lane pool. Prefix-stable by construction: the
    stream is drawn once from (seed, pool) and truncated, so the
    length-5 hidden sequence extends the length-4 one by one item.
    That keeps every repeated item's serial position and neighbours
    fixed as the ladder climbs, which is what Hebb repetition
    learning needs (chunk formation), and it is the deliberate
    difference from buzz_hunt's per-length hidden draws. No
    back-to-back repeats, same rule as the novel material."""
    pool = sorted(int(x) for x in lanes)
    tag = f"{int(p_seed)}|{'-'.join(str(x) for x in pool)}"
    rng = random.Random(
        int.from_bytes(hashlib.sha256(tag.encode()).digest()[:8], "big"))
    out: list[int] = []
    while len(out) < int(length):
        pick = pool[rng.randrange(len(pool))]
        if out and pick == out[-1] and len(pool) > 1:
            continue
        out.append(pick)
    return out


def draw_echo_sequence(rng: random.Random, length: int,
                       lanes: list[int]) -> list[int]:
    """A fresh sequence for one trial: uniform over the lanes in play,
    no back-to-back repeats, revisits allowed (SIMON precedent; see
    the module docstring). Same shape as the hidden material so the
    two trial kinds cannot be told apart at the rig."""
    pool = sorted(int(x) for x in lanes)
    out: list[int] = []
    while len(out) < int(length):
        pick = pool[rng.randrange(len(pool))]
        if out and pick == out[-1] and len(pool) > 1:
            continue
        out.append(pick)
    return out


def pulses_from_params(waveform: str, p: dict) -> list:
    """Rebuild the playback pulse train from (waveform, params), as
    (lane, onset_s, duration_ms) tuples: the same notebook contract
    buzz_hunt's stimuli honour, so an echo trial row is auditable
    from its own columns."""
    if waveform != "echo_seq":
        raise ValueError(f"unknown echo waveform {waveform!r}")
    seq = [int(float(x)) for x in str(p["seq"]).split("-") if x != ""]
    ioi = float(p["ioi_ms"]) / 1000.0
    dur = float(p["pulse_ms"])
    return [(lane, i * ioi, dur) for i, lane in enumerate(seq)]


class EchoMode(WaitSkip):
    name = "Echo"

    # Points per correctly reproduced item (paid on partial attempts
    # too: partial-credit scoring is the better-behaved span quantity,
    # Conway 2005) plus the completed-sequence bonus taken from the
    # shared score config. Nothing here reads speed.
    ITEM_POINTS = 2
    # Gap between the "Watch the echo" card and the first item. The
    # turn hand-over has no gap of its own: reproduction opens at the
    # last item's offset (docstring: REPRODUCTION INPUT).
    LEAD_S = 1.0
    # The shortest silence between one item's light going off and the
    # next item's onset. A 10 mm coin ERM keeps vibrating for about
    # 115 ms after current off (Precision Microdrives 310-103 class
    # value, latency.* in the config), so a gap under that has two
    # fingers buzzing at once; one display frame of slack on top. The
    # ioi floor can never be tighter than item_on_s plus this.
    MOTOR_CLEAR_S = 0.15
    # Redraw budget for the second novel trial at a length: the two
    # trials per length must be different sequences (Kessels), and at
    # length 2 over four lanes identical draws are common enough to
    # guard against. Deterministic given the block rng.
    _REDRAW_TRIES = 40

    def __init__(self, engine: "GameEngine",
                 lanes: list[int],
                 p_seed: int, block_seed: int,
                 start_len: int, trials_per_len: int, max_len: int,
                 runs: int,
                 item_on_ms: float, ioi_ms: float,
                 hebb_every: int,
                 idle_timeout_s: float, rest_s: float,
                 fatigue_timeout_run: int, fatigue_rest_s: float,
                 session_cap_min: float,
                 cumulative: bool,
                 score_cfg: ScoreConfig,
                 demo_trials: int | None = None,
                 ioi_step_ms: float = 0.0,
                 ioi_floor_ms: float | None = None) -> None:
        self.engine = engine
        # Lanes in play: one hand's four, or all eight bilaterally
        # (right 0..3 then left 4..7, engine global numbering). Same
        # fallback shape as PatternMode so bare test constructions
        # behave.
        if len(lanes) >= 8:
            self.lanes = list(lanes)[:8]
        else:
            self.lanes = list(lanes)[:4]
            while len(self.lanes) < 4:
                self.lanes.append(len(self.lanes))
        self.n_lanes = len(self.lanes)
        self.p_seed = int(p_seed)
        self.block_seed = int(block_seed)
        self.score_cfg = score_cfg
        self.start_len = max(1, int(start_len))
        self.trials_per_len = max(1, int(trials_per_len))
        self.max_len = max(self.start_len, int(max_len))
        self.runs = max(1, int(runs))
        # Presentation rate is a pinned administration parameter, the
        # Berch lesson: a function of sequence length only (docstring:
        # PRESENTATION RATE), never of success within a length, and
        # the schedule actually used is recorded in block_stats. The
        # floor is the motor's: an item must be lit and buzzing long
        # enough to reach amplitude, and the next onset must wait for
        # the previous finger to stop (MOTOR_CLEAR_S).
        self.item_on_s = max(0.05, float(item_on_ms) / 1000.0)
        motor_floor_s = self.item_on_s + self.MOTOR_CLEAR_S
        self.ioi_s = max(motor_floor_s, float(ioi_ms) / 1000.0)
        self.ioi_step_s = max(0.0, float(ioi_step_ms) / 1000.0)
        floor = (self.ioi_s if ioi_floor_ms is None
                 else float(ioi_floor_ms) / 1000.0)
        self.ioi_floor_s = min(self.ioi_s, max(motor_floor_s, floor))
        # The ioi of the trial in flight, set per trial from the
        # schedule; ioi_s above is the start-length value.
        self._trial_ioi_s = self.ioi_s
        self.hebb_every = max(2, int(hebb_every))
        self.idle_timeout_s = max(1.0, float(idle_timeout_s))
        self.rest_s = max(0.0, float(rest_s))
        self.fatigue_run = max(1, int(fatigue_timeout_run))
        self.fatigue_rest_s = max(0.0, float(fatigue_rest_s))
        self.session_cap_s = float(session_cap_min) * 60.0
        self.cumulative = bool(cumulative) and demo_trials is None
        self.demo_trials = demo_trials
        if self.cumulative:
            # Play-value mode, said loudly at the one place the config
            # change is findable: appended material rehearses every
            # prefix, so cumulative spans are inflated and must never
            # be pooled with ladder spans (Gendle and Ransom's SIMON
            # spans of about 7 on four lanes against Corsi's 6.2 on
            # nine blocks).
            log.warning("echo: cumulative (classic Simon) mode is on; "
                        "this block's numbers are play value only and "
                        "not comparable to ladder blocks")

        self.block_rng = random.Random(self.block_seed)

        # Demo miniature (Test Mode): a fixed 3-trial ladder so a demo
        # still writes real rows of both trial kinds (trial 3 is the
        # hidden sequence under the shipped hebb_every), with rests
        # cut, matching the pattern / buzz_hunt demo convention.
        self._demo_plan: list[int] | None = None
        if demo_trials is not None:
            self._demo_plan = [2, 3, 3]
            self.rest_s = min(self.rest_s, 1.0)
            self.fatigue_rest_s = min(self.fatigue_rest_s, 1.0)

        # Ladder state.
        self.run_idx = 0
        self.length = self.start_len
        self.trial_in_len = 0                  # 0-based within length
        self._len_results: list[bool] = []
        # Trial state machine: announce -> play -> respond -> rest ...
        self.phase = "announce"
        self._announced = False
        self.active: PendingTrial | None = None
        self.trial_counter = 0
        self.sequence: list[int] = []
        self.is_hebb = False
        self._novel_at_len: list[list[int]] = []
        self._play_t0: float | None = None
        self._item_idx = 0
        self._lit_lane: int | None = None
        self._item_off_due: float | None = None
        self._turn_due: float | None = None
        self._respond_t0: float | None = None
        self._deadline: float | None = None
        self._entered: list[tuple[int, float]] = []
        self._match = 0
        self._rest_until: float | None = None
        self._rest_kind = "between"
        self._t0: float | None = None
        self._presses: deque[PressEvent] = deque()

        # Bookkeeping for block_stats and the notebook.
        self._records: list[dict] = []
        self._hebb_trials: list[int] = []
        self.playback_presses = 0
        self.best_len = 0
        self.total_correct = 0
        self._timeout_run = 0
        self._fatigue_triggers = 0
        self._run_end_reasons: list[str] = []
        self.end_reason: str | None = None

    # ---- the presentation schedule -----------------------------------------
    def ioi_for(self, length: int) -> float:
        """Onset-to-onset interval, seconds, for a sequence of this
        length: the start-length ioi less one step per extra item,
        never under the floor. A pure function of length and config,
        so two blocks under one config present every length at the
        same rate whatever their players did."""
        extra = max(0, int(length) - self.start_len)
        return max(self.ioi_floor_s, self.ioi_s - extra * self.ioi_step_s)

    def ioi_schedule_ms(self) -> dict[str, float]:
        """The whole schedule, start length to ceiling, in ms, for
        block_stats and the notebook's protocol check."""
        return {str(n): round(self.ioi_for(n) * 1000.0, 1)
                for n in range(self.start_len, self.max_len + 1)}

    # ---- plumbing ----------------------------------------------------------
    def queue_press(self, ev: PressEvent) -> None:
        self._presses.append(ev)

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN:
            # Keyboard stays wired even with boards attached, the
            # classic.py reasoning: a busted auto-detect must never
            # leave the therapist with no working input. Keyboard play
            # is a full equal here (the stimulus is on screen), unlike
            # the sensor-only modes.
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
                    # Keyboard presses bypass the FSR raw-log path, so
                    # mark the source the way every mode does (the
                    # mirror-mode fix generalised).
                    raw = getattr(self.engine, "raw_logger", None)
                    if raw:
                        raw.queue_event(
                            "press", lane=lane, t_perf=t_perf,
                            hand=self.engine.hand_mode,
                            detail="keyboard")

    @property
    def current_timeout_s(self) -> float:
        # The reproduction idle window, the only clock a response ever
        # runs against. Reproduction is self-paced and never scored on
        # speed, so this is a safety net, not a measure.
        return self.idle_timeout_s

    def on_resume(self, pause_dur: float) -> None:
        # Slide every absolute deadline forward so a pause cannot fire
        # an item early, time a reproduction out, or eat rest or cap
        # time. The armed wait moves via shift_wait, which the engine
        # calls alongside this.
        if self.active is not None:
            self.active.stim_t_perf += pause_dur
        for attr in ("_play_t0", "_item_off_due", "_turn_due",
                     "_respond_t0", "_deadline", "_rest_until", "_t0"):
            v = getattr(self, attr)
            if v is not None:
                setattr(self, attr, v + pause_dur)

    # ---- main tick ---------------------------------------------------------
    def update(self, dt: float) -> None:
        now = time.perf_counter()
        if self._t0 is None:
            self._t0 = now
        while self._presses:
            self._handle_press(self._presses.popleft(), now)
        if self.phase == "done":
            return
        if self.phase == "announce":
            if not self._announced:
                self._begin_announce(now)
            elif self._turn_due is not None and now >= self._turn_due:
                self._begin_play(now)
            return
        if self.phase == "play":
            self._play_frame(now)
        elif self.phase == "respond":
            self._respond_frame(now)
        elif self.phase == "rest":
            if self._rest_until is not None and now >= self._rest_until:
                self._leave_rest(now)

    # ---- announce ----------------------------------------------------------
    def _begin_announce(self, now: float) -> None:
        self._announced = True
        self._prepare_trial(now)
        self._set_message("Watch the echo...", 1.2)
        # _turn_due doubles as the announce deadline: one absolute
        # clock per phase transition keeps on_resume's shifting simple.
        self._turn_due = now + self.LEAD_S
        self.arm_wait("announce", self._turn_due,
                      self._begin_play, started_at=now)

    def _prepare_trial(self, now: float) -> None:
        length = self.length
        if self._demo_plan is not None:
            length = self._demo_plan[len(self._records)]
        trial_no = len(self._records) + 1
        # Hidden-sequence schedule: every hebb_every-th trial of the
        # block, the Hebb 1961 spacing, same counter shape as
        # buzz_hunt so the two modes' slopes line up. Cumulative mode
        # has no fresh draws to hide repeats among, so no Hebb trials.
        self.is_hebb = (not self.cumulative
                        and trial_no % self.hebb_every == 0)
        if self.cumulative:
            self.sequence = self._cumulative_sequence(length)
        elif self.is_hebb:
            self.sequence = echo_stream(self.p_seed, self.lanes, length)
            self._hebb_trials.append(trial_no)
        else:
            self.sequence = self._fresh_sequence(length)
        self.trial_counter += 1
        self._item_idx = 0
        self._match = 0
        self._entered = []
        self._lit_lane = None
        self._play_t0 = None
        self._respond_t0 = None
        self._deadline = None
        self.active = PendingTrial(
            trial_id=self.trial_counter,
            lane=self.sequence[0],
            stim_t_perf=now,
            keys_pressed=[],
            incorrect_presses=[],
        )
        # Per-trial CSV stamps, the buzz_hunt convention for modes
        # that never call on_stim_multi: the cue switch state for
        # cue_flags, the target on screen by design (watching it IS
        # the task), and the idle window as the row's timeout.
        cues = self.engine.cue_settings()
        self.engine._last_cue_code = cues.code
        self.engine._last_target_shown = True
        self.engine._last_stim_timeout_ms = self.idle_timeout_s * 1000.0
        self.engine._last_stim_delivered = None
        # A skipped forced rest means this trial starts on less
        # recovery than the fatigue rule asked for; the shared skip
        # path flagged it, and the flag lands here where the trial is
        # findable (the pattern-mode convention).
        skipped = self.take_skip_flag()
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "echo_trial", lane=self.sequence[0], t_perf=now,
                detail=(f"trial_id={self.trial_counter};"
                        f"len={len(self.sequence)};"
                        f"hebb={1 if self.is_hebb else 0};"
                        f"run={self.run_idx + 1}"
                        + (f";short_rest={skipped}" if skipped else "")),
                hand=self.engine.hand_mode)

    def _fresh_sequence(self, length: int) -> list[int]:
        """A novel draw, redrawn if it duplicates the other trial at
        this length: Kessels administers two DIFFERENT sequences per
        length, and at short lengths over four lanes identical draws
        happen often enough to matter."""
        seen = [s for s in self._novel_at_len if len(s) == length]
        for _ in range(self._REDRAW_TRIES):
            cand = draw_echo_sequence(self.block_rng, length, self.lanes)
            if cand not in seen:
                break
        self._novel_at_len.append(cand)
        return cand

    def _cumulative_sequence(self, length: int) -> list[int]:
        """Classic Simon material: one growing sequence per run,
        extended by one fresh item after each success, so every prefix
        is rehearsed. Non-comparable by design; see the docstring."""
        prev = self._records[-1]["played"] if self._records else []
        if prev and len(prev) + 1 == length:
            grown = list(prev)
            while True:
                pick = self.lanes[
                    self.block_rng.randrange(self.n_lanes)]
                if pick != grown[-1] or self.n_lanes == 1:
                    grown.append(pick)
                    return grown
        return draw_echo_sequence(self.block_rng, length, self.lanes)

    # ---- playback ----------------------------------------------------------
    def _begin_play(self, now: float) -> None:
        self.clear_wait()
        self.phase = "play"
        self._play_t0 = now
        self._item_idx = 0
        self._item_off_due = None
        self._turn_due = None
        self._trial_ioi_s = self.ioi_for(len(self.sequence))
        if self.active is not None:
            self.active.stim_t_perf = now
        self.engine.log_segment_start("stim", self.trial_counter,
                                      self.sequence[0], now)

    def _last_offset_due(self) -> float | None:
        """When the final item's light is due off, on the grid: the
        moment reproduction opens. None before playback starts."""
        if self._play_t0 is None or not self.sequence:
            return None
        return (self._play_t0
                + (len(self.sequence) - 1) * self._trial_ioi_s
                + self.item_on_s)

    def _play_frame(self, now: float) -> None:
        # Absolute item deadlines off the playback anchor, the
        # syllables lesson: re-anchoring each onset to the frame clock
        # adds the frame delay to every interval and stretches the
        # presentation grid the whole design pins.
        assert self._play_t0 is not None
        # Item offset first, so a flash ends on its own grid.
        if (self._item_off_due is not None and now >= self._item_off_due):
            self._item_off_due = None
            self._light_lane(None)
        n = len(self.sequence)
        if self._item_idx < n:
            due = self._play_t0 + self._item_idx * self._trial_ioi_s
            if now >= due:
                lane = self.sequence[self._item_idx]
                self._fire_item(lane, self._item_idx, now)
                self._item_off_due = now + self.item_on_s
                self._item_idx += 1
            return
        # All items played and the last light off: the show is over
        # and it is the patient's turn, with no gap of its own.
        if self._item_off_due is not None:
            return
        self._end_play(now)

    def _end_play(self, now: float) -> None:
        """Close the show phase and open reproduction. Reached from
        the play frame when the last light goes off, or from a press
        that lands at or after that offset (a fast reply)."""
        self._item_off_due = None
        self._light_lane(None)
        self.engine.log_segment_end("stim", self.trial_counter,
                                    self.sequence[-1], now)
        self._begin_respond(now)

    def _fire_item(self, lane: int, idx: int, now: float) -> None:
        """One playback item: tile light plus buzz, simultaneous
        onset, plus the cue tone where the shared switch asks for it.
        The light is unconditional (it IS the stimulus); the buzz and
        tone follow the cue.* switches so a researcher can run a
        visual-only block and cue_flags will say so."""
        cues = self.engine.cue_settings()
        self._light_lane(lane)
        delivered = None
        if cues.buzz_before and self.engine.source.provides_samples:
            ok = self.engine.pulse_motor(lane, self.item_on_s * 1000.0)
            delivered = bool(ok)
            if not ok:
                # A dropped buzz leaves the light carrying the item,
                # so the trial stands; the delivery flag on the row
                # says the bimodal claim does not hold for it.
                self.engine._block_stim_failures += 1
        if delivered is not None:
            last = getattr(self.engine, "_last_stim_delivered", None)
            self.engine._last_stim_delivered = (
                delivered if last is None else (last and delivered))
        if self.engine.audio is not None and cues.sound_before:
            try:
                self.engine.audio.play_stim(lane)
            except Exception:
                pass
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "stim", lane=lane, t_perf=now,
                detail=f"trial_id={self.trial_counter};echo_item={idx}",
                hand=self.engine.hand_mode)
        # EEG: each playback item is a cue-grammar stimulus. Armed on
        # the engine's pending list so the byte goes out after the
        # flip that shows the light, the same photon-anchored path
        # on_stim_multi uses; the byte codes the delivered channel mix
        # (existing stim band, no new codes).
        markers = getattr(self.engine, "markers", None)
        if markers is not None and markers.active:
            code = stim_code(cues.sound_before, cues.buzz_before, True)
            pending = getattr(self.engine, "_pending_eeg_stim", None)
            if pending is None:
                pending = self.engine._pending_eeg_stim = []
            pending.append((int(code), lane))

    # ---- reproduction ------------------------------------------------------
    def _begin_respond(self, now: float) -> None:
        self.phase = "respond"
        self._respond_t0 = now
        self._deadline = now + self.idle_timeout_s
        self._set_message("Your turn", 1.5)
        self.engine.log_segment_start("respond", self.trial_counter,
                                      self.sequence[0], now)

    def _respond_frame(self, now: float) -> None:
        if self._deadline is not None and now >= self._deadline:
            self._close(now, "omission")

    def _handle_press(self, ev: PressEvent, now: float) -> None:
        if self.phase == "play":
            # A press stamped at or after the last item's offset is a
            # fast reply, not a playback press: the show is over on
            # the grid even if this frame has not yet noticed. Open
            # reproduction and score the press below.
            last_off = self._last_offset_due()
            if (last_off is not None and self._item_idx >= len(self.sequence)
                    and ev.t_perf >= last_off):
                self._end_play(now)
        if self.phase in ("announce", "play"):
            # A press while the rig is presenting is logged and let
            # go: the target is on screen anyway, so buzz_hunt's
            # strict replay-restart rule protects nothing here, and
            # penalising eagerness would punish exactly the patients
            # this ladder is gentlest on.
            self.playback_presses += 1
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "press", lane=ev.lane, t_perf=ev.t_perf,
                    detail=(f"playback_press;"
                            f"trial_id={self.trial_counter}"),
                    hand=self.engine.hand_mode)
            return
        if self.phase != "respond" or self.active is None:
            return
        self._deadline = now + self.idle_timeout_s
        self.active.keys_pressed.append(ev.lane)
        self._entered.append((ev.lane, ev.t_perf))
        self._timeout_run = 0
        expected = self.sequence[self._match]
        correct = ev.lane == expected
        # Per-press response marker, standard bands: correctness plus
        # the lane actually pressed, at the press's own detector time.
        # The trial row goes out with a continuous log, so log_trial
        # will not add a second, trial-level response marker on top.
        send = getattr(self.engine, "_eeg_send", None)
        if callable(send):
            send(response_code("correct" if correct else "wrong",
                               ev.lane),
                 lane=ev.lane, t_event=ev.t_perf)
        if correct:
            self._match += 1
            # A correct-so-far press is answered on the screen only:
            # the motors are show-phase only (docstring: THE MOTORS
            # ARE SHOW-PHASE ONLY).
            self._echo_back(ev.lane, now)
            if self._match >= len(self.sequence):
                self._close(now, "correct")
        else:
            self.active.incorrect_presses.append((ev.lane, ev.t_perf))
            self._close(now, "wrong")

    def _echo_back(self, lane: int, now: float) -> None:
        """Screen-side acknowledgement of a correct-so-far press: a
        tile flash, plus the cue tone where the shared switch asks
        for it. Never a buzz: no STIM leaves this mode outside the
        show phase."""
        gp = self._gameplay_screen()
        if gp is not None and hasattr(gp, "lanes"):
            for ls in gp.lanes:
                if ls.lane == lane:
                    # Success green, matching the theme's success
                    # colour, without reaching for a screen object a
                    # bare test engine may not carry.
                    ls.flash((34, 197, 94), 0.25, now)
        cues = self.engine.cue_settings()
        if self.engine.audio is not None and cues.sound_before:
            try:
                self.engine.audio.play_stim(lane)
            except Exception:
                pass

    # ---- closing -----------------------------------------------------------
    def _close(self, now: float, kind: str) -> None:
        trial = self.active
        if trial is None:
            return
        self.active = None
        self.engine.log_segment_end("respond", self.trial_counter,
                                    self.sequence[0], now)
        self._light_lane(None)
        n_right = self._match
        length = len(self.sequence)
        correct = kind == "correct"
        if correct:
            outcome = TrialResult(
                label="Great",
                points=(self.score_cfg.great_points
                        + self.ITEM_POINTS * length),
                rt_ms=None)
            self.total_correct += 1
            if length > self.best_len:
                self.best_len = length
                self._set_message(f"Longest echo: {length}", 2.0,
                                  kind="best")
            else:
                self._set_message("Great echo!", 1.5, kind="success")
        else:
            # Partial credit still pays per item (never punishing),
            # and the card stays neutral: an "almost" is information,
            # not a penalty.
            outcome = TrialResult(
                label="Miss",
                points=(self.score_cfg.miss_points
                        + self.ITEM_POINTS * n_right),
                rt_ms=None)
            if kind == "omission":
                self._set_message(
                    f"Time's up. {n_right} of {length}", 1.8)
            else:
                self._set_message(
                    f"Almost! {n_right} of {length}", 1.8)
        # Press offsets from the "Your turn" moment, milliseconds,
        # packed on the row: the notebook's inter-press intervals (the
        # eCorsi 600 ms motor baseline analogue) fall out of these,
        # and they never touch the score.
        r0 = self._respond_t0 if self._respond_t0 is not None else now
        press_offsets = "-".join(
            f"{(t - r0) * 1000.0:.0f}" for _l, t in self._entered)
        trial_idx = (self.trial_in_len + 1
                     if self._demo_plan is None else 1)
        stimulus = (
            f"echo;len={length};trial={trial_idx};"
            f"run={self.run_idx + 1};"
            f"hebb={1 if self.is_hebb else 0};"
            f"played={pack_lanes(self.sequence)};"
            f"pressed={pack_lanes([l for l, _t in self._entered])};"
            f"n_right={n_right};outcome={kind};"
            f"pt={press_offsets}")
        play_t0 = self._play_t0 if self._play_t0 is not None else now
        stim_end = (play_t0 + (length - 1) * self._trial_ioi_s
                    + self.item_on_s)
        info = ContinuousTrialLog(
            waveform="echo_seq",
            params={"seq": pack_lanes(self.sequence),
                    "pulse_ms": round(self.item_on_s * 1000.0, 1),
                    # The ioi THIS trial ran at (the length schedule),
                    # so a row is auditable on its own.
                    "ioi_ms": round(self._trial_ioi_s * 1000.0, 1),
                    "hebb": 1 if self.is_hebb else 0},
            seed=self.block_seed,
            segments=[("stim", play_t0, stim_end), ("respond", r0, now)])
        # after_press_cue False: the trial close must not buzz the
        # finger either, whatever cue.buzz_after says (docstring: THE
        # MOTORS ARE SHOW-PHASE ONLY).
        self.engine.log_trial(trial, outcome, now, stimulus=stimulus,
                              correct_lanes=list(self.sequence),
                              continuous=info, after_press_cue=False)
        # Feedback markers, optional as everywhere (FRN work only).
        # The mode emits them itself because continuous rows skip the
        # engine's feedback path by contract.
        if getattr(self.engine, "_eeg_feedback_markers", False):
            send = getattr(self.engine, "_eeg_send", None)
            if callable(send):
                send(EEG_CODES["feedback_positive" if correct
                               else "feedback_negative"], t_event=now)
        self._records.append({
            "trial": len(self._records) + 1,
            "run": self.run_idx + 1,
            "len": length,
            "trial_at_len": trial_idx,
            "hebb": self.is_hebb,
            "outcome": kind,
            "n_right": n_right,
            "played": list(self.sequence),
            "pressed": [l for l, _t in self._entered],
            "ioi_ms": round(self._trial_ioi_s * 1000.0, 1),
        })
        self._after_trial(now, kind, correct)

    def _after_trial(self, now: float, kind: str, correct: bool) -> None:
        # Fatigue guard first: two straight omissions is a hand that
        # has stopped answering, not two memory samples. Only a press
        # resets the streak (in _handle_press); the forced rest does
        # NOT, deliberately unlike pattern's guard, because silence
        # that continues straight through the rest must reach the
        # second trigger and end the block as "fatigue" rather than
        # bleed omissions into the ladder until both_failed reports
        # exhaustion as a memory result. The omission that trips the
        # guard never reaches the ladder bookkeeping below either:
        # exhaustion is not a failed memory trial, so the slot
        # replays after the forced rest instead of ending the ladder,
        # and the trial row plus per_length in block_stats still
        # carry what happened.
        if kind == "omission":
            self._timeout_run += 1
        if self._timeout_run >= self.fatigue_run:
            self._fatigue_triggers += 1
            if self._fatigue_triggers >= 2:
                self._set_message("Great effort. Session done", 2.0)
                self._end("fatigue")
                return
            self._enter_rest(now, self.fatigue_rest_s, "forced",
                             "Take a breather")
            return
        # Session cap, at a trial close only.
        if (self._t0 is not None
                and (now - self._t0) > self.session_cap_s):
            self._set_message("Session complete", 2.0)
            self._end("time_cap")
            return
        # Demo miniature: fixed plan, no ladder rules.
        if self._demo_plan is not None:
            if len(self._records) >= len(self._demo_plan):
                self._end("completed")
            else:
                self._enter_rest(now, self.rest_s, "between", "")
            return
        if self.cumulative:
            if correct:
                self.length = len(self.sequence) + 1
                self._enter_rest(now, self.rest_s, "between", "")
            else:
                self._finish_run(now, "cumulative_miss")
            return
        # The Kessels ladder: both trials at a length always run;
        # at least one correct advances, both failing ends the run.
        self._len_results.append(correct)
        self.trial_in_len += 1
        if self.trial_in_len < self.trials_per_len:
            self._enter_rest(now, self.rest_s, "between", "")
            return
        passed = any(self._len_results)
        self._len_results = []
        self.trial_in_len = 0
        if not passed:
            self._finish_run(now, "both_failed")
        elif self.length >= self.max_len:
            self._finish_run(now, "ceiling")
        else:
            self.length += 1
            self._enter_rest(now, self.rest_s, "between", "")

    def _finish_run(self, now: float, reason: str) -> None:
        self._run_end_reasons.append(reason)
        self.run_idx += 1
        if self.run_idx >= self.runs:
            self._end("completed")
            return
        # Optional extra ladder (echo.runs): fresh climb from the
        # start length; the Kessels standard is one, so this is off
        # by default.
        self.length = self.start_len
        self.trial_in_len = 0
        self._len_results = []
        self._novel_at_len = []
        self._enter_rest(now, max(self.rest_s, 2.0), "between",
                         "New round")

    # ---- rests and endings -------------------------------------------------
    def _enter_rest(self, now: float, dur_s: float, kind: str,
                    msg: str) -> None:
        self.phase = "rest"
        self._rest_kind = kind
        self._rest_until = now + max(0.0, dur_s)
        send = getattr(self.engine, "_eeg_send", None)
        if kind == "forced" and callable(send):
            send(EEG_CODES["rest_start"], t_event=now)
        if kind == "forced":
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "fatigue_rest", t_perf=now,
                    detail=f"after_trial={len(self._records)}",
                    hand=getattr(self.engine, "hand_mode", "right"))
        # Skippable like every enforced wait; skipped_rest lands in
        # wait_skip_stats and raw.csv through the shared path.
        self.arm_wait("fatigue_rest" if kind == "forced" else "rest",
                      self._rest_until, self._leave_rest,
                      started_at=now,
                      protects=("recovery before play resumes"
                                if kind == "forced" else None))
        if msg:
            self._set_message(msg, min(3.0, max(1.5, dur_s)))
        self._clear_lanes()

    def _leave_rest(self, now: float) -> None:
        self.clear_wait()
        if self._rest_kind == "forced":
            send = getattr(self.engine, "_eeg_send", None)
            if callable(send):
                send(EEG_CODES["rest_end"], t_event=now)
        self._rest_until = None
        self.phase = "announce"
        self._announced = False

    def _end(self, reason: str) -> None:
        self.phase = "done"
        self.end_reason = reason
        self.clear_wait()
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
                gp.set_message(text, duration_s)

    def _light_lane(self, lane: int | None) -> None:
        """Playback lighting: exactly one tile active at a time, no
        timing bar (there is nothing to respond to yet). The rising
        edge fires the gameplay screen's ignition ring, so each item
        lands as an event rather than a fade."""
        gp = self._gameplay_screen()
        if gp is None or not hasattr(gp, "lanes"):
            return
        self._lit_lane = lane
        for ls in gp.lanes:
            ls.active = (lane is not None and ls.lane == lane)
            ls.clear_timing()

    def _clear_lanes(self) -> None:
        self._light_lane(None)

    # ---- block summary -----------------------------------------------------
    def block_stats(self) -> dict:
        """What finish_block folds into metadata.json: the Kessels
        numbers, per-length outcomes, the hidden-trial indices, and
        every presentation parameter actually used (the Berch lesson:
        the parameters that varied across 25 years of Corsi labs are
        exactly the ones a block must pin next to its data)."""
        span = max((r["len"] for r in self._records
                    if r["outcome"] == "correct"), default=0)
        per_length: list[dict] = []
        for r in self._records:
            key = (r["run"], r["len"])
            slot = next((p for p in per_length
                         if (p["run"], p["len"]) == key), None)
            if slot is None:
                slot = {"run": r["run"], "len": r["len"],
                        "outcomes": []}
                per_length.append(slot)
            slot["outcomes"].append(r["outcome"])
        return {
            "participant_seed": self.p_seed,
            "block_seed": self.block_seed,
            "n_lanes": self.n_lanes,
            "start_len": self.start_len,
            "trials_per_len": self.trials_per_len,
            "max_len": self.max_len,
            "runs": self.runs,
            "item_on_ms": round(self.item_on_s * 1000.0, 1),
            # ioi_ms is the START-length interval; the schedule below
            # is what every length actually ran at (docstring:
            # PRESENTATION RATE), and motor_clear_ms the floor rule.
            "ioi_ms": round(self.ioi_s * 1000.0, 1),
            "ioi_step_ms": round(self.ioi_step_s * 1000.0, 1),
            "ioi_floor_ms": round(self.ioi_floor_s * 1000.0, 1),
            "ioi_schedule_ms": self.ioi_schedule_ms(),
            "motor_clear_ms": round(self.MOTOR_CLEAR_S * 1000.0, 1),
            "idle_timeout_s": self.idle_timeout_s,
            "rest_s": self.rest_s,
            "hebb_every": self.hebb_every,
            "cumulative": self.cumulative,
            "demo": self.demo_trials is not None,
            "span": span,
            "total_correct": self.total_correct,
            # The Kessels product score: span x correct sequences.
            "product_score": span * self.total_correct,
            "n_trials": len(self._records),
            "n_omissions": sum(1 for r in self._records
                               if r["outcome"] == "omission"),
            "per_length": per_length,
            "hebb_trials": list(self._hebb_trials),
            "playback_presses": self.playback_presses,
            "fatigue_rests": self._fatigue_triggers,
            "run_end_reasons": list(self._run_end_reasons),
            **self.wait_skip_stats(),
            "end_reason": self.end_reason,
        }
