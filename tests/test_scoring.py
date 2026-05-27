"""Tests for the RT-based scoring used by classic and adaptive modes.
classify_offset (rhythm scoring) has its own coverage in test_rhythm.py;
this file pins the simpler classify() boundaries."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ScoreConfigDefaultsTests(unittest.TestCase):
    """Score values are part of the data schema. The defaults must not
    drift silently or historical sessions would become incomparable."""

    def test_default_thresholds_and_points(self) -> None:
        from rehab.game.scoring import ScoreConfig
        cfg = ScoreConfig()
        self.assertEqual(cfg.great_ms, 200)
        self.assertEqual(cfg.good_ms, 500)
        self.assertEqual(cfg.great_points, 3)
        self.assertEqual(cfg.good_points, 2)
        self.assertEqual(cfg.late_points, 1)
        # Misses + early presses must default to zero - the score never
        # goes backwards. Therapists can override either if needed.
        self.assertEqual(cfg.miss_points, 0)
        self.assertEqual(cfg.early_penalty, 0)


class ClassifyMissTests(unittest.TestCase):

    def test_none_rt_is_miss_with_zero_points(self) -> None:
        from rehab.game.scoring import ScoreConfig, classify
        result = classify(None, ScoreConfig())
        self.assertEqual(result.label, "Miss")
        self.assertEqual(result.points, 0)
        self.assertIsNone(result.rt_ms)

    def test_miss_respects_cfg_override(self) -> None:
        # A therapist could plausibly want a negative-mood reward on
        # misses. The config should be honoured even though defaults
        # never go below zero.
        from rehab.game.scoring import ScoreConfig, classify
        cfg = ScoreConfig(miss_points=-2)
        self.assertEqual(classify(None, cfg).points, -2)


class ClassifyGreatBoundaryTests(unittest.TestCase):

    def test_rt_zero_is_great(self) -> None:
        from rehab.game.scoring import ScoreConfig, classify
        self.assertEqual(classify(0, ScoreConfig()).label, "Great")

    def test_rt_at_great_threshold_inclusive(self) -> None:
        # 200ms is "Great", not "Good". Threshold is inclusive.
        from rehab.game.scoring import ScoreConfig, classify
        r = classify(200, ScoreConfig())
        self.assertEqual(r.label, "Great")
        self.assertEqual(r.points, 3)

    def test_rt_just_over_great_is_good(self) -> None:
        from rehab.game.scoring import ScoreConfig, classify
        r = classify(200.001, ScoreConfig())
        self.assertEqual(r.label, "Good")
        self.assertEqual(r.points, 2)


class ClassifyGoodBoundaryTests(unittest.TestCase):

    def test_rt_at_good_threshold_inclusive(self) -> None:
        from rehab.game.scoring import ScoreConfig, classify
        r = classify(500, ScoreConfig())
        self.assertEqual(r.label, "Good")
        self.assertEqual(r.points, 2)

    def test_rt_just_over_good_is_late(self) -> None:
        from rehab.game.scoring import ScoreConfig, classify
        r = classify(500.001, ScoreConfig())
        self.assertEqual(r.label, "Late")
        self.assertEqual(r.points, 1)


class ClassifyLateTests(unittest.TestCase):

    def test_very_slow_rt_is_late(self) -> None:
        # No upper bound on Late - even multi-second reactions still
        # earn the 1-point participation reward.
        from rehab.game.scoring import ScoreConfig, classify
        r = classify(99999, ScoreConfig())
        self.assertEqual(r.label, "Late")
        self.assertEqual(r.points, 1)


class ClassifyCustomConfigTests(unittest.TestCase):

    def test_custom_thresholds_shift_boundaries(self) -> None:
        from rehab.game.scoring import ScoreConfig, classify
        cfg = ScoreConfig(great_ms=100, good_ms=300,
                           great_points=10, good_points=5, late_points=2)
        self.assertEqual(classify(100, cfg).label, "Great")
        self.assertEqual(classify(101, cfg).label, "Good")
        self.assertEqual(classify(300, cfg).label, "Good")
        self.assertEqual(classify(301, cfg).label, "Late")
        # Custom point values propagate.
        self.assertEqual(classify(50, cfg).points, 10)
        self.assertEqual(classify(200, cfg).points, 5)
        self.assertEqual(classify(1000, cfg).points, 2)


class EarlyPenaltyTests(unittest.TestCase):

    def test_early_penalty_label_and_default_zero_points(self) -> None:
        from rehab.game.scoring import ScoreConfig, early_penalty
        r = early_penalty(ScoreConfig())
        self.assertEqual(r.label, "Early")
        # Default early_penalty is 0 so an early press doesn't drag the
        # session score below where it started.
        self.assertEqual(r.points, 0)
        self.assertIsNone(r.rt_ms)

    def test_early_penalty_respects_cfg(self) -> None:
        from rehab.game.scoring import ScoreConfig, early_penalty
        cfg = ScoreConfig(early_penalty=-1)
        self.assertEqual(early_penalty(cfg).points, -1)


class TrialResultImmutabilityTests(unittest.TestCase):
    """TrialResult is a frozen dataclass - downstream loggers rely on
    being able to share it between threads without defensive copies."""

    def test_trial_result_is_frozen(self) -> None:
        from rehab.game.scoring import TrialResult
        r = TrialResult(label="Great", points=3, rt_ms=150.0)
        with self.assertRaises(Exception):
            r.points = 999  # type: ignore[misc]


if __name__ == "__main__":
    unittest.main()
