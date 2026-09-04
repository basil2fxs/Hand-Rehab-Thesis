"""The menu-music mute: one corner pill on every menu screen, one
choice remembered per participant.

Three layers:

  1. data/prefs.py: the store, keyed by the same identity the session
     folders use, sound on by default, a broken file never fatal.
  2. The engine: whose preference applies (the logged-in code, or the
     identity typed on the login screen before login), the toggle
     that saves and silences at once, and the menu player reading it.
  3. The screens: the pill is on the login, the hub, the hand picker,
     the results screen, Settings and the song picker; a click on it
     or M flips it; on the login screen M types into a focused field
     instead.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_menu_music import _Clock, _FakeAudio  # noqa: E402


def _key(key: int, unicode: str = ""):
    import pygame
    return pygame.event.Event(pygame.KEYDOWN, {
        "key": key, "mod": 0, "unicode": unicode, "scancode": 0})


def _click(pos):
    import pygame
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                              {"pos": pos, "button": 1})


# ---------------------------------------------------------------------
# 1. the store
# ---------------------------------------------------------------------
class PrefsStoreTests(unittest.TestCase):
    def test_default_is_sound_on_and_a_set_persists(self) -> None:
        from finger_rehab.data.prefs import ParticipantPrefs
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "prefs.json"
            prefs = ParticipantPrefs(path)
            self.assertFalse(prefs.menu_muted("P03"))
            self.assertTrue(prefs.set_menu_muted("p03", True))
            self.assertTrue(prefs.menu_muted("P03"))
            self.assertFalse(prefs.menu_muted("P04"))
            # A fresh store reads the file back.
            again = ParticipantPrefs(path)
            self.assertTrue(again.menu_muted("P03"))
            raw = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(raw["participants"]["P03"]
                             ["menu_music_muted"], True)

    def test_identity_rule_matches_the_session_folders(self) -> None:
        from finger_rehab.data.prefs import identity_key
        self.assertEqual(identity_key(" p07 "), "P07")
        self.assertEqual(identity_key("Mara"), "Mara")
        self.assertEqual(identity_key(""), "NA")
        self.assertEqual(identity_key(None), "NA")

    def test_a_broken_file_starts_empty_and_is_rewritten(self) -> None:
        from finger_rehab.data.prefs import ParticipantPrefs
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "prefs.json"
            path.write_text("{not json", encoding="utf-8")
            prefs = ParticipantPrefs(path)
            self.assertFalse(prefs.menu_muted("P03"))
            self.assertTrue(prefs.set_menu_muted("P03", True))
            self.assertTrue(json.loads(path.read_text())["participants"]
                            ["P03"]["menu_music_muted"])

    def test_the_file_is_the_config_path_and_is_writable_when_frozen(
            self) -> None:
        from finger_rehab import config as fconfig
        from finger_rehab.data.prefs import (DEFAULT_PREFS_FILE,
                                             prefs_from_config)
        cfg = fconfig.Config.load()
        # The test session redirects the default; the shipped file
        # name still routes to the writable root, not the bundle.
        self.assertEqual(
            cfg.resolve_path(DEFAULT_PREFS_FILE),
            (fconfig.USER_ROOT / DEFAULT_PREFS_FILE).resolve())
        with tempfile.TemporaryDirectory() as td:
            cfg.data["session"]["prefs_file"] = str(Path(td) / "p.json")
            self.assertEqual(prefs_from_config(cfg).path,
                             Path(td) / "p.json")


# ---------------------------------------------------------------------
# 2. the engine
# ---------------------------------------------------------------------
class _Harness(unittest.TestCase):
    def setUp(self) -> None:
        import pygame
        pygame.init()
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["session"]["data_dir"] = str(self.root / "sessions")
        cfg.data["session"]["prefs_file"] = str(self.root / "prefs.json")
        cfg.data["session"]["suggest_code"] = "never"
        cfg.data["audio"]["enabled"] = False
        cfg.data["report"] = {"enabled": False}
        self.eng = GameEngine(cfg, KeyboardOnlySource())
        self.eng._screens = self.eng._build_screens()
        self.eng.audio = _FakeAudio()
        self.eng.show_title()

    def tearDown(self) -> None:
        import pygame
        try:
            self.eng._close_loggers()
        except Exception:
            pass
        self._td.cleanup()
        pygame.quit()

    def _login(self, who: str = "P03") -> None:
        self.eng.begin_session(who, "30", dominant_hand="right")


class EngineMuteTests(_Harness):
    def test_identity_is_the_login_then_the_participant(self) -> None:
        title = self.eng._screens["title"]
        self.assertEqual(self.eng.pref_identity(), "NA")
        title.name_input.text = "p03"
        self.assertEqual(self.eng.pref_identity(), "P03")
        self._login("P05")
        self.assertEqual(self.eng.pref_identity(), "P05")
        self.eng.end_session()
        self.assertEqual(self.eng.pref_identity(), "NA")

    def test_toggle_saves_and_silences_at_once(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        self._login("P03")
        self.eng.show_mode_select()
        self.eng._tick_menu_music()
        player = self.eng.menu_music
        player._clock = _Clock()
        self.assertTrue(player.is_playing)
        self.assertTrue(self.eng.toggle_menu_music_mute())
        self.assertEqual(player.state, "idle")
        self.assertIsNone(self.eng.audio.menu_path)
        self.assertTrue(self.eng.menu_music_muted())
        for _ in range(3):
            self.eng._tick_menu_music()
        self.assertFalse(player.is_playing)
        raw = json.loads((self.root / "prefs.json").read_text())
        self.assertTrue(raw["participants"]["P03"]["menu_music_muted"])
        # Back on: the next tick starts a track again.
        self.assertFalse(self.eng.toggle_menu_music_mute())
        self.eng._tick_menu_music()
        self.assertTrue(player.is_playing)
        self.assertIsInstance(MenuMusicPlayer.FADE_OUT_S, float)

    def test_the_mute_follows_the_person_not_the_machine(self) -> None:
        self._login("P03")
        self.eng.toggle_menu_music_mute()
        self.eng.end_session()
        # The next person on the same laptop gets sound.
        self._login("P04")
        self.assertFalse(self.eng.menu_music_muted())
        self.eng.show_mode_select()
        self.eng._tick_menu_music()
        self.assertTrue(self.eng.menu_music.is_playing)
        self.eng.end_session()
        # P03 comes back muted at the next visit.
        self._login("p03")
        self.assertTrue(self.eng.menu_music_muted())
        # And the machine's own switch is untouched.
        self.assertTrue(self.eng.cfg.get("audio.menu_music_enabled"))

    def test_the_real_user_settings_file_is_never_the_store(self) -> None:
        from finger_rehab import config as fconfig
        self._login("P03")
        self.eng.toggle_menu_music_mute()
        self.assertFalse(fconfig.USER_OVERRIDES.exists()
                         and "menu_music_muted"
                         in fconfig.USER_OVERRIDES.read_text())


# ---------------------------------------------------------------------
# 3. the screens
# ---------------------------------------------------------------------
class ScreenMuteTests(_Harness):
    # The song picker is on this list even though the menu playlist
    # does not run there: it previews tracks on the same stream, so it
    # is the one menu that can make noise on its own and it needs the
    # same control. See MutedPreviewTests in test_rhythm_preview.py.
    MENU_KEYS = ("title", "mode_select", "setup", "results", "diagnostics",
                 "rhythm_setup")

    def test_every_menu_screen_has_the_pill_and_draws_it(self) -> None:
        import pygame
        from finger_rehab.ui.screens import MuteButton
        surf = pygame.Surface((1280, 800))
        for key in self.MENU_KEYS:
            sc = self.eng._screens[key]
            self.assertIsInstance(sc.mute_btn, MuteButton, key)
            r = sc.mute_btn.rect
            self.assertTrue(0 <= r.left and r.right <= 1280, key)
            self.assertTrue(0 <= r.top and r.bottom <= 100, key)
            self.eng.screen_obj = sc
            sc.draw(surf)

    def test_a_click_on_the_pill_flips_the_mute_on_every_screen(self) -> None:
        self._login("P03")
        for key in self.MENU_KEYS:
            sc = self.eng._screens[key]
            self.eng.screen_obj = sc
            before = self.eng.menu_music_muted()
            sc.handle_event(_click(sc.mute_btn.rect.center))
            self.assertNotEqual(self.eng.menu_music_muted(), before, key)

    def test_m_flips_the_mute_on_every_screen(self) -> None:
        import pygame
        self._login("P03")
        for key in self.MENU_KEYS:
            sc = self.eng._screens[key]
            self.eng.screen_obj = sc
            before = self.eng.menu_music_muted()
            sc.handle_event(_key(pygame.K_m, "m"))
            self.assertNotEqual(self.eng.menu_music_muted(), before, key)

    def test_on_the_login_screen_m_types_into_a_focused_field(self) -> None:
        import pygame
        title = self.eng._screens["title"]
        title.name_input.focused = True
        title.handle_event(_key(pygame.K_m, "M"))
        self.assertEqual(title.name_input.text, "M")
        self.assertFalse(self.eng.menu_music_muted())
        title.name_input.focused = False
        title.sex_seg.focused = True
        title.handle_event(_key(pygame.K_m, "m"))
        self.assertEqual(title.sex_seg.value, "male")
        self.assertFalse(self.eng.menu_music_muted())
        title.sex_seg.focused = False
        title.handle_event(_key(pygame.K_m, "m"))
        self.assertTrue(self.eng.menu_music_muted())

    def test_the_login_pill_sets_the_typed_identity(self) -> None:
        import pygame
        title = self.eng._screens["title"]
        title.name_input.text = "P09"
        title.handle_event(_key(pygame.K_m, "m"))
        raw = json.loads((self.root / "prefs.json").read_text())
        self.assertTrue(raw["participants"]["P09"]["menu_music_muted"])
        self.assertNotIn("NA", raw["participants"])
        # Logging P09 in keeps that choice.
        title.hand_seg.set("right")
        title._begin()
        self.assertTrue(self.eng.menu_music_muted())

    def test_results_game_menu_moved_to_g(self) -> None:
        import pygame
        self._login("P03")
        results = self.eng._screens["results"]
        self.eng.screen_obj = results
        results.handle_event(_key(pygame.K_g, "g"))
        self.assertIs(self.eng.screen_obj, self.eng._screens["mode_select"])

    def test_the_pill_says_its_state(self) -> None:
        import pygame
        self._login("P03")
        hub = self.eng._screens["mode_select"]
        seen: list[str] = []
        real_font = hub.layout.font

        class _SpyFont:
            def __init__(self, font):
                self._font = font

            def render(self, text, *args, **kwargs):
                seen.append(str(text))
                return self._font.render(text, *args, **kwargs)

            def __getattr__(self, name):
                return getattr(self._font, name)
        hub.layout.font = lambda pt, bold=False: _SpyFont(real_font(pt, bold))
        try:
            hub.draw(pygame.Surface((1280, 800)))
            self.assertIn("MUSIC ON  (M)", seen)
            self.eng.toggle_menu_music_mute()
            seen.clear()
            hub.draw(pygame.Surface((1280, 800)))
            self.assertIn("MUSIC OFF  (M)", seen)
        finally:
            hub.layout.font = real_font


if __name__ == "__main__":
    unittest.main()
