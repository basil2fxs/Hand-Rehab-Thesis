"""Syllables: a syllable-matching game for children with reading
difficulty. The word is heard and seen, then its syllables come down
the screen one set at a time, four written options over four fingers,
and the child presses the finger under the chunk that was spoken. A
different population from the rest of this suite, with a different
evidence base; the claim limits at the bottom of this docstring are
part of the design.

WHAT THE CHILD DOES. ATTEND: the whole word appears at the top as n
empty slots with the word written large under them, and the word is
spoken. MODEL: each slot lights in turn at the beat, its chunk shows,
the syllable is spoken, and one tactile roll runs across all four
fingers of the playing hand. Then the slots empty again. CHOOSE, once
per syllable in order: four tiles fall slowly down four lanes that sit
over the four fingers, one tile is the syllable and three are foils.
The child presses the finger under the right tile. A correct press
lifts the tile into the word strip; a wrong press greys that tile and
nothing else. COMPLETE: the strip is full, the whole word is spoken
again.

WHY A CHOICE TASK AND NOT COUNTING. Phonological awareness
instruction works (Ehri, Nunes, Willows, Schuster, Yaghoub-Zadeh and
Shanahan 2001, 52 studies, d = 0.86 on PA and 0.53 on reading, and PA
WITH LETTERS beat PA alone), but for children with a reading
disability the only treatment family with a confirmed effect in the
randomised-trial meta-analysis is phonics, print to sound (Galuschka,
Ise, Krick and Schulte-Koerne 2014, g = 0.32). Two syllable-level
PRINT studies point straight at this task: Bhattacharya and Ehri
(2004) improved struggling adolescent readers' decoding of new words
by having them analyse the graphosyllabic units of multisyllabic
words, where whole-word practice did nothing; Mueller, Richter,
Karageorgos, Krawietz and Ennemoser (2017) improved German poor
readers' word-reading fluency with syllable-based training. Both used
WRITTEN syllables, which is what the falling tiles are. Segmentation
develops from large units to small (Liberman, Shankweiler, Fischer and
Carter 1974: 46 percent of four year olds could tap syllables and none
could tap phonemes; Ziegler and Goswami's 2005 grain size theory
explains why English readers need the big units as well as the small
ones), so the syllable is the right grain to start at.

THE GAME SHAPE COMES FROM GRAPHOGAME. Richardson and Lyytinen (2014)
describe the method this mode copies: multiple-choice trials pairing
an audio segment with the right written form, adaptation aimed at
about 80 percent correct, immediate positive feedback. Mehringer et
al. (2020) add the distractor rule (a target among one to nine
distractors, some deliberately confusable). Two results bound what may
be claimed from it: Ahmed, Wilson, Mead, Noble, Richardson, Wolpert
and Goswami (2020) found only a small nonword-decoding effect in
English, and McTigue, Solheim, Zimmer and Uppstad (2020) found a
negligible overall effect across the GraphoGame literature with
SUPPORTIVE ADULT INTERACTION as the only significant moderator. Hence
the adult line on the rest screen, and hence the claim limits below.

WHAT IS DELIBERATELY DIFFERENT FROM GRAPHOGAME. GraphoGame makes the
child re-pick the right answer before moving on. Here a wrong press
greys its tile and the other tiles keep falling; if the set leaves the
screen unanswered the right tile glows on its way out, the syllable is
spoken, and the WORD comes back later (after two other words, then
after four) rather than being drilled on the spot. The reasons are
spacing and feedback timing: spaced retrieval beats massed for word
learning in children with language disorder (Leonard and Deevy 2020),
an unsuccessful retrieval attempt followed by the answer still helps
later learning (Kornell, Hays and Bjork 2009), delayed feedback beat
immediate feedback in Grade 6 children (Metcalfe, Kornell and Finn
2009), and adults with dyslexia learn worse from immediate feedback
but normally from delayed feedback (Gabay 2021, following Foerde and
Shohamy 2011 on the striatal-to-hippocampal shift). So positive
feedback is immediate and loud (the tile lifts, the chime plays) and
negative feedback is quiet, informational and late.

NO HINTS, EVER. Fitts and Seeger (1953) showed response selection is
fastest when the stimulus and the response share a spatial code: a
tile falling in the lane over the finger that answers it IS that code,
and it is the only mapping the child gets. Nothing else may carry the
answer before the press. The model's tactile pulse is therefore a
four-finger ROLL, not a single buzz (a buzz on one finger during the
model would announce which lane to press later); the option-set spawn
goes through the engine's cue path with `silent_stim` set, so it arms
the force window, the timeout and the EEG marker but fires no tone, no
screen highlight and no buzzer; the four tiles are drawn identically;
and the target lane is drawn by a deficit rule with a random
tie-break, never in a predictable place.

DIFFICULTY MOVES ON TWO CLOCKS.
- The FOIL RUNG (1 to 8) controls how similar the wrong options are,
  how long the tiles take to fall, and whether the syllable is spoken
  again at spawn. It moves by a 3-down-1-up staircase on first-press
  correctness, which converges on the 79.4 percent point of the
  psychometric function (Levitt 1971), the same region GraphoGame
  targets. A rung can move every three sets, so it tracks the child
  inside a round.
- The WORD BAND (A everyday two-syllable words, B two and three, C
  the four-syllable ones) keeps the brief's 8-of-the-last-10 /
  under-5-of-10 rule on WORD outcomes, evaluated at round boundaries,
  so word length changes slowly and the child sees a card when it
  does.
The number of options is always four: it sits inside GraphoGame's one
to nine range, it matches four fingers, and chance is a flat 25
percent the analysis can draw as a line.

TIMING IS SIZED TO A CHILD READING. Choice reaction time grows with
the number of alternatives (Hick's law, reviewed in Proctor and
Schneider 2018) and children are slower than adults by a factor near
1.5 to 1.8 at age 8 (Kail 1991), so an 8 year old needs roughly a
second before any READING is done, and a struggling reader needs time
to read four chunks and compare them. Time pressure is also what
separates dyslexic from typical letter-sound binding (Aravena,
Snellings, Tijms and van der Molen 2013). So a set is on screen for
4.0 s at the entry rung and never under 2.5 s: the window is a floor
for thinking, not a rhythm target.

HANDS. With both hands connected the hands ALTERNATE PER WORD: all
four tiles sit over the playing hand, the resting hand shows seat
dots, and the switch is announced at ATTEND before any tile exists.
Never within a word and never mirrored: dyslexic children are worse
than controls at asynchronous bimanual tapping but not at unimanual
tapping (Wolff, Michel, Ovrut and Drake 1990), eight tiles would
double the alternatives and crowd the screen, and a mirrored set lets
a child play a whole block on the hand they favour. One hand
connected plays every word on that hand, with nothing gated behind
two.

DISPLAY. Tiles use wide letter tracking, because extra-large letter
spacing improved dyslexic children's reading on the fly (Zorzi et al.
2012, PNAS), and the app's ordinary sans font, because special
dyslexia fonts do not help (Wery and Diliberto 2017; Kuster, van
Weerdenburg, Gompel and Bosman 2018). Everything is lower case:
reversals only exist in lower case, and print is lower case.

WHAT THE NUMBER MEASURES UNDER THE SHIPPED CUE DEFAULTS. Those
defaults play the buzzer and the cue tone with the screen, and this
mode splits them across the phases on purpose. The model is
audio-tactile-visual: the syllable is spoken, the four-finger roll
runs, the slot lights. The choice-set spawn is none of those (the
`silent_stim` path fires no tone, no highlight and no buzz), so the
rt on a set row is a spoken-to-printed matching time under a silent
onset, not a cued reaction time, and it is not comparable with the
rt of any other mode in this suite. The after-press cue on a correct
press rides cue.buzz_after / cue.sound_after like everywhere else.
The cue_flags column on every row is how the analysis separates
blocks run under different channel mixes instead of pooling them.

THE REWARD LAYER is unchanged from the tapping version and stays
deterministic and informational, the one cell of the reward
literature that does not undermine children's intrinsic motivation
(Deci, Koestner and Ryan 1999): points 6/3/0 per set, up to three
corner stars at fixed streaks of 3, 5 and 8 WORDS answered with every
first press right, one sticker per completed round stamped on the
session's walking strip, a one-shot "Bigger words!" card on band
promotion, silence on demotion, no penalties anywhere. Ronimus,
Kujala, Tolvanen and Lyytinen (2014) found rewards raise play time
only early, so this layer exists to sharpen ten minutes, and no
analysis may present streaks or stickers as training.

WHAT ONE ROW LOGS. One trials.csv row per option SET, not per word:

    word;pos=<k>;nsyll=<n>;syl=<chunk>;band=<A|B|C>;rung=<1-8>;
    hand=<L|R>;fall=<ms>;respeak=<0|1>;ret=<0|1|2>;
    opts=<lane>:<text>:<kind>,... (four, 1-indexed lanes);
    tlane=<1-indexed target lane>;
    presses=<lane>:<t_ms from spawn>:<peak>:<kind>,...;
    first=<ok|wrong|none>;err=<ok|wrong_first|miss>;rt=<ms>;
    streak=<n>;ease=1 (biased draws only);sup=<0|1>

rt is spawn to correct press. time_difference_ms on the row is that
rt; error_type carries err on Miss rows; correct_keys is the target
lane alone; the row's hand column is the word's hand. Word-level
outcomes are derived by the notebook from the set rows (all sets of
one word attempt share word and ret).

WHAT THIS MODE CANNOT CLAIM. It trains and measures in-task
behaviour: first-press accuracy at matching a spoken syllable to one
of four written chunks, which foil types capture wrong presses, and
how long that decision takes. Those are not reading, decoding or
spelling outcomes; a change in them means nothing outside the game
without a standardised pre and post measure and a control group
(Galuschka 2014, McTigue 2020). It is not a dyslexia treatment and
must never label a child dyslexic. Chance is 25 percent per set, so
accuracy near 25 percent is guessing and the analysis must show that
line. The foil taxonomy counts confusions; it does not diagnose
letter position dyslexia or anything else (Kohnen, Nickels, Castles,
Friedmann and McArthur 2012 needed purpose-built tests for that). The
tactile channel is engagement and cueing, not a claimed active
ingredient (Stevens et al. 2021, meta-analytic null on the
multisensory element). GraphoGame's effects depend on adult support
(McTigue 2020), so a session played alone is a different condition and
the `supervised` flag records which one it was. The hardware was built
and ethically scoped for adult stroke rehabilitation; use with
children needs new ethics approval, a finger-spacing check and hygiene
procedures, and none of these parameters have been validated on
children with this device, so the first study is feasibility and
acceptability, not efficacy.
"""
from __future__ import annotations

import logging
import random
import shutil
import subprocess
import os
import sys
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from ...hardware.fsr_detector import PressEvent
from ..rest_skip import WaitSkip
from ..scoring import ScoreConfig, TrialResult
from ._keys import keymap_for_hand, resolve_key
from .classic import PendingTrial
from .syllables_foils import Inventory, build_option_set
from .syllables_words import Word, syllable_lists, words_for

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


BANDS = ("A", "B", "C")
# Press kinds, in the order the input rule tests them. Only "correct"
# ever scores; "wrong" is the only other kind that changes anything
# (it sets first=wrong for the set and greys its tile).
KIND_CORRECT = "correct"
KIND_WRONG = "wrong"
KIND_WRONG_REPEAT = "wrong_repeat"
KIND_ANTICIP = "anticip"
KIND_OFF_HAND = "off_hand"


@dataclass
class Press:
    """One press inside an option set, whatever it did."""
    lane: int
    t_perf: float
    kind: str
    peak: float | None = None


@dataclass
class SetRecord:
    """What one closed option set contributes to block_stats."""
    word: str
    pos: int
    n_syll: int
    band: str
    rung: int
    hand: str
    ret: int
    first: str                 # ok | wrong | none
    err: str                   # ok | wrong_first | miss
    rt_ms: float | None
    wrong_kind: str | None     # foil kind of the first wrong press
    n_anticip: int = 0
    n_off_hand: int = 0


@dataclass
class WordRecord:
    """What one closed word attempt contributes: the unit the band
    gate and the streak work on."""
    word: str
    n_syll: int
    band: str
    ret: int
    correct: bool              # every set's first press was right
    completed: bool            # the strip filled
    error: str                 # ok | wrong_first | miss
    hand: str = "right"
    sets: list[SetRecord] = field(default_factory=list)


class SyllablesMode(WaitSkip):
    name = "Syllables"

    # How long the set stays on screen after the correct press, so the
    # tile is seen lifting into the word strip before the next set.
    CORRECT_HOLD_S = 0.3
    # The corrective display on a missed set: the right tile glows on
    # its way out and the syllable is spoken. Delayed by construction
    # (it lands one to three seconds after any wrong press), which is
    # the feedback timing the docstring defends.
    MISS_GLOW_S = 0.6
    # A greyed tile drifts off over this long. Screen-side only.
    GREY_DRIFT_S = 0.5
    # Fixed streak milestones, in WORDS answered with every first
    # press right. Fixed and transparent rather than a variable-ratio
    # schedule, so the reward carries no reward-prediction-error
    # surprise into the EEG record.
    STREAK_MILESTONES = (3, 5, 8)
    # Hard cap on warm-up taps whatever the config asks for.
    WARMUP_TAPS_MAX = 5
    # Metronome count-in beats before the warm-up taps are counted.
    # The warm-up is the only place a beat grid still exists.
    COUNT_IN_BEATS = 4
    # Returns are extra words on top of the block's budget, so they
    # are capped or a child who misses a lot never reaches the end.
    MAX_RETURNS = 6
    # The floor on the fall window, whatever the config says. Below
    # this the task measures reading speed under time pressure, which
    # is the thing Aravena et al. (2013) showed dyslexic readers fail
    # for reasons that have nothing to do with this game.
    MIN_FALL_S = 2.5

    def __init__(self, engine: "GameEngine",
                 lanes: list[int],
                 band: str,
                 ioi_ms: float,
                 words_total: int,
                 round_size: int,
                 break_s: float,
                 warmup_taps: int,
                 attend_s: float,
                 tap_debounce_ms: float,
                 inter_trial_gap_ms: float,
                 session_cap_min: float,
                 score_cfg: ScoreConfig,
                 rung: int = 1,
                 rung_min: int = 1,
                 rung_max: int = 8,
                 fall_s: list[float] | None = None,
                 set_gap_s: float = 0.4,
                 spawn_lockout_s: float = 0.25,
                 respeak_rungs: list[int] | None = None,
                 return_after: list[int] | None = None,
                 complete_s: float = 1.4,
                 homophone_foils: bool = False,
                 alternate_hands: bool = True,
                 supervised: bool = True,
                 speech: dict | None = None,
                 seed: int = 0,
                 demo_trials: int | None = None,
                 lanes_by_hand: dict[str, list[int]] | None = None,
                 ) -> None:
        self.engine = engine
        # The lanes of each playing hand, in the hand's own order
        # (lanes[0] index through lanes[3] little). A word plays on ONE
        # hand: its four lanes are the four option lanes, in desk
        # order, so the leftmost tile sits over the leftmost finger.
        if lanes_by_hand and len([h for h, v in lanes_by_hand.items()
                                  if v]) > 1:
            self.hands = {h: list(v)[:4]
                          for h, v in lanes_by_hand.items() if v}
        else:
            four = list(lanes)[:4]
            while len(four) < 4:
                four.append(len(four))
            hand_name = str(getattr(engine, "hand_mode", "right"))
            if hand_name not in ("left", "right"):
                hand_name = "right"
            self.hands = {hand_name: four}
        self.hand_names = list(self.hands)
        self.bilateral = len(self.hand_names) > 1
        self.lanes = self.hands[self.hand_names[0]]
        self.band = band if band in BANDS else "A"
        self.ioi_s = max(0.2, float(ioi_ms) / 1000.0)
        self.round_size = max(1, int(round_size))
        self.break_s = max(0.0, float(break_s))
        self.warmup_total = max(0, min(self.WARMUP_TAPS_MAX,
                                       int(warmup_taps)))
        self.attend_s = max(0.2, float(attend_s))
        self.tap_debounce_s = max(0.0, float(tap_debounce_ms) / 1000.0)
        self.inter_trial_gap_s = max(0.0, float(inter_trial_gap_ms) / 1000.0)
        self.session_cap_s = float(session_cap_min) * 60.0
        self.score_cfg = score_cfg
        self.rung_min = max(1, int(rung_min))
        self.rung_max = max(self.rung_min, min(8, int(rung_max)))
        self.rung = max(self.rung_min, min(self.rung_max, int(rung)))
        self.rung_start = self.rung
        self._fall_table = [max(self.MIN_FALL_S, float(v))
                            for v in (fall_s or [4.0, 4.0, 3.5, 3.5,
                                                 3.0, 3.0, 2.5, 2.5])]
        self.set_gap_s = max(0.0, float(set_gap_s))
        # The lockout has a floor as well as a config value: the tiles
        # are still fading in below it, so a press there answered a
        # set the child could not have read.
        self.spawn_lockout_s = max(0.2, float(spawn_lockout_s))
        self.respeak_rungs = set(int(r) for r in (respeak_rungs or [1, 2, 3]))
        self.return_after = [max(0, int(v))
                             for v in (return_after or [2, 4])] or [2, 4]
        self.complete_s = max(0.2, float(complete_s))
        self.homophone_foils = bool(homophone_foils)
        self.alternate_hands = bool(alternate_hands)
        self.supervised = bool(supervised)
        speech = dict(speech or {})
        self.speech_backend = str(speech.get("backend", "auto") or "auto")
        self.speech_dir = str(speech.get("dir", "assets/speech"))
        self.speech_volume = float(speech.get("volume", 1.0))
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
        self.inventory = Inventory(syllable_lists())
        self._bag: list[Word] = []

        # ---- the word in play ----
        self.word: Word | None = None
        self.word_hand: str = self.hand_names[0]
        self.filled: list[str | None] = []      # the word strip
        # Which lane won each slot, so the strip can fill in the
        # colour of the finger that answered it. A slot coloured by
        # POSITION would be a false cue: position and finger have
        # nothing to do with each other here.
        self.filled_lanes: list[int | None] = []
        self.pos = 0                            # syllable being chosen
        self.ret = 0                            # 0 first attempt, 1-2 returns
        self.option_set = None
        self.silent_stim = False                # engine reads this at spawn

        # ---- session flow ----
        # warmup -> gap -> attend -> model -> choose -> complete -> gap
        # ... with break between rounds and done at the end.
        self.phase = "warmup" if self.warmup_total else "gap"
        self.trial_counter = 0
        self.words_done = 0                     # distinct first attempts
        self.active: PendingTrial | None = None
        self._presses: deque[PressEvent] = deque()
        self._t0: float | None = None
        self._phase_t0: float | None = None
        self._phase_until: float | None = None
        self._model_idx = -1
        self._model_next_t: float | None = None
        self.model_hand: str | None = None
        self._say_proc: subprocess.Popen | None = None
        self._missing_speech: set[str] = set()
        self.end_reason: str | None = None

        # ---- the option set in play ----
        self._spawn_t: float | None = None
        self._exit_t: float | None = None
        self._next_spawn_t: float | None = None
        self._set_close_t: float | None = None
        self._set_presses: list[Press] = []
        self._dead_lanes: set[int] = set()
        self._first_kind: str | None = None     # ok | wrong (first real press)
        self._correct_t: float | None = None
        self._glow_t: float | None = None       # missed-set corrective glow
        self._last_tap_t: dict[int, float] = {}
        self._respeak = False
        self.lift_t: float | None = None        # screen: tile lifting

        # ---- difficulty ----
        self._run = 0                           # consecutive first-press ok
        self._rung_trace: list[int] = [self.rung]
        self._lane_targets: dict[int, int] = {}
        self._recent_target_lanes: list[int] = []

        # ---- material rotation ----
        self._hand_cursor = 0
        self._parked: list[dict] = []
        self._returns_started = 0
        self._retired: list[str] = []
        # Every word the child has met this block, so the ease-in
        # rescue draw reaches for something new rather than handing
        # back a word they have just failed.
        self._seen_words: set[str] = set()

        # ---- aggregates ----
        self._sets: list[SetRecord] = []
        self._records: list[WordRecord] = []
        self._band_trace: list[str] = [self.band]
        self._recent: deque[bool] = deque(maxlen=10)
        self._since_band_change = 0

        # ---- warm-up probe ----
        self._warmup_beats: list[float] = []
        self._warmup_asyn: list[float] = []
        self._warmup_done = 0

        # ---- reward layer ----
        self._streak = 0
        self._max_streak = 0
        self.round_stars = 0
        self.star_flash_t: float | None = None
        self._stickers = 0
        self.sticker_flash_t: float | None = None
        self.band_celebrate: str | None = None
        self._miss_run = 0
        self._ease_word = False
        self._n_ease_in = 0

    # ---- geometry the screen and the keyboard note share ------------------
    def desk_row(self) -> list[int]:
        """Every playing lane in physical desk order, left to right.
        Lane lists run index outward, which is left to right on the
        right hand and right to left on the left, so the left hand
        contributes its lanes reversed and comes first."""
        row: list[int] = []
        if "left" in self.hands:
            row.extend(reversed(self.hands["left"]))
        for hand in self.hand_names:
            if hand != "left":
                row.extend(self.hands[hand])
        return row

    def active_lanes(self) -> list[int]:
        """The four lanes this word plays on, in desk order: the
        playing hand's own fingers, left to right."""
        lanes = self.hands.get(self.word_hand) or self.lanes
        if self.word_hand == "left":
            return list(reversed(lanes))
        return list(lanes)

    def _hand_of_lane(self, lane: int) -> str:
        for hand, lanes in self.hands.items():
            if lane in lanes:
                return hand
        return self.hand_names[0]

    def _lane_in_game(self, lane: int) -> bool:
        return any(lane in lanes for lanes in self.hands.values())

    def _finger_of_lane(self, lane: int) -> int:
        """The finger a lane sits under within its hand (0 index to 3
        little). Calibration gaps and colours are per FINGER."""
        lanes = self.hands.get(self._hand_of_lane(lane), self.lanes)
        try:
            return max(0, min(3, lanes.index(lane)))
        except ValueError:
            return max(0, min(3, lane - lanes[0]))

    @property
    def n_syll(self) -> int:
        return len(self.word.syllables) if self.word else 0

    @property
    def fall_s(self) -> float:
        """How long this rung's tiles are on screen."""
        idx = max(0, min(len(self._fall_table) - 1, self.rung - 1))
        return self._fall_table[idx]

    @property
    def current_timeout_s(self) -> float:
        """The set's response window, which is the RT censoring limit
        the engine writes into the trial row."""
        return self.fall_s

    def eeg_stim_code(self) -> int | None:
        """The choice band: 50 for a set on a first attempt, 51 for a
        set on a returned word. None everywhere else, so the model
        roll keeps the ordinary 30-band cue-condition code."""
        if self.phase != "choose":
            return None
        from ...hardware import eeg_trigger
        return eeg_trigger.CODES[
            "stim_choice_set_return" if self.ret else "stim_choice_set"]

    # ---- material ---------------------------------------------------------
    def _draw_word(self) -> Word:
        """Shuffle-bag draw over the current band pool, so a round
        cannot repeat one word while another never comes up. The bag
        rebuilds when it empties or after a band change."""
        if not self._bag:
            self._bag = [w for w in words_for(self.band,
                                              bilateral=self.bilateral)
                         if w.word not in self._retired]
            if not self._bag:
                # A band small enough to retire whole: better to
                # repeat than to stall the block.
                self._bag = list(words_for(self.band,
                                           bilateral=self.bilateral))
            self.rng.shuffle(self._bag)
        return self._bag.pop()

    def _best_syllable_count(self) -> int | None:
        """The syllable count the child has done best on so far this
        block, ties to the LOWER count (the kinder direction)."""
        by_count: dict[int, list[bool]] = {}
        for r in self._records:
            by_count.setdefault(r.n_syll, []).append(r.correct)
        best, best_acc = None, -1.0
        for n in sorted(by_count):
            acc = sum(by_count[n]) / len(by_count[n])
            if acc > best_acc:
                best, best_acc = n, acc
        return best

    def _draw_ease_word(self) -> Word | None:
        """One word at the child's best syllable count, bypassing the
        shuffle bag: the bag's fairness is about material coverage,
        this draw is about breaking a failure spiral."""
        best = self._best_syllable_count()
        if best is None:
            return None
        pool = [w for w in words_for(self.band, bilateral=self.bilateral)
                if w.n_syll == best and w.word not in self._retired]
        if not pool:
            return None
        # A word already played this block is a poor rescue: the child
        # has just failed it, and a retired one is meant to be gone for
        # the block. Fall back through seen, then to the whole pool,
        # so the draw never returns None when material exists.
        prev = self.word.word if self.word is not None else None
        unseen = [w for w in pool
                  if w.word != prev and w.word not in self._seen_words]
        fresh = [w for w in pool if w.word != prev]
        return self.rng.choice(unseen or fresh or pool)

    def _next_hand(self) -> str:
        """Which hand the next word plays on. One hand connected: that
        hand. Both connected with alternate_hands: left, right, left,
        right across words, starting on the session's main hand."""
        if not self.bilateral or not self.alternate_hands:
            main = str(getattr(self.engine, "hand_mode", "right"))
            if main in self.hands:
                return main
            return self.hand_names[0]
        order = [h for h in ("left", "right") if h in self.hands]
        main = str(getattr(self.engine, "hand_mode", "right"))
        if main in order:
            # Start on the main hand, then alternate.
            order = ([main] + [h for h in order if h != main])
        hand = order[self._hand_cursor % len(order)]
        self._hand_cursor += 1
        return hand

    # ---- plumbing shared with the other modes ------------------------------
    def queue_press(self, ev: PressEvent) -> None:
        self._presses.append(ev)

    def on_resume(self, pause_dur: float) -> None:
        for attr in ("_t0", "_phase_t0", "_phase_until", "_model_next_t",
                     "_spawn_t", "_exit_t", "_next_spawn_t",
                     "_set_close_t", "_correct_t", "_glow_t", "lift_t"):
            v = getattr(self, attr)
            if v is not None:
                setattr(self, attr, v + pause_dur)
        self._warmup_beats = [t + pause_dur for t in self._warmup_beats]
        # A pause mid-word breaks the presentation the trial rests on
        # (the word was spoken and modelled before the pause, the tiles
        # fall after it), so the fair move is to restart the word from
        # ATTEND rather than salvage half of it.
        if self.phase in ("attend", "model", "choose", "complete"):
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event(
                    "trial_restart",
                    detail=(f"old_trial_id={self.trial_counter};"
                            f"new_trial_id={self.trial_counter + 1};"
                            f"phase={self.phase}"),
                    hand=self.engine.hand_mode)
            self.active = None
            self.option_set = None
            self._begin_word(time.perf_counter(), reuse_word=True)

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN:
            # Keyboard fallback stays wired even with an Arduino
            # connected: a busted auto-detect must never leave the
            # therapist with no working input.
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
                    raw_logger = getattr(self.engine, "raw_logger", None)
                    if raw_logger:
                        raw_logger.queue_event(
                            "press", lane=lane, t_perf=t_perf,
                            hand=self.engine.hand_mode, detail="keyboard")

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
        elif self.phase == "model":
            self._update_model(now)
        elif self.phase == "choose":
            self._update_choose(now)
        elif self.phase == "complete":
            if self._phase_until is not None and now >= self._phase_until:
                self._after_word(now)

    # ---- warm-up probe -----------------------------------------------------
    def _update_warmup(self, now: float) -> None:
        if not self._warmup_beats:
            first = now + self.ioi_s
            total = self.COUNT_IN_BEATS + self.warmup_total
            self._warmup_beats = [first + i * self.ioi_s
                                  for i in range(total)]
        if now >= self._warmup_beats[-1] + self.ioi_s:
            self._stop_metronome()
            self._enter_phase("gap", now)

    def _warmup_tap(self, ev: PressEvent) -> None:
        scorable = self._warmup_beats[self.COUNT_IN_BEATS:]
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
    def _due_return(self) -> dict | None:
        """The parked word whose wait is up, if any. Returns are
        played before fresh draws so the spacing is exact."""
        for entry in self._parked:
            if entry["remaining"] <= 0:
                return entry
        return None

    def _begin_word(self, now: float, reuse_word: bool = False) -> None:
        # Returns over the cap are let go BEFORE the completion check,
        # or a block whose every word missed would keep drawing fresh
        # words for ever: the due entry blocked the "block finished"
        # branch and then fell through to a fresh draw.
        entry = self._due_return()
        while entry is not None and self._returns_started >= self.MAX_RETURNS:
            self._parked.remove(entry)
            self._retire(entry, "return_cap")
            entry = self._due_return()
        # Completion and the session cap are checked at word
        # boundaries so the block never ends mid-word.
        if self.words_done >= self.words_total and entry is None:
            self._end("completed")
            return
        if (self._t0 is not None
                and (now - self._t0) > self.session_cap_s):
            self._end("time_cap")
            return
        if not reuse_word or self.word is None:
            if entry is not None:
                self._parked.remove(entry)
                self.word = entry["word"]
                self.word_hand = entry["hand"]
                self.ret = entry["return_count"] + 1
                self._ease_word = False
                self._returns_started += 1
            else:
                # Ease-in: two Misses in a row bias ONE draw toward
                # the child's best syllable count, never two in a row.
                ease = (self._draw_ease_word()
                        if self._miss_run >= 2 and not self._ease_word
                        else None)
                if ease is not None:
                    self.word = ease
                    self._ease_word = True
                    self._n_ease_in += 1
                else:
                    self.word = self._draw_word()
                    self._ease_word = False
                self.ret = 0
                self.word_hand = self._next_hand()
                for parked in self._parked:
                    parked["remaining"] -= 1
        if self.word is not None:
            self._seen_words.add(self.word.word)
        self.band_celebrate = None
        self.filled = [None] * self.n_syll
        self.filled_lanes = [None] * self.n_syll
        self.pos = 0
        self.option_set = None
        self.active = None
        self._set_presses = []
        self._dead_lanes = set()
        self._last_tap_t = {}
        self._enter_phase("attend", now)
        self._speak_word()

    def _enter_phase(self, phase: str, now: float) -> None:
        self.phase = phase
        self._phase_t0 = now
        self._phase_until = None
        self.clear_wait()
        if phase != "model":
            self.model_hand = None
        if phase == "warmup":
            self._warmup_beats = []
            self._start_metronome()
        elif phase == "attend":
            self._phase_until = now + self.attend_s
        elif phase == "model":
            self._model_idx = -1
            self._model_next_t = now + self.ioi_s
        elif phase == "choose":
            self._next_spawn_t = now
            self._set_close_t = None
        elif phase == "complete":
            self._phase_until = now + self.complete_s
            # "feedback" is the wait vocabulary the skip chip already
            # knows: the complete card IS this mode's feedback moment.
            self.arm_wait("feedback", self._phase_until,
                          self._skip_complete, started_at=now)
        elif phase == "break":
            self._phase_until = now + self.break_s
            self.arm_wait("break", self._phase_until,
                          self._skip_to_next_word, started_at=now)
        elif phase == "gap":
            self._phase_until = now + self.inter_trial_gap_s
            self.arm_wait("gap", self._phase_until,
                          self._skip_to_next_word, started_at=now)

    def _skip_to_next_word(self, now: float) -> None:
        self._begin_word(now)

    def _skip_complete(self, now: float) -> None:
        self._after_word(now)

    def _update_model(self, now: float) -> None:
        """Light each slot in turn at the beat, speak its syllable, and
        fire ONE tactile roll across all four fingers of the playing
        hand.

        The roll is the whole point: the old tapping mode buzzed the
        single finger that would answer that syllable, which in a
        choice task would announce the target lane before the tiles
        exist. Four lanes in one on_stim_multi call reach the board as
        an arpeggio (the engine spaces one motor per board), so the
        child feels the syllable without feeling WHERE it is.

        Beat deadlines are ABSOLUTE: each syllable is due one interval
        after the previous DEADLINE, not one after the frame that
        noticed it, so the frame delay cannot accumulate across a
        word."""
        due = self._model_next_t
        if due is None or now < due:
            return
        self._model_idx += 1
        if self._model_idx >= self.n_syll:
            self._model_idx = -1
            self._model_next_t = None
            self._enter_phase("choose", due)
            return
        self._model_next_t = due + self.ioi_s
        if self._model_next_t <= now:
            # The loop stalled past a whole beat (alt-tab, IO).
            # Re-anchor rather than burst-fire catch-up syllables.
            self._model_next_t = now + self.ioi_s
        self.model_hand = self.word_hand
        self._speak_syllable(self._model_idx)
        # Every lane of the playing hand, so the roll carries the
        # syllable without carrying a lane. The trial id is the word's
        # next set id, which is what the marker stream needs to tie the
        # 30-band model bytes to the word they belong to.
        self.engine.on_stim_multi(self.active_lanes(),
                                  self.trial_counter, now)

    # ---- the choice phase --------------------------------------------------
    def _update_choose(self, now: float) -> None:
        if self.option_set is None:
            if self._next_spawn_t is not None and now >= self._next_spawn_t:
                self._spawn_set(now)
            return
        if self._set_close_t is not None:
            if now >= self._set_close_t:
                self._close_set(now)
            return
        if self._exit_t is not None and now >= self._exit_t:
            self._miss_set(now)

    def _spawn_set(self, now: float) -> None:
        """Four tiles for syllable `self.pos`: build them, open the
        trial, and mark the onset.

        The marker call goes through the engine's ordinary cue path so
        the force window, the timeout and the EEG byte all arm the way
        they do everywhere else, with `silent_stim` set for the length
        of the call so nothing is heard, felt or highlighted. A cue on
        the target lane here would hand the child the answer."""
        lanes = self.active_lanes()
        self.option_set = build_option_set(
            self.word, self.pos, self.rung, self.rng, self.inventory,
            lanes, self._lane_targets, self._recent_target_lanes,
            homophone_foils=self.homophone_foils)
        tlane = self.option_set.target_lane
        self._lane_targets[tlane] = self._lane_targets.get(tlane, 0) + 1
        self._recent_target_lanes.append(tlane)
        self.trial_counter += 1
        self.active = PendingTrial(
            trial_id=self.trial_counter,
            lane=tlane,
            stim_t_perf=now,
            keys_pressed=[],
            incorrect_presses=[],
        )
        self._spawn_t = now
        self._exit_t = now + self.fall_s
        self._next_spawn_t = None
        self._set_close_t = None
        self._set_presses = []
        self._dead_lanes = set()
        self._first_kind = None
        self._correct_t = None
        self._glow_t = None
        self.lift_t = None
        self._last_tap_t = {}
        self._respeak = self.rung in self.respeak_rungs
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "set_spawn", lane=tlane, t_perf=now,
                detail=(f"trial_id={self.trial_counter};"
                        f"word={self.word.word};pos={self.pos};"
                        f"rung={self.rung};ret={self.ret}"),
                hand=self.word_hand)
        self.silent_stim = True
        try:
            self.engine.on_stim_multi(lanes, self.trial_counter, now,
                                      buzz=False)
        finally:
            self.silent_stim = False
        if self._respeak:
            self._speak_syllable(self.pos)

    def _handle_press(self, ev: PressEvent, now: float) -> None:
        if self.phase == "warmup":
            self._warmup_tap(ev)
            return
        if self.phase != "choose" or self.option_set is None:
            # No penalty anywhere in this mode: a child fidgeting
            # between words must not lose anything for it.
            return
        if self._set_close_t is not None:
            # The set is already scored and fading out.
            return
        last = self._last_tap_t.get(ev.lane)
        if last is not None and (ev.t_perf - last) < self.tap_debounce_s:
            return
        self._last_tap_t[ev.lane] = ev.t_perf
        kind = self._classify(ev)
        peak = self._peak_for(ev)
        self._set_presses.append(Press(lane=ev.lane, t_perf=ev.t_perf,
                                       kind=kind, peak=peak))
        if self.active is not None:
            self.active.keys_pressed.append(ev.lane)
        if kind == KIND_CORRECT:
            if self._first_kind is None:
                self._first_kind = "ok"
            self.filled[self.pos] = self.option_set.target
            self.filled_lanes[self.pos] = ev.lane
            self._correct_t = ev.t_perf
            self.lift_t = ev.t_perf
            self._score_set(now, ev.t_perf)
            self._set_close_t = ev.t_perf + self.CORRECT_HOLD_S
        elif kind == KIND_WRONG:
            if self._first_kind is None:
                self._first_kind = "wrong"
            self._dead_lanes.add(ev.lane)
            if self.active is not None:
                self.active.incorrect_presses.append((ev.lane, ev.t_perf))

    def _classify(self, ev: PressEvent) -> str:
        """The input rule, in the order the docstring states it. Only
        a press on the target lane, after the lockout, while the set
        is on screen, ever scores."""
        opt = self.option_set.option_for_lane(ev.lane)
        if opt is None or not self._lane_in_game(ev.lane):
            return KIND_OFF_HAND
        if (self._spawn_t is not None
                and ev.t_perf < self._spawn_t + self.spawn_lockout_s):
            return KIND_ANTICIP
        if ev.lane in self._dead_lanes:
            return KIND_WRONG_REPEAT
        if ev.lane == self.option_set.target_lane:
            return KIND_CORRECT
        return KIND_WRONG

    def _miss_set(self, now: float) -> None:
        """The set left the screen unanswered: the target tile glows on
        its way out and the syllable is spoken once. The word stops
        here and comes back later."""
        self._glow_t = now
        self._score_set(now, None)
        self._speak_syllable(self.pos)
        self._set_close_t = now + self.MISS_GLOW_S

    def _close_set(self, now: float) -> None:
        missed = self._first_kind != "ok" and self._correct_t is None
        self.option_set = None
        self._spawn_t = None
        self._exit_t = None
        self._set_close_t = None
        if missed:
            self._park_word(now)
            self._finish_word(now, completed=False)
            return
        self.pos += 1
        if self.pos >= self.n_syll:
            self._enter_phase("complete", now)
            self._speak_word()
            return
        self._next_spawn_t = now + self.set_gap_s

    # ---- scoring -----------------------------------------------------------
    def _score_set(self, now: float, correct_t: float | None) -> None:
        """Close one option set: label it, log its row, move the
        staircase. Called once per set, either at the correct press or
        at the exit line."""
        trial = self.active
        if trial is None or self.word is None or self.option_set is None:
            return
        self.active = None
        first = self._first_kind or "none"
        if correct_t is not None:
            err = "ok" if first == "ok" else "wrong_first"
        else:
            err = "miss"
        rt_ms = ((correct_t - self._spawn_t) * 1000.0
                 if correct_t is not None and self._spawn_t is not None
                 else None)
        if err == "ok":
            outcome = TrialResult(label="Great",
                                  points=self.score_cfg.great_points,
                                  rt_ms=rt_ms)
        elif err == "wrong_first":
            outcome = TrialResult(label="Good",
                                  points=self.score_cfg.good_points,
                                  rt_ms=rt_ms)
        else:
            outcome = TrialResult(label="Miss",
                                  points=self.score_cfg.miss_points,
                                  rt_ms=rt_ms)
        wrong_kind = None
        for p in self._set_presses:
            if p.kind == KIND_WRONG:
                wrong_kind = self.option_set.kind_for_lane(p.lane)
                break
        rec = SetRecord(
            word=self.word.word, pos=self.pos, n_syll=self.n_syll,
            band=self.band, rung=self.rung, hand=self.word_hand,
            ret=self.ret, first=first, err=err, rt_ms=rt_ms,
            wrong_kind=wrong_kind,
            n_anticip=sum(1 for p in self._set_presses
                          if p.kind == KIND_ANTICIP),
            n_off_hand=sum(1 for p in self._set_presses
                           if p.kind == KIND_OFF_HAND),
        )
        self._sets.append(rec)
        # The EEG response marker must lock to the child's own press,
        # so it is the first press that was neither an anticipation nor
        # an off-hand press; outcome.rt_ms is spawn-to-correct-press,
        # which is not the same thing on a wrong-then-right set.
        resp_t = None
        for p in self._set_presses:
            if p.kind in (KIND_ANTICIP, KIND_OFF_HAND):
                continue
            resp_t = p.t_perf
            break
        self.engine.log_trial(
            trial, outcome, now,
            stimulus=self._pack_stimulus(rec),
            # One lane is right, and the row says which.
            correct_lanes=[self.option_set.target_lane],
            # A Miss here is a set nobody answered, never a wrong
            # finger: the mode's own code beats the engine's
            # had_incorrect_press-derived guess.
            error_type=(err if outcome.label == "Miss" else ""),
            response_t_perf=resp_t,
            hand=self.word_hand,
        )
        if self._source_alive():
            self._move_rung(err in ("ok",), err, now)

    def _move_rung(self, first_ok: bool, err: str, now: float) -> None:
        """The 3-down-1-up staircase (Levitt 1971): three consecutive
        first-press-correct sets make the foils harder, one set whose
        first press was wrong or missed makes them easier. The run
        counter resets on every move, so a rung cannot move twice off
        one run."""
        old = self.rung
        if first_ok:
            self._run += 1
            if self._run >= 3 and self.rung < self.rung_max:
                self.rung += 1
                self._run = 0
            elif self._run >= 3:
                self._run = 0
        else:
            self._run = 0
            if self.rung > self.rung_min:
                self.rung -= 1
        if self.rung == old:
            return
        self._rung_trace.append(self.rung)
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "rung_change",
                detail=(f"old={old};new={self.rung};"
                        f"reason={'run3' if first_ok else err};"
                        f"set_idx={len(self._sets)}"),
                hand=self.word_hand)

    def _park_word(self, now: float) -> None:
        """A missed word waits, then comes back in full with fresh
        foils. Two returns, then it retires for the block: expanding
        spaced retrieval (Leonard and Deevy 2020), not drilling."""
        if self.word is None:
            return
        nxt = self.ret
        if nxt >= len(self.return_after):
            self._retire({"word": self.word, "return_count": self.ret},
                         "third_miss")
            return
        entry = {
            "word": self.word,
            "hand": self.word_hand,
            "return_count": self.ret,
            "remaining": self.return_after[nxt],
        }
        self._parked.append(entry)
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "word_parked",
                detail=(f"word={self.word.word};"
                        f"return_count={self.ret};"
                        f"due_after={entry['remaining']}"),
                hand=self.word_hand)

    def _retire(self, entry: dict, reason: str) -> None:
        word = entry.get("word")
        name = getattr(word, "word", str(word))
        self._retired.append(name)
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "word_retired",
                detail=f"word={name};reason={reason}",
                hand=self.word_hand)

    def _finish_word(self, now: float, completed: bool) -> None:
        """Close the word attempt: the record the band gate, the streak
        and the ease-in draw all work from."""
        if self.word is None:
            return
        # Only the sets of THIS attempt, which is the tail of the list:
        # the same word can appear again as a return with its own sets,
        # and the two attempts are separate rows in every chart.
        tail: list[SetRecord] = []
        for s in reversed(self._sets):
            if s.word != self.word.word or s.ret != self.ret:
                break
            tail.append(s)
        sets = list(reversed(tail))
        all_first_ok = bool(sets) and all(s.first == "ok" for s in sets)
        if completed and all_first_ok:
            label, error = "Great", "ok"
        elif completed:
            label, error = "Good", "wrong_first"
        else:
            label, error = "Miss", "miss"
        rec = WordRecord(word=self.word.word, n_syll=self.n_syll,
                         band=self.band, ret=self.ret,
                         correct=(label == "Great"), completed=completed,
                         error=error, hand=self.word_hand, sets=sets)
        self._records.append(rec)
        if label == "Great":
            self._streak += 1
            self._max_streak = max(self._max_streak, self._streak)
            if self._streak in self.STREAK_MILESTONES:
                stars = self.STREAK_MILESTONES.index(self._streak) + 1
                self.round_stars = max(self.round_stars, stars)
                self.star_flash_t = now
                raw = getattr(self.engine, "raw_logger", None)
                if raw:
                    raw.queue_event(
                        "syllables_streak",
                        detail=(f"n={self._streak} "
                                f"word_idx={self.words_done}"),
                        hand=self.word_hand)
        else:
            self._streak = 0
        self._miss_run = self._miss_run + 1 if label == "Miss" else 0
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "word_complete",
                detail=(f"word={self.word.word};ret={self.ret};"
                        f"outcome={label};sets={len(sets)}"),
                hand=self.word_hand)
        # The band gate only learns from words the child could
        # actually answer: with the serial link down every set times
        # out, and an unguarded gate would demote on hardware
        # downtime, making difficulty respond to the device.
        if self._source_alive() and self.ret == 0:
            self._recent.append(label != "Miss")
            self._since_band_change += 1
            self._maybe_move_band()
        if not completed:
            self._enter_phase("gap", now)
            self._after_word_bookkeeping(now)

    def _after_word(self, now: float) -> None:
        """Leaving the COMPLETE card: close the word, then the gap."""
        self._finish_word(now, completed=True)
        self._enter_phase("gap", now)
        self._after_word_bookkeeping(now)

    def _after_word_bookkeeping(self, now: float) -> None:
        if self.ret == 0:
            self.words_done += 1
            self._round_rewards(now)
            self._maybe_break(now)

    def _source_alive(self) -> bool:
        """False only when a sample-providing source is disconnected
        (fully, or this session's playing hands via a one-board drop).
        Keyboard sessions are always alive."""
        src = getattr(self.engine, "source", None)
        if src is None or not getattr(src, "provides_samples", False):
            return True
        if not getattr(src, "is_connected", True):
            return False
        down = getattr(self.engine, "_hands_down", None)
        if not isinstance(down, set):
            down = set()
        hands = set(getattr(self, "hand_names", None) or [])
        if not hands:
            hand = str(getattr(self.engine, "hand_mode", "right"))
            hands = {"left", "right"} if hand == "both" else {hand}
        return not (down & hands)

    def _peak_for(self, ev: PressEvent) -> float | None:
        helper = getattr(self.engine, "_peak_force_for_lane", None)
        if not callable(helper):
            return None
        try:
            return helper(ev.lane)
        except Exception:
            return None

    # ---- the stimulus string ----------------------------------------------
    def _pack_stimulus(self, rec: SetRecord) -> str:
        """The row's stimulus cell, documented in the module docstring
        because the notebook parses it. Everything the analysis needs
        about one option set is here: what was on screen, on which
        lanes, of which foil kinds, and every press that landed."""
        opts = ",".join(
            f"{o.lane + 1}:{o.text}:{o.kind}"
            for o in self.option_set.options) if self.option_set else ""
        presses = ",".join(
            f"{p.lane + 1}:"
            f"{(p.t_perf - (self._spawn_t or p.t_perf)) * 1000.0:.1f}:"
            + (f"{p.peak:.1f}" if p.peak is not None else "")
            + f":{p.kind}"
            for p in self._set_presses)
        parts = [
            rec.word,
            f"pos={rec.pos}",
            f"nsyll={rec.n_syll}",
            f"syl={self.option_set.target if self.option_set else ''}",
            f"band={rec.band}",
            f"rung={rec.rung}",
            f"hand={'L' if rec.hand == 'left' else 'R'}",
            f"fall={self.fall_s * 1000.0:.0f}",
            f"respeak={1 if self._respeak else 0}",
            f"ret={rec.ret}",
            f"opts={opts}",
            f"tlane={self.option_set.target_lane + 1 if self.option_set else 0}",
            f"presses={presses}",
            f"first={rec.first}",
            f"err={rec.err}",
            f"rt={rec.rt_ms:.1f}" if rec.rt_ms is not None else "rt=",
        ]
        if self._ease_word:
            # Only on biased draws, so the notebook can hold them out
            # of the accuracy charts.
            parts.append("ease=1")
        parts.append(f"streak={self._streak}")
        parts.append(f"sup={1 if self.supervised else 0}")
        return ";".join(parts)

    # ---- rewards and rounds ------------------------------------------------
    @property
    def stickers(self) -> int:
        return self._stickers

    @property
    def n_rounds(self) -> int:
        return max(1, -(-self.words_total // self.round_size))

    def _round_rewards(self, now: float) -> None:
        """One sticker the moment a round's last word closes, before
        any break screen. Earned by finishing the round, never by
        scoring in it."""
        if self.words_done <= 0 or self.words_done % self.round_size:
            return
        self._stickers += 1
        self.sticker_flash_t = now
        self.round_stars = 0
        self.star_flash_t = None
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "syllables_sticker",
                detail=f"round={self._stickers}",
                hand=self.engine.hand_mode)

    def _maybe_break(self, now: float) -> None:
        if (self.words_done < self.words_total and self.break_s > 0
                and self.words_done % self.round_size == 0):
            self._enter_phase("break", now)

    # ---- band progression --------------------------------------------------
    def _maybe_move_band(self) -> None:
        """The brief's rule, on WORD outcomes: promote at 8 of the last
        10 answered, demote under 5 of 10. Evaluated only once 10 words
        have run since the last change, so one change cannot cascade
        off the window that triggered it."""
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
        promoted = new_idx > idx
        self.band = BANDS[new_idx]
        self._band_trace.append(self.band)
        self._since_band_change = 0
        self._recent.clear()
        self._bag = []
        if promoted:
            self.band_celebrate = self.band
        detail = (f"band={self.band} wins={wins}/10 "
                  f"word_idx={self.words_done}")
        if promoted:
            detail += " shown=1"
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event("syllables_band", detail=detail,
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

    def _speech_root(self) -> Path:
        try:
            from ...config import _bundle_root
            root = _bundle_root()
        except Exception:
            root = Path(__file__).resolve().parents[3]
        return root / self.speech_dir

    def speech_path(self, stem: str) -> Path | None:
        """The rendered file for a word or a word_k syllable, or None
        when nothing is on disk. ogg first, then wav: the renderer
        writes ogg, a hand-made file is likely to be wav."""
        root = self._speech_root()
        for ext in (".ogg", ".wav"):
            p = root / f"{stem}{ext}"
            if p.exists():
                return p
        return None

    def _speak_word(self) -> None:
        if self.word is not None:
            self._speak(self.word.word, self.word.word)

    def _speak_syllable(self, k: int) -> None:
        if self.word is None or not (0 <= k < self.n_syll):
            return
        self._speak(f"{self.word.word}_{k}", self.word.syllables[k])

    def _speech_failed(self, stem: str, reason: str) -> None:
        self.speech_failures = getattr(self, "speech_failures", 0) + 1
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event("speech_failed", t_perf=time.perf_counter(),
                            detail=f"file={stem};reason={reason}", hand=self.word_hand)

    def _speak(self, stem: str, text: str) -> None:
        """Play a rendered speech file, or fall back to the macOS `say`
        command on a developer machine.

        The lab machine runs the Windows build, where `say` does not
        exist, and Apple's licence does not allow its voices inside a
        distributed build, so files are the shipping path and `say` is
        a convenience for whoever is working on the mode. backend
        `auto` (the default) plays a file when one is there and speaks
        on a Mac when one is not; `file` never spawns anything; `say`
        never reads a file; `off` is silent. A missing file is logged
        once per stem and never raises: a child mid-session must not
        meet a stack trace because an asset was not rendered."""
        backend = self.speech_backend
        if backend == "off":
            self._speech_failed(stem, "disabled")
            return
        path = None if backend == "say" else self.speech_path(stem)
        if path is not None:
            audio = getattr(self.engine, "audio", None)
            player = getattr(audio, "play_speech", None)
            delivered = False
            if callable(player):
                try:
                    delivered = bool(player(str(path), volume=self.speech_volume))
                except Exception:
                    pass
            if not delivered:
                self._speech_failed(stem, "playback_unavailable")
                return
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event("speech", t_perf=time.perf_counter(),
                                detail=f"file={path.name}",
                                hand=self.word_hand)
            return
        if backend == "file":
            self._speech_failed(stem, "missing_file")
            if stem not in self._missing_speech:
                self._missing_speech.add(stem)
                log.info("No speech file for %r under %s; running silent",
                         stem, self.speech_dir)
            return
        if sys.platform != "darwin" or shutil.which("say") is None:
            self._speech_failed(stem, "missing_voice")
            if stem not in self._missing_speech:
                self._missing_speech.add(stem)
                log.info("No speech file for %r and no `say` here; "
                         "running silent", stem)
            return
        # The system voice is a developer convenience, never a shipped
        # path: each call holds the shared audio device for about a
        # second. Under a dummy audio driver (every test and every
        # headless run) a block's worth of words piles up on that
        # device and wedges coreaudiod, so stay silent there.
        if os.environ.get("SDL_AUDIODRIVER", "").lower() == "dummy":
            self._speech_failed(stem, "headless_audio")
            if stem not in self._missing_speech:
                self._missing_speech.add(stem)
                log.info("No speech file for %r and audio is dummy; "
                         "running silent", stem)
            return
        # One voice at a time. Without this the previous word is
        # orphaned rather than stopped, so a fast block leaves a queue
        # of processes nobody reaps.
        prev = self._say_proc
        if prev is not None and prev.poll() is None:
            try:
                prev.terminate()
            except Exception:
                pass
        try:
            self._say_proc = subprocess.Popen(
                ["say", str(text)],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            self._say_proc = None
            return
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event("speech", t_perf=time.perf_counter(),
                            detail=f"say={text}", hand=self.word_hand)

    def _reap_say(self) -> None:
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
        block ran under, first-press accuracy split every way the
        analysis asks for it, the foil-kind confusion counts, the
        staircase trace and the engagement numbers, so a session is
        readable without parsing the stimulus strings back out."""
        sets = self._sets
        n_sets = len(sets)
        first_ok = sum(1 for s in sets if s.first == "ok")

        def _acc(rows: list[SetRecord]) -> float | None:
            return (round(sum(1 for s in rows if s.first == "ok")
                          / len(rows), 3) if rows else None)

        def _group(key) -> dict:
            out: dict[str, list[SetRecord]] = {}
            for s in sets:
                out.setdefault(str(key(s)), []).append(s)
            return {k: {"n": len(v), "acc": _acc(v)}
                    for k, v in sorted(out.items())}

        confusion: dict[str, int] = {}
        for s in sets:
            if s.first == "wrong" and s.wrong_kind:
                confusion[s.wrong_kind] = confusion.get(s.wrong_kind, 0) + 1
        rts = [s.rt_ms for s in sets
               if s.first == "ok" and s.rt_ms is not None]

        def _mean(xs) -> float | None:
            return round(sum(xs) / len(xs), 1) if xs else None

        def _sd(xs) -> float | None:
            if len(xs) < 2:
                return None
            m = sum(xs) / len(xs)
            return round((sum((x - m) ** 2 for x in xs)
                          / (len(xs) - 1)) ** 0.5, 1)

        words = self._records
        first_attempts = [w for w in words if w.ret == 0]
        returns = [w for w in words if w.ret > 0]
        per_hand = {}
        for hand in self.hand_names:
            rows = [s for s in sets if s.hand == hand]
            per_hand[hand] = {"n": len(rows), "acc": _acc(rows)}
        return {
            "hands": self.hand_names,
            "band_final": self.band,
            "band_trace": list(self._band_trace),
            "rung_start": self.rung_start,
            "rung_final": self.rung,
            "rung_trace": list(self._rung_trace),
            "ioi_ms": round(self.ioi_s * 1000.0),
            "n_sets": n_sets,
            "first_press_accuracy": (round(first_ok / n_sets, 3)
                                     if n_sets else None),
            "chance_level": round(1.0 / 4, 3),
            "accuracy_by_rung": _group(lambda s: s.rung),
            "accuracy_by_pos": _group(lambda s: s.pos),
            "accuracy_by_nsyll": _group(lambda s: s.n_syll),
            "confusion_by_kind": confusion,
            "mean_rt_correct_ms": _mean(rts),
            "sd_rt_correct_ms": _sd(rts),
            "n_anticipations": sum(s.n_anticip for s in sets),
            "n_off_hand": sum(s.n_off_hand for s in sets),
            "words_attempted": len(first_attempts),
            "words_completed": sum(1 for w in first_attempts if w.completed),
            "words_returned": self._returns_started,
            "returns_completed": sum(1 for w in returns if w.completed),
            "words_retired": len(self._retired),
            # Words parked when the block ended: they were missed and
            # their return never came round, which is a fact about the
            # block's length, not about the child.
            "words_parked_at_end": len(self._parked),
            "per_hand": per_hand,
            # The word-level accuracy the results screen and the
            # history chip read: a word counts when the child finished
            # it, whatever it took.
            "n_words": len(first_attempts),
            "accuracy": (round(sum(1 for w in first_attempts if w.completed)
                               / len(first_attempts), 3)
                         if first_attempts else None),
            "supervised": self.supervised,
            "speech_failures": getattr(self, "speech_failures", 0),
            "warmup_taps": self._warmup_done,
            "warmup_asyn_mean_ms": _mean(self._warmup_asyn),
            "warmup_asyn_sd_ms": _sd(self._warmup_asyn),
            "max_streak": self._max_streak,
            "stickers": self._stickers,
            "n_ease_in": self._n_ease_in,
            "demo": self.demo,
            "end_reason": self.end_reason,
            **self.wait_skip_stats(),
        }
