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


class WatcherCommandTests(unittest.TestCase):
    """One rule for what gets registered, shared by the flags, the
    launch-time sync and the Settings switch."""

    def test_a_frozen_copy_registers_itself(self):
        self.assertEqual(autostart.watcher_command(frozen=True),
                         [sys.executable, "--watch"])

    def test_a_source_checkout_registers_main_py(self):
        cmd = autostart.watcher_command(frozen=False)
        self.assertEqual(cmd[0], sys.executable)
        self.assertEqual(cmd[-1], "--watch")
        self.assertTrue(Path(cmd[1]).is_file(), cmd[1])
        self.assertEqual(Path(cmd[1]).name, "main.py")


class UnsafeLocationTests(unittest.TestCase):
    """A LaunchAgent pointing into a disk image or a translocated copy
    is dead the moment the image is ejected or the app reopened."""

    def setUp(self):
        if sys.platform != "darwin":
            self.skipTest("macos only")

    def test_a_mounted_disk_image_is_refused(self):
        why = autostart.unsafe_location(
            "/Volumes/Finger Rehab/Finger Rehab.app/Contents/MacOS/Finger Rehab")
        self.assertIn("Applications", why)

    def test_a_translocated_copy_is_refused(self):
        why = autostart.unsafe_location(
            "/private/var/folders/x/T/AppTranslocation/1234/d/Finger Rehab.app"
            "/Contents/MacOS/Finger Rehab")
        self.assertIn("Applications", why)

    def test_applications_is_fine(self):
        self.assertIsNone(autostart.unsafe_location(
            "/Applications/Finger Rehab.app/Contents/MacOS/Finger Rehab"))


class FakeSchtasks:
    """A stand-in for the Windows task scheduler that remembers the one
    task, so /Query /XML answers with what /Create was given."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []
        self.tr: str | None = None

    def __call__(self, cmd):
        self.calls.append(list(cmd))
        verb = cmd[1] if len(cmd) > 1 else ""
        if cmd[0] == "launchctl":
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if verb == "/Create":
            self.tr = cmd[cmd.index("/TR") + 1]
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if verb == "/Delete":
            self.tr = None
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        if verb == "/Query":
            if self.tr is None:
                return subprocess.CompletedProcess(cmd, 1, stdout="",
                                                   stderr="not found")
            tr = self.tr
            if tr.startswith('"'):
                end = tr.index('"', 1)
                exe, args = tr[:end + 1], tr[end + 1:].strip()
            else:
                exe, _, args = tr.partition(" ")
            xml = (f"<Task><Actions><Exec><Command>{exe}</Command>"
                   f"<Arguments>{args}</Arguments></Exec></Actions></Task>")
            return subprocess.CompletedProcess(cmd, 0, stdout=xml, stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")


class SyncTests(unittest.TestCase):
    """The rule that runs on every normal launch of an installed copy.

    On macOS the plist is redirected into a temp folder, so the test
    reads and writes a real plist without touching the login items. On
    Windows the fake scheduler above stands in for schtasks.
    """

    def setUp(self):
        if sys.platform not in ("win32", "darwin"):
            self.skipTest("desktop only")
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.marker = root / "first_launch"
        self.runner = FakeSchtasks()
        self._orig_plist = autostart.agent_plist_path
        autostart.agent_plist_path = lambda: root / "agent.plist"
        self.addCleanup(setattr, autostart, "agent_plist_path",
                        self._orig_plist)
        if sys.platform == "win32":
            self.here = ["C:\\Users\\me\\AppData\\Local\\Programs\\Finger Rehab"
                         "\\Finger Rehab.exe", "--watch"]
            self.there = ["D:\\Finger Rehab\\Finger Rehab.exe", "--watch"]
        else:
            self.here = ["/Applications/Finger Rehab.app/Contents/MacOS"
                         "/Finger Rehab", "--watch"]
            self.there = ["/Users/me/Desktop/Finger Rehab.app/Contents"
                          "/MacOS/Finger Rehab", "--watch"]

    def _sync(self, cmd, frozen=True):
        return autostart.sync(cmd, frozen=frozen, runner=self.runner,
                              marker=self.marker)

    def _registered(self):
        return autostart.registered_command(self.runner)

    def test_a_source_checkout_never_registers_itself(self):
        what, note = self._sync(self.here, frozen=False)
        self.assertEqual(what, "source")
        self.assertEqual(note, "")
        self.assertIsNone(self._registered())
        self.assertFalse(self.marker.exists())

    def test_first_launch_registers_once_and_says_so(self):
        what, note = self._sync(self.here)
        self.assertEqual(what, "first")
        self.assertIn("plug a board in", note)
        self.assertIn("Settings", note)
        self.assertTrue(self.marker.exists())
        self.assertEqual(self._registered(), self.here)

    def test_the_next_launch_leaves_it_alone(self):
        self._sync(self.here)
        n = len(self.runner.calls)
        what, note = self._sync(self.here)
        self.assertEqual((what, note), ("kept", ""))
        # Reading the state is fine; writing it again is not.
        writes = [c for c in self.runner.calls[n:]
                  if c[1] in ("/Create", "bootstrap")]
        self.assertEqual(writes, [])

    def test_turned_off_in_settings_stays_off(self):
        self._sync(self.here)
        ok, _ = autostart.unregister(runner=self.runner)
        self.assertTrue(ok)
        what, note = self._sync(self.here)
        self.assertEqual((what, note), ("off", ""))
        self.assertIsNone(self._registered())

    def test_the_installer_registered_it_and_settings_turned_it_off(self):
        # The Windows installer runs --register-autostart before the
        # game ever opens, so the first launch finds it registered.
        ok, _ = autostart.register(list(self.here), runner=self.runner)
        self.assertTrue(ok)
        what, _ = self._sync(self.here)
        self.assertEqual(what, "kept")
        self.assertTrue(self.marker.exists())
        autostart.unregister(runner=self.runner)
        what, note = self._sync(self.here)
        self.assertEqual((what, note), ("off", ""))
        self.assertIsNone(self._registered())

    def test_a_refused_registration_is_retried_next_launch(self):
        refusing = FakeRunner(returncode=1)
        what, msg = autostart.sync(self.here, frozen=True, runner=refusing,
                                   marker=self.marker)
        self.assertEqual(what, "failed")
        self.assertTrue(msg)
        self.assertFalse(self.marker.exists())

    def test_a_moved_app_re_registers_its_new_path(self):
        self._sync(self.there)
        self.assertEqual(self._registered(), self.there)
        what, note = self._sync(self.here)
        self.assertEqual((what, note), ("moved", ""))
        self.assertEqual(self._registered(), self.here)

    def test_running_from_the_disk_image_refuses_and_says_drag(self):
        if sys.platform != "darwin":
            self.skipTest("macos only")
        what, note = self._sync(
            ["/Volumes/Finger Rehab/Finger Rehab.app/Contents/MacOS"
             "/Finger Rehab", "--watch"])
        self.assertEqual(what, "unsafe")
        self.assertIn("Applications", note)
        self.assertIsNone(self._registered())
        # Nothing was decided, so the real first launch still happens.
        self.assertFalse(self.marker.exists())


class MainFlagTests(unittest.TestCase):
    """The two flags the installer and the uninstaller run, hidden."""

    def _run_main(self, argv, register=None, unregister=None):
        import io
        from contextlib import redirect_stderr, redirect_stdout
        from unittest.mock import patch
        import main as main_mod
        out, err = io.StringIO(), io.StringIO()
        with patch.object(sys, "argv", ["main.py", *argv]), \
             patch.object(autostart, "register",
                          register or autostart.register), \
             patch.object(autostart, "unregister",
                          unregister or autostart.unregister), \
             redirect_stdout(out), redirect_stderr(err):
            code = main_mod.main()
        return code, out.getvalue(), err.getvalue()

    def test_register_prints_one_line_and_exits_zero(self):
        seen = {}
        def fake_register(cmd, poll_s=1.0, runner=None):
            seen["cmd"] = list(cmd)
            return True, "The game will start when a board is plugged in."
        code, out, err = self._run_main(["--register-autostart"],
                                        register=fake_register)
        self.assertEqual(code, 0)
        self.assertEqual(out.strip().splitlines(),
                         ["The game will start when a board is plugged in."])
        self.assertEqual(err, "")
        self.assertEqual(seen["cmd"], autostart.watcher_command())

    def test_a_refusal_goes_to_stderr_with_exit_one(self):
        code, out, err = self._run_main(
            ["--register-autostart"],
            register=lambda cmd, poll_s=1.0, runner=None:
                (False, "Windows refused to create the scheduled task."))
        self.assertEqual(code, 1)
        self.assertEqual(out, "")
        self.assertIn("refused", err)

    def test_unregister_exits_zero(self):
        called = []
        code, out, _ = self._run_main(
            ["--unregister-autostart"],
            unregister=lambda runner=None: (called.append(1) or
                                            (True, "Auto-start turned off.")))
        self.assertEqual(code, 0)
        self.assertEqual(called, [1])
        self.assertIn("turned off", out)


class SettingsSwitchTests(unittest.TestCase):
    """The Auto-start button on the real Settings screen, with the
    operating system replaced by the fake scheduler and a temp plist."""

    def setUp(self):
        if sys.platform not in ("win32", "darwin"):
            self.skipTest("desktop only")
        import pygame
        pygame.init()
        pygame.font.init()
        self.addCleanup(pygame.quit)
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        orig = autostart.agent_plist_path
        autostart.agent_plist_path = lambda: Path(self.tmp.name) / "a.plist"
        self.addCleanup(setattr, autostart, "agent_plist_path", orig)
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        from finger_rehab.ui.screens import DiagnosticsScreen
        cfg = Config.load()
        cfg.data.setdefault("ui", {})["resolution"] = [1280, 800]
        self.engine = GameEngine(cfg, KeyboardOnlySource())
        self.screen = DiagnosticsScreen(self.engine)
        self.runner = FakeSchtasks()
        self.screen._autostart_runner = self.runner
        self.screen._autostart_on = self.screen._read_autostart()
        self.screen.rebuild_panel()

    def _button(self):
        hits = [b for b in self.screen._panel_buttons
                if b.label.startswith("Auto-start")]
        self.assertEqual(len(hits), 1, [b.label for b in hits])
        return hits[0]

    def test_it_sits_with_the_firmware_buttons_and_is_drawn(self):
        import pygame
        b = self._button()
        self.assertTrue(self.screen._firmware_rect().contains(b.rect))
        for other in self.screen._panel_buttons:
            if other is not b:
                self.assertFalse(b.rect.colliderect(other.rect), other.label)
        self.screen.draw(pygame.Surface((1280, 800)))

    def test_it_reads_off_then_turns_on_for_the_games_own_path(self):
        b = self._button()
        self.assertEqual(b.label, "Auto-start: off")
        b.on_click()
        self.assertEqual(autostart.registered_command(self.runner),
                         autostart.watcher_command())
        self.assertEqual(self._button().label, "Auto-start: on")
        self.assertIn("plug", self.screen._port_status)

    def test_a_second_press_turns_it_off(self):
        self._button().on_click()
        self._button().on_click()
        self.assertIsNone(autostart.registered_command(self.runner))
        self.assertEqual(self._button().label, "Auto-start: off")
        self.assertIn("off", self.screen._port_status)


class TitleNoteTests(unittest.TestCase):
    """The one line the launch-time sync may leave on the title screen."""

    def setUp(self):
        import pygame
        pygame.init()
        pygame.font.init()
        self.addCleanup(pygame.quit)
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
        from finger_rehab.ui.screens import TitleScreen
        cfg = Config.load()
        cfg.data.setdefault("ui", {})["resolution"] = [1280, 800]
        self.engine = GameEngine(cfg, KeyboardOnlySource())
        self.screen = TitleScreen(self.engine)

    def _painted(self):
        import pygame
        import finger_rehab.ui.screens as screens_mod
        seen: list[str] = []
        original = screens_mod.draw_text
        def recorder(surf, text, pos, *args, **kwargs):
            seen.append(str(text))
            return original(surf, text, pos, *args, **kwargs)
        screens_mod.draw_text = recorder
        try:
            self.screen.draw(pygame.Surface((1280, 800)))
        finally:
            screens_mod.draw_text = original
        return seen

    def test_the_note_is_painted_when_set(self):
        self.engine.autostart_note = ("Auto-start is on: plug a board in "
                                      "and the game opens. Settings turns "
                                      "it off.")
        self.assertIn(self.engine.autostart_note, self._painted())

    def test_nothing_extra_is_painted_otherwise(self):
        self.engine.autostart_note = ""
        self.assertFalse([t for t in self._painted() if "Auto-start" in t])


if __name__ == "__main__":
    unittest.main()
