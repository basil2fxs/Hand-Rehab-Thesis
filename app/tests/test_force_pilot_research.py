"""Force Pilot after the deep research of 1 October 2026.

The centre line is drawn and the card says to follow it; the probe
asks for a press as hard as is comfortable; F1 is the force-target
correlation on the repeating waves against the irregular ones, with
the level rho kept as a description; F2 is the lag class contrast
read against a device range; F3 and F4 are feasibility checks with
the still-finger baseline beside them; and the width-free measures
print beside T2 and T3.
"""
from __future__ import annotations

import contextlib
import io
import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

APP = Path(__file__).resolve().parents[1]
NOTEBOOK = APP.parent / "analysis" / "session_analysis.ipynb"


class StillFingerTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_a_flat_target_is_a_still_finger_s_whole_run(self):
        import numpy as np
        flat = np.full(500, 12.0)
        self.assertEqual(self.ra.fp_still_tic(flat, 4.0), 1.0)
        self.assertEqual(self.ra.fp_still_mae(flat), 0.0)

    def test_a_sine_leaves_the_still_finger_part_of_the_run(self):
        import numpy as np
        t = np.linspace(0.0, 20.0, 4001)
        sine = 14.0 + 6.0 * np.sin(2 * np.pi * 0.15 * t)
        # Half-width 8 against an amplitude of 6: a still finger at the
        # middle holds the whole wave, as on Slow breath.
        self.assertEqual(self.ra.fp_still_tic(sine, 8.0), 1.0)
        # Half-width 4: the best still finger is not at the middle but
        # near an extreme, where a sine dwells. A window from -2 to +6
        # about the centre holds every sample with sin above -1/3.
        want = 0.5 + np.arcsin(1.0 / 3.0) / np.pi
        self.assertAlmostEqual(self.ra.fp_still_tic(sine, 4.0), want,
                               places=2)
        # The median of a sine is its centre; the mean absolute
        # deviation of a sine is 2A/pi.
        self.assertAlmostEqual(self.ra.fp_still_mae(sine),
                               2.0 * 6.0 / np.pi, places=1)

    def test_rmse_over_sd_ignores_the_corridor(self):
        import numpy as np
        t = np.linspace(0.0, 10.0, 2001)
        target = 14.0 + 5.0 * np.sin(2 * np.pi * 0.2 * t)
        err = 0.5 * np.sin(2 * np.pi * 1.0 * t)
        got = self.ra.fp_rmse_over_sd(err, target)
        self.assertAlmostEqual(got, (0.5 / np.sqrt(2)) / (5.0 / np.sqrt(2)),
                               places=2)


def _long(ra, rows):
    import pandas as pd
    cols = ra.COHORT_LONG_COLS
    out = []
    for i, metrics in enumerate(rows):
        for metric, val in metrics.items():
            r = {c: None for c in cols}
            r.update(participant=f"P{i:02d}", phase="pass1", hand="right",
                     hand_role="dominant", mode="force_pilot",
                     metric=metric, value=val, n_trials=12)
            out.append(r)
    return pd.DataFrame(out, columns=cols)


class ForcePilotChecksTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_f1_reads_the_repeating_waves_against_the_irregular_ones(self):
        ra = self.ra
        rows = [{"r_target_periodic": 0.95 - 0.004 * i,
                 "r_target_nonperiodic": 0.85 - 0.003 * i}
                for i in range(8)]
        row = ra._fp_class_contrast_row(_long(ra, rows), 3)
        self.assertEqual(row["id"], "F1")
        self.assertEqual(row["verdict"], "pass")
        self.assertEqual(row["family"], "pre-specified")
        self.assertLess(row["p"], 0.05)
        # The other way round fails: the irregular waves tracked better.
        rows = [{"r_target_periodic": 0.80 + 0.004 * i,
                 "r_target_nonperiodic": 0.90 + 0.003 * i}
                for i in range(8)]
        row = ra._fp_class_contrast_row(_long(ra, rows), 3)
        self.assertEqual(row["verdict"], "fail")

    def test_f2_asks_for_a_longer_lag_on_the_irregular_waves(self):
        ra = self.ra
        rows = [{"lag_np_ms": 60.0 + 5.0 * i,
                 "pd_lag_periodic_ms": -40.0 + 3.0 * i}
                for i in range(8)]
        row = ra._fp_lag_contrast_row(_long(ra, rows), 3)
        self.assertEqual(row["id"], "F2")
        self.assertEqual(row["verdict"], "pass")
        self.assertLess(row["p"], 0.05)
        self.assertIn("inside the device range -150 to +300 ms",
                      row["detail"])
        # A lag near zero on both is not a failure of timing, but it is
        # not the contrast either.
        rows = [{"lag_np_ms": -10.0 + i, "pd_lag_periodic_ms": 5.0 + i}
                for i in range(8)]
        self.assertEqual(ra._fp_lag_contrast_row(_long(ra, rows), 3)
                         ["verdict"], "fail")

    def test_the_level_rho_is_a_description_now(self):
        ra = self.ra
        rows = [{f"lvl{k}_mae_pct": 4.0 - 0.1 * k for k in range(1, 13)}
                for _i in range(6)]
        row = ra._ladder_bandwidth_row(_long(ra, rows), 3, 0)
        self.assertEqual(row["id"], "F1lvl")
        self.assertEqual(row["verdict"], "reported")
        self.assertEqual(row["family"], "exploratory")
        self.assertTrue(row["p"] != row["p"])      # no p: not tested

    def test_the_validity_table_carries_the_new_rows(self):
        import pandas as pd
        ra = self.ra
        rows = [{"r_target_periodic": 0.95 - 0.004 * i,
                 "r_target_nonperiodic": 0.85 - 0.003 * i,
                 "lag_np_ms": 60.0 + 5.0 * i,
                 "pd_lag_periodic_ms": -40.0 + 3.0 * i}
                for i in range(8)]
        cohort = {"long": _long(ra, rows), "sel": pd.DataFrame(),
                  "trials": pd.DataFrame(), "min_n": 3, "metas": {},
                  "tables": {}, "frames": {}}
        with contextlib.redirect_stdout(io.StringIO()):
            v = ra.sec_cohort_validity(cohort).set_index("id")
        self.assertIn("irregular waves", str(v.loc["F1", "check"]))
        self.assertIn("longer lag", str(v.loc["F2", "check"]))
        self.assertIn("F1lvl", v.index)

    def test_the_literature_rows_say_feasibility_and_drop_kurillo(self):
        ra = self.ra
        spec = {s["id"]: s for s in ra.MODE_LIT["force_pilot"]}
        self.assertNotIn("Kurillo", spec["F1"]["source"])
        self.assertIn("Drop", spec["F1"]["source"])
        self.assertTrue(spec["F3"]["claim"].startswith("a feasibility check"))
        self.assertTrue(spec["F4"]["claim"].startswith("a feasibility check"))
        self.assertIn("correlation", spec["F6"]["reference"])
        have = {(m, k) for m, k, _u in ra.COHORT_SECOND_GO_METRICS}
        self.assertIn(("force_pilot", "r_target"), have)
        self.assertIn(("force_pilot", "rmse_sd"), have)

    def test_the_old_wording_is_gone(self):
        nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
        src = "".join("".join(c["source"]) for c in nb["cells"])
        self.assertNotIn("Clinical Biomechanics \"\n                    "
                         "\"20(10):1071-1080", src)
        self.assertNotIn("level number IS bandwidth", src)
        self.assertNotIn("F2's criterion is a 100 to 300 ms band", src)


class ProbeTableTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_the_probe_table_reads_the_logged_peaks(self):
        import tempfile
        head = ("iso_ts,t_perf,sample_idx,fsr1,fsr2,fsr3,fsr4,fsr5,fsr6,"
                "fsr7,fsr8,hand,event,lane,detail\n")
        rows = [
            "t,1.0,1,0,0,0,0,0,0,0,0,right,block_start,,force_pilot",
            "t,2.0,2,0,0,0,0,0,0,0,0,right,max_press_peaks,0,"
            "hand=right;finger=0;peaks=200.0-220.0-210.0;max_counts=210.0",
            "t,3.0,3,0,0,0,0,0,0,0,0,right,max_press_near_full_scale,1,"
            "hand=right;finger=1;peak_counts=480.0;full_scale=511",
            "t,3.1,4,0,0,0,0,0,0,0,0,right,max_press_peaks,1,"
            "hand=right;finger=1;peaks=470.0-480.0-460.0;max_counts=470.0",
        ]
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "P01_120000_force_pilot"
            folder.mkdir()
            (folder / "raw.csv").write_text(
                head + "\n".join(rows) + "\n" + "x" * 0,
                encoding="utf-8")
            tbl = self.ra.fp_probe_table([folder]).set_index("finger")
        self.assertEqual(list(tbl.index), [0, 1])
        self.assertEqual(tbl.loc[0, "peaks"], "200-220-210")
        self.assertAlmostEqual(tbl.loc[0, "cv"], 10.0 / 210.0, places=4)
        self.assertAlmostEqual(tbl.loc[0, "max_n"],
                               210.0 * self.ra.N_PER_COUNT)
        self.assertFalse(bool(tbl.loc[0, "near_full_scale"]))
        self.assertTrue(bool(tbl.loc[1, "near_full_scale"]))


class ForcePilotScreenWordsTests(unittest.TestCase):

    def test_the_probe_and_the_card_say_the_approved_words(self):
        text = (APP / "finger_rehab" / "ui" / "force_pilot_screen.py") \
            .read_text(encoding="utf-8")
        self.assertIn("Press as hard as is comfortable, then let go and "
                      "rest.", text)
        self.assertNotIn("Press as hard as you can", text)
        self.assertNotIn('"Keep your line inside the band."', text)
        from finger_rehab.ui.force_pilot_screen import ForcePilotScreen
        self.assertEqual(ForcePilotScreen.FOLLOW_LINE,
                         "Keep your line on the centre line; the band is "
                         "how far you can drift.")
        sheet = (APP / "docs" / "study_day" / "run_sheet.md") \
            .read_text(encoding="utf-8")
        self.assertIn("as hard as\n      is comfortable", sheet)
        self.assertIn("keep your line on the centre line", sheet)


if __name__ == "__main__":
    unittest.main()
