"""The lab's SRT after the deep research of 1 October 2026.

The Lab session plays the SRT first in both orders, with the script's
own display and a response byte per trial; the true press-to-flash
interval is logged; the setup screen names no sequence; the timing
check reads intervals after an answered trial; the notebook reads a
reversal-free and a reweighted effect, a per-person interval, the
anticipations against chance and the spoken answer about the order;
and a light-sensor recording gives the flash and tone delays.
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from tests.test_srt_mode import FRAME, Sim, _engine, _fast_cfg, _use  # noqa: E402

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent


def _session(root: Path, respond, group="constant", **srt):
    """One short SRT block played on the 60 Hz flip clock; returns the
    engine and its block folder."""
    _use(root, group, 500)
    eng = _engine(root, **{**_fast_cfg(), **srt})
    eng.set_hand_mode("right")
    eng.begin_srt_block()
    sim = Sim(eng)
    sim.run(respond)
    return eng, Path(eng.last_session_root)


def _rows(folder: Path) -> list[dict]:
    import csv
    perf = [p for p in folder.iterdir() if p.name.startswith("SRT_P09_")]
    return list(csv.DictReader(perf[0].open(encoding="utf-8")))


def _write_bdf(path: Path, chans: dict, rate: int) -> None:
    """A BioSemi BDF file of one-second records, 24-bit samples."""
    names = list(chans)
    ns = len(names)
    n_rec = len(chans[names[0]]) // rate

    def f(value, width):
        return str(value).ljust(width)[:width].encode("ascii")
    head = (b"\xffBIOSEMI" + f("", 80) + f("", 80) + f("01.10.26", 8)
            + f("10.00.00", 8) + f(256 * (ns + 1), 8) + f("24BIT", 44)
            + f(n_rec, 8) + f(1, 8) + f(ns, 4))
    sig = (b"".join(f(n, 16) for n in names) + f("", 80) * ns
           + f("", 8) * ns + f(-1, 8) * ns + f(1, 8) * ns
           + f(-8388608, 8) * ns + f(8388607, 8) * ns + f("", 80) * ns
           + f(rate, 8) * ns + f("", 32) * ns)
    body = bytearray()
    for r in range(n_rec):
        for name in names:
            v = np.asarray(chans[name][r * rate:(r + 1) * rate],
                           dtype=np.int64) & 0xFFFFFF
            b = np.stack([v & 0xFF, (v >> 8) & 0xFF, (v >> 16) & 0xFF],
                         axis=1).astype(np.uint8)
            body += b.tobytes()
    path.write_bytes(head + sig + bytes(body))


class LabSessionTests(unittest.TestCase):

    def _plan(self, code, lab=True):
        from finger_rehab.config import Config
        from finger_rehab.game.battery import build_plan
        cfg = (Config.load(APP / "config" / "eeg_lab.yaml") if lab
               else Config.load())
        return build_plan(cfg, code, "right")

    def test_the_srt_opens_the_lab_session_in_both_orders(self):
        for code in ("P001", "P002"):
            with self.subTest(code=code):
                plan = self._plan(code)
                self.assertEqual(plan.steps[0].mode, "srt")
                self.assertEqual(plan.steps[0].rest_before_s, 0.0)
                self.assertEqual([s.position for s in plan.steps],
                                 list(range(1, len(plan.steps) + 1)))
                rests = [s for s in plan.steps if s.rest_before_s > 0]
                self.assertEqual(len(rests), 1)

    def test_the_rest_of_the_order_is_unchanged(self):
        from finger_rehab.game.battery import move_first
        lab = self._plan("P002")
        before = [s.mode for s in lab.steps[1:]]
        again = move_first(lab.steps, ["srt"])
        self.assertEqual([s.mode for s in again[1:]], before)

    def test_the_lab_build_draws_the_scripts_display_and_marks_responses(self):
        from finger_rehab.config import Config
        lab = Config.load(APP / "config" / "eeg_lab.yaml")
        self.assertEqual(lab.get("srt.look"), "lab")
        self.assertIs(lab.get("srt.response_markers"), True)
        home = Config.load()
        self.assertEqual(home.get("srt.look"), "app")
        self.assertIs(home.get("srt.photodiode_patch"), False)
        self.assertIs(home.get("srt.response_markers"), False)


class LabLookTests(unittest.TestCase):

    def setUp(self):
        pygame.init()
        self.td = tempfile.TemporaryDirectory()
        _use(Path(self.td.name))

    def tearDown(self):
        self.td.cleanup()
        pygame.quit()

    def _run(self, **srt):
        eng = _engine(Path(self.td.name), **{**_fast_cfg(), **srt})
        eng.set_hand_mode("right")
        eng.begin_srt_block()
        self.addCleanup(eng._abandon_if_in_block)
        sim = Sim(eng)
        sim.key(pygame.K_SPACE)
        sim.frame()
        sim.key(pygame.K_SPACE)
        sim.frame()
        while sim.mode.flash_square is None:
            sim.frame()
        return eng, eng._screens["srt"], sim

    def test_the_scripts_squares_on_a_black_page(self):
        eng, sc, _sim = self._run(look="lab")
        rects = sc.lane_rects(eng.mode)
        self.assertEqual([r.centerx for r in rects], [496, 592, 688, 784])
        self.assertEqual({r.centery for r in rects}, {400})
        self.assertEqual({(r.w, r.h) for r in rects}, {(83, 52)})
        surf = pygame.Surface((1280, 800))
        sc.draw(surf)
        self.assertEqual(tuple(surf.get_at((4, 4)))[:3], (0, 0, 0))
        lit = eng.mode.flash_square
        for i, r in enumerate(rects):
            want = (255, 0, 0) if i + 1 == lit else (128, 128, 128)
            self.assertEqual(tuple(surf.get_at(r.center))[:3], want)

    def test_the_light_sensor_patch_shows_on_flash_frames_only(self):
        eng, sc, sim = self._run(look="lab", photodiode_patch=True)
        surf = pygame.Surface((1280, 800))
        sc.draw(surf)
        self.assertEqual(tuple(surf.get_at((10, 790)))[:3], (255, 255, 255))
        while eng.mode.flash_square is not None:
            sim.frame()
        sc.draw(surf)
        self.assertEqual(tuple(surf.get_at((10, 790)))[:3], (0, 0, 0))

    def test_no_patch_unless_asked(self):
        eng, sc, _sim = self._run(look="lab")
        surf = pygame.Surface((1280, 800))
        sc.draw(surf)
        self.assertEqual(tuple(surf.get_at((10, 790)))[:3], (0, 0, 0))

    def test_a_click_on_a_lab_square_enters_it(self):
        eng, sc, _sim = self._run(look="lab")
        m = eng.mode
        m.step_i = next(i for i, s in enumerate(m.steps)
                        if s.kind == "recall")
        rect = sc.lane_rects(m, recall=True)[1]
        sc.handle_event(pygame.event.Event(
            pygame.MOUSEBUTTONDOWN, {"button": 1, "pos": rect.center}))
        self.assertEqual(m.recalled, [2])


class PressToFlashTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        pygame.init()
        cls.td = tempfile.TemporaryDirectory()
        cls.eng, cls.folder = _session(
            Path(cls.td.name), lambda sim, tr: (0.35, tr.square))
        cls.rows = _rows(cls.folder)

    @classmethod
    def tearDownClass(cls):
        cls.td.cleanup()
        pygame.quit()

    def test_the_interval_as_lived_is_logged(self):
        vals = [float(r["press_to_flash_ms"]) for r in self.rows
                if r["phase"] == "learning" and r["press_to_flash_ms"]]
        self.assertTrue(vals)
        # 500 ms nominal, one frame, and the press to the frame that
        # ended its trial: about 517 to 550 ms at 60 Hz.
        self.assertGreaterEqual(min(vals), 500 + FRAME * 1000 - 0.5)
        self.assertLessEqual(max(vals), 500 + 3 * FRAME * 1000 + 0.5)

    def test_blank_on_a_blocks_first_trial(self):
        for r in self.rows:
            if r["trial"] == "1":
                self.assertEqual(r["press_to_flash_ms"], "")

    def test_the_summary_carries_it_and_the_display(self):
        st = self.eng.mode.block_stats()
        self.assertGreater(st["press_to_flash_median_ms"], 500)
        self.assertEqual(st["look"], "app")
        self.assertIn(st["vsync"], (None, True, False))


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def test_the_lab_sequence_positions_two_squares_fix(self):
        self.assertEqual(self.ra.srt_predictable_positions(
            [1, 3, 2, 1, 4, 3, 2, 4, 1, 3]), {2, 5, 6, 7, 9, 10})

    def test_reversals_are_found_within_a_block(self):
        import pandas as pd
        g = pd.DataFrame({"game": "g", "phase": "learning",
                          "block": [1] * 5 + [2] * 3,
                          "target_lane": list("vbvnm") + list("vbv")})
        self.assertEqual(list(self.ra._srt_reversal(g)),
                         [False, False, True, False, False,
                          False, False, True])

    def test_the_recall_chance_is_the_checked_one(self):
        self.assertEqual(self.ra.SRT_RECALL_CHANCE["longest_run"],
                         (3.46, 5.0))

    def test_one_persons_interval_holds_the_difference(self):
        rng = np.random.default_rng(1)
        post = rng.normal(440, 60, 44)
        last = rng.normal(400, 60, 92)
        lo, hi = self.ra._srt_boot_effect(post, last, n=2000)
        d = np.median(post) - np.median(last)
        self.assertLess(lo, d)
        self.assertGreater(hi, d)

    def test_the_fast_mode_boundary(self):
        rng = np.random.default_rng(2)
        rts = np.concatenate([np.exp(rng.normal(np.log(120), 0.2, 120)),
                              np.exp(rng.normal(np.log(420), 0.2, 880))])
        cut = self.ra._srt_fast_cut(rts)
        self.assertTrue(150 < cut < 260, cut)
        one = np.exp(rng.normal(np.log(420), 0.2, 1000))
        self.assertTrue(np.isnan(self.ra._srt_fast_cut(one)))

    def test_the_timing_check_reads_the_interval_after_an_answer(self):
        import pandas as pd
        rows = []
        for i in range(1, 9):
            acc = "miss" if i == 4 else "correct"
            extra = 16.7 + (200 if i == 5 else 0)
            rows.append({"game": "g", "phase": "learning", "block": 1,
                         "trial": i, "accuracy": acc,
                         "isi_before_ms": "" if i == 1 else 500,
                         "rsi_ms": 1000 if i == 1 else 500 + extra,
                         "monitor_hz": 60,
                         "press_to_flash_ms": "" if i in (1, 5) else 535})
        out = self.ra.srt_timing_check(
            pd.DataFrame(rows),
            {"g": {"block_summary": {"srt": {"vsync": True}}}})
        self.assertEqual(int(out.loc[0, "late_trials"]), 0)
        self.assertEqual(int(out.loc[0, "trials"]), 6)
        self.assertAlmostEqual(out.loc[0, "press_to_flash_ms"], 535)
        self.assertEqual(out.loc[0, "vsync"], "yes")

    def test_rayan_blocks_leave_out_each_blocks_first_trial(self):
        import pandas as pd
        f = pd.DataFrame({"participant": "P1", "setup": "lab",
                          "phase": ["learning"] * 3, "block": [1, 1, 1],
                          "trial": [1, 2, 3],
                          "accuracy": ["correct"] * 3,
                          "rt_ms": [400, 410, 420], "flag": ""})
        a = self.ra.srt_rayan_blocks(f)
        self.assertEqual(list(a["time_difference_ms"]), [410, 420])

    def test_the_spoken_answer_is_read_from_the_intake_sheet(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            game = root / "2026-10-01" / "P09_101010_srt"
            game.mkdir(parents=True)
            (root / "intake_sheet.csv").write_text(
                "participant,edinburgh_lq,srt_noticed,srt_report\n"
                "P09,80,yes,the lights went round in a loop\n")
            got = self.ra.srt_awareness([game])
        self.assertEqual(got["P09"],
                         ("yes", "the lights went round in a loop"))

    def test_the_chapter_runs_on_a_played_block(self):
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                rng = np.random.default_rng(3)

                def respond(sim, tr):
                    return (float(rng.uniform(0.30, 0.45)), tr.square)
                _eng, folder = _session(Path(td), respond)
                out = self.ra.sec_srt([folder])
        finally:
            pygame.quit()
        per = out["per_session"]
        for col in ("sequence_effect_norev_ms",
                    "sequence_effect_reweighted_ms",
                    "sequence_effect_lo_ms", "anticipation_rate_post",
                    "fast_share_learn", "late_pred2_ms"):
            self.assertIn(col, per.columns)
        self.assertLessEqual(per.loc[0, "sequence_effect_lo_ms"],
                             per.loc[0, "sequence_effect_ms"])

    def test_the_flash_and_tone_delays_from_a_bdf(self):
        rate = 2048
        n = rate * 3
        status = np.full(n, 0x110000, dtype=np.int64)
        light = np.full(n, 1000, dtype=np.int64)
        rng = np.random.default_rng(5)
        sound = rng.integers(-3, 4, n).astype(np.int64)
        for m in (1000, 3500):
            status[m:m + 20] |= 30
            light[m + 41:m + 300] = 5000
            t = np.arange(400) / rate
            sound[m + 25:m + 425] += (2000 * np.sin(2 * np.pi * 700 * t)
                                      ).astype(np.int64)
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "timing.bdf"
            _write_bdf(path, {"Erg1": light, "Erg2": sound,
                              "Status": status}, rate)
            out = self.ra.srt_stimulus_timing(path, "Erg1", "Erg2")
        self.assertEqual(len(out), 2)
        for v in out["light_ms"]:
            self.assertAlmostEqual(v, 41 / rate * 1000, delta=0.6)
        for v in out["sound_ms"]:
            self.assertAlmostEqual(v, 26 / rate * 1000, delta=1.0)

    def test_the_claims_are_corrected(self):
        limits = " ".join(self.ra.MODE_CLAIM_LIMITS["srt"])
        self.assertIn("call it sequence learning", limits)
        self.assertIn("srt.look: lab", limits)
        self.assertIn("One EEG session is one person", limits)
        doc = self.ra.sec_srt.__doc__
        self.assertIn("this project's rule, not the lab's", doc)
        self.assertNotIn("35 to 110 ms", doc)


class WordingTests(unittest.TestCase):

    def test_the_setup_screen_names_no_sequence(self):
        from finger_rehab.ui.srt_setup_screen import group_line
        line = group_line("cyclical", 500)
        self.assertEqual(line,
                         "Gaps of 250, 500 and 750 ms in a fixed repeating "
                         "order.")
        text = (APP / "finger_rehab" / "ui" / "srt_setup_screen.py") \
            .read_text(encoding="utf-8")
        self.assertIn("block and one question.", text)
        self.assertNotIn("learning blocks, a final", text)

    def test_the_mode_says_what_the_evidence_supports(self):
        text = (APP / "finger_rehab" / "game" / "modes" / "srt.py") \
            .read_text(encoding="utf-8")
        self.assertIn("press_to_flash_ms", text)
        self.assertNotIn("location tones improve learning on\nthis task",
                         text)
        self.assertIn("The timing groups and the musical experience "
                      "question\nare the script's own.", text)
        setup = (APP / "finger_rehab" / "game" / "srt_setup.py") \
            .read_text(encoding="utf-8")
        self.assertIn("Shin and Ivry 2002", setup)

    def test_the_lab_procedure_times_the_screen_and_asks_about_the_order(self):
        guide = " ".join((APP / "docs" / "eeg_lab_setup.txt").read_text(
            encoding="utf-8").split())
        self.assertIn("srt.photodiode_patch: true", guide)
        self.assertIn("Did you notice anything about the order of the lit "
                      "cards?", guide)
        self.assertIn("8 to 17 ms at 60 Hz", guide)
        readme = (REPO / "EEG_Lab" / "README.md").read_text(encoding="utf-8")
        self.assertIn("light sensor", readme)
        tpl = (APP / "docs" / "study_day" / "intake_sheet_template.csv") \
            .read_text(encoding="utf-8").strip().split(",")
        self.assertIn("srt_noticed", tpl)
        self.assertIn("srt_report", tpl)

    def test_the_deep_review_is_filed(self):
        self.assertTrue((APP / "docs" / "research" / "deep" / "srt.md")
                        .is_file())
        index = (APP / "docs" / "research" / "deep" / "README.md") \
            .read_text(encoding="utf-8")
        self.assertIn("(srt.md)", index)


if __name__ == "__main__":
    unittest.main()
