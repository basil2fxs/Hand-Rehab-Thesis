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

import csv
import io
import json
import os
import sys
import unittest
from pathlib import Path


os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import matplotlib
matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_force_pilot import _engine, _mode, _fresh_profile


class _RealRawLogger:
    """Same on-disk row shape as rehab.data.logger.RawLogger (see its
    RAW_COLUMNS), written synchronously so the test controls exactly
    which sample lands at which t_perf -- no background-thread timing
    to race in a test."""

    def __init__(self, path: Path) -> None:
        from rehab.data.logger import RAW_COLUMNS
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
    from rehab.game.modes.force_pilot import target_pct
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

    from rehab.data.logger import TrialLogger

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
