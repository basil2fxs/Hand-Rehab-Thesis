"""Tests for the post-block research report (rehab/analytics/report.py)
and the pieces around it: session folder naming, the sessions index,
and the results screen's Data folder button."""
from __future__ import annotations

import csv
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


TRIAL_HEADER = [
    "iso_ts", "block_t_s", "participant", "age", "hand", "block",
    "trial", "lane", "time_difference_ms", "early_late", "points",
    "feedback", "error_type", "keys_pressed", "correct_keys",
    "num_presses", "had_incorrect_press", "first_incorrect_ms",
    "first_incorrect_lane", "bpm_at_trial", "streak_at_trial",
    "in_recovery", "song_time_s", "peak_force_n", "impulse_n", "phase",
    "loud_trial", "timeout_ms", "force_window_sum", "force_window_peaks",
]


def _write_session(root: Path, n_trials: int = 12) -> None:
    rows = []
    for t in range(1, n_trials + 1):
        miss = (t % 5 == 0)
        rows.append({
            "iso_ts": "2026-07-02T10:00:00", "block_t_s": f"{t:.1f}",
            "participant": "Pat", "age": "50", "hand": "right",
            "block": "adaptive", "trial": str(t),
            "lane": str((t % 4) + 1),
            "time_difference_ms": "" if miss else f"{300 - t * 2:.1f}",
            "early_late": "Miss" if miss else "Good",
            "points": "0" if miss else "3",
            "feedback": "Miss" if miss else "Good",
            "error_type": "timeout" if miss else "",
            "keys_pressed": "" if miss else str((t % 4) + 1),
            "correct_keys": str((t % 4) + 1),
            "num_presses": "0" if miss else "1",
            "had_incorrect_press": "FALSE",
            "peak_force_n": "" if miss else f"{100 + t:.3f}",
            "loud_trial": "TRUE" if t == 10 else "FALSE",
            "timeout_ms": "900",
        })
    with (root / "trials.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=TRIAL_HEADER)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in TRIAL_HEADER})
    meta = {
        "participant": "Pat", "age": "50", "hand": "right",
        "started_at": "2026-07-02T10:00:00",
        "finished_at": "2026-07-02T10:03:00",
        "source_name": "MultiSerialSource",
        "software_version": "1.0.0",
        "block_summary": {
            "block": "adaptive", "status": "completed",
            "trials": n_trials, "hits": n_trials - 2, "misses": 2,
            "hit_rate": 0.83, "final_score": 100, "avg_rt_ms": 280.0,
            "force_unit": "sensor units",
            "miss_force": {"window_ms": 1000, "total": 300.0,
                            "n_misses": 2, "mean_per_miss": 150.0},
            "loud_trials": {"n": 1, "configured_fraction": 0.10,
                             "boost": 1.35},
            "per_lane": {
                "0": {"rt_mean_ms": 280.0, "rt_std_ms": 20.0,
                       "rt_cv": 0.07, "hit_rate": 0.9,
                       "timeout_rate": 0.1, "misclick_rate": 0.0,
                       "peak_force_mean": 110.0, "impulse_mean": 9.0,
                       "n_trials": 3},
            },
        },
    }
    (root / "metadata.json").write_text(json.dumps(meta))


class ReportGenerationTests(unittest.TestCase):
    def test_generates_all_outputs(self) -> None:
        from rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root)
            out = report.generate(root)
            self.assertIsNotNone(out)
            self.assertTrue((root / "report.html").exists())
            self.assertTrue((root / "summary.csv").exists())
            charts = list((root / "charts").glob("*.png"))
            self.assertGreaterEqual(len(charts), 3)

    def test_html_contains_key_content(self) -> None:
        from rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root)
            report.generate(root)
            html_text = (root / "report.html").read_text()
            for needle in ("Pat", "Per-finger breakdown",
                            "data:image/png", "Miss-trial force",
                            "Loud trials played", "adaptive"):
                self.assertIn(needle, html_text)

    def test_summary_csv_is_one_flat_row(self) -> None:
        from rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root)
            report.generate(root)
            with (root / "summary.csv").open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["participant"], "Pat")
            self.assertEqual(row["miss_force.total"], "300.0")
            self.assertEqual(row["loud_trials.n"], "1")

    def test_empty_folder_returns_none(self) -> None:
        from rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(report.generate(Path(td)))

    def test_metadata_only_still_reports(self) -> None:
        # A crashed block can leave metadata without trials. Tables
        # still generate; charts are skipped.
        from rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root)
            (root / "trials.csv").unlink()
            out = report.generate(root)
            self.assertIsNotNone(out)
            self.assertTrue((root / "report.html").exists())


class SessionsIndexTests(unittest.TestCase):
    def test_index_appends_with_single_header(self) -> None:
        from rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            entry = {"finished_at": "t", "participant": "P", "age": "1",
                     "mode": "classic", "hand": "right",
                     "status": "completed", "trials": 5, "hit_rate": 0.8,
                     "avg_rt_ms": 300, "final_score": 50, "folder": "f"}
            p = report.append_index(td, entry)
            report.append_index(td, dict(entry, folder="f2"))
            lines = p.read_text().splitlines()
            self.assertEqual(len(lines), 3)   # header + 2 rows
            self.assertTrue(lines[0].startswith("date,finished_at,"))

    def test_unknown_keys_ignored(self) -> None:
        from rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            p = report.append_index(td, {"participant": "P",
                                          "bogus_key": "x"})
            with p.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["participant"], "P")
            self.assertNotIn("bogus_key", rows[0])

    def test_date_column_leads_the_index(self) -> None:
        from rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            p = report.append_index(td, {"date": "2026-07-02",
                                          "participant": "P"})
            header = p.read_text().splitlines()[0]
            self.assertTrue(header.startswith("date,"))

    def test_old_schema_index_set_aside_not_mixed(self) -> None:
        # An index written with an older column set must be renamed to
        # sessions_index_legacy.csv, not appended to with misaligned
        # rows.
        from rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            old = Path(td) / "sessions_index.csv"
            old.write_text("finished_at,participant\n2026-01-01,Old\n")
            p = report.append_index(td, {"date": "2026-07-02",
                                          "participant": "New"})
            legacy = Path(td) / "sessions_index_legacy.csv"
            self.assertTrue(legacy.exists())
            self.assertIn("Old", legacy.read_text())
            with p.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["participant"], "New")
            self.assertEqual(rows[0]["date"], "2026-07-02")


class LaneLabelTests(unittest.TestCase):
    def test_unilateral_right(self) -> None:
        from rehab.analytics.report import lane_label
        self.assertEqual(lane_label(0, "right"), "Right Index")
        self.assertEqual(lane_label(3, "right"), "Right Pinky")

    def test_unilateral_left(self) -> None:
        from rehab.analytics.report import lane_label
        self.assertEqual(lane_label(0, "left"), "Left Index")

    def test_bilateral(self) -> None:
        from rehab.analytics.report import lane_label
        self.assertEqual(lane_label(0, "both"), "Right Index")
        self.assertEqual(lane_label(4, "both"), "Left Index")
        self.assertEqual(lane_label(7, "both"), "Left Pinky")


class OpenSessionFolderTests(unittest.TestCase):
    def _engine(self, root: str | None):
        from rehab.game.engine import GameEngine
        e = GameEngine.__new__(GameEngine)
        e.last_session_root = root
        return e

    def test_opens_existing_folder_mac(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            e = self._engine(td)
            with patch("rehab.game.engine.sys") as m_sys, \
                 patch("rehab.game.engine.subprocess") as m_sub:
                m_sys.platform = "darwin"
                self.assertTrue(e.open_last_session_folder())
                m_sub.Popen.assert_called_once_with(["open", td])

    def test_missing_folder_returns_false(self) -> None:
        e = self._engine("/nonexistent/path/xyz")
        self.assertFalse(e.open_last_session_folder())
        e2 = self._engine(None)
        self.assertFalse(e2.open_last_session_folder())


class ReportHookTests(unittest.TestCase):
    def test_generate_session_report_writes_outputs(self) -> None:
        # End-to-end through the ENGINE hook: a real session folder,
        # engine state pointing at it, hook builds report + index.
        from rehab.game.engine import GameEngine
        from rehab.config import Config
        with tempfile.TemporaryDirectory() as td:
            sessions = Path(td) / "sessions"
            root = sessions / "Pat_20260702_100000_adaptive"
            root.mkdir(parents=True)
            _write_session(root)
            e = GameEngine.__new__(GameEngine)
            e.cfg = Config.load()
            e.cfg.data.setdefault("session", {})["data_dir"] = str(sessions)
            e.session_paths = MagicMock()
            e.session_paths.root = root
            e.session = MagicMock()
            e.session.participant = "Pat"
            e.session.age = "50"
            e.session.finished_at = "2026-07-02T10:03:00"
            e.session.block_summary = {"block": "adaptive",
                                        "status": "completed",
                                        "trials": 12, "hit_rate": 0.83,
                                        "avg_rt_ms": 280.0,
                                        "final_score": 100}
            e.current_block = "adaptive"
            e.hand_mode = "right"
            e._generate_session_report()
            self.assertTrue((root / "report.html").exists())
            self.assertTrue((sessions / "sessions_index.csv").exists())


if __name__ == "__main__":
    unittest.main()
