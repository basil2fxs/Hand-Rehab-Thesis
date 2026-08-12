"""The pre-press buzzer cue: the motor under the TARGET finger buzzes
when that trial's stimulus fires, telling the patient which finger to
press. cue.buzz_before is the switch.

Rules this locks in:
  - it fires on the target lane(s) only, in every mode
  - a timeout or a wrong finger never drives a motor
  - the switch turns it off completely
  - cue length is built by repeating the firmware's fixed 150 ms pulse,
    because the sketch hardcodes drive strength and exposes no way to
    change it

The post-press confirmation buzz (cue.buzz_after) and the way the four
switches combine live in test_sensory_cues.py.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _engine(buzz_before=True, buzz_after=False, cue_ms=250):
    from finger_rehab.game.engine import GameEngine
    e = GameEngine.__new__(GameEngine)
    e.cfg = MagicMock()
    e.cfg.get = MagicMock(side_effect=lambda k, d=None: {
        "cue.buzz_before": buzz_before,
        "cue.buzz_after": buzz_after,
        "cue.sound_before": False,
        "cue.sound_after": False,
        "cue.show_target": True,
        "motor.cue_ms": cue_ms,
        "motor.pulse_interval_ms": 120,
        "game.timeout_s": 1.0,
        "fsr.num_sensors_per_hand": 4,
    }.get(k, d))
    sent = []
    src = MagicMock()
    src.send_command = lambda c: (sent.append(c) or True)
    e.source = src
    e._sent = sent
    e.hand_mode = "right"
    e.audio = None
    e.raw_logger = None
    e._screens = {}
    e.mode = None
    e.detectors = {}
    e._ensure_metric_state()
    return e


class CueFiresOnTargetTests(unittest.TestCase):
    def test_buzzes_the_target_finger(self) -> None:
        e = _engine()
        e.on_stim(lane=2, trial_id=1, t_perf=0.0)
        self.assertIn("STIM:3", e._sent)      # lane 2 -> motor 3

    def test_only_the_target_finger_buzzes(self) -> None:
        e = _engine()
        e.on_stim(lane=0, trial_id=1, t_perf=0.0)
        others = [c for c in e._sent if c not in ("STIM:1",)]
        self.assertEqual(others, [], f"unexpected commands: {others}")

    def test_mirror_mode_buzzes_both_targets(self) -> None:
        e = _engine()
        e.on_stim_multi([0, 5], trial_id=1, t_perf=0.0)
        self.assertIn("STIM:1", e._sent)
        self.assertIn("STIM:6", e._sent)

    def test_toggle_off_sends_nothing(self) -> None:
        e = _engine(buzz_before=False)
        e.on_stim(lane=1, trial_id=1, t_perf=0.0)
        self.assertEqual([c for c in e._sent if c.startswith("STIM")], [])


class NoOtherBuzzingTests(unittest.TestCase):
    """With cue.buzz_after off the buzzer only ever says which finger
    to press. Closing a trial must not drive a motor, whatever the
    outcome was."""

    def test_log_trial_never_sends_a_stim(self) -> None:
        from finger_rehab.game.modes.classic import PendingTrial
        from finger_rehab.game.scoring import TrialResult
        e = _engine()
        e.score = 0
        e.hits = 0
        e.misses = 0
        e.hit_streak = 0
        e.miss_streak = 0
        e._streak_fired = set()
        e._streak_thresholds = ()
        e._block_rt_sum = 0.0
        e._block_rt_count = 0
        e._block_bpm_min = None
        e._block_bpm_max = None
        e._block_wrong_press_trials = 0
        e._block_peak_streak = 0
        e._last_gained = 0
        e.current_block = "classic"
        e.trial_logger = None
        e.session_paths = None
        e.session = MagicMock()
        e.theme = MagicMock()
        e._per_lane_rts = {}
        e._per_lane_misses = {}
        e._per_lane_wrong = {}
        e._sent.clear()
        for label, rt in (("Great", 200.0), ("Miss", None)):
            e.log_trial(
                PendingTrial(trial_id=1, lane=0, stim_t_perf=0.0,
                              keys_pressed=[0], incorrect_presses=[]),
                TrialResult(label=label, points=0, rt_ms=rt), now=0.0)
        self.assertEqual([c for c in e._sent if c.startswith("STIM")], [],
                          "a motor fired on a press/hit/miss")


class CueLengthTests(unittest.TestCase):
    def test_single_pulse_when_cue_is_one_firmware_pulse(self) -> None:
        e = _engine(cue_ms=150)
        e.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertEqual(len(e._motor_queue), 0,
                          "150 ms should need no repeat pulses")

    def test_longer_cue_schedules_repeat_pulses(self) -> None:
        # The firmware holds 150 ms per command, so a 450 ms cue can
        # only be produced by re-arming the motor.
        e = _engine(cue_ms=450)
        e.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertGreater(len(e._motor_queue), 0)
        for lane, _due in e._motor_queue:
            self.assertEqual(lane, 0)

    def test_repeat_pulses_are_sent_when_due(self) -> None:
        import time
        e = _engine(cue_ms=450)
        e.on_stim(lane=1, trial_id=1, t_perf=0.0)
        e._sent.clear()
        # Force everything due, then drain.
        e._motor_queue = [(lane, time.perf_counter() - 1.0)
                          for lane, _ in e._motor_queue]
        e._drain_motor_queue()
        self.assertTrue(all(c == "STIM:2" for c in e._sent), e._sent)
        self.assertEqual(e._motor_queue, [])

    def test_stop_all_motors_clears_queue_and_sends_stop(self) -> None:
        e = _engine(cue_ms=450)
        e.on_stim(lane=0, trial_id=1, t_perf=0.0)
        e._sent.clear()
        e.stop_all_motors()
        self.assertEqual(e._motor_queue, [])
        self.assertIn("STOP", e._sent)

    def test_pulse_gap_stays_under_the_firmware_hold(self) -> None:
        # A gap longer than the firmware's 150 ms hold would make the
        # motor stutter instead of running continuously.
        e = _engine(cue_ms=450)
        e.cfg.get = MagicMock(side_effect=lambda k, d=None: {
            "motor.cue_ms": 450, "motor.pulse_interval_ms": 500,
        }.get(k, d))
        e._motor_queue = []
        e._schedule_cue_pulses(0)
        if len(e._motor_queue) >= 2:
            gap = (e._motor_queue[1][1] - e._motor_queue[0][1]) * 1000
            self.assertLess(gap, e.FIRMWARE_STIM_MS)


class ConfigDefaultsTests(unittest.TestCase):
    def test_cue_on_by_default(self) -> None:
        # Read default.yaml, not Config.load(): the merged config picks
        # up whatever this machine's user_settings.yaml happens to say,
        # and the claim here is about what ships.
        import yaml
        from finger_rehab.config import DEFAULT_CONFIG
        with open(DEFAULT_CONFIG) as f:
            shipped = yaml.safe_load(f)
        self.assertIs(shipped["cue"]["buzz_before"], True)

    def test_cue_length_within_researched_range(self) -> None:
        # ~30 ms is the floor for a vibration to be perceived as such;
        # cueing studies use bursts up to about 400 ms, beyond which the
        # cue starts overlapping the patient's own response.
        from finger_rehab.config import Config
        ms = int(Config.load().get("motor.cue_ms"))
        self.assertGreaterEqual(ms, 150)
        self.assertLessEqual(ms, 450)

    def test_pulse_interval_under_firmware_hold(self) -> None:
        from finger_rehab.config import Config
        self.assertLess(int(Config.load().get("motor.pulse_interval_ms")), 150)


if __name__ == "__main__":
    unittest.main()
