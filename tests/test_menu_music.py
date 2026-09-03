"""Menu music: plays between games, never inside one.

Three layers are pinned here, because each can break the rule on its
own:

  1. AudioEngine's menu_* methods share ONE mixer.music stream with
     rhythm mode. The guards that keep the menu side from ever taking
     the stream off a game are tested with the mixer patched out.
  2. MenuMusicPlayer's state machine: which screens it runs on, the
     fade at block start, the results-screen duck, the shuffle, and
     the live config reads the Settings controls rely on.
  3. The real engine: every mode's begin_* path silences the playlist
     the moment its block owns the session folder, and the menus
     bring it back afterwards.

Gameplay audio is a recorded experimental condition (cue click, hit
chime, rhythm songs), so "no menu track under a block, ever" is a
data-integrity rule, not a taste rule.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class _FakeAudio:
    """Stands in for AudioEngine: tracks who holds the music stream.
    Mirrors the real guard (menu_play refuses while a game owns the
    stream) so the player is tested against the contract the real
    engine enforces."""

    def __init__(self) -> None:
        self.menu_path: str | None = None
        self.menu_volume: float | None = None
        self.game_song: str | None = None
        self.metronome = False
        self.play_log: list[str] = []
        self.refused = 0

    # -- surface the menu player uses --------------------------------
    def game_stream_active(self) -> bool:
        return self.game_song is not None or self.metronome

    def menu_play(self, path, volume=1.0) -> bool:
        if self.game_stream_active():
            self.refused += 1
            return False
        self.menu_path = str(path)
        self.menu_volume = volume
        self.play_log.append(Path(str(path)).name)
        return True

    def menu_stop(self) -> None:
        self.menu_path = None

    def menu_set_volume(self, volume) -> None:
        self.menu_volume = volume

    def menu_busy(self) -> bool:
        return self.menu_path is not None

    # -- the Force Pilot background track (audio/block_music.py) -----
    block_path: str | None = None
    block_volume: float | None = None
    block_log: list = []

    def block_music_play(self, path, volume=1.0) -> bool:
        if self.game_stream_active():
            return False
        self.menu_path = None
        self.block_path = str(path)
        self.block_volume = volume
        self.block_log = list(self.block_log) + [Path(str(path)).name]
        return True

    def block_music_stop(self) -> None:
        self.block_path = None

    def block_music_set_volume(self, volume) -> None:
        self.block_volume = volume

    def block_music_busy(self) -> bool:
        return self.block_path is not None

    # -- surface the game engine uses during a block -----------------
    def play_song(self, path, loops=0, start_s=0.0) -> bool:
        self.menu_path = None
        self.block_path = None
        self.game_song = str(path)
        return True

    def start_metronome(self, bpm, first_click_in_s=None) -> None:
        self.menu_path = None
        self.block_path = None
        self.metronome = True

    def stop(self) -> None:
        self.game_song = None
        self.metronome = False
        self.menu_path = None
        self.block_path = None

    def song_time(self) -> float:
        return 0.0

    @property
    def is_playing(self) -> bool:
        return False

    def set_trial_gain(self, gain) -> None:
        pass

    def set_volumes(self, **kw) -> None:
        pass

    def play_hit(self, combo=0) -> None:
        pass

    def play_miss(self) -> None:
        pass

    def play_stim(self, lane) -> None:
        pass

    def tick(self) -> None:
        pass

    def shutdown(self) -> None:
        pass


class _FakeCfg:
    """Just enough Config for the player: dotted get + resolve_path."""

    def __init__(self, root: Path, tracks: list[str],
                 enabled: bool = True, volume: float = 0.5) -> None:
        self.root = Path(root)
        self.data = {
            "audio": {
                "music_dir": "music",
                "menu_music_enabled": enabled,
                "menu_music_volume": volume,
                "menu_music_tracks": list(tracks),
            },
        }

    def get(self, key, default=None):
        node = self.data
        for part in key.split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            else:
                return default
        return node

    def resolve_path(self, value):
        return self.root / value


class _Clock:
    def __init__(self, t: float = 1000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def step(self, dt: float) -> None:
        self.t += dt


def _player(tmp: str, tracks=("a.mp3", "b.mp3", "c.mp3"),
            listed=None, enabled=True, volume=0.5):
    """A MenuMusicPlayer on a fake audio + fake cfg + fake clock."""
    from finger_rehab.audio.menu_music import MenuMusicPlayer
    root = Path(tmp)
    (root / "music").mkdir(parents=True, exist_ok=True)
    for name in tracks:
        (root / "music" / name).write_bytes(b"not real audio")
    cfg = _FakeCfg(root, list(listed if listed is not None else tracks),
                   enabled=enabled, volume=volume)
    audio = _FakeAudio()
    p = MenuMusicPlayer(audio, cfg)
    clock = _Clock()
    p._clock = clock
    return p, audio, cfg, clock


class AudioEngineMenuGuardTests(unittest.TestCase):
    """The stream-sharing guards on the real AudioEngine, mixer
    patched out. These are what make it impossible for the menu side
    to stomp a rhythm song or the metronome."""

    def _engine(self):
        from finger_rehab.audio.engine import AudioEngine
        a = AudioEngine()
        a._initialised = True
        return a

    def test_menu_play_refuses_while_game_song_loaded(self) -> None:
        from finger_rehab.audio import engine as audio_mod
        a = self._engine()
        a._song_path = "/tmp/rhythm-song.mp3"
        with patch.object(audio_mod.pygame.mixer, "music") as music:
            with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
                self.assertFalse(a.menu_play(f.name))
            music.load.assert_not_called()
            music.play.assert_not_called()
        self.assertFalse(a._menu_active)

    def test_menu_play_refuses_while_metronome_running(self) -> None:
        from finger_rehab.audio import engine as audio_mod
        a = self._engine()
        a._metronome_period = 0.5
        with patch.object(audio_mod.pygame.mixer, "music") as music:
            with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
                self.assertFalse(a.menu_play(f.name))
            music.load.assert_not_called()

    def test_menu_play_takes_the_stream_when_free(self) -> None:
        from finger_rehab.audio import engine as audio_mod
        a = self._engine()
        with patch.object(audio_mod.pygame.mixer, "music") as music:
            with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
                self.assertTrue(a.menu_play(f.name, volume=0.5))
            music.load.assert_called_once()
            music.play.assert_called_once()
        self.assertTrue(a._menu_active)

    def test_play_song_reclaims_the_stream_from_the_menu(self) -> None:
        # Rhythm starting its song must simply take over: the flag
        # flips so no later menu_stop can kill the game's music.
        from finger_rehab.audio import engine as audio_mod
        a = self._engine()
        a._menu_active = True
        with patch.object(audio_mod.pygame.mixer, "music"):
            with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
                self.assertTrue(a.play_song(f.name))
        self.assertFalse(a._menu_active)
        self.assertIsNotNone(a._song_path)

    def test_start_metronome_reclaims_the_stream(self) -> None:
        from finger_rehab.audio import engine as audio_mod
        a = self._engine()
        a._menu_active = True
        with patch.object(audio_mod.pygame.mixer, "music"):
            a.start_metronome(80.0)
        self.assertFalse(a._menu_active)

    def test_menu_stop_never_stops_a_game_song(self) -> None:
        # A stale menu_stop arriving after rhythm took the stream must
        # not silence the song mid-block.
        from finger_rehab.audio import engine as audio_mod
        a = self._engine()
        a._menu_active = True
        a._song_path = "/tmp/rhythm-song.mp3"
        with patch.object(audio_mod.pygame.mixer, "music") as music:
            a.menu_stop()
            music.stop.assert_not_called()
        self.assertFalse(a._menu_active)

    def test_stop_clears_the_menu_flag(self) -> None:
        from finger_rehab.audio import engine as audio_mod
        a = self._engine()
        a._menu_active = True
        with patch.object(audio_mod.pygame.mixer, "music"), \
             patch.object(audio_mod.pygame.mixer, "stop"):
            a.stop()
        self.assertFalse(a._menu_active)

    def test_menu_methods_noop_before_init(self) -> None:
        from finger_rehab.audio.engine import AudioEngine
        a = AudioEngine()
        self.assertFalse(a.menu_play("/tmp/x.mp3"))
        a.menu_stop()
        a.menu_set_volume(0.5)
        self.assertFalse(a.menu_busy())


class MenuMusicPlayerScreenTests(unittest.TestCase):
    """Which screens the playlist runs on. The set is closed on
    purpose; anything not in it is silent."""

    def test_plays_on_every_menu_screen(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        with tempfile.TemporaryDirectory() as td:
            for key in MenuMusicPlayer.MENU_SCREENS:
                p, audio, _cfg, _clock = _player(td)
                p.update(key, False)
                self.assertTrue(p.is_playing, key)
                self.assertIsNotNone(audio.menu_path, key)

    def test_menu_screen_set_is_exactly_the_menus(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        self.assertEqual(set(MenuMusicPlayer.MENU_SCREENS),
                         {"title", "mode_select", "setup", "results"})

    def test_silent_on_every_other_screen(self) -> None:
        # rhythm_setup matters most: its preview plays through the
        # same mixer.music stream this player would be using.
        with tempfile.TemporaryDirectory() as td:
            for key in ("gameplay", "rhythm", "rhythm_setup", "quick_cal",
                        "calibration", "diagnostics", "syllables",
                        "force_pilot", "buzz_hunt", None):
                p, audio, _cfg, _clock = _player(td)
                p.update(key, False)
                self.assertFalse(p.is_playing, str(key))
                self.assertEqual(audio.play_log, [], str(key))

    def test_block_running_silences_even_a_menu_key(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, _clock = _player(td)
            p.update("mode_select", True)
            self.assertFalse(p.is_playing)
            self.assertEqual(audio.play_log, [])


class MenuMusicPlayerFadeTests(unittest.TestCase):

    def test_fades_out_when_a_block_starts_then_stops(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, clock = _player(td)
            p.update("mode_select", False)
            clock.step(2.0)
            p.update("mode_select", False)
            self.assertTrue(p.is_playing)
            # Block begins: instantly out of "playing", ramping down.
            p.update("gameplay", True)
            self.assertEqual(p.state, "fading")
            clock.step(MenuMusicPlayer.FADE_OUT_S + 0.1)
            p.update("gameplay", True)
            self.assertEqual(p.state, "idle")
            self.assertIsNone(audio.menu_path)

    def test_fade_is_shorter_than_the_minimum_countdown(self) -> None:
        # Test Mode trims GET READY to 1.5 s; the fade must be gone
        # inside that so no trial can fire over menu music.
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        self.assertLess(MenuMusicPlayer.FADE_OUT_S, 1.5)

    def test_disable_mid_play_fades_out(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        with tempfile.TemporaryDirectory() as td:
            p, audio, cfg, clock = _player(td)
            p.update("title", False)
            self.assertTrue(p.is_playing)
            cfg.data["audio"]["menu_music_enabled"] = False
            p.update("title", False)
            self.assertEqual(p.state, "fading")
            clock.step(MenuMusicPlayer.FADE_OUT_S + 0.1)
            p.update("title", False)
            self.assertEqual(p.state, "idle")
            self.assertIsNone(audio.menu_path)

    def test_disabled_never_starts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, _clock = _player(td, enabled=False)
            for _ in range(3):
                p.update("title", False)
            self.assertEqual(audio.play_log, [])
            self.assertFalse(p.is_playing)

    def test_stop_now_is_immediate(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, _clock = _player(td)
            p.update("title", False)
            self.assertTrue(p.is_playing)
            p.stop_now()
            self.assertEqual(p.state, "idle")
            self.assertIsNone(audio.menu_path)


class MenuMusicPlayerVolumeTests(unittest.TestCase):

    def test_default_level_is_half_as_loud_as_the_game_music(self) -> None:
        """No number in the config means the derived level: 10 dB
        under the rhythm song (which plays at master), an amplitude
        of 0.32 on top of master. Not 0.5, which is only 6 dB down."""
        from finger_rehab.audio.menu_music import (HALF_LOUDNESS,
                                                   MenuMusicPlayer,
                                                   menu_music_level)
        self.assertAlmostEqual(HALF_LOUDNESS, 10 ** (-10 / 20), places=2)
        self.assertLess(HALF_LOUDNESS, 0.5)
        with tempfile.TemporaryDirectory() as td:
            p, audio, cfg, clock = _player(td, volume=None)
            self.assertAlmostEqual(menu_music_level(cfg), HALF_LOUDNESS)
            p.update("title", False)
            clock.step(MenuMusicPlayer.FADE_IN_S + 0.1)
            p.update("title", False)
            self.assertAlmostEqual(audio.menu_volume, HALF_LOUDNESS,
                                   places=3)
            # A number pins it; a broken value falls back.
            cfg.data["audio"]["menu_music_volume"] = 0.7
            self.assertAlmostEqual(menu_music_level(cfg), 0.7)
            cfg.data["audio"]["menu_music_volume"] = "loud"
            self.assertAlmostEqual(menu_music_level(cfg), HALF_LOUDNESS)

    def test_shipped_config_derives_the_level(self) -> None:
        import yaml
        repo = Path(__file__).resolve().parents[1]
        cfg = yaml.safe_load(
            (repo / "config" / "default.yaml").read_text())
        self.assertIsNone(cfg["audio"]["menu_music_volume"])

    def test_the_mute_fades_the_track_out_and_keeps_it_off(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, clock = _player(td)
            p.update("title", False)
            self.assertTrue(p.is_playing)
            p.update("title", False, muted=True)
            self.assertEqual(p.state, "fading")
            clock.step(MenuMusicPlayer.FADE_OUT_S + 0.1)
            p.update("title", False, muted=True)
            self.assertEqual(p.state, "idle")
            self.assertIsNone(audio.menu_path)
            for _ in range(3):
                clock.step(1.0)
                p.update("mode_select", False, muted=True)
            self.assertFalse(p.is_playing)
            # Unmuted: back on.
            p.update("mode_select", False, muted=False)
            self.assertTrue(p.is_playing)

    def test_volume_reaches_the_slider_level_after_fade_in(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, clock = _player(td, volume=0.6)
            p.update("title", False)
            clock.step(MenuMusicPlayer.FADE_IN_S + 0.1)
            p.update("title", False)
            self.assertAlmostEqual(audio.menu_volume, 0.6, places=3)

    def test_volume_slider_is_live_between_tracks_too(self) -> None:
        # The player reads cfg every tick, which is what lets the
        # Settings slider work with no wiring to the player at all.
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        with tempfile.TemporaryDirectory() as td:
            p, audio, cfg, clock = _player(td, volume=0.6)
            p.update("title", False)
            clock.step(MenuMusicPlayer.FADE_IN_S + 0.1)
            p.update("title", False)
            cfg.data["audio"]["menu_music_volume"] = 0.2
            p.update("title", False)
            self.assertAlmostEqual(audio.menu_volume, 0.2, places=3)

    def test_results_screen_start_is_ducked_then_rises(self) -> None:
        # The results chime is still sounding when the screen lands,
        # so the track opens held down instead of fighting it.
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, clock = _player(td, volume=0.8)
            p.update("results", False)
            self.assertAlmostEqual(
                audio.menu_volume, 0.8 * MenuMusicPlayer.DUCK_FACTOR,
                places=3)
            # Still held during the duck window.
            clock.step(MenuMusicPlayer.DUCK_S * 0.5)
            p.update("results", False)
            self.assertAlmostEqual(
                audio.menu_volume, 0.8 * MenuMusicPlayer.DUCK_FACTOR,
                places=3)
            # Fully up after duck + rise.
            clock.step(MenuMusicPlayer.DUCK_S
                       + MenuMusicPlayer.FADE_IN_S + 0.1)
            p.update("results", False)
            self.assertAlmostEqual(audio.menu_volume, 0.8, places=3)

    def test_ordinary_menus_start_from_silence_not_ducked_hold(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, clock = _player(td, volume=0.8)
            p.update("title", False)
            self.assertAlmostEqual(audio.menu_volume, 0.0, places=3)
            clock.step(MenuMusicPlayer.FADE_IN_S + 0.1)
            p.update("title", False)
            self.assertAlmostEqual(audio.menu_volume, 0.8, places=3)


class MenuMusicPlaylistTests(unittest.TestCase):

    def test_whole_set_plays_before_any_repeat(self) -> None:
        tracks = ("a.mp3", "b.mp3", "c.mp3", "d.mp3")
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, clock = _player(td, tracks=tracks)
            while len(audio.play_log) < 8:
                p.update("title", False)
                clock.step(0.1)
                # End the current track so the next update advances.
                audio.menu_path = None
            self.assertEqual(set(audio.play_log[:4]), set(tracks))
            self.assertEqual(set(audio.play_log[4:8]), set(tracks))

    def test_no_back_to_back_repeat_across_the_cycle_seam(self) -> None:
        tracks = ("a.mp3", "b.mp3", "c.mp3")
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, clock = _player(td, tracks=tracks)
            while len(audio.play_log) < 9:
                p.update("title", False)
                clock.step(0.1)
                audio.menu_path = None
            for prev, cur in zip(audio.play_log, audio.play_log[1:]):
                self.assertNotEqual(prev, cur)

    def test_playlist_is_the_configured_list_not_the_folder(self) -> None:
        # Three files on disk, two listed: rhythm's library can grow
        # without the menus picking the new tracks up.
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, clock = _player(
                td, tracks=("a.mp3", "b.mp3", "rhythm_only.mp3"),
                listed=["a.mp3", "b.mp3"])
            names = {t.name for t in p._tracks}
            self.assertEqual(names, {"a.mp3", "b.mp3"})
            while len(audio.play_log) < 4:
                p.update("title", False)
                clock.step(0.1)
                audio.menu_path = None
            self.assertNotIn("rhythm_only.mp3", audio.play_log)

    def test_missing_files_are_skipped_not_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p, _audio, _cfg, _clock = _player(
                td, tracks=("a.mp3",), listed=["a.mp3", "gone.mp3"])
            self.assertEqual([t.name for t in p._tracks], ["a.mp3"])
            p.update("title", False)
            self.assertTrue(p.is_playing)

    def test_no_tracks_means_silent_not_crashing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, _clock = _player(td, tracks=(), listed=[])
            p.update("title", False)
            self.assertFalse(p.is_playing)
            self.assertEqual(audio.play_log, [])

    def test_refused_start_backs_off_instead_of_hammering(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, clock = _player(td)
            audio.game_song = "somebody-elses.mp3"
            p.update("title", False)
            self.assertEqual(audio.refused, 1)
            p.update("title", False)
            p.update("title", False)
            self.assertEqual(audio.refused, 1)
            clock.step(MenuMusicPlayer.RETRY_S + 0.1)
            p.update("title", False)
            self.assertEqual(audio.refused, 2)

    def test_shipped_config_lists_six_real_files(self) -> None:
        """The default playlist's files exist in assets/music with a
        LICENCE txt each, the same attribution pattern as every other
        track in the folder."""
        import yaml
        repo = Path(__file__).resolve().parents[1]
        cfg = yaml.safe_load(
            (repo / "config" / "default.yaml").read_text())
        tracks = cfg["audio"]["menu_music_tracks"]
        self.assertEqual(len(tracks), 6)
        music = repo / "assets" / "music"
        for name in tracks:
            self.assertTrue((music / name).exists(), name)
            licence = music / (Path(name).stem + ".LICENCE.txt")
            self.assertTrue(licence.exists(), licence.name)
            body = licence.read_text()
            self.assertIn("Kevin MacLeod", body)
            self.assertIn("CC BY 4.0", body)


def _engine_with_fake_audio(source=None):
    """A real engine on the shipped config with real block lifecycle
    (temp sessions dir via conftest), mocked screens, and the fake
    audio so the menu player runs without a mixer."""
    import pygame
    pygame.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    # Keep block teardown fast: the HTML report + charts are not what
    # these tests measure, and the sweep below closes ten blocks.
    cfg.data.setdefault("report", {})["enabled"] = False
    eng = GameEngine(cfg, source or KeyboardOnlySource())
    eng._screens = {k: MagicMock() for k in (
        "title", "mode_select", "setup", "rhythm_setup", "gameplay",
        "rhythm", "syllables", "force_pilot", "buzz_hunt",
        "results", "diagnostics", "calibration", "quick_cal")}
    eng.audio = _FakeAudio()
    return eng


def _motor_source():
    src = MagicMock()
    src.provides_samples = True
    src.is_connected = True
    src.name = "fake-two-board"
    src.hand_modes_available = {"right", "left", "both"}
    src.send_command = lambda c: True
    src.get_sample = lambda timeout=0.0: None
    return src


class EngineMenuMusicTests(unittest.TestCase):
    """The real engine: menus play, blocks never do."""

    def tearDown(self) -> None:
        import pygame
        pygame.quit()

    def _tick(self, eng, n=1):
        for _ in range(n):
            eng._tick_menu_music()

    def test_menus_play_and_a_real_block_silences(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        with tempfile.TemporaryDirectory() as td:
            eng = _engine_with_fake_audio()
            eng.cfg.data["session"]["data_dir"] = td
            eng.show_mode_select()
            self._tick(eng)
            player = eng.menu_music
            self.assertIsNotNone(player)
            clock = _Clock()
            player._clock = clock
            self.assertTrue(player.is_playing)
            # A real classic game via the real starter: real
            # _begin_block, real loggers, real session folder.
            self.assertTrue(eng.begin_game("classic"))
            self.assertTrue(eng.block_is_running())
            self._tick(eng)
            self.assertNotEqual(player.state, "playing")
            clock.step(MenuMusicPlayer.FADE_OUT_S + 0.1)
            self._tick(eng)
            self.assertEqual(player.state, "idle")
            self.assertIsNone(eng.audio.menu_path)
            # While the block runs, no amount of ticking starts music.
            clock.step(30.0)
            self._tick(eng, n=5)
            self.assertEqual(player.state, "idle")
            self.assertIsNone(eng.audio.menu_path)
            # Game over: the results screen is a menu again.
            eng.finish_block()
            self.assertFalse(eng.block_is_running())
            self._tick(eng)
            self.assertTrue(player.is_playing)

    def test_no_mode_ever_runs_under_menu_music(self) -> None:
        """Every begin_* starter, driven for real: the moment the
        block owns the session folder the playlist is out of
        "playing", and it is fully stopped before the shortest GET
        READY can end."""
        from finger_rehab.audio.beatmap import Beatmap, Note
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        starters = ["classic", "adaptive", "mirror", "reaction",
                    "pattern", "chords", "syllables", "force_pilot",
                    "buzz_hunt", "echo", "rhythm"]
        with tempfile.TemporaryDirectory() as td:
            eng = _engine_with_fake_audio(source=_motor_source())
            eng.cfg.data["session"]["data_dir"] = td
            eng.session.participant = "Music Test"
            self._tick(eng)
            clock = _Clock()
            eng.menu_music._clock = clock
            for mode in starters:
                eng.show_mode_select()
                clock.step(5.0)
                self._tick(eng, n=2)
                self.assertTrue(eng.menu_music.is_playing, mode)
                if mode == "rhythm":
                    bm = Beatmap(title="Test", bpm=120.0, song=None,
                                 notes=[Note(t=1.0, lane=0),
                                        Note(t=2.0, lane=1)])
                    eng.begin_rhythm_block(bm)
                else:
                    eng.set_hand_mode("both" if mode == "mirror"
                                      else "right")
                    getattr(eng, f"begin_{mode}_block")()
                self.assertTrue(eng.block_is_running(), mode)
                self._tick(eng)
                self.assertNotEqual(eng.menu_music.state, "playing",
                                    mode)
                clock.step(MenuMusicPlayer.FADE_OUT_S + 0.1)
                self._tick(eng)
                self.assertEqual(eng.menu_music.state, "idle", mode)
                self.assertIsNone(eng.audio.menu_path, mode)
                # Close this block out and return to the hub.
                eng._abandon_if_in_block()
                eng.mode = None
                eng.audio.stop()

    def test_rhythm_setup_screen_gets_no_menu_music(self) -> None:
        # The song picker previews tracks on the shared stream, so the
        # playlist must already be gone there.
        eng = _engine_with_fake_audio()
        eng.show_rhythm_setup()
        self._tick(eng, n=3)
        self.assertIsNotNone(eng.menu_music)
        self.assertFalse(eng.menu_music.is_playing)
        self.assertIsNone(eng.audio.menu_path)

    def test_rhythm_song_playback_is_untouched(self) -> None:
        # With the menu track up, rhythm starting its song takes the
        # stream and keeps it; the player never gets it back while the
        # block runs.
        with tempfile.TemporaryDirectory() as td:
            eng = _engine_with_fake_audio()
            eng.cfg.data["session"]["data_dir"] = td
            eng.show_mode_select()
            self._tick(eng)
            clock = _Clock()
            eng.menu_music._clock = clock
            self.assertTrue(eng.menu_music.is_playing)
            eng._begin_block("rhythm")
            # The mode starts its song mid-block, exactly as
            # RhythmMode.update does.
            eng.audio.play_song("/tmp/some-song.mp3")
            self.assertEqual(eng.audio.game_song, "/tmp/some-song.mp3")
            clock.step(5.0)
            self._tick(eng, n=3)
            # The game song is still the stream owner.
            self.assertEqual(eng.audio.game_song, "/tmp/some-song.mp3")
            self.assertIsNone(eng.audio.menu_path)
            eng._abandon_if_in_block()

    def test_tick_without_audio_is_harmless(self) -> None:
        eng = _engine_with_fake_audio()
        eng.audio = None
        eng.show_mode_select()
        self._tick(eng, n=2)
        self.assertIsNone(eng.menu_music)


class SettingsMenuMusicControlTests(unittest.TestCase):
    """The Settings screen's switch and slider write the same config
    keys the player reads live."""

    def setUp(self) -> None:
        import pygame
        pygame.init()
        pygame.font.init()
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        from finger_rehab.ui.screens import DiagnosticsScreen
        cfg = Config.load()
        cfg.data.setdefault("ui", {})["resolution"] = [1280, 800]
        self.eng = GameEngine(cfg, KeyboardOnlySource())
        self.screen = DiagnosticsScreen(self.eng)

    def tearDown(self) -> None:
        import pygame
        pygame.quit()

    def test_toggle_flips_config_and_stops_the_player_now(self) -> None:
        self.eng.audio = _FakeAudio()
        self.eng.show_title = lambda: None
        self.eng._screens = {"title": MagicMock()}
        self.eng.screen_obj = self.eng._screens["title"]
        self.eng._tick_menu_music()
        self.assertTrue(self.eng.menu_music.is_playing)
        self.screen._toggle_menu_music()
        self.assertFalse(
            self.eng.cfg.get("audio.menu_music_enabled"))
        self.assertEqual(self.eng.menu_music.state, "idle")
        self.assertIsNone(self.eng.audio.menu_path)
        # And back on.
        self.screen._toggle_menu_music()
        self.assertTrue(self.eng.cfg.get("audio.menu_music_enabled"))

    def test_music_slider_opens_on_the_derived_level(self) -> None:
        from finger_rehab.audio.menu_music import menu_music_level
        self.eng.cfg.data["audio"]["menu_music_volume"] = None
        from finger_rehab.ui.screens import DiagnosticsScreen
        screen = DiagnosticsScreen(self.eng)
        # The knob snaps to 5 percent steps, so within one step.
        self.assertAlmostEqual(screen._vol_sliders["music"].value,
                               menu_music_level(self.eng.cfg), delta=0.03)

    def test_music_slider_exists_and_saves_its_key(self) -> None:
        self.assertIn("music", self.screen._vol_sliders)
        self.screen._vol_sliders["music"].value = 0.35
        self.screen._apply_volumes_live()
        self.assertAlmostEqual(
            self.eng.cfg.get("audio.menu_music_volume"), 0.35)
        self.screen._save_volumes()
        # conftest redirects USER_OVERRIDES to a temp file; read back
        # through a fresh load to prove the key persisted.
        from finger_rehab.config import Config
        cfg2 = Config.load()
        self.assertAlmostEqual(
            float(cfg2.get("audio.menu_music_volume")), 0.35)


if __name__ == "__main__":
    unittest.main()
