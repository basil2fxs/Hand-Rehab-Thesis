"""Mirror-mode tests. Mirror is the bilateral-training game where
both hands' same finger fire at once and the patient has to land
both presses inside the timing window for the trial to count. The
RT for scoring is the later of the two presses so the score
reflects how synchronised the bimanual movement was, not just the
strong-side speed.

Test plan:
  - one trial, both presses on time -> Hit, RT = later press
  - one trial, only one side presses -> Miss
  - one trial, wrong finger on either side -> Miss (re-classified)
  - on_stim_multi fires both lanes through the existing pipeline
  - mode-select "mirror" pick skips setup and forces hand_mode=both
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _press(lane: int, t: float):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                       hand="both")


class _Spy:
    def __init__(self):
        self.cfg = MagicMock()
        self.cfg.get = MagicMock(return_value=0)
        self.apply_wrong_press_penalty = MagicMock(return_value=2)
        self.apply_idle_press_penalty = MagicMock(return_value=1)
        self.on_stim_multi = MagicMock()
        self.log_trial = MagicMock()
        self.finish_block = MagicMock()
        self.hand_mode = "both"


def _build(spy: _Spy, pattern=None, repeat_count=1,
            trigger=0.5, timeout=1.0):
    from finger_rehab.game.modes.mirror import MirrorMode
    from finger_rehab.game.scoring import ScoreConfig
    return MirrorMode(
        engine=spy,
        pattern=pattern if pattern is not None else [0, 1, 2, 3],
        repeat_count=repeat_count,
        trigger_interval_s=trigger,
        timeout_s=timeout,
        early_window_s=0.1,
        score_cfg=ScoreConfig(),
    )


class BothPressesNeededTests(unittest.TestCase):
    """One trial needs presses on BOTH sides for a Hit. Only the
    later press time counts toward RT.

    Mirror picks fingers via the adaptive engine, so order is
    random across trials. These tests pin pattern=[0] so the
    single-finger pool guarantees finger 0 fires regardless of
    weighting, leaving the press-pair logic as the thing under
    test rather than the order of trials.
    """

    def test_both_sides_on_time_logs_hit(self) -> None:
        spy = _Spy()
        mode = _build(spy, pattern=[0])
        mode._fire(now=0.0)
        # Finger 0 -> right=lane 0, left=lane 4.
        mode._handle_press(_press(0, 0.10), now=0.10)   # right
        # No log_trial yet because left hasn't pressed.
        spy.log_trial.assert_not_called()
        mode._handle_press(_press(4, 0.18), now=0.18)   # left
        spy.log_trial.assert_called_once()
        outcome = spy.log_trial.call_args[0][1]
        self.assertNotEqual(outcome.label, "Miss")
        # RT should be the LATER press (180 ms), not the earlier one.
        self.assertAlmostEqual(outcome.rt_ms, 180.0, places=2)

    def test_only_one_side_times_out_as_miss(self) -> None:
        spy = _Spy()
        mode = _build(spy, pattern=[0], timeout=0.2)
        mode._fire(now=0.0)
        mode._handle_press(_press(0, 0.10), now=0.10)   # right only
        # Force timeout. update() is what triggers the time-out
        # path; call it with now past stim + timeout.
        mode.update(dt=0.0)
        # Pretend wall time advanced past the timeout window. Also
        # park the adapter at a slow BPM so current_timeout_s lines
        # up with the test's 0.2 s timeout fallback - otherwise the
        # adapter's default 2.5 s window would swallow the test's
        # advanced 1 s clock.
        mode.adapter.bpm = 270.0   # ~0.22 s window at timeout_factor 0.9
        import time
        original = time.perf_counter
        time.perf_counter = lambda: 1.0
        try:
            mode.update(dt=0.0)
        finally:
            time.perf_counter = original
        spy.log_trial.assert_called_once()
        outcome = spy.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")
        # RT is undefined because the trial timed out without both
        # presses, so classify returned Miss with rt_ms=None.
        self.assertIsNone(outcome.rt_ms)

    def test_wrong_finger_on_one_side_reclassified_as_miss(self) -> None:
        spy = _Spy()
        mode = _build(spy, pattern=[0])
        mode._fire(now=0.0)
        # Finger 0 target. Right hand correctly presses lane 0, but
        # left hand presses lane 5 (middle) instead of 4 (index).
        mode._handle_press(_press(0, 0.10), now=0.10)
        mode._handle_press(_press(5, 0.15), now=0.15)
        # The wrong press should fire the wrong-press penalty.
        spy.apply_wrong_press_penalty.assert_called()
        # Trial still in flight because left hasn't pressed the
        # correct finger yet. Land the correct left finger so we
        # can check the reclassification.
        mode._handle_press(_press(4, 0.20), now=0.20)
        spy.log_trial.assert_called_once()
        outcome = spy.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")

    def test_sub_perfect_ms_press_scores_full_quality_not_zero(self) -> None:
        """classify() returns label='Perfect' for the fastest presses,
        checked before 'Great', but _finish caps mirror's own reward at
        Great (audit finding #72: the inter-trial rest is a
        deterministic function of BPM with no jitter, so the Perfect
        tier is reachable by anticipating the cadence rather than
        reacting to the stim, and the notebook's own analysis throws
        any press under ANTICIPATION_MS=100ms away as anticipation,
        not a response). This test also covers the original regression
        it replaced: Mirror's _QUALITY (a copy of AdaptiveMode's) must
        score the capped outcome as full credit, not fall through the
        .get(..., 0.0) default -- that default treated the best
        possible bimanual press exactly like a Miss."""
        spy = _Spy()
        mode = _build(spy, pattern=[0])
        records: list = []
        original = mode.adapter.record

        def _spy_record(lane, was_hit, rt_ms, quality=None):
            records.append((lane, was_hit, rt_ms, quality))
            return original(lane, was_hit, rt_ms, quality=quality)

        mode.adapter.record = _spy_record
        mode._fire(now=0.0)
        # Well under score_cfg's perfect_ms (default 100ms) for both
        # sides.
        mode._handle_press(_press(0, 0.03), now=0.03)
        mode._handle_press(_press(4, 0.04), now=0.04)
        outcome = spy.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Great")
        self.assertEqual(outcome.points, mode.score_cfg.great_points)
        self.assertEqual(len(records), 1)
        _, _, _, quality = records[0]
        self.assertGreaterEqual(quality, mode._QUALITY["Great"])

    def test_good_tier_press_not_affected_by_perfect_cap(self) -> None:
        """The Perfect-cap only touches sub-perfect_ms pairs; a
        genuinely Good-tier press is untouched."""
        spy = _Spy()
        mode = _build(spy, pattern=[0])
        mode._fire(now=0.0)
        mode._handle_press(_press(0, 0.30), now=0.30)
        mode._handle_press(_press(4, 0.32), now=0.32)
        outcome = spy.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Good")


class OnStimMultiWiringTests(unittest.TestCase):
    """_fire calls engine.on_stim_multi with both target lanes."""

    def test_fire_passes_both_lanes(self) -> None:
        spy = _Spy()
        mode = _build(spy, pattern=[1])     # finger 1 = middle
        mode._fire(now=0.0)
        spy.on_stim_multi.assert_called_once()
        lanes_arg = spy.on_stim_multi.call_args[0][0]
        # Pair should be (1, 5): right middle + left middle.
        self.assertEqual(sorted(lanes_arg), [1, 5])

    def test_fire_pattern_index_0_uses_lanes_0_and_4(self) -> None:
        spy = _Spy()
        mode = _build(spy, pattern=[0])
        mode._fire(now=0.0)
        lanes_arg = spy.on_stim_multi.call_args[0][0]
        self.assertEqual(sorted(lanes_arg), [0, 4])


class BetweenTrialSpamTests(unittest.TestCase):
    """A press with no active trial costs the idle-press penalty,
    same rule classic / adaptive use."""

    def test_idle_press_penalises(self) -> None:
        spy = _Spy()
        mode = _build(spy)
        # No trial active; a press arrives.
        mode._handle_press(_press(0, 0.0), now=0.0)
        spy.apply_idle_press_penalty.assert_called_once()


class AdaptiveTimingTests(unittest.TestCase):
    """Mirror runs the challenge-point adaptive engine internally so
    BPM + timeout + finger picks all evolve with performance."""

    def test_total_trials_matches_pattern_times_repeat(self) -> None:
        # Old contract: 4 fingers x 8 repeats = 32 trials. Adaptive
        # picking shouldn't change the budget, just the order.
        spy = _Spy()
        mode = _build(spy, pattern=[0, 1, 2, 3], repeat_count=8)
        self.assertEqual(mode.total_trials, 32)

    def test_finger_order_is_random_not_sequential(self) -> None:
        # With the four-finger pool and a default seed the adapter
        # picks a mix of fingers, NOT the old 0, 1, 2, 3, 0, 1, 2, 3
        # deterministic sweep. We fire 20 trials without recording
        # any outcomes (so the adapter weights stay equal) and check
        # the resulting sequence isn't the deterministic cycle.
        spy = _Spy()
        mode = _build(spy, pattern=[0, 1, 2, 3], repeat_count=5)
        fired: list[int] = []
        for _ in range(20):
            mode._fire(now=0.0)
            assert mode.active is not None
            fired.append(mode.active.finger)
            mode.active = None
        # Sanity: all picks land in 0..3.
        for f in fired:
            self.assertIn(f, (0, 1, 2, 3))
        # The old deterministic order would be [0,1,2,3]*5. Random
        # picking won't reproduce that.
        deterministic = [0, 1, 2, 3] * 5
        self.assertNotEqual(fired, deterministic)
        # And we should see at least two distinct fingers across
        # 20 picks (in practice we see all four).
        self.assertGreater(len(set(fired)), 1)

    def test_pattern_subset_restricts_finger_pool(self) -> None:
        # Therapist sets pattern=[0, 2] to drill only index + ring.
        # Adapter still picks from {0, 2} only.
        spy = _Spy()
        mode = _build(spy, pattern=[0, 2], repeat_count=10)
        fired: set[int] = set()
        for _ in range(15):
            mode._fire(now=0.0)
            assert mode.active is not None
            fired.add(mode.active.finger)
            mode.active = None
        self.assertTrue(fired.issubset({0, 2}))

    def test_finish_calls_adapter_record_and_next_bpm(self) -> None:
        # After a finished trial the adapter has to see the outcome
        # and recompute BPM so the next trial reflects performance.
        spy = _Spy()
        mode = _build(spy, pattern=[0])
        mode._fire(now=0.0)
        # Hit both sides on time.
        mode._handle_press(_press(0, 0.10), now=0.10)
        mode._handle_press(_press(4, 0.15), now=0.15)
        # Adapter should have one trial recorded against finger 0.
        self.assertEqual(mode.adapter.state[0].n_trials, 1)
        # And the streak counter inside the adapter ticked up because
        # the trial was a hit (not a miss).
        self.assertGreaterEqual(mode.adapter.current_streak, 1)

    def test_current_timeout_tracks_adapter_bpm(self) -> None:
        # Slow the adapter way down; the press window must widen so
        # patients who need more time get it.
        spy = _Spy()
        mode = _build(spy, pattern=[0])
        mode.adapter.bpm = 30.0     # 2 s cadence
        slow_window = mode.current_timeout_s
        mode.adapter.bpm = 120.0    # 0.5 s cadence
        fast_window = mode.current_timeout_s
        self.assertGreater(slow_window, fast_window)

    def test_cadence_uses_adapter_bpm_not_static_trigger(self) -> None:
        # Bump BPM up so 60/bpm is shorter than the test's 0.5 s
        # static trigger_interval. _fire should run on the bpm-derived
        # gate, not the static one.
        import time as _t
        spy = _Spy()
        mode = _build(spy, pattern=[0], trigger=10.0)  # static = 10 s
        mode.adapter.bpm = 120.0                        # cadence = 0.5 s
        # No active trial. Wall clock 0.6 s past the start; cadence
        # 0.5 s means the gate has opened, _fire should run on the
        # next update() tick.
        now = _t.perf_counter()
        mode.last_trigger_t = now - 0.6
        mode.update(dt=0.0)
        # _fire ran (active trial exists).
        self.assertIsNotNone(mode.active)


class EnginePickPathTests(unittest.TestCase):
    """ModeSelectScreen._pick('mirror') must force hand_mode=both
    and go straight to begin_mirror_block, bypassing the setup
    hand-picker screen."""

    def test_pick_mirror_skips_setup_and_starts_block(self) -> None:
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            from finger_rehab.ui.screens import ModeSelectScreen
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            eng = GameEngine(cfg, KeyboardOnlySource(cfg))
            # Stub the navigation so picking the card doesn't actually
            # try to start a block on the half-built engine.
            eng.begin_mirror_block = MagicMock()
            eng.show_setup = MagicMock()
            sc = ModeSelectScreen(eng)
            sc._pick("mirror")
            # Mirror bypasses setup.
            eng.show_setup.assert_not_called()
            eng.begin_mirror_block.assert_called_once()
            # And forces hand_mode = both.
            self.assertEqual(eng.hand_mode, "both")
            self.assertEqual(cfg.get("bilateral.hand"), "both")
        finally:
            pygame.quit()


class EndToEndMirrorBlockTests(unittest.TestCase):
    """Drive begin_mirror_block through a real engine + run a handful
    of mainloop frames to catch any crash from the integration points
    (pattern parsing, sequence building, on_stim_multi wiring,
    gameplay screen draw). Regression coverage for the _parse_pattern
    keyword bug that made the mode crash on entry."""

    def test_mirror_block_starts_and_draws_without_crash(self) -> None:
        import os, time, sys
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            eng = GameEngine(cfg, KeyboardOnlySource(cfg))
            eng.screen = pygame.display.set_mode(
                (eng.layout.width, eng.layout.height))
            eng._screens = eng._build_screens()
            # The mode-select pick path forces hand_mode="both"
            # before calling begin_mirror_block. Mirror also force-
            # rebuilds detectors + lanes itself, but going through
            # the same setup gives a realistic regression check.
            eng.hand_mode = "both"
            eng._build_detectors()
            for key in ("gameplay", "rhythm"):
                sc = eng._screens.get(key)
                if sc and hasattr(sc, "rebuild_lanes"):
                    sc.rebuild_lanes()
            eng.begin_mirror_block()
            # The mode constructed cleanly and is now the active one.
            self.assertEqual(eng.current_block, "mirror")
            self.assertIsNotNone(eng.mode)
            # Run a few mainloop tick cycles. update() will fire a
            # stim within the first cadence interval; draw() reaches
            # the new pair-bracket indicator path. If anything in
            # that chain crashes, the assertion at the end never
            # runs.
            for _ in range(10):
                eng._pump_source()
                if hasattr(eng.mode, "update"):
                    eng.mode.update(0.016)
                if eng.screen_obj and hasattr(eng.screen_obj, "draw"):
                    eng.screen_obj.draw(eng.screen)
                time.sleep(0.02)
            # If we got here without throwing the block is live.
            self.assertEqual(eng.current_block, "mirror")
        finally:
            pygame.quit()

    def test_mirror_retry_via_results_screen(self) -> None:
        # The Retry button on the results screen calls
        # retry_last_block, which must recognise "mirror" or fall
        # through to mode select. Confirms the new branch added in
        # retry_last_block.
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            eng = GameEngine(cfg, KeyboardOnlySource(cfg))
            eng.screen = pygame.display.set_mode(
                (eng.layout.width, eng.layout.height))
            eng._screens = eng._build_screens()
            eng.hand_mode = "both"
            eng._build_detectors()
            for key in ("gameplay", "rhythm"):
                sc = eng._screens.get(key)
                if sc and hasattr(sc, "rebuild_lanes"):
                    sc.rebuild_lanes()
            eng.current_block = "mirror"
            # Stub begin_mirror_block to confirm retry_last_block
            # routes to it, not to show_mode_select.
            called = {"begin": False, "show_mode": False}
            eng.begin_mirror_block = lambda: called.__setitem__("begin", True)
            eng.show_mode_select = lambda: called.__setitem__("show_mode", True)
            eng.retry_last_block()
            self.assertTrue(called["begin"])
            self.assertFalse(called["show_mode"])
        finally:
            pygame.quit()


class PerHandLoggingTests(unittest.TestCase):
    """Regression coverage for the per-hand logging fix.

    Before the fix, a mirror trial's CSV row logged hand="both" and a
    lane in 1..4 only (PendingMirrorTrial.lane() never returns
    finger + 4), and time_difference_ms carried the shared LATER-press
    RT used for scoring. None of that let an analysis recover which
    hand was actually slow on a given trial, even though synchronised
    bilateral movement is mirror's whole training goal. Driven through
    a real engine + real TrialLogger, not mocked, so this catches the
    bug at the point it actually showed up: the CSV row.
    """

    def test_trials_csv_carries_each_hands_own_press_latency(self) -> None:
        import os
        import csv
        import tempfile
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            from finger_rehab.hardware.fsr_detector import PressEvent

            tmpdir = tempfile.mkdtemp()
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data.setdefault("session", {})["data_dir"] = tmpdir
            eng = GameEngine(cfg, KeyboardOnlySource(cfg))
            eng.screen = pygame.display.set_mode(
                (eng.layout.width, eng.layout.height))
            eng._screens = eng._build_screens()
            eng.hand_mode = "both"
            eng._build_detectors()
            for key in ("gameplay", "rhythm"):
                sc = eng._screens.get(key)
                if sc and hasattr(sc, "rebuild_lanes"):
                    sc.rebuild_lanes()

            eng.begin_mirror_block()
            mode = eng.mode
            mode._fire(now=0.0)
            finger = mode.active.finger
            # Right hand fast (100 ms), left hand slow (270 ms), so the
            # two sides are only distinguishable if each is logged
            # separately rather than collapsed into the shared
            # later-press RT (270 ms) that scoring uses.
            mode._handle_press(
                PressEvent(lane=finger, t_perf=0.10, value=0,
                           baseline=0.0, hand="both"), now=0.10)
            mode._handle_press(
                PressEvent(lane=finger + 4, t_perf=0.27, value=0,
                           baseline=0.0, hand="both"), now=0.27)

            eng.trial_logger.close()
            with open(eng.session_paths.trials_csv) as f:
                rows = list(csv.DictReader(f))

            # One row per trial, not two: the fix attributes both
            # hands from a single row rather than duplicating it (which
            # would double-count the trial in every block-level stat).
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["hand"], "both")
            # The scored RT is still the later of the two presses,
            # unchanged by the fix.
            self.assertAlmostEqual(
                float(row["time_difference_ms"]), 270.0, places=1)
            # Each hand's OWN latency is now attributable from this one
            # row, independent of the shared scored RT above.
            self.assertAlmostEqual(
                float(row["mirror_right_rt_ms"]), 100.0, places=1)
            self.assertAlmostEqual(
                float(row["mirror_left_rt_ms"]), 270.0, places=1)
        finally:
            pygame.quit()

    def test_miss_on_one_side_leaves_that_hands_rt_blank(self) -> None:
        spy = _Spy()
        mode = _build(spy, pattern=[0], timeout=0.2)
        mode._fire(now=0.0)
        mode._handle_press(_press(0, 0.10), now=0.10)   # right only
        mode.adapter.bpm = 270.0
        import time
        original = time.perf_counter
        time.perf_counter = lambda: 1.0
        try:
            mode.update(dt=0.0)
        finally:
            time.perf_counter = original
        spy.log_trial.assert_called_once()
        kwargs = spy.log_trial.call_args.kwargs
        right_rt, left_rt = kwargs["mirror_hand_rts"]
        self.assertAlmostEqual(right_rt, 100.0, places=1)
        self.assertIsNone(left_rt)


class AsyncPairDowngradesToMissTests(unittest.TestCase):
    """Audit finding #64: the BPM-derived press window is the only
    togetherness bound classify() sees, and it widens to 5.4s at the
    BPM floor -- exactly when a struggling patient's asynchrony
    matters most. A fixed-ms max_async_ms gate must downgrade a
    grossly asynchronous pair to Miss regardless of how fast the
    later press was, even when both presses land inside the window."""

    def test_grossly_async_pair_scores_miss_even_inside_the_window(
            self) -> None:
        spy = _Spy()
        mode = _build(spy, pattern=[0])
        mode.adapter.bpm = 10.0   # BPM floor -> 5.4s window
        mode._fire(now=0.0)
        mode._handle_press(_press(0, 0.10), now=0.10)    # right, 100ms
        mode._handle_press(_press(4, 3.00), now=3.00)    # left, 3000ms
        outcome = spy.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")

    def test_in_sync_pair_still_scores_a_hit(self) -> None:
        spy = _Spy()
        mode = _build(spy, pattern=[0])
        mode.adapter.bpm = 10.0
        mode._fire(now=0.0)
        mode._handle_press(_press(0, 0.10), now=0.10)
        mode._handle_press(_press(4, 0.18), now=0.18)    # 80ms gap
        outcome = spy.log_trial.call_args[0][1]
        self.assertNotEqual(outcome.label, "Miss")

    def test_async_gate_is_fixed_ms_not_bpm_scaled(self) -> None:
        # Same 400ms gap at a fast BPM (narrow window) should still be
        # caught by the fixed max_async_ms gate, not just by the
        # (already narrow) BPM window timing the pair out.
        spy = _Spy()
        mode = _build(spy, pattern=[0])
        mode.adapter.bpm = 10.0
        mode.max_async_ms = 350.0
        mode._fire(now=0.0)
        mode._handle_press(_press(0, 0.10), now=0.10)
        mode._handle_press(_press(4, 0.50), now=0.50)    # 400ms gap
        outcome = spy.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")


class DistinctFingerCountBudgetTests(unittest.TestCase):
    """Audit finding #74: _pick_finger reduces to
    sorted(set(self.pattern)), so a duplicate finger entry in the
    config pattern buys a longer block with NO extra weighting toward
    that finger (unlike classic mode's pattern * repeat_count
    sequence, where a repeated entry directly weights it). The trial
    budget must be based on the DISTINCT finger count, matching what
    the picker actually draws from."""

    def test_duplicate_pattern_entry_does_not_inflate_the_budget(
            self) -> None:
        spy = _Spy()
        mode = _build(spy, pattern=[0, 0, 1, 2], repeat_count=8)
        # 3 distinct fingers * 8 repeats, not 4 raw entries * 8.
        self.assertEqual(mode.total_trials, 24)

    def test_no_duplicate_pattern_is_unaffected(self) -> None:
        spy = _Spy()
        mode = _build(spy, pattern=[0, 1, 2, 3], repeat_count=8)
        self.assertEqual(mode.total_trials, 32)


class BlockRtDoubleCountTests(unittest.TestCase):
    """Audit finding #65: a Miss trial can still carry an rt_ms (the
    async-gap downgrade above, and the wrong-finger-then-correct
    downgrade both keep it for time_difference_ms), so log_trial must
    gate the block-level RT sum/count and the per-lane RT list on the
    outcome label, not just rt_ms being non-None -- otherwise a Miss
    trial double-counts as both a hit (via its RT) and a miss (via
    the miss counters), inflating hit_rate, n_trials and avg_rt_ms."""

    def _real_engine(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        import tempfile
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data.setdefault("session", {})["data_dir"] = tempfile.mkdtemp()
        eng = GameEngine(cfg, KeyboardOnlySource(cfg))
        eng.screen = pygame.display.set_mode(
            (eng.layout.width, eng.layout.height))
        eng._screens = eng._build_screens()
        eng.hand_mode = "both"
        eng._build_detectors()
        for key in ("gameplay", "rhythm"):
            sc = eng._screens.get(key)
            if sc and hasattr(sc, "rebuild_lanes"):
                sc.rebuild_lanes()
        return eng, pygame

    def test_wrong_finger_miss_with_an_rt_does_not_inflate_rt_count(
            self) -> None:
        from finger_rehab.hardware.fsr_detector import PressEvent
        eng, pygame = self._real_engine()
        try:
            eng.begin_mirror_block()
            mode = eng.mode
            mode.adapter.bpm = 10.0
            # 3 clean hits.
            for _ in range(3):
                mode._fire(now=0.0)
                finger = mode.active.finger
                mode._handle_press(
                    PressEvent(lane=finger, t_perf=0.05, value=0,
                               baseline=0.0, hand="both"), now=0.05)
                mode._handle_press(
                    PressEvent(lane=finger + 4, t_perf=0.06, value=0,
                               baseline=0.0, hand="both"), now=0.06)
            # 1 wrong-finger-then-correct Miss that still carries an
            # rt_ms on the row (mirror.py keeps rt_ms=rt_ms on the
            # downgrade).
            mode._fire(now=0.0)
            finger = mode.active.finger
            other = (finger + 1) % 4
            mode._handle_press(
                PressEvent(lane=other, t_perf=0.03, value=0,
                           baseline=0.0, hand="both"), now=0.03)
            mode._handle_press(
                PressEvent(lane=finger, t_perf=0.05, value=0,
                           baseline=0.0, hand="both"), now=0.05)
            mode._handle_press(
                PressEvent(lane=finger + 4, t_perf=0.06, value=0,
                           baseline=0.0, hand="both"), now=0.06)
            self.assertEqual(eng.hits, 3)
            self.assertEqual(eng.misses, 1)
            # The bug: _block_rt_count used to include the Miss row
            # too (4), inflating the denominator used by
            # _populate_research_summary's hit_rate rollup.
            self.assertEqual(eng._block_rt_count, 3)
        finally:
            pygame.quit()


class MirrorBlockSummarySectionTests(unittest.TestCase):
    """Audit finding #68: the player is never shown the trained
    quantity (bimanual sync), and the block summary exports no
    asynchrony despite per-hand RTs on every row. _build_block_summary
    must add a "mirror" section (mean gap + per-hand mean RT) built
    from clean synchronised hits only."""

    def _real_engine(self):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        import tempfile
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data.setdefault("session", {})["data_dir"] = tempfile.mkdtemp()
        eng = GameEngine(cfg, KeyboardOnlySource(cfg))
        eng.screen = pygame.display.set_mode(
            (eng.layout.width, eng.layout.height))
        eng._screens = eng._build_screens()
        eng.hand_mode = "both"
        eng._build_detectors()
        for key in ("gameplay", "rhythm"):
            sc = eng._screens.get(key)
            if sc and hasattr(sc, "rebuild_lanes"):
                sc.rebuild_lanes()
        return eng, pygame

    def test_block_summary_carries_mirror_sync_section(self) -> None:
        from finger_rehab.hardware.fsr_detector import PressEvent
        eng, pygame = self._real_engine()
        try:
            eng.begin_mirror_block()
            mode = eng.mode
            mode.adapter.bpm = 40.0
            for i in range(4):
                mode._fire(now=0.0)
                finger = mode.active.finger
                mode._handle_press(
                    PressEvent(lane=finger, t_perf=0.05, value=0,
                               baseline=0.0, hand="both"), now=0.05)
                mode._handle_press(
                    PressEvent(lane=finger + 4,
                               t_perf=0.08 + i * 0.01, value=0,
                               baseline=0.0, hand="both"),
                    now=0.08 + i * 0.01)
            summary = eng._build_block_summary("completed")
            mir = summary.get("mirror")
            self.assertIsNotNone(mir)
            self.assertEqual(mir["n_synced_hits"], 4)
            self.assertIsNotNone(mir["mean_gap_ms"])
            self.assertIsNotNone(mir["right_hand_mean_rt_ms"])
            self.assertIsNotNone(mir["left_hand_mean_rt_ms"])

            # Results screen reads it back through _mirror_summary().
            eng.session.block_summary = summary
            results = eng._screens.get("results")
            self.assertIsNotNone(results)
            self.assertEqual(results._mirror_summary(), mir)
            # And draw() takes the mirror branch without crashing.
            results.draw(eng.screen)
        finally:
            pygame.quit()


class KeyboardPressRawLoggingTests(unittest.TestCase):
    """Audit finding #75: keyboard KEYDOWN presses in mirror.handle_event
    went straight to queue_press, bypassing engine._on_press -- the
    only place raw.csv normally gets a "press" event. A keyboard-only
    mirror session's raw.csv had zero press/release rows, so an
    anticipatory between-trial press was invisible to the data.
    handle_event must also queue a raw press event (detail=keyboard)."""

    def test_keyboard_press_appears_in_raw_csv(self) -> None:
        import os
        import csv
        import tempfile
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
            from finger_rehab.game.modes._keys import resolve_key

            tmpdir = tempfile.mkdtemp()
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data.setdefault("session", {})["data_dir"] = tmpdir
            eng = GameEngine(cfg, KeyboardOnlySource(cfg))
            eng.screen = pygame.display.set_mode(
                (eng.layout.width, eng.layout.height))
            eng._screens = eng._build_screens()
            eng.hand_mode = "both"
            eng._build_detectors()
            for key in ("gameplay", "rhythm"):
                sc = eng._screens.get(key)
                if sc and hasattr(sc, "rebuild_lanes"):
                    sc.rebuild_lanes()

            eng.begin_mirror_block()
            mode = eng.mode
            mode._fire(now=0.0)
            finger = mode.active.finger
            km = cfg.get("game.keyboard_map_bilateral", {})
            right_key = next(k for k, v in km.items() if v == finger)
            left_key = next(k for k, v in km.items() if v == finger + 4)
            for key_name in (right_key, left_key):
                ev = pygame.event.Event(
                    pygame.KEYDOWN, key=resolve_key(key_name))
                mode.handle_event(ev)
            mode.update(dt=0.0)

            eng.raw_logger.stop()
            with open(eng.session_paths.raw_csv) as f:
                rows = list(csv.DictReader(f))
            press_rows = [r for r in rows if r.get("event") == "press"]
            self.assertEqual(len(press_rows), 2)
            self.assertTrue(all(r.get("detail") == "keyboard"
                                 for r in press_rows))
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
