"""Phase 4 tests: the trial CSV gains a `peak_force_n` column and the
session.json block_summary gains the full research aggregate set
(per-lane rt stats, outcome rates, peak-force means, fatigue slopes,
beat-offset stats, bilateral asymmetry, drift, startup latency).

The summary is constructed in GameEngine._build_block_summary +
_populate_research_summary. These tests drive a __new__-built engine
with hand-crafted per-lane state and assert the returned summary has
the expected shape and values.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TrialCsvPeakForceColumnTests(unittest.TestCase):

    def test_force_columns_appear_in_tail(self) -> None:
        # The 2025 schema must remain a strict prefix; force-related
        # columns were appended at the tail so existing CSV parsers
        # that consume the older columns still work. peak_force_n
        # came first, then impulse_n, then the phase tag for the
        # protocol pretest/main/aftertest scaffolding.
        from rehab.data.logger import TRIAL_COLUMNS
        self.assertIn("peak_force_n", TRIAL_COLUMNS)
        self.assertIn("impulse_n", TRIAL_COLUMNS)
        self.assertIn("phase", TRIAL_COLUMNS)
        # peak_force_n must come before impulse_n, impulse_n before
        # phase. Keeps the additive-only contract intact.
        self.assertLess(
            TRIAL_COLUMNS.index("peak_force_n"),
            TRIAL_COLUMNS.index("impulse_n"),
        )
        self.assertLess(
            TRIAL_COLUMNS.index("impulse_n"),
            TRIAL_COLUMNS.index("phase"),
        )

    def test_age_still_after_participant(self) -> None:
        # Regression: the age column was added in a prior phase. The
        # peak_force_n append must not have moved age.
        from rehab.data.logger import TRIAL_COLUMNS
        self.assertEqual(
            TRIAL_COLUMNS.index("age"),
            TRIAL_COLUMNS.index("participant") + 1,
        )


def _bare_engine_for_summary():
    """Build a GameEngine with just enough state for
    _build_block_summary + _populate_research_summary to run. The
    summary builder reads many engine attrs that the production
    __init__ sets up; we mirror the bits it touches here."""
    import time
    from rehab.game.engine import GameEngine
    eng = GameEngine.__new__(GameEngine)
    eng.cfg = MagicMock()
    eng.cfg.get = MagicMock(side_effect=lambda k, d=None:
                              4 if k == "fsr.num_sensors_per_hand"
                              else d)
    eng.current_block = "classic"
    eng.hand_mode = "right"
    eng.score = 0
    eng.hits = 0
    eng.misses = 0
    eng._block_t0 = time.perf_counter() - 12.0
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
    eng._across_blocks_mean_rt = []
    eng._across_blocks_mean_peak = []
    eng._drift_samples = {}
    eng._rhythm_press_times_s = []
    eng._rhythm_beat_times_s = []
    eng.mode = None
    eng.source = MagicMock()
    eng.source.get_startup_latency = MagicMock(return_value={"COM3": 42.5})
    return eng


class BlockSummaryPerLaneTests(unittest.TestCase):

    def test_per_lane_block_has_rt_stats_and_rates(self) -> None:
        eng = _bare_engine_for_summary()
        # Lane 0: three hits at 100, 200, 300 ms (mean 200, std 100).
        eng._per_lane_rts = {0: [100.0, 200.0, 300.0]}
        # Lane 0: one timeout, one wrong-press event.
        eng._per_lane_misses = {0: 1}
        eng._per_lane_wrong = {0: 1}
        eng._per_lane_peak_force = {0: [12.0, 14.0]}
        eng.hits = 3
        eng.misses = 1
        eng._block_rt_sum = 600.0
        eng._block_rt_count = 3
        s = eng._build_block_summary("completed")
        self.assertIn("per_lane", s)
        lane0 = s["per_lane"]["0"]
        self.assertAlmostEqual(lane0["rt_mean_ms"], 200.0)
        self.assertAlmostEqual(lane0["rt_std_ms"], 100.0)
        self.assertAlmostEqual(lane0["rt_cv"], 0.5, places=4)
        # n_total = 3 hits + 1 timeout = 4 trials; hit_rate = 0.75.
        self.assertEqual(lane0["n_trials"], 4)
        self.assertAlmostEqual(lane0["hit_rate"], 0.75)
        self.assertAlmostEqual(lane0["timeout_rate"], 0.25)
        # Misclicks are normalised the same way.
        self.assertAlmostEqual(lane0["misclick_rate"], 0.25)
        self.assertAlmostEqual(lane0["peak_force_mean"], 13.0)


class BlockSummaryFatigueSlopeTests(unittest.TestCase):

    def test_fatigue_slope_rt_appears_after_two_blocks(self) -> None:
        eng = _bare_engine_for_summary()
        eng._across_blocks_mean_rt = [200.0]   # one prior block
        eng._block_rt_sum = 250.0
        eng._block_rt_count = 1                 # current block mean = 250
        s = eng._build_block_summary("completed")
        # Two blocks: 200 then 250 -> slope +50 ms/block.
        self.assertAlmostEqual(
            s["fatigue_slope_rt_ms_per_block"], 50.0, places=6)

    def test_fatigue_slope_returns_none_on_first_block(self) -> None:
        eng = _bare_engine_for_summary()
        eng._across_blocks_mean_rt = []
        eng._block_rt_sum = 200.0
        eng._block_rt_count = 1
        s = eng._build_block_summary("completed")
        # Only one block of data -> slope undefined.
        self.assertIsNone(s["fatigue_slope_rt_ms_per_block"])


class BlockSummaryBeatOffsetTests(unittest.TestCase):

    def test_beat_offset_present_only_in_rhythm_block(self) -> None:
        eng = _bare_engine_for_summary()
        eng.current_block = "classic"
        eng._rhythm_press_times_s = [1.05, 2.05]
        eng._rhythm_beat_times_s = [1.0, 2.0]
        s = eng._build_block_summary("completed")
        self.assertNotIn("beat_offset_stats", s)
        eng.current_block = "rhythm"
        s = eng._build_block_summary("completed")
        self.assertIn("beat_offset_stats", s)
        # 50 ms late on both presses.
        self.assertAlmostEqual(
            s["beat_offset_stats"]["beat_offset_mean_ms"], 50.0, places=2)


class BlockSummaryBilateralAsymmetryTests(unittest.TestCase):

    def test_asymmetry_only_in_bilateral_mode(self) -> None:
        eng = _bare_engine_for_summary()
        eng.hand_mode = "right"   # unilateral
        s = eng._build_block_summary("completed")
        self.assertNotIn("asymmetry_index", s)
        eng.hand_mode = "both"
        # Lanes 0..3 right, 4..7 left.
        eng._per_lane_peak_force = {
            0: [10.0, 10.0],   # right
            5: [20.0, 20.0],   # left
        }
        s = eng._build_block_summary("completed")
        self.assertIn("asymmetry_index", s)
        # |L - R| / mean = |20 - 10| / 15 = 0.6667.
        self.assertAlmostEqual(
            s["asymmetry_index"]["peak_force"], 0.6667, places=3)
        # Inter-hand correlation is a placeholder until force-stream
        # resampling lands. Field exists but is None.
        self.assertIn("inter_hand_correlation", s)
        self.assertIsNone(s["inter_hand_correlation"])


class BlockSummaryDriftTests(unittest.TestCase):

    def test_drift_slope_per_sensor(self) -> None:
        eng = _bare_engine_for_summary()
        # Baseline rising 4 units/min on right sensor 1.
        eng._drift_samples = {
            ("right", 1): [(0.0, 100.0), (1.0, 104.0), (2.0, 108.0)],
        }
        s = eng._build_block_summary("completed")
        self.assertIn("drift_units_per_min", s)
        self.assertAlmostEqual(
            s["drift_units_per_min"]["right_1"], 4.0, places=4)


class BlockSummaryStartupLatencyTests(unittest.TestCase):

    def test_startup_latency_from_source(self) -> None:
        eng = _bare_engine_for_summary()
        eng.source.get_startup_latency = MagicMock(
            return_value={"COM3": 42.5, "COM4": 38.0})
        s = eng._build_block_summary("completed")
        self.assertEqual(s["startup_latency_ms"]["COM3"], 42.5)
        self.assertEqual(s["startup_latency_ms"]["COM4"], 38.0)

    def test_summary_survives_when_source_has_no_latency_method(self) -> None:
        eng = _bare_engine_for_summary()
        # KeyboardOnlySource doesn't have get_startup_latency.
        eng.source = MagicMock(spec=["is_connected"])
        s = eng._build_block_summary("completed")
        # No exception; key just absent or None.
        self.assertIsInstance(s, dict)


class ForceUnitTests(unittest.TestCase):

    def test_force_unit_counts_when_no_calibration(self) -> None:
        eng = _bare_engine_for_summary()
        # cfg.get returns None for force_calibration_n_per_count.
        s = eng._build_block_summary("completed")
        self.assertEqual(s["force_unit"], "counts")

    def test_force_unit_newtons_when_calibration_set(self) -> None:
        eng = _bare_engine_for_summary()
        def _get(k, d=None):
            if k == "fsr.num_sensors_per_hand":
                return 4
            if k == "fsr.force_calibration_n_per_count":
                return 0.025
            return d
        eng.cfg.get = MagicMock(side_effect=_get)
        s = eng._build_block_summary("completed")
        self.assertEqual(s["force_unit"], "N")


if __name__ == "__main__":
    unittest.main()
