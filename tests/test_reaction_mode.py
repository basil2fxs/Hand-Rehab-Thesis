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
    from rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                       hand="right")


def _build_mode(**overrides):
    """A ReactionMode wired to a MagicMock engine, with timings shrunk
    so tests drive the state machine with explicit `now` values instead
    of sleeping."""
    from rehab.game.modes.reaction import ReactionMode
    from rehab.game.scoring import ScoreConfig
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


class EngineIntegrationTests(unittest.TestCase):
    """begin_reaction_block through to the CSV and metadata on disk.
    This is the path a real session takes, so it is where a broken
    column name or a summary that never lands would show up."""

    def test_block_writes_distinguishable_rows_and_summary(self) -> None:
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
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
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
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
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            import rehab.ui.screens as screens
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


class SetupScreenGatingTests(unittest.TestCase):
    """The pace slider is a classic-only control. Showing it for
    reaction would hand the patient a knob that claims the wait is
    fixed, which is the opposite of the mode's design."""

    def test_slider_ignores_events_unless_classic(self) -> None:
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            from rehab.ui.screens import SetupScreen
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


if __name__ == "__main__":
    unittest.main()
