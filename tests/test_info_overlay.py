"""Tests for the home-screen Info overlay. Clicking the Info pill opens
a modal protocol card; while it is open the screen is modal (a click does
not start a session); a click or Esc closes it. The protocol text must
name all four game modes so a therapist running a trial knows the order
and counts that keep every participant's data set comparable."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class InfoOverlayTests(unittest.TestCase):
    def _title_screen(self):
        import pygame
        pygame.init()
        pygame.font.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["audio"]["enabled"] = False
        pygame.display.set_mode((1280, 800))
        eng = GameEngine(cfg, KeyboardOnlySource())
        eng._screens = eng._build_screens()
        return eng, eng._screens["title"]

    def _click(self, ts, pos):
        import pygame
        ts.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, button=1, pos=pos))

    def test_starts_closed(self):
        _, ts = self._title_screen()
        self.assertFalse(ts._show_info)

    def test_info_click_opens_overlay(self):
        _, ts = self._title_screen()
        self._click(ts, ts.info_rect.center)
        self.assertTrue(ts._show_info)

    def test_esc_closes_overlay(self):
        import pygame
        _, ts = self._title_screen()
        ts._show_info = True
        ts.handle_event(pygame.event.Event(
            pygame.KEYDOWN, key=pygame.K_ESCAPE))
        self.assertFalse(ts._show_info)

    def test_click_closes_overlay(self):
        _, ts = self._title_screen()
        ts._show_info = True
        self._click(ts, (10, 10))
        self.assertFalse(ts._show_info)

    def test_overlay_is_modal_click_does_not_start_session(self):
        eng, ts = self._title_screen()
        ts._show_info = True
        before = eng.screen_obj
        # A click on the START button while the overlay is open must be
        # swallowed (overlay closes, no navigation to mode select).
        self._click(ts, ts.start_btn.rect.center)
        self.assertIs(eng.screen_obj, before)
        self.assertFalse(ts._show_info)

    def test_protocol_text_names_all_four_modes(self):
        # Reaction replaced Classic as the baseline core mode, so the
        # session protocol the overlay teaches names reaction first.
        _, ts = self._title_screen()
        blob = " ".join(ts.INFO_STEPS).lower()
        for mode in ("reaction", "adaptive", "rhythm", "mirror"):
            self.assertIn(mode, blob)

    def test_protocol_renders_without_error(self):
        import pygame
        _, ts = self._title_screen()
        ts._show_info = True
        surf = pygame.Surface((1280, 800))
        ts.draw(surf)  # must not raise


if __name__ == "__main__":
    unittest.main()
