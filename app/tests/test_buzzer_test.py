"""Tests for the per-finger buzzer test in the Settings screen.

Clicking a finger tile fires a single STIM pulse on that finger only,
using the hand-prefixed command (LEFT:/RIGHT:STIM:n) so multi_serial
routes it to the right board. The existing per-hand sequence test still
covers all four fingers at once; this is the individual version.
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

import pygame  # noqa: E402


def _diag_screen(send_result=True, send_raises=None):
    """Build a DiagnosticsScreen headless with a recording mock source."""
    pygame.init()
    pygame.font.init()
    from finger_rehab.ui.widgets import Layout
    from finger_rehab.ui.theme import get as get_theme
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.ui.screens import DiagnosticsScreen
    from finger_rehab.config import Config

    e = GameEngine.__new__(GameEngine)
    e.layout = Layout(1280, 800, 1.0)
    e.theme = get_theme("clinical")
    e.cfg = Config.load()
    e.audio = None
    e.detectors = {}
    sent: list[str] = []

    def _send(cmd):
        if send_raises is not None:
            raise send_raises
        sent.append(cmd)
        return send_result

    src = MagicMock()
    src.provides_samples = False
    src.name = "KeyboardOnlySource"
    src.is_connected = False
    src.has_recent_data = lambda t=1.5: False
    src.get_sample = lambda timeout=0: None
    src.send_command = _send
    e.source = src
    return DiagnosticsScreen(e), sent


def _click(screen, pos):
    screen.handle_event(
        pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=pos))


class BuzzerMappingTests(unittest.TestCase):
    def test_each_tile_buzzes_its_own_finger(self) -> None:
        screen, sent = _diag_screen()
        # Right hand lanes 0..3 -> RIGHT:STIM:1..4; left 4..7 -> LEFT:STIM:1..4.
        expected = {
            0: "RIGHT:STIM:1", 1: "RIGHT:STIM:2",
            2: "RIGHT:STIM:3", 3: "RIGHT:STIM:4",
            4: "LEFT:STIM:1", 5: "LEFT:STIM:2",
            6: "LEFT:STIM:3", 7: "LEFT:STIM:4",
        }
        for ls in screen.lanes:
            sent.clear()
            _click(screen, ls.rect.center)
            self.assertEqual(sent, [expected[ls.lane]],
                             f"lane {ls.lane}")

    def test_one_pulse_per_click(self) -> None:
        screen, sent = _diag_screen()
        ls = screen.lanes[0]
        _click(screen, ls.rect.center)
        self.assertEqual(len(sent), 1)

    def test_click_empty_space_does_not_buzz(self) -> None:
        screen, sent = _diag_screen()
        # Top-left corner is above the tiles and clear of every widget.
        _click(screen, (5, 5))
        self.assertEqual(sent, [])

    def test_clicked_tile_flashes(self) -> None:
        screen, _ = _diag_screen()
        ls = screen.lanes[0]
        self.assertEqual(ls.flash_until, 0.0)
        _click(screen, ls.rect.center)
        self.assertGreater(ls.flash_until, 0.0)


class BuzzerDeliveryFeedbackTests(unittest.TestCase):
    def test_not_delivered_message_when_send_returns_false(self) -> None:
        screen, _ = _diag_screen(send_result=False)
        _click(screen, screen.lanes[0].rect.center)
        self.assertIn("not delivered", screen._port_status)

    def test_success_message_names_the_finger(self) -> None:
        screen, _ = _diag_screen(send_result=True)
        _click(screen, screen.lanes[0].rect.center)   # right index
        self.assertIn("Buzzing", screen._port_status)
        self.assertIn("Index", screen._port_status)

    def test_send_error_is_caught(self) -> None:
        screen, _ = _diag_screen(send_raises=OSError("port gone"))
        # Must not raise out of handle_event.
        _click(screen, screen.lanes[0].rect.center)
        self.assertIn("error", screen._port_status.lower())


if __name__ == "__main__":
    unittest.main()
