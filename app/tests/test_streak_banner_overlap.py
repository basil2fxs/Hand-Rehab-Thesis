"""Only one streak banner is ever on screen at once.

The encouragement thresholds sit two trials apart at the bottom of
GameEngine._ENCOURAGEMENT (3 then 5), and a banner lives for 1.8 s at a
FIXED point on the strip. At rhythm's cadence two notes take about a
second, so the "5 in a row, nice" banner used to be added while
"3 in a row" was still alive, at the same centre, and pygame drew both:
the strip read as one unreadable smear rather than a count.

The count is the whole point of process praise (Mueller and Dweck 1998,
J Pers Soc Psychol: praise the doing, not the person), so a banner that
cannot be read is worse than no banner. The newest count is the true
one, so an older banner retires when a new one arrives.

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

    def test_six_hits_leave_one_readable_banner_on_the_lane_strip(self):
        """Crossing 3 and 5 inside one banner lifetime leaves one."""
        from finger_rehab.ui.screens import GameplayScreen
        eng = _engine()
        screen = GameplayScreen(eng)
        eng._screens["gameplay"] = screen
        for _ in range(6):
            eng._update_streak(True, "gameplay")
        live = _banners(screen)
        self.assertEqual(len(live), 1,
                         f"banners on screen: {[p.text for p in live]}")
        # The newest count, not the stale one.
        self.assertEqual(live[0].text, eng._ENCOURAGEMENT[5])

    def test_rhythm_screen_holds_one_banner_too(self) -> None:
        from finger_rehab.ui.screens import RhythmScreen
        eng = _engine()
        screen = RhythmScreen(eng)
        eng._screens["rhythm"] = screen
        for _ in range(6):
            eng._update_streak(True, "rhythm")
        live = _banners(screen)
        self.assertEqual(len(live), 1,
                         f"banners on screen: {[p.text for p in live]}")
        self.assertEqual(live[0].text, eng._ENCOURAGEMENT[5])

    def test_a_banner_never_retires_a_lane_popup(self) -> None:
        """Only banners share the strip. The per-trial wording above a
        lane is a different thing at a different place and must survive
        a streak threshold landing on the same frame."""
        from finger_rehab.ui.screens import GameplayScreen
        eng = _engine()
        screen = GameplayScreen(eng)
        eng._screens["gameplay"] = screen
        import time
        screen.flash_lane(1, (0, 200, 0), 0.4, time.perf_counter(),
                          popup_text="Spot on")
        for _ in range(3):
            eng._update_streak(True, "gameplay")
        texts = [p.text for p in screen._popups if p.alive]
        self.assertIn("Spot on", texts)
        self.assertEqual(len(_banners(screen)), 1)

    def test_the_thresholds_are_close_enough_to_collide(self) -> None:
        """The bug is only reachable because two thresholds sit within
        one banner lifetime of each other. If the table ever spreads
        out, this test says so rather than quietly passing."""
        from finger_rehab.game.engine import GameEngine
        steps = sorted(GameEngine._ENCOURAGEMENT)
        gaps = [b - a for a, b in zip(steps, steps[1:])]
        self.assertLessEqual(min(gaps), 3)


if __name__ == "__main__":
    unittest.main()
