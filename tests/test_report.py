"""Tests for the post-block research report (finger_rehab/analytics/report.py)
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
        from finger_rehab.analytics import report
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
        from finger_rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root)
            report.generate(root)
            html_text = (root / "report.html").read_text()
            for needle in ("Pat", "Per-finger breakdown",
                            "data:image/png", "Miss-trial force",
                            "Loud trials played", "adaptive"):
                self.assertIn(needle, html_text)

    def test_adaptive_pace_reaches_the_headline(self) -> None:
        # Pace is adaptive's trained quantity: the controller holds
        # hit rate in a fixed band by design, so a report without a
        # BPM row hid the one number that says the patient improved.
        from finger_rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root)
            meta = json.loads((root / "metadata.json").read_text())
            meta["block_summary"]["bpm_final"] = 72.0
            meta["block_summary"]["bpm_max"] = 90.0
            meta["block_summary"]["bpm_min"] = 30.0
            (root / "metadata.json").write_text(json.dumps(meta))
            report.generate(root)
            html_text = (root / "report.html").read_text()
            for needle in ("Final pace (BPM)", "Top pace (BPM)",
                           "72.0", "90.0"):
                self.assertIn(needle, html_text)

    def test_mirror_sync_gap_reaches_the_headline(self) -> None:
        # Mirror's trained quantity is the |right - left| press gap;
        # the generic Average RT row only ever showed the later of
        # the two presses.
        from finger_rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root)
            meta = json.loads((root / "metadata.json").read_text())
            meta["block_summary"]["block"] = "mirror"
            meta["block_summary"]["mirror"] = {
                "mean_gap_ms": 84.2, "n_synced_hits": 9,
                "right_hand_mean_rt_ms": 410.0,
                "left_hand_mean_rt_ms": 460.0,
            }
            (root / "metadata.json").write_text(json.dumps(meta))
            report.generate(root)
            html_text = (root / "report.html").read_text()
            for needle in ("Mean gap over clean pairs (ms)", "84.2",
                           "Right hand mean RT (ms)", "460.0"):
                self.assertIn(needle, html_text)

    def test_summary_csv_is_one_flat_row(self) -> None:
        from finger_rehab.analytics import report
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
        from finger_rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            self.assertIsNone(report.generate(Path(td)))

    def test_metadata_only_still_reports(self) -> None:
        # A crashed block can leave metadata without trials. Tables
        # still generate; charts are skipped.
        from finger_rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root)
            (root / "trials.csv").unlink()
            out = report.generate(root)
            self.assertIsNotNone(out)
            self.assertTrue((root / "report.html").exists())


class SessionsIndexTests(unittest.TestCase):
    def test_index_appends_with_single_header(self) -> None:
        from finger_rehab.analytics import report
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
        from finger_rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            p = report.append_index(td, {"participant": "P",
                                          "bogus_key": "x"})
            with p.open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(rows[0]["participant"], "P")
            self.assertNotIn("bogus_key", rows[0])

    def test_date_column_leads_the_index(self) -> None:
        from finger_rehab.analytics import report
        with tempfile.TemporaryDirectory() as td:
            p = report.append_index(td, {"date": "2026-07-02",
                                          "participant": "P"})
            header = p.read_text().splitlines()[0]
            self.assertTrue(header.startswith("date,"))

    def test_old_schema_index_set_aside_not_mixed(self) -> None:
        # An index written with an older column set must be renamed to
        # sessions_index_legacy.csv, not appended to with misaligned
        # rows.
        from finger_rehab.analytics import report
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
        from finger_rehab.analytics.report import lane_label
        self.assertEqual(lane_label(0, "right"), "Right Index")
        self.assertEqual(lane_label(3, "right"), "Right Pinky")

    def test_unilateral_left(self) -> None:
        from finger_rehab.analytics.report import lane_label
        self.assertEqual(lane_label(0, "left"), "Left Index")

    def test_bilateral(self) -> None:
        from finger_rehab.analytics.report import lane_label
        self.assertEqual(lane_label(0, "both"), "Right Index")
        self.assertEqual(lane_label(4, "both"), "Left Index")
        self.assertEqual(lane_label(7, "both"), "Left Pinky")

    def test_mirror_does_not_claim_a_hand(self) -> None:
        # Audit finding #69: mirror always logs the right-hand copy of
        # the finger as its lane, so the generic bilateral label
        # ("Right <finger>", never "Left") reads as a hand asymmetry
        # that is really just a lane-keying convention. mode="mirror"
        # must label the pair, not one hand.
        from finger_rehab.analytics.report import lane_label
        for lane in range(4):
            label = lane_label(lane, "both", mode="mirror")
            self.assertNotIn("Right", label)
            self.assertNotIn("Left", label)
        self.assertEqual(lane_label(0, "both", mode="mirror"),
                          "Index (both hands)")

    def test_per_finger_table_labels_mirror_rows_without_a_hand(
            self) -> None:
        # Drives the real _per_finger_table with a metadata blob whose
        # block_summary.block is "mirror", the same signal the report
        # generation pipeline reads.
        from finger_rehab.analytics.report import _per_finger_table
        meta = {
            "hand": "both",
            "block_summary": {
                "block": "mirror",
                "per_lane": {"0": {"n_trials": 4, "hit_rate": 0.75}},
            },
        }
        html_out = _per_finger_table(meta)
        self.assertIn("Index (both hands)", html_out)
        self.assertNotIn("Right Index", html_out)
        self.assertNotIn("Left Index", html_out)


class ForcePilotPerFingerTableTests(unittest.TestCase):
    """Audit finding #79: the generic per_lane table (RTs, which Force
    Pilot never logs, plus Miss counts from every mode's shared
    log_trial bookkeeping) showed a finger with one Great and one
    rough run as "Trials 1, Hit rate 0.0, Timeout rate 1.0" and
    dropped fingers whose runs were all clean, while the mode's own
    block_summary.force_pilot.per_lane (mae_pct/time_in_corridor/
    press+release MAE) never appeared in report.html at all."""

    def test_force_pilot_table_reads_the_modes_own_per_lane_stats(
            self) -> None:
        from finger_rehab.analytics.report import _per_finger_table
        meta = {
            "hand": "right",
            "block_summary": {
                "block": "force_pilot",
                # Generic per_lane: what the shared engine bookkeeping
                # produces for a Miss-containing lane with no RTs.
                "per_lane": {
                    "2": {"n_trials": 1, "hit_rate": 0.0,
                          "timeout_rate": 1.0},
                },
                "force_pilot": {
                    "per_lane": {
                        "2": {"runs": 2, "mae_pct": 12.5,
                              "time_in_corridor": 0.63,
                              "press_mae_pct": 10.1,
                              "release_mae_pct": 14.9},
                        "3": {"runs": 2, "mae_pct": 4.2,
                              "time_in_corridor": 0.91,
                              "press_mae_pct": 3.8,
                              "release_mae_pct": 4.6},
                    },
                },
            },
        }
        html_out = _per_finger_table(meta)
        self.assertNotIn("Hit rate", html_out)
        self.assertNotIn("Timeout rate", html_out)
        self.assertIn("Right Ring", html_out)
        self.assertIn("Right Pinky", html_out)   # clean-only lane 3
        self.assertIn("12.5", html_out)
        self.assertIn("0.63", html_out)
        self.assertIn("4.2", html_out)

    def test_force_pilot_table_splits_rows_by_corridor_level(
            self) -> None:
        # block_stats keeps a by_level split precisely because pooling
        # runs from different corridor levels misrepresents both; the
        # HTML report used to show only the pooled row, hiding a level
        # change the in-app results screen flags.
        from finger_rehab.analytics.report import _per_finger_table
        meta = {
            "hand": "right",
            "block_summary": {
                "block": "force_pilot",
                "force_pilot": {
                    "per_lane": {
                        "1": {"runs": 4, "mae_pct": 8.0,
                              "time_in_corridor": 0.7,
                              "by_level": {
                                  "1": {"runs": 2, "mae_pct": 11.0,
                                        "time_in_corridor": 0.6},
                                  "2": {"runs": 2, "mae_pct": 5.0,
                                        "time_in_corridor": 0.8},
                              }},
                    },
                },
            },
        }
        html_out = _per_finger_table(meta)
        self.assertIn("<th>Level</th>", html_out)
        self.assertIn("11.0", html_out)
        self.assertIn("5.0", html_out)
        # The pooled 8.0 must not stand alone as if it were one level.
        self.assertEqual(html_out.count("<td>Right Middle</td>"), 2)

    def test_falls_back_to_generic_table_for_old_metadata(self) -> None:
        # Old saves without block_summary.force_pilot.per_lane must
        # still render something rather than an empty table.
        from finger_rehab.analytics.report import _per_finger_table
        meta = {
            "hand": "right",
            "block_summary": {
                "block": "force_pilot",
                "per_lane": {"2": {"n_trials": 1, "hit_rate": 0.0,
                                   "timeout_rate": 1.0}},
            },
        }
        html_out = _per_finger_table(meta)
        self.assertIn("Hit rate", html_out)   # generic fallback table


class OpenSessionFolderTests(unittest.TestCase):
    def _engine(self, root: str | None):
        from finger_rehab.game.engine import GameEngine
        e = GameEngine.__new__(GameEngine)
        e.last_session_root = root
        return e

    def test_opens_existing_folder_mac(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            e = self._engine(td)
            with patch("finger_rehab.game.engine.sys") as m_sys, \
                 patch("finger_rehab.game.engine.subprocess") as m_sub:
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
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.config import Config
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
