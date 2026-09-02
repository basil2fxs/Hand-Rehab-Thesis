"""The rhythm song screen previews the selected song by itself.

Landing on the screen plays the pick (the default pick included) for
four seconds and stops; any pick plays again from the top; leaving
the screen stops it. The preview shares the one music stream with the
menu playlist, so it waits for the playlist's fade rather than
cutting over it, and START stops it before the block's own song can
start, so nothing carries into the block. Driven through the real
engine and screen with the fake audio from the menu music tests.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_menu_music import _Clock, _FakeAudio  # noqa: E402


def _click(pos):
    import pygame
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                              {"pos": pos, "button": 1})


class _Harness(unittest.TestCase):
    def setUp(self) -> None:
        import pygame
        pygame.init()
        self._td = tempfile.TemporaryDirectory()
        root = Path(self._td.name)
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["session"]["data_dir"] = str(root / "sessions")
        cfg.data["session"]["prefs_file"] = str(root / "prefs.json")
        cfg.data["audio"]["enabled"] = False
        cfg.data["report"] = {"enabled": False}
        # A music folder of our own: the real one is scanned by
        # librosa for durations, which this screen's logic never needs.
        music = root / "music"
        music.mkdir()
        for name in ("Alpha.mp3", "Beta.mp3", "Gamma.mp3"):
            (music / name).write_bytes(b"not audio")
        cfg.data["audio"]["music_dir"] = str(music)
        cfg.data["audio"]["menu_music_tracks"] = ["Alpha.mp3", "Beta.mp3"]
        self.eng = GameEngine(cfg, KeyboardOnlySource())
        self.eng._screens = self.eng._build_screens()
        self.eng.audio = _FakeAudio()
        self.clock = _Clock()
        self.eng.begin_session("P03", "30", dominant_hand="right")
        self.eng.show_mode_select()
        self.eng._tick_menu_music()
        self.eng.menu_music._clock = self.clock
        self.screen = self.eng._screens["rhythm_setup"]
        self.screen._clock = self.clock
        # No librosa work: the duration probe is a thread we do not
        # want in the way, so hand it an already-known answer.
        self.screen._spawn_duration_worker = lambda: None

    def tearDown(self) -> None:
        import pygame
        try:
            self.eng._close_loggers()
        except Exception:
            pass
        self._td.cleanup()
        pygame.quit()

    def _frame(self, dt: float = 0.0) -> None:
        """One engine-side frame: menu tick, then the screen's update."""
        self.clock.step(dt)
        self.eng._tick_menu_music()
        self.eng.screen_obj.update(dt)

    def _enter(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        self.assertTrue(self.eng.menu_music.is_playing)
        self.eng.show_rhythm_setup()
        self.assertIs(self.eng.screen_obj, self.screen)
        # Still faded? No preview yet, no cut over the menu track.
        self._frame(0.0)
        self.assertNotEqual(self.eng.menu_music.state, "idle")
        self.assertFalse(self.screen._previewing)
        self.assertIsNone(self.eng.audio.game_song)
        self._frame(MenuMusicPlayer.FADE_OUT_S + 0.1)


class PreviewTests(_Harness):
    def test_entry_previews_the_default_pick_for_four_seconds(self) -> None:
        self._enter()
        self.assertEqual(self.screen.PREVIEW_S, 4.0)
        self.assertTrue(self.screen._previewing)
        self.assertEqual(self.eng.audio.game_song, self.screen._selected_track)
        self.assertTrue(self.eng.audio.game_song.endswith("Alpha.mp3"))
        self._frame(3.5)
        self.assertTrue(self.screen._previewing)
        self._frame(0.6)
        self.assertFalse(self.screen._previewing)
        self.assertIsNone(self.eng.audio.game_song)

    def test_a_pick_restarts_the_preview_same_song_included(self) -> None:
        self._enter()
        self._frame(4.5)
        self.assertFalse(self.screen._previewing)
        self.screen.draw(__import__("pygame").Surface((1280, 800)))
        rects = {Path(str(p)).name: r for r, p in self.screen._track_rects}
        self.screen.handle_event(_click(rects["Beta.mp3"].center))
        self.assertTrue(self.screen._previewing)
        self.assertTrue(self.eng.audio.game_song.endswith("Beta.mp3"))
        # Same song again, mid-preview: from the top, four more seconds.
        self._frame(2.0)
        self.screen.handle_event(_click(rects["Beta.mp3"].center))
        self._frame(3.0)
        self.assertTrue(self.screen._previewing)
        self._frame(1.1)
        self.assertFalse(self.screen._previewing)

    def test_back_stops_it_and_the_menu_music_returns(self) -> None:
        self._enter()
        self.screen.back_btn.on_click()
        self.assertFalse(self.screen._previewing)
        self.assertIsNone(self.eng.audio.game_song)
        self.assertIs(self.eng.screen_obj, self.eng._screens["mode_select"])
        self._frame(0.1)
        self.assertTrue(self.eng.menu_music.is_playing)

    def test_escape_stops_it_too(self) -> None:
        import pygame
        self._enter()
        self.eng._handle_global_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_ESCAPE, "mod": 0,
                             "unicode": "", "scancode": 0}))
        self.assertFalse(self.screen._previewing)
        self.assertFalse(self.screen._preview_pending)
        self.assertIsNone(self.eng.audio.game_song)

    def test_start_never_carries_the_preview_into_the_block(self) -> None:
        import finger_rehab.audio.beatmap as bm
        self._enter()
        real = bm.extract_beatmap

        def fake(path, difficulty="medium", lane_pattern=None, num_lanes=4):
            # The preview must already be gone when the chart builds.
            self.assertFalse(self.screen._previewing)
            self.assertIsNone(self.eng.audio.game_song)
            b = bm.procedural_beatmap(120.0, 4, difficulty=difficulty,
                                     num_lanes=num_lanes)
            b.song = str(path)
            return b
        bm.extract_beatmap = fake
        try:
            self.screen._start()
        finally:
            bm.extract_beatmap = real
        self.assertTrue(self.eng.block_is_running())
        self.assertEqual(self.eng.current_block, "rhythm")
        self.assertFalse(self.screen._previewing)
        self.assertFalse(self.screen._preview_pending)
        self.eng._abandon_if_in_block()

    def test_no_audio_is_harmless(self) -> None:
        self.eng.audio = None
        self.eng.show_rhythm_setup()
        self.screen.update(0.016)
        self.assertFalse(self.screen._previewing)


if __name__ == "__main__":
    unittest.main()
