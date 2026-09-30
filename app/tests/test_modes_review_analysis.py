"""The analysis added by the review of the seven modes (30 September
2026), each against data built to give a known answer.

- Presses on the board's own clock: the board samples every 5 ms but
  its adapter hands samples over in bursts, and each press is stamped
  when its burst arrives. The lower envelope of arrival time against
  sample count rebuilds the grid.
- Chords: a quiet finger's leak read against what a resting finger
  reaches on the same pad, and spans on the board's clock.
- Rhythm: how much of each error the next press takes back.
- Adaptive: what the controller did, not only how fast it went.
- Buzz Hunt: errors graded by finger distance.
- Echo and the reliability tables: the continuous measures and the
  runs a later study needs.
- The Holm family: W3 is P1 under another id and counts once.
"""
from __future__ import annotations

import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_analysis_gaps import _load_notebook  # noqa: E402

_RA = None


def _ra():
    global _RA
    if _RA is None:
        _RA = _load_notebook("modes_review")
    return _RA


RAW_COLS = ["iso_ts", "t_perf", "sample_idx", "fsr1", "fsr2", "fsr3",
            "fsr4", "fsr5", "fsr6", "fsr7", "fsr8", "hand", "event", "lane",
            "detail"]


def _bursty_stream(seconds=20.0, period=0.005, burst=0.020, delay=0.001):
    """Sample moments on a 5 ms grid, each stamped when its 20 ms
    burst arrives: the next burst boundary plus a fixed 1 ms."""
    n = int(seconds / period)
    k = np.arange(n)
    per_burst = int(round(burst / period))
    true_t = 100.0 + k * period
    # The samples of one burst are stamped microseconds apart, in the
    # order they were taken, as on the real adapter.
    arrive = (100.0 + (k // per_burst + 1) * burst + delay
              + (k % per_burst) * 2e-6)
    return true_t, arrive


def _write_raw(folder: Path, rows):
    folder.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(rows, columns=RAW_COLS)
    df.to_csv(folder / "raw.csv", index=False)
    return folder


class GridTiming(unittest.TestCase):
    def test_the_envelope_recovers_how_late_each_sample_was(self):
        ra = _ra()
        true_t, arrive = _bursty_stream()
        late = ra.sample_grid_lateness(arrive)
        truth = (arrive - true_t) * 1000.0
        truth -= np.percentile(truth, 0.5)
        ok = np.isfinite(late)
        self.assertGreater(ok.mean(), 0.99)
        self.assertLess(np.max(np.abs(late[ok] - truth[ok])), 0.5)
        # Four samples a burst: 0, 5, 10 and 15 ms late.
        self.assertAlmostEqual(float(np.mean(late[ok])), 7.5, delta=0.5)

    def test_a_press_gets_the_lateness_of_the_sample_it_was_found_on(self):
        ra = _ra()
        true_t, arrive = _bursty_stream(seconds=10.0)
        rows, idx = [], 0
        press_at = {600, 1201, 1802}
        for k, (tt, ta) in enumerate(zip(true_t, arrive)):
            idx += 1
            rows.append(["", ta, idx, 10, 10, 10, 10, 0, 0, 0, 0, "right",
                         "", "", ""])
            if k in press_at:
                idx += 1
                rows.append(["", ta, idx, 0, 0, 0, 0, 0, 0, 0, 0, "right",
                             "press", 1, ""])
        with tempfile.TemporaryDirectory() as td:
            folder = _write_raw(Path(td) / "P1_000000_rhythm", rows)
            ra.TIMING_CACHE.clear()
            pt = ra.press_timing(folder)
            self.assertEqual(len(pt), 3)
            # Lateness is read against the least-late sample, the
            # last of each burst (1 ms here plus 5 ms of its burst).
            floor_ms = float(np.min(arrive - true_t)) * 1000.0
            want = [(arrive[k] - true_t[k]) * 1000.0 - floor_ms
                    for k in sorted(press_at)]
            for got, w in zip(pt["late_ms"], want):
                self.assertAlmostEqual(got, w, delta=0.6)
            table = ra.timing_floor_rows([folder])
            self.assertEqual(int(table["matched"].iloc[0]), 3)
            self.assertGreater(table["bursting_share"].iloc[0], 0.4)


class ChordFloor(unittest.TestCase):
    def test_a_resting_pad_has_a_floor_near_its_noise(self):
        ra = _ra()
        rng = np.random.default_rng(1)
        t = 100.0 + np.arange(0, 60.0, 0.005)
        rows = []
        for i, tt in enumerate(t):
            v = 40 + rng.normal(0.0, 1.0, 4).round()
            rows.append(["", tt, i + 1, *v, 0, 0, 0, 0, "right", "", "",
                         ""])
        with tempfile.TemporaryDirectory() as td:
            folder = _write_raw(Path(td) / "P1_000000_chords", rows)
            ra.CHORD_FLOOR_CACHE.clear()
            floor = ra.chord_rest_peaks(folder)
        self.assertEqual(set(floor), {0, 1, 2, 3, 4, 5, 6, 7} & set(floor))
        for lane in range(4):
            # The largest of about 640 draws above a median baseline:
            # near three SDs of the noise.
            self.assertGreater(floor[lane], 2.0)
            self.assertLess(floor[lane], 4.5)

    def test_a_window_with_a_press_is_not_rest(self):
        ra = _ra()
        t = 100.0 + np.arange(0, 20.0, 0.005)
        rows = []
        for i, tt in enumerate(t):
            rows.append(["", tt, i + 1, 40, 40, 40, 40, 0, 0, 0, 0,
                         "right", "", "", ""])
        # Presses every second: no window is free of them.
        for k, tt in enumerate(np.arange(100.5, 120.0, 1.0)):
            rows.append(["", tt, 10 ** 6 + k, 0, 0, 0, 0, 0, 0, 0, 0,
                         "right", "press", 0, ""])
        with tempfile.TemporaryDirectory() as td:
            folder = _write_raw(Path(td) / "P2_000000_chords", rows)
            ra.CHORD_FLOOR_CACHE.clear()
            self.assertEqual(ra.chord_rest_peaks(folder), {})


class RhythmGain(unittest.TestCase):
    def _hits(self, gain, n=2000, seed=2):
        rng = np.random.default_rng(seed)
        a = [0.0]
        for _ in range(n - 1):
            a.append((1.0 - gain) * a[-1] + rng.normal(0.0, 20.0))
        return pd.DataFrame({"song_time_s": np.arange(n) * 0.75,
                             "time_difference_ms": a})

    def test_the_gain_reads_back(self):
        ra = _ra()
        for g in (0.3, 0.6, 0.9):
            self.assertAlmostEqual(ra.rhythm_correction_gain(self._hits(g)),
                                   g, delta=0.06)

    def test_long_gaps_are_left_out(self):
        ra = _ra()
        hits = self._hits(0.5)
        hits["song_time_s"] = np.arange(len(hits)) * 2.5
        self.assertTrue(np.isnan(ra.rhythm_correction_gain(hits)))


class AdaptiveController(unittest.TestCase):
    def test_what_the_controller_did(self):
        ra = _ra()
        n = 40
        bpm = [30 + 3 * i for i in range(20)] + [87] * 20
        # Hits for the first 20, then three in four.
        label = ["Great"] * 20 + (["Great", "Great", "Great", "Miss"] * 5)
        rec = [False] * n
        rec[30] = rec[31] = True
        rec[36] = True
        rows = pd.DataFrame({"early_late": label, "bpm_at_trial": bpm,
                             "in_recovery": rec, "error_type": "",
                             "mode": "adaptive"})
        got = ra.adaptive_controller_rows(rows)
        self.assertEqual(got["recovery_entries"], 2)
        self.assertAlmostEqual(got["window_at_peak_ms"],
                               0.9 * 60000.0 / 87, places=6)
        self.assertGreater(got["time_in_band"], 0.0)
        self.assertLessEqual(got["time_in_band"], 1.0)
        # The band is first held once the pace has climbed 20 BPM.
        self.assertGreater(got["first_band_entry"], 8)


class BuzzHuntDistance(unittest.TestCase):
    def test_errors_graded_by_distance(self):
        ra = _ra()
        rows = []
        for i in range(6):
            who = f"P{i:02d}"
            for d, k in ((1, 3), (2, 1), (3, 0)):
                rows.append({"participant": who, "mode": "buzz_hunt",
                             "hand_role": "dominant", "phase": "pass1",
                             "metric": f"errors_d{d}", "value": k,
                             "n_trials": 4})
        row = ra._b2_distance_row(pd.DataFrame(rows), 3)
        self.assertEqual(row["id"], "B2d")
        self.assertEqual(row["verdict"], "reported")
        self.assertAlmostEqual(row["value"], 0.75, places=3)
        self.assertIn("against 0.50", row["detail"])
        self.assertEqual(row["family"], "exploratory")


class ReliabilityProjection(unittest.TestCase):
    def test_every_retest_row_says_how_many_runs_make_0_8(self):
        ra = _ra()
        rng = np.random.default_rng(3)
        true = rng.normal(0.0, 1.0, 20)
        p1 = pd.Series(true + rng.normal(0.0, 1.0, 20))
        p2 = pd.Series(true + rng.normal(0.0, 1.0, 20))
        st = ra.cohort_retest_stats(p1, p2)
        self.assertIn("runs_for_0_8", st)
        icc = st["icc21"]
        if np.isfinite(icc) and icc > 0:
            self.assertEqual(st["runs_for_0_8"], ra.fp_runs_for_icc(icc))

    def test_the_second_go_list_carries_the_continuous_measures(self):
        ra = _ra()
        have = {(m, k) for m, k, _u in ra.COHORT_SECOND_GO_METRICS}
        for want in (("echo", "total_items"), ("echo", "span_mean"),
                     ("rhythm", "asyn_mean_ms"), ("rhythm", "asyn_rsd_ms"),
                     ("pattern", "random_take_rt_ms"),
                     ("adaptive", "window_at_peak_ms")):
            self.assertIn(want, have)


class HolmFamily(unittest.TestCase):
    def test_w3_is_counted_once_and_takes_p1s_verdict(self):
        ra = _ra()
        rows = []
        for i in range(8):
            rows.append({"participant": f"P{i:02d}", "mode": "pattern",
                         "hand": "right", "hand_role": "dominant",
                         "phase": "pass1", "metric": "learning_score_ms",
                         "value": 30.0 + 4.0 * i, "n_trials": 24,
                         "position": 1, "visit": "1", "day": "",
                         "block_folder": f"P{i:02d}_x_pattern",
                         "config_hash": ""})
        cohort = {"long": pd.DataFrame(rows), "tables": {}, "min_n": 3,
                  "frames": {}}
        with contextlib.redirect_stdout(io.StringIO()):
            tbl = ra.sec_cohort_validity(cohort)
        v = tbl.set_index("id")
        self.assertTrue(np.isfinite(v.loc["P1", "p"]))
        self.assertTrue(np.isnan(v.loc["W3", "p"]))
        self.assertEqual(v.loc["W3", "verdict"], v.loc["P1", "verdict"])
        self.assertEqual(v.loc["W3", "p_holm"], v.loc["P1", "p_holm"])
        fam = v[(v["family"] == "pre-specified") & v["p"].notna()]
        self.assertEqual(list(fam.index).count("W3"), 0)


if __name__ == "__main__":
    unittest.main()
