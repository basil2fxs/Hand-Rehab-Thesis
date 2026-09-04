"""Rayan's R and Python analyses, ported into the notebook.

Two kinds of pin. The first is parity with his own output CSVs under
bin/old_rayyan_stuff/data (or RAYAN_DATA_DIR): peak, noise, SNR and
repeatability to the last decimal, the drift regression to his printed
equations, the Teasdale onsets to his processed CSV at his sample
rate, and the block-of-100 pipeline to the block means his plots
show. Those tests skip when the data folder is absent (it is
untracked). The second kind needs no data: a synthetic frame in this
logger's own layout (event rows with zeros, eight lanes, trial_id=N)
and a session the REAL engine wrote on the keyboard source, given a
200 Hz sample stream shaped around its own stim rows, run through
prepare() and the three new sections end to end.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import random
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import matplotlib
matplotlib.use("Agg")
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

NOTEBOOK = ROOT / "analysis" / "session_analysis.ipynb"

RAYAN = ROOT / "bin" / "old_rayyan_stuff" / "data"
if not RAYAN.exists() and os.environ.get("RAYAN_DATA_DIR"):
    RAYAN = Path(os.environ["RAYAN_DATA_DIR"])
RAW_FILES = sorted((RAYAN / "raw").glob("*.csv")) if RAYAN.exists() else []
TRIAL_FILES = sorted(RAYAN.glob("*.csv")) if RAYAN.exists() else []
HAVE_DATA = bool(RAW_FILES) and len(TRIAL_FILES) == 3

RAYAN_OFFSET = 255.0
RAYAN_COUNTS_PER_N = 51.2

CONSTANTS = ("RAYAN_PEAK_WINDOW_S", "RAYAN_NOISE_EXCLUDE_S",
             "RAYAN_SEGMENT_TRIALS", "RAYAN_RT_MIN_MS", "RAYAN_RT_MAX_MS",
             "RAYAN_CHUNK_TRIALS", "SINGLETACT_FULL_SCALE_COUNTS",
             "SINGLETACT_ADC_CEILING")
FUNCTIONS = ("rayan_stream", "rayan_static_offsets", "rayan_stim_levels",
             "rayan_baseline_shift", "rayan_stim_peaks",
             "rayan_baseline_noise", "rayan_repeatability",
             "rayan_sensor_table", "sec_rayan_sensor", "rayan_blocks",
             "_holm", "rayan_block_model", "sec_rayan_blocks",
             "rayan_trial_peaks", "sec_rayan_trial_peaks",
             "rayan_lookback_zoom")


class _Live:
    """Attribute access straight into the notebook module's dict, so a
    function re-bound by prepare()'s section wrapping is the one a test
    calls (the tests/test_cohort_notebook.py pattern)."""

    def __init__(self, ns: dict) -> None:
        self.__dict__ = ns


_NB = None


def nb() -> _Live:
    """Exec every notebook cell's definitions once per test module."""
    global _NB
    if _NB is not None:
        return _NB
    from tests.test_rehab_analysis import (FUTURE_FLAGS, MODULE_NAME,
                                           _code_cells, _definitions)
    name = MODULE_NAME + "_rayan"
    module = ModuleType(name)
    module.__file__ = str(NOTEBOOK)
    sys.modules[name] = module
    ns = module.__dict__
    try:
        for index, lines in _code_cells():
            source = _definitions(index, lines)
            code = compile(source, f"session_analysis.ipynb cell {index}",
                           "exec", flags=FUTURE_FLAGS, dont_inherit=True)
            exec(code, ns)
    finally:
        sys.modules.pop(name, None)
    ns["FIGDIR"] = Path(tempfile.mkdtemp())
    _NB = _Live(ns)
    return _NB


def _notebook_text() -> str:
    raw = json.loads(NOTEBOOK.read_text())
    return "".join("".join(c["source"]) + "\n" for c in raw["cells"]
                   if c["cell_type"] == "code")


def _his_raw() -> pd.DataFrame:
    """His raw log with his response events renamed to this logger's
    'press'. Everything else is read as it is."""
    df = pd.read_csv(RAW_FILES[0], low_memory=False)
    df["event"] = df["event"].replace({"resp": "press",
                                       "resp_early_correct": "press"})
    return df


# ------------------------------------------------ the notebook's shape

class NotebookShapeTests(unittest.TestCase):

    def test_the_three_sections_go_through_keep(self):
        text = _notebook_text()
        for name in ("rayan_sensor", "rayan_blocks", "rayan_trial_peaks"):
            self.assertIn(f'keep(ctx, "{name}"', text)

    def test_every_constant_and_function_is_defined(self):
        ns = nb()
        for name in CONSTANTS + FUNCTIONS:
            self.assertTrue(hasattr(ns, name), f"{name} missing")
        self.assertEqual(ns.RAYAN_PEAK_WINDOW_S, 1.2)
        self.assertEqual(tuple(ns.RAYAN_NOISE_EXCLUDE_S), (0.2, 1.5))
        self.assertEqual(ns.RAYAN_SEGMENT_TRIALS, 50)
        self.assertEqual(ns.RAYAN_CHUNK_TRIALS, 100)
        self.assertEqual(ns.SINGLETACT_FULL_SCALE_COUNTS, 512)

    def test_the_new_block_is_plain_ascii(self):
        raw = json.loads(NOTEBOOK.read_text())
        setup = "".join(raw["cells"][2]["source"])
        start = setup.index("Rayan's sensor and block analyses, ported")
        end = setup.index("Objective 1, per-finger hit rate", start)
        block = setup[start:end]
        bad = sorted({ch for ch in block if ord(ch) > 126})
        self.assertEqual(bad, [], f"non-ASCII in the new block: {bad!r}")

    def test_onset_chapter_states_its_sample_rate(self):
        self.assertIn("Sample rate for the detector: count over span",
                      _notebook_text())

    def test_references_carry_his_pipeline(self):
        flat = "\n".join(e for _, entries in nb().REFERENCES for e in entries)
        for needle in ("Holm, S. (1979)", "Savitzky, A., and Golay",
                       "Gustafsson, F. (1996)", "Hopkins, W.G. (2000)",
                       "Bates, D.", "Kuznetsova, A.", "Halekoh, U.",
                       "Lenth, R.V."):
            self.assertIn(needle, flat)


# ------------------------------------------- parity with his own CSVs

@unittest.skipUnless(HAVE_DATA, "Rayan's data folder is not present")
class HisFilesParityTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.ns = nb()
        cls.raw = _his_raw()
        cls.peaks = cls.ns.rayan_stim_peaks(cls.raw)
        # His peaks are counts above a flat 255; ours are above the pad's
        # pre-stim resting median. Re-base to his convention to compare.
        cls.peaks_255 = (cls.peaks["peak_counts"] + cls.peaks["offset"]
                         - RAYAN_OFFSET)

    def test_a_max_and_mean_peak(self):
        self.assertEqual(len(self.peaks), 599)
        self.assertEqual(float(self.peaks_255.max()), 767.0)
        self.assertAlmostEqual(float(self.peaks_255.mean()), 311.445743,
                               places=5)
        his = RAYAN / "Peak Analysis" / "overall_peak_force_summary.csv"
        if his.exists():
            t = pd.read_csv(his)
            self.assertEqual(int(t["n_presses"].iloc[0]), 599)
            self.assertAlmostEqual(float(t["overall_avg_peak"].iloc[0]),
                                   float(self.peaks_255.mean()), places=5)

    def test_b_rest_noise_and_snr(self):
        noise = self.ns.rayan_baseline_noise(self.raw)
        sd, n_rest = noise["fsr1"]
        self.assertAlmostEqual(sd, 8.669076, places=5)
        self.assertEqual(n_rest, 8981)
        self.assertAlmostEqual(float(self.peaks_255.mean()) / sd,
                               35.926060, places=4)

    def test_c_repeatability_per_segment(self):
        rep = self.ns.rayan_repeatability(self.peaks)
        his = pd.read_csv(next((RAYAN / "repeat").glob("*.csv")))
        his = his.rename(columns={"mean_force": "his_mean",
                                  "cv_percent": "his_cv"})
        self.assertEqual(len(rep), 12)
        offset = float(self.peaks["offset"].iloc[0])
        rep["mean_255"] = rep["mean_counts"] + offset - RAYAN_OFFSET
        rep["cv_255"] = 100.0 * rep["sd_counts"] / rep["mean_255"]
        m = rep.merge(his, on=["lane", "segment"])
        self.assertEqual(len(m), 12)
        np.testing.assert_allclose(m["mean_255"], m["his_mean"], atol=1e-6)
        np.testing.assert_allclose(m["cv_255"], m["his_cv"], atol=1e-4)

    def test_d_drift_regression_matches_his_equations(self):
        de = self.ns.drift_events(self.raw, "fsr1")
        pr = de[(de["kind"] == "press") & np.isfinite(de["zeroed_counts"])]
        self.assertGreater(len(pr), 500)
        k_raw, c_raw = np.polyfit(pr["t"], (pr["value"] - RAYAN_OFFSET)
                                  / RAYAN_COUNTS_PER_N, 1)
        k_zero, c_zero = np.polyfit(pr["t"], pr["zeroed_counts"]
                                    / RAYAN_COUNTS_PER_N, 1)
        # Tolerances are the documented sample-row-versus-event-row gap:
        # his R reads the level off the event row itself, which this
        # logger leaves at zero, so the nearest sample stands in.
        self.assertAlmostEqual(k_raw, 0.00400, delta=0.0005)
        self.assertAlmostEqual(c_raw, 1.948, delta=0.05)
        self.assertAlmostEqual(k_zero, 0.00171, delta=0.0005)
        self.assertAlmostEqual(c_zero, 0.956, delta=0.05)

    def test_e_teasdale_onsets_match_his_processed_csv(self):
        ns = self.ns
        his = pd.read_csv(next((RAYAN / "raw" / "Processed Data")
                               .glob("*.csv")))
        his_rt = pd.to_numeric(his["reaction_time_ms"], errors="coerce")
        ev = self.raw["event"].fillna("").astype(str).str.lower()
        samp = self.raw[ev.isin(["", "sample"])].dropna(subset=["t_perf"])
        t = samp["t_perf"].to_numpy(dtype=float)
        f1 = np.nan_to_num(samp["fsr1"].to_numpy(dtype=float), nan=0.0) \
            - RAYAN_OFFSET
        d = np.diff(t)
        d = d[(d > 0) & np.isfinite(d)]
        fs = 1.0 / float(np.median(d))        # his estimate_fs
        self.assertAlmostEqual(fs, 195.66, delta=0.05)
        stims = self.raw[(ev == "stim") & self.raw["lane"].notna()]
        self.assertEqual(len(stims), len(his))
        found = []
        rts = []
        peaks = []
        for _, s in stims.iterrows():
            t0 = float(s["t_perf"])
            i0 = int(np.searchsorted(t, t0 - 0.05, side="left"))
            i1 = int(np.searchsorted(t, t0 + 1.2, side="right"))
            onset, _f, _d = ns.teasdale_onset(f1[i0:i1], fs=fs,
                                              search_from=0,
                                              search_to=int(1.2 * fs))
            p0 = i0 if onset is None else i0 + onset
            found.append(onset is not None)
            rts.append(np.nan if onset is None
                       else (t[i0 + onset] - t0) * 1000.0)
            peaks.append(float(np.max(f1[p0:i1])))
        found = np.asarray(found)
        # Compared by stim order, never by trial_id: his numbering
        # restarts per block.
        np.testing.assert_array_equal(found, his_rt.notna().to_numpy())
        self.assertEqual(int((~found).sum()), 85)
        diff = np.abs(np.asarray(rts)[found] - his_rt.to_numpy()[found])
        self.assertLessEqual(float(diff.max()), 0.05)
        np.testing.assert_array_equal(np.asarray(peaks),
                                      his["peak_fsr1_raw"].to_numpy(dtype=float))

    def test_f_block_pipeline_on_his_trial_logs(self):
        ns = self.ns
        frames = []
        for p in TRIAL_FILES:
            df = pd.read_csv(p, low_memory=False)
            df["game"] = p.stem
            df["mode"] = "classic"
            df["phase"] = df["block"]
            df["iso_ts"] = np.arange(len(df))
            frames.append(df)
        a = ns.rayan_blocks(pd.concat(frames, ignore_index=True))
        self.assertEqual(len(a), 1582)
        self.assertEqual(a.groupby("block_all").size().to_dict(),
                         {0: 89, 1: 300, 2: 300, 3: 300, 4: 298, 5: 295})
        means, pairs, post_pre, trend, info = ns.rayan_block_model(a)
        self.assertEqual(info["n_people"], 3)
        np.testing.assert_allclose(
            means["emmean"].to_numpy(),
            [299.16, 215.05, 178.17, 168.44, 144.64, 143.19], atol=0.01)
        self.assertIsNone(post_pre)
        self.assertAlmostEqual(trend["estimate"], -177.254, delta=0.01)
        holm = pairs.set_index("contrast")["p_holm"]
        self.assertAlmostEqual(holm["2 - 3"], 0.2468, delta=1e-3)
        self.assertAlmostEqual(holm["4 - 5"], 0.8197, delta=1e-3)


# ---------------------------------------- this logger's own conventions

class OurConventionsTests(unittest.TestCase):

    def _raw(self, event_fill=9999):
        """Eight lanes, hand both, event rows with `event_fill` in every
        fsr cell, stims on lanes 0 and 5 with detail trial_id=N, presses
        after them, and a 200 Hz stream where the cued pad rises 150
        counts over 0.3 s after each cue."""
        rng = np.random.default_rng(3)
        rows = []
        t = 0.0
        base = [250, 260, 255, 290, 270, 300, 265, 280]
        cues = [(2.0, 0, 1), (5.0, 5, 2), (8.0, 0, 3), (11.0, 5, 4)]
        while t < 14.0:
            vals = [b + rng.normal(0, 1.0) for b in base]
            for tc, lane, _n in cues:
                if tc <= t < tc + 0.3:
                    vals[lane] += 150.0 * np.sin(np.pi * (t - tc) / 0.3)
            rows.append({"t_perf": t, "event": "", "lane": np.nan,
                         "detail": "", "hand": "both",
                         **{f"fsr{i + 1}": round(v, 1)
                            for i, v in enumerate(vals)}})
            t += 0.005
        for tc, lane, n in cues:
            rows.append({"t_perf": tc, "event": "stim", "lane": lane,
                         "detail": f"trial_id={n}", "hand": "both",
                         **{f"fsr{i + 1}": event_fill for i in range(8)}})
            rows.append({"t_perf": tc + 0.12, "event": "press",
                         "lane": lane, "detail": "", "hand": "both",
                         **{f"fsr{i + 1}": event_fill for i in range(8)}})
        return pd.DataFrame(rows).sort_values("t_perf").reset_index(drop=True)

    def test_peaks_never_read_an_event_row_and_map_lanes_to_pads(self):
        ns = nb()
        peaks = ns.rayan_stim_peaks(self._raw())
        self.assertEqual(len(peaks), 4)
        self.assertFalse((peaks["raw_peak"] >= 9999).any())
        self.assertEqual(list(peaks["trial"]), [1, 2, 3, 4])
        self.assertEqual(list(peaks["sensor"]), ["fsr1", "fsr6", "fsr1",
                                                 "fsr6"])
        self.assertTrue(((peaks["peak_counts"] > 130)
                         & (peaks["peak_counts"] < 170)).all())
        self.assertEqual(ns.lane_side(5, "both"), "left")
        self.assertEqual(ns.lane_side(0, "both"), "right")

    def test_noise_leaves_the_cue_windows_out(self):
        ns = nb()
        noise = ns.rayan_baseline_noise(self._raw())
        sd, n_rest = noise["fsr1"]
        # 14 s at 200 Hz minus four 1.7 s exclusion windows.
        self.assertLess(abs(n_rest - (14.0 - 4 * 1.7) * 200), 12)
        self.assertLess(sd, 2.0)
        sd6, _ = noise["fsr6"]
        self.assertLess(sd6, 2.0)

    def test_baseline_shift_reads_cue_time_levels(self):
        ns = nb()
        ts = np.arange(0, 100, 0.005)
        streams = {"fsr1": 250.0 + ts * 0.5}       # 50 counts over 100 s
        stims = pd.DataFrame({"t_perf": np.arange(1.0, 100.0, 2.0)})
        levels = ns.rayan_stim_levels(ts, streams, stims)
        shift = ns.rayan_baseline_shift(levels)
        # median of the last 20 cues minus the first 20: 2 s apart, so
        # 30 cues of 2 s at 0.5 counts per second.
        self.assertAlmostEqual(shift["fsr1"], 30.0, delta=0.5)
        self.assertTrue(np.isnan(ns.rayan_baseline_shift(
            {"fsr1": np.arange(5.0)})["fsr1"]))

    def test_blocks_map_phase_to_his_block_numbers(self):
        ns = nb()
        rows = []
        k = 0
        for phase, n in (("pretest", 6), ("", 12), ("aftertest", 6)):
            for i in range(n):
                k += 1
                rows.append({"participant": "P1", "game": "g", "mode": "reaction",
                             "trial": k, "phase": phase, "iso_ts": k,
                             "time_difference_ms": 300.0 - i,
                             "had_incorrect_press": False,
                             "keys_pressed": "1", "correct_keys": "1",
                             "finger": "Index", "side": "right"})
        # One RT out of range and one wrong press must drop. Chunks are
        # numbered in logged order BEFORE the filter, as his R builds
        # block100 before the analytic set, so the wrong press (main row
        # 5) thins chunk 1 rather than shifting every later trial back.
        rows[3]["time_difference_ms"] = 1500.0
        rows[10]["keys_pressed"] = "2"
        a = ns.rayan_blocks(pd.DataFrame(rows), chunk=5)
        self.assertEqual(a.groupby("block_all").size().to_dict(),
                         {0: 5, 1: 4, 2: 5, 3: 2, 6: 6})
        self.assertTrue(a.loc[a["block_all"].isin([0, 6]), "is_random"].all())
        self.assertFalse(a.loc[a["block_all"] == 1, "is_random"].any())


# ------------------------------------- end to end on a real session

def _stream_for(folder: Path, rng: random.Random) -> int:
    """Give a keyboard session's raw.csv the 200 Hz sample stream the
    device would have written: each pad at its own rest level with a
    little noise, and the cued pad rising 180 counts around the moment
    the game logged the press. Event rows are kept exactly as the
    engine wrote them (zeros in the fsr cells). Returns the stim count."""
    from finger_rehab.data.logger import RAW_COLUMNS
    raw = pd.read_csv(folder / "raw.csv")
    ev = raw["event"].fillna("").astype(str)
    stims = raw[(ev == "stim") & raw["lane"].notna()].copy()
    trials = pd.read_csv(folder / "trials.csv")
    rt_of = {int(r["trial"]): float(r["time_difference_ms"])
             for _, r in trials.iterrows()
             if pd.notna(r.get("time_difference_ms"))}
    base = [258.0, 262.0, 255.0, 290.0]
    bumps = []
    for _, s in stims.iterrows():
        n = int(str(s["detail"]).split("trial_id=")[-1].split(";")[0])
        rt = rt_of.get(n, 250.0) / 1000.0
        bumps.append((float(s["t_perf"]) + rt - 0.03, int(s["lane"])))
    t0 = float(stims["t_perf"].min()) - 3.0
    t1 = float(stims["t_perf"].max()) + 3.0
    events = [dict(r) for _, r in raw[ev != ""].iterrows()]
    rows = []
    t = t0
    idx = 0
    while t < t1:
        vals = [b + rng.gauss(0.0, 1.2) for b in base]
        for tb, lane in bumps:
            u = t - tb
            if 0.0 <= u < 0.15:
                vals[lane] += 180.0 * np.sin(0.5 * np.pi * u / 0.15)
            elif 0.15 <= u < 0.25:
                vals[lane] += 180.0
            elif 0.25 <= u < 0.45:
                vals[lane] += 180.0 * np.cos(0.5 * np.pi * (u - 0.25) / 0.2)
        idx += 1
        rows.append({"iso_ts": "2026-08-20T10:00:00.000", "t_perf": t,
                     "sample_idx": idx, "hand": "right", "event": "",
                     "lane": "", "detail": "",
                     **{f"fsr{i + 1}": int(round(v)) for i, v in enumerate(vals)},
                     **{f"fsr{i + 5}": 0 for i in range(4)}})
        t += 0.005
    for e in events:
        idx += 1
        e["sample_idx"] = idx
        rows.append(e)
    out = pd.DataFrame(rows).sort_values("t_perf", kind="stable")
    out = out.reindex(columns=RAW_COLUMNS)
    out["lane"] = out["lane"].map(lambda v: "" if pd.isna(v) or v == ""
                                  else str(int(float(v))))
    out.to_csv(folder / "raw.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    return len(stims)


class EndToEndTests(unittest.TestCase):
    """One reaction block the real engine wrote on the keyboard source,
    then the three sections on it through prepare()."""

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
            rng = random.Random(11)
            eng.begin_session("P77", "30", dominant_hand="right", visit="1")
            cls.folder = _play_reaction(eng, "right", 250.0, rng,
                                        n_trials=12)
            eng.end_session()
        finally:
            if eng is not None:
                try:
                    eng._close_loggers()
                except Exception:
                    pass
            pygame.quit()
        cls.root = root
        cls.n_stims = _stream_for(cls.folder, random.Random(5))
        cls.ns = nb()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            cls.ctx = cls.ns.prepare("all", root=root)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_the_engine_left_a_stim_per_trial(self):
        self.assertEqual(self.n_stims, 12)
        self.assertEqual(len(self.ctx["trials"]), 12)

    def test_sensor_section_end_to_end(self):
        ns, ctx = self.ns, self.ctx
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            table = ns.sec_rayan_sensor(ctx["folders"], ctx["calset"])
        self.assertIsNotNone(table)
        self.assertEqual(int(table["presses"].sum()), 12)
        self.assertTrue(set(table["sensor"]) <= {"fsr1", "fsr2", "fsr3",
                                                 "fsr4"})
        self.assertTrue(((table["mean peak (counts)"] > 150)
                         & (table["mean peak (counts)"] < 200)).all())
        self.assertTrue((table["noise sd (counts)"] < 3.0).all())
        self.assertTrue((table["SNR"] > 40).all())
        self.assertTrue((table["baseline shift (counts)"].abs() < 5).all())
        self.assertEqual(int(table["at ADC ceiling"].sum()), 0)
        figs = {p.name for p in ns.FIGDIR.glob("*.png")}
        for name in ("rayan_repeatability.png", "rayan_snr.png",
                     "rayan_cv_heatmap.png"):
            self.assertIn(name, figs)
        self.assertTrue(any(n.startswith("baseline_lookback_zoom_")
                            for n in figs))
        text = buf.getvalue()
        self.assertIn("Baseline shift", text)
        self.assertNotIn("Left against right", text)

    def test_trial_peaks_section_end_to_end(self):
        ns, ctx = self.ns, self.ctx
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            wide = ns.sec_rayan_trial_peaks(ctx["folders"], ctx["trials"])
        self.assertIsNotNone(wide)
        self.assertEqual(len(wide), 12)
        self.assertTrue(((wide["on_target"] > 150)
                         & (wide["on_target"] < 200)).all())
        self.assertTrue((wide["off_share"] < 0.15).all())
        self.assertEqual(set(wide["block"]), {"main 1"})
        # The heatmap and the panels are per HAND, not pooled: pivoting
        # on the finger alone put lane 0 and lane 4 in one row, so a
        # both-hands session averaged its two hands into one cell.
        self.assertIn("side", wide.columns)
        self.assertEqual(set(wide["side"]), {"right"})
        figs = {p.name for p in ns.FIGDIR.glob("*.png")}
        self.assertIn("rayan_finger_block_heatmap_right.png", figs)
        self.assertNotIn("rayan_finger_block_heatmap.png", figs)
        self.assertTrue(any(n.startswith("rayan_trial_peaks_right_")
                            for n in figs))

    def test_blocks_section_says_why_one_chunk_is_not_enough(self):
        ns, ctx = self.ns, self.ctx
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out = ns.sec_rayan_blocks(ctx["trials"])
        self.assertIsNone(out)
        self.assertIn("chunks of 100", buf.getvalue())

    def test_no_participant_name_reaches_a_figure_name(self):
        for p in self.ns.FIGDIR.glob("*.png"):
            self.assertNotIn("P77", p.name)


if __name__ == "__main__":
    unittest.main()
