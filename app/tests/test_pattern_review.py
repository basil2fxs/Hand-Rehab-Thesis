"""Muscle Memory (pattern) faults from the 27 September 2026 code
review, each reproduced before it was fixed.

A trial that timed out while the board was away counted as a miss in
the take's accuracy, the stars and the fatigue guard (one drop forced
a rest, a second ended the block), and the notebook's take table
counted it too. Every block run without a sequence file was labelled
builtin_fallback with an error, and the notebook warned about each.
Use built-in riff was undone by the next menu screen whenever the
file had come through the drop folder.
"""
from __future__ import annotations

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_pattern_mode import _build_mode, _press, _seg_index  # noqa: E402
from tests.test_pattern_file import GOOD, _Cfg  # noqa: E402


class DropVoidTests(unittest.TestCase):

    def _drop_engine_mode(self, overlaps):
        engine, mode = _build_mode(fatigue_timeout_run=2)
        engine._drop_overlaps = lambda hand, t_from, t_to: overlaps
        mode._seg_idx = _seg_index(mode, "seq")
        mode._trial_in_seg = 0
        return engine, mode

    def test_a_timeout_during_a_drop_is_voided(self):
        engine, mode = self._drop_engine_mode(True)
        seg = mode.segments[mode._seg_idx]
        mode._fire(now=10.0)
        mode._close(None, 12.5)
        self.assertEqual(seg.n_done, 0)
        self.assertEqual(seg.n_voided, 1)
        self.assertEqual(mode._trials, [])
        self.assertEqual(mode._timeout_run, 0)
        kw = engine.log_trial.call_args.kwargs
        self.assertEqual(kw["error_type"], "device_drop")
        self.assertEqual(mode._trial_in_seg, 1)

    def test_a_plain_timeout_still_counts(self):
        engine, mode = self._drop_engine_mode(False)
        seg = mode.segments[mode._seg_idx]
        mode._fire(now=10.0)
        mode._close(None, 12.5)
        self.assertEqual(seg.n_done, 1)
        self.assertEqual(seg.n_voided, 0)
        self.assertEqual(mode._timeout_run, 1)
        self.assertIsNone(engine.log_trial.call_args.kwargs["error_type"])

    def test_voided_trials_do_not_trip_the_fatigue_guard(self):
        engine, mode = self._drop_engine_mode(True)
        for i in range(4):
            mode._fire(now=10.0 + 3.0 * i)
            mode._close(None, 12.5 + 3.0 * i)
        self.assertEqual(mode._fatigue_triggers, 0)
        self.assertNotEqual(mode.phase, "rest")

    def test_the_take_summary_reports_the_voided_count(self):
        engine, mode = self._drop_engine_mode(True)
        mode._fire(now=10.0)
        mode._close(None, 12.5)
        engine._drop_overlaps = lambda hand, t_from, t_to: False
        mode._fire(now=13.0)
        mode._handle_press(_press(lane=mode.active.lane, t=13.3), now=13.3)
        st = mode._segment_rt_stats(mode._seg_idx)
        self.assertEqual(st["n"], 1)
        self.assertEqual(st["n_voided"], 1)
        self.assertEqual(st["accuracy"], 1.0)


class MaterialLabelTests(unittest.TestCase):

    def test_no_file_reads_generated_through_the_engine(self):
        import pygame
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from tests.test_rhythm_tactile import _fake_source
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                cfg = Config.load()
                cfg.data["ui"]["resolution"] = [640, 480]
                cfg.data["audio"]["enabled"] = False
                cfg.data["session"]["data_dir"] = td
                cfg.data["report"] = {"enabled": False}
                cfg.data["eeg"] = {"enabled": False}
                cfg.data["game"]["start_countdown_s"] = 0
                cfg.data.setdefault("pattern", {})
                cfg.data["pattern"]["sequence_file"] = str(
                    Path(td) / "pattern_sequence.yaml")
                cfg.data["pattern"]["sequence_pointer"] = str(
                    Path(td) / "pattern_sequence.json")
                cfg.data["pattern"]["sequence_drop_dir"] = str(
                    Path(td) / "pattern_sequences")
                source, _board = _fake_source()
                eng = GameEngine(cfg, source)
                eng.audio = None
                from unittest.mock import MagicMock
                eng._screens = {"gameplay": MagicMock(lanes=[]),
                                "pattern": MagicMock(lanes=[]),
                                "results": MagicMock()}
                eng.begin_pattern_block()
                mode = eng.mode
                self.assertIsNone(mode.sequence_file_error)
                self.assertEqual(mode.block_material(), "generated")
                self.assertEqual(mode.block_stats()["material"], "generated")
        finally:
            pygame.quit()


class ClearTests(unittest.TestCase):

    def test_clear_is_not_undone_by_the_drop_folder_sync(self):
        from finger_rehab.data import pattern_file as pf
        with tempfile.TemporaryDirectory() as td:
            cfg = _Cfg(Path(td))
            drop = pf.drop_dir(cfg)
            drop.mkdir(parents=True)
            (drop / pf.DROP_NAME).write_text(GOOD)
            res = pf.sync_drop_folder(cfg)
            self.assertTrue(res is not None and res.ok)
            self.assertTrue(pf.active_path(cfg).exists())
            pf.clear_active(cfg)
            self.assertFalse(pf.active_path(cfg).exists())
            self.assertIsNone(pf.sync_drop_folder(cfg))
            self.assertFalse(pf.active_path(cfg).exists())
            plan, reason = pf.load_active_plan(cfg)
            self.assertIsNone(plan)
            # A changed file is a new file and imports again.
            (drop / pf.DROP_NAME).write_text(GOOD.replace("Test riff",
                                                          "Other riff"))
            res = pf.sync_drop_folder(cfg)
            self.assertTrue(res is not None and res.ok)
            plan, _reason = pf.load_active_plan(cfg)
            self.assertEqual(plan.name, "Other riff")


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_the_take_table_leaves_voided_trials_out(self):
        import pandas as pd
        rows = []
        for i in range(12):
            rows.append(dict(mode="pattern", game="g1", session="s1",
                             trial=i + 1, stimulus="seq;b=2;soc=trained;pos="
                             + str(i), early_late="Good",
                             time_difference_ms=400.0 + i, error_type="",
                             pattern_trial=True))
        for i in range(3):
            rows.append(dict(mode="pattern", game="g1", session="s1",
                             trial=13 + i, stimulus="seq;b=2;soc=trained;pos="
                             + str(i), early_late="Miss",
                             time_difference_ms=None,
                             error_type="device_drop", pattern_trial=True))
        t = self.ra.pattern_take_table(pd.DataFrame(rows))
        self.assertEqual(len(t), 1)
        self.assertEqual(int(t.iloc[0]["n"]), 12)
        self.assertEqual(float(t.iloc[0]["accuracy"]), 1.0)

    def test_an_absent_file_is_not_a_fallback_warning(self):
        stored = {"g1": {"material": "builtin_fallback",
                         "sequence_file_error": "no sequence file loaded"},
                  "g2": {"material": "builtin_fallback",
                         "sequence_file_error": "riff.yaml is not valid: x"}}
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.ra._pattern_schedule_readout(stored)
        out = buf.getvalue()
        self.assertEqual(out.count("FELL BACK"), 1)
        self.assertIn("g2", out)


if __name__ == "__main__":
    unittest.main()
