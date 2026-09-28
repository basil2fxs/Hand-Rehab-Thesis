"""The EEG cheat sheet in the lab README is drawn from the marker map.

scripts/make_eeg_cheat_sheet.py reads every number from
finger_rehab/hardware/eeg_trigger.py and config/eeg_lab.yaml. A change
to either without re-running it would leave the lab reading an old
code off the picture, so the committed pictures must be exactly what
the script draws today.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
IMAGES = APP / "docs" / "images"


def _script():
    spec = importlib.util.spec_from_file_location(
        "make_eeg_cheat_sheet", APP / "scripts" / "make_eeg_cheat_sheet.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class CheatSheetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.mod = _script()

    def test_the_committed_pictures_are_current(self) -> None:
        for theme in ("dark", "light"):
            with self.subTest(theme=theme):
                path = IMAGES / f"eeg_cheat_sheet_{theme}.svg"
                self.assertEqual(
                    path.read_text(encoding="utf-8"), self.mod.draw(theme),
                    f"{path.name} is stale: run "
                    f"python3 scripts/make_eeg_cheat_sheet.py")

    def test_the_numbers_come_from_the_map(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (
            CODES, CODES_VERSION, MODE_IDS)
        text = self.mod.draw("dark")
        want = [
            f">{CODES['prep_foreperiod']}<",
            f">{CODES['stim_visual_buzz_tone']}<",
            f">{CODES['resp_correct_base']}+<",
            f">{CODES['resp_wrong_base']}+<",
            f">{CODES['resp_anticipation_base']}+<",
            f">{CODES['resp_timeout']}<",
            f">{CODES['feedback_positive']}<",
            f">{CODES['session_end']}<",
            f">{CODES['block_start_base'] + MODE_IDS['srt']}<",
            f">{CODES['block_end_base'] + MODE_IDS['srt']}<",
            f"map v{CODES_VERSION}",
        ]
        for needle in want:
            self.assertIn(needle, text)

    def test_the_wire_comes_from_the_lab_config(self) -> None:
        import yaml
        eeg = yaml.safe_load((APP / "config" / "eeg_lab.yaml").read_text(
            encoding="utf-8"))["eeg"]
        text = self.mod.draw("light")
        self.assertIn(f"held {eeg['pulse_ms']} ms", text)
        self.assertIn(f"{eeg['port']}, {eeg['baud']} baud", text)

    def test_plain_ascii(self) -> None:
        for theme in ("dark", "light"):
            self.assertTrue(self.mod.draw(theme).isascii(), theme)


if __name__ == "__main__":
    unittest.main()
