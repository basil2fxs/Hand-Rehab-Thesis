"""Regression test for the Force Pilot notebook chapter's level split.

The audit finding this covers: sec_force_tracking's per-finger table
and its within-session learning-curve slope pooled runs across
corridor level (the software side additionally pools across finger
and hand, fixed and pinned separately in test_force_pilot.py). A run
at the easiest level and a run at the hardest level are not the same
measurement, so blending them into one row/slope hides the level
change as if it were tracking quality.

This drives the REAL ForcePilotMode (not a synthetic DataFrame) with
a real TrialLogger writing trials.csv and a real-shaped raw.csv, for
two runs of the SAME finger with a promotion forced in between so the
two runs land at two different corridor levels, then hands that real
session folder to the REAL notebook functions
(build_catalogue / load_games / force_tracking_runs / sec_force_tracking)
and checks the level split survives end to end.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import matplotlib
matplotlib.use("Agg")
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_force_pilot import _engine, _mode, _fresh_profile


class _RealRawLogger:
    """Same on-disk row shape as finger_rehab.data.logger.RawLogger (see its
    RAW_COLUMNS), written synchronously so the test controls exactly
    which sample lands at which t_perf -- no background-thread timing
    to race in a test."""

    def __init__(self, path: Path) -> None:
        from finger_rehab.data.logger import RAW_COLUMNS
        path.parent.mkdir(parents=True, exist_ok=True)
        self._file = path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(RAW_COLUMNS)
        self._idx = 0

    def _pad(self, vals):
        vals = list(vals)
        return vals + [0] * (8 - len(vals))

    def queue_sample(self, t_perf, vals, hand="right") -> None:
        self._idx += 1
        self._writer.writerow([
            "2026-08-10T10:00:00.000", f"{t_perf:.6f}", str(self._idx),
            *[str(v) for v in self._pad(vals)], hand, "", "", ""])

    def queue_event(self, event, lane=None, detail="", t_perf=None,
                    fsr_vals=None, hand="right") -> None:
        self._idx += 1
        self._writer.writerow([
            "2026-08-10T10:00:00.000", f"{(t_perf or 0.0):.6f}",
            str(self._idx), *[str(v) for v in self._pad(fsr_vals or ())],
            hand, event, "" if lane is None else str(lane), detail])

    def close(self) -> None:
        self._file.flush()
        self._file.close()


BASELINE_COUNTS = 100.0
MAX_PRESS_COUNTS = 400.0


def _queue_baseline(raw: _RealRawLogger, finger: int, hand: str,
                    t_end: float, span_s: float = 1.5,
                    step_s: float = 0.01) -> None:
    """Resting samples just before a run, so trial_tare's pre-window
    (t_start - 1.0s to t_start - 0.05s) has something to read as the
    zero-force reference. Independent of simulation causality: raw.csv
    is sorted by t_perf on load, not by write order."""
    t = t_end - span_s
    while t < t_end - 0.03:
        vals = [0.0] * 4
        vals[finger] = BASELINE_COUNTS
        raw.queue_sample(t, vals, hand=hand)
        t += step_s


def _play_run_with_raw(m, raw: _RealRawLogger, finger: int, hand: str,
                       t_start: float, force_fn, dt: float = 1.0 / 60.0):
    from finger_rehab.game.modes.force_pilot import target_pct
    t = t_start
    while m.phase == "run":
        t += dt
        t_run = t - (m.run_t0 or t_start)
        target = target_pct(m.sections, t_run)
        pct = force_fn(t_run, target)
        m.view.pct = pct
        vals = [0.0] * 4
        vals[finger] = BASELINE_COUNTS + (pct / 100.0) * MAX_PRESS_COUNTS
        raw.queue_sample(t, vals, hand=hand)
        m._tick(t)
    return t


def _write_session(root: Path) -> Path:
    """One real Force Pilot game folder: two runs of the same finger,
    forced to promote between them so they land at two different
    corridor levels. Returns the folder path."""
    day_dir = root / "2026-08-10"
    folder = day_dir / "Pat_100000_force_pilot"
    folder.mkdir(parents=True, exist_ok=True)

    from finger_rehab.data.logger import TrialLogger

    e = _engine()
    e.calibration_profiles["right"] = _fresh_profile()
    e.trial_logger = TrialLogger(folder / "trials.csv")
    raw = _RealRawLogger(folder / "raw.csv")
    e.raw_logger = raw

    m = _mode(e)
    m.total_runs = 1000            # never let the block finish here
    finger, hand = 0, "right"

    def perfect(t_run, target):
        return target

    # Pin the scheduler to the same finger throughout, and pre-load
    # one strong "recent" run so the SECOND real run's own strong tic
    # completes a promotion at the close of run 1 (two-strong-runs
    # rule), landing run 2 at level 2.
    m._finger_sched[hand].next = lambda weights=None: finger
    m._recent_tic_by_hf[(hand, finger)] = [0.9]

    t0 = 1000.0
    m._tick(t0)
    assert m.phase == "announce", m.phase
    t = t0 + m.announce_s + 0.01
    m._tick(t)
    assert m.phase == "run", m.phase
    _queue_baseline(raw, finger, hand, m.run_t0)
    t = _play_run_with_raw(m, raw, finger, hand, t, perfect)
    assert m.phase == "feedback", m.phase

    t = m._phase_until + 0.01
    m._tick(t)                                  # feedback -> announce
    assert m.phase == "announce", m.phase
    assert m._level_by_hf[(hand, finger)] == 2, m._level_by_hf
    t = m._phase_until + 0.01
    m._tick(t)                                  # announce -> run
    assert m.phase == "run", m.phase
    assert m.level == 2
    _queue_baseline(raw, finger, hand, m.run_t0)
    _play_run_with_raw(m, raw, finger, hand, t, perfect)

    raw.close()

    meta = {
        "participant": "Pat", "age": "50", "hand": "right",
        "started_at": "2026-08-10T10:00:00",
        "finished_at": "2026-08-10T10:03:00",
        "source_name": "MultiSerialSource",
        "software_version": "1.0.0",
        "block_summary": {"block": "force_pilot", "status": "running",
                          "trials": 2, "force_unit": "sensor units"},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


class ForcePilotNotebookLevelSplitTests(unittest.TestCase):
    def test_per_finger_table_and_slope_split_by_level(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = _write_session(root)
            ra_ns = _load_ra()
            cat = ra_ns.build_catalogue(root=root)
            self.assertEqual(len(cat), 1, cat)
            folders = [Path(p) for p in cat["folder"]]
            trials = ra_ns.load_games(folders, cat)
            runs, dropped = ra_ns.force_tracking_runs(folders, trials)
            self.assertEqual(dropped, 0)
            self.assertEqual(len(runs), 2)
            self.assertEqual(sorted(runs["level"]), [1, 2])
            # Both runs are the same real finger and hand: this is the
            # exact case the audit finding named -- one finger playing
            # at two levels must not get pooled into one row.
            self.assertEqual(runs["finger"].nunique(), 1)
            self.assertEqual(runs["hand"].nunique(), 1)

            buf = io.StringIO()
            import contextlib
            with contextlib.redirect_stdout(buf):
                result = ra_ns.sec_force_tracking(folders, trials)
            out = buf.getvalue()
            self.assertIsNotNone(result)
            # The fixed per-finger table groups by level too, so both
            # levels' rows are visible in the printed table, not
            # collapsed into a single (hand, finger) row.
            self.assertIn("per finger and level", out)
            self.assertIn("learning within session(s), split by",
                          out)


class ForcePilotStoredStatsLevelReprTests(unittest.TestCase):
    """Audit finding #77: the stored-stats table's level_final column
    read (d.get("levels") or {}).get("final"), the OLD single-level
    shape, but block_stats() now returns levels keyed per (hand,
    finger) ({"right:0": {start, final, trace}, ...}), so the column
    printed None for every block."""

    def test_level_final_reads_the_current_per_finger_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = _write_session(root)
            meta_path = folder / "metadata.json"
            meta = json.loads(meta_path.read_text())
            meta["block_summary"]["force_pilot"] = {
                "levels": {"right:0": {"start": 1, "final": 2,
                                       "trace": [1, 2]}},
                "overall": {"mae_pct": 3.2, "time_in_corridor": 0.81},
                "visual_gain": 1.0,
            }
            meta_path.write_text(json.dumps(meta))

            ra_ns = _load_ra()
            cat = ra_ns.build_catalogue(root=root)
            folders = [Path(p) for p in cat["folder"]]
            trials = ra_ns.load_games(folders, cat)
            metas = ra_ns.load_metas(folders)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                ra_ns.sec_force_tracking(folders, trials, metas)
            out = buf.getvalue()
            self.assertIn("what each block stored about itself", out)
            self.assertNotIn("level_final           None", out)
            self.assertIn("right:0:2", out)


class ForcePilotDemoFlagTests(unittest.TestCase):
    """Audit finding #82: force_tracking_runs pooled every corridor
    row regardless of the demo (supervisor Test Mode) flag, which
    block_stats stores precisely as block_summary.force_pilot.demo,
    so a compressed Test Mode block entered the per-finger tables and
    the learning slopes indistinguishably from patient runs."""

    def test_demo_flag_readable_from_metas_and_excluded_from_chapter(
            self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            folder = _write_session(root)
            meta_path = folder / "metadata.json"
            meta = json.loads(meta_path.read_text())
            meta["block_summary"]["force_pilot"] = {
                "levels": {"right:0": {"start": 1, "final": 2,
                                       "trace": [1, 2]}},
                "overall": {"mae_pct": 3.2, "time_in_corridor": 0.81},
                "demo": True,
            }
            meta_path.write_text(json.dumps(meta))

            ra_ns = _load_ra()
            cat = ra_ns.build_catalogue(root=root)
            folders = [Path(p) for p in cat["folder"]]
            trials = ra_ns.load_games(folders, cat)
            metas = ra_ns.load_metas(folders)

            runs, _dropped = ra_ns.force_tracking_runs(
                folders, trials, metas)
            self.assertIn("demo", runs.columns)
            self.assertTrue(runs["demo"].all())

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = ra_ns.sec_force_tracking(folders, trials, metas)
            out = buf.getvalue()
            self.assertIsNone(result)
            self.assertIn("demo", out.lower())

    def test_no_metas_falls_back_to_the_scored_duration_tell(self):
        # Old call sites / old metadata without the demo flag: the
        # short-duration fallback still separates a demo run (~14 s)
        # from real play (23 to 30 s) rather than losing the split.
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root)
            ra_ns = _load_ra()
            cat = ra_ns.build_catalogue(root=root)
            folders = [Path(p) for p in cat["folder"]]
            trials = ra_ns.load_games(folders, cat)
            runs, _dropped = ra_ns.force_tracking_runs(folders, trials)
            self.assertIn("demo", runs.columns)
            # These runs are real 20-30 s tracking runs (the shared
            # test session, not a Test Mode block), so the fallback
            # must not flag them as demo.
            self.assertFalse(runs["demo"].any())


class ForcePilotRampSegmentationTests(unittest.TestCase):
    """Audit finding #83: the brief names step count and pause
    duration on slow ramps (Naik 2011's segmentation measures, a
    reliable PD discriminator per the cluster notes) as deliverable
    metrics; the chapter computed none of them."""

    def test_ramp_segmentation_counts_plateaus_not_a_clean_ramp(self):
        ra_ns = _load_ra()
        fs = 200.0
        t = np.arange(0, 2.3, 1.0 / fs)
        pct = np.zeros_like(t)
        # ramp 0->10 over 1s, flat pause 0.3s, ramp 10->20 over 1s.
        for a, b, p0, p1 in ((0.0, 1.0, 0.0, 10.0),
                             (1.0, 1.3, 10.0, 10.0),
                             (1.3, 2.3, 10.0, 20.0)):
            m = (t >= a) & (t < b)
            pct[m] = p0 if p1 == p0 else p0 + (p1 - p0) * (t[m] - a) / (
                b - a)
        out = ra_ns.ramp_segmentation(t, pct, [("ramp_up", 0.0, 2.3)])
        self.assertEqual(out["ramp_up"]["steps"], 1)
        self.assertAlmostEqual(out["ramp_up"]["mean_pause_s"], 0.3,
                               delta=0.02)

        t2 = np.arange(0, 2.0, 1.0 / fs)
        pct2 = 10.0 * t2
        clean = ra_ns.ramp_segmentation(t2, pct2, [("ramp_up", 0.0, 2.0)])
        self.assertEqual(clean["ramp_up"]["steps"], 0)

    def test_force_tracking_runs_carries_step_and_pause_columns(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _write_session(root)
            ra_ns = _load_ra()
            cat = ra_ns.build_catalogue(root=root)
            folders = [Path(p) for p in cat["folder"]]
            trials = ra_ns.load_games(folders, cat)
            runs, _dropped = ra_ns.force_tracking_runs(folders, trials)
            for col in ("ramp_rate_pct_s", "ramp_up_steps",
                        "ramp_up_pause_s", "release_steps",
                        "release_pause_s"):
                self.assertIn(col, runs.columns)


def _load_ra():
    """Build the same namespace test_rehab_analysis.py's `ra` fixture
    builds (exec every notebook cell's definitions into one module),
    standalone: this file's tests are unittest.TestCase, which cannot
    request a pytest fixture directly."""
    from types import SimpleNamespace
    from tests.test_rehab_analysis import _code_cells, _definitions, \
        FUTURE_FLAGS, MODULE_NAME
    from types import ModuleType
    name = MODULE_NAME + "_standalone"
    cells = _code_cells()
    module = ModuleType(name)
    module.__file__ = str(ROOT / "analysis" / "session_analysis.ipynb")
    sys.modules[name] = module
    ns = module.__dict__
    try:
        for index, lines in cells:
            source = _definitions(index, lines)
            code = compile(source, f"session_analysis.ipynb cell {index}",
                           "exec", flags=FUTURE_FLAGS, dont_inherit=True)
            exec(code, ns)
    finally:
        sys.modules.pop(name, None)
    import tempfile
    ns["FIGDIR"] = Path(tempfile.mkdtemp())
    return SimpleNamespace(**{k: v for k, v in ns.items()
                             if not k.startswith("__")})


if __name__ == "__main__":
    unittest.main()
