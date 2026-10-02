"""Syllables made plain to play (Basil, 2 October 2026).

The reading check (the fixed probe) opens a case reader's sitting only,
codes from D01 up; the warm-up words and hear and pick are one part
with one card and one counter; the instructions say what each part
asks; the play screen shows no band or level; the card's key says
Start; and the results grade the words, with the reading check shown
on its own card. The card after the reading check waits for Start.
The voice plays without a cue tone before each modelled syllable, and
the gaps between voice prompts are a little shorter.
"""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_syllables_mode import _build_mode, _press  # noqa: E402


def _rule(probe="case", probe_only=False, code="P01"):
    from finger_rehab.game.engine import GameEngine
    values = {"syllables.probe": probe, "syllables.probe_only": probe_only}
    ns = SimpleNamespace(
        cfg=SimpleNamespace(get=lambda k, d=None: values.get(k, d)),
        session=SimpleNamespace(participant=code))
    return GameEngine.syllables_probe_on(ns)


class ReadingCheckRuleTests(unittest.TestCase):

    def test_only_case_readers_get_the_check(self):
        for code in ("D01", "d7", "D12"):
            self.assertTrue(_rule(code=code), code)
        for code in ("P01", "NA", "", "DAN", "test"):
            self.assertFalse(_rule(code=code), code)

    def test_the_setting_can_force_it(self):
        self.assertTrue(_rule(probe=True, code="P01"))
        self.assertTrue(_rule(probe="true", code="P01"))
        self.assertFalse(_rule(probe=False, code="D01"))
        self.assertTrue(_rule(probe=False, probe_only=True, code="P01"))

    def test_the_config_says_case(self):
        from finger_rehab.config import Config
        self.assertEqual(Config.load().get("syllables.probe"), "case")


def _transitions(m, limit=200000):
    """(section, phase) changes while every set is answered right."""
    seen, t, answered = [], 0.0, set()
    for _ in range(limit):
        if m.phase == "done":
            return seen
        key = (m.section, m.phase)
        if not seen or seen[-1] != key:
            seen.append(key)
        m._tick(t)
        if (m.phase == "choose" and m.option_set is not None
                and m._set_close_t is None and t >= m._spawn_t + 0.5
                and m.trial_counter not in answered):
            answered.add(m.trial_counter)
            m.queue_press(_press(m.option_set.target_lane, t))
        t += 0.05
    raise AssertionError("block never ended")


class OnePartTests(unittest.TestCase):

    def test_warm_up_runs_into_hear_and_pick_with_no_card(self):
        _e, m = _build_mode(age_band="6-9", sections=True, words_total=12)
        names = [n for n, _q in m.section_plan]
        self.assertEqual(names[:2], ["review", "pick"])
        seen = _transitions(m)
        cards = [s for s, ph in seen if ph == "section"]
        self.assertIn("review", cards)
        self.assertNotIn("pick", cards)
        self.assertIn("build", cards)

    def test_the_card_key_says_start(self):
        _e, m = _build_mode(age_band="6-9", sections=True, words_total=12)
        m._tick(0.0)
        self.assertEqual(m.phase, "section")
        self.assertEqual(m._skip_state().armed.label, "Start")


class HeldCardTests(unittest.TestCase):
    """The card after the reading check waits for Start, so a baseline
    session can end there with two presses of Esc and no training word
    starts by itself."""

    def _after_check(self):
        from tests.test_syllables_research import (_probe_open, _sectioned,
                                                   _tick_until)
        _e, m = _sectioned("6-9", probe=True)
        t = 0.0
        for _k in range(len(m._probe_items)):
            t = _tick_until(m, t, _probe_open)
            m.queue_press(_press(m._probe_tlane, m._spawn_t + 0.4))
            m._tick(m._spawn_t + 0.4)
            t = m._spawn_t + 0.45 if m._spawn_t else t + 0.45
        t = _tick_until(m, t, lambda x: x.phase == "section")
        return m, t

    def test_the_card_after_the_check_waits_for_start(self):
        m, t = self._after_check()
        self.assertEqual(m.section, "review")
        for k in range(400):
            m._tick(t + 0.1 * k)
        self.assertEqual(m.phase, "section")
        view = m.wait_view(t + 40)
        self.assertTrue(view["show"])
        self.assertEqual(view["label"], "Start")
        self.assertTrue(m.skip_wait(t + 40))
        self.assertNotEqual(m.phase, "section")

    def test_other_cards_still_move_on(self):
        _e, m = _build_mode(age_band="6-9", sections=True, words_total=12)
        m._tick(0.0)
        self.assertEqual(m.phase, "section")
        m._tick(m.SECTION_CARD_S + 0.1)
        self.assertNotEqual(m.phase, "section")


class VoicePacingTests(unittest.TestCase):
    """2 October 2026: no beep before each modelled syllable, and the
    breaks between voice prompts a little shorter."""

    def _to_model(self):
        _e, m = _build_mode(age_band="6-9", sections=True, words_total=12,
                            attend_s=3.0, ioi_ms=800)
        t = 0.0
        while m.phase != "model":
            m._tick(t)
            if m.phase == "section":
                m.skip_wait(t)
            t += 0.01
        return _e, m, t

    def test_the_model_plays_no_cue_tone(self):
        e, m, t = self._to_model()
        e.on_stim_multi.reset_mock()
        while m.phase == "model":
            m._tick(t)
            t += 0.01
        calls = e.on_stim_multi.call_args_list
        self.assertEqual(len(calls), m.n_syll)
        for c in calls:
            self.assertIs(c.kwargs.get("tone"), False)
            self.assertIs(c.kwargs.get("buzz"), False)

    def test_the_first_syllable_comes_soon_after_attend(self):
        _e, m, t = self._to_model()
        self.assertAlmostEqual(m._model_next_t - t,
                               m.MODEL_LEAD_S, delta=0.02)
        self.assertLess(m.MODEL_LEAD_S, m.ioi_s)

    def test_the_gaps_are_a_little_shorter(self):
        from finger_rehab.config import Config
        from finger_rehab.game.modes.syllables import SyllablesMode as M
        cfg = Config.load()
        self.assertEqual(cfg.get("syllables.beat_ioi_ms"), 800)
        self.assertEqual(cfg.get("syllables.set_gap_s"), 0.8)
        self.assertEqual(cfg.get("syllables.inter_trial_gap_ms"), 1300)
        self.assertEqual(cfg.get("syllables.complete_s"), 2.8)
        self.assertEqual((M.MODEL_GAP_S, M.BLEND_HOLD_S, M.READ_BACK_TAIL_S),
                         (0.4, 1.0, 0.8))
        # The word still stays on screen 3 s, as the thesis says.
        self.assertEqual(cfg.get("syllables.attend_s"), 3.0)


class WordsOnScreenTests(unittest.TestCase):

    def _screen(self):
        from finger_rehab.ui.syllables_screen import SyllablesScreen
        return SyllablesScreen, SyllablesScreen.__new__(SyllablesScreen)

    def test_warm_up_and_hear_and_pick_share_a_card_and_a_counter(self):
        cls, sc = self._screen()
        self.assertEqual(cls.SECTION_COPY["review"], cls.SECTION_COPY["pick"])
        self.assertEqual(cls.SECTION_NAMES["review"], "Hear and pick")
        plan = [("review", 3), ("pick", 12), ("build", 5)]
        mode = SimpleNamespace(phase="choose", sectioned=True,
                               section_plan=plan, _section_words=0,
                               section="review", _speed_done=0)
        mode._section_quota = lambda: dict(plan)[mode.section]
        self.assertEqual(sc._top_label(mode), "Hear and pick: 1 of 15")
        mode.section = "pick"
        self.assertEqual(sc._top_label(mode), "Hear and pick: 4 of 15")
        mode.section, mode._section_words = "build", 1
        self.assertEqual(sc._top_label(mode), "Build the word: 2 of 5")

    def test_the_instructions_say_what_each_part_asks(self):
        _cls, sc = self._screen()

        def line(section, pos, rewards):
            mode = SimpleNamespace(phase="choose", sectioned=True,
                                   section=section, pos=pos,
                                   profile=SimpleNamespace(rewards=rewards))
            return sc._stage(mode)[1]
        self.assertIn("first part", line("pick", 0, "child"))
        self.assertIn("next part", line("pick", 1, "child"))
        self.assertEqual(line("pick", 0, "adult"),
                         "Press the finger under the part you heard.")
        self.assertIn("first part of the word", line("build", 0, "adult"))
        self.assertIn("next part of the word", line("build", 2, "adult"))
        for section in ("pick", "build"):
            self.assertNotIn("comes next", line(section, 0, "child"))

    def test_the_reading_check_card_says_what_it_is(self):
        cls, _sc = self._screen()
        title, words = cls.SECTION_COPY["probe"]
        self.assertEqual(title, "READING CHECK")
        self.assertIn("No hints, no score", words)

    def test_no_band_or_level_on_the_play_screen(self):
        import pygame
        pygame.init()
        try:
            from tests.test_syllables_research import _sectioned
            from finger_rehab.ui import syllables_screen as mod
            e, m = _sectioned("6-9")
            sc = mod.SyllablesScreen.__new__(mod.SyllablesScreen)
            sc.engine = e
            sc.engine.score = 0
            sc.theme = SimpleNamespace(muted=(120, 120, 120),
                                       accent=(200, 50, 150))
            sc.layout = SimpleNamespace(width=1280, height=800,
                                        font=lambda *a, **k:
                                        pygame.font.Font(None, 20))
            drawn = []
            with mock.patch.object(mod, "draw_text",
                                   lambda surf, text, *a, **k:
                                   drawn.append(str(text))):
                with mock.patch.object(sc, "_accent",
                                       return_value=(200, 50, 150)):
                    sc._draw_top(pygame.Surface((1280, 800)), m)
            self.assertTrue(drawn)
            for text in drawn:
                self.assertNotIn("Band", text)
                self.assertNotIn("Level", text)
        finally:
            pygame.quit()


class ResultsTests(unittest.TestCase):

    def _results(self, summary, hits=10, misses=10):
        from finger_rehab.ui.screens import ResultsScreen
        eng = SimpleNamespace(current_block="syllables", hits=hits,
                              misses=misses, score=120,
                              session=SimpleNamespace(
                                  block_summary={"syllables": summary}),
                              mode=None)
        rs = ResultsScreen.__new__(ResultsScreen)
        rs.engine = eng
        return ResultsScreen, rs

    def test_the_grade_follows_words_correct(self):
        cls, rs = self._results({"accuracy": 1.0})
        self.assertEqual(cls._grade_for(rs._grade_rate())[0], "S")
        cls, rs = self._results({}, hits=3, misses=1)
        self.assertAlmostEqual(rs._grade_rate(), 0.75)

    def test_advice_in_plain_words(self):
        from finger_rehab.ui.screens import ResultsScreen
        easy = {"first_press_accuracy": 0.99, "unaided_accuracy": 0.99,
                "profile": "6-9"}
        hard = {"first_press_accuracy": 0.3, "unaided_accuracy": 0.3,
                "profile": "6-9", "prompt": {"n_sets": 40,
                                             "n_prompted": 2}}
        for sy in (easy, hard):
            line = ResultsScreen._syllables_advice(sy)
            self.assertNotIn("band", line)
            self.assertNotIn("asking anything", line)


if __name__ == "__main__":
    unittest.main()
