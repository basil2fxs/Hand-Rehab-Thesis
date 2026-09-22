"""A second copy of the game is refused before it touches the port.

main.py used to open the serial source, build the engine and only
then take the run lock, without reading the result. A double
double-click, or a click on the icon while the auto-started copy was
still unpacking, opened a second window. On Windows the COM port is
exclusive, so that second window silently fell back to keyboard mode
and a session could be recorded on the wrong copy. The watcher had no
lock of its own either, so a login task and a watcher started by hand
could both react to the same board arriving.
"""
from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import main as main_mod
from finger_rehab.hardware import autostart
from finger_rehab.utils import log as logutil


class _Quiet(unittest.TestCase):
    """Temp lock paths and no log file, so nothing lands in the repo."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.game_lock = self.root / "game.lock"
        p = patch.object(autostart, "run_lock_path",
                         lambda: self.game_lock)
        p.start()
        self.addCleanup(p.stop)
        p = patch.object(autostart, "user_root", lambda: self.root)
        p.start()
        self.addCleanup(p.stop)
        # logutil.setup runs once per process; marking it done keeps
        # main() from opening a log file under the checkout.
        p = patch.object(logutil, "_done", True)
        p.start()
        self.addCleanup(p.stop)


class GameLockTests(_Quiet):

    def test_a_second_copy_is_refused_before_the_port_is_opened(self):
        held = autostart.RunLock(self.game_lock)
        self.assertTrue(held.acquire())
        self.addCleanup(held.release)
        built = []
        err = io.StringIO()
        with patch.object(sys, "argv", ["main.py", "--source", "keyboard"]), \
                patch.object(main_mod, "_build_source",
                             lambda cfg, args: built.append(1)), \
                patch.object(sys, "stderr", err):
            rc = main_mod.main()
        self.assertEqual(rc, main_mod.ALREADY_RUNNING)
        self.assertEqual(built, [], "the source was opened anyway")
        self.assertIn("already running", err.getvalue())

    def test_the_lock_is_held_while_the_source_is_built(self):
        seen = []

        def fake_build(cfg, args):
            seen.append(autostart.game_is_running(self.game_lock))
            return None

        with patch.object(sys, "argv", ["main.py", "--source", "keyboard"]), \
                patch.object(main_mod, "_build_source", fake_build):
            rc = main_mod.main()
        self.assertEqual(rc, 2)
        self.assertEqual(seen, [True], "lock not held during the open")
        # Released on the way out, so the next launch is not refused.
        self.assertFalse(autostart.game_is_running(self.game_lock))

    def test_listing_ports_works_while_the_game_runs(self):
        held = autostart.RunLock(self.game_lock)
        self.assertTrue(held.acquire())
        self.addCleanup(held.release)
        with patch.object(sys, "argv", ["main.py", "--list-ports"]), \
                patch("finger_rehab.hardware.serial_source."
                      "list_available_ports", lambda: []):
            rc = main_mod.main()
        self.assertEqual(rc, 0)


class WatcherLockTests(_Quiet):

    def test_a_second_watcher_is_refused(self):
        held = autostart.RunLock(self.root / "watcher.lock")
        self.assertTrue(held.acquire())
        self.addCleanup(held.release)
        watched = []
        with patch.object(sys, "argv", ["main.py", "--watch"]), \
                patch.object(autostart, "watch",
                             lambda *a, **k: watched.append(1)):
            rc = main_mod.main()
        self.assertEqual(rc, 0)
        self.assertEqual(watched, [], "a second watcher started polling")

    def test_the_watcher_holds_its_lock_while_polling(self):
        seen = []

        def fake_watch(*a, **k):
            seen.append(autostart.game_is_running(self.root / "watcher.lock"))
            return autostart.WatchResult()

        with patch.object(sys, "argv", ["main.py", "--watch"]), \
                patch.object(autostart, "watch", fake_watch):
            rc = main_mod.main()
        self.assertEqual(rc, 0)
        self.assertEqual(seen, [True])
        self.assertFalse(autostart.game_is_running(self.root / "watcher.lock"))
        # The watcher must not take the GAME lock, or it would refuse
        # the very launch it exists to make.
        self.assertFalse(autostart.game_is_running(self.game_lock))


class ModeFlagTests(unittest.TestCase):

    def test_mode_flag_offers_every_mode_the_hub_can_start(self):
        from finger_rehab.game.engine import GameEngine
        self.assertEqual(set(main_mod.MODE_KEYS),
                         set(GameEngine._BLOCK_STARTERS))

    def test_reaction_is_accepted(self):
        with patch.object(sys, "argv", ["main.py", "--mode", "reaction"]):
            ns = main_mod.parse_args()
        self.assertEqual(ns.mode, "reaction")


if __name__ == "__main__":
    unittest.main()
