"""Chords after the deep research of 1 October 2026.

The quiet fingers are read locked to the press, zeroed on the 250 ms
before the stimulus and signed, because at the study's light presses
the registered ER is mostly built before the press and the quiet
fingers unload during the hold; C6 reads each chord's mean onset, the
measure Verwey 2023 reports, with the first press as a sensitivity
row; a timing-only clean rate sits beside the registered one; the
record carries the mean onset and every finger's level; and the GET
READY card says to keep the other fingers still on their pads.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

RAW_COLS = ["iso_ts", "t_perf", "sample_idx", "fsr1", "fsr2", "fsr3",
            "fsr4", "fsr5", "fsr6", "fsr7", "fsr8", "hand", "event", "lane",
            "detail"]


def _raw_chord_block(folder: Path) -> Path:
    """One pair chord (index and middle) at t = 101.0: the targets rise
    80 counts from their presses, the ring finger (a neighbour of the
    middle) drops 3 counts at the press, the little finger stays put."""
    import numpy as np
    import pandas as pd
    rows = []
    t = 100.0
    i = 0
    while t < 103.0:
        # Decide on the time as written, so a float step cannot put a
        # sample on the wrong side of an onset.
        tr = round(t, 4)
        v = [40.0, 40.0, 40.0, 40.0]
        if tr >= 101.4:
            v[0] = 120.0
            v[2] = 37.0
        if tr >= 101.45:
            v[1] = 120.0
        i += 1
        rows.append(["", tr, i, *v, 0, 0, 0, 0, "right", "", "", ""])
        t += 0.005
    rows.append(["", 101.0, 10 ** 6, 0, 0, 0, 0, 0, 0, 0, 0, "right",
                 "stim", 0, "trial_id=1"])
    rows.append(["", 101.4, 10 ** 6 + 1, 0, 0, 0, 0, 0, 0, 0, 0, "right",
                 "press", 0, ""])
    rows.append(["", 101.45, 10 ** 6 + 2, 0, 0, 0, 0, 0, 0, 0, 0,
                 "right", "press", 1, ""])
    folder.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows, columns=RAW_COLS).to_csv(folder / "raw.csv",
                                                index=False)
    _ = np
    return folder


class ChordsNotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_the_quiet_fingers_are_read_locked_to_the_press(self):
        import pandas as pd
        ra = self.ra
        rows = pd.DataFrame([{"trial": 1, "correct_keys": "1,2",
                              "early_late": "Great",
                              "had_incorrect_press": False,
                              "hand_mode": "right", "game": "g1"}])
        with tempfile.TemporaryDirectory() as td:
            folder = _raw_chord_block(Path(td) / "P1_000000_chords")
            q = ra.chord_quiet_levels(folder, rows).set_index("finger")
        self.assertEqual(sorted(q.index), ["Pinky", "Ring"])
        # The ring finger unloads 3 counts beside the pressing middle;
        # the little finger does not move.
        self.assertAlmostEqual(q.loc["Ring", "hold"], -3.0, places=6)
        self.assertTrue(bool(q.loc["Ring", "neighbour"]))
        self.assertAlmostEqual(q.loc["Pinky", "hold"], 0.0, places=6)
        self.assertFalse(bool(q.loc["Pinky", "neighbour"]))
        self.assertAlmostEqual(q.loc["Ring", "target_hold"], 80.0, places=6)
        summary = ra.chord_quiet_summary(q.reset_index())
        self.assertEqual(summary["er_hold"], 0.0)
        self.assertEqual(summary["quiet_unload_share"], 0.5)
        self.assertEqual(summary["quiet_leak_share"], 0.0)

    def test_a_wrong_press_trial_is_left_out(self):
        import pandas as pd
        ra = self.ra
        rows = pd.DataFrame([{"trial": 1, "correct_keys": "1,2",
                              "early_late": "Late",
                              "had_incorrect_press": True,
                              "hand_mode": "right", "game": "g1"}])
        with tempfile.TemporaryDirectory() as td:
            folder = _raw_chord_block(Path(td) / "P1_000000_chords")
            self.assertTrue(ra.chord_quiet_levels(folder, rows).empty)

    def test_c6_reads_the_mean_onset(self):
        ra = self.ra
        recs = []
        for size, mean_on, first in ((1, 500.0, 500.0), (2, 630.0, 520.0),
                                     (3, 760.0, 540.0)):
            for k in range(3):
                recs.append({"kind": "single" if size == 1 else "chord",
                             "scope": "within", "class": "hit",
                             "size": size, "wrong": False,
                             "mean_onset_ms": mean_on, "rt_ms": first})
        # A misread cue is left out of both.
        recs.append({"kind": "chord", "scope": "within",
                     "class": "leak_fail", "size": 3, "wrong": True,
                     "mean_onset_ms": 5000.0, "rt_ms": 5000.0})
        bs = {"chords": {"trials": recs}}
        self.assertAlmostEqual(ra.chord_cost_from_records(bs), 130.0)
        self.assertAlmostEqual(ra.chord_cost_from_records(bs, "rt_ms"), 20.0)
        # The size table route takes the same key.
        by_size = [{"size": s, "n": 3, "median_mean_onset_ms": m,
                    "median_rt_ms": f}
                   for s, m, f in ((1, 500.0, 500.0), (2, 630.0, 520.0),
                                   (3, 760.0, 540.0))]
        self.assertAlmostEqual(
            ra.chord_cost_per_finger(by_size, "median_mean_onset_ms"), 130.0)
        self.assertAlmostEqual(ra.chord_cost_per_finger(by_size), 20.0)

    def test_the_block_emits_the_new_rows(self):
        import pandas as pd
        ra = self.ra
        recs = []
        for size in (1, 2, 3):
            for k in range(3):
                recs.append({"kind": "single" if size == 1 else "chord",
                             "scope": "within", "hand": "right",
                             "class": "hit" if k else "over_force",
                             "size": size, "wrong": False, "w_ms": 150.0,
                             "span_ms": (None if size == 1
                                         else 40.0 + 60.0 * k),
                             "mean_onset_ms": 400.0 + 120.0 * size,
                             "rt_ms": 450.0 + 10.0 * size, "er": 0.04,
                             "over_force": k == 0, "subblock": 1})
        block = {"game": "g1", "folder": None, "meta": {},
                 "bs": {"chords": {"hand": "right", "trials": recs,
                                   "by_size": [{"size": 1, "n": 3}]}},
                 "rows": pd.DataFrame(), "hand": "right", "calset": None,
                 "extra": {}}
        em = {m: v for _h, m, v, _n in ra._cohort_chords(block)}
        self.assertAlmostEqual(em["chord_cost_ms"], 120.0)
        self.assertAlmostEqual(em["chord_cost_first_ms"], 10.0)
        # Over-force chords count as missed in the clean rate but land
        # inside their window: 40, 100 and 160 ms against W 150.
        self.assertAlmostEqual(em["timing_clean_rate"], 4.0 / 6.0)
        self.assertAlmostEqual(em["median_span_ms_no_quad"], 100.0)

    def test_the_literature_rows_carry_c6_and_the_corrections(self):
        ra = self.ra
        spec = {s["id"]: s for s in ra.MODE_LIT["chords"]}
        self.assertIn("C6", spec)
        self.assertIn("mean onset", spec["C6"]["claim"])
        self.assertIn("Journal of Neurophysiology", spec["C1"]["source"])
        self.assertNotIn("Journal of Motor Behavior", spec["C1"]["source"])
        self.assertIn("reported, not tested", spec["C3"]["claim"])
        self.assertNotIn("C3", ra.COHORT_PRESPECIFIED)
        for metric in ("chord_cost_first_ms", "timing_clean_rate", "er_hold",
                       "quiet_unload_share"):
            self.assertIn(("chords", metric), ra.COHORT_DESCRIBE_ONLY)

    def test_the_music_split_is_descriptive(self):
        import pandas as pd
        ra = self.ra
        cols = ra.COHORT_LONG_COLS
        rows = []
        for i, (yrs, er) in enumerate(((0, 0.05), (0, 0.06), (8, 0.03),
                                       (12, 0.02))):
            r = {c: None for c in cols}
            r.update(participant=f"P{i:02d}", phase="pass1", hand="right",
                     hand_role="dominant", mode="chords",
                     metric="median_er", value=er, n_trials=40)
            rows.append(r)
        long = pd.DataFrame(rows, columns=cols)
        music = {"P00": 0.0, "P01": 0.0, "P02": 8.0, "P03": 12.0}
        split = ra.cohort_music_split(long, music).set_index(
            ["metric", "music"])
        self.assertAlmostEqual(split.loc[("median_er", "none"), "median"],
                               0.055)
        self.assertAlmostEqual(
            split.loc[("median_er", "1 year or more"), "median"], 0.025)
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "intake_sheet.csv").write_text(
                "participant,edinburgh_lq,music_years\nP01,80,3\np02,-70,0\n",
                encoding="utf-8")
            self.assertEqual(ra.cohort_intake_music(td),
                             {"P01": 3.0, "P02": 0.0})


class ChordsGameTests(unittest.TestCase):

    def test_the_record_carries_the_mean_onset_and_every_finger(self):
        from tests.test_chords_mode import (_build_mode, _complete_chord,
                                            _force_pair)
        engine, mode = _build_mode()
        det = SimpleNamespace(val_ema=[50.0, 50.0, 50.0, 50.0],
                              baseline=[48.0, 49.0, 50.0, 47.0],
                              pressed=[False] * 4)
        engine.detectors = {"right": det}
        _force_pair(mode)
        mode._fire(10.0)
        self.assertEqual(mode.active.pre_levels,
                         {0: 2.0, 1: 1.0, 2: 0.0, 3: 3.0})
        targets = list(mode.active.targets)
        quiet = [lane for lane in range(4) if lane not in targets]
        # A quiet finger unloads to 5 counts under its baseline.
        det.val_ema[quiet[0]] = det.baseline[quiet[0]] - 5.0
        _complete_chord(mode, 10.4, gap_s=0.05)
        rec = mode._records[-1]
        self.assertAlmostEqual(rec["mean_onset_ms"], 425.0, places=3)
        # _complete_chord presses the targets in order.
        self.assertEqual(rec["first_finger"],
                         mode._finger_of_lane(targets[0]))
        pre = rec["pre_levels"][str(quiet[0])]
        self.assertAlmostEqual(rec["end_deltas"][str(quiet[0])],
                               -5.0 - pre)

    def test_the_get_ready_card_says_keep_the_others_still(self):
        from finger_rehab.ui.screens import GameplayScreen
        text = " ".join(GameplayScreen.GET_READY_LINES["chords"])
        self.assertEqual(text, "Press the lit fingers together and hold "
                               "until the ring fills. Keep the other "
                               "fingers resting still on their pads.")


if __name__ == "__main__":
    unittest.main()
