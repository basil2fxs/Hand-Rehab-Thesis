"""Each game's instruction said aloud, and a pause before the sitting's
first game (3 November 2026).

The one participant who ran a sitting alone rated the on-screen
instructions 2 of 5 and asked for a pause before the first trials. With
instructions.spoken on, the GET READY card's own lines are said in the
computer's own voice and the card is held until they have been; the
sitting's first game waits game.first_countdown_s before its first trial.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finger_rehab.audio import spoken  # noqa: E402


class _Card:
    def __init__(self) -> None:
        self.countdowns: list[float] = []
        self.lanes: list = []

    def start_countdown(self, seconds) -> None:
        self.countdowns.append(float(seconds))

    def __getattr__(self, name):          # every other screen call is a no-op
        return lambda *a, **k: None


def _engine(td: str, said: list, spoken_on: bool):
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [640, 480]
    cfg.data["audio"]["enabled"] = False
    cfg.data["session"]["data_dir"] = td
    cfg.data["report"] = {"enabled": False}
    cfg.data.setdefault("instructions", {})["spoken"] = spoken_on
    eng = GameEngine(cfg, KeyboardOnlySource())
    card = _Card()
    eng._screens = {"gameplay": card, "syllables": card, "force_pilot": card,
                    "buzz_hunt": card, "rhythm": MagicMock(), "mode_select": MagicMock(),
                    "results": MagicMock(), "hub": MagicMock()}
    eng._speaker = MagicMock()
    eng._speaker.speak.side_effect = said.append
    return eng, card


class LinesTests(unittest.TestCase):
    def test_the_card_lines_are_what_is_said(self):
        self.assertEqual(spoken.lines_for("reaction"),
                         "Press the finger that lights up, as fast as you can. "
                         "Sometimes nothing lights up: then keep still.")
        for mode in ("echo", "chords", "pattern", "adaptive", "mirror", "force_pilot",
                     "buzz_hunt", "syllables", "rhythm"):
            self.assertTrue(spoken.lines_for(mode), mode)
        self.assertIsNone(spoken.lines_for("no_such_game"))

    def test_say_always_writes_to_a_file(self):
        cmd = spoken.render_command("Hello.", Path("/tmp/x.wav"), platform="darwin")
        self.assertEqual(cmd[:3], ["say", "-o", "/tmp/x.wav"])
        win = spoken.render_command("It's here.", Path("C:/x.wav"), platform="win32")
        self.assertEqual(win[0], "powershell")
        self.assertIn("It''s here.", win[-1])

    @unittest.skipUnless(sys.platform == "darwin", "the macOS voice")
    def test_the_macos_voice_renders_a_wav(self):
        with tempfile.TemporaryDirectory() as td:
            path = spoken.render("Press the finger that lights up.", Path(td))
            self.assertIsNotNone(path)
            self.assertEqual(path.read_bytes()[:4], b"RIFF")


class EngineTests(unittest.TestCase):
    def test_the_card_is_said_and_held_until_it_has_been(self):
        said: list = []
        with tempfile.TemporaryDirectory() as td:
            eng, card = _engine(td, said, spoken_on=True)
            eng._session_games = 3                   # not the sitting's first game
            eng._begin_block("chords")
        self.assertEqual(said, [spoken.lines_for("chords")])
        self.assertGreaterEqual(card.countdowns[-1],
                                spoken.seconds_for(spoken.lines_for("chords")) + 1.5)

    def test_off_says_nothing_and_keeps_the_countdown(self):
        said: list = []
        with tempfile.TemporaryDirectory() as td:
            eng, card = _engine(td, said, spoken_on=False)
            eng._session_games = 3
            eng._begin_block("chords")
        self.assertEqual(said, [])
        self.assertEqual(card.countdowns[-1], float(eng.cfg.get("game.start_countdown_s")))

    def test_the_first_game_of_a_sitting_waits_longer(self):
        said: list = []
        with tempfile.TemporaryDirectory() as td:
            eng, card = _engine(td, said, spoken_on=False)
            eng._session_games = 0
            eng._begin_block("reaction")
            first = card.countdowns[-1]
            eng._session_games = 1
            eng._begin_block("reaction")
            later = card.countdowns[-1]
        self.assertEqual(first, float(eng.cfg.get("game.first_countdown_s")))
        self.assertEqual(later, float(eng.cfg.get("game.start_countdown_s")))
