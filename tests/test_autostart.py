"""The watcher that starts the game when a board is plugged in.

Nothing here touches the real operating system: registering is driven
through an injected runner that records the command it was handed, and
the port scan and the launcher are injected too. What IS real is the
lock, because a lock that only works in a test is worthless.
"""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from finger_rehab.hardware import autostart  # noqa: E402


class FakeRunner:
    """Stands in for schtasks and launchctl."""

    def __init__(self, returncode: int = 0) -> None:
        self.calls: list[list[str]] = []
        self.returncode = returncode

    def __call__(self, cmd):
        self.calls.append(list(cmd))
        return subprocess.CompletedProcess(cmd, self.returncode,
                                           stdout="", stderr="")


class RunLockTests(unittest.TestCase):
    """A real lock on a real file."""

    def test_a_second_holder_is_refused(self):
        with TemporaryDirectory() as td:
            path = Path(td) / "game.lock"
            first = autostart.RunLock(path)
            self.assertTrue(first.acquire())
            try:
                self.assertTrue(autostart.game_is_running(path))
                second = autostart.RunLock(path)
                self.assertFalse(second.acquire())
            finally:
                first.release()
            # Released, so the next process gets it. This is the case a
            # pid file gets wrong after a crash.
            self.assertFalse(autostart.game_is_running(path))

    def test_release_is_safe_without_acquire(self):
        with TemporaryDirectory() as td:
            autostart.RunLock(Path(td) / "game.lock").release()


class WatchTests(unittest.TestCase):
    """The decision the watcher makes on each pass."""

    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.lock = Path(self.tmp.name) / "game.lock"
        self.launched: list[list[str]] = []
        self.addCleanup(self.tmp.cleanup)

    def _launcher(self, cmd):
        self.launched.append(list(cmd))
        return True

    def _watch(self, port_sequence, iterations=None):
        seq = list(port_sequence)
        def ports_fn():
            return seq.pop(0) if seq else []
        return autostart.watch(
            ["game"], poll_s=0.1, ports_fn=ports_fn,
            launcher=self._launcher, lock_path=self.lock,
            iterations=iterations if iterations is not None
            else len(port_sequence),
            sleep_fn=lambda s: None)

    def test_a_board_arriving_starts_the_game(self):
        self._watch([[], ["COM3"]])
        self.assertEqual(self.launched, [["game"]])

    def test_a_board_already_there_at_login_does_not(self):
        # Logging in with the rig plugged in should not open the game:
        # the point is to react to someone plugging it in.
        self._watch([["COM3"], ["COM3"], ["COM3"]])
        self.assertEqual(self.launched, [])

    def test_it_starts_the_game_once_not_once_per_scan(self):
        self._watch([[], ["COM3"], ["COM3"], ["COM3"]])
        self.assertEqual(len(self.launched), 1)

    def test_a_replug_during_a_session_is_ignored(self):
        # The game holds the lock, so the unplug and replug that follows
        # must not open a second copy over the top of it.
        held = autostart.RunLock(self.lock)
        self.assertTrue(held.acquire())
        self.addCleanup(held.release)
        result = self._watch([[], ["COM3"]])
        self.assertEqual(self.launched, [])
        self.assertTrue(result.skipped_running)

    def test_closing_the_game_with_the_board_in_does_not_reopen_it(self):
        # No arrival edge while the board stays plugged in, so the user
        # can actually close the game and have it stay closed.
        self._watch([["COM3"], ["COM3"], ["COM3"], ["COM3"]])
        self.assertEqual(self.launched, [])

    def test_unplug_then_plug_reopens_it(self):
        self._watch([["COM3"], [], ["COM3"]])
        self.assertEqual(len(self.launched), 1)

    def test_a_failing_port_scan_does_not_kill_the_watcher(self):
        calls = {"n": 0}
        def angry_ports():
            calls["n"] += 1
            if calls["n"] == 2:
                raise OSError("USB hiccup")
            return ["COM3"] if calls["n"] > 2 else []
        result = autostart.watch(
            ["game"], poll_s=0.1, ports_fn=angry_ports,
            launcher=self._launcher, lock_path=self.lock,
            iterations=4, sleep_fn=lambda s: None)
        self.assertTrue(result.launched)
        self.assertGreaterEqual(calls["n"], 4)

    def test_the_poll_interval_cannot_spin(self):
        slept: list[float] = []
        autostart.watch(["game"], poll_s=0.0, ports_fn=lambda: [],
                        launcher=self._launcher, lock_path=self.lock,
                        iterations=2, sleep_fn=slept.append)
        self.assertTrue(all(s >= 0.1 for s in slept), slept)


class RegisterTests(unittest.TestCase):
    """What gets handed to the operating system."""

    def test_windows_registers_a_per_user_logon_task(self):
        if sys.platform != "win32":
            self.skipTest("windows only")
        runner = FakeRunner()
        ok, _ = autostart.register(["C:\\App\\Finger Rehab.exe", "--watch"],
                                   runner=runner)
        self.assertTrue(ok)
        cmd = runner.calls[0]
        self.assertIn("/SC", cmd)
        self.assertIn("ONLOGON", cmd)
        # No /RU means it runs as the logged-in user, which is what
        # keeps it free of an admin prompt on the Curtin machines.
        self.assertNotIn("/RU", cmd)

    def test_macos_writes_a_launch_agent_and_loads_it(self):
        if sys.platform != "darwin":
            self.skipTest("macos only")
        import plistlib
        runner = FakeRunner()
        path = autostart.agent_plist_path()
        existed = path.exists()
        backup = path.read_bytes() if existed else None
        try:
            ok, _ = autostart.register(["/Applications/FR.app/fr", "--watch"],
                                       runner=runner)
            self.assertTrue(ok)
            data = plistlib.loads(path.read_bytes())
            self.assertEqual(data["Label"], autostart.AGENT_LABEL)
            self.assertTrue(data["RunAtLoad"])
            self.assertEqual(data["ProgramArguments"][-1], "--watch")
            # bootout before bootstrap, or loading over a live agent
            # fails and the old command keeps running.
            verbs = [c[1] for c in runner.calls if len(c) > 1]
            self.assertEqual(verbs[:2], ["bootout", "bootstrap"])
        finally:
            if backup is not None:
                path.write_bytes(backup)
            elif path.exists():
                path.unlink()

    def test_unregister_is_safe_when_nothing_is_registered(self):
        if sys.platform not in ("win32", "darwin"):
            self.skipTest("desktop only")
        runner = FakeRunner()
        ok, msg = autostart.unregister(runner=runner)
        self.assertIsInstance(msg, str)
        self.assertTrue(msg)

    def test_status_answers_without_touching_anything(self):
        runner = FakeRunner(returncode=1)
        st = autostart.status(runner=runner)
        for key in ("supported", "registered", "game_running", "lock",
                    "where"):
            self.assertIn(key, st)


class LaunchTests(unittest.TestCase):
    def test_a_missing_executable_is_reported_not_raised(self):
        # The watcher runs unattended, so a bad path must not take it
        # down; it should report and keep watching.
        self.assertFalse(autostart.launch_game(
            [str(Path("/definitely/not/here/fr"))]))


if __name__ == "__main__":
    unittest.main()
