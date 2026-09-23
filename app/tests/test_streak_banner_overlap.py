"""Streak banners: rare, one at a time, and never over the targets.

Banners come only with a big streak (10, 20, 30, 50, 75, 100 in a
row), ten or more apart, so a message is an occasion rather than
something on every few presses. Only one is ever on screen: the
newest count is the true one, so an older banner retires when a new
one arrives. And a banner sits on blank page, below the tiles, where
it cannot cover the thing the player is aiming at.

Driven through the real GameEngine and the real screens, on both
screens that carry banners.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _engine(cfg_tweak=None):
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["audio"]["enabled"] = False
    if cfg_tweak:
        cfg_tweak(cfg)
    return GameEngine(cfg, KeyboardOnlySource())


def _banners(screen):
    return [p for p in screen._popups
            if p.alive and getattr(p, "is_banner", False)]


class StreakBannerTests(unittest.TestCase):

    def setUp(self) -> None:
        import pygame
        pygame.init()
        self.addCleanup(pygame.quit)

    def test_twenty_hits_leave_one_readable_banner_on_the_lane_strip(self):
        """Crossing 10 and 20 inside one banner lifetime leaves one."""
        from finger_rehab.ui.screens import GameplayScreen
        eng = _engine()
        screen = GameplayScreen(eng)
        eng._screens["gameplay"] = screen
        for _ in range(20):
            eng._update_streak(True, "gameplay")
        live = _banners(screen)
        self.assertEqual(len(live), 1,
                         f"banners on screen: {[p.text for p in live]}")
        # The newest count, not the stale one.
        self.assertEqual(live[0].text, eng._ENCOURAGEMENT[20])

    def test_rhythm_screen_holds_one_banner_too(self) -> None:
        from finger_rehab.ui.screens import RhythmScreen
        eng = _engine()
        screen = RhythmScreen(eng)
        eng._screens["rhythm"] = screen
        for _ in range(20):
            eng._update_streak(True, "rhythm")
        live = _banners(screen)
        self.assertEqual(len(live), 1,
                         f"banners on screen: {[p.text for p in live]}")
        self.assertEqual(live[0].text, eng._ENCOURAGEMENT[20])

    def test_nothing_before_ten(self) -> None:
        from finger_rehab.ui.screens import GameplayScreen
        eng = _engine()
        screen = GameplayScreen(eng)
        eng._screens["gameplay"] = screen
        for _ in range(9):
            eng._update_streak(True, "gameplay")
        self.assertEqual(_banners(screen), [])

    def test_a_banner_never_retires_a_lane_popup(self) -> None:
        """Only banners share the strip. A popup above a lane is a
        different thing at a different place and must survive a streak
        threshold landing on the same frame."""
        from finger_rehab.ui.screens import GameplayScreen
        eng = _engine()
        screen = GameplayScreen(eng)
        eng._screens["gameplay"] = screen
        import time
        screen.flash_lane(1, (0, 200, 0), 0.4, time.perf_counter(),
                          popup_text="Spot on")
        for _ in range(10):
            eng._update_streak(True, "gameplay")
        texts = [p.text for p in screen._popups if p.alive]
        self.assertIn("Spot on", texts)
        self.assertEqual(len(_banners(screen)), 1)

    def test_the_thresholds_are_at_least_ten_apart(self) -> None:
        """One message per ten trials at most."""
        from finger_rehab.game.engine import GameEngine
        steps = sorted(GameEngine._ENCOURAGEMENT)
        self.assertGreaterEqual(steps[0], 10)
        gaps = [b - a for a, b in zip(steps, steps[1:])]
        self.assertGreaterEqual(min(gaps), 10)

    def test_banners_sit_below_the_tiles(self) -> None:
        """On blank page: under the lane tiles on the cadence screen,
        under the strike tiles on the rhythm screen, and they do not
        rise back into them."""
        from finger_rehab.ui.screens import GameplayScreen, RhythmScreen
        eng = _engine()
        gp = GameplayScreen(eng)
        rs = RhythmScreen(eng)
        eng._screens["gameplay"] = gp
        eng._screens["rhythm"] = rs
        gp.add_encouragement("10 in a row")
        rs.add_encouragement("10 in a row")
        for screen in (gp, rs):
            (banner,) = _banners(screen)
            tiles_bottom = max(ls.rect.bottom for ls in screen.lanes)
            self.assertGreater(banner.start_pos[1] - 20, tiles_bottom)
            self.assertEqual(banner.rise_px, 0)


if __name__ == "__main__":
    unittest.main()
