"""Trial Mode: the login's SESSION picker and the four lengths.

Free play is the hub as it always was. A length starts its preset at
LOG IN. Every length plays the study battery's own blocks with the
study battery's own settings (overrides_from), so a block of one pass
pools across lengths; the 45 is the pre-registered sitting itself, and
the 60 is that sitting block for block with four second goes after it
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
CORE = {"reaction", "force_pilot", "chords"}
SECOND_GOES = ["rhythm", "echo", "pattern", "adaptive"]


def _cfg(overlay: str | None = None):
    from finger_rehab.config import Config
    cfg = Config.load()
    if overlay:
        cfg = Config.load(overlay)
    return cfg


def _key(st) -> tuple:
    return (st.mode, st.hand, st.phase, st.rest_before_s,
            st.rest_min_s, st.stretch_before_s, st.track, st.difficulty)


class PresetShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cfg = _cfg()

    def test_the_picker_offers_the_four_lengths(self) -> None:
        from finger_rehab.game.battery import trial_options
        self.assertEqual(trial_options(self.cfg), LENGTHS)

    def test_every_length_plays_the_study_batterys_settings(self) -> None:
        from finger_rehab.game.battery import build_plan
        for code in ("P01", "P02"):
            study = build_plan(self.cfg, code, "right")
            for name in TRIALS:
                plan = build_plan(self.cfg, code, "right", name)
                self.assertEqual(plan.overrides, study.overrides,
                                 f"{name} {code}")

    def test_every_block_is_a_study_battery_block(self) -> None:
        from finger_rehab.game.battery import build_plan
        study_modes = {s.mode for s in build_plan(self.cfg, "P01",
                                                  "right").steps}
        for name in TRIALS:
            for code in ("P01", "P02"):
                plan = build_plan(self.cfg, code, "right", name)
                steps = plan.steps
                self.assertEqual({s.hand for s in steps}, {"right"})
                self.assertLessEqual({s.mode for s in steps}, study_modes)
                self.assertLessEqual({s.phase for s in steps},
                                     {"pass1", "pass2"})
                pass1 = [s.mode for s in steps if s.phase == "pass1"]
                pass2 = [s.mode for s in steps if s.phase == "pass2"]
                # Once a pass, and a second go only at a first one.
                self.assertEqual(len(pass1), len(set(pass1)), name)
                self.assertEqual(len(pass2), len(set(pass2)), name)
                self.assertLessEqual(set(pass2), set(pass1), name)
                if pass2:
                    first2 = next(s for s in steps if s.phase == "pass2")
                    self.assertEqual(first2.rest_before_s, 180.0, name)
                    self.assertEqual(first2.rest_min_s, 60.0, name)

    def test_the_15_is_the_core_once(self) -> None:
        from finger_rehab.game.battery import build_plan
        for code in ("P01", "P02"):
            plan = build_plan(self.cfg, code, "right", "trial_15")
            self.assertEqual({s.mode for s in plan.steps},
                             CORE | {"adaptive"})
            self.assertEqual({s.phase for s in plan.steps}, {"pass1"})
            self.assertEqual(plan.budget_min, 15.0)

    def test_the_30_retests_the_core_after_a_rest(self) -> None:
        from finger_rehab.game.battery import build_plan
        for code in ("P01", "P02"):
            plan = build_plan(self.cfg, code, "right", "trial_30")
            pass1 = [s.mode for s in plan.steps if s.phase == "pass1"]
            pass2 = [s.mode for s in plan.steps if s.phase == "pass2"]
            self.assertEqual(set(pass1), CORE | {"adaptive", "syllables"})
            # The core again, in the order pass 1 played it, as the
            # 45 minute sitting does.
            self.assertEqual(pass2, [m for m in pass1 if m in CORE])
            self.assertEqual(plan.budget_min, 30.0)

    def test_the_60_is_the_45_block_for_block_then_four_second_goes(
            self) -> None:
        from finger_rehab.game.battery import build_plan
        for code in ("P01", "P02"):
            study = build_plan(self.cfg, code, "right")
            plan = build_plan(self.cfg, code, "right", "trial_60")
            n = len(study.steps)
            head = plan.steps[:n]
            # The stretch before the first second go is the one change
            # a step can carry that the 45 does not have, and it sits
            # after the twelfth block.
            self.assertEqual([_key(s) for s in head],
                             [_key(s) for s in study.steps], code)
            extra = plan.steps[n:]
            pass1 = [s.mode for s in study.steps if s.phase == "pass1"]
            self.assertEqual([s.mode for s in extra],
                             [m for m in pass1 if m in SECOND_GOES], code)
            self.assertEqual({s.phase for s in extra}, {"pass2"})
            self.assertGreater(extra[0].stretch_before_s, 0.0)
            self.assertEqual(plan.budget_min, 60.0)

    def test_each_length_keeps_its_own_id(self) -> None:
        from finger_rehab.game.battery import build_plan
        ids = {name: build_plan(self.cfg, "P01", "right", name).id
               for _m, name in LENGTHS}
        self.assertEqual(ids["study_battery"], "healthy_one_hand_v2")
        self.assertEqual(len(set(ids.values())), len(ids))

    def test_a_length_without_its_preset_is_not_offered(self) -> None:
        from finger_rehab.game.battery import trial_options
        cfg = _cfg()
        cfg.data["protocol"]["trials"] = [
            {"minutes": 20, "preset": "no_such_preset"},
            {"minutes": 15, "preset": "trial_15"},
            {"minutes": "soon", "preset": "trial_30"}]
        self.assertEqual(trial_options(cfg), [(15, "trial_15")])

    def test_settings_from_a_missing_preset_are_refused(self) -> None:
        from finger_rehab.game.battery import BatteryError, build_plan
        cfg = _cfg()
        cfg.data["protocol"]["presets"]["trial_15"]["overrides_from"] = \
            "no_such_preset"
        with self.assertRaises(BatteryError):
            build_plan(cfg, "P01", "right", "trial_15")

    def test_the_lab_offers_no_length(self) -> None:
        # A length starts at LOG IN, before the RA has started the EEG
        # recording; the lab keeps PLAY ALL on the menu, which runs its
        # own sitting with the SRT.
        from finger_rehab.game.battery import build_plan, trial_options
        cfg = _cfg(str(APP / "config" / "eeg_lab.yaml"))
        self.assertEqual(trial_options(cfg), [])
        plan = build_plan(cfg, "P01", "right", "study_battery")
        self.assertIn("srt", [s.mode for s in plan.steps])


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
        self.assertEqual(self.eng._battery["id"], "trial_30_v1")
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
