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
        eng, mode = _build_mode()
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
        eng, mode = _build_mode()
        with patched_clock() as clock:
            _drive(mode, clock,
                   _perfect(mode, clock, fail_all_from=2))
        self.assertEqual([r["len"] for r in mode._records], [2, 2])
        stats = mode.block_stats()
        self.assertEqual(stats["span"], 0)
        self.assertEqual(stats["run_end_reasons"], ["both_failed"])

    def test_ceiling_ends_a_perfect_run(self) -> None:
        eng, mode = _build_mode(max_len=4)
        with patched_clock() as clock:
            _drive(mode, clock, _perfect(mode, clock))
        self.assertEqual([r["len"] for r in mode._records],
                         [2, 2, 3, 3, 4, 4])
        stats = mode.block_stats()
        self.assertEqual(stats["run_end_reasons"], ["ceiling"])
        self.assertEqual(stats["span"], 4)

    def test_presentation_never_speeds_up(self) -> None:
        # The classic toy accelerates with success; a measure must
        # not (Berch: rate drift is what made 25 years of Corsi data
        # incomparable). The pinned rate is also what block_stats
        # reports, so the analysis can hold every block to it.
        eng, mode = _build_mode(max_len=4)
        ioi_before = mode.ioi_s
        with patched_clock() as clock:
            _drive(mode, clock, _perfect(mode, clock))
        self.assertEqual(mode.ioi_s, ioi_before)
        stats = mode.block_stats()
        self.assertEqual(stats["ioi_ms"], 1000.0)
        self.assertEqual(stats["item_on_ms"], 500.0)

    def test_hebb_trials_are_the_hidden_prefix_and_count_for_the_ladder(
            self) -> None:
        from finger_rehab.game.modes.echo import echo_stream
        eng, mode = _build_mode(max_len=4)
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
        eng, mode = _build_mode(runs=2, max_len=3)
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
        eng, mode = _build_mode()
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
        eng, mode = _build_mode(idle_timeout_s=2.0,
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
        eng, mode = _build_mode()
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
        eng, mode = _build_mode(idle_timeout_s=1.0)
        with patched_clock() as clock:
            _drive(mode, clock, responder=None, step_s=0.1,
                   max_steps=2000)
        stats = mode.block_stats()
        self.assertEqual(stats["end_reason"], "fatigue")
        self.assertEqual(stats["fatigue_rests"], 2)


# ---------------------------------------------------------------------
# cumulative (classic Simon) mode
# ---------------------------------------------------------------------
class CumulativeTests(unittest.TestCase):

    def test_grows_by_appending_and_dies_on_first_miss(self) -> None:
        eng, mode = _build_mode(cumulative=True)
        with patched_clock() as clock:
            _drive(mode, clock,
                   _perfect(mode, clock, fail_all_from=5))
        played = [r["played"] for r in mode._records]
        self.assertEqual([len(p) for p in played], [2, 3, 4, 5])
        for shorter, longer in zip(played, played[1:]):
            self.assertEqual(longer[:len(shorter)], shorter,
                             "cumulative material must extend the "
                             "same sequence, that IS the toy's rule")
        stats = mode.block_stats()
        self.assertTrue(stats["cumulative"])
        self.assertEqual(stats["run_end_reasons"], ["cumulative_miss"])
        # No hidden trials: there are no fresh draws to hide a repeat
        # among when everything repeats by design.
        self.assertEqual(stats["hebb_trials"], [])


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
            # The demo miniature is the fixed 2, 3, 3 ladder with
            # real rows, the pattern / buzz_hunt demo convention.
            self.assertTrue(echo["demo"])
            self.assertEqual(echo["n_trials"], 3)
            self.assertEqual(echo["span"], 3)
            self.assertEqual(echo["total_correct"], 3)
            self.assertEqual(echo["product_score"], 9)
            self.assertEqual(echo["n_lanes"], 4)
            # The Berch parameters, pinned next to the data.
            for key in ("item_on_ms", "ioi_ms", "idle_timeout_s",
                        "hebb_every", "start_len", "max_len"):
                self.assertIn(key, echo)
            with (root / "trials.csv").open(encoding="utf-8") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 3)
            for row in rows:
                self.assertTrue(row["stimulus"].startswith("echo;"))
                self.assertIn("played=", row["stimulus"])
                self.assertIn("pressed=", row["stimulus"])
                self.assertIn("pt=", row["stimulus"])
                # Reproduction is untimed: no RT may ever appear.
                self.assertEqual(row["time_difference_ms"], "")
                self.assertEqual(row["waveform"], "echo_seq")
            # The third trial is the hidden one under hebb_every 3,
            # and it renders in the CSV like any other.
            self.assertIn("hebb=1", rows[2]["stimulus"])
            self.assertIn("hebb=0", rows[0]["stimulus"])

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
            # With this seed the 8 demo items span both hands; the
            # notebook's 4-vs-8 split keys off n_lanes either way.
            self.assertTrue(any(l >= 4 for l in lanes), lanes)
            self.assertTrue(any(l < 4 for l in lanes), lanes)

    def test_echo_owns_eeg_mode_id_12(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (MODE_IDS,
                                                       block_code)
        self.assertEqual(MODE_IDS["echo"], 12)
        self.assertEqual(block_code("echo", "start"), 212)
        self.assertEqual(block_code("echo", "end"), 232)


if __name__ == "__main__":
    unittest.main()
