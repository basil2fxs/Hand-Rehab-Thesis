"""Tests for RAS music mode pieces (Thread 2)."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class BeatmapTests(unittest.TestCase):
    def test_procedural_beatmap_is_sorted(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        bm = procedural_beatmap(bpm=120, beats=16, difficulty="hard")
        times = [n.t for n in bm.notes]
        self.assertEqual(times, sorted(times))
        self.assertGreater(len(bm.notes), 0)

    def test_difficulty_stride_reduces_note_count(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        hard = procedural_beatmap(bpm=120, beats=16, difficulty="hard")
        med = procedural_beatmap(bpm=120, beats=16, difficulty="medium")
        easy = procedural_beatmap(bpm=120, beats=16, difficulty="easy")
        self.assertGreaterEqual(len(hard.notes), len(med.notes))
        self.assertGreaterEqual(len(med.notes), len(easy.notes))

    def test_rejects_zero_bpm(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        with self.assertRaises(ValueError):
            procedural_beatmap(bpm=0, beats=16)


class SchedulerTests(unittest.TestCase):
    def test_notes_due_yields_each_note_once(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        from rehab.audio.scheduler import BeatScheduler
        bm = procedural_beatmap(bpm=120, beats=8, difficulty="hard")
        sched = BeatScheduler(bm)
        # Walk time forward in big jumps. Each note should fire exactly once.
        fired: list = []
        for t in [0.6, 1.2, 1.8, 2.4, 3.0, 3.6, 4.2, 4.8]:
            for n in sched.notes_due(t):
                fired.append(n.index)
        self.assertEqual(sorted(set(fired)), sorted(fired))
        self.assertEqual(len(fired), len(bm.notes))


class LibrosaIntegrationTests(unittest.TestCase):
    def test_extract_beatmap_falls_back_when_audio_missing(self) -> None:
        from rehab.audio.beatmap import extract_beatmap
        # Point at a nonexistent file. The extractor should fall back to
        # a procedural map rather than crash.
        bm = extract_beatmap("/nonexistent/song.mp3", difficulty="medium")
        self.assertGreater(len(bm.notes), 0)

    def test_extract_beatmap_recovers_tempo_from_click_track(self) -> None:
        # Generate a deterministic 120-BPM click track, then verify that
        # extract_beatmap returns a Beatmap whose tempo is in the ballpark.
        if (importlib.util.find_spec("librosa") is None
                or importlib.util.find_spec("soundfile") is None):
            self.skipTest("librosa / soundfile not installed")
        import tempfile
        import numpy as np
        import soundfile as sf
        from rehab.audio.beatmap import extract_beatmap
        sr = 22050
        duration_s = 6.0
        period = 60.0 / 120.0       # 120 BPM = 0.5s between clicks
        y = np.zeros(int(sr * duration_s), dtype=np.float32)
        click_n = int(0.02 * sr)
        click = 0.8 * np.sin(2 * np.pi * 2000 * np.arange(click_n) / sr)
        for i in range(int(duration_s / period)):
            start = int(i * period * sr)
            y[start:start + click_n] = click.astype(np.float32)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            wav_path = f.name
        try:
            sf.write(wav_path, y, sr)
            bm = extract_beatmap(wav_path, difficulty="hard")
            # librosa might detect 60 (half-time) or 120 BPM. Either is fine,
            # just verify we got a sane tempo and some notes.
            self.assertGreater(bm.bpm, 50.0)
            self.assertLess(bm.bpm, 250.0)
            self.assertGreater(len(bm.notes), 4)
            # Notes must be sorted in time.
            ts = [n.t for n in bm.notes]
            self.assertEqual(ts, sorted(ts))
        finally:
            Path(wav_path).unlink(missing_ok=True)

    def test_coerce_scalar_handles_numpy_arrays(self) -> None:
        from rehab.audio.beatmap import _coerce_scalar
        try:
            import numpy as np
        except ImportError:
            self.skipTest("numpy not installed")
        self.assertAlmostEqual(_coerce_scalar(120.0), 120.0)
        self.assertAlmostEqual(_coerce_scalar(np.float64(120.0)), 120.0)
        self.assertAlmostEqual(_coerce_scalar(np.array([117.5])), 117.5)
        self.assertAlmostEqual(_coerce_scalar(np.array(99.0)), 99.0)


class ClassifyOffsetBoundaryTests(unittest.TestCase):
    """classify_offset boundaries decide Perfect / Great / Good / Late /
    Early / Miss. Off-by-one at any boundary would shift every patient's
    score so the windows need exact-equality tests."""

    def test_at_perfect_boundary_returns_perfect(self) -> None:
        from rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()       # perfect_ms=50
        self.assertEqual(classify_offset(50.0, w)[0], "Perfect")
        self.assertEqual(classify_offset(-50.0, w)[0], "Perfect")

    def test_just_past_perfect_returns_great(self) -> None:
        from rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()
        self.assertEqual(classify_offset(50.01, w)[0], "Great")

    def test_at_great_boundary_returns_great(self) -> None:
        from rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()       # great_ms=100
        self.assertEqual(classify_offset(100.0, w)[0], "Great")
        self.assertEqual(classify_offset(-100.0, w)[0], "Great")

    def test_at_good_boundary_returns_good(self) -> None:
        from rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()       # good_ms=175
        self.assertEqual(classify_offset(175.0, w)[0], "Good")
        self.assertEqual(classify_offset(-175.0, w)[0], "Good")

    def test_positive_offset_past_good_is_late(self) -> None:
        from rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()
        self.assertEqual(classify_offset(200.0, w)[0], "Late")

    def test_negative_offset_past_good_is_early(self) -> None:
        from rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()
        self.assertEqual(classify_offset(-200.0, w)[0], "Early")

    def test_at_miss_boundary_still_late_or_early(self) -> None:
        from rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()       # miss_ms=300
        self.assertEqual(classify_offset(300.0, w)[0], "Late")
        self.assertEqual(classify_offset(-300.0, w)[0], "Early")

    def test_past_miss_window_is_miss(self) -> None:
        from rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()
        self.assertEqual(classify_offset(300.01, w)[0], "Miss")
        self.assertEqual(classify_offset(-301.0, w)[0], "Miss")

    def test_perfect_points_are_one_above_great(self) -> None:
        # The incentive ordering "Perfect > Great > Good > Late" must
        # survive a custom ScoreConfig that bumps great_points up.
        from rehab.game.scoring import RhythmWindows, ScoreConfig, classify_offset
        w = RhythmWindows()
        cfg = ScoreConfig(great_points=10, good_points=5, late_points=2)
        _, perfect_pts = classify_offset(10.0, w, cfg)
        _, great_pts = classify_offset(80.0, w, cfg)
        self.assertEqual(perfect_pts, great_pts + 1)


class RhythmModePressMatchingTests(unittest.TestCase):
    """RhythmMode._score_press picks the nearest unmatched note in the
    same lane. Tests that a press in the wrong lane is logged as
    unmatched, and two close-together notes in the same lane each get
    their own press."""

    def _make_mode(self):
        from unittest.mock import MagicMock
        from rehab.audio.beatmap import Beatmap, Note
        from rehab.game.modes.rhythm import RhythmMode
        from rehab.game.scoring import RhythmWindows, ScoreConfig
        bm = Beatmap(notes=[
            Note(t=1.0, lane=0),
            Note(t=2.0, lane=0),
            Note(t=3.0, lane=1),
        ])
        engine = MagicMock()
        engine.audio = None
        # Need a side_effect rather than a fixed return_value so the
        # pre_song_lead lookup returns a numeric 0 (disabling the
        # note-time shift) while other lookups return the dict the test
        # already relied on.
        def _cfg_get(key, default=None):
            if key == "rhythm.pre_song_lead_s":
                return 0
            return {"q": 0}
        engine.cfg.get = MagicMock(side_effect=_cfg_get)
        mode = RhythmMode(engine, bm, RhythmWindows(), ScoreConfig())
        mode._countdown_done = True     # skip countdown logic
        mode._countdown_s = 0.0         # so song_time = perf_counter - t_start
        return mode, engine

    def test_press_in_wrong_lane_logged_as_unmatched(self) -> None:
        from rehab.hardware.fsr_detector import PressEvent
        mode, engine = self._make_mode()
        # Press in lane 2 at t=1.0; no note in lane 2.
        mode._t_start = (__import__("time").perf_counter() - 1.0)
        mode._score_press(PressEvent(lane=2, t_perf=0.0,
                                       value=0, baseline=0.0))
        engine.log_rhythm_unmatched.assert_called_once()
        engine.log_rhythm_hit.assert_not_called()

    def test_two_presses_same_lane_match_different_notes(self) -> None:
        # When two notes on the same lane are close together, the first
        # press should hit the nearer note and the second press should
        # match the OTHER one (not double-fire on the first).
        from rehab.hardware.fsr_detector import PressEvent
        import time as _t
        mode, engine = self._make_mode()
        # Press 1 near note at t=1.0
        mode._t_start = _t.perf_counter() - 1.0
        mode._score_press(PressEvent(lane=0, t_perf=0.0, value=0,
                                       baseline=0.0))
        # Press 2 a beat later, near note at t=2.0
        mode._t_start = _t.perf_counter() - 2.0
        mode._score_press(PressEvent(lane=0, t_perf=0.0, value=0,
                                       baseline=0.0))
        # Two hits logged, no unmatched.
        self.assertEqual(engine.log_rhythm_hit.call_count, 2)
        engine.log_rhythm_unmatched.assert_not_called()
        # The first note (t=1.0) and second note (t=2.0) both got
        # marked with hit_at.
        hits = [s for s in mode.scheduler.scheduled if s.hit_at is not None]
        self.assertEqual(len(hits), 2)


class RhythmPreSongLeadTests(unittest.TestCase):
    """The pre-song lead shifts every beat forward by N seconds so
    notes have time to slide down before the first press is due. Audio
    start is delayed by the same N so the music stays beat-synced."""

    def _build(self, lead_s: float):
        from unittest.mock import MagicMock
        from rehab.audio.beatmap import Beatmap, Note
        from rehab.game.modes.rhythm import RhythmMode
        from rehab.game.scoring import RhythmWindows, ScoreConfig
        bm = Beatmap(notes=[
            Note(t=0.5, lane=0),
            Note(t=1.0, lane=1),
            Note(t=2.0, lane=2),
        ])
        engine = MagicMock()
        engine.audio = None
        def _cfg_get(key, default=None):
            if key == "rhythm.pre_song_lead_s":
                return lead_s
            return default
        engine.cfg.get = MagicMock(side_effect=_cfg_get)
        mode = RhythmMode(engine, bm, RhythmWindows(), ScoreConfig())
        return mode, bm

    def test_all_notes_shifted_forward_by_lead(self) -> None:
        mode, bm = self._build(lead_s=2.0)
        # Original times were 0.5, 1.0, 2.0. After shift: 2.5, 3.0, 4.0.
        self.assertEqual(bm.notes[0].t, 2.5)
        self.assertEqual(bm.notes[1].t, 3.0)
        self.assertEqual(bm.notes[2].t, 4.0)

    def test_zero_lead_keeps_original_times(self) -> None:
        mode, bm = self._build(lead_s=0.0)
        self.assertEqual(bm.notes[0].t, 0.5)
        self.assertEqual(bm.notes[1].t, 1.0)
        self.assertEqual(bm.notes[2].t, 2.0)

    def test_audio_started_flag_starts_false(self) -> None:
        # Audio isn't kicked off until song_time crosses pre_song_lead_s.
        # On construction the flag must be False so the rhythm screen
        # can hide the song progress bar during the lead window.
        mode, _ = self._build(lead_s=2.0)
        self.assertFalse(mode._audio_started)


class RhythmMissWindowCloseRegressionTests(unittest.TestCase):
    """Regression: when a note scrolled past its miss window without any
    press, log_rhythm_hit used to be called without was_pressed=False,
    so the trial CSV recorded keys_pressed=<correct lane> AND
    num_presses=0 - misleading both researchers and any downstream
    analysis that filters on keys_pressed."""

    def _build_mode(self):
        from unittest.mock import MagicMock
        from rehab.audio.beatmap import Beatmap, Note
        from rehab.game.modes.rhythm import RhythmMode
        from rehab.game.scoring import RhythmWindows, ScoreConfig
        bm = Beatmap(notes=[Note(t=1.0, lane=2)])
        engine = MagicMock()
        engine.audio = None
        # Disable pre_song_lead in the fixture so note times stay
        # exactly where the test set them up.
        def _cfg_get(key, default=None):
            if key == "rhythm.pre_song_lead_s":
                return 0
            return {"q": 0}
        engine.cfg.get = MagicMock(side_effect=_cfg_get)
        mode = RhythmMode(engine, bm, RhythmWindows(), ScoreConfig())
        mode._countdown_done = True
        mode._countdown_s = 0.0
        return mode, engine

    def test_no_press_miss_passes_was_pressed_false(self) -> None:
        import time as _t
        mode, engine = self._build_mode()
        # Push song_time well past note time + miss window so the
        # update loop triggers the no-press miss log path.
        mode._t_start = _t.perf_counter() - 5.0  # song_time ~= 5s
        mode.update(dt=0.0)
        # The miss-window-close path should fire exactly once.
        engine.log_rhythm_hit.assert_called_once()
        # Examine the call. was_pressed must be False.
        _, kwargs = engine.log_rhythm_hit.call_args
        self.assertEqual(kwargs.get("was_pressed"), False)

    def test_no_press_miss_row_has_empty_keys_pressed(self) -> None:
        # End-to-end: drive log_rhythm_hit on a no-press miss and verify
        # the trial-CSV row gets keys_pressed="" and num_presses=0.
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock
        from rehab.audio.beatmap import Note
        from rehab.audio.scheduler import ScheduledNote
        from rehab.data.logger import TrialLogger
        from rehab.game.scoring import ScoreConfig
        from rehab.game.engine import GameEngine
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trials.csv"
            engine = GameEngine.__new__(GameEngine)
            engine.session = MagicMock()
            engine.session.participant = "tester"
            engine.hand_mode = "right"
            engine.current_block = "B1"
            engine.score = 0
            engine._last_gained = 0
            engine.hits = 0
            engine.misses = 0
            engine.hit_streak = 0
            engine._streak_fired = set()
            engine._block_rhythm_spurious_presses = 0
            engine._screens = {}
            engine.audio = None
            engine.trial_logger = TrialLogger(path)
            engine.mode = None
            engine._maybe_resave_metadata = lambda: None
            engine._trial_context = lambda streak, song_time_s=None: {}
            engine._outcome_colour = lambda label: (0, 0, 0)
            engine._update_streak = lambda hit, screen: None
            engine._score_for = lambda points, label: points

            note = ScheduledNote(index=0, note=Note(t=1.0, lane=2))
            engine.log_rhythm_hit(note, 0.0, "Miss",
                                    ScoreConfig().miss_points, now=5.0,
                                    was_pressed=False)
            engine.trial_logger.close()

            import csv as _csv
            with path.open() as f:
                rows = list(_csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["keys_pressed"], "")
            self.assertEqual(rows[0]["num_presses"], "0")
            self.assertEqual(rows[0]["feedback"], "Miss")
            # The correct lane is still recorded so the analyst knows
            # which note was missed.
            self.assertEqual(rows[0]["correct_keys"], "3")

    def test_pressed_miss_still_logs_keys_pressed(self) -> None:
        # A press that lands too far from a note (within miss window
        # logic but past miss_ms) still classifies as "Miss". was_pressed
        # defaults to True so keys_pressed reflects the actual press.
        import tempfile
        from pathlib import Path
        from unittest.mock import MagicMock
        from rehab.audio.beatmap import Note
        from rehab.audio.scheduler import ScheduledNote
        from rehab.data.logger import TrialLogger
        from rehab.game.scoring import ScoreConfig
        from rehab.game.engine import GameEngine
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "trials.csv"
            engine = GameEngine.__new__(GameEngine)
            engine.session = MagicMock()
            engine.session.participant = "tester"
            engine.hand_mode = "right"
            engine.current_block = "B1"
            engine.score = 0
            engine._last_gained = 0
            engine.hits = 0
            engine.misses = 0
            engine.hit_streak = 0
            engine._streak_fired = set()
            engine._block_rhythm_spurious_presses = 0
            engine._screens = {}
            engine.audio = None
            engine.trial_logger = TrialLogger(path)
            engine.mode = None
            engine._maybe_resave_metadata = lambda: None
            engine._trial_context = lambda streak, song_time_s=None: {}
            engine._outcome_colour = lambda label: (0, 0, 0)
            engine._update_streak = lambda hit, screen: None
            engine._score_for = lambda points, label: points

            note = ScheduledNote(index=4, note=Note(t=2.0, lane=1))
            # Default was_pressed=True - patient did press, just far off.
            engine.log_rhythm_hit(note, 400.0, "Miss",
                                    ScoreConfig().miss_points, now=2.5)
            engine.trial_logger.close()

            import csv as _csv
            with path.open() as f:
                rows = list(_csv.DictReader(f))
            self.assertEqual(rows[0]["keys_pressed"], "2")
            self.assertEqual(rows[0]["num_presses"], "1")
            self.assertEqual(rows[0]["feedback"], "Miss")


class BeatmapEdgeCaseTests(unittest.TestCase):
    """Defensive coverage on degenerate inputs to extract_beatmap +
    procedural_beatmap + Beatmap so a quietly broken input doesn't
    crash the rhythm mode."""

    def test_empty_beatmap_has_zero_duration(self) -> None:
        from rehab.audio.beatmap import Beatmap
        bm = Beatmap(title="empty")
        self.assertEqual(bm.duration_s, 0.0)
        self.assertEqual(bm.notes, [])

    def test_custom_lane_pattern_out_of_range_filtered(self) -> None:
        # If a caller passes a pattern that addresses lanes >= num_lanes,
        # those beats get dropped silently. Documents that quirk so a
        # future change doesn't accidentally accept lane 99.
        from rehab.audio.beatmap import procedural_beatmap
        bm = procedural_beatmap(
            bpm=120, beats=16, difficulty="hard",
            lane_pattern=[0, 1, 99],
            num_lanes=4,
        )
        for n in bm.notes:
            self.assertLess(n.lane, 4)

    def test_procedural_beatmap_minimum_one_beat(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        bm = procedural_beatmap(bpm=120, beats=1, difficulty="hard")
        self.assertEqual(len(bm.notes), 1)

    def test_unknown_difficulty_defaults_to_medium_stride(self) -> None:
        from rehab.audio.beatmap import procedural_beatmap
        # "ultra-hard" isn't a known difficulty; should fall through to
        # the default stride (medium = every 2nd beat) without crashing.
        bm = procedural_beatmap(bpm=120, beats=16, difficulty="ultra-hard")
        # 16 beats / stride 2 = 8 notes.
        self.assertEqual(len(bm.notes), 8)


class SchedulerEdgeCaseTests(unittest.TestCase):
    """Scheduler must handle an empty beatmap (zero notes) and a single-
    note beatmap correctly. all_done must terminate the rhythm block
    even when nothing was generated."""

    def test_all_done_on_empty_beatmap_after_song_time_zero(self) -> None:
        from rehab.audio.beatmap import Beatmap
        from rehab.audio.scheduler import BeatScheduler
        sched = BeatScheduler(Beatmap(title="empty"))
        # duration_s = 0, no notes. all_done returns True for any
        # positive song time.
        self.assertTrue(sched.all_done(0.001))
        self.assertEqual(list(sched.notes_due(10.0)), [])
        self.assertEqual(sched.upcoming(0.0), [])

    def test_single_note_scheduler_yields_once_then_done(self) -> None:
        from rehab.audio.beatmap import Beatmap, Note
        from rehab.audio.scheduler import BeatScheduler
        bm = Beatmap(notes=[Note(t=0.5, lane=0)])
        sched = BeatScheduler(bm)
        # Before t=0.5: nothing due, not all_done.
        self.assertEqual(list(sched.notes_due(0.4)), [])
        self.assertFalse(sched.all_done(0.4))
        # At t=0.5: due, fired flag set, no longer yielded.
        due = list(sched.notes_due(0.6))
        self.assertEqual(len(due), 1)
        self.assertEqual(list(sched.notes_due(0.7)), [])
        # After duration (0.5 + 1.0 = 1.5): all_done.
        self.assertTrue(sched.all_done(1.6))

    def test_reset_clears_fired_flags(self) -> None:
        from rehab.audio.beatmap import Beatmap, Note
        from rehab.audio.scheduler import BeatScheduler
        bm = Beatmap(notes=[Note(t=0.1, lane=0)])
        sched = BeatScheduler(bm)
        list(sched.notes_due(1.0))      # fire it
        self.assertTrue(sched._sched[0].fired)
        sched.reset()
        self.assertFalse(sched._sched[0].fired)
        # After reset, notes_due yields it again.
        self.assertEqual(len(list(sched.notes_due(1.0))), 1)


if __name__ == "__main__":
    unittest.main()
