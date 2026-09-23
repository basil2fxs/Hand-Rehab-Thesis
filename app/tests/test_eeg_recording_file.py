"""The lab folder has a place for ActiView's recordings, and every game
says which recording it belongs to.

ActiView writes the BDF; the game cannot. What it can do is name the
file at login, show the name on the game menu, keep a sessions/eeg/
folder ready beside its own session folders, and write the name into
each game's metadata.json, so a lab day comes home as one folder with
the pairing already written down. The session-start byte (240) now
goes out with the first game instead of the login: the researcher reads
the name on the menu and then starts the recording, and a 240 sent at
login would land before it.
"""

from __future__ import annotations

import json
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

from unittest.mock import MagicMock  # noqa: E402

from tests.test_eeg_contract import _EngineHarness as _Base  # noqa: E402


class _EngineHarness(_Base):
    """The contract harness plus the two menu screens a login and a
    logout move between."""

    def _make_engine(self, td, eeg_enabled=True):
        eng = super()._make_engine(td, eeg_enabled=eeg_enabled)
        eng._screens.setdefault("mode_select", MagicMock())
        eng._screens.setdefault("title", MagicMock())
        return eng

TODAY = time.strftime("%Y-%m-%d")


class TheRecordingIsNamedAtLogin(_EngineHarness):

    def _logged_in(self, td, who="P07"):
        eng = self._make_engine(td)
        eng.begin_session(who, "30")
        return eng

    def test_name_folder_and_second_login_the_same_day(self):
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._logged_in(td)
                self.assertEqual(eng.eeg_recording, f"P07_{TODAY}")
                folder = eng.eeg_recording_dir()
                self.assertEqual(folder, Path(td) / "eeg")
                self.assertTrue(folder.is_dir())
                name, found = eng.eeg_recording_status()
                self.assertEqual((name, found), (f"P07_{TODAY}.bdf", False))
                # ActiView saves it; the menu turns to "is in".
                (folder / name).write_bytes(b"BDF")
                eng._eeg_recording_checked = (0.0, False)
                self.assertTrue(eng.eeg_recording_status()[1])
                eng.end_session()
                # Same person, same day, second login: never told to
                # overwrite the first recording.
                eng.begin_session("P07", "30")
                self.assertEqual(eng.eeg_recording, f"P07_{TODAY}_2")
        finally:
            pygame.quit()

    def test_odd_participant_names_make_safe_file_names(self):
        from finger_rehab.game.engine import GameEngine
        self.assertEqual(GameEngine._file_safe("Basil T"), "Basil_T")
        self.assertEqual(GameEngine._file_safe("a/b:c"), "a_b_c")
        self.assertEqual(GameEngine._file_safe(""), "NA")

    def test_the_normal_game_names_nothing(self):
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td, eeg_enabled=False)
                eng.begin_session("P07", "30")
                self.assertIsNone(eng.eeg_recording)
                self.assertFalse((Path(td) / "eeg").exists())
        finally:
            pygame.quit()


class SessionStartRidesTheFirstGame(_EngineHarness):

    def test_240_waits_for_the_first_game_and_comes_once(self):
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td)
                eng.begin_session("P07", "30")
                self._settle(eng)
                self.assertNotIn(240, self._wire_codes(eng))
                eng.begin_classic_block()
                self._settle(eng)
                codes = self._wire_codes(eng)
                self.assertEqual(codes[:2], [240, 201])
                root = Path(eng.session_paths.root)
                eng.finish_block()
                self._settle(eng)
                eng.begin_classic_block()
                self._settle(eng)
                eng.finish_block()
                eng.end_session()
                codes = self._wire_codes(eng)
                self.assertEqual(codes.count(240), 1)
                self.assertEqual(codes[-1], 241)
                # Still a session-level byte: not in the game's raw.csv.
                from finger_rehab.hardware.eeg_trigger import parse_detail
                logged = [int(parse_detail(r["detail"])["code"])
                          for r in self._eeg_rows(root)]
                self.assertNotIn(240, logged)
                # And the game says which recording it belongs to.
                meta = json.loads((root / "metadata.json").read_text())
                self.assertEqual(meta["eeg"]["recording_file"],
                                 f"P07_{TODAY}.bdf")
                self.assertEqual(meta["eeg"]["recording_folder"], "eeg")
                self.assertFalse(meta["eeg"]["recording_present"])
        finally:
            pygame.quit()

    def test_a_login_with_no_game_leaves_the_wire_quiet(self):
        import pygame
        pygame.init()
        try:
            with tempfile.TemporaryDirectory() as td:
                eng = self._make_engine(td)
                eng.begin_session("P07", "30")
                eng.end_session()
                self._settle(eng)
                codes = self._wire_codes(eng)
                self.assertNotIn(240, codes)
                self.assertNotIn(241, codes)
        finally:
            pygame.quit()


class TheMenuSaysWhatToDo(unittest.TestCase):

    def test_the_line_before_and_after_the_file_appears(self):
        from finger_rehab.ui.screens import ModeSelectScreen
        state = {"found": False}
        engine = SimpleNamespace(
            eeg_recording_status=lambda: ("P07_2026-09-24.bdf",
                                          state["found"]),
            eeg_recording_dir=lambda: Path("/lab/EEG_Lab/sessions/eeg"))
        screen = SimpleNamespace(engine=engine)
        line = ModeSelectScreen.eeg_recording_line(screen)
        self.assertIn("record ActiView as P07_2026-09-24.bdf", line)
        self.assertIn("EEG_Lab/sessions/eeg", line)
        state["found"] = True
        self.assertEqual(ModeSelectScreen.eeg_recording_line(screen),
                         "EEG recording P07_2026-09-24.bdf is in "
                         "EEG_Lab/sessions/eeg")
        engine.eeg_recording_status = lambda: (None, False)
        self.assertEqual(ModeSelectScreen.eeg_recording_line(screen), "")


class TheLabFolderShipsTheRecordingFolder(unittest.TestCase):

    def test_sessions_eeg_is_there_with_its_note_and_data_survives(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "blp", ROOT / "scripts" / "build_lab_package.py")
        blp = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(blp)
        with tempfile.TemporaryDirectory() as td:
            pkg = Path(td) / "lab"
            blp.assemble(pkg=pkg)
            note = pkg / "sessions" / "eeg" / "README.txt"
            self.assertTrue(note.is_file())
            self.assertIn("P07_2026-09-24.bdf", note.read_text())
            # A used folder: recordings and game data are never touched
            # by a rebuild.
            (pkg / "sessions" / "eeg" / "P07_2026-09-24.bdf").write_bytes(b"x")
            day = pkg / "sessions" / "2026-09-24" / "P07_120000_reaction"
            day.mkdir(parents=True)
            (day / "trials.csv").write_text("t\n")
            blp.assemble(pkg=pkg)
            self.assertTrue((pkg / "sessions" / "eeg" /
                             "P07_2026-09-24.bdf").is_file())
            self.assertTrue((day / "trials.csv").is_file())


if __name__ == "__main__":
    unittest.main()
