"""Audit finding #113: a session could not be started keyboard-only.
Title (outside a focused text field), mode select, hand pick, rhythm
setup and results were all mouse-click only, so "playable start to
finish with keyboard only" held for the block itself but not for
getting INTO one. This drives each of those screens' handle_event with
real pygame KEYDOWN events and checks the forward-navigation action
fires, the same way a mouse click on the equivalent button would."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


def _key_event(key: int):
    import pygame
    return pygame.event.Event(
        pygame.KEYDOWN, {"key": key, "mod": 0, "unicode": "", "scancode": 0})


def _engine(mode: str | None = None):
    import pygame
    pygame.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    if mode is not None:
        cfg.data.setdefault("game", {})["mode"] = mode
    return GameEngine(cfg, KeyboardOnlySource())


class TitleScreenKeyboardOnlyTests(unittest.TestCase):
    """Enter used to be gated on "a field is still focused after
    dispatch", but TextInput's own Enter handling defocuses the field
    on that same event, so the check always read False and Enter never
    fired -- with no mouse, this screen had no way out at all."""

    def test_enter_starts_session_even_with_no_field_focused(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import TitleScreen
            eng = _engine()
            calls = []
            eng.show_mode_select = lambda: calls.append(True)
            sc = TitleScreen(eng)
            self.assertFalse(sc.name_input.focused)
            self.assertFalse(sc.age_input.focused)
            # No name typed: the first Enter warns about the shared
            # NA identity instead of starting; typing a name (or a
            # second deliberate Enter) proceeds. Keyboard-only flow
            # stays fully navigable either way.
            sc.handle_event(_key_event(pygame.K_RETURN))
            self.assertEqual(calls, [])
            self.assertTrue(sc.begin_note)
            sc.name_input.text = "Mara"
            sc.handle_event(_key_event(pygame.K_RETURN))
            self.assertEqual(calls, [True])
        finally:
            pygame.quit()

    def test_enter_starts_session_while_name_field_focused(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import TitleScreen
            eng = _engine()
            calls = []
            eng.show_mode_select = lambda: calls.append(True)
            sc = TitleScreen(eng)
            sc.name_input.focused = True
            sc.name_input.text = "Basil"
            sc.handle_event(_key_event(pygame.K_RETURN))
            self.assertEqual(calls, [True])
            self.assertEqual(eng.session.participant, "Basil")
        finally:
            pygame.quit()

    def test_tab_with_nothing_focused_focuses_name_field(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import TitleScreen
            sc = TitleScreen(_engine())
            sc.handle_event(_key_event(pygame.K_TAB))
            self.assertTrue(sc.name_input.focused)
            self.assertFalse(sc.age_input.focused)
        finally:
            pygame.quit()

    def test_tab_cycles_from_name_to_age(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import TitleScreen
            sc = TitleScreen(_engine())
            sc.handle_event(_key_event(pygame.K_TAB))  # focuses name
            sc.handle_event(_key_event(pygame.K_TAB))  # name -> age
            self.assertFalse(sc.name_input.focused)
            self.assertTrue(sc.age_input.focused)
        finally:
            pygame.quit()


class ModeSelectKeyboardOnlyTests(unittest.TestCase):

    def test_digit_key_picks_matching_card(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import ModeSelectScreen
            eng = _engine()
            picked = []
            eng.show_setup = lambda: picked.append(
                eng.cfg.get("game.mode"))
            sc = ModeSelectScreen(eng)
            # '2' is the second card: adaptive.
            sc.handle_event(_key_event(pygame.K_2))
            self.assertEqual(picked, ["adaptive"])
        finally:
            pygame.quit()

    def test_zero_key_picks_tenth_card(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import ModeSelectScreen
            eng = _engine()
            picked = []
            eng.show_setup = lambda: picked.append(
                eng.cfg.get("game.mode"))
            sc = ModeSelectScreen(eng)
            self.assertEqual(len(sc.MODES), 10)
            sc.handle_event(_key_event(pygame.K_0))
            self.assertEqual(picked, [sc.MODES[9][0]])
        finally:
            pygame.quit()


class SetupScreenKeyboardOnlyTests(unittest.TestCase):

    def test_r_key_picks_right_hand_and_starts_block(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import SetupScreen
            eng = _engine(mode="reaction")
            started = []
            eng.begin_reaction_block = lambda: started.append(True)
            eng._screens = {"gameplay": None, "rhythm": None}
            sc = SetupScreen(eng)
            sc.handle_event(_key_event(pygame.K_r))
            self.assertEqual(eng.hand_mode, "right")
            self.assertEqual(started, [True])
        finally:
            pygame.quit()

    def test_l_and_b_keys_pick_left_and_both(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import SetupScreen
            eng = _engine(mode="adaptive")
            eng.begin_adaptive_block = lambda: None
            eng._screens = {"gameplay": None, "rhythm": None}
            sc = SetupScreen(eng)
            sc.handle_event(_key_event(pygame.K_l))
            self.assertEqual(eng.hand_mode, "left")
            sc.handle_event(_key_event(pygame.K_b))
            self.assertEqual(eng.hand_mode, "both")
        finally:
            pygame.quit()


class RhythmSetupScreenKeyboardOnlyTests(unittest.TestCase):

    def test_enter_starts_with_the_pre_selected_track(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import RhythmSetupScreen
            eng = _engine(mode="rhythm")
            eng.begin_rhythm_block = lambda bm: None
            sc = RhythmSetupScreen(eng)
            # refresh() (called by __init__) is expected to pre-select
            # the first available track when the music folder has one;
            # skip cleanly (not a failure of this fix) when the dev
            # environment has no bundled tracks to select from.
            if sc._selected_track is None:
                self.skipTest("no tracks available in assets/music")
            started = {}

            def _start_spy(*a, **kw):
                started["called"] = True
            sc._start = _start_spy
            sc.handle_event(_key_event(pygame.K_RETURN))
            self.assertTrue(started.get("called"))
        finally:
            pygame.quit()


class ResultsScreenKeyboardOnlyTests(unittest.TestCase):

    def test_enter_triggers_retry(self) -> None:
        import pygame
        pygame.init()
        try:
            from finger_rehab.ui.screens import ResultsScreen
            eng = _engine()
            retried = []
            eng.retry_last_block = lambda: retried.append(True)
            sc = ResultsScreen(eng)
            sc.handle_event(_key_event(pygame.K_RETURN))
            self.assertEqual(retried, [True])
        finally:
            pygame.quit()


class EndGameGuardKeyboardOnlyTests(unittest.TestCase):
    """The mid-game exit guard is a double-press chip: Esc, Esc. No
    button to click, so the whole in-and-out of a game needs nothing
    but the keyboard. The session dialog on game select keeps its
    keyboard path (Tab + Enter) as before."""

    def _engine_in_block(self):
        import pygame
        import tempfile
        pygame.init()
        eng = _engine()
        self._td = tempfile.TemporaryDirectory()
        eng.cfg.data["session"]["data_dir"] = self._td.name
        eng._screens = eng._build_screens()
        eng.hand_mode = "right"
        eng.begin_classic_block()
        return eng

    def test_esc_esc_ends_the_game_keyboard_only(self) -> None:
        import pygame
        eng = self._engine_in_block()
        try:
            eng._handle_global_event(_key_event(pygame.K_ESCAPE))
            self.assertTrue(eng.exit_chip_active)
            eng._handle_global_event(_key_event(pygame.K_ESCAPE))
            self.assertFalse(eng.exit_chip_active)
            self.assertIs(eng.screen_obj, eng._screens["mode_select"])
        finally:
            eng._close_loggers()
            self._td.cleanup()
            pygame.quit()

    def test_any_key_backs_out_of_the_guard(self) -> None:
        import pygame
        eng = self._engine_in_block()
        try:
            eng._handle_global_event(_key_event(pygame.K_ESCAPE))
            eng._handle_global_event(_key_event(pygame.K_SPACE))
            self.assertFalse(eng.exit_chip_active)
            self.assertFalse(eng.paused)
            self.assertIs(eng.screen_obj, eng._screens["gameplay"])
        finally:
            eng._close_loggers()
            self._td.cleanup()
            pygame.quit()


if __name__ == "__main__":
    unittest.main()
