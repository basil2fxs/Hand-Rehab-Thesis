"""Trial Mode: the login's SESSION picker and the four lengths.

Free play is the hub as it always was. A length starts its preset at
LOG IN. No length plays Syllables: it is built for readers with
dyslexia and runs on its own with a dyslexic participant (28 September
2026). Every length plays games twice wherever the minutes allow,
because a second go is what shows improvement. The 45 and the 60 play
the study sitting's full-length games (family full); the 15 and the 30
play shortened games (family short) so that more of them fit twice.
Blocks pool within a family and never across
(docs/research/trial_mode.md).
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

APP = Path(__file__).resolve().parents[1]
LENGTHS = [(15, "trial_15"), (30, "trial_30"), (45, "study_battery"),
           (60, "trial_60")]
TRIALS = ("trial_15", "trial_30", "trial_60")
EIGHT = {"reaction", "rhythm", "echo", "force_pilot", "chords",
         "buzz_hunt", "pattern", "adaptive"}
CORE = {"reaction", "force_pilot", "chords"}
FAMILY = {"study_battery": "full", "trial_60": "full",
          "trial_15": "short", "trial_30": "short"}
REST_S = {"trial_15": 0.0, "trial_30": 120.0, "study_battery": 180.0,
          "trial_60": 180.0}


def _cfg(overlay: str | None = None):
    from finger_rehab.config import Config
    return Config.load(overlay) if overlay else Config.load()


def _key(st) -> tuple:
    return (st.mode, st.hand, st.phase, st.rest_before_s,
            st.rest_min_s, st.stretch_before_s, st.track, st.difficulty)


def _plans(cfg, name):
    from finger_rehab.game.battery import build_plan
    return [build_plan(cfg, code, "right", name) for code in ("P01", "P02")]


class PresetShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = _cfg()

    def test_the_picker_offers_the_four_lengths(self) -> None:
        from finger_rehab.game.battery import trial_options
        self.assertEqual(trial_options(self.cfg), LENGTHS)

    def test_no_length_plays_syllables(self) -> None:
        for _m, name in LENGTHS:
            for plan in _plans(self.cfg, name):
                self.assertNotIn("syllables", [s.mode for s in plan.steps],
                                 name)

    def test_every_block_is_one_of_the_eight_played_at_most_twice(self):
        for _m, name in LENGTHS:
            for plan in _plans(self.cfg, name):
                steps = plan.steps
                self.assertEqual({s.hand for s in steps}, {"right"})
                self.assertLessEqual({s.mode for s in steps}, EIGHT)
                self.assertLessEqual({s.phase for s in steps},
                                     {"pass1", "pass2"})
                pass1 = [s.mode for s in steps if s.phase == "pass1"]
                pass2 = [s.mode for s in steps if s.phase == "pass2"]
                self.assertEqual(len(pass1), len(set(pass1)), name)
                self.assertEqual(len(pass2), len(set(pass2)), name)
                self.assertLessEqual(set(pass2), set(pass1), name)
                first2 = next(s for s in steps if s.phase == "pass2")
                self.assertEqual(first2.rest_before_s, REST_S[name], name)
                # A second go comes after every first go.
                self.assertTrue(all(s.phase == "pass2"
                                    for s in steps[len(pass1):]), name)

    def test_each_family_plays_its_own_settings(self) -> None:
        from finger_rehab.game.battery import resolved_overrides
        full = resolved_overrides(self.cfg, "study_battery")
        short = resolved_overrides(self.cfg, "trial_short")
        for _m, name in LENGTHS:
            for plan in _plans(self.cfg, name):
                self.assertEqual(plan.family, FAMILY[name], name)
                self.assertEqual(plan.overrides,
                                 full if FAMILY[name] == "full" else short,
                                 name)

    def test_the_short_set_shortens_counts_and_nothing_else(self) -> None:
        from finger_rehab.game.battery import (_flatten, load_preset,
                                               resolved_overrides)
        own = set(_flatten(load_preset(self.cfg, "trial_short")
                           ["overrides"]))
        self.assertEqual(own, {
            "reaction.block_trials", "chords.subblocks",
            "chords.trials_per_subblock", "force_pilot.short_ladder",
            "buzz_hunt.loc_trials_per_hand", "buzz_hunt.span_trials",
            "echo.games", "pattern.soc_cycles_per_block",
            "pattern.random_block_trials"})
        full = resolved_overrides(self.cfg, "study_battery")
        short = resolved_overrides(self.cfg, "trial_short")
        self.assertLess(short["reaction"]["block_trials"],
                        full["reaction"]["block_trials"])
        # Everything the short set does not name comes from the study
        # sitting: the frozen windows, the rhythm cue, the echo ceiling.
        self.assertEqual(short["chords"]["sync_windows_ms"],
                         full["chords"]["sync_windows_ms"])
        self.assertEqual(short["reaction"]["response_windows_s"],
                         full["reaction"]["response_windows_s"])
        self.assertEqual(short["rhythm"], full["rhythm"])
        self.assertEqual(short["echo"]["max_len"], full["echo"]["max_len"])
        self.assertTrue(short["force_pilot"]["short_ladder"])

    def test_the_15_is_three_games_twice(self) -> None:
        for plan in _plans(self.cfg, "trial_15"):
            pass1 = [s.mode for s in plan.steps if s.phase == "pass1"]
            pass2 = [s.mode for s in plan.steps if s.phase == "pass2"]
            self.assertEqual(set(pass1), CORE)
            self.assertEqual(pass2, pass1)
            self.assertEqual(plan.budget_min, 15.0)

    def test_the_30_plays_all_eight_then_four_again(self) -> None:
        for plan in _plans(self.cfg, "trial_30"):
            pass1 = [s.mode for s in plan.steps if s.phase == "pass1"]
            pass2 = [s.mode for s in plan.steps if s.phase == "pass2"]
            self.assertEqual(set(pass1), EIGHT)
            self.assertEqual(pass2, [m for m in pass1
                                     if m in CORE | {"adaptive"}])
            self.assertEqual(plan.budget_min, 30.0)

    def test_the_45_is_eight_then_four_again(self) -> None:
        for plan in _plans(self.cfg, "study_battery"):
            pass1 = [s.mode for s in plan.steps if s.phase == "pass1"]
            pass2 = [s.mode for s in plan.steps if s.phase == "pass2"]
            self.assertEqual(set(pass1), EIGHT)
            self.assertEqual(pass2, [m for m in pass1
                                     if m in CORE | {"rhythm"}])
            self.assertEqual(plan.id, "healthy_one_hand_v3")

    def test_the_60_is_the_45_then_every_other_game_again(self) -> None:
        study = _plans(self.cfg, "study_battery")
        for s_plan, plan in zip(study, _plans(self.cfg, "trial_60")):
            n = len(s_plan.steps)
            self.assertEqual([_key(s) for s in plan.steps[:n]],
                             [_key(s) for s in s_plan.steps])
            pass1 = [s.mode for s in plan.steps if s.phase == "pass1"]
            pass2 = [s.mode for s in plan.steps if s.phase == "pass2"]
            # Every game twice.
            self.assertEqual(sorted(pass2), sorted(pass1))
            extra = plan.steps[n:]
            self.assertEqual([s.mode for s in extra],
                             [m for m in pass1 if m in
                              {"echo", "buzz_hunt", "pattern", "adaptive"}])
            self.assertGreater(extra[0].stretch_before_s, 0.0)
            self.assertEqual(plan.budget_min, 60.0)

    def test_each_length_keeps_its_own_id(self) -> None:
        from finger_rehab.game.battery import build_plan
        ids = {name: build_plan(self.cfg, "P01", "right", name).id
               for _m, name in LENGTHS}
        self.assertEqual(ids, {"trial_15": "trial_15_v2",
                               "trial_30": "trial_30_v2",
                               "study_battery": "healthy_one_hand_v3",
                               "trial_60": "trial_60_v2"})

    def test_a_length_without_its_preset_is_not_offered(self) -> None:
        from finger_rehab.game.battery import trial_options
        cfg = _cfg()
        cfg.data["protocol"]["trials"] = [
            {"minutes": 20, "preset": "no_such_preset"},
            {"minutes": 15, "preset": "trial_15"},
            {"minutes": "soon", "preset": "trial_30"}]
        self.assertEqual(trial_options(cfg), [(15, "trial_15")])

    def test_settings_from_a_missing_or_circular_preset_are_refused(self):
        from finger_rehab.game.battery import BatteryError, build_plan
        cfg = _cfg()
        cfg.data["protocol"]["presets"]["trial_short"]["overrides_from"] = \
            "no_such_preset"
        with self.assertRaises(BatteryError):
            build_plan(cfg, "P01", "right", "trial_15")
        cfg = _cfg()
        cfg.data["protocol"]["presets"]["trial_short"]["overrides_from"] = \
            "trial_15"
        with self.assertRaises(BatteryError):
            build_plan(cfg, "P01", "right", "trial_15")

    def test_the_lab_offers_no_length_and_no_syllables(self) -> None:
        # A length starts at LOG IN, before the RA has started the EEG
        # recording; the lab keeps PLAY ALL on the menu, which runs its
        # own sitting with the SRT.
        from finger_rehab.game.battery import build_plan, trial_options
        cfg = _cfg(str(APP / "config" / "eeg_lab.yaml"))
        self.assertEqual(trial_options(cfg), [])
        plan = build_plan(cfg, "P01", "right", "study_battery")
        modes = [s.mode for s in plan.steps]
        self.assertIn("srt", modes)
        self.assertNotIn("syllables", modes)
        self.assertEqual(plan.family, "full")


class NotebookFamilyTests(unittest.TestCase):
    """The notebook reads one family at a time: a shortened game is not
    the same measure as a full one, so the two never pool."""

    def _tree(self, root: Path) -> list[Path]:
        import json
        folders = []
        for who, family in (("P01", "full"), ("P02", "short"),
                            ("P03", None)):
            d = root / "2026-09-28" / f"{who}_100000_reaction"
            d.mkdir(parents=True)
            battery = {"id": "x", "preset": "x", "phase": "pass1",
                       "position": 1, "of": 6}
            if family:
                battery["family"] = family
            (d / "metadata.json").write_text(json.dumps({
                "participant": who, "visit": "1", "battery": battery,
                "block_summary": {"block": "reaction",
                                  "status": "completed"}}),
                encoding="utf-8")
            folders.append(d)
        return folders

    def test_one_family_is_read_and_the_other_counted(self) -> None:
        import pandas as pd
        from tests.test_cohort_notebook import _load_notebook
        ra = _load_notebook()
        with tempfile.TemporaryDirectory() as td:
            folders = self._tree(Path(td))
            cat = pd.DataFrame({"who": ["P01", "P02", "P03"],
                                "folder": [str(f) for f in folders]})
            self.assertEqual(ra.COHORT_FAMILY, "full")
            sel, dropped = ra.cohort_catalogue(cat)
            # A block written before blocks carried a family is full.
            self.assertEqual(sorted(sel["who"]), ["P01", "P03"])
            self.assertEqual(dropped["other_family"], 1)
            ra.COHORT_FAMILY = "short"
            try:
                sel, dropped = ra.cohort_catalogue(cat)
            finally:
                ra.COHORT_FAMILY = "full"
            self.assertEqual(list(sel["who"]), ["P02"])
            self.assertEqual(dropped["other_family"], 2)

    def test_a_code_with_hub_games_only_is_not_counted(self) -> None:
        # Syllables is played on its own with a dyslexic reader, from
        # the hub. A code with no sitting block is in no analysis table
        # and must not count in n.
        import pandas as pd
        from tests.test_cohort_notebook import _load_notebook
        ra = _load_notebook()
        sel = pd.DataFrame({"participant": ["P01", "P01", "P02", "D01"],
                            "phase": ["pass1", "", "pass2", ""]})
        people = pd.DataFrame({"participant": ["D01", "P01", "P02"]})
        kept, hub_only = ra.cohort_sitting_people(people, sel)
        self.assertEqual(list(kept["participant"]), ["P01", "P02"])
        self.assertEqual(hub_only, ["D01"])
        # A tree with no sitting block at all keeps its table.
        kept, hub_only = ra.cohort_sitting_people(people,
                                                  sel.assign(phase=""))
        self.assertEqual(list(kept["participant"]), ["D01", "P01", "P02"])
        self.assertEqual(hub_only, [])

    def test_every_second_go_of_every_length_is_read(self) -> None:
        # A game a length plays twice is read by the T rows (the
        # reliability core) or by the exploratory second-go table, never
        # by nothing.
        from tests.test_cohort_notebook import _load_notebook
        ra = _load_notebook()
        core = {m for _i, m, *_r in ra.COHORT_RELIABILITY_METRICS}
        second = {m for m, *_r in ra.COHORT_SECOND_GO_METRICS}
        self.assertEqual(core, CORE)
        cfg = _cfg()
        for _minutes, name in LENGTHS:
            for plan in _plans(cfg, name):
                again = {s.mode for s in plan.steps if s.phase == "pass2"}
                self.assertTrue(again, name)
                self.assertLessEqual(again, core | second,
                                     (name, sorted(again - core - second)))


class HubOnlyCodeTests(unittest.TestCase):
    """Syllables runs on its own with a dyslexic reader, from the hub.
    That code shares the sessions tree with the study, so the selection
    chapter has to name it and leave it out of n."""

    def test_a_hub_only_code_is_named_and_not_counted(self) -> None:
        import contextlib
        import io
        import random

        import pygame
        from tests import test_cohort_notebook as tc
        ra = tc._load_notebook()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            pygame.init()
            eng = tc._engine(root)
            try:
                rng = random.Random(3)
                for code in ("P01", "D01"):
                    eng.begin_session(code, "30", dominant_hand="right",
                                      visit="1")
                    eng._uncal_ack = {"left", "right"}
                    if code == "P01":
                        tc._play_battery(eng, "right", 250.0, rng,
                                         fail_from=9)
                    else:
                        tc._play_reaction(eng, "right", 400.0, rng)
                    eng.end_session()
            finally:
                eng._close_loggers()
                pygame.quit()
            cat = ra.build_catalogue(root=root)
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                cohort = ra.sec_cohort_selection(cat, root=root, min_n=1)
        self.assertEqual(set(cohort["sel"]["participant"]), {"P01", "D01"})
        self.assertEqual(list(cohort["people"]["participant"]), ["P01"])
        self.assertIn("1 participant(s)", buf.getvalue())
        self.assertIn("hub games only, with no sitting block: D01",
                      buf.getvalue())


class ShortForcePilotTests(unittest.TestCase):
    def test_a_short_block_flies_the_short_ladder(self) -> None:
        import pygame
        pygame.init()
        self.addCleanup(pygame.quit)
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.game.modes.force_pilot import SHORT_LADDER
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        with tempfile.TemporaryDirectory() as td:
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data["session"]["data_dir"] = td
            cfg.data["audio"]["enabled"] = False
            cfg.data["report"] = {"enabled": False}
            # The shipped config names no levels: it can only switch
            # ladders, never list them.
            self.assertNotIn("levels", cfg.data["force_pilot"])
            self.assertFalse(cfg.data["force_pilot"]["short_ladder"])
            cfg.data["force_pilot"]["short_ladder"] = True
            eng = GameEngine(cfg, KeyboardOnlySource())
            eng._screens = eng._build_screens()
            eng.begin_session("P07", "30", dominant_hand="right")
            eng.set_hand_mode("right")
            eng.begin_force_pilot_block()
            self.assertEqual([w.lvl for w in eng.mode.levels],
                             list(SHORT_LADDER))
            eng._abandon_if_in_block()
            eng._close_loggers()


class _LoginHarness(unittest.TestCase):
    def setUp(self) -> None:
        import pygame
        pygame.init()
        self._td = tempfile.TemporaryDirectory()
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [1280, 800]
        cfg.data["session"]["data_dir"] = self._td.name
        cfg.data["audio"]["enabled"] = False
        cfg.data["report"] = {"enabled": False}
        self.eng = GameEngine(cfg, KeyboardOnlySource())
        self.eng._screens = self.eng._build_screens()
        self.eng.show_title()
        self.title = self.eng._screens["title"]

    def tearDown(self) -> None:
        import pygame
        try:
            self.eng._abandon_if_in_block()
            self.eng._close_loggers()
        except Exception:
            pass
        self._td.cleanup()
        pygame.quit()

    def _log_in(self, name="P07", hand="right", trial=""):
        t = self.title
        t.name_input.text = name
        if hand:
            t.hand_seg.set(hand)
        t.trial_seg.set(trial)
        t._begin()


class LabLoginTests(unittest.TestCase):
    def test_the_lab_login_has_no_session_picker(self) -> None:
        import pygame
        pygame.init()
        self.addCleanup(pygame.quit)
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        with tempfile.TemporaryDirectory() as td:
            cfg = Config.load(APP / "config" / "eeg_lab.yaml")
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data["session"]["data_dir"] = td
            cfg.data["audio"]["enabled"] = False
            cfg.data["report"] = {"enabled": False}
            cfg.data["eeg"]["enabled"] = False
            eng = GameEngine(cfg, KeyboardOnlySource())
            eng._screens = eng._build_screens()
            title = eng._screens["title"]
            self.assertNotIn(title.trial_seg, title._fields)
            title.name_input.text = "P07"
            title.hand_seg.set("right")
            title._begin()
            self.assertIs(eng.screen_obj, eng._screens["hand_choice"])
            self.assertIsNone(eng._battery)
            eng._close_loggers()


class LoginTests(_LoginHarness):
    def test_the_picker_offers_free_play_then_the_lengths(self) -> None:
        seg = self.title.trial_seg
        self.assertEqual(seg.label, "SESSION")
        self.assertEqual([c for _k, c in seg.options],
                         ["Free play", "15 min", "30 min", "45 min",
                          "60 min"])
        self.assertEqual([k for k, _c in seg.options],
                         [""] + [name for _m, name in LENGTHS])
        self.assertEqual(seg.value, "")

    def test_free_play_opens_the_hand_screen(self) -> None:
        self._log_in(trial="")
        self.assertTrue(self.eng._session_active)
        self.assertIs(self.eng.screen_obj, self.eng._screens["hand_choice"])
        self.assertIsNone(self.eng._battery)
        self.assertEqual(self.eng.battery_preset, "study_battery")

    def test_a_length_starts_its_games_at_log_in(self) -> None:
        self._log_in(trial="trial_30")
        self.assertEqual(self.eng.battery_preset, "trial_30")
        self.assertIsNotNone(self.eng._battery)
        self.assertEqual(self.eng._battery["preset"], "trial_30")
        self.assertEqual(self.eng._battery["id"], "trial_30_v2")
        self.assertEqual(self.eng._battery["family"], "short")
        self.assertIsNot(self.eng.screen_obj,
                         self.eng._screens["hand_choice"])
        # P07 is order A: Reaction opens the sitting.
        self.assertTrue(self.eng.block_is_running())
        self.assertEqual(self.eng.current_block, "reaction")

    def test_a_length_needs_the_main_hand(self) -> None:
        self._log_in(name="Mara", hand=None, trial="trial_15")
        self.assertFalse(self.eng._session_active)
        self.assertIn("main hand", self.title.begin_note)

    def test_the_next_person_starts_on_free_play(self) -> None:
        self._log_in(trial="trial_15")
        self.eng._abandon_if_in_block()
        self.eng.end_session()
        self.eng.show_title()
        self.assertEqual(self.eng._screens["title"].trial_seg.value, "")
        self.assertEqual(self.eng.battery_preset, "study_battery")

    def test_play_all_on_the_hub_keeps_the_sessions_length(self) -> None:
        self._log_in(trial="trial_15")
        self.eng._abandon_if_in_block()
        self.eng._cancel_battery()
        self.assertTrue(self.eng.start_battery())
        self.assertEqual(self.eng._battery["preset"], "trial_15")


if __name__ == "__main__":
    unittest.main()
