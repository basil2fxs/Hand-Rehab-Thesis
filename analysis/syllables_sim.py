"""Syllables played through by simulated readers, on every age profile.

No reader with dyslexia has played Syllables. Here the real engine plays
a Syllables block for two simulated readers on each of the five age
profiles: a fluent one, who picks the right part 97 times in 100 at
reading speed, and one who struggles, picking a foil a quarter of the
time and answering later. The block's own summary must tell them apart
on the measures the game reports (first-press accuracy, the staircase
rung it ends on, the time to a correct press) and every profile must run
to its end.

    cd analysis
    python3 syllables_sim.py [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import tempfile
import time as _time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
APP = Path(__file__).resolve().parents[1] / "app"
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))
import measure_battery as mb  # noqa: E402
import simulate_cohort as sc  # noqa: E402

READERS = {"fluent": (0.03, 1.0), "struggling": (0.25, 1.8)}
BANDS = ("6-9", "10-12", "13-15", "16+", "60+")


class Reader(sc.CohortParticipant):
    error_rate = 0.03
    slow = 1.0

    def syllable_error_rate(self) -> float:
        return self.error_rate

    def syllable_delay(self, m) -> float:
        return self._rt() * self.slow


def one_block(band: str, reader: str, seed: int, root: Path) -> dict:
    truth = dict(sorted(sc.make_truth(1, 2026).items())[0][1])
    code = f"S{seed:02d}"
    real = _time.perf_counter
    clock = mb.SimClock(real())
    _time.perf_counter = lambda: clock.t
    try:
        rig = mb.FakeRig()
        hand = mb.HandModel(rng=random.Random(seed))
        who = Reader(hand, random.Random(seed + 1), truth, 0)
        who.error_rate, who.slow = READERS[reader]
        eng = sc.build_engine(code, truth, root / code, rig)
        eng.cfg.data.setdefault("syllables", {})["age_band"] = band
        eng.begin_syllables_block()
        mb.run_block(eng, rig, hand, who, clock, 60.0, 1800.0)
        s = dict((eng.session.block_summary or {}).get("syllables") or {})
        status = (eng.session.block_summary or {}).get("status")
    finally:
        _time.perf_counter = real
    return {"band": band, "reader": reader, "status": status,
            "n_sets": s.get("n_sets"), "first_press_accuracy": s.get("first_press_accuracy"),
            "rung_final": s.get("rung_final"), "mean_rt_correct_ms": s.get("mean_rt_correct_ms"),
            "words_completed": s.get("words_completed"), "words_attempted": s.get("words_attempted"),
            "confusion_by_kind": s.get("confusion_by_kind")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    out = []
    with tempfile.TemporaryDirectory() as td:
        for k, band in enumerate(BANDS):
            for j, reader in enumerate(READERS):
                r = one_block(band, reader, 10 * k + j, Path(td))
                out.append(r)
                print(f"{band:6s} {reader:10s} {r['status']}: {r['n_sets']} sets, first-press accuracy "
                      f"{r['first_press_accuracy']}, rung {r['rung_final']}, correct in "
                      f"{r['mean_rt_correct_ms']} ms, {r['words_completed']} of {r['words_attempted']} words")
    if args.json:
        args.json.write_text(json.dumps(out, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
