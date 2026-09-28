"""CONTRIBUTING.md is the whole loop for someone new: clone, run, test,
build, release. Every path and command it names must still exist, or
the first thing a newcomer meets is a step that fails. The release it
describes is the one the workflow really does.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path
from urllib.parse import unquote

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "app"
GUIDE = REPO / "CONTRIBUTING.md"
WORKFLOW = REPO / ".github" / "workflows" / "build-apps.yml"


class ContributingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.text = GUIDE.read_text(encoding="utf-8")

    def test_plain_ascii(self) -> None:
        self.assertTrue(self.text.isascii())

    def test_links_resolve(self) -> None:
        for target in re.findall(r"\]\((?!https?://|#)([^)#]+)", self.text):
            with self.subTest(link=target):
                self.assertTrue((REPO / unquote(target)).exists(), target)

    def test_named_files_exist(self) -> None:
        # A whole path in backticks, at least one folder deep: from the
        # top (app/..., .github/...) or, in the generated-files table,
        # from app/. Bare file names and commands are left to the other
        # tests.
        for path in re.findall(r"`((?:[\w.-]+/)+[\w.-]+\.(?:py|sh|bat|yml|"
                               r"yaml|spec|txt|ipynb|command))`", self.text):
            with self.subTest(path=path):
                self.assertTrue((REPO / path).exists()
                                or (APP / path).exists(), path)

    def test_commands_name_real_scripts(self) -> None:
        for script in re.findall(r"python3? ((?:scripts|builds)/\w+\.py)",
                                 self.text):
            with self.subTest(script=script):
                self.assertTrue((APP / script).is_file(), script)

    def test_the_release_it_describes_is_the_workflow(self) -> None:
        ci = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("release:", ci)
        self.assertIn("needs: [test, build]", ci)
        self.assertIn("builds/release_notes.py", ci)
        self.assertIn("SOFTWARE_VERSION", self.text)
        for name in ("FingerRehab-Setup-Windows.exe", "FingerRehab-macOS.dmg",
                     "FingerRehab-EEGLab.zip"):
            with self.subTest(file=name):
                self.assertIn(name, self.text)
                self.assertIn(name, ci)


class ReleaseNotesTests(unittest.TestCase):
    def test_notes_name_every_file_and_the_commit(self) -> None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "release_notes", APP / "builds" / "release_notes.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        notes = mod.notes("4.0", "0123456789abcdef", when="2026-09-28 04:00 UTC")
        self.assertTrue(notes.isascii())
        self.assertIn("Finger Rehab 4.0", notes)
        self.assertIn("[0123456](", notes)
        for name, _what in mod.FILES:
            self.assertIn(f"`{name}`", notes)
        self.assertIn("Windows protected your PC", notes)
        self.assertIn("Open Anyway", notes)


if __name__ == "__main__":
    unittest.main()
