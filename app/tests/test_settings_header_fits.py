"""Two collisions on the Settings screen at the shipped 1280 x 800.

The header line under the title ran under the TEST MODE and MENU
MUSIC pills at the right whenever a board was connected, and in the
levels panel the FEEDBACK and BUZZER labels printed under their own
values. Both are checked here by drawing the real screen and reading
back where every blit landed.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402


class _RecordingSurface(pygame.Surface):
    """A surface that remembers the rect of every blit."""

    def __init__(self, size):
        super().__init__(size)
        self.blits: list[pygame.Rect] = []

    def blit(self, source, dest, *args, **kwargs):
        if isinstance(dest, pygame.Rect):
            rect = pygame.Rect(dest)
        else:
            rect = pygame.Rect(dest, source.get_size())
        self.blits.append(rect)
        return super().blit(source, dest, *args, **kwargs)


def _settings_screen():
    pygame.init()
    pygame.font.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["audio"]["enabled"] = False
    eng = GameEngine(cfg, KeyboardOnlySource())
    eng._screens = eng._build_screens()
    eng.show_diagnostics()
    return eng._screens["diagnostics"]


class HeaderChipTests(unittest.TestCase):
    """The connection chip and the Test Mode chip at the top right
    clear the title and the tabs in every state (the header line that
    used to collide with the pills went with the tabs, 29 September
    2026)."""

    STATES = ("CONNECTED", "KEYBOARD", "DISCONNECTED", "NO DATA")

    def test_the_chips_clear_the_title_and_the_tabs(self):
        screen = _settings_screen()
        chips = []
        real = screen._draw_chip

        def spy(*a, **k):
            r = real(*a, **k)
            chips.append(r)
            return r

        screen._draw_chip = spy
        screen.engine.cfg.data["game"]["test_mode_enabled"] = True
        title_font = screen.layout.font(42)
        title_right = 640 + title_font.size("Settings")[0] // 2
        for state in self.STATES:
            with self.subTest(state=state):
                chips.clear()
                with patch.object(screen, "_connection_state",
                                  lambda: (state, screen.theme.muted)):
                    screen.draw(_RecordingSurface((1280, 800)))
                self.assertEqual(len(chips), 2)
                for chip in chips:
                    self.assertGreater(chip.left, title_right + 16)
                    self.assertLessEqual(chip.right, 1280)
                    self.assertLess(chip.bottom, screen._tab_rect(0).top)


class SliderLabelTests(unittest.TestCase):
    """A slider's label and its value never share a pixel."""

    def _label_and_value(self, slider):
        surf = _RecordingSurface((1280, 800))
        slider.draw(surf)
        # The label is the first blit, the value the second.
        return surf.blits[0], surf.blits[1]

    def test_every_settings_slider_keeps_its_label_clear(self):
        screen = _settings_screen()
        for key, slider in screen._vol_sliders.items():
            with self.subTest(slider=key):
                slider.value = slider.max_value
                label, value = self._label_and_value(slider)
                self.assertFalse(label.colliderect(value),
                                 f"{key}: {label} meets {value}")

    def test_a_narrow_slider_shrinks_rather_than_overlaps(self):
        pygame.init()
        pygame.font.init()
        from finger_rehab.ui.theme import get as get_theme
        from finger_rehab.ui.widgets import Layout, Slider
        slider = Slider(pygame.Rect(0, 60, 120, 20), get_theme("clinical"),
                        Layout(1280, 800, 1.0), min_value=150.0,
                        max_value=450.0, initial=450.0, step=50.0,
                        label="BUZZER", value_format="{:.0f} ms")
        label, value = self._label_and_value(slider)
        self.assertFalse(label.colliderect(value))
        self.assertLessEqual(value.right, 120)


if __name__ == "__main__":
    unittest.main()
