"""Tests for the Test Mode shortcut.

Test Mode is a supervisor-demo feature: when on, every block (classic,
adaptive, rhythm) is shrunk to ~6 trials so the full pipeline can be
walked through in under a minute. Off, blocks run their normal full
length so trial CSVs from a real research session aren't truncated.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TestModeTrialsHelperTests(unittest.TestCase):
    """The `_test_mode_trials` helper returns None when off, an int
    cap when on. Everything else routes through this single source of
    truth."""

    def _engine(self, enabled: bool, trials: int = 6):
        from rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        eng.cfg = MagicMock()
        def _get(k, d=None):
            if k == "game.test_mode_enabled":
                return enabled
            if k == "game.test_mode_trials":
                return trials
            return d
        eng.cfg.get = MagicMock(side_effect=_get)
        return eng

    def test_disabled_returns_none(self) -> None:
        eng = self._engine(enabled=False)
        self.assertIsNone(eng._test_mode_trials())

    def test_enabled_returns_configured_cap(self) -> None:
        eng = self._engine(enabled=True, trials=8)
        self.assertEqual(eng._test_mode_trials(), 8)

    def test_enabled_minimum_two_trials(self) -> None:
        # Below 2 trials the demo loses meaningful information (one
        # press, then immediately Results). We clamp upward so even
        # a hand-edited cfg with test_mode_trials=0 still produces
        # a usable demo.
        eng = self._engine(enabled=True, trials=0)
        self.assertEqual(eng._test_mode_trials(), 2)


class ClassicTestModeTests(unittest.TestCase):
    """When Test Mode is on, begin_classic_block must shrink
    repeat_count so total trials ~= test_mode_trials."""

    def test_classic_repeat_count_caps_to_test_mode(self) -> None:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            # Pattern length 6 (default), test_mode 6 trials -> ceil(6/6)
            # = 1 repeat. Without test mode the default repeat_count is 8
            # which would give 48 trials.
            cfg.data.setdefault("game", {})["test_mode_enabled"] = True
            cfg.data["game"]["test_mode_trials"] = 6
            cfg.data["game"]["pattern"] = "1,2,3,4,1,2"
            eng = GameEngine(cfg, KeyboardOnlySource())
            # Mock the screen creation so begin_classic_block doesn't
            # try to swap to a screen that hasn't been built.
            eng._screens = {"gameplay": MagicMock()}
            eng._begin_block = lambda *a, **kw: None
            eng.begin_classic_block()
            # repeat_count should be 1 (= ceil(6 / 6))
            self.assertEqual(eng.mode.repeat_count, 1)
        finally:
            pygame.quit()

    def test_classic_repeat_count_unchanged_when_test_mode_off(self) -> None:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data.setdefault("game", {})["test_mode_enabled"] = False
            cfg.data["game"]["repeat_count"] = 8
            eng = GameEngine(cfg, KeyboardOnlySource())
            eng._screens = {"gameplay": MagicMock()}
            eng._begin_block = lambda *a, **kw: None
            eng.begin_classic_block()
            self.assertEqual(eng.mode.repeat_count, 8)
        finally:
            pygame.quit()


class AdaptiveTestModeTests(unittest.TestCase):

    def test_adaptive_total_trials_overridden(self) -> None:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data.setdefault("game", {})["test_mode_enabled"] = True
            cfg.data["game"]["test_mode_trials"] = 5
            cfg.data["game"]["total_trials"] = 40
            eng = GameEngine(cfg, KeyboardOnlySource())
            eng._screens = {"gameplay": MagicMock()}
            eng._begin_block = lambda *a, **kw: None
            eng.begin_adaptive_block()
            self.assertEqual(eng.mode.total_trials, 5)
        finally:
            pygame.quit()

    def test_adaptive_total_trials_normal_when_off(self) -> None:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data.setdefault("game", {})["test_mode_enabled"] = False
            cfg.data["game"]["total_trials"] = 40
            eng = GameEngine(cfg, KeyboardOnlySource())
            eng._screens = {"gameplay": MagicMock()}
            eng._begin_block = lambda *a, **kw: None
            eng.begin_adaptive_block()
            self.assertEqual(eng.mode.total_trials, 40)
        finally:
            pygame.quit()


class RhythmTestModeTests(unittest.TestCase):

    def test_rhythm_beatmap_truncates_in_test_mode(self) -> None:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from rehab.audio.beatmap import Beatmap, Note
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data.setdefault("game", {})["test_mode_enabled"] = True
            cfg.data["game"]["test_mode_trials"] = 4
            eng = GameEngine(cfg, KeyboardOnlySource())
            eng._screens = {"rhythm": MagicMock()}
            eng._begin_block = lambda *a, **kw: None
            # Long beatmap that should get truncated.
            bm = Beatmap(notes=[Note(t=float(i), lane=i % 4)
                                  for i in range(20)])
            eng.begin_rhythm_block(bm)
            self.assertEqual(len(bm.notes), 4)
        finally:
            pygame.quit()

    def test_rhythm_beatmap_untouched_when_off(self) -> None:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from rehab.audio.beatmap import Beatmap, Note
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data.setdefault("game", {})["test_mode_enabled"] = False
            eng = GameEngine(cfg, KeyboardOnlySource())
            eng._screens = {"rhythm": MagicMock()}
            eng._begin_block = lambda *a, **kw: None
            bm = Beatmap(notes=[Note(t=float(i), lane=i % 4)
                                  for i in range(20)])
            eng.begin_rhythm_block(bm)
            self.assertEqual(len(bm.notes), 20)
        finally:
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
