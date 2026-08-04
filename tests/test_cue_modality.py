"""Cue modality: visual only, vibration only, or both.

This is the comparison the project line started from. Palmer (2024)
found reaction time differed between an LED-only cue and all cues
together, and the 2023 device existed to test it. Until this was added
the buzzer fired on every trial in every mode, so there was no contrast
left to measure.

What each mode must do:
  both       screen reveals the finger AND the motor buzzes
  visual     screen reveals it, motor stays silent
  vibration  motor buzzes, screen does NOT reveal the finger
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


class _Lane:
    """Stand-in for a LaneStrip: only the bits on_stim_multi touches."""

    def __init__(self, lane):
        self.lane = lane
        self.active = False
        self.timing_armed = False

    def arm_timing(self, *_):
        self.timing_armed = True

    def clear_timing(self):
        self.timing_armed = False


def _engine(cue_mode="both", motors=True):
    from rehab.game.engine import GameEngine
    e = GameEngine.__new__(GameEngine)
    sent = []
    e.cfg = MagicMock()
    e.cfg.get = MagicMock(side_effect=lambda k, d=None: {
        "game_cue.mode": cue_mode,
        "motor.enabled": motors,
        "motor.cue_ms": 250,
        "motor.pulse_interval_ms": 120,
        "game.timeout_s": 1.0,
        "audio.stim_tone_enabled": False,
        "fsr.num_sensors_per_hand": 4,
    }.get(k, d))
    src = MagicMock()
    src.send_command = lambda c: (sent.append(c) or True)
    e.source = src
    e._sent = sent
    gp = MagicMock()
    gp.lanes = [_Lane(i) for i in range(4)]
    e._screens = {"gameplay": gp}
    e._lanes = gp.lanes
    e.hand_mode = "right"
    e.audio = None
    e.raw_logger = None
    e.mode = None
    e.detectors = {}
    e._ensure_metric_state()
    return e


class CueModalityTests(unittest.TestCase):
    def test_both_shows_and_buzzes(self) -> None:
        e = _engine("both")
        e.on_stim(lane=2, trial_id=1, t_perf=0.0)
        self.assertTrue(e._lanes[2].active, "screen did not reveal the finger")
        self.assertIn("STIM:3", e._sent, "motor did not buzz")

    def test_visual_shows_but_stays_silent(self) -> None:
        e = _engine("visual")
        e.on_stim(lane=2, trial_id=1, t_perf=0.0)
        self.assertTrue(e._lanes[2].active, "screen did not reveal the finger")
        self.assertEqual([c for c in e._sent if c.startswith("STIM")], [],
                          "motor buzzed in visual-only mode")

    def test_vibration_buzzes_but_hides_the_finger(self) -> None:
        e = _engine("vibration")
        e.on_stim(lane=2, trial_id=1, t_perf=0.0)
        self.assertIn("STIM:3", e._sent, "motor did not buzz")
        self.assertFalse(e._lanes[2].active,
                          "screen revealed the finger in vibration-only mode")

    def test_timing_bar_still_runs_in_vibration_only(self) -> None:
        # The patient must still see how long they have left, even when
        # the tile is not allowed to say which finger it is.
        e = _engine("vibration")
        e.on_stim(lane=1, trial_id=1, t_perf=0.0)
        self.assertTrue(e._lanes[1].timing_armed)

    def test_unknown_mode_falls_back_to_both(self) -> None:
        e = _engine("nonsense")
        e.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertTrue(e._lanes[0].active)
        self.assertIn("STIM:1", e._sent)
        self.assertEqual(e._last_cue_mode, "both")

    def test_mode_recorded_for_the_trial(self) -> None:
        for mode in ("both", "visual", "vibration"):
            with self.subTest(mode=mode):
                e = _engine(mode)
                e.on_stim(lane=0, trial_id=1, t_perf=0.0)
                self.assertEqual(e._last_cue_mode, mode)

    def test_visual_mode_ignores_the_motor_toggle(self) -> None:
        # Motors on but cue set to visual: still silent.
        e = _engine("visual", motors=True)
        e.on_stim(lane=3, trial_id=1, t_perf=0.0)
        self.assertEqual([c for c in e._sent if c.startswith("STIM")], [])


class CueModeColumnTests(unittest.TestCase):
    def test_column_registered(self) -> None:
        from rehab.data.logger import TRIAL_COLUMNS
        self.assertIn("cue_mode", TRIAL_COLUMNS)

    def test_default_is_both(self) -> None:
        # Read default.yaml directly. Config.load() merges
        # user_settings.yaml on top, and this assertion is about what
        # the software ships with, not what a local override says.
        import yaml
        from rehab.config import DEFAULT_CONFIG
        with open(DEFAULT_CONFIG) as f:
            shipped = yaml.safe_load(f)
        self.assertEqual(shipped["game_cue"]["mode"], "both")


if __name__ == "__main__":
    unittest.main()
