"""The quiet screens: skip controls inside their cards, the session's
hand on the menu, and the syllables prompt on the wire.

Rest periods used to put the skip control on its own at the foot of
the screen, under a card that showed the countdown, so players missed
"Space to skip". It now sits inside the card, straight under the
seconds. The menu names the session's hand and changes it in one
press. The prompt buzz in Syllables gets its own EEG byte, 52.
"""
from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _engine(td: str):
    from finger_rehab import config as config_mod
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    os.environ[config_mod.DATA_ROOT_ENV] = td
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["audio"]["enabled"] = False
    cfg.data["session"]["data_dir"] = td
    cfg.data["report"] = {"enabled": False}
    eng = GameEngine(cfg, KeyboardOnlySource())
    eng._screens = eng._build_screens()
    return eng


class _Pygame(unittest.TestCase):

    def setUp(self) -> None:
        import pygame
        pygame.init()
        self.addCleanup(pygame.quit)
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        old = os.environ.get("FINGER_REHAB_DATA_ROOT")
        self.addCleanup(
            lambda: os.environ.__setitem__("FINGER_REHAB_DATA_ROOT", old)
            if old is not None
            else os.environ.pop("FINGER_REHAB_DATA_ROOT", None))
        self.eng = _engine(self._td.name)
        self.eng.begin_session("P01", "30")
        self.eng.choose_session_hand("right")


class SkipSitsInsideTheCard(_Pygame):

    def _card_and_chip(self, gp):
        import pygame
        surf = pygame.Surface((1280, 800))
        gp.draw(surf)
        return self.eng._skip_chip_rect

    def test_the_countdown_card_holds_its_skip(self) -> None:
        import pygame
        self.eng.begin_game("reaction")
        gp = self.eng._screens["gameplay"]
        chip = self._card_and_chip(gp)
        self.assertIsNotNone(chip)
        # The card is 420 x 300 and centred.
        card = pygame.Rect(0, 0, 420, 300)
        card.center = (640, 400)
        self.assertTrue(card.contains(chip), (card, chip))
        self.eng.finish_block()

    def test_a_rest_gets_a_card_with_the_skip_under_the_seconds(
            self) -> None:
        import pygame
        self.eng.begin_game("chords")
        self.eng.skip_current_wait()
        self.eng.mode._enter_rest(time.perf_counter(), 30.0, "between",
                                  "Rest")
        gp = self.eng._screens["gameplay"]
        chip = self._card_and_chip(gp)
        self.assertIsNotNone(chip)
        card = pygame.Rect(0, 0, 440, 250)
        card.center = (640, 400)
        self.assertTrue(card.contains(chip), (card, chip))
        # Under the countdown, in the card's lower half.
        self.assertGreater(chip.centery, card.centery)
        self.eng.finish_block()

    def test_the_muscle_memory_rest_card_holds_its_skip(self) -> None:
        self.eng.begin_game("pattern")
        self.eng.skip_current_wait()
        m = self.eng.mode
        m._seg_idx = 1
        m._enter_rest(time.perf_counter(), 10.0, "between", "Rest")
        gp = self.eng._screens["gameplay"]
        chip = self._card_and_chip(gp)
        self.assertIsNotNone(chip)
        # Near the centre, not in the old bottom band.
        self.assertLess(chip.centery, 800 - 110 - 40)
        self.eng.finish_block()


class TheMenuNamesTheHand(_Pygame):

    def test_the_hand_button_reads_the_session_hand_and_changes_it(
            self) -> None:
        import pygame
        hub = self.eng._screens["mode_select"]
        self.eng.show_mode_select()
        hub.draw(pygame.Surface((1280, 800)))
        self.assertEqual(hub.hand_btn.label, "Right hand")
        hub.handle_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h,
                                            unicode="h", mod=0))
        self.assertIs(self.eng.screen_obj,
                      self.eng._screens["hand_choice"])
        self.eng.choose_session_hand("left")
        self.assertEqual(self.eng.session_hand(), "left")
        hub.draw(pygame.Surface((1280, 800)))
        self.assertEqual(hub.hand_btn.label, "Left hand")

    def test_the_cards_carry_one_short_line(self) -> None:
        from finger_rehab.ui.screens import ModeSelectScreen
        for key, title, desc in ModeSelectScreen.MODES:
            self.assertLessEqual(len(desc.split()), 6, key)


class ThePromptIsMarked(unittest.TestCase):

    def test_a_prompt_sends_stim_and_byte_52(self) -> None:
        import pygame
        pygame.init()
        self.addCleanup(pygame.quit)
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(td)
            sent, stims, events = [], [], []
            eng.source = SimpleNamespace(provides_samples=True)
            eng._send_stim = lambda lane: stims.append(lane) or True
            eng._schedule_cue_pulses = lambda lane: None
            eng._eeg_send = (lambda code, lane=None, t_event=None:
                             sent.append(code))
            eng.raw_logger = SimpleNamespace(
                queue_event=lambda name, **k: events.append((name, k)))
            self.assertTrue(eng.on_prompt_buzz(2, 7, time.perf_counter()))
            self.assertEqual(stims, [2])
            self.assertEqual(sent, [52])
            self.assertEqual(events[0][0], "prompt_buzz")
            self.assertIn("delivered=yes", events[0][1]["detail"])

    def test_no_motors_means_no_buzz_and_no_byte(self) -> None:
        import pygame
        pygame.init()
        self.addCleanup(pygame.quit)
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(td)
            sent = []
            eng._eeg_send = (lambda code, lane=None, t_event=None:
                             sent.append(code))
            self.assertIsNone(eng.on_prompt_buzz(2, 7, time.perf_counter()))
            self.assertEqual(sent, [])


if __name__ == "__main__":
    unittest.main()
