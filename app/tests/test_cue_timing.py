"""Cue timing at the frame level.

The cue path is shared, so the timestamps it hands out are what every
reaction time and every asynchrony in the dataset is built from. The
frame loop only notices a deadline on the next frame, and that is
fine, provided the lateness never accumulates: a constant offset folds
into the device constant, a growing one corrupts the measurement.

Syllables is where this bit. The model phase used to schedule each
syllable one IOI after the FRAME that fired the previous one, so
every interval carried the frame delay as a stretch: measured against
a 500 ms grid at 120 fps the intervals averaged 505 ms and the last
syllable of a word drifted up to 25 ms off the grid, worse at 60 Hz.
The deadlines are now absolute (each due time is the previous due
time plus one IOI).

The mode has since moved from tapping the syllable count back to
choosing a written chunk, so the paced response beats these tests
used to check no longer exist and the model's cue is a four-finger
roll through on_stim_multi rather than a single-lane buzz. The grid
itself still matters: the model is the child's one hearing of the
word broken into parts, and a beat that stretches makes a different
stimulus at the end of a long word than at the start.

What these tests pin, driving the mode with a simulated 17 ms frame
clock (a 60 Hz display's worst case, chosen not to divide the 500 ms
IOI so frame lateness cannot hide):
  - every model onset lands within one frame of its grid slot
  - the beat does not stretch across a word, or shift with word length
  - every model cue is a roll over all four fingers, never one lane
  - a stalled loop re-anchors instead of burst-firing catch-up
    syllables the one-motor-per-board hardware could not deliver
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


FRAME_S = 0.017      # a hair over 60 Hz; 500 ms is not a multiple of it


def _build_mode(**overrides):
    """A SyllablesMode wired to a MagicMock engine, driven with
    explicit `now` values through _tick, same shape as the builder in
    test_syllables_mode.py."""
    from finger_rehab.game.modes.syllables import SyllablesMode
    from finger_rehab.game.scoring import ScoreConfig
    engine = MagicMock()
    engine._screens = {}
    engine.hand_mode = "right"
    engine.source.provides_samples = False
    engine.detectors = {}
    engine._peak_force_for_lane = lambda lane: None
    engine.cfg.get = MagicMock(side_effect=lambda k, d=None: d)
    kwargs = dict(
        engine=engine,
        lanes=[0, 1, 2, 3],
        band="A",
        ioi_ms=500,
        words_total=50,
        round_size=10,
        break_s=30.0,
        warmup_taps=0,
        attend_s=0.3,
        tap_debounce_ms=150,
        inter_trial_gap_ms=0,
        session_cap_min=20.0,
        score_cfg=ScoreConfig(),
        speech={"backend": "off"},
        seed=7,
        demo_trials=None,
    )
    kwargs.update(overrides)
    return engine, SyllablesMode(**kwargs)


def _word_with(n_syll: int):
    from finger_rehab.game.modes.syllables_words import WORDS
    return next(w for w in WORDS if w.n_syll == n_syll)


def _model_calls(engine):
    """The model's cue calls only. Every syllable is a four-finger
    roll through on_stim_multi, so the spy that counts the beat is
    that call and not the single-lane on_stim the tapping version
    used. The silent option-set spawn goes through the same method
    with silent_stim set, so calls made outside the model phase are
    filtered out by the caller's guard, not counted here."""
    return engine.on_stim_multi.call_args_list


def _run_frames(engine, mode, n_onsets: int, frame_s: float = FRAME_S):
    """Tick the mode on a fixed frame grid from t=0 until `n_onsets`
    model rolls have fired. Returns (onset times as passed to the cue
    path, the model phase's entry tick)."""
    t = 0.0
    model_t0 = None
    guard = 0
    while engine.on_stim_multi.call_count < n_onsets:
        t += frame_s
        was = mode.phase
        mode._tick(t)
        if was != "model" and mode.phase == "model" and model_t0 is None:
            model_t0 = t
        guard += 1
        if guard > 2000:
            raise AssertionError(
                f"model never produced {n_onsets} onsets, at {mode.phase}")
    onsets = [c.args[2] for c in _model_calls(engine)]
    return onsets, model_t0


class ModelBeatGridTests(unittest.TestCase):
    """The model's pulses and tones must land on the IOI grid. These
    would all fail under the old frame-anchored scheduling."""

    def test_every_onset_lands_within_one_frame_of_its_grid_slot(self):
        engine, mode = _build_mode()
        mode._tick(0.0)
        mode.word = _word_with(4)
        onsets, _ = _run_frames(engine, mode, 4)
        t0 = onsets[0]
        for k, tk in enumerate(onsets):
            dev = abs((tk - t0) - k * mode.ioi_s)
            self.assertLessEqual(
                dev, FRAME_S + 1e-9,
                f"syllable {k} sits {dev * 1000:.1f} ms off the grid; "
                f"frame lateness is accumulating")

    def test_the_beat_does_not_stretch_across_a_word(self):
        # Frame-anchored scheduling stretched EVERY interval by the
        # frame delay, so the word's total span grew by (n-1) frames'
        # worth. On the absolute grid the span stays within one frame
        # of (n-1) IOIs however long the word is.
        engine, mode = _build_mode()
        mode._tick(0.0)
        mode.word = _word_with(4)
        onsets, _ = _run_frames(engine, mode, 4)
        span = onsets[-1] - onsets[0]
        self.assertLessEqual(span, 3 * mode.ioi_s + FRAME_S + 1e-9,
                             f"model span {span * 1000:.1f} ms: the "
                             f"beat is stretching")

    def test_the_grid_holds_on_a_short_word_too(self):
        # The paced respond phase this slot used to test is gone: the
        # choice task scores a press against the tile on screen, not
        # against a beat, so there are no response beats left to sit on
        # the grid. What still has to hold is that the grid is a
        # property of the IOI and not of the word, so a two-syllable
        # word gets the same spacing a four-syllable one does.
        engine, mode = _build_mode()
        mode._tick(0.0)
        mode.word = _word_with(2)
        onsets, model_t0 = _run_frames(engine, mode, 2)
        self.assertIsNotNone(model_t0)
        gap = onsets[1] - onsets[0]
        self.assertLessEqual(
            abs(gap - mode.ioi_s), FRAME_S + 1e-9,
            f"the two onsets sit {gap * 1000:.1f} ms apart, not one IOI")

    def test_every_model_roll_reaches_all_four_fingers(self):
        # The no-hints rule: a single-lane buzz during the model would
        # announce which finger answers that syllable later. Every
        # model cue must therefore be a roll across the whole playing
        # hand, which is also why these tests spy on on_stim_multi.
        engine, mode = _build_mode()
        mode._tick(0.0)
        mode.word = _word_with(4)
        _run_frames(engine, mode, 4)
        for i, call in enumerate(_model_calls(engine)):
            self.assertEqual(sorted(call.args[0]), [0, 1, 2, 3],
                             f"model roll {i} named lanes {call.args[0]}")
        engine.on_stim.assert_not_called()

    def test_a_stalled_loop_reanchors_instead_of_bursting(self):
        # An alt-tab or IO stall can jump the clock past several due
        # times. Catch-up syllables one frame apart would ask the
        # board for overlapping motor pulses, so the grid re-anchors
        # at the stall instead.
        engine, mode = _build_mode()
        mode._tick(0.0)
        mode.word = _word_with(4)
        onsets, _ = _run_frames(engine, mode, 1)
        t1 = onsets[0]
        stall_t = t1 + 1.7                  # more than two IOIs later
        mode._tick(stall_t)
        self.assertEqual(engine.on_stim_multi.call_count, 2,
                         "the stall itself should release one syllable")
        mode._tick(stall_t + FRAME_S)
        self.assertEqual(engine.on_stim_multi.call_count, 2,
                         "catch-up syllables burst out a frame apart")
        mode._tick(stall_t + mode.ioi_s + FRAME_S)
        self.assertEqual(engine.on_stim_multi.call_count, 3,
                         "the beat should resume one IOI after the stall")


class ResearchDefaultStatementTests(unittest.TestCase):
    """The shipped cue defaults (buzzer and tone on before the press)
    are a whole-suite choice. Each research mode's docstring, and the
    cue block in default.yaml, must say plainly what the measured
    quantity becomes under them and that cue_flags is how the analysis
    separates cue conditions. These strings are load-bearing for the
    thesis writeup, so they are pinned like the shipped defaults are."""

    def test_each_research_mode_names_the_multisensory_measure(self):
        import finger_rehab.game.modes.chords as chords
        import finger_rehab.game.modes.pattern as pattern
        import finger_rehab.game.modes.reaction as reaction
        import finger_rehab.game.modes.syllables as syllables
        for mod in (reaction, pattern, chords, syllables):
            with self.subTest(module=mod.__name__):
                doc = mod.__doc__ or ""
                self.assertIn("audio-tactile-visual", doc)
                self.assertIn("cue_flags", doc)

    def test_the_config_comment_carries_the_same_statement(self):
        from finger_rehab.config import DEFAULT_CONFIG
        text = Path(DEFAULT_CONFIG).read_text(encoding="utf-8")
        self.assertIn("audio-tactile-visual", text)
        self.assertIn("cue_flags", text)


if __name__ == "__main__":
    unittest.main()
