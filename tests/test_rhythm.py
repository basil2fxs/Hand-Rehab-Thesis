"""Tests for RAS music mode pieces (Thread 2)."""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class BeatmapTests(unittest.TestCase):
    def test_procedural_beatmap_is_sorted(self) -> None:
        from finger_rehab.audio.beatmap import procedural_beatmap
        bm = procedural_beatmap(bpm=120, beats=16, difficulty="hard")
        times = [n.t for n in bm.notes]
        self.assertEqual(times, sorted(times))
        self.assertGreater(len(bm.notes), 0)

    def test_difficulty_stride_reduces_note_count(self) -> None:
        from finger_rehab.audio.beatmap import procedural_beatmap
        hard = procedural_beatmap(bpm=120, beats=16, difficulty="hard")
        med = procedural_beatmap(bpm=120, beats=16, difficulty="medium")
        easy = procedural_beatmap(bpm=120, beats=16, difficulty="easy")
        self.assertGreaterEqual(len(hard.notes), len(med.notes))
        self.assertGreaterEqual(len(med.notes), len(easy.notes))

    def test_rejects_zero_bpm(self) -> None:
        from finger_rehab.audio.beatmap import procedural_beatmap
        with self.assertRaises(ValueError):
            procedural_beatmap(bpm=0, beats=16)


class SchedulerTests(unittest.TestCase):
    def test_notes_due_yields_each_note_once(self) -> None:
        from finger_rehab.audio.beatmap import procedural_beatmap
        from finger_rehab.audio.scheduler import BeatScheduler
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
        from finger_rehab.audio.beatmap import extract_beatmap
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
        from finger_rehab.audio.beatmap import extract_beatmap
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
        from finger_rehab.audio.beatmap import _coerce_scalar
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
        from finger_rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()       # perfect_ms=50
        self.assertEqual(classify_offset(50.0, w)[0], "Perfect")
        self.assertEqual(classify_offset(-50.0, w)[0], "Perfect")

    def test_just_past_perfect_returns_great(self) -> None:
        from finger_rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()
        self.assertEqual(classify_offset(50.01, w)[0], "Great")

    def test_at_great_boundary_returns_great(self) -> None:
        from finger_rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()       # great_ms=100
        self.assertEqual(classify_offset(100.0, w)[0], "Great")
        self.assertEqual(classify_offset(-100.0, w)[0], "Great")

    def test_at_good_boundary_returns_good(self) -> None:
        from finger_rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()       # good_ms=175
        self.assertEqual(classify_offset(175.0, w)[0], "Good")
        self.assertEqual(classify_offset(-175.0, w)[0], "Good")

    def test_positive_offset_past_good_is_late(self) -> None:
        from finger_rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()
        self.assertEqual(classify_offset(200.0, w)[0], "Late")

    def test_negative_offset_past_good_is_early(self) -> None:
        from finger_rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()
        self.assertEqual(classify_offset(-200.0, w)[0], "Early")

    def test_at_miss_boundary_still_late_or_early(self) -> None:
        from finger_rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()       # miss_ms=300
        self.assertEqual(classify_offset(300.0, w)[0], "Late")
        self.assertEqual(classify_offset(-300.0, w)[0], "Early")

    def test_past_miss_window_is_miss(self) -> None:
        from finger_rehab.game.scoring import RhythmWindows, classify_offset
        w = RhythmWindows()
        self.assertEqual(classify_offset(300.01, w)[0], "Miss")
        self.assertEqual(classify_offset(-301.0, w)[0], "Miss")

    def test_perfect_outscores_great(self) -> None:
        # The incentive ordering "Perfect > Great > Good > Late" must
        # survive a custom ScoreConfig. Perfect now has its own
        # configurable point value rather than being implicitly
        # great_points + 1, so the custom cfg overrides both
        # independently.
        from finger_rehab.game.scoring import RhythmWindows, ScoreConfig, classify_offset
        w = RhythmWindows()
        cfg = ScoreConfig(perfect_points=15, great_points=10,
                           good_points=5, late_points=2)
        _, perfect_pts = classify_offset(10.0, w, cfg)
        _, great_pts = classify_offset(80.0, w, cfg)
        _, good_pts = classify_offset(150.0, w, cfg)
        _, late_pts = classify_offset(250.0, w, cfg)
        self.assertEqual(perfect_pts, 15)
        self.assertEqual(great_pts, 10)
        self.assertEqual(good_pts, 5)
        self.assertEqual(late_pts, 2)
        # Strict descending order regardless of the chosen values.
        self.assertGreater(perfect_pts, great_pts)
        self.assertGreater(great_pts, good_pts)
        self.assertGreater(good_pts, late_pts)


class RhythmModePressMatchingTests(unittest.TestCase):
    """RhythmMode._score_press picks the nearest unmatched note in the
    same lane. Tests that a press in the wrong lane is logged as
    unmatched, and two close-together notes in the same lane each get
    their own press."""

    def _make_mode(self):
        from unittest.mock import MagicMock
        from finger_rehab.audio.beatmap import Beatmap, Note
        from finger_rehab.game.modes.rhythm import RhythmMode
        from finger_rehab.game.scoring import RhythmWindows, ScoreConfig
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
        from finger_rehab.hardware.fsr_detector import PressEvent
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
        from finger_rehab.hardware.fsr_detector import PressEvent
        import time as _t
        mode, engine = self._make_mode()
        # A press can only match a note the patient has already been
        # cued for (fired), so mark both same-lane notes fired up
        # front, as update()'s notes_due() would have by these times.
        for s in mode.scheduler.scheduled:
            if s.note.lane == 0:
                s.fired = True
        # Press 1 near note at t=1.0
        mode._t_start = _t.perf_counter() - 1.0
        mode._score_press(PressEvent(lane=0, t_perf=_t.perf_counter(),
                                       value=0, baseline=0.0))
        # Press 2 a beat later, near note at t=2.0
        mode._t_start = _t.perf_counter() - 2.0
        mode._score_press(PressEvent(lane=0, t_perf=_t.perf_counter(),
                                       value=0, baseline=0.0))
        # Two hits logged, no unmatched.
        self.assertEqual(engine.log_rhythm_hit.call_count, 2)
        engine.log_rhythm_unmatched.assert_not_called()
        # The first note (t=1.0) and second note (t=2.0) both got
        # marked with hit_at.
        hits = [s for s in mode.scheduler.scheduled if s.hit_at is not None]
        self.assertEqual(len(hits), 2)

    def test_press_is_scored_against_its_own_timestamp_not_drain_time(self) -> None:
        """A press queued at the true beat (song_time=1.0) but not
        drained by _score_press until later must still score as 0ms
        offset -- the delay between queueing and draining is processing
        lag, not the patient being late. Uses a fake clock (the chords-
        mode pattern) to advance wall time between the press's own
        timestamp and the _score_press call without a real sleep."""
        import finger_rehab.game.modes.rhythm as rhythm_mod
        from finger_rehab.hardware.fsr_detector import PressEvent

        class _Clock:
            def __init__(self, t0: float) -> None:
                self.t = t0

            def perf_counter(self) -> float:
                return self.t

        real_time = rhythm_mod.time
        clock = _Clock(1000.0)
        rhythm_mod.time = clock
        try:
            mode, engine = self._make_mode()
            for s in mode.scheduler.scheduled:
                if s.note.lane == 0:
                    s.fired = True
            mode._t_start = clock.t - 1.0   # song_time reads ~1.0 now
            press_t_perf = clock.t          # captured at the true beat
            # Wall time (and hence self.song_time) moves on 150ms before
            # _score_press actually drains the queued press.
            clock.t += 0.150
            mode._score_press(PressEvent(lane=0, t_perf=press_t_perf,
                                           value=0, baseline=0.0))
        finally:
            rhythm_mod.time = real_time
        engine.log_rhythm_hit.assert_called_once()
        offset_ms = engine.log_rhythm_hit.call_args[0][1]
        self.assertLess(abs(offset_ms), 50.0,
                         f"drain-time lag leaked into offset_ms: {offset_ms}")

    def test_press_before_a_note_has_fired_does_not_consume_it(self) -> None:
        """A false-start or wrong-finger press made WELL before a lane's
        note (outside the good window) must not silently consume that
        future note -- the patient's later, genuinely on-time press
        needs something to match."""
        import time as _t
        from finger_rehab.hardware.fsr_detector import PressEvent
        mode, engine = self._make_mode()
        # Note at t=2.0 on lane 0 has NOT fired yet, and 400ms early is
        # outside the 175ms good window, so this must stay unmatched.
        mode._t_start = _t.perf_counter() - 1.6   # song_time ~1.6, 400ms early
        mode._score_press(PressEvent(lane=0, t_perf=_t.perf_counter(),
                                       value=0, baseline=0.0))
        engine.log_rhythm_hit.assert_not_called()
        engine.log_rhythm_unmatched.assert_called_once()
        # The note is still open for the genuine on-time press.
        note_2s = next(s for s in mode.scheduler.scheduled
                       if s.note.t == 2.0)
        self.assertIsNone(note_2s.hit_at)

    def test_anticipation_in_the_early_tier_scores_early(self) -> None:
        """A press 250 ms before its note sits in the documented Early
        tier (-miss_ms..-good_ms, 1 point). With the old -good_ms
        matching floor it was penalised as a spurious press and the
        note then missed, so the Early tier was unreachable in
        gameplay and the logged offset distribution was truncated
        asymmetrically (early cut at -175 ms, late kept to +300 ms),
        biasing the mean asynchrony positive."""
        import time as _t
        from finger_rehab.hardware.fsr_detector import PressEvent
        mode, engine = self._make_mode()
        # song_time ~1.75: 250 ms early of the lane-0 note at t=2.0,
        # and 750 ms past the lane-0 note at t=1.0 (outside its late
        # radius), so the future note is the only candidate.
        mode._t_start = _t.perf_counter() - 1.75
        mode._score_press(PressEvent(lane=0, t_perf=_t.perf_counter(),
                                       value=0, baseline=0.0))
        engine.log_rhythm_unmatched.assert_not_called()
        engine.log_rhythm_hit.assert_called_once()
        args, _ = engine.log_rhythm_hit.call_args
        offset_ms, label = args[1], args[2]
        self.assertEqual(label, "Early")
        self.assertLess(offset_ms, -175.0)
        self.assertGreaterEqual(offset_ms, -300.0)

    def test_early_press_within_good_window_scores_even_before_fired(
            self) -> None:
        """Audit finding #54 (HIGH): a press up to good_ms before an
        UNFIRED note used to be rejected outright (the `fired` gate ran
        before the time-window check), so the entire early half of the
        published Perfect/Great/Good windows was unreachable and a
        press this early was penalised as a spurious wrong-finger press
        instead of scored. Anticipatory (early) pressing is the norm in
        sensorimotor synchronisation, not an error, so it must score."""
        import time as _t
        from finger_rehab.hardware.fsr_detector import PressEvent
        mode, engine = self._make_mode()
        # Note at t=2.0 on lane 0 has NOT fired (scheduler._next is
        # still 0; notes_due() has never run). Press 100ms early, well
        # inside the 175ms good window.
        for s in mode.scheduler.scheduled:
            self.assertFalse(s.fired)
        mode._t_start = _t.perf_counter() - 1.9   # song_time ~1.9, 100ms early
        mode._score_press(PressEvent(lane=0, t_perf=_t.perf_counter(),
                                       value=0, baseline=0.0))
        engine.log_rhythm_unmatched.assert_not_called()
        engine.log_rhythm_hit.assert_called_once()
        args, _ = engine.log_rhythm_hit.call_args
        offset_ms = args[1]
        self.assertLess(offset_ms, 0.0)           # early = negative
        self.assertGreater(offset_ms, -175.0)     # inside the good window
        note_2s = next(s for s in mode.scheduler.scheduled
                       if s.note.t == 2.0)
        self.assertIsNotNone(note_2s.hit_at)

    def test_press_expired_and_miss_logged_does_not_double_count(
            self) -> None:
        """Audit finding #55 (HIGH): a press landing between miss_ms
        (300ms) and the old 2x matching radius (600ms) after a beat
        used to still be matched to a note whose no-press Miss row had
        already been written by the window-expiry path, producing two
        trial rows -- and two misses -- for one note."""
        import time as _t
        from finger_rehab.hardware.fsr_detector import PressEvent
        mode, engine = self._make_mode()
        note = next(s for s in mode.scheduler.scheduled if s.note.t == 1.0)
        note.fired = True          # notes_due() already cued this note
        note._miss_logged = True   # expiry path already wrote the Miss row
        mode._t_start = _t.perf_counter() - 1.4   # song_time ~1.4, 400ms late
        mode._score_press(PressEvent(lane=0, t_perf=_t.perf_counter(),
                                       value=0, baseline=0.0))
        # Must NOT be re-matched to the already-miss-logged note --
        # counts as an unmatched (spurious) press instead of a second
        # hit row for the same note.
        engine.log_rhythm_hit.assert_not_called()
        engine.log_rhythm_unmatched.assert_called_once()
        self.assertIsNone(note.hit_at)


class RhythmPreSongLeadTests(unittest.TestCase):
    """The pre-song lead shifts every beat forward by N seconds so
    notes have time to slide down before the first press is due. Audio
    start is delayed by the same N so the music stays beat-synced."""

    def _build(self, lead_s: float):
        from unittest.mock import MagicMock
        from finger_rehab.audio.beatmap import Beatmap, Note
        from finger_rehab.game.modes.rhythm import RhythmMode
        from finger_rehab.game.scoring import RhythmWindows, ScoreConfig
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


class RhythmAudioOffsetCompensationTests(unittest.TestCase):
    """Audit finding #57 (MEDIUM): rhythm.audio_offset_ms (default
    40ms) used to be subtracted from every press regardless of whether
    any sound was actually playing, so a keyboard-only / audio-disabled
    session (where the patient syncs to the visual strike line, not
    audio) had every logged offset shifted ~40ms early for no reason,
    and the metronome click (a much smaller ~12ms latency) was
    over-compensated by the same song-sized constant."""

    def _make_mode(self, audio):
        from unittest.mock import MagicMock
        from finger_rehab.audio.beatmap import Beatmap, Note
        from finger_rehab.game.modes.rhythm import RhythmMode
        from finger_rehab.game.scoring import RhythmWindows, ScoreConfig
        bm = Beatmap(notes=[Note(t=1.0, lane=0)])
        engine = MagicMock()
        engine.audio = audio

        def _cfg_get(key, default=None):
            if key == "rhythm.pre_song_lead_s":
                return 0
            if key == "rhythm.audio_offset_ms":
                return 40
            if key == "rhythm.metronome_offset_ms":
                return 12
            return default
        engine.cfg.get = MagicMock(side_effect=_cfg_get)
        mode = RhythmMode(engine, bm, RhythmWindows(), ScoreConfig())
        mode._countdown_done = True
        mode._countdown_s = 0.0
        return mode, engine

    def _press_on_the_beat(self, mode):
        import time as _t
        from finger_rehab.hardware.fsr_detector import PressEvent
        mode._t_start = _t.perf_counter() - 1.0   # song_time ~= 1.0
        mode._score_press(PressEvent(lane=0, t_perf=_t.perf_counter(),
                                       value=0, baseline=0.0))

    def test_no_audio_object_applies_zero_compensation(self) -> None:
        # Keyboard-only / audio init failed: engine.audio is None.
        mode, engine = self._make_mode(audio=None)
        self._press_on_the_beat(mode)
        offset_ms = engine.log_rhythm_hit.call_args[0][1]
        self.assertAlmostEqual(offset_ms, 0.0, delta=5.0)

    def test_audio_disabled_no_song_no_metronome_applies_zero(self) -> None:
        # Audio engine exists (audio.enabled: true in config) but
        # nothing is actually playing yet -- neither a song nor the
        # metronome fallback has started.
        from unittest.mock import MagicMock
        audio = MagicMock()
        audio._song_path = None
        audio._metronome_period = None
        mode, engine = self._make_mode(audio=audio)
        self._press_on_the_beat(mode)
        offset_ms = engine.log_rhythm_hit.call_args[0][1]
        self.assertAlmostEqual(offset_ms, 0.0, delta=5.0)

    def test_song_playing_applies_the_song_offset(self) -> None:
        from unittest.mock import MagicMock
        audio = MagicMock()
        audio._song_path = "/tmp/song.mp3"
        audio._metronome_period = None
        mode, engine = self._make_mode(audio=audio)
        self._press_on_the_beat(mode)
        offset_ms = engine.log_rhythm_hit.call_args[0][1]
        # A press exactly on the visible beat should read as ~40ms
        # early once the song's audio-output latency is subtracted.
        self.assertAlmostEqual(offset_ms, -40.0, delta=5.0)

    def test_metronome_running_applies_the_smaller_metronome_offset(
            self) -> None:
        from unittest.mock import MagicMock
        audio = MagicMock()
        audio._song_path = None
        audio._metronome_period = 0.5
        mode, engine = self._make_mode(audio=audio)
        self._press_on_the_beat(mode)
        offset_ms = engine.log_rhythm_hit.call_args[0][1]
        # Metronome latency (~12ms) must not be over-compensated with
        # the much larger song constant (~40ms).
        self.assertAlmostEqual(offset_ms, -12.0, delta=5.0)


class RhythmCountdownPressQueueTests(unittest.TestCase):
    """Audit finding #60 (LOW): a press made during the countdown or
    pre-song lead used to be queued and then drained the moment the
    countdown ended, scored as an unmatched spurious press (wrong-press
    penalty, red flash, miss thunk) even though the screen explicitly
    says not to press yet. The pause path already clears the queue on
    pause; queue_press itself must refuse to queue while the countdown
    is still running."""

    def _make_mode(self):
        from unittest.mock import MagicMock
        from finger_rehab.audio.beatmap import Beatmap, Note
        from finger_rehab.game.modes.rhythm import RhythmMode
        from finger_rehab.game.scoring import RhythmWindows, ScoreConfig
        bm = Beatmap(notes=[Note(t=1.0, lane=0)])
        engine = MagicMock()
        engine.audio = None

        def _cfg_get(key, default=None):
            if key == "rhythm.pre_song_lead_s":
                return 0
            return default
        engine.cfg.get = MagicMock(side_effect=_cfg_get)
        return RhythmMode(engine, bm, RhythmWindows(), ScoreConfig())

    def test_press_during_countdown_is_not_queued(self) -> None:
        from finger_rehab.hardware.fsr_detector import PressEvent
        import time as _t
        mode = self._make_mode()
        self.assertFalse(mode._countdown_done)
        mode.queue_press(PressEvent(lane=0, t_perf=_t.perf_counter(),
                                      value=0, baseline=0.0))
        self.assertEqual(len(mode._presses), 0)

    def test_press_after_countdown_is_queued_normally(self) -> None:
        from finger_rehab.hardware.fsr_detector import PressEvent
        import time as _t
        mode = self._make_mode()
        mode._countdown_done = True
        mode._audio_started = True
        mode.queue_press(PressEvent(lane=0, t_perf=_t.perf_counter(),
                                      value=0, baseline=0.0))
        self.assertEqual(len(mode._presses), 1)

    def test_press_in_the_silent_lead_is_dropped_not_penalised(
            self) -> None:
        # After the countdown card disappears there are still up to
        # 2 s of silent lead before the audio and the first note. A
        # press there used to be penalised as a wrong-finger spurious
        # press (-3, red flash, miss thunk) with nothing on screen
        # saying pressing was premature. It is dropped instead, until
        # the first note's own matching window opens.
        from finger_rehab.hardware.fsr_detector import PressEvent
        import time as _t
        mode = self._make_mode()
        mode._countdown_done = True
        mode._audio_started = False
        # Far from the first note: song_time is negative or near zero
        # in this fixture while the first note sits at t > 0.3.
        mode.queue_press(PressEvent(lane=0, t_perf=_t.perf_counter(),
                                      value=0, baseline=0.0))
        self.assertEqual(len(mode._presses), 0)


class RhythmMissWindowCloseRegressionTests(unittest.TestCase):
    """Regression: when a note scrolled past its miss window without any
    press, log_rhythm_hit used to be called without was_pressed=False,
    so the trial CSV recorded keys_pressed=<correct lane> AND
    num_presses=0 - misleading both researchers and any downstream
    analysis that filters on keys_pressed."""

    def _build_mode(self):
        from unittest.mock import MagicMock
        from finger_rehab.audio.beatmap import Beatmap, Note
        from finger_rehab.game.modes.rhythm import RhythmMode
        from finger_rehab.game.scoring import RhythmWindows, ScoreConfig
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
        from finger_rehab.audio.beatmap import Note
        from finger_rehab.audio.scheduler import ScheduledNote
        from finger_rehab.data.logger import TrialLogger
        from finger_rehab.game.scoring import ScoreConfig
        from finger_rehab.game.engine import GameEngine
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
        from finger_rehab.audio.beatmap import Note
        from finger_rehab.audio.scheduler import ScheduledNote
        from finger_rehab.data.logger import TrialLogger
        from finger_rehab.game.scoring import ScoreConfig
        from finger_rehab.game.engine import GameEngine
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
        from finger_rehab.audio.beatmap import Beatmap
        bm = Beatmap(title="empty")
        self.assertEqual(bm.duration_s, 0.0)
        self.assertEqual(bm.notes, [])

    def test_custom_lane_pattern_out_of_range_filtered(self) -> None:
        # If a caller passes a pattern that addresses lanes >= num_lanes,
        # those beats get dropped silently. Documents that quirk so a
        # future change doesn't accidentally accept lane 99.
        from finger_rehab.audio.beatmap import procedural_beatmap
        bm = procedural_beatmap(
            bpm=120, beats=16, difficulty="hard",
            lane_pattern=[0, 1, 99],
            num_lanes=4,
        )
        for n in bm.notes:
            self.assertLess(n.lane, 4)

    def test_procedural_beatmap_minimum_one_beat(self) -> None:
        from finger_rehab.audio.beatmap import procedural_beatmap
        bm = procedural_beatmap(bpm=120, beats=1, difficulty="hard")
        self.assertEqual(len(bm.notes), 1)

    def test_unknown_difficulty_defaults_to_medium_stride(self) -> None:
        from finger_rehab.audio.beatmap import procedural_beatmap
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
        from finger_rehab.audio.beatmap import Beatmap
        from finger_rehab.audio.scheduler import BeatScheduler
        sched = BeatScheduler(Beatmap(title="empty"))
        # duration_s = 0, no notes. all_done returns True for any
        # positive song time.
        self.assertTrue(sched.all_done(0.001))
        self.assertEqual(list(sched.notes_due(10.0)), [])
        self.assertEqual(sched.upcoming(0.0), [])

    def test_single_note_scheduler_yields_once_then_done(self) -> None:
        from finger_rehab.audio.beatmap import Beatmap, Note
        from finger_rehab.audio.scheduler import BeatScheduler
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
        from finger_rehab.audio.beatmap import Beatmap, Note
        from finger_rehab.audio.scheduler import BeatScheduler
        bm = Beatmap(notes=[Note(t=0.1, lane=0)])
        sched = BeatScheduler(bm)
        list(sched.notes_due(1.0))      # fire it
        self.assertTrue(sched._sched[0].fired)
        sched.reset()
        self.assertFalse(sched._sched[0].fired)
        # After reset, notes_due yields it again.
        self.assertEqual(len(list(sched.notes_due(1.0))), 1)


class CueOnTheBeatTests(unittest.TestCase):
    """The cue (buzz, tone, EEG marker all ride on_stim) must land on
    the SCORED ZERO: note time plus the audio-path latency, the moment
    a press scores 0 ms. It used to dispatch on the first frame after
    the raw note time, which was always a frame late against the
    schedule and a whole audio offset away from the beat the patient
    hears (measured on a fake wire: -31 ms for a song). These tests
    drive update() on a fake clock stepped in 17 ms frames and pin the
    new dispatch: against the scored zero, frame-centred, and with the
    scheduled cue moment as the logged timestamp.

    They run under rhythm.tactile_mode on_beat with a zero buzzer
    latency, the pre-September condition where the buzz rides the beat
    dispatch: one on_stim per note carries everything. Lead mode and
    the latency split are pinned in tests/test_rhythm_tactile.py."""

    FRAME_S = 0.017

    def _make_mode(self, song=True, rise_comp_ms=0.0):
        from unittest.mock import MagicMock
        from finger_rehab.audio.beatmap import Beatmap, Note
        from finger_rehab.game.modes.rhythm import RhythmMode
        from finger_rehab.game.scoring import RhythmWindows, ScoreConfig
        bm = Beatmap(notes=[Note(t=1.0, lane=0), Note(t=2.0, lane=1),
                            Note(t=3.0, lane=2)],
                     song=("song.mp3" if song else None))
        engine = MagicMock()
        engine._rhythm_buzz_lead_ms = None
        cfg = {
            "rhythm.pre_song_lead_s": 0,
            "game.start_countdown_s": 0,
            "rhythm.audio_offset_ms": 40,
            "rhythm.metronome_offset_ms": 12,
            "rhythm.buzz_rise_comp_ms": rise_comp_ms,
            "rhythm.tactile_mode": "on_beat",
            "latency.buzzer_ms": 0,
            "latency.visual_ms": 0,
        }
        engine.cfg.get = MagicMock(
            side_effect=lambda k, d=None: cfg.get(k, d))
        if song:
            engine.audio._song_path = "song.mp3"
            engine.audio._metronome_period = None
        else:
            engine.audio._song_path = None
            engine.audio._metronome_period = 0.5
        engine.audio.play_song = MagicMock(return_value=True)
        mode = RhythmMode(engine, bm, RhythmWindows(), ScoreConfig())
        return mode, engine, bm

    def _drive(self, mode, clock, until_song_t):
        end = mode._t_start + until_song_t
        while clock.t < end:
            clock.t += self.FRAME_S
            mode.update(self.FRAME_S)

    class _Clock:
        def __init__(self, t0: float) -> None:
            self.t = t0

        def perf_counter(self) -> float:
            return self.t

    def _with_fake_clock(self, fn):
        import finger_rehab.game.modes.rhythm as rhythm_mod
        real_time = rhythm_mod.time
        clock = self._Clock(1000.0)
        rhythm_mod.time = clock
        try:
            return fn(clock)
        finally:
            rhythm_mod.time = real_time

    def test_cue_fires_at_the_scored_zero_with_a_song(self) -> None:
        # Tracks the dispatch wall time per call via a side effect so
        # both halves are pinned: the logged timestamp is the
        # scheduled cue moment, and the dispatch frame is centred on
        # it (within half a frame either side, never a full frame
        # late).
        def go(clock):
            mode, engine, bm = self._make_mode(song=True)
            dispatched = []
            engine.on_stim.side_effect = (
                lambda lane, idx, t_perf, buzz=True:
                dispatched.append(clock.t))
            self._drive(mode, clock, 2.5)
            calls = engine.on_stim.call_args_list
            self.assertEqual(len(calls), 2, "two notes were due by 2.5s")
            for call, at, note in zip(calls, dispatched, bm.notes[:2]):
                _lane, _idx, t_perf = call[0]
                target = mode._t_start + note.t + 0.040
                self.assertAlmostEqual(t_perf, target, places=9)
                err_ms = (at - target) * 1000.0
                self.assertLessEqual(abs(err_ms),
                                     self.FRAME_S * 1000.0 / 2 + 0.5,
                    f"dispatch missed the beat by {err_ms:.1f} ms")

        self._with_fake_clock(go)

    def test_metronome_uses_its_own_smaller_offset(self) -> None:
        def go(clock):
            mode, engine, bm = self._make_mode(song=False)
            self._drive(mode, clock, 1.5)
            calls = engine.on_stim.call_args_list
            self.assertEqual(len(calls), 1)
            _lane, _idx, t_perf = calls[0][0]
            self.assertAlmostEqual(
                t_perf, mode._t_start + bm.notes[0].t + 0.012, places=9)

        self._with_fake_clock(go)

    def test_press_exactly_at_the_cue_scores_zero_offset(self) -> None:
        # The whole point of the move: the buzz and the scored zero
        # are now the same moment, so a press right at the buzz is a
        # 0 ms asynchrony, not an artefact of the audio offset.
        def go(clock):
            from finger_rehab.hardware.fsr_detector import PressEvent
            mode, engine, bm = self._make_mode(song=True)
            self._drive(mode, clock, 1.2)
            self.assertEqual(engine.on_stim.call_count, 1)
            _lane, _idx, cue_t = engine.on_stim.call_args[0]
            mode.queue_press(PressEvent(lane=0, t_perf=cue_t,
                                        value=0, baseline=0.0))
            clock.t += self.FRAME_S
            mode.update(self.FRAME_S)
            engine.log_rhythm_hit.assert_called_once()
            offset_ms = engine.log_rhythm_hit.call_args[0][1]
            self.assertLess(abs(offset_ms), 1.0,
                f"press at the cue scored {offset_ms:.1f} ms, not 0")

        self._with_fake_clock(go)

    def test_rise_comp_pulls_only_the_buzz_earlier(self) -> None:
        # A rig that has bench-measured its motors subtracts the rise
        # time from the BUZZ: the STIM command leads the scored zero
        # by it through on_tactile_lead, while the tone, the screen
        # and the stimulus marker (on_stim, now with buzz=False) stay
        # on the scored zero. Before September the whole cue moved.
        def go(clock):
            mode, engine, bm = self._make_mode(song=True,
                                               rise_comp_ms=20.0)
            self._drive(mode, clock, 1.2)
            _lane, _idx, t_perf = engine.on_stim.call_args[0]
            self.assertAlmostEqual(
                t_perf, mode._t_start + bm.notes[0].t + 0.040, places=9)
            self.assertFalse(engine.on_stim.call_args[1]["buzz"])
            engine.on_tactile_lead.assert_called_once()
            _lane, _idx, t_buzz = engine.on_tactile_lead.call_args[0]
            self.assertAlmostEqual(
                t_buzz, mode._t_start + bm.notes[0].t + 0.040 - 0.020,
                places=9)

        self._with_fake_clock(go)

    def test_on_beat_with_no_rise_keeps_one_event_per_note(self) -> None:
        # The pre-September shape: with nothing to lead by, the buzz
        # rides on_stim (buzz=True) and no lead call is made, so the
        # wire and the EEG see one event per note.
        def go(clock):
            mode, engine, bm = self._make_mode(song=True)
            self._drive(mode, clock, 2.5)
            self.assertEqual(engine.on_stim.call_count, 2)
            for call in engine.on_stim.call_args_list:
                self.assertTrue(call[1]["buzz"])
            engine.on_tactile_lead.assert_not_called()

        self._with_fake_clock(go)


if __name__ == "__main__":
    unittest.main()
