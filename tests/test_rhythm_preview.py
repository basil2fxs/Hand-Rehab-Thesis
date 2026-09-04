"""The rhythm song screen previews the selected song by itself.

Landing on the screen plays the pick (the default pick included) for
four seconds and stops; any pick plays again from the top; leaving
the screen stops it. The preview shares the one music stream with the
menu playlist, so it waits for the playlist's fade rather than
cutting over it, and START stops it before the block's own song can
start, so nothing carries into the block. Driven through the real
engine and screen with the fake audio from the menu music tests.

The second half covers the participant's menu-music mute on this
screen. The menu playlist does not run here, so before the pill was
added this was the one menu that could make noise at someone who had
set MUSIC OFF, with nothing on screen to stop it.
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

import finger_rehab.ui.screens as screens_module  # noqa: E402
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
        # Stub the duration probe on the CLASS, before the engine
        # builds its screens. The screen's constructor calls refresh(),
        # which starts the probe thread, so an instance-level stub set
        # afterwards is already too late: the thread is off trying to
        # decode the placeholder files above and lands its failure in
        # whichever test happens to be running at the time. None of
        # these tests care about track durations.
        self._real_probe = screens_module.RhythmSetupScreen._spawn_duration_worker
        screens_module.RhythmSetupScreen._spawn_duration_worker = (
            lambda self: None)
        self.addCleanup(setattr, screens_module.RhythmSetupScreen,
                        "_spawn_duration_worker", self._real_probe)
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


class MutedPreviewTests(_Harness):
    """MUSIC OFF on the song picker.

    The rule: previews the screen starts by itself (landing, a rescan,
    picking a track off the list) stay silent, the Play preview button
    still works. That keeps the pill honest without taking away the
    only way to hear what a track sounds like before starting it.
    """

    def _mute(self) -> None:
        self.assertTrue(self.eng.toggle_menu_music_mute())
        self.assertTrue(self.eng.menu_music_muted())

    def _enter_muted(self) -> None:
        """Land on the screen with the mute already on. The playlist is
        stopped outright by the toggle, so there is no fade to wait
        for, but frame past one anyway so nothing can be blamed on
        timing."""
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        self._mute()
        self.eng.show_rhythm_setup()
        self._frame(0.0)
        self._frame(MenuMusicPlayer.FADE_OUT_S + 0.1)

    def _rects(self) -> dict:
        import pygame
        self.screen.draw(pygame.Surface((1280, 800)))
        return {Path(str(p)).name: r for r, p in self.screen._track_rects}

    def test_the_screen_has_the_pill_and_it_is_on_screen(self) -> None:
        from finger_rehab.ui.screens import MuteButton
        btn = self.screen.mute_btn
        self.assertIsInstance(btn, MuteButton)
        self.assertGreaterEqual(btn.rect.left, 0)
        self.assertLessEqual(btn.rect.right, 1280)
        self.assertLessEqual(btn.rect.bottom, 100)

    def test_landing_muted_plays_nothing_and_owes_nothing(self) -> None:
        self._enter_muted()
        self.assertFalse(self.screen._previewing)
        self.assertIsNone(self.eng.audio.game_song)
        # The owed preview has to be cleared, not just skipped, or it
        # fires the moment something else calls update().
        self.assertFalse(self.screen._preview_pending)
        self._frame(5.0)
        self.assertFalse(self.screen._previewing)
        self.assertIsNone(self.eng.audio.game_song)

    def test_a_rescan_while_muted_stays_silent(self) -> None:
        self._enter_muted()
        self.screen.refresh_btn.on_click()
        self._frame(0.1)
        self.assertFalse(self.screen._previewing)
        self.assertIsNone(self.eng.audio.game_song)

    def test_picking_a_track_while_muted_selects_but_stays_silent(self) -> None:
        self._enter_muted()
        before = self.screen._selected_track
        self.screen.handle_event(_click(self._rects()["Gamma.mp3"].center))
        self._frame(0.1)
        self.assertNotEqual(self.screen._selected_track, before)
        self.assertTrue(self.screen._selected_track.endswith("Gamma.mp3"))
        self.assertFalse(self.screen._previewing)
        self.assertIsNone(self.eng.audio.game_song)

    def test_play_preview_still_works_while_muted(self) -> None:
        self._enter_muted()
        self.screen.preview_btn.on_click()
        self.assertTrue(self.screen._previewing)
        self.assertTrue(self.eng.audio.game_song.endswith("Alpha.mp3"))
        # And it is still a four-second preview, not an open stream.
        self._frame(4.5)
        self.assertFalse(self.screen._previewing)
        self.assertIsNone(self.eng.audio.game_song)

    def test_the_button_stops_a_muted_preview_too(self) -> None:
        self._enter_muted()
        self.screen.preview_btn.on_click()
        self.assertTrue(self.screen._previewing)
        self.screen.preview_btn.on_click()
        self.assertFalse(self.screen._previewing)
        self.assertIsNone(self.eng.audio.game_song)

    def test_an_asked_for_preview_survives_waiting_for_the_fade(self) -> None:
        # The Play preview button pressed while the stream is still
        # busy: the ask has to be carried across the wait, otherwise
        # the retry inside update() reads as automatic and the mute
        # swallows it.
        self._enter_muted()
        self.screen._menu_music_faded = lambda: False
        self.screen.preview_btn.on_click()
        self.assertTrue(self.screen._preview_pending)
        self.assertFalse(self.screen._previewing)
        self.screen._menu_music_faded = lambda: True
        self._frame(0.1)
        self.assertTrue(self.screen._previewing)
        self.assertTrue(self.eng.audio.game_song.endswith("Alpha.mp3"))

    def test_the_pill_stops_a_preview_that_is_already_playing(self) -> None:
        import pygame
        self._enter()
        self.assertTrue(self.screen._previewing)
        self.screen.handle_event(pygame.event.Event(
            pygame.KEYDOWN, {"key": pygame.K_m, "mod": 0,
                             "unicode": "m", "scancode": 0}))
        self.assertTrue(self.eng.menu_music_muted())
        self.assertFalse(self.screen._previewing)
        self.assertIsNone(self.eng.audio.game_song)

    def test_a_click_on_the_pill_flips_it_and_eats_the_event(self) -> None:
        self._enter_muted()
        before = self.screen._selected_track
        self.screen.handle_event(_click(self.screen.mute_btn.rect.center))
        self.assertFalse(self.eng.menu_music_muted())
        # Unmuting must not start a preview on its own either: the
        # participant asked for sound back, not for a song right now.
        self.assertFalse(self.screen._previewing)
        self._frame(0.1)
        self.assertFalse(self.screen._previewing)
        self.assertEqual(self.screen._selected_track, before)

    def test_unmuting_lets_the_next_pick_preview_again(self) -> None:
        self._enter_muted()
        self.screen.handle_event(_click(self.screen.mute_btn.rect.center))
        self.assertFalse(self.eng.menu_music_muted())
        self.screen.handle_event(_click(self._rects()["Beta.mp3"].center))
        self._frame(0.1)
        self.assertTrue(self.screen._previewing)
        self.assertTrue(self.eng.audio.game_song.endswith("Beta.mp3"))

    def test_the_subtitle_says_which_way_round_it_is(self) -> None:
        # A muted screen that still promised a preview would read as
        # broken audio, so the header text follows the pill.
        import pygame
        surf = pygame.Surface((1280, 800))
        seen = []
        real = screens_module._draw_header

        def spy(s, title, subtitle, *a, **k):
            seen.append(subtitle)
            return real(s, title, subtitle, *a, **k)
        screens_module._draw_header = spy
        try:
            self.screen.draw(surf)
            self._mute()
            self.screen.draw(surf)
        finally:
            screens_module._draw_header = real
        self.assertEqual(len(seen), 2)
        self.assertIn("plays a 4 second preview", seen[0])
        self.assertNotIn("Music is off", seen[0])
        self.assertIn("Music is off", seen[1])
        self.assertIn("Play preview", seen[1])

    def test_the_choice_is_the_participants_own_and_is_remembered(self) -> None:
        self._mute()
        self.eng.end_session()
        self.eng.begin_session("P03", "30", dominant_hand="right")
        self.assertTrue(self.eng.menu_music_muted())
        self.eng.show_rhythm_setup()
        self._frame(0.1)
        self.assertFalse(self.screen._previewing)
        # A different participant starts from sound on.
        self.eng.end_session()
        self.eng.begin_session("P04", "30", dominant_hand="right")
        self.assertFalse(self.eng.menu_music_muted())


if __name__ == "__main__":
    unittest.main()
