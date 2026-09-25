"""SRT: the lab's serial reaction time task, trial for trial.

WHAT IT IS. Four grey squares in a row. One flashes red with its own
tone and the participant presses that finger as fast as they can.
Between two random blocks the flashes follow a fixed ten-item order
nobody mentions. Getting faster on the fixed order, and slower again
when the order turns random, is sequence learning, the effect the
serial reaction time task was built to show (Nissen and Bullemer 1987,
Cognitive Psychology).

WHERE IT COMES FROM. Dr Welber Marinovic's PsychoPy script,
archive/Webler EEG past program/SRT_Sequence_learning_Final_v2.py.
Its structure is Nissen and Bullemer's (1987) Experiment 1: four
locations, a ten-item sequence, eight blocks of 100 and a 500 ms wait
after each response (Schwarb and Schumacher 2012). That wait starts
at the response, so it is a response-to-stimulus interval (RSI); the
script and the files call it ISI and so does this code. The lane
tones are the lab's own addition: location tones improve learning on
this task (Leow et al. 2025, European Journal of Neuroscience). The
research file is docs/research/new_modes/srt-sequence-learning.md.
This mode replicates the script:

- Order: welcome, practice (48 random trials with Correct / Incorrect
  / Miss! feedback), MAIN TASK, eight learning blocks of the sequence
  ten times over (100 trials each), FINAL PHASE (48 random), the
  explicit recall, thank you. Every screen between them waits for
  SPACE; every block opens with a 1000 ms wait.
- A trial: the interval, then the target turns red for 100 ms with
  its lane tone (the lab's own V, B, N and M wav files, E5 F5 G5 A5),
  and the first press within 2.6 s of the flash ends it (the 100 ms
  flash plus the 2.5 s deadline, as the script counts it). No press:
  a 200 ms pause. Practice then shows its feedback word for 200 ms.
- Presses in the last 100 ms of the interval count as anticipations,
  scored by the finger they chose; earlier presses are thrown away.
  Accuracy is labelled exactly as the script labels it: correct,
  incorrect, anticipatory_correct, anticipatory_incorrect, miss (and
  too_early, which the script defines and can never reach).
- Timing groups for the learning blocks: constant, cyclical and
  random, all averaging the learning interval (game/srt_setup.py).
  Random blocks always run at 500 ms.
- EEG: byte 30 on the flip that first shows the red square, reset by
  the marker writer, nothing else per trial. Inside an srt block (mode
  id 13) a 30 is the flash and its tone together, as the lab's
  pipeline has always read it.
- The frame structure is kept: the interval is drawn after the frame
  that ends a trial, so the flash lands one frame after the interval
  runs out, the flash covers whole frames and the feedback word
  follows the miss pause. Everything is scheduled on the flip clock
  (engine.last_flip_t) rather than by counting frames, so a dropped
  frame shifts one onset instead of every onset after it.
- Recall: the participant enters the sequence they think they saw,
  one square at a time (the finger, or V B N M on a keyboard), with
  BACKSPACE to undo and ENTER or SPACE to submit once every item is
  in; each entry lights its square yellow for 150 ms, and presses in
  that 150 ms are dropped as the script drops them.
- Exports: the script's three CSVs, same names and columns, in the
  session folder (export_files), beside the app's own trials.csv.

WHAT IS NEW. The learning interval, the timing group and the sequence
come from a setup chosen on the setup screen and kept between
sessions (game/srt_setup.py). The squares' labels name the finger on
the pads and the key on a keyboard. The performance CSV gains columns
after the script's own (hand, setup, onset time, the interval the
participant actually got), so the lab's readers still find every
column where they expect it.

WHAT DIFFERS AND WHY.
- Responses come from the finger pads (force threshold crossings on
  the 200 Hz stream) or the keyboard. Pad presses carry their own
  sample time; key presses are timed when the frame loop reads them,
  up to one frame late, where the script's PsychoPy keyboard stamped
  each key to the millisecond. Pad RTs are the ones to report.
- Screen geometry is the script's norm units laid over the app's
  1280 x 800 surface, so the squares keep their size and spacing
  relative to the window.
- The tone plays when the flash is drawn, before the flip, as the
  script's sound.play() did. Its delay to the speaker belongs to the
  machine; tone_lead_ms can move it earlier once measured.
- Esc raises the app's End-session dialog instead of quitting; an
  abandoned block still writes everything it collected.
- The lab script leaves the hands to the keyboard. Here a setup picks
  one hand's four fingers or two hands (V and B left, N and M right,
  as the lab's own studies ran it); two hands needs both boards. With
  one hand in two-hand play the right hand answers and left presses
  are recorded and ignored.
"""
from __future__ import annotations

import csv
import logging
import random
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import pygame

from ...hardware.eeg_trigger import CODES as EEG_CODES
from ...hardware.eeg_trigger import response_code
from ...hardware.fsr_detector import PressEvent
from ..srt_setup import (LETTERS, SRTSetup, cyclical_pattern, isi_list,
                         random_targets, recall_scores, sequence_text)
from ._keys import keymap_for_hand, resolve_key

if TYPE_CHECKING:
    from ..engine import GameEngine


log = logging.getLogger(__name__)

FINGERS = ("Index", "Middle", "Ring", "Little")

# Two hands, as the lab's own studies ran the task: squares 1 to 4 are
# the left middle, left index, right index and right middle fingers,
# the fingers that rest on V, B, N and M. Two-hand play numbers the
# right hand's lanes 0 to 3 and the left's 4 to 7, index first.
TWO_HAND_LANES = (5, 4, 0, 1)
TWO_HAND_LABELS = ("L middle", "L index", "R index", "R middle")

# The script's columns, in its order. Extra columns go after these.
PERF_COLUMNS = ["participant", "age", "gender", "musical_experience",
                "group", "phase", "block", "trial", "seq_position",
                "target_lane", "response_key", "accuracy", "rt_ms",
                "isi_before_ms", "monitor_hz"]
PERF_EXTRA = ["hand", "setup", "learning_isi_ms", "sequence", "input",
              "response_finger", "onset_s", "rsi_ms"]


@dataclass
class Step:
    kind: str                     # message | block | recall | saved
    key: str = ""                 # which message
    phase: str = ""               # practice | learning | posttest
    block: int = 0
    targets: list = field(default_factory=list)   # squares 1..4
    isis: list = field(default_factory=list)      # ms after each trial
    feedback: bool = False


@dataclass
class Trial:
    index: int                    # 0-based within its block
    square: int                   # 1..4
    isi_before_ms: int | None     # None on a block's first trial
    flash_due: float              # flip time the flash is due on
    prev_end: float               # flip that ended the trial before
    state: str = "wait"           # wait | respond
    armed_at: float | None = None     # update time the flash was drawn
    armed_flip: float | None = None   # flip the flash was drawn for
    onset: float | None = None        # flip that showed it
    tone_played: bool = False
    early: list = field(default_factory=list)
    press: PressEvent | None = None
    press_square: int | None = None
    source: str = ""
    rt_ms: float | None = None


class SRTMode:
    name = "SRT"

    def __init__(self, engine: "GameEngine", setup: SRTSetup, *,
                 random_trials: int = 48, learning_blocks: int = 8,
                 learning_reps: int = 10, random_isi_ms: int = 500,
                 first_wait_ms: int = 1000, flash_ms: int = 100,
                 deadline_ms: int = 2500, anticipation_ms: int = 100,
                 miss_pause_ms: int = 200, feedback_ms: int = 200,
                 recall_select_ms: int = 150, saved_hold_s: float = 1.5,
                 stim_code: int = 30, response_markers: bool = False,
                 tone_files: list[Path] | None = None,
                 tone_volume: float = 1.0, tone_lead_ms: float = 0.0,
                 labels: list[str] | None = None,
                 musical_experience: int | None = None,
                 seed: int = 0, demo_trials: int | None = None) -> None:
        self.engine = engine
        self.setup = setup
        self.seq = tuple(int(s) for s in setup.sequence)
        self.random_trials = int(random_trials)
        self.learning_blocks = int(learning_blocks)
        self.learning_reps = int(learning_reps)
        self.random_isi_ms = int(random_isi_ms)
        self.first_wait_s = first_wait_ms / 1000.0
        self.flash_s = flash_ms / 1000.0
        self.window_s = (flash_ms + deadline_ms) / 1000.0
        self.anticipation_s = anticipation_ms / 1000.0
        self.miss_pause_s = miss_pause_ms / 1000.0
        self.feedback_s = feedback_ms / 1000.0
        self.recall_select_s = recall_select_ms / 1000.0
        self.saved_hold_s = float(saved_hold_s)
        self.stim_code = int(stim_code)
        self.response_markers = bool(response_markers)
        self.tone_files = [Path(p) for p in (tone_files or [])]
        self.tone_volume = float(tone_volume)
        self.tone_lead_s = max(0.0, float(tone_lead_ms)) / 1000.0
        self._labels_override = list(labels) if labels else None
        self.two_hands = getattr(setup, "hands", "one") == "two"
        self.musical_experience = musical_experience
        self.seed = int(seed)
        self.demo = demo_trials is not None
        self.demo_trials = int(demo_trials) if demo_trials else None
        self.rng = random.Random(self.seed)
        # Swappable clock, so a test can step frames by hand.
        self._clock = time.perf_counter
        self.steps = self._build_steps()
        self.step_i = 0
        self._presses: deque[PressEvent] = deque()
        self._advance = False
        self.trial: Trial | None = None
        self._block_start_flip: float | None = None
        self._block_done_at: float | None = None
        self._last_end: float | None = None
        self._feedback: tuple[str, tuple, float, float] | None = None
        self._flash_now: int | None = None
        self._fb_now: tuple | None = None
        # Recall state.
        self.recalled: list[int] = []
        self._select: tuple[int, float] | None = None
        self.recall_done = False
        self._saved_until: float | None = None
        self.done = False
        # Data.
        self.perf_rows: list[dict] = []
        self.trial_counter = 0
        self._frame_hist: list[float] = []
        # Set on the first frame, from the clock the frames run on.
        self.t_start: float | None = None
        self.t_end: float | None = None

    # ---- the script, as a list of steps ------------------------------------
    def _build_steps(self) -> list[Step]:
        """The whole session in the script's order. Random material is
        drawn here, once, from the seeded generator, in the order the
        script drew it (practice, each learning block's intervals,
        post-test), so a session can be rebuilt from its seed."""
        n_rand = self.demo_trials or self.random_trials
        n_blocks = 2 if self.demo else self.learning_blocks
        reps = 1 if self.demo else self.learning_reps
        self.n_blocks = n_blocks
        steps = [Step("message", key="welcome"),
                 Step("message", key="practice")]
        practice = random_targets(n_rand, self.rng)
        steps.append(Step("block", phase="practice", block=1,
                          targets=practice,
                          isis=[self.random_isi_ms] * len(practice),
                          feedback=True))
        steps.append(Step("message", key="main"))
        for b in range(1, n_blocks + 1):
            steps.append(Step("message", key="block", block=b))
            targets = list(self.seq) * reps
            isis = isi_list(self.setup.group, int(self.setup.isi_ms),
                            len(targets), len(self.seq), self.rng)
            steps.append(Step("block", phase="learning", block=b,
                              targets=targets, isis=isis))
        steps.append(Step("message", key="final"))
        post = random_targets(n_rand, self.rng)
        steps.append(Step("block", phase="posttest", block=1,
                          targets=post,
                          isis=[self.random_isi_ms] * len(post)))
        steps.append(Step("message", key="recall_intro"))
        steps.append(Step("recall"))
        steps.append(Step("saved"))
        steps.append(Step("message", key="thanks"))
        return steps

    @property
    def step(self) -> Step | None:
        if 0 <= self.step_i < len(self.steps):
            return self.steps[self.step_i]
        return None

    @property
    def n_trials_total(self) -> int:
        return sum(len(s.targets) for s in self.steps if s.kind == "block")

    # ---- input -------------------------------------------------------------
    @property
    def on_pads(self) -> bool:
        src = getattr(self.engine, "source", None)
        return bool(getattr(src, "provides_samples", False))

    def labels(self) -> list[str]:
        """What sits under each square: the script's key letters on a
        keyboard, the finger on the pads (mirrored for the left hand,
        whose little finger is the leftmost)."""
        if self._labels_override and len(self._labels_override) == 4:
            return list(self._labels_override)
        if not self.on_pads:
            return [c.upper() for c in LETTERS]
        if self.two_hands:
            return list(TWO_HAND_LABELS)
        if self._response_hand() == "left":
            return list(reversed(FINGERS))
        return list(FINGERS)

    def _response_hand(self) -> str:
        if self.two_hands:
            return "both"
        hand = getattr(self.engine, "hand_mode", "right")
        return "left" if hand == "left" else "right"

    def lane_to_square(self, lane: int) -> int | None:
        """Square 1..4 for a pressed lane, or None for a lane that
        does not answer (a ring or little finger with two hands, the
        left hand in two-hand play with one hand answering)."""
        hand = getattr(self.engine, "hand_mode", "right")
        lane = int(lane)
        if self.two_hands:
            return (TWO_HAND_LANES.index(lane) + 1
                    if lane in TWO_HAND_LANES else None)
        if hand == "both":
            return lane + 1 if 0 <= lane < 4 else None
        if not 0 <= lane < 4:
            return None
        if hand == "left":
            return 4 - lane
        return lane + 1

    def square_to_lane(self, square: int) -> int:
        if self.two_hands:
            return TWO_HAND_LANES[int(square) - 1]
        if getattr(self.engine, "hand_mode", "right") == "left":
            return 4 - int(square)
        return int(square) - 1

    def queue_press(self, ev: PressEvent) -> None:
        self._presses.append(ev)

    def _key_lane(self, key: int) -> int | None:
        """The lane a key stands for: the hand's keymap first, then the
        script's V B N M, which answer in every hand mode."""
        km = self.engine.cfg.get(
            keymap_for_hand(getattr(self.engine, "hand_mode", "right")), {})
        for key_name, lane in (km or {}).items():
            if resolve_key(key_name) == key:
                return int(lane)
        for i, letter in enumerate(LETTERS):
            if resolve_key(letter) == key:
                return self.square_to_lane(i + 1)
        return None

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.MOUSEBUTTONDOWN and getattr(e, "button", 0) == 1:
            step = self.step
            if step is not None and step.kind == "recall":
                sq = self._square_at(getattr(e, "pos", (-1, -1)))
                if sq is not None:
                    self._recall_add(sq, self._clock())
            return
        if e.type != pygame.KEYDOWN:
            return
        lane = self._key_lane(e.key)
        if lane is not None:
            t_perf = self._clock()
            hand = getattr(self.engine, "hand_mode", "right")
            self.queue_press(PressEvent(lane=lane, t_perf=t_perf, value=0,
                                        baseline=0.0, hand=hand))
            # Keyboard presses bypass engine._on_press, which is where
            # sensor presses reach raw.csv; mark them the same way the
            # other modes do so a keyboard press is never mistaken for
            # a pad press.
            raw = getattr(self.engine, "raw_logger", None)
            if raw:
                raw.queue_event("press", lane=lane, t_perf=t_perf,
                                hand=hand, detail="keyboard")
            return
        step = self.step
        if step is None:
            return
        if step.kind == "message" and e.key == pygame.K_SPACE:
            self._advance = True
        elif step.kind == "recall":
            now = self._clock()
            if self._select is not None and now < self._select[1]:
                return
            if e.key == pygame.K_BACKSPACE and self.recalled:
                self.recalled.pop()
            elif (e.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                            pygame.K_SPACE)
                  and len(self.recalled) == len(self.seq)):
                self.recall_done = True

    # ---- the flip clock ------------------------------------------------------
    def _frame(self) -> float:
        fp = getattr(self.engine, "frame_period_s", None)
        if isinstance(fp, (int, float)) and 1 / 250 <= fp <= 1 / 20:
            return float(fp)
        return 1 / 60

    def _next_flip(self, now: float, frame: float) -> float:
        """When the frame being built now will reach the screen: one
        frame after the last flip. Without a flip clock (tests, a
        stalled loop) the answer is now."""
        lf = getattr(self.engine, "last_flip_t", None)
        if not isinstance(lf, (int, float)) or not 0 <= now - lf < 1.5 * frame:
            return now
        return lf + frame

    def _flip_since(self, t: float) -> float | None:
        lf = getattr(self.engine, "last_flip_t", None)
        if isinstance(lf, (int, float)) and lf >= t:
            return float(lf)
        return None

    def on_resume(self, pause_dur: float) -> None:
        tr = self.trial
        if tr is not None:
            for attr in ("flash_due", "prev_end", "armed_at", "armed_flip",
                         "onset"):
                v = getattr(tr, attr)
                if v is not None:
                    setattr(tr, attr, v + pause_dur)
            tr.early = []
        for attr in ("_block_done_at", "_saved_until", "_last_end",
                     "_block_start_flip"):
            v = getattr(self, attr)
            if v is not None:
                setattr(self, attr, v + pause_dur)
        if self._feedback is not None:
            text, colour, a, b = self._feedback
            self._feedback = (text, colour, a + pause_dur, b + pause_dur)
        self._presses.clear()

    # ---- main tick -------------------------------------------------------------
    def update(self, dt: float) -> None:
        now = self._clock()
        if self.t_start is None:
            self.t_start = now
        frame = self._frame()
        nf = self._next_flip(now, frame)
        if 0.0 < dt < 0.1:
            self._frame_hist.append(dt)
            if len(self._frame_hist) > 240:
                del self._frame_hist[:120]
        self._flash_now = None
        self._fb_now = None
        step = self.step
        if step is None or self.done:
            self._presses.clear()
            return
        if step.kind == "message":
            self._presses.clear()
            if self._advance:
                self._advance = False
                self._next_step(now, nf)
            return
        if step.kind == "block":
            self._update_block(step, now, nf, frame)
            return
        if step.kind == "recall":
            while self._presses:
                ev = self._presses.popleft()
                sq = self.lane_to_square(ev.lane)
                if sq is not None:
                    self._recall_add(sq, now)
            if self._select is not None and now >= self._select[1]:
                self._select = None
            if self.recall_done:
                self._next_step(now, nf)
            return
        if step.kind == "saved":
            self._presses.clear()
            if self._saved_until is None:
                self._saved_until = now + self.saved_hold_s
            elif now >= self._saved_until:
                self._next_step(now, nf)
            return

    def _next_step(self, now: float, nf: float) -> None:
        self._advance = False
        self._presses.clear()
        self.trial = None
        self._feedback = None
        self._block_done_at = None
        self.step_i += 1
        step = self.step
        if step is None:
            self._finish()
            return
        if step.kind == "block":
            # The script's first ISI frame is the first flip after the
            # key that started the block.
            self._block_start_flip = nf
            self._last_end = nf
            self.trial = self._make_trial(step, 0, nf)

    def _finish(self) -> None:
        if self.done:
            return
        self.done = True
        self.t_end = self._clock()
        self.engine.finish_block()

    # ---- blocks ------------------------------------------------------------------
    def _make_trial(self, step: Step, i: int, after: float,
                    post_s: float = 0.0) -> Trial:
        """Trial i of the block, its flash due one frame after the
        interval that follows `after` (the flip that ended the last
        trial, or the block's first flip)."""
        frame = self._frame()
        if i == 0:
            isi_before = None
            due = after + self.first_wait_s
        else:
            isi_before = int(step.isis[i - 1])
            due = after + post_s + isi_before / 1000.0 + frame
        return Trial(index=i, square=int(step.targets[i]),
                     isi_before_ms=isi_before, flash_due=due,
                     prev_end=after)

    def _update_block(self, step: Step, now: float, nf: float,
                      frame: float) -> None:
        tr = self.trial
        if tr is None:
            if self._block_done_at is not None:
                self._show_feedback_state(nf, frame)
                self._presses.clear()
                if nf >= self._block_done_at + frame - frame / 2:
                    self._next_step(now, nf)
                return
            tr = self.trial = self._make_trial(step, 0, nf)
        # 1. The flip that showed the flash, once it has happened.
        if tr.state == "respond" and tr.onset is None:
            flip = self._flip_since(tr.armed_at)
            if flip is not None:
                tr.onset = flip
            elif getattr(self.engine, "last_flip_t", None) is None:
                tr.onset = tr.armed_flip
            if tr.onset is not None:
                raw = getattr(self.engine, "raw_logger", None)
                if raw:
                    raw.queue_event(
                        "stim", lane=self.square_to_lane(tr.square),
                        t_perf=tr.onset,
                        hand=getattr(self.engine, "hand_mode", "right"),
                        detail=f"srt sq={tr.square}")
        # 2. Presses held from the anticipation window.
        if tr.state == "respond" and tr.onset is not None and tr.early:
            early, tr.early = tr.early, []
            for ev in early:
                self._consider(tr, ev)
        # 3. New presses.
        while self._presses:
            ev = self._presses.popleft()
            if tr.state == "wait" or tr.onset is None:
                # Too early to be anything: dropped, like the script's
                # buffer flush. Near the flash: held until the flip
                # time is known, then judged against it.
                if ev.t_perf >= tr.flash_due - self.anticipation_s - 2 * frame:
                    tr.early.append(ev)
            else:
                self._consider(tr, ev)
        # 4. Move on.
        self._show_feedback_state(nf, frame)
        if tr.state == "wait":
            if (self.tone_lead_s > 0 and not tr.tone_played
                    and now >= tr.flash_due - self.tone_lead_s - frame / 2):
                self._play_tone(tr.square)
            if nf >= tr.flash_due - frame / 2:
                self._arm_flash(tr, now, nf)
            return
        ref = tr.onset if tr.onset is not None else tr.armed_flip
        if tr.press is not None and tr.onset is not None:
            if nf < ref + self.flash_s - frame / 2:
                self._flash_now = tr.square
            self._end_trial(step, tr, now, nf, frame)
            return
        if tr.onset is not None and nf >= tr.onset + self.window_s - frame / 2:
            self._end_trial(step, tr, now, nf, frame)
            return
        if nf < ref + self.flash_s - frame / 2:
            self._flash_now = tr.square

    def _arm_flash(self, tr: Trial, now: float, nf: float) -> None:
        tr.state = "respond"
        tr.armed_at = now
        tr.armed_flip = nf
        self._flash_now = tr.square
        if not tr.tone_played:
            self._play_tone(tr.square)
        # The byte rides the flip that shows the red square: armed now,
        # written by the frame loop straight after the flip.
        pending = getattr(self.engine, "_pending_eeg_stim", None)
        if isinstance(pending, list):
            pending.append((self.stim_code, self.square_to_lane(tr.square)))
        else:
            send = getattr(self.engine, "_eeg_send", None)
            if callable(send):
                send(self.stim_code, lane=self.square_to_lane(tr.square),
                     t_event=nf)

    def _play_tone(self, square: int) -> None:
        tr = self.trial
        if tr is not None:
            tr.tone_played = True
        audio = getattr(self.engine, "audio", None)
        if audio is None or not self.tone_files:
            return
        path = self.tone_files[(int(square) - 1) % len(self.tone_files)]
        play = getattr(audio, "play_sample", None)
        if callable(play):
            try:
                play(path, self.tone_volume)
            except Exception as e:
                log.debug("srt tone failed: %s", e)

    def _consider(self, tr: Trial, ev: PressEvent) -> None:
        """First press from 100 ms before the flash to the deadline
        answers the trial; the rest are ignored, as the script only
        ever read one key per trial."""
        if tr.press is not None or tr.onset is None:
            return
        rt = (ev.t_perf - tr.onset) * 1000.0
        if rt < -self.anticipation_s * 1000.0 or rt > self.window_s * 1000.0:
            return
        sq = self.lane_to_square(ev.lane)
        if sq is None:
            return
        tr.press = ev
        tr.press_square = sq
        tr.rt_ms = rt
        tr.source = "pad" if float(getattr(ev, "value", 0) or 0) > 0 else "key"

    def _accuracy(self, tr: Trial) -> str:
        """The script's labels, in the script's order of tests."""
        if tr.press is None:
            return "miss"
        if tr.rt_ms < -self.anticipation_s * 1000.0:
            return "too_early"
        if tr.press_square == tr.square:
            return "anticipatory_correct" if tr.rt_ms < 0 else "correct"
        return "anticipatory_incorrect" if tr.rt_ms < 0 else "incorrect"

    def _end_trial(self, step: Step, tr: Trial, now: float, nf: float,
                   frame: float) -> None:
        acc = self._accuracy(tr)
        end = nf
        pause = self.miss_pause_s if acc == "miss" else 0.0
        fb_text, fb_colour = "", (255, 255, 255)
        if step.feedback:
            if acc == "miss":
                fb_text, fb_colour = "Miss!", (255, 255, 255)
            elif acc in ("correct", "anticipatory_correct"):
                fb_text, fb_colour = "Correct", (0, 128, 0)
            elif acc in ("incorrect", "anticipatory_incorrect"):
                fb_text, fb_colour = "Incorrect", (255, 0, 0)
        post = pause + (self.feedback_s if fb_text else 0.0)
        self._feedback = ((fb_text, fb_colour, end + pause + frame,
                           end + pause + self.feedback_s + frame)
                          if fb_text else None)
        self._log_trial(step, tr, acc, end)
        self._last_end = end
        nxt = tr.index + 1
        if nxt < len(step.targets):
            self.trial = self._make_trial(step, nxt, end, post)
        else:
            self.trial = None
            self._block_done_at = end + post

    def _show_feedback_state(self, nf: float, frame: float) -> None:
        """Whether this frame carries the practice feedback word: from
        the flip after the miss pause, for 200 ms of flips."""
        fb = self._feedback
        self._fb_now = None
        if fb is None:
            return
        if nf >= fb[3] - frame / 2:
            self._feedback = None
        elif nf >= fb[2] - frame / 2:
            self._fb_now = (fb[0], fb[1])

    @property
    def feedback_now(self) -> tuple | None:
        """(text, colour) when this frame shows the feedback word."""
        return self._fb_now

    @property
    def flash_square(self) -> int | None:
        """The square drawn red on this frame, or None."""
        return self._flash_now

    # ---- logging -------------------------------------------------------------------
    def _participant_fields(self) -> dict:
        sess = getattr(self.engine, "session", None)
        return {
            "participant": getattr(sess, "participant", "") or "",
            "age": getattr(sess, "age", "") or "",
            "gender": getattr(sess, "sex", "") or "",
            "musical_experience": ("" if self.musical_experience is None
                                   else int(self.musical_experience)),
        }

    def monitor_hz(self) -> int:
        fp = getattr(self.engine, "frame_period_s", None)
        if not isinstance(fp, (int, float)) or fp <= 0:
            hist = sorted(self._frame_hist)
            fp = hist[len(hist) // 2] if hist else 1 / 60
        return int(round(1.0 / fp))

    def _log_trial(self, step: Step, tr: Trial, acc: str,
                   end: float) -> None:
        self.trial_counter += 1
        seq_pos = (tr.index % len(self.seq)) + 1
        lane_target = self.square_to_lane(tr.square)
        lane_press = (None if tr.press is None
                      else int(tr.press.lane))
        t0 = getattr(self.engine, "_block_t0", None) or self.t_start or 0.0
        onset = tr.onset if tr.onset is not None else tr.armed_flip
        row = dict(self._participant_fields())
        row.update({
            "group": self.setup.group,
            "phase": step.phase,
            "block": step.block,
            "trial": tr.index + 1,
            "seq_position": seq_pos,
            "target_lane": LETTERS[tr.square - 1],
            "response_key": (LETTERS[tr.press_square - 1]
                             if tr.press_square else "none"),
            "accuracy": acc,
            "rt_ms": ("" if tr.rt_ms is None else round(tr.rt_ms, 2)),
            "isi_before_ms": ("" if tr.isi_before_ms is None
                              else tr.isi_before_ms),
            "monitor_hz": self.monitor_hz(),
            "hand": self._response_hand(),
            "setup": self.setup.name,
            "learning_isi_ms": int(self.setup.isi_ms),
            "sequence": sequence_text(self.seq),
            "input": tr.source if tr.press is not None else "",
            "response_finger": self._finger_name(lane_press),
            "onset_s": ("" if onset is None else round(onset - t0, 4)),
            "rsi_ms": ("" if onset is None
                       else round((onset - tr.prev_end) * 1000.0, 1)),
        })
        self.perf_rows.append(row)
        hit = acc in ("correct", "anticipatory_correct")
        stim = (f"srt;{step.phase};b={step.block};pos={seq_pos};"
                f"sq={tr.square};isi={row['isi_before_ms']};"
                f"group={self.setup.group};learn_isi={int(self.setup.isi_ms)}")
        # trials.csv speaks the app's vocabulary, so the notebook's
        # generic hit rate (anything but Miss) reads these rows right:
        # a wrong finger is a Miss with had_incorrect_press, as in
        # Classic. The script's own label rides in feedback and
        # error_type, and verbatim in the lab-format file.
        label = {"correct": "Hit",
                 "anticipatory_correct": "Early"}.get(acc, "Miss")
        csv_row = {
            "trial": self.trial_counter,
            "lane": lane_target + 1,
            "time_difference_ms": ("" if tr.rt_ms is None
                                   else f"{tr.rt_ms:.1f}"),
            "early_late": label,
            "feedback": acc,
            "error_type": "" if acc == "correct" else acc,
            "keys_pressed": "" if lane_press is None else str(lane_press + 1),
            "correct_keys": str(lane_target + 1),
            "num_presses": 0 if lane_press is None else 1,
            "had_incorrect_press": ("TRUE" if acc in (
                "incorrect", "anticipatory_incorrect") else "FALSE"),
            "first_incorrect_ms": ("" if acc not in (
                "incorrect", "anticipatory_incorrect")
                else f"{tr.rt_ms:.1f}"),
            "first_incorrect_lane": ("" if acc not in (
                "incorrect", "anticipatory_incorrect")
                else str(lane_press + 1)),
            "timeout_ms": f"{self.window_s * 1000.0:.0f}",
            "stimulus": stim,
        }
        log_row = getattr(self.engine, "log_srt_trial", None)
        if callable(log_row):
            log_row(csv_row, hit=hit)
        if self.response_markers:
            self._response_marker(tr, acc)

    def _finger_name(self, lane: int | None):
        """The finger that answered, 1 index to 4 little; with two
        hands, L or R in front of it."""
        if lane is None:
            return ""
        if self.two_hands:
            return f"{'L' if lane >= 4 else 'R'}{lane % 4 + 1}"
        return lane % 4 + 1

    def _response_marker(self, tr: Trial, acc: str) -> None:
        send = getattr(self.engine, "_eeg_send", None)
        if not callable(send):
            return
        if tr.press is None:
            send(EEG_CODES["resp_timeout"])
            return
        kind = {"correct": "correct", "incorrect": "wrong"}.get(
            acc, "anticipation")
        lane = int(tr.press.lane)
        send(response_code(kind, lane), lane=lane, t_event=tr.press.t_perf)

    # ---- recall -------------------------------------------------------------------
    def _recall_add(self, square: int, now: float) -> None:
        if self._select is not None and now < self._select[1]:
            return
        if len(self.recalled) >= len(self.seq):
            return
        self.recalled.append(int(square))
        self._select = (int(square), now + self.recall_select_s)

    @property
    def select_square(self) -> int | None:
        if self._select is None:
            return None
        return self._select[0] if self._clock() < self._select[1] else None

    def square_rects(self, width: int, height: int) -> list[pygame.Rect]:
        """The script's squares in its norm units over a width x height
        window: 0.13 wide and high, centres at x -0.225 -0.075 0.075
        0.225, y 0."""
        out = []
        w = int(round(0.13 * width / 2))
        h = int(round(0.13 * height / 2))
        for x_norm in (-0.225, -0.075, 0.075, 0.225):
            cx = (x_norm + 1.0) / 2.0 * width
            cy = height / 2.0
            r = pygame.Rect(0, 0, w, h)
            r.center = (int(round(cx)), int(round(cy)))
            out.append(r)
        return out

    def _square_at(self, pos) -> int | None:
        layout = getattr(self.engine, "layout", None)
        w = getattr(layout, "width", 1280)
        h = getattr(layout, "height", 800)
        for i, r in enumerate(self.square_rects(w, h)):
            if r.collidepoint(pos):
                return i + 1
        return None

    # ---- words ----------------------------------------------------------------------
    def instruction(self) -> str:
        what = "finger" if self.on_pads else "key"
        return f"Press the {what} that matches the flashing square as fast as you can"

    def message_text(self, step: Step | None = None) -> str:
        step = step or self.step
        if step is None:
            return ""
        pads = self.on_pads
        which = ("finger\nas quickly as you can." if pads
                 else "key\n(V, B, N, or M) as quickly as you can.")
        what = "finger" if pads else "key"
        texts = {
            "welcome": ("Welcome to the experiment.\n\n"
                        "Four grey squares will appear on screen.\n"
                        f"When a square flashes RED, press the matching {which}"
                        "\n\nPress SPACE to begin."),
            "practice": ("PRACTICE\n\n"
                         "Get familiar with the task.\n"
                         f"Press the {what} that matches the red square "
                         "as fast as you can.\n\n"
                         "Press SPACE to start."),
            "main": ("MAIN TASK\n\n"
                     "You will now complete several blocks.\n"
                     "Keep responding to the flashing square as fast "
                     "as you can.\n\n"
                     "Press SPACE to start."),
            "block": (f"Block {step.block} of {self.n_blocks}\n\n"
                      "Press SPACE when ready."),
            "final": ("FINAL PHASE\n\n"
                      "Almost done! One last set of trials.\n\n"
                      "Press SPACE to start."),
            "recall_intro": ("SEQUENCE RECALL\n\n"
                             "You will now answer one final question.\n\n"
                             "Press SPACE to continue."),
            "thanks": ("Thank you for participating!\n"
                       "The task is now complete.\n\n"
                       "Press SPACE to finish."),
        }
        return texts.get(step.key, "")

    def recall_text(self) -> str:
        n = len(self.seq)
        enter = ("Press the matching fingers" if self.on_pads
                 else "Press V, B, N, or M")
        return ("Did you notice a repeating sequence during the main task?"
                "\n\n"
                f"{enter} to enter the {n}-item sequence you learned.\n\n"
                "Press BACKSPACE to remove your last entry. "
                f"Press ENTER or SPACE to submit when all {n} items "
                "are entered.\n\n"
                "If you are unsure, please guess.")

    def recall_progress(self) -> str:
        labels = self.labels()
        names = [labels[s - 1] for s in self.recalled]
        return (f"Items entered: {len(self.recalled)} / {len(self.seq)}"
                f"\n\nYour sequence: {' - '.join(names)}")

    def recall_hint(self) -> tuple[str, tuple[int, int, int]] | None:
        if len(self.recalled) == len(self.seq):
            return ("Press ENTER or SPACE to submit  |  BACKSPACE to undo",
                    (0, 255, 0))
        if self.recalled:
            return ("BACKSPACE = undo last entry", (255, 255, 255))
        return None

    # ---- exports ---------------------------------------------------------------------
    @staticmethod
    def _safe(text: str) -> str:
        out = "".join(c if (c.isalnum() or c in "-_") else "_"
                      for c in str(text or "").strip())
        return out.strip("_") or "NA"

    def export_files(self, folder: Path) -> list[Path]:
        """The script's three files in `folder`, named as the script
        named them. The recall file only once a recall was submitted.
        Returns the paths written."""
        folder = Path(folder)
        written: list[Path] = []
        who = self._safe(self._participant_fields()["participant"])
        group = self._safe(self.setup.group)
        ts = time.strftime("%Y-%m-%d_%Hh%M.%S",
                           time.localtime())
        try:
            folder.mkdir(parents=True, exist_ok=True)
            perf = folder / f"SRT_{who}_{group}_{ts}.csv"
            with perf.open("w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=PERF_COLUMNS + PERF_EXTRA)
                w.writeheader()
                for row in self.perf_rows:
                    w.writerow({k: row.get(k, "") for k in
                                PERF_COLUMNS + PERF_EXTRA})
            written.append(perf)
            seq_file = folder / f"SRT_SEQUENCE_{who}_{ts}.csv"
            pattern = cyclical_pattern(int(self.setup.isi_ms), len(self.seq))
            participant = self._participant_fields()["participant"]
            with seq_file.open("w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["participant", "seq_position", "finger",
                            "cyclical_isi_after_ms"])
                for pos, (sq, isi) in enumerate(zip(self.seq, pattern),
                                                start=1):
                    w.writerow([participant, pos, LETTERS[sq - 1], isi])
            written.append(seq_file)
            if self.recall_done:
                rec = folder / f"SRT_RECALL_{who}_{group}_{ts}.csv"
                with rec.open("w", newline="", encoding="utf-8") as f:
                    w = csv.writer(f)
                    w.writerow(["participant", "position", "recalled_finger",
                                "actual_finger", "correct"])
                    for pos, (got, want) in enumerate(
                            zip(self.recalled, self.seq), start=1):
                        w.writerow([participant, pos, LETTERS[got - 1],
                                    LETTERS[want - 1], int(got == want)])
                written.append(rec)
        except OSError as e:
            log.warning("SRT export to %s failed: %s", folder, e)
        return written

    # ---- block summary -----------------------------------------------------------------
    @staticmethod
    def _median(xs: list[float]) -> float | None:
        xs = sorted(xs)
        n = len(xs)
        if not n:
            return None
        mid = n // 2
        return xs[mid] if n % 2 else (xs[mid - 1] + xs[mid]) / 2.0

    # RTs over this are left out of the RT measures, as the lab's own
    # SRT studies did (Leow et al. 2025 and 2026). The trial stays in
    # the file and in the accuracy counts.
    RT_MAX_MS = 1000.0

    def _rts(self, phase: str, block: int | None = None,
             isi: int | None = None) -> list[float]:
        """Correct RTs (the script's 'correct', anticipations and
        errors out), without each block's first trial, whose wait is
        the 1 s block start, and without RTs over RT_MAX_MS. With
        `isi`, only trials that followed an interval of that length."""
        out = []
        for r in self.perf_rows:
            if (r["phase"] != phase or r["accuracy"] != "correct"
                    or r["rt_ms"] == "" or r["trial"] == 1):
                continue
            if block is not None and r["block"] != block:
                continue
            if isi is not None and r["isi_before_ms"] != isi:
                continue
            rt = float(r["rt_ms"])
            if rt <= self.RT_MAX_MS:
                out.append(rt)
        return out

    def _phase_stats(self, phase: str, block: int | None = None) -> dict:
        rows = [r for r in self.perf_rows if r["phase"] == phase
                and (block is None or r["block"] == block)]
        n = len(rows)
        med = self._median(self._rts(phase, block))

        def count(label):
            return sum(1 for r in rows if r["accuracy"] == label)
        right = count("correct") + count("anticipatory_correct")
        wrong = count("incorrect") + count("anticipatory_incorrect")
        return {
            "n": n,
            "accuracy": round(right / n, 3) if n else None,
            "error_rate": round(wrong / n, 3) if n else None,
            "median_rt_ms": None if med is None else round(med, 1),
            "n_miss": count("miss"),
            "n_incorrect": count("incorrect"),
            "n_anticipatory": (count("anticipatory_correct")
                               + count("anticipatory_incorrect")),
            "anticipatory_correct_rate": (
                round(count("anticipatory_correct") / n, 3) if n else None),
        }

    def block_stats(self) -> dict:
        """What metadata.json records for the session: the setup, each
        phase and learning block, the learning measures and the
        recall. RTs are the lab's: correct trials only, each block's
        first trial out, nothing over 1000 ms; medians, because RT
        distributions are skewed. The measures follow the research
        file's Section 4 (docs/research/new_modes/
        srt-sequence-learning.md)."""
        blocks = [self._phase_stats("learning", b)
                  for b in range(1, self.n_blocks + 1)]
        practice = self._phase_stats("practice")
        post = self._phase_stats("posttest")
        last = blocks[-1]["median_rt_ms"] if blocks else None
        first = blocks[0]["median_rt_ms"] if blocks else None
        post_rt = post["median_rt_ms"]
        sl = (None if post_rt is None or last is None
              else round(post_rt - last, 1))
        # The post-test always runs at the random blocks' interval, so
        # outside a constant 500 ms setup it changes the rhythm as well
        # as the order. The matched effect compares it with only the
        # last block's trials that followed that same interval.
        matched = self._median(self._rts("learning", self.n_blocks,
                                         isi=self.random_isi_ms))
        sl_matched = (None if post_rt is None or matched is None
                      else round(post_rt - matched, 1))
        speedup = (None if first is None or last is None
                   else round(first - last, 1))
        cost = (None if not blocks or post["error_rate"] is None
                or blocks[-1]["error_rate"] is None
                else round(post["error_rate"] - blocks[-1]["error_rate"], 3))
        n_right = sum(1 for r in self.perf_rows
                      if r["accuracy"] in ("correct",
                                           "anticipatory_correct"))
        n_all = len(self.perf_rows)
        scores = (recall_scores(self.recalled, self.seq)
                  if self.recall_done else {})
        recall_correct = scores.get("positional")
        audio_latency = None
        try:
            audio_latency = self.engine.cfg.get("latency.tone_ms", None)
        except Exception:
            pass
        start = self.t_start if self.t_start is not None else self._clock()
        duration = (self.t_end or self._clock()) - start
        return {
            "setup": self.setup.to_dict(),
            "group": self.setup.group,
            "hands": "two" if self.two_hands else "one",
            "learning_isi_ms": int(self.setup.isi_ms),
            "sequence": sequence_text(self.seq),
            "sequence_letters": sequence_text(self.seq, letters=True),
            "lab_sequence": self.setup.is_lab_sequence,
            "random_trials": self.demo_trials or self.random_trials,
            "learning_blocks": self.n_blocks,
            "learning_reps": 1 if self.demo else self.learning_reps,
            "demo": self.demo,
            "seed": self.seed,
            "stim_code": self.stim_code,
            "response_markers": self.response_markers,
            "monitor_hz": self.monitor_hz(),
            "tone_latency_ms_config": audio_latency,
            "tone_lead_ms": round(self.tone_lead_s * 1000.0, 1),
            "musical_experience": self.musical_experience,
            "n_trials": n_all,
            "n_planned": self.n_trials_total,
            "accuracy": round(n_right / n_all, 3) if n_all else None,
            "practice": practice,
            "learning": blocks,
            "posttest": post,
            # Post-test random RT minus the last learning block: the
            # cost of losing the sequence, positive when it was learnt
            # (the contrast of Robertson 2007 and Beaulieu et al. 2014).
            "sequence_effect_ms": sl,
            "sequence_effect_matched_ms": sl_matched,
            "sequence_effect_prop": (None if sl is None or not post_rt
                                     else round(sl / post_rt, 3)),
            # First learning block minus the last: general speed-up
            # plus learning, the learning curve's span.
            "learning_speedup_ms": speedup,
            # Post-test error rate minus the last learning block's.
            "accuracy_cost": cost,
            "rt_max_ms": self.RT_MAX_MS,
            "recall": {
                "done": self.recall_done,
                "entered": sequence_text(self.recalled) if self.recalled
                else "",
                "n_correct": recall_correct,
                "of": len(self.seq),
                "triplet": scores.get("triplet"),
                "longest_run": scores.get("longest_run"),
            },
            "duration_s": round(duration, 1),
        }
