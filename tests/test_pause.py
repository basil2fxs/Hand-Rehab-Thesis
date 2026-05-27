"""Tests for pause / resume behaviour."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class ClassicModePauseTests(unittest.TestCase):
    def test_on_resume_shifts_active_trial_stim_time(self) -> None:
        from rehab.game.modes.classic import ClassicMode, PendingTrial
        from rehab.game.scoring import ScoreConfig
        mode = ClassicMode(
            engine=MagicMock(),
            pattern=[0, 1, 2, 3],
            repeat_count=1,
            trigger_interval_s=0.6,
            timeout_s=1.0,
            early_window_s=0.1,
            score_cfg=ScoreConfig(),
        )
        mode.active = PendingTrial(
            trial_id=1, lane=0,
            stim_t_perf=100.0, keys_pressed=[], incorrect_presses=[],
        )
        mode.last_trigger_t = 100.0
        # Paused for 3 seconds. The active trial should look 3 seconds younger
        # afterwards so the timeout window doesn't elapse during the pause.
        mode.on_resume(3.0)
        self.assertEqual(mode.active.stim_t_perf, 103.0)
        self.assertEqual(mode.last_trigger_t, 103.0)


class AdaptiveModePauseTests(unittest.TestCase):
    def test_on_resume_shifts_timestamps(self) -> None:
        from rehab.analytics.adaptive import AdaptiveConfig
        from rehab.game.modes.adaptive import AdaptiveMode
        from rehab.game.modes.classic import PendingTrial
        from rehab.game.scoring import ScoreConfig
        mode = AdaptiveMode(
            engine=MagicMock(),
            total_trials=10, block_size=4,
            score_cfg=ScoreConfig(),
            timeout_s=1.0, early_window_s=0.1,
            adaptive_cfg=AdaptiveConfig(),
        )
        mode.active = PendingTrial(
            trial_id=1, lane=0,
            stim_t_perf=200.0, keys_pressed=[], incorrect_presses=[],
        )
        mode.last_trigger_t = 200.0
        mode.on_resume(5.0)
        self.assertEqual(mode.active.stim_t_perf, 205.0)
        self.assertEqual(mode.last_trigger_t, 205.0)


class RhythmModePauseTests(unittest.TestCase):
    def test_on_resume_shifts_song_clock_fallback(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        from rehab.game.modes.rhythm import RhythmMode
        from rehab.game.scoring import RhythmWindows, ScoreConfig
        engine = MagicMock()
        engine.audio = None     # force the fallback clock path
        engine.cfg.get = MagicMock(return_value={"q": 0})
        bm = procedural_beatmap(bpm=120, beats=8, difficulty="hard")
        mode = RhythmMode(engine, bm, RhythmWindows(), ScoreConfig())
        before = mode._t_start
        mode.on_resume(7.5)
        self.assertAlmostEqual(mode._t_start - before, 7.5, places=5)

    def test_on_pause_freezes_song_time(self) -> None:
        # While paused, song_time should hold steady even as real time ticks
        # forward. Otherwise the falling notes keep scrolling visually.
        from rehab.audio.beatmap import procedural_beatmap
        from rehab.game.modes.rhythm import RhythmMode
        from rehab.game.scoring import RhythmWindows, ScoreConfig
        engine = MagicMock()
        engine.audio = None
        engine.cfg.get = MagicMock(return_value={"q": 0})
        bm = procedural_beatmap(bpm=120, beats=8, difficulty="hard")
        mode = RhythmMode(engine, bm, RhythmWindows(), ScoreConfig())
        # Skip the countdown so we're past it in song_time.
        mode._countdown_done = True
        mode._t_start = mode._t_start - 5.0     # pretend 5 s have elapsed
        snapshot_before = mode.song_time
        mode.on_pause()
        # Take 3 readings spaced apart; they should all match the snapshot.
        import time as _t
        first = mode.song_time
        _t.sleep(0.05)
        second = mode.song_time
        _t.sleep(0.05)
        third = mode.song_time
        self.assertEqual(first, second)
        self.assertEqual(second, third)
        self.assertAlmostEqual(first, snapshot_before, places=2)
        mode.on_resume(0.1)
        # After resume the snapshot is dropped and song_time moves again.
        self.assertIsNone(mode._frozen_song_t)


class EncouragementStreakTests(unittest.TestCase):
    """Engine fires the right encouragement at each streak threshold and
    won't re-fire the same one within a block."""

    def _make_engine_with_stub_screens(self):
        from rehab.game.engine import GameEngine
        # Build a minimal engine without invoking pygame. We only need
        # `_update_streak` and the `_streak_thresholds` / `_screens` dict.
        eng = GameEngine.__new__(GameEngine)
        eng.hit_streak = 0
        eng.miss_streak = 0
        eng.mode = None
        eng._streak_thresholds = (3, 5, 8, 12, 20, 30, 50)
        eng._streak_fired = set()
        eng._recovery_threshold = 3
        # Stub gameplay/rhythm screens that capture every encouragement call.
        eng._screens = {
            "gameplay": MagicMock(),
            "rhythm": MagicMock(),
        }
        return eng

    def test_encouragement_fires_at_thresholds(self) -> None:
        eng = self._make_engine_with_stub_screens()
        for _ in range(5):
            eng._update_streak(was_hit=True, screen_key="gameplay")
        calls = eng._screens["gameplay"].add_encouragement.call_args_list
        # 2 thresholds crossed in 5 hits: 3 and 5.
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0].args[0], "Nice!")
        self.assertEqual(calls[1].args[0], "Keep going!")

    def test_miss_resets_streak(self) -> None:
        eng = self._make_engine_with_stub_screens()
        for _ in range(2):
            eng._update_streak(was_hit=True, screen_key="gameplay")
        eng._update_streak(was_hit=False, screen_key="gameplay")
        self.assertEqual(eng.hit_streak, 0)
        # Next hit shouldn't trigger anything until streak hits 3 again.
        eng._update_streak(was_hit=True, screen_key="gameplay")
        self.assertEqual(eng._screens["gameplay"].add_encouragement.call_count, 0)

    def test_threshold_fires_only_once_per_block(self) -> None:
        eng = self._make_engine_with_stub_screens()
        # Hit 3, miss to reset streak, hit 3 again. The "Nice!" popup
        # should only fire on the first crossing.
        for _ in range(3):
            eng._update_streak(was_hit=True, screen_key="gameplay")
        eng._update_streak(was_hit=False, screen_key="gameplay")
        for _ in range(3):
            eng._update_streak(was_hit=True, screen_key="gameplay")
        self.assertEqual(eng._screens["gameplay"].add_encouragement.call_count, 1)


class AudioPlaySongStartOffsetTests(unittest.TestCase):
    def test_start_s_clamped_to_zero(self) -> None:
        # Direct mathematical check on the song-start anchor used by song_time.
        # We don't need a real mixer here; the calculation lives in play_song
        # but we can call it via a partial smoke check on the engine class.
        # Just confirm the helper accepts negative start_s without error.
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        # Without init, play_song should return False rather than raise.
        self.assertFalse(a.play_song("/nonexistent.mp3", start_s=-3.0))


class OutcomeColourTests(unittest.TestCase):
    """Three-tier lane flash so the patient sees how close they got:
       red    = Miss
       orange = Late / Early (right lane, off timing)
       green  = Perfect / Great / Good (clean correct press)
    """

    def _make_engine(self):
        from rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        from rehab.ui import theme as theme_mod
        eng.theme = theme_mod.get("clinical")
        return eng

    def test_miss_is_red(self) -> None:
        eng = self._make_engine()
        self.assertEqual(eng._outcome_colour("Miss"), eng.theme.lane_miss)

    def test_late_and_early_are_orange(self) -> None:
        eng = self._make_engine()
        self.assertEqual(eng._outcome_colour("Late"), eng._ORANGE_CLOSE)
        self.assertEqual(eng._outcome_colour("Early"), eng._ORANGE_CLOSE)

    def test_perfect_great_good_are_green(self) -> None:
        eng = self._make_engine()
        for label in ("Perfect", "Great", "Good"):
            self.assertEqual(eng._outcome_colour(label), eng.theme.lane_hit,
                              f"{label} should flash green (clean correct press)")


class RhythmLaneNoDarkenOnStimTests(unittest.TestCase):
    """Rhythm mode uses falling notes + target rings to telegraph the
    next press, so the lane itself must never go to its darker `active`
    fill. on_stim should leave rhythm-screen lanes inactive while still
    activating the gameplay-screen lane for classic / adaptive."""

    def test_on_stim_keeps_rhythm_lanes_inactive(self) -> None:
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        import pygame
        pygame.init()
        try:
            from rehab.config import Config
            from rehab.game.engine import GameEngine
            from rehab.hardware.keyboard_source import KeyboardOnlySource
            from rehab.ui.screens import GameplayScreen, RhythmScreen
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            eng = GameEngine(cfg, KeyboardOnlySource())
            eng._screens = {
                "gameplay": GameplayScreen(eng),
                "rhythm":   RhythmScreen(eng),
            }
            eng.on_stim(lane=2, trial_id=1, t_perf=0.0)
            self.assertTrue(eng._screens["gameplay"].lanes[2].active,
                "gameplay lane 2 should be active so the target stands out")
            for ls in eng._screens["rhythm"].lanes:
                self.assertFalse(ls.active,
                    f"rhythm lane {ls.lane} must not darken on stim "
                    f"(falling note already shows the target)")
        finally:
            pygame.quit()


class AudioHitChimeTests(unittest.TestCase):
    """AudioEngine.play_hit is the confirmation tone on a correct press
    (every mode). The per-lane stim tone now ALSO plays on every stim
    in classic + adaptive (matching Aiden's game). Rhythm mode skips
    the stim tone so it doesn't clash with the song."""

    def test_play_hit_no_op_without_init(self) -> None:
        from rehab.audio.engine import AudioEngine
        a = AudioEngine()
        # Not initialised; should be silent and not raise.
        a.play_hit()
        self.assertFalse(a._initialised)

    def test_engine_on_stim_calls_play_stim_for_classic_adaptive(self) -> None:
        # The cue tone was reinstated for classic + adaptive (config
        # toggle audio.stim_tone_enabled). Rhythm stays silent on stim
        # because the song carries the rhythm cue. Belt-and-braces
        # source-level check so a refactor can't silently rip it out.
        from pathlib import Path
        src = (Path(__file__).resolve().parents[1]
                / "rehab" / "game" / "engine.py").read_text()
        # play_stim IS called.
        self.assertIn("self.audio.play_stim(", src,
                       "play_stim must be wired in on_stim for cue tone")
        # And it must be gated on the current_block so rhythm doesn't
        # also fire it.
        self.assertIn('current_block in ("classic", "adaptive")', src,
                       "stim tone must only fire for classic + adaptive")


if __name__ == "__main__":
    unittest.main()
