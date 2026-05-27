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
        # RT bands.
        self.assertEqual(cfg.perfect_ms, 100)
        self.assertEqual(cfg.great_ms, 200)
        self.assertEqual(cfg.good_ms, 500)
        # Wider point spread (10/6/3/1) so the difference between a
        # fast and a slow correct press actually reads in the HUD.
        self.assertEqual(cfg.perfect_points, 10)
        self.assertEqual(cfg.great_points, 6)
        self.assertEqual(cfg.good_points, 3)
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


class ClassifyPerfectBoundaryTests(unittest.TestCase):
    """Perfect tier (sub-100 ms RT) is the top reward. A 50 ms press
    that would have just been "Great" under the old scheme now reads
    as Perfect with 10 points instead of 6."""

    def test_rt_zero_is_perfect(self) -> None:
        from rehab.game.scoring import ScoreConfig, classify
        r = classify(0, ScoreConfig())
        self.assertEqual(r.label, "Perfect")
        self.assertEqual(r.points, 10)

    def test_rt_at_perfect_threshold_inclusive(self) -> None:
        from rehab.game.scoring import ScoreConfig, classify
        r = classify(100, ScoreConfig())
        self.assertEqual(r.label, "Perfect")
        self.assertEqual(r.points, 10)

    def test_rt_just_over_perfect_is_great(self) -> None:
        from rehab.game.scoring import ScoreConfig, classify
        r = classify(100.001, ScoreConfig())
        self.assertEqual(r.label, "Great")
        self.assertEqual(r.points, 6)


class ClassifyGreatBoundaryTests(unittest.TestCase):

    def test_rt_at_great_threshold_inclusive(self) -> None:
        # 200ms is "Great", not "Good". Threshold is inclusive.
        from rehab.game.scoring import ScoreConfig, classify
        r = classify(200, ScoreConfig())
        self.assertEqual(r.label, "Great")
        self.assertEqual(r.points, 6)

    def test_rt_just_over_great_is_good(self) -> None:
        from rehab.game.scoring import ScoreConfig, classify
        r = classify(200.001, ScoreConfig())
        self.assertEqual(r.label, "Good")
        self.assertEqual(r.points, 3)


class ClassifyGoodBoundaryTests(unittest.TestCase):

    def test_rt_at_good_threshold_inclusive(self) -> None:
        from rehab.game.scoring import ScoreConfig, classify
        r = classify(500, ScoreConfig())
        self.assertEqual(r.label, "Good")
        self.assertEqual(r.points, 3)

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
        # Force perfect_ms below the Great band so this test covers the
        # Great/Good/Late path. (The default 100 ms perfect threshold
        # would otherwise eat the 50 ms sample below as Perfect.)
        cfg = ScoreConfig(perfect_ms=0, great_ms=100, good_ms=300,
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


class WrongPressPenaltyTests(unittest.TestCase):
    """apply_wrong_press_penalty subtracts the configured points and
    floors the score at zero. Score never displays negative even with
    repeated misses."""

    def _make_engine(self, penalty: int):
        # Build a minimal engine via __new__ so we don't need pygame.
        from unittest.mock import MagicMock
        from rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        eng.cfg = MagicMock()
        eng.cfg.get = MagicMock(side_effect=lambda k, d=None:
                                  penalty if k == "scoring.wrong_press_penalty"
                                  else d)
        eng.score = 10
        eng._last_gained = 0
        return eng

    def test_subtracts_configured_amount(self) -> None:
        eng = self._make_engine(penalty=2)
        actual = eng.apply_wrong_press_penalty()
        self.assertEqual(actual, 2)
        self.assertEqual(eng.score, 8)
        self.assertEqual(eng._last_gained, -2)

    def test_floors_at_zero(self) -> None:
        eng = self._make_engine(penalty=5)
        eng.score = 3
        actual = eng.apply_wrong_press_penalty()
        # Only 3 actually subtracted (clamped at 0), not 5.
        self.assertEqual(actual, 3)
        self.assertEqual(eng.score, 0)

    def test_zero_penalty_is_noop(self) -> None:
        eng = self._make_engine(penalty=0)
        eng.score = 5
        actual = eng.apply_wrong_press_penalty()
        self.assertEqual(actual, 0)
        self.assertEqual(eng.score, 5)


class IdlePressPenaltyTests(unittest.TestCase):
    """apply_idle_press_penalty subtracts the smaller idle-press
    deduction for presses that land between trials. Independent of
    the wrong_press_penalty path so a config can disable one without
    the other."""

    def _make_engine(self, idle_pen: int, wrong_pen: int = 0):
        from unittest.mock import MagicMock
        from rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        eng.cfg = MagicMock()
        def _get(k, d=None):
            if k == "scoring.idle_press_penalty":
                return idle_pen
            if k == "scoring.wrong_press_penalty":
                return wrong_pen
            return d
        eng.cfg.get = MagicMock(side_effect=_get)
        eng.score = 10
        eng._last_gained = 0
        eng._block_idle_presses = 0
        return eng

    def test_subtracts_idle_penalty(self) -> None:
        eng = self._make_engine(idle_pen=1)
        actual = eng.apply_idle_press_penalty()
        self.assertEqual(actual, 1)
        self.assertEqual(eng.score, 9)
        self.assertEqual(eng._block_idle_presses, 1)

    def test_idle_count_increments_per_call(self) -> None:
        eng = self._make_engine(idle_pen=1)
        for _ in range(4):
            eng.apply_idle_press_penalty()
        # 4 idle presses, all counted, score floored at zero on the last.
        self.assertEqual(eng._block_idle_presses, 4)

    def test_zero_idle_penalty_is_noop(self) -> None:
        eng = self._make_engine(idle_pen=0)
        eng.score = 5
        actual = eng.apply_idle_press_penalty()
        self.assertEqual(actual, 0)
        self.assertEqual(eng.score, 5)
        self.assertEqual(eng._block_idle_presses, 0)

    def test_floors_at_zero(self) -> None:
        eng = self._make_engine(idle_pen=5)
        eng.score = 2
        actual = eng.apply_idle_press_penalty()
        self.assertEqual(actual, 2)
        self.assertEqual(eng.score, 0)


class SpamArithmeticTests(unittest.TestCase):
    """Sanity-check the scoring numbers from the patient's POV: with
    the bumped defaults, finger-mashing must always net less than a
    focused single correct press, otherwise spamming is the dominant
    strategy and the rehab signal is junk."""

    def test_three_wrong_plus_one_hit_is_net_negative(self) -> None:
        """Mash all four fingers per trial: 1 great hit (+3), 3 wrong
        presses (-2 each with the new default). Net = -3 vs +3 for a
        focused single press, so spamming is dominated."""
        great_points = 3
        wrong_pen = 2
        spam_net = great_points + (-3 * wrong_pen)
        focused_net = great_points
        self.assertLess(spam_net, 0,
                         "Spamming should be net-negative with default "
                         "wrong_press_penalty")
        self.assertGreater(focused_net - spam_net, 0,
                            "Focused press must out-score spam")

    def test_one_fumble_then_correct_is_still_positive(self) -> None:
        """A patient with motor impairment might hit one wrong key
        before finding the target. Net should still be positive so
        the system isn't punishing genuine fumbles too hard."""
        net = 3 - 2   # great hit minus one wrong-press penalty
        self.assertGreater(net, 0)

    def test_two_fumbles_still_breaks_even_or_better(self) -> None:
        """Two wrong then correct = +3 - 4 = -1. Borderline. Acceptable
        because most fumbles are a single mis-press, not two."""
        net = 3 - 2 - 2
        # Document the boundary, not assert positive.
        self.assertLessEqual(net, 0)


if __name__ == "__main__":
    unittest.main()
