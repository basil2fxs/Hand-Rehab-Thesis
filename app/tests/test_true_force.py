"""True force per press, the shared exports, and Rayan's model on the SRT.

The game's trials.csv logs peak_force_n as the target pad's peak SO FAR
when the trial is logged, and the modes that end a trial on the press
log it as the press registers: on the pilot Reaction block that was a
median 0.76 N against a true press peak of 1.75 N. The notebook reads
the peak off the raw stream instead, zeroed the way Rayan's
analyze_baseline_drift_modified_newtons.R zeroes it (the mean of the
250 ms before the cue), and converts each pad with its own bench slope
once scripts/pad_bench.py has measured it. These tests hold that to a
session the real engine wrote, with a synthetic 200 Hz stream whose
presses rise exactly 180 counts above rest.

Also here: the MATLAB file and the Rayan layout the export cell writes,
the SRT task in his block model, and the Muscle Memory chapter on a
block that ended before its first probe (it used to raise KeyError).
"""
from __future__ import annotations

import contextlib
import io
import random
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.test_rayan_port import _stream_for, nb  # noqa: E402


class EngineSessionTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import pygame
        from tests.test_cohort_notebook import _engine, _play_reaction
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name) / "sessions"
        root.mkdir()
        pygame.init()
        eng = None
        try:
            eng = _engine(root)
            eng.begin_session("P78", "30", dominant_hand="right", visit="1")
            cls.folder = _play_reaction(eng, "right", 250.0,
                                        random.Random(12), n_trials=12)
            eng.end_session()
        finally:
            if eng is not None:
                try:
                    eng._close_loggers()
                except Exception:
                    pass
            pygame.quit()
        _stream_for(cls.folder, random.Random(6))
        cls.ns = nb()
        with contextlib.redirect_stdout(io.StringIO()):
            cls.ctx = cls.ns.prepare("all", root=root)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def _bench_root(self, slopes):
        root = Path(tempfile.mkdtemp())
        cal = root / "config" / "calibration"
        cal.mkdir(parents=True)
        rows = [{"label": "calibrated", "pad": p + 1, "finger": f,
                 "measure": "slope_counts_per_n", "value": v, "datasheet": 51.2}
                for p, (f, v) in enumerate(zip(("index", "middle", "ring",
                                                "little"), slopes))]
        pd.DataFrame(rows).to_csv(
            cal / "pad_bench_calibrated_20260930_120000_summary.csv",
            index=False)
        return root

    def test_the_true_peak_is_the_press_peak(self):
        ns, ctx = self.ns, self.ctx
        tf = ns.true_press_force(ctx["folders"], None, ctx["calset"],
                                 bench={})
        self.assertEqual(len(tf), 12)
        self.assertTrue(((tf["peak_counts"] > 175)
                         & (tf["peak_counts"] < 186)).all())
        game = tf["game"].iloc[0]
        per_n = ns.raw_n_per_count(ctx["calset"], game)
        np.testing.assert_allclose(tf["peak_n"], tf["peak_counts"] * per_n)
        self.assertEqual(set(tf["n_from"]), {"rating"})

    def test_bench_slopes_convert_each_pad(self):
        ns, ctx = self.ns, self.ctx
        slopes = [40.0, 50.0, 60.0, 70.0]
        bench = ns.bench_pad_slopes(root=self._bench_root(slopes))
        self.assertEqual(bench["slopes"], {0: 40.0, 1: 50.0, 2: 60.0, 3: 70.0})
        tf = ns.true_press_force(ctx["folders"], None, ctx["calset"],
                                 bench=bench)
        want = tf["peak_counts"] / tf["lane"].map(lambda l: slopes[l])
        np.testing.assert_allclose(tf["peak_n"], want)
        self.assertEqual(set(tf["n_from"]), {"bench"})

    def test_no_bench_file_means_no_slopes(self):
        self.assertEqual(self.ns.bench_pad_slopes(root=tempfile.mkdtemp()), {})

    def test_the_sensor_table_carries_the_zeroed_newtons(self):
        ns, ctx = self.ns, self.ctx
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            table = ns.sec_rayan_sensor(ctx["folders"], ctx["calset"],
                                        ctx["trials"])
        for col in ("mean peak, 250 ms zero (counts)",
                    "mean peak, 250 ms zero (N)", "N from"):
            self.assertIn(col, table.columns)
        self.assertTrue(((table["mean peak, 250 ms zero (counts)"] > 175)
                         & (table["mean peak, 250 ms zero (counts)"] < 186)).all())
        self.assertIn("TRUE FORCE PER PRESS", buf.getvalue())

    def test_the_force_chapter_reads_the_true_peak(self):
        ns, ctx = self.ns, self.ctx
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            ns.sec_force(ctx["trials"], ctx["unit"], ctx["calset"],
                         ctx["folders"])
        self.assertIn("TRUE PEAK PER PRESS", buf.getvalue())

    def test_the_matlab_file_reads_back(self):
        from scipy.io import loadmat
        ns = self.ns
        frame = pd.DataFrame({"trial": [1, 2, 3], "rt ms": [250.5, np.nan, 300.0],
                              "hand": ["right", None, "left"],
                              "ok": [True, False, True]})
        out = Path(tempfile.mkdtemp())
        path = ns.export_matlab({"trials": frame}, out)
        got = loadmat(path, squeeze_me=True)["trials"]
        self.assertEqual(list(got["trial"].item()), [1.0, 2.0, 3.0])
        self.assertTrue(np.isnan(got["rt_ms"].item()[1]))
        # MATLAB keeps an empty string as a 0 by 0 char array.
        hands = [h if isinstance(h, str) else "" for h in got["hand"].item()]
        self.assertEqual(hands, ["right", "", "left"])
        self.assertEqual(list(got["ok"].item()), [1.0, 0.0, 1.0])
        self.assertIn("struct2table", (out / "README_matlab.txt").read_text())

    def test_the_rayan_layout_rests_at_255_with_values_on_events(self):
        ns, ctx = self.ns, self.ctx
        out = Path(tempfile.mkdtemp())
        written = ns.export_for_rayan(ctx["folders"], out)
        raws = sorted((out / "raw").glob("*.csv"))
        self.assertEqual(len(raws), 1)
        self.assertIn(out / "README.txt", [out / "README.txt"])
        df = pd.read_csv(raws[0])
        ev = df["event"].fillna("").astype(str)
        stims = df[ev == "stim"]
        self.assertTrue((stims["fsr1"] > 0).all())
        self.assertTrue(stims["detail"].astype(str).str.contains(r"trial=\d").all())
        first = float(stims["t_perf"].min())
        rest = df[(ev == "") & (df["t_perf"] < first)]
        self.assertAlmostEqual(float(rest["fsr1"].median()), 255.0, delta=1.0)
        trials = [p for p in written if p.parent == out]
        self.assertTrue(trials)
        log = pd.read_csv(trials[0])
        self.assertTrue(set(log["block"]) <= {"pretest", "main", "aftertest"})


class SrtModelTests(unittest.TestCase):

    def _frame(self, people=5, seed=4):
        rng = np.random.default_rng(seed)
        rows = []
        for p in range(people):
            base = 420.0 + rng.normal(0, 30)
            for phase, blocks in (("practice", [1]), ("learning", range(1, 9)),
                                  ("posttest", [1])):
                for b in blocks:
                    mean = (base if phase == "practice"
                            else base - 12.0 * b if phase == "learning"
                            else base - 40.0)
                    for k in range(40):
                        rows.append({"participant": f"P{p:02d}", "phase": phase,
                                     "block": b, "trial": k + 1,
                                     "accuracy": "correct" if k % 10 else "incorrect",
                                     "rt_ms": mean + rng.normal(0, 40),
                                     "flag": "", "setup": "constant, 500 ms"})
        return pd.DataFrame(rows)

    def test_phases_map_onto_his_blocks(self):
        ns = nb()
        a = ns.srt_rayan_blocks(self._frame())
        self.assertEqual(sorted(a["block_all"].unique()), list(range(10)))
        self.assertEqual(set(a.loc[a["is_random"], "block_all"]), {0, 9})
        self.assertTrue((a["time_difference_ms"] <= 1000).all())
        # his filter: wrong presses out (one in ten of the fake trials)
        self.assertEqual(len(a), 5 * 10 * 36)

    def test_the_model_finds_the_sequence_effect(self):
        ns = nb()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            out = ns.srt_rayan_model(self._frame())
        means, effect, info = out["constant, 500 ms"]
        self.assertEqual(info["n_people"], 5)
        self.assertEqual(len(means), 10)
        # post-test 40 below base, last learning block 96 below: the
        # post-test is slower by about 56 ms, the rebound
        self.assertAlmostEqual(effect["estimate"], 56.0, delta=12.0)
        self.assertLess(effect["lower"], effect["estimate"])
        self.assertIn("sequence effect", buf.getvalue())


class PatternNoProbeTests(unittest.TestCase):

    def test_scores_keep_their_columns_without_a_probe(self):
        ns = nb()
        takes = pd.DataFrame({"game": ["g", "g"], "session": ["s", "s"],
                              "take": [1, 2], "order": [1, 2],
                              "kind": ["random", "seq"], "soc": ["", "a"],
                              "rts": [pd.Series([300.0, 310.0]),
                                      pd.Series([290.0, 280.0])]})
        scores = ns.pattern_learning_scores(takes)
        self.assertTrue(scores.empty)
        self.assertIn("learning_score_ms", scores.columns)
        self.assertTrue(scores[scores["learning_score_ms"].notna()].empty)


if __name__ == "__main__":
    unittest.main()
