"""Tests for reaction mode, the baseline block every cross-session
comparison rests on. The guarantees pinned here are the ones the
research design depends on: the wait cannot be timed (seeded exponential
foreperiod), anticipations and false starts never score as hits, catch
trials punish guessing, wrong fingers follow the Classic conventions,
and the reaction time reaches the trial CSV through the same
time_difference_ms column Classic used, so every downstream analysis
keeps working.
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
    """A ReactionMode wired to a MagicMock engine, with timings shrunk
    so tests drive the state machine with explicit `now` values instead
    of sleeping."""
    from finger_rehab.game.modes.reaction import ReactionMode
    from finger_rehab.game.scoring import ScoreConfig
    engine = MagicMock()
    engine.detectors = {}
    engine._screens = {}
    engine.hand_mode = "right"
    engine.score = 0
    engine._reaction_best_ms = {}
    engine._reaction_level = 1
    engine._reaction_clean_blocks = 0
    kwargs = dict(
        engine=engine,
        lanes_by_hand={"right": [0, 1, 2, 3]},
        sub_mode="choice",
        srt_finger=0,
        scorable_trials=3,
        attempt_cap=10,
        fp_min_s=1.5, fp_mean_extra_s=2.5, fp_max_s=9.0,
        fp_mode="exponential",
        catch_rate=0.0, catch_wait_s=8.0,
        anticipation_cut_ms=100.0, lapse_ms=500.0,
        response_window_s=2.0,
        level=1, max_level=3,
        level_up_lapse_rate=0.10, level_down_lapse_rate=0.30,
        rest_gate_s=0.3, feedback_s=1.2,
        false_start_feedback_s=1.5, inter_trial_gap_s=0.5,
        score_cfg=ScoreConfig(),
        seed=42,
    )
    kwargs.update(overrides)
    return engine, ReactionMode(**kwargs)


class ForeperiodTests(unittest.TestCase):
    """The randomised wait is the mode's reason to exist. If it ever
    leaves its bounds or stops being reproducible from the seed, the
    anticipation control and the reproducibility claim both die."""

    def test_draws_stay_within_bounds(self) -> None:
        _, mode = _build_mode()
        for _ in range(500):
            fp = mode._draw_foreperiod()
            self.assertGreaterEqual(fp, mode.fp_min)
            self.assertLessEqual(fp, mode.fp_max)

    def test_same_seed_reproduces_the_wait_sequence(self) -> None:
        _, a = _build_mode(seed=1234)
        _, b = _build_mode(seed=1234)
        draws_a = [a._draw_foreperiod() for _ in range(30)]
        draws_b = [b._draw_foreperiod() for _ in range(30)]
        self.assertEqual(draws_a, draws_b)

    def test_uniform_mode_uses_the_pvt_range(self) -> None:
        # The uniform option exists for blocks meant to sit next to
        # published PVT numbers, which use 2-10 s inter-stimulus gaps.
        _, mode = _build_mode(fp_mode="uniform")
        for _ in range(200):
            fp = mode._draw_foreperiod()
            self.assertGreaterEqual(fp, 2.0)
            self.assertLessEqual(fp, 10.0)


class FalseStartTests(unittest.TestCase):
    """A press before the stimulus must never become a hit, never cost
    a scorable slot, and must reach the CSV distinguishably. Stroke can
    impair response inhibition, so these are expected events, not rare
    corner cases."""

    def test_press_during_foreperiod_is_a_false_start(self) -> None:
        engine, mode = _build_mode()
        mode._begin_trial(now=10.0)
        self.assertEqual(mode._phase, "foreperiod")
        mode._handle_press(_press(lane=1, t=10.5), now=10.5)
        engine.log_reaction_event.assert_called_once()
        kwargs = engine.log_reaction_event.call_args.kwargs
        self.assertEqual(kwargs["error_type"], "false_start")
        self.assertEqual(kwargs["label"], "Early")
        # No stimulus fired, so nothing must go through the scorable
        # path and the scorable count must not move.
        engine.log_trial.assert_not_called()
        self.assertEqual(mode.completed, 0)
        # The attempt still counts toward the cap so a rough block ends.
        self.assertEqual(mode.trial_counter, 1)

    def test_false_start_hand_follows_the_pressing_lane(self) -> None:
        # A foreperiod false start fires before any board is cued, so
        # there is no cued lane to derive a side from, but the
        # PRESSING lane did happen. In a both-hands block the row must
        # carry the real board the press landed on, not the block's
        # generic hand_mode="both", or a bilateral response-inhibition
        # split cannot use the hand column.
        engine, mode = _build_mode(
            lanes_by_hand={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]})
        engine.hand_mode = "both"
        engine._lane_hand = lambda lane: "left" if lane >= 4 else "right"
        mode._begin_trial(now=10.0)
        mode._handle_press(_press(lane=5, t=10.5), now=10.5)
        kwargs = engine.log_reaction_event.call_args.kwargs
        self.assertEqual(kwargs["hand"], "left")

    def test_catch_false_start_hand_follows_the_pressing_lane(self) -> None:
        engine, mode = _build_mode(
            lanes_by_hand={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]},
            catch_rate=1.0)
        engine.hand_mode = "both"
        engine._lane_hand = lambda lane: "left" if lane >= 4 else "right"
        mode._begin_trial(now=10.0)
        self.assertEqual(mode._phase, "catch")
        mode._handle_press(_press(lane=6, t=10.5), now=10.5)
        kwargs = engine.log_reaction_event.call_args.kwargs
        self.assertEqual(kwargs["error_type"], "catch_false_start")
        self.assertEqual(kwargs["hand"], "left")

    def test_sub_cut_press_after_stimulus_is_an_anticipation(self) -> None:
        # Under 100 ms the press cannot be a response to the stimulus
        # (Basner and Dinges 2011), whichever finger fired.
        engine, mode = _build_mode()
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        target = mode.active.lane
        mode._handle_press(_press(lane=target, t=12.05), now=12.05)
        kwargs = engine.log_reaction_event.call_args.kwargs
        self.assertEqual(kwargs["error_type"], "anticipation")
        self.assertAlmostEqual(kwargs["rt_ms"], 50.0, places=3)
        engine.log_trial.assert_not_called()
        self.assertEqual(mode.completed, 0)


class ScorableTrialTests(unittest.TestCase):
    """Valid presses and timeouts go through engine.log_trial exactly
    like Classic, which is what keeps time_difference_ms meaning the
    same thing across every session in the dataset."""

    def test_valid_press_logs_rt_through_log_trial(self) -> None:
        engine, mode = _build_mode()
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        target = mode.active.lane
        mode._handle_press(_press(lane=target, t=12.3), now=12.3)
        engine.log_trial.assert_called_once()
        outcome = engine.log_trial.call_args[0][1]
        self.assertAlmostEqual(outcome.rt_ms, 300.0, places=3)
        self.assertEqual(outcome.label, "Good")
        self.assertEqual(mode.completed, 1)
        self.assertEqual(mode.n_valid, 1)

    def test_timeout_logs_a_miss(self) -> None:
        engine, mode = _build_mode()
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        mode._close_scorable(None, now=14.5)
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")
        self.assertIsNone(outcome.rt_ms)
        self.assertEqual(mode.n_miss, 1)
        self.assertEqual(mode.completed, 1)

    def test_slow_press_counts_as_lapse(self) -> None:
        # 500 ms and over is the PVT lapse convention. It must still be
        # a scorable RT (the patient did press), only tallied so level
        # progression can react.
        engine, mode = _build_mode()
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        target = mode.active.lane
        mode._handle_press(_press(lane=target, t=12.7), now=12.7)
        self.assertEqual(mode.n_valid, 1)
        self.assertEqual(mode.n_lapse, 1)

    def test_press_past_the_response_window_is_a_timeout_not_a_late_hit(
            self) -> None:
        # update() pops the whole press queue before it checks the
        # phase=='stim' timeout branch, so a press landing after the
        # window but before the next tick used to reach
        # _press_on_stim and log a scorable "Late" row whose own
        # rt_ms exceeded the response_window it was meant to be
        # censored against. It must close the same way a real timeout
        # does: a Miss with no RT.
        engine, mode = _build_mode(response_window_s=2.0)
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        target = mode.active.lane
        mode._handle_press(_press(lane=target, t=12.0 + 2.15), now=12.0 + 2.15)
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")
        self.assertIsNone(outcome.rt_ms)
        self.assertEqual(mode.n_miss, 1)
        self.assertEqual(mode.n_valid, 0)
        # But the row must not be byte-identical to never pressing:
        # a response at window+150 ms is an extreme lapse, not an
        # absence of response. The press stays on the row with its
        # own error_type and its latency recoverable from
        # first_incorrect_ms.
        trial = engine.log_trial.call_args[0][0]
        self.assertEqual(trial.keys_pressed, [target])
        self.assertEqual(len(trial.incorrect_presses), 1)
        self.assertEqual(
            engine.log_trial.call_args.kwargs.get("error_type"),
            "late_press")

    def test_true_timeout_carries_no_late_press_marker(self) -> None:
        engine, mode = _build_mode(response_window_s=2.0)
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        mode.update_to = None
        mode._close_scorable(None, now=14.5)
        trial = engine.log_trial.call_args[0][0]
        self.assertEqual(trial.keys_pressed, [])
        self.assertIsNone(
            engine.log_trial.call_args.kwargs.get("error_type"))

    def test_choice_wrong_finger_follows_classic_miss_convention(self) -> None:
        # In choice mode a wrong finger consumes the trial (accuracy is
        # a headline metric) and must land as the same Miss-with-
        # incorrect-press row Classic writes, so downstream parsing
        # stays uniform.
        engine, mode = _build_mode()
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        wrong = (mode.active.lane + 1) % 4
        mode._handle_press(_press(lane=wrong, t=12.3), now=12.3)
        engine.log_trial.assert_called_once()
        trial = engine.log_trial.call_args[0][0]
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")
        self.assertIsNone(outcome.rt_ms)
        self.assertEqual(len(trial.incorrect_presses), 1)
        self.assertEqual(trial.incorrect_presses[0][0], wrong)
        self.assertEqual(mode.n_wrong_choice, 1)
        self.assertEqual(mode.completed, 1)


class SimpleSubModeTests(unittest.TestCase):
    """Simple RT measures one designated finger. A different finger
    must be logged as wrong_finger and retried, never scored as an RT,
    or the designated finger's average absorbs presses it never made."""

    def test_only_designated_finger_is_cued(self) -> None:
        _, mode = _build_mode(sub_mode="simple", srt_finger=2)
        for _ in range(10):
            self.assertEqual(mode._next_lane(), 2)

    def test_wrong_finger_is_logged_and_retried(self) -> None:
        engine, mode = _build_mode(sub_mode="simple", srt_finger=0)
        mode._begin_trial(now=10.0)
        mode._fire(now=12.0)
        mode._handle_press(_press(lane=3, t=12.3), now=12.3)
        kwargs = engine.log_reaction_event.call_args.kwargs
        self.assertEqual(kwargs["error_type"], "wrong_finger")
        self.assertEqual(kwargs["pressed_lane"], 3)
        self.assertAlmostEqual(kwargs["press_offset_ms"], 300.0, places=3)
        engine.log_trial.assert_not_called()
        self.assertEqual(mode.completed, 0)
        self.assertEqual(mode.n_wrong_finger, 1)


class CatchTrialTests(unittest.TestCase):
    """Catch trials are the second anticipation control: sometimes no
    stimulus comes, so guessing loses. Surviving one must be rewarded
    without touching the hit counters; pressing during one is a false
    start."""

    def test_surviving_a_catch_rewards_waiting(self) -> None:
        engine, mode = _build_mode(catch_rate=1.0)
        mode._begin_trial(now=10.0)
        self.assertEqual(mode._phase, "catch")
        mode._catch_survived(now=18.0)
        kwargs = engine.log_reaction_event.call_args.kwargs
        self.assertEqual(kwargs["label"], "CatchOk")
        self.assertEqual(engine.score, mode.CATCH_REWARD)
        self.assertEqual(mode.n_catch_ok, 1)
        self.assertEqual(mode.completed, 0)

    def test_press_during_catch_is_a_false_start(self) -> None:
        engine, mode = _build_mode(catch_rate=1.0)
        mode._begin_trial(now=10.0)
        mode._handle_press(_press(lane=0, t=11.0), now=11.0)
        kwargs = engine.log_reaction_event.call_args.kwargs
        self.assertEqual(kwargs["error_type"], "catch_false_start")
        self.assertEqual(mode.n_catch_false_start, 1)
        self.assertEqual(engine.score, 0)


class SchedulingTests(unittest.TestCase):
    """Choice mode must cue every finger equally often, or a per-finger
    RT comparison reports how often each finger was asked rather than
    anything about the hand."""

    def test_choice_lanes_are_balanced(self) -> None:
        _, mode = _build_mode()
        counts = {0: 0, 1: 0, 2: 0, 3: 0}
        for _ in range(40):
            counts[mode._next_lane()] += 1
        self.assertEqual(set(counts.values()), {10})

    def test_response_window_drives_the_timing_bar(self) -> None:
        # on_stim_multi reads current_timeout_s to size the timing bar
        # and to log timeout_ms; it must be the level's window.
        _, mode = _build_mode(response_window_s=1.5)
        self.assertEqual(mode.current_timeout_s, 1.5)


class BlockLifecycleTests(unittest.TestCase):
    """The block must end on its own in every case: target reached, or
    attempt cap hit after a rough run. A block that cannot end traps a
    patient mid-session."""

    def test_finishes_when_scorable_target_reached(self) -> None:
        engine, mode = _build_mode()
        mode.completed = mode.total_trials
        mode._phase = "arm"
        mode.update(0.0)
        engine.finish_block.assert_called_once()
        # A second tick must not double-finish.
        mode.update(0.0)
        engine.finish_block.assert_called_once()

    def test_finishes_at_attempt_cap_even_short_of_target(self) -> None:
        engine, mode = _build_mode()
        mode.trial_counter = mode.attempt_cap
        mode._phase = "arm"
        mode.update(0.0)
        engine.finish_block.assert_called_once()

    def test_pause_shifts_inflight_deadlines(self) -> None:
        # Without the shift, resuming after a pause would fire the
        # stimulus instantly (foreperiod) or time out the active trial.
        _, mode = _build_mode()
        mode._begin_trial(now=10.0)
        due_before = mode._stim_due
        mode.on_resume(5.0)
        self.assertAlmostEqual(mode._stim_due, due_before + 5.0)
        mode._fire(now=20.0)
        mode.on_resume(3.0)
        self.assertAlmostEqual(mode.active.stim_t_perf, 23.0)


class LevelProgressionTests(unittest.TestCase):
    """Difficulty only moves through the response window, and only on
    lapse-or-miss evidence. Raising the press force would change what
    the mode measures, so it must never be the lever."""

    def test_two_clean_blocks_step_up_one_bad_block_steps_down(self) -> None:
        engine, mode = _build_mode()
        mode.completed = 25
        mode.n_lapse = 0
        mode.n_miss = 0
        mode._update_level_progression()
        self.assertEqual(engine._reaction_level, 1)
        self.assertEqual(engine._reaction_clean_blocks, 1)
        mode._update_level_progression()
        self.assertEqual(engine._reaction_level, 2)
        self.assertEqual(engine._reaction_clean_blocks, 0)
        # One block over the 30% lapse-like rate drops straight back.
        mode.n_lapse = 10
        mode._update_level_progression()
        self.assertEqual(engine._reaction_level, 1)

    def test_middling_block_resets_the_clean_run(self) -> None:
        engine, mode = _build_mode()
        engine._reaction_clean_blocks = 1
        mode.completed = 25
        mode.n_lapse = 5          # 20%: neither clean nor bad
        mode.n_miss = 0
        mode._update_level_progression()
        self.assertEqual(engine._reaction_level, 1)
        self.assertEqual(engine._reaction_clean_blocks, 0)

    def test_all_wrong_finger_choice_block_does_not_level_up(self) -> None:
        """Every press fast but on the wrong finger: n_lapse and n_miss
        are both zero, so a rate that ignores n_wrong_choice would read
        this as a clean block. It must not advance the level."""
        engine, mode = _build_mode()
        mode.completed = 25
        mode.n_valid = 0
        mode.n_lapse = 0
        mode.n_miss = 0
        mode.n_wrong_choice = 25
        mode._update_level_progression()
        mode._update_level_progression()
        self.assertEqual(engine._reaction_level, 1)
        self.assertEqual(engine._reaction_clean_blocks, 0)

    def test_zero_completed_block_is_neutral_for_progression(self) -> None:
        """A block that ended at the attempt cap on nothing but false
        starts has no scorable evidence. It must neither count as a
        clean block (two of those would tighten the window on exactly
        the impulse-impaired patient it protects) nor wipe an earned
        clean streak."""
        engine, mode = _build_mode()
        engine._reaction_clean_blocks = 1
        mode.completed = 0
        mode._update_level_progression()
        mode._update_level_progression()
        self.assertEqual(engine._reaction_level, 1)
        self.assertEqual(engine._reaction_clean_blocks, 1)

    def test_low_evidence_clean_block_does_not_advance(self) -> None:
        """Three clean presses among a wall of wrong-finger retries in
        simple sub-mode: the rate looks clean but under half the
        planned trials completed, so the block is neutral."""
        engine, mode = _build_mode(scorable_trials=25)
        mode.completed = 3
        mode.n_lapse = 0
        mode.n_miss = 0
        mode._update_level_progression()
        mode._update_level_progression()
        self.assertEqual(engine._reaction_level, 1)
        self.assertEqual(engine._reaction_clean_blocks, 0)


class BlockStatsTests(unittest.TestCase):
    """The block summary is what a researcher reads without opening
    trials.csv, so the median (not the mean) must headline it and the
    anticipation diagnostic must be present."""

    def test_stats_report_median_and_counts(self) -> None:
        _, mode = _build_mode()
        for i, rt in enumerate([200.0, 300.0, 400.0]):
            mode._valid_rts.append(rt)
            mode._valid_fps.append(2.0 + i)
            mode._valid_idx.append(i + 1)
        mode.n_valid = 3
        mode.completed = 3
        stats = mode.block_stats()
        self.assertEqual(stats["median_rt_ms"], 300.0)
        self.assertEqual(stats["n_valid"], 3)
        self.assertEqual(stats["seed"], 42)
        self.assertIn("spearman_rho_rt_vs_fp", stats)

    def test_ex_small_samples_return_none_not_noise(self) -> None:
        # Two RTs cannot support a slope or a rank correlation; the
        # stats must say None rather than print noise.
        _, mode = _build_mode()
        mode._valid_rts = [200.0, 250.0]
        mode._valid_fps = [2.0, 3.0]
        mode._valid_idx = [1, 2]
        stats = mode.block_stats()
        self.assertIsNone(stats["slope_rt_ms_per_trial"])
        self.assertIsNone(stats["spearman_rho_rt_vs_fp"])

    def test_lapse_like_rate_is_none_with_nothing_completed(self) -> None:
        # 0.0 would read downstream as a perfectly clean block from a
        # block that never produced a scorable trial.
        _, mode = _build_mode()
        mode.completed = 0
        stats = mode.block_stats()
        self.assertIsNone(stats["lapse_like_rate"])


class EngineIntegrationTests(unittest.TestCase):
    """begin_reaction_block through to the CSV and metadata on disk.
    This is the path a real session takes, so it is where a broken
    column name or a summary that never lands would show up."""

    def test_block_writes_distinguishable_rows_and_summary(self) -> None:
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
                cfg.data["reaction"] = {"seed": 1234, "catch_rate": 0.0}
                eng = GameEngine(cfg, KeyboardOnlySource())
                gp = MagicMock()
                gp.lanes = []
                # finish_block ends on show_results, so the stub set
                # needs a results screen too.
                eng._screens = {"gameplay": gp, "results": MagicMock()}
                eng.begin_reaction_block()
                self.assertEqual(eng.current_block, "reaction")
                mode = eng.mode
                self.assertEqual(mode.seed, 1234)
                # One false start, then one clean 300 ms press.
                mode._begin_trial(now=100.0)
                mode._handle_press(_press(lane=0, t=100.5), now=100.5)
                mode._begin_trial(now=105.0)
                mode._fire(now=107.0)
                target = mode.active.lane
                mode._handle_press(_press(lane=target, t=107.3), now=107.3)
                root = Path(eng.session_paths.root)
                eng.finish_block()
                with (root / "trials.csv").open() as f:
                    rows = list(csv.DictReader(f))
                self.assertEqual(len(rows), 2)
                fs, hit = rows[0], rows[1]
                self.assertEqual(fs["error_type"], "false_start")
                self.assertEqual(fs["early_late"], "Early")
                self.assertEqual(fs["time_difference_ms"], "")
                self.assertEqual(hit["early_late"], "Good")
                self.assertAlmostEqual(
                    float(hit["time_difference_ms"]), 300.0, delta=1.0)
                # The stimulus column carries sub-mode + foreperiod so
                # the anticipation diagnostic can run from the CSV.
                self.assertTrue(hit["stimulus"].startswith("choice;fp="))
                meta = json.loads(
                    (root / "metadata.json").read_text())
                stats = meta["block_summary"]["reaction"]
                self.assertEqual(stats["seed"], 1234)
                self.assertEqual(stats["n_valid"], 1)
                self.assertEqual(stats["n_false_start_foreperiod"], 1)
        finally:
            pygame.quit()


class BilateralPerTrialHandTests(unittest.TestCase):
    """A both-hands reaction block cues one board per trial, right OR
    left, from lanes_by_hand's 0..3 / 4..7 split. The trials.csv hand
    column must say which board that trial actually cued, not just
    the block-level "both", or the notebook's reaction chapter cannot
    split RT median/p10/histogram/trend by hand for a bilateral block."""

    def _run_bilateral_block(self):
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            td = tempfile.mkdtemp()
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [640, 480]
            cfg.data["audio"]["enabled"] = False
            cfg.data["session"]["data_dir"] = td
            cfg.data["report"] = {"enabled": False}
            cfg.data["bilateral"] = {"hand": "both"}
            cfg.data["reaction"] = {"seed": 7, "catch_rate": 0.0}
            eng = GameEngine(cfg, KeyboardOnlySource())
            gp = MagicMock()
            gp.lanes = []
            eng._screens = {"gameplay": gp, "results": MagicMock()}
            eng.begin_reaction_block()
            self.assertEqual(eng.hand_mode, "both")
            mode = eng.mode
            # PairedBalancedScheduler alternates hands, so eight clean
            # hits are guaranteed to cover both the right board (lanes
            # 0-3) and the left board (lanes 4-7) at least once each.
            t = 100.0
            for i in range(8):
                mode._begin_trial(now=t)
                mode._fire(now=t + 2.0)
                target = mode.active.lane
                mode._handle_press(_press(lane=target, t=t + 2.2),
                                   now=t + 2.2)
                t += 3.0
            root = Path(eng.session_paths.root)
            eng.finish_block()
            with (root / "trials.csv").open() as f:
                rows = list(csv.DictReader(f))
            return rows
        finally:
            pygame.quit()

    def test_hand_column_is_per_trial_not_block_level(self) -> None:
        rows = self._run_bilateral_block()
        self.assertEqual(len(rows), 8)
        # This is the finding this test reproduces: every row used to
        # come back "both" no matter which board the lane belonged
        # to, which is what the fix below asserts against.
        seen = set()
        for r in rows:
            lane0 = int(r["lane"]) - 1
            expected = "left" if lane0 >= 4 else "right"
            self.assertEqual(
                r["hand"], expected,
                f"lane {lane0 + 1} row logged hand={r['hand']!r}, "
                f"expected {expected!r} (both-hands block, "
                f"per-trial hand must follow the lane)")
            seen.add(r["hand"])
        # Both boards actually fired in this run, so the assertion
        # above is exercising both branches, not just one.
        self.assertEqual(seen, {"right", "left"})


class LevelAndWindowOnScreenTests(unittest.TestCase):
    """The response window is reaction's only difficulty lever (see the
    mode's PROGRESSION docstring), yet nothing on the gameplay screen
    named the level or the window in force, so a block feeling harder
    had no visible cause for patient or clinician. Drives the real
    engine and the real GameplayScreen; only draw_text is intercepted,
    the same pattern test_force_pilot.py and test_lighthouse.py use to
    pin their own on-screen difficulty indicators."""

    def test_level_and_window_are_drawn(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            import finger_rehab.ui.screens as screens
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [640, 480]
            cfg.data["audio"]["enabled"] = False
            cfg.data["reaction"] = {"seed": 1, "catch_rate": 0.0}
            eng = GameEngine(cfg, KeyboardOnlySource())
            eng._screens = {"gameplay": MagicMock(), "results": MagicMock()}
            eng.begin_reaction_block()
            eng.mode.level = 2
            eng.mode.max_level = 3
            eng.mode.response_window = 1.5
            gp = screens.GameplayScreen(eng)
            surf = pygame.Surface((640, 480))
            seen = []
            original = screens.draw_text

            def recorder(s, text, pos, *a, **k):
                seen.append(str(text))
                return original(s, text, pos, *a, **k)

            screens.draw_text = recorder
            try:
                gp.draw(surf)
            finally:
                screens.draw_text = original
            joined = " | ".join(seen)
            self.assertIn("Level 2 of 3", joined)
            self.assertIn("Window 1.5s", joined)
        finally:
            pygame.quit()


class ReactionScreenLayerTests(unittest.TestCase):
    """The reaction gameplay layer, pinned after the screenshot-driven
    rework: the level pill must not render through the SCORE label,
    the RT feedback chip is the mode's headline feedback (larger,
    higher, stronger than the shared default), the streak chip parks
    under the mode pill instead of inside the feedback chip, the tier
    popup never rises through the RT number, and the foreperiod veil
    is strong enough that the stimulus visibly turns the lights back
    on. Real engine, real GameplayScreen, keyboard source."""

    def _engine_and_screen(self):
        import pygame
        pygame.init()
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        import finger_rehab.ui.screens as screens
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["audio"]["enabled"] = False
        cfg.data["reaction"] = {"seed": 1, "catch_rate": 0.0}
        eng = GameEngine(cfg, KeyboardOnlySource())
        eng._screens = {"gameplay": MagicMock(), "results": MagicMock()}
        eng.begin_reaction_block()
        gp = screens.GameplayScreen(eng)
        gp._countdown_until = 0.0
        return eng, gp, screens

    def test_level_pill_clears_the_score_label(self) -> None:
        import pygame
        try:
            eng, gp, screens = self._engine_and_screen()
            surf = pygame.Surface((1280, 800))
            calls = []
            original = screens.draw_text

            def recorder(s, text, pos, theme, layout, pt=20,
                         centre=False, **k):
                calls.append((str(text), pos, pt, centre))
                return original(s, text, pos, theme, layout, pt=pt,
                                centre=centre, **k)

            screens.draw_text = recorder
            try:
                gp.draw(surf)
            finally:
                screens.draw_text = original

            def rect_for(needle):
                for text, pos, pt, centre in calls:
                    if needle in text:
                        font = gp.layout.font(pt)
                        w, h = font.size(text)
                        r = pygame.Rect(0, 0, w, h)
                        if centre:
                            r.center = pos
                        else:
                            r.topleft = pos
                        return r
                raise AssertionError(f"{needle!r} never drawn")

            level_rect = rect_for("Level 1 of")
            score_rect = rect_for("SCORE")
            self.assertFalse(level_rect.colliderect(score_rect),
                             "level pill renders through SCORE again")
        finally:
            pygame.quit()

    def test_rt_chip_is_the_headline_and_sits_clear_of_tiles(
            self) -> None:
        import pygame
        try:
            eng, gp, screens = self._engine_and_screen()
            gp.set_message("262 ms", 2.0, kind="success")
            chips = []
            original = screens._chip

            def recorder(surf, layout, centre, text, fg, **k):
                chips.append((text, centre, k))
                return original(surf, layout, centre, text, fg, **k)

            screens._chip = recorder
            try:
                gp.draw(pygame.Surface((1280, 800)))
            finally:
                screens._chip = original
            rt = [(c, k) for t, c, k in chips if t == "262 ms"]
            self.assertEqual(len(rt), 1)
            centre, kwargs = rt[0]
            # Larger and stronger than the shared 30 pt / alpha 30
            # default, and high enough that the grown chip still
            # clears the tallest lane tile (top = 220).
            self.assertGreaterEqual(kwargs.get("font_pt", 0), 34)
            self.assertGreaterEqual(kwargs.get("bg_alpha", 0), 40)
            self.assertLessEqual(centre[1], 190)
        finally:
            pygame.quit()

    def test_streak_chip_stays_out_of_the_feedback_chip(self) -> None:
        import pygame
        try:
            eng, gp, screens = self._engine_and_screen()
            eng.hit_streak = 3
            centred = []
            gp._draw_chip = (lambda surf, centre, text, fg, **k:
                             centred.append(text))
            gp.draw(pygame.Surface((1280, 800)))
            self.assertFalse(
                [t for t in centred if "STREAK" in t],
                "reaction streak chip is back at (cx, 170), inside "
                "the RT feedback chip")
        finally:
            pygame.quit()

    def test_no_tier_popup_in_reaction(self) -> None:
        import pygame
        try:
            eng, gp, _screens = self._engine_and_screen()
            now = 100.0
            gp.flash_lane(0, (0, 200, 0), 0.4, now, popup_text="Good")
            self.assertEqual(gp._popups, [],
                             "tier popup rises through the RT chip")
            # Every other mode keeps the popup.
            eng.current_block = "adaptive"
            gp.flash_lane(0, (0, 200, 0), 0.4, now, popup_text="Good")
            self.assertEqual(len(gp._popups), 1)
        finally:
            pygame.quit()

    def test_foreperiod_veil_is_strong_enough_to_read(self) -> None:
        import pygame
        try:
            eng, gp, _screens = self._engine_and_screen()
            eng.mode._phase = "foreperiod"
            gp.draw(pygame.Surface((1280, 800)))
            self.assertIsNotNone(gp._hold_dim)
            alpha = gp._hold_dim.get_at((5, 5)).a
            # 140 washed the pastel tiles to near full brightness, so
            # the stimulus had nothing to switch back on.
            self.assertGreaterEqual(alpha, 160)
        finally:
            pygame.quit()


class SetupScreenGatingTests(unittest.TestCase):
    """The pace slider is a classic-only control. Showing it for
    reaction would hand the patient a knob that claims the wait is
    fixed, which is the opposite of the mode's design."""

    def test_slider_ignores_events_unless_classic(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            from finger_rehab.ui.screens import SetupScreen
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            eng = GameEngine(cfg, KeyboardOnlySource())
            ss = SetupScreen(eng)
            ss.pace_slider.handle_event = MagicMock()
            ev = pygame.event.Event(
                pygame.MOUSEBUTTONDOWN, pos=(640, 250), button=1)
            eng.cfg.data.setdefault("game", {})["mode"] = "reaction"
            ss.handle_event(ev)
            ss.pace_slider.handle_event.assert_not_called()
            eng.cfg.data["game"]["mode"] = "classic"
            ss.handle_event(ev)
            ss.pace_slider.handle_event.assert_called_once()
        finally:
            pygame.quit()


class ResultsScreenMedianCardTests(unittest.TestCase):
    """reaction.py's own research case (Ratcliff 1993; Whelan 2008)
    names the median RT as the headline because the distribution is
    right-skewed and a mean gets dragged by lapses, but the Results
    screen used to fall into the generic card set and show only AVG
    RT (a mean). A reaction block must show MEDIAN RT, sourced from
    the block summary, not the mode-agnostic mean."""

    def _draw_reaction_results(self, block_summary_reaction):
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
        e.hits, e.misses, e.score = 18, 6, 1200
        e.current_block, e.hand_mode = "reaction", "right"
        e.best_streak, e.per_lane_stats = 3, {}
        e.last_session_root = None
        e.mode = None
        e.session = type("S", (), {
            "participant": "T", "age": "60",
            "block_summary": {"reaction": block_summary_reaction}})()
        e.stop_all_motors = lambda *a, **k: None
        e.overall_mean_rt = lambda: 298.5
        e.overall_best_rt = lambda: 202.4
        r = ResultsScreen(e)
        r._shown_t = 1.0  # entry animation already finished
        # These assertions are about the FULL read-out (every card
        # this mode produces, plus its per-finger charts), which is
        # what the More detail view draws. The finished screen shows
        # the three ResultsScreen.SLIM_CARDS picks out of the same
        # list; test_session_flow covers that view.
        r.show_details = True
        seen = []
        r._draw_stat_card = (
            lambda surf, rect, lbl, val, col: seen.append((lbl, val)))
        surf = pygame.Surface((1280, 800))
        r.draw(surf)
        pygame.quit()
        return seen

    def test_median_rt_card_replaces_avg_rt_as_the_headline(self) -> None:
        cards = self._draw_reaction_results({
            "median_rt_ms": 202.4, "p10_rt_ms": 180.0, "accuracy": None,
        })
        labels = [lbl for lbl, _ in cards]
        self.assertIn("MEDIAN RT", labels)
        median_val = dict(cards)["MEDIAN RT"]
        self.assertEqual(median_val, "202 ms")
        # AVG RT (the mean, dragged by lapses in this scenario) must
        # not be the number under the headline MEDIAN RT label.
        self.assertNotEqual(median_val, "298 ms")

    def test_choice_accuracy_shown_when_available(self) -> None:
        cards = self._draw_reaction_results({
            "median_rt_ms": 250.0, "p10_rt_ms": 200.0, "accuracy": 0.72,
        })
        labels = [lbl for lbl, _ in cards]
        self.assertIn("ACCURACY", labels)
        self.assertEqual(dict(cards)["ACCURACY"], "72%")


if __name__ == "__main__":
    unittest.main()
