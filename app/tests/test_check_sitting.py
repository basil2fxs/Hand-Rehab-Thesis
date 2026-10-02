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
           "buzz_hunt", "pattern", "adaptive",
           "reaction", "rhythm", "force_pilot", "chords"]
COUNTS = {"reaction": 20, "chords": 40, "pattern": 296, "rhythm": 107,
          "echo": 20, "buzz_hunt": 20, "adaptive": 40}
# The 15 minute length of 28 September to 1 October 2026: three
# shortened games, twice (family short). Kept so a sitting from then
# still checks against itself.
ORDER_15 = ["reaction", "chords", "force_pilot",
            "reaction", "chords", "force_pilot"]
COUNTS_SHORT = {"reaction": 12, "chords": 20}
# The 15 since 2 October 2026: the core games once, full length.
ORDER_15_FULL = ["reaction", "force_pilot", "chords", "adaptive"]


def write_sitting(root: Path, code: str = "P01", skip=(), test_mode=(),
                  fp_runs=12, rest_s=181.0, drops=0, sex="female",
                  measured=True, order=ORDER_A, counts=COUNTS,
                  family="full", preset="study_battery", pass2_from=9,
                  preset_cfg=None):
    day = root / "2026-10-20"
    for pos, mode in enumerate(order, start=1):
        if pos in skip:
            continue
        g = day / f"{code}_{9 + pos:02d}0000_{mode}"
        g.mkdir(parents=True)
        (g / "trials.csv").write_text("h\n1\n")
        (g / "raw.csv").write_text("h\n1\n")
        bs = {"status": "completed", "trials": counts.get(mode, 12),
              "connection": {"drops": drops if pos == 2 else 0},
              "stim_cue_failures": 0}
        if mode == "force_pilot":
            bs["force_pilot"] = {"runs": fp_runs}
        bat = {"id": "x", "preset": preset, "family": family,
               "position": pos, "of": len(order),
               "phase": "pass2" if pos >= pass2_from else "pass1"}
        if pos == pass2_from and rest_s is not None:
            bat["rest_before_s"] = rest_s
        snap = {"game": {"test_mode_enabled": pos in test_mode},
                "latency": {"measured": measured,
                            "measured_on": "2026-10-19"},
                "rhythm": {"audio_offset_ms": 87}}
        if preset_cfg is not None:
            snap["protocol"] = {"presets": {preset: preset_cfg}}
        meta = {"participant": code, "hand": "right",
                "dominant_hand": "left", "age": "22", "sex": sex,
                "hand_length_mm": "184",
                "started_at": f"2026-10-20T{9 + pos:02d}:00:00",
                "finished_at": f"2026-10-20T{9 + pos:02d}:02:00",
                "calibration": {"created_at": "2026-10-20T09:55:00"},
                "config_snapshot": snap,
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
        # Hand breadth left the login: it is never asked for.
        self.assertNotIn("breadth", bad)

    def test_the_passes_are_read_off_the_sitting(self):
        good = " ".join(line for ok, line in self._check() if ok)
        self.assertIn("steps 1 to 8 pass 1, 9 to 12 pass 2", good)
        self.assertIn("all 12 steps finished", good)

    def test_the_15_is_checked_against_itself(self):
        # Four full-length blocks, one pass, no rest, an 18 minute stop.
        result = self._check(order=ORDER_15_FULL, preset="trial_15",
                             pass2_from=99, rest_s=None,
                             preset_cfg={"hard_stop_min": 18})
        bad = self._bad(result)
        self.assertEqual(len(bad), 1, bad)
        self.assertIn("18 min stop", bad[0])
        good = " ".join(line for ok, line in result if ok)
        self.assertIn("all 4 steps finished", good)
        self.assertIn("full counts in every block", good)
        self.assertNotIn("rest", good)

    def test_a_short_trial_length_is_checked_against_itself(self):
        # The old 15: six shortened blocks, no rest, an 18 minute stop.
        # Its short counts are its full counts, not short blocks.
        result = self._check(order=ORDER_15, counts=COUNTS_SHORT,
                             family="short", preset="trial_15",
                             pass2_from=4, fp_runs=6, rest_s=None,
                             preset_cfg={"hard_stop_min": 18})
        bad = self._bad(result)
        self.assertEqual(len(bad), 1, bad)
        self.assertIn("18 min stop", bad[0])
        good = " ".join(line for ok, line in result if ok)
        self.assertIn("all 6 steps finished", good)
        self.assertIn("full counts in every block", good)
        self.assertNotIn("rest", good)
        # A full-length Force Pilot in a short sitting is not its plan.
        bad = " ".join(self._bad(self._check(
            order=ORDER_15, counts=COUNTS_SHORT, family="short",
            preset="trial_15", pass2_from=4, fp_runs=12, rest_s=None,
            preset_cfg={"hard_stop_min": 18})))
        self.assertIn("force_pilot (12 of 6 runs)", bad)


if __name__ == "__main__":
    unittest.main()
