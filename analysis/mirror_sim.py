"""Mirror and the hand comparison on two simulated boards.

Mirror needs a board on each hand, and the study had one, so the mode and
the measures between the hands (OC2, OC3) were built and unit-tested but
never played. Here the real engine plays a Mirror block on a rig of two
simulated boards, driven by the cohort simulation's players
(app/scripts/simulate_cohort.py), each given a hand that leads by a known
gap and an other hand that presses with a known share of the force, as
an affected hand might. The block's own summary must give the pairs, the
gap and the leading hand back, its asymmetry index the force share, and
the two hands' force streams their correlation.

    cd analysis
    python3 mirror_sim.py [--players 8] [--json out.json]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import tempfile
from pathlib import Path

import numpy as np

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
import measure_battery as mb  # noqa: E402
import simulate_cohort as sc  # noqa: E402
from finger_rehab.analytics.metrics import inter_hand_correlation  # noqa: E402


class TwoBoardRig(mb.FakeRig):
    """Two boards, right and left, as discovery assigns them."""
    name = "SimulatedTwoBoardRig"

    def __init__(self) -> None:
        super().__init__()
        from types import SimpleNamespace
        self.hands = [SimpleNamespace(hand="right", port="/dev/sim0"),
                      SimpleNamespace(hand="left", port="/dev/sim1")]

    @property
    def hand_modes_available(self) -> set[str]:
        return {"right", "left", "both"}


class WeakerLeft(mb.HandModel):
    """The left hand presses with `share` of the right hand's force."""
    share: float = 1.0

    def sample(self, now: float) -> tuple[int, ...]:
        vals = list(super().sample(now))
        for lane in range(4, 8):
            if self.press_until.get(lane, 0.0) > now:
                vals[lane] = int(round(mb.RESTING + self.share * mb.PRESS_COUNTS))
        return tuple(vals)


def streams(folder: Path) -> tuple[np.ndarray, np.ndarray]:
    """Each hand's summed force over its four pads, sample by sample."""
    right, left = [], []
    with (folder / "raw.csv").open(encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            if r.get("event") or not r.get("sample_idx"):
                continue
            try:
                vals = [float(r[f"fsr{k}"]) for k in range(1, 9)]
            except (KeyError, TypeError, ValueError):
                continue
            right.append(sum(vals[0:4]))
            left.append(sum(vals[4:8]))
    return np.array(right), np.array(left)


def one_player(code: str, truth: dict, lead_s: float, share: float, seed: int, root: Path) -> dict:
    data_dir = root / code
    rig = TwoBoardRig()
    hand = WeakerLeft(rng=random.Random(seed))
    hand.share = share
    sc.MIRROR_LEAD_S = lead_s
    who = sc.CohortParticipant(hand, random.Random(seed + 1), truth, 0)
    # the engine reads time.perf_counter, so it runs on the simulated
    # clock, as the battery simulation runs it
    import time as _time
    real_perf = _time.perf_counter
    clock = mb.SimClock(real_perf())
    _time.perf_counter = lambda: clock.t
    eng = sc.build_engine(code, truth, data_dir, rig)
    try:
        eng.hand_mode = "both"
        eng._build_detectors()
        eng.begin_mirror_block()
        mb.run_block(eng, rig, hand, who, clock, 120.0, 900.0)
        summary = dict(eng.session.block_summary or {})
        folders = sorted(data_dir.rglob("raw.csv"))
        folder = folders[-1].parent if folders else data_dir
    finally:
        _time.perf_counter = real_perf
    m = summary.get("mirror") or {}
    right, left = streams(folder)
    return {"code": code, "dominant": truth["dominant"], "lead_planted_ms": lead_s * 1000.0,
            "share_planted": share, "trials": summary.get("trials"),
            "median_gap_ms": m.get("median_gap_ms"),
            "right_leads_by_ms": (None if m.get("left_hand_mean_rt_ms") is None
                                  or m.get("right_hand_mean_rt_ms") is None
                                  else m["left_hand_mean_rt_ms"] - m["right_hand_mean_rt_ms"]),
            "asymmetry_peak_force": (summary.get("asymmetry_index") or {}).get("peak_force"),
            "inter_hand_r": inter_hand_correlation(list(left), list(right)) if len(right) else None,
            "mirror": {k: v for k, v in m.items() if not isinstance(v, (list, dict))}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--players", type=int, default=8)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    truth = sc.make_truth(args.players, 2026)
    rng = random.Random(11)
    out = []
    with tempfile.TemporaryDirectory() as td:
        for k, (code, t) in enumerate(sorted(truth.items())):
            lead = rng.choice([0.010, 0.020, 0.030, 0.040])
            share = rng.choice([1.0, 0.8, 0.6])
            out.append(one_player(code, t, lead, share, 100 + k, Path(td)))
            r = out[-1]
            print(f"{code}: {r['dominant']}-handed, lead {r['lead_planted_ms']:.0f} ms, left share {share}: "
                  f"{r['trials']} trials, median gap {r['median_gap_ms']}, right leads by {r['right_leads_by_ms']}, "
                  f"peak-force asymmetry {r['asymmetry_peak_force']}, r {r['inter_hand_r']}")
    if args.json:
        args.json.write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
