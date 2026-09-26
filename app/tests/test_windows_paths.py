"""Every tracked file can be checked out on Windows.

The lab PC and one of the two installers are Windows, and git there
refuses a path Windows cannot hold: con.wav (con of confidence) broke
the build at checkout, before a single test ran. Windows keeps
device names whatever the extension, forbids a handful of characters,
drops a trailing dot or space, and cannot hold two names that differ
only in case.
"""
from __future__ import annotations

import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finger_rehab.game.modes.syllables_words import (  # noqa: E402
    WINDOWS_DEVICE_NAMES, speech_stem)

BAD_CHARS = re.compile(r'[<>:"|?*\\\x00-\x1f]')


def _tracked() -> list[str]:
    try:
        out = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT.parent,
                             capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return []
    return [p for p in out.stdout.split("\0") if p]


class TrackedPathsTests(unittest.TestCase):

    def setUp(self):
        self.paths = _tracked()
        if not self.paths:
            self.skipTest("not a git checkout")

    def test_no_part_is_a_windows_device_name(self):
        bad = [p for p in self.paths
               if any(part.split(".")[0].lower() in WINDOWS_DEVICE_NAMES
                      for part in p.split("/"))]
        self.assertEqual(bad, [])

    def test_no_character_windows_forbids(self):
        bad = [p for p in self.paths
               if any(BAD_CHARS.search(part) or part.endswith((".", " "))
                      for part in p.split("/"))]
        self.assertEqual(bad, [])

    def test_no_two_paths_differ_only_in_case(self):
        seen: dict[str, str] = {}
        clashes = []
        for p in self.paths:
            other = seen.setdefault(p.lower(), p)
            if other != p:
                clashes.append((other, p))
        self.assertEqual(clashes, [])


class SpeechStemTests(unittest.TestCase):

    def test_a_device_name_takes_an_underscore(self):
        for name in ("con", "prn", "aux", "nul", "com1", "lpt9", "CON"):
            with self.subTest(name=name):
                self.assertEqual(speech_stem(name), name + "_")

    def test_everything_else_is_left_alone(self):
        for name in ("ven", "cons", "econ", "com", "tiger"):
            with self.subTest(name=name):
                self.assertEqual(speech_stem(name), name)


if __name__ == "__main__":
    unittest.main()
