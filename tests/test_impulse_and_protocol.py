"""Tests for two related additions:

  1. Force-time integral (impulse) capture on the FSR detector +
     plumbing through the engine into the trial CSV.
  2. Pretest / main / aftertest protocol that runs configured
     blocks back-to-back, tagging each trial row with a phase
     label for downstream learning-effects analysis.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ImpulseDetectorTests(unittest.TestCase):
    """ReleaseEvent now carries impulse_raw + impulse_minus_baseline.
    Compute trapezoidal integration over the press window."""

    def _cal(self):
        from rehab.hardware.fsr_detector import Calibration
        # value_alpha=1 disables smoothing so the test can predict
        # the integral analytically.
        return Calibration(
            num_sensors=4, value_alpha=1.0,
            on_delta=[40] * 4, off_delta=[20] * 4,
            abs_on_min=[300] * 4, abs_off_max=[300] * 4,
            debounce_ms=0,
        )

    def test_release_event_carries_impulse_fields(self) -> None:
        from rehab.hardware.fsr_detector import FSRDetector, ReleaseEvent
        det = FSRDetector(self._cal(), hand="right")
        releases: list[ReleaseEvent] = []
        det.on_release = releases.append
        # Warm-up: baseline settles near 50.
        det.feed(0.0, (50, 50, 50, 50))
        # Press window: rising edge at t=0.1, hold 500 for 0.3 s.
        # Trapezoidal integral of (500 - ~50) over 0.3 s = ~135.
        det.feed(0.1, (500, 50, 50, 50))   # rising edge
        det.feed(0.2, (500, 50, 50, 50))   # held
        det.feed(0.3, (500, 50, 50, 50))   # held
        det.feed(0.4, (500, 50, 50, 50))   # held
        det.feed(0.5, (50, 50, 50, 50))    # falling edge
        self.assertEqual(len(releases), 1)
        ev = releases[0]
        self.assertIsNotNone(ev.impulse_minus_baseline)
        # Baseline at rising-edge ~ 50. (500 - 50) * 0.4 s = 180,
        # minus the trapezoid lopping at the falling edge gives a
        # bit less. Just check it lands in a sensible range and the
        # duration is right.
        self.assertGreater(ev.impulse_minus_baseline, 100.0)
        self.assertLess(ev.impulse_minus_baseline, 250.0)
        self.assertAlmostEqual(ev.duration_s, 0.4, places=2)

    def test_impulse_resets_between_presses(self) -> None:
        # Two presses on the same sensor. The second press's impulse
        # must reflect only that press, not carry over from the
        # first. Detects state leaks in the integrator.
        from rehab.hardware.fsr_detector import FSRDetector, ReleaseEvent
        det = FSRDetector(self._cal(), hand="right")
        releases: list[ReleaseEvent] = []
        det.on_release = releases.append
        det.feed(0.0, (50, 50, 50, 50))
        # Press 1: hard, 800 held for 0.2 s.
        det.feed(0.1, (800, 50, 50, 50))
        det.feed(0.2, (800, 50, 50, 50))
        det.feed(0.3, (50, 50, 50, 50))
        # Press 2: lighter, 500 held for 0.2 s.
        det.feed(0.4, (500, 50, 50, 50))
        det.feed(0.5, (500, 50, 50, 50))
        det.feed(0.6, (50, 50, 50, 50))
        self.assertEqual(len(releases), 2)
        # Press 2's impulse must be smaller than press 1's.
        self.assertGreater(
            releases[0].impulse_minus_baseline,
            releases[1].impulse_minus_baseline,
        )


class EngineImpulsePlumbingTests(unittest.TestCase):
    """log_trial writes the impulse_n column whenever a press was
    live at the moment the trial closed. Mirrors the existing
    peak_force_n plumbing."""

    def test_impulse_in_trial_csv_columns(self) -> None:
        from rehab.data.logger import TRIAL_COLUMNS
        self.assertIn("impulse_n", TRIAL_COLUMNS)

    def test_per_lane_impulse_appears_in_block_summary(self) -> None:
        # Build a __new__-style engine, seed per_lane_impulse, and
        # confirm _populate_research_summary surfaces it under
        # block_summary.per_lane[lane]["impulse_mean"].
        from rehab.game.engine import GameEngine
        import time
        eng = GameEngine.__new__(GameEngine)
        eng.cfg = MagicMock()
        eng.cfg.get = MagicMock(side_effect=lambda k, d=None:
                                  4 if k == "fsr.num_sensors_per_hand"
                                  else d)
        eng.current_block = "classic"
        eng.hand_mode = "right"
        eng.hits = 1
        eng.misses = 0
        eng._block_t0 = time.perf_counter()
        eng._block_rt_sum = 200.0
        eng._block_rt_count = 1
        eng._block_bpm_min = None
        eng._block_bpm_max = None
        eng._block_peak_streak = 0
        eng._block_wrong_press_trials = 0
        eng._block_rhythm_spurious_presses = 0
        eng._block_idle_presses = 0
        eng._per_lane_rts = {0: [200.0]}
        eng._per_lane_misses = {}
        eng._per_lane_wrong = {}
        eng._per_lane_peak_force = {0: [12.5]}
        eng._per_lane_impulse = {0: [3.4, 4.0]}
        eng._across_blocks_mean_rt = []
        eng._across_blocks_mean_peak = []
        eng._drift_samples = {}
        eng._rhythm_press_times_s = []
        eng._rhythm_beat_times_s = []
        eng._rhythm_signed_offsets_ms = []
        eng.mode = None
        eng.source = MagicMock(spec=["is_connected"])
        eng.score = 0
        s = eng._build_block_summary("completed")
        lane0 = s["per_lane"]["0"]
        self.assertIn("impulse_mean", lane0)
        self.assertAlmostEqual(lane0["impulse_mean"], 3.7, places=4)


class RhythmEntrainmentLagOneTests(unittest.TestCase):
    """For rhythm blocks the summary should include
    entrainment_lag1_r alongside beat_offset_stats."""

    def test_lag1_appears_with_three_offsets(self) -> None:
        from rehab.game.engine import GameEngine
        import time
        eng = GameEngine.__new__(GameEngine)
        eng.cfg = MagicMock()
        eng.cfg.get = MagicMock(return_value=4)
        eng.current_block = "rhythm"
        eng.hand_mode = "right"
        eng.hits = 3
        eng.misses = 0
        eng._block_t0 = time.perf_counter()
        eng._block_rt_sum = 0.0
        eng._block_rt_count = 0
        eng._block_bpm_min = None
        eng._block_bpm_max = None
        eng._block_peak_streak = 0
        eng._block_wrong_press_trials = 0
        eng._block_rhythm_spurious_presses = 0
        eng._block_idle_presses = 0
        eng._per_lane_rts = {}
        eng._per_lane_misses = {}
        eng._per_lane_wrong = {}
        eng._per_lane_peak_force = {}
        eng._per_lane_impulse = {}
        eng._across_blocks_mean_rt = []
        eng._across_blocks_mean_peak = []
        eng._drift_samples = {}
        # Press times + beat times pair-aligned. Signed offsets
        # entrained: each press is consistently +10 ms late.
        eng._rhythm_press_times_s = [1.01, 2.01, 3.01, 4.01]
        eng._rhythm_beat_times_s = [1.0, 2.0, 3.0, 4.0]
        eng._rhythm_signed_offsets_ms = [10.0, 10.0, 10.0, 10.0]
        eng.mode = None
        eng.source = MagicMock(spec=["is_connected"])
        eng.score = 0
        s = eng._build_block_summary("completed")
        bo = s.get("beat_offset_stats") or {}
        # Constant offsets -> stdev = 0 -> Pearson undefined (None).
        # The presence of the key alone is what matters for schema
        # stability; the math edge case is acceptable.
        self.assertIn("entrainment_lag1_r", bo)


class ProtocolTests(unittest.TestCase):
    """start_protocol parses cfg.protocol.blocks, kicks off the
    first step, and finish_block auto-advances through the rest.
    Each block's trial CSV rows get the phase label."""

    def _engine(self, blocks):
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data.setdefault("protocol", {})["blocks"] = blocks
        eng = GameEngine(cfg, KeyboardOnlySource(cfg))
        # Stub the begin_*_block methods so they record calls
        # instead of actually starting a block (which would need a
        # full screen / detector stack).
        calls: list[str] = []
        eng.begin_classic_block = lambda: calls.append("classic")
        eng.begin_adaptive_block = lambda: calls.append("adaptive")
        eng.begin_mirror_block = lambda: calls.append("mirror")
        return eng, calls, pygame

    def test_no_protocol_returns_false(self) -> None:
        eng, calls, pg = self._engine([])
        try:
            self.assertFalse(eng.start_protocol())
            self.assertEqual(calls, [])
        finally:
            pg.quit()

    def test_three_step_protocol_runs_first_block(self) -> None:
        eng, calls, pg = self._engine([
            {"mode": "classic",  "phase": "pretest"},
            {"mode": "adaptive", "phase": "main"},
            {"mode": "classic",  "phase": "aftertest"},
        ])
        try:
            self.assertTrue(eng.start_protocol())
            self.assertEqual(calls, ["classic"])
            self.assertEqual(eng._current_phase, "pretest")
            self.assertTrue(eng._protocol_active)
            self.assertEqual(eng._protocol_index, 1)
        finally:
            pg.quit()

    def test_finish_block_advances_to_next_step(self) -> None:
        eng, calls, pg = self._engine([
            {"mode": "classic", "phase": "pretest"},
            {"mode": "adaptive", "phase": "main"},
        ])
        try:
            # Stub the bits of finish_block that need real session
            # state. Only the protocol-advance branch is under test.
            eng.raw_logger = None
            eng.audio = None
            eng.session_paths = None
            eng.session = MagicMock()
            eng.session.finished_at = ""
            eng.session.notes = ""
            eng._build_block_summary = MagicMock(return_value={})
            eng._close_loggers = MagicMock()
            eng.show_results = MagicMock()
            eng.start_protocol()
            # First step is classic-pretest, calls[0] = "classic".
            self.assertEqual(eng._current_phase, "pretest")
            eng.finish_block()
            # finish_block should fire the second begin_*_block.
            self.assertEqual(calls, ["classic", "adaptive"])
            self.assertEqual(eng._current_phase, "main")
            # show_results NOT called yet because protocol still
            # has the second step active.
            eng.show_results.assert_not_called()
        finally:
            pg.quit()

    def test_final_step_falls_through_to_results(self) -> None:
        eng, calls, pg = self._engine([
            {"mode": "classic", "phase": "pretest"},
        ])
        try:
            eng.raw_logger = None
            eng.audio = None
            eng.session_paths = None
            eng.session = MagicMock()
            eng._build_block_summary = MagicMock(return_value={})
            eng._close_loggers = MagicMock()
            eng.show_results = MagicMock()
            eng.start_protocol()
            self.assertEqual(eng._current_phase, "pretest")
            eng.finish_block()
            # Only one step, so finish_block goes to Results.
            eng.show_results.assert_called_once()
            # Protocol state cleared so a subsequent free-play
            # block doesn't inherit the phase.
            self.assertFalse(eng._protocol_active)
            self.assertEqual(eng._current_phase, "")
        finally:
            pg.quit()

    def test_unknown_mode_in_protocol_is_dropped(self) -> None:
        # An entry with mode="bogus" must not crash the parser; it
        # just gets skipped so the rest of the protocol still runs.
        eng, calls, pg = self._engine([
            {"mode": "bogus", "phase": "junk"},
            {"mode": "classic", "phase": "pretest"},
        ])
        try:
            self.assertTrue(eng.start_protocol())
            # First valid entry (classic) runs first.
            self.assertEqual(calls, ["classic"])
            self.assertEqual(eng._current_phase, "pretest")
        finally:
            pg.quit()


if __name__ == "__main__":
    unittest.main()
