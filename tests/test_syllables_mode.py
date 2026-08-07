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


def _build_mode(**overrides):
    """A SyllablesMode wired to a MagicMock engine, driven with
    explicit `now` values through _tick, following the chords-mode
    test harness. Speech is off (no macOS say in a test), the peak
    helper reports no force data (keyboard reality) unless a test
    installs its own, and the timing knobs are shrunk so a scenario
    runs in a handful of ticks."""
    from rehab.game.modes.syllables import SyllablesMode
    from rehab.game.scoring import ScoreConfig
    engine = MagicMock()
    engine._screens = {}
    engine.hand_mode = "right"
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


if __name__ == "__main__":
    unittest.main()
