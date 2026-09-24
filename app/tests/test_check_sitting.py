"""scripts/check_sitting.py is what the RA runs before a participant
leaves: a complete sitting reads READY, and each way a sitting can go
wrong on the day (a step never finished, Test Mode left on, a short
Force Pilot, a cut rest, a board drop, a blank intake field) reads
CHECK with what to do."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

ORDER_A = ["reaction", "rhythm", "echo", "force_pilot", "chords",
           "buzz_hunt", "pattern", "adaptive", "syllables",
           "reaction", "force_pilot", "chords"]
COUNTS = {"reaction": 20, "chords": 40, "pattern": 296, "rhythm": 107,
          "echo": 20, "buzz_hunt": 20, "adaptive": 40, "syllables": 25}


def write_sitting(root: Path, code: str = "P01", skip=(), test_mode=(),
                  fp_runs=12, rest_s=181.0, drops=0, sex="female",
                  measured=True):
    day = root / "2026-10-20"
    for pos, mode in enumerate(ORDER_A, start=1):
        if pos in skip:
            continue
        g = day / f"{code}_{9 + pos:02d}0000_{mode}"
        g.mkdir(parents=True)
        (g / "trials.csv").write_text("h\n1\n")
        (g / "raw.csv").write_text("h\n1\n")
        bs = {"status": "completed", "trials": COUNTS.get(mode, 12),
              "connection": {"drops": drops if pos == 2 else 0},
              "stim_cue_failures": 0}
        if mode == "force_pilot":
            bs["force_pilot"] = {"runs": fp_runs}
        bat = {"id": "healthy_one_hand_v2", "position": pos,
               "phase": "pass2" if pos >= 10 else "pass1"}
        if pos == 10:
            bat["rest_before_s"] = rest_s
        meta = {"participant": code, "hand": "right",
                "dominant_hand": "left", "age": "22", "sex": sex,
                "hand_length_mm": "184", "hand_breadth_mm": "81",
                "started_at": f"2026-10-20T{9 + pos:02d}:00:00",
                "finished_at": f"2026-10-20T{9 + pos:02d}:02:00",
                "calibration": {"created_at": "2026-10-20T09:55:00"},
                "config_snapshot": {"game": {
                    "test_mode_enabled": pos in test_mode},
                    "latency": {"measured": measured,
                                "measured_on": "2026-10-19"},
                    "rhythm": {"audio_offset_ms": 87}},
                "battery": bat, "block_summary": bs}
        (g / "metadata.json").write_text(json.dumps(meta))


class CheckSittingTests(unittest.TestCase):

    def _check(self, **kw):
        import check_sitting as cs
        with tempfile.TemporaryDirectory() as td:
            write_sitting(Path(td), **kw)
            rows = cs.games(Path(td), None)
            return cs.check_code("P01", rows)

    def _bad(self, result):
        return [line for ok, line in result if not ok]

    def test_a_complete_sitting_passes_except_the_clock(self):
        bad = self._bad(self._check())
        # The synthetic blocks sit an hour apart, so only the clock
        # line can complain.
        self.assertEqual(len(bad), 1, bad)
        self.assertIn("50 min stop", bad[0])

    def test_a_step_never_finished_is_named(self):
        bad = " ".join(self._bad(self._check(skip=(7,))))
        self.assertIn("steps not finished: 7", bad)

    def test_test_mode_short_force_pilot_and_a_cut_rest(self):
        bad = " ".join(self._bad(self._check(test_mode=(1,), fp_runs=3,
                                             rest_s=70.0)))
        self.assertIn("reaction (Test Mode on)", bad)
        self.assertIn("force_pilot (3 of 12 runs)", bad)
        self.assertIn("cut short", bad)

    def test_rhythm_on_estimated_delays_is_flagged(self):
        bad = " ".join(self._bad(self._check(measured=False)))
        self.assertIn("audio_latency.py --write", bad)

    def test_drops_and_a_blank_intake_field(self):
        bad = " ".join(self._bad(self._check(drops=2, sex="")))
        self.assertIn("2 board drop(s)", bad)
        self.assertIn("sex", bad)


if __name__ == "__main__":
    unittest.main()
