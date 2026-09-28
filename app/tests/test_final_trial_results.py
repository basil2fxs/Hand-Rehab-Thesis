"""FINAL TRIAL RESULTS: the study's checklist and its data folders.

The folder sits in a public repository and will hold participant data,
so the rule that matters most is that git never picks the data up:
only the folder's README and one README per subfolder may be shared.
The rest pins the layout the README walks through, and the house rules
every README here follows.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
FOLDER = REPO / "FINAL TRIAL RESULTS"
SUBFOLDERS = ("1 Healthy study", "2 Sensor comparison", "3 EEG lab",
              "4 Syllables case", "5 Thesis results")
BANNED_CHARS = ("\u2014", "\u2013", "\u00a7", "\u2018", "\u2019", "\u201c",
                "\u201d", "\u2026", "\u00a0")  # escapes, so this file stays ASCII
BANNED_WORDS = ("delve", "leverage", "robust", "seamless", "showcase",
                "crucial", "pivotal", "intricate", "testament", "foster",
                "comprehensive", "profound")


def _readmes() -> list[Path]:
    return [FOLDER / "README.md"] + [FOLDER / s / "README.md"
                                     for s in SUBFOLDERS]


class LayoutTests(unittest.TestCase):
    def test_every_subfolder_has_its_readme(self) -> None:
        for path in _readmes():
            self.assertTrue(path.is_file(), path)
            self.assertTrue(path.read_text(encoding="utf-8").strip(), path)

    def test_the_readme_walks_every_subfolder(self) -> None:
        text = (FOLDER / "README.md").read_text(encoding="utf-8")
        for sub in SUBFOLDERS:
            self.assertIn(sub, text)

    def test_local_links_point_at_something(self) -> None:
        for path in _readmes():
            text = path.read_text(encoding="utf-8")
            for target in re.findall(r"\]\((?!https?://|#)([^)#]+)", text):
                target = target.replace("%20", " ")
                with self.subTest(file=path.name, link=target):
                    self.assertTrue((path.parent / target).exists(), target)

    def test_house_rules(self) -> None:
        for path in _readmes():
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=str(path.relative_to(FOLDER))):
                for ch in BANNED_CHARS:
                    self.assertNotIn(ch, text)
                for word in BANNED_WORDS:
                    self.assertIsNone(
                        re.search(rf"\b{word}\b", text, re.I), word)


@unittest.skipUnless(shutil.which("git") and (REPO / ".git").exists(),
                     "needs the git checkout")
class PrivacyTests(unittest.TestCase):
    """What git would share from the folder, asked of git itself."""

    def _ignored(self, rel: str) -> bool:
        out = subprocess.run(["git", "check-ignore", "-q", rel], cwd=FOLDER,
                             capture_output=True)
        return out.returncode == 0

    def test_data_never_reaches_git(self) -> None:
        for rel in ("1 Healthy study/sessions/2026-10-01/P01_100000_"
                    "reaction/trials.csv",
                    "1 Healthy study/sessions/intake_sheet.csv",
                    "1 Healthy study/sessions/README.md",
                    "3 EEG lab/sessions/eeg/P07_2026-10-02.bdf",
                    "4 Syllables case/notes.txt",
                    "5 Thesis results/4.6/cohort_reliability.csv",
                    "consent scans.pdf"):
            with self.subTest(path=rel):
                self.assertTrue(self._ignored(rel), rel)

    def test_the_readmes_are_shared(self) -> None:
        for path in _readmes():
            rel = str(path.relative_to(FOLDER))
            with self.subTest(path=rel):
                self.assertFalse(self._ignored(rel), rel)


if __name__ == "__main__":
    unittest.main()
