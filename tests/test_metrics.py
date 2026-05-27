"""Tests for rehab/analytics/metrics.py.

Each function gets hand-crafted input where the expected output can
be computed in your head, so a failure points straight at the
formula rather than at numerical precision wobble.
"""
from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class RtStatsTests(unittest.TestCase):

    def test_three_values_mean_std_cv(self) -> None:
        # 190, 200, 210 -> mean=200, sample var=100, std=10, cv=0.05.
        from rehab.analytics.metrics import rt_stats
        out = rt_stats([190.0, 200.0, 210.0])
        self.assertAlmostEqual(out["rt_mean"], 200.0)
        self.assertAlmostEqual(out["rt_std"], 10.0, places=6)
        self.assertAlmostEqual(out["rt_cv"], 0.05, places=6)

    def test_empty_returns_all_none(self) -> None:
        from rehab.analytics.metrics import rt_stats
        out = rt_stats([])
        self.assertIsNone(out["rt_mean"])
        self.assertIsNone(out["rt_std"])
        self.assertIsNone(out["rt_cv"])

    def test_single_value_no_stdev(self) -> None:
        # n=1: sample stdev needs n >= 2, so std + cv are None.
        from rehab.analytics.metrics import rt_stats
        out = rt_stats([200.0])
        self.assertEqual(out["rt_mean"], 200.0)
        self.assertIsNone(out["rt_std"])
        self.assertIsNone(out["rt_cv"])

    def test_zero_mean_cv_undefined(self) -> None:
        # CV divides by mean; mean=0 -> CV is None.
        from rehab.analytics.metrics import rt_stats
        out = rt_stats([0.0, 0.0, 0.0])
        self.assertEqual(out["rt_mean"], 0.0)
        self.assertEqual(out["rt_std"], 0.0)
        self.assertIsNone(out["rt_cv"])


class OutcomeRatesTests(unittest.TestCase):

    def test_two_hits_one_misclick_one_timeout(self) -> None:
        from rehab.analytics.metrics import outcome_rates
        r = outcome_rates(["hit", "hit", "misclick", "timeout"])
        self.assertAlmostEqual(r["hit_rate"], 0.5)
        self.assertAlmostEqual(r["misclick_rate"], 0.25)
        self.assertAlmostEqual(r["timeout_rate"], 0.25)

    def test_empty_zero_rates(self) -> None:
        from rehab.analytics.metrics import outcome_rates
        r = outcome_rates([])
        self.assertEqual(r["hit_rate"], 0.0)
        self.assertEqual(r["misclick_rate"], 0.0)
        self.assertEqual(r["timeout_rate"], 0.0)

    def test_custom_label_mapping(self) -> None:
        # Caller using the game's native labels can map them through
        # the label-set arguments without translating to canonical
        # strings first.
        from rehab.analytics.metrics import outcome_rates
        outs = ["Perfect", "Great", "Late", "Miss"]
        r = outcome_rates(
            outs,
            hit_labels=("Perfect", "Great", "Good", "Late"),
            misclick_labels=(),
            timeout_labels=("Miss",),
        )
        self.assertAlmostEqual(r["hit_rate"], 0.75)
        self.assertAlmostEqual(r["misclick_rate"], 0.0)
        self.assertAlmostEqual(r["timeout_rate"], 0.25)


class FatigueSlopeTests(unittest.TestCase):

    def test_linear_increase_returns_step(self) -> None:
        # 200, 210, 220, 230 -> +10 per block.
        from rehab.analytics.metrics import fatigue_slope
        self.assertAlmostEqual(fatigue_slope([200, 210, 220, 230]), 10.0)

    def test_flat_zero_slope(self) -> None:
        from rehab.analytics.metrics import fatigue_slope
        self.assertAlmostEqual(fatigue_slope([100.0, 100.0, 100.0]), 0.0)

    def test_decreasing_negative_slope(self) -> None:
        # Force fading: 30 -> 28 -> 26 -> 24 = -2 per block.
        from rehab.analytics.metrics import fatigue_slope
        self.assertAlmostEqual(fatigue_slope([30.0, 28.0, 26.0, 24.0]), -2.0)

    def test_below_two_blocks_none(self) -> None:
        from rehab.analytics.metrics import fatigue_slope
        self.assertIsNone(fatigue_slope([100.0]))
        self.assertIsNone(fatigue_slope([]))


class AsymmetryIndexTests(unittest.TestCase):

    def test_l8_r12_index_is_0_4(self) -> None:
        # |8 - 12| / mean(8, 12) = 4 / 10 = 0.4.
        from rehab.analytics.metrics import asymmetry_index
        self.assertAlmostEqual(asymmetry_index(8.0, 12.0), 0.4)

    def test_equal_hands_index_zero(self) -> None:
        from rehab.analytics.metrics import asymmetry_index
        self.assertAlmostEqual(asymmetry_index(10.0, 10.0), 0.0)

    def test_both_zero_returns_none(self) -> None:
        # Mean denominator is zero so the index is undefined.
        from rehab.analytics.metrics import asymmetry_index
        self.assertIsNone(asymmetry_index(0.0, 0.0))

    def test_missing_side_returns_none(self) -> None:
        from rehab.analytics.metrics import asymmetry_index
        self.assertIsNone(asymmetry_index(None, 10.0))
        self.assertIsNone(asymmetry_index(10.0, None))


class BeatOffsetStatsTests(unittest.TestCase):

    def test_perfectly_on_beat_zero_offsets(self) -> None:
        from rehab.analytics.metrics import beat_offset_stats
        s = beat_offset_stats([1.0, 2.0, 3.0], [1.0, 2.0, 3.0])
        self.assertAlmostEqual(s["beat_offset_mean_ms"], 0.0)
        self.assertAlmostEqual(s["beat_offset_abs_mean_ms"], 0.0)
        self.assertAlmostEqual(s["beat_offset_std_ms"], 0.0, places=6)

    def test_consistently_50ms_late(self) -> None:
        from rehab.analytics.metrics import beat_offset_stats
        s = beat_offset_stats([1.05, 2.05, 3.05], [1.0, 2.0, 3.0])
        self.assertAlmostEqual(s["beat_offset_mean_ms"], 50.0, places=6)
        self.assertAlmostEqual(s["beat_offset_abs_mean_ms"], 50.0, places=6)
        # All identical -> sample stdev is 0.
        self.assertAlmostEqual(s["beat_offset_std_ms"], 0.0, places=6)

    def test_mixed_early_late_mean_zero_abs_mean_nonzero(self) -> None:
        # 50ms early then 50ms late -> mean cancels to 0, abs mean = 50.
        from rehab.analytics.metrics import beat_offset_stats
        s = beat_offset_stats([0.95, 2.05], [1.0, 2.0])
        self.assertAlmostEqual(s["beat_offset_mean_ms"], 0.0, places=6)
        self.assertAlmostEqual(s["beat_offset_abs_mean_ms"], 50.0, places=6)

    def test_picks_nearest_beat_not_just_next(self) -> None:
        # Press at 1.95 is closer to beat 2.0 than beat 1.0.
        from rehab.analytics.metrics import beat_offset_stats
        s = beat_offset_stats([1.95], [1.0, 2.0])
        self.assertAlmostEqual(s["beat_offset_mean_ms"], -50.0, places=6)

    def test_empty_inputs_return_none(self) -> None:
        from rehab.analytics.metrics import beat_offset_stats
        s = beat_offset_stats([], [1.0, 2.0])
        self.assertIsNone(s["beat_offset_mean_ms"])
        s = beat_offset_stats([1.0], [])
        self.assertIsNone(s["beat_offset_mean_ms"])


class DriftSlopeTests(unittest.TestCase):

    def test_5_units_per_minute_drift(self) -> None:
        # Baseline rises by 5 every minute -> slope = 5.
        from rehab.analytics.metrics import drift_slope
        s = drift_slope([0.0, 1.0, 2.0, 3.0], [100.0, 105.0, 110.0, 115.0])
        self.assertAlmostEqual(s, 5.0, places=6)

    def test_no_drift_zero_slope(self) -> None:
        from rehab.analytics.metrics import drift_slope
        s = drift_slope([0.0, 1.0, 2.0], [100.0, 100.0, 100.0])
        self.assertAlmostEqual(s, 0.0, places=6)

    def test_below_two_samples_none(self) -> None:
        from rehab.analytics.metrics import drift_slope
        self.assertIsNone(drift_slope([0.0], [100.0]))
        self.assertIsNone(drift_slope([], []))

    def test_mismatched_lengths_none(self) -> None:
        from rehab.analytics.metrics import drift_slope
        self.assertIsNone(drift_slope([0.0, 1.0], [100.0]))


class InterHandCorrelationTests(unittest.TestCase):

    def test_identical_series_r_is_one(self) -> None:
        from rehab.analytics.metrics import inter_hand_correlation
        L = [1.0, 2.0, 3.0, 4.0, 5.0]
        R = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertAlmostEqual(inter_hand_correlation(L, R), 1.0, places=6)

    def test_perfectly_opposite_series_r_is_neg_one(self) -> None:
        from rehab.analytics.metrics import inter_hand_correlation
        L = [1.0, 2.0, 3.0, 4.0, 5.0]
        R = [5.0, 4.0, 3.0, 2.0, 1.0]
        self.assertAlmostEqual(inter_hand_correlation(L, R), -1.0, places=6)

    def test_constant_series_returns_none(self) -> None:
        # Pearson undefined when one side has zero variance.
        from rehab.analytics.metrics import inter_hand_correlation
        self.assertIsNone(inter_hand_correlation(
            [1.0, 1.0, 1.0], [1.0, 2.0, 3.0]))

    def test_mismatched_lengths_none(self) -> None:
        from rehab.analytics.metrics import inter_hand_correlation
        self.assertIsNone(inter_hand_correlation([1.0, 2.0], [1.0]))


class TapVariabilityCvTests(unittest.TestCase):

    def test_even_rhythm_cv_is_zero(self) -> None:
        # Taps every 0.5s -> ITIs all 0.5 -> stdev = 0 -> CV = 0.
        from rehab.analytics.metrics import tap_variability_cv
        taps = [0.0, 0.5, 1.0, 1.5, 2.0, 2.5]
        self.assertAlmostEqual(tap_variability_cv(taps), 0.0, places=6)

    def test_irregular_rhythm_positive_cv(self) -> None:
        # ITIs 0.5, 0.6, 0.4, 0.5: mean 0.5, var = 0.0067/3 sample-style.
        from rehab.analytics.metrics import tap_variability_cv
        taps = [0.0, 0.5, 1.1, 1.5, 2.0]
        cv = tap_variability_cv(taps)
        self.assertGreater(cv, 0.0)
        self.assertLess(cv, 1.0)

    def test_fewer_than_three_taps_returns_none(self) -> None:
        # Need at least three taps so there are two intervals to
        # compute a sample stdev on.
        from rehab.analytics.metrics import tap_variability_cv
        self.assertIsNone(tap_variability_cv([]))
        self.assertIsNone(tap_variability_cv([0.5]))
        self.assertIsNone(tap_variability_cv([0.5, 1.0]))

    def test_zero_or_negative_mean_iti_returns_none(self) -> None:
        # Taps at the same moment -> zero mean ITI -> CV undefined.
        from rehab.analytics.metrics import tap_variability_cv
        self.assertIsNone(tap_variability_cv([1.0, 1.0, 1.0]))


class TempoEntrainmentIndexTests(unittest.TestCase):

    def test_perfect_correlation_returns_one(self) -> None:
        from rehab.analytics.metrics import tempo_entrainment_index
        # RT and beat offset rise together -> r = 1.
        rts = [100.0, 200.0, 300.0, 400.0]
        offsets = [10.0, 20.0, 30.0, 40.0]
        r = tempo_entrainment_index(rts, offsets)
        self.assertAlmostEqual(r, 1.0, places=6)

    def test_anti_correlation_returns_neg_one(self) -> None:
        from rehab.analytics.metrics import tempo_entrainment_index
        rts = [100.0, 200.0, 300.0, 400.0]
        offsets = [40.0, 30.0, 20.0, 10.0]
        r = tempo_entrainment_index(rts, offsets)
        self.assertAlmostEqual(r, -1.0, places=6)

    def test_constant_rts_returns_none(self) -> None:
        # Zero variance on one side -> Pearson undefined.
        from rehab.analytics.metrics import tempo_entrainment_index
        rts = [200.0, 200.0, 200.0]
        offsets = [10.0, 20.0, 30.0]
        self.assertIsNone(tempo_entrainment_index(rts, offsets))

    def test_mismatched_lengths_none(self) -> None:
        from rehab.analytics.metrics import tempo_entrainment_index
        self.assertIsNone(tempo_entrainment_index([1.0, 2.0], [1.0]))


class ForceIndividuationIndexTests(unittest.TestCase):

    def test_isolated_target_returns_one(self) -> None:
        # Target rises, neighbours stay flat -> no co-activation,
        # mean |r| = 0 (flat neighbours get 0 by the docstring),
        # individuation index = 1.
        from rehab.analytics.metrics import force_individuation_index
        target = [0.0, 1.0, 2.0, 3.0, 4.0]
        neighbours = [[0.0] * 5, [0.0] * 5, [0.0] * 5]
        idx = force_individuation_index(target, neighbours)
        self.assertAlmostEqual(idx, 1.0, places=6)

    def test_full_co_activation_returns_zero(self) -> None:
        # All sensors rise together -> r = 1 with each neighbour,
        # individuation = 0.
        from rehab.analytics.metrics import force_individuation_index
        target = [0.0, 1.0, 2.0, 3.0, 4.0]
        neighbours = [list(target), list(target), list(target)]
        idx = force_individuation_index(target, neighbours)
        self.assertAlmostEqual(idx, 0.0, places=6)

    def test_partial_co_activation_in_between(self) -> None:
        from rehab.analytics.metrics import force_individuation_index
        target = [0.0, 1.0, 2.0, 3.0, 4.0]
        # One neighbour fully matches, one is flat.
        neighbours = [list(target), [0.0] * 5]
        idx = force_individuation_index(target, neighbours)
        # mean |r| = (1.0 + 0.0) / 2 = 0.5 -> index = 0.5.
        self.assertAlmostEqual(idx, 0.5, places=6)

    def test_flat_target_returns_none(self) -> None:
        # Target itself has zero variance -> no signal to measure
        # individuation against.
        from rehab.analytics.metrics import force_individuation_index
        self.assertIsNone(force_individuation_index(
            [0.0] * 5, [[1.0, 2.0, 3.0, 4.0, 5.0]]))

    def test_empty_neighbours_returns_none(self) -> None:
        from rehab.analytics.metrics import force_individuation_index
        self.assertIsNone(force_individuation_index(
            [0.0, 1.0, 2.0], []))


if __name__ == "__main__":
    unittest.main()
