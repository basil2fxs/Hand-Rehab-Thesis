"""Tests for Echo mode, the explicit span game. The guarantees pinned
here are the ones the measurement depends on: the ladder follows the
Kessels standard (two different sequences per length, advance on at
least one correct, terminate when both fail, ceiling), the hidden Hebb
material is name-stable and prefix-stable, presentation never speeds
up, reproduction is untimed and never scored on speed, every trial
reaches the CSV with its played and pressed lane lists, and the safety
rails (fatigue rest, session cap) end a block rather than trap a
patient in it. The end-to-end tests run the real engine on a keyboard
source, because keyboard play is a first-class citizen in this mode.
"""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import time as _time
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def setUpModule() -> None:
    import pygame
    pygame.init()
    pygame.display.set_mode((1280, 800))


def tearDownModule() -> None:
    import pygame
    pygame.quit()


class FakeClock:
    def __init__(self, t: float) -> None:
        self.t = t


class patched_clock:
    """Swap time.perf_counter for a stepped clock, the mirror-mode
    trick, so a whole ladder of one-second items runs in milliseconds
    of real time. Restores on exit."""

    def __enter__(self) -> FakeClock:
        self._orig = _time.perf_counter
        self.clock = FakeClock(self._orig())
        _time.perf_counter = lambda: self.clock.t
        return self.clock

    def __exit__(self, *exc) -> None:
        _time.perf_counter = self._orig


def _press(lane: int, t: float, hand: str = "right"):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=600, baseline=50.0,
                      hand=hand)


def _build_mode(**overrides):
    """An EchoMode on a MagicMock engine, for the ladder and material
    tests where the CSV plumbing is not the question. MagicMock's
    auto-attributes satisfy every engine touch point the mode makes."""
    from finger_rehab.game.modes.echo import EchoMode
    from finger_rehab.game.scoring import ScoreConfig
    engine = MagicMock()
    engine._screens = {}
    engine.hand_mode = "right"
    kwargs = dict(
        engine=engine,
        lanes=[0, 1, 2, 3],
        p_seed=1234,
        block_seed=99,
        start_len=2,
        trials_per_len=2,
        max_len=9,
        runs=1,
        item_on_ms=500.0,
        ioi_ms=1000.0,
        hebb_every=3,
        idle_timeout_s=3.0,
        rest_s=0.5,
        fatigue_timeout_run=2,
        fatigue_rest_s=1.0,
        session_cap_min=30.0,
        cumulative=False,
        score_cfg=ScoreConfig(),
        demo_trials=None,
    )
    kwargs.update(overrides)
    return engine, EchoMode(**kwargs)


def _ladder_mode(**overrides):
    """The legacy Kessels ladder (echo.rule: ladder). Everything in
    LadderTests, HebbTests and ReproductionTests below is that rule's
    contract and must keep passing untouched now the shipped rule is
    Simon."""
    kwargs = dict(rule="ladder")
    kwargs.update(overrides)
    return _build_mode(**kwargs)


def _simon_mode(**overrides):
    """The shipped rule: one sequence per game growing from a single
    item, one spare life, per-participant material."""
    kwargs = dict(rule="simon", start_len=1, max_len=8,
                  participant="Basil", games=1, lives=1)
    kwargs.update(overrides)
    return _build_mode(**kwargs)


def _drive(mode, clock, responder=None, step_s: float = 0.1,
           max_steps: int = 30000) -> None:
    """Step the clock and the mode together until the block ends (or
    the budget runs out, which the caller's assertions then report)."""
    for _ in range(max_steps):
        if mode.phase == "done":
            return
        clock.t += step_s
        mode.update(step_s)
        if responder is not None:
            responder(clock)


def _perfect(mode, clock, fail_at: set[int] | None = None,
             fail_all_from: int | None = None):
    """A responder that replays the sequence exactly, except at the
    lengths named in `fail_at` (first trial only: one wrong press) or
    at every trial from `fail_all_from` up (both trials wrong, the
    termination condition)."""
    answered = {"n": 0}

    def respond(clk) -> None:
        if mode.phase != "respond" or mode.active is None:
            return
        if mode.trial_counter == answered["n"]:
            return
        answered["n"] = mode.trial_counter
        length = len(mode.sequence)
        fail = False
        if fail_all_from is not None and length >= fail_all_from:
            fail = True
        if fail_at and length in fail_at and mode.trial_in_len == 0:
            fail = True
        if fail:
            wrong = next(l for l in mode.lanes
                         if l != mode.sequence[0])
            mode.queue_press(_press(wrong, clk.t))
            return
        for lane in mode.sequence:
            mode.queue_press(_press(lane, clk.t))
    return respond


# ---------------------------------------------------------------------
# material
# ---------------------------------------------------------------------
class MaterialTests(unittest.TestCase):
    """The hidden stream is the cross-session manipulation; the novel
    draws are the measurement material. Both have shape rules the
    analysis depends on."""

    def test_participant_seed_survives_typing_slips(self) -> None:
        from finger_rehab.game.modes.echo import participant_echo_seed
        self.assertEqual(participant_echo_seed("Basil"),
                         participant_echo_seed("  basil "))
        self.assertNotEqual(participant_echo_seed("alice"),
                            participant_echo_seed("bob"))

    def test_echo_seed_is_not_the_buzz_hunt_seed(self) -> None:
        # Same name, different version tags: the two modes' hidden
        # material must be independent or playing one would train
        # the other's secret sequence.
        from finger_rehab.game.modes.buzz_hunt import participant_hebb_seed
        from finger_rehab.game.modes.echo import participant_echo_seed
        self.assertNotEqual(participant_echo_seed("Basil"),
                            participant_hebb_seed("Basil"))

    def test_hidden_stream_is_prefix_stable(self) -> None:
        # The length-L hidden sequence is the first L items of one
        # fixed stream, so repeated material keeps its serial
        # positions as the ladder climbs (what Hebb learning needs).
        from finger_rehab.game.modes.echo import echo_stream
        lanes = [0, 1, 2, 3]
        for length in range(2, 9):
            self.assertEqual(echo_stream(7, lanes, length + 1)[:length],
                             echo_stream(7, lanes, length))

    def test_hidden_stream_depends_on_the_lane_pool(self) -> None:
        from finger_rehab.game.modes.echo import echo_stream
        four = echo_stream(7, [0, 1, 2, 3], 8)
        eight = echo_stream(7, list(range(8)), 8)
        self.assertNotEqual(four, eight)
        self.assertTrue(set(four) <= {0, 1, 2, 3})
        self.assertTrue(set(eight) <= set(range(8)))

    def test_no_material_ever_repeats_back_to_back(self) -> None:
        import random
        from finger_rehab.game.modes.echo import (draw_echo_sequence,
                                                  echo_stream)
        rng = random.Random(5)
        for length in range(2, 10):
            for seq in (echo_stream(11, [0, 1, 2, 3], length),
                        draw_echo_sequence(rng, length, [0, 1, 2, 3])):
                self.assertTrue(
                    all(a != b for a, b in zip(seq, seq[1:])), seq)

    def test_pulse_reconstruction_matches_the_grid(self) -> None:
        from finger_rehab.game.modes.echo import pulses_from_params
        pulses = pulses_from_params(
            "echo_seq", {"seq": "0-2-1", "pulse_ms": 500,
                         "ioi_ms": 1000})
        self.assertEqual(pulses, [(0, 0.0, 500.0), (2, 1.0, 500.0),
                                  (1, 2.0, 500.0)])
        with self.assertRaises(ValueError):
            pulses_from_params("buzz_seq", {})


# ---------------------------------------------------------------------
# the ladder
# ---------------------------------------------------------------------
class LadderTests(unittest.TestCase):
    """Growth and termination are the Kessels standard, and the two
    trials at a length are different sequences. Get any of this wrong
    and the span is a different test's number."""

    def test_two_different_sequences_per_length_advance_on_one(
            self) -> None:
        eng, mode = _ladder_mode()
        with patched_clock() as clock:
            # Fail the FIRST trial at every length: one correct out of
            # two must still advance, all the way to termination when
            # both trials at length 4 fail.
            _drive(mode, clock,
                   _perfect(mode, clock, fail_at={2, 3},
                            fail_all_from=4))
        lens = [r["len"] for r in mode._records]
        self.assertEqual(lens, [2, 2, 3, 3, 4, 4])
        by_len = {}
        for r in mode._records:
            by_len.setdefault(r["len"], []).append(r)
        for length, rows in by_len.items():
            self.assertEqual(len(rows), 2, f"length {length}")
            self.assertNotEqual(rows[0]["played"], rows[1]["played"],
                                f"length {length}: Kessels administers "
                                "two DIFFERENT sequences")
        stats = mode.block_stats()
        self.assertEqual(stats["end_reason"], "completed")
        self.assertEqual(stats["run_end_reasons"], ["both_failed"])
        self.assertEqual(stats["span"], 3)
        self.assertEqual(stats["total_correct"], 2)
        self.assertEqual(stats["product_score"], 6)

    def test_both_failing_at_the_start_length_ends_the_block(
            self) -> None:
        eng, mode = _ladder_mode()
        with patched_clock() as clock:
            _drive(mode, clock,
                   _perfect(mode, clock, fail_all_from=2))
        self.assertEqual([r["len"] for r in mode._records], [2, 2])
        stats = mode.block_stats()
        self.assertEqual(stats["span"], 0)
        self.assertEqual(stats["run_end_reasons"], ["both_failed"])

    def test_ceiling_ends_a_perfect_run(self) -> None:
        eng, mode = _ladder_mode(max_len=4)
        with patched_clock() as clock:
            _drive(mode, clock, _perfect(mode, clock))
        self.assertEqual([r["len"] for r in mode._records],
                         [2, 2, 3, 3, 4, 4])
        stats = mode.block_stats()
        self.assertEqual(stats["run_end_reasons"], ["ceiling"])
        self.assertEqual(stats["span"], 4)

    def test_presentation_is_a_function_of_length_not_success(
            self) -> None:
        # The classic toy accelerates with success; a measure must
        # not (Berch: rate drift is what made 25 years of Corsi data
        # incomparable). The 2026-09 schedule keeps that rule in the
        # form that matters: the rate is pinned per LENGTH, so both
        # trials at a length run at one rate whether the first one
        # failed or not, the start rate is what block_stats reports,
        # and the whole schedule sits next to it.
        eng, mode = _ladder_mode(max_len=5, item_on_ms=400.0, ioi_ms=800.0,
                                ioi_step_ms=50.0, ioi_floor_ms=600.0)
        with patched_clock() as clock:
            _drive(mode, clock, _perfect(mode, clock, fail_at={2, 3, 4}))
        by_len: dict[int, set[float]] = {}
        for r in mode._records:
            by_len.setdefault(r["len"], set()).add(r["ioi_ms"])
        self.assertEqual(by_len, {2: {800.0}, 3: {750.0}, 4: {700.0},
                                  5: {650.0}})
        stats = mode.block_stats()
        self.assertEqual(stats["ioi_ms"], 800.0)
        self.assertEqual(stats["item_on_ms"], 400.0)
        self.assertEqual(stats["ioi_step_ms"], 50.0)
        self.assertEqual(stats["ioi_floor_ms"], 600.0)
        self.assertEqual(stats["ioi_schedule_ms"],
                         {"2": 800.0, "3": 750.0, "4": 700.0, "5": 650.0})

    def test_the_schedule_floors_at_the_motor_and_step_zero_is_fixed_rate(
            self) -> None:
        from finger_rehab.game.modes.echo import EchoMode
        _e, mode = _ladder_mode(max_len=9, item_on_ms=400.0, ioi_ms=800.0,
                               ioi_step_ms=50.0, ioi_floor_ms=600.0)
        self.assertEqual([round(mode.ioi_for(n), 3) for n in range(2, 10)],
                         [0.8, 0.75, 0.7, 0.65, 0.6, 0.6, 0.6, 0.6])
        # A floor under item_on plus the motor's spin-down is raised
        # to it: the next finger must have stopped before the next
        # item starts.
        _e, tight = _ladder_mode(item_on_ms=400.0, ioi_ms=800.0,
                                ioi_step_ms=100.0, ioi_floor_ms=100.0)
        self.assertAlmostEqual(tight.ioi_floor_s,
                               0.4 + EchoMode.MOTOR_CLEAR_S)
        self.assertAlmostEqual(tight.ioi_for(9), 0.55)
        # Step zero is the fixed-rate Corsi protocol again.
        _e, flat = _ladder_mode(item_on_ms=500.0, ioi_ms=1000.0)
        self.assertEqual({flat.ioi_for(n) for n in range(2, 10)}, {1.0})
        # The shipped config is the tightened schedule.
        from finger_rehab.config import Config
        cfg = Config.load()
        self.assertEqual(float(cfg.get("echo.item_on_ms")), 400.0)
        self.assertEqual(float(cfg.get("echo.ioi_ms")), 800.0)
        self.assertEqual(float(cfg.get("echo.ioi_step_ms")), 50.0)
        self.assertEqual(float(cfg.get("echo.ioi_floor_ms")), 600.0)

    def test_hebb_trials_are_the_hidden_prefix_and_count_for_the_ladder(
            self) -> None:
        from finger_rehab.game.modes.echo import echo_stream
        eng, mode = _ladder_mode(max_len=4)
        with patched_clock() as clock:
            _drive(mode, clock, _perfect(mode, clock))
        stats = mode.block_stats()
        self.assertEqual(stats["hebb_trials"], [3, 6])
        for r in mode._records:
            if r["hebb"]:
                self.assertEqual(
                    r["played"],
                    echo_stream(mode.p_seed, mode.lanes, r["len"]),
                    "a hidden trial must replay the participant "
                    "stream's prefix")
        # Six trials logged: the hidden ones filled ladder slots like
        # any other trial (the patient must not be able to tell).
        self.assertEqual(stats["n_trials"], 6)

    def test_extra_runs_restart_the_ladder(self) -> None:
        eng, mode = _ladder_mode(runs=2, max_len=3)
        with patched_clock() as clock:
            _drive(mode, clock, _perfect(mode, clock))
        self.assertEqual([(r["run"], r["len"]) for r in mode._records],
                         [(1, 2), (1, 2), (1, 3), (1, 3),
                          (2, 2), (2, 2), (2, 3), (2, 3)])
        self.assertEqual(mode.block_stats()["run_end_reasons"],
                         ["ceiling", "ceiling"])


# ---------------------------------------------------------------------
# reproduction rules
# ---------------------------------------------------------------------
class ReproductionTests(unittest.TestCase):

    def test_wrong_press_ends_the_attempt_with_partial_credit(
            self) -> None:
        eng, mode = _ladder_mode()
        with patched_clock() as clock:
            done = {"sent": False}

            def respond(clk) -> None:
                if mode.phase != "respond" or done["sent"]:
                    return
                done["sent"] = True
                # First item right, then a wrong lane: the attempt
                # must close there (Corsi convention), scored with
                # what was entered.
                mode.queue_press(_press(mode.sequence[0], clk.t))
                wrong = next(l for l in mode.lanes
                             if l != mode.sequence[1])
                mode.queue_press(_press(wrong, clk.t + 0.1))
            for _ in range(200):
                if mode._records:
                    break
                clock.t += 0.1
                mode.update(0.1)
                respond(clock)
        rec = mode._records[0]
        self.assertEqual(rec["outcome"], "wrong")
        self.assertEqual(rec["n_right"], 1)
        self.assertEqual(len(rec["pressed"]), 2)
        # The logged outcome is untimed and pays per correct item:
        # never a speed number anywhere in it.
        _args, kwargs = eng.log_trial.call_args
        outcome = _args[1]
        self.assertIsNone(outcome.rt_ms)
        self.assertEqual(outcome.points, mode.ITEM_POINTS * 1)

    def test_silence_times_out_as_an_omission(self) -> None:
        eng, mode = _ladder_mode(idle_timeout_s=2.0,
                                fatigue_timeout_run=99)
        with patched_clock() as clock:
            for _ in range(120):
                if mode._records:
                    break
                clock.t += 0.1
                mode.update(0.1)
        self.assertEqual(mode._records[0]["outcome"], "omission")
        self.assertEqual(mode._records[0]["pressed"], [])

    def test_playback_presses_are_logged_never_punished(self) -> None:
        eng, mode = _ladder_mode()
        with patched_clock() as clock:
            poked = {"n": 0}

            def poke(clk) -> None:
                if mode.phase == "play" and poked["n"] < 3:
                    poked["n"] += 1
                    mode.queue_press(_press(0, clk.t))
            for _ in range(80):
                clock.t += 0.1
                mode.update(0.1)
                poke(clock)
                if mode.phase == "respond":
                    break
        self.assertGreater(mode.playback_presses, 0)
        # The trial is still in flight (not aborted) and no penalty
        # path was touched.
        self.assertIsNotNone(mode.active)
        eng.apply_wrong_press_penalty.assert_not_called()

    def test_two_straight_timeouts_force_a_rest_then_end(self) -> None:
        eng, mode = _ladder_mode(idle_timeout_s=1.0)
        with patched_clock() as clock:
            _drive(mode, clock, responder=None, step_s=0.1,
                   max_steps=2000)
        stats = mode.block_stats()
        self.assertEqual(stats["end_reason"], "fatigue")
        self.assertEqual(stats["fatigue_rests"], 2)

    def test_a_fast_reply_at_the_last_offset_counts(self) -> None:
        # Reproduction opens on the grid, the moment the last item's
        # light is due off, so a reply stamped there is a reply even
        # if the frame that would have noticed has not run yet. A
        # press stamped while the last item is still lit stays a
        # playback press.
        eng, mode = _ladder_mode(item_on_ms=400.0, ioi_ms=800.0)
        with patched_clock() as clock:
            for _ in range(400):
                clock.t += 0.05
                mode.update(0.05)
                if (mode.phase == "play"
                        and mode._item_idx >= len(mode.sequence)):
                    break
            self.assertEqual(mode.phase, "play")
            last_off = mode._last_offset_due()
            # Still lit: a playback press, let go.
            early = last_off - 0.05
            mode.queue_press(_press(mode.sequence[0], early))
            clock.t = early
            mode.update(0.0)
            self.assertEqual(mode.phase, "play")
            self.assertEqual(mode.playback_presses, 1)
            self.assertEqual(mode._entered, [])
            # Light due off, frame not yet run: the press is a reply.
            clock.t = last_off + 0.01
            mode.queue_press(_press(mode.sequence[0], clock.t))
            mode.update(0.0)
            self.assertEqual(mode.phase, "respond")
            self.assertEqual([l for l, _t in mode._entered],
                             [mode.sequence[0]])
            self.assertEqual(mode._match, 1)

    def test_no_buzz_answers_a_press_in_reproduction(self) -> None:
        # The MagicMock engine records every pulse_motor call: after
        # the show phase there must be none, whatever a correct press
        # used to earn.
        eng, mode = _ladder_mode()
        eng.source.provides_samples = True
        eng.cue_settings.return_value.buzz_before = True
        with patched_clock() as clock:
            for _ in range(400):
                clock.t += 0.05
                mode.update(0.05)
                if mode.phase == "respond":
                    break
            self.assertEqual(mode.phase, "respond")
            n_show = eng.pulse_motor.call_count
            self.assertEqual(n_show, len(mode.sequence))
            for lane in mode.sequence:
                mode.queue_press(_press(lane, clock.t))
                clock.t += 0.2
                mode.update(0.2)
        self.assertEqual(mode._records[0]["outcome"], "correct")
        self.assertEqual(eng.pulse_motor.call_count, n_show)
        # The trial close declined the engine's after-press cue too.
        _args, kwargs = eng.log_trial.call_args
        self.assertIs(kwargs.get("after_press_cue"), False)


# ---------------------------------------------------------------------
# the Simon rule: the shipped game
# ---------------------------------------------------------------------
def _simon_play(mode, clock, miss_at=None):
    """Replay each trial exactly, except at the lengths in `miss_at`:
    a dict of length -> how many attempts at that length to fail,
    counted per game. A miss presses a later item of the sequence
    first, so it is a transposition at serial position 1, the
    dominant spatial-span error and a deterministic one whatever the
    draw."""
    miss_at = dict(miss_at or {})
    answered = {"n": 0}
    missed: dict[tuple[int, int], int] = {}

    def respond(clk) -> None:
        if mode.phase != "respond" or mode.active is None:
            return
        if mode.trial_counter == answered["n"]:
            return
        answered["n"] = mode.trial_counter
        length = len(mode.sequence)
        key = (mode.run_idx, length)
        if missed.get(key, 0) < miss_at.get(length, 0):
            missed[key] = missed.get(key, 0) + 1
            wrong = next((l for l in mode.sequence[1:]
                          if l != mode.sequence[0]),
                         next(l for l in mode.lanes
                              if l != mode.sequence[0]))
            mode.queue_press(_press(wrong, clk.t))
            return
        for lane in mode.sequence:
            mode.queue_press(_press(lane, clk.t))
    return respond


class SimonMaterialTests(unittest.TestCase):
    """The per-game seed and the per-game stream. Same person, same
    game count, same sequence: that is what makes a game replayable in
    analysis and what stops two games of one session repeating."""

    def test_seed_moves_with_the_game_and_the_name(self) -> None:
        from finger_rehab.game.modes.echo import participant_simon_seed
        self.assertNotEqual(participant_simon_seed("Basil", 0),
                            participant_simon_seed("Basil", 1))
        self.assertNotEqual(participant_simon_seed("alice", 3),
                            participant_simon_seed("bob", 3))
        self.assertEqual(participant_simon_seed("Basil", 2),
                         participant_simon_seed("  basil ", 2))

    def test_seed_is_not_the_ladder_or_buzz_hunt_seed(self) -> None:
        from finger_rehab.game.modes.buzz_hunt import participant_hebb_seed
        from finger_rehab.game.modes.echo import (participant_echo_seed,
                                                  participant_simon_seed)
        for idx in range(4):
            self.assertNotEqual(participant_simon_seed("Basil", idx),
                                participant_echo_seed("Basil"))
            self.assertNotEqual(participant_simon_seed("Basil", idx),
                                participant_hebb_seed("Basil"))

    def test_stream_is_prefix_stable_and_never_doubles(self) -> None:
        from finger_rehab.game.modes.echo import simon_stream
        lanes = [0, 1, 2, 3]
        long = simon_stream(99, lanes, 12)
        for length in range(1, 12):
            self.assertEqual(simon_stream(99, lanes, length),
                             long[:length])
        self.assertTrue(all(a != b for a, b in zip(long, long[1:])), long)

    def test_eight_lanes_are_all_drawn_from(self) -> None:
        from finger_rehab.game.modes.echo import simon_stream
        seq = simon_stream(7, list(range(8)), 60)
        self.assertEqual(set(seq), set(range(8)))


class SimonRuleTests(unittest.TestCase):

    def test_one_sequence_grows_by_one_from_length_one(self) -> None:
        from finger_rehab.game.modes.echo import simon_stream
        eng, mode = _simon_mode(max_len=6)
        seq = simon_stream(mode.game_seed, mode.lanes, 6)
        with patched_clock() as clock:
            _drive(mode, clock, _simon_play(mode, clock))
        self.assertEqual([r["len"] for r in mode._records],
                         [1, 2, 3, 4, 5, 6])
        for r in mode._records:
            self.assertEqual(r["played"], seq[:r["len"]],
                             "every trial replays the SAME sequence, "
                             "one item longer: that IS the Simon rule")
        stats = mode.block_stats()
        self.assertEqual(stats["rule"], "simon")
        self.assertEqual(stats["run_end_reasons"], ["ceiling"])
        self.assertEqual(stats["span"], 6)
        self.assertEqual(stats["total_items"], 21)
        self.assertIsNone(stats["product_score"])
        self.assertEqual(stats["hebb_trials"], [])

    def test_the_life_replays_the_same_length_once(self) -> None:
        eng, mode = _simon_mode(max_len=8)
        with patched_clock() as clock:
            _drive(mode, clock, _simon_play(mode, clock,
                                            miss_at={4: 1, 6: 9}))
        rows = [(r["len"], r["outcome"], r["life"], r["pos"])
                for r in mode._records]
        self.assertEqual(rows, [
            (1, "correct", False, 0), (2, "correct", False, 0),
            (3, "correct", False, 0), (4, "wrong", False, 1),
            (4, "correct", True, 0), (5, "correct", False, 0),
            (6, "wrong", False, 1)])
        # The replay is the same four items, not a redraw.
        self.assertEqual(mode._records[3]["played"],
                         mode._records[4]["played"])
        stats = mode.block_stats()
        self.assertEqual(stats["span"], 5)
        # Partial credit over the whole game: the correct trials pay
        # their length, the two failed attempts slipped on their own
        # first press and pay nothing.
        self.assertEqual(stats["total_items"],
                         1 + 2 + 3 + 0 + 4 + 5 + 0)
        game = stats["games_played"][0]
        self.assertEqual(game["end_reason"], "second_miss")
        self.assertEqual(game["life_used_at"], 4)
        self.assertTrue(game["recovered"])
        self.assertEqual([m["kind"] for m in game["misses"]],
                         ["wrong", "wrong"])
        self.assertEqual(stats["end_reason"], "completed")

    def test_the_row_carries_the_rule_seed_life_and_miss(self) -> None:
        eng, mode = _simon_mode(max_len=4)
        with patched_clock() as clock:
            _drive(mode, clock, _simon_play(mode, clock, miss_at={2: 1}))
        stims = [c.kwargs["stimulus"] for c in eng.log_trial.call_args_list]
        self.assertTrue(all(s.startswith("echo;") for s in stims))
        self.assertTrue(all("rule=simon" in s for s in stims))
        self.assertTrue(all(f"seed={mode.game_seed}" in s for s in stims))
        # The failed length-2 attempt, then its replay.
        self.assertIn("life=0;lives_left=1", stims[1])
        self.assertIn("pos=1", stims[1])
        self.assertIn("miss=transposition", stims[1])
        self.assertIn("life=1;lives_left=0", stims[2])
        self.assertIn("miss=none", stims[2])
        # The pulse train is still rebuildable from the params.
        _args, kwargs = eng.log_trial.call_args
        params = kwargs["continuous"].params
        self.assertEqual(params["rule"], "simon")
        self.assertEqual(params["game_seed"], mode.game_seed)

    def test_a_wrong_lane_the_sequence_never_held_is_an_intrusion(
            self) -> None:
        eng, mode = _simon_mode(max_len=4)
        with patched_clock() as clock:
            done = {"sent": False}
            for _ in range(400):
                if mode._records:
                    break
                clock.t += 0.1
                mode.update(0.1)
                if mode.phase == "respond" and not done["sent"]:
                    done["sent"] = True
                    wrong = next(l for l in mode.lanes
                                 if l not in mode.sequence)
                    mode.queue_press(_press(wrong, clock.t))
        self.assertEqual(mode._records[0]["miss"], "intrusion")

    def test_silence_spends_the_life_then_ends_the_game_as_fatigue(
            self) -> None:
        eng, mode = _simon_mode(idle_timeout_s=1.0, fatigue_rest_s=1.0)
        with patched_clock() as clock:
            _drive(mode, clock, responder=None, step_s=0.1,
                   max_steps=4000)
        stats = mode.block_stats()
        self.assertEqual([r["outcome"] for r in mode._records],
                         ["omission", "omission"])
        self.assertEqual([r["life"] for r in mode._records],
                         [False, True])
        self.assertEqual(stats["end_reason"], "fatigue")
        self.assertEqual(stats["games_played"][0]["end_reason"],
                         "fatigue")
        self.assertEqual(stats["n_omissions"], 2)
        # The forced rest between them is the recovery rest, and it
        # went out on the EEG rest band like every other forced rest.
        sent = [c.args[0] for c in eng._eeg_send.call_args_list]
        from finger_rehab.hardware.eeg_trigger import CODES
        self.assertIn(CODES["rest_start"], sent)
        self.assertIn(CODES["rest_end"], sent)

    def test_no_life_is_the_strict_arcade_rule(self) -> None:
        eng, mode = _simon_mode(lives=0, max_len=8)
        with patched_clock() as clock:
            _drive(mode, clock, _simon_play(mode, clock, miss_at={3: 9}))
        self.assertEqual([r["len"] for r in mode._records], [1, 2, 3])
        self.assertEqual(mode.block_stats()["games_played"][0]
                         ["end_reason"], "second_miss")

    def test_two_games_draw_different_material_and_report_both(
            self) -> None:
        eng, mode = _simon_mode(games=2, max_len=4)
        with patched_clock() as clock:
            _drive(mode, clock, _simon_play(mode, clock, miss_at={4: 9}))
        by_game: dict[int, list] = {}
        for r in mode._records:
            by_game.setdefault(r["run"], []).append(r)
        self.assertEqual(sorted(by_game), [1, 2])
        first = by_game[1][-1]["played"]
        second = by_game[2][-1]["played"]
        self.assertNotEqual(first, second,
                            "each game draws its own sequence")
        stats = mode.block_stats()
        games = stats["games_played"]
        self.assertEqual(len(games), 2)
        self.assertNotEqual(games[0]["game_seed"], games[1]["game_seed"])
        self.assertEqual(games[0]["game_index"], 0)
        self.assertEqual(games[1]["game_index"], 1)
        # Every game gets its own life back.
        self.assertEqual([g["life_used_at"] for g in games], [4, 4])
        self.assertEqual(stats["span"], max(g["span"] for g in games))
        self.assertEqual(stats["span_mean"],
                         round(sum(g["span"] for g in games) / 2, 2))

    def test_the_game_count_carries_the_seed_forward(self) -> None:
        from finger_rehab.game.modes.echo import participant_simon_seed
        eng, mode = _simon_mode(game_index_base=5, max_len=2)
        self.assertEqual(mode.game_seed,
                         participant_simon_seed("Basil", 5))
        self.assertEqual(mode.game_index, 5)

    def test_lengths_one_and_two_share_the_opening_rate(self) -> None:
        _e, mode = _simon_mode(max_len=6, item_on_ms=400.0, ioi_ms=800.0,
                               ioi_step_ms=50.0, ioi_floor_ms=600.0)
        self.assertEqual([round(mode.ioi_for(n), 3)
                          for n in range(1, 7)],
                         [0.8, 0.8, 0.75, 0.7, 0.65, 0.6])
        self.assertEqual(mode.block_stats()["ioi_schedule_ms"]["1"],
                         800.0)
        self.assertEqual(mode.block_stats()["ioi_anchor_len"], 2)

    def test_a_retired_cumulative_config_runs_as_simon(self) -> None:
        with self.assertLogs("finger_rehab.game.modes.echo",
                             level="WARNING") as caught:
            _e, mode = _build_mode(cumulative=True, participant="Basil")
        self.assertEqual(mode.rule, "simon")
        self.assertTrue(any("retired" in m for m in caught.output))


class PriorGameCountTests(unittest.TestCase):
    """The seed carries on across sessions, so the count of a
    participant's earlier Simon games has to be read off the sessions
    tree the same way the vs-last chip reads it."""

    def _write(self, root: Path, name: str, participant: str,
               echo: dict | None, block: str = "echo") -> Path:
        folder = root / name
        folder.mkdir(parents=True)
        meta = {"participant": participant,
                "block_summary": {"block": block, "status": "completed"}}
        if echo is not None:
            meta["block_summary"]["echo"] = echo
        (folder / "metadata.json").write_text(json.dumps(meta),
                                              encoding="utf-8")
        return folder

    def test_counts_games_excludes_this_folder_and_survives_junk(
            self) -> None:
        from finger_rehab.game.modes.echo import count_prior_echo_games
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write(root, "a", "Basil",
                        {"rule": "simon",
                         "games_played": [{"span": 4}, {"span": 5}]})
            self._write(root, "b", "Basil", {"rule": "simon",
                                             "games_played": [{"span": 3}]})
            # Not counted: another participant, a ladder block, a
            # different mode, and the folder this block is writing.
            self._write(root, "c", "Someone",
                        {"rule": "simon", "games_played": [{"span": 9}]})
            self._write(root, "d", "Basil", {"rule": "ladder", "span": 6})
            self._write(root, "e", "Basil", None, block="reaction")
            here = self._write(root, "f", "Basil",
                               {"rule": "simon",
                                "games_played": [{"span": 2}]})
            (root / "broken").mkdir()
            (root / "broken" / "metadata.json").write_text(
                "{ not json", encoding="utf-8")
            self.assertEqual(
                count_prior_echo_games(root, "Basil", exclude_root=here), 3)
            self.assertEqual(count_prior_echo_games(root, "Basil"), 4)
        self.assertEqual(
            count_prior_echo_games(Path(td) / "gone", "Basil"), 0)

    def test_a_simon_block_with_no_games_played_counts_as_one(
            self) -> None:
        from finger_rehab.game.modes.echo import count_prior_echo_games
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write(root, "a", "Basil", {"rule": "simon"})
            self.assertEqual(count_prior_echo_games(root, "Basil"), 1)

    def test_an_abandoned_game_still_used_up_its_sequence(self) -> None:
        # A block quit part way through game 2 records only game 1,
        # but game 2's sequence was shown. Counting it is what stops
        # the next block replaying material the player has seen.
        from finger_rehab.game.modes.echo import count_prior_echo_games
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._write(root, "a", "Basil",
                        {"rule": "simon", "n_trials": 9,
                         "games_played": [{"span": 4, "n_trials": 6}]})
            self.assertEqual(count_prior_echo_games(root, "Basil"), 2)
            self._write(root, "b", "Basil",
                        {"rule": "simon", "n_trials": 6,
                         "games_played": [{"span": 4, "n_trials": 6}]})
            self.assertEqual(count_prior_echo_games(root, "Basil"), 3)


class SimonChipTests(unittest.TestCase):
    """The vs-last-time chip compares Simon spans with Simon spans and
    nothing else: a growing sequence re-presents every prefix, so its
    span sits above the same person's ladder span."""

    def test_only_simon_blocks_compare(self) -> None:
        from finger_rehab.data.history import comparable_value
        self.assertEqual(
            comparable_value("echo", {"echo": {"rule": "simon",
                                               "span": 6}}), 6.0)
        self.assertIsNone(
            comparable_value("echo", {"echo": {"rule": "ladder",
                                               "span": 6}}))
        self.assertIsNone(comparable_value("echo", {"echo": {"span": 6}}))


# ---------------------------------------------------------------------
# end to end through the real engine
# ---------------------------------------------------------------------
def _make_engine(data_dir: str, hand: str = "right"):
    """A real GameEngine on the keyboard source, screens built,
    reports off. Keyboard is deliberate: Echo's stimulus is on screen,
    so keyboard play must be the full game, not a degraded one."""
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data.setdefault("bilateral", {})["hand"] = hand
    cfg.data.setdefault("session", {})["data_dir"] = data_dir
    cfg.data["session"]["participant"] = "EchoProof"
    cfg.data.setdefault("report", {})["enabled"] = False
    cfg.data.setdefault("audio", {})["enabled"] = False
    cfg.data["game"]["test_mode_enabled"] = True
    cfg.data["game"]["test_mode_trials"] = 6
    eng = GameEngine(cfg, KeyboardOnlySource())
    eng._screens = eng._build_screens()
    eng.show_results = lambda: None
    return eng


class EndToEndTests(unittest.TestCase):

    def _run_demo_block(self, eng, clock) -> None:
        answered = {"n": 0}
        mode = eng.mode

        def respond(clk) -> None:
            if mode.phase != "respond" or mode.active is None:
                return
            if mode.trial_counter == answered["n"]:
                return
            answered["n"] = mode.trial_counter
            for lane in mode.sequence:
                hand = ("left" if lane >= 4 else "right") \
                    if eng.hand_mode == "both" else eng.hand_mode
                mode.queue_press(_press(lane, clk.t, hand=hand))
        for _ in range(6000):
            if eng.trial_logger is None:
                return
            clock.t += 0.05
            mode.update(0.05)
            respond(clock)

    def test_demo_block_writes_real_rows_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as td, \
                patched_clock() as clock:
            eng = _make_engine(td)
            eng.begin_echo_block()
            self.assertEqual(eng.current_block, "echo")
            self._run_demo_block(eng, clock)
            self.assertIsNone(eng.trial_logger, "block did not end")
            root = Path(eng.last_session_root)
            meta = json.loads(
                (root / "metadata.json").read_text(encoding="utf-8"))
            echo = meta["block_summary"]["echo"]
            # The Simon demo miniature: one game to a ceiling of three
            # items, with real rows, the pattern / buzz_hunt demo
            # convention.
            self.assertTrue(echo["demo"])
            self.assertEqual(echo["rule"], "simon")
            self.assertEqual(echo["max_len"], 3)
            self.assertEqual(echo["n_trials"], 3)
            self.assertEqual(echo["span"], 3)
            self.assertEqual(echo["total_items"], 6)
            self.assertIsNone(echo["product_score"])
            self.assertEqual(echo["n_lanes"], 4)
            self.assertEqual(len(echo["games_played"]), 1)
            game = echo["games_played"][0]
            # Test Mode never advances the participant's game count.
            self.assertEqual(game["game_index"], -1)
            self.assertEqual(game["end_reason"], "ceiling")
            self.assertIsNone(game["life_used_at"])
            # The Berch parameters, pinned next to the data, the
            # length schedule included.
            for key in ("item_on_ms", "ioi_ms", "ioi_step_ms",
                        "ioi_floor_ms", "ioi_schedule_ms",
                        "motor_clear_ms", "idle_timeout_s",
                        "ioi_anchor_len", "start_len", "max_len",
                        "lives", "games"):
                self.assertIn(key, echo)
            self.assertEqual(echo["ioi_schedule_ms"]["1"], 800.0)
            self.assertEqual(echo["ioi_schedule_ms"]["2"], 800.0)
            self.assertEqual(echo["ioi_schedule_ms"]["3"], 750.0)
            with (root / "trials.csv").open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 3)
            played = []
            for row in rows:
                self.assertTrue(row["stimulus"].startswith("echo;"))
                self.assertIn("played=", row["stimulus"])
                self.assertIn("pressed=", row["stimulus"])
                self.assertIn("pt=", row["stimulus"])
                self.assertIn("rule=simon", row["stimulus"])
                self.assertIn(f"seed={game['game_seed']}",
                              row["stimulus"])
                self.assertIn("life=0", row["stimulus"])
                self.assertIn("pos=0", row["stimulus"])
                self.assertIn("miss=none", row["stimulus"])
                # Reproduction is untimed: no RT may ever appear.
                self.assertEqual(row["time_difference_ms"], "")
                self.assertEqual(row["waveform"], "echo_seq")
                played.append(next(
                    p[len("played="):] for p in row["stimulus"].split(";")
                    if p.startswith("played=")))
            # One sequence, one item longer each trial.
            self.assertEqual([len(p.split("-")) for p in played],
                             [1, 2, 3])
            self.assertTrue(played[2].startswith(played[1]))
            self.assertTrue(played[1].startswith(played[0]))

    def test_a_ladder_demo_still_runs_the_legacy_rule(self) -> None:
        with tempfile.TemporaryDirectory() as td, \
                patched_clock() as clock:
            eng = _make_engine(td)
            eng.cfg.data.setdefault("echo", {})["rule"] = "ladder"
            eng.cfg.data["echo"]["start_len"] = 2
            eng.cfg.data["echo"]["max_len"] = 9
            eng.begin_echo_block()
            self._run_demo_block(eng, clock)
            root = Path(eng.last_session_root)
            meta = json.loads(
                (root / "metadata.json").read_text(encoding="utf-8"))
            echo = meta["block_summary"]["echo"]
            self.assertEqual(echo["rule"], "ladder")
            self.assertEqual(echo["n_trials"], 3)
            self.assertEqual(echo["span"], 3)
            self.assertEqual(echo["total_correct"], 3)
            self.assertEqual(echo["product_score"], 9)
            with (root / "trials.csv").open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            # The third trial is the hidden one under hebb_every 3,
            # and it renders in the CSV like any other.
            self.assertIn("hebb=1", rows[2]["stimulus"])
            self.assertIn("hebb=0", rows[0]["stimulus"])
            self.assertIn("rule=ladder", rows[0]["stimulus"])
            self.assertNotIn("life=", rows[0]["stimulus"])

    def test_bilateral_demo_draws_over_eight_lanes(self) -> None:
        with tempfile.TemporaryDirectory() as td, \
                patched_clock() as clock:
            eng = _make_engine(td, hand="both")
            # Pin the block seed so the material is reproducible and
            # the both-hands assertion cannot flake on a lucky draw.
            eng.cfg.data.setdefault("echo", {})["seed"] = 20260901
            eng.begin_echo_block()
            self.assertEqual(eng.mode.n_lanes, 8)
            self._run_demo_block(eng, clock)
            root = Path(eng.last_session_root)
            meta = json.loads(
                (root / "metadata.json").read_text(encoding="utf-8"))
            echo = meta["block_summary"]["echo"]
            self.assertEqual(echo["n_lanes"], 8)
            with (root / "trials.csv").open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            lanes = set()
            for row in rows:
                for part in row["stimulus"].split(";"):
                    if part.startswith("played="):
                        lanes.update(int(x) for x in
                                     part[len("played="):].split("-"))
            self.assertTrue(lanes <= set(range(8)), lanes)
            # With this seed the demo sequence crosses hands; the
            # notebook's 4-vs-8 split keys off n_lanes either way.
            self.assertTrue(any(l >= 4 for l in lanes), lanes)
            self.assertTrue(any(l < 4 for l in lanes), lanes)

    def test_echo_owns_eeg_mode_id_12(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (MODE_IDS,
                                                       block_code)
        self.assertEqual(MODE_IDS["echo"], 12)
        self.assertEqual(block_code("echo", "start"), 212)
        self.assertEqual(block_code("echo", "end"), 232)


# ---------------------------------------------------------------------
# the wire: a sample-providing rig through the real engine
# ---------------------------------------------------------------------
RESTING = 100
TAP = 400


class _WireRig:
    """A fake board the real engine drives: 200 Hz samples the test
    pushes, every command recorded with the fake clock's time."""

    def __init__(self, clock) -> None:
        from collections import deque
        self.clock = clock
        self.commands: list[tuple[float, str]] = []
        self._q = deque()

    def start(self) -> None: ...
    def stop(self) -> None: ...

    def push(self, t: float, values) -> None:
        from finger_rehab.hardware.source import Sample
        self._q.append(Sample(t_perf=t, values=tuple(values)))

    def get_sample(self, timeout: float = 0.0):
        return self._q.popleft() if self._q else None

    def send_command(self, cmd: str) -> bool:
        self.commands.append((self.clock.t, cmd))
        return True

    @property
    def is_connected(self) -> bool:
        return True

    @property
    def provides_samples(self) -> bool:
        return True

    @property
    def name(self) -> str:
        return "WireRig"


def _make_wire_engine(data_dir: str, clock, buzz_after: bool = True):
    """The real engine on a _WireRig with both buzz switches ON, so
    any buzz the mode or the engine's after-press path could fire
    would show on the wire. Calibration profiles are installed the
    way scripts/measure_battery.py installs them."""
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.calibration_profile import CalibrationProfile
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data.setdefault("session", {})["data_dir"] = data_dir
    cfg.data["session"]["participant"] = "EchoWire"
    cfg.data.setdefault("report", {})["enabled"] = False
    cfg.data.setdefault("audio", {})["enabled"] = False
    cfg.data["eeg"] = {"enabled": False}
    cfg.data.setdefault("quick_cal", {})["enabled"] = False
    cfg.data.setdefault("serial", {})["watch_ports"] = False
    cfg.data["cue"]["buzz_before"] = True
    cfg.data["cue"]["buzz_after"] = buzz_after
    cfg.data["game"]["test_mode_enabled"] = True
    cfg.data["game"]["test_mode_trials"] = 6
    rig = _WireRig(clock)
    eng = GameEngine(cfg, rig)
    eng._screens = eng._build_screens()
    eng.show_results = lambda: None
    eng.begin_session("EchoWire", "30", dominant_hand="right", visit="1")
    prof = CalibrationProfile(hand="right", participant="EchoWire",
                              resting=[RESTING] * 4,
                              press=[RESTING + 60] * 4)
    prof.set_max_press([RESTING + 300] * 4)
    prof.session_token = str(getattr(eng, "_session_token", ""))
    eng.apply_calibration(prof)
    eng._uncal_ack = {"left", "right"}
    return eng, rig


class _Pump:
    """Frames at 60 Hz with a 200 Hz sample stream under them: every
    lane rests unless a tap is in flight on it."""

    def __init__(self, eng, rig, clock) -> None:
        self.eng, self.rig, self.clock = eng, rig, clock
        self.next_sample = clock.t
        self.press_until: dict[int, float] = {}

    def tap(self, lane: int, dur_s: float) -> None:
        self.press_until[lane] = self.clock.t + dur_s

    def frame(self) -> None:
        self.clock.t += 1.0 / 60.0
        while self.next_sample <= self.clock.t:
            t = self.next_sample
            vals = [TAP if self.press_until.get(l, -1.0) > t else RESTING
                    for l in range(4)]
            self.rig.push(t, vals)
            self.next_sample += 1.0 / 200.0
        self.eng._pump_source()
        self.eng.screen_obj.update(1.0 / 60.0)
        self.eng._drain_motor_queue()

    def until(self, pred, max_frames: int = 6000) -> None:
        for _ in range(max_frames):
            if pred():
                return
            self.frame()
        raise AssertionError("condition never met")


class WireTests(unittest.TestCase):
    """What a rig sees in an echo trial, through the real engine,
    the real detectors and the real gameplay screen."""

    def test_stim_leaves_the_rig_only_during_the_show_phase(self) -> None:
        with tempfile.TemporaryDirectory() as td, \
                patched_clock() as clock:
            eng, rig = _make_wire_engine(td, clock, buzz_after=True)
            pump = _Pump(eng, rig, clock)
            pump.until(lambda: eng.detectors.get("right") is not None
                       and eng.detectors["right"].baseline[0] is not None,
                       300)
            eng.begin_echo_block()
            mode = eng.mode
            rig.commands.clear()
            pump.until(lambda: mode.phase == "play")
            play_t0 = mode._play_t0
            pump.until(lambda: mode.phase == "respond")
            respond_t0 = mode._respond_t0
            show_stims = [t for t, c in rig.commands if c.startswith("STIM")]
            self.assertGreaterEqual(len(show_stims), len(mode.sequence))
            self.assertTrue(all(play_t0 - 1e-9 <= t < respond_t0
                                for t in show_stims), show_stims)
            marker = len(rig.commands)
            # Reproduce the whole sequence with real taps on the pads.
            for lane in mode.sequence:
                pump.tap(lane, 0.10)
                pump.until(lambda l=lane: any(e == l for e, _t
                                              in mode._entered), 120)
                for _ in range(20):
                    pump.frame()
            pump.until(lambda: len(mode._records) >= 1, 600)
            self.assertEqual(mode._records[0]["outcome"], "correct")
            for _ in range(30):
                pump.frame()
            after = [c for _t, c in rig.commands[marker:]
                     if c.startswith("STIM") or c.startswith("RIGHT:STIM")]
            self.assertEqual(after, [],
                             "no STIM may leave the rig once the show "
                             "phase is over, buzz_after on included")

    def test_a_fifteen_millisecond_tap_counts_as_a_reply(self) -> None:
        # No minimum hold anywhere: three samples above threshold at
        # 200 Hz is a press to the detector and a reply to the mode.
        with tempfile.TemporaryDirectory() as td, \
                patched_clock() as clock:
            eng, rig = _make_wire_engine(td, clock, buzz_after=False)
            pump = _Pump(eng, rig, clock)
            pump.until(lambda: eng.detectors.get("right") is not None
                       and eng.detectors["right"].baseline[0] is not None,
                       300)
            eng.begin_echo_block()
            mode = eng.mode
            # Trial 1 of a Simon game is a single item, so its tap
            # both registers and completes the trial.
            pump.until(lambda: mode.phase == "respond")
            lane = mode.sequence[0]
            pump.tap(lane, 0.015)
            pump.until(lambda: len(mode._records) >= 1, 120)
            self.assertEqual(mode._records[0]["pressed"], [lane])
            self.assertEqual(mode._records[0]["outcome"], "correct")
            # Trial 2 is two items, so the same short tap leaves the
            # trial in flight rather than closing it.
            pump.until(lambda: mode.phase == "respond"
                       and len(mode.sequence) == 2, 600)
            lane = mode.sequence[0]
            pump.tap(lane, 0.015)
            for _ in range(6):
                pump.frame()
            self.assertEqual([l for l, _t in mode._entered], [lane])
            self.assertEqual(mode._match, 1)
            self.assertIsNotNone(mode.active)


if __name__ == "__main__":
    unittest.main()
