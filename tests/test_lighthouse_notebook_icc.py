"""Regression test for the Lighthouse notebook chapter's test-retest
ICC scaffold (audit finding #88).

sec_precision_hold's ICC(2,1) block used to build its wide matrix by
grouping holds on (session, finger) alone:

    wide = (holds.groupby(["session", "finger"])["lit_mae"].mean()
            .unstack("session").dropna())

A bilateral participant's left and right hand carry the SAME finger
names (index, middle, ring, little), so that key folds two different
effectors into one row per finger, averaging away exactly the
between-target variance ICC(2,1) is meant to read. This drives two
real bilateral Lighthouse blocks (two "sessions", two days) through
the real GameEngine/LighthouseMode with a real TrialLogger and a real
raw.csv, then hands the real session folders to the real notebook
functions (build_catalogue / load_games / precision_hold_rows /
score_hold / sec_precision_hold), exactly as test_force_pilot_notebook
_levels.py does for the equivalent Force Pilot finding.
"""
from __future__ import annotations

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import matplotlib
matplotlib.use("Agg")
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_force_pilot_notebook_levels import _RealRawLogger
from tests.test_lighthouse import _engine, _fresh_profile, _mode


BASELINE_COUNTS = 100.0
MAX_PRESS_COUNTS = 400.0


def _write_session(root: Path, day: str, right_noise: float,
                   left_noise: float) -> Path:
    """One real bilateral Lighthouse game folder: one right-hand index
    hold and one left-hand index hold, each held steady around its own
    noise level (a fixed offset from target through the hold, so the
    scored lit MAE lands near that noise). Real GameEngine, real
    LighthouseMode, real TrialLogger, real raw.csv -- the notebook
    reads this off disk exactly as it would a patient's session."""
    from rehab.data.logger import TrialLogger

    folder = root / day / "Pat_100000_lighthouse"
    folder.mkdir(parents=True, exist_ok=True)

    e = _engine(hand_mode="both")
    e.calibration_profiles["right"] = _fresh_profile("right")
    e.calibration_profiles["left"] = _fresh_profile("left")
    e.trial_logger = TrialLogger(folder / "trials.csv")
    raw = _RealRawLogger(folder / "raw.csv")
    e.raw_logger = raw
    e.finish_block = lambda: None

    # Level 1 (fully lit, no dark windows) keeps this to the plain lit
    # MAE the ICC block reads; short timings so the test runs fast.
    m = _mode(e, hands={"right": [0, 1, 2, 3], "left": [4, 5, 6, 7]},
              holds_per_finger=1, echoes_per_finger=0, level=1,
              hold_s=2.0, ignite_hold_s=0.1, ignite_timeout_s=5.0,
              announce_s=0.3, rest_s=0.1,
              lit_lead_s=0.2, lit_gap_s=0.1, lit_tail_s=0.2)
    order = iter([("right", 0), ("left", 4)])
    m._hold_sched.next = lambda: next(order)
    m._kind_bag = ["hold", "hold"]
    m.total_trials = 2

    noise_by_lane = {0: right_noise, 4: left_noise}

    def sample_now(t: float) -> None:
        vals = [BASELINE_COUNTS, 0.0, 0.0, 0.0,
                BASELINE_COUNTS, 0.0, 0.0, 0.0]
        if m.phase == "trial" and m.kind == "hold":
            if m.sub == "ignite" or m.hold_t0 is None:
                pct = m.target_pct
            else:
                pct = m.target_pct + noise_by_lane.get(m.lane, 0.0)
            m.view.pct = pct
            counts = BASELINE_COUNTS + (pct / 100.0) * MAX_PRESS_COUNTS
            vals[0 if m.lane == 0 else 4] = counts
        raw.queue_sample(t, vals, hand="both")

    # A resting lead-in so trial_tare's pre-window (1.0s before the
    # first ignite) has samples to tare from.
    t = 998.5
    while t < 1000.0:
        raw.queue_sample(t, [BASELINE_COUNTS, 0, 0, 0,
                             BASELINE_COUNTS, 0, 0, 0], hand="both")
        t += 0.01

    t = 1000.0
    m._tick(t)
    while m.phase != "done":
        t += 1.0 / 60.0
        sample_now(t)
        m._tick(t)

    raw.close()
    e.trial_logger.close()

    meta = {
        "participant": "Pat", "age": "50", "hand": "both",
        "started_at": f"{day}T10:00:00",
        "finished_at": f"{day}T10:03:00",
        "source_name": "MultiSerialSource",
        "software_version": "1.0.0",
        "block_summary": {"block": "lighthouse", "status": "completed",
                          "trials": 2},
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


def _load_ra():
    """Same pattern as test_force_pilot_notebook_levels.py's _load_ra:
    exec every notebook cell's definitions into one standalone module
    namespace, for a unittest.TestCase (which cannot request a pytest
    fixture directly)."""
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_lighthouse_icc"
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
    ns["FIGDIR"] = Path(tempfile.mkdtemp())
    return SimpleNamespace(**{k: v for k, v in ns.items()
                             if not k.startswith("__")})


class LighthouseICCHandFingerTests(unittest.TestCase):
    def test_icc_targets_are_hand_finger_pairs_not_finger_alone(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            # Same noise level per hand on both days: a real
            # test-retest participant whose right index is steady and
            # left index is noisy on both recordings.
            _write_session(root, "2026-08-10", right_noise=0.5,
                           left_noise=8.0)
            _write_session(root, "2026-08-11", right_noise=0.7,
                           left_noise=8.5)

            ra_ns = _load_ra()
            cat = ra_ns.build_catalogue(root=root)
            self.assertEqual(cat["session"].nunique(), 2, cat)
            folders = [Path(p) for p in cat["folder"]]
            trials = ra_ns.load_games(folders, cat)

            hold_rows, _echo_rows = ra_ns.precision_hold_rows(trials)
            holds = pd.DataFrame(
                [h for h in (ra_ns.score_hold(r)
                             for _i, r in hold_rows.iterrows())
                 if h is not None])
            self.assertEqual(len(holds), 4, holds)  # 2 sessions x 2 hands
            self.assertEqual(set(holds["hand"]), {"right", "left"})

            # The fixed grouping: two hand-finger targets, each with
            # its own session-to-session pair.
            wide_fixed = (holds.groupby(["session", "hand", "finger"])
                         ["lit_mae"].mean().unstack("session").dropna())
            self.assertEqual(wide_fixed.shape, (2, 2))

            # The bug this closes: grouping on finger alone collapses
            # both hands' index finger into one row, which is what a
            # bilateral participant's real data used to do.
            wide_buggy = (holds.groupby(["session", "finger"])
                         ["lit_mae"].mean().unstack("session").dropna())
            self.assertEqual(wide_buggy.shape, (1, 2))

            # The deployed notebook code must match the fixed shape,
            # not the buggy one: run the real chapter end to end (real
            # raw.csv on disk, no monkeypatching) and confirm it does
            # not crash and reports the two real sessions.
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                result = ra_ns.sec_precision_hold(folders, trials)
            out = buf.getvalue()
            self.assertIsNotNone(result)
            self.assertIn("test-retest ICC(2,1)", out)
            self.assertIn("across 2 sessions", out)
            # Tie the printed number to the fixed grouping specifically:
            # if the deployed cell ever regresses to the buggy
            # (session, finger) key, this recomputes what it WOULD have
            # printed and the two diverge (the buggy matrix pools a
            # steady and a noisy finger into the same row).
            printed = float(out.rsplit(":", 1)[1].split()[0])
            expected = ra_ns.icc_two_one(wide_fixed.values)
            self.assertAlmostEqual(printed, round(expected, 2), places=2)
            # The buggy (session, finger) grouping collapses to ONE
            # row here, which icc_two_one refuses to score at all
            # (it needs at least two targets): the bug did not just
            # bias the number, it made a real ICC impossible to
            # compute from a bilateral participant's own data.
            import math
            self.assertTrue(math.isnan(ra_ns.icc_two_one(wide_buggy.values)))


if __name__ == "__main__":
    unittest.main()
