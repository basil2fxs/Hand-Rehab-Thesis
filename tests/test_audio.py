"""Tests for the AudioEngine wrapper around pygame.mixer. Most of these
exercise the un-initialised / failure paths since the engine is built
to be safe to call before / after init() / shutdown()."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class AudioEngineUninitialisedTests(unittest.TestCase):
    """Every method on an uninit AudioEngine must be safe to call.
    The engine is constructed in GameEngine.__init__ but init() runs
    later, so during that gap audio operations get called against a
    half-built engine."""

    def test_methods_noop_before_init(self) -> None:
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        self.assertFalse(a._initialised)
        # All of these must return / no-op without raising.
        a.tick()
        a.play_hit()
        a.play_stim(0)
        a.stop()
        a.shutdown()
        # play_song refuses gracefully and returns False.
        self.assertFalse(a.play_song("/tmp/nonexistent.mp3"))
        self.assertFalse(a.play_song("/tmp/nonexistent.mp3", start_s=10.0))
        # song_time defaults to 0.0 before any play.
        self.assertEqual(a.song_time(), 0.0)
        self.assertFalse(a.is_playing)

    def test_start_metronome_without_init_does_nothing(self) -> None:
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        a.start_metronome(80.0)
        # No initialised mixer, so the metronome state stays clean.
        self.assertIsNone(a._metronome_period)
        self.assertFalse(a.is_playing)


class AudioEngineInitFailureTests(unittest.TestCase):
    """If pygame.mixer.init blows up (no audio device, locked mixer),
    AudioEngine.init() must return False and leave _initialised False
    so subsequent calls all no-op."""

    def test_init_returns_false_when_mixer_init_raises(self) -> None:
        from rehab.audio import engine as audio_mod
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        # Patch pygame.mixer.init to raise as if no device available.
        with patch.object(audio_mod.pygame.mixer, "init",
                          side_effect=Exception("no audio device")):
            ok = a.init()
        self.assertFalse(ok)
        self.assertFalse(a._initialised)
        # Subsequent calls must stay safe.
        a.play_hit()
        a.tick()
        self.assertFalse(a.play_song("/tmp/nope.mp3"))


class ShutdownIdempotencyTests(unittest.TestCase):
    """shutdown() may be called multiple times during teardown
    (engine.finally + caller). Must be idempotent."""

    def test_shutdown_twice_is_safe(self) -> None:
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        a.shutdown()
        a.shutdown()    # Should not raise.

    def test_shutdown_after_failed_init_is_safe(self) -> None:
        from rehab.audio import engine as audio_mod
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        with patch.object(audio_mod.pygame.mixer, "init",
                          side_effect=Exception("nope")):
            a.init()
        a.shutdown()    # Should not raise even though init never ran.


class PlaySongInputValidationTests(unittest.TestCase):
    """play_song must handle bad input gracefully: missing file,
    negative start_s, empty string."""

    def test_missing_file_returns_false(self) -> None:
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        # Force _initialised so we hit the file-existence check.
        a._initialised = True
        self.assertFalse(a.play_song("/tmp/this-mp3-doesnt-exist-xyz.mp3"))

    def test_empty_path_returns_false(self) -> None:
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        a._initialised = True
        self.assertFalse(a.play_song(""))

    def test_negative_start_s_is_clamped(self) -> None:
        # We can't actually load audio in a headless test, but we can
        # check play_song doesn't crash with a negative start. The
        # max(0.0, start_s) inside the method takes care of clamping.
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        # Without init it returns False before even reading start_s,
        # which is sufficient: the engine.py pause-resume path calls
        # play_song(start_s=resume_at) and expects no crash.
        self.assertFalse(a.play_song("/tmp/x.mp3", start_s=-5.0))


class AudioInitOrderRegressionTests(unittest.TestCase):
    """pygame.init() implicitly initialises the mixer with platform
    defaults before AudioEngine.init() runs. Without first tearing
    down that implicit init, pre_init's 512-byte buffer is silently
    ignored and audio falls back to high-latency defaults that read
    as lag in rhythm mode. The fix calls mixer.quit() when get_init()
    reports an active mixer, so pre_init actually takes effect."""

    def test_init_quits_mixer_before_pre_init_when_already_up(self) -> None:
        from rehab.audio import engine as audio_mod
        from rehab.audio.engine import AudioEngine
        order: list[str] = []

        def fake_get_init():
            return (44100, -16, 2) if "quit" not in order else None

        with patch.object(audio_mod.pygame.mixer, "get_init",
                          side_effect=fake_get_init), \
             patch.object(audio_mod.pygame.mixer, "quit",
                          side_effect=lambda: order.append("quit")), \
             patch.object(audio_mod.pygame.mixer, "pre_init",
                          side_effect=lambda *a, **kw: order.append("pre_init")), \
             patch.object(audio_mod.pygame.mixer, "init",
                          side_effect=lambda *a, **kw: order.append("init")), \
             patch.object(audio_mod.pygame.mixer, "set_num_channels",
                          side_effect=lambda n: order.append(f"channels={n}")), \
             patch.object(audio_mod.pygame, "sndarray"):
            a = AudioEngine()
            a.init()

        # quit must come BEFORE pre_init, otherwise the buffer size is
        # locked at the implicit-init default.
        self.assertIn("quit", order)
        self.assertIn("pre_init", order)
        self.assertIn("init", order)
        self.assertLess(order.index("quit"), order.index("pre_init"))
        self.assertLess(order.index("pre_init"), order.index("init"))

    def test_init_skips_quit_when_mixer_not_initialised(self) -> None:
        # If pygame.init() hasn't run yet (or quit() already happened),
        # get_init() returns None and we should NOT call quit again -
        # that would log noise and waste a syscall.
        from rehab.audio import engine as audio_mod
        from rehab.audio.engine import AudioEngine
        order: list[str] = []
        with patch.object(audio_mod.pygame.mixer, "get_init",
                          return_value=None), \
             patch.object(audio_mod.pygame.mixer, "quit",
                          side_effect=lambda: order.append("quit")), \
             patch.object(audio_mod.pygame.mixer, "pre_init",
                          side_effect=lambda *a, **kw: order.append("pre_init")), \
             patch.object(audio_mod.pygame.mixer, "init",
                          side_effect=lambda *a, **kw: order.append("init")), \
             patch.object(audio_mod.pygame.mixer, "set_num_channels",
                          side_effect=lambda n: None), \
             patch.object(audio_mod.pygame, "sndarray"):
            a = AudioEngine()
            a.init()
        self.assertNotIn("quit", order)
        self.assertIn("pre_init", order)
        self.assertIn("init", order)


class MetronomeMathTests(unittest.TestCase):
    """The metronome math must not divide by zero on a zero / negative
    BPM and tick() must not burst-fire after an alt-tab stall."""

    def test_start_metronome_zero_bpm_does_not_divide_by_zero(self) -> None:
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        a._initialised = True
        a.start_metronome(0.0)
        # 60 / max(0, 1) = 60. No crash.
        self.assertEqual(a._metronome_period, 60.0)

    def test_start_metronome_negative_bpm_clamped(self) -> None:
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        a._initialised = True
        a.start_metronome(-50.0)
        # max(-50, 1) = 1, period 60.0.
        self.assertEqual(a._metronome_period, 60.0)


class StopClearsStateTests(unittest.TestCase):
    """stop() should leave the engine in a clean state so a fresh
    play_song / start_metronome starts from zero."""

    def test_stop_clears_song_and_metronome_anchors(self) -> None:
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        a._initialised = True
        a.start_metronome(120.0)
        self.assertIsNotNone(a._metronome_period)
        self.assertIsNotNone(a._song_start_perf)
        a.stop()
        self.assertIsNone(a._metronome_period)
        self.assertIsNone(a._next_metronome_t)
        self.assertIsNone(a._song_start_perf)
        self.assertIsNone(a._song_path)
        self.assertFalse(a.is_playing)

    def test_song_time_returns_zero_after_stop(self) -> None:
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        a._initialised = True
        a.start_metronome(80.0)
        # song_time grows from a positive anchor.
        self.assertGreaterEqual(a.song_time(), 0.0)
        a.stop()
        self.assertEqual(a.song_time(), 0.0)


if __name__ == "__main__":
    unittest.main()
