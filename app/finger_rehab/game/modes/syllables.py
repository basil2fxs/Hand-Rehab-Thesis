"""Syllables: a syllable-matching game for children with reading
difficulty. The word is heard and seen, then its syllables come down
the screen one set at a time, four written options over four fingers,
and the child presses the finger under the chunk that was spoken. A
different population from the rest of this suite, with a different
evidence base; the claim limits at the bottom of this docstring are
part of the design.

WHAT THE CHILD DOES. ATTEND: the whole word appears at the top as n
empty slots with the word written large under them, and the word is
spoken. MODEL: each slot lights in turn at the beat, its chunk shows
and the syllable is spoken as it sounds in that word; then every slot
shows its chunk at once and the whole word is said again, the blend.
No motor runs. Then the slots empty again. CHOOSE, once per syllable
in order: four tiles fall slowly down
four lanes that sit over the four fingers, one tile is the syllable
and three are foils. The child presses the finger under the right
tile. If the set is still unanswered late in its fall, the right
finger buzzes once (PROMPT below). A correct press lifts the
tile into the word strip; a wrong press greys that tile and nothing
else. COMPLETE: the strip is full, the whole word is spoken again.

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
written syllables, as the tiles are, though neither asked for a choice
among four: this is print-linked syllable work, not a replication.
Segmentation develops from large units to small (Liberman,
Shankweiler, Fischer and Carter 1974: 46 percent of four year olds
could tap syllables and none could tap phonemes; Ziegler and Goswami's
2005 grain size theory explains why English readers need the big units
as well as the small ones). That argument is about children of 4 to 6.
For a reader of 7 and over the foils test grapheme-phoneme contrasts
inside the syllable (an onset, a vowel, a coda, a letter order), so
the task is phonics with letters at the syllable grain, in the terms
of the meta-analyses above (the deep review of 1 October 2026,
docs/research/deep/syllables.md).

WHY EACH SYLLABLE SOUNDS AS IT DOES IN ITS WORD. Bhattacharya and
Ehri's graphosyllabic method says the word, splits it into spoken
syllables as close as possible to their sounds in the whole word,
matches each to its spelling, then blends them back into the word.
The model does exactly that, so the ti and ger of tiger are "tie" and
"guh" and blend back into tiger. Until 29 September 2026 every chunk
had one spelt recording reused in every word, which said the ger of
tiger as "jer" (the ginger reading) and never blended back. The cost
of the in-word form is that a weak vowel ("uh", "ih") sounds the same
under ter, tar and tur, so on those syllables a vowel foil could only
be rejected by spelling knowledge: every profile swaps it for a coda
foil there (_foil_kinds). Spelling pronunciations remain the better
aid for REMEMBERING spellings (Ocal and Ehri 2017; Hilte and Reitsma
2006), which is not what the choice task asks.

THE GAME SHAPE COMES FROM GRAPHOGAME. Richardson and Lyytinen (2014)
describe the method this mode copies: multiple-choice trials pairing
an audio segment with the right written form, adaptation aimed at
about 80 percent correct, immediate positive feedback. Mehringer et
al. (2020) add the distractor rule (a target among one to nine
distractors, some deliberately confusable). Two results bound what may
be claimed from it: the Education Endowment Foundation's trial of
GraphoGame Rime in English (Worth, Nelson, Harland, Bernardinelli and
Styles 2018; 398 Year 2 pupils in 15 schools) found no effect on
reading or spelling, and Ahmed, Wilson, Mead, Noble, Richardson,
Wolpert and Goswami (2020) is a later re-analysis of part of that
sample, not a separate positive result; McTigue, Solheim, Zimmer and
Uppstad (2020) found a negligible overall effect across the GraphoGame
literature with SUPPORTIVE ADULT INTERACTION as the only significant
moderator. Hence an adult seated beside the reader in the case
procedure (FINAL TRIAL RESULTS/4 Syllables case/README.md; the rest
screen's adult line never shows in the sectioned sitting), and hence
the claim limits below.

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
negative feedback is quiet, informational and late. That describes the
one-section block: in the sectioned sitting the answer is shown
straight after a second wrong press (SECTIONS), which is not late.

NO HINT BEFORE THE CHILD HAS HAD TIME. Fitts and Seeger (1953) showed
response selection is fastest when the stimulus and the response
share a spatial code: a tile falling in the lane over the finger that
answers it IS that code. Nothing carries the answer early: the model
plays no buzz at all; the option-set spawn goes through the engine's
cue path with `silent_stim` set, so it arms the force window, the
timeout and the EEG marker but fires no tone, no screen highlight and
no buzzer; the four tiles are drawn identically; and the target lane
is drawn by a deficit rule with a random tie-break, never in a
predictable place.

PROMPT. A late buzz on the right finger, and only that finger, the
time-delay prompting method from special education: the answer is
given only after the learner has had a fair chance to find it (Eyler
and Ledford 2024 review the method; Browder et al. 2009 rate it
evidence-based for sight-word teaching, from single-case studies of
children with intellectual disability, not of dyslexia). The delay is
PROGRESSIVE and per word. A new word's prompt comes at the first
share of the fall in prompt_steps (0.6, then 0.75, then 0.9); each
set of that word answered right before any buzz moves it one step
later, and past the last step the word plays with no prompt. A wrong
first press before the buzz, or a set that leaves the screen, moves
it one step back. Walker (2008) reviewed constant and progressive
time delay across 22 studies: constant delay, what this mode used
before, came with more errors to criterion and a later handover from
the prompt to the learner, though from indirect comparisons only. The
fade is the guidance hypothesis at work: help given every time keeps
performance up and learning down (Salmoni, Schmidt and Walter 1984;
Winstein and Schmidt 1990, 50 percent feedback beat 100 percent at
retention; Sigrist, Rauter, Riener and Wolf 2013 for haptic
guidance). The delay also never undercuts the child: once three sets
have been answered before any buzz, the buzz waits at least the
child's median time to a first press plus prompt_floor_margin_ms
(300). The median is a Kaplan-Meier estimate over the last 12 sets
(Kaplan and Meier 1958), each set the buzz or the end of the fall cut
off counted as censored there. The plain median of the answers that
beat the buzz, used until 1 October 2026, read 2.54 s for a simulated
slow child whose true median was 3.71 s (the deep review), so it
undercut the readers it was there for. When fewer than half the sets
were answered alone, the longest time seen stands in. The buzz never
comes after 0.9 of the fall, so it always lands while the tiles are
there to press. Letting the child try first fits the retrieval
literature (Kornell, Hays and Bjork 2009; Metcalfe 2017: errors then
correction beat error avoidance in typical learners) and Gabay
(2021): adults with dyslexia learn worse from immediate feedback than
from delayed. One finger only: several motors at once carry no
information here and read as noise.
What the buzz is not: it carries no letter or sound, so it is a prompt
to respond, not a reading aid, and there is no evidence a vibration
prompt helps reading (Stevens et al. 2021 found no effect of the
multisensory element in Orton-Gillingham). The UNPROMPTED CORRECT
rate (sets answered right before any buzz) mixes reading speed with
accuracy: at fixed knowledge it fell from 0.84 to 0.29 as a simulated
reader slowed from 1.5 to 4.5 s, while the accuracy of the answers
given before any buzz stayed at 0.93 to 0.97 (the deep review). So
the analysis reports it beside those two parts, the time to an
unaided first press and the accuracy before the buzz, and the case's
repeated measure is the fixed probe (PROBE below), which never
adapts. A prompted answer scores Good, not Great, and does not move
the foil staircase.

DIFFICULTY MOVES ON TWO CLOCKS.
- The FOIL RUNG (1 to 8) controls how similar the wrong options are,
  how long the tiles take to fall, and whether the syllable is spoken
  again at spawn. It moves by a 3-down-1-up staircase on first-press
  correctness. Levitt (1971) puts that rule at 79.4 percent, but with
  equal steps up and down the transformed rules miss their nominal
  points (Garcia-Perez 1998), and simulated classic blocks ran at 0.80
  to 0.84 on the sets that move it, near the 80 percent GraphoGame
  targets. That holds for the classic design only: in the sectioned
  sitting the rung sets just time, print and respeak and climbs
  towards its ceiling, so it is never a threshold there. A rung can
  move every three sets, so it tracks the child inside a round.
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
Schneider 2018) and children are slower than adults: about 1.8 times
at 10 and 1.5 times at 12 (Hale 1990), and slower still at 8, since
the gap shrinks exponentially with age (Kail 1991). So an 8 year old
needs roughly a second before any READING is done, and a struggling
reader needs time to read four chunks and compare them. Time pressure is also what
separates dyslexic from typical letter-sound binding (Aravena,
Snellings, Tijms and van der Molen 2013). So a set is on screen for
6.0 s at the entry rung and never under 4.0 s: the window is a floor
for thinking, not a rhythm target. The pace around the sets is as
unhurried: the word is shown for 3 s, each modelled syllable ends
with half a second of quiet, a right tile is held 0.8 s as it lifts,
1 s passes between sets and 1.5 s between words. These were 4.0 and
2.5 s, 1.5 s and about 0.15, 0.3, 0.4 and 0.8 s until 29 September
2026, when play-testing found the mode rushed; the numbers are design
choices, not measured optima.

WHO THE BLOCK IS FOR. Everything above describes the 6 to 9 year old
the mode was built for. syllables_profiles.py sets it up for older
readers too, from the intake age: faster falls and derived and made-up
words from 10, and for adults the word heard without being seen, no
buzz, rarer derived and made-up words and a fall-time staircase whose
threshold is the result. The classic profile is the design the
healthy baseline study pre-registered, before Syllables left that
study on 28 September 2026. Speech is a free synthetic voice (Kokoro,
British), each syllable said as it sounds in its word
(scripts/syllables_tts.py); a recorded Australian voice can replace
it (scripts/syllables_recording_kit.py), with each chunk spelt.

SECTIONS (syllables.sections, on by default; every profile except
classic). The research pass of 30 September 2026
(docs/research/new_modes/syllables-task-design.md) found the syllable
programmes that worked mixed recognition with production and ended on
whole-word reading, so a block is split into parts, each with its own
card: HEAR AND PICK, whose first words (up to four, the REVIEW) take
unrelated foils and move no ladder before the task above takes foils
from one confusion family at a time, with one card and one counter
for both (2 October 2026), BUILD THE WORD (the word heard, not
shown, from 10 up, and built slot by slot; each slot's lanes hold one
of the word's other syllables as well as family foils, so the last
slot is still a choice) and, from 10 to 59, a QUICK LOOK speed
check. Up to four words
review, 30 percent of the rest build, the others pick. The changes
inside a set: the tiles drop into place and stay still with a time bar
above them; after two wrong presses the answer is shown (its tile
glows, its syllable is heard and it fills its slot plainly), because
answering until correct taught no more than being told (Butler,
Karpicke and Roediger 2007) and a lure is corrected best straight away
(Marsh, Fazio and Goswick 2012); a set that times out is shown the
same way. Every word then ends whole: the slots close into one word,
held silent for read_hold_s (1.5 s, 1.0 for adults) so the reader
decodes it, then it is heard (Share 1999; Kyte and Johnson 2006). A
word with a shown slot counts as missed and comes back later.
FOILS BY FAMILY. Each profile has confusion families (vowel, onset,
coda, reversal, position, order, affix; syllables_profiles.py) with a
level each: level 0 puts the target among unrelated chunks, levels 1
to 3 put one to three of the family's foils in the set. Three unaided
right first presses on a family's sets raise its level, and at level
3 a further run of three passes it (the code's family_mastered; the
analysis says "passed level 3", since a run of three is far below the
80 to 100 percent over two sessions that skill-acquisition studies
use, McDougale et al. 2020); an error lowers it. A family is taught for three
words at a time, then the next open family takes over (lowest level
first), which is a new contrast blocked for a few words and then
mixed. The rung still moves by 3-down-1-up and sets the time allowed.
Levels start at 0 in every block: carrying them across sittings is
not built. QUICK LOOK. A real word of up to nine letters is shown for
the exposure, covered by hash marks for 150 ms, then four words of the
same syllable count (closest first letter and length first) sit over
the four fingers for up to 4 s; one press answers. The exposure starts
at the profile's speed_expo_ms and moves 80 ms at a time between 100
ms and 1.5 s: down after every right answer until the first error,
then 3-down-1-up. The threshold is the mean exposure at the reversals
after the first, and 20 trials give a rough one: two simulated blocks
of one reader differed with an SD of about 0.05 to 0.07 s, and 16
trials gave no threshold in 11 to 33 percent of blocks for 10 to 15,
so every profile with a quick look plays 20 (the deep review). It is
practice and a fluency measure, as the German syllable app
ended its lessons with brief-exposure reading (Hess et al 2024) and
repeated syllable reading sped up only the units trained (Huemer, Aro,
Landerl and Lyytinen 2010); it is not a claimed cause of better
reading.
Exposures are whole display frames (about 17 ms at 60 Hz). The design
note's counts per section (Section 6.1) are for a shorter block than
the 30-word default; 6 to 9 plays 20 words (syllables_profiles.py).

PROBE, the READING CHECK card (syllables.probe: case, so it plays for
a case reader, a code from D01 up, in every profile but classic). The
sitting opens with fixed sets, the same sets in the same order for
every session of an age group (assets/words/syllables_probe.json,
built by scripts/build_syllables_probe.py). Each holds the target, one
near foil from one family and two far foils, every family equally
often; half the targets are heard with a weak vowel where the family
allows it, and half the words are held out of training for that age,
so the probe holds practised and unpractised words. The word is
heard, then after attend_s the four tiles appear as the target
syllable is heard once; one press answers, right or wrong, and the
tiles go at once either way, with no prompt, no replay, no return, no
points and no after-press cue, in a fixed time per set (the profile's
entry fall). The in-game numbers adapt to the reader and cannot show
change across sessions; a fixed list can (GraphoGame keeps static
assessment levels apart from training, Richardson and Lyytinen 2014;
fixed lists reach an ICC of 0.91, Yeatman et al. 2021). Probe rows are
sec=probe and move no ladder, and the session cap times the training
from the probe's end. syllables.probe_only plays the probe alone; or
two presses of Esc at the card after the probe end a baseline session
with every answer on disk. That card waits for Start (_card_holds), so
no training word starts by itself in a baseline session.

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
defaults are audio-tactile-visual (the buzzer and the cue tone with
the screen), and this mode splits them across the phases on purpose.
The model is audio-visual: the syllable is spoken and the slot lights. The
choice-set spawn is none of those (the `silent_stim` path fires no
tone, no highlight and no buzz), so the rt on a set row is a
spoken-to-printed matching time under a silent onset, not a cued
reaction time, and it is not comparable with the rt of any other mode
in this suite. An rt on a prompted set (prompt=1) includes the buzz's
help and belongs with the prompted answers, not the unprompted ones.
The after-press cue on a correct press rides cue.buzz_after /
cue.sound_after like everywhere else.
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
    first=<ok|wrong|none>;err=<ok|wrong_first|miss|device_drop>;rt=<ms>;
    ease=1 (biased draws only);streak=<n>;sup=<0|1>;
    pon=<0|1, prompt armed for this set>;pstep=<the word's rung on
    the delay ladder, len(prompt_steps) when off>;prompt=<0|1, it
    fired>;
    pat=<ms from spawn to the prompt, blank if none>;
    pclass=<unprompted_correct|unprompted_error|prompted_correct|
            prompted_error|no_response>;
    weak=<0|1, the target heard with a weak vowel>;
    pdue=<ms from spawn to the planned buzz, blank when it is off>;
    prof=<classic|6-9|10-12|13-15|16+|60+>;lex=<word|pseudo>;
    print=<0|1, the word printed before the choice>;
    replay=<0|1, the chunk replayed with R>;
    and in the sectioned sitting: sec=<review|pick|build>;
    fam=<the set's confusion family, mix, or blank in review>;
    flv=<the family's level for this set, 0-3>;
    fn=<how many of the family's foils made it on screen>;
    shown=<0|1, the answer shown after two wrong presses>
    (err=shown on those rows)

A speed trial's row is shorter:

    word;sec=speed;nsyll=<n>;expo=<ms the word was shown>;hand=<L|R>;
    opts=<lane>:<word>:<t|f>,...;tlane=<lane>;presses=...;
    first=<ok|wrong|none>;err=<ok|wrong_first|miss|device_drop>;
    rt=<ms from the four words>;prof=...;lex=word;sup=<0|1>

A probe set's row:

    word;sec=probe;item=<1-based place in the list>;pos=<k>;nsyll=<n>;
    syl=<chunk>;weak=<0|1>;held=<0|1, held out of training>;
    fam=<family>;near=<the near foil's kind>;hand=<L|R>;
    fall=<ms allowed>;opts=...;tlane=...;presses=...;
    first=<ok|wrong|none>;err=<ok|wrong_first|miss|device_drop>;
    rt=<ms, right answers>;at=<ms to the answer, right or wrong>;
    prof=...;lex=<word|pseudo>;sup=<0|1>;pv=<probe file version>

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
multisensory element); the prompt buzz is a response prompt, a rise
in unprompted accuracy can come from speed alone (PROMPT), and nothing
here shows the buzz taught reading. One reader's change across
sessions cannot be put down to the game either: untrained dyslexic
children improved as much as two game-trained groups (Luniewska et al.
2018), so a case reports what the reader did, not why. GraphoGame's effects depend on adult
support (McTigue 2020), so a session played alone is a different
condition and the `supervised` flag records which one it was. The hardware was built
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
from ...hardware.eeg_trigger import CODES as EEG_CODES, response_code
from .classic import PendingTrial
from .syllables_foils import (FAMILY_KIND, REVERSIBLE_LETTERS, Inventory,
                              build_option_set, draw_target_lane,
                              kinds_for_rung)
from .syllables_profiles import Profile, resolve as resolve_profile
from .syllables_words import (Word, all_words, load_pools, load_probe,
                              pool_syllable_lists, profile_words,
                              speech_stem, syllable_lists, words_for)

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)


def km_median(obs) -> float | None:
    """The Kaplan-Meier median of (seconds, answered) pairs: the first
    time the estimated share of sets still unanswered falls to one
    half, or None when it never does (Kaplan and Meier 1958). A set cut
    off by the buzz or the end of its fall is censored there: it says
    the answer would have come later, not when."""
    pts = sorted((float(s), bool(e)) for s, e in obs)
    n = len(pts)
    surv = 1.0
    i = 0
    while i < n:
        at = pts[i][0]
        j, died = i, 0
        while j < n and pts[j][0] == at:
            died += 1 if pts[j][1] else 0
            j += 1
        if died:
            surv *= 1.0 - died / (n - i)
            if surv <= 0.5:
                return at
        i = j
    return None


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
    # The prompt buzz: whether it was armed for this set (the word's
    # fade state), whether it fired, and which of the five outcome
    # classes the set falls in (see PROMPT in the module docstring).
    prompt_armed: bool = False
    prompted: bool = False
    pclass: str = ""
    # The sectioned sitting: which section the set belonged to, the
    # confusion family it taught and that family's level, and whether
    # it closed with the answer shown after two wrong presses.
    section: str = "pick"
    family: str | None = None
    family_level: int = 0
    shown: bool = False


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
    # 0.3 s until 29 September 2026, when play felt rushed.
    CORRECT_HOLD_S = 0.8
    # The corrective display on a missed set: the right tile glows on
    # its way out and the syllable is spoken. Delayed by construction
    # (it lands one to three seconds after any wrong press), which is
    # the feedback timing the docstring defends. Long enough to hear
    # the syllable out and see which tile it was.
    MISS_GLOW_S = 1.5
    # The model: silence after each spoken syllable before the next,
    # and after the syllables the whole word again (the blend), held
    # this long before the first set. Kept short between syllables on
    # purpose: pauses between the parts of a word make children forget
    # the first part when they blend (Gonzalez-Frey and Ehri 2021).
    MODEL_GAP_S = 0.5
    BLEND_HOLD_S = 1.2
    # A greyed tile drifts off over this long. Screen-side only.
    GREY_DRIFT_S = 0.5
    # Fixed streak milestones, in WORDS answered with every first
    # press right. Fixed and transparent rather than a variable-ratio
    # schedule, so the reward carries no reward-prediction-error
    # surprise into the EEG record.
    STREAK_MILESTONES = (3, 5, 8)
    # The latest the prompt may come, as a share of the fall, so it
    # always lands while the tiles are still there to press.
    PROMPT_CAP = 0.9
    # First presses found alone needed before the child's own speed
    # sets the floor, and how many recent sets the floor reads.
    PROMPT_FLOOR_MIN_N = 3
    PROMPT_FLOOR_WINDOW = 12

    # The prompt's outcome classes, in the order the analysis reads
    # them. "Unprompted correct" is the learning measure.
    PCLASSES = ("unprompted_correct", "unprompted_error",
                "prompted_correct", "prompted_error", "no_response")
    # Returns are extra words on top of the block's budget, so they
    # are capped or a child who misses a lot never reaches the end.
    MAX_RETURNS = 6
    # The floor on the fall window, whatever the config says. Below
    # this the task measures reading speed under time pressure, which
    # is the thing Aravena et al. (2013) showed dyslexic readers fail
    # for reasons that have nothing to do with this game. 2.5 s until
    # 29 September 2026.
    MIN_FALL_S = 4.0
    # The sectioned sitting (SECTIONS in the docstring). The card
    # between sections, the speed check's mask, its answer window and
    # the feedback hold after its answer, and its exposure staircase.
    SECTION_CARD_S = 3.0
    SPEED_MASK_S = 0.15
    SPEED_LIMIT_S = 4.0
    SPEED_FEEDBACK_S = 1.0
    EXPO_STEP_S = 0.08
    EXPO_MIN_S = 0.10
    EXPO_MAX_S = 1.50
    # A word's review share, and the build share of what is left.
    REVIEW_MAX = 4
    SPEED_MAX_LETTERS = 9
    FOCUS_WORDS = 3
    BUILD_SHARE = 0.3

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
                 set_gap_s: float = 1.0,
                 spawn_lockout_s: float = 0.25,
                 respeak_rungs: list[int] | None = None,
                 return_after: list[int] | None = None,
                 complete_s: float = 3.0,
                 homophone_foils: bool = False,
                 alternate_hands: bool = True,
                 supervised: bool = True,
                 speech: dict | None = None,
                 seed: int = 0,
                 demo_trials: int | None = None,
                 lanes_by_hand: dict[str, list[int]] | None = None,
                 prompt: bool = True,
                 prompt_steps: tuple[float, ...] = (0.6, 0.75, 0.9),
                 prompt_floor_margin_ms: float = 300.0,
                 prompt_at: float | None = None,
                 prompt_fade_after: int | None = None,
                 prompt_return_after: int | None = None,
                 age_band: str = "classic",
                 age=None,
                 sections: bool = False,
                 probe: bool = False,
                 probe_only: bool = False,
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
        # warmup_taps is accepted and ignored. The tapping warm-up is
        # gone: no other mode had one, and the timing baseline it took
        # was never part of what this matching task measures.
        self.warmup_total = 0
        # The prompt buzz (PROMPT in the docstring). prompt_steps is
        # the progressive delay ladder, each a share of the fall; a
        # word starts on the first rung and walks up it. Each rung is
        # clamped so the buzz lands after the spawn lockout and before
        # the tiles leave. prompt_at, prompt_fade_after and
        # prompt_return_after were the constant-delay settings and are
        # accepted and ignored, like warmup_taps.
        self.prompt_enabled = bool(prompt)
        steps = [min(self.PROMPT_CAP, max(0.3, float(x)))
                 for x in (prompt_steps or ())]
        self.prompt_steps = tuple(sorted(steps)) or (0.75,)
        self.prompt_floor_margin_s = max(
            0.0, float(prompt_floor_margin_ms) / 1000.0)
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
                            for v in (fall_s or [6.0, 6.0, 5.5, 5.5,
                                                 5.0, 5.0, 4.5, 4.5])]
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
        # Whether the set being built is on a syllable heard with a
        # weak vowel (set by _foil_kinds, read by _spawn_set).
        self._weak_set = False
        self.alternate_hands = bool(alternate_hands)
        self.supervised = bool(supervised)
        speech = dict(speech or {})
        self.speech_backend = str(speech.get("backend", "auto") or "auto")
        self.speech_dir = str(speech.get("dir", "assets/speech"))
        self.speech_volume = float(speech.get("volume", 1.0))
        self._speech_len: dict[str, float] = {}
        self._manifest_entries: dict | None = None
        self._manifest_meta: dict | None = None
        # Each word's syllable files as they sound in that word, and
        # which have a weak vowel (the manifest's syllable_map).
        self._manifest_syllables: dict = {}
        self.demo = demo_trials is not None
        if self.demo:
            # Test Mode: a handful of words and token breaks, so a
            # supervisor demo reaches Results inside a minute.
            self.words_total = max(2, int(demo_trials))
            self.break_s = min(self.break_s, 1.0)
        else:
            self.words_total = max(1, int(words_total))

        self.seed = int(seed)
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
        # gap -> attend -> model -> choose -> complete -> gap ... with
        # break between rounds and done at the end.
        self.phase = "gap"
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
        self._prompt_due: float | None = None   # when this set buzzes
        self._prompted_t: float | None = None   # when it did
        self._prompt_armed = False
        self._prompt_step = 0                   # the rung this set used
        # Per word: the rung of the delay ladder it is on; one past
        # the last rung is off.
        self._prompt_state: dict[str, dict] = {}
        # The child's recent sets as (seconds, answered alone): the
        # time of a first press made before any buzz, or the time the
        # set was cut off by the buzz or the end of its fall. The floor
        # under the delay is their Kaplan-Meier median (PROMPT).
        self._floor_obs: deque = deque(maxlen=self.PROMPT_FLOOR_WINDOW)
        self._prompt_plan_s: float | None = None

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
        # Sets the rig ate (a board drop over an unanswered set):
        # logged as device_drop, replayed, out of every number.
        self._voided_sets: list[SetRecord] = []
        self._set_voided = False
        # Whether the word in play was printed at ATTEND and MODEL,
        # fixed when the word starts: the rung can move inside the
        # word, and the row must say what was on screen.
        self._word_printed = True
        self._set_falls: list[float] = []
        self._records: list[WordRecord] = []
        self._band_trace: list[str] = [self.band]
        self._recent: deque[bool] = deque(maxlen=10)
        self._since_band_change = 0

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

        # ---- who the block is for (syllables_profiles.py) ----
        # classic is the design the study pre-registered and changes
        # nothing below; every other profile overrides what it names.
        self.profile: Profile = resolve_profile(age_band, age)
        prof = self.profile
        self._bank_bands = prof.pools == ("child",) and not prof.child_bands
        if prof.fall_table:
            self._fall_table = [max(prof.min_fall_s, float(v))
                                for v in prof.fall_table]
        if prof.respeak_rungs is not None:
            self.respeak_rungs = set(prof.respeak_rungs)
        if prof.prompt is not None:
            self.prompt_enabled = bool(prof.prompt)
        if prof.prompt_steps:
            self.prompt_steps = tuple(sorted(
                min(self.PROMPT_CAP, max(0.3, float(x)))
                for x in prof.prompt_steps))
        if not prof.returns:
            self.return_after = []
        if not self._bank_bands:
            self.inventory = Inventory(pool_syllable_lists())
        self._pseudo_bag: list[Word] = []
        self.sound_lead_s = max(0.0, prof.sound_lead_ms / 1000.0)
        self._speech_queue: list[tuple] = []
        self._replayed = False
        # The fall-time staircase (adults): the rung and the foil mix
        # stay put and only the fall moves.
        self.fall_mode = prof.staircase == "fall"
        self._fall_now = prof.fall_start_s
        self._fall_run = 0
        self._fall_dir = 0
        self._fall_trace: list[float] = [self._fall_now]
        self._fall_reversals: list[float] = []

        # The age's own block length where it is shorter than the
        # config's (6 to 9 plays 20 words; syllables_profiles.py).
        if prof.words_per_block and not self.demo:
            self.words_total = max(1, min(self.words_total,
                                          int(prof.words_per_block)))
        # ---- the fixed probe (PROBE in the docstring) ----
        # Its sets for this age, and the words it holds out of
        # training, which no draw below may hand the reader whether or
        # not this block plays the probe.
        self.probe_time_s, probe_items = load_probe(prof.pid)
        self._held_out: set[str] = {str(it["word"]) for it in probe_items
                                    if it.get("held_out")}
        on = bool(probe) and bool(sections) and prof.pid != "classic"
        self._probe_items: list[dict] = (list(probe_items) if on
                                         and self.probe_time_s > 0 else [])
        self.probe_only = bool(probe_only) and bool(self._probe_items)
        self.probe_item: dict | None = None
        self.probe_options: list[tuple[int, str, bool]] | None = None
        self._probe_kinds: dict[int, str] = {}
        self._probe_tlane: int | None = None
        self._probe_presses: list[Press] = []
        self._probe_done = 0
        self._probe_records: list[dict] = []
        self._probe_void = False
        self._probe_reuse = False

        # ---- the sectioned sitting (SECTIONS in the docstring) ----
        # Every age profile plays it when syllables.sections is on;
        # classic keeps the one-section block the study pre-registered.
        self.sectioned = bool(sections) and prof.pid != "classic"
        self.section_plan: list[tuple[str, int]] = (
            self._plan_sections() if self.sectioned else [])
        self.section_idx = 0
        self.section = (self.section_plan[0][0] if self.section_plan
                        else "pick")
        self._section_words = 0
        self._section_announced = False
        self.still_tiles = self.sectioned
        self.strip_closed = False
        self._slots_shown: list[bool] = []
        self._wrong_presses = 0
        self.family_levels = {f: 0 for f in prof.families}
        self._family_runs = {f: 0 for f in prof.families}
        self.family_mastered: set[str] = set()
        self._family_trace: list[str] = []
        self._set_family: str | None = None
        self._set_family_level = 0
        self._set_family_n = 0
        self._focus_family: str | None = None
        self._focus_words = 0
        self._focus_n = 0
        self._focus_last: dict[str, int] = {}
        # The speed check: the word flashed, the four words offered,
        # and the exposure staircase.
        self.speed_word: Word | None = None
        self.speed_options: list[tuple[int, str, bool]] | None = None
        self._speed_tlane: int | None = None
        self._speed_presses: list[Press] = []
        self._speed_done = 0
        self._speed_records: list[dict] = []
        self._speed_seen: set[str] = set()
        self._expo_s = max(self.EXPO_MIN_S, prof.speed_expo_ms / 1000.0)
        self._expo_run = 0
        self._expo_dir = 0
        self._expo_trace: list[float] = [self._expo_s]
        self._expo_reversals: list[float] = []
        self._speed_void = False
        self._speed_reuse = False
        self._expo_missed = False

    # ---- the sectioned sitting ---------------------------------------------
    def _plan_sections(self) -> list[tuple[str, int]]:
        """The sitting's sections and their sizes, in the order the
        programs that worked used (syllables-task-design.md, Section
        6.1): review, hear and pick, build, then the speed check. The
        words of the block are shared out: up to four to review, 30
        percent of the rest to build, the others to pick. Speed trials
        come on top, for the profiles that have them, and the fixed
        probe, when it plays, comes first and on top of the words; with
        probe_only it is the whole sitting."""
        probe = ([("probe", 2 if self.demo else len(self._probe_items))]
                 if self._probe_items else [])
        if self.probe_only:
            return probe
        total = self.words_total
        review = min(self.REVIEW_MAX, total // 6)
        rest = total - review
        build = int(round(rest * self.BUILD_SHARE)) if rest >= 3 else 0
        pick = rest - build
        plan = [("review", review), ("pick", pick), ("build", build)]
        if self.profile.speed_trials:
            plan.append(("speed", 2 if self.demo
                         else int(self.profile.speed_trials)))
        return [(name, n) for name, n in probe + plan if n > 0]

    def _section_quota(self) -> int:
        if not self.section_plan:
            return 0
        idx = min(self.section_idx, len(self.section_plan) - 1)
        return int(self.section_plan[idx][1])

    def _advance_section(self, now: float) -> None:
        """A section is done: a sticker for finishing it, then the next
        section's card, or nothing when it was the last (the block ends
        at the next word boundary). The review's warm-up words and hear
        and pick are one task to the player, so the review moves into
        hear and pick with no sticker and no card (Basil, 2 October
        2026: the two looked like one part shown twice); the rows still
        say which words were the review's."""
        raw = getattr(self.engine, "raw_logger", None)
        nxt = (self.section_plan[self.section_idx + 1][0]
               if self.section_idx + 1 < len(self.section_plan) else None)
        joined = self.section == "review" and nxt == "pick"
        if not joined:
            self._stickers += 1
            self.sticker_flash_t = now
            if raw:
                raw.queue_event("syllables_sticker",
                                detail=f"section={self.section}",
                                hand=self.engine.hand_mode)
        self.section_idx += 1
        if self.section_idx >= len(self.section_plan):
            return
        self.section = self.section_plan[self.section_idx][0]
        self._section_words = 0
        if not joined:
            self._enter_phase("section", now)
        if raw:
            raw.queue_event("syllables_section",
                            detail=f"section={self.section}",
                            hand=self.engine.hand_mode)

    def _weak_now(self) -> bool:
        """Whether the syllable in play is heard with a weak vowel, by
        the rule _foil_kinds states, kept for the set being built."""
        weak = (self.heard_weak(self.pos) if self.word is not None
                else None)
        if weak is None:
            weak = (self.profile.guard_unstressed_vowels
                    and self.word is not None
                    and self.pos != self.word.stress
                    and not self.chunks_spelt(
                        self.word.syllables[self.pos]))
        self._weak_set = bool(weak)
        return bool(weak)

    def _pick_family(self, weak: bool) -> str | None:
        """The confusion family this set teaches: one the syllable can
        show and the reader has not mastered, at the lowest level
        reached, ties at random. None once every family that fits is
        mastered, when the foils mix."""
        chunk = self.word.syllables[self.pos] if self.word else ""
        fams = []
        for fam in self.profile.families:
            if fam in self.family_mastered:
                continue
            if fam == "vowel" and weak:
                continue
            if fam == "reversal" and not (set(chunk) & REVERSIBLE_LETTERS):
                continue
            # Building already tests order: the word's other syllables
            # sit in the lanes on every slot.
            if fam == "order" and (self.n_syll < 2
                                   or self.section == "build"):
                continue
            fams.append(fam)
        if not fams:
            return None
        if self._focus_family in fams:
            return self._focus_family
        low = min(self.family_levels[f] for f in fams)
        return self.rng.choice([f for f in fams
                                if self.family_levels[f] == low])

    def _advance_focus(self) -> None:
        """The family the next words teach. Each family gets a short
        block of FOCUS_WORDS words, then the next open family takes
        over, lowest level first and the one taught longest ago on a
        tie: a new contrast blocked for a few words, then mixed
        (syllables-task-design.md, Sections 6.1 and 6.3). A syllable
        that cannot show the focus family uses another open one."""
        fam = self._focus_family
        if (fam is not None and fam not in self.family_mastered
                and self._focus_words < self.FOCUS_WORDS):
            self._focus_words += 1
            return
        open_fams = [f for f in self.profile.families
                     if f not in self.family_mastered]
        if not open_fams:
            self._focus_family = None
            return
        low = min(self.family_levels[f] for f in open_fams)
        cands = [f for f in open_fams if self.family_levels[f] == low]
        if len(cands) > 1 and fam in cands:
            cands.remove(fam)
        oldest = min(self._focus_last.get(f, -1) for f in cands)
        pick = self.rng.choice([f for f in cands
                                if self._focus_last.get(f, -1) == oldest])
        self._focus_n += 1
        self._focus_family = pick
        self._focus_words = 1
        self._focus_last[pick] = self._focus_n

    def _mixed_kinds(self) -> tuple[str, ...]:
        prof = self.profile
        if prof.foil_weights:
            names = sorted(prof.foil_weights)
            return tuple(self.rng.choices(
                names, weights=[prof.foil_weights[n] for n in names], k=3))
        return tuple(kinds_for_rung(self.rung_max, self.homophone_foils))

    def _section_kinds(self) -> tuple[str, ...]:
        """The three foil kinds of a set in the sectioned sitting.
        Review: unrelated chunks only, a warm-up solved at a glance.
        Pick: the set's family at its level, one foil of it per level
        and unrelated chunks for the rest, so a new contrast starts
        easy. Build: one of the word's own syllables always, then the
        family's foils. With every family mastered the foils mix."""
        weak = self._weak_now()
        if self.section == "review":
            self._set_family, self._set_family_level = None, 0
            return ("F1", "F1", "F1")
        fam = self._pick_family(weak)
        if fam is None:
            self._set_family, self._set_family_level = "mix", 0
            kinds = self._mixed_kinds()
            if self.section == "build":
                kinds = ("F6",) + tuple(k for k in kinds
                                        if k != "F6")[:2]
                kinds = kinds + ("F1",) * (3 - len(kinds))
        else:
            level = self.family_levels[fam]
            self._set_family, self._set_family_level = fam, level
            kind = FAMILY_KIND[fam]
            if self.section == "build":
                n = min(level, 2)
                kinds = ("F6",) + (kind,) * n + ("F1",) * (2 - n)
            else:
                kinds = (kind,) * level + ("F1",) * (3 - level)
        if weak:
            kinds = tuple("F7" if k == "F3" else k for k in kinds)
        return kinds

    def _move_family(self, first_ok: bool) -> None:
        """The per-family ladder: three unaided right first presses on
        a family's sets raise it one level (one more of its foils in a
        set), and at level 3 mark it mastered; an error takes it back a
        level. A set whose family foil never made it on screen (the
        generator had nothing legal) moves nothing."""
        fam = self._set_family
        if fam is None or fam == "mix" or fam not in self.family_levels:
            return
        level = self.family_levels[fam]
        if level >= 1 and self._set_family_n == 0:
            return
        old = (level, fam in self.family_mastered)
        if first_ok:
            self._family_runs[fam] += 1
            if self._family_runs[fam] >= 3:
                self._family_runs[fam] = 0
                if level < 3:
                    self.family_levels[fam] = level + 1
                else:
                    self.family_mastered.add(fam)
        else:
            self._family_runs[fam] = 0
            if level > 0:
                self.family_levels[fam] = level - 1
        new = (self.family_levels[fam], fam in self.family_mastered)
        if new == old:
            return
        self._family_trace.append(
            f"{fam}:{new[0]}{'m' if new[1] else ''}")
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "family_change",
                detail=(f"family={fam};level={new[0]};"
                        f"mastered={1 if new[1] else 0};"
                        f"set_idx={len(self._sets)}"),
                hand=self.word_hand)

    def _draw_review_word(self) -> Word:
        """A review word: the shortest words the block's material
        has, the warm-up the section is for."""
        if self._bank_bands:
            pool = [w for w in words_for("A", bilateral=self.bilateral)
                    if w.word not in self._retired
                    and w.word not in self._held_out]
        else:
            real, _pseudo = profile_words(self.profile, self.band)
            pool = [w for w in real if w.word not in self._retired
                    and w.word not in self._held_out]
        if not pool:
            return self._draw_word()
        short = min(w.n_syll for w in pool)
        pool = [w for w in pool if w.n_syll == short]
        fresh = [w for w in pool if w.word not in self._seen_words]
        return self.rng.choice(fresh or pool)

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
        """How long this rung's tiles are on screen, or the adult
        staircase's current fall."""
        if getattr(self, "fall_mode", False):
            return self._fall_now
        idx = max(0, min(len(self._fall_table) - 1, self.rung - 1))
        return self._fall_table[idx]

    @property
    def blending(self) -> bool:
        """The model's last step: every part shown and the whole word
        said again."""
        return (self.phase == "model" and self.n_syll > 0
                and self._model_idx >= self.n_syll)

    @property
    def show_print(self) -> bool:
        """Whether the word and its chunks are printed before the
        choice (ATTEND and MODEL). Always in classic; faded above the
        profile's print rung otherwise, never for adults, who could
        answer from the print without listening at all."""
        return self.rung <= self.profile.print_rungs

    @property
    def current_timeout_s(self) -> float:
        """The set's response window, which is the RT censoring limit
        the engine writes into the trial row."""
        if self.phase == "speed":
            return self.SPEED_LIMIT_S
        if self.phase == "probe":
            return self.probe_time_s
        return self.fall_s

    def eeg_stim_code(self) -> int | None:
        """The choice band: 50 for a set on a first attempt, 51 for a
        set on a returned word, 53 for the four words of a speed
        trial. None everywhere else, so the model keeps the ordinary
        30-band cue-condition code."""
        from ...hardware import eeg_trigger
        if self.phase == "speed":
            return eeg_trigger.CODES["stim_choice_speed"]
        if self.phase == "probe":
            # A probe set is a choice set on a first attempt.
            return eeg_trigger.CODES["stim_choice_set"]
        if self.phase != "choose":
            return None
        return eeg_trigger.CODES[
            "stim_choice_set_return" if self.ret else "stim_choice_set"]

    # ---- material ---------------------------------------------------------
    def _draw_word(self) -> Word:
        """Shuffle-bag draw over the current band pool, so a round
        cannot repeat one word while another never comes up. The bag
        rebuilds when it empties or after a band change. An age
        profile past the child bank draws its own pools instead, a
        made-up word at the profile's share."""
        if not self._bank_bands:
            return self._draw_profile_word()
        if not self._bag:
            self._bag = [w for w in words_for(self.band,
                                              bilateral=self.bilateral)
                         if w.word not in self._retired
                         and w.word not in self._held_out]
            if not self._bag:
                # A band small enough to retire whole: better to
                # repeat than to stall the block. The probe's held-out
                # words stay out even then.
                self._bag = ([w for w in words_for(
                    self.band, bilateral=self.bilateral)
                    if w.word not in self._held_out]
                    or list(words_for(self.band,
                                      bilateral=self.bilateral)))
            self.rng.shuffle(self._bag)
        return self._bag.pop()

    def _draw_profile_word(self) -> Word:
        real, pseudo = profile_words(self.profile, self.band)
        use_pseudo = bool(pseudo) and (
            self.rng.random() < self.profile.pseudo_share)
        bag, source = ((self._pseudo_bag, pseudo) if use_pseudo
                       else (self._bag, real))
        if not bag:
            bag.extend(w for w in source if w.word not in self._retired
                       and w.word not in self._held_out)
            if not bag:
                bag.extend(w for w in source
                           if w.word not in self._held_out)
            if not bag:
                bag.extend(source)
            self.rng.shuffle(bag)
        return bag.pop()

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
                if w.n_syll == best and w.word not in self._retired
                and w.word not in self._held_out]
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
                     "_set_close_t", "_correct_t", "_glow_t", "lift_t",
                     "_prompt_due", "_prompted_t"):
            v = getattr(self, attr)
            if v is not None:
                setattr(self, attr, v + pause_dur)
        # A pause mid-word breaks the presentation the trial rests on
        # (the word was spoken and modelled before the pause, the tiles
        # fall after it), so the fair move is to restart the word from
        # ATTEND rather than salvage half of it. Not on the COMPLETE
        # card: every set is scored and logged by then, and a restart
        # there played the word again and logged each set twice.
        if self.phase in ("attend", "model", "choose"):
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
        elif self.phase in ("flash", "mask") or (
                self.phase == "speed" and self.active is not None):
            # A speed trial cut by a pause is flashed again: the
            # exposure is the measure, and a pause inside it spoils it.
            raw = getattr(self.engine, "raw_logger", None)
            if raw and self.phase == "speed":
                raw.queue_event(
                    "trial_restart",
                    detail=(f"old_trial_id={self.trial_counter};"
                            f"new_trial_id={self.trial_counter + 1};"
                            f"phase=speed"),
                    hand=self.engine.hand_mode)
            self.active = None
            self.speed_options = None
            self._begin_speed_trial(time.perf_counter(), reuse=True)
        elif self.phase == "probe_listen" or (
                self.phase == "probe" and self.active is not None):
            # A probe set cut by a pause is played again from its word:
            # the probe is the same for every session only if every
            # set is heard and answered the same way.
            raw = getattr(self.engine, "raw_logger", None)
            if raw and self.phase == "probe":
                raw.queue_event(
                    "trial_restart",
                    detail=(f"old_trial_id={self.trial_counter};"
                            f"new_trial_id={self.trial_counter + 1};"
                            f"phase=probe"),
                    hand=self.engine.hand_mode)
            self.active = None
            self.probe_options = None
            self._begin_probe_trial(time.perf_counter(), reuse=True)

    def handle_event(self, e: pygame.event.Event) -> None:
        if (e.type == pygame.KEYDOWN and e.key == pygame.K_r
                and self.profile.pid != "classic"):
            self.replay()
            return
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

    def replay(self) -> bool:
        """Say this set's chunk once more (R on the keyboard, the
        supervisor's key for a child). Once per set, logged, and the
        set is kept out of the adult threshold. While building, the
        whole word is said instead: the chunk is the answer."""
        if (self.phase != "choose" or self.option_set is None
                or self._replayed or self._set_close_t is not None):
            return False
        self._replayed = True
        if self.sectioned and self.section == "build":
            self._speak_word()
        else:
            self._speak_syllable(self.pos)
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event("replay", t_perf=time.perf_counter(),
                            detail=f"trial_id={self.trial_counter}",
                            hand=self.word_hand)
        return True

    # ---- main tick ---------------------------------------------------------
    def update(self, dt: float) -> None:
        self._tick(time.perf_counter())

    def _tick(self, now: float) -> None:
        if self._t0 is None:
            self._t0 = now
            self._enter_phase(self.phase, now)
        self._reap_say()
        self._flush_speech(now)
        while self._presses:
            self._handle_press(self._presses.popleft(), now)
        if self.phase == "done":
            return
        if self.phase == "break":
            if self._phase_until is not None and now >= self._phase_until:
                self._begin_word(now)
        elif self.phase == "gap":
            if self._phase_until is None or now >= self._phase_until:
                self._begin_word(now)
        elif self.phase == "attend":
            if now >= self._phase_until:
                # Adults hear the word and go straight to the choice:
                # a modelled, printed chunk is an answer to copy. A
                # word to build is heard whole and never modelled: the
                # parts are the answer.
                model = self.profile.model and not (
                    self.sectioned and self.section == "build")
                self._enter_phase("model" if model else "choose", now)
        elif self.phase == "model":
            self._update_model(now)
        elif self.phase == "choose":
            self._update_choose(now)
        elif self.phase == "complete":
            if self._phase_until is not None and now >= self._phase_until:
                self._after_word(now)
        elif self.phase == "section":
            if self._phase_until is not None and now >= self._phase_until:
                self._begin_word(now)
        elif self.phase == "flash":
            if now >= self._phase_until:
                self._enter_phase("mask", now)
        elif self.phase == "mask":
            if now >= self._phase_until:
                self._spawn_speed(now)
        elif self.phase == "speed":
            self._update_speed(now)
        elif self.phase == "probe_listen":
            if self._phase_until is not None and now >= self._phase_until:
                self._spawn_probe(now)
        elif self.phase == "probe":
            self._update_probe(now)

    # ---- word flow ---------------------------------------------------------
    def _due_return(self) -> dict | None:
        """The parked word whose wait is up, if any. Returns are
        played before fresh draws so the spacing is exact."""
        for entry in self._parked:
            if entry["remaining"] <= 0:
                return entry
        return None

    def _begin_word(self, now: float, reuse_word: bool = False) -> None:
        if self.sectioned and not self._section_announced:
            # The first section gets its card too, before its first
            # word.
            self._section_announced = True
            self._enter_phase("section", now)
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event("syllables_section",
                                detail=f"section={self.section}",
                                hand=self.engine.hand_mode)
            return
        if self.sectioned and self.section == "speed":
            self._begin_speed_trial(now)
            return
        if self.sectioned and self.section == "probe":
            self._begin_probe_trial(now)
            return
        # Returns over the cap are let go BEFORE the completion check,
        # or a block whose every word missed would keep drawing fresh
        # words for ever: the due entry blocked the "block finished"
        # branch and then fell through to a fresh draw. In the
        # sectioned sitting a word returns only to hear and pick or to
        # build, never to the review.
        entry = (self._due_return()
                 if not self.sectioned or self.section in ("pick", "build")
                 else None)
        while entry is not None and self._returns_started >= self.MAX_RETURNS:
            self._parked.remove(entry)
            self._retire(entry, "return_cap")
            entry = self._due_return()
        # Completion and the session cap are checked at word
        # boundaries so the block never ends mid-word. A restart of
        # the word in play (a pause) is not a boundary: a return
        # playing past the word budget would otherwise end the block
        # from inside the resume, half played and unrecorded.
        restart = reuse_word and self.word is not None
        if not restart:
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
                elif self.sectioned and self.section == "review":
                    self.word = self._draw_review_word()
                    self._ease_word = False
                else:
                    self.word = self._draw_word()
                    self._ease_word = False
                self.ret = 0
                self.word_hand = self._next_hand()
                for parked in self._parked:
                    parked["remaining"] -= 1
        if self.word is not None:
            self._seen_words.add(self.word.word)
        if (self.sectioned and not restart
                and self.section in ("pick", "build")):
            self._advance_focus()
        self.band_celebrate = None
        self.filled = [None] * self.n_syll
        self.filled_lanes = [None] * self.n_syll
        self.pos = 0
        self.option_set = None
        self.active = None
        self._set_presses = []
        self._dead_lanes = set()
        self._last_tap_t = {}
        self.strip_closed = False
        self._slots_shown = [False] * self.n_syll
        # Speech still queued from the word before (a skipped
        # read-back) must not play over this one.
        self._speech_queue = []
        # A word to build is heard, not shown, past a young child's
        # first rungs: its spelling is the answer.
        self._word_printed = self.show_print and not (
            self.sectioned and self.section == "build"
            and self.profile.pid != "6-9")
        self._enter_phase("attend", now)
        self._speak_word()

    def _enter_phase(self, phase: str, now: float) -> None:
        self.phase = phase
        self._phase_t0 = now
        self._phase_until = None
        self.clear_wait()
        if phase != "model":
            self.model_hand = None
        if phase == "attend":
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
        elif phase == "section":
            held = self._card_holds()
            self._phase_until = None if held else now + self.SECTION_CARD_S
            self.arm_wait("stage", now + self.SECTION_CARD_S,
                          self._skip_to_next_word, started_at=now,
                          label="Start", hold_when_due=held)
        elif phase == "flash":
            self._phase_until = now + self._expo_s
        elif phase == "mask":
            self._phase_until = now + self.SPEED_MASK_S

    def _card_holds(self) -> bool:
        """The card after the probe waits for Start instead of leaving
        after SECTION_CARD_S. Only a case reader plays the probe, with
        a supervisor beside them, and a baseline session ends at this
        card with two presses of Esc: a card that left after 3 s could
        start training words in a baseline session."""
        i = self.section_idx
        return (0 < i < len(self.section_plan)
                and self.section_plan[i - 1][0] == "probe")

    def _skip_to_next_word(self, now: float) -> None:
        self._begin_word(now)

    def _skip_complete(self, now: float) -> None:
        self._after_word(now)

    def _update_model(self, now: float) -> None:
        """Light each slot in turn at the beat and speak its syllable,
        then show them all and say the whole word (the blend).

        No buzz. The model used to run a roll across all four fingers
        for every syllable, which players felt as every motor going
        off at the start of each word for no reason. The one buzz this
        mode now plays is the prompt on the right finger late in a set
        (PROMPT in the docstring), where it helps.

        Beat deadlines are ABSOLUTE: each syllable is due one interval
        after the previous DEADLINE, not one after the frame that
        noticed it, so the frame delay cannot accumulate across a
        word."""
        due = self._model_next_t
        if due is None or now < due:
            return
        self._model_idx += 1
        if self._model_idx == self.n_syll:
            # The blend: every slot shows its part and the whole word
            # is said again, the last step of graphosyllabic analysis
            # (Bhattacharya and Ehri 2004), with the same print lead
            # as each syllable.
            self._speak_syllable_after(None, now)
            self._model_next_t = (max(now, due) + self.sound_lead_s
                                  + self.blend_s())
            return
        if self._model_idx > self.n_syll:
            self._model_idx = -1
            self._model_next_t = None
            self._enter_phase("choose", due)
            return
        beat = self.model_ioi_s(self._model_idx)
        self._model_next_t = due + beat
        if self._model_next_t <= now:
            # The loop stalled past a whole beat (alt-tab, IO).
            # Re-anchor rather than burst-fire catch-up syllables.
            self._model_next_t = now + beat
        self.model_hand = self.word_hand
        self._speak_syllable_after(self._model_idx, now)
        # Still goes through the stimulus path, buzz off, so the
        # 30-band model byte and the slot light keep their timing. The
        # trial id is the word's next set id (the counter moves at the
        # spawn), which ties the byte to the word it belongs to.
        self.engine.on_stim_multi(self.active_lanes(),
                                  self.trial_counter + 1, now, buzz=False)

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
        if self._prompt_due is not None and now >= self._prompt_due:
            self._fire_prompt(now)
        if self._exit_t is not None and now >= self._exit_t:
            self._miss_set(now)

    def _fire_prompt(self, now: float) -> None:
        """Buzz the right finger once: the set is still unanswered at
        its prompt delay. Nothing on screen changes. The set only
        counts as prompted when the buzz went out: a keyboard rig, the
        buzzer channel switched off or a failed STIM prompted nobody,
        and the row must not say it did."""
        self._prompt_due = None
        if self.option_set is None:
            return
        lane = self.option_set.target_lane
        fire = getattr(self.engine, "on_prompt_buzz", None)
        delivered = fire(lane, self.trial_counter, now) if callable(fire) \
            else None
        if delivered:
            self._prompted_t = now

    def _word_prompt_step(self) -> int:
        if self.word is None:
            return 0
        st = self._prompt_state.get(self.word.word)
        return 0 if st is None else int(st["step"])

    def _word_prompt_on(self) -> bool:
        if not self.prompt_enabled or self.word is None:
            return False
        return self._word_prompt_step() < len(self.prompt_steps)

    def _prompt_delay_s(self) -> float:
        """Seconds from spawn to the buzz for the set in play: the
        word's rung of the ladder, never earlier than this child's own
        median time to a first press plus a margin, never later than
        PROMPT_CAP of the fall. The median is a Kaplan-Meier estimate
        over the recent sets (PROMPT in the docstring); when fewer than
        half were answered alone it never reaches one half, and the
        longest time seen, a lower bound on it, stands in."""
        step = min(self._word_prompt_step(), len(self.prompt_steps) - 1)
        delay = self.prompt_steps[step] * self.fall_s
        floor = self.prompt_floor_s()
        if floor is not None:
            delay = max(delay, floor + self.prompt_floor_margin_s)
        return min(delay, self.PROMPT_CAP * self.fall_s)

    def prompt_floor_s(self) -> float | None:
        """The child's median time to a first press found alone, from
        the recent sets, or None before PROMPT_FLOOR_MIN_N of them."""
        obs = list(self._floor_obs)
        if sum(1 for _s, e in obs if e) < self.PROMPT_FLOOR_MIN_N:
            return None
        median = km_median(obs)
        return median if median is not None else max(s for s, _e in obs)

    def _latency_obs(self) -> tuple[float, bool] | None:
        """(seconds, answered alone) for the set in play: the time of
        its first press when that came before any buzz, else the time
        the buzz or the end of the fall cut it off."""
        if self._spawn_t is None:
            return None
        first = next((p for p in self._set_presses
                      if p.kind not in (KIND_ANTICIP, KIND_OFF_HAND)), None)
        pt = self._prompted_t
        if first is not None and (pt is None or first.t_perf < pt):
            return (max(0.0, first.t_perf - self._spawn_t), True)
        if pt is not None:
            return (max(0.0, pt - self._spawn_t), False)
        return (self.fall_s, False)

    def _classify_prompt(self) -> tuple[str, bool]:
        """(outcome class, prompted) for the set in play. Prompted
        means the buzz came before the child's first real press, so
        that press may have been helped by it."""
        first = None
        for p in self._set_presses:
            if p.kind in (KIND_ANTICIP, KIND_OFF_HAND):
                continue
            first = p
            break
        pt = self._prompted_t
        prompted = pt is not None and (first is None or first.t_perf >= pt)
        if first is None:
            return "no_response", prompted
        ok = first.kind == KIND_CORRECT
        if prompted:
            return ("prompted_correct" if ok else "prompted_error"), True
        return ("unprompted_correct" if ok else "unprompted_error"), False

    def _update_prompt_fade(self, pclass: str, missed: bool) -> None:
        """Walk the word along the delay ladder: a set answered right
        before the buzz moves it one rung later (past the last rung
        the word plays with no prompt), a wrong first press before the
        buzz or a set that left the screen moves it one rung earlier,
        and an answer that needed the buzz leaves it where it is."""
        if self.word is None:
            return
        st = self._prompt_state.setdefault(self.word.word, {"step": 0})
        off = len(self.prompt_steps)
        if missed or pclass == "unprompted_error":
            st["step"] = max(0, min(int(st["step"]), off) - 1)
        elif pclass == "unprompted_correct":
            st["step"] = min(off, int(st["step"]) + 1)

    def _spawn_set(self, now: float) -> None:
        """Four tiles for syllable `self.pos`: build them, open the
        trial, and mark the onset.

        The marker call goes through the engine's ordinary cue path so
        the force window, the timeout and the EEG byte all arm the way
        they do everywhere else, with `silent_stim` set for the length
        of the call so nothing is heard, felt or highlighted. A cue on
        the target lane here would hand the child the answer."""
        lanes = self.active_lanes()
        kinds = (self._section_kinds() if self.sectioned
                 else self._foil_kinds())
        self.option_set = build_option_set(
            self.word, self.pos, self.rung, self.rng, self.inventory,
            lanes, self._lane_targets, self._recent_target_lanes,
            homophone_foils=self.homophone_foils, kinds=kinds,
            avoid=(frozenset({"F3"}) if self._weak_set
                   else frozenset()))
        self._replayed = False
        self._set_voided = False
        self._wrong_presses = 0
        fkind = FAMILY_KIND.get(self._set_family or "")
        self._set_family_n = (sum(1 for o in self.option_set.options
                                  if o.kind == fkind) if fkind else 0)
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
        self._prompted_t = None
        self._prompt_armed = self._word_prompt_on()
        self._prompt_step = self._word_prompt_step()
        self._prompt_plan_s = (self._prompt_delay_s()
                               if self._prompt_armed else None)
        self._prompt_due = (now + self._prompt_plan_s
                            if self._prompt_plan_s is not None else None)
        self._next_spawn_t = None
        self._set_close_t = None
        self._set_presses = []
        self._dead_lanes = set()
        self._first_kind = None
        self._correct_t = None
        self._glow_t = None
        self.lift_t = None
        self._last_tap_t = {}
        # Never while building: the syllable spoken is the answer.
        self._respeak = (self.rung in self.respeak_rungs
                         and not (self.sectioned
                                  and self.section == "build"))
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
            self._speak_syllable_after(self.pos, now)

    def _foil_kinds(self) -> tuple[str, ...] | None:
        """The three foil kinds for this set, or None for the rung
        schedule unchanged (classic). An age profile draws from its
        foil shares, far foils only at rung 1 for teens.

        A vowel foil becomes a coda foil where the syllable is HEARD
        with a weak vowel, since ter, tar and tur all say "tuh" and
        only spelling knowledge could pick one: in every profile when
        the syllable_map says the syllable is weak in its word, and,
        for a word the map does not cover, on any unstressed syllable
        in the profiles that guard it while its chunk audio is not
        spelt."""
        prof = self.profile
        weak = (self.heard_weak(self.pos) if self.word is not None
                else None)
        self._weak_set = bool(weak)
        if prof.pid == "classic" and not weak:
            return None
        if (prof.pid != "classic" and prof.foil_weights
                and not (prof.far_foils_rung1_only and self.rung == 1)):
            names = sorted(prof.foil_weights)
            kinds = tuple(self.rng.choices(
                names, weights=[prof.foil_weights[n] for n in names], k=3))
        else:
            kinds = kinds_for_rung(self.rung, self.homophone_foils)
        if weak is None:
            weak = (prof.guard_unstressed_vowels and self.word is not None
                    and self.pos != self.word.stress
                    and not self.chunks_spelt(self.word.syllables[self.pos]))
        # Kept for the set being built: the fallback chain and every
        # kind must stay clear of a vowel swap too (_spawn_set).
        self._weak_set = bool(weak)
        if weak:
            kinds = tuple("F7" if k == "F3" else k for k in kinds)
        return kinds

    def _handle_press(self, ev: PressEvent, now: float) -> None:
        if self.phase == "speed":
            self._handle_speed_press(ev, now)
            return
        if self.phase == "probe":
            self._handle_probe_press(ev, now)
            return
        if (self.phase != "choose" or self.option_set is None
                or self._set_close_t is not None):
            # No penalty anywhere in this mode: a child fidgeting
            # between words, or after a set is scored and fading out,
            # must not lose anything for it. The EEG record still
            # books the press as idle (131, no set open), the
            # artefact bookkeeping the lab document promises for
            # every press.
            self._eeg_press_byte(EEG_CODES["resp_idle"], ev)
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
            self._prompt_due = None
            self._score_set(now, ev.t_perf)
            self._set_close_t = ev.t_perf + self.CORRECT_HOLD_S
        elif kind == KIND_WRONG:
            if self._first_kind is None:
                self._first_kind = "wrong"
            self._dead_lanes.add(ev.lane)
            if self.active is not None:
                self.active.incorrect_presses.append((ev.lane, ev.t_perf))
                self.engine.eeg_wrong_press(self.active.incorrect_presses)
            # The sectioned sitting allows one more try, then shows the
            # answer: a child who guesses through all four learns
            # nothing a told answer would not teach (Butler, Karpicke
            # and Roediger 2007), and the right answer seen soon after
            # an error keeps a lure from sticking (Marsh, Fazio and
            # Goswick 2012).
            if self.sectioned:
                self._wrong_presses += 1
                if self._wrong_presses >= 2:
                    self._show_answer(max(now, ev.t_perf), shown=True)
        elif kind == KIND_ANTICIP:
            # Inside the spawn lockout: ignored by the score, but a
            # press all the same, marked as a false start at its own
            # time (120 + lane) so the record never says "no press".
            code = response_code("anticipation", ev.lane)
            if code is not None:
                self._eeg_press_byte(code, ev)

    def _eeg_press_byte(self, code: int, ev: PressEvent) -> None:
        send = getattr(self.engine, "_eeg_send", None)
        if callable(send):
            send(int(code), lane=ev.lane, t_event=ev.t_perf)

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
        if self.sectioned:
            self._show_answer(now, shown=False)
            return
        self._glow_t = now
        self._score_set(now, None)
        self._speak_syllable(self.pos)
        self._set_close_t = now + self.MISS_GLOW_S

    def _show_answer(self, now: float, shown: bool) -> None:
        """The sectioned sitting's answer display, after two wrong
        presses (shown) or a set that ran out of time: the right tile
        glows, its syllable is heard, and it fills its slot marked as
        shown, not found, so the word still ends whole. The word comes
        back later."""
        if self.option_set is None:
            return
        target = self.option_set.target
        self._glow_t = now
        self._prompt_due = None
        self._score_set(now, None, shown=shown)
        if 0 <= self.pos < len(self._slots_shown) and not self._set_voided:
            self.filled[self.pos] = target
            self.filled_lanes[self.pos] = None
            self._slots_shown[self.pos] = True
        self._speak_syllable(self.pos)
        self._set_close_t = now + self.MISS_GLOW_S

    def _close_set(self, now: float) -> None:
        missed = self._first_kind != "ok" and self._correct_t is None
        self.option_set = None
        self._spawn_t = None
        self._exit_t = None
        self._set_close_t = None
        self._prompt_due = None
        if self._set_voided:
            # The rig ate the set: the same chunk again with fresh
            # tiles, nothing booked against the word.
            self._set_voided = False
            self._next_spawn_t = now + self.set_gap_s
            return
        if self.sectioned:
            # The word carries on through a shown answer, so it always
            # ends whole and is read back.
            self.pos += 1
            if self.pos >= self.n_syll:
                self._enter_phase("complete", now)
                self._read_whole(now)
                return
            self._next_spawn_t = now + self.set_gap_s
            return
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
    def _score_set(self, now: float, correct_t: float | None,
                   shown: bool = False) -> None:
        """Close one option set: label it, log its row, move the
        staircase. Called once per set, either at the correct press, at
        the exit line, or (sectioned) when two wrong presses show the
        answer."""
        trial = self.active
        if trial is None or self.word is None or self.option_set is None:
            return
        self.active = None
        first = self._first_kind or "none"
        if correct_t is not None:
            err = "ok" if first == "ok" else "wrong_first"
        elif shown:
            err = "shown"
        else:
            err = "miss"
        # A set that left the screen unanswered while this hand's
        # board was away is the rig's, not the reader's: the test the
        # engine's log_trial runs, taken here as well so the mode
        # books nothing on it (no miss, no park, no prompt step, no
        # staircase move) and replays the chunk once the set fades.
        voided = (err == "miss" and not trial.incorrect_presses
                  and self._rig_void(now))
        rt_ms = ((correct_t - self._spawn_t) * 1000.0
                 if correct_t is not None and self._spawn_t is not None
                 else None)
        pclass, prompted = self._classify_prompt()
        if voided:
            err, pclass = "device_drop", "void"
        if err == "ok" and not prompted:
            outcome = TrialResult(label="Great",
                                  points=self.score_cfg.great_points,
                                  rt_ms=rt_ms)
        elif err == "ok":
            # Right, with the buzz's help: counted and scored, a step
            # under an answer found alone.
            outcome = TrialResult(label="Good",
                                  points=self.score_cfg.good_points,
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
            prompt_armed=self._prompt_armed,
            prompted=self._prompted_t is not None,
            pclass=pclass,
            section=self.section if self.sectioned else "pick",
            family=self._set_family if self.sectioned else None,
            family_level=self._set_family_level if self.sectioned else 0,
            shown=(err == "shown"),
        )
        if voided:
            self._voided_sets.append(rec)
        else:
            self._sets.append(rec)
            # The adult threshold reads the fall of every set the
            # reader answered on one hearing: a replayed set stays
            # out, as replay() promises. In the sectioned sitting it
            # reads hear-and-pick sets only, the sets the fall moves
            # on (_move_rung).
            if not self._replayed and (not self.sectioned
                                       or self.section == "pick"):
                self._set_falls.append(self.fall_s)
            obs = self._latency_obs()
            if obs is not None:
                self._floor_obs.append(obs)
            self._update_prompt_fade(pclass,
                                     missed=(err in ("miss", "shown")))
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
        if resp_t is None and outcome.label == "Miss":
            # A press inside the lockout was marked at the press
            # (120 + lane); telling log_trial a press happened keeps
            # it from adding a deadline-expired byte (130) on top.
            resp_t = next((p.t_perf for p in self._set_presses
                           if p.kind == KIND_ANTICIP), None)
        self.engine.log_trial(
            trial, outcome, now,
            stimulus=self._pack_stimulus(rec),
            # One lane is right, and the row says which.
            correct_lanes=[self.option_set.target_lane],
            # A Miss here is a set nobody answered, never a wrong
            # finger: the mode's own code beats the engine's
            # had_incorrect_press-derived guess. device_drop is the
            # engine's own void vocabulary.
            error_type=(err if outcome.label == "Miss" else ""),
            response_t_perf=resp_t,
            hand=self.word_hand,
        )
        if voided:
            self._set_voided = True
            return
        if self.sectioned and self.section == "review":
            # The review is a warm-up at a glance: it moves no ladder.
            return
        if (self.sectioned and self._source_alive()
                and pclass != "prompted_correct"):
            self._move_family(pclass == "unprompted_correct")
        if self._source_alive() and pclass != "prompted_correct":
            # The staircase reads answers found alone: a set the
            # prompt helped neither makes the foils harder nor easier
            # (docstring, PROMPT: a prompted answer "does not move the
            # foil staircase"). A wrong first press after the buzz is
            # still a wrong first press and moves it down.
            self._move_rung(pclass == "unprompted_correct", err, now)

    def _rig_void(self, now: float) -> bool:
        """True when a board drop on this word's hand overlapped the
        set on screen, by the engine's own test. `is True` because a
        bare test engine answers with a mock, which is not a drop."""
        check = getattr(self.engine, "_drop_overlaps", None)
        if not callable(check):
            return False
        return check(self.word_hand, self._spawn_t, now) is True

    def _move_rung(self, first_ok: bool, err: str, now: float) -> None:
        """The 3-down-1-up staircase (Levitt 1971): three consecutive
        first-press-correct sets make the foils harder, one set whose
        first press was wrong or missed makes them easier. The run
        counter resets on every move, so a rung cannot move twice off
        one run."""
        if self.fall_mode:
            # Hear and pick only in the sectioned sitting: otherwise
            # the build sets that end the sitting set the threshold
            # (the deep review of 1 October 2026: the last 12 sets of
            # every simulated block were build sets).
            if self.sectioned and self.section != "pick":
                return
            self._move_fall(first_ok, err)
            return
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

    def _move_fall(self, first_ok: bool, err: str) -> None:
        """The adult staircase: four unaided right answers in a row
        shorten the fall by step_down, any error or miss lengthens it
        by step_up, inside the profile's bounds. With step_down over
        step_up at 0.85, 4-down-1-up settles near 85.8 percent correct
        (Garcia-Perez 1998: a ratio of 0.8415 gives 85.84; the 84.1
        once quoted was Levitt's 1971 figure for equal steps). The
        threshold is speed and foil discrimination together, under
        adaptive foils (the deep review). A replayed set leaves the
        fall where it is. A change of direction is a reversal, and the
        mean of the last six is the threshold."""
        prof = self.profile
        if self._replayed:
            return
        old = self._fall_now
        if first_ok:
            self._fall_run += 1
            if self._fall_run >= prof.fall_down_after:
                self._fall_now = max(prof.fall_lo_s,
                                     round(old - prof.fall_step_down_s, 3))
                self._fall_run = 0
        else:
            self._fall_run = 0
            self._fall_now = min(prof.fall_hi_s,
                                 round(old + prof.fall_step_up_s, 3))
        if self._fall_now == old:
            return
        direction = 1 if self._fall_now > old else -1
        if self._fall_dir and direction != self._fall_dir:
            self._fall_reversals.append(old)
        self._fall_dir = direction
        self._fall_trace.append(self._fall_now)
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "fall_change",
                detail=(f"old={old * 1000:.0f};new={self._fall_now * 1000:.0f};"
                        f"reason={'run4' if first_ok else err};"
                        f"set_idx={len(self._sets)}"),
                hand=self.word_hand)

    def fall_threshold(self) -> dict:
        """The adult outcome: the mean fall over the last 12 sets, and
        the mean of the last six reversals when there are six. In the
        sectioned sitting both read hear-and-pick sets only."""
        falls = self._set_falls[-12:]
        revs = self._fall_reversals[-6:]
        return {
            "fall_last12_s": (round(sum(falls) / len(falls), 3)
                              if falls else None),
            "fall_reversal_mean_s": (round(sum(revs) / len(revs), 3)
                                     if len(revs) >= 6 else None),
            "n_reversals": len(self._fall_reversals),
            "fall_trace_s": list(self._fall_trace),
        }

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

    def _finish_word(self, now: float, completed: bool,
                     advance: bool = True) -> None:
        """Close the word attempt: the record the band gate, the streak
        and the ease-in draw all work from. advance False leaves the
        next phase to the caller (the sectioned sitting's read-back)."""
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
        if not completed and advance:
            self._enter_phase("gap", now)
            self._after_word_bookkeeping(now)

    def _after_word(self, now: float) -> None:
        """Leaving the COMPLETE card: close the word, then the gap. In
        the sectioned sitting a word with a shown slot was not found
        whole, so it is booked as missed and comes back later."""
        if self.sectioned:
            found = not any(self._slots_shown)
            self._finish_word(now, completed=found, advance=False)
            if not found and self.section in ("pick", "build"):
                self._park_word(now)
            self._enter_phase("gap", now)
            self._after_word_bookkeeping(now)
            return
        self._finish_word(now, completed=True)
        self._enter_phase("gap", now)
        self._after_word_bookkeeping(now)

    def _read_whole(self, now: float) -> None:
        """The last step of every word in the sectioned sitting: the
        slots close into one word, held silently long enough for the
        reader to decode it, and only then is it heard. Children store
        a spelling mainly by decoding it themselves (Share 1999; Kyte
        and Johnson 2006), so the voice confirms rather than tells."""
        self.strip_closed = True
        hold = max(0.0, float(self.profile.read_hold_s))
        self._speech_queue.append((now + hold, None))
        said = 0.8
        if self.word is not None and self.speech_backend not in ("off",
                                                                 "say"):
            said = max(said, self.speech_seconds(
                self.speech_path(self.word.word)))
        self._phase_until = now + max(self.complete_s, hold + said + 1.0)
        self.arm_wait("feedback", self._phase_until,
                      self._skip_complete, started_at=now)

    def _after_word_bookkeeping(self, now: float) -> None:
        if self.ret == 0:
            self.words_done += 1
            if self.sectioned:
                self._section_words += 1
                if self._section_words >= self._section_quota():
                    self._advance_section(now)
                return
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
        pat = (f"{(self._prompted_t - self._spawn_t) * 1000.0:.0f}"
               if self._prompted_t is not None and self._spawn_t is not None
               else "")
        parts.append(f"pon={1 if rec.prompt_armed else 0}")
        parts.append(f"pstep={self._prompt_step}")
        parts.append(f"prompt={1 if rec.prompted else 0}")
        parts.append(f"pat={pat}")
        parts.append(f"pclass={rec.pclass}")
        parts.append(f"weak={1 if self._weak_set else 0}")
        parts.append("pdue=" + (f"{self._prompt_plan_s * 1000.0:.0f}"
                                if self._prompt_plan_s is not None
                                else ""))
        parts.append(f"prof={self.profile.pid}")
        parts.append(f"lex={getattr(self.word, 'lex', 'word')}")
        parts.append(f"print={1 if self._word_printed else 0}")
        parts.append(f"replay={1 if self._replayed else 0}")
        if self.sectioned:
            parts.append(f"sec={rec.section}")
            parts.append(f"fam={rec.family or ''}")
            parts.append(f"flv={rec.family_level}")
            parts.append(f"fn={self._set_family_n}")
            parts.append(f"shown={1 if rec.shown else 0}")
        return ";".join(parts)

    # ---- the speed check (sectioned, 10 and over) -------------------------
    def _begin_speed_trial(self, now: float, reuse: bool = False) -> None:
        """One speed trial: a whole word flashed, a mask, then four
        words to pick it from. Practice and a fluency measure at the
        end of the sitting (SECTIONS in the docstring); not claimed to
        improve reading."""
        reuse = reuse or self._speed_reuse
        self._speed_reuse = False
        if not reuse or self.speed_word is None:
            if self._speed_done >= self._section_quota():
                self._end("completed")
                return
            if (self._t0 is not None
                    and (now - self._t0) > self.session_cap_s):
                self._end("time_cap")
                return
            self.speed_word = self._draw_speed_word()
            if self.speed_word is None:
                self._end("completed")
                return
            self.word_hand = self._next_hand()
        self.speed_options = None
        self._speed_tlane = None
        self._speed_presses = []
        self.option_set = None
        self.active = None
        self._spawn_t = None
        self._exit_t = None
        self._set_close_t = None
        self._glow_t = None
        self.lift_t = None
        self._enter_phase("flash", now)

    def _speed_pool(self) -> list[Word]:
        """Real words short enough to take in at a glance and to fit
        four across the screen at a readable size: the profile's own,
        plus the bank's bands B and C so an adult pool of long words
        still has enough."""
        real, _pseudo = profile_words(self.profile, self.band)
        extra = [w for w in all_words() if w.band in ("B", "C")]
        seen: set[str] = set()
        out: list[Word] = []
        for w in list(real) + extra:
            if (w.word in seen or w.n_syll < 2
                    or w.word in self._held_out
                    or len(w.word) > self.SPEED_MAX_LETTERS):
                continue
            seen.add(w.word)
            out.append(w)
        return out or list(real)

    def _draw_speed_word(self) -> Word | None:
        real = self._speed_pool()
        pool = [w for w in real if w.word not in self._speed_seen]
        if not pool:
            pool = list(real)
        if not pool:
            return None
        word = self.rng.choice(pool)
        self._speed_seen.add(word.word)
        return word

    def _speed_choices(self, word: Word) -> list[str]:
        """Three other words that look like the one flashed: the same
        number of syllables, the same first letter where possible and a
        length within two letters, so the pick needs the whole word."""
        cands = [w for w in self._speed_pool() if w.word != word.word]
        same = [w for w in cands if w.n_syll == word.n_syll] or cands

        def closeness(w: Word) -> tuple:
            return (w.word[:1] != word.word[:1],
                    abs(len(w.word) - len(word.word)))
        same.sort(key=closeness)
        near = same[:12] if len(same) > 12 else same
        picks: list[str] = []
        for w in self.rng.sample(near, len(near)):
            if w.word not in picks:
                picks.append(w.word)
            if len(picks) == 3:
                break
        return picks

    def _spawn_speed(self, now: float) -> None:
        word = self.speed_word
        lanes = self.active_lanes()
        others = self._speed_choices(word)
        tlane = draw_target_lane(lanes, self._lane_targets,
                                 self._recent_target_lanes, self.rng)
        self._lane_targets[tlane] = self._lane_targets.get(tlane, 0) + 1
        self._recent_target_lanes.append(tlane)
        rest = [lane for lane in lanes if lane != tlane]
        self.rng.shuffle(rest)
        opts = [(tlane, word.word, True)]
        opts += [(lane, text, False) for lane, text in zip(rest, others)]
        self.speed_options = sorted(opts)
        self._speed_tlane = tlane
        self.trial_counter += 1
        self.active = PendingTrial(trial_id=self.trial_counter, lane=tlane,
                                   stim_t_perf=now, keys_pressed=[],
                                   incorrect_presses=[])
        self._spawn_t = now
        self._exit_t = now + self.SPEED_LIMIT_S
        self._set_close_t = None
        self._enter_phase("speed", now)
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "speed_spawn", lane=tlane, t_perf=now,
                detail=(f"trial_id={self.trial_counter};word={word.word};"
                        f"expo={self._expo_s * 1000.0:.0f}"),
                hand=self.word_hand)
        self.silent_stim = True
        try:
            self.engine.on_stim_multi(lanes, self.trial_counter, now,
                                      buzz=False)
        finally:
            self.silent_stim = False

    def _update_speed(self, now: float) -> None:
        if self._set_close_t is not None:
            if now >= self._set_close_t:
                self._close_speed(now)
            return
        if self._exit_t is not None and now >= self._exit_t:
            self._glow_t = now
            self._score_speed(now, None, wrong=False)
            self._set_close_t = now + self.SPEED_FEEDBACK_S

    def _handle_speed_press(self, ev: PressEvent, now: float) -> None:
        """One press answers a speed trial: the four words stay still,
        and a second look is not the measure."""
        if self._set_close_t is not None or self.speed_options is None:
            self._eeg_press_byte(EEG_CODES["resp_idle"], ev)
            return
        if ev.lane not in self.active_lanes():
            return
        last = self._last_tap_t.get(ev.lane)
        if last is not None and (ev.t_perf - last) < self.tap_debounce_s:
            return
        self._last_tap_t[ev.lane] = ev.t_perf
        peak = self._peak_for(ev)
        if (self._spawn_t is not None
                and ev.t_perf < self._spawn_t + self.spawn_lockout_s):
            self._speed_presses.append(Press(ev.lane, ev.t_perf,
                                             KIND_ANTICIP, peak))
            code = response_code("anticipation", ev.lane)
            if code is not None:
                self._eeg_press_byte(code, ev)
            return
        correct = ev.lane == self._speed_tlane
        self._speed_presses.append(Press(
            ev.lane, ev.t_perf, KIND_CORRECT if correct else KIND_WRONG,
            peak))
        if self.active is not None:
            self.active.keys_pressed.append(ev.lane)
        if correct:
            self.lift_t = ev.t_perf
            self._score_speed(now, ev.t_perf)
        else:
            if self.active is not None:
                self.active.incorrect_presses.append((ev.lane, ev.t_perf))
                self.engine.eeg_wrong_press(self.active.incorrect_presses)
            self._glow_t = ev.t_perf
            self._score_speed(now, None, wrong=True)
        self._set_close_t = max(now, ev.t_perf) + self.SPEED_FEEDBACK_S

    def _score_speed(self, now: float, correct_t: float | None,
                     wrong: bool = False) -> None:
        trial = self.active
        if trial is None or self.speed_word is None:
            return
        self.active = None
        rt_ms = ((correct_t - self._spawn_t) * 1000.0
                 if correct_t is not None and self._spawn_t is not None
                 else None)
        # A trial nobody answered while this hand's board was away is
        # the rig's: logged as device_drop, flashed again, and kept
        # out of the staircase and the threshold.
        voided = (correct_t is None and not wrong
                  and not trial.incorrect_presses and self._rig_void(now))
        if correct_t is not None:
            first, err, label = "ok", "ok", "Great"
        elif wrong:
            first, err, label = "wrong", "wrong_first", "Miss"
        elif voided:
            first, err, label = "none", "device_drop", "Miss"
        else:
            first, err, label = "none", "miss", "Miss"
        points = (self.score_cfg.great_points if label == "Great"
                  else self.score_cfg.miss_points)
        outcome = TrialResult(label=label, points=points, rt_ms=rt_ms)
        rec = {"word": self.speed_word.word, "expo_ms":
               round(self._expo_s * 1000.0), "first": first, "err": err,
               "rt_ms": rt_ms, "nsyll": self.speed_word.n_syll,
               "hand": self.word_hand}
        if voided:
            self._speed_void = True
        else:
            self._speed_records.append(rec)
        resp_t = next((p.t_perf for p in self._speed_presses
                       if p.kind in (KIND_CORRECT, KIND_WRONG)), None)
        if resp_t is None and label == "Miss":
            resp_t = next((p.t_perf for p in self._speed_presses
                           if p.kind == KIND_ANTICIP), None)
        self.engine.log_trial(
            trial, outcome, now, stimulus=self._pack_speed(rec),
            correct_lanes=[self._speed_tlane],
            error_type=("" if label == "Great" else err),
            response_t_perf=resp_t, hand=self.word_hand)
        if not voided and self._source_alive():
            self._move_expo(first == "ok")

    def _move_expo(self, ok: bool) -> None:
        """The exposure staircase. Until the first wrong answer, each
        right answer shows the next word 80 ms shorter, so a fluent
        reader reaches their range in a few trials; after it, three
        right answers in a row take 80 ms off and a wrong answer or no
        answer adds 80 ms, inside 100 ms to 1.5 s. With equal steps
        3-down-1-up only loosely targets Levitt's 79.4 percent
        (Garcia-Perez 1998). The threshold is the mean exposure at the
        reversals after the first, once there are two; a run this
        short gives a rough one (two simulated blocks of one reader
        differed with an SD of about 0.05 to 0.07 s), so the final
        exposure and the accuracy are kept beside it. Exposures are whole
        display frames in practice (about 17 ms at 60 Hz)."""
        old = self._expo_s
        if ok:
            self._expo_run += 1
            if self._expo_run >= (3 if self._expo_missed else 1):
                self._expo_run = 0
                self._expo_s = max(self.EXPO_MIN_S,
                                   round(old - self.EXPO_STEP_S, 3))
        else:
            self._expo_missed = True
            self._expo_run = 0
            self._expo_s = min(self.EXPO_MAX_S,
                               round(old + self.EXPO_STEP_S, 3))
        if self._expo_s == old:
            return
        direction = 1 if self._expo_s > old else -1
        if self._expo_dir and direction != self._expo_dir:
            self._expo_reversals.append(old)
        self._expo_dir = direction
        self._expo_trace.append(self._expo_s)

    def _close_speed(self, now: float) -> None:
        self.speed_options = None
        self._speed_tlane = None
        self._spawn_t = None
        self._exit_t = None
        self._set_close_t = None
        self._glow_t = None
        self.lift_t = None
        if self._speed_void:
            self._speed_void = False
            self._speed_reuse = True
        else:
            self._speed_done += 1
        self._enter_phase("gap", now)

    def _pack_speed(self, rec: dict) -> str:
        opts = ",".join(f"{lane + 1}:{text}:{'t' if tgt else 'f'}"
                        for lane, text, tgt in (self.speed_options or []))
        presses = ",".join(
            f"{p.lane + 1}:"
            f"{(p.t_perf - (self._spawn_t or p.t_perf)) * 1000.0:.1f}:"
            + (f"{p.peak:.1f}" if p.peak is not None else "")
            + f":{p.kind}"
            for p in self._speed_presses)
        rt = rec["rt_ms"]
        return ";".join([
            rec["word"], "sec=speed", f"nsyll={rec['nsyll']}",
            f"expo={rec['expo_ms']}",
            f"hand={'L' if rec['hand'] == 'left' else 'R'}",
            f"opts={opts}",
            f"tlane={(self._speed_tlane or 0) + 1}",
            f"presses={presses}", f"first={rec['first']}",
            f"err={rec['err']}",
            f"rt={rt:.1f}" if rt is not None else "rt=",
            f"prof={self.profile.pid}", "lex=word",
            f"sup={1 if self.supervised else 0}",
        ])

    def speed_threshold(self) -> dict:
        recs = self._speed_records
        revs = self._expo_reversals[1:]
        return {
            "n": len(recs),
            "acc": (round(sum(1 for r in recs if r["first"] == "ok")
                          / len(recs), 3) if recs else None),
            "expo_final_ms": round(self._expo_s * 1000.0),
            "expo_reversal_mean_ms": (round(sum(revs) / len(revs) * 1000.0)
                                      if len(revs) >= 2 else None),
            "n_reversals": len(self._expo_reversals),
            "expo_trace_ms": [round(v * 1000.0) for v in self._expo_trace],
        }

    # ---- the fixed probe (PROBE in the docstring) -------------------------
    def _probe_word(self, item: dict) -> Word:
        """The Word a probe set belongs to, from the bank and the pools,
        so its in-word syllable files are found; one rebuilt from the
        set's own syllables when neither holds it."""
        name = str(item.get("word", ""))
        for w in all_words():
            if w.word == name:
                return w
        for pool in load_pools().values():
            for w in pool:
                if w.word == name:
                    return w
        syls = tuple(str(s) for s in item.get("syllables") or [name])
        return Word(word=name, band="probe", syllables=syls, stress=0,
                    lex=str(item.get("lex", "word")))

    def _begin_probe_trial(self, now: float, reuse: bool = False) -> None:
        """One probe set: the word heard, then after attend_s the four
        tiles and the target syllable once. With the list done, the
        section ends; a sitting of the probe alone ends with it."""
        reuse = reuse or self._probe_reuse
        self._probe_reuse = False
        if not reuse or self.probe_item is None:
            if self._probe_done >= self._section_quota():
                # The session cap times the training from here: the
                # probe has its own fixed length (3 to 4 minutes), and
                # counting it would cut the end of a slower reader's
                # sitting, where the build and the quick look are.
                self._t0 = now
                self._advance_section(now)
                if self.section_idx >= len(self.section_plan):
                    self._end("completed")
                return
            self.probe_item = self._probe_items[self._probe_done]
            self.word_hand = self._next_hand()
        item = self.probe_item
        self.word = self._probe_word(item)
        self.pos = int(item.get("pos", 0))
        self.ret = 0
        self.probe_options = None
        self._probe_kinds = {}
        self._probe_tlane = None
        self._probe_presses = []
        self.option_set = None
        self.active = None
        self._spawn_t = None
        self._exit_t = None
        self._set_close_t = None
        self._glow_t = None
        self.lift_t = None
        self._last_tap_t = {}
        self._speech_queue = []
        self._enter_phase("probe_listen", now)
        self._phase_until = now + self.attend_s
        self._speak_word()

    def _spawn_probe(self, now: float) -> None:
        item = self.probe_item
        lanes = self.active_lanes()
        tl = int(item.get("tlane", 0))
        opts: list[tuple[int, str, bool]] = []
        kinds: dict[int, str] = {}
        for o in item.get("options") or []:
            k = int(o.get("lane", -1))
            if 0 <= k < len(lanes):
                opts.append((lanes[k], str(o.get("text", "")), k == tl))
                kinds[lanes[k]] = str(o.get("kind", ""))
        self.probe_options = sorted(opts)
        self._probe_kinds = kinds
        self._probe_tlane = lanes[tl] if 0 <= tl < len(lanes) else lanes[0]
        self.trial_counter += 1
        self.active = PendingTrial(trial_id=self.trial_counter,
                                   lane=self._probe_tlane, stim_t_perf=now,
                                   keys_pressed=[], incorrect_presses=[])
        self._spawn_t = now
        self._exit_t = now + self.probe_time_s
        self._set_close_t = None
        self._enter_phase("probe", now)
        raw = getattr(self.engine, "raw_logger", None)
        if raw:
            raw.queue_event(
                "probe_spawn", lane=self._probe_tlane, t_perf=now,
                detail=(f"trial_id={self.trial_counter};"
                        f"item={self._probe_done + 1};"
                        f"word={self.word.word};pos={self.pos}"),
                hand=self.word_hand)
        self.silent_stim = True
        try:
            self.engine.on_stim_multi(lanes, self.trial_counter, now,
                                      buzz=False)
        finally:
            self.silent_stim = False
        self._speak_syllable_after(self.pos, now)

    def _update_probe(self, now: float) -> None:
        if self._set_close_t is not None:
            if now >= self._set_close_t:
                self._close_probe(now)
            return
        if self._exit_t is not None and now >= self._exit_t:
            self._score_probe(now, None)
            self._set_close_t = now

    def _handle_probe_press(self, ev: PressEvent, now: float) -> None:
        """One press answers a probe set, right or wrong, and the tiles
        go at once whichever it was: nothing tells the reader how the
        answer went, so the set measures without teaching."""
        if self._set_close_t is not None or self.probe_options is None:
            self._eeg_press_byte(EEG_CODES["resp_idle"], ev)
            return
        if ev.lane not in self.active_lanes():
            return
        last = self._last_tap_t.get(ev.lane)
        if last is not None and (ev.t_perf - last) < self.tap_debounce_s:
            return
        self._last_tap_t[ev.lane] = ev.t_perf
        peak = self._peak_for(ev)
        if (self._spawn_t is not None
                and ev.t_perf < self._spawn_t + self.spawn_lockout_s):
            self._probe_presses.append(Press(ev.lane, ev.t_perf,
                                             KIND_ANTICIP, peak))
            code = response_code("anticipation", ev.lane)
            if code is not None:
                self._eeg_press_byte(code, ev)
            return
        correct = ev.lane == self._probe_tlane
        press = Press(ev.lane, ev.t_perf,
                      KIND_CORRECT if correct else KIND_WRONG, peak)
        self._probe_presses.append(press)
        if self.active is not None:
            self.active.keys_pressed.append(ev.lane)
            if not correct:
                self.active.incorrect_presses.append((ev.lane, ev.t_perf))
                self.engine.eeg_wrong_press(self.active.incorrect_presses)
        self._score_probe(now, press)
        self._set_close_t = max(now, ev.t_perf)

    def _score_probe(self, now: float, press: Press | None) -> None:
        """Log one probe set. No points, no streak, no chime and no
        after-press buzz: the label only sorts the row (Good right,
        Miss otherwise), and the engine chimes on Great alone here."""
        trial, item = self.active, self.probe_item
        if trial is None or item is None:
            return
        self.active = None
        at_ms = ((press.t_perf - self._spawn_t) * 1000.0
                 if press is not None and self._spawn_t is not None
                 else None)
        correct = press is not None and press.kind == KIND_CORRECT
        voided = press is None and self._rig_void(now)
        if correct:
            first, err, label = "ok", "ok", "Good"
        elif press is not None:
            first, err, label = "wrong", "wrong_first", "Miss"
        elif voided:
            first, err, label = "none", "device_drop", "Miss"
        else:
            first, err, label = "none", "miss", "Miss"
        rt_ms = at_ms if correct else None
        outcome = TrialResult(label=label, points=0, rt_ms=rt_ms)
        rec = {"item": self._probe_done + 1, "word": self.word.word,
               "pos": self.pos, "syl": str(item.get("syl", "")),
               "family": str(item.get("family", "")),
               "near": str(item.get("near", "")),
               "weak": int(item.get("weak", 0) or 0),
               "held_out": bool(item.get("held_out")),
               "lex": str(item.get("lex", "word")),
               "first": first, "err": err, "rt_ms": rt_ms,
               "at_ms": at_ms, "hand": self.word_hand,
               "chosen_kind": (self._probe_kinds.get(press.lane)
                               if press is not None else None)}
        if voided:
            self._probe_void = True
        else:
            self._probe_records.append(rec)
        resp_t = (press.t_perf if press is not None
                  else next((p.t_perf for p in self._probe_presses
                             if p.kind == KIND_ANTICIP), None))
        self.engine.log_trial(
            trial, outcome, now, stimulus=self._pack_probe(rec),
            correct_lanes=[self._probe_tlane],
            error_type=("" if correct else err),
            response_t_perf=resp_t, hand=self.word_hand,
            after_press_cue=False)

    def _close_probe(self, now: float) -> None:
        self.probe_options = None
        self._probe_tlane = None
        self._spawn_t = None
        self._exit_t = None
        self._set_close_t = None
        if self._probe_void:
            # The rig ate the set: the same set again, so the list
            # stays whole.
            self._probe_void = False
            self._probe_reuse = True
        else:
            self._probe_done += 1
        self._enter_phase("gap", now)

    def _pack_probe(self, rec: dict) -> str:
        opts = ",".join(
            f"{lane + 1}:{text}:"
            + ("target" if tgt else self._probe_kinds.get(lane, ""))
            for lane, text, tgt in (self.probe_options or []))
        presses = ",".join(
            f"{p.lane + 1}:"
            f"{(p.t_perf - (self._spawn_t or p.t_perf)) * 1000.0:.1f}:"
            + (f"{p.peak:.1f}" if p.peak is not None else "")
            + f":{p.kind}"
            for p in self._probe_presses)
        rt, at = rec["rt_ms"], rec["at_ms"]
        item = self.probe_item or {}
        return ";".join([
            rec["word"], "sec=probe", f"item={rec['item']}",
            f"pos={rec['pos']}", f"nsyll={self.n_syll}",
            f"syl={rec['syl']}", f"weak={rec['weak']}",
            f"held={1 if rec['held_out'] else 0}",
            f"fam={rec['family']}", f"near={rec['near']}",
            f"hand={'L' if rec['hand'] == 'left' else 'R'}",
            f"fall={self.probe_time_s * 1000.0:.0f}",
            f"opts={opts}",
            f"tlane={(self._probe_tlane or 0) + 1}",
            f"presses={presses}", f"first={rec['first']}",
            f"err={rec['err']}",
            f"rt={rt:.1f}" if rt is not None else "rt=",
            f"at={at:.1f}" if at is not None else "at=",
            f"prof={self.profile.pid}", f"lex={rec['lex']}",
            f"sup={1 if self.supervised else 0}",
            f"pv={int(item.get('version', 0) or 0)}",
        ])

    def probe_stats(self) -> dict:
        """The probe's numbers for metadata.json: accuracy over the
        sets answered, on held-out and practised words apart, and by
        family. The notebook reads the rows; this is the summary."""
        recs = self._probe_records

        def _acc(rows: list[dict]) -> dict:
            n = len(rows)
            ok = sum(1 for r in rows if r["first"] == "ok")
            return {"n": n, "acc": round(ok / n, 3) if n else None}

        fams = sorted({r["family"] for r in recs})
        return {
            "version": int((self._probe_items[0].get("version", 0)
                            if self._probe_items else 0) or 0),
            "n_items": len(self._probe_items),
            "time_s": self.probe_time_s,
            "complete": len(recs) >= self._section_quota_of("probe"),
            **_acc(recs),
            "held_out": _acc([r for r in recs if r["held_out"]]),
            "practised": _acc([r for r in recs if not r["held_out"]]),
            "by_family": {f: _acc([r for r in recs if r["family"] == f])
                          for f in fams},
            "no_answer": sum(1 for r in recs if r["first"] == "none"),
        }

    def _section_quota_of(self, name: str) -> int:
        for sec, n in self.section_plan:
            if sec == name:
                return int(n)
        return 0

    def _speech_meta(self) -> dict:
        """The voice every heard item came from (the speech manifest),
        for the methods: model, voice, accent, render dates."""
        self._speech_manifest()
        meta = dict(self._manifest_meta or {})
        return {"backend": self.speech_backend,
                "model": meta.get("model"), "voice": meta.get("voice"),
                "accent": meta.get("accent"),
                "rendered_on": meta.get("rendered_on"),
                "syllables_rendered_on": meta.get("syllables_rendered_on"),
                "chunk_form": meta.get("chunk_form"),
                "latency_ms": meta.get("latency_ms")}

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
        if not self._bank_bands:
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
            p = root / f"{speech_stem(stem)}{ext}"
            if p.exists():
                return p
        return None

    def chunk_speech_path(self, chunk: str) -> Path | None:
        """The recorded file for one written chunk, or None. A chunk is
        recorded once, as a spelling pronunciation (never an 'uh'),
        and reused in every word that holds it
        (scripts/syllables_recording_kit.py). The fallback for a word
        the syllable_map does not cover (syllable_file)."""
        root = self._speech_root() / "chunks"
        for ext in (".wav", ".ogg"):
            p = root / f"{speech_stem(chunk)}{ext}"
            if p.exists():
                return p
        return None

    def _word_syllables(self) -> dict:
        """The syllable_map entry of the word in play, or {}."""
        if self.word is None:
            return {}
        self._speech_manifest()
        return dict((self._manifest_syllables or {}).get(self.word.word)
                    or {})

    def syllable_file(self, k: int) -> Path | None:
        """The file for syllable k of the word in play: as it sounds IN
        that word (the manifest's syllable_map, 29 September 2026), so
        the parts blend back into the word, the ger of tiger a "guh"
        and the ger of ginger a "juh". A word the map does not cover
        falls back to its chunk's spelt file, then to a word_k render."""
        if self.word is None or not (0 <= k < self.n_syll):
            return None
        files = self._word_syllables().get("files") or []
        if k < len(files):
            base = self._speech_root() / str(files[k])
            for ext in (".wav", ".ogg"):
                p = base.with_name(base.name + ext)
                if p.exists():
                    return p
        return (self.chunk_speech_path(self.word.syllables[k])
                or self.speech_path(f"{self.word.word}_{k}"))

    def heard_weak(self, k: int) -> bool | None:
        """Whether syllable k is heard with a weak vowel (uh, ih) as it
        is in its word, where ter, tar and tur sound alike. None when
        the syllable_map does not cover the word."""
        weak = self._word_syllables().get("weak")
        if not weak or not (0 <= k < len(weak)):
            return None
        return bool(weak[k])

    def speech_seconds(self, path: Path | None) -> float:
        """A speech file's length, from the manifest the recording kit
        writes, else from a WAV header; 0.0 when neither says."""
        if path is None:
            return 0.0
        key = str(path)
        if key in self._speech_len:
            return self._speech_len[key]
        secs = 0.0
        try:
            entry = self._speech_manifest().get(
                f"{path.parent.name}/{path.stem}"
                if path.parent.name in ("chunks", "syllables")
                else path.stem) or {}
            secs = float(entry.get("duration_ms", 0.0)) / 1000.0
            if secs <= 0.0 and path.suffix == ".wav":
                import wave
                with wave.open(str(path), "rb") as w:
                    secs = w.getnframes() / float(w.getframerate())
        except Exception:
            secs = 0.0
        self._speech_len[key] = secs
        return secs

    def _speech_manifest(self) -> dict:
        if self._manifest_entries is None:
            try:
                import json
                data = json.loads((self._speech_root() / "manifest.json")
                                  .read_text(encoding="utf-8"))
                self._manifest_entries = dict(data.get("entries") or {})
                self._manifest_meta = {k: v for k, v in data.items()
                                       if k not in ("entries",
                                                    "syllable_map")}
                self._manifest_syllables = dict(
                    data.get("syllable_map") or {})
            except Exception:
                self._manifest_entries = {}
                self._manifest_meta = {}
                self._manifest_syllables = {}
        return self._manifest_entries

    def model_ioi_s(self, k: int) -> float:
        """The beat after the k-th modelled syllable: the configured
        interval, stretched so the syllable's file finishes with
        MODEL_GAP_S of quiet before the next. Speech plays on one
        channel, so the next file would cut the last one off."""
        if (self.word is None or not (0 <= k < self.n_syll)
                or self.speech_backend in ("off", "say")):
            return self.ioi_s
        path = self.syllable_file(k)
        return max(self.ioi_s, self.speech_seconds(path) + self.MODEL_GAP_S)

    def blend_s(self) -> float:
        """How long the blend holds: the whole word said, then
        BLEND_HOLD_S before the first set."""
        said = 0.0
        if self.word is not None and self.speech_backend not in ("off",
                                                                 "say"):
            said = self.speech_seconds(self.speech_path(self.word.word))
        return max(self.ioi_s, said) + self.BLEND_HOLD_S

    def chunks_spelt(self, chunk: str | None = None) -> bool:
        """Whether the chunk recordings are spelling pronunciations
        (the recording kit's manifest says chunk_form spelling). Given a
        chunk, also whether that one has a file: the voice can be made
        for some age pools and not others, and a chunk with no file is
        said by `say` or not at all, never in its spelt form."""
        self._speech_manifest()
        if (self._manifest_meta or {}).get("chunk_form") != "spelling":
            return False
        return chunk is None or self.chunk_speech_path(chunk) is not None

    def _speak_syllable_after(self, k: int | None, now: float) -> None:
        """Speak syllable k (None: the whole word, at the blend) now,
        or sound_lead_s after the print for a child: 11 year olds
        integrate letters and sound best at a small letter lead,
        adults near synchrony."""
        if self.sound_lead_s <= 0.0:
            self._say_part(k)
        else:
            self._speech_queue.append((now + self.sound_lead_s, k))

    def _say_part(self, k: int | None) -> None:
        if k is None:
            self._speak_word()
        else:
            self._speak_syllable(k)

    def _flush_speech(self, now: float) -> None:
        if not self._speech_queue:
            return
        due = [q for q in self._speech_queue if q[0] <= now]
        self._speech_queue = [q for q in self._speech_queue if q[0] > now]
        for _t, k in due:
            self._say_part(k)

    def _speak_word(self) -> None:
        if self.word is not None:
            self._speak(self.word.word, self.word.word)

    def _speak_syllable(self, k: int) -> None:
        if self.word is None or not (0 <= k < self.n_syll):
            return
        chunk = self.word.syllables[k]
        self._speak(f"{self.word.word}_{k}", chunk, chunk=chunk,
                    path=self.syllable_file(k))

    def _speak(self, stem: str, text: str, chunk: str | None = None,
               path: Path | None = None) -> None:
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
            return
        if backend == "say":
            path = None
        elif path is None:
            if chunk is not None:
                path = self.chunk_speech_path(chunk)
            path = path or self.speech_path(stem)
        if path is not None:
            audio = getattr(self.engine, "audio", None)
            player = getattr(audio, "play_speech", None)
            if callable(player):
                try:
                    player(str(path), volume=self.speech_volume)
                except Exception:
                    pass
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event("speech", t_perf=time.perf_counter(),
                                detail=f"file={path.name}",
                                hand=self.word_hand)
            return
        if backend == "file":
            if stem not in self._missing_speech:
                self._missing_speech.add(stem)
                log.info("No speech file for %r under %s; running silent",
                         stem, self.speech_dir)
            return
        if sys.platform != "darwin" or shutil.which("say") is None:
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
    def _prompt_stats(self) -> dict:
        """The prompt's numbers: the five outcome classes, the share
        of correct answers that needed the buzz, and the floor. The
        unprompted correct rate mixes speed with accuracy (PROMPT in
        the docstring), so the notebook sets it beside the time to an
        unaided first press and the accuracy before any buzz."""
        sets = self._sets
        counts = {c: sum(1 for r in sets if r.pclass == c)
                  for c in self.PCLASSES}
        n = len(sets)
        correct = counts["unprompted_correct"] + counts["prompted_correct"]
        return {
            "enabled": self.prompt_enabled,
            "steps": list(self.prompt_steps),
            "floor_margin_ms": round(self.prompt_floor_margin_s * 1000.0),
            "n_sets": n,
            "n_prompted": sum(1 for r in sets if r.prompted),
            "classes": counts,
            "unprompted_correct_rate": (
                round(counts["unprompted_correct"] / n, 3) if n else None),
            "prompted_share_of_correct": (
                round(counts["prompted_correct"] / correct, 3)
                if correct else None),
            "words_faded": sum(1 for st in self._prompt_state.values()
                               if st["step"] >= len(self.prompt_steps)),
            # The floor under the delay at block end: a Kaplan-Meier
            # median over the recent sets (PROMPT in the docstring).
            "floor": {"rule": "kaplan_meier",
                      "n_sets": len(self._floor_obs),
                      "n_answered": sum(1 for _s, e in self._floor_obs
                                        if e),
                      "median_s": (round(self.prompt_floor_s(), 3)
                                   if self.prompt_floor_s() is not None
                                   else None)},
        }

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
            # Sets a board drop ate: replayed, out of every number
            # here, on their rows as device_drop.
            "n_voided_sets": len(self._voided_sets),
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
            # The warm-up is gone; the keys stay so older notebooks
            # and the history reader find them.
            "warmup_taps": 0,
            "warmup_asyn_mean_ms": None,
            "warmup_asyn_sd_ms": None,
            "prompt": self._prompt_stats(),
            "max_streak": self._max_streak,
            "stickers": self._stickers,
            "n_ease_in": self._n_ease_in,
            "demo": self.demo,
            "end_reason": self.end_reason,
            "profile": self.profile.pid,
            # What the methods must report (the deep review of 1
            # October 2026): the seed, the voice and the block size.
            "seed": self.seed,
            "speech": self._speech_meta(),
            "words_per_block": self.words_total,
            "held_out_words": len(self._held_out),
            **({"probe": self.probe_stats()} if self._probe_items else {}),
            "unaided_accuracy": (round(sum(
                1 for s in sets if s.pclass == "unprompted_correct")
                / n_sets, 3) if n_sets else None),
            **({"fall_threshold": self.fall_threshold()}
               if self.fall_mode else {}),
            **({"sections": self._section_stats()}
               if self.sectioned else {}),
            **self.wait_skip_stats(),
        }

    def _section_stats(self) -> dict:
        """The sectioned sitting's own numbers: first-press accuracy
        per section and per confusion family, where each family's
        ladder ended, how many answers were shown after two wrong
        presses, and the speed check's threshold."""
        sets = self._sets

        def _acc(rows: list[SetRecord]) -> dict:
            n = len(rows)
            ok = sum(1 for s in rows if s.first == "ok")
            return {"n": n, "acc": round(ok / n, 3) if n else None}

        by_section = {name: _acc([s for s in sets if s.section == name])
                      for name, _n in self.section_plan
                      if name not in ("speed", "probe")}
        families = {}
        for fam in self.profile.families:
            rows = [s for s in sets if s.family == fam]
            # "mastered" is the code's name for a further run of three
            # at level 3; the analysis says passed level 3, which is
            # what it is (SECTIONS in the docstring).
            families[fam] = {**_acc(rows),
                             "level": self.family_levels.get(fam, 0),
                             "mastered": fam in self.family_mastered,
                             "passed_level_3": fam in self.family_mastered}
        return {
            "plan": [[name, n] for name, n in self.section_plan],
            "reached": (self.section_plan[min(
                self.section_idx, len(self.section_plan) - 1)][0]
                if self.section_plan else None),
            "by_section": by_section,
            "families": families,
            "mixed_sets": _acc([s for s in sets if s.family == "mix"]),
            "family_trace": list(self._family_trace),
            "n_shown": sum(1 for s in sets if s.shown),
            **({"speed": self.speed_threshold()}
               if any(name == "speed" for name, _n in self.section_plan)
               else {}),
        }
