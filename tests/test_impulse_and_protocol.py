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

    def test_flat_hold_with_falling_edge_drop(self) -> None:
        # 500 held for 0.4 s (t=0.1 to t=0.5), then a final sample at
        # t=0.6 with sm=0 closes the press. True trapezoidal integral
        # of this profile is:
        #   t=0.1 to t=0.5: 500 * 0.4 = 200
        #   t=0.5 to t=0.6: half-trapezoid (500+0)/2 * 0.1 = 25
        # Total = 225. A rectangular (right-Riemann) sum gives 200
        # because the falling sample contributes 0 * dt = 0, and a
        # left-Riemann sum gives 250 because it would credit the
        # whole interval at 500. Pinning 225 locks trapezoidal in.
        from rehab.hardware.fsr_detector import (
            Calibration, FSRDetector, ReleaseEvent,
        )
        cal = Calibration(
            num_sensors=1, value_alpha=1.0,
            on_delta=[100], off_delta=[80],
            abs_on_min=[300], abs_off_max=[300],
            baseline_alpha=0.0,   # freeze baseline so it stays at 0
            debounce_ms=0,
        )
        det = FSRDetector(cal, hand="right")
        releases: list[ReleaseEvent] = []
        det.on_release = releases.append
        # Warm-up at 0 so the baseline locks at 0.
        det.feed(0.0, (0,))
        det.feed(0.1, (500,))    # rising edge
        det.feed(0.2, (500,))    # hold
        det.feed(0.3, (500,))    # hold
        det.feed(0.4, (500,))    # hold
        det.feed(0.5, (500,))    # last in-press sample
        det.feed(0.6, (0,))      # falling edge
        self.assertEqual(len(releases), 1)
        self.assertAlmostEqual(releases[0].impulse_raw, 225.0, places=1)
        # Baseline is 0 so impulse_minus_baseline equals impulse_raw
        # for this test.
        self.assertAlmostEqual(
            releases[0].impulse_minus_baseline, 225.0, places=1)

    def test_ramp_press_yields_triangle_area(self) -> None:
        # Linear ramp from 0 (baseline) up to 500 over 5 samples then
        # straight back down to 0. The true integral of a triangle
        # with base 1.0 s and height 500 is 250. Rectangular (right-
        # Riemann) would give ~275, trapezoidal gives 250 exactly.
        from rehab.hardware.fsr_detector import (
            Calibration, FSRDetector, ReleaseEvent,
        )
        cal = Calibration(
            num_sensors=1, value_alpha=1.0,
            on_delta=[100], off_delta=[80],
            abs_on_min=[150], abs_off_max=[150],
            baseline_alpha=0.0,
            debounce_ms=0,
        )
        det = FSRDetector(cal, hand="right")
        releases: list[ReleaseEvent] = []
        det.on_release = releases.append
        # Warm-up at 0.
        det.feed(0.0, (0,))
        # Ramp 200 -> 300 -> 400 -> 500 -> 400 -> 300 -> 200 -> 0
        # over 0.1 s steps. Rising edge fires when sm exceeds the on
        # threshold (~150), which happens at the first 200 sample.
        det.feed(0.1, (200,))   # rising
        det.feed(0.2, (300,))
        det.feed(0.3, (400,))
        det.feed(0.4, (500,))
        det.feed(0.5, (400,))
        det.feed(0.6, (300,))
        det.feed(0.7, (200,))
        det.feed(0.8, (0,))     # falling
        self.assertEqual(len(releases), 1)
        # Trapezoidal integration of the points above with dt=0.1:
        # (200+300)/2*0.1 + (300+400)/2*0.1 + (400+500)/2*0.1
        #   + (500+400)/2*0.1 + (400+300)/2*0.1 + (300+200)/2*0.1
        #   + (200+0)/2*0.1
        # = 25 + 35 + 45 + 45 + 35 + 25 + 10 = 220.
        # Rectangular (current bug) would have given:
        # 300*0.1 + 400*0.1 + 500*0.1 + 400*0.1 + 300*0.1
        #   + 200*0.1 + 0*0.1 = 210
        # We assert near 220 to lock the trapezoidal contract in.
        self.assertAlmostEqual(releases[0].impulse_raw, 220.0, places=1)

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
