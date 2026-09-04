"""What "every mode plays on the keyboard" actually means.

Eight of the ten do, on one hand (4 keys) and on both (8 keys). Two
do not, and cannot: Force Pilot scores a continuous force trace and
Buzz Hunt asks which finger was buzzed, and a keyboard can produce
neither a force nor a buzz. A keyboard surrogate for either would not
be the same measurement, it would be a made-up number in a study
dataset, so both refuse by design.

What was missing was the refusal actually refusing. The hub badged
the two cards NEEDS SENSOR HARDWARE, but the badge was advice only:
picking one anyway walked through the hand picker and opened a block,
which created a session folder with metadata.json and raw.csv in it
and then could never write a trial row. The guard now sits on
GameEngine.begin_game, which is the one route the hub, the hand
picker and the results screen's NEXT UP button all take.

So this file pins both halves:

  1. The eight take every mapped key, in left, right and both, driven
     through a real engine on a real KeyboardOnlySource, checked on
     the raw.csv rows that come out.
  2. The two are refused before a session folder exists, the screens
     say why, and with a sensor source attached they start normally.
"""
from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

# The eight that play on keys, and the block starter for each.
KEYBOARD_MODES = {
    "reaction": "begin_reaction_block",
    "adaptive": "begin_adaptive_block",
    "pattern": "begin_pattern_block",
    "chords": "begin_chords_block",
    "syllables": "begin_syllables_block",
    "mirror": "begin_mirror_block",
    "echo": "begin_echo_block",
    "rhythm": "begin_rhythm_block",
}


def _engine(root: Path, screens_stub: bool = True):
    """A real GameEngine on a real KeyboardOnlySource, writing into
    `root`. Screens are stubbed for the block-driving tests because a
    keypress does not need a rendered lane strip; the screen tests
    below build the real ones instead."""
    import pygame
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["audio"]["enabled"] = False
    cfg.data["session"]["data_dir"] = str(root)
    cfg.data["session"]["prefs_file"] = str(root / "prefs.json")
    cfg.data["session"]["participant"] = "P09"
    cfg.data["session"]["age"] = "30"
    cfg.data["session"]["suggest_code"] = "never"
    cfg.data["report"] = {"enabled": False}
    eng = GameEngine(cfg, KeyboardOnlySource())
    if screens_stub:
        gp = MagicMock()
        gp.lanes = []
        eng._screens = {"gameplay": gp, "results": MagicMock(),
                        "rhythm": gp, "syllables": gp, "echo": gp,
                        "mirror": gp, "mode_select": MagicMock()}
    else:
        eng._screens = eng._build_screens()
    del pygame
    return eng


class EveryKeyOfEveryKeyboardModeTests(unittest.TestCase):
    """The eight, driven for real. For each mode and each hand mode,
    fire every key in the map that hand mode selects and count the
    raw.csv press rows tagged detail="keyboard"."""

    def setUp(self) -> None:
        import pygame
        pygame.init()

    def tearDown(self) -> None:
        import pygame
        pygame.quit()

    def _drive(self, mode_key: str, hand: str):
        """Returns (keys fired, lanes those keys cover, keyboard-tagged
        raw rows, the hand mode the block actually ran in)."""
        import pygame
        from finger_rehab.game.modes._keys import (keymap_for_hand,
                                                   resolve_key)
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(Path(td))
            eng.set_hand_mode(hand)
            starter = getattr(eng, KEYBOARD_MODES[mode_key])
            if mode_key == "rhythm":
                from finger_rehab.audio.beatmap import Beatmap, Note
                starter(Beatmap(notes=[Note(t=1.0, lane=0)]))
                # Rhythm drops presses made before the countdown; that
                # gate is covered on its own and is not what this is
                # measuring.
                eng.mode._countdown_done = True
            else:
                starter()
            mode = eng.mode
            keymap = eng.cfg.get(keymap_for_hand(eng.hand_mode), {})
            for key_name in keymap:
                code = resolve_key(key_name)
                self.assertIsNotNone(code, f"{key_name} is not a real key")
                mode.handle_event(pygame.event.Event(
                    pygame.KEYDOWN, {"key": code, "mod": 0,
                                     "unicode": "", "scancode": 0}))
            mode.update(0.0)
            eng.raw_logger.stop()
            with open(eng.session_paths.raw_csv) as f:
                rows = list(csv.DictReader(f))
            kb = [r for r in rows if r.get("detail") == "keyboard"]
            return (len(keymap), sorted(set(keymap.values())), kb,
                    eng.hand_mode)

    def test_every_mode_answers_every_key_in_every_hand_mode(self) -> None:
        for mode_key in KEYBOARD_MODES:
            for hand in ("right", "left", "both"):
                with self.subTest(mode=mode_key, hand=hand):
                    n_keys, lanes, kb, ran_as = self._drive(mode_key, hand)
                    # Mirror is bilateral by design and forces both
                    # hands whatever it was asked for, so it always
                    # gets the eight-key map.
                    expect = "both" if mode_key == "mirror" else hand
                    self.assertEqual(ran_as, expect)
                    if expect == "both":
                        self.assertEqual(n_keys, 8)
                        self.assertEqual(lanes, list(range(8)))
                    else:
                        self.assertEqual(n_keys, 4)
                        self.assertEqual(lanes, list(range(4)))
                    self.assertEqual(len(kb), n_keys,
                        f"{mode_key} on {hand} swallowed a key")
                    for row in kb:
                        self.assertEqual(row["event"], "press")

    def test_the_shipped_keymaps_are_the_ones_on_the_device(self) -> None:
        # j k l ; for the right hand, a s d f for the left, and the
        # bilateral map is the two together over eight lanes.
        from finger_rehab.config import Config
        cfg = Config.load()
        right = cfg.get("game.keyboard_map")
        left = cfg.get("game.keyboard_map_left")
        both = cfg.get("game.keyboard_map_bilateral")
        self.assertEqual(sorted(right), sorted(["j", "k", "l", "semicolon"]))
        self.assertEqual(sorted(left), sorted(["a", "s", "d", "f"]))
        self.assertEqual(sorted(right.values()), [0, 1, 2, 3])
        self.assertEqual(sorted(left.values()), [0, 1, 2, 3])
        self.assertEqual(sorted(both.values()), list(range(8)))
        self.assertEqual(len(both), 8)


class SensorOnlyModesAreRefusedTests(unittest.TestCase):
    """Force Pilot and Buzz Hunt on a keyboard rig. The refusal has to
    happen before anything is written, because a session folder with no
    trials in it is worse than no folder: it looks like a participant
    who did nothing."""

    def setUp(self) -> None:
        import pygame
        pygame.init()

    def tearDown(self) -> None:
        import pygame
        pygame.quit()

    def test_the_two_are_the_two_the_battery_names(self) -> None:
        from finger_rehab.game.battery import HARDWARE_MODES
        from finger_rehab.ui.screens import ModeSelectScreen
        self.assertEqual(set(HARDWARE_MODES), {"force_pilot", "buzz_hunt"})
        self.assertEqual(ModeSelectScreen.NEEDS_HARDWARE,
                         set(HARDWARE_MODES))
        # And they are not among the eight this file drives.
        self.assertFalse(set(HARDWARE_MODES) & set(KEYBOARD_MODES))

    def test_the_hub_still_shows_all_ten_cards(self) -> None:
        # Refused, not hidden: a card that vanishes on a keyboard rig
        # would leave an RA wondering whether the build has the mode.
        from finger_rehab.ui.screens import ModeSelectScreen, playable_modes
        keys = [k for k, _t, _d in ModeSelectScreen.MODES]
        self.assertEqual(len(keys), 10)
        self.assertEqual(set(keys),
                         set(KEYBOARD_MODES) | {"force_pilot", "buzz_hunt"})
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(Path(td), screens_stub=False)
            playable = playable_modes(eng)
            self.assertEqual(set(playable), set(KEYBOARD_MODES))
            # And in card order, because NEXT UP walks this list.
            self.assertEqual(playable,
                             [k for k in keys if k in KEYBOARD_MODES])

    def test_begin_game_refuses_and_writes_nothing(self) -> None:
        for mode_key in ("force_pilot", "buzz_hunt"):
            with self.subTest(mode=mode_key):
                with tempfile.TemporaryDirectory() as td:
                    root = Path(td)
                    eng = _engine(root)
                    self.assertFalse(eng.begin_game(mode_key, "right"))
                    self.assertFalse(eng.block_is_running())
                    self.assertIsNone(eng.mode)
                    # Nothing on disk. This is the whole point of
                    # refusing here rather than at the mode's own
                    # first tick.
                    made = [p for p in root.rglob("*") if p.is_file()]
                    self.assertEqual(made, [], f"{mode_key} left {made}")

    def test_a_sensor_source_is_allowed_straight_through(self) -> None:
        # The mirror image: with something that provides samples, the
        # guard must not fire, or the fix has broken the real rig.
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource

        class _PretendSensors(KeyboardOnlySource):
            # provides_samples is a read-only property on the real
            # class, so a stand-in rather than a monkeypatched flag.
            @property
            def provides_samples(self) -> bool:
                return True

        for mode_key in ("force_pilot", "buzz_hunt"):
            with self.subTest(mode=mode_key):
                with tempfile.TemporaryDirectory() as td:
                    # Real screens: these two blocks show their own.
                    eng = _engine(Path(td), screens_stub=False)
                    eng.source = _PretendSensors()
                    self.assertTrue(eng.begin_game(mode_key, "right"))
                    self.assertTrue(eng.block_is_running())
                    self.assertEqual(eng.current_block, mode_key)
                    eng._abandon_if_in_block()

    def test_the_hub_refuses_the_pick_and_says_why(self) -> None:
        import pygame
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            eng = _engine(root, screens_stub=False)
            eng.show_title()
            eng.begin_session("P09", "30", dominant_hand="right")
            hub = eng._screens["mode_select"]
            eng.screen_obj = hub
            surf = pygame.Surface((1280, 800))
            hub.draw(surf)
            keys = [k for k, _t, _d in hub.MODES]
            for mode_key in ("force_pilot", "buzz_hunt"):
                btn = hub.buttons[keys.index(mode_key)]
                hub.handle_event(pygame.event.Event(
                    pygame.MOUSEBUTTONDOWN,
                    {"pos": btn.rect.center, "button": 1}))
                hub.handle_event(pygame.event.Event(
                    pygame.MOUSEBUTTONUP,
                    {"pos": btn.rect.center, "button": 1}))
                self.assertIs(eng.screen_obj, hub,
                    f"{mode_key} took the participant off the hub")
                self.assertFalse(eng.block_is_running())
                self.assertEqual(hub.pick_note, hub.NO_HARDWARE_NOTE)
                hub.draw(surf)
            # A playable card clears the note and moves on.
            hub.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONDOWN,
                {"pos": hub.buttons[keys.index("reaction")].rect.center,
                 "button": 1}))
            hub.handle_event(pygame.event.Event(
                pygame.MOUSEBUTTONUP,
                {"pos": hub.buttons[keys.index("reaction")].rect.center,
                 "button": 1}))
            self.assertEqual(hub.pick_note, "")
            self.assertIs(eng.screen_obj, eng._screens["setup"])

    def test_the_number_key_shortcut_is_refused_too(self) -> None:
        # The hub is drivable keyboard-only (1-9 then 0), so the digit
        # has to take the same route as the click.
        import pygame
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(Path(td), screens_stub=False)
            eng.show_title()
            eng.begin_session("P09", "30", dominant_hand="right")
            hub = eng._screens["mode_select"]
            eng.screen_obj = hub
            keys = [k for k, _t, _d in hub.MODES]
            digits = "1234567890"
            for mode_key in ("force_pilot", "buzz_hunt"):
                d = digits[keys.index(mode_key)]
                hub.handle_event(pygame.event.Event(
                    pygame.KEYDOWN, {"key": getattr(pygame, f"K_{d}"),
                                     "mod": 0, "unicode": d, "scancode": 0}))
                self.assertIs(eng.screen_obj, hub)
                self.assertEqual(hub.pick_note, hub.NO_HARDWARE_NOTE)

    def test_the_hand_picker_says_why_rather_than_doing_nothing(self) -> None:
        # Reached with the mode already set in config, which is how a
        # resumed or scripted session can land there. A card that
        # silently does nothing reads as a broken button.
        import pygame
        with tempfile.TemporaryDirectory() as td:
            eng = _engine(Path(td), screens_stub=False)
            eng.show_title()
            eng.begin_session("P09", "30", dominant_hand="right")
            setup = eng._screens["setup"]
            eng.screen_obj = setup
            eng.cfg.data.setdefault("game", {})["mode"] = "force_pilot"
            setup.handle_event(pygame.event.Event(
                pygame.KEYDOWN, {"key": pygame.K_r, "mod": 0,
                                 "unicode": "r", "scancode": 0}))
            self.assertFalse(eng.block_is_running())
            from finger_rehab.ui.screens import ModeSelectScreen
            self.assertEqual(setup.pick_note,
                             ModeSelectScreen.NO_HARDWARE_NOTE)
            setup.draw(pygame.Surface((1280, 800)))
            # A playable mode clears it.
            eng.cfg.data["game"]["mode"] = "reaction"
            setup.handle_event(pygame.event.Event(
                pygame.KEYDOWN, {"key": pygame.K_r, "mod": 0,
                                 "unicode": "r", "scancode": 0}))
            self.assertEqual(setup.pick_note, "")
            self.assertTrue(eng.block_is_running())
            eng._abandon_if_in_block()

    def test_the_study_battery_skips_them_with_the_same_reason(self) -> None:
        from finger_rehab.game.battery import BatteryStep, unplayable_reason
        keyboard = MagicMock()
        keyboard.provides_samples = False
        sensors = MagicMock()
        sensors.provides_samples = True
        for mode_key in ("force_pilot", "buzz_hunt"):
            with self.subTest(mode=mode_key):
                step = BatteryStep(mode=mode_key, hand="right",
                                   hand_requested="dominant")
                self.assertEqual(
                    unplayable_reason(step, keyboard, one_board=False),
                    "needs sensor hardware")
                self.assertEqual(
                    unplayable_reason(step, sensors, one_board=False), "")


if __name__ == "__main__":
    unittest.main()
