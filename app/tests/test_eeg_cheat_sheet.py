"""The EEG picture in the lab README is drawn from the marker map.

scripts/make_eeg_cheat_sheet.py draws one cheat sheet, dark and light,
kept to what most games send: a finger lights up, the press, the
result and the numbers around each game (Basil, 1 October 2026:
the earlier single sheet, minimal, nothing single games add). It reads
every number from finger_rehab/hardware/eeg_trigger.py and
config/eeg_lab.yaml, so the committed pictures must be exactly what the
script draws today.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
IMAGES = APP / "docs" / "images"
README = APP.parent / "EEG_Lab" / "README.md"


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

    def test_one_picture_in_both_themes(self) -> None:
        self.assertEqual(set(self.mod.PICTURES), {"eeg_cheat_sheet"})
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

    def test_the_numbers_come_from_the_map(self) -> None:
        from finger_rehab.hardware.eeg_trigger import CODES
        text = self.mod.draw("dark")
        for code in (CODES["stim_visual_buzz_tone"],
                     CODES["resp_correct_base"] + self.mod.RING,
                     CODES["resp_timeout"], CODES["feedback_positive"],
                     CODES["feedback_negative"], CODES["prep_countdown"]):
            self.assertIn(f">{code}<", text)
        # 142 belongs to the delayed ring the lab build no longer draws
        # (5 October 2026), so the sheet leaves it out.
        self.assertNotIn(f">{CODES['feedback_neutral']}<", text)
        for base in ("resp_correct_base", "resp_wrong_base",
                     "resp_anticipation_base", "block_start_base",
                     "block_end_base"):
            self.assertIn(f">{CODES[base]}+<", text)
        self.assertIn(f">{CODES['stim_visual']} + 1 beep + 2 buzz<", text)

    def test_only_what_most_games_send(self) -> None:
        """No number that only one game, the lab's own task or the
        session sends: the full map is in markers_codes.csv."""
        from finger_rehab.hardware.eeg_trigger import CODES
        for theme in self.mod.THEMES:
            text = self.mod.draw(theme)
            for key in ("prep_foreperiod", "prep_buzz_lead",
                        "prep_run_start", "prep_segment_edge",
                        "stim_buzz_hunt", "resp_idle", "session_start",
                        "session_end", "pause", "resume",
                        "block_abandoned"):
                self.assertNotIn(f">{CODES[key]}<", text, (theme, key))

    def test_the_trial_is_one_the_lab_sends(self) -> None:
        """The result drawn is sent in the lab, by the games the note
        names."""
        feedback = self.mod.lab_feedback()
        text = self.mod.draw("light")
        names = [self.mod.GAME_NAMES[m] for m in feedback
                 if m in self.mod.GAME_NAMES and m != "reaction"]
        self.assertTrue(names)
        self.assertIn(" and ".join(names) + ".", text)

    def test_plain_ascii(self) -> None:
        for name, draw in self.mod.PICTURES.items():
            for theme in self.mod.THEMES:
                self.assertTrue(draw(theme).isascii(), (name, theme))

    def test_the_readme_shows_the_one_picture(self) -> None:
        text = README.read_text(encoding="utf-8")
        self.assertIn("eeg_cheat_sheet_dark.svg", text)
        self.assertIn("eeg_cheat_sheet_light.svg", text)
        self.assertNotIn("eeg_markers_how", text)
        self.assertNotIn("eeg_markers_where", text)


if __name__ == "__main__":
    unittest.main()
