"""Syllables after the deep research of 1 October 2026.

The case sitting opens with a fixed probe, the same sets in the same
order every session, which never adapts, prompts or tells the reader
how an answer went, and half its words never come up in training; the
buzz's floor reads a censored median, so a slow reader is not
undercut; each set row says whether its syllable is heard with a weak
vowel and when the buzz was due; the block records its seed and its
voice; 6 to 9 plays 20 words and every quick look 20 trials; the adult
fall moves on hear-and-pick sets only; the results line reads the
unaided rate; the recording kit runs a listening check; and the
notebook reads speed apart from accuracy, the probe across sessions
and the corrected sources.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_syllables_mode import _build_mode, _press  # noqa: E402

APP = Path(__file__).resolve().parents[1]
PROBE = APP / "assets" / "words" / "syllables_probe.json"


def _sectioned(age_band="6-9", **over):
    over.setdefault("words_total", 12)
    return _build_mode(age_band=age_band, sections=True, **over)


def _tick_until(m, t, pred, step=0.05, limit=40000):
    for _ in range(limit):
        if pred(m):
            return t
        m._tick(t)
        t += step
    raise AssertionError(f"never reached, at {m.phase}")


def _probe_open(m):
    return (m.phase == "probe" and m.probe_options is not None
            and m._set_close_t is None)


class ProbeFileTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.data = json.loads(PROBE.read_text(encoding="utf-8"))

    def test_the_file_is_what_the_builder_makes(self):
        out = subprocess.run(
            [sys.executable, str(APP / "scripts" / "build_syllables_probe.py"),
             "--check"], capture_output=True, text=True)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)

    def test_every_set_has_one_answer_and_one_near_foil(self):
        from finger_rehab.game.modes.syllables_foils import FAMILY_KIND
        for group, items in self.data["item_sets"].items():
            for it in items:
                texts = [o["text"] for o in it["options"]]
                self.assertEqual(texts.count(it["syl"]), 1, it["word"])
                kinds = sorted(o["kind"] for o in it["options"])
                self.assertEqual(kinds, sorted(["target", "F1", "F1",
                                                FAMILY_KIND[it["family"]]]))
                self.assertEqual(it["options"][it["tlane"]]["kind"],
                                 "target")
                if it["family"] == "vowel":
                    self.assertEqual(it["weak"], 0)

    def test_families_lanes_and_held_out_words_are_balanced(self):
        for group, items in self.data["item_sets"].items():
            fams = Counter(it["family"] for it in items)
            self.assertEqual(len(set(fams.values())), 1, group)
            lanes = Counter(it["tlane"] for it in items)
            self.assertLessEqual(max(lanes.values()) - min(lanes.values()),
                                 1, group)
            held = sum(1 for it in items if it["held_out"])
            self.assertLessEqual(abs(2 * held - len(items)), 2, group)
            self.assertEqual(len({it["word"] for it in items}), len(items))
            self.assertTrue(all(a["family"] != b["family"]
                                for a, b in zip(items, items[1:])))

    def test_every_case_profile_has_a_probe_and_classic_none(self):
        from finger_rehab.game.modes.syllables_words import load_probe
        for pid, time_s in (("6-9", 6.0), ("10-12", 4.8), ("13-15", 4.2),
                            ("16+", 3.6), ("60+", 4.2)):
            got_s, items = load_probe(pid)
            self.assertEqual(got_s, time_s, pid)
            self.assertGreaterEqual(len(items), 24, pid)
        self.assertEqual(load_probe("classic"), (0.0, []))


class ProbeFlowTests(unittest.TestCase):

    def test_the_probe_opens_the_sitting(self):
        _e, m = _sectioned("6-9", probe=True)
        self.assertEqual(m.section_plan[0], ("probe", 24))
        _e, m = _sectioned("10-12", probe=True, words_total=30)
        self.assertEqual(m.section_plan[0], ("probe", 28))
        _e, m = _sectioned("6-9", probe=True, demo_trials=4)
        self.assertEqual(m.section_plan[0], ("probe", 2))
        _e, m = _sectioned("6-9", probe=True, probe_only=True)
        self.assertEqual(m.section_plan, [("probe", 24)])
        _e, m = _build_mode(age_band="classic", sections=True, probe=True)
        self.assertEqual(m.section_plan, [])

    def test_a_probe_set_measures_without_teaching(self):
        e, m = _sectioned("6-9", probe=True)
        t = _tick_until(m, 0.0, _probe_open)
        item = m._probe_items[0]
        self.assertEqual(m.word.word, item["word"])
        self.assertEqual(m.pos, item["pos"])
        self.assertIsNone(m._prompt_due)
        self.assertFalse(m.replay())
        wrong = [ln for ln, _txt, tgt in m.probe_options if not tgt][0]
        spawn = m._spawn_t
        m.queue_press(_press(wrong, spawn + 0.5))
        m._tick(spawn + 0.5)
        # The tiles go at once and nothing lifts or glows.
        self.assertIsNone(m.probe_options)
        self.assertEqual(m.phase, "gap")
        self.assertIsNone(m.lift_t)
        self.assertIsNone(m._glow_t)
        call = e.log_trial.call_args
        self.assertFalse(call.kwargs["after_press_cue"])
        self.assertEqual(call.args[1].points, 0)
        stim = call.kwargs["stimulus"]
        self.assertIn(";sec=probe;", stim)
        self.assertIn("first=wrong", stim)
        self.assertIn(f"held={1 if item['held_out'] else 0}", stim)
        self.assertEqual(m._sets, [])
        self.assertEqual(m._probe_done, 1)
        self.assertEqual(m.rung, m.rung_start)

    def test_the_whole_probe_then_the_training(self):
        e, m = _sectioned("6-9", probe=True)
        t = 0.0
        for k in range(24):
            t = _tick_until(m, t, _probe_open)
            m.queue_press(_press(m._probe_tlane, m._spawn_t + 0.4))
            m._tick(m._spawn_t + 0.4)
            t = m._spawn_t + 0.45 if m._spawn_t else t + 0.45
        t = _tick_until(m, t, lambda x: x.section != "probe")
        self.assertEqual(m.section, "review")
        # The session cap times the training, not the probe.
        self.assertGreater(m._t0, 24 * m.attend_s)
        st = m.block_stats()["probe"]
        self.assertTrue(st["complete"])
        self.assertEqual(st["acc"], 1.0)
        self.assertEqual(st["held_out"]["n"] + st["practised"]["n"], 24)

    def test_probe_only_ends_after_the_probe(self):
        e, m = _sectioned("6-9", probe=True, probe_only=True)
        t = 0.0
        for k in range(24):
            t = _tick_until(m, t, _probe_open)
            t = m._spawn_t + m.probe_time_s + 0.1
        t = _tick_until(m, t, lambda x: x.phase == "done")
        self.assertEqual(m.end_reason, "completed")
        st = m.block_stats()["probe"]
        self.assertEqual(st["no_answer"], 24)
        self.assertEqual(st["acc"], 0.0)

    def test_held_out_words_never_come_up_in_training(self):
        _e, m = _sectioned("6-9", probe=False)
        held = m._held_out
        self.assertGreaterEqual(len(held), 10)
        drawn = {m._draw_word().word for _ in range(600)}
        self.assertFalse(drawn & held)
        _e, m = _sectioned("16+", probe=False)
        drawn = {m._draw_profile_word().word for _ in range(600)}
        self.assertFalse(drawn & m._held_out)
        self.assertFalse({w.word for w in m._speed_pool()} & m._held_out)


class FloorAndLoggingTests(unittest.TestCase):

    def test_the_kaplan_meier_median(self):
        from finger_rehab.game.modes.syllables import km_median
        self.assertEqual(km_median([(1, True), (2, True), (3, True)]), 2)
        # Half the sets cut off by the buzz: the median is later than
        # every answer seen, so it never reaches one half.
        self.assertIsNone(km_median([(2, True), (2.5, True), (3, False),
                                     (3, False), (3, False), (3, False)]))
        self.assertIsNone(km_median([(3, False)]))

    def test_a_slow_reader_is_not_undercut(self):
        _e, m = _sectioned("6-9")
        m.word = m._draw_word()
        fall = m.fall_s
        m._floor_obs.extend([(2.0, True)] * 3 + [(3.6, False)] * 5)
        # The old rule took the median of the three answers (2.0 s);
        # with the five cut off at 3.6 s the floor stands at 3.6 s.
        self.assertAlmostEqual(m.prompt_floor_s(), 3.6)
        self.assertAlmostEqual(m._prompt_delay_s(),
                               min(max(0.6 * fall, 3.9), 0.9 * fall))

    def test_the_row_says_weak_and_when_the_buzz_was_due(self):
        e, m = _sectioned("6-9")
        t = _tick_until(m, 0.0, lambda x: x.phase == "choose"
                        and x.option_set is not None)
        m.queue_press(_press(m.option_set.target_lane, m._spawn_t + 0.5))
        m._tick(m._spawn_t + 0.5)
        stim = e.log_trial.call_args.kwargs["stimulus"]
        self.assertRegex(stim, r";weak=[01];")
        self.assertRegex(stim, r";pdue=\d+;")

    def test_the_block_records_its_seed_voice_and_size(self):
        _e, m = _sectioned("6-9", probe=True, words_total=30, seed=11)
        st = m.block_stats()
        self.assertEqual(st["seed"], 11)
        self.assertEqual(st["words_per_block"], 20)
        self.assertIn("voice", st["speech"])
        self.assertEqual(st["prompt"]["floor"]["rule"], "kaplan_meier")
        self.assertIn("probe", st)
        self.assertNotIn("probe", st["sections"]["by_section"])


class ProfileTests(unittest.TestCase):

    def test_six_to_nine_plays_twenty_words(self):
        _e, m = _sectioned("6-9", words_total=30)
        self.assertEqual(m.words_total, 20)
        _e, m = _sectioned("6-9", words_total=10)
        self.assertEqual(m.words_total, 10)
        _e, m = _sectioned("10-12", words_total=30)
        self.assertEqual(m.words_total, 30)

    def test_every_quick_look_runs_twenty_trials(self):
        from finger_rehab.game.modes.syllables_profiles import PROFILES
        for pid in ("10-12", "13-15", "16+"):
            self.assertEqual(PROFILES[pid].speed_trials, 20, pid)

    def test_the_adult_fall_moves_on_hear_and_pick_only(self):
        _e, m = _sectioned("16+", words_total=12)
        self.assertTrue(m.fall_mode)
        start = m._fall_now
        m.section = "review"
        for _ in range(8):
            m._move_rung(True, "ok", 0.0)
        self.assertEqual(m._fall_now, start)
        m.section = "build"
        for _ in range(8):
            m._move_rung(False, "miss", 0.0)
        self.assertEqual(m._fall_now, start)
        m.section = "pick"
        for _ in range(4):
            m._move_rung(True, "ok", 0.0)
        self.assertLess(m._fall_now, start)

    def test_the_corrected_claims(self):
        mode_src = (APP / "finger_rehab" / "game" / "modes"
                    / "syllables.py").read_text(encoding="utf-8")
        prof_src = (APP / "finger_rehab" / "game" / "modes"
                    / "syllables_profiles.py").read_text(encoding="utf-8")
        cfg = (APP / "config" / "default.yaml").read_text(encoding="utf-8")
        self.assertNotIn("which converges on the 79.4 percent point",
                         mode_src)
        self.assertNotIn("so the syllable is the right grain to start at",
                         mode_src)
        self.assertNotIn("Hence the adult line on the rest screen",
                         mode_src)
        self.assertIn("Kaplan-Meier", mode_src)
        self.assertIn("85.8 percent", prof_src)
        self.assertNotIn("(84.1 percent, Levitt 1971)", prof_src)
        self.assertNotIn("30 words is about 11 minutes", cfg)
        self.assertIn("probe: case", cfg)


class ScreenAndAdviceTests(unittest.TestCase):

    def test_the_probe_card_and_tiles(self):
        from finger_rehab.ui.feedback_bank import offending
        from finger_rehab.ui.syllables_screen import SyllablesScreen
        title, line = SyllablesScreen.SECTION_COPY["probe"]
        self.assertEqual(offending(title + " " + line), [])
        self.assertIn("No hints", line)
        self.assertEqual(title, "READING CHECK")
        self.assertEqual(SyllablesScreen.SECTION_NAMES["probe"],
                         "Reading check")

    def test_the_results_line_reads_the_unaided_rate(self):
        from finger_rehab.ui.screens import ResultsScreen
        slow = {"first_press_accuracy": 0.93, "unaided_accuracy": 0.3,
                "profile": "6-9",
                "prompt": {"n_sets": 40, "n_prompted": 26}}
        self.assertIn("more time", ResultsScreen._syllables_advice(slow))
        hard = {"first_press_accuracy": 0.5, "unaided_accuracy": 0.3,
                "profile": "16+", "prompt": {"n_sets": 40,
                                             "n_prompted": 0}}
        line = ResultsScreen._syllables_advice(hard)
        self.assertNotIn("band", line)
        easy = {"first_press_accuracy": 0.99, "unaided_accuracy": 0.99,
                "profile": "13-15"}
        self.assertIsNone(ResultsScreen._syllables_advice(easy))


class ListeningCheckTests(unittest.TestCase):

    def test_two_listeners_and_the_flagged_sets(self):
        sys.path.insert(0, str(APP / "scripts"))
        import syllables_recording_kit as kit
        items = [{"key": "child:a:0", "syl": "ba", "options":
                  ["ba", "da", "ka", "ma"], "file": "a.wav"},
                 {"key": "child:b:1", "syl": "ter", "options":
                  ["ter", "tar", "pen", "dog"], "file": "b.wav"},
                 {"key": "child:c:0", "syl": "on", "options":
                  ["on", "in", "up", "at"], "file": None}]
        played = []
        answers = iter(["1", "r", "2"])
        got = kit.run_listen(items, ask=lambda _p: next(answers),
                             play=played.append)
        self.assertEqual(got, {"child:a:0": "ba", "child:b:1": "tar",
                               "child:c:0": None})
        self.assertEqual(played, ["a.wav", "b.wav", "b.wav"])
        record = {"listeners": {"L1": {"answers": got},
                                "L2": {"answers": {"child:a:0": "ba",
                                                   "child:b:1": "ter"}}}}
        summary = kit.listen_summary(record, items)
        self.assertEqual(summary["listeners"], {"L1": 0.5, "L2": 1.0})
        self.assertEqual([f["key"] for f in summary["flagged"]],
                         ["child:b:1"])

    def test_the_probe_items_reach_the_check(self):
        sys.path.insert(0, str(APP / "scripts"))
        import syllables_recording_kit as kit
        items = kit.probe_listen_items(APP / "assets" / "speech")
        self.assertEqual(len(items), 24 + 28 + 25)
        self.assertTrue(all(len(it["options"]) == 4 for it in items))
        self.assertGreater(sum(1 for it in items if it["file"]), 70)


def _run_case_block(root: Path, answer_probe=lambda k: k % 2 == 0):
    """One real case block for a 9 year old: the probe, answered right
    on every other set, then 4 training words answered right."""
    import pygame
    pygame.init()
    try:
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.fsr_detector import PressEvent
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = False
        cfg.data["session"]["data_dir"] = str(root)
        cfg.data["report"] = {"enabled": False}
        cfg.data["syllables"]["speech"] = {"backend": "off"}
        cfg.data["syllables"]["words_per_block"] = 4
        cfg.data["syllables"]["break_s"] = 0
        cfg.data["syllables"]["seed"] = 21
        cfg.data["syllables"]["attend_s"] = 0.5
        cfg.data["syllables"]["inter_trial_gap_ms"] = 100
        eng = GameEngine(cfg, KeyboardOnlySource())
        gp = MagicMock()
        gp.lanes = []
        eng._screens = {name: MagicMock() for name in
                        ("results", "syllables", "mode_select",
                         "title", "login", "calibration")}
        eng._screens["gameplay"] = gp
        eng.show_results = lambda: None
        eng.begin_session("D99", "9", dominant_hand="right", visit="")
        eng.begin_syllables_block()
        mode = eng.mode
        answered: set = set()
        vt = 1000.0
        for _ in range(200000):
            if mode.phase == "done":
                break
            vt += 1.0 / 60.0
            mode._tick(vt)
            if mode.phase == "section" and mode._phase_until is None:
                # The card after the reading check waits for Start; the
                # supervisor presses it to go on to the game.
                mode.skip_wait(vt)
            if (mode.phase == "probe" and mode.probe_options
                    and mode._set_close_t is None
                    and vt >= mode._spawn_t + 0.4
                    and ("p", mode.trial_counter) not in answered):
                answered.add(("p", mode.trial_counter))
                right = answer_probe(mode._probe_done)
                lane = (mode._probe_tlane if right else
                        [ln for ln, _t, tg in mode.probe_options
                         if not tg][0])
                mode.queue_press(PressEvent(lane=lane, t_perf=vt, value=0,
                                            baseline=0.0,
                                            hand=mode.word_hand))
            if (mode.phase == "choose" and mode.option_set is not None
                    and mode._set_close_t is None
                    and vt >= mode._spawn_t + 0.4
                    and ("c", mode.trial_counter) not in answered):
                answered.add(("c", mode.trial_counter))
                mode.queue_press(PressEvent(
                    lane=mode.option_set.target_lane, t_perf=vt, value=0,
                    baseline=0.0, hand=mode.word_hand))
        eng.finish_block()
        eng.end_session()
    finally:
        pygame.quit()


class CaseNotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_syllables_notebook import _load_ra
        cls._td = tempfile.TemporaryDirectory()
        _run_case_block(Path(cls._td.name))
        cls.ra = _load_ra()
        cat = cls.ra.build_catalogue(root=cls._td.name)
        folders = [Path(p) for p in cat["folder"]]
        cls.trials = cls.ra.load_games(folders, cat)
        cls.metas = cls.ra.load_metas(folders)

    @classmethod
    def tearDownClass(cls):
        cls._td.cleanup()
        import matplotlib.pyplot as plt
        plt.close("all")

    def test_probe_rows_stay_out_of_the_training_frame(self):
        sy = self.ra.syllable_set_frame(self.trials)
        pf = self.ra.syllable_probe_frame(self.trials)
        self.assertEqual(len(pf), 24)
        self.assertTrue(len(sy))
        self.assertFalse(sy["section"].eq("probe").any())
        self.assertAlmostEqual(pf["first_ok"].mean(), 0.5)
        self.assertEqual(int(pf["held_out"].sum()), 12)
        for col in ("weak", "pdue_ms", "alone", "lat_ms"):
            self.assertIn(col, sy.columns)

    def test_the_case_chapter_and_the_probe_chapter_run(self):
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            out = self.ra.sec_syllables(self.trials, self.metas)
        text = buf.getvalue()
        self.assertIn("SYLLABLES: THE CASE SITTING", text)
        self.assertIn("SYLLABLES: THE PROBE", text)
        self.assertIn("Kaplan-Meier", text)
        self.assertIn("no test", text)
        probe = out["probe"]["by_session"]
        self.assertEqual(int(probe["sets"].sum()), 24)
        self.assertAlmostEqual(float(probe["right"].iloc[0]), 0.5)
        lat = out["sections"]["latency"]
        self.assertTrue(len(lat))


class NotebookHelperTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_syllables_notebook import _load_ra
        cls.ra = _load_ra()

    def test_the_kaplan_meier_median_and_interval(self):
        ra = self.ra
        self.assertEqual(ra.syllable_km_median([1, 2, 3], [1, 1, 1]), 2)
        self.assertTrue(np_isnan(ra.syllable_km_median(
            [2, 3, 3, 3], [1, 0, 0, 0])))
        med, lo, hi = ra.syllable_km_ci([1, 2, 3, 4, 5, 6, 7, 8],
                                        [1] * 8)
        self.assertEqual(med, 4)
        self.assertLessEqual(lo, med)

    def test_the_nonoverlap_and_its_exact_p(self):
        nap, p = self.ra.syllable_nap([0.5, 0.55, 0.6, 0.58, 0.52],
                                      [0.7, 0.72, 0.8, 0.75, 0.9])
        self.assertEqual(nap, 1.0)
        self.assertAlmostEqual(p, 1 / 252)
        nap, p = self.ra.syllable_nap([0.6, 0.6, 0.6], [0.6, 0.6, 0.6])
        self.assertEqual(nap, 0.5)
        self.assertEqual(p, 1.0)

    def test_the_near_foil_test_leaves_the_far_foil_out(self):
        import pandas as pd
        rows = []
        for i in range(40):
            opts = [(1, "ba", "target"), (2, "zo", "F1"), (3, "bi", "F3"),
                    (4, "da", "F2")]
            wrong = "F3" if i < 8 else None
            rows.append({"opts": opts, "first": "wrong" if wrong else "ok",
                         "wrong_kind": wrong})
        tbl, p, n = self.ra.syllable_near_foil_test(pd.DataFrame(rows))
        self.assertNotIn("F1", tbl.index)
        self.assertEqual(n, 8)
        self.assertLess(p, 0.05)

    def test_the_sources_are_corrected(self):
        ra = self.ra
        spec = {s["id"]: s for s in ra.MODE_LIT["syllables"]}
        self.assertIn("63(10):3252-3262", spec["S4"]["source"])
        self.assertNotIn("Kornell", spec["S4"]["source"])
        self.assertNotIn("letter-position foils hardest",
                         spec["S2"]["reference"])
        self.assertNotIn("79.4 percent, chance 25",
                         spec["S1"]["reference"])
        limits = " ".join(ra.MODE_CLAIM_LIMITS["syllables"])
        self.assertIn("passed level 3", limits)
        self.assertIn("Luniewska", limits)
        refs = " ".join(r for _t, group in ra.REFERENCES for r in group)
        self.assertIn("Kornell, N., Hays, M.J., and Bjork, R.A. (2009)",
                      refs)
        self.assertNotIn("Castel", refs)
        self.assertIn("Kaplan, E.L., and Meier, P. (1958)", refs)


def np_isnan(x) -> bool:
    return x != x


if __name__ == "__main__":
    unittest.main()
