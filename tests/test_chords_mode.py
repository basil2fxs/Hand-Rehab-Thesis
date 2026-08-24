"""Tests for Chords mode, the multi-finger co-activation block. The
guarantees pinned here are the ones the measurement depends on: the
difficulty ladder follows the enslaving-adjacency formula it claims to,
every chord lights all its fingers at once and lands in the CSV as
"1+3+4" with the full target set in correct_keys, the synchrony window
is what separates a chord from a sequence of taps, cross-talk is scored
from the force-window peaks and rewarded separately from completion,
the buzzer cue for a same-board chord is a spaced arpeggio the shared
driver can actually deliver, and the safety rails (quiet-hand gate,
enforced rests, fatigue triggers, session cap) end a block rather than
trap a tired hand in it.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _press(lane: int, t: float = 0.0):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                       hand="right")


def _build_mode(**overrides):
    """A ChordsMode wired to a MagicMock engine, driven with explicit
    `now` values instead of sleeping, following the pattern-mode test
    harness. The engine reports keyboard input (no live FSR data) so
    the sensor-dependent checks relax unless a test wires them up."""
    from finger_rehab.game.modes.chords import ChordsMode
    from finger_rehab.game.scoring import ScoreConfig
    engine = MagicMock()
    engine._screens = {}
    engine.hand_mode = "right"
    engine.source.provides_samples = False
    engine.detectors = {}
    engine.calibration_profiles = {}
    engine._force_window_peak = {}
    engine._force_window_saw_samples = False
    engine.cfg.get = MagicMock(side_effect=lambda k, d=None: {
        "fsr.on_delta": [20, 13, 15, 46],
    }.get(k, d))
    kwargs = dict(
        engine=engine,
        hand="right",
        lanes=[0, 1, 2, 3],
        timeout_s=3.0,
        sync_windows_ms=[250, 200, 150, 100],
        hold_ms=200,
        baseline_quiet_ms=500,
        settle_prompt_s=5.0,
        iti_min_s=1.5,
        iti_max_s=2.5,
        trials_per_subblock=20,
        subblocks=5,
        probe_trials_per_finger=2,
        rest_between_s=30.0,
        fatigue_rest_s=120.0,
        session_cap_min=30.0,
        score_cfg=ScoreConfig(),
        seed=7,
        demo_trials=None,
    )
    kwargs.update(overrides)
    mode = ChordsMode(**kwargs)
    mode._t0 = 0.0
    return engine, mode


def _burn_probes(mode, t: float = 5.0) -> float:
    """Complete every remaining opening probe cleanly so the next fire
    is a chord. Returns a time safely past the presses used."""
    while mode._probe_left_start > 0:
        mode._fire(t)
        for lane in mode.active.targets:
            mode._handle_press(_press(lane, t + 0.2), t + 0.2)
        t += 1.0
    return t


def _complete_chord(mode, t0: float, gap_s: float = 0.05) -> float:
    """Press every target of the active chord, onsets `gap_s` apart.
    Returns the time of the last press."""
    t = t0
    for lane in mode.active.targets:
        mode._handle_press(_press(lane, t), t)
        t += gap_s
    return t - gap_s


class DifficultyLadderTests(unittest.TestCase):
    """The ladder is the manipulation: it claims chords get harder in
    the order the enslaving literature predicts (adjacent quiet fingers
    next to active ones, ring worst). If the formula or the tier
    contents drift, the difficulty validation in the analysis is
    testing a different hypothesis than the docstring defends."""

    # The briefed values, recomputed from the formula every run.
    EXPECTED_D = {
        (2, 3): 2.0, (0, 1): 3.0,
        (1, 2, 3): 2.5, (1, 2): 3.0, (0, 1, 2, 3): 3.0,
        (0, 1, 2): 3.5, (0, 3): 5.0, (0, 2, 3): 5.5,
        (0, 2): 6.0, (1, 3): 7.0, (0, 1, 3): 7.5,
    }

    def test_difficulty_formula_reproduces_the_briefed_values(self) -> None:
        from finger_rehab.game.modes.chords import chord_difficulty
        for chord, d in self.EXPECTED_D.items():
            self.assertAlmostEqual(chord_difficulty(chord), d, places=3,
                                   msg=f"chord {chord}")

    def test_ladder_covers_every_chord_of_two_to_four_fingers(self) -> None:
        from finger_rehab.game.modes.chords import CHORD_TIERS
        seen = [c for tier in CHORD_TIERS for c in tier]
        # 6 pairs + 4 triples + 1 quad = 11, each exactly once.
        self.assertEqual(len(seen), 11)
        self.assertEqual(len(set(seen)), 11)
        for c in seen:
            self.assertGreaterEqual(len(c), 2)
            self.assertLessEqual(len(c), 4)

    def test_tiers_step_up_in_predicted_hardness(self) -> None:
        from finger_rehab.game.modes.chords import CHORD_TIERS, chord_difficulty
        maxima = [max(chord_difficulty(c) for c in tier)
                  for tier in CHORD_TIERS]
        self.assertEqual(maxima, sorted(maxima))
        # The top tier is exactly the enclosed-quiet-finger chords the
        # adjacency literature names as hardest: IR, MP, IMP.
        self.assertEqual(set(CHORD_TIERS[3]),
                         {(0, 2), (1, 3), (0, 1, 3)})

    def test_levels_run_tiers_within_windows(self) -> None:
        _, mode = _build_mode()
        self.assertEqual(mode.max_level, 15)
        mode.level = 3
        self.assertEqual((mode.current_tier, mode.current_w_ms), (3, 250.0))
        mode.level = 4
        self.assertEqual((mode.current_tier, mode.current_w_ms), (0, 200.0))
        mode.level = 15
        self.assertEqual((mode.current_tier, mode.current_w_ms), (3, 100.0))


class TrialFlowTests(unittest.TestCase):
    """A chord trial must light every target at once, log the chord in
    the shape downstream tools expect, and pay completion, togetherness
    and quiet separately: those three numbers are the mode."""

    def test_chord_lights_all_targets_in_one_stim(self) -> None:
        engine, mode = _build_mode()
        t = _burn_probes(mode)
        mode._fire(t)
        lanes_arg = engine.on_stim_multi.call_args[0][0]
        self.assertEqual(sorted(lanes_arg), list(mode.active.targets))
        self.assertGreaterEqual(len(lanes_arg), 2)

    def test_stimulus_and_correct_keys_carry_the_chord(self) -> None:
        engine, mode = _build_mode()
        t = _burn_probes(mode)
        mode._fire(t)
        targets = mode.active.targets
        _complete_chord(mode, t + 0.3)
        kwargs = engine.log_trial.call_args.kwargs
        self.assertEqual(kwargs["stimulus"],
                         "+".join(str(l + 1) for l in targets))
        self.assertEqual(kwargs["correct_lanes"], list(targets))

    def test_presses_inside_the_window_score_all_components(self) -> None:
        engine, mode = _build_mode()
        t = _burn_probes(mode)
        mode._fire(t)
        # 50 ms span against a 250 ms window: together, near-full
        # togetherness. No force data, so quiet pays in full.
        _complete_chord(mode, t + 0.3, gap_s=0.05)
        outcome = engine.log_trial.call_args[0][1]
        self.assertNotEqual(outcome.label, "Miss")
        rec = mode._records[-1]
        self.assertEqual(rec["class"], "hit")
        self.assertAlmostEqual(rec["span_ms"], 50.0, places=3)
        # 6 completion + round(2 * (1 - 50/250)) + 2 quiet = 10.
        self.assertEqual(outcome.points, 10)

    def test_span_past_the_window_is_a_late_chord(self) -> None:
        engine, mode = _build_mode()
        t = _burn_probes(mode)
        mode._fire(t)
        # 300 ms span against the opening 250 ms window: completed but
        # not together, so completion and quiet pay, togetherness not.
        _complete_chord(mode, t + 0.3, gap_s=0.3)
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Late")
        rec = mode._records[-1]
        self.assertEqual(rec["class"], "late_chord")
        self.assertEqual(outcome.points, 8)

    def test_timeout_with_some_fingers_keeps_partial_completion(self) -> None:
        engine, mode = _build_mode()
        t = _burn_probes(mode)
        mode._fire(t)
        targets = mode.active.targets
        mode._handle_press(_press(targets[0], t + 0.4), t + 0.4)
        mode._finish(t + 4.0, hold_achieved=None)
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")
        self.assertIsNone(outcome.rt_ms)
        rec = mode._records[-1]
        self.assertEqual(rec["class"], "partial")
        # Half the chord landed, so half the completion points did:
        # a three-of-four chord must not read as a frozen hand.
        self.assertEqual(outcome.points,
                         round(6 * 1 / len(targets)))

    def test_wrong_finger_downgrades_to_miss(self) -> None:
        engine, mode = _build_mode()
        t = _burn_probes(mode)
        mode._fire(t)
        quiet = [l for l in mode.lanes
                 if l not in mode.active.targets][0]
        mode._handle_press(_press(quiet, t + 0.2), t + 0.2)
        engine.apply_wrong_press_penalty.assert_called()
        _complete_chord(mode, t + 0.4)
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")
        self.assertEqual(outcome.points, 0)
        # A quiet finger crossing its own press threshold is the
        # loudest possible leak, so the class says so.
        self.assertEqual(mode._records[-1]["class"], "leak_fail")

    def test_double_tap_on_a_target_is_not_a_wrong_press(self) -> None:
        engine, mode = _build_mode()
        t = _burn_probes(mode)
        mode._fire(t)
        first = mode.active.targets[0]
        mode._handle_press(_press(first, t + 0.2), t + 0.2)
        mode._handle_press(_press(first, t + 0.3), t + 0.3)
        engine.apply_wrong_press_penalty.assert_not_called()
        # The onset kept is the FIRST press: a re-tap must not shrink
        # the measured span.
        self.assertAlmostEqual(mode.active.onsets[first], t + 0.2)

    def test_press_between_trials_costs_the_idle_penalty(self) -> None:
        engine, mode = _build_mode()
        mode._handle_press(_press(0, 1.0), 1.0)
        engine.apply_idle_press_penalty.assert_called_once()
        engine.log_trial.assert_not_called()


class CrossTalkTests(unittest.TestCase):
    """ER is the mode's core number. It has to come from the engine's
    force-window peaks, normalised per finger, and it has to move the
    quiet component of the score, or the mode rewards chords without
    rewarding individuation."""

    def test_er_is_leak_over_press_normalised_per_finger(self) -> None:
        # References from the shipped thresholds: on_delta / 0.40 =
        # (50, 32.5, 37.5, 115) counts. The instructed finger presses
        # exactly its reference (norm 1.0); one quiet finger leaks 10
        # percent of its own reference. ER = mean leak / mean press =
        # (0.1 + 0 + 0) / 3 / 1.0.
        engine, mode = _build_mode()
        mode._fire(5.0)
        lane = mode.active.targets[0]
        quiet = [l for l in mode.lanes if l != lane]
        refs = {0: 50.0, 1: 32.5, 2: 37.5, 3: 115.0}
        peaks = {lane: refs[lane], quiet[0]: 0.1 * refs[quiet[0]]}
        engine._force_window_peak = peaks
        engine._force_window_saw_samples = True
        mode._handle_press(_press(lane, 5.4), 5.4)
        rec = mode._records[-1]
        self.assertAlmostEqual(rec["er"], 0.1 / 3, places=3)
        self.assertEqual(rec["class"], "hit")

    def test_a_leak_past_the_threshold_fails_quiet_and_classes(self) -> None:
        # One quiet finger at 50 percent of the press is 2-3x worse
        # than healthy enslaving: leak_fail, and the quiet points go.
        engine, mode = _build_mode()
        mode._fire(5.0)
        lane = mode.active.targets[0]
        quiet = [l for l in mode.lanes if l != lane]
        refs = {0: 50.0, 1: 32.5, 2: 37.5, 3: 115.0}
        engine._force_window_peak = {
            lane: refs[lane], quiet[0]: 0.5 * refs[quiet[0]]}
        engine._force_window_saw_samples = True
        mode._handle_press(_press(lane, 5.4), 5.4)
        rec = mode._records[-1]
        self.assertEqual(rec["class"], "leak_fail")
        outcome = engine.log_trial.call_args[0][1]
        # 6 completion + 2 together + 0 quiet.
        self.assertEqual(outcome.points, 8)
        self.assertNotEqual(outcome.label, "Miss")

    def test_over_force_flags_without_failing_the_trial(self) -> None:
        engine, mode = _build_mode()
        mode._fire(5.0)
        lane = mode.active.targets[0]
        refs = {0: 50.0, 1: 32.5, 2: 37.5, 3: 115.0}
        engine._force_window_peak = {lane: 3.0 * refs[lane]}
        engine._force_window_saw_samples = True
        mode._handle_press(_press(lane, 5.4), 5.4)
        rec = mode._records[-1]
        self.assertTrue(rec["over_force"])
        self.assertEqual(rec["class"], "over_force")
        outcome = engine.log_trial.call_args[0][1]
        self.assertNotEqual(outcome.label, "Miss")

    def test_keyboard_mode_leaves_er_empty_but_pays_quiet(self) -> None:
        # No FSR samples means no leak measurement. The quiet points
        # must not be withheld for data the hardware never produced;
        # a pressed quiet finger is still caught as a wrong press.
        engine, mode = _build_mode()
        t = _burn_probes(mode)
        mode._fire(t)
        _complete_chord(mode, t + 0.3)
        rec = mode._records[-1]
        self.assertIsNone(rec["er"])
        self.assertEqual(engine.log_trial.call_args[0][1].points, 10)


class ProbeAndMatrixTests(unittest.TestCase):
    """The single-finger probes at the session's edges are what let the
    analysis build a true enslaving matrix and separate trained-task
    gains from transfer, so their balance and their arithmetic are
    load-bearing."""

    def test_session_opens_with_balanced_single_finger_probes(self) -> None:
        _, mode = _build_mode()
        fired = []
        t = 5.0
        while mode._probe_left_start > 0:
            mode._fire(t)
            self.assertEqual(mode.active.kind, "probe")
            self.assertEqual(len(mode.active.targets), 1)
            fired.append(mode.active.fingers[0])
            for lane in mode.active.targets:
                mode._handle_press(_press(lane, t + 0.2), t + 0.2)
            t += 1.0
        self.assertEqual(len(fired), 8)
        for finger in range(4):
            self.assertEqual(fired.count(finger), 2)

    def test_enslaving_matrix_from_probe_peaks(self) -> None:
        engine, mode = _build_mode()
        refs = {0: 50.0, 1: 32.5, 2: 37.5, 3: 115.0}
        t = 5.0
        while mode._probe_left_start > 0:
            mode._fire(t)
            lane = mode.active.targets[0]
            peaks = {lane: refs[lane]}
            for q in mode.lanes:
                if q != lane:
                    # Every quiet finger leaks 10 percent of its own
                    # reference while the instructed one presses 100
                    # percent of its own: every off-diagonal cell
                    # should read 10.0 percent.
                    peaks[q] = 0.1 * refs[q]
            engine._force_window_peak = peaks
            engine._force_window_saw_samples = True
            mode._handle_press(_press(lane, t + 0.4), t + 0.4)
            t += 1.0
        matrix = mode.block_stats()["enslaving_matrix_start"]
        for i in range(4):
            self.assertIsNone(matrix[i][i])
            for j in range(4):
                if i != j:
                    self.assertAlmostEqual(matrix[i][j], 10.0, places=1)


class ProgressionTests(unittest.TestCase):
    """The staircase is the challenge-point control: 8 of the last 10
    clean hits move up, 5 or fewer move down, and the ladder is clamped
    at both ends so a bad run cannot fall off the bottom."""

    def test_eight_of_ten_promotes_on_a_sliding_window(self) -> None:
        # The window SLIDES rather than clearing on promote: clearing
        # capped the climb at one level per 10 trials, which left the
        # top half of both ladders unreachable in a fixed-dose session
        # (a flawless player topped out at 10 of 15 unilaterally, 6
        # within / 4 cross bilaterally). The 8-of-10 criterion is
        # unchanged; a short cooldown spaces consecutive moves.
        _, mode = _build_mode()
        for _ in range(10):
            mode._staircase(True)
        self.assertEqual(mode.level, 1)
        self.assertEqual(len(mode._stair), 10)
        self.assertEqual(mode.highest_level, 1)

    def test_cooldown_spaces_promotions(self) -> None:
        _, mode = _build_mode()
        for _ in range(10):
            mode._staircase(True)
        self.assertEqual(mode.level, 1)
        # The window is still full of hits, but the next promotion
        # waits for LEVEL_CHANGE_COOLDOWN more trials.
        for _ in range(mode.LEVEL_CHANGE_COOLDOWN - 1):
            mode._staircase(True)
        self.assertEqual(mode.level, 1)
        mode._staircase(True)
        self.assertEqual(mode.level, 2)

    def test_flawless_player_can_reach_the_top_of_the_ladder(self) -> None:
        # 100 within-hand chords per unilateral session: the whole
        # 15-level ladder must be reachable, W=100 ms floor included.
        _, mode = _build_mode()
        for _ in range(100):
            mode._staircase(True)
        self.assertEqual(mode.level, mode.max_level)

    def test_five_or_fewer_demotes(self) -> None:
        _, mode = _build_mode()
        mode.level = 2
        for _ in range(10):
            mode._staircase(False)
        self.assertEqual(mode.level, 1)

    def test_six_or_seven_holds_the_level(self) -> None:
        _, mode = _build_mode()
        for hit in [True] * 7 + [False] * 3:
            mode._staircase(hit)
        self.assertEqual(mode.level, 0)

    def test_ladder_is_clamped_at_both_ends(self) -> None:
        _, mode = _build_mode()
        for _ in range(10):
            mode._staircase(False)
        self.assertEqual(mode.level, 0)
        mode.level = mode.max_level
        mode._stair.clear()
        for _ in range(10):
            mode._staircase(True)
        self.assertEqual(mode.level, mode.max_level)


class QuietGateAndHoldTests(unittest.TestCase):
    """The quiet-hand gate and the short hold are what make the leak
    measurement mean something: enslaving is measured from rest, and
    it drifts upward during sustained holds, so the mode enforces the
    first and caps the second."""

    def _fake_detector(self, pressed):
        det = MagicMock()
        det.pressed = pressed
        return det

    def test_chord_waits_for_the_quiet_hand(self) -> None:
        engine, mode = _build_mode()
        engine.detectors = {"right": self._fake_detector([True, False,
                                                          False, False])}
        mode._update_settle(10.0)
        engine.on_stim_multi.assert_not_called()
        # Finger lifts: the quiet clock starts, and only after the
        # full quiet window does the stimulus fire.
        engine.detectors["right"].pressed = [False] * 4
        mode._update_settle(11.0)
        engine.on_stim_multi.assert_not_called()
        mode._update_settle(11.6)
        engine.on_stim_multi.assert_called_once()

    def test_a_press_resets_the_quiet_clock(self) -> None:
        engine, mode = _build_mode()
        det = self._fake_detector([False] * 4)
        engine.detectors = {"right": det}
        mode._update_settle(10.0)
        det.pressed = [False, False, True, False]
        mode._update_settle(10.3)
        self.assertIsNone(mode._quiet_since)
        det.pressed = [False] * 4
        mode._update_settle(10.4)
        mode._update_settle(10.7)
        engine.on_stim_multi.assert_not_called()
        mode._update_settle(10.95)
        engine.on_stim_multi.assert_called_once()

    def test_hold_met_finishes_a_clean_hit(self) -> None:
        engine, mode = _build_mode()
        mode._fsr = True
        det = self._fake_detector([True] * 4)
        engine.detectors = {"right": det}
        t = _burn_probes_fsr(mode, det)
        mode._fire(t)
        det.pressed = [True] * 4
        _complete_chord(mode, t + 0.3)
        self.assertEqual(mode.phase, "hold")
        mode._update_hold(t + 0.3 + 0.1)
        self.assertEqual(mode.phase, "hold")
        mode._update_hold(t + 0.3 + 0.35)
        rec = mode._records[-1]
        self.assertIs(rec["hold"], True)
        self.assertEqual(rec["class"], "hit")

    def test_early_release_fails_the_hold(self) -> None:
        engine, mode = _build_mode()
        mode._fsr = True
        det = self._fake_detector([True] * 4)
        engine.detectors = {"right": det}
        t = _burn_probes_fsr(mode, det)
        mode._fire(t)
        det.pressed = [True] * 4
        _complete_chord(mode, t + 0.3)
        self.assertEqual(mode.phase, "hold")
        det.pressed = [False] * 4
        mode._update_hold(t + 0.35)
        rec = mode._records[-1]
        self.assertIs(rec["hold"], False)
        self.assertEqual(rec["class"], "no_hold")


def _burn_probes_fsr(mode, det, t: float = 5.0) -> float:
    """Probe burner for the FSR harness: keeps the fake detector down
    through each probe's hold so the probes close cleanly."""
    while mode._probe_left_start > 0:
        mode._fire(t)
        det.pressed = [True] * 4
        for lane in mode.active.targets:
            mode._handle_press(_press(lane, t + 0.2), t + 0.2)
        if mode.phase == "hold":
            mode._update_hold(t + 0.2 + mode.hold_s + 0.05)
        det.pressed = [False] * 4
        t += 1.0
    return t


class SessionFlowTests(unittest.TestCase):
    """The session shape is the dose: probes at both edges, enforced
    rests between rounds, a fatigue guard judged against the first
    round, and a wall-clock ceiling. These are what make 100 chords
    safe to hand a stroke patient."""

    def _small_mode(self, **overrides):
        kwargs = dict(probe_trials_per_finger=1, trials_per_subblock=2,
                      subblocks=2, iti_min_s=0.0, iti_max_s=0.0)
        kwargs.update(overrides)
        return _build_mode(**kwargs)

    def _play_chord(self, mode, t: float, hit: bool = True) -> None:
        mode._fire(t)
        gap = 0.02 if hit else 0.5
        _complete_chord(mode, t + 0.3, gap_s=gap)

    def test_rest_between_rounds_gates_on_the_floor(self) -> None:
        engine, mode = self._small_mode()
        t = _burn_probes(mode)
        self._play_chord(mode, t)
        self._play_chord(mode, t + 2.0)
        self.assertEqual(mode.phase, "rest")
        self.assertEqual(mode._rest_kind, "between")
        # Before the floor a press does nothing; after it, any finger
        # moves on.
        mode._handle_press(_press(0, t + 5.0), t + 5.0)
        self.assertEqual(mode.phase, "rest")
        mode._handle_press(_press(0, t + 40.0), t + 40.0)
        self.assertEqual(mode.phase, "settle")

    def test_fatigue_drop_forces_a_longer_rest(self) -> None:
        engine, mode = self._small_mode(subblocks=3)
        t = _burn_probes(mode)
        # First round clean, second round all late chords: hit rate
        # drops 100 points, which is well past the 30-point trigger.
        self._play_chord(mode, t, hit=True)
        self._play_chord(mode, t + 2.0, hit=True)
        mode._leave_rest(t + 40.0)
        self._play_chord(mode, t + 45.0, hit=False)
        self._play_chord(mode, t + 47.0, hit=False)
        self.assertEqual(mode._fatigue_triggers, 1)
        self.assertEqual(mode._rest_kind, "fatigue")
        engine.finish_block.assert_not_called()

    def test_second_fatigue_trigger_ends_the_session(self) -> None:
        engine, mode = self._small_mode(subblocks=3)
        t = _burn_probes(mode)
        self._play_chord(mode, t, hit=True)
        self._play_chord(mode, t + 2.0, hit=True)
        mode._fatigue_triggers = 1
        mode._leave_rest(t + 40.0)
        self._play_chord(mode, t + 45.0, hit=False)
        self._play_chord(mode, t + 47.0, hit=False)
        engine.finish_block.assert_called_once()
        self.assertEqual(mode.end_reason, "fatigue")

    def test_session_cap_ends_at_a_trial_close(self) -> None:
        engine, mode = self._small_mode(session_cap_min=1.0)
        mode._t0 = 0.0
        mode._fire(100.0)
        for lane in mode.active.targets:
            mode._handle_press(_press(lane, 100.2), 100.2)
        engine.finish_block.assert_called_once()
        self.assertEqual(mode.end_reason, "time_cap")

    def test_full_session_closes_with_probes_then_finishes(self) -> None:
        engine, mode = self._small_mode()
        t = _burn_probes(mode)
        for _ in range(2):
            self._play_chord(mode, t)
            t += 2.0
        mode._leave_rest(t + 40.0)
        t += 45.0
        for _ in range(2):
            self._play_chord(mode, t)
            t += 2.0
        # Closing probes: 1 per finger.
        for _ in range(4):
            mode._fire(t)
            self.assertEqual(mode.active.kind, "probe")
            for lane in mode.active.targets:
                mode._handle_press(_press(lane, t + 0.2), t + 0.2)
            t += 1.0
        engine.finish_block.assert_called_once()
        self.assertEqual(mode.end_reason, "completed")
        kinds = [r["kind"] for r in mode._records]
        self.assertEqual(kinds,
                         ["probe"] * 4 + ["chord"] * 4 + ["probe"] * 4)

    def test_pause_shifts_inflight_deadlines(self) -> None:
        # A chord with one finger down and one to go is the worst case
        # for a pause: both the stim clock and the landed onset must
        # slide, or the span and RT measure the pause.
        _, mode = _build_mode()
        mode._t0 = 100.0
        t = _burn_probes(mode, 105.0)
        mode._fire(t)
        lane = mode.active.targets[0]
        mode._handle_press(_press(lane, t + 0.2), t + 0.2)
        self.assertIsNotNone(mode.active)
        mode.on_resume(5.0)
        self.assertAlmostEqual(mode.active.stim_t_perf, t + 5.0)
        self.assertAlmostEqual(mode.active.onsets[lane], t + 5.2)
        # The session-cap clock must not count the pause either.
        self.assertAlmostEqual(mode._t0, 105.0)


class KeyboardFallbackTests(unittest.TestCase):
    """JKL; must keep working with an Arduino connected, same contract
    as every other mode: a busted auto-detect must never leave the
    therapist with no input."""

    def test_keydown_queues_a_press(self) -> None:
        import pygame
        engine, mode = _build_mode()
        engine.cfg.get = MagicMock(return_value={"j": 0, "semicolon": 3})
        e = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_j)
        mode.handle_event(e)
        self.assertEqual(len(mode._presses), 1)
        self.assertEqual(mode._presses[0].lane, 0)


class ArpeggioCueTests(unittest.TestCase):
    """The buzzer cue for a chord. The four motors on a board share one
    driver, so a chord's haptic cue has to be sequential pulses spaced
    at least a full firmware hold apart, and mirror's two boards must
    keep buzzing together."""

    def _engine(self, hand_mode="right"):
        from finger_rehab.game.engine import GameEngine
        e = GameEngine.__new__(GameEngine)
        e.cfg = MagicMock()
        e.cfg.get = MagicMock(side_effect=lambda k, d=None: {
            "cue.buzz_before": True,
            "cue.buzz_after": False,
            "cue.sound_before": False,
            "cue.sound_after": False,
            "cue.show_target": True,
            "motor.cue_ms": 250,
            "motor.pulse_interval_ms": 120,
            "motor.arpeggio_gap_ms": 40,
            "game.timeout_s": 1.0,
            "fsr.num_sensors_per_hand": 4,
        }.get(k, d))
        sent = []
        src = MagicMock()
        src.send_command = lambda c: (sent.append(c) or True)
        e.source = src
        e._sent = sent
        e.hand_mode = hand_mode
        e.audio = None
        e.raw_logger = None
        e._screens = {}
        e.mode = None
        e.detectors = {}
        e._ensure_metric_state()
        return e

    def test_same_board_chord_becomes_a_spaced_arpeggio(self) -> None:
        e = self._engine()
        e.on_stim_multi([1, 2, 3], trial_id=1, t_perf=0.0)
        stims = [c for c in e._sent if c.startswith("STIM")]
        # Only the first finger buzzes now; the rest are queued.
        self.assertEqual(stims, ["STIM:2"])
        self.assertNotIn("STOP", e._sent)
        queued = sorted(e._motor_queue, key=lambda x: x[1])
        self.assertEqual([ln for ln, _ in queued], [2, 3])
        # Onsets a full firmware pulse plus the gap apart, so no pulse
        # is cut short by the next and the one-motor guard never has
        # to issue a STOP mid-cue.
        dues = [due for _, due in queued]
        gap = dues[1] - dues[0]
        self.assertGreaterEqual(gap, e.FIRMWARE_STIM_MS / 1000.0)
        self.assertAlmostEqual(gap, 0.190, places=2)

    def test_arpeggio_order_is_fixed_low_to_high(self) -> None:
        e = self._engine()
        # Handed in scrambled order: the cue still runs index to pinky
        # so the sequence cannot be read as a required press order.
        e.on_stim_multi([3, 0, 2], trial_id=1, t_perf=0.0)
        stims = [c for c in e._sent if c.startswith("STIM")]
        self.assertEqual(stims, ["STIM:1"])
        queued = sorted(e._motor_queue, key=lambda x: x[1])
        self.assertEqual([ln for ln, _ in queued], [2, 3])

    def test_two_boards_still_buzz_together(self) -> None:
        # Mirror mode: same finger, both hands. Two boards, two
        # drivers, no reason to sequence them.
        e = self._engine("both")
        e.on_stim_multi([1, 5], trial_id=1, t_perf=0.0)
        stims = [c for c in e._sent if c.startswith("STIM")]
        self.assertEqual(sorted(stims), ["STIM:2", "STIM:6"])

    def test_single_target_keeps_the_held_cue(self) -> None:
        e = self._engine()
        e.on_stim_multi([2], trial_id=1, t_perf=0.0)
        self.assertEqual([c for c in e._sent if c.startswith("STIM")],
                         ["STIM:3"])
        # The held cue re-arms the SAME motor out to motor.cue_ms.
        self.assertTrue(all(ln == 2 for ln, _ in e._motor_queue))
        self.assertTrue(e._motor_queue)


class EngineIntegrationTests(unittest.TestCase):
    """begin_chords_block through to the CSV and metadata on disk: the
    path a real session takes, where a broken column value or a missing
    summary would show up."""

    def test_block_writes_chord_rows_and_summary(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            with tempfile.TemporaryDirectory() as td:
                cfg = Config.load()
                cfg.data["ui"]["resolution"] = [640, 480]
                cfg.data["audio"]["enabled"] = False
                cfg.data["session"]["data_dir"] = td
                cfg.data["report"] = {"enabled": False}
                # Test Mode gives the miniature (two probes then
                # chords) so the demo path a supervisor sees is what
                # gets exercised.
                cfg.data["game"]["test_mode_enabled"] = True
                cfg.data["game"]["test_mode_trials"] = 4
                cfg.data["session"]["participant"] = "Basil"
                eng = GameEngine(cfg, KeyboardOnlySource())
                eng.session.participant = "Basil"
                gp = MagicMock()
                gp.lanes = []
                eng._screens = {"gameplay": gp, "results": MagicMock()}
                eng.begin_chords_block()
                self.assertEqual(eng.current_block, "chords")
                mode = eng.mode
                mode._t0 = 0.0
                # The demo miniature opens with two probes; play them
                # and one chord so both trial kinds land in the CSV.
                t = 100.0
                n_probes = mode._probe_left_start
                while mode._probe_left_start > 0:
                    mode._fire(t)
                    self.assertEqual(mode.active.kind, "probe")
                    for lane in mode.active.targets:
                        mode._handle_press(_press(lane, t + 0.3), t + 0.3)
                    t += 2.0
                mode._fire(t)
                self.assertEqual(mode.active.kind, "chord")
                targets = mode.active.targets
                tp = t + 0.3
                for lane in targets:
                    mode._handle_press(_press(lane, tp), tp)
                    tp += 0.05
                root = Path(eng.session_paths.root)
                eng.finish_block()
                with (root / "trials.csv").open() as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), n_probes + 1)
                probe_row, chord_row = rows[0], rows[-1]
                self.assertEqual(probe_row["stimulus"],
                                 str(probe_row["lane"]))
                self.assertEqual(probe_row["correct_keys"],
                                 str(probe_row["lane"]))
                self.assertEqual(chord_row["stimulus"], "+".join(
                    str(l + 1) for l in targets))
                self.assertEqual(chord_row["correct_keys"], ",".join(
                    str(l + 1) for l in targets))
                self.assertEqual(chord_row["block"], "chords")
                meta = json.loads((root / "metadata.json").read_text())
                stats = meta["block_summary"]["chords"]
                self.assertTrue(stats["demo"])
                self.assertEqual(stats["n_probes"] + stats["n_chords"],
                                 n_probes + 1)
                self.assertIn("enslaving_matrix_start", stats)
        finally:
            pygame.quit()


# ---- hold trace replay -----------------------------------------------------
class _TraceClock:
    """Stand-in for the time module inside the chords module: the
    replay advances it sample by sample so the mode's own
    time.perf_counter() reads simulation time."""

    def __init__(self, t0: float = 1000.0) -> None:
        self.t = t0

    def perf_counter(self) -> float:
        return self.t


class _MessageScreen:
    """Records every centre-screen message with its simulation time,
    so a test can pin not just the words but WHEN they appeared."""

    def __init__(self, clock: _TraceClock) -> None:
        self.clock = clock
        self.messages: list[tuple[float, str, str]] = []
        self.lanes: list = []

    def set_message(self, text, dur, kind="info"):
        self.messages.append((self.clock.t, str(text), kind))


_TRACE_REST = 280.0
_TRACE_PRESS = 620.0
_TRACE_RAMP_S = 0.015


def _trace_value(t: float, windows) -> int:
    """Trapezoid press profile: 15 ms ramp up, flat, 15 ms ramp down,
    the shape a light fingertip press makes on the FSR."""
    v = _TRACE_REST
    for (a, b) in windows:
        if a <= t <= b + _TRACE_RAMP_S:
            if t < a + _TRACE_RAMP_S:
                f = (t - a) / _TRACE_RAMP_S
            elif t > b:
                f = max(0.0, 1.0 - (t - b) / _TRACE_RAMP_S)
            else:
                f = 1.0
            v = max(v, _TRACE_REST + (_TRACE_PRESS - _TRACE_REST) * f)
    return int(v)


class HoldTraceReplayTests(unittest.TestCase):
    """Replays synthetic 200 Hz FSR traces through the REAL detector
    into the mode on a fake clock: fast tap, held press, staggered
    chords with an early release. This is the harness that diagnosed
    the hold confusion Basil reported ("as soon as I press the button
    it seems to go away"): the only hold feedback was a message
    delivered milliseconds AFTER the trial had closed, and a stale
    onset let the last finger complete a chord an earlier finger had
    already left, failing the hold at the very instant of the press.
    Pinned here: a held press satisfies the hold, live progress is
    exposed while the fingers are down (the ring the screen draws), a
    tap fails with wording that names the finger and the action, a
    lifted finger withdraws its onset so no chord completes off
    fingers that are not down together, and re-landing that finger
    recovers the trial."""

    def setUp(self) -> None:
        import finger_rehab.game.modes.chords as chords_mod
        self._chords_mod = chords_mod
        self._real_time = chords_mod.time
        self.clock = _TraceClock()
        chords_mod.time = self.clock

    def tearDown(self) -> None:
        self._chords_mod.time = self._real_time

    def _build(self, probes: int):
        from finger_rehab.game.modes.chords import ChordsMode
        from finger_rehab.game.scoring import ScoreConfig
        from finger_rehab.hardware.fsr_detector import Calibration, FSRDetector
        det = FSRDetector(Calibration(), hand="right")
        engine = MagicMock()
        engine.hand_mode = "right"
        engine.source.provides_samples = True
        engine.detectors = {"right": det}
        engine.calibration_profiles = {}
        engine._force_window_peak = {}
        engine._force_window_saw_samples = False
        screen = _MessageScreen(self.clock)
        engine._screens = {"gameplay": screen}
        engine.cfg.get = MagicMock(side_effect=lambda k, d=None: d)
        mode = ChordsMode(
            engine=engine, hand="right", lanes=[0, 1, 2, 3],
            timeout_s=3.0, sync_windows_ms=[250, 200, 150, 100],
            hold_ms=200, baseline_quiet_ms=500, settle_prompt_s=5.0,
            iti_min_s=1.5, iti_max_s=2.5, trials_per_subblock=20,
            subblocks=5, probe_trials_per_finger=probes,
            rest_between_s=30.0, fatigue_rest_s=120.0,
            session_cap_min=30.0, score_cfg=ScoreConfig(), seed=7,
        )
        det.on_press = mode.queue_press
        mode._t0 = self.clock.t
        return engine, mode, det, screen

    def _replay(self, mode, det, engine, plan_fn):
        """Run the loop: 200 Hz samples into the real detector, mode
        updated every third sample (about 60 Hz). Returns the stim
        time, the hold-progress samples seen, and every phase the
        mode passed through."""
        plan = None
        stim_t = None
        progress: list[float] = []
        phases: list[str] = []
        n = 0
        t_stop = self.clock.t + 8.0
        while self.clock.t < t_stop:
            if mode.active is not None and plan is None:
                stim_t = mode.active.stim_t_perf
                plan = plan_fn(list(mode.active.targets), stim_t)
            vals = tuple(
                _trace_value(self.clock.t, (plan or {}).get(l, []))
                for l in range(4))
            det.feed(self.clock.t, vals)
            if n % 3 == 0:
                mode.update(1 / 60)
                if not phases or phases[-1] != mode.phase:
                    phases.append(mode.phase)
                p = mode.hold_progress()
                if p is not None:
                    progress.append(p)
            if plan is not None and engine.log_trial.called:
                break
            self.clock.t += 1.0 / 200.0
            n += 1
        return stim_t, progress, phases

    def _warn_text(self, screen) -> str:
        warns = [txt for (_, txt, kind) in screen.messages
                 if kind == "warn"]
        return warns[-1] if warns else ""

    def test_a_held_press_satisfies_the_hold_with_live_progress(self):
        engine, mode, det, screen = self._build(probes=2)

        def plan(targets, stim_t):
            s = stim_t + 0.30
            return {targets[0]: [(s, s + 0.40)]}

        _, progress, phases = self._replay(mode, det, engine, plan)
        rec = mode._records[-1]
        self.assertEqual(rec["class"], "hit")
        self.assertIs(rec["hold"], True)
        self.assertIn("hold", phases)
        # The ring's data: progress exposed while the finger is down,
        # monotonic, inside 0..1, and gone once the trial closed.
        self.assertGreaterEqual(len(progress), 3)
        self.assertEqual(progress, sorted(progress))
        self.assertGreaterEqual(progress[0], 0.0)
        self.assertLessEqual(progress[-1], 1.0)
        self.assertIsNone(mode.hold_progress())

    def test_a_tap_names_the_finger_that_lifted(self):
        engine, mode, det, screen = self._build(probes=2)

        def plan(targets, stim_t):
            s = stim_t + 0.30
            self._target = targets[0]
            return {targets[0]: [(s, s + 0.08)]}

        self._replay(mode, det, engine, plan)
        rec = mode._records[-1]
        self.assertEqual(rec["class"], "no_hold")
        from finger_rehab.game.modes.chords import FINGER_NAMES
        expected = FINGER_NAMES[self._target]
        self.assertEqual(self._warn_text(screen),
                         f"{expected} lifted too soon")
        for (_, txt, _) in screen.messages:
            self.assertNotIn("beat", txt.lower())
        # The together bonus is forfeited on a broken hold: 6
        # completion + 2 quiet, never the full 10 the old build paid
        # while scolding.
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.points, 8)

    def test_a_lifted_finger_withdraws_its_onset(self):
        engine, mode, det, screen = self._build(probes=0)

        def plan(targets, stim_t):
            a, b = targets[0], targets[1]
            s = stim_t + 0.30
            return {a: [(s, s + 0.08)],
                    b: [(s + 0.20, s + 0.60)]}

        stim_t, _, phases = self._replay(mode, det, engine, plan)
        rec = mode._records[-1]
        # The old build closed this trial no_hold at the INSTANT the
        # second finger landed (its onset window satisfied W through
        # the first finger's stale onset), an unavoidable fail the
        # message then lectured about. Now the chord never completes
        # off a lifted finger: no hold phase, and the trial runs its
        # full response window before closing partial.
        self.assertNotIn("hold", phases)
        self.assertEqual(rec["class"], "partial")
        close_t = engine.log_trial.call_args[0][2]
        self.assertGreaterEqual(close_t - stim_t, 2.9)
        self.assertEqual(self._warn_text(screen),
                         "Press together and keep them down")

    def test_relanding_the_lifted_finger_recovers_the_chord(self):
        engine, mode, det, screen = self._build(probes=0)

        def plan(targets, stim_t):
            a, b = targets[0], targets[1]
            s = stim_t + 0.30
            return {a: [(s, s + 0.08), (s + 0.35, s + 0.90)],
                    b: [(s + 0.20, s + 0.60)]}

        _, progress, phases = self._replay(mode, det, engine, plan)
        rec = mode._records[-1]
        self.assertEqual(rec["class"], "hit")
        self.assertIs(rec["hold"], True)
        self.assertIn("hold", phases)
        # Span is measured on the chord that actually formed: the
        # re-landed onset, not the withdrawn tap.
        self.assertLessEqual(rec["span_ms"], 250.0)
        self.assertGreater(len(progress), 0)


class RtIsFirstOnsetTests(unittest.TestCase):
    """Audit finding #19: rt_ms must be the brief's RT (first target
    onset minus go), not chord completion (last onset minus go), or
    classify()'s speed tiers and the results screen's RT cards read a
    slow chord as a fast press."""

    def test_rt_ms_is_first_onset_not_last(self) -> None:
        engine, mode = _build_mode()
        t = _burn_probes(mode)
        mode._fire(t)
        targets = mode.active.targets
        stim_t = mode.active.stim_t_perf
        # First press 300ms after stim, second 350ms after: rt_ms must
        # read 300 (first onset), not 350 (completion/last onset).
        mode._handle_press(_press(targets[0], stim_t + 0.30), stim_t + 0.30)
        mode._handle_press(_press(targets[1], stim_t + 0.35), stim_t + 0.35)
        rec = mode._records[-1]
        self.assertAlmostEqual(rec["rt_ms"], 300.0, delta=2.0)
        self.assertAlmostEqual(rec["complete_ms"], 350.0, delta=2.0)
        outcome = engine.log_trial.call_args[0][1]
        self.assertAlmostEqual(outcome.rt_ms, 300.0, delta=2.0)


class LeakFeedbackNamesFingerTests(unittest.TestCase):
    """Audit finding #26: a measured leak fail (no wrong press) must
    name the offending finger, the argmax of leak_norms, not a generic
    'Quiet fingers leaked'."""

    def test_measured_leak_fail_names_the_worst_finger(self) -> None:
        engine, mode = _build_mode()
        mode._fire(5.0)
        lane = mode.active.targets[0]
        quiet = [l for l in mode.lanes if l != lane]
        refs = {0: 50.0, 1: 32.5, 2: 37.5, 3: 115.0}
        engine._force_window_peak = {
            lane: refs[lane], quiet[0]: 0.5 * refs[quiet[0]]}
        engine._force_window_saw_samples = True
        orig = mode._feedback_text
        captured = {}

        def wrap(*a, **kw):
            text = orig(*a, **kw)
            captured["text"] = text
            return text
        mode._feedback_text = wrap
        mode._handle_press(_press(lane, 5.4), 5.4)
        rec = mode._records[-1]
        self.assertEqual(rec["class"], "leak_fail")
        self.assertIn("leaked, keep it still", captured["text"])
        self.assertNotEqual(captured["text"], "Quiet fingers leaked")


class BilateralHandColumnTests(unittest.TestCase):
    """Audit finding #25: a chord trial's hand column must carry the
    trial's own side, not the block-level 'both', or trials.csv cannot
    be filtered on hand alone in bilateral play."""

    def test_log_trial_gets_the_trial_own_hand(self) -> None:
        engine, mode = _build_mode(
            hand="right", lanes=[0, 1, 2, 3],
            lanes_by_hand={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        t = _burn_probes(mode)
        mode._fire(t)
        fired_hand = mode.active.hand
        _complete_chord(mode, t + 0.3)
        kwargs = engine.log_trial.call_args.kwargs
        self.assertEqual(kwargs["hand"], fired_hand)
        self.assertIn(fired_hand, ("left", "right"))


class PerChordSplitByWindowTests(unittest.TestCase):
    """Audit finding #21: block_stats' per-chord table must split on
    the synchrony window as well as hand and chord, since the level
    ladder interleaves tier and window and a skilled player's easy
    chords are met at wide windows while hard ones are first met at
    the tightest."""

    def test_per_chord_table_carries_w_ms_and_splits_on_it(self) -> None:
        engine, mode = _build_mode()
        t = _burn_probes(mode)
        # Two chord hits at different windows for the mode's current
        # chord, forced by changing the level between fires.
        mode._fire(t)
        _complete_chord(mode, t + 0.3, gap_s=0.01)
        mode.level = 4          # bumps the window tier down
        t2 = t + 2.0
        mode._fire(t2)
        _complete_chord(mode, t2 + 0.3, gap_s=0.01)
        stats = mode.block_stats()
        w_values = {row["w_ms"] for row in stats["per_chord"]}
        self.assertGreaterEqual(len(w_values), 1)
        for row in stats["per_chord"]:
            self.assertIn("w_ms", row)


class ChordsResultsScreenCardsTests(unittest.TestCase):
    """Audit finding #23: a chords block must not fall through to the
    generic results cards (HIT RATE counting every non-Miss, AVG RT
    mixing probe RTs with chord completion times); it needs its own
    cards built from the mode's own outcome classes."""

    def _draw_chords_results(self, block_summary_chords):
        import pygame
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.ui.screens import ResultsScreen
        from finger_rehab.ui.theme import get as get_theme
        from finger_rehab.ui.widgets import Layout
        pygame.init()
        pygame.font.init()
        pygame.display.set_mode((1280, 800))
        e = GameEngine.__new__(GameEngine)
        e.cfg = Config.load()
        e.theme = get_theme("clinical")
        e.layout = Layout(1280, 800, 1.0)
        e.hits, e.misses, e.score = 100, 20, 500
        e.current_block, e.hand_mode = "chords", "right"
        e.best_streak, e.per_lane_stats = 5, {}
        e.hit_streak = 5
        e.last_session_root = None
        e.mode = None
        e.session = type("S", (), {
            "participant": "T", "age": "60",
            "block_summary": {"chords": block_summary_chords}})()
        e.stop_all_motors = lambda *a, **k: None
        e.overall_mean_rt = lambda: 300.0
        e.overall_best_rt = lambda: 200.0
        r = ResultsScreen(e)
        r._shown_t = 1.0
        cards = []
        r._draw_stat_card = (
            lambda surf, rect, lbl, val, col: cards.append((lbl, val)))
        surf = pygame.Surface((1280, 800))
        r.draw(surf)
        pygame.quit()
        return cards

    def test_chords_results_use_clean_hit_rate_not_generic_hit_rate(
            self) -> None:
        # 100 non-Miss trials out of 120 (83%), but only 20 are clean
        # "hit" outcomes (20%): the generic card must not appear.
        cards = self._draw_chords_results({
            "outcome_classes": {"hit": 20, "late_chord": 40,
                                "leak_fail": 20, "no_hold": 20},
            "median_er": 0.4, "level_highest": 5,
            "over_force_trials": 3,
        })
        labels = [lbl for lbl, _ in cards]
        values = dict(cards)
        self.assertNotIn("HIT RATE", labels)
        self.assertNotIn("AVG RT", labels)
        self.assertNotIn("BEST RT", labels)
        self.assertIn("CLEAN HIT RATE", labels)
        self.assertEqual(values["CLEAN HIT RATE"], "20%")
        self.assertIn("MEDIAN ER", labels)
        self.assertIn("LEAK FAILS", labels)
        self.assertIn("OVER-FORCE", labels)

    def test_clean_hit_rate_prefers_the_scope_pure_count(self) -> None:
        # The card used to divide by EVERY record, so the 16-32
        # near-guaranteed probes and the cross-scope chords diluted
        # it: the headline moved with the session's probe:chord mix,
        # not skill. 32 probes all hit + 60 within (30 hit) + 40
        # cross would pool to 47%; the chord-only rate is 50%.
        cards = self._draw_chords_results({
            "outcome_classes": {"hit": 62, "late_chord": 30,
                                "leak_fail": 40},
            "chord_outcome_classes": {"hit": 30, "late_chord": 30},
            "median_er": 0.1, "level_highest": 5,
            "over_force_trials": 0,
        })
        values = dict(cards)
        self.assertEqual(values["CLEAN HIT RATE"], "50%")


class DisconnectedSourceTests(unittest.TestCase):
    """Audit finding #27: a dropped serial connection must not freeze
    the quiet gate forever on a stale press latch, and the settle
    prompt should say the sensor connection dropped rather than
    repeating advice that cannot fix it."""

    def test_disconnect_clears_frozen_detector_pressed_state(self) -> None:
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.fsr_detector import FSRDetector, Calibration

        class FakeSource:
            provides_samples = True
            is_connected = True
            name = "fake"

        e = GameEngine.__new__(GameEngine)
        e.source = FakeSource()
        e._source_was_connected = True
        e.raw_logger = None
        e.hand_mode = "right"
        det = FSRDetector(Calibration(), "right")
        # A finger is "down" the instant the connection drops: with no
        # more samples ever arriving, nothing would clear this bit
        # without the engine doing it on the disconnect transition.
        det.pressed = [True, False, False, False]
        e.detectors = {"right": det}

        e.source.is_connected = False
        e._check_source_connection()
        self.assertEqual(det.pressed, [False, False, False, False])

    def _busy_hand_mode(self, connected: bool):
        """A ChordsMode whose hand detector reads permanently pressed,
        the shape both a genuinely busy hand and a frozen post-
        disconnect detector produce: _hand_quiet() never returns
        True, so the settle gate stays in its prompt branch."""
        engine, mode = _build_mode()
        mode._fsr = True
        engine.source.provides_samples = True
        engine.source.is_connected = connected
        stuck = type("StuckDetector", (), {})()
        stuck.pressed = [True, False, False, False]
        engine.detectors = {"right": stuck}
        mode._settle_t0 = 0.0
        mode._quiet_since = None
        mode._prompt_t = -100.0
        return engine, mode

    def test_settle_prompt_names_the_dropped_sensor(self) -> None:
        _, mode = self._busy_hand_mode(connected=False)
        captured = {}
        orig = mode._set_message

        def wrap(text, *a, **kw):
            captured["text"] = text
            return orig(text, *a, **kw)
        mode._set_message = wrap
        mode._update_settle(mode.settle_prompt_s + 1.0)
        self.assertEqual(captured.get("text"), "Sensor connection lost")

    def test_settle_prompt_says_relax_when_connected(self) -> None:
        _, mode = self._busy_hand_mode(connected=True)
        captured = {}
        orig = mode._set_message

        def wrap(text, *a, **kw):
            captured["text"] = text
            return orig(text, *a, **kw)
        mode._set_message = wrap
        mode._update_settle(mode.settle_prompt_s + 1.0)
        self.assertEqual(captured.get("text"), "Relax your hand")


class CrossLadderTests(unittest.TestCase):
    """The cross-hand ladder is the bimanual manipulation: mirror
    chords first (the symmetry advantage), asymmetry and size costed
    explicitly. The briefed D_cross values are recomputed from the
    formula every run, exactly like the within-hand ladder tests."""

    EXPECTED_D_CROSS = {
        ((0,), (0,)): 4.0, ((3,), (3,)): 6.0,
        ((1,), (1,)): 8.0, ((2,), (2,)): 8.0,
        ((2, 3), (2, 3)): 7.0, ((0, 1), (0, 1)): 9.0,
        ((1, 2), (1, 2)): 9.0,
        ((0,), (1,)): 9.0, ((1,), (0,)): 9.0,
        ((2,), (3,)): 10.0, ((3,), (2,)): 10.0,
        ((1,), (2,)): 11.0, ((2,), (1,)): 11.0,
        ((0,), (2,)): 12.0, ((0,), (1, 2)): 12.5,
        ((0,), (3,)): 14.0, ((0, 1), (2, 3)): 17.0,
    }

    def test_cross_difficulty_reproduces_the_briefed_values(self) -> None:
        from finger_rehab.game.modes.chords import chord_difficulty_cross
        for (left, right), d in self.EXPECTED_D_CROSS.items():
            self.assertAlmostEqual(chord_difficulty_cross(left, right),
                                   d, places=3,
                                   msg=f"{left}|{right}")

    def test_tiers_cover_the_brief_and_step_up_in_hardness(self) -> None:
        from finger_rehab.game.modes.chords import (CROSS_TIERS,
                                             chord_difficulty_cross)
        listed = [c for tier in CROSS_TIERS for c in tier]
        self.assertEqual(set(listed), set(self.EXPECTED_D_CROSS))
        self.assertEqual(len(listed), len(self.EXPECTED_D_CROSS))
        medians = []
        for tier in CROSS_TIERS:
            ds = sorted(chord_difficulty_cross(l, r) for l, r in tier)
            medians.append(ds[len(ds) // 2])
        self.assertEqual(medians, sorted(medians))

    def test_every_cross_chord_is_two_to_four_fingers_both_hands(
            self) -> None:
        from finger_rehab.game.modes.chords import CROSS_TIERS
        for tier in CROSS_TIERS:
            for left, right in tier:
                self.assertGreaterEqual(len(left), 1)
                self.assertGreaterEqual(len(right), 1)
                self.assertLessEqual(len(left) + len(right), 4)

    def test_mirror_tiers_have_zero_asymmetry(self) -> None:
        from finger_rehab.game.modes.chords import (CROSS_TIERS,
                                             cross_mirror_distance)
        for tier in CROSS_TIERS[:2]:
            for left, right in tier:
                self.assertEqual(cross_mirror_distance(left, right), 0.0)
        for tier in CROSS_TIERS[2:]:
            for left, right in tier:
                self.assertGreater(cross_mirror_distance(left, right), 0.0)

    def test_cross_label_reads_left_bar_right(self) -> None:
        from finger_rehab.game.modes.chords import cross_label
        self.assertEqual(cross_label((0,), (1,)), "I|M")
        self.assertEqual(cross_label((0, 1), (2, 3)), "IM|RP")


def _build_bilateral(**overrides):
    """_build_mode with both hands' lanes wired, the shape
    begin_chords_block passes for hand_mode 'both'."""
    kwargs = dict(
        hand="right",
        lanes=[0, 1, 2, 3],
        lanes_by_hand={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]},
    )
    kwargs.update(overrides)
    return _build_mode(**kwargs)


class ScopeScheduleTests(unittest.TestCase):
    """Scope-pure sub-blocks: the third and fifth of each five deal
    cross-hand chords, in a fixed order, bilateral only. A short
    custom config still gets at least one cross sub-block."""

    def test_default_five_subblocks_run_w_w_x_w_x(self) -> None:
        _, mode = _build_bilateral()
        self.assertEqual(mode._scope_seq,
                         ["within", "within", "cross", "within",
                          "cross"])

    def test_two_subblocks_still_get_one_cross(self) -> None:
        _, mode = _build_bilateral(subblocks=2)
        self.assertEqual(mode._scope_seq, ["within", "cross"])

    def test_unilateral_never_draws_cross(self) -> None:
        _, mode = _build_mode()
        self.assertEqual(set(mode._scope_seq), {"within"})
        self.assertEqual(mode.current_scope, "within")


class CrossPlayTests(unittest.TestCase):
    """A cross sub-block's chords span both hands and are logged
    distinctly: 'x:' stimulus, scope on the record, per-hand ER,
    lead-lag, and their own staircase. Nothing here may leak into the
    within-hand aggregates."""

    def _mode_in_cross(self, **overrides):
        """A bilateral mode advanced into its first cross sub-block
        (two within sub-blocks of 1 trial each, then cross)."""
        kwargs = dict(trials_per_subblock=1, subblocks=5)
        kwargs.update(overrides)
        engine, mode = _build_bilateral(**kwargs)
        t = _burn_probes(mode)
        for _ in range(2):          # the two within sub-blocks
            self.assertEqual(mode.current_scope, "within")
            mode._fire(t)
            self.assertEqual(mode.active.scope, "within")
            _complete_chord(mode, t + 0.3, gap_s=0.01)
            mode.phase = "settle"   # skip the rest gate
            mode._rest_until = None
            t += 2.0
        self.assertEqual(mode.current_scope, "cross")
        return engine, mode, t

    def test_cross_chord_spans_both_hands(self) -> None:
        engine, mode, t = self._mode_in_cross()
        mode._fire(t)
        trial = mode.active
        self.assertEqual(trial.kind, "chord")
        self.assertEqual(trial.scope, "cross")
        left = [l for l in trial.targets if l >= 4]
        right = [l for l in trial.targets if l < 4]
        self.assertGreaterEqual(len(left), 1)
        self.assertGreaterEqual(len(right), 1)
        # Tier XB1: mirror singles, one finger per hand.
        self.assertEqual(len(trial.targets), 2)
        self.assertEqual(trial.fingers_left, trial.fingers_right)
        # The stim goes out through the shared multi-lane path (the
        # EEG marker layer hangs off it, unchanged).
        lanes_sent = engine.on_stim_multi.call_args[0][0]
        self.assertEqual(sorted(lanes_sent), sorted(trial.targets))

    def test_cross_stimulus_descriptor_is_marked(self) -> None:
        engine, mode, t = self._mode_in_cross()
        mode._fire(t)
        targets = mode.active.targets
        _complete_chord(mode, t + 0.3, gap_s=0.01)
        kwargs = engine.log_trial.call_args.kwargs
        expected = "x:" + "+".join(str(l + 1) for l in targets)
        self.assertEqual(kwargs["stimulus"], expected)
        # hand=None keeps the block-level 'both' on the row: the trial
        # genuinely used both hands.
        self.assertIsNone(kwargs["hand"])

    def test_cross_record_carries_the_bimanual_fields(self) -> None:
        engine, mode, t = self._mode_in_cross()
        mode._fire(t)
        trial = mode.active
        # Right hand leads by 80 ms.
        right = [l for l in trial.targets if l < 4]
        left = [l for l in trial.targets if l >= 4]
        mode._handle_press(_press(right[0], t + 0.30), t + 0.30)
        mode._handle_press(_press(left[0], t + 0.38), t + 0.38)
        rec = mode._records[-1]
        self.assertEqual(rec["scope"], "cross")
        self.assertEqual(rec["hand"], "both")
        self.assertIn("|", rec["chord"])
        self.assertTrue(rec["mirror"])
        self.assertEqual(rec["asym"], 0.0)
        self.assertEqual(rec["lead_hand"], "right")
        self.assertAlmostEqual(rec["lag_ms"], 80.0, delta=2.0)
        self.assertIsNone(rec["er"])
        from finger_rehab.game.modes.chords import chord_difficulty_cross
        self.assertAlmostEqual(
            rec["d"], chord_difficulty_cross(trial.fingers_left,
                                             trial.fingers_right))

    def test_cross_er_is_per_hand_and_never_pools(self) -> None:
        engine, mode, t = self._mode_in_cross()
        mode._fire(t)
        trial = mode.active
        refs = {l: 50.0 for l in range(8)}
        peaks = {l: 0.0 for l in range(8)}
        for l in trial.targets:
            peaks[l] = 50.0
        # Only the LEFT hand leaks: 20 percent on each quiet finger.
        for l in range(4, 8):
            if l not in trial.targets:
                peaks[l] = 10.0
        engine._force_window_peak = peaks
        engine._force_window_saw_samples = True
        mode._reference_counts = lambda lane: refs[lane]
        _complete_chord(mode, t + 0.3, gap_s=0.01)
        rec = mode._records[-1]
        self.assertAlmostEqual(rec["er_left"], 0.2, places=3)
        self.assertAlmostEqual(rec["er_right"], 0.0, places=3)
        self.assertIsNone(rec["er"])
        # The within-hand summary aggregates must not see this trial.
        stats = mode.block_stats()
        self.assertIsNone(stats["median_er"])

    def test_cross_staircase_is_separate(self) -> None:
        engine, mode = _build_bilateral(trials_per_subblock=30)
        t = _burn_probes(mode)
        mode._sub_idx = 2           # jump into the cross sub-block
        self.assertEqual(mode.current_scope, "cross")
        level_before = mode.level
        for _ in range(10):
            mode._fire(t)
            self.assertEqual(mode.active.scope, "cross")
            _complete_chord(mode, t + 0.2, gap_s=0.01)
            t += 2.0
        self.assertEqual(mode.level_cross, 1)
        self.assertEqual(mode.level, level_before)

    def test_within_chords_in_bilateral_log_mirror_leak(self) -> None:
        engine, mode = _build_bilateral()
        t = _burn_probes(mode)
        mode._fire(t)
        trial = mode.active
        own = mode.hands[trial.hand]
        other = [l for l in range(8) if l not in own]
        peaks = {l: 0.0 for l in range(8)}
        for l in trial.targets:
            peaks[l] = 50.0
        peaks[other[0]] = 5.0          # silent mirror force, 10 percent
        engine._force_window_peak = peaks
        engine._force_window_saw_samples = True
        mode._reference_counts = lambda lane: 50.0
        _complete_chord(mode, t + 0.3, gap_s=0.01)
        rec = mode._records[-1]
        self.assertEqual(rec["scope"], "within")
        self.assertAlmostEqual(rec["mirror_leak"], 0.1, places=3)
        stats = mode.block_stats()
        self.assertAlmostEqual(
            stats["per_hand"][trial.hand]["median_mirror_leak"], 0.1,
            places=3)

    def test_block_stats_split_the_scopes(self) -> None:
        engine, mode, t = self._mode_in_cross()
        mode._fire(t)
        _complete_chord(mode, t + 0.3, gap_s=0.01)
        stats = mode.block_stats()
        self.assertEqual(stats["n_chords"], 2)           # the within pair
        self.assertEqual(stats["cross"]["n_chords"], 1)
        for row in stats["per_chord"]:
            self.assertNotIn("|", row["chord"])
        for row in stats["per_chord_cross"]:
            self.assertIn("|", row["chord"])
        self.assertEqual(stats["scope_sequence"],
                         ["within", "within", "cross", "within",
                          "cross"])
        self.assertIn("hit_rate_mirror", stats["cross"])
        self.assertIn("bilateral_deficit", stats["cross"])


class WarmupTests(unittest.TestCase):
    """The diagnosis behind Basil's 'I get 1 finger at a time': the
    opening probes owned the start of every session with nothing on
    screen saying warm-up, and the old bilateral Test Mode miniature
    was two-thirds probes. Pinned here: the announced warm-up state,
    the demo rebalance, the probe pacing and the hard cap on time to
    the first chord."""

    def test_demo_miniature_is_mostly_chords(self) -> None:
        _, mode = _build_mode(demo_trials=6)
        self.assertEqual(mode._probe_left_start, 1)
        self.assertEqual(mode.trials_per_subblock, 5)
        _, mode = _build_bilateral(demo_trials=6)
        self.assertEqual(mode._probe_left_start, 2)
        self.assertEqual(mode.trials_per_subblock, 4)

    def test_bilateral_demo_alternates_scopes(self) -> None:
        _, mode = _build_bilateral(demo_trials=6)
        t = _burn_probes(mode)
        scopes = []
        for _ in range(4):
            mode._fire(t)
            scopes.append(mode.active.scope)
            _complete_chord(mode, t + 0.3, gap_s=0.01)
            t += 2.0
        self.assertEqual(scopes, ["within", "cross", "within", "cross"])

    def test_warmup_state_counts_down_then_clears(self) -> None:
        _, mode = _build_mode()
        state = mode.warmup_state()
        self.assertEqual(state, ("warmup", 0, 8))
        t = _burn_probes(mode)
        self.assertIsNone(mode.warmup_state())
        # Wind-down state appears once training is done.
        mode._sub_idx = mode.subblocks
        state = mode.warmup_state()
        self.assertEqual(state[0], "winddown")
        self.assertEqual(state[2], 8)

    def test_probes_pace_on_the_warmup_gap(self) -> None:
        _, mode = _build_mode(warmup_iti_s=0.7)
        mode._fire(5.0)
        for lane in mode.active.targets:
            mode._handle_press(_press(lane, 5.2), 5.2)
        # Next trial is still a probe: the gap is the fixed warm-up
        # one, not the jittered chord ITI (1.5-2.5).
        self.assertAlmostEqual(mode._next_ok_t - 5.2, 0.7, delta=0.01)

    def test_warmup_announcement_reaches_the_screen(self) -> None:
        engine, mode = _build_mode()
        seen = []
        gp = MagicMock()
        gp.set_message = lambda text, dur, kind="info": seen.append(text)
        engine._screens = {"gameplay": gp}
        t = _burn_probes(mode)
        self.assertTrue(any(s.startswith("Warm-up 1 of 8")
                            for s in seen), seen)
        mode._fire(t)
        self.assertIn("Warm-up done. Chords: press together", seen)

    def test_warmup_cap_defers_probes_and_starts_chords(self) -> None:
        _, mode = _build_mode(warmup_cap_s=10.0)
        mode._t0 = 0.0
        t = 5.0
        # Two slow probes, then the budget is gone: the remaining six
        # move to the closing set and the next fire is a chord.
        for _ in range(2):
            mode._fire(t)
            for lane in mode.active.targets:
                mode._handle_press(_press(lane, t + 0.2), t + 0.2)
            t += 6.0
        self.assertEqual(mode._probe_left_start, 0)
        self.assertEqual(mode._probe_left_end, 8 + 6)
        mode._fire(t)
        self.assertEqual(mode.active.kind, "chord")
        stats = mode.block_stats()
        self.assertTrue(stats["warmup_capped"])

    def test_warmup_cap_never_fires_inside_the_budget(self) -> None:
        _, mode = _build_mode()
        mode._t0 = 0.0
        t = _burn_probes(mode, t=5.0)
        self.assertFalse(mode._warmup_capped)
        self.assertEqual(mode._probe_left_end, 8)


class FirstChordLatencyTests(unittest.TestCase):
    """The headline regression for the diagnosis, driven through the
    REAL engine under the shipped default config: a compliant player
    (RT 650 ms) meets the first chord inside the first minute in the
    worst case (both hands), and the mode fires exactly the planned
    probes first. Before the fix a bilateral session took ~53 s of
    perfect play (longer in real hands) with nothing announcing the
    warm-up; Test Mode bilateral was 4 probes to 2 chords."""

    def setUp(self) -> None:
        import finger_rehab.game.modes.chords as chords_mod
        self._chords_mod = chords_mod
        self._real_time = chords_mod.time
        self.clock = _TraceClock()
        chords_mod.time = self.clock

    def tearDown(self) -> None:
        self._chords_mod.time = self._real_time

    def _engine(self, td: str):
        import pygame
        pygame.init()
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = False
        cfg.data["session"]["data_dir"] = td
        cfg.data["report"] = {"enabled": False}
        cfg.data["bilateral"]["hand"] = "both"
        cfg.data["chords"]["seed"] = 7
        eng = GameEngine(cfg, KeyboardOnlySource())
        gp = MagicMock()
        gp.lanes = []
        eng._screens = {"gameplay": gp, "results": MagicMock()}
        return eng

    def _drive_to_first_chord(self, mode, react_s: float | None):
        """50 Hz update loop against the trace clock with a scripted
        player. react_s=None never presses (the slowest hand there
        is). Returns (probes seen, seconds to the first chord stim)."""
        from finger_rehab.hardware.fsr_detector import PressEvent
        t_start = self.clock.t
        pending: list[tuple[float, int]] = []
        seen: int | None = None
        probes = 0
        while self.clock.t - t_start < 180.0:
            for (due, lane) in list(pending):
                if self.clock.t >= due:
                    pending.remove((due, lane))
                    mode.queue_press(PressEvent(
                        lane=lane, t_perf=due, value=0,
                        baseline=0.0, hand="both"))
            mode.update(0.02)
            if mode.active is not None and mode.active.trial_id != seen:
                seen = mode.active.trial_id
                if mode.active.kind == "chord":
                    return probes, self.clock.t - t_start
                probes += 1
                if react_s is not None:
                    for i, lane in enumerate(mode.active.targets):
                        pending.append(
                            (self.clock.t + react_s + 0.05 * i, lane))
            self.clock.t += 0.02
        self.fail("no chord fired inside 180 simulated seconds")

    def test_bilateral_first_chord_inside_the_first_minute(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = self._engine(td)
            try:
                eng.begin_chords_block()
                probes, elapsed = self._drive_to_first_chord(
                    eng.mode, react_s=0.65)
                self.assertEqual(probes, 16)
                self.assertLess(elapsed, 60.0)
                self.assertFalse(eng.mode._warmup_capped)
            finally:
                import pygame
                pygame.quit()

    def test_never_pressing_hand_still_meets_a_chord_by_the_cap(
            self) -> None:
        # The pathological case the cap exists for: every probe times
        # out. The first chord must still arrive just past the 60 s
        # budget (one in-flight trial of slack), with the unplayed
        # probes deferred to the closing set.
        with tempfile.TemporaryDirectory() as td:
            eng = self._engine(td)
            try:
                eng.begin_chords_block()
                cap = eng.mode.warmup_cap_s
                timeout = eng.mode.timeout
                probes, elapsed = self._drive_to_first_chord(
                    eng.mode, react_s=None)
                self.assertLess(probes, 16)
                self.assertLess(elapsed, cap + timeout + 3.0)
                self.assertTrue(eng.mode._warmup_capped)
                self.assertGreater(eng.mode._probe_left_end, 16)
            finally:
                import pygame
                pygame.quit()


class EngineCrossIntegrationTests(unittest.TestCase):
    """A bilateral Test Mode session through the real engine: cross
    rows land in trials.csv with the 'x:' stimulus, and the block
    summary carries the cross section next to the unchanged
    within-hand keys."""

    def test_bilateral_demo_writes_cross_rows_and_summary(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            with tempfile.TemporaryDirectory() as td:
                cfg = Config.load()
                cfg.data["ui"]["resolution"] = [640, 480]
                cfg.data["audio"]["enabled"] = False
                cfg.data["session"]["data_dir"] = td
                cfg.data["report"] = {"enabled": False}
                cfg.data["bilateral"]["hand"] = "both"
                cfg.data["game"]["test_mode_enabled"] = True
                cfg.data["game"]["test_mode_trials"] = 6
                cfg.data["session"]["participant"] = "Basil"
                eng = GameEngine(cfg, KeyboardOnlySource())
                eng.session.participant = "Basil"
                gp = MagicMock()
                gp.lanes = []
                eng._screens = {"gameplay": gp, "results": MagicMock()}
                eng.begin_chords_block()
                mode = eng.mode
                mode._t0 = 0.0
                root = Path(eng.session_paths.root)
                t = 100.0
                # Play the whole miniature; the mode ends the block
                # itself (its _end calls engine.finish_block).
                while mode.phase != "done":
                    mode._fire(t)
                    tp = t + 0.3
                    for lane in mode.active.targets:
                        mode._handle_press(_press(lane, tp), tp)
                        tp += 0.02
                    t += 2.0
                with (root / "trials.csv").open() as f:
                    rows = list(csv.DictReader(f))
                cross_rows = [r for r in rows
                              if r["stimulus"].startswith("x:")]
                self.assertEqual(len(cross_rows), 2)
                for r in cross_rows:
                    self.assertEqual(r["hand"], "both")
                    lanes = [int(x) - 1 for x in
                             r["stimulus"][2:].split("+")]
                    self.assertTrue(any(l < 4 for l in lanes))
                    self.assertTrue(any(l >= 4 for l in lanes))
                meta = json.loads((root / "metadata.json").read_text())
                stats = meta["block_summary"]["chords"]
                self.assertEqual(stats["cross"]["n_chords"], 2)
                self.assertEqual(stats["n_chords"], 2)
                self.assertEqual(stats["n_probes"], 2)
        finally:
            pygame.quit()


class MeasurementIntegrityTests(unittest.TestCase):
    """ER, the probe matrices and the headline card must measure what
    they claim: enslaving from complete responses, transfer from
    correctly-cued probes, and a clean-chord rate over chords."""

    def _fsr_chord(self, **over):
        engine, mode = _build_mode(**over)
        mode._fsr = True
        det = MagicMock()
        det.pressed = [True] * 4
        engine.detectors = {"right": det}
        t = _burn_probes_fsr(mode, det)
        mode._fire(t)
        while mode.active.kind != "chord":
            det.pressed = [True] * 4
            for lane in mode.active.targets:
                mode._handle_press(_press(lane, t + 0.2), t + 0.2)
            if mode.phase == "hold":
                mode._update_hold(t + 0.2 + mode.hold_s + 0.05)
            det.pressed = [False] * 4
            t += 1.0
            mode._fire(t)
        return engine, mode, det, t

    def test_partial_chord_records_no_er(self) -> None:
        # The ER denominator averages over EVERY target, so a 1-of-2
        # partial halved it and mechanically doubled er: a hand with a
        # true 0.05 leak recorded er 0.10, and those inflated values
        # drove median_er and the across-session ER curve, where
        # completeness masqueraded as enslaving change.
        engine, mode, det, t = self._fsr_chord()
        trial = mode.active
        self.assertGreater(len(trial.targets), 1)
        pressed_lane = trial.targets[0]
        peaks = {l: 2.5 for l in mode.hands["right"]}
        peaks[pressed_lane] = 50.0
        engine._force_window_peak = peaks
        engine._force_window_saw_samples = True
        mode._reference_counts = lambda lane: 50.0
        det.pressed = [False] * 4
        mode._handle_press(_press(pressed_lane, t + 0.3), t + 0.3)
        mode._finish(t + 4.0, hold_achieved=None)   # timeout, partial
        rec = mode._records[-1]
        self.assertEqual(rec["class"], "partial")
        self.assertIsNone(rec["er"])

    def test_wrong_press_probe_stays_out_of_the_matrix(self) -> None:
        # A cue-misread probe with a full press on a non-instructed
        # finger wrote a ~100% cell into the enslaving matrix, so a
        # start matrix inflated by early cue errors overstated
        # start-to-end individuation gains.
        from finger_rehab.game.modes.chords import ChordsMode
        rec_wrong = {"kind": "probe", "chord": "I", "press_norm": 1.0,
                     "leaks": {"1": 1.0, "2": 0.04, "3": 0.04},
                     "wrong": True}
        rec_clean = {"kind": "probe", "chord": "I", "press_norm": 1.0,
                     "leaks": {"1": 0.05, "2": 0.04, "3": 0.04},
                     "wrong": False}
        matrix = ChordsMode._probe_matrix([rec_wrong, rec_clean])
        # Only the clean probe's leaks appear.
        self.assertAlmostEqual(matrix[0][1], 5.0, places=1)
        self.assertAlmostEqual(matrix[0][2], 4.0, places=1)

    def test_block_stats_name_the_force_reference_basis(self) -> None:
        # Every force quantity in this mode divides by the calibrated
        # light-press gap; the summary says whose numbers those were
        # (profile stamp + participant) or that the config fallback
        # ran, so a mis-referenced session is detectable offline.
        from finger_rehab.hardware.calibration_profile import (
            CalibrationProfile)
        engine, mode = _build_mode()
        basis = mode.block_stats()["reference_basis"]
        self.assertEqual(basis["right"]["basis"], "config_fallback")
        prof = CalibrationProfile(hand="right", participant="Pat",
                                  resting=[100.0] * 4,
                                  press=[160.0] * 4)
        engine.calibration_profiles = {"right": prof}
        basis = mode.block_stats()["reference_basis"]
        self.assertEqual(basis["right"]["basis"], "profile")
        self.assertEqual(basis["right"]["participant"], "Pat")

    def test_block_stats_carry_scope_pure_class_counts(self) -> None:
        engine, mode = _build_mode()
        t = _burn_probes(mode)
        mode._fire(t)
        _complete_chord(mode, t + 0.3, gap_s=0.01)
        stats = mode.block_stats()
        # Probes dominate outcome_classes; the chord-only count holds
        # exactly the one chord played.
        self.assertEqual(sum(stats["chord_outcome_classes"].values()), 1)
        self.assertGreater(sum(stats["outcome_classes"].values()), 1)


class DeviceDropTests(unittest.TestCase):
    """A sensor dropout mid-trial is hardware loss, not patient
    failure: the trial closes as class device_drop, moves neither the
    staircase nor the sub-block hit rate, and is re-dealt."""

    def _fsr_mode(self):
        engine, mode = _build_mode()
        mode._fsr = True
        engine.source.provides_samples = True
        engine.source.is_connected = True
        engine._hands_down = set()
        det = MagicMock()
        det.pressed = [True] * 4
        engine.detectors = {"right": det}
        t = _burn_probes_fsr(mode, det)
        mode._fire(t)
        return engine, mode, det, t

    def _tick(self, mode, now):
        import time as _time
        from unittest.mock import patch
        with patch.object(_time, "perf_counter", return_value=now):
            mode.update(0.016)

    def test_drop_mid_hold_closes_as_device_drop(self) -> None:
        engine, mode, det, t = self._fsr_mode()
        det.pressed = [True] * 4
        _complete_chord(mode, t + 0.3, gap_s=0.01)
        self.assertEqual(mode.phase, "hold")
        sub_done_before = mode._sub_done
        stair_before = len(mode._stair)
        # The real drop: source down, engine clears the latches.
        engine.source.is_connected = False
        det.pressed = [False] * 4
        self._tick(mode, t + 0.4)
        rec = mode._records[-1]
        self.assertEqual(rec["class"], "device_drop")
        self.assertEqual(mode.phase, "settle")
        # Nothing moved: no staircase entry, no sub-block progress.
        self.assertEqual(len(mode._stair), stair_before)
        self.assertEqual(mode._sub_done, sub_done_before)
        stats = mode.block_stats()
        self.assertEqual(stats["n_device_drops"], 1)
        self.assertEqual(stats["outcome_classes"].get("device_drop"), 1)
        # Excluded from the chord performance aggregates.
        self.assertNotIn("device_drop", stats["chord_outcome_classes"])

    def test_one_board_drop_of_the_trials_hand_counts_too(self) -> None:
        engine, mode, det, t = self._fsr_mode()
        det.pressed = [True] * 4
        _complete_chord(mode, t + 0.3, gap_s=0.01)
        self.assertEqual(mode.phase, "hold")
        engine.source.is_connected = True
        engine._hands_down = {"right"}
        det.pressed = [False] * 4
        self._tick(mode, t + 0.4)
        self.assertEqual(mode._records[-1]["class"], "device_drop")


class SessionCapInSettleTests(unittest.TestCase):
    def test_cap_fires_while_stuck_in_settle(self) -> None:
        # The 30-minute cap was only consulted at trial close, so a
        # hand that never quieted (or a dead device) looped 'Relax
        # your hand' forever past the cap.
        import time as _time
        from unittest.mock import patch
        engine, mode = _build_mode(session_cap_min=0.01)
        mode._fsr = True
        det = MagicMock()
        det.pressed = [True] * 4      # never quiet
        engine.detectors = {"right": det}
        engine.finish_block = MagicMock()
        mode._t0 = 0.0
        with patch.object(_time, "perf_counter", return_value=120.0):
            mode.update(0.016)
        self.assertEqual(mode.phase, "done")
        self.assertEqual(mode.end_reason, "time_cap")

    def test_cap_fires_while_parked_at_a_rest(self) -> None:
        import time as _time
        from unittest.mock import patch
        engine, mode = _build_mode(session_cap_min=0.01)
        engine.finish_block = MagicMock()
        mode._t0 = 0.0
        mode._enter_rest(1.0, 30.0, "between", "Rest your hand")
        with patch.object(_time, "perf_counter", return_value=120.0):
            mode.update(0.016)
        self.assertEqual(mode.phase, "done")
        self.assertEqual(mode.end_reason, "time_cap")


if __name__ == "__main__":
    unittest.main()
