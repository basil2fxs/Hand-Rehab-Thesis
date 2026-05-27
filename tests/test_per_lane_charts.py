"""Tests for the per-lane stats that drive the Results-screen
histograms: mean RT per lane (left chart) and miss + wrong-press
count per lane (right chart).

The engine maintains three dicts: `_per_lane_rts`,
`_per_lane_misses`, `_per_lane_wrong`. They reset at every block
start and accumulate over the block. Results screen reads them
directly so the engine is the single source of truth.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _bare_engine():
    """Build a GameEngine via __new__ with just enough state for the
    log_trial / log_rhythm_hit / log_rhythm_unmatched calls used in
    these tests. Real engine construction needs pygame + a source +
    pyserial; this lets us hit the per-lane bookkeeping in isolation."""
    from rehab.game.engine import GameEngine
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
    eng._block_rt_sum = 0.0
    eng._block_rt_count = 0
    eng._block_bpm_min = None
    eng._block_bpm_max = None
    eng._block_wrong_press_trials = 0
    eng._block_rhythm_spurious_presses = 0
    eng._block_idle_presses = 0
    eng._block_peak_streak = 0
    eng._last_gained = 0
    eng.current_block = "classic"
    eng.hand_mode = "right"
    eng.trial_logger = None
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
    return eng


class ClassicAdaptivePerLaneTests(unittest.TestCase):
    """log_trial routes each trial's RT, miss flag, and wrong-press
    count to the right lane's bucket."""

    def _trial(self, lane: int, incorrect=()):
        # Minimal stand-in for PendingTrial. log_trial only reads
        # .lane, .stim_t_perf, .keys_pressed, and .incorrect_presses.
        from rehab.game.modes.classic import PendingTrial
        return PendingTrial(
            trial_id=1, lane=lane, stim_t_perf=0.0,
            keys_pressed=[lane],
            incorrect_presses=list(incorrect),
        )

    def _result(self, label: str, rt_ms: float | None, points: int = 0):
        from rehab.game.scoring import TrialResult
        return TrialResult(label=label, points=points, rt_ms=rt_ms)

    def test_rt_appended_to_target_lane(self) -> None:
        eng = _bare_engine()
        # Stub _trial_context so log_trial doesn't try to read engine.mode.
        eng._trial_context = MagicMock(return_value={})
        eng.log_trial(self._trial(lane=2),
                       self._result("Great", rt_ms=180.0), now=0.0)
        eng.log_trial(self._trial(lane=2),
                       self._result("Good", rt_ms=350.0), now=0.0)
        eng.log_trial(self._trial(lane=0),
                       self._result("Great", rt_ms=200.0), now=0.0)
        self.assertEqual(eng._per_lane_rts[2], [180.0, 350.0])
        self.assertEqual(eng._per_lane_rts[0], [200.0])
        # Lane 1 + 3 got no trials -> not in the dict.
        self.assertNotIn(1, eng._per_lane_rts)
        self.assertNotIn(3, eng._per_lane_rts)

    def test_miss_increments_per_lane_misses(self) -> None:
        eng = _bare_engine()
        eng._trial_context = MagicMock(return_value={})
        eng.log_trial(self._trial(lane=3),
                       self._result("Miss", rt_ms=None), now=0.0)
        eng.log_trial(self._trial(lane=3),
                       self._result("Miss", rt_ms=None), now=0.0)
        eng.log_trial(self._trial(lane=1),
                       self._result("Miss", rt_ms=None), now=0.0)
        self.assertEqual(eng._per_lane_misses[3], 2)
        self.assertEqual(eng._per_lane_misses[1], 1)
        # Miss has no RT -> not appended to RTs.
        self.assertNotIn(3, eng._per_lane_rts)

    def test_wrong_press_counts_against_target_lane(self) -> None:
        # Patient pressed wrong fingers twice then got the right one.
        # The target was lane 2; the wrong-press chart should record
        # 2 against lane 2 (where the patient was meant to land).
        eng = _bare_engine()
        eng._trial_context = MagicMock(return_value={})
        eng.log_trial(
            self._trial(lane=2, incorrect=[(0, 0.1), (3, 0.2)]),
            self._result("Late", rt_ms=600.0),
            now=0.0,
        )
        self.assertEqual(eng._per_lane_wrong[2], 2)
        # Trial still completed so the RT is recorded under lane 2.
        self.assertEqual(eng._per_lane_rts[2], [600.0])


class RhythmPerLaneTests(unittest.TestCase):
    """log_rhythm_hit + log_rhythm_unmatched populate the same dicts
    so the rhythm Results screen sees per-lane data too."""

    def _sched_note(self, lane: int):
        from rehab.audio.beatmap import Note
        sched = MagicMock()
        sched.note = Note(t=1.0, lane=lane)
        sched.index = 0
        return sched

    def test_rhythm_hit_appends_abs_offset_to_lane(self) -> None:
        eng = _bare_engine()
        eng.current_block = "rhythm"
        eng._trial_context = MagicMock(return_value={})
        # Hit on lane 1 with a +50 ms offset and -75 ms offset. The
        # chart's "RT" sample is the absolute offset because the
        # therapist cares about precision, not direction.
        eng.log_rhythm_hit(self._sched_note(1), 50.0, "Great", 6,
                            now=0.0, was_pressed=True)
        eng.log_rhythm_hit(self._sched_note(1), -75.0, "Good", 3,
                            now=0.0, was_pressed=True)
        self.assertEqual(eng._per_lane_rts[1], [50.0, 75.0])

    def test_rhythm_miss_increments_target_lane_count(self) -> None:
        eng = _bare_engine()
        eng.current_block = "rhythm"
        eng._trial_context = MagicMock(return_value={})
        eng.log_rhythm_hit(self._sched_note(3), 0.0, "Miss", 0,
                            now=0.0, was_pressed=False)
        eng.log_rhythm_hit(self._sched_note(3), 0.0, "Miss", 0,
                            now=0.0, was_pressed=False)
        self.assertEqual(eng._per_lane_misses[3], 2)

    def test_unmatched_press_records_against_pressed_lane(self) -> None:
        # Patient pressed middle when there was no note -> chart shows
        # a spike on middle (lane 1), not on the original target.
        eng = _bare_engine()
        eng.current_block = "rhythm"
        eng.log_rhythm_unmatched(lane=1, now=0.0)
        eng.log_rhythm_unmatched(lane=1, now=0.1)
        eng.log_rhythm_unmatched(lane=0, now=0.2)
        self.assertEqual(eng._per_lane_wrong[1], 2)
        self.assertEqual(eng._per_lane_wrong[0], 1)


class BlockResetTests(unittest.TestCase):
    """_begin_block clears the per-lane dicts so a Retry doesn't show
    the previous block's bars mixed with the new one."""

    def test_begin_block_clears_per_lane_state(self) -> None:
        eng = _bare_engine()
        # Seed prior-block data.
        eng._per_lane_rts = {0: [100.0, 200.0], 3: [300.0]}
        eng._per_lane_misses = {0: 1}
        eng._per_lane_wrong = {2: 5}
        # Stub the dependencies _begin_block reaches into.
        eng.session = MagicMock()
        eng.session.notes = ""
        eng.session.started_at = ""
        eng.session.config_snapshot = {}
        eng.session_paths = MagicMock()
        eng._screens = {}
        eng._open_loggers = lambda: None
        eng.detectors = {}
        eng._begin_block("classic")
        self.assertEqual(eng._per_lane_rts, {})
        self.assertEqual(eng._per_lane_misses, {})
        self.assertEqual(eng._per_lane_wrong, {})


if __name__ == "__main__":
    unittest.main()
