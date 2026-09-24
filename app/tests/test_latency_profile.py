"""app/config/latency_profile.yaml is this machine's measured sound and
buzz delays (scripts/audio_latency.py --write). The game lays it over
default.yaml at every start, the lab preset included; a hand-set value
in user_settings.yaml still wins; it can only set the delay keys; and
a broken file is ignored, never fatal."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class LatencyProfileTests(unittest.TestCase):

    def _load(self, profile_text, user_text=None, override=None):
        import finger_rehab.config as config
        with tempfile.TemporaryDirectory() as td:
            prof = Path(td) / "latency_profile.yaml"
            if profile_text is not None:
                prof.write_text(profile_text)
            user = Path(td) / "user_settings.yaml"
            if user_text is not None:
                user.write_text(user_text)
            with mock.patch.object(config, "LATENCY_PROFILE", prof), \
                    mock.patch.object(config, "USER_OVERRIDES", user):
                return config.Config.load(override)

    PROFILE = ("latency:\n  measured: true\n  measured_on: '2026-09-24'\n"
               "  tone_ms: 77\n  buzzer_ms: 74\n"
               "rhythm:\n  audio_offset_ms: 87\n  metronome_offset_ms: 77\n")

    def test_the_measured_delays_replace_the_estimates(self):
        c = self._load(self.PROFILE)
        self.assertEqual(c.get("rhythm.audio_offset_ms"), 87)
        self.assertEqual(c.get("rhythm.metronome_offset_ms"), 77)
        self.assertEqual(c.get("latency.tone_ms"), 77)
        self.assertEqual(c.get("latency.buzzer_ms"), 74)
        self.assertTrue(c.get("latency.measured"))
        # Everything else in the sections is still default.yaml's.
        self.assertEqual(c.get("latency.visual_ms"), 20)
        self.assertEqual(c.get("rhythm.tactile_mode"), "lead")

    def test_the_lab_preset_gets_them_too(self):
        c = self._load(self.PROFILE, override=ROOT / "config" /
                       "eeg_lab.yaml")
        self.assertEqual(c.get("rhythm.audio_offset_ms"), 87)
        self.assertTrue(c.get("eeg.enabled"))

    def test_a_hand_set_value_still_wins(self):
        c = self._load(self.PROFILE, user_text="rhythm:\n  "
                                               "audio_offset_ms: 60\n")
        self.assertEqual(c.get("rhythm.audio_offset_ms"), 60)
        self.assertEqual(c.get("latency.buzzer_ms"), 74)

    def test_it_can_only_set_the_delay_keys(self):
        c = self._load(self.PROFILE + "  tactile_mode: feedback\n"
                       "game:\n  test_mode_enabled: true\n")
        self.assertEqual(c.get("rhythm.tactile_mode"), "lead")
        self.assertFalse(c.get("game.test_mode_enabled"))

    def test_no_file_and_a_broken_file_leave_the_defaults(self):
        for text in (None, "latency: [unclosed\n", "just a string\n"):
            c = self._load(text)
            self.assertEqual(c.get("rhythm.audio_offset_ms"), 40)
            self.assertFalse(c.get("latency.measured"))


class MotorOnsetMathTests(unittest.TestCase):

    def test_the_averaged_onset_finds_a_quiet_start(self):
        import numpy as np
        sys.path.insert(0, str(ROOT / "scripts"))
        import audio_latency as al
        sr = al.SR
        rng = np.random.default_rng(3)
        data = rng.normal(0, 0.01, 12 * sr).astype(np.float32)
        cmds, t0 = [], 50.0
        for k in range(10):
            tc = 1.0 + k * 1.0
            cmds.append(t0 + tc)
            i = int((tc + 0.070) * sr)             # sound 70 ms after
            ramp = np.linspace(0, 1, int(0.06 * sr))
            buzz = np.sin(2 * np.pi * 180 * np.arange(len(ramp)) / sr)
            data[i:i + len(ramp)] += (0.2 * ramp * buzz).astype(np.float32)
        on = al.averaged_onset_ms(data, t0, cmds)
        self.assertIsNotNone(on)
        self.assertAlmostEqual(on, 70.0, delta=6.0)


if __name__ == "__main__":
    unittest.main()
