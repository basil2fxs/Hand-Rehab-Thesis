"""The root README is the only front door this repo has.

One thing is pinned here above all: the game table lists every mode the
hub offers. A mode added to ModeSelectScreen.MODES and not to the
README is a mode nobody outside the code knows exists, and that is
exactly the drift a README picks up first. The rest of the checks are
cheap guards on the things that rot silently: the file the hub
screenshot points at, links to files that were moved, and the plain
ASCII house rule.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
README = REPO / "README.md"
# The house rule bans these outright. The em dash and the section sign
# are the two that keep coming back from pasted text.
# Written as escapes so this file is itself plain ASCII.
BANNED_CHARS = (
    "\u2014"  # em dash
    "\u2013"  # en dash
    "\u00a7"  # section sign
    "\u2018\u2019\u201c\u201d"  # curly quotes
    "\u2026"  # ellipsis
    "\u00a0"  # non-breaking space
)


def _readme() -> str:
    return README.read_text(encoding="utf-8")


class ReadmeExistsTests(unittest.TestCase):

    def test_markdown_not_plain_text(self):
        """GitHub renders .md and not .txt, which is the whole reason
        the old README.txt was replaced."""
        self.assertTrue(README.is_file(), "README.md is missing")
        self.assertFalse((REPO / "README.txt").exists(),
                         "README.txt came back; README.md replaced it")

    def test_it_stays_short(self):
        lines = _readme().splitlines()
        self.assertLess(len(lines), 120,
                        f"README is {len(lines)} lines; keep it under 120")


class EveryLiveModeIsListedTests(unittest.TestCase):
    """The hub's own MODES table is the source of truth."""

    def _titles(self) -> list[str]:
        from finger_rehab.ui.screens import ModeSelectScreen
        return [title for _key, title, _desc in ModeSelectScreen.MODES]

    def test_every_hub_mode_has_a_readme_row(self):
        text = _readme()
        for title in self._titles():
            with self.subTest(mode=title):
                self.assertIn(f"| **{title}** |", text,
                              f"the README game table is missing {title}")

    def test_the_table_lists_nothing_extra(self):
        """A mode retired from the hub has to leave the table too, or
        the README advertises a game that cannot be picked."""
        rows = re.findall(r"^\| \*\*(.+?)\*\* \|", _readme(), re.M)
        self.assertEqual(sorted(rows), sorted(self._titles()))

    def test_one_line_each(self):
        for row in re.findall(r"^\| \*\*.+?\*\* \| (.+?) \|$",
                              _readme(), re.M):
            self.assertLessEqual(len(row), 100,
                                 f"table row runs long: {row[:40]}...")


class LinksAndImagesResolveTests(unittest.TestCase):

    def _targets(self) -> list[str]:
        text = _readme()
        # Markdown images and links, plus the src/href of the raw HTML
        # header block. Anything starting with a scheme is external.
        found = re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text)
        found += re.findall(r'(?:src|href)="([^"]+)"', text)
        return [t for t in found
                if not t.startswith(("http://", "https://", "#"))]

    def test_the_hero_screenshot_is_committed(self):
        shot = REPO / "docs" / "images" / "hub.png"
        self.assertTrue(shot.is_file(),
                        "docs/images/hub.png is missing; the README "
                        "opens with it")
        self.assertIn("docs/images/hub.png", _readme())

    def test_every_local_link_points_at_something(self):
        for target in self._targets():
            with self.subTest(target=target):
                self.assertTrue((REPO / target).exists(),
                                f"README links to {target}, which is gone")


class HouseStyleTests(unittest.TestCase):

    def test_plain_ascii(self):
        for path in (README, REPO / "assets" / "music" / "README.md",
                     REPO / "assets" / "icons" / "README.md"):
            text = path.read_text(encoding="utf-8")
            for ch in BANNED_CHARS:
                with self.subTest(file=path.name, char=hex(ord(ch))):
                    self.assertNotIn(ch, text)


if __name__ == "__main__":
    unittest.main()
