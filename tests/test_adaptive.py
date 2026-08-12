"""Tests for the adaptive difficulty engine (Thread 1)."""
from __future__ import annotations

import random
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class AdaptiveEngineTests(unittest.TestCase):
    def test_construction_requires_positive_num_lanes(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveEngine
        with self.assertRaises(ValueError):
            AdaptiveEngine(num_lanes=0)
        with self.assertRaises(ValueError):
            AdaptiveEngine(num_lanes=-1)

    def test_weak_lanes_get_higher_weight(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        for _ in range(20):
            eng.record(0, hit=False, rt_ms=None)
            eng.record(3, hit=True, rt_ms=300.0)
        w = eng.lane_weights()
        self.assertGreater(w[0], w[3])

    def test_bpm_speeds_up_when_hits_are_easy(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        eng.bpm = 80.0
        for _ in range(20):
            for lane in range(4):
                eng.record(lane, hit=True, rt_ms=250.0)
        self.assertGreater(eng.next_bpm(), 80.0)

    def test_bpm_slows_down_when_misses_pile_up(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        eng.bpm = 80.0
        for _ in range(20):
            for lane in range(4):
                eng.record(lane, hit=False, rt_ms=None)
        self.assertLess(eng.next_bpm(), 80.0)

    def test_sequence_avoids_immediate_repeats_when_possible(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        rng = random.Random(42)
        seq = eng.generate_sequence(50, rng=rng, avoid_repeats=True)
        repeats = sum(1 for i in range(1, len(seq)) if seq[i] == seq[i - 1])
        # With weights roughly even and 4 lanes, repeats should be rare.
        self.assertLess(repeats, 5)

    def test_warm_start_from_csv_like_history(self) -> None:
        from finger_rehab.analytics.adaptive import warm_start_from_history
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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(min_trials=2))
        eng.bpm = 80.0
        for _ in range(20):
            for lane in range(4):
                eng.record(lane, hit=True, rt_ms=180.0, quality=1.0)
        self.assertGreater(eng.next_bpm(), 80.0)

    def test_session_quality_rate_tracks_quality_not_hits(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        # First record sets the EMA directly, NOT averaged with 0.5.
        eng.record(0, hit=True, rt_ms=200.0, quality=1.0)
        self.assertEqual(eng.state[0].quality_ema, 1.0)

    def test_patient_hitting_greats_from_start_does_not_get_slowed(self) -> None:
        # End-to-end: starting BPM should NOT crash to the floor on
        # the early trials when the patient is performing well.
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveEngine
        eng = AdaptiveEngine()
        for _ in range(5):
            eng.record(0, hit=True, rt_ms=200.0, quality=1.0)
        self.assertEqual(eng.current_streak, 5)
        self.assertEqual(eng.current_miss_streak, 0)

    def test_record_resets_streak_on_miss(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine

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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
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
        from finger_rehab.game.engine import GameEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(bpm_step=10.0,
                                                  bpm_min=30.0))
        eng.bpm = 80.0
        eng.enter_recovery()
        # 2.5x the normal step (25 BPM) should come off.
        self.assertAlmostEqual(eng.bpm, 55.0)
        self.assertTrue(eng.in_recovery)

    def test_recovery_floors_at_bpm_min(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        eng = AdaptiveEngine(cfg=AdaptiveConfig(bpm_step=10.0,
                                                  bpm_min=30.0))
        eng.bpm = 35.0
        eng.enter_recovery()
        # Should clamp at bpm_min, not go below.
        self.assertEqual(eng.bpm, 30.0)

    def test_recovery_lane_weights_favour_strongest_finger(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveEngine
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
        from finger_rehab.analytics.adaptive import AdaptiveEngine
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
        from finger_rehab.game.scoring import ScoreConfig
        cfg = ScoreConfig()
        self.assertEqual(cfg.miss_points, 0)
        self.assertEqual(cfg.early_penalty, 0)

    def test_classify_offset_miss_defaults_to_zero(self) -> None:
        from finger_rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()
        label, pts = classify_offset(500.0, w)    # 500ms way outside miss window
        self.assertEqual(label, "Miss")
        self.assertEqual(pts, 0)

    def test_default_yaml_miss_points_zero(self) -> None:
        from finger_rehab.config import Config
        cfg = Config.load()
        self.assertEqual(cfg.get("scoring.miss_points"), 0)
        self.assertEqual(cfg.get("scoring.early_penalty"), 0)


# ---------------------------------------------------------------------
# Audit findings #42-53 (adaptive fix stage)
# ---------------------------------------------------------------------

def _bare_engine():
    """Real GameEngine, minus construction, wired with just the state
    on_stim_multi + log_trial actually touch, plus a recording stand-in
    for the trial logger. Mirrors tests/test_capture_completeness.py's
    helper of the same name."""
    from unittest.mock import MagicMock
    from finger_rehab.game.engine import GameEngine
    eng = GameEngine.__new__(GameEngine)
    eng.cfg = MagicMock()
    eng.cfg.get = MagicMock(return_value=0)
    eng.score = 0
    eng.hits = 0
    eng.misses = 0
    eng.hit_streak = 0
    eng.miss_streak = 0
    eng._streak_fired = set()
    eng._streak_thresholds = ()
    eng._recovery_threshold = 3
    eng._block_rt_sum = 0.0
    eng._block_rt_count = 0
    eng._block_bpm_min = None
    eng._block_bpm_max = None
    eng._block_wrong_press_trials = 0
    eng._block_rhythm_spurious_presses = 0
    eng._block_idle_presses = 0
    eng._block_peak_streak = 0
    eng._last_gained = 0
    eng.current_block = "adaptive"
    eng.hand_mode = "right"
    eng.raw_logger = None
    eng.audio = None
    eng._screens = {}
    eng.session_paths = None
    eng.session = MagicMock()
    eng.session.participant = "T"
    eng.session.age = ""
    eng.theme = MagicMock()
    eng.mode = None
    eng._per_lane_rts = {}
    eng._per_lane_misses = {}
    eng._per_lane_wrong = {}
    eng._trial_context_orig = None
    eng._last_stim_bpm = None
    eng._last_stim_in_recovery = None

    rows: list[dict] = []
    logger = MagicMock()
    logger.write = rows.append
    eng.trial_logger = logger
    eng._rows = rows
    return eng


class BpmAtTrialSnapshotTests(unittest.TestCase):
    """Finding #42: bpm_at_trial (and in_recovery) must record the
    state AS OF THIS TRIAL'S STIM, not whatever the adapter has become
    by the time the row is written. AdaptiveMode calls
    adapter.record()+next_bpm() (and a miss can push the adapter into
    recovery via _update_streak) before log_trial, both BEFORE
    _trial_context would otherwise read the adapter live."""

    def test_bpm_at_trial_uses_the_stim_time_snapshot_not_live_value(
            self) -> None:
        from finger_rehab.game.modes.classic import PendingTrial
        from finger_rehab.game.scoring import TrialResult
        eng = _bare_engine()
        eng._ensure_metric_state()

        class FakeAdapter:
            bpm = 30.0
            in_recovery = False

        class FakeMode:
            adapter = FakeAdapter()
        eng.mode = FakeMode()

        # Trial fires at bpm=30 (on_stim_multi snapshots it).
        eng.on_stim_multi([0], trial_id=1, t_perf=0.0)
        self.assertEqual(eng._last_stim_bpm, 30.0)

        # Mirrors what AdaptiveMode._finish does next: record() +
        # next_bpm() (and _update_streak, inside log_trial, could also
        # flip in_recovery) BEFORE the row is written -- a miss crashes
        # the adapter to the floor and into recovery.
        eng.mode.adapter.bpm = 10.0
        eng.mode.adapter.in_recovery = True

        trial = PendingTrial(trial_id=1, lane=0, stim_t_perf=0.0,
                              keys_pressed=[], incorrect_presses=[])
        eng.log_trial(trial, TrialResult(label="Miss", points=0,
                                          rt_ms=None), now=0.0)
        row = eng._rows[0]
        self.assertEqual(row["bpm_at_trial"], "30.0",
            "must log the BPM this trial was PRESENTED at (30), not "
            "the post-miss value (10) the adapter crashed to before "
            "the row was written")
        self.assertEqual(row["in_recovery"], "FALSE",
            "recovery had not started yet when this trial's stim fired")

    def test_next_trial_gets_its_own_fresh_snapshot(self) -> None:
        from finger_rehab.game.modes.classic import PendingTrial
        from finger_rehab.game.scoring import TrialResult
        eng = _bare_engine()
        eng._ensure_metric_state()

        class FakeAdapter:
            bpm = 10.0
            in_recovery = True

        class FakeMode:
            adapter = FakeAdapter()
        eng.mode = FakeMode()

        eng.on_stim_multi([0], trial_id=2, t_perf=1.0)
        trial = PendingTrial(trial_id=2, lane=0, stim_t_perf=1.0,
                              keys_pressed=[0], incorrect_presses=[])
        eng.log_trial(trial, TrialResult(label="Great", points=6,
                                          rt_ms=150.0), now=1.0)
        row = eng._rows[0]
        self.assertEqual(row["bpm_at_trial"], "10.0")
        self.assertEqual(row["in_recovery"], "TRUE")


def _mode(engine=None, **overrides):
    from unittest.mock import MagicMock
    from finger_rehab.analytics.adaptive import AdaptiveConfig
    from finger_rehab.game.modes.adaptive import AdaptiveMode
    from finger_rehab.game.scoring import ScoreConfig
    if engine is None:
        engine = MagicMock()
        engine.cfg = MagicMock()
        engine.cfg.get = MagicMock(return_value=0)
        engine.apply_wrong_press_penalty = MagicMock(return_value=2)
        engine.apply_idle_press_penalty = MagicMock(return_value=0)
        engine.log_trial = MagicMock()
        engine.on_stim = MagicMock()
        engine.hand_mode = "right"
        engine.raw_logger = None
    kwargs = dict(engine=engine, num_lanes=4, total_trials=8,
                  block_size=4, score_cfg=ScoreConfig(), timeout_s=1.0,
                  early_window_s=0.1, start_bpm=30.0,
                  adaptive_cfg=AdaptiveConfig(target_low=0.65,
                                              target_high=0.80,
                                              bpm_min=10.0, bpm_max=140.0,
                                              bpm_step=10.0,
                                              weakness_bias=2.5,
                                              min_trials=2))
    kwargs.update(overrides)
    return engine, AdaptiveMode(**kwargs)


def _press(lane: int, t: float):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                       hand="right")


class CadenceFloorTests(unittest.TestCase):
    """Finding #43: the presented cadence must floor at the adapter's
    OWN configured bpm_min (10 -> 6s gap for severe weakness), not a
    stale literal 20 (3s gap) left over from an earlier floor. Drives
    update() itself through a fake clock rather than recomputing the
    formula independently, so a hardcoded 20 in the source is actually
    caught."""

    def test_update_waits_a_full_6s_gap_at_bpm_min_not_3s(self) -> None:
        import finger_rehab.game.modes.adaptive as adaptive_mod
        engine, mode = _mode()
        mode.adapter.bpm = mode.adapter.cfg.bpm_min  # 10.0 -> 6s cadence
        mode.completed = 0
        mode.total_trials = 99
        mode.active = None
        mode.seq_idx = 0
        mode.sequence = [0, 1, 2, 3]

        fake_t = [1000.0]
        orig_perf_counter = adaptive_mod.time.perf_counter
        adaptive_mod.time.perf_counter = lambda: fake_t[0]
        try:
            mode.update(0.0)  # first trial fires immediately
            self.assertIsNotNone(mode.active)
            mode.active = None  # simulate an instant finish, re-arm
            mode.last_trigger_t = fake_t[0]

            # 3.5s later (past the OLD 3s/20bpm floor, short of the
            # correct 6s/10bpm floor): must NOT have fired again.
            fake_t[0] += 3.5
            mode.update(0.0)
            self.assertIsNone(mode.active,
                "fired again after 3.5s -- still using the stale 20 "
                "BPM (3s) floor instead of bpm_min=10 (6s)")

            # Past the real 6s gap: must fire now.
            fake_t[0] += 3.0  # total 6.5s since last_trigger_t
            mode.update(0.0)
            self.assertIsNotNone(mode.active,
                "did not fire even after the full 6s gap at bpm_min=10")
        finally:
            adaptive_mod.time.perf_counter = orig_perf_counter


class RecoverySequenceRegenTests(unittest.TestCase):
    """Finding #50: entering (or exiting) recovery must bias the very
    NEXT lane pick, not whatever is left of the sequence drawn under
    the OLD weighting -- up to block_size-1 trials could otherwise
    still come from before the transition."""

    def _build_with_recovery_transition(self, becomes_recovery: bool):
        engine, mode = _mode()

        def _log_trial(trial, outcome, now, **kw):
            # Stand-in for engine._update_streak, which is what
            # actually flips adapter.in_recovery inside the real
            # engine.log_trial.
            mode.adapter.in_recovery = becomes_recovery
        engine.log_trial.side_effect = _log_trial
        return engine, mode

    def test_entering_recovery_discards_remaining_sequence(self) -> None:
        engine, mode = self._build_with_recovery_transition(True)
        mode.sequence = [0, 1, 2, 3]
        mode.seq_idx = 0
        mode._fire(now=0.0)
        self.assertEqual(mode.seq_idx, 1,
            "only 1 of 4 pre-drawn trials should be consumed so far")
        target = mode.active.lane
        mode._handle_press(_press(target, 0.05), now=0.05)
        self.assertGreaterEqual(mode.seq_idx, len(mode.sequence),
            "entering recovery must discard whatever is left of the "
            "pre-recovery sequence so the next _fire() regenerates "
            "under the recovery-biased weights immediately")

    def test_exiting_recovery_also_discards_remaining_sequence(self) -> None:
        engine, mode = self._build_with_recovery_transition(False)
        mode.adapter.in_recovery = True
        mode._last_recovery = True
        mode.sequence = [0, 1, 2, 3]
        mode.seq_idx = 0
        mode._fire(now=0.0)
        target = mode.active.lane
        mode._handle_press(_press(target, 0.05), now=0.05)
        self.assertGreaterEqual(mode.seq_idx, len(mode.sequence),
            "exiting recovery must also discard the recovery-shaped "
            "sequence rather than letting it keep playing out")

    def test_no_transition_leaves_sequence_alone(self) -> None:
        engine, mode = self._build_with_recovery_transition(False)
        mode.sequence = [0, 1, 2, 3]
        mode.seq_idx = 0
        mode._fire(now=0.0)
        target = mode.active.lane
        mode._handle_press(_press(target, 0.05), now=0.05)
        self.assertEqual(mode.seq_idx, 1,
            "no recovery transition happened, so the sequence should "
            "advance normally, not get discarded")


class SingleNextBpmPerTrialTests(unittest.TestCase):
    """Finding #51 (part 1): next_bpm() must run exactly once per
    completed trial. _fire() used to call it again at every sequence
    regen (every block_size trials) with no new data, doubling up
    right at the boundary."""

    def test_next_bpm_called_once_per_trial_across_a_regen_boundary(
            self) -> None:
        engine, mode = _mode()
        calls = []
        orig = mode.adapter.next_bpm
        def _spy():
            r = orig()
            calls.append(r)
            return r
        mode.adapter.next_bpm = _spy

        t = 0.0
        for _ in range(5):  # crosses the block_size=4 regen boundary
            mode._fire(now=t)
            target = mode.active.lane
            t += 0.05
            mode._handle_press(_press(target, t), now=t)
            t += 0.1
        self.assertEqual(len(calls), 5,
            f"5 completed trials must mean exactly 5 next_bpm() calls, "
            f"got {len(calls)} (a regen-time extra call inflates this)")


class ColdStartClampTests(unittest.TestCase):
    """Finding #51 (part 2): two opening misses (min_trials=2) must
    not floor BPM in a single step -- the full -2*bpm_step clamp can
    equal (or exceed) the whole gap from a comfortable start_bpm down
    to bpm_min, letting 2 trials decide the entire block's pace."""

    def test_two_opening_misses_do_not_instantly_floor_bpm(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        ac = AdaptiveConfig(target_low=0.65, target_high=0.80,
                             bpm_min=10.0, bpm_max=140.0, bpm_step=10.0,
                             weakness_bias=2.5, min_trials=2)
        eng = AdaptiveEngine(num_lanes=4, cfg=ac)
        eng.bpm = 30.0
        eng.record(0, hit=False, rt_ms=None, quality=0.0)
        eng.record(1, hit=False, rt_ms=None, quality=0.0)
        new_bpm = eng.next_bpm()
        self.assertGreater(new_bpm, ac.bpm_min,
            "two opening misses should not floor BPM in one call; the "
            "cold-start clamp should soften the first couple of "
            "next_bpm() decisions")

    def test_a_sustained_collapse_still_reaches_the_floor(self) -> None:
        # The softening must be temporary -- a genuinely struggling
        # patient still needs to reach bpm_min, just not off 2 trials.
        from finger_rehab.analytics.adaptive import AdaptiveConfig, AdaptiveEngine
        ac = AdaptiveConfig(target_low=0.65, target_high=0.80,
                             bpm_min=10.0, bpm_max=140.0, bpm_step=10.0,
                             weakness_bias=2.5, min_trials=2)
        eng = AdaptiveEngine(num_lanes=4, cfg=ac)
        eng.bpm = 30.0
        for _ in range(10):
            for lane in range(4):
                eng.record(lane, hit=False, rt_ms=None, quality=0.0)
            eng.next_bpm()
        self.assertEqual(eng.bpm, ac.bpm_min)


class AnticipationQualityTests(unittest.TestCase):
    """Finding #52: classify() has no lower RT bound, so a sub-cut
    (mash-speed) press reads as a clean Perfect/Great. The label/score/
    rt_ms this mode logs must stay as classify() said (the notebook's
    own exclusion_flags already drops sub-100ms cued rows by
    time_difference_ms), but the ADAPTER must not be told it was a
    quality=1.0 press -- that would speed the pace up off blind
    mashing."""

    def test_subcut_press_does_not_feed_full_quality_to_adapter(
            self) -> None:
        engine, mode = _mode()
        records = []
        orig = mode.adapter.record
        def _spy(lane, was_hit, rt_ms, quality=None):
            records.append((lane, was_hit, rt_ms, quality))
            return orig(lane, was_hit, rt_ms, quality=quality)
        mode.adapter.record = _spy

        mode._fire(now=0.0)
        target = mode.active.lane
        mode._handle_press(_press(target, 0.060), now=0.060)  # 60ms

        outcome = engine.log_trial.call_args[0][1]
        self.assertIn(outcome.label, ("Perfect", "Great"),
            "the classified label/score/rt_ms must stay as classify() "
            "said -- the notebook filters sub-100ms rows itself")
        self.assertEqual(records[0][3], 0.0,
            "a 60ms press is too fast to be a real reaction; the "
            "adapter must not be told quality=1.0 off it")

    def test_normal_speed_press_still_feeds_full_quality(self) -> None:
        engine, mode = _mode()
        records = []
        orig = mode.adapter.record
        def _spy(lane, was_hit, rt_ms, quality=None):
            records.append((lane, was_hit, rt_ms, quality))
            return orig(lane, was_hit, rt_ms, quality=quality)
        mode.adapter.record = _spy

        mode._fire(now=0.0)
        target = mode.active.lane
        mode._handle_press(_press(target, 0.150), now=0.150)  # 150ms

        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Great")
        self.assertEqual(records[0][3], 1.0,
            "a genuine 150ms press must still earn full adapter credit")


class IdlePressRawEventTests(unittest.TestCase):
    """Finding #53: an idle (between-trial) press must reach raw.csv
    with its own lane and timestamp, not just bump a per-block count --
    otherwise no idle press can ever be told apart from any other after
    the fact."""

    def test_idle_press_queues_a_raw_event_with_lane_and_time(
            self) -> None:
        from unittest.mock import MagicMock
        engine, mode = _mode()
        engine.raw_logger = MagicMock()

        mode._handle_press(_press(2, 1.234), now=1.234)

        engine.apply_idle_press_penalty.assert_called_once()
        engine.raw_logger.queue_event.assert_called_once()
        args, kwargs = engine.raw_logger.queue_event.call_args
        self.assertEqual(args[0], "idle_press")
        self.assertEqual(kwargs["lane"], 2)
        self.assertEqual(kwargs["t_perf"], 1.234)

    def test_no_raw_logger_does_not_crash(self) -> None:
        engine, mode = _mode()
        engine.raw_logger = None
        mode._handle_press(_press(1, 0.5), now=0.5)  # must not raise
        engine.apply_idle_press_penalty.assert_called_once()


class BandCitationTests(unittest.TestCase):
    """Finding #44: the 70-80 vs 65-80 percent band was stated
    inconsistently and misattributed to Guadagnoli & Lee (2004), who
    do not report a numeric success-rate band. Code, config and every
    docstring must now agree on one number (65-80) with no bare "70-80"
    left implying a different figure than the config actually holds."""

    def test_config_defaults_are_65_to_80(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveConfig
        cfg = AdaptiveConfig()
        self.assertEqual(cfg.target_low, 0.65)
        self.assertEqual(cfg.target_high, 0.80)

    def test_default_yaml_matches_the_engine_defaults(self) -> None:
        from finger_rehab.config import Config
        cfg = Config.load()
        self.assertEqual(cfg.get("adaptive.target_low"), 0.65)
        self.assertEqual(cfg.get("adaptive.target_high"), 0.80)

    def test_no_stray_70_80_band_text_left_in_the_module(self) -> None:
        import finger_rehab.analytics.adaptive as ad
        src = Path(ad.__file__).read_text()
        self.assertNotIn("70-80", src)
        self.assertNotIn("70 to 80", src)


class PaceLabelUnusedDocstringTests(unittest.TestCase):
    """Finding #49: pace_label's docstring claimed the HUD shows it;
    nothing calls it (the gameplay HUD deliberately dropped BPM). The
    docstring must say so rather than describe a UI element that
    doesn't exist."""

    def test_docstring_no_longer_claims_the_hud_uses_it(self) -> None:
        from finger_rehab.analytics.adaptive import AdaptiveEngine
        doc = AdaptiveEngine.pace_label.__doc__ or ""
        self.assertNotIn("Used by the HUD", doc)


if __name__ == "__main__":
    unittest.main()
