"""The EEG pictures in the lab README are drawn from the marker map.

scripts/make_eeg_cheat_sheet.py draws three pictures, dark and light:
how a number reaches the recording, where the numbers land in a lab
sitting, and what each number means. It reads every number from
finger_rehab/hardware/eeg_trigger.py, config/eeg_lab.yaml and the lab
sitting the game builds. A change to any of them without re-running it
would leave the lab reading an old code off a picture, so the committed
pictures must be exactly what the script draws today.
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

    def test_three_pictures_in_both_themes(self) -> None:
        self.assertEqual(set(self.mod.PICTURES), {
            "eeg_markers_how", "eeg_markers_where", "eeg_cheat_sheet"})
        self.assertEqual(set(self.mod.THEMES), {"dark", "light"})

    def test_the_committed_pictures_are_current(self) -> None:
        for name, draw in self.mod.PICTURES.items():
            for theme in self.mod.THEMES:
                with self.subTest(picture=name, theme=theme):
                    path = IMAGES / f"{name}_{theme}.svg"
                    self.assertEqual(
                        path.read_text(encoding="utf-8"), draw(theme),
                        f"{path.name} is stale: run "
                        f"python3 scripts/make_eeg_cheat_sheet.py")

    def test_the_cheat_sheet_numbers_come_from_the_map(self) -> None:
        from finger_rehab.hardware.eeg_trigger import (
            CODES, CODES_VERSION, MODE_IDS)
        text = self.mod.draw("dark")
        want = [CODES["prep_countdown"], CODES["prep_buzz_lead"],
                CODES["prep_run_start"], CODES["prep_segment_edge"],
                CODES["stim_visual"], CODES["stim_visual_tone"],
                CODES["stim_visual_buzz_tone"], CODES["stim_buzz_hunt"],
                CODES["resp_timeout"], CODES["resp_idle"],
                CODES["feedback_positive"], CODES["feedback_negative"],
                CODES["feedback_neutral"], CODES["session_start"],
                CODES["session_end"], CODES["pause"], CODES["resume"],
                CODES["rest_start"], CODES["rest_end"]]
        for base in ("resp_correct_base", "resp_wrong_base",
                     "resp_anticipation_base"):
            want += [CODES[base] + lane for lane in range(4)]
        for code in want:
            self.assertIn(f">{code}<", text)
        self.assertIn(f"map v{CODES_VERSION}", text)
        # Every game of the lab sitting has its start and end byte.
        for mode in set(self.mod.lab_sitting()):
            self.assertIn(f">{CODES['block_start_base'] + MODE_IDS[mode]}<",
                          text, mode)
            self.assertIn(f">{CODES['block_end_base'] + MODE_IDS[mode]}<",
                          text, mode)

    def test_the_sitting_is_the_one_the_lab_plays(self) -> None:
        games = self.mod.lab_sitting()
        # The lab's own task stands in for Reaction, once; no Muscle
        # Memory (config/eeg_lab.yaml).
        self.assertEqual(games[0], "srt")
        self.assertEqual(games.count("srt"), 1)
        self.assertNotIn("reaction", games)
        self.assertNotIn("pattern", games)

    def test_the_trial_is_a_lab_trial(self) -> None:
        """The trial drawn is one the lab sitting really sends: the cue,
        a correct ring-finger press and a full-ring result, in a game
        that sends result bytes in the lab."""
        from finger_rehab.hardware.eeg_trigger import CODES, MODE_IDS
        text = self.mod.draw_where("light")
        self.assertIn("chords", self.mod.lab_wire()["feedback"])
        self.assertIn("chords", self.mod.lab_sitting())
        for code in (CODES["stim_visual_buzz_tone"],
                     CODES["resp_correct_base"] + 2,
                     CODES["feedback_positive"],
                     CODES["prep_countdown"],
                     CODES["block_start_base"] + MODE_IDS["chords"],
                     CODES["block_end_base"] + MODE_IDS["chords"],
                     CODES["session_start"], CODES["session_end"]):
            self.assertIn(f">{code}<", text)
        # A lab sitting never plays the app's own Reaction block, so
        # its wait byte has no place in the lab's pictures.
        for name, draw in self.mod.PICTURES.items():
            self.assertNotIn(f">{CODES['prep_foreperiod']}<", draw("light"),
                             name)

    def test_the_wire_comes_from_the_lab_config(self) -> None:
        import yaml
        eeg = yaml.safe_load((APP / "config" / "eeg_lab.yaml").read_text(
            encoding="utf-8"))["eeg"]
        text = self.mod.draw_how("light")
        self.assertIn(f"held {eeg['pulse_ms']} ms", text)
        self.assertIn(f"an Arduino on {eeg['port']}", text)

    def test_plain_ascii_and_no_page_background(self) -> None:
        # The page shows through, so each theme sits on GitHub's own
        # background rather than a box of its own.
        for name, draw in self.mod.PICTURES.items():
            for theme in self.mod.THEMES:
                svg = draw(theme)
                self.assertTrue(svg.isascii(), (name, theme))
                self.assertNotIn(self.mod.THEMES[theme]["page"], svg,
                                 (name, theme))


if __name__ == "__main__":
    unittest.main()
