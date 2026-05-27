"""L/R dashboard data + screen tests.

The dashboard is the Thread C deliverable that lets a therapist see
asymmetric recovery (the affected hand catching up to the
unaffected one). Pure data layer lives in
rehab/analytics/dashboard.py - I test that against hand-crafted
JSON fixtures here. The screen itself only gets a smoke test
because rendering correctness is verified by eye via screenshots.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock


sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _write_session(root: Path, ts: str, participant: str,
                    per_lane: dict, hand_mode: str = "both",
                    block: str = "classic",
                    asymmetry: dict | None = None,
                    force_unit: str = "counts") -> Path:
    """Write a minimal session.json that the dashboard loader
    can parse. Layout mirrors what GameEngine.session.save writes
    in the real app, but with only the fields the loader actually
    reads."""
    folder = root / f"{participant}_{ts}"
    folder.mkdir(parents=True, exist_ok=True)
    md = folder / "metadata.json"
    payload = {
        "participant": participant,
        "started_at": ts,
        "hand": hand_mode,
        "block_summary": {
            "block": block,
            "per_lane": per_lane,
            "force_unit": force_unit,
        },
    }
    if asymmetry is not None:
        payload["block_summary"]["asymmetry_index"] = asymmetry
    with md.open("w", encoding="utf-8") as f:
        json.dump(payload, f)
    return md


class AggregateHandTests(unittest.TestCase):
    """_aggregate_hand pools the per_lane rows for one hand into a
    weighted-mean summary."""

    def test_two_lanes_pooled_by_n_trials(self) -> None:
        # Right hand: lane 0 (5 trials, RT 200) and lane 1 (15 trials,
        # RT 300). Weighted mean RT = (5*200 + 15*300) / 20 = 275.
        from rehab.analytics.dashboard import _aggregate_hand
        per_lane = {
            "0": {"n_trials": 5,  "rt_mean_ms": 200.0,
                   "peak_force_mean": 10.0, "hit_rate": 0.8},
            "1": {"n_trials": 15, "rt_mean_ms": 300.0,
                   "peak_force_mean": 20.0, "hit_rate": 0.6},
        }
        s = _aggregate_hand(per_lane, range(0, 4))
        self.assertEqual(s.n_trials, 20)
        self.assertAlmostEqual(s.rt_mean_ms, 275.0)
        # Hit rate weighted: (0.8 * 5 + 0.6 * 15) / 20 = 0.65.
        self.assertAlmostEqual(s.hit_rate, 0.65, places=4)
        # Force weighted: (10 * 5 + 20 * 15) / 20 = 17.5.
        self.assertAlmostEqual(s.peak_force_mean, 17.5)

    def test_empty_range_returns_none_fields(self) -> None:
        from rehab.analytics.dashboard import _aggregate_hand
        s = _aggregate_hand({}, range(4, 8))
        self.assertEqual(s.n_trials, 0)
        self.assertIsNone(s.hit_rate)
        self.assertIsNone(s.rt_mean_ms)
        self.assertIsNone(s.peak_force_mean)


class LoadRecentSessionsTests(unittest.TestCase):

    def test_returns_empty_for_nonexistent_dir(self) -> None:
        from rehab.analytics.dashboard import load_recent_sessions
        rows = load_recent_sessions(Path("/nonexistent/path"))
        self.assertEqual(rows, [])

    def test_parses_subfolder_metadata_json(self) -> None:
        from rehab.analytics.dashboard import load_recent_sessions
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root, "2026-05-27T10:00:00", "Basil",
                            per_lane={
                                "0": {"n_trials": 10, "rt_mean_ms": 200.0,
                                       "hit_rate": 0.9,
                                       "peak_force_mean": 15.0},
                                "4": {"n_trials": 10, "rt_mean_ms": 250.0,
                                       "hit_rate": 0.7,
                                       "peak_force_mean": 12.0},
                            },
                            asymmetry={"peak_force": 0.22, "rt_mean": 0.18})
            rows = load_recent_sessions(root, limit=10)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row.participant, "Basil")
            self.assertEqual(row.hand_mode, "both")
            self.assertAlmostEqual(row.right.hit_rate, 0.9)
            self.assertAlmostEqual(row.left.hit_rate, 0.7)
            self.assertAlmostEqual(row.asymmetry_index_force, 0.22)

    def test_orders_oldest_first(self) -> None:
        from rehab.analytics.dashboard import load_recent_sessions
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root, "2026-05-27T09:00:00", "P",
                            per_lane={"0": {"n_trials": 1}})
            _write_session(root, "2026-05-27T10:00:00", "P",
                            per_lane={"0": {"n_trials": 1}})
            _write_session(root, "2026-05-27T11:00:00", "P",
                            per_lane={"0": {"n_trials": 1}})
            rows = load_recent_sessions(root, limit=10)
            self.assertEqual(
                [r.started_at for r in rows],
                ["2026-05-27T09:00:00",
                 "2026-05-27T10:00:00",
                 "2026-05-27T11:00:00"],
            )

    def test_limit_keeps_only_recent_n(self) -> None:
        from rehab.analytics.dashboard import load_recent_sessions
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for h in range(5):
                _write_session(root,
                                f"2026-05-27T{h:02d}:00:00",
                                "P",
                                per_lane={"0": {"n_trials": 1}})
            rows = load_recent_sessions(root, limit=3)
            # Three newest: 02, 03, 04.
            self.assertEqual(
                [r.started_at for r in rows],
                ["2026-05-27T02:00:00",
                 "2026-05-27T03:00:00",
                 "2026-05-27T04:00:00"],
            )

    def test_participant_filter(self) -> None:
        from rehab.analytics.dashboard import load_recent_sessions
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root, "2026-05-27T10:00:00", "Basil",
                            per_lane={"0": {"n_trials": 1}})
            _write_session(root, "2026-05-27T11:00:00", "Aiden",
                            per_lane={"0": {"n_trials": 1}})
            rows = load_recent_sessions(root, limit=10,
                                          participant="Basil")
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0].participant, "Basil")

    def test_broken_json_is_skipped_not_fatal(self) -> None:
        # A single malformed file shouldn't break the whole dashboard.
        # The loader logs a warning and moves on.
        from rehab.analytics.dashboard import load_recent_sessions
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bad = root / "bad_session"
            bad.mkdir()
            (bad / "metadata.json").write_text("{not valid json")
            _write_session(root, "2026-05-27T10:00:00", "P",
                            per_lane={"0": {"n_trials": 1}})
            rows = load_recent_sessions(root, limit=10)
            self.assertEqual(len(rows), 1)


class LRDashboardScreenSmokeTests(unittest.TestCase):
    """Render the screen with no sessions + with one session to
    confirm draw() doesn't crash and the empty-state message kicks
    in correctly."""

    def _make_engine(self, sessions_dir: Path):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data.setdefault("session", {})["data_dir"] = str(sessions_dir)
        eng = GameEngine(cfg, KeyboardOnlySource(cfg))
        eng.screen = pygame.display.set_mode(
            (eng.layout.width, eng.layout.height))
        eng._screens = eng._build_screens()
        return eng

    def test_empty_state_does_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng = self._make_engine(Path(td))
            try:
                dash = eng._screens["lr_dashboard"]
                dash.refresh()
                dash.draw(eng.screen)
                self.assertEqual(dash._rows, [])
            finally:
                import pygame
                pygame.quit()

    def test_renders_with_one_session(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root, "2026-05-27T10:00:00", "TestUser",
                            per_lane={
                                "0": {"n_trials": 10, "rt_mean_ms": 200.0,
                                       "hit_rate": 0.8,
                                       "peak_force_mean": 15.0},
                                "4": {"n_trials": 10, "rt_mean_ms": 240.0,
                                       "hit_rate": 0.6,
                                       "peak_force_mean": 12.0},
                            },
                            asymmetry={"peak_force": 0.22,
                                         "rt_mean": 0.18})
            eng = self._make_engine(root)
            try:
                eng.session.participant = "TestUser"
                dash = eng._screens["lr_dashboard"]
                dash.refresh()
                self.assertEqual(len(dash._rows), 1)
                dash.draw(eng.screen)
            finally:
                import pygame
                pygame.quit()


if __name__ == "__main__":
    unittest.main()
