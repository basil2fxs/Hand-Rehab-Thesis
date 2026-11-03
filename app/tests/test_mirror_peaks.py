"""Mirror's hand comparison reads each press's whole peak.

The block summary's peak-force asymmetry took each hand's live peak when
the pair completed, when the hand that pressed second had barely passed
its trigger. On two simulated boards, a left hand at 60 percent force,
0.50 by the index, read 0.90 when the right hand led and 0.08 when the
left did (analysis/mirror_sim.py, 3 November 2026). Each hand's peak now
comes from its own release, so both read 0.51.
"""
from __future__ import annotations

import os
import random
import sys
import tempfile
import time as _time
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))

import measure_battery as mb  # noqa: E402
import simulate_cohort as sc  # noqa: E402


class _TwoBoards(mb.FakeRig):
    def __init__(self) -> None:
        super().__init__()
        self.hands = [SimpleNamespace(hand="right", port="/dev/sim0"),
                      SimpleNamespace(hand="left", port="/dev/sim1")]

    @property
    def hand_modes_available(self) -> set[str]:
        return {"right", "left", "both"}


class _WeakLeft(mb.HandModel):
    def sample(self, now: float) -> tuple[int, ...]:
        vals = list(super().sample(now))
        for lane in range(4, 8):
            if self.press_until.get(lane, 0.0) > now:
                vals[lane] = int(round(mb.RESTING + 0.6 * mb.PRESS_COUNTS))
        return tuple(vals)


def _asymmetry(dominant: str) -> float:
    truth = dict(sorted(sc.make_truth(1, 2026).items())[0][1])
    truth["dominant"] = dominant
    real = _time.perf_counter
    clock = mb.SimClock(real())
    _time.perf_counter = lambda: clock.t
    old_lead = sc.MIRROR_LEAD_S
    sc.MIRROR_LEAD_S = 0.040
    try:
        with tempfile.TemporaryDirectory() as td:
            rig, hand = _TwoBoards(), _WeakLeft(rng=random.Random(5))
            who = sc.CohortParticipant(hand, random.Random(6), truth, 0)
            eng = sc.build_engine("P01", truth, Path(td) / "P01", rig)
            eng.hand_mode = "both"
            eng._build_detectors()
            eng.begin_mirror_block()
            mb.run_block(eng, rig, hand, who, clock, 120.0, 900.0)
            return float(eng.session.block_summary["asymmetry_index"]["peak_force"])
    finally:
        _time.perf_counter = real
        sc.MIRROR_LEAD_S = old_lead


class MirrorPeakTests(unittest.TestCase):
    def test_the_asymmetry_is_the_force_share_whichever_hand_leads(self):
        # |L - R| / mean(L, R) for a left hand at 0.6 of the right is 0.5
        for dominant in ("right", "left"):
            self.assertAlmostEqual(_asymmetry(dominant), 0.5, delta=0.05, msg=dominant)
