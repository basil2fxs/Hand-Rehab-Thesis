"""A trial where the patient pressed a wrong finger before the right
one must end as a MISS, not a hit. Critical for the adaptive
algorithm's weakness signal: if a fumble-then-correct trial keeps
counting as a hit, the engine never picks the struggling finger more
often. Same applies in classic for the per-lane miss histogram on
the Results screen.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ClassicWrongPressMissTests(unittest.TestCase):
    """ClassicMode._handle_press -> _finish: a wrong then a correct
    press must result in a Miss outcome being logged."""

    def _build(self):
        from rehab.game.modes.classic import ClassicMode
        from rehab.game.scoring import ScoreConfig
        engine = MagicMock()
        engine.cfg = MagicMock()
        engine.cfg.get = MagicMock(return_value=0)
        engine.apply_wrong_press_penalty = MagicMock(return_value=2)
        engine.apply_idle_press_penalty = MagicMock(return_value=0)
        engine.log_trial = MagicMock()
        engine.on_stim = MagicMock()
        mode = ClassicMode(
            engine=engine,
            pattern=[0, 1, 2, 3],
            repeat_count=1,
            trigger_interval_s=0.5,
            timeout_s=1.0,
            early_window_s=0.1,
            score_cfg=ScoreConfig(),
        )
        return engine, mode

    def _press(self, lane: int, t: float = 0.0):
        from rehab.hardware.fsr_detector import PressEvent
        return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                            hand="right")

    def test_correct_press_alone_logs_as_hit(self) -> None:
        engine, mode = self._build()
        mode._fire(now=0.0)
        mode._handle_press(self._press(lane=0, t=0.15), now=0.15)
        # log_trial called with a non-Miss outcome.
        engine.log_trial.assert_called_once()
        outcome = engine.log_trial.call_args[0][1]
        self.assertNotEqual(outcome.label, "Miss")

    def test_wrong_then_correct_logs_as_miss(self) -> None:
        engine, mode = self._build()
        mode._fire(now=0.0)
        # Patient fumbles to lane 2 first, then hits the target (lane 0).
        mode._handle_press(self._press(lane=2, t=0.10), now=0.10)
        mode._handle_press(self._press(lane=0, t=0.20), now=0.20)
        engine.log_trial.assert_called_once()
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")
        self.assertEqual(outcome.points, 0)

    def test_multiple_wrong_then_correct_still_one_miss(self) -> None:
        # Mashing 3 wrong then the right one is still one trial; the
        # outcome must end up as a single Miss, not multiple.
        engine, mode = self._build()
        mode._fire(now=0.0)
        for wrong_lane, t in [(1, 0.05), (2, 0.10), (3, 0.15)]:
            mode._handle_press(self._press(lane=wrong_lane, t=t), now=t)
        mode._handle_press(self._press(lane=0, t=0.25), now=0.25)
        engine.log_trial.assert_called_once()
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")


class AdaptiveWrongPressMissTests(unittest.TestCase):
    """AdaptiveMode._handle_press -> _finish: same behaviour as
    classic, plus the adapter must see was_hit=False on a fumble-
    then-correct trial so the weakness bias fires for that finger."""

    def _build(self):
        from rehab.analytics.adaptive import AdaptiveConfig
        from rehab.game.modes.adaptive import AdaptiveMode
        from rehab.game.scoring import ScoreConfig
        engine = MagicMock()
        engine.cfg = MagicMock()
        engine.cfg.get = MagicMock(return_value=0)
        engine.apply_wrong_press_penalty = MagicMock(return_value=2)
        engine.apply_idle_press_penalty = MagicMock(return_value=0)
        engine.log_trial = MagicMock()
        engine.on_stim = MagicMock()
        ac = AdaptiveConfig(
            target_low=0.65, target_high=0.80,
            bpm_min=10.0, bpm_max=140.0,
            bpm_step=10.0, weakness_bias=2.5, min_trials=2,
        )
        mode = AdaptiveMode(
            engine=engine,
            num_lanes=4,
            total_trials=4,
            block_size=4,
            score_cfg=ScoreConfig(),
            timeout_s=1.0,
            early_window_s=0.1,
            start_bpm=30.0,
            adaptive_cfg=ac,
        )
        return engine, mode

    def _press(self, lane: int, t: float = 0.0):
        from rehab.hardware.fsr_detector import PressEvent
        return PressEvent(lane=lane, t_perf=t, value=0, baseline=0.0,
                            hand="right")

    def test_correct_press_logs_hit(self) -> None:
        engine, mode = self._build()
        mode._fire(now=0.0)
        target = mode.active.lane
        mode._handle_press(self._press(lane=target, t=0.15), now=0.15)
        outcome = engine.log_trial.call_args[0][1]
        self.assertNotEqual(outcome.label, "Miss")

    def test_wrong_then_correct_logs_miss_and_adapter_sees_miss(self) -> None:
        engine, mode = self._build()
        mode._fire(now=0.0)
        target = mode.active.lane
        wrong = (target + 1) % 4
        # Spy on the adapter's record() so we can check what hit-rate
        # signal it received.
        records: list = []
        original = mode.adapter.record
        def _spy(lane, was_hit, rt_ms, quality=None):
            records.append((lane, was_hit, rt_ms, quality))
            return original(lane, was_hit, rt_ms, quality=quality)
        mode.adapter.record = _spy
        mode._handle_press(self._press(lane=wrong, t=0.10), now=0.10)
        mode._handle_press(self._press(lane=target, t=0.20), now=0.20)
        outcome = engine.log_trial.call_args[0][1]
        self.assertEqual(outcome.label, "Miss")
        # Adapter must see was_hit=False for the target lane.
        self.assertEqual(len(records), 1)
        rec_lane, rec_hit, _, _ = records[0]
        self.assertEqual(rec_lane, target)
        self.assertFalse(rec_hit,
                          "Adapter must see a fumble-then-correct as a "
                          "MISS so the weakness bias fires on that lane")


if __name__ == "__main__":
    unittest.main()
