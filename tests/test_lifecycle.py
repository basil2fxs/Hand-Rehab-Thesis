"""Tests for the session lifecycle: finish_block, _abandon_if_in_block,
and the ResultsScreen grade thresholds. These paths are critical for
data integrity (CSV file handles, metadata JSON) so they need direct
coverage."""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")


class ResultsScreenGradeTests(unittest.TestCase):
    """Grade letter S/A/B/C/D/E + colour are derived from hit rate.
    Out-of-range rates must still produce a sensible result so a buggy
    upstream value doesn't crash the results screen."""

    def setUp(self) -> None:
        import pygame
        pygame.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        from rehab.ui.screens import ResultsScreen
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        self.eng = GameEngine(cfg, KeyboardOnlySource())
        self.rs = ResultsScreen(self.eng)

    def tearDown(self) -> None:
        import pygame
        pygame.quit()

    def test_grade_thresholds_walk_through_all_tiers(self) -> None:
        cases = [
            (1.00, "S"), (0.96, "S"),
            (0.95, "S"), (0.90, "A"), (0.85, "A"),
            (0.80, "B"), (0.70, "B"),
            (0.60, "C"), (0.50, "C"),
            (0.40, "D"), (0.30, "D"),
            (0.20, "E"), (0.00, "E"),
        ]
        for rate, expected in cases:
            got, _ = self.rs._grade_for(rate)
            self.assertEqual(got, expected,
                f"rate {rate} should grade {expected}, got {got}")

    def test_grade_handles_out_of_range_input(self) -> None:
        # Defensive: a negative or > 1.0 rate must not crash.
        self.rs._grade_for(-0.5)        # -> E
        self.rs._grade_for(1.5)         # -> S
        # Both should return a tuple of (str, str).
        for rate in (-1.0, 0.0, 1.0, 2.0):
            got = self.rs._grade_for(rate)
            self.assertIsInstance(got, tuple)
            self.assertEqual(len(got), 2)
            self.assertIsInstance(got[0], str)
            self.assertIsInstance(got[1], str)

    def test_zero_trials_renders_without_crash(self) -> None:
        # Right after a block aborts with no trials logged, hits +
        # misses can both be 0. The screen must still draw cleanly with
        # no division by zero.
        import pygame
        self.eng.hits = 0
        self.eng.misses = 0
        self.eng.score = 0
        screen = pygame.display.set_mode((1280, 800))
        self.rs.draw(screen)
        # If we got here without an exception, the screen draws.


class FinishBlockLifecycleTests(unittest.TestCase):
    """finish_block must save metadata, close loggers, set
    last_session_root, AND not leak file handles when save fails."""

    def _make_engine(self):
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        eng = GameEngine(cfg, KeyboardOnlySource())
        # Stub show_results so we don't try to switch screens (the
        # _screens dict is only populated during run()).
        eng.show_results = lambda: None
        return eng

    def test_finish_block_saves_metadata_and_closes_loggers(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine()
            eng.cfg.data["session"]["data_dir"] = td
            eng.current_block = "classic"
            eng._begin_block("classic")
            self.assertIsNotNone(eng.session_paths)
            paths = eng.session_paths
            eng.finish_block()
            # Loggers closed, paths cleared, last_session_root set.
            self.assertIsNone(eng.trial_logger)
            self.assertIsNone(eng.raw_logger)
            self.assertIsNone(eng.session_paths)
            self.assertEqual(eng.last_session_root, str(paths.root))
            # Metadata file written.
            self.assertTrue(paths.metadata_json.exists())

    def test_finish_block_closes_loggers_even_when_save_fails(self) -> None:
        # If Session.save raises (e.g. disk full, permission), the raw-
        # logger thread MUST still get stopped or the next session will
        # leak a thread and an open file handle.
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine()
            eng.cfg.data["session"]["data_dir"] = td
            eng._begin_block("classic")
            raw_logger = eng.raw_logger
            trial_logger = eng.trial_logger
            self.assertIsNotNone(raw_logger)
            self.assertIsNotNone(trial_logger)
            # Make session.save explode.
            eng.session.save = lambda p: (_ for _ in ()).throw(
                OSError("disk full"))
            eng.finish_block()
            # Despite the save failure, loggers must be closed.
            self.assertIsNone(eng.trial_logger)
            self.assertIsNone(eng.raw_logger)
            # And the raw-logger thread shouldn't be alive anymore.
            if raw_logger._thread is not None:
                self.assertFalse(raw_logger._thread.is_alive())
            # last_session_root still set (we use the same dir for the
            # CSVs even if the JSON didn't make it).
            self.assertIsNotNone(eng.last_session_root)


class AutoSaveDuringBlockTests(unittest.TestCase):
    """Auto-save behaviour so a hard crash mid-block leaves recoverable
    data. metadata.json must exist immediately after _open_loggers, the
    notes field must say 'in progress' until finish/abandon, and the
    file should be re-written periodically as trials accumulate."""

    def _make_engine(self):
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        eng = GameEngine(cfg, KeyboardOnlySource())
        eng.show_results = lambda: None
        return eng

    def test_metadata_written_at_block_start(self) -> None:
        import json
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine()
            eng.cfg.data["session"]["data_dir"] = td
            eng._begin_block("classic")
            metadata = eng.session_paths.metadata_json
            self.assertTrue(metadata.exists(),
                "metadata.json must exist immediately after _open_loggers")
            with metadata.open() as f:
                data = json.load(f)
            self.assertIn("in progress", data["notes"].lower())
            self.assertEqual(data["finished_at"], "")
            self.assertIsNotNone(eng.last_session_root)

    def test_last_session_root_set_at_block_start(self) -> None:
        # Even before finish_block runs, last_session_root must point
        # at the active folder so a crash leaves a recoverable path.
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine()
            eng.cfg.data["session"]["data_dir"] = td
            eng._begin_block("adaptive")
            self.assertIsNotNone(eng.last_session_root)
            self.assertTrue(Path(eng.last_session_root).exists())

    def test_periodic_resave_updates_metadata(self) -> None:
        import json
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine()
            eng.cfg.data["session"]["data_dir"] = td
            eng._begin_block("classic")
            metadata = eng.session_paths.metadata_json
            # Simulate 10 hits so the periodic re-save fires.
            eng.hits = 10
            eng.misses = 0
            eng.score = 50
            eng._maybe_resave_metadata()
            with metadata.open() as f:
                data = json.load(f)
            # Notes should now mention the trial count + score.
            self.assertIn("trial 10", data["notes"])
            self.assertIn("score 50", data["notes"])

    def test_periodic_resave_no_op_before_n_trials(self) -> None:
        # Should NOT re-save on trial 1, 2, ..., 9. Only on multiples of 10.
        import json
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine()
            eng.cfg.data["session"]["data_dir"] = td
            eng._begin_block("classic")
            metadata = eng.session_paths.metadata_json
            initial_mtime = metadata.stat().st_mtime
            # 5 trials in -> no resave.
            eng.hits = 3
            eng.misses = 2
            eng._maybe_resave_metadata()
            self.assertEqual(metadata.stat().st_mtime, initial_mtime)
            # Verify the original 'in progress' note is still there.
            with metadata.open() as f:
                self.assertIn("in progress", json.load(f)["notes"].lower())


class ResearchSchemaTests(unittest.TestCase):
    """Trial schema captures the context a researcher needs for thesis
    analysis: timestamps, engine state (BPM, recovery, streak), song
    position for rhythm. Block summary lands in metadata.json."""

    def _make_engine(self):
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        eng = GameEngine(cfg, KeyboardOnlySource())
        eng.show_results = lambda: None
        return eng

    def test_trial_columns_include_research_fields(self) -> None:
        from rehab.data.logger import TRIAL_COLUMNS
        for field_name in ("iso_ts", "block_t_s", "bpm_at_trial",
                            "streak_at_trial", "in_recovery",
                            "song_time_s"):
            self.assertIn(field_name, TRIAL_COLUMNS,
                f"{field_name} must be in trials.csv schema for research")

    def test_classic_trial_row_populates_context(self) -> None:
        # Fire a synthetic trial in classic mode and confirm the new
        # columns appear in the written row.
        from unittest.mock import MagicMock
        from rehab.game.modes.classic import PendingTrial
        from rehab.game.scoring import TrialResult
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine()
            eng.cfg.data["session"]["data_dir"] = td
            eng.mode = None     # classic-only path (no adapter)
            eng._screens = {"gameplay": MagicMock(), "rhythm": MagicMock()}
            eng._begin_block("classic")
            trial = PendingTrial(
                trial_id=1, lane=2, stim_t_perf=0.0,
                keys_pressed=[2], incorrect_presses=[],
            )
            outcome = TrialResult(label="Great", points=3, rt_ms=180.0)
            eng.log_trial(trial, outcome, 0.0)
            # Read trials.csv back.
            import csv
            with eng.session_paths.trials_csv.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["block"], "classic")
            self.assertNotEqual(row["iso_ts"], "")
            self.assertNotEqual(row["block_t_s"], "")
            self.assertEqual(row["bpm_at_trial"], "")    # no adapter in classic
            self.assertEqual(row["song_time_s"], "")     # not rhythm
            # streak_at_trial captured BEFORE _update_streak runs, so
            # the first hit shows 0 (came in with no streak).
            self.assertEqual(row["streak_at_trial"], "0")

    def test_adaptive_trial_row_captures_bpm(self) -> None:
        from unittest.mock import MagicMock
        from rehab.game.modes.classic import PendingTrial
        from rehab.game.scoring import TrialResult
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine()
            eng.cfg.data["session"]["data_dir"] = td
            # Fake an adapter so _trial_context picks up its BPM.
            class FakeAdapter:
                bpm = 90.0
                in_recovery = False
            class FakeMode:
                adapter = FakeAdapter()
            eng.mode = FakeMode()
            eng._screens = {"gameplay": MagicMock(), "rhythm": MagicMock()}
            eng._begin_block("adaptive")
            trial = PendingTrial(
                trial_id=1, lane=0, stim_t_perf=0.0,
                keys_pressed=[0], incorrect_presses=[],
            )
            outcome = TrialResult(label="Great", points=3, rt_ms=220.0)
            eng.log_trial(trial, outcome, 0.0)
            import csv
            with eng.session_paths.trials_csv.open() as f:
                row = list(csv.DictReader(f))[0]
            self.assertEqual(row["bpm_at_trial"], "90.0")
            self.assertEqual(row["in_recovery"], "FALSE")

    def test_block_summary_written_at_finish(self) -> None:
        import json
        from unittest.mock import MagicMock
        from rehab.game.modes.classic import PendingTrial
        from rehab.game.scoring import TrialResult
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine()
            eng.cfg.data["session"]["data_dir"] = td
            eng.mode = None
            eng._screens = {"gameplay": MagicMock(), "rhythm": MagicMock()}
            eng._begin_block("classic")
            metadata_path = eng.session_paths.metadata_json
            # Log a few trials + finish.
            for i in range(3):
                trial = PendingTrial(
                    trial_id=i + 1, lane=i, stim_t_perf=0.0,
                    keys_pressed=[i], incorrect_presses=[],
                )
                eng.log_trial(
                    trial,
                    TrialResult(label="Great", points=3, rt_ms=200.0),
                    0.0,
                )
            eng.finish_block()
            with metadata_path.open() as f:
                meta = json.load(f)
            summary = meta["block_summary"]
            self.assertEqual(summary["block"], "classic")
            self.assertEqual(summary["status"], "completed")
            self.assertEqual(summary["trials"], 3)
            self.assertEqual(summary["hits"], 3)
            self.assertEqual(summary["misses"], 0)
            self.assertEqual(summary["hit_rate"], 1.0)
            self.assertEqual(summary["avg_rt_ms"], 200.0)
            self.assertGreaterEqual(summary["peak_streak"], 0)
            # No BPM context for classic.
            self.assertNotIn("bpm_min", summary)


class AbandonLifecycleTests(unittest.TestCase):
    """_abandon_if_in_block must be safe to call when not in a block,
    must save the abandon marker, and must not double-fire CSV handles."""

    def _make_engine(self):
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        eng = GameEngine(cfg, KeyboardOnlySource())
        return eng

    def test_abandon_when_not_in_block_is_a_noop(self) -> None:
        eng = self._make_engine()
        self.assertIsNone(eng.session_paths)
        # Should not raise and not flip last_session_root from None.
        eng._abandon_if_in_block()
        self.assertIsNone(eng.session_paths)
        self.assertIsNone(eng.last_session_root)

    def test_abandon_writes_abandoned_marker_to_metadata(self) -> None:
        import json
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine()
            eng.cfg.data["session"]["data_dir"] = td
            eng._begin_block("adaptive")
            metadata_path = eng.session_paths.metadata_json
            eng._abandon_if_in_block()
            self.assertTrue(metadata_path.exists())
            with metadata_path.open() as f:
                data = json.load(f)
            self.assertIn("abandoned mid-block", data["notes"])
            self.assertEqual(eng.session_paths, None)
            self.assertIsNone(eng.mode)

    def test_double_abandon_is_safe(self) -> None:
        # Calling _abandon twice in a row must not raise and must not
        # try to write metadata twice. The second call is a no-op
        # because session_paths is already None.
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine()
            eng.cfg.data["session"]["data_dir"] = td
            eng._begin_block("classic")
            eng._abandon_if_in_block()
            # Should not raise.
            eng._abandon_if_in_block()


class SessionPathsCollisionTests(unittest.TestCase):
    """If two sessions land on the same timestamp (down to the second),
    SessionPaths must auto-suffix the folder so we don't crash on a
    pre-existing directory."""

    def test_collision_appends_numeric_suffix(self) -> None:
        from rehab.data.logger import SessionPaths
        with tempfile.TemporaryDirectory() as td:
            data_dir = Path(td)
            p1 = SessionPaths.for_session(data_dir, "Basil")
            p2 = SessionPaths.for_session(data_dir, "Basil")
            # Two distinct folders even if the timestamp collides.
            self.assertNotEqual(p1.root, p2.root)
            self.assertTrue(p1.root.exists())
            self.assertTrue(p2.root.exists())

    def test_unsafe_chars_in_name_get_replaced(self) -> None:
        from rehab.data.logger import SessionPaths
        with tempfile.TemporaryDirectory() as td:
            paths = SessionPaths.for_session(Path(td), "A/B C")
            # Slashes and spaces replaced so the folder is a valid path.
            self.assertNotIn("/", paths.root.name)
            self.assertNotIn(" ", paths.root.name)


class RetryLastBlockTests(unittest.TestCase):
    """Retry button on the results screen re-runs the same block kind
    with the same config. Classic / adaptive read their settings from
    config; rhythm needs the last beatmap source song stashed on the
    engine."""

    def test_retry_routes_classic_to_begin_classic(self) -> None:
        from unittest.mock import MagicMock
        from rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        eng.current_block = "classic"
        eng.begin_classic_block = MagicMock()
        eng.begin_adaptive_block = MagicMock()
        eng.show_mode_select = MagicMock()
        eng.retry_last_block()
        eng.begin_classic_block.assert_called_once()
        eng.begin_adaptive_block.assert_not_called()
        eng.show_mode_select.assert_not_called()

    def test_retry_routes_adaptive_to_begin_adaptive(self) -> None:
        from unittest.mock import MagicMock
        from rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        eng.current_block = "adaptive"
        eng.begin_classic_block = MagicMock()
        eng.begin_adaptive_block = MagicMock()
        eng.show_mode_select = MagicMock()
        eng.retry_last_block()
        eng.begin_adaptive_block.assert_called_once()

    def test_retry_without_prior_block_falls_back_to_mode_select(self) -> None:
        from unittest.mock import MagicMock
        from rehab.game.engine import GameEngine
        eng = GameEngine.__new__(GameEngine)
        eng.current_block = "(none)"
        eng.show_mode_select = MagicMock()
        eng.retry_last_block()
        eng.show_mode_select.assert_called_once()


if __name__ == "__main__":
    unittest.main()
