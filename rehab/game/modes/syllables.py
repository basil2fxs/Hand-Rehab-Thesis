"""Syllable Beats mode: phonological awareness training for children
with reading difficulty, played by tapping the beats inside words on
the four force sensors. A different population from the rest of this
suite, with a different evidence base; the claim limits at the bottom
of this docstring are part of the design.

WHY THIS DESIGN. Phonological awareness training causally improves
reading: Bradley and Bryant (1983, Nature) showed it longitudinally,
and the National Reading Panel meta-analysis (Ehri, Nunes, Willows,
Schuster, Yaghoub-Zadeh and Shanahan, 2001, Reading Research
Quarterly; 52 studies) put PA instruction at d = 0.86 on PA and 0.53
on reading, the strongest claim anywhere in this mode. Segmentation
develops from large units to small: Liberman, Shankweiler, Fischer and
Carter (1974, J Exp Child Psychol) showed it with a TAPPING task
(46 percent of 4 year olds could tap syllables, none phonemes), and
Anthony and Francis (2005) and Ziegler and Goswami (2005, grain size
theory) confirm the progression, which is why the level ladder runs
syllables before onset-rime before phonemes and why a tapping device
is a natural fit: the canonical measure IS tapping. The temporal
sampling framework (Goswami 2011, Trends Cogn Sci) ties dyslexia to
impaired entrainment at slow speech rhythms; Thomson and Goswami
(2008, J Physiol Paris) found dyslexic children tap less accurately
to metronomes at 1.5 to 2.5 Hz with 2 Hz the key marker, and rhythm
training has transferred to PA and reading in two RCTs (Flaugnacco et
al. 2015, PLOS ONE; Descamps et al. 2025, Scientific Reports,
Mila-Learn), though the wider music-transfer literature is mixed
(Dumont et al. 2017), so transfer is plausible, not proven.

PARAMETER DEFENCES, in the order they appear in config:
- 500 ms beat interval (2 Hz): the Thomson and Goswami deficit marker,
  and inside the 400 to 500 ms spontaneous motor tempo of 4 to 8 year
  olds (Drake, Jones and Baruch 2000; McAuley et al. 2006; Repp and Su
  2013), so children synchronise best near it. 667 ms (1.5 Hz) is the
  slow option for younger children, 400 ms (2.5 Hz) the stretch, the
  other two rates Thomson and Goswami tested.
- plus or minus 150 ms on-beat window: a literature-informed design
  choice sized to child asynchrony SDs (Repp and Su 2013); raw signed
  asynchronies are logged regardless so the analysis can re-window.
- stress ratio 2.0 (stressed tap at least twice the trial's median
  peak, unstressed under 1.5x): a design choice, relative not absolute
  because child force output varies widely; no literature number
  exists for a tapped stress ratio. It is the production analogue of
  the DeeDee stress-perception deficit (Goswami et al. 2010, 2013).
- 10 words per round, breaks between rounds, 20 minute hard cap,
  8 of 10 promotion / under 5 of 10 demotion: mastery-criterion
  conventions from PA programs; the session dose keeps the program
  inside the NRP's effective 5 to 18 hour window, where 20 to 75 hour
  programs did WORSE (Ehri et al. 2001).
- graphemes fade in at level 6 after a correct response because PA
  plus letters beats PA alone (d = 0.67, Ehri et al. 2001); letters
  are feedback, never a prerequisite, so a non-reading child can
  always play.
- feedback is visual and kind (blocks fill, extra taps show grey,
  missing stay hollow, one replay, no punishment sound) and there is
  deliberately NO speeded-naming drill: naming speed does not respond
  to direct training (de Jong and Vrielink 2004; Norton and Wolf
  2012).

LEVEL LADDER (syllables.level, researcher-set):
  1 counting: free pace, any fingers, 1 to 3 syllable words; success
    is tap count = syllable count.
  2 finger-mapped: taps must run index to little, one finger per
    syllable, left to right like the blocks; adds 4-syllable words.
  3 beat-paced: as 2, at the configured beat (4-tick count-in, one
    tap per beat); per-tap signed asynchrony is scored. This is the
    temporal-sampling core.
  4 stress marking: as 3, plus press noticeably harder on the
    stressed syllable (the force sensors as an accent channel).
  5 onset-rime: CVC-family words, two taps, onset then rime on the
    first two fingers; the display splits into a small and a large
    block.
  6 phoneme counting: transparent-spelling words, one tap per phoneme
    (2 to 4), graphemes fade into the blocks after a correct response.
Band promotion (A to B to C) runs inside a block on the brief's 8 of
last 10 / under 5 of 10 rule and every firing is logged to raw.csv.
LEVEL movement is across sessions and needs the session history this
app deliberately does not keep, so the level is a config knob the
researcher moves using the brief's unlock rule (80 percent at top
band in two consecutive sessions).

ASSET REALITY. The brief's recorded words and picture library do not
exist and cannot be added, so the word is shown as large text split
into per-syllable blocks that light in rhythm, the per-finger buzzer
pulses in sequence through the shared cue path (one motor per board
at a time, which is exactly what a syllable beat needs), and each
syllable onset plays the finger's cue tone through the existing audio
engine. On macOS, if the `say` command exists, the word is spoken
once at ATTEND time in a background process (never blocking the frame
loop, failing silent); everywhere else the mode is fully usable
without speech. The word list ships in syllables_words.py with the
grading rationale in its docstring. The buzzer and tone ride the
shared cue.* switches, so under the shipped defaults the model is
audio-tactile-visual, and any tap timing it trains is timing to that
mix, not to sound alone; cue_flags on every trial row records which
channels a block actually ran, which is what lets sessions played
with the vibration off (a child may ask for that) be separated from
full-cue sessions in the analysis instead of pooled.

TRIAL LOOP: ATTEND (word appears, spoken once if possible) -> MODEL
(blocks light left to right at the beat interval, buzzer and tone per
syllable) -> COUNT-IN (paced levels only, metronome ticks) -> RESPOND
(taps collected from the press detector, whose timestamps come from
the 200 Hz sample stream, not the frame clock) -> FEEDBACK (blocks
fill or hollow; full success pulses and chimes through the shared
after-press cue path) -> one model REPLAY on error -> next word.
Warm-up before the first word is 10 paced taps to the metronome with
no word: a tap threshold check and a per-session sensorimotor
synchronisation probe, logged to raw.csv.

WHAT ONE TRIAL LOGS (fixed CSV schema, so the word-level detail rides
the stimulus column the way pattern mode rides it):
- stimulus: semicolon-separated key=value string, documented here
  because the notebook parses it:
    word;lvl=<level>;band=<A|B|C>;nsyll=<target taps>;stress=<idx>;
    paced=<0|1>;ioi=<ms>;replay=<0|1>;err=<error type or ok>;
    taps=<lane>:<t_ms>:<peak>,...;asyn=<a1>,<a2>,...
  taps are 1-indexed lanes with time in ms from RESPOND start and the
  tap's peak force (counts above baseline; empty in keyboard mode).
  asyn appears on paced trials only: per-tap signed asynchrony in ms,
  negative = early, the rhythm-mode sign convention.
- time_difference_ms: first-tap reaction time on free-paced levels;
  MEAN signed asynchrony on paced levels (the rhythm convention).
- lane / correct_keys: the trial is keyed on the first required
  finger, with every required finger in correct_keys. Per-lane charts
  mean little here because fingers are syllable positions, not
  targets; the analysis works from the stimulus field.
- error types (err=): timeout, missing_tap, extra_tap, wrong_order,
  off_beat, wrong_stress, ok.
- outcome labels: Great = every level criterion met, Good = right
  count but a level criterion missed, Miss = wrong count or timeout.
  No penalties are applied anywhere; this mode is for children.

BOTH HANDS. A child with both hands on the device can use both:
syllable position n maps to finger n of EITHER hand, so pressing the
left index or the right index both count as position 1. The design
follows from what the mode measures: the levels test WHICH beat the
child marks and WHEN, never which hand carries it, and the canonical
segmentation measure (Liberman's tapping task) has no hand
requirement, so demanding a particular hand would add a rule the
construct does not contain and would hand out errors that say
nothing about phonological awareness. Order checking is therefore
done on positions, not lanes, and there is no such thing as a
"wrong hand" anywhere in the mode: the child is never told to
switch. The model phase still buzzes exactly one finger per
syllable (one motor per board), and WHICH hand carries each model
buzz comes off a shuffle bag over the hands, so across a block both
hands are modelled equally, the same paired balance the adult modes
use; the modelled lanes ride the stimulus string (model=) so the
analysis can split taps and models by hand. On screen the blocks
are hand-neutral (they carry finger colours, not sides) and the
finger row shows both hands, the left one mirrored.

WHAT THIS MODE CANNOT CLAIM. It trains and measures in-task
behaviour: syllable segmentation, beat synchronisation, stress
marking. It is not a dyslexia treatment and cannot claim to improve
reading (that needs standardised pre and post measures and a
control); it is not a diagnostic instrument and must never label a
child dyslexic. The tactile channel is engagement and cueing, not a
claimed active ingredient: the multisensory element of structured
literacy has no demonstrated additive effect (Stevens et al. 2021,
meta-analytic null). The hardware was built and ethically scoped for
adult stroke rehabilitation; use with children needs new ethics
approval, a finger-spacing check and hygiene procedures, and none of
these parameters have been validated on children with this device, so
the first study is feasibility and acceptability, not efficacy.
"""
from __future__ import annotations

import logging
import random
import shutil
import subprocess
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

import pygame

from ...hardware.fsr_detector import PressEvent
from ..scheduling import BalancedScheduler
from ..scoring import ScoreConfig, TrialResult
from ._keys import keymap_for_hand, resolve_key
from .classic import PendingTrial
from .syllables_words import Word, words_for

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


BANDS = ("A", "B", "C")


@dataclass
class Tap:
    """One accepted tap in the response phase. Time comes from the
    press detector, which stamps events from the 200 Hz sample stream
    (5 ms resolution), never from the 60 Hz frame clock."""
    lane: int
    t_perf: float
    peak: float | None = None      # counts above baseline; None = no FSR data


@dataclass
class TrialRecord:
    """What one closed word-trial contributes to block_stats."""
    word: str
    n_syll: int
    band: str
    correct: bool
    error: str
    asynchronies: list[float] = field(default_factory=list)
    stress_ratio: float | None = None
    stress_correct: bool | None = None


class SyllablesMode:
    name = "Syllables"

    # Once the expected number of taps has landed, wait this long for a
    # possible extra tap before scoring, so feedback still starts
    # within the brief's 200 ms of the last tap while an extra tap is
    # not silently cut off.
    SETTLE_S = 0.2
    # How long the success or error feedback stays on screen before the
    # replay or the next word. Long enough for a child to see every
    # block's fill state, short enough that 10 words stay lively.
    FEEDBACK_S = 1.4

    def __init__(self, engine: "GameEngine",
                 lanes: list[int],
                 level: int,
                 band: str,
                 ioi_ms: float,
                 words_total: int,
                 round_size: int,
                 break_s: float,
                 warmup_taps: int,
                 attend_s: float,
                 free_window_s: float,
                 count_in_beats: int,
                 grace_ms: float,
                 on_beat_window_ms: float,
                 stress_ratio: float,
                 unstressed_max_ratio: float,
                 tap_debounce_ms: float,
                 inter_trial_gap_ms: float,
                 session_cap_min: float,
                 replay_on_error: bool,
                 speak_words: bool,
                 say_voice: str | None,
                 score_cfg: ScoreConfig,
                 seed: int = 0,
                 demo_trials: int | None = None,
                 lanes_by_hand: dict[str, list[int]] | None = None,
                 ) -> None:
        self.engine = engine
        # The lanes of each playing hand, indexed by syllable
        # position: lanes[0] carries syllable 1 (index finger) through
        # lanes[3] (little finger). With both hands connected the
        # position maps to finger n of EITHER hand (see docstring);
        # self.lanes stays the first hand's four for the paths that
        # need one canonical lane per position (CSV keying, block
        # text), and _position_of resolves any hand's lane back to
        # its position.
        if lanes_by_hand and len([h for h, v in lanes_by_hand.items()
                                  if v]) > 1:
            self.hands = {h: list(v)[:4]
                          for h, v in lanes_by_hand.items() if v}
        else:
            four = list(lanes)[:4]
            while len(four) < 4:
                four.append(len(four))
            # Key the single hand by what the session actually plays,
            # so the finger row can mirror a left-hand session.
            hand_name = str(getattr(engine, "hand_mode", "right"))
            if hand_name not in ("left", "right"):
                hand_name = "right"
            self.hands = {hand_name: four}
        self.hand_names = list(self.hands)
        self.bilateral = len(self.hand_names) > 1
        self.lanes = self.hands[self.hand_names[0]]
        self.level = max(1, min(6, int(level)))
        self.band = band if band in BANDS else "A"
        self.ioi_s = max(0.2, float(ioi_ms) / 1000.0)
        self.round_size = max(1, int(round_size))
        self.break_s = max(0.0, float(break_s))
        self.warmup_total = max(0, int(warmup_taps))
        self.attend_s = max(0.2, float(attend_s))
        self.free_window_s = float(free_window_s)
        self.count_in_beats = max(0, int(count_in_beats))
        self.grace_s = max(0.0, float(grace_ms) / 1000.0)
        self.on_beat_window_s = float(on_beat_window_ms) / 1000.0
        self.stress_ratio = float(stress_ratio)
        self.unstressed_max_ratio = float(unstressed_max_ratio)
        self.tap_debounce_s = max(0.0, float(tap_debounce_ms) / 1000.0)
        self.inter_trial_gap_s = max(0.0, float(inter_trial_gap_ms) / 1000.0)
        self.session_cap_s = float(session_cap_min) * 60.0
        self.replay_on_error = bool(replay_on_error)
        self.speak_words = bool(speak_words)
        self.say_voice = say_voice
        self.score_cfg = score_cfg
        self.demo = demo_trials is not None
        if self.demo:
            # Test Mode: a handful of words, no warm-up, token breaks,
            # so a supervisor demo reaches Results inside a minute.
            self.words_total = max(2, int(demo_trials))
            self.warmup_total = 0
            self.break_s = min(self.break_s, 1.0)
        else:
            self.words_total = max(1, int(words_total))

        self.rng = random.Random(int(seed))
        self._bag: list[Word] = []
        # Which hand carries each model buzz: a shuffle bag over the
        # hands so both are modelled equally across a block, in an
        # order the child cannot predict. One entry, one syllable.
        self._model_hand_order = BalancedScheduler(
            list(range(len(self.hand_names))), self.rng,
            avoid_repeats=False)
        # The lanes the model phase actually buzzed for the current
        # word, in onset order, packed into the stimulus string when
        # both hands play so the analysis can split models by hand.
        self._model_lanes: list[int] = []

        # Session flow state. Phases:
        #   warmup -> (attend -> model -> countin -> respond -> feedback
        #   -> replay?) per word -> break between rounds -> done.
        self.phase = "warmup" if self.warmup_total else "gap"
        self.word: Word | None = None
        self.trial_counter = 0
        self.words_done = 0
        self.active: PendingTrial | None = None
        self.taps: list[Tap] = []
        self._presses: deque[PressEvent] = deque()
        self._t0: float | None = None          # session clock (hard cap)
        self._phase_t0: float | None = None
        self._phase_until: float | None = None
        self._model_idx = -1                    # syllable lit during MODEL
        self._model_next_t: float | None = None
        self._respond_t0: float | None = None
        self._beat_times: list[float] = []      # paced tap targets
        self._replayed = False                  # one replay per word, max
        self._pending_replay = False
        self._last_result: dict | None = None   # screen reads for feedback
        self._last_tap_t: dict[int, float] = {}  # per-lane debounce
        self._say_proc: subprocess.Popen | None = None
        self.end_reason: str | None = None

        # Warm-up probe state: the child taps along with the metronome,
        # any finger, one tap per beat. Logged to raw.csv per tap.
        self._warmup_beats: list[float] = []
        self._warmup_asyn: list[float] = []
        self._warmup_done = 0

        # Aggregates for block_stats.
        self._records: list[TrialRecord] = []
        self._band_trace: list[str] = [self.band]
        self._recent: deque[bool] = deque(maxlen=10)
        self._since_band_change = 0

    # ---- material ----------------------------------------------------------
    def _draw_word(self) -> Word:
        """Shuffle-bag draw over the current level and band pool, so a
        round cannot repeat one word while another never comes up. The
        bag rebuilds when it empties or after a band change."""
        if not self._bag:
            self._bag = list(words_for(self.level, self.band))
            self.rng.shuffle(self._bag)
        return self._bag.pop()

    def units_for(self, word: Word) -> list[str]:
        """The text chunks the child taps out, one per block: syllables
        at levels 1 to 4, onset and rime at 5, graphemes at 6."""
        if self.level >= 6 and word.graphemes:
            return list(word.graphemes)
        if self.level == 5 and word.onset_rime:
            return list(word.onset_rime)
        return list(word.syllables)

    @property
    def n_expected(self) -> int:
        return len(self.units_for(self.word)) if self.word else 0

    @property
    def paced(self) -> bool:
        # Levels 3 and 4 are the beat-paced rungs of the ladder.
        return self.level in (3, 4)

    @property
    def order_required(self) -> bool:
        # Level 1 is counting with any fingers; everything above maps
        # syllable position onto finger order.
        return self.level >= 2

    def expected_lanes(self) -> list[int]:
        """One canonical lane per expected position (the first hand's
        fingers), used where the plumbing wants a single lane. The
        press path accepts either hand via _position_of."""
        return [self.lanes[i] for i in range(self.n_expected)]

    def acceptable_lanes(self) -> list[int]:
        """Every lane that can legally carry some expected position:
        both hands' copies of positions 0..n-1. This is what the
        trial's correct_keys records in bilateral play, so the CSV
        says the left and right finger were both acceptable."""
        return sorted(hands[i]
                      for hands in self.hands.values()
                      for i in range(min(self.n_expected, len(hands))))

    def _position_of(self, lane: int) -> int | None:
        """Which syllable position a lane carries, whichever hand it
        belongs to, or None for a lane outside the game."""
        for lanes in self.hands.values():
            if lane in lanes:
                return lanes.index(lane)
        return None

    # ---- plumbing shared with the other modes ------------------------------
    def queue_press(self, ev: PressEvent) -> None:
        self._presses.append(ev)

    @property
    def current_timeout_s(self) -> float:
        """The response window for the current word. The engine logs it
        as the trial's RT censoring limit (timeout_ms column)."""
        if self.paced:
            n = max(1, self.n_expected)
            return (self.count_in_beats + n) * self.ioi_s + self.grace_s
        return self.free_window_s

    def on_resume(self, pause_dur: float) -> None:
        # Session-level clocks slide forward like every other mode.
        for attr in ("_t0", "_phase_t0", "_phase_until", "_model_next_t",
                     "_respond_t0"):
            v = getattr(self, attr)
            if v is not None:
                setattr(self, attr, v + pause_dur)
        self._beat_times = [t + pause_dur for t in self._beat_times]
        self._warmup_beats = [t + pause_dur for t in self._warmup_beats]
        # A pause mid-word breaks the rhythm the trial is measuring
        # (taps already landed are on the old clock, beats on the new),
        # so the fair move is to restart the word from ATTEND rather
        # than salvage half a trial. Nothing was logged for it yet.
        if self.phase in ("attend", "model", "countin", "respond"):
            self.active = None
            self._begin_word(time.perf_counter(), reuse_word=True)

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
                    self.queue_press(PressEvent(
                        lane=lane, t_perf=time.perf_counter(),
                        value=0, baseline=0.0,
                        hand=self.engine.hand_mode,
                    ))

    # ---- main tick ---------------------------------------------------------
    def update(self, dt: float) -> None:
        self._tick(time.perf_counter())

    def _tick(self, now: float) -> None:
        if self._t0 is None:
            self._t0 = now
            self._enter_phase(self.phase, now)
        self._reap_say()
        while self._presses:
            self._handle_press(self._presses.popleft(), now)
        if self.phase == "done":
            return
        if self.phase == "warmup":
            self._update_warmup(now)
        elif self.phase == "break":
            if self._phase_until is not None and now >= self._phase_until:
                self._begin_word(now)
        elif self.phase == "gap":
            if self._phase_until is None or now >= self._phase_until:
                self._begin_word(now)
        elif self.phase == "attend":
            if now >= self._phase_until:
                self._enter_phase("model", now)
        elif self.phase in ("model", "replay"):
            self._update_model(now)
        elif self.phase == "countin":
            if now >= self._phase_until:
                # Anchor the response beats on the scheduled count-in
                # end, which sits on the model's grid, not on the frame
                # that noticed it: the child is scored against the beat
                # they heard, not the beat plus a frame of loop delay.
                self._enter_phase("respond", self._phase_until)
        elif self.phase == "respond":
            self._update_respond(now)
        elif self.phase == "feedback":
            if now >= self._phase_until:
                self._after_feedback(now)

    # ---- warm-up probe -----------------------------------------------------
    def _update_warmup(self, now: float) -> None:
        if not self._warmup_beats:
            # Count-in plus one beat per warm-up tap. The metronome is
            # the audio timing reference (the screen is 60 Hz); it was
            # started in _enter_phase.
            first = now + self.ioi_s
            total = self.count_in_beats + self.warmup_total
            self._warmup_beats = [first + i * self.ioi_s
                                  for i in range(total)]
        if now >= self._warmup_beats[-1] + self.ioi_s:
            self._stop_metronome()
            self._enter_phase("gap", now)

    def _warmup_tap(self, ev: PressEvent) -> None:
        # Match the tap to the nearest scorable beat (count-in beats
        # are not scored) and log the signed asynchrony to raw.csv so
        # the analysis gets its per-session synchronisation probe.
        scorable = self._warmup_beats[self.count_in_beats:]
        if not scorable:
            return
        nearest = min(scorable, key=lambda b: abs(ev.t_perf - b))
        asyn_ms = (ev.t_perf - nearest) * 1000.0
        self._warmup_asyn.append(asyn_ms)
        self._warmup_done += 1
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event("warmup_tap", lane=ev.lane, t_perf=ev.t_perf,
                            detail=f"asyn_ms={asyn_ms:.1f}",
                            hand=self.engine.hand_mode)

    # ---- word flow ---------------------------------------------------------
    def _begin_word(self, now: float, reuse_word: bool = False) -> None:
        # Session cap and completion are checked at word boundaries so
        # the block never ends mid-trial.
        if self.words_done >= self.words_total:
            self._end("completed")
            return
        if (self._t0 is not None
                and (now - self._t0) > self.session_cap_s):
            self._end("time_cap")
            return
        if not reuse_word or self.word is None:
            self.word = self._draw_word()
        self.trial_counter += 1
        self.taps = []
        self._last_tap_t = {}
        self._model_lanes = []
        self._replayed = False
        self._pending_replay = False
        self._last_result = None
        self.active = PendingTrial(
            trial_id=self.trial_counter,
            lane=self.expected_lanes()[0] if self.order_required
            else self.lanes[0],
            stim_t_perf=now,
            keys_pressed=[],
            incorrect_presses=[],
        )
        self._enter_phase("attend", now)
        self._speak(self.word.word)

    def _enter_phase(self, phase: str, now: float) -> None:
        self.phase = phase
        self._phase_t0 = now
        self._phase_until = None
        if phase == "warmup":
            self._warmup_beats = []
            self._start_metronome()
        elif phase == "attend":
            self._phase_until = now + self.attend_s
        elif phase in ("model", "replay"):
            self._model_idx = -1
            self._model_next_t = now + self.ioi_s
        elif phase == "countin":
            self._phase_until = now + self.count_in_beats * self.ioi_s
            self._start_metronome()
        elif phase == "respond":
            self._respond_t0 = now
            self.taps = []
            self._last_tap_t = {}
            if self.paced:
                # One beat per unit, continuing the count-in pulse.
                self._beat_times = [now + (i + 1) * self.ioi_s
                                    for i in range(self.n_expected)]
            else:
                self._beat_times = []
                self._stop_metronome()
            self._phase_until = now + self.current_timeout_s - (
                self.count_in_beats * self.ioi_s if self.paced else 0.0)
        elif phase == "feedback":
            self._phase_until = now + self.FEEDBACK_S
            self._stop_metronome()
        elif phase == "break":
            self._phase_until = now + self.break_s
        elif phase == "gap":
            self._phase_until = now + self.inter_trial_gap_s

    def _update_model(self, now: float) -> None:
        """Light the blocks one per beat, left to right. Each onset goes
        through the engine's shared cue path (engine.on_stim), which
        fires the finger's buzzer and cue tone under the cue.* switches
        and records the cue condition; one motor per board runs at a
        time, so sequential onsets at the beat interval are exactly
        what the hardware can deliver.

        Beat deadlines are ABSOLUTE: each syllable is due one IOI after
        the previous DEADLINE, not one IOI after the frame that noticed
        it. Re-anchoring to the frame clock added the frame delay to
        every interval (measured +5 ms per beat at 120 fps, drifting
        10-25 ms across a word, worse at 60 Hz), a systematic stretch
        of the 2 Hz grid the beat-synchronisation analysis assumes. The
        cue still fires at the frame that crosses the deadline, so each
        onset jitters within a frame of its grid slot, but the error no
        longer accumulates."""
        due = self._model_next_t
        if due is None or now < due:
            return
        self._model_idx += 1
        if self._model_idx >= self.n_expected:
            self._model_idx = -1
            self._model_next_t = None
            if self.phase == "replay":
                # The replay is demonstration only; the word is already
                # scored and logged, so move on.
                self._enter_phase("gap", now)
                self.words_done += 1
                self._maybe_break(now)
            elif self.paced:
                # Hand the grid deadline over, not the frame time, so
                # the count-in ticks continue the model's beat rather
                # than restarting it a frame late.
                self._enter_phase("countin", due)
            else:
                self._enter_phase("respond", due)
            return
        self._model_next_t = due + self.ioi_s
        if self._model_next_t <= now:
            # The loop stalled past a whole beat (alt-tab, IO). Re-anchor
            # rather than burst-fire catch-up syllables a frame apart,
            # which the one-motor-per-board hardware could not deliver.
            self._model_next_t = now + self.ioi_s
        # Which finger: the syllable's position. Which hand: the next
        # one due off the hand bag, so with both hands connected the
        # model's buzzes divide equally between them across the block
        # (one hand connected always draws that hand).
        pos = (self._model_idx if self.order_required
               else min(self._model_idx, 3))
        hand = self.hand_names[self._model_hand_order.next()]
        lane = self.hands[hand][pos]
        if self.phase == "model":
            self._model_lanes.append(lane)
        # The replay runs after the trial was scored (self.active is
        # gone), but it is still the multisensory model, so the cue
        # path fires either way, tagged with the word's trial id.
        tid = (self.active.trial_id if self.active is not None
               else self.trial_counter)
        self.engine.on_stim(lane, tid, now)

    def _update_respond(self, now: float) -> None:
        # Track each in-flight tap's running peak while the finger is
        # still down, so the stress criterion sees the whole press.
        self._poll_tap_peaks()
        window_over = (self._phase_until is not None
                       and now >= self._phase_until)
        enough = len(self.taps) >= self.n_expected
        settled = (enough and self.taps
                   and now >= self.taps[-1].t_perf + self.SETTLE_S)
        if window_over or settled:
            self._score_word(now)

    def _handle_press(self, ev: PressEvent, now: float) -> None:
        if self.phase == "warmup":
            self._warmup_tap(ev)
            return
        if self.phase == "break":
            # Breaks are fixed-length rest for a child, not self-paced
            # like the adult modes; presses during one are ignored.
            return
        if self.phase != "respond" or self.active is None:
            # No penalty anywhere in this mode: a child fidgeting
            # between words must not lose points for it.
            return
        pos = self._position_of(ev.lane)
        if pos is None:
            return
        last = self._last_tap_t.get(ev.lane)
        if last is not None and (ev.t_perf - last) < self.tap_debounce_s:
            return
        self._last_tap_t[ev.lane] = ev.t_perf
        peak = self._peak_for(ev)
        self.taps.append(Tap(lane=ev.lane, t_perf=ev.t_perf, peak=peak))
        self.active.keys_pressed.append(ev.lane)
        # Wrong-POSITION taps land in incorrect_presses so the CSV's
        # had_incorrect_press / first_incorrect_lane columns carry
        # them, without any of the adult modes' penalties. The check
        # is on the syllable position, never the hand: left index and
        # right index are the same position, so there is no wrong
        # hand in this mode.
        k = len(self.taps) - 1
        if (self.order_required and
                (k >= self.n_expected or pos != k)):
            self.active.incorrect_presses.append((ev.lane, ev.t_perf))

    def _peak_for(self, ev: PressEvent) -> float | None:
        helper = getattr(self.engine, "_peak_force_for_lane", None)
        if not callable(helper):
            return None
        try:
            return helper(ev.lane)
        except Exception:
            return None

    def _poll_tap_peaks(self) -> None:
        helper = getattr(self.engine, "_peak_force_for_lane", None)
        if not callable(helper):
            return
        for tap in self.taps:
            try:
                live = helper(tap.lane)
            except Exception:
                continue
            if live is not None and (tap.peak is None or live > tap.peak):
                tap.peak = live

    # ---- scoring -----------------------------------------------------------
    def _score_word(self, now: float) -> None:
        trial = self.active
        word = self.word
        if trial is None or word is None:
            return
        self.active = None
        n = self.n_expected
        taps = self.taps
        count_correct = len(taps) == n
        # Order is checked on the taps that exist; count errors are
        # named first in the taxonomy below, so wrong_order is only
        # ever reported for a right-count trial. The check runs on
        # syllable POSITIONS, so either hand's finger satisfies its
        # position and no hand is ever wrong.
        order_correct = (not self.order_required
                         or [self._position_of(t.lane)
                             for t in taps[:n]]
                         == list(range(min(n, len(taps)))))

        asyn: list[float] = []
        all_on_beat = True
        if self.paced:
            # Tap k is paired with beat k: one tap per beat is the
            # instruction, so nearest-beat matching would hide a
            # skipped syllable.
            for k, tap in enumerate(taps[:len(self._beat_times)]):
                a = (tap.t_perf - self._beat_times[k]) * 1000.0
                asyn.append(a)
                if abs(a) > self.on_beat_window_s * 1000.0:
                    all_on_beat = False
            if len(taps) < n:
                all_on_beat = False

        stress_correct: bool | None = None
        stress_ratio_val: float | None = None
        if self.level == 4 and count_correct:
            stress_correct, stress_ratio_val = self._score_stress(
                taps, word)

        # Error taxonomy, worst first, mirroring the brief's list.
        if not taps:
            error = "timeout"
        elif len(taps) > n:
            error = "extra_tap"
        elif len(taps) < n:
            error = "missing_tap"
        elif not order_correct:
            error = "wrong_order"
        elif self.paced and not all_on_beat:
            error = "off_beat"
        elif stress_correct is False:
            error = "wrong_stress"
        else:
            error = "ok"
        correct = error == "ok"

        # Outcome: Great when everything the level asks for landed,
        # Good when the count was right but a criterion missed, Miss
        # otherwise. rt carries first-tap RT free-paced and mean
        # signed asynchrony paced (the rhythm sign convention).
        if self.paced and asyn:
            rt_ms = sum(asyn) / len(asyn)
        elif taps and self._respond_t0 is not None:
            rt_ms = (taps[0].t_perf - self._respond_t0) * 1000.0
        else:
            rt_ms = None
        if correct:
            outcome = TrialResult(label="Great",
                                  points=self.score_cfg.great_points,
                                  rt_ms=rt_ms)
        elif count_correct:
            outcome = TrialResult(label="Good",
                                  points=self.score_cfg.good_points,
                                  rt_ms=rt_ms)
        else:
            outcome = TrialResult(label="Miss",
                                  points=self.score_cfg.miss_points,
                                  rt_ms=rt_ms)

        self._last_result = {
            "correct": correct,
            "error": error,
            "n_taps": len(taps),
            "stress_correct": stress_correct,
        }
        self._records.append(TrialRecord(
            word=word.word, n_syll=n, band=self.band,
            correct=correct, error=error, asynchronies=list(asyn),
            stress_ratio=stress_ratio_val,
            stress_correct=stress_correct,
        ))
        self.engine.log_trial(
            trial, outcome, now,
            stimulus=self._pack_stimulus(word, error, asyn),
            # In bilateral play both hands' copies of each expected
            # position are acceptable, and the CSV says so.
            correct_lanes=self.acceptable_lanes(),
        )
        self._recent.append(correct)
        self._since_band_change += 1
        self._maybe_move_band()
        self._pending_replay = (not correct and self.replay_on_error
                                and not self._replayed)
        self._enter_phase("feedback", now)

    def _score_stress(self, taps: list[Tap],
                      word: Word) -> tuple[bool | None, float | None]:
        """Level 4 accent criterion, relative to the child's own trial:
        the stressed tap at least stress_ratio times the median peak,
        every other tap under unstressed_max_ratio times it. Keyboard
        mode has no force data, so the criterion is unscored (None)
        rather than failed: the child cannot mark stress on a channel
        that does not exist."""
        peaks = [t.peak for t in taps]
        if any(p is None for p in peaks) or len(peaks) < 2:
            return None, None
        s_idx = word.stress
        if s_idx >= len(peaks):
            return None, None
        med = sorted(peaks)[len(peaks) // 2]
        if med <= 0:
            return None, None
        ratio = peaks[s_idx] / med
        ok = ratio >= self.stress_ratio and all(
            (p / med) < self.unstressed_max_ratio
            for i, p in enumerate(peaks) if i != s_idx)
        return ok, ratio

    def _pack_stimulus(self, word: Word, error: str,
                       asyn: list[float]) -> str:
        taps_s = ",".join(
            f"{t.lane + 1}:"
            f"{(t.t_perf - (self._respond_t0 or t.t_perf)) * 1000.0:.1f}:"
            + (f"{t.peak:.1f}" if t.peak is not None else "")
            for t in self.taps)
        parts = [
            word.word,
            f"lvl={self.level}",
            f"band={self.band}",
            f"nsyll={self.n_expected}",
            f"stress={word.stress}",
            f"paced={1 if self.paced else 0}",
            f"ioi={self.ioi_s * 1000.0:.0f}",
            f"replay={1 if self._replayed else 0}",
            f"err={error}",
            f"taps={taps_s}",
        ]
        if asyn:
            parts.append("asyn=" + ",".join(f"{a:.1f}" for a in asyn))
        if self.bilateral and self._model_lanes:
            # Which lanes the model phase buzzed, 1-indexed like taps,
            # so the analysis can split model hands from tap hands.
            parts.append("model=" + ",".join(str(l + 1)
                                             for l in self._model_lanes))
        return ";".join(parts)

    def _after_feedback(self, now: float) -> None:
        if self._pending_replay:
            self._pending_replay = False
            self._replayed = True
            self._enter_phase("replay", now)
            return
        self.words_done += 1
        self._enter_phase("gap", now)
        self._maybe_break(now)

    def _maybe_break(self, now: float) -> None:
        # A rest lands after every full round, except when the block is
        # already over (the completion check in _begin_word owns that).
        if (self.words_done < self.words_total and self.break_s > 0
                and self.words_done % self.round_size == 0):
            self._enter_phase("break", now)

    # ---- band progression --------------------------------------------------
    def _maybe_move_band(self) -> None:
        """The brief's within-level rule: promote at 8 of the last 10
        fully correct, demote under 5 of 10. Evaluated only once 10
        words have run since the last change, so one change cannot
        cascade off the window that triggered it. Every firing is
        logged so the difficulty trace is reconstructible."""
        if len(self._recent) < 10 or self._since_band_change < 10:
            return
        wins = sum(1 for c in self._recent if c)
        idx = BANDS.index(self.band)
        new_idx = idx
        if wins >= 8 and idx < len(BANDS) - 1:
            new_idx = idx + 1
        elif wins < 5 and idx > 0:
            new_idx = idx - 1
        if new_idx == idx:
            return
        self.band = BANDS[new_idx]
        self._band_trace.append(self.band)
        self._since_band_change = 0
        self._recent.clear()
        self._bag = []          # refill from the new band's pool
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "syllables_band",
                detail=f"band={self.band} wins={wins}/10 "
                       f"word_idx={self.words_done}",
                hand=self.engine.hand_mode)

    # ---- audio and speech helpers ------------------------------------------
    def _start_metronome(self) -> None:
        audio = getattr(self.engine, "audio", None)
        if audio is None:
            return
        try:
            audio.start_metronome(60.0 / self.ioi_s)
        except Exception:
            pass

    def _stop_metronome(self) -> None:
        audio = getattr(self.engine, "audio", None)
        if audio is None:
            return
        try:
            audio.stop()
        except Exception:
            pass

    def _speak(self, word: str) -> None:
        """Speak the word once at ATTEND time via the macOS `say`
        command, in the background so the frame loop never waits on
        it, failing silent everywhere it cannot work."""
        if not self.speak_words or sys.platform != "darwin":
            return
        if shutil.which("say") is None:
            return
        cmd = ["say"]
        if self.say_voice:
            cmd += ["-v", str(self.say_voice)]
        cmd.append(word)
        try:
            self._say_proc = subprocess.Popen(
                cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            self._say_proc = None

    def _reap_say(self) -> None:
        # poll() collects the finished process so it never lingers as a
        # zombie; cheap no-op while it is still speaking.
        if self._say_proc is not None and self._say_proc.poll() is not None:
            self._say_proc = None

    # ---- end of block ------------------------------------------------------
    def _end(self, reason: str) -> None:
        self.phase = "done"
        self.end_reason = reason
        self._stop_metronome()
        self.engine.finish_block()

    # ---- block summary -----------------------------------------------------
    def block_stats(self) -> dict:
        """What finish_block folds into session.json: the settings the
        block ran under, accuracy split by syllable count (the
        Liberman-style curve), the pooled asynchronies from paced
        trials and the warm-up probe, the stress ratios, and the band
        trace, so a session is readable without parsing the stimulus
        strings back out of trials.csv."""
        by_count: dict[int, list[bool]] = {}
        for r in self._records:
            by_count.setdefault(r.n_syll, []).append(r.correct)
        acc_by_count = {
            str(k): round(sum(v) / len(v), 3)
            for k, v in sorted(by_count.items()) if v}
        asyn = [a for r in self._records for a in r.asynchronies]
        ratios = [r.stress_ratio for r in self._records
                  if r.stress_ratio is not None]
        errors: dict[str, int] = {}
        for r in self._records:
            if not r.correct:
                errors[r.error] = errors.get(r.error, 0) + 1

        def _mean(xs: list[float]) -> float | None:
            return round(sum(xs) / len(xs), 1) if xs else None

        def _sd(xs: list[float]) -> float | None:
            if len(xs) < 2:
                return None
            m = sum(xs) / len(xs)
            return round((sum((x - m) ** 2 for x in xs)
                          / (len(xs) - 1)) ** 0.5, 1)

        n = len(self._records)
        return {
            "level": self.level,
            "hands": self.hand_names,
            "band_final": self.band,
            "band_trace": list(self._band_trace),
            "ioi_ms": round(self.ioi_s * 1000.0),
            "on_beat_window_ms": round(self.on_beat_window_s * 1000.0),
            "stress_ratio_criterion": self.stress_ratio,
            "n_words": n,
            "accuracy": round(sum(1 for r in self._records if r.correct)
                              / n, 3) if n else None,
            "accuracy_by_syllables": acc_by_count,
            "error_counts": errors,
            "asyn_mean_ms": _mean(asyn),
            "asyn_sd_ms": _sd(asyn),
            "warmup_taps": self._warmup_done,
            "warmup_asyn_mean_ms": _mean(self._warmup_asyn),
            "warmup_asyn_sd_ms": _sd(self._warmup_asyn),
            "stress_ratio_median": (round(sorted(ratios)[len(ratios) // 2], 2)
                                    if ratios else None),
            "demo": self.demo,
            "end_reason": self.end_reason,
        }
