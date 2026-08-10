"""Tests for the research-capture completeness pass.

Four things were previously computed but never persisted (or never
computed at all):

  1. `loud_trial` per trial - the boosted-cue flag is a stimulus
     property and MUST be in the trial CSV or it is an uncontrolled
     confound in any RT analysis.
  2. `timeout_ms` per trial - the response window (RT censoring
     limit), which varies per trial in adaptive mode.
  3. `force_window_sum` / `force_window_peaks` per trial - the
     all-finger force over the post-stim window, previously shown on
     the results screen only.
  4. Block summary: miss_force totals, loud-trial count, the rhythm
     song identity, and end-of-block sensor baselines.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class TrialColumnsTests(unittest.TestCase):
    def test_new_columns_registered(self) -> None:
        from rehab.data.logger import TRIAL_COLUMNS
        for col in ("loud_trial", "timeout_ms",
                     "force_window_sum", "force_window_peaks"):
            self.assertIn(col, TRIAL_COLUMNS)


def _bare_engine():
    """GameEngine via __new__ with the state log_trial needs, plus a
    recording stand-in for the trial logger."""
    from rehab.game.engine import GameEngine
    eng = GameEngine.__new__(GameEngine)
    eng.cfg = MagicMock()
    eng.cfg.get = MagicMock(return_value=0)
    eng.score = 0
    eng.hits = 0
    eng.misses = 0
    eng.hit_streak = 0
    eng.miss_streak = 0
    eng._streak_fired = set()
    eng._streak_thresholds = ()
    eng._block_rt_sum = 0.0
    eng._block_rt_count = 0
    eng._block_bpm_min = None
    eng._block_bpm_max = None
    eng._block_wrong_press_trials = 0
    eng._block_rhythm_spurious_presses = 0
    eng._block_idle_presses = 0
    eng._block_peak_streak = 0
    eng._last_gained = 0
    eng.current_block = "adaptive"
    eng.hand_mode = "right"
    eng.raw_logger = None
    eng.audio = None
    eng._screens = {}
    eng.session_paths = None
    eng.session = MagicMock()
    eng.session.participant = "T"
    eng.session.age = ""
    eng.theme = MagicMock()
    eng.mode = None
    eng._per_lane_rts = {}
    eng._per_lane_misses = {}
    eng._per_lane_wrong = {}
    eng._trial_context_orig = None

    rows: list[dict] = []
    logger = MagicMock()
    logger.write = rows.append
    eng.trial_logger = logger
    eng._rows = rows
    return eng


def _trial(lane: int, incorrect=()):
    from rehab.game.modes.classic import PendingTrial
    return PendingTrial(
        trial_id=1, lane=lane, stim_t_perf=0.0,
        keys_pressed=[lane], incorrect_presses=list(incorrect),
    )


def _result(label: str, rt_ms, points: int = 0):
    from rehab.game.scoring import TrialResult
    return TrialResult(label=label, points=points, rt_ms=rt_ms)


class _Det:
    def __init__(self, base: float) -> None:
        self._b = base

    def baseline_value(self, i: int) -> float:
        return self._b


class LogTrialCaptureTests(unittest.TestCase):
    def test_loud_flag_and_timeout_written(self) -> None:
        eng = _bare_engine()
        eng._ensure_metric_state()
        eng._loud_trials_by_id = {1: True}
        eng._last_stim_timeout_ms = 850.0
        eng.log_trial(_trial(lane=2), _result("Great", 180.0), now=0.0)
        row = eng._rows[0]
        self.assertEqual(row["loud_trial"], "TRUE")
        self.assertEqual(row["timeout_ms"], "850")

    def test_quiet_trial_logged_false(self) -> None:
        eng = _bare_engine()
        eng._ensure_metric_state()
        eng._loud_trials_by_id = {1: False}
        eng.log_trial(_trial(lane=0), _result("Good", 300.0), now=0.0)
        self.assertEqual(eng._rows[0]["loud_trial"], "FALSE")

    def test_miss_with_no_incorrect_press_is_a_timeout(self) -> None:
        eng = _bare_engine()
        eng._ensure_metric_state()
        eng.log_trial(_trial(lane=1), _result("Miss", None), now=0.0)
        self.assertEqual(eng._rows[0]["error_type"], "timeout")

    def test_miss_caused_by_wrong_finger_is_not_a_timeout(self) -> None:
        # A wrong-then-correct trial that a mode downgrades to Miss
        # finished promptly, on the wrong finger -- it did not time
        # out. Collapsing both into error_type=="timeout" would make a
        # timeout-rate analysis silently swallow every wrong-finger
        # Miss too.
        eng = _bare_engine()
        eng._ensure_metric_state()
        eng.log_trial(_trial(lane=1, incorrect=[(2, 0.05)]),
                      _result("Miss", None), now=0.0)
        row = eng._rows[0]
        self.assertEqual(row["error_type"], "wrong_finger")
        self.assertEqual(row["had_incorrect_press"], "TRUE")

    def test_force_window_cells_empty_without_samples(self) -> None:
        # Keyboard mode: no FSR data in the window -> both cells empty
        # (a zero would be a lie).
        eng = _bare_engine()
        eng._ensure_metric_state()
        eng._open_force_window(0.0, trial_id=1)
        eng.log_trial(_trial(lane=1), _result("Miss", None), now=0.0)
        row = eng._rows[0]
        self.assertEqual(row["force_window_sum"], "")
        self.assertEqual(row["force_window_peaks"], "")

    def test_force_window_cells_with_data(self) -> None:
        eng = _bare_engine()
        eng._ensure_metric_state()
        det = _Det(300.0)
        eng.detectors = {"right": det}
        eng._open_force_window(0.0, trial_id=1)
        # deltas 50, 0, 0, 200 above the 300 baseline
        eng._track_force_peaks(det, (350, 300, 300, 500), None,
                                (0, 0, 0, 0), 4)
        eng.log_trial(_trial(lane=1), _result("Miss", None), now=0.0)
        row = eng._rows[0]
        self.assertEqual(row["force_window_sum"], "250.000")
        self.assertEqual(row["force_window_peaks"], "1:50.000;4:200.000")
        # Miss banked into the block accumulator too.
        self.assertEqual(eng._miss_force_total, 250.0)
        self.assertEqual(eng._miss_force_count, 1)


class RhythmCaptureTests(unittest.TestCase):
    def _sched_note(self, lane: int, index: int = 0):
        from rehab.audio.beatmap import Note
        sched = MagicMock()
        sched.note = Note(t=1.0, lane=lane)
        sched.index = index
        return sched

    def test_rhythm_miss_banks_force_when_window_matches(self) -> None:
        eng = _bare_engine()
        eng.current_block = "rhythm"
        eng._ensure_metric_state()
        det = _Det(300.0)
        eng.detectors = {"right": det}
        eng._open_force_window(0.0, trial_id=7)
        eng._track_force_peaks(det, (400, 300, 300, 300), None,
                                (0, 0, 0, 0), 4)
        eng.log_rhythm_hit(self._sched_note(0, index=7), 0.0, "Miss", 0,
                            now=0.0, was_pressed=False)
        self.assertEqual(eng._miss_force_total, 100.0)
        self.assertEqual(eng._miss_force_count, 1)
        self.assertEqual(eng._rows[0]["force_window_sum"], "100.000")

    def test_rhythm_miss_skips_someone_elses_window(self) -> None:
        # The NEXT note re-armed the window before this one resolved:
        # nothing banked, force cells empty, window left alone.
        eng = _bare_engine()
        eng.current_block = "rhythm"
        eng._ensure_metric_state()
        det = _Det(300.0)
        eng.detectors = {"right": det}
        eng._open_force_window(5.0, trial_id=8)   # belongs to note 8
        eng._track_force_peaks(det, (400, 300, 300, 300), None,
                                (0, 0, 0, 0), 4)
        eng.log_rhythm_hit(self._sched_note(0, index=7), 0.0, "Miss", 0,
                            now=0.0, was_pressed=False)
        self.assertEqual(eng._miss_force_count, 0)
        self.assertEqual(eng._rows[0]["force_window_sum"], "")
        # Note 8's window survives untouched.
        self.assertEqual(eng._force_window_trial_id, 8)

    def test_rhythm_row_has_loud_flag(self) -> None:
        eng = _bare_engine()
        eng.current_block = "rhythm"
        eng._ensure_metric_state()
        eng._loud_trials_by_id = {3: True}
        eng.log_rhythm_hit(self._sched_note(1, index=3), 40.0, "Great", 6,
                            now=0.0, was_pressed=True)
        self.assertEqual(eng._rows[0]["loud_trial"], "TRUE")


class OnStimRecordingTests(unittest.TestCase):
    def test_on_stim_records_loud_flag_and_timeout(self) -> None:
        eng = _bare_engine()
        eng.detectors = {}
        eng.source = MagicMock()
        eng.cfg.get = MagicMock(
            side_effect=lambda k, d=None:
                {"game.timeout_s": 0.9, "cue.buzz_before": False,
                 "cue.sound_before": False}.get(k, d))
        eng._ensure_metric_state()
        eng._loud_trial_fraction = 1.0   # every trial loud
        eng._loud_trial_boost = 1.35
        audio = MagicMock()
        eng.audio = audio
        eng.on_stim(lane=0, trial_id=1, t_perf=100.0)
        self.assertTrue(eng._loud_trials_by_id[1])
        self.assertEqual(eng._block_loud_trials, 1)
        audio.set_trial_gain.assert_called_with(1.35)
        self.assertEqual(eng._last_stim_timeout_ms, 900.0)
        # Window opened and tagged with the trial id.
        self.assertEqual(eng._force_window_trial_id, 1)
        self.assertEqual(eng._force_window_start, 100.0)

    def test_no_audio_means_flag_false(self) -> None:
        # Without an audio engine no boost is heard, so the CSV must
        # not claim the trial played loud.
        eng = _bare_engine()
        eng.detectors = {}
        eng.source = MagicMock()
        eng.cfg.get = MagicMock(
            side_effect=lambda k, d=None:
                {"cue.buzz_before": False}.get(k, d))
        eng._ensure_metric_state()
        eng._loud_trial_fraction = 1.0
        eng.audio = None
        eng.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertFalse(eng._loud_trials_by_id[1])
        self.assertEqual(eng._block_loud_trials, 0)


class BlockSummaryCaptureTests(unittest.TestCase):
    def _summary_engine(self):
        eng = _bare_engine()
        eng._ensure_metric_state()
        eng._per_lane_peak_force = {}
        eng._per_lane_impulse = {}
        eng._across_blocks_mean_rt = []
        eng._across_blocks_mean_peak = []
        eng._drift_samples = {}
        eng._rhythm_press_times_s = []
        eng._rhythm_beat_times_s = []
        eng._rhythm_signed_offsets_ms = []
        eng.detectors = {"right": _Det(310.5)}
        eng.detectors["right"].last_value = [0, 0, 0, 0]
        eng.source = MagicMock(spec=[])   # no get_startup_latency
        return eng

    def test_summary_contains_miss_force_and_loud_trials(self) -> None:
        eng = self._summary_engine()
        eng._miss_force_total = 500.0
        eng._miss_force_count = 2
        eng._force_window_ms = 1000.0
        eng._block_loud_trials = 4
        eng._loud_trial_fraction = 0.10
        eng._loud_trial_boost = 1.35
        s = eng._build_block_summary("completed")
        self.assertEqual(s["miss_force"]["total"], 500.0)
        self.assertEqual(s["miss_force"]["n_misses"], 2)
        self.assertEqual(s["miss_force"]["mean_per_miss"], 250.0)
        self.assertEqual(s["miss_force"]["window_ms"], 1000.0)
        self.assertEqual(s["loud_trials"]["n"], 4)
        self.assertEqual(s["loud_trials"]["configured_fraction"], 0.10)

    def test_summary_contains_baseline_end(self) -> None:
        eng = self._summary_engine()
        s = eng._build_block_summary("completed")
        self.assertEqual(s["baseline_end"]["right_0"], 310.5)
        self.assertEqual(len(s["baseline_end"]), 4)

    def test_rhythm_summary_contains_song(self) -> None:
        eng = self._summary_engine()
        eng.current_block = "rhythm"
        bm = MagicMock()
        bm.title = "Test Track"
        bm.difficulty = "medium"
        bm.bpm = 118.2
        bm.notes = [1, 2, 3]
        bm.song = "assets/music/test.ogg"
        eng.mode = MagicMock()
        eng.mode.beatmap = bm
        eng.mode.adapter = None
        s = eng._build_block_summary("completed")
        self.assertEqual(s["song"]["title"], "Test Track")
        self.assertEqual(s["song"]["difficulty"], "medium")
        self.assertEqual(s["song"]["bpm"], 118.2)
        self.assertEqual(s["song"]["n_notes"], 3)
        self.assertIn("test.ogg", s["song"]["song_path"])


if __name__ == "__main__":
    unittest.main()


class StimDeliveryCaptureTests(unittest.TestCase):
    """The buzzer cue's delivery is recorded per trial. Without it a
    session where the Arduino dropped out looks like a patient who
    simply stopped responding."""

    def test_column_registered(self) -> None:
        from rehab.data.logger import TRIAL_COLUMNS
        self.assertIn("stim_delivered", TRIAL_COLUMNS)

    def _stim_engine(self, send_result):
        eng = _bare_engine()
        eng._ensure_metric_state()
        eng.detectors = {}
        eng.source = MagicMock()
        eng.source.send_command = MagicMock(return_value=send_result)
        eng.cfg.get = MagicMock(
            side_effect=lambda k, d=None: {
                "cue.buzz_before": True, "game.timeout_s": 1.0,
                "cue.sound_before": False,
            }.get(k, d))
        eng.audio = None
        eng.raw_logger = MagicMock()
        return eng

    def test_successful_stim_logged_true(self) -> None:
        eng = self._stim_engine(True)
        eng.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertIs(eng._last_stim_delivered, True)
        self.assertEqual(eng._block_stim_failures, 0)
        eng.log_trial(_trial(lane=0), _result("Great", 200.0), now=0.0)
        self.assertEqual(eng._rows[0]["stim_delivered"], "TRUE")

    def test_failed_stim_logged_false_and_counted(self) -> None:
        eng = self._stim_engine(False)
        eng.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertIs(eng._last_stim_delivered, False)
        self.assertEqual(eng._block_stim_failures, 1)
        eng.log_trial(_trial(lane=0), _result("Miss", None), now=0.0)
        self.assertEqual(eng._rows[0]["stim_delivered"], "FALSE")

    def test_raw_event_emitted_per_stim(self) -> None:
        eng = self._stim_engine(True)
        eng.on_stim(lane=2, trial_id=1, t_perf=5.0)
        kinds = [c.args[0] if c.args else c.kwargs.get("event")
                 for c in eng.raw_logger.queue_event.call_args_list]
        self.assertIn("stim_motor", kinds)

    def test_no_buzzer_cue_logs_empty(self) -> None:
        # With cue.buzz_before off there is no serial write to succeed
        # or fail, so the column must stay empty rather than claiming a
        # delivery either way.
        eng = self._stim_engine(True)
        eng.cfg.get = MagicMock(
            side_effect=lambda k, d=None: {
                "cue.buzz_before": False, "cue.buzz_after": False,
                "cue.sound_before": False, "cue.sound_after": False,
                "game.timeout_s": 1.0,
            }.get(k, d))
        eng.on_stim(lane=0, trial_id=1, t_perf=0.0)
        self.assertIsNone(eng._last_stim_delivered)
        eng.log_trial(_trial(lane=0), _result("Great", 200.0), now=0.0)
        self.assertEqual(eng._rows[0]["stim_delivered"], "")


class PauseCaptureTests(unittest.TestCase):
    """Pauses are recorded so a long break mid-block is visible and can
    be subtracted from the block duration."""

    def test_summary_has_pause_and_stim_fields(self) -> None:
        eng = _bare_engine()
        eng._ensure_metric_state()
        eng._per_lane_peak_force = {}
        eng._per_lane_impulse = {}
        eng._across_blocks_mean_rt = []
        eng._across_blocks_mean_peak = []
        eng._drift_samples = {}
        eng._rhythm_press_times_s = []
        eng._rhythm_beat_times_s = []
        eng._rhythm_signed_offsets_ms = []
        eng.detectors = {}
        eng.source = MagicMock(spec=[])
        eng._block_pause_count = 2
        eng._block_paused_s = 41.25
        eng._block_stim_failures = 3
        s = eng._build_block_summary("completed")
        self.assertEqual(s["pauses"], 2)
        self.assertEqual(s["paused_total_s"], 41.25)
        self.assertEqual(s["stim_cue_failures"], 3)
