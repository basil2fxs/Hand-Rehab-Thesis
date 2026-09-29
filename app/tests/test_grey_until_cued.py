"""Grey until cued: in Reaction, Adaptive, Muscle Memory, Chords, Echo
and Mirror every waiting finger tile is a neutral grey, and a tile shows
its finger's colour only when a cue lights it, so colour on a tile means
one thing, this finger now (Basil, 28 and 29 September 2026). Each game
is started for real and its tiles read off the drawn frame.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

GREY_GAMES = ("reaction", "adaptive", "pattern", "chords", "echo",
              "mirror")


def _started(block):
    import pygame
    pygame.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    import finger_rehab.ui.screens as screens
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["audio"]["enabled"] = False
    eng = GameEngine(cfg, KeyboardOnlySource())
    eng._screens = {"gameplay": MagicMock(), "results": MagicMock()}
    if block == "mirror":
        eng.set_hand_mode("both")
    getattr(eng, eng._BLOCK_STARTERS[block])()
    gp = screens.GameplayScreen(eng)
    gp._countdown_until = 0.0
    return eng, gp


def _fill_at(surf, ls):
    """The tile's body colour, away from its badge and its label."""
    return tuple(surf.get_at((ls.rect.centerx,
                              ls.rect.y + ls.rect.h // 3)))[:3]


class GreyUntilCued(unittest.TestCase):

    def tearDown(self):
        import pygame
        pygame.quit()

    def test_the_six_games_are_the_grey_ones(self):
        from finger_rehab.ui.screens import GameplayScreen
        self.assertEqual(GameplayScreen.NEUTRAL_IDLE_BLOCKS,
                         frozenset(GREY_GAMES))

    def test_waiting_tiles_are_grey_and_a_cue_is_its_finger_colour(self):
        import pygame
        for block in GREY_GAMES:
            with self.subTest(game=block):
                eng, gp = _started(block)
                try:
                    for ls in gp.lanes:
                        ls.active = False
                        ls.flash_until = 0.0
                    lit = gp.lanes[1]
                    surf = pygame.Surface((1280, 800))
                    gp.draw(surf)
                    # The game may re-arm its own cue on the frame; set
                    # ours after the first draw and draw again.
                    for ls in gp.lanes:
                        ls.active = ls is lit
                        ls.flash_until = 0.0
                        ls.is_pressed = False
                    for ls in gp.lanes:
                        ls.draw(surf, 0.0)
                    grey = lit.neutral_colours()[0]
                    for ls in gp.lanes:
                        self.assertTrue(ls.neutral_idle, block)
                        want = (eng.theme.lane_active[ls.finger % 4]
                                if ls.active else grey)
                        self.assertEqual(_fill_at(surf, ls), want,
                                         f"{block} lane {ls.lane}")
                finally:
                    eng._abandon_if_in_block()

    def test_a_game_off_the_list_keeps_its_finger_colours(self):
        import pygame
        eng, gp = _started("classic")
        try:
            gp.draw(pygame.Surface((1280, 800)))
            self.assertTrue(all(not ls.neutral_idle for ls in gp.lanes))
        finally:
            eng._abandon_if_in_block()


if __name__ == "__main__":
    unittest.main()
