"""Tests for Syllable Beats, the children's phonological awareness
mode. The guarantees pinned here are the ones the measurement and the
child's experience depend on: the word list is internally consistent
(splits join back to the spelling, stress indices are real, the level
subsets hold what they claim), each level draws only its own material
and applies only its own criteria, the model lights one finger per
beat through the shared cue path, taps are debounced and scored
against the brief's error taxonomy, paced trials carry signed
asynchronies in the rhythm sign convention, the stress criterion is
relative to the child's own taps and unscorable (not failed) without
force data, errors earn exactly one replay and never a penalty, band
movement follows the 8-of-10 / under-5-of-10 rule and is logged, and
the session ends politely at word boundaries on completion or the
time cap.

The read-across row (2026-08 upgrade) adds its own guarantees: taps
walk physically left to right on ANY hand (a left-hand 2-unit word is
middle then index, the flip from the old index-first rule), spanning
words of 5-8 units exist only in bilateral play and give each
position exactly ONE lane (centred on the midline, littles recruited
last), correct_keys says so, the stimulus carries map=row, the model
buzzes the row in order without consuming the hand bag, the keyboard
equals the sensors (an 8-unit word is the home row typed left to
right), and the long material stays out of every single-hand pool.
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


def _press(lane: int, t: float = 0.0):
    from rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                      hand="right")


def _build_mode(hand_mode: str = "right", **overrides):
    """A SyllablesMode wired to a MagicMock engine, driven with
    explicit `now` values through _tick, following the chords-mode
    test harness. Speech is off (no macOS say in a test), the peak
    helper reports no force data (keyboard reality) unless a test
    installs its own, and the timing knobs are shrunk so a scenario
    runs in a handful of ticks. `hand_mode` keys a single-hand mode
    to that hand (a left session's walk runs the other way)."""
    from rehab.game.modes.syllables import SyllablesMode
    from rehab.game.scoring import ScoreConfig
    engine = MagicMock()
    engine._screens = {}
    engine.hand_mode = hand_mode
    engine.source.provides_samples = False
    engine.detectors = {}
    engine._peak_force_for_lane = lambda lane: None
    engine.cfg.get = MagicMock(side_effect=lambda k, d=None: {
        "game.keyboard_map": {"j": 0, "k": 1, "l": 2, "semicolon": 3},
    }.get(k, d))
    kwargs = dict(
        engine=engine,
        lanes=[0, 1, 2, 3],
        level=1,
        band="A",
        ioi_ms=500,
        words_total=50,
        round_size=10,
        break_s=30.0,
        warmup_taps=0,
        attend_s=0.5,
        free_window_s=6.0,
        count_in_beats=4,
        grace_ms=1000,
        on_beat_window_ms=150,
        stress_ratio=2.0,
        unstressed_max_ratio=1.5,
        tap_debounce_ms=150,
        inter_trial_gap_ms=0,
        session_cap_min=20.0,
        replay_on_error=True,
        speak_words=False,
        say_voice=None,
        score_cfg=ScoreConfig(),
        seed=7,
        demo_trials=None,
    )
    kwargs.update(overrides)
    return engine, SyllablesMode(**kwargs)


def _run_to_respond(mode, t: float = 0.0) -> float:
    """Tick the mode from cold through attend, model and any count-in
    until the respond phase opens. Returns the respond start time."""
    guard = 0
    while mode.phase != "respond":
        mode._tick(t)
        t += 0.1
        guard += 1
        if guard > 500:
            raise AssertionError(f"never reached respond, at {mode.phase}")
    return mode._respond_t0


def _tap_out(mode, lanes, t0: float, gap: float = 0.4) -> float:
    """Queue one tap per lane, `gap` seconds apart, and tick past the
    settle window so the word gets scored. Returns the scoring time."""
    t = t0
    for lane in lanes:
        mode.queue_press(_press(lane, t))
        mode._tick(t)
        t += gap
    t_score = t - gap + mode.SETTLE_S + 0.05
    mode._tick(t_score)
    return t_score


def _logged_stimulus(engine) -> str:
    assert engine.log_trial.called, "no trial was logged"
    return engine.log_trial.call_args.kwargs["stimulus"]


def _logged_outcome(engine):
    return engine.log_trial.call_args.args[1]


class WordListTests(unittest.TestCase):
    """The word list IS the stimulus set. A split that does not join
    back to the spelling would render a broken word on screen; a
    stress index out of range would crash level 4; a subset holding
    the wrong material would make a level train something other than
    what its docstring defends."""

    def test_at_least_eighty_words_and_all_splits_join(self) -> None:
        from rehab.game.modes.syllables_words import WORDS
        self.assertGreaterEqual(len(WORDS), 80)
        for w in WORDS:
            self.assertEqual("".join(w.syllables), w.word, w.word)
            self.assertTrue(0 <= w.stress < w.n_syll, w.word)
            self.assertIn(w.band, ("A", "B", "C"), w.word)

    def test_every_four_syllable_word_is_band_c(self) -> None:
        # The brief's banding rule: 4-syllable words are band C
        # regardless of frequency.
        from rehab.game.modes.syllables_words import WORDS
        for w in WORDS:
            if w.n_syll == 4:
                self.assertEqual(w.band, "C", w.word)

    def test_onset_rime_and_grapheme_cuts_join_to_the_word(self) -> None:
        from rehab.game.modes.syllables_words import (
            ONSET_RIME_WORDS, TRANSPARENT_WORDS)
        self.assertGreaterEqual(len(ONSET_RIME_WORDS), 20)
        self.assertGreaterEqual(len(TRANSPARENT_WORDS), 20)
        for w in ONSET_RIME_WORDS:
            self.assertEqual("".join(w.onset_rime), w.word, w.word)
        for w in TRANSPARENT_WORDS:
            self.assertEqual("".join(w.graphemes), w.word, w.word)
            # Four fingers cap the phoneme count at 4 by design.
            self.assertTrue(2 <= len(w.graphemes) <= 4, w.word)

    def test_level_pools_hold_only_their_material(self) -> None:
        from rehab.game.modes.syllables_words import words_for
        # Level 1 is the counting entry point: no 4-syllable words.
        self.assertTrue(all(w.n_syll <= 3 for w in words_for(1, "A")))
        # Level 2 up adds the 4-syllable words at band C.
        self.assertTrue(any(w.n_syll == 4 for w in words_for(2, "C")))
        # Levels 5 and 6 are their subsets.
        self.assertTrue(all(w.onset_rime for w in words_for(5, "A")))
        self.assertTrue(all(w.graphemes for w in words_for(6, "A")))

    def test_thin_bands_top_up_from_easier_bands(self) -> None:
        # Band C at level 1 holds only the rare 3-syllable words; the
        # pool must borrow downward rather than cycle a handful of
        # items through a 10-word round.
        from rehab.game.modes.syllables_words import words_for
        self.assertGreaterEqual(len(words_for(1, "C")), 8)


class CountingLevelTests(unittest.TestCase):
    """Level 1 is syllable counting: tap count against syllable count,
    any fingers, free pace. That is the Liberman tapping task and the
    ladder's entry rung, so the count comparison has to be exact and
    the extra and missing cases have to name themselves."""

    def test_right_count_scores_great_with_err_ok(self) -> None:
        engine, mode = _build_mode(level=1)
        t = _run_to_respond(mode)
        n = mode.n_expected
        _tap_out(mode, [0] * n, t + 0.5)
        stim = _logged_stimulus(engine)
        self.assertIn("err=ok", stim)
        self.assertTrue(stim.startswith(mode.word.word + ";"))
        self.assertEqual(_logged_outcome(engine).label, "Great")

    def test_any_finger_counts_at_level_one(self) -> None:
        # Counting is about how many, not which finger: taps on the
        # wrong fingers must still score by count alone.
        engine, mode = _build_mode(level=1)
        t = _run_to_respond(mode)
        n = mode.n_expected
        lanes = [3 - (i % 4) for i in range(n)]
        _tap_out(mode, lanes, t + 0.5)
        self.assertIn("err=ok", _logged_stimulus(engine))

    def test_correct_keys_lists_every_playing_lane_at_level_one(
            self) -> None:
        """Audit finding #41: acceptable_lanes() used to restrict to
        positions 0..n-1 even at level 1, where order_required is
        False and any finger counts (proved above). A consumer
        computing wrong-finger rates from correct_keys vs keys_pressed
        would invent errors on level-1 rows: a tap on lane 4 of a
        2-syllable word scores err=ok, so correct_keys must say lane 4
        was acceptable too, not just lanes 1-2."""
        engine, mode = _build_mode(level=1)
        from rehab.game.modes.syllables_words import WORDS
        mode.word = next(w for w in WORDS if w.n_syll == 2)
        _run_to_respond(mode, 0.1)
        self.assertEqual(mode.acceptable_lanes(), [0, 1, 2, 3])

    def test_extra_tap_is_named_and_misses(self) -> None:
        engine, mode = _build_mode(level=1)
        t = _run_to_respond(mode)
        _tap_out(mode, [0] * (mode.n_expected + 1), t + 0.5)
        self.assertIn("err=extra_tap", _logged_stimulus(engine))
        self.assertEqual(_logged_outcome(engine).label, "Miss")

    def test_missing_tap_is_named_when_the_window_closes(self) -> None:
        engine, mode = _build_mode(level=1)
        t = _run_to_respond(mode)
        with_short = mode.n_expected - 1
        tt = t + 0.5
        for i in range(with_short):
            mode.queue_press(_press(0, tt))
            mode._tick(tt)
            tt += 0.4
        mode._tick(t + mode.free_window_s + 0.1)
        if with_short == 0:
            self.assertIn("err=timeout", _logged_stimulus(engine))
        else:
            self.assertIn("err=missing_tap", _logged_stimulus(engine))

    def test_no_taps_at_all_is_a_timeout_not_a_punishment(self) -> None:
        engine, mode = _build_mode(level=1)
        t = _run_to_respond(mode)
        mode._tick(t + mode.free_window_s + 0.1)
        self.assertIn("err=timeout", _logged_stimulus(engine))
        # No penalty path exists in this mode: a child is never
        # docked points.
        engine.apply_wrong_press_penalty.assert_not_called()
        engine.apply_idle_press_penalty.assert_not_called()

    def test_repeated_lane_does_not_retro_write_the_earlier_tap(
            self) -> None:
        """Audit finding #33: _peak_force_for_lane reports the CURRENT
        press's running peak, so polling every tap on a lane (not just
        the newest) retro-wrote a second same-lane press's peak onto
        the first tap. A level-1 child drumming one finger for a
        2-syllable word (soft tap then hard tap, same lane) must keep
        the soft tap's own peak."""
        engine, mode = _build_mode(level=1, tap_debounce_ms=0)
        mode._tick(0.0)
        from rehab.game.modes.syllables_words import WORDS
        mode.word = next(w for w in WORDS if w.n_syll == 2)
        t = _run_to_respond(mode, 0.1)
        peaks = {0: 10.0}
        engine._peak_force_for_lane = lambda lane: peaks.get(lane)
        mode.queue_press(_press(0, t))
        mode._tick(t)
        mode._poll_tap_peaks()
        self.assertEqual(mode.taps[0].peak, 10.0)
        peaks[0] = 50.0
        mode.queue_press(_press(0, t + 0.3))
        mode._tick(t + 0.3)
        mode._poll_tap_peaks()
        self.assertEqual(len(mode.taps), 2)
        self.assertEqual(mode.taps[0].peak, 10.0)
        self.assertEqual(mode.taps[1].peak, 50.0)

    def test_double_touch_on_one_finger_debounces(self) -> None:
        # A bouncy finger lands two contacts 50 ms apart; the second
        # must not count as an extra tap.
        engine, mode = _build_mode(level=1)
        t = _run_to_respond(mode)
        n = mode.n_expected
        tt = t + 0.5
        for _ in range(n):
            mode.queue_press(_press(0, tt))
            mode._tick(tt)
            mode.queue_press(_press(0, tt + 0.05))
            mode._tick(tt + 0.05)
            tt += 0.4
        mode._tick(tt + mode.SETTLE_S)
        self.assertIn("err=ok", _logged_stimulus(engine))


class OrderLevelTests(unittest.TestCase):
    """Level 2 maps syllable position onto finger order, index first.
    Order errors must be named as such (not folded into misses) and
    must land in the CSV's incorrect-press columns, because
    finger-mapping is the skill this rung adds."""

    def _two_syllable_word(self, mode):
        from rehab.game.modes.syllables_words import WORDS
        return next(w for w in WORDS if w.n_syll == 2)

    def test_in_order_taps_score_great(self) -> None:
        engine, mode = _build_mode(level=2)
        mode._tick(0.0)
        mode.word = self._two_syllable_word(mode)
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [0, 1], t + 0.5)
        self.assertIn("err=ok", _logged_stimulus(engine))

    def test_reversed_taps_name_wrong_order_and_record_the_press(self) -> None:
        engine, mode = _build_mode(level=2)
        mode._tick(0.0)
        mode.word = self._two_syllable_word(mode)
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [1, 0], t + 0.5)
        self.assertIn("err=wrong_order", _logged_stimulus(engine))
        # Count was right, so the child keeps the softer Good outcome.
        self.assertEqual(_logged_outcome(engine).label, "Good")
        trial = engine.log_trial.call_args.args[0]
        self.assertTrue(trial.incorrect_presses)

    def test_replay_flag_reports_the_replay_that_will_run(self) -> None:
        """Audit finding #35: replay= was packed from self._replayed,
        which is still False at pack time on every trial (it is only
        set True afterwards, in _after_feedback) and never logged
        again once true, so the flag was permanently 0. With
        replay_on_error, an error trial's row must say replay=1
        because the replay demonstrably runs right after."""
        engine, mode = _build_mode(level=2, replay_on_error=True)
        mode._tick(0.0)
        from rehab.game.modes.syllables_words import WORDS
        mode.word = next(w for w in WORDS if w.n_syll == 2)
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [1, 0], t + 0.5)      # reversed -> wrong_order
        stim = _logged_stimulus(engine)
        self.assertIn("err=wrong_order", stim)
        self.assertIn("replay=1", stim)
        self.assertTrue(mode._pending_replay)

    def test_replay_flag_is_zero_without_replay_on_error(self) -> None:
        engine, mode = _build_mode(level=2, replay_on_error=False)
        mode._tick(0.0)
        from rehab.game.modes.syllables_words import WORDS
        mode.word = next(w for w in WORDS if w.n_syll == 2)
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [1, 0], t + 0.5)
        self.assertIn("replay=0", _logged_stimulus(engine))


def _word(name: str):
    from rehab.game.modes.syllables_words import WORDS
    return next(w for w in WORDS if w.word == name)


BILATERAL = {"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]}


class ReadAcrossRowWalkTests(unittest.TestCase):
    """The one rule of the row design: taps travel physically LEFT TO
    RIGHT, the way the blocks light and the way print runs, on any
    hand. On the right hand that is index outward (unchanged); on the
    left hand the same word walks the n fingers nearest the thumb, so
    a 2-unit word is middle then index (d f on the keyboard), NOT
    index then middle. This flips the old left-hand behaviour on
    purpose: the old rule made a left-hand word run physically right
    to left, against the mapping the mode exists to teach."""

    def test_left_hand_two_unit_word_walks_middle_then_index(self) -> None:
        engine, mode = _build_mode(hand_mode="left", level=2)
        mode._tick(0.0)
        mode.word = _word("wombat")
        self.assertEqual(mode.expected_lanes(), [1, 0])
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [1, 0], t + 0.5)
        self.assertIn("err=ok", _logged_stimulus(engine))

    def test_left_hand_index_first_is_now_wrong_order(self) -> None:
        engine, mode = _build_mode(hand_mode="left", level=2)
        mode._tick(0.0)
        mode.word = _word("wombat")
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [0, 1], t + 0.5)
        self.assertIn("err=wrong_order", _logged_stimulus(engine))

    def test_left_hand_four_unit_word_starts_on_the_little(self) -> None:
        engine, mode = _build_mode(hand_mode="left", level=2)
        mode._tick(0.0)
        mode.word = _word("kookaburra")
        self.assertEqual(mode.expected_lanes(), [3, 2, 1, 0])
        # The blocks wear the fingers that play them: little to index.
        self.assertEqual([mode.finger_for_position(i) for i in range(4)],
                         [3, 2, 1, 0])

    def test_left_model_buzzes_left_to_right_too(self) -> None:
        # The model teaches the walk, so its buzz order must BE the
        # walk: middle then index on a left-hand 2-unit word.
        engine, mode = _build_mode(hand_mode="left", level=2)
        mode._tick(0.0)
        mode.word = _word("wombat")
        _run_to_respond(mode, 0.1)
        lanes = [c.args[0] for c in engine.on_stim.call_args_list]
        self.assertEqual(lanes, [1, 0])

    def test_right_hand_behaviour_is_unchanged(self) -> None:
        engine, mode = _build_mode(level=2)
        mode._tick(0.0)
        mode.word = _word("kookaburra")
        self.assertEqual(mode.expected_lanes(), [0, 1, 2, 3])

    def test_bilateral_short_word_accepts_each_hands_own_walk(self) -> None:
        """Either hand still counts on short words, but through its
        OWN walk: position 0 of a 2-unit word is the right index OR
        the left middle (lane 5), and the left index (lane 4) now
        carries position 1, not position 0."""
        engine, mode = _build_mode(level=2, lanes_by_hand=BILATERAL)
        mode._tick(0.0)
        mode.word = _word("wombat")
        self.assertEqual(mode.lanes_for_position(0), [0, 5])
        self.assertEqual(mode.lanes_for_position(1), [1, 4])
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [5, 4], t + 0.5)      # all-left, walked l-to-r
        self.assertIn("err=ok", _logged_stimulus(engine))

    def test_bilateral_old_left_index_first_is_wrong_order(self) -> None:
        engine, mode = _build_mode(level=2, lanes_by_hand=BILATERAL)
        mode._tick(0.0)
        mode.word = _word("wombat")
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [4, 5], t + 0.5)      # the pre-flip "correct"
        self.assertIn("err=wrong_order", _logged_stimulus(engine))

    def test_mixed_hands_still_count_on_short_words(self) -> None:
        engine, mode = _build_mode(level=2, lanes_by_hand=BILATERAL)
        mode._tick(0.0)
        mode.word = _word("wombat")
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [5, 1], t + 0.5)      # left middle, right middle
        self.assertIn("err=ok", _logged_stimulus(engine))


class SpanningRowTests(unittest.TestCase):
    """Words of 5-8 units span both hands as ONE row in physical desk
    order, centred on the midline: 5 units run left-ring to
    right-middle, 8 use all eight fingers. Each position owns exactly
    one lane, so correct_keys names the row, the stimulus carries
    map=row, and the model's hand is determined by the position (the
    hand shuffle bag keeps balancing only the short words it owns)."""

    ROWS = {
        "stamp": [6, 5, 4, 0, 1],
        "basket": [6, 5, 4, 0, 1, 2],
        "blanket": [7, 6, 5, 4, 0, 1, 2],
        "breakfast": [7, 6, 5, 4, 0, 1, 2, 3],
    }

    def _row_mode(self, word_name: str, **overrides):
        engine, mode = _build_mode(level=6, band="C",
                                   lanes_by_hand=BILATERAL, **overrides)
        mode._tick(0.0)
        mode.word = _word(word_name)
        return engine, mode

    def test_rows_are_centred_and_recruit_littles_last(self) -> None:
        for word_name, want in self.ROWS.items():
            engine, mode = self._row_mode(word_name)
            self.assertTrue(mode.row_mode, word_name)
            self.assertEqual(mode.row_lanes(), want, word_name)
        # 5 and 6 unit rows never touch a little finger (lanes 7, 3):
        # the weakest, most enslaved fingers join only at 7-8 units.
        self.assertNotIn(7, self.ROWS["stamp"] + self.ROWS["basket"])
        self.assertNotIn(3, self.ROWS["stamp"] + self.ROWS["basket"])

    def test_row_taps_in_desk_order_score_ok(self) -> None:
        engine, mode = self._row_mode("breakfast")
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, self.ROWS["breakfast"], t + 0.5, gap=0.3)
        stim = _logged_stimulus(engine)
        self.assertIn("err=ok", stim)
        self.assertIn("map=row", stim)
        self.assertIn("nsyll=8", stim)

    def test_swapped_row_taps_name_wrong_order(self) -> None:
        engine, mode = self._row_mode("stamp")
        lanes = list(self.ROWS["stamp"])
        lanes[0], lanes[1] = lanes[1], lanes[0]
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, lanes, t + 0.5, gap=0.3)
        self.assertIn("err=wrong_order", _logged_stimulus(engine))
        self.assertEqual(_logged_outcome(engine).label, "Good")

    def test_correct_keys_is_the_row_one_lane_per_position(self) -> None:
        engine, mode = self._row_mode("basket")
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, self.ROWS["basket"], t + 0.5, gap=0.3)
        self.assertEqual(
            engine.log_trial.call_args.kwargs["correct_lanes"],
            self.ROWS["basket"])

    def test_model_buzzes_the_row_and_leaves_the_hand_bag_alone(
            self) -> None:
        engine, mode = self._row_mode("blanket")
        bag_before = mode._model_hand_order
        drawn = []
        real_next = bag_before.next
        bag_before.next = lambda: drawn.append(1) or real_next()
        _run_to_respond(mode, 0.1)
        lanes = [c.args[0] for c in engine.on_stim.call_args_list]
        self.assertEqual(lanes, self.ROWS["blanket"])
        self.assertEqual(drawn, [], "the hand bag was consumed on a "
                                    "spanning word")

    def test_playing_finger_with_no_block_is_a_wrong_tap(self) -> None:
        """On a 5-unit word the right ring and both littles carry no
        position. A tap there is a real press on a playing hand, so
        it must land in the tap list and the incorrect-press record,
        never be silently ignored: ignoring it would hide exactly the
        stray presses the row regime is expected to produce."""
        engine, mode = self._row_mode("stamp")
        t = _run_to_respond(mode, 0.1)
        lanes = self.ROWS["stamp"][:4] + [3]     # last tap on R-little
        _tap_out(mode, lanes, t + 0.5, gap=0.3)
        self.assertIn("err=wrong_order", _logged_stimulus(engine))
        trial = engine.log_trial.call_args.args[0]
        self.assertTrue(trial.incorrect_presses)
        self.assertEqual(trial.incorrect_presses[0][0], 3)

    def test_short_words_carry_no_map_row_flag(self) -> None:
        engine, mode = _build_mode(level=2, lanes_by_hand=BILATERAL)
        mode._tick(0.0)
        mode.word = _word("wombat")
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [0, 1], t + 0.5)
        self.assertNotIn("map=row", _logged_stimulus(engine))

    def test_row_finger_colours_mirror_across_the_midline(self) -> None:
        engine, mode = self._row_mode("breakfast")
        self.assertEqual(
            [mode.finger_for_position(i) for i in range(8)],
            [3, 2, 1, 0, 0, 1, 2, 3])

    def test_home_row_typed_left_to_right_plays_an_eight_unit_word(
            self) -> None:
        """The keyboard IS the sensor mapping: an 8-unit word is
        literally a s d f j k l ; typed left to right, with nothing
        extra configured (the bilateral keymap already says so). The
        keys resolve through handle_event to the exact row lanes;
        their taps are then replayed on the simulated clock (a real
        KEYDOWN stamps wall time, which a ticked test cannot mix in)
        and must score the word clean."""
        import pygame
        engine, mode = _build_mode(level=6, band="C",
                                   lanes_by_hand=BILATERAL)
        engine.hand_mode = "both"
        engine.cfg.get = MagicMock(side_effect=lambda k, d=None: {
            "game.keyboard_map_bilateral": {
                "j": 0, "k": 1, "l": 2, "semicolon": 3,
                "f": 4, "d": 5, "s": 6, "a": 7},
        }.get(k, d))
        mode._tick(0.0)
        mode.word = _word("breakfast")
        t = _run_to_respond(mode, 0.1)
        keys = [pygame.K_a, pygame.K_s, pygame.K_d, pygame.K_f,
                pygame.K_j, pygame.K_k, pygame.K_l, pygame.K_SEMICOLON]
        for key in keys:
            mode.handle_event(pygame.event.Event(pygame.KEYDOWN, key=key))
        typed = [p.lane for p in mode._presses]
        self.assertEqual(typed, mode.row_lanes(),
                         "home row left to right must be the row")
        mode._presses.clear()
        _tap_out(mode, typed, t + 0.5, gap=0.3)
        stim = _logged_stimulus(engine)
        self.assertIn("err=ok", stim)
        self.assertIn("map=row", stim)

    def test_stress_normalisation_reads_the_finger_not_the_position(
            self) -> None:
        """On the row a left-ring lane carries position 0, but its
        calibration gap is still the RING's. Reading the gap by
        position (the old code) would normalise the left ring by the
        index finger's gap, quietly skewing every level-4 stress
        ratio on 5-syllable words."""
        engine, mode = _build_mode(level=4, lanes_by_hand=BILATERAL)
        mode._tick(0.0)
        mode.word = _word("hippopotamus")
        gaps_left = {0: 11.0, 1: 12.0, 2: 13.0, 3: 14.0}
        gaps_right = {0: 21.0, 1: 22.0, 2: 23.0, 3: 24.0}

        class _Prof:
            def __init__(self, gaps):
                self._g = gaps

            def gap(self):
                return self._g

        engine.calibration_profiles = {"left": _Prof(gaps_left),
                                       "right": _Prof(gaps_right)}
        # Row for 5 units: 6 (L-ring), 5 (L-middle), 4 (L-index),
        # 0 (R-index), 1 (R-middle).
        self.assertEqual(mode._reference_counts(6), 13.0)   # L ring
        self.assertEqual(mode._reference_counts(5), 12.0)   # L middle
        self.assertEqual(mode._reference_counts(4), 11.0)   # L index
        self.assertEqual(mode._reference_counts(0), 21.0)   # R index
        self.assertEqual(mode._reference_counts(1), 22.0)   # R middle


class LongMaterialPoolTests(unittest.TestCase):
    """The long words are a bilateral pool extension, never a level or
    a requirement: a one-hand child keeps the full ladder on the 2-4
    unit material, 5-syllable words live only in bilateral band C at
    levels 2-4, the level 6 bilateral pool widens to 5-6 graphemes,
    and the 7-8 stretch enters at band C only. Level 1 keeps its
    3-syllable counting cap everywhere."""

    def test_single_hand_pools_never_exceed_four_units(self) -> None:
        from rehab.game.modes.syllables_words import words_for
        for level in (1, 2, 3, 4):
            for band in ("A", "B", "C"):
                self.assertTrue(all(w.n_syll <= 4
                                    for w in words_for(level, band)))
        self.assertTrue(all(len(w.graphemes) <= 4
                            for w in words_for(6, "C")))

    def test_five_syllable_words_only_in_bilateral_band_c(self) -> None:
        from rehab.game.modes.syllables_words import words_for
        pool = words_for(2, "C", bilateral=True)
        self.assertTrue(any(w.n_syll == 5 for w in pool))
        for band in ("A", "B"):
            self.assertTrue(all(w.n_syll <= 4 for w in
                                words_for(2, band, bilateral=True)))
        # Level 1 keeps the counting entry point's 3-syllable cap.
        self.assertTrue(all(w.n_syll <= 3 for w in
                            words_for(1, "C", bilateral=True)))

    def test_level_six_bilateral_widens_to_six_and_stretches_at_c(
            self) -> None:
        from rehab.game.modes.syllables_words import words_for
        for band in ("A", "B"):
            pool = words_for(6, band, bilateral=True)
            self.assertEqual(max(len(w.graphemes) for w in pool), 6)
        pool_c = words_for(6, "C", bilateral=True)
        self.assertEqual(max(len(w.graphemes) for w in pool_c), 8)
        # The 2-4 entry material stays in every bilateral pool.
        self.assertTrue(any(len(w.graphemes) <= 4 for w in pool_c))

    def test_long_grapheme_cuts_join_and_are_five_to_eight(self) -> None:
        from rehab.game.modes.syllables_words import (
            TRANSPARENT_WORDS_STRETCH, TRANSPARENT_WORDS_WIDE)
        self.assertGreaterEqual(len(TRANSPARENT_WORDS_WIDE), 10)
        self.assertGreaterEqual(len(TRANSPARENT_WORDS_STRETCH), 3)
        for w in TRANSPARENT_WORDS_WIDE + TRANSPARENT_WORDS_STRETCH:
            self.assertEqual("".join(w.graphemes), w.word, w.word)
        self.assertTrue(all(5 <= len(w.graphemes) <= 6
                            for w in TRANSPARENT_WORDS_WIDE))
        self.assertTrue(all(7 <= len(w.graphemes) <= 8
                            for w in TRANSPARENT_WORDS_STRETCH))

    def test_no_six_to_eight_syllable_words_exist(self) -> None:
        # The binding what-NOT-to-do: strings past young verbal span
        # (Gathercole et al. 2004) would measure memory, not
        # segmentation. Phonemes are the long territory, syllables
        # stop at 5.
        from rehab.game.modes.syllables_words import WORDS
        self.assertEqual(max(w.n_syll for w in WORDS), 5)


class RowScreenTests(unittest.TestCase):
    """What the child sees on a spanning word: the either-hand promise
    is replaced (not just hidden) by the row rule, and the block row
    opens a wider gap between the two hands' groups so the word
    visibly crosses hands where the fingers do."""

    def _screen(self, engine):
        import pygame
        pygame.init()
        pygame.font.init()
        from rehab.ui.syllables_screen import SyllablesScreen
        from rehab.ui.theme import get as get_theme
        from rehab.ui.widgets import Layout
        # The block geometry is real arithmetic on the layout, so the
        # mock engine needs the real 1280x800 logical layout, not a
        # MagicMock that turns every coordinate into nonsense.
        engine.layout = Layout(1280, 800, 1.0)
        engine.theme = get_theme("clinical")
        return SyllablesScreen(engine)

    def test_long_word_line_replaces_either_hand_line(self) -> None:
        engine, mode = _build_mode(level=6, band="C",
                                   lanes_by_hand=BILATERAL)
        scr = self._screen(engine)
        mode._tick(0.0)
        mode.word = _word("breakfast")
        mode.phase = "respond"
        line = scr._either_hand_line(mode)
        self.assertIn("both hands", line)
        self.assertIn("left to right", line)
        self.assertNotIn("either hand", line)
        # Short words keep the either-hand promise.
        mode.word = _word("cat")
        self.assertIn("either hand", scr._either_hand_line(mode))

    def test_row_blocks_split_into_two_hand_groups(self) -> None:
        engine, mode = _build_mode(level=6, band="C",
                                   lanes_by_hand=BILATERAL)
        scr = self._screen(engine)
        mode._tick(0.0)
        mode.word = _word("basket")     # 6 units, split after 3
        rects = scr._block_rects(mode)
        self.assertEqual(len(rects), 6)
        gaps = [rects[i + 1].left - rects[i].right
                for i in range(len(rects) - 1)]
        split = mode.row_split()
        self.assertEqual(split, 3)
        hand_gap = gaps[split - 1]
        within = [g for i, g in enumerate(gaps) if i != split - 1]
        self.assertGreater(hand_gap, max(within),
                           "the gap between the hands' groups must be "
                           "visibly wider than the within-hand gaps")
        # The whole row still fits the 1280 logical width.
        self.assertGreaterEqual(rects[0].left, 0)
        engine2, mode2 = _build_mode(level=6, band="C",
                                     lanes_by_hand=BILATERAL)
        mode2._tick(0.0)
        mode2.word = _word("breakfast")
        rects8 = scr._block_rects(mode2)
        self.assertLessEqual(rects8[-1].right, 1280)
        self.assertGreaterEqual(rects8[0].left, 0)

    def test_short_words_keep_one_even_row(self) -> None:
        engine, mode = _build_mode(level=2, lanes_by_hand=BILATERAL)
        scr = self._screen(engine)
        mode._tick(0.0)
        mode.word = _word("kangaroo")
        rects = scr._block_rects(mode)
        gaps = {rects[i + 1].left - rects[i].right
                for i in range(len(rects) - 1)}
        self.assertEqual(len(gaps), 1, "short words must keep the "
                                       "single even block gap")


class PacedLevelTests(unittest.TestCase):
    """Level 3 is the temporal-sampling core: the model lights one
    finger per beat through the shared cue path, the child taps one
    beat per tick, and every tap's signed asynchrony is logged in the
    rhythm sign convention (negative = early). If the beat bookkeeping
    drifts, the headline metric of the whole mode is wrong."""

    def _start(self, engine, mode):
        mode._tick(0.0)
        from rehab.game.modes.syllables_words import WORDS
        mode.word = next(w for w in WORDS if w.n_syll == 2)
        return _run_to_respond(mode, 0.1)

    def test_model_fires_one_stim_per_syllable_in_finger_order(self) -> None:
        engine, mode = _build_mode(level=3)
        self._start(engine, mode)
        lanes = [c.args[0] for c in engine.on_stim.call_args_list]
        self.assertEqual(lanes, [0, 1])

    def test_on_beat_taps_carry_signed_asynchronies(self) -> None:
        engine, mode = _build_mode(level=3)
        t0 = self._start(engine, mode)
        beats = list(mode._beat_times)
        self.assertEqual(len(beats), 2)
        # First tap 40 ms early, second 40 ms late: both inside the
        # 150 ms window, so the word is correct and the signed values
        # land in the stimulus string.
        mode.queue_press(_press(0, beats[0] - 0.04))
        mode._tick(beats[0])
        mode.queue_press(_press(1, beats[1] + 0.04))
        mode._tick(beats[1] + 0.05)
        mode._tick(beats[1] + 0.05 + mode.SETTLE_S + 0.05)
        stim = _logged_stimulus(engine)
        self.assertIn("err=ok", stim)
        self.assertIn("asyn=-40.0,40.0", stim)
        # time_difference_ms carries the MEAN signed asynchrony on
        # paced trials, the rhythm convention.
        self.assertAlmostEqual(_logged_outcome(engine).rt_ms, 0.0,
                               places=5)

    def test_a_late_tap_names_off_beat(self) -> None:
        engine, mode = _build_mode(level=3)
        self._start(engine, mode)
        beats = list(mode._beat_times)
        mode.queue_press(_press(0, beats[0] + 0.3))
        mode._tick(beats[0] + 0.3)
        mode.queue_press(_press(1, beats[1]))
        mode._tick(beats[1])
        mode._tick(beats[1] + mode.SETTLE_S + 0.05)
        self.assertIn("err=off_beat", _logged_stimulus(engine))
        self.assertEqual(_logged_outcome(engine).label, "Good")

    def test_response_window_covers_count_in_beats_and_grace(self) -> None:
        engine, mode = _build_mode(level=3)
        mode._tick(0.0)
        from rehab.game.modes.syllables_words import WORDS
        mode.word = next(w for w in WORDS if w.n_syll == 3)
        expected = (mode.count_in_beats + 3) * mode.ioi_s + mode.grace_s
        self.assertAlmostEqual(mode.current_timeout_s, expected)


class StressLevelTests(unittest.TestCase):
    """Level 4 uses the force sensors as an accent channel: press the
    stressed syllable harder. The criterion is relative to the child's
    own taps (children differ hugely in absolute force) and must be
    UNSCORED, not failed, when no force data exists, or every keyboard
    session would read as a stress deficit."""

    def _start_with_peaks(self, peaks_by_order):
        engine, mode = _build_mode(level=4)
        mode._tick(0.0)
        from rehab.game.modes.syllables_words import WORDS
        # kangaroo: 3 syllables, stress on the third. The taps land on
        # lanes 0, 1, 2 in order, so keying the fake force reading by
        # lane gives each tap its own stable peak, exactly what the
        # live poll would see from three separate sensors.
        mode.word = next(w for w in WORDS if w.word == "kangaroo")
        by_lane = {i: p for i, p in enumerate(peaks_by_order)}
        engine._peak_force_for_lane = lambda lane: by_lane.get(lane)
        _run_to_respond(mode, 0.1)
        beats = list(mode._beat_times)
        for i, b in enumerate(beats):
            mode.queue_press(_press(i, b))
            mode._tick(b)
        mode._tick(beats[-1] + mode.SETTLE_S + 0.05)
        return engine, mode

    def test_a_clear_accent_on_the_stressed_syllable_passes(self) -> None:
        engine, mode = self._start_with_peaks([10.0, 10.0, 30.0])
        self.assertIn("err=ok", _logged_stimulus(engine))
        self.assertTrue(mode._last_result["stress_correct"])

    def test_flat_taps_name_wrong_stress(self) -> None:
        engine, mode = self._start_with_peaks([10.0, 10.0, 11.0])
        self.assertIn("err=wrong_stress", _logged_stimulus(engine))
        self.assertEqual(_logged_outcome(engine).label, "Good")

    def test_two_syllable_word_can_pass_the_stress_criterion(self) -> None:
        """galah is 2 syllables, stress on the second. With the old
        "median of all taps" formula the reference was always the
        louder tap itself (sorted(peaks)[1] == max for n==2), so the
        stressed tap could never clear it no matter how hard it was
        pressed. A 3x-louder correctly-stressed tap must pass now that
        the reference excludes the tap being judged."""
        engine, mode = _build_mode(level=4)
        mode._tick(0.0)
        from rehab.game.modes.syllables_words import WORDS
        mode.word = next(w for w in WORDS if w.word == "galah")
        self.assertEqual(mode.word.stress, 1)
        by_lane = {0: 100.0, 1: 300.0}
        engine._peak_force_for_lane = lambda lane: by_lane.get(lane)
        _run_to_respond(mode, 0.1)
        beats = list(mode._beat_times)
        for i, b in enumerate(beats):
            mode.queue_press(_press(i, b))
            mode._tick(b)
        mode._tick(beats[-1] + mode.SETTLE_S + 0.05)
        self.assertIn("err=ok", _logged_stimulus(engine))
        self.assertTrue(mode._last_result["stress_correct"])

    def test_no_force_data_leaves_stress_unscored_not_failed(self) -> None:
        engine, mode = _build_mode(level=4)
        mode._tick(0.0)
        from rehab.game.modes.syllables_words import WORDS
        mode.word = next(w for w in WORDS if w.word == "kangaroo")
        _run_to_respond(mode, 0.1)
        beats = list(mode._beat_times)
        for i, b in enumerate(beats):
            mode.queue_press(_press(i, b))
            mode._tick(b)
        mode._tick(beats[-1] + mode.SETTLE_S + 0.05)
        self.assertIn("err=ok", _logged_stimulus(engine))
        self.assertIsNone(mode._last_result["stress_correct"])


class StressCalibrationTests(unittest.TestCase):
    """The stress ratio must compare forces on a common per-finger
    scale, the same guard chords.py already applies to its cross-talk
    ratio, or a child pressing every syllable equally hard can pass or
    fail purely from which physical finger carries the stress."""

    def test_equal_true_force_but_unequal_pad_gain_is_corrected(self) -> None:
        engine, mode = _build_mode(level=4)
        mode._tick(0.0)
        from rehab.game.modes.syllables_words import WORDS
        mode.word = next(w for w in WORDS if w.word == "kangaroo")
        # Same real press on every syllable, but lane 2 (the stressed
        # one) sits on a pad that reads 3x as many counts per newton as
        # lanes 0/1. Raw counts would read this as a huge accent; once
        # normalised by each lane's calibration gap the true (flat)
        # force is what the criterion sees.
        by_lane = {0: 10.0, 1: 10.0, 2: 30.0}
        engine._peak_force_for_lane = lambda lane: by_lane.get(lane)
        gaps = {0: 1.0, 1: 1.0, 2: 3.0}

        class _Prof:
            def gap(self):
                return gaps

        engine.calibration_profiles = {"right": _Prof()}
        _run_to_respond(mode, 0.1)
        beats = list(mode._beat_times)
        for i, b in enumerate(beats):
            mode.queue_press(_press(i, b))
            mode._tick(b)
        mode._tick(beats[-1] + mode.SETTLE_S + 0.05)
        # Normalised: 10/1, 10/1, 30/3 -> 10, 10, 10 -- perfectly flat,
        # no real accent, so the criterion must fail.
        self.assertIn("err=wrong_stress", _logged_stimulus(engine))
        self.assertFalse(mode._last_result["stress_correct"])


class SubsetLevelTests(unittest.TestCase):
    """Levels 5 and 6 change the unit, not the game: onset-rime cuts
    a CVC word into two taps, phoneme counting cuts a transparent
    word into one tap per sound. The unit count drives everything
    downstream, so it has to match the material exactly."""

    def test_level_five_asks_for_exactly_two_taps(self) -> None:
        engine, mode = _build_mode(level=5)
        t = _run_to_respond(mode)
        self.assertIsNotNone(mode.word.onset_rime)
        self.assertEqual(mode.n_expected, 2)
        self.assertEqual(mode.units_for(mode.word),
                         list(mode.word.onset_rime))
        _tap_out(mode, [0, 1], t + 0.5)
        self.assertIn("err=ok", _logged_stimulus(engine))

    def test_level_six_asks_for_one_tap_per_grapheme(self) -> None:
        engine, mode = _build_mode(level=6)
        t = _run_to_respond(mode)
        n = len(mode.word.graphemes)
        self.assertEqual(mode.n_expected, n)
        _tap_out(mode, list(range(n)), t + 0.5)
        self.assertIn("err=ok", _logged_stimulus(engine))


class ReplayAndFlowTests(unittest.TestCase):
    """The brief's feedback contract: one model replay after an error,
    never more, and the replay is a demonstration (the word is logged
    once, before the replay). Breaks land between rounds and the
    session ends politely at word boundaries."""

    def _finish_word(self, engine, mode, correct: bool, t: float) -> float:
        t = _run_to_respond(mode, t)
        n = mode.n_expected
        lanes = list(range(min(n, 4))) if correct else [0] * (n + 1)
        while len(lanes) < (n if correct else n + 1):
            lanes.append(lanes[-1])
        return _tap_out(mode, lanes, t + 0.3)

    def test_an_error_earns_exactly_one_replay(self) -> None:
        engine, mode = _build_mode(level=1, words_total=5)
        t = self._finish_word(engine, mode, correct=False, t=0.0)
        self.assertEqual(engine.log_trial.call_count, 1)
        # Feedback, then the replay runs the model again.
        t += mode.FEEDBACK_S + 0.1
        mode._tick(t)
        self.assertEqual(mode.phase, "replay")
        stims_before = engine.on_stim.call_count
        guard = 0
        while mode.phase == "replay":
            t += 0.1
            mode._tick(t)
            guard += 1
            self.assertLess(guard, 200)
        self.assertGreater(engine.on_stim.call_count, stims_before)
        # Still exactly one logged trial: the replay is not scored.
        self.assertEqual(engine.log_trial.call_count, 1)
        self.assertEqual(mode.words_done, 1)

    def test_a_correct_word_moves_straight_on(self) -> None:
        engine, mode = _build_mode(level=1, words_total=5)
        t = self._finish_word(engine, mode, correct=True, t=0.0)
        t += mode.FEEDBACK_S + 0.1
        mode._tick(t)
        self.assertNotEqual(mode.phase, "replay")
        self.assertEqual(mode.words_done, 1)

    def test_break_lands_after_each_round(self) -> None:
        engine, mode = _build_mode(level=1, words_total=4, round_size=2,
                                   break_s=5.0, replay_on_error=False)
        t = 0.0
        for _ in range(2):
            t = self._finish_word(engine, mode, correct=True, t=t)
            t += mode.FEEDBACK_S + 0.1
            mode._tick(t)
        self.assertEqual(mode.phase, "break")
        # The break is fixed-length rest: a press during it is ignored.
        mode.queue_press(_press(0, t + 0.5))
        mode._tick(t + 0.5)
        self.assertEqual(mode.phase, "break")
        mode._tick(t + 5.2)
        self.assertNotEqual(mode.phase, "break")

    def test_completing_the_words_finishes_the_block(self) -> None:
        engine, mode = _build_mode(level=1, words_total=2,
                                   replay_on_error=False)
        t = 0.0
        for _ in range(2):
            t = self._finish_word(engine, mode, correct=True, t=t)
            t += mode.FEEDBACK_S + 0.1
            mode._tick(t)
        mode._tick(t + 0.1)
        engine.finish_block.assert_called_once()
        self.assertEqual(mode.end_reason, "completed")

    def test_time_cap_ends_at_a_word_boundary(self) -> None:
        engine, mode = _build_mode(level=1, words_total=50,
                                   session_cap_min=0.01,
                                   replay_on_error=False)
        t = self._finish_word(engine, mode, correct=True, t=0.0)
        t += mode.FEEDBACK_S + 0.1
        mode._tick(t)
        mode._tick(t + 1.0)
        engine.finish_block.assert_called_once()
        self.assertEqual(mode.end_reason, "time_cap")

    def test_demo_trials_shrink_the_session_for_a_supervisor(self) -> None:
        engine, mode = _build_mode(level=1, demo_trials=3,
                                   warmup_taps=10)
        self.assertEqual(mode.words_total, 3)
        # No warm-up in a demo: the point is reaching Results fast.
        self.assertEqual(mode.warmup_total, 0)
        mode._tick(0.0)
        self.assertNotEqual(mode.phase, "warmup")


class BandProgressionTests(unittest.TestCase):
    """The brief's difficulty rule: 8 of the last 10 fully correct
    promotes the band, under 5 of 10 demotes it, and every firing is
    logged so the difficulty trace can be rebuilt. Silent band drift
    would make cross-session accuracy comparisons meaningless."""

    def test_eight_of_ten_promotes_and_logs(self) -> None:
        engine, mode = _build_mode(level=1, band="A")
        mode._recent.extend([True] * 8 + [False] * 2)
        mode._since_band_change = 10
        mode._maybe_move_band()
        self.assertEqual(mode.band, "B")
        self.assertTrue(engine.raw_logger.queue_event.called)
        self.assertEqual(
            engine.raw_logger.queue_event.call_args.args[0],
            "syllables_band")

    def test_under_five_of_ten_demotes(self) -> None:
        engine, mode = _build_mode(level=1, band="B")
        mode._recent.extend([True] * 4 + [False] * 6)
        mode._since_band_change = 10
        mode._maybe_move_band()
        self.assertEqual(mode.band, "A")

    def test_no_move_before_ten_words_since_the_last_change(self) -> None:
        engine, mode = _build_mode(level=1, band="A")
        mode._recent.extend([True] * 10)
        mode._since_band_change = 5
        mode._maybe_move_band()
        self.assertEqual(mode.band, "A")

    def test_band_cannot_leave_the_ladder(self) -> None:
        engine, mode = _build_mode(level=1, band="C")
        mode._recent.extend([True] * 10)
        mode._since_band_change = 10
        mode._maybe_move_band()
        self.assertEqual(mode.band, "C")

    def test_band_never_moves_at_level_five_or_six(self) -> None:
        """Audit finding #38: words_for ignores band above level 4 (the
        onset-rime and phoneme pools are drawn without a band split,
        deliberately), but _maybe_move_band used to run at every
        level, so band_trace on an L5/L6 block claimed the material
        got harder or easier when nothing about the draw pool changed
        at all."""
        for level in (5, 6):
            engine, mode = _build_mode(level=level, band="A")
            mode._recent.extend([True] * 10)
            mode._since_band_change = 10
            mode._maybe_move_band()
            self.assertEqual(mode.band, "A")
            self.assertEqual(mode._band_trace, ["A"])
            self.assertFalse(engine.raw_logger.queue_event.called)


class WarmupProbeTests(unittest.TestCase):
    """The warm-up doubles as the per-session synchronisation probe:
    each tap's signed gap to the nearest beat goes to raw.csv, and the
    block summary carries the mean and SD, so losing it would lose the
    session-to-session tapping-steadiness trace."""

    def test_warmup_taps_log_their_asynchrony(self) -> None:
        engine, mode = _build_mode(level=1, warmup_taps=3)
        mode._tick(0.0)
        self.assertEqual(mode.phase, "warmup")
        beats = mode._warmup_beats or []
        mode._tick(0.1)
        beats = mode._warmup_beats
        scorable = beats[mode.count_in_beats:]
        mode.queue_press(_press(0, scorable[0] + 0.03))
        mode._tick(scorable[0] + 0.03)
        self.assertEqual(len(mode._warmup_asyn), 1)
        self.assertAlmostEqual(mode._warmup_asyn[0], 30.0, delta=1.0)
        event = engine.raw_logger.queue_event.call_args.args[0]
        self.assertEqual(event, "warmup_tap")

    def test_warmup_ends_into_the_first_word(self) -> None:
        engine, mode = _build_mode(level=1, warmup_taps=2)
        mode._tick(0.0)
        mode._tick(0.1)
        end = mode._warmup_beats[-1] + mode.ioi_s + 0.1
        mode._tick(end)
        self.assertNotEqual(mode.phase, "warmup")


class LoggingContractTests(unittest.TestCase):
    """The notebook parses the stimulus string, so its format is a
    contract: word first, the level context as key=value pairs, taps
    as lane:time:peak triples. correct_keys carries every required
    finger and the response window is exposed for the timeout_ms
    column."""

    def test_stimulus_packs_word_context_and_taps(self) -> None:
        engine, mode = _build_mode(level=2)
        mode._tick(0.0)
        from rehab.game.modes.syllables_words import WORDS
        mode.word = next(w for w in WORDS if w.word == "wombat")
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [0, 1], t + 0.5)
        stim = _logged_stimulus(engine)
        self.assertTrue(stim.startswith("wombat;"))
        for key in ("lvl=2", "band=A", "nsyll=2", "stress=0",
                    "paced=0", "ioi=500", "replay=0", "err=ok",
                    "taps="):
            self.assertIn(key, stim)
        # Two taps, 1-indexed lanes, time then peak (empty without
        # force data).
        taps_part = [p for p in stim.split(";")
                     if p.startswith("taps=")][0]
        entries = taps_part[len("taps="):].split(",")
        self.assertEqual(len(entries), 2)
        self.assertTrue(entries[0].startswith("1:"))
        self.assertTrue(entries[1].startswith("2:"))

    def test_correct_lanes_carries_every_required_finger(self) -> None:
        engine, mode = _build_mode(level=2)
        mode._tick(0.0)
        from rehab.game.modes.syllables_words import WORDS
        mode.word = next(w for w in WORDS if w.n_syll == 3)
        t = _run_to_respond(mode, 0.1)
        _tap_out(mode, [0, 1, 2], t + 0.5)
        self.assertEqual(
            engine.log_trial.call_args.kwargs["correct_lanes"], [0, 1, 2])

    def test_block_stats_summarise_the_session(self) -> None:
        engine, mode = _build_mode(level=1, words_total=2,
                                   replay_on_error=False)
        t = _run_to_respond(mode)
        _tap_out(mode, [0] * mode.n_expected, t + 0.5)
        stats = mode.block_stats()
        self.assertEqual(stats["level"], 1)
        self.assertEqual(stats["n_words"], 1)
        self.assertIn("accuracy_by_syllables", stats)
        self.assertIn("band_trace", stats)
        self.assertEqual(stats["ioi_ms"], 500)


class KeyboardFallbackTests(unittest.TestCase):
    """The keyboard fallback (j k l ; = lanes 0..3) must stay wired in
    every mode: a busted serial auto-detect must never leave a session
    with no working input."""

    def test_keydown_becomes_a_press_on_the_mapped_lane(self) -> None:
        import pygame
        engine, mode = _build_mode(level=1)
        e = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j)
        mode.handle_event(e)
        self.assertEqual(len(mode._presses), 1)
        self.assertEqual(mode._presses[0].lane, 0)


class ScreenStoryTests(unittest.TestCase):
    """The child-facing story the screen tells, pinned as copy: every
    phase announces itself, the count-in counts DOWN to a GO, a
    timeout is never called close, bilateral play says either hand
    counts, and the keyboard hints live in the corner note only when
    the keyboard IS the input. These strings are what a seven year
    old and their parent act on, so they are load-bearing."""

    def _screen(self, engine):
        import pygame
        pygame.init()
        pygame.font.init()
        from rehab.ui.syllables_screen import SyllablesScreen
        return SyllablesScreen(engine)

    def test_every_phase_announces_itself(self) -> None:
        engine, mode = _build_mode(level=1)
        scr = self._screen(engine)
        mode._tick(0.0)
        want = {
            "warmup": "WARM UP",
            "attend": "LISTEN...",
            "model": "WATCH",
            "replay": "WATCH AGAIN",
            "countin": "GET READY...",
            "respond": "YOUR TURN!",
            "break": "REST TIME",
        }
        for phase, title in want.items():
            mode.phase = phase
            got, sub, _colour = scr._stage(mode)
            self.assertEqual(got, title, f"{phase} announces {got!r}")
        # The model instruction says hands off in words, not mechanism.
        mode.phase = "model"
        _t, sub, _c = scr._stage(mode)
        self.assertIn("Hands off", sub)

    def test_warmup_swell_is_phased_off_the_beat_grid(self) -> None:
        """Audit finding #36: the swell used to compute
        `phase = (now % ioi_s) / ioi_s`, anchored to the wall-clock
        epoch rather than the beat grid the scored warm-up beats
        started on (mode._warmup_beats[0]). A child cueing off the
        circle instead of the metronome tick would then tap with a
        constant offset of up to half a period against the very
        asynchronies the probe measures. The swell must be exactly
        in phase with the beat grid: at the beat itself (phase 0) the
        circle is at its largest, `60 + 26`."""
        import math
        from unittest.mock import patch
        engine, mode = _build_mode(level=1, warmup_taps=3, ioi_ms=500)
        scr = self._screen(engine)
        # Anchor the beat grid far from t=0, so an epoch-based phase
        # and a grid-based phase disagree unless the fix is in place.
        mode._warmup_beats = [1000.0, 1500.0, 2000.0]
        surf = MagicMock()
        radii = []
        with patch("pygame.draw.circle",
                   side_effect=lambda _s, _c, _pos, r: radii.append(r)):
            # Exactly on the beat: phase 0, largest circle.
            scr._draw_warmup(surf, mode, 1000.0)
            # One full IOI later, same beat-grid phase: same radius.
            scr._draw_warmup(surf, mode, 1500.0)
            # Half a period off the beat, a different beat-grid phase.
            scr._draw_warmup(surf, mode, 1000.0 + mode.ioi_s / 2)
        # Each call draws two circles (accent, then the punched-out
        # background one at r - 16); only the even entries are the
        # accent circle's own radius.
        outer = radii[0::2]
        expected_on_beat = 60 + int(26 * math.exp(-4.0 * 0.0))
        expected_half = 60 + int(26 * math.exp(-4.0 * 0.5))
        self.assertEqual(outer[0], expected_on_beat)
        self.assertEqual(outer[1], expected_on_beat,
                         "phase must repeat every IOI on the beat grid")
        self.assertEqual(outer[2], expected_half)

    def test_feedback_praises_or_names_the_one_thing_to_change(self) -> None:
        engine, mode = _build_mode(level=1)
        scr = self._screen(engine)
        mode._tick(0.0)
        mode.phase = "feedback"
        mode._last_result = {"correct": True, "error": "ok"}
        self.assertEqual(scr._stage(mode)[0], "WONDERFUL!")
        for err, frag in (("extra_tap", "too many"),
                          ("missing_tap", "still empty"),
                          ("wrong_order", "first finger"),
                          ("off_beat", "tick"),
                          ("wrong_stress", "harder")):
            mode._last_result = {"correct": False, "error": err}
            title, sub, _ = scr._stage(mode)
            self.assertEqual(title, "SO CLOSE!")
            self.assertIn(frag, sub)

    def test_a_timeout_is_not_called_close(self) -> None:
        # Zero taps landed; "so close" would be untrue and a child
        # knows it. The copy stays kind without lying.
        engine, mode = _build_mode(level=1)
        scr = self._screen(engine)
        mode._tick(0.0)
        mode.phase = "feedback"
        mode._last_result = {"correct": False, "error": "timeout"}
        title, sub, _ = scr._stage(mode)
        self.assertNotIn("CLOSE", title)
        self.assertIn("Watch", sub)

    def test_count_in_counts_down_not_up(self) -> None:
        engine, mode = _build_mode(level=3)
        scr = self._screen(engine)
        mode._tick(0.0)
        mode.word = mode._draw_word()
        mode._enter_phase("countin", 10.0)
        ioi = mode.ioi_s
        self.assertEqual(scr.countin_remaining(mode, 10.0), 4)
        self.assertEqual(scr.countin_remaining(mode, 10.0 + 1.5 * ioi), 3)
        self.assertEqual(scr.countin_remaining(mode, 10.0 + 3.5 * ioi), 1)

    def test_bilateral_respond_says_either_hand_counts(self) -> None:
        engine, mode = _build_mode(
            level=1,
            lanes_by_hand={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        scr = self._screen(engine)
        mode._tick(0.0)
        mode.phase = "respond"
        self.assertIn("either hand", scr._either_hand_line(mode))
        # One hand connected: no bilateral promise to make.
        engine1, mode1 = _build_mode(level=1)
        mode1._tick(0.0)
        mode1.phase = "respond"
        self.assertEqual(scr._either_hand_line(mode1), "")
        # And never during the model: that is the hand tag's job.
        mode.phase = "model"
        self.assertEqual(scr._either_hand_line(mode), "")

    def test_controls_note_only_when_the_keyboard_is_the_input(self) -> None:
        engine, mode = _build_mode(level=1)
        scr = self._screen(engine)
        engine.source.provides_samples = False
        self.assertEqual(scr.controls_lines(mode),
                         ["Right hand: J K L ;"])
        # Real sensors connected: fingers sit on the pads, no legend.
        engine.source.provides_samples = True
        self.assertEqual(scr.controls_lines(mode), [])

    def test_model_hand_tag_tracks_the_buzz_and_clears(self) -> None:
        engine, mode = _build_mode(
            level=2,
            lanes_by_hand={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        mode._tick(0.0)
        t = 0.0
        seen = set()
        guard = 0
        while mode.phase != "respond" and guard < 500:
            t += 0.05
            mode._tick(t)
            if mode.phase == "model" and mode.model_hand:
                seen.add(mode.model_hand)
            guard += 1
        self.assertTrue(seen and seen <= {"left", "right"})
        self.assertIsNone(mode.model_hand)


class EngineIntegrationTests(unittest.TestCase):
    """The wiring the user actually clicks through: the mode-select
    card leads to a real block on the dedicated screen, the screen
    draws in every phase without a display, and abandoning saves a
    block summary carrying the syllables stats."""

    def _engine(self, tmpdir: str):
        import pygame
        pygame.init()
        pygame.font.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        from rehab.ui.syllables_screen import SyllablesScreen
        cfg = Config.load()
        cfg.data.setdefault("ui", {})["resolution"] = [1280, 800]
        cfg.data.setdefault("session", {})["data_dir"] = tmpdir
        cfg.data.setdefault("game", {})["test_mode_enabled"] = True
        cfg.data.setdefault("syllables", {})["speak_words"] = False
        # No report generation: this test is about the block wiring,
        # not the researcher outputs.
        cfg.data.setdefault("report", {})["enabled"] = False
        eng = GameEngine(cfg, KeyboardOnlySource())
        # Only the screen under test: the block path guards every
        # other screen lookup, and building the full set drags in
        # screens this test does not exercise.
        eng._screens = {"syllables": SyllablesScreen(eng)}
        return eng

    def test_block_starts_on_its_own_screen_and_draws(self) -> None:
        import tempfile
        import pygame
        with tempfile.TemporaryDirectory() as tmpdir:
            eng = self._engine(tmpdir)
            try:
                eng.begin_syllables_block()
                self.assertIs(eng.screen_obj, eng._screens["syllables"])
                self.assertEqual(eng.mode.name, "Syllables")
                self.assertEqual(eng.current_block, "syllables")
                surf = pygame.Surface((1280, 800))
                # Drive the mode through its phases and draw each one;
                # a draw crash on any phase would blank the screen for
                # a child mid-session.
                t = 0.0
                seen = set()
                for _ in range(400):
                    eng.mode._tick(eng.mode._t0 + t
                                   if eng.mode._t0 else t)
                    seen.add(eng.mode.phase)
                    eng.screen_obj.draw(surf)
                    t += 0.1
                    if eng.mode.phase == "done":
                        break
                self.assertIn("attend", seen)
                self.assertIn("model", seen)
                self.assertIn("respond", seen)
                # Abandon writes the summary with the syllables stats.
                eng._abandon_if_in_block()
                self.assertIn("syllables", eng.session.block_summary)
            finally:
                try:
                    eng._abandon_if_in_block()
                except Exception:
                    pass
                pygame.quit()

    def test_mode_select_card_and_setup_route_exist(self) -> None:
        # The card was shipped ahead of the mode; now that the mode is
        # real, the pick path must call the real entry point.
        from rehab.ui.screens import ModeSelectScreen
        keys = [k for k, _t, _d in ModeSelectScreen.MODES]
        self.assertIn("syllables", keys)

    def test_extra_tap_miss_carries_its_own_error_type(self) -> None:
        """Audit finding #34: a level-1 Miss caused by a wrong TAP COUNT
        (extra_tap) is not a wrong finger and not necessarily a
        timeout, but log_trial's had_incorrect_press-derived logic
        knows only wrong_finger / timeout, so an extra tap that landed
        promptly used to read as error_type=timeout in trials.csv."""
        import csv
        import glob
        import pygame
        import tempfile
        from rehab.hardware.fsr_detector import PressEvent
        with tempfile.TemporaryDirectory() as tmpdir:
            eng = self._engine(tmpdir)
            eng.cfg.data.setdefault("syllables", {})["level"] = 1
            eng.cfg.data["syllables"]["words_per_block"] = 1
            eng.cfg.data["syllables"]["warmup_taps"] = 0
            try:
                eng.begin_syllables_block()
                mode = eng.mode
                t = 0.0
                mode._tick(mode._t0 + t if mode._t0 else t)
                guard = 0
                while mode.phase != "respond" and guard < 500:
                    t += 0.05
                    mode._tick(mode._t0 + t)
                    guard += 1
                n = mode.n_expected
                for _ in range(n + 1):    # one tap too many
                    mode.queue_press(PressEvent(
                        lane=0, t_perf=mode._t0 + t, value=0,
                        baseline=0.0, hand="right"))
                    mode._tick(mode._t0 + t)
                    t += 0.3
                mode._tick(mode._t0 + t + mode.SETTLE_S + 0.05)
                eng._abandon_if_in_block()
                files = glob.glob(tmpdir + "/**/trials.csv",
                                  recursive=True)
                with open(files[0]) as f:
                    row = next(csv.DictReader(f))
                self.assertEqual(row["feedback"], "Miss")
                self.assertEqual(row["error_type"], "extra_tap")
            finally:
                try:
                    eng._abandon_if_in_block()
                except Exception:
                    pass
                pygame.quit()

    def test_no_loud_trial_boost_inside_syllable_models(self) -> None:
        """Audit finding #29: engine.on_stim fires once per model
        SYLLABLE, not once per trial, so the loud-trial fraction used
        to land on an arbitrary syllable inside a word -- a random
        loudness accent the child cannot tell apart from the
        deliberate level-4 stress cue. Boosted at the default 10%
        fraction, a 12-word block (about 24-36 syllables) would almost
        certainly hit at least one loud onset under the old code."""
        import pygame
        import tempfile
        from unittest.mock import MagicMock
        with tempfile.TemporaryDirectory() as tmpdir:
            eng = self._engine(tmpdir)
            eng.cfg.data.setdefault("syllables", {})["level"] = 2
            eng.cfg.data["syllables"]["words_per_block"] = 13
            eng.cfg.data["syllables"]["warmup_taps"] = 0
            eng.audio = MagicMock()
            # test_mode_enabled (set by _engine()) shrinks words_total
            # to the demo count regardless of words_per_block, so the
            # block can complete inside the loop below; finish_block
            # then needs a "results" screen this harness does not
            # otherwise register.
            eng._screens["results"] = MagicMock()
            try:
                eng.begin_syllables_block()
                mode = eng.mode
                t = 0.0
                mode._tick(mode._t0 + t if mode._t0 else t)
                guard = 0
                gains = []
                eng.audio.set_trial_gain.side_effect = gains.append
                while mode.phase != "done" and guard < 5000:
                    if mode.phase == "respond":
                        for lane in range(mode.n_expected):
                            from rehab.hardware.fsr_detector import (
                                PressEvent)
                            mode.queue_press(PressEvent(
                                lane=lane, t_perf=mode._t0 + t,
                                value=0, baseline=0.0, hand="right"))
                            mode._tick(mode._t0 + t)
                            t += 0.05
                        mode._tick(mode._t0 + t + mode.SETTLE_S + 0.05)
                    else:
                        t += 0.02
                        mode._tick(mode._t0 + t)
                    guard += 1
                self.assertFalse(
                    [g for g in gains if g and g > 1.0],
                    "a syllables model onset played boosted (loud)")
            finally:
                try:
                    eng._abandon_if_in_block()
                except Exception:
                    pass
                pygame.quit()

    def test_wrong_order_good_trial_does_not_chime(self) -> None:
        """Audit finding #40: syllables promises "no punishment sound"
        and config's own comment says no error sound plays anywhere in
        this mode, but the generic after-press cue chimes on any
        non-Miss outcome, so a wrong_order "Good" trial (screen text
        SO CLOSE!) used to play the success chime under
        cue.sound_after. Only a clean (Great) word may chime."""
        import pygame
        import tempfile
        from unittest.mock import MagicMock
        from rehab.hardware.fsr_detector import PressEvent
        from rehab.game.modes.syllables_words import WORDS
        with tempfile.TemporaryDirectory() as tmpdir:
            eng = self._engine(tmpdir)
            eng.cfg.data.setdefault("syllables", {})["level"] = 2
            eng.cfg.data["syllables"]["words_per_block"] = 3
            eng.cfg.data["syllables"]["warmup_taps"] = 0
            eng.cfg.data.setdefault("cue", {})["sound_after"] = True
            eng.audio = MagicMock()
            two_syll = next(w for w in WORDS if w.n_syll == 2)
            try:
                eng.begin_syllables_block()
                mode = eng.mode
                t = 0.0
                mode._tick(mode._t0 + t if mode._t0 else t)
                guard = 0
                while mode.words_done < 3 and guard < 2000:
                    if mode.phase == "attend":
                        mode.word = two_syll     # reproducible target
                    if mode.phase == "respond":
                        for lane in (1, 0):       # reversed = wrong_order
                            mode.queue_press(PressEvent(
                                lane=lane, t_perf=mode._t0 + t,
                                value=0, baseline=0.0, hand="right"))
                            mode._tick(mode._t0 + t)
                            t += 0.3
                        mode._tick(mode._t0 + t + mode.SETTLE_S + 0.05)
                    else:
                        t += 0.05
                        mode._tick(mode._t0 + t)
                    guard += 1
                self.assertEqual(eng.audio.play_hit.call_count, 0)
                self.assertEqual(eng.audio.play_miss.call_count, 0)
            finally:
                try:
                    eng._abandon_if_in_block()
                except Exception:
                    pass
                pygame.quit()

    def test_default_config_documents_the_mode(self) -> None:
        import yaml
        root = Path(__file__).resolve().parents[1]
        data = yaml.safe_load((root / "config" / "default.yaml").read_text())
        syl = data.get("syllables")
        self.assertIsInstance(syl, dict)
        for key in ("level", "band", "beat_ioi_ms", "words_per_block",
                    "round_size", "break_s", "warmup_taps",
                    "on_beat_window_ms", "stress_ratio",
                    "session_cap_min", "replay_on_error",
                    "speak_words", "seed"):
            self.assertIn(key, syl)
        self.assertEqual(syl["beat_ioi_ms"], 500)
        self.assertEqual(syl["on_beat_window_ms"], 150)
        self.assertEqual(syl["stress_ratio"], 2.0)


class SyllablesResultsScreenCardsTests(unittest.TestCase):
    """Audit finding #30: on a paced (level 3/4) syllables block, rt_ms
    is the MEAN SIGNED beat asynchrony, not a reaction time, so falling
    through to the generic AVG RT / BEST RT cards could print an
    impossibly fast "RT" for a positive (late) mean, or show a
    personal-best "RT" built from the most anticipatory word. A
    syllables block must not fall through to the generic cards, and
    the paced cards must read the mode's own asyn_mean_ms/sd, absolute
    rather than signed."""

    def _draw_syllables_results(self, block_summary_syllables):
        import pygame
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.ui.screens import ResultsScreen
        from rehab.ui.theme import get as get_theme
        from rehab.ui.widgets import Layout
        pygame.init()
        pygame.font.init()
        pygame.display.set_mode((1280, 800))
        e = GameEngine.__new__(GameEngine)
        e.cfg = Config.load()
        e.theme = get_theme("clinical")
        e.layout = Layout(1280, 800, 1.0)
        e.hits, e.misses, e.score = 20, 4, 300
        e.current_block, e.hand_mode = "syllables", "right"
        e.best_streak, e.per_lane_stats = 5, {}
        e.hit_streak = 5
        e.last_session_root = None
        e.mode = None
        e.session = type("S", (), {
            "participant": "T", "age": "8",
            "block_summary": {"syllables": block_summary_syllables}})()
        e.stop_all_motors = lambda *a, **k: None
        # A positive (late) mean signed asynchrony: the exact case
        # that used to print an "impossibly fast RT" under the old
        # AVG RT / BEST RT cards.
        e._per_lane_rts = {0: [20.0]}
        e.overall_mean_rt = lambda: 20.0
        e.overall_best_rt = lambda: 20.0
        r = ResultsScreen(e)
        r._shown_t = 1.0
        cards = []
        r._draw_stat_card = (
            lambda surf, rect, lbl, val, col: cards.append((lbl, val)))
        surf = pygame.Surface((1280, 800))
        r.draw(surf)
        pygame.quit()
        return cards

    def test_paced_level_reads_asyn_stats_not_generic_rt(self) -> None:
        cards = self._draw_syllables_results({
            "level": 3, "accuracy": 0.8, "band_final": "B",
            "asyn_mean_ms": 20.0, "asyn_sd_ms": 35.0,
        })
        labels = [lbl for lbl, _ in cards]
        values = dict(cards)
        self.assertNotIn("AVG RT", labels)
        self.assertNotIn("BEST RT", labels)
        self.assertIn("AVG OFFSET", labels)
        self.assertEqual(values["AVG OFFSET"], "20 ms")
        self.assertIn("OFFSET SD", labels)
        self.assertIn("WORDS CORRECT", labels)
        self.assertEqual(values["WORDS CORRECT"], "80%")
        self.assertIn("BAND", labels)
        self.assertEqual(values["BAND"], "B")

    def test_paced_level_takes_absolute_value_of_a_negative_mean(
            self) -> None:
        # A negative (early) mean must read the same magnitude as the
        # matching positive mean: the card is a distance-off-beat
        # readout, not a signed bias.
        cards = self._draw_syllables_results({
            "level": 4, "accuracy": 0.7, "band_final": "A",
            "asyn_mean_ms": -20.0, "asyn_sd_ms": 35.0,
        })
        values = dict(cards)
        self.assertEqual(values["AVG OFFSET"], "20 ms")

    def test_free_paced_level_keeps_avg_and_best_rt(self) -> None:
        cards = self._draw_syllables_results({
            "level": 1, "accuracy": 0.9, "band_final": "A",
            "asyn_mean_ms": None, "asyn_sd_ms": None,
        })
        labels = [lbl for lbl, _ in cards]
        self.assertIn("AVG RT", labels)
        self.assertIn("BEST RT", labels)
        self.assertNotIn("AVG OFFSET", labels)


if __name__ == "__main__":
    unittest.main()
