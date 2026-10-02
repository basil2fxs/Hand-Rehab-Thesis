"""Syllables in sections (syllables.sections, the default).

The research pass of 30 September 2026
(docs/research/new_modes/syllables-task-design.md) turned the block
into a sitting of parts: review, hear and pick, build the word and,
from 10 to 59, a quick look speed check. Each rule the mode's
docstring states under SECTIONS is pinned here: the plan, the section
cards, unrelated foils in the review, the answer shown after two wrong
presses, every word ending whole and read before it is heard, build
words heard and not shown, foils by confusion family with their own
ladder, and the speed check's flash, mask, choices, staircase and
logging. The classic profile keeps the single-section block.
"""
from __future__ import annotations

import io
import contextlib
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_syllables_mode import (  # noqa: E402
    _build_mode, _parse_stimulus, _press, _stimuli)


def _sectioned(age_band: str = "10-12", **over):
    over.setdefault("words_total", 12)
    return _build_mode(age_band=age_band, sections=True, **over)


def _tick_until(m, t, pred, step=0.05, limit=20000):
    for _ in range(limit):
        if pred(m):
            return t
        m._tick(t)
        t += step
    raise AssertionError(f"never reached, at {m.phase}")


def _set_open(m) -> bool:
    return (m.phase == "choose" and m.option_set is not None
            and m._set_close_t is None)


def _answer_right(m, t, delay=0.5):
    t = _tick_until(m, t, _set_open)
    t = max(t, m._spawn_t + delay)
    m.queue_press(_press(m.option_set.target_lane, t))
    m._tick(t)
    return t + 0.05


def _play_through(m, t=0.0, speed_right=True):
    """Answer every set right and every speed trial as asked, to the
    end of the block."""
    answered = set()
    for _ in range(400000):
        if m.phase == "done":
            return t
        m._tick(t)
        if _set_open(m) and t >= m._spawn_t + 0.5:
            key = m.trial_counter
            if key not in answered:
                answered.add(key)
                m.queue_press(_press(m.option_set.target_lane, t))
        if (m.phase == "speed" and m.speed_options is not None
                and m._set_close_t is None and t >= m._spawn_t + 0.5):
            key = ("s", m.trial_counter)
            if key not in answered:
                answered.add(key)
                lane = (m._speed_tlane if speed_right else
                        [ln for ln, _w, tg in m.speed_options if not tg][0])
                m.queue_press(_press(lane, t))
        t += 0.05
    raise AssertionError(f"block never ended, at {m.phase}")


class PlanTests(unittest.TestCase):
    def test_classic_keeps_the_single_section_block(self):
        _e, m = _build_mode(sections=True)
        self.assertEqual(m.profile.pid, "classic")
        self.assertFalse(m.sectioned)
        self.assertEqual(m.section_plan, [])

    def test_off_by_the_switch(self):
        _e, m = _build_mode(age_band="10-12", sections=False)
        self.assertFalse(m.sectioned)

    def test_the_words_are_shared_out(self):
        _e, m = _sectioned("10-12", words_total=30)
        self.assertEqual(m.section_plan, [("review", 4), ("pick", 18),
                                          ("build", 8), ("speed", 20)])
        _e, m = _sectioned("16+", words_total=30)
        self.assertEqual(m.section_plan[-1], ("speed", 20))

    def test_no_speed_check_under_ten_or_from_sixty(self):
        for band in ("6-9", "60+"):
            _e, m = _sectioned(band, words_total=30)
            self.assertNotIn("speed", [n for n, _k in m.section_plan])

    def test_demo_plays_two_speed_trials(self):
        _e, m = _sectioned("13-15", demo_trials=4)
        self.assertEqual(m.section_plan[-1], ("speed", 2))

    def test_the_engine_passes_the_switch_and_the_config_ships_it(self):
        import yaml
        cfg = yaml.safe_load((ROOT / "config" / "default.yaml").read_text())
        self.assertIs(cfg["syllables"]["sections"], True)
        src = (ROOT / "finger_rehab" / "game" / "engine.py").read_text()
        at = src.index("self.mode = SyllablesMode(")
        call = src[at:src.index("self._begin_block(\"syllables\")", at)]
        self.assertIn('sections=bool(self.cfg.get("syllables.sections"',
                      call)


class FlowTests(unittest.TestCase):
    def test_the_first_section_gets_its_card(self):
        _e, m = _sectioned()
        seen = []
        t = 0.0
        for _ in range(400):
            m._tick(t)
            if not seen or seen[-1] != m.phase:
                seen.append(m.phase)
            if m.phase == "attend":
                break
            t += 0.05
        # The test mode's gap is zero, so it can pass unseen.
        self.assertEqual([s for s in seen if s != "gap"],
                         ["section", "attend"])
        self.assertEqual(m.section, "review")

    def test_review_foils_are_unrelated_and_move_no_ladder(self):
        e, m = _sectioned(words_total=12)
        self.assertEqual(m.section_plan[0], ("review", 2))
        t = 0.0
        rung0 = m.rung
        levels0 = dict(m.family_levels)
        while m.section == "review" and m.phase != "done":
            t = _tick_until(m, t, lambda x: _set_open(x)
                            or x.section != "review")
            if m.section != "review":
                break
            kinds = {o.kind for o in m.option_set.options} - {"target"}
            self.assertEqual(kinds, {"F1"})
            # A wrong press in the review still moves nothing.
            wrong = [o.lane for o in m.option_set.options
                     if o.lane != m.option_set.target_lane][0]
            m.queue_press(_press(wrong, t + 0.5))
            t = _answer_right(m, t + 0.6, delay=0.7)
        self.assertEqual(m.rung, rung0)
        self.assertEqual(m.family_levels, levels0)
        rows = [_parse_stimulus(s) for s in _stimuli(e)]
        self.assertTrue(rows)
        self.assertTrue(all(r["sec"] == "review" for r in rows))

    def test_two_wrong_presses_show_the_answer(self):
        e, m = _sectioned()
        t = _tick_until(m, 0.0, lambda x: _set_open(x)
                        and x.section == "pick")
        t += 0.5
        word, pos = m.word.word, m.pos
        target = m.option_set.target
        wrong = [o.lane for o in m.option_set.options
                 if o.lane != m.option_set.target_lane]
        m.queue_press(_press(wrong[0], t))
        m.queue_press(_press(wrong[1], t + 0.3))
        m._tick(t + 0.35)
        self.assertIsNotNone(m._set_close_t)
        self.assertEqual(m.filled[pos], target)
        self.assertTrue(m._slots_shown[pos])
        self.assertIsNone(m.filled_lanes[pos])
        row = _parse_stimulus(_stimuli(e)[-1])
        self.assertEqual((row["sec"], row["err"], row["shown"]),
                         ("pick", "shown", "1"))
        # The word carries on and ends whole, then comes back later.
        t = _tick_until(m, t + 0.4, lambda x: x.phase == "complete")
        self.assertTrue(m.strip_closed)
        self.assertTrue(all(f is not None for f in m.filled))
        _tick_until(m, t, lambda x: x.phase in ("gap", "section"))
        self.assertIn(word, [p["word"].word for p in m._parked])
        self.assertFalse(m._records[-1].completed)

    def test_a_set_that_runs_out_is_shown_and_the_word_goes_on(self):
        e, m = _sectioned()
        t = _tick_until(m, 0.0, lambda x: _set_open(x)
                        and x.section == "pick" and x.n_syll > 1)
        pos = m.pos
        t = _tick_until(m, t, lambda x: x._glow_t is not None)
        self.assertTrue(m._slots_shown[pos])
        row = _parse_stimulus(_stimuli(e)[-1])
        self.assertEqual((row["err"], row["shown"]), ("miss", "0"))
        _tick_until(m, t, lambda x: _set_open(x) or x.phase == "complete")
        self.assertEqual(m.pos, pos + 1)

    def test_every_word_is_read_before_it_is_heard(self):
        _e, m = _sectioned()
        heard = []
        m._speak_word = lambda: heard.append("word")
        t = _tick_until(m, 0.0, lambda x: x.section == "pick"
                        and _set_open(x))
        n = m.n_syll
        for _ in range(n):
            t = _answer_right(m, t)
        t = _tick_until(m, t, lambda x: x.phase == "complete")
        self.assertTrue(m.strip_closed)
        due, stem = m._speech_queue[-1]
        self.assertIsNone(stem)
        self.assertAlmostEqual(due - m._phase_t0,
                               m.profile.read_hold_s, places=2)
        self.assertGreaterEqual(m._phase_until - m._phase_t0,
                                m.profile.read_hold_s + 1.0)

    def test_build_words_are_heard_not_shown_and_not_modelled(self):
        _e, m = _sectioned("10-12")
        t = _tick_until(m, 0.0, lambda x: x.section == "build"
                        and x.phase == "attend", limit=200000)
        self.assertFalse(m._word_printed)
        phases = set()
        t = _tick_until(m, t, lambda x: phases.add(x.phase)
                        or (x.phase == "choose"
                            and x.option_set is not None))
        self.assertNotIn("model", phases)
        self.assertFalse(m._respeak)

    def test_the_youngest_see_the_word_they_build(self):
        _e, m = _sectioned("6-9")
        _tick_until(m, 0.0, lambda x: x.section == "build"
                    and x.phase == "attend", limit=200000)
        self.assertEqual(m._word_printed, m.show_print)

    def test_build_sets_hold_the_words_own_syllables(self):
        e, m = _sectioned("10-12", words_total=24)
        _play_through(m)
        build = [_parse_stimulus(s) for s in _stimuli(e)
                 if ";sec=build;" in s]
        self.assertTrue(build)
        with_own = [r for r in build
                    if any(k == "F6" for _l, _w, k in r["opts"])]
        self.assertGreaterEqual(len(with_own), len(build) // 2)

    def test_replay_while_building_says_the_word(self):
        _e, m = _sectioned("16+")
        said = []
        m._speak_word = lambda: said.append("word")
        m._speak_syllable = lambda k: said.append(k)
        _tick_until(m, 0.0, lambda x: x.section == "build"
                    and _set_open(x), limit=400000)
        self.assertTrue(m.replay())
        self.assertEqual(said[-1], "word")


class FamilyTests(unittest.TestCase):
    def test_the_ladder_climbs_on_three_and_falls_on_one(self):
        _e, m = _sectioned()
        m._set_family, m._set_family_n = "vowel", 1
        for _ in range(3):
            m._move_family(True)
        self.assertEqual(m.family_levels["vowel"], 1)
        m._move_family(False)
        self.assertEqual(m.family_levels["vowel"], 0)
        m.family_levels["vowel"] = 3
        for _ in range(3):
            m._move_family(True)
        self.assertIn("vowel", m.family_mastered)

    def test_a_set_without_its_family_foil_moves_nothing(self):
        _e, m = _sectioned()
        m.family_levels["coda"] = 2
        m._set_family, m._set_family_n = "coda", 0
        for _ in range(3):
            m._move_family(True)
        m._move_family(False)
        self.assertEqual(m.family_levels["coda"], 2)

    def test_a_family_is_taught_three_words_at_a_time(self):
        _e, m = _sectioned()
        focus = []
        for _ in range(9):
            m._advance_focus()
            focus.append(m._focus_family)
        self.assertEqual(len(set(focus[0:3])), 1)
        self.assertEqual(len(set(focus[3:6])), 1)
        self.assertNotEqual(focus[0], focus[3])
        self.assertNotEqual(focus[3], focus[6])

    def test_pick_sets_show_their_family_at_its_level(self):
        from finger_rehab.game.modes.syllables_foils import FAMILY_KIND
        _e, m = _sectioned(words_total=18)
        for fam in m.family_levels:
            m.family_levels[fam] = 2
        _tick_until(m, 0.0, lambda x: x.section == "pick"
                    and _set_open(x))
        fam = m._set_family
        self.assertIn(fam, m.profile.families)
        self.assertEqual(m._set_family_level, 2)
        kinds = [o.kind for o in m.option_set.options]
        self.assertEqual(kinds.count(FAMILY_KIND[fam]), m._set_family_n)
        self.assertLessEqual(m._set_family_n, 2)
        row = m._pack_stimulus(m._sets[-1]) if m._sets else ""
        self.assertIn(";fam=", row)


class SpeedTests(unittest.TestCase):
    def _to_speed(self, band="13-15"):
        e, m = _sectioned(band, words_total=6)
        t = 0.0
        answered = set()
        for _ in range(400000):
            if m.phase == "flash":
                return e, m, t
            m._tick(t)
            if _set_open(m) and t >= m._spawn_t + 0.5:
                if m.trial_counter not in answered:
                    answered.add(m.trial_counter)
                    m.queue_press(_press(m.option_set.target_lane, t))
            t += 0.05
        raise AssertionError("no speed trial")

    def test_flash_then_mask_then_four_words(self):
        _e, m, t = self._to_speed()
        expo = m._expo_s
        t0 = m._phase_t0
        word = m.speed_word
        self.assertLessEqual(len(word.word), m.SPEED_MAX_LETTERS)
        t = _tick_until(m, t, lambda x: x.phase == "mask", step=0.01)
        self.assertAlmostEqual(m._phase_t0 - t0, expo, delta=0.02)
        t = _tick_until(m, t, lambda x: x.phase == "speed", step=0.01)
        opts = m.speed_options
        self.assertEqual(len(opts), 4)
        self.assertEqual(sum(1 for _l, _w, tg in opts if tg), 1)
        self.assertEqual({w for _l, w, tg in opts if tg}, {word.word})
        self.assertEqual(len({ln for ln, _w, _t in opts}), 4)
        self.assertEqual(m.current_timeout_s, m.SPEED_LIMIT_S)
        from finger_rehab.hardware import eeg_trigger
        self.assertEqual(eeg_trigger.CODES["stim_choice_speed"], 53)
        self.assertEqual(m.eeg_stim_code(), 53)

    def test_one_press_answers_and_the_row_says_so(self):
        e, m, t = self._to_speed()
        t = _tick_until(m, t, lambda x: x.phase == "speed")
        m.queue_press(_press(m._speed_tlane, t + 0.6))
        m._tick(t + 0.6)
        row = _parse_stimulus(_stimuli(e)[-1])
        self.assertEqual(row["sec"], "speed")
        self.assertEqual((row["first"], row["err"]), ("ok", "ok"))
        self.assertEqual(int(row["expo"]), 600)
        self.assertEqual(sum(1 for _l, _w, k in row["opts"] if k == "t"),
                         1)
        # A second press changes nothing.
        before = len(_stimuli(e))
        m.queue_press(_press(m._speed_tlane, t + 0.8))
        m._tick(t + 0.8)
        self.assertEqual(len(_stimuli(e)), before)

    def test_the_exposure_staircase(self):
        _e, m = _sectioned("13-15")
        m._expo_s = 0.70
        m._move_expo(True)
        self.assertAlmostEqual(m._expo_s, 0.62)
        m._move_expo(False)
        self.assertAlmostEqual(m._expo_s, 0.70)
        self.assertEqual(len(m._expo_reversals), 1)
        m._move_expo(True)
        m._move_expo(True)
        self.assertAlmostEqual(m._expo_s, 0.70)
        m._move_expo(True)
        self.assertAlmostEqual(m._expo_s, 0.62)
        self.assertEqual(len(m._expo_reversals), 2)
        m._expo_s = m.EXPO_MIN_S
        for _ in range(3):
            m._move_expo(True)
        self.assertAlmostEqual(m._expo_s, m.EXPO_MIN_S)
        m._expo_s = m.EXPO_MAX_S
        m._move_expo(False)
        self.assertAlmostEqual(m._expo_s, m.EXPO_MAX_S)

    def test_a_board_drop_flashes_the_same_word_again(self):
        e, m, t = self._to_speed()
        m.engine._drop_overlaps = lambda *a: True
        word = m.speed_word
        done = m._speed_done
        t = _tick_until(m, t, lambda x: x.phase == "speed")
        t = _tick_until(m, t, lambda x: x.phase == "flash")
        row = _parse_stimulus(_stimuli(e)[-1])
        self.assertEqual(row["err"], "device_drop")
        self.assertEqual(m._speed_done, done)
        self.assertIs(m.speed_word, word)
        self.assertEqual(m._speed_records, [])

    def test_a_pause_in_the_flash_shows_it_again(self):
        _e, m, t = self._to_speed()
        word = m.speed_word
        m._tick(t + 0.05)
        m.on_resume(2.0)
        self.assertEqual(m.phase, "flash")
        self.assertIs(m.speed_word, word)

    def test_replay_does_nothing_in_the_speed_check(self):
        _e, m, t = self._to_speed()
        _tick_until(m, t, lambda x: x.phase == "speed")
        self.assertFalse(m.replay())


class RealEngineMarkerTests(unittest.TestCase):
    """A sectioned block for a 12 year old through the real engine and
    marker writer: each speed trial's four words are marked 53 and
    answered by exactly one response byte, and its row names the
    target lane."""

    @classmethod
    def setUpClass(cls):
        from tests.test_syllables_eeg import _run_block
        cls.result = _run_block(4, "correct", sections=True, age="12")

    def test_the_block_ends(self):
        self.assertEqual(self.result["phase"], "done")

    def test_each_speed_trial_is_marked_53_with_one_response(self):
        codes = self.result["codes"]
        idx = [i for i, c in enumerate(codes) if c == 53]
        self.assertEqual(len(idx), 20)
        stims = {30, 31, 32, 33, 34, 35, 36, 37, 38, 50, 51, 53}
        for i, start in enumerate(idx):
            end = next((j for j in range(start + 1, len(codes))
                        if codes[j] in stims), len(codes))
            responses = [c for c in codes[start + 1:end]
                         if 100 <= c <= 131]
            self.assertEqual(len(responses), 1, (i, responses))
            self.assertTrue(100 <= responses[0] <= 107, responses)

    def test_speed_rows_name_the_target_lane(self):
        rows = [r for r in self.result["trials"]
                if ";sec=speed;" in r.get("stimulus", "")]
        self.assertEqual(len(rows), 20)
        for r in rows:
            row = _parse_stimulus(r["stimulus"])
            tl = [ln for ln, _w, k in row["opts"] if k == "t"][0]
            self.assertEqual(tl, int(row["tlane"]))
            self.assertEqual(r["correct_keys"], str(tl))


class StatsTests(unittest.TestCase):
    def test_block_stats_carry_the_sections(self):
        _e, m = _sectioned("13-15", words_total=8)
        _play_through(m)
        self.assertEqual(m.end_reason, "completed")
        st = m.block_stats()["sections"]
        self.assertEqual([n for n, _k in st["plan"]],
                         ["review", "pick", "build", "speed"])
        self.assertEqual(set(st["by_section"]), {"review", "pick", "build"})
        self.assertEqual(st["reached"], "speed")
        self.assertEqual(st["speed"]["n"], 20)
        self.assertEqual(st["speed"]["acc"], 1.0)
        # Right every time: the exposure only went down.
        self.assertLess(st["speed"]["expo_final_ms"], 600)
        self.assertEqual(st["n_shown"], 0)
        self.assertEqual(set(st["families"]), set(m.profile.families))

    def test_a_sticker_per_section(self):
        # The warm-up words and hear and pick are one part to the
        # player, so the review earns no sticker of its own (2 October
        # 2026).
        _e, m = _sectioned("6-9", words_total=8)
        _play_through(m)
        names = [n for n, _q in m.section_plan]
        joined = 1 if names[:2] == ["review", "pick"] else 0
        self.assertEqual(m.stickers, len(m.section_plan) - joined)


class NotebookTests(unittest.TestCase):
    """The notebook reads the sectioned rows apart from the
    single-section block and reads the speed rows on their own."""

    @classmethod
    def setUpClass(cls):
        from tests.test_syllables_notebook import _load_ra
        cls.ra = _load_ra()

    def _trials(self):
        import pandas as pd
        e, m = _sectioned("13-15", words_total=8)
        _play_through(m)
        rows = []
        for i, call in enumerate(e.log_trial.call_args_list):
            rows.append({"mode": "syllables", "session": "s1",
                         "game": "g1", "hand_mode": "right",
                         "trial": i + 1, "block": 1,
                         "stimulus": call.kwargs.get("stimulus"),
                         "error_type": call.kwargs.get("error_type", ""),
                         "time_difference_ms": 500.0, "early_late": ""})
        return pd.DataFrame(rows), m

    def test_speed_rows_stay_out_of_the_set_frame(self):
        trials, m = self._trials()
        sy = self.ra.syllable_set_frame(trials)
        self.assertEqual(len(sy), len(m._sets))
        self.assertTrue(sy["section"].isin(["review", "pick",
                                            "build"]).all())
        sp = self.ra.syllable_speed_frame(trials)
        self.assertEqual(len(sp), 20)
        self.assertTrue(sp["first_ok"].all())
        self.assertTrue((sp["expo_ms"] > 0).all())

    def test_the_sections_get_their_own_summary(self):
        trials, _m = self._trials()
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            out = self.ra.sec_syllables(trials)
        text = buf.getvalue()
        self.assertIn("THE CASE SITTING", text)
        # The on-screen name, QUICK LOOK, since 1 October 2026.
        self.assertIn("quick look", text)
        self.assertIn("sections", out)
        self.assertNotIn("sets", out)

    def test_a_shown_answer_counts_as_a_missed_word(self):
        import pandas as pd
        trials, _m = self._trials()
        rows = trials.copy()
        i = rows.index[rows["stimulus"].str.contains("sec=pick")][0]
        rows.loc[i, "stimulus"] = (rows.loc[i, "stimulus"]
                                   .replace("err=ok", "err=shown")
                                   .replace("shown=0", "shown=1"))
        sy = self.ra.syllable_set_frame(pd.DataFrame(rows))
        hit = sy[sy["shown"]]
        self.assertEqual(len(hit), 1)
        self.assertTrue(hit["missed"].all())


class ScreenTests(unittest.TestCase):
    def setUp(self):
        import pygame
        pygame.init()
        self.addCleanup(pygame.quit)

    def _screen(self, engine):
        from finger_rehab.ui.syllables_screen import SyllablesScreen
        screen = SyllablesScreen.__new__(SyllablesScreen)
        screen.engine = engine
        layout = MagicMock()
        layout.width = 1280
        layout.height = 800
        screen.layout = layout
        return screen

    def test_still_tiles_drop_in_then_stay(self):
        e, m = _sectioned()
        _tick_until(m, 0.0, _set_open)
        e.mode = m
        screen = self._screen(e)
        early = screen.tile_layout(m, m._spawn_t + 0.05)
        late = screen.tile_layout(m, m._spawn_t + 0.5)
        later = screen.tile_layout(m, m._spawn_t + 3.0)
        self.assertEqual({i["state"] for i in late}, {"still"})
        self.assertLess(early[0]["rect"].centery, late[0]["rect"].centery)
        self.assertEqual([i["rect"].center for i in late],
                         [i["rect"].center for i in later])
        self.assertEqual(len({i["rect"].size for i in late}), 1)

    def test_the_time_bar_runs_down(self):
        e, m = _sectioned()
        _tick_until(m, 0.0, _set_open)
        screen = self._screen(e)
        self.assertAlmostEqual(
            screen.time_bar_frac(m, m._spawn_t, m.fall_s), 1.0)
        self.assertAlmostEqual(
            screen.time_bar_frac(m, m._spawn_t + m.fall_s / 2, m.fall_s),
            0.5, places=2)
        self.assertEqual(
            screen.time_bar_frac(m, m._spawn_t + m.fall_s + 1, m.fall_s),
            0.0)

    def test_the_speed_words_are_drawn_alike_until_a_press(self):
        e, m, t = SpeedTests._to_speed(self)
        _tick_until(m, t, lambda x: x.phase == "speed")
        screen = self._screen(e)
        items = screen.speed_layout(m, m._spawn_t + 0.5)
        self.assertEqual(len(items), 4)
        self.assertEqual({i["state"] for i in items}, {"still"})
        self.assertEqual(len({i["rect"].size for i in items}), 1)
        self.assertEqual(len({i["alpha"] for i in items}), 1)

    def test_the_results_line_reports_the_speed_check(self):
        from finger_rehab.ui.screens import ResultsScreen
        sy = {"first_press_accuracy": 0.8,
              "sections": {"speed": {"n": 16, "acc": 0.75,
                                     "expo_final_ms": 420,
                                     "expo_reversal_mean_ms": None}}}
        self.assertEqual(ResultsScreen._syllables_advice(sy),
                         "Quick look: 16 words, 75% right, each shown "
                         "for 420 ms by the end.")
        # Advice about the level still comes first.
        sy["first_press_accuracy"] = 0.3
        self.assertIn("easier words", ResultsScreen._syllables_advice(sy))
        self.assertIsNone(ResultsScreen._syllables_advice(
            {"first_press_accuracy": 0.8}))

    def test_section_copy_names_every_section(self):
        from finger_rehab.ui.syllables_screen import SyllablesScreen
        for name in ("review", "pick", "build", "speed"):
            title, line = SyllablesScreen.SECTION_COPY[name]
            self.assertTrue(title and line)
            self.assertNotIn("—", title + line)


if __name__ == "__main__":
    unittest.main()
