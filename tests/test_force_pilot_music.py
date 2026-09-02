"""Background music in Force Pilot, and nowhere else.

The rule everywhere else is no music under a block. Force Pilot is the
one exception, and these tests keep it that narrow:

  1. audio/block_music.py: plays only for force_pilot, only after the
     menu playlist has faded, never over a rhythm song, stops on
     pause and at block end, sits under the menu level, and the lab
     config turns it off.
  2. AudioEngine's block_music_* guards, mixer patched out, so the
     block track can never take the stream off a game song and a
     game song always takes it back.
  3. The real engine: a Force Pilot block on a two-board rig starts
     the track once the menus have faded, a reaction block never
     does, and the track is gone when the block ends.
  4. Scoring is blind to it: the same run scored with the track on
     and off writes the same trial row.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_menu_music import _Clock, _FakeAudio, _FakeCfg  # noqa: E402


def _player(tmp: str, enabled=True, volume=0.2, tracks=("a.mp3", "b.mp3")):
    from finger_rehab.audio.block_music import BlockMusicPlayer
    root = Path(tmp)
    (root / "music").mkdir(parents=True, exist_ok=True)
    for name in tracks:
        (root / "music" / name).write_bytes(b"not real audio")
    cfg = _FakeCfg(root, list(tracks))
    cfg.data["force_pilot"] = {"music_enabled": enabled,
                               "music_volume": volume}
    cfg.data["rhythm"] = {"music_enabled": True, "music_volume": 0.5}
    audio = _FakeAudio()
    p = BlockMusicPlayer(audio, cfg)
    clock = _Clock()
    p._clock = clock
    return p, audio, cfg, clock


# ---------------------------------------------------------------------
# 1. the player
# ---------------------------------------------------------------------
class BlockMusicPlayerTests(unittest.TestCase):
    def test_only_force_pilot_and_only_after_the_menu_fade(self) -> None:
        from finger_rehab.audio.block_music import BlockMusicPlayer
        self.assertEqual(BlockMusicPlayer.BLOCK_MODES, ("force_pilot",))
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, _clock = _player(td)
            p.update("force_pilot", menu_state="fading")
            self.assertFalse(p.is_playing)
            p.update("force_pilot", menu_state="idle")
            self.assertTrue(p.is_playing)
            self.assertIsNotNone(audio.block_path)

    def test_every_other_mode_stays_silent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, _clock = _player(td)
            for mode in ("rhythm", "reaction", "lighthouse", "buzz_hunt",
                         "chords", "echo", "pattern", "mirror",
                         "adaptive", "syllables", "classic", None):
                p.update(mode, menu_state="idle")
                self.assertFalse(p.is_playing, str(mode))
            self.assertEqual(audio.block_log, [])

    def test_disabled_never_starts(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, _clock = _player(td, enabled=False)
            for _ in range(3):
                p.update("force_pilot", menu_state="idle")
            self.assertFalse(p.is_playing)
            self.assertEqual(audio.block_log, [])

    def test_rises_to_its_level_and_sits_under_the_menu_level(self) -> None:
        from finger_rehab.audio.block_music import BlockMusicPlayer
        from finger_rehab.audio.menu_music import HALF_LOUDNESS
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, clock = _player(td, volume=0.2)
            p.update("force_pilot", menu_state="idle")
            self.assertAlmostEqual(audio.block_volume, 0.0, places=3)
            clock.step(BlockMusicPlayer.FADE_IN_S + 0.1)
            p.update("force_pilot", menu_state="idle")
            self.assertAlmostEqual(audio.block_volume, 0.2, places=3)
            self.assertLess(0.2, HALF_LOUDNESS)

    def test_pause_and_block_end_stop_it(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, _clock = _player(td)
            p.update("force_pilot", menu_state="idle")
            self.assertTrue(p.is_playing)
            p.update("force_pilot", paused=True, menu_state="idle")
            self.assertFalse(p.is_playing)
            self.assertIsNone(audio.block_path)
            p.update("force_pilot", paused=False, menu_state="idle")
            self.assertTrue(p.is_playing)
            p.update(None, menu_state="idle")
            self.assertFalse(p.is_playing)
            self.assertIsNone(audio.block_path)

    def test_never_starts_over_a_game_song(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, _clock = _player(td)
            audio.game_song = "rhythm.mp3"
            p.update("force_pilot", menu_state="idle")
            self.assertFalse(p.is_playing)
            self.assertEqual(audio.block_log, [])

    def test_the_next_track_follows_when_one_runs_out(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p, audio, _cfg, clock = _player(td)
            p.update("force_pilot", menu_state="idle")
            first = audio.block_path
            audio.block_path = None      # ran out
            clock.step(0.1)
            p.update("force_pilot", menu_state="idle")
            self.assertTrue(p.is_playing)
            self.assertIsNotNone(audio.block_path)
            self.assertEqual(len(audio.block_log), 2)
            self.assertIsNotNone(first)

    def test_shipped_and_lab_configs(self) -> None:
        import yaml
        repo = Path(__file__).resolve().parents[1]
        default = yaml.safe_load(
            (repo / "config" / "default.yaml").read_text())
        self.assertTrue(default["force_pilot"]["music_enabled"])
        self.assertLess(default["force_pilot"]["music_volume"], 0.316)
        for mode in ("rhythm", "reaction", "lighthouse", "buzz_hunt",
                     "chords", "echo", "pattern", "mirror", "adaptive",
                     "syllables"):
            self.assertNotIn("music_enabled", default.get(mode, {}), mode)
        lab = yaml.safe_load((repo / "config" / "eeg_lab.yaml").read_text())
        self.assertFalse(lab["force_pilot"]["music_enabled"])
        # The lab file lays over the default, so the merged view is
        # what the engine reads.
        from finger_rehab.config import Config
        cfg = Config.load(repo / "config" / "eeg_lab.yaml")
        self.assertFalse(cfg.get("force_pilot.music_enabled"))
        self.assertTrue(cfg.get("eeg.enabled"))


# ---------------------------------------------------------------------
# 2. the AudioEngine guards
# ---------------------------------------------------------------------
class AudioEngineBlockGuardTests(unittest.TestCase):
    def _engine(self):
        from finger_rehab.audio.engine import AudioEngine
        a = AudioEngine()
        a._initialised = True
        return a

    def test_refuses_while_a_game_owns_the_stream(self) -> None:
        from finger_rehab.audio import engine as audio_mod
        a = self._engine()
        a._song_path = "/tmp/rhythm-song.mp3"
        with patch.object(audio_mod.pygame.mixer, "music") as music:
            with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
                self.assertFalse(a.block_music_play(f.name, 0.2))
            music.load.assert_not_called()
        self.assertFalse(a._block_music_active)

    def test_takes_the_stream_when_free_and_a_song_takes_it_back(
            self) -> None:
        from finger_rehab.audio import engine as audio_mod
        a = self._engine()
        with patch.object(audio_mod.pygame.mixer, "music") as music:
            with tempfile.NamedTemporaryFile(suffix=".mp3") as f:
                self.assertTrue(a.block_music_play(f.name, 0.2))
                music.load.assert_called_once()
                self.assertTrue(a._block_music_active)
                self.assertFalse(a.game_stream_active())
                self.assertTrue(a.play_song(f.name))
            self.assertFalse(a._block_music_active)
            music.stop.assert_not_called()
            # A stale block_music_stop must not stop the game song.
            a.block_music_stop()
            music.stop.assert_not_called()

    def test_stop_and_metronome_clear_the_flag(self) -> None:
        from finger_rehab.audio import engine as audio_mod
        a = self._engine()
        a._block_music_active = True
        with patch.object(audio_mod.pygame.mixer, "music"), \
             patch.object(audio_mod.pygame.mixer, "stop"):
            a.stop()
            self.assertFalse(a._block_music_active)
            a._block_music_active = True
            a.start_metronome(80.0)
            self.assertFalse(a._block_music_active)

    def test_noop_before_init(self) -> None:
        from finger_rehab.audio.engine import AudioEngine
        a = AudioEngine()
        self.assertFalse(a.block_music_play("/tmp/x.mp3"))
        a.block_music_stop()
        a.block_music_set_volume(0.2)
        self.assertFalse(a.block_music_busy())


# ---------------------------------------------------------------------
# 3. the real engine
# ---------------------------------------------------------------------
class _Rig:
    """A two-board rig that never delivers a sample (the study battery
    tests' rig): every mode opens, nothing ticks."""
    provides_samples = True
    is_connected = True
    name = "fake-two-board"
    hand_modes_available = {"right", "left", "both"}

    def start(self) -> None: ...
    def stop(self) -> None: ...

    def get_sample(self, timeout: float = 0.0):
        return None

    def send_command(self, cmd: str) -> bool:
        return True


class EngineBlockMusicTests(unittest.TestCase):
    def setUp(self) -> None:
        import pygame
        pygame.init()
        self._td = tempfile.TemporaryDirectory()
        root = Path(self._td.name)
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["session"]["data_dir"] = str(root / "sessions")
        cfg.data["session"]["prefs_file"] = str(root / "prefs.json")
        cfg.data["audio"]["enabled"] = False
        cfg.data["report"] = {"enabled": False}
        self.eng = GameEngine(cfg, _Rig())
        self.eng._screens = self.eng._build_screens()
        self.eng.audio = _FakeAudio()
        self.clock = _Clock()
        self.eng.begin_session("P03", "30", dominant_hand="right")
        self.eng._uncal_ack = {"left", "right"}

    def tearDown(self) -> None:
        import pygame
        try:
            self.eng._abandon_if_in_block()
            self.eng._close_loggers()
        except Exception:
            pass
        self._td.cleanup()
        pygame.quit()

    def _tick(self, dt: float = 0.0, n: int = 1) -> None:
        for _ in range(n):
            self.clock.step(dt)
            self.eng._tick_menu_music()
            self.eng._tick_block_music()

    def _hub(self) -> None:
        self.eng.show_mode_select()
        self._tick()
        self.eng.menu_music._clock = self.clock
        if self.eng.block_music is not None:
            self.eng.block_music._clock = self.clock
        self._tick(5.0)
        self.assertTrue(self.eng.menu_music.is_playing)

    def test_force_pilot_gets_the_track_after_the_menu_fade(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        self._hub()
        self.assertTrue(self.eng.begin_game("force_pilot", "right"))
        self.assertTrue(self.eng.block_is_running())
        self.eng.block_music._clock = self.clock
        self._tick()
        # Menu fading, nothing under it yet.
        self.assertIsNone(self.eng.audio.block_path)
        self._tick(MenuMusicPlayer.FADE_OUT_S + 0.1)
        self.assertEqual(self.eng.menu_music.state, "idle")
        self.assertTrue(self.eng.block_music.is_playing)
        self.assertIsNotNone(self.eng.audio.block_path)
        self.assertIsNone(self.eng.audio.menu_path)
        # Pause silences it; resume brings it back.
        self.eng._pause_now()
        self._tick()
        self.assertIsNone(self.eng.audio.block_path)
        self.eng._resume_now()
        self._tick()
        self.assertIsNotNone(self.eng.audio.block_path)
        # Block over: track gone, menus back on the results screen.
        self.eng.finish_block()
        self._tick()
        self.assertIsNone(self.eng.audio.block_path)
        self.assertFalse(self.eng.block_music.is_playing)
        self.assertTrue(self.eng.menu_music.is_playing)

    def test_no_other_block_gets_a_track(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        for mode in ("reaction", "lighthouse", "buzz_hunt", "chords",
                     "echo"):
            self._hub()
            self.assertTrue(self.eng.begin_game(mode, "right"), mode)
            self.eng.block_music._clock = self.clock
            self._tick(MenuMusicPlayer.FADE_OUT_S + 0.1, n=3)
            self.assertIsNone(self.eng.audio.block_path, mode)
            self.assertFalse(self.eng.block_music.is_playing, mode)
            self.eng._abandon_if_in_block()

    def test_lab_config_keeps_force_pilot_silent(self) -> None:
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        self.eng.cfg.data["force_pilot"]["music_enabled"] = False
        self._hub()
        self.assertTrue(self.eng.begin_game("force_pilot", "right"))
        self.eng.block_music._clock = self.clock
        self._tick(MenuMusicPlayer.FADE_OUT_S + 0.1, n=3)
        self.assertIsNone(self.eng.audio.block_path)

    def test_the_track_never_reaches_the_raw_or_trial_logs(self) -> None:
        # The track is presentation only: nothing about it is logged
        # as an event, so a block's data reads the same with it on.
        from finger_rehab.audio.menu_music import MenuMusicPlayer
        self._hub()
        self.assertTrue(self.eng.begin_game("force_pilot", "right"))
        self.eng.block_music._clock = self.clock
        self._tick(MenuMusicPlayer.FADE_OUT_S + 0.1, n=3)
        self.assertTrue(self.eng.block_music.is_playing)
        root = Path(self.eng.session_paths.root)
        self.eng.finish_block()
        raw = (root / "raw.csv").read_text(encoding="utf-8").lower()
        self.assertNotIn("music", raw)


# ---------------------------------------------------------------------
# 4. scoring is blind to the track
# ---------------------------------------------------------------------
class ScoringUnaffectedTests(unittest.TestCase):
    def _score_run(self, music: bool) -> tuple[dict, dict]:
        from tests.test_force_pilot import (_engine, _fresh_profile, _mode,
                                            _play_run, _to_run_phase)
        e = _engine(cfg_extra={"force_pilot.music_enabled": music,
                               "force_pilot.music_volume": 0.2})
        e.audio = _FakeAudio()
        if music:
            e.audio.block_music_play("/tmp/track.mp3", 0.2)
        e.calibration_profiles["right"] = _fresh_profile()
        m = _mode(e)
        t = _to_run_phase(m)
        _play_run(m, t, lambda t_run, target: target + 3.0)
        rec = m._records[0]
        # The written cells only: the stub engine's identity fields
        # are MagicMocks, which differ by object and say nothing.
        row = {k: v for k, v in e.trial_logger.rows[0].items()
               if isinstance(v, (str, int, float, type(None)))}
        return {"tic": rec.tic_frac, "mae": rec.mae_pct,
                "stalls": rec.stalls, "rings": rec.rings_collected}, row

    def test_same_run_same_row_with_the_track_on_or_off(self) -> None:
        stats_on, row_on = self._score_run(True)
        stats_off, row_off = self._score_run(False)
        self.assertEqual(stats_on, stats_off)
        for key in ("early_late", "waveform_params", "segments",
                    "points", "rt_ms", "error_type"):
            self.assertEqual(row_on.get(key), row_off.get(key), key)
        self.assertEqual(row_on, row_off)


if __name__ == "__main__":
    unittest.main()
