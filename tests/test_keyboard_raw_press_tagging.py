"""Audit finding #112: a keyboard-surrogate press is not tagged per trial,
so in a session with an Arduino attached (keyboard deliberately stays live
as a backup) a keyboard-injected press is indistinguishable from a real
FSR press. mirror.py already carried this fix (audit finding #75,
detail="keyboard" on the raw.csv press row) but the other seven modes that
build their own keyboard PressEvent in handle_event did not: reaction,
adaptive, pattern, chords, syllables, classic, rhythm. This drives each of
those modes through a real GameEngine + KeyboardOnlySource, fires one
mapped KEYDOWN, and checks the resulting raw.csv row is tagged."""
from __future__ import annotations

import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def _drive_keyboard_press(begin_fn_name: str, rhythm: bool = False):
    """Build a real engine on KeyboardOnlySource, begin the named block,
    fire one KEYDOWN on the first mapped key, and return the raw.csv rows
    tagged detail="keyboard"."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    import pygame
    pygame.init()
    try:
        from rehab.config import Config
        from rehab.game.engine import GameEngine
        from rehab.game.modes._keys import keymap_for_hand, resolve_key
        from rehab.hardware.keyboard_source import KeyboardOnlySource
        with tempfile.TemporaryDirectory() as td:
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [640, 480]
            cfg.data["audio"]["enabled"] = False
            cfg.data["session"]["data_dir"] = td
            cfg.data["session"]["participant"] = "Test Person"
            cfg.data["session"]["age"] = "30"
            cfg.data["report"] = {"enabled": False}
            eng = GameEngine(cfg, KeyboardOnlySource())
            gp = MagicMock()
            gp.lanes = []
            eng._screens = {"gameplay": gp, "results": MagicMock(),
                             "rhythm": gp, "syllables": gp}
            if rhythm:
                from rehab.audio.beatmap import Beatmap, Note
                bm = Beatmap(notes=[Note(t=1.0, lane=0)])
                getattr(eng, begin_fn_name)(bm)
                # Skip the countdown gate: rhythm's queue_press drops
                # any press made before it, which is a separate, already
                # -covered behaviour, not what this test is checking.
                eng.mode._countdown_done = True
            else:
                getattr(eng, begin_fn_name)()
            mode = eng.mode
            km = eng.cfg.get(keymap_for_hand(eng.hand_mode), {})
            key_name, lane = next(iter(km.items()))
            kc = resolve_key(key_name)
            ev = pygame.event.Event(
                pygame.KEYDOWN,
                {"key": kc, "mod": 0, "unicode": "", "scancode": 0})
            mode.handle_event(ev)
            mode.update(0.0)
            eng.raw_logger.stop()
            with open(eng.session_paths.raw_csv) as f:
                rows = list(csv.DictReader(f))
            return [r for r in rows if r.get("detail") == "keyboard"]
    finally:
        pygame.quit()


class KeyboardPressTaggedInRawCsvTests(unittest.TestCase):
    """Every mode with its own keyboard handle_event must log the same
    detail="keyboard" raw.csv press row mirror.py already logs, so a
    mixed session (Arduino attached, keyboard live as backup) can tell
    a keyboard-surrogate press apart from a genuine FSR press."""

    def test_reaction(self) -> None:
        rows = _drive_keyboard_press("begin_reaction_block")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "press")

    def test_adaptive(self) -> None:
        rows = _drive_keyboard_press("begin_adaptive_block")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "press")

    def test_pattern(self) -> None:
        rows = _drive_keyboard_press("begin_pattern_block")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "press")

    def test_chords(self) -> None:
        rows = _drive_keyboard_press("begin_chords_block")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "press")

    def test_syllables(self) -> None:
        rows = _drive_keyboard_press("begin_syllables_block")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "press")

    def test_classic(self) -> None:
        rows = _drive_keyboard_press("begin_classic_block")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "press")

    def test_rhythm(self) -> None:
        rows = _drive_keyboard_press("begin_rhythm_block", rhythm=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["event"], "press")


if __name__ == "__main__":
    unittest.main()
