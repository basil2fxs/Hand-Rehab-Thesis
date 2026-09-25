"""Syllables across ages: the profiles and the study's pin.

The healthy baseline study pre-registered the Syllables block as it
stood (Section 1.4, S6 and S7), so the battery pins the classic
profile and nothing else may move it; every test of the classic block
in test_syllables_mode.py still runs against that profile. The other
profiles each change something a reader of that age needs changed,
and each change is pinned here: adults hear the word without seeing
it, answer without a buzz, read rarer and made-up words and have their
fall time measured; teens get faster falls and a shorter buzz ladder;
young children see the print fade above rung 3.
"""
from __future__ import annotations

import os
import sys
import unittest
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from finger_rehab.game.modes import syllables_foils as F  # noqa: E402
from finger_rehab.game.modes.syllables_profiles import (  # noqa: E402
    PROFILES, band_for_age, resolve)
from finger_rehab.game.modes.syllables_words import (  # noqa: E402
    all_words, load_pools)
from tests.test_syllables_mode import (  # noqa: E402
    _answer_set, _build_mode, _run_to_choose)


def _wait_for_next_set(m, t, step=0.05):
    """Tick to the next set on screen, whatever position it is at."""
    for _ in range(4000):
        if (m.phase == "choose" and m.option_set is not None
                and m._set_close_t is None):
            return t
        m._tick(t)
        t += step
    raise AssertionError(f"no next set, at {m.phase}")


def _let_it_fall(m, t, step=0.05):
    """Tick until the set on screen closes: a wrong press only greys
    its tile, so the set is scored when it leaves the screen."""
    trial = m.trial_counter
    for _ in range(4000):
        if m.option_set is None or m.trial_counter != trial:
            return t
        m._tick(t)
        t += step
    raise AssertionError("the set never closed")


class Resolution(unittest.TestCase):
    def test_ages_map_to_bands(self):
        for age, want in ((6, "6-9"), (9, "6-9"), (10, "10-12"),
                          (12, "10-12"), (13, "13-15"), (15, "13-15"),
                          (16, "16+"), (45, "16+"), (60, "60+"),
                          (82, "60+")):
            self.assertEqual(resolve("auto", age).pid, want, age)

    def test_blank_and_odd_inputs(self):
        self.assertEqual(resolve("auto", "").pid, "6-9")
        self.assertEqual(resolve("auto", None).pid, "6-9")
        self.assertIsNone(band_for_age("n/a"))
        self.assertEqual(resolve("classic", 30).pid, "classic")
        self.assertEqual(resolve("no such band", 30).pid, "classic")
        self.assertEqual(resolve("10-15", 14).pid, "13-15")
        self.assertEqual(resolve("10-15", "").pid, "10-12")

    def test_the_study_battery_pins_classic(self):
        import yaml
        cfg = yaml.safe_load((ROOT / "config" / "default.yaml").read_text())
        over = cfg["protocol"]["presets"]["study_battery"]["overrides"]
        self.assertEqual(over["syllables"]["age_band"], "classic")
        self.assertEqual(cfg["syllables"]["age_band"], "auto")

    def test_the_engine_passes_the_intake_age(self):
        src = (ROOT / "finger_rehab" / "game" / "engine.py").read_text()
        at = src.index("self.mode = SyllablesMode(")
        call = src[at:src.index("self._begin_block(\"syllables\")", at)]
        self.assertIn("age_band=", call)
        self.assertIn("age=getattr(self.session, \"age\"", call)


class Classic(unittest.TestCase):
    def test_classic_changes_nothing(self):
        _e, m = _build_mode()
        self.assertEqual(m.profile.pid, "classic")
        self.assertTrue(m._bank_bands)
        self.assertFalse(m.fall_mode)
        self.assertEqual(m.sound_lead_s, 0.0)
        for rung in range(1, 9):
            m.rung = rung
            self.assertTrue(m.show_print)
            self.assertIsNone(m._foil_kinds())
        self.assertFalse(m.replay())

    def test_classic_has_no_replay_key(self):
        import pygame
        _e, m = _build_mode()
        t = _run_to_choose(m)
        m.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_r))
        self.assertFalse(m._replayed)


class Adults(unittest.TestCase):
    def _adult(self, **over):
        return _build_mode(age_band="16+", **over)

    def test_heard_not_seen_and_no_buzz(self):
        _e, m = self._adult()
        self.assertFalse(m.show_print)
        self.assertFalse(m.prompt_enabled)
        t = 0.0
        while m.phase != "attend":
            m._tick(t)
            t += 0.05
        while m.phase == "attend":
            m._tick(t)
            t += 0.05
        self.assertEqual(m.phase, "choose")      # no MODEL
        for rung in range(1, 9):
            self.assertIn(rung, m.respeak_rungs)

    def test_adult_words_and_a_share_made_up(self):
        _e, m = self._adult()
        drawn = [m._draw_word() for _ in range(600)]
        self.assertTrue(all(3 <= w.n_syll <= 5 for w in drawn))
        share = sum(w.lex == "pseudo" for w in drawn) / len(drawn)
        self.assertAlmostEqual(share, 0.4, delta=0.07)
        child = {w.word for w in all_words()}
        self.assertFalse({w.word for w in drawn} & child)

    def test_adult_foils_never_reversals_same_word_or_spelling(self):
        _e, m = self._adult()
        kinds = Counter()
        t = _run_to_choose(m)
        for _ in range(60):
            for o in m.option_set.options:
                kinds[o.kind] += 1
            t = _answer_set(m, t)
            t = _wait_for_next_set(m, t)
        for bad in ("F4", "F6", "F8"):
            self.assertEqual(kinds[bad], 0, kinds)
        self.assertGreater(kinds["F3"], 0)

    def test_the_fall_staircase(self):
        _e, m = self._adult()
        prof = m.profile
        t = _run_to_choose(m)
        start = m.fall_s
        self.assertAlmostEqual(start, prof.fall_start_s)
        for _ in range(4):
            t = _answer_set(m, t)
            t = _wait_for_next_set(m, t)
        self.assertAlmostEqual(m.fall_s, start - prof.fall_step_down_s)
        t = _answer_set(m, t, lane=next(
            o.lane for o in m.option_set.options if o.kind != F.TARGET))
        t = _let_it_fall(m, t)
        self.assertAlmostEqual(m.fall_s, start - prof.fall_step_down_s
                               + prof.fall_step_up_s)
        self.assertEqual(m.rung, m.rung_start)   # the rung stays put
        stats = m.block_stats()
        self.assertEqual(stats["profile"], "16+")
        self.assertIn("fall_threshold", stats)
        self.assertEqual(stats["fall_threshold"]["n_reversals"], 1)

    def test_the_fall_stays_inside_its_bounds(self):
        _e, m = self._adult()
        for _ in range(40):
            m._move_fall(False, "miss")
        self.assertAlmostEqual(m.fall_s, m.profile.fall_hi_s)
        for _ in range(400):
            m._move_fall(True, "ok")
        self.assertAlmostEqual(m.fall_s, m.profile.fall_lo_s)

    def test_one_replay_per_set_and_it_never_moves_the_fall(self):
        _e, m = self._adult()
        t = _run_to_choose(m)
        self.assertTrue(m.replay())
        self.assertFalse(m.replay())
        before = m.fall_s
        t = _answer_set(m, t, lane=next(
            o.lane for o in m.option_set.options if o.kind != F.TARGET))
        t = _let_it_fall(m, t)
        self.assertEqual(m.fall_s, before)
        t = _wait_for_next_set(m, t)
        self.assertFalse(m._replayed)
        self.assertTrue(m.replay())

    def test_the_row_says_who_it_was_for(self):
        engine, m = self._adult()
        t = _run_to_choose(m)
        _answer_set(m, t)
        stim = engine.log_trial.call_args.kwargs["stimulus"]
        for field in ("prof=16+", "lex=", "print=0", "replay=0"):
            self.assertIn(field, stim)


class Teens(unittest.TestCase):
    def test_faster_falls_and_print_to_rung_two(self):
        _e, m = _build_mode(age_band="auto", age="11")
        self.assertEqual(m.profile.pid, "10-12")
        self.assertEqual(m._fall_table[0], 3.2)
        self.assertEqual(min(m._fall_table), 2.0)
        m.rung = 2
        self.assertTrue(m.show_print)
        m.rung = 3
        self.assertFalse(m.show_print)
        self.assertEqual(m.prompt_steps, (0.75, 0.9))

    def test_far_foils_only_at_rung_one(self):
        _e, m = _build_mode(age_band="13-15")
        m._begin_word(0.0)
        m.rung = 1
        self.assertEqual(m._foil_kinds(), ("F1", "F1", "F1"))
        m.rung = 4
        for _ in range(50):
            self.assertNotIn("F1", m._foil_kinds())


class YoungChildren(unittest.TestCase):
    def test_print_fades_above_rung_three(self):
        _e, m = _build_mode(age_band="6-9")
        m.rung = 3
        self.assertTrue(m.show_print)
        m.rung = 4
        self.assertFalse(m.show_print)

    def test_no_vowel_foil_on_a_reduced_syllable_without_spelt_audio(self):
        _e, m = _build_mode(age_band="6-9")
        m._begin_word(0.0)
        m.rung = 4                                # F2, F3, F7
        stressed = m.word.stress
        m.pos = next(i for i in range(m.n_syll) if i != stressed)
        self.assertNotIn("F3", m._foil_kinds())
        m.pos = stressed
        self.assertIn("F3", m._foil_kinds())

    def test_the_sound_trails_the_print(self):
        _e, m = _build_mode(age_band="6-9")
        m._begin_word(0.0)
        m._speak_syllable_after(0, 10.0)
        self.assertEqual(len(m._speech_queue), 1)
        m._flush_speech(10.1)
        self.assertEqual(len(m._speech_queue), 1)
        m._flush_speech(10.2)
        self.assertEqual(m._speech_queue, [])


class MorphologyFoil(unittest.TestCase):
    def test_affixes_swap_only_at_the_word_edge(self):
        import random
        rng = random.Random(1)
        inv = F.Inventory([("un", "hap", "py"), ("dis", "mis"),
                           ("pay", "ment", "ness", "less")])
        self.assertIn(F._f9_affix("un", ("un", "hap", "py"), 0, inv, rng),
                      F.PREFIX_SWAPS["un"])
        self.assertIsNone(F._f9_affix("un", ("fun", "un", "der"), 1,
                                      inv, rng))
        self.assertIn(F._f9_affix("ment", ("pay", "ment"), 1, inv, rng),
                      F.SUFFIX_SWAPS["ment"])
        self.assertIsNone(F._f9_affix("hap", ("un", "hap", "py"), 1,
                                      inv, rng))


class Pools(unittest.TestCase):
    def test_the_pools_are_sound(self):
        pools = load_pools()
        self.assertGreater(len(pools["teen"]), 60)
        self.assertGreater(len(pools["adult"]), 60)
        self.assertGreaterEqual(len(pools["pseudo"]), 40)
        real = {w.word for w in all_words()} | {
            w.word for n in ("teen", "adult") for w in pools[n]}
        for name, words in pools.items():
            for w in words:
                self.assertEqual("".join(w.syllables), w.word)
                self.assertTrue(0 <= w.stress < w.n_syll)
        for w in pools["adult"]:
            self.assertTrue(3 <= w.n_syll <= 5, w.word)
        for w in pools["pseudo"]:
            self.assertEqual(w.lex, "pseudo")
            self.assertNotIn(w.word, real)


if __name__ == "__main__":
    unittest.main()


class TheNotebook(unittest.TestCase):
    """An adult block's rows are summarised on their own, with the
    threshold, and never reach the child chapter's checks."""

    def test_an_adult_block_is_summarised_apart(self):
        import contextlib
        import io
        import pandas as pd
        from tests.test_analysis_logic_gaps import _load_notebook
        ra = _load_notebook("syllables_profiles")
        engine, m = _build_mode(age_band="16+")
        t = _run_to_choose(m)
        for _ in range(30):
            t = _answer_set(m, t)
            t = _wait_for_next_set(m, t)
        rows = [dict(mode="syllables", session="S1", block="syllables",
                     trial=i + 1, stimulus=c.kwargs["stimulus"])
                for i, c in enumerate(engine.log_trial.call_args_list)]
        trials = pd.DataFrame(rows)
        sy = ra.syllable_set_frame(trials)
        self.assertEqual(set(sy["profile"]), {"16+"})
        self.assertTrue(set(sy["lex"]) <= {"word", "pseudo"})
        with contextlib.redirect_stdout(io.StringIO()):
            out = ra.sec_syllables_profiles(sy)
            checks = ra.sec_syllables_checks(trials)
        self.assertIn("16+", out["summary"].index)
        self.assertLess(out["summary"].loc["16+", "threshold_ms"], 2400)
        self.assertTrue(checks["checks"].empty)
