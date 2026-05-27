"""Tests for the adaptive difficulty engine (Thread 1)."""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class AdaptiveEngineTests(unittest.TestCase):
    def test_construction_requires_positive_num_lanes(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        with self.assertRaises(ValueError):
            AdaptiveEngine(num_lanes=0)
        with self.assertRaises(ValueError):
            AdaptiveEngine(num_lanes=-1)

    def test_weak_lanes_get_higher_weight(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        for _ in range(20):
            eng.record(0, hit=False, rt_ms=None)
            eng.record(3, hit=True, rt_ms=300.0)
        w = eng.lane_weights()
        self.assertGreater(w[0], w[3])

    def test_bpm_speeds_up_when_hits_are_easy(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        eng.bpm = 80.0
        for _ in range(20):
            for lane in range(4):
                eng.record(lane, hit=True, rt_ms=250.0)
        self.assertGreater(eng.next_bpm(), 80.0)

    def test_bpm_slows_down_when_misses_pile_up(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        eng.bpm = 80.0
        for _ in range(20):
            for lane in range(4):
                eng.record(lane, hit=False, rt_ms=None)
        self.assertLess(eng.next_bpm(), 80.0)

    def test_sequence_avoids_immediate_repeats_when_possible(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        rng = random.Random(42)
        seq = eng.generate_sequence(50, rng=rng, avoid_repeats=True)
        repeats = sum(1 for i in range(1, len(seq)) if seq[i] == seq[i - 1])
        # With weights roughly even and 4 lanes, repeats should be rare.
        self.assertLess(repeats, 5)

    def test_warm_start_from_csv_like_history(self) -> None:
        from rehab.analytics.adaptive import warm_start_from_history
        history = [
            {"lane": 0, "hit": "True", "rt_ms": "300"},
            {"lane": 1, "hit": "False", "rt_ms": ""},
            {"lane": "bad", "hit": True, "rt_ms": None},   # skipped
            {"hit": True, "rt_ms": 200},                    # skipped (no lane)
            {"lane": 2, "hit": True, "rt_ms": "250"},
        ]
        eng = warm_start_from_history(history)
        self.assertEqual(sum(s.n_trials for s in eng.state), 3)


class QualityWeightedAdaptiveTests(unittest.TestCase):
    """The adapter should react to press QUALITY, not just hit/miss. A
    session of all Lates is technically 100% hits but the patient is
    clearly struggling, so the pace should drop."""

    def test_all_lates_slow_the_pace_down(self) -> None:
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2))
        eng.bpm = 80.0
        # 20 trials where every press was a hit but at Late quality.
        for _ in range(20):
            for lane in range(4):
                eng.record(lane, hit=True, rt_ms=800.0, quality=0.25)
        # Even though hit_rate is 100%, the quality rate is ~0.25 which
        # is below target_low, so BPM should drop.
        self.assertLess(eng.next_bpm(), 80.0)

    def test_all_greats_speed_the_pace_up(self) -> None:
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2))
        eng.bpm = 80.0
        for _ in range(20):
            for lane in range(4):
                eng.record(lane, hit=True, rt_ms=180.0, quality=1.0)
        self.assertGreater(eng.next_bpm(), 80.0)

    def test_session_quality_rate_tracks_quality_not_hits(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        # Drive ALL four lanes so the per-lane EMAs converge, otherwise
        # the unstimulated lanes drag the session rate back toward 0.5.
        for _ in range(20):
            for lane in range(4):
                eng.record(lane, hit=True, rt_ms=900.0, quality=0.25)
        # Hit rate converges high since every trial was a hit.
        self.assertGreater(eng.session_hit_rate, 0.9)
        # Quality rate converges toward the per-trial quality of 0.25.
        self.assertLess(eng.session_quality_rate, 0.4)


class RtAwareSlowDownTests(unittest.TestCase):
    """When the patient is hitting but reacting slowly (RT near the
    edge of the press window), the adapter should slow down further.
    Helps severely impaired patients who CAN hit but only just."""

    def test_session_rt_ms_averages_played_lanes_only(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        # Only feed lanes 0 and 1. Lanes 2 + 3 keep their default 500ms
        # EMA but shouldn't pull the session average toward 500.
        for _ in range(20):
            eng.record(0, hit=True, rt_ms=900.0, quality=0.6)
            eng.record(1, hit=True, rt_ms=900.0, quality=0.6)
        rt = eng.session_rt_ms
        # EMA converges toward 900 since we only fed lanes 0 and 1.
        self.assertGreater(rt, 700.0)
        self.assertLess(rt, 1000.0)

    def test_rt_utilisation_ratio_against_current_timeout(self) -> None:
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2))
        eng.bpm = 60.0     # cadence = 1.0s, window = 0.9s = 900 ms
        for _ in range(30):
            for lane in range(4):
                eng.record(lane, hit=True, rt_ms=800.0, quality=0.5)
        # rt_ema converges near 800ms; window is 900ms; util ~ 0.88.
        self.assertGreater(eng.rt_utilisation, 0.8)
        self.assertLess(eng.rt_utilisation, 1.0)

    def test_slow_rt_pushes_bpm_down_even_with_decent_quality(self) -> None:
        # Patient is hitting (quality 0.6 = somewhere between Good and
        # Great) but their RT is eating most of the window. The adapter
        # should still slow down because they're cutting it fine.
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2))
        eng.bpm = 60.0     # window ~900ms
        for _ in range(30):
            for lane in range(4):
                eng.record(lane, hit=True, rt_ms=820.0, quality=0.6)
        # qr ~ 0.6 (just under target_low 0.65) AND util high -> slow down.
        self.assertLess(eng.next_bpm(), 60.0)

    def test_high_quality_with_high_rt_does_not_speed_up(self) -> None:
        # qr above target_high should normally speed up, but if RT is
        # eating > 80% of the window the engine should hold steady (or
        # slow, but at minimum not speed up).
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2))
        eng.bpm = 60.0
        for _ in range(40):
            for lane in range(4):
                # Quality 0.95 (Great-ish) but RT 820ms / 900ms window.
                eng.record(lane, hit=True, rt_ms=820.0, quality=0.95)
        self.assertLessEqual(eng.next_bpm(), 60.0,
            "engine should not speed up when RT is near the window edge")

    def test_bpm_can_drop_below_old_floor_of_20(self) -> None:
        # bpm_min was lowered from 20 to 10 (3s -> 6s per stim) so a
        # severely impaired patient still has room to slow further.
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        cfg = AdaptiveConfig(min_trials=2, bpm_min=10.0, bpm_step=15.0)
        eng = AdaptiveEngine(cfg=cfg)
        eng.bpm = 30.0
        # Force a hard slow-down by feeding many misses.
        for _ in range(30):
            for lane in range(4):
                eng.record(lane, hit=False, rt_ms=None, quality=0.0)
        for _ in range(5):
            eng.next_bpm()
        self.assertLessEqual(eng.bpm, 20.0,
            "should be able to drop below the old 20 BPM floor")
        self.assertGreaterEqual(eng.bpm, 10.0,
            "should clamp at the new 10 BPM floor")


class ColdStartTests(unittest.TestCase):
    """The quality EMA used to default to 0.5, which sat below the
    target_low band. A patient hitting Greats from trial one would
    get slowed down before the EMA could converge. quality_ema now
    seeds to the first observed quality on the very first trial."""

    def test_first_trial_seeds_quality_ema_to_observed_value(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        # First record sets the EMA directly, NOT averaged with 0.5.
        eng.record(0, hit=True, rt_ms=200.0, quality=1.0)
        self.assertEqual(eng.state[0].quality_ema, 1.0)

    def test_patient_hitting_greats_from_start_does_not_get_slowed(self) -> None:
        # End-to-end: starting BPM should NOT crash to the floor on
        # the early trials when the patient is performing well.
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2,
                                                  bpm_step=10.0))
        eng.bpm = 60.0
        for i in range(1, 9):
            eng.record(i % 4, hit=True, rt_ms=200.0, quality=1.0)
            eng.next_bpm()
        # Should have gone UP from 60, not crashed down.
        self.assertGreater(eng.bpm, 60.0,
            f"hitting Greats from start should NOT slow down, got bpm={eng.bpm}")


class StreakAmplifiedSpeedUpTests(unittest.TestCase):
    """Confident speed-up is gated on the live streak and amplified by
    how long that streak is. A patient on a 10-hit run should see a
    bigger jump than one with a fresh 3-hit run."""

    def test_record_tracks_consecutive_hits(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        for _ in range(5):
            eng.record(0, hit=True, rt_ms=200.0, quality=1.0)
        self.assertEqual(eng.current_streak, 5)
        self.assertEqual(eng.current_miss_streak, 0)

    def test_record_resets_streak_on_miss(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        for _ in range(4):
            eng.record(0, hit=True, rt_ms=200.0, quality=1.0)
        eng.record(0, hit=False, rt_ms=None, quality=0.0)
        self.assertEqual(eng.current_streak, 0)
        self.assertEqual(eng.current_miss_streak, 1)

    def test_speed_up_gated_on_streak(self) -> None:
        # Even with hit rate above target, if the streak is below 2
        # the adapter must NOT speed up. Prevents a single fluke press
        # after a miss spree from instantly pushing the pace.
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2))
        eng.bpm = 60.0
        # High hit rate AND high quality, but only streak=1.
        for s in eng.state:
            s.hit_ema = 0.95
            s.quality_ema = 0.95
            s.n_trials = 10
            s.rt_ema_ms = 200.0
        eng.current_streak = 1   # under the gate
        before = eng.bpm
        eng.next_bpm()
        self.assertEqual(eng.bpm, before,
            "low streak must NOT trigger confident speed-up")

    def test_long_streak_amplifies_speed_up(self) -> None:
        # A 10-hit streak should produce a noticeably larger jump
        # than a 3-hit streak under identical hit-rate + quality + RT.
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine

        def jump_for_streak(streak_len: int) -> float:
            eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2,
                                                     bpm_step=10.0))
            eng.bpm = 60.0
            for s in eng.state:
                s.hit_ema = 0.95
                s.quality_ema = 0.95
                s.n_trials = 10
                s.rt_ema_ms = 200.0
            eng.current_streak = streak_len
            before = eng.bpm
            eng.next_bpm()
            return eng.bpm - before

        small = jump_for_streak(3)
        big = jump_for_streak(10)
        self.assertGreater(big, small,
            f"streak 10 jump ({big}) should exceed streak 3 jump ({small})")


class ClosedLoopEquilibriumTests(unittest.TestCase):
    """End-to-end: simulate a patient with a fixed reaction time and
    verify the engine drives BPM toward an equilibrium where their RT
    sits in the comfortable 0.55-0.80 utilisation band."""

    def _drive(self, fixed_rt_ms: float, start_bpm: float = 60.0,
                n_trials: int = 80) -> float:
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2,
                                                  bpm_step=10.0,
                                                  bpm_min=10.0,
                                                  bpm_max=160.0))
        eng.bpm = start_bpm
        for i in range(n_trials):
            window_ms = eng.current_timeout_s * 1000.0
            # Patient hits if their fixed RT fits inside the window.
            hit = fixed_rt_ms <= window_ms
            rt = fixed_rt_ms if hit else None
            # Quality scales with how much of the window the press
            # used: 1.0 at instant, 0.0 at the edge.
            if hit:
                q = max(0.0, 1.0 - (fixed_rt_ms / window_ms))
            else:
                q = 0.0
            eng.record(i % 4, hit=hit, rt_ms=rt, quality=q)
            eng.next_bpm()
        return eng.bpm

    def test_fast_patient_drives_bpm_high(self) -> None:
        # 150 ms RT patient. Window must shrink to ~300 ms (util ~0.5).
        # cadence = 60/bpm = 0.333 -> bpm ~ 180. Capped at bpm_max=160.
        final_bpm = self._drive(150.0)
        self.assertGreater(final_bpm, 100.0,
            f"fast patient should drive BPM well above 100, got {final_bpm}")

    def test_moderate_patient_settles_mid_range(self) -> None:
        # 400 ms RT patient. Equilibrium window ~600 ms (util ~0.67).
        # cadence = window/0.9 = 0.667, bpm = 60/0.667 = ~90.
        final_bpm = self._drive(400.0)
        self.assertGreater(final_bpm, 50.0,
            f"moderate patient BPM too low: {final_bpm}")
        self.assertLess(final_bpm, 130.0,
            f"moderate patient BPM too high: {final_bpm}")

    def test_slow_patient_drives_bpm_down(self) -> None:
        # 1500 ms RT patient (severely impaired). Needs a very long
        # window. Should converge well below the start_bpm of 80.
        final_bpm = self._drive(1500.0, start_bpm=80.0)
        self.assertLess(final_bpm, 50.0,
            f"slow patient BPM should drop well below 50, got {final_bpm}")


class ProbeStepTests(unittest.TestCase):
    """When the patient sits comfortably in the target band with spare
    RT, the engine nudges BPM up by a fraction of a step to find their
    real limit instead of plateauing forever. The nudge comes from the
    rt_pressure path (low utilisation -> positive pressure)."""

    def test_probe_fires_when_in_band_with_comfortable_rt_and_streak(self) -> None:
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2, bpm_step=10.0))
        eng.bpm = 80.0
        # Hit rate in band (target_low=0.65, target_high=0.80),
        # RT comfortable (200 ms of 675 ms window = 0.30 util).
        for s in eng.state:
            s.hit_ema = 0.72
            s.quality_ema = 0.72
            s.n_trials = 10
            s.rt_ema_ms = 200.0
        eng.current_streak = 4
        before = eng.bpm
        eng.next_bpm()
        self.assertGreater(eng.bpm, before)
        self.assertLess(eng.bpm - before, 5.0,
            "probe should be a small nudge, not a full step")

    def test_probe_does_not_fire_without_streak(self) -> None:
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2))
        eng.bpm = 80.0
        for s in eng.state:
            s.hit_ema = 0.72         # in band
            s.quality_ema = 0.72
            s.n_trials = 10
            s.rt_ema_ms = 200.0
        eng.current_streak = 0       # no streak
        before = eng.bpm
        eng.next_bpm()
        self.assertEqual(eng.bpm, before)


class ScoreMultiplierTests(unittest.TestCase):
    """Score multipliers reward speed (pace) and consistency (streak)."""

    def _make_engine(self):
        from rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        eng.hit_streak = 0
        eng.mode = None
        return eng

    def test_pace_multiplier_unity_when_no_mode(self) -> None:
        eng = self._make_engine()
        self.assertEqual(eng._pace_multiplier(), 1.0)

    def test_pace_multiplier_scales_with_bpm(self) -> None:
        eng = self._make_engine()
        class FakeMode:
            class A:
                bpm = 120.0
            adapter = A()
        eng.mode = FakeMode()
        self.assertAlmostEqual(eng._pace_multiplier(), 2.0)

    def test_streak_multiplier_caps_at_1_5x(self) -> None:
        eng = self._make_engine()
        eng.hit_streak = 99
        self.assertAlmostEqual(eng._streak_multiplier(), 1.5)

    def test_score_for_negative_points_passes_through(self) -> None:
        # Misses must not get multiplied (a -2 miss shouldn't become -6).
        eng = self._make_engine()
        eng.hit_streak = 5
        self.assertEqual(eng._score_for(-2, "Miss"), -2)

    def test_score_for_hit_gets_combined_multiplier(self) -> None:
        eng = self._make_engine()
        class FakeMode:
            class A:
                bpm = 120.0   # 2x pace
            adapter = A()
        eng.mode = FakeMode()
        eng.hit_streak = 5        # 1.5x streak
        # 3 base points * 2.0 pace * 1.5 streak = 9
        self.assertEqual(eng._score_for(3, "Great"), 9)


class AdaptiveRecoveryTests(unittest.TestCase):
    """Three misses in a row should drop the adapter into recovery: big
    BPM drop + lane weights biased toward the patient's strongest finger
    until they land a hit. Then recovery clears."""

    def test_enter_recovery_drops_bpm_hard(self) -> None:
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(bpm_step=10.0,
                                                  bpm_min=30.0))
        eng.bpm = 80.0
        eng.enter_recovery()
        # 2.5x the normal step (25 BPM) should come off.
        self.assertAlmostEqual(eng.bpm, 55.0)
        self.assertTrue(eng.in_recovery)

    def test_recovery_floors_at_bpm_min(self) -> None:
        from rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(bpm_step=10.0,
                                                  bpm_min=30.0))
        eng.bpm = 35.0
        eng.enter_recovery()
        # Should clamp at bpm_min, not go below.
        self.assertEqual(eng.bpm, 30.0)

    def test_recovery_lane_weights_favour_strongest_finger(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        # Make lane 2 the strongest by feeding it hits, the rest get misses.
        for _ in range(15):
            eng.record(2, hit=True, rt_ms=200.0, quality=1.0)
            for lane in (0, 1, 3):
                eng.record(lane, hit=False, rt_ms=None, quality=0.0)
        eng.enter_recovery()
        weights = eng.lane_weights()
        # Lane 2 (strongest) gets the majority of the weight.
        self.assertGreater(weights[2], 0.5)
        for i in (0, 1, 3):
            self.assertLess(weights[i], 0.2)

    def test_exit_recovery_restores_normal_weights(self) -> None:
        from rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        eng.enter_recovery()
        eng.exit_recovery()
        # Out of recovery the weights follow the weakness rule again, so
        # if no data exists they're roughly even.
        weights = eng.lane_weights()
        for w in weights:
            self.assertAlmostEqual(w, 0.25, places=2)


class NoNegativeScoreTests(unittest.TestCase):
    """Score must never go below zero. Misses worth 0 by default."""

    def test_score_config_defaults_to_zero_miss(self) -> None:
        from rehab.game.scoring import ScoreConfig
        cfg = ScoreConfig()
        self.assertEqual(cfg.miss_points, 0)
        self.assertEqual(cfg.early_penalty, 0)

    def test_classify_offset_miss_defaults_to_zero(self) -> None:
        from rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()
        label, pts = classify_offset(500.0, w)    # 500ms way outside miss window
        self.assertEqual(label, "Miss")
        self.assertEqual(pts, 0)

    def test_default_yaml_miss_points_zero(self) -> None:
        from rehab.config import Config
        cfg = Config.load()
        self.assertEqual(cfg.get("scoring.miss_points"), 0)
        self.assertEqual(cfg.get("scoring.early_penalty"), 0)


if __name__ == "__main__":
    unittest.main()
