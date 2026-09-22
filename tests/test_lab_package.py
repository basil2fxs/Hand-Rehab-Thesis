"""Tests for the EEG lab package.

docs/lab_package is the one folder handed to the EEG lab. Its top
level holds exactly five entries: Finger Rehab.exe, eeg_lab.yaml,
run_in_psychopy.py, README.txt and a fresh source/ copy of the game.
Three things are pinned here. The launcher picks the right route (the
exe on Windows, source/ elsewhere, or nothing) and refuses to start
from source without the packages the game needs.
scripts/build_lab_package.py produces that minimal folder from any
repo and clears the text files earlier layouts shipped. The two build
scripts and the CI workflow all go through that one script, so the
local folder and the CI zip cannot fork.
"""
from __future__ import annotations

import importlib.util
import io
import os
import re
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

LAUNCHER = REPO / "docs" / "lab_package" / "run_in_psychopy.py"
BUILDER = REPO / "scripts" / "build_lab_package.py"
TARGET = {"Finger Rehab.exe", "eeg_lab.yaml", "run_in_psychopy.py",
          "README.txt", "source"}
# What the game imports at run time; see PACKAGES in the launcher.
NEEDED = {"pygame-ce", "pyserial", "pyyaml", "numpy", "scipy", "librosa",
          "soundfile", "matplotlib"}
# Shipped by earlier package layouts; must never come back.
STALE = ("eeg_lab_setup.txt", "EEG Lab.bat", "run_from_source.py")


def _load(path: Path):
    """Import a script by path (neither folder is a package).

    Bytecode writing is off for the duration. Importing the launcher
    normally drops docs/lab_package/__pycache__ next to it, and that
    folder is the one copied to the EEG lab: its top level must hold
    exactly the four entries and nothing else. The stray cache made
    test_eeg_contract's completeness check fail on the second run of
    the suite, and would have been handed to the lab either way.
    """
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    was = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.dont_write_bytecode = was
    return mod


class LauncherTests(unittest.TestCase):
    """run_in_psychopy.py: opened in PsychoPy Coder, Run pressed."""

    def setUp(self) -> None:
        self.mod = _load(LAUNCHER)
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.here = Path(td.name)

    def _source_layout(self) -> None:
        (self.here / "source" / "finger_rehab").mkdir(parents=True)
        (self.here / "source" / "config").mkdir()
        (self.here / "source" / "main.py").write_text("")
        (self.here / "source" / "config" / "eeg_lab.yaml").write_text("")

    def _run(self, platform: str = "linux"):
        """main() with subprocess.call captured: (rc, call, stdout).
        The platform is passed explicitly so the route under test does
        not depend on the machine running the suite."""
        out = io.StringIO()
        with patch.object(self.mod.subprocess, "call",
                          return_value=0) as call, redirect_stdout(out):
            rc = self.mod.main(self.here, platform=platform)
        return rc, call, out.getvalue()

    def test_compiles(self) -> None:
        compile(LAUNCHER.read_text(), str(LAUNCHER), "exec")

    def test_source_route_runs_main_py_with_the_lab_config(self) -> None:
        self._source_layout()
        (self.here / "eeg_lab.yaml").write_text("eeg:\n  enabled: true\n")
        with patch.object(self.mod, "missing_packages", return_value=[]):
            rc, call, _ = self._run()
        self.assertEqual(rc, 0)
        # The interpreter PsychoPy ran the script with, the real
        # main.py, and the lab folder's own eeg_lab.yaml (the copy the
        # lab edits) rather than the one inside source/.
        call.assert_called_once_with(
            [sys.executable, str(self.here / "source" / "main.py"),
             "--config", str(self.here / "eeg_lab.yaml")],
            cwd=str(self.here / "source"))

    def test_source_route_falls_back_to_the_bundled_config(self) -> None:
        self._source_layout()
        with patch.object(self.mod, "missing_packages", return_value=[]):
            rc, call, _ = self._run()
        self.assertEqual(rc, 0)
        self.assertEqual(
            call.call_args.args[0][-1],
            str(self.here / "source" / "config" / "eeg_lab.yaml"))

    def test_exe_route_when_source_is_missing(self) -> None:
        exe = self.here / "Finger Rehab.exe"
        exe.write_bytes(b"")
        with patch.object(self.mod, "missing_packages") as missing:
            rc, call, _ = self._run()
        self.assertEqual(rc, 0)
        # The exe carries its own Python; no package check applies.
        missing.assert_not_called()
        call.assert_called_once_with([str(exe)], cwd=str(self.here))

    def test_source_wins_over_the_exe_off_windows(self) -> None:
        # A Mac or Linux PsychoPy cannot run the exe, so source/ is
        # the route there even with the exe beside it.
        self._source_layout()
        (self.here / "Finger Rehab.exe").write_bytes(b"")
        with patch.object(self.mod, "missing_packages", return_value=[]):
            _, call, _ = self._run(platform="darwin")
        self.assertEqual(call.call_args.args[0][0], sys.executable)

    def test_exe_wins_on_windows_and_needs_no_packages(self) -> None:
        # The lab desktop: the exe carries its own Python, so the first
        # Run must not stop at a pip line for PsychoPy's classic pygame.
        self._source_layout()
        exe = self.here / "Finger Rehab.exe"
        exe.write_bytes(b"")
        with patch.object(self.mod, "missing_packages") as missing:
            rc, call, out = self._run(platform="win32")
        self.assertEqual(rc, 0)
        missing.assert_not_called()
        call.assert_called_once_with([str(exe)], cwd=str(self.here))
        # And it says where the data goes, next to the exe.
        self.assertIn(str(self.here / "sessions"), out)

    def test_missing_pygame_ce_prints_uninstall_then_install(self) -> None:
        # PsychoPy's classic pygame owns the same package name, so the
        # fix is two pip lines in this order, ready to paste.
        self._source_layout()
        with patch.object(self.mod, "_pygame_is_ce", return_value=False), \
                patch.object(self.mod.importlib.util, "find_spec",
                             return_value=object()):
            rc, call, out = self._run()
        self.assertNotEqual(rc, 0)
        call.assert_not_called()
        lines = out.strip().splitlines()
        self.assertEqual(len(lines), 3, out)
        self.assertIn(f'"{sys.executable}" -m pip uninstall -y pygame',
                      lines[1])
        self.assertIn(f'"{sys.executable}" -m pip install pygame-ce',
                      lines[2])

    def test_pip_line_names_every_missing_package(self) -> None:
        self._source_layout()

        def find_spec(name):
            return None if name in ("librosa", "soundfile") else object()

        with patch.object(self.mod, "_pygame_is_ce", return_value=True), \
                patch.object(self.mod.importlib.util, "find_spec",
                             find_spec):
            rc, call, out = self._run()
        self.assertNotEqual(rc, 0)
        call.assert_not_called()
        # The header and one install line; no uninstall when pygame-ce
        # is already the pygame in place.
        self.assertEqual(len(out.strip().splitlines()), 2, out)
        self.assertIn("-m pip install librosa soundfile", out)
        self.assertNotIn("pygame-ce", out)
        self.assertNotIn("uninstall", out)

    def test_every_run_time_package_is_checked(self) -> None:
        self.assertEqual(set(self.mod.PACKAGES.values()), NEEDED)

    def test_classic_pygame_is_not_accepted(self) -> None:
        # Classic pygame imports fine and has no IS_CE; only pygame-ce
        # passes.
        fake = type(sys)("pygame")
        with patch.dict(sys.modules, {"pygame": fake}):
            self.assertFalse(self.mod._pygame_is_ce())
        fake.IS_CE = 1
        with patch.dict(sys.modules, {"pygame": fake}):
            self.assertTrue(self.mod._pygame_is_ce())

    def test_nothing_to_run_says_so_in_one_line(self) -> None:
        rc, call, out = self._run()
        self.assertEqual(rc, 1)
        call.assert_not_called()
        self.assertEqual(len(out.strip().splitlines()), 1, out)

    def test_launcher_invokes_main_py_only(self) -> None:
        # Same rule as the launchers in test_eeg_contract: no second
        # entry point may grow beside main.py.
        for match in re.findall(r"\S+\.py\b", LAUNCHER.read_text()):
            base = match.replace("\\", "/").rsplit("/", 1)[-1]
            self.assertEqual(base.strip("\"'"), "main.py",
                             f"launcher invokes {match}")

    def test_main_py_takes_the_config_flag_the_launcher_passes(self) -> None:
        import main as entry
        with patch.object(sys, "argv", ["main.py", "--config", "lab.yaml"]):
            self.assertEqual(entry.parse_args().config, "lab.yaml")


class BuilderTests(unittest.TestCase):
    """scripts/build_lab_package.py: the one assembly path for the
    folder and the CI zip."""

    def setUp(self) -> None:
        self.mod = _load(BUILDER)
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.repo = self.root / "repo"
        self._fake_repo(self.repo)
        self.pkg = self.repo / "docs" / "lab_package"
        self.exe = self.root / "Finger Rehab.exe"
        self.exe.write_bytes(b"MZ")

    @staticmethod
    def _fake_repo(root: Path) -> None:
        """The bits the builder copies, beside everything it must leave."""
        files = {
            "main.py": "", "requirements.txt": "",
            "finger_rehab/__init__.py": "",
            "finger_rehab/game/engine.py": "",
            "finger_rehab/game/__pycache__/engine.cpython-312.pyc": "",
            "finger_rehab/.DS_Store": "",
            "config/default.yaml": "a: 1\n",
            "config/eeg_lab.yaml": "eeg:\n  enabled: true\n",
            "config/user_settings.yaml": "serial: {}\n",
            "config/calibration/current_right.json": "{}",
            "assets/icons/app_icon.ico": "", "assets/music/a.mp3": "",
            "assets/.DS_Store": "",
            "tests/test_x.py": "", "sessions/P01/trials.csv": "",
            "docs/eeg_lab_setup.txt": "notes",
            "docs/lab_package/run_in_psychopy.py": "# launcher\n",
            "docs/lab_package/README.txt": "lab readme\n",
        }
        for rel, text in files.items():
            p = root / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text)

    def _cruft(self) -> None:
        """Leftovers from the old layout and a stale source/."""
        for name in STALE + (".DS_Store",):
            (self.pkg / name).write_text("old")
        (self.pkg / "__pycache__").mkdir()
        (self.pkg / "source" / "gone").mkdir(parents=True)
        (self.pkg / "source" / "gone" / "stale.py").write_text("")

    def test_package_holds_exactly_the_four_entries(self) -> None:
        self._cruft()
        names = self.mod.assemble(self.repo, self.pkg, self.exe)
        self.assertEqual(set(names), TARGET)
        self.assertEqual({p.name for p in self.pkg.iterdir()}, TARGET)
        self.assertEqual((self.pkg / "eeg_lab.yaml").read_text(),
                         (self.repo / "config" / "eeg_lab.yaml").read_text())
        self.assertEqual((self.pkg / "Finger Rehab.exe").read_bytes(), b"MZ")

    def test_source_is_rebuilt_fresh_with_what_main_py_needs(self) -> None:
        self._cruft()
        self.mod.assemble(self.repo, self.pkg, self.exe)
        src = self.pkg / "source"
        for rel in ("main.py", "requirements.txt", "finger_rehab/__init__.py",
                    "finger_rehab/game/engine.py", "config/default.yaml",
                    "config/eeg_lab.yaml", "assets/icons/app_icon.ico",
                    "assets/music/a.mp3"):
            self.assertTrue((src / rel).is_file(), rel)
        for rel in ("gone", "tests", "sessions", "docs",
                    "config/user_settings.yaml", "config/calibration"):
            self.assertFalse((src / rel).exists(), rel)
        for p in self.pkg.rglob("*"):
            self.assertNotIn(p.name, ("__pycache__", ".DS_Store"), str(p))
            self.assertNotEqual(p.suffix, ".pyc", str(p))

    def test_out_elsewhere_gets_the_launcher_copied(self) -> None:
        # CI assembles into bin/dist; the committed launcher must travel
        # with it.
        pkg = self.root / "zip" / "Finger Rehab EEG Lab"
        names = self.mod.assemble(self.repo, pkg, self.exe)
        self.assertEqual(set(names), TARGET)
        self.assertEqual((pkg / "run_in_psychopy.py").read_text(),
                         "# launcher\n")
        self.assertEqual((pkg / "README.txt").read_text(), "lab readme\n")

    def test_readme_is_short_and_plain(self) -> None:
        # Fifteen lines at most, ASCII only: the lab reads it once.
        text = (REPO / "docs" / "lab_package" / "README.txt").read_text()
        self.assertLessEqual(len(text.strip().splitlines()), 15)
        self.assertTrue(text.isascii())

    def test_without_an_exe_the_rest_still_builds(self) -> None:
        # A Mac build cannot make the exe: the folder keeps the one
        # already there, or ships without until CI supplies it.
        (self.pkg / "Finger Rehab.exe").write_bytes(b"old")
        names = self.mod.assemble(self.repo, self.pkg, None)
        self.assertEqual(set(names), TARGET)
        self.assertEqual((self.pkg / "Finger Rehab.exe").read_bytes(), b"old")
        (self.pkg / "Finger Rehab.exe").unlink()
        names = self.mod.assemble(self.repo, self.pkg, None)
        self.assertEqual(set(names), TARGET - {"Finger Rehab.exe"})

    def test_unknown_top_level_file_fails_the_build(self) -> None:
        # Anything outside the four is a mistake to fix, not to delete
        # unseen.
        (self.pkg / "notes.txt").write_text("")
        with self.assertRaises(SystemExit):
            self.mod.assemble(self.repo, self.pkg, self.exe)

    def test_command_line(self) -> None:
        # The call CI and build_app.bat make.
        pkg = self.root / "out"
        out = io.StringIO()
        with patch.object(self.mod, "REPO", self.repo), redirect_stdout(out):
            rc = self.mod.main(["--exe", str(self.exe), "--out", str(pkg)])
        self.assertEqual(rc, 0)
        self.assertEqual({p.name for p in pkg.iterdir()}, TARGET)
        for name in TARGET:
            self.assertIn(name, out.getvalue())

    def test_real_repo_source_runs_main_py(self) -> None:
        # The proof that source/ is complete: assemble the real repo
        # into a temp folder and run main.py from it with the lab
        # config, the way the launcher does. --list-ports loads the
        # config and the serial layer, then exits before any window.
        pkg = self.root / "real"
        self.mod.assemble(REPO, pkg, None)
        src = pkg / "source"
        for rel in ("tests", "sessions", "docs", "config/user_settings.yaml"):
            self.assertFalse((src / rel).exists(), rel)
        env = dict(os.environ, SDL_VIDEODRIVER="dummy",
                   SDL_AUDIODRIVER="dummy")
        r = subprocess.run(
            [sys.executable, str(src / "main.py"),
             "--config", str(pkg / "eeg_lab.yaml"), "--list-ports"],
            cwd=str(src), capture_output=True, text=True, env=env,
            timeout=120)
        self.assertEqual(r.returncode, 0, r.stderr)


class BuildWiringTests(unittest.TestCase):
    """Every build path goes through the one script, and none of them
    copies the old text files back in."""

    def _text(self, rel: str) -> str:
        p = REPO / rel
        if not p.is_file():
            self.skipTest(f"{rel} is not in this checkout")
        return p.read_text()

    def test_ci_assembles_exactly_the_target_package(self) -> None:
        import yaml
        wf = yaml.safe_load(self._text(".github/workflows/build-apps.yml"))
        steps = wf["jobs"]["build"]["steps"]
        (step,) = [s for s in steps
                   if s.get("name", "").startswith("Assemble EEG lab package")]
        run = step["run"]
        self.assertIn('python scripts/build_lab_package.py '
                      '--exe "bin/dist/Finger Rehab.exe" '
                      '--out "bin/dist/Finger Rehab EEG Lab"', run)
        self.assertIn('Compress-Archive -Path "bin/dist/Finger Rehab EEG Lab"',
                      run)
        self.assertNotIn("Copy-Item", run)
        for name in STALE:
            self.assertNotIn(name, run)
        # The script's manifest is the package: the four entries, no more.
        self.assertEqual(_load(BUILDER).TOP_LEVEL, TARGET)

    def test_mac_build_script_goes_through_the_builder(self) -> None:
        sh = self._text("builds/build_app.sh")
        self.assertIn('python3 scripts/build_lab_package.py '
                      '--exe "builds/Windows/Finger Rehab.exe"', sh)
        # No hand copy into the package folder may survive beside the
        # script call (the Linux branch's cp of its own binary is fine).
        for line in sh.splitlines():
            if line.lstrip().startswith("cp "):
                self.assertNotIn("docs/lab_package", line)
        for name in STALE:
            self.assertNotIn(name, sh)

    def test_windows_build_script_goes_through_the_builder(self) -> None:
        bat = self._text("builds/build_app.bat")
        self.assertIn('py scripts\\build_lab_package.py '
                      '--exe "bin\\dist\\Finger Rehab.exe"', bat)
        self.assertNotIn("docs\\lab_package\\", bat)
        for name in STALE:
            self.assertNotIn(name, bat)

    def test_gitignore_covers_every_generated_part(self) -> None:
        rules = self._text(".gitignore").splitlines()
        for rule in ("docs/lab_package/*.exe", "docs/lab_package/eeg_lab.yaml",
                     "docs/lab_package/source/"):
            self.assertIn(rule, rules)
        self.assertNotIn("docs/lab_package/eeg_lab_setup.txt", rules)


if __name__ == "__main__":
    unittest.main()


class MainInstallHasNoEEGTests(unittest.TestCase):
    """The game people install is the game, not the lab rig.

    Basil's rule: one main game, and a separate lab handover folder
    that holds the EEG side. The marker code stays in the binary
    (ripping it out of ten modes would fork the project and let
    Welber's copy drift), but no EEG FILE ships in the main install
    and nothing in it mentions EEG.
    """

    def test_the_game_spec_does_not_bundle_the_lab_config(self):
        spec = (REPO / "finger_rehab.spec").read_text()
        self.assertNotIn("eeg_lab.yaml", spec.split("datas = [")[1]
                         .split("]")[0])
        # And it must still bundle the one config it does need.
        self.assertIn("config/default.yaml", spec)

    def test_the_lab_config_still_exists_for_the_lab_package(self):
        # Excluded from the bundle, NOT deleted: the lab package puts
        # it beside the exe and main.py reads it from there.
        self.assertTrue((REPO / "config" / "eeg_lab.yaml").exists())
        self.assertIn("eeg_lab.yaml", (REPO / "main.py").read_text())


class OneAppTests(unittest.TestCase):
    """The Setup app is gone: the installer and the game's Settings
    screen do its jobs. Nothing may build, ship or mention it."""

    BUILD_FILES = ("builds/build_app.sh", "builds/build_app.bat",
                   ".github/workflows/build-apps.yml", "finger_rehab.spec",
                   ".gitignore", "README.md", "builds/README.txt",
                   "config/default.yaml", "main.py",
                   "finger_rehab/hardware/autostart.py")

    def test_the_setup_tool_is_gone(self):
        self.assertFalse((REPO / "setup_tool.py").exists())
        self.assertFalse((REPO / "setup_tool.spec").exists())
        for name in self.BUILD_FILES:
            text = (REPO / name).read_text(encoding="utf-8")
            self.assertNotIn("setup_tool", text, name)
            self.assertNotIn("Finger Rehab Setup", text, name)

    def test_ci_ships_the_three_artefacts(self):
        ci = (REPO / ".github" / "workflows" / "build-apps.yml").read_text()
        for name in ("FingerRehab-Setup-Windows.exe", "FingerRehab-macOS.dmg",
                     "FingerRehab-EEGLab.zip"):
            self.assertIn(name, ci, name)
        self.assertIn("installers\\windows.iss", ci)
        self.assertIn("hdiutil create", ci)
        self.assertIn("build_lab_package.py", ci)

    def test_the_mac_build_script_makes_the_disk_image(self):
        sh = (REPO / "builds" / "build_app.sh").read_text()
        self.assertIn("hdiutil create", sh)
        self.assertIn("FingerRehab-macOS.dmg", sh)
        self.assertIn("ln -s /Applications", sh)

    def test_the_installer_wraps_the_game_and_runs_the_flags(self):
        iss = (REPO / "installers" / "windows.iss").read_text()
        self.assertIn('Source: "..\\bin\\dist\\Finger Rehab.exe"', iss)
        self.assertIn("--register-autostart", iss)
        self.assertIn("--unregister-autostart", iss)
        self.assertIn("PrivilegesRequired=lowest", iss)
        self.assertIn("OutputBaseFilename=FingerRehab-Setup-Windows", iss)
        # A real GUID, not the spec's placeholder, so an update finds
        # the earlier install.
        self.assertRegex(iss, r"AppId=\{\{[0-9A-F]{8}-[0-9A-F]{4}-[0-9A-F]{4}"
                              r"-[0-9A-F]{4}-[0-9A-F]{12}\}")
        # Nothing wipes the folder, so sessions survive an uninstall.
        self.assertNotRegex(iss, r"(?m)^\[UninstallDelete\]")
        # The register flag runs hidden: it must never open a window.
        line = next(l for l in iss.splitlines()
                    if "--register-autostart" in l)
        self.assertIn("runhidden", line)

    def test_the_flags_exist_in_main(self):
        text = (REPO / "main.py").read_text()
        self.assertIn("--register-autostart", text)
        self.assertIn("--unregister-autostart", text)

    def test_one_version_everywhere(self):
        # The spec's literal is pinned to SOFTWARE_VERSION by
        # test_screen_layout; this pins the installer's copy of it.
        ci = (REPO / ".github" / "workflows" / "build-apps.yml").read_text()
        self.assertIn("builds/version.py", ci)
        self.assertIn("/DAppVersion=", ci)
        from finger_rehab.data.session import SOFTWARE_VERSION
        out = subprocess.run([sys.executable, str(REPO / "builds" / "version.py")],
                             capture_output=True, text=True, check=True)
        self.assertEqual(out.stdout.strip(), SOFTWARE_VERSION)

    def test_the_watcher_is_the_same_binary_as_the_game(self):
        # One binary in two modes, so there is no second executable to
        # build, sign and keep in step.
        self.assertIn("--watch", (REPO / "main.py").read_text())
