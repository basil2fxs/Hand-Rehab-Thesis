"""The Auto-start switch in Settings follows the same location rule
as the launch-time sync: a copy running from the disk image or from
App Translocation must not register that path, because launchd would
run it after the image is ejected. The title screen already says to
drag the app into Applications; the switch has to say the same rather
than quietly register a path that dies with the image.
"""
from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from finger_rehab.hardware import autostart  # noqa: E402

DMG = "/Volumes/Finger Rehab/Finger Rehab.app/Contents/MacOS/Finger Rehab"
INSTALLED = "/Applications/Finger Rehab.app/Contents/MacOS/Finger Rehab"


class SwitchLocationTests(unittest.TestCase):

    def setUp(self):
        if sys.platform != "darwin":
            self.skipTest("the disk image rule is a macOS one")
        import pygame
        pygame.init()
        pygame.font.init()
        self.addCleanup(pygame.quit)
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.plist = Path(self.tmp.name) / "a.plist"
        orig = autostart.agent_plist_path
        autostart.agent_plist_path = lambda: self.plist
        self.addCleanup(setattr, autostart, "agent_plist_path", orig)
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        from finger_rehab.ui.screens import DiagnosticsScreen
        cfg = Config.load()
        cfg.data.setdefault("ui", {})["resolution"] = [1280, 800]
        self.engine = GameEngine(cfg, KeyboardOnlySource())
        self.screen = DiagnosticsScreen(self.engine)
        self.calls: list[list[str]] = []

        def runner(cmd):
            self.calls.append(list(cmd))
            return subprocess.CompletedProcess(cmd, 0, "", "")

        self.screen._autostart_runner = runner
        self.screen._autostart_on = self.screen._read_autostart()
        self.screen.rebuild_panel()

    def _button(self):
        hits = [b for b in self.screen._panel_buttons
                if b.label.startswith("Auto-start")]
        self.assertEqual(len(hits), 1)
        return hits[0]

    def _press_as_frozen_copy_at(self, exe: str):
        with patch.object(sys, "frozen", True, create=True), \
                patch.object(sys, "executable", exe):
            self._button().on_click()

    def test_from_the_disk_image_it_refuses_and_says_drag(self):
        self._press_as_frozen_copy_at(DMG)
        self.assertFalse(self.plist.exists())
        self.assertEqual(self._button().label, "Auto-start: off")
        self.assertIn("Applications", self.screen._port_status)
        self.assertEqual(self.calls, [], "launchctl was called")

    def test_from_a_translocated_copy_it_refuses(self):
        self._press_as_frozen_copy_at(
            "/private/var/folders/ab/T/AppTranslocation/1234/d/"
            "Finger Rehab.app/Contents/MacOS/Finger Rehab")
        self.assertFalse(self.plist.exists())
        self.assertEqual(self._button().label, "Auto-start: off")

    def test_from_applications_it_registers_that_path(self):
        self._press_as_frozen_copy_at(INSTALLED)
        self.assertEqual(self._button().label, "Auto-start: on")
        self.assertEqual(autostart.registered_command(), [INSTALLED, "--watch"])

    def test_a_source_checkout_still_registers(self):
        self._button().on_click()
        self.assertEqual(self._button().label, "Auto-start: on")
        self.assertEqual(autostart.registered_command(),
                         autostart.watcher_command())


if __name__ == "__main__":
    unittest.main()
