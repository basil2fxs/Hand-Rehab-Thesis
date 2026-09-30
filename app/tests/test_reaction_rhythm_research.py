"""Reaction and Rhythm after the deep research of 30 September to
1 October 2026, before any participant.

Reaction: R1 is one-sided. With catch trials in the design the chance
the light comes next falls over the wait, and RT rises a little with it
(Han and Proctor 2022), so only a falling RT means the wait was timed;
the old two-sided rule failed 78 percent of simulated cohorts at +10 ms
a second. The pooled slope of RT on the wait prints beside it, R3 says
how often a true zero shift could pass, and a sensitivity block adds
the rows the research asked for. The game itself is unchanged.

Rhythm: Rh1 is now the share of presses later than +150 ms, where a
reaction to the buzz lands; the mean asynchrony is reported as an
estimate. Only blocks on measured delays, with the buzz on the beat and
no pause, feed Rh1 and Rh2. The study chart is a frozen file whose
notes sit on the music's attacks, each row carries its note's time,
the NEXT UP card warns before a Rhythm step on unmeasured delays, and
the study block shows no streak banners.
"""
from __future__ import annotations

import contextlib
import csv
import io
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

TRACK = ROOT / "assets" / "music" / "Easy_Lemon.mp3"
CHART = ROOT / "assets" / "charts" / "Easy_Lemon_medium.json"


def _nb():
    import matplotlib
    matplotlib.use("Agg")
    from tests.test_cohort_notebook import _load_notebook
    return _load_notebook()


def _long(mode, metric_values, role="dominant"):
    rows = []
    for i, vals in enumerate(metric_values):
        for metric, val in vals.items():
            rows.append(dict(participant=f"P{i + 1:02d}", phase="pass1",
                             position=1, visit="1", day="d", hand="right",
                             hand_role=role, mode=mode, metric=metric,
                             value=val, n_trials=20, block_folder="x",
                             config_hash="h"))
    return pd.DataFrame(rows)


def _cohort(long, **extra):
    c = {"long": long, "min_n": 3, "frames": {}, "people": pd.DataFrame(),
         "sel": pd.DataFrame(), "trials": pd.DataFrame(), "metas": {},
         "dropped": {}, "tables": {}}
    c.update(extra)
    return c


class ReactionR1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ra = _nb()

    def _r1(self, rhos):
        long = _long("reaction", [{"rho_rt_vs_fp": r,
                                   "false_start_rate": 0.02} for r in rhos])
        with contextlib.redirect_stdout(io.StringIO()):
            v = self.ra.sec_cohort_validity(_cohort(long), None)
        return v[v["id"] == "R1"].iloc[0]

    def test_a_rise_with_the_wait_passes(self):
        row = self._r1([0.22, 0.30, 0.18, 0.25, 0.27, 0.31, 0.20, 0.24])
        self.assertEqual(row["verdict"], "pass")
        self.assertEqual(row["criterion"],
                         "median rho > -0.2 and false starts < 10%")

    def test_a_fall_with_the_wait_fails(self):
        row = self._r1([-0.22, -0.30, -0.18, -0.25, -0.27, -0.31, -0.20])
        self.assertEqual(row["verdict"], "fail")

    def test_the_pooled_slope_recovers_a_known_rise(self):
        rng = np.random.default_rng(3)
        rows = []
        for p in range(6):
            base = 380.0 + rng.normal(0, 30)
            for k in range(30):
                fp = 1.5 + rng.exponential(2.5)
                rows.append({"mode": "reaction", "participant": f"P{p}",
                             "game": f"g{p}", "phase": "pass1",
                             "stimulus": f"choice;fp={fp:.3f}",
                             "time_difference_ms": base + 10.0 * fp
                             + rng.normal(0, 25),
                             "early_late": "Good", "error_type": ""})
        text = self.ra.reaction_wait_slope(pd.DataFrame(rows), "pass1")
        est = float(text.split("wait ")[1].split(" ms")[0])
        self.assertAlmostEqual(est, 10.0, delta=4.0)
        self.assertIn("expected with catch trials", text)

    def test_the_zero_shift_pass_rate(self):
        f = self.ra._tost_pass_at_zero
        self.assertGreater(f(5.0, 40, 20.0), 0.99)
        mid = f(20.0, 10, 20.0)
        self.assertGreater(mid, 0.3)
        self.assertLess(mid, 0.95)
        self.assertEqual(f(80.0, 4, 20.0), 0.0)
        self.assertTrue(np.isnan(f(np.nan, 10, 20.0)))


class ReactionSensitivityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ra = _nb()

    def test_the_rows_count_what_they_say(self):
        rows = []
        for k in range(20):
            rows.append({"mode": "reaction", "game": "g1", "participant": "P1",
                         "stimulus": "choice;fp=2.000"
                         + (";co_press=2" if k == 5 else ""),
                         "time_difference_ms": 300.0 + 10 * k,
                         "early_late": "Good", "error_type": "",
                         "loud_trial": "TRUE" if k % 10 == 0 else "FALSE",
                         "keys_pressed": "2", "correct_keys": "2"})
        # Two wrong fingers, one and three away; one very slow press.
        rows.append({"mode": "reaction", "game": "g1", "participant": "P1",
                     "stimulus": "choice;fp=2.000", "time_difference_ms": 180.0,
                     "early_late": "Miss", "error_type": "wrong_finger",
                     "keys_pressed": "2", "correct_keys": "1"})
        rows.append({"mode": "reaction", "game": "g1", "participant": "P1",
                     "stimulus": "choice;fp=2.000", "time_difference_ms": 190.0,
                     "early_late": "Miss", "error_type": "wrong_finger",
                     "keys_pressed": "4", "correct_keys": "1"})
        rows.append({"mode": "reaction", "game": "g1", "participant": "P1",
                     "stimulus": "choice;fp=2.000", "time_difference_ms": 1200.0,
                     "early_late": "Good", "error_type": ""})
        rx = self.ra.reaction_frame(pd.DataFrame(rows))
        sens = self.ra.reaction_sensitivity(rx)
        self.assertEqual(sens["wrong_by_distance"], {1: 1, 3: 1})
        self.assertAlmostEqual(sens["co_press_share"], 1 / 21)
        # 1200 ms is over twice the block median (about 410 ms).
        self.assertAlmostEqual(sens["lapse_2x_rate"], 1 / 23)
        self.assertGreater(sens["median_rt_ms_ex_first4"],
                           sens["median_rt_ms"] - 1)
        caf = sens["caf"].set_index("rt_ms")
        self.assertEqual(caf.loc["150 to 200", "accuracy"], 0.0)
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            self.ra._print_reaction_sensitivity(sens)
        self.assertIn("wrong presses by distance", buf.getvalue())


class RhythmRh1Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ra = _nb()

    def test_rh1_is_the_late_share_and_the_mean_is_reported(self):
        vals = [{"late_share": s, "asyn_mean_ms": m, "asyn_sd_ms": 35.0}
                for s, m in ((0.0, -12.0), (0.01, 5.0), (0.02, -20.0),
                             (0.0, 3.0), (0.03, -8.0), (0.01, 0.0),
                             (0.0, -15.0), (0.02, 10.0))]
        long = _long("rhythm", vals)
        with contextlib.redirect_stdout(io.StringIO()):
            v = self.ra.sec_cohort_validity(_cohort(long), None)
        # The dominant hand's rows come first; this cohort has no other.
        rh1 = v[v["id"] == "Rh1"].iloc[0]
        rh1m = v[v["id"] == "Rh1m"].iloc[0]
        self.assertIn("anticipate", rh1["check"])
        self.assertEqual(rh1["family"], "pre-specified")
        self.assertIn(rh1["verdict"], ("pass", "direction only"))
        self.assertEqual(rh1m["verdict"], "reported")
        self.assertEqual(rh1m["family"], "exploratory")
        self.assertIn("Dalla Bella", rh1m["detail"])

    def test_a_reacting_cohort_fails_rh1(self):
        vals = [{"late_share": s, "asyn_mean_ms": 190.0}
                for s in (0.6, 0.7, 0.8, 0.5, 0.9, 0.65)]
        long = _long("rhythm", vals)
        with contextlib.redirect_stdout(io.StringIO()):
            v = self.ra.sec_cohort_validity(_cohort(long), None)
        self.assertEqual(v[v["id"] == "Rh1"].iloc[0]["verdict"], "fail")

    def test_which_blocks_may_feed_rh1_and_rh2(self):
        f = self.ra.rhythm_block_problem
        ok = {"config_snapshot": {"latency": {"measured": True}},
              "block_summary": {"tactile_cue": {"mode": "on_beat"},
                                "pauses": 0}}
        self.assertEqual(f(ok), "")
        self.assertEqual(f({}), "")
        self.assertIn("not measured", f(
            {"config_snapshot": {"latency": {"measured": False}}}))
        self.assertIn("lead", f({"block_summary": {"tactile_cue":
                                                   {"mode": "lead"}}}))
        self.assertEqual(f({"block_summary": {"pauses": 2}}), "paused")

    def test_unmeasured_blocks_leave_rh1(self):
        ra = self.ra
        folders = [f"/s/d/P{i + 1:02d}_rhythm" for i in range(4)]
        sel = pd.DataFrame({"participant": [f"P{i + 1:02d}" for i in range(4)],
                            "mode": "rhythm", "folder": folders})
        metas = {ra.game_key(f): {"config_snapshot": {"latency": {
            "measured": i != 0}}} for i, f in enumerate(folders)}
        keep, out = ra.rhythm_registered_people(
            {"sel": sel, "metas": metas})
        self.assertEqual(keep, {"P02", "P03", "P04"})
        self.assertIn("not measured", out["P01"][0])

    def test_the_note_time_rebuilds_press_and_note(self):
        rows = pd.DataFrame({"stimulus": ["note;t=2.000", "note;t=1.000"],
                             "time_difference_ms": [20.0, -10.0],
                             "song_time_s": [9.0, 9.5]})
        press, note = self.ra.tap_series(rows)
        np.testing.assert_allclose(note, [1.0, 2.0])
        np.testing.assert_allclose(press, [0.99, 2.02])


class FrozenChartTests(unittest.TestCase):

    def test_the_chart_is_the_studys_on_the_attacks(self):
        from finger_rehab.audio.beatmap import chart_sha, study_chart
        raw = json.loads(CHART.read_text(encoding="utf-8"))
        self.assertEqual(raw["n_notes"], 107)
        self.assertEqual(len(raw["notes"]), 107)
        lags = [n["attack_lag_ms"] for n in raw["notes"]]
        # The research's numbers: a median 36.9 ms, 90 on the beat.
        self.assertAlmostEqual(float(np.median(lags)), 36.9, delta=0.5)
        self.assertEqual(sum(n["beat"] == "on" for n in raw["notes"]), 90)
        for n in raw["notes"]:
            self.assertAlmostEqual(n["t"], n["t_tracker"]
                                   - n["attack_lag_ms"] / 1000.0, places=3)
        bm = study_chart(TRACK, "medium", 4)
        self.assertIsNotNone(bm)
        self.assertEqual(bm.chart["source"], "frozen")
        self.assertEqual(bm.chart["sha"], chart_sha(raw["notes"]))
        self.assertEqual(bm.song, str(TRACK))
        self.assertIsNone(study_chart(TRACK, "medium", 8))
        self.assertIsNone(study_chart(TRACK, "hard", 4))

    def test_another_mp3_is_refused(self):
        from finger_rehab.audio.beatmap import study_chart
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "Easy_Lemon.mp3"
            fake.write_bytes(b"not the song")
            self.assertIsNone(study_chart(fake, "medium", 4))


def _engine(root: Path, measured: bool):
    import pygame
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    pygame.init()
    pygame.display.set_mode((1280, 800))
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["session"]["data_dir"] = str(root / "sessions")
    cfg.data["session"]["calibration_dir"] = str(root / "cal")
    cfg.data["audio"]["enabled"] = False
    cfg.data["report"] = {"enabled": False}
    cfg.data["eeg"] = {"enabled": False}
    cfg.data["game"]["start_countdown_s"] = 0
    cfg.data.setdefault("quick_cal", {})["enabled"] = False
    cfg.data.setdefault("serial", {})["watch_ports"] = False
    cfg.data.setdefault("latency", {})["measured"] = measured
    eng = GameEngine(cfg, KeyboardOnlySource(cfg))
    eng._screens = eng._build_screens()
    eng.begin_session("P31", "30", dominant_hand="right", visit="1")
    eng._uncal_ack = {"left", "right"}
    return eng


class RhythmEngineTests(unittest.TestCase):

    def test_the_battery_step_plays_the_frozen_chart_and_logs_note_times(self):
        import pygame
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(Path(td), measured=True)
            try:
                eng._begin_protocol_rhythm({"mode": "rhythm", "hand": "right",
                                            "track": TRACK.name,
                                            "difficulty": "medium"})
                mode = eng.mode
                self.assertEqual(mode.beatmap.chart["source"], "frozen")
                raw = json.loads(CHART.read_text(encoding="utf-8"))
                first = raw["notes"][0]["t"]
                lead = float(mode._pre_song_lead_s)
                self.assertAlmostEqual(mode.beatmap.notes[0].t, first + lead,
                                       places=4)
                sched = mode.schedule[0] if hasattr(mode, "schedule") else None
                if sched is None:
                    from types import SimpleNamespace
                    sched = SimpleNamespace(index=0,
                                            note=mode.beatmap.notes[0],
                                            stim_t_perf=None)
                eng.log_rhythm_hit(sched, 12.0, "Perfect", 10, 0.0,
                                   was_pressed=True)
                folder = Path(eng.trial_logger.path).parent
                eng.finish_block()
            finally:
                eng._close_loggers()
                pygame.quit()
            with (folder / "trials.csv").open(encoding="utf-8") as f:
                row = next(csv.DictReader(f))
            self.assertEqual(row["stimulus"], f"note;t={first:.3f}")
            meta = json.loads((folder / "metadata.json").read_text())
            chart = meta["block_summary"]["song"]["chart"]
            self.assertEqual(chart["source"], "frozen")
            self.assertEqual(chart["file"], CHART.name)

    def test_next_up_warns_before_rhythm_on_unmeasured_delays(self):
        import pygame
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as td:
            for measured, want in ((False, "Audio delay"), (True, "")):
                eng = _engine(Path(td), measured=measured)
                try:
                    with patch.object(eng, "pending_protocol_step",
                                      return_value={"mode": "rhythm"}):
                        self.assertTrue(eng.battery_step_note()
                                        .startswith(want) if want else
                                        eng.battery_step_note() == "")
                    with patch.object(eng, "pending_protocol_step",
                                      return_value={"mode": "echo"}):
                        self.assertEqual(eng.battery_step_note(), "")
                finally:
                    eng._close_loggers()
                    pygame.quit()

    def test_no_streak_banner_in_the_study_block(self):
        import pygame
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(Path(td), measured=True)
            try:
                seen = []
                eng._screens["rhythm"].add_encouragement = seen.append
                eng.current_block = "rhythm"
                eng._streak_fired = set()
                eng._protocol_active = True
                eng.hit_streak = 9
                eng._update_streak(True, "rhythm")
                self.assertEqual(seen, [])
                eng._protocol_active = False
                eng._streak_fired = set()
                eng.hit_streak = 9
                eng._update_streak(True, "rhythm")
                self.assertEqual(len(seen), 1)
            finally:
                eng._close_loggers()
                pygame.quit()

    def test_the_get_ready_card_says_what_to_do(self):
        from finger_rehab.ui.screens import RhythmScreen
        text = " ".join(RhythmScreen.GET_READY_LINES)
        self.assertIn("ring", text)
        self.assertIn("buzz", text)


class CheckSittingChartTests(unittest.TestCase):

    def _check(self, chart, pauses=0):
        from tests.test_check_sitting import write_sitting
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import check_sitting as cs
        finally:
            sys.path.remove(str(ROOT / "scripts"))
        with tempfile.TemporaryDirectory() as td:
            write_sitting(Path(td))
            for meta_p in Path(td).glob("*/*_rhythm/metadata.json"):
                meta = json.loads(meta_p.read_text())
                meta["block_summary"]["song"] = {"chart": chart}
                meta["block_summary"]["pauses"] = pauses
                meta_p.write_text(json.dumps(meta))
            rows = cs.games(Path(td), None)
            return [line for ok, line in cs.check_code("P01", rows)
                    if not ok]

    def test_a_block_on_another_chart_is_flagged(self):
        from finger_rehab.audio.beatmap import chart_sha
        raw = json.loads(CHART.read_text(encoding="utf-8"))
        good = {"source": "frozen", "file": CHART.name,
                "sha": chart_sha(raw["notes"])}
        self.assertFalse([b for b in self._check(good) if "chart" in b])
        bad = self._check({"source": "extracted", "sha": "0" * 16})
        self.assertEqual(sum("did not play the study chart" in b
                             for b in bad), 2)
        paused = self._check(good, pauses=1)
        self.assertEqual(sum("paused" in b for b in paused), 2)

    def test_the_sitting_check_knows_the_study_chart(self):
        sys.path.insert(0, str(ROOT / "scripts"))
        try:
            import check_sitting
        finally:
            sys.path.remove(str(ROOT / "scripts"))
        from finger_rehab.audio.beatmap import chart_sha
        raw = json.loads(CHART.read_text(encoding="utf-8"))
        self.assertEqual(check_sitting._study_chart_sha(),
                         chart_sha(raw["notes"]))


if __name__ == "__main__":
    unittest.main()
