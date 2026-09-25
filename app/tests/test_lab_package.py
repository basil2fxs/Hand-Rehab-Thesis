"""Tests for the EEG lab package.

EEG_Lab is the one folder handed to the EEG lab. Its top
level holds exactly six entries: Finger Rehab.exe, eeg_lab.yaml,
run_in_psychopy.py, README.txt, a fresh source/ copy of the game and
sessions/, which ships with the eeg/ folder ActiView saves into.
Three things are pinned here. The launcher picks the right route (the
exe on Windows, source/ elsewhere, or nothing) and, from source, installs
what PsychoPy lacks beside itself before the game starts.
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
from unittest.mock import MagicMock, patch


REPO = Path(__file__).resolve().parents[1]
# The lab folder moved to the top level, beside app/.
LAB_FOLDER = REPO.parent / "EEG_Lab"


def repo_file(rel: str) -> Path:
    """Build files live under app/; .github, .gitignore and README.md
    sit at the top level beside it. Try both, the top level first for
    those three, since app/ has a short README of its own."""
    top = rel.split("/")[0] in (".github", ".gitignore", "README.md")
    for base in ((REPO.parent, REPO) if top else (REPO, REPO.parent)):
        p = base / rel
        if p.exists():
            return p
    return REPO / rel
sys.path.insert(0, str(REPO))

LAUNCHER = LAB_FOLDER / "run_in_psychopy.py"
BUILDER = REPO / "scripts" / "build_lab_package.py"
TARGET = {"Finger Rehab.exe", "eeg_lab.yaml", "run_in_psychopy.py",
          "README.txt", "source", "sessions"}
# What the game imports at run time; see PACKAGES in the launcher.
NEEDED = {"pygame-ce", "pyserial", "pyyaml", "numpy", "scipy", "librosa",
          "soundfile", "matplotlib"}
# Shipped by earlier package layouts; must never come back.
STALE = ("eeg_lab_setup.txt", "EEG Lab.bat", "run_from_source.py")


def _load(path: Path):
    """Import a script by path (neither folder is a package).

    Bytecode writing is off for the duration. Importing the launcher
    normally drops EEG_Lab/__pycache__ next to it, and that
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
        call.assert_called_once()
        self.assertEqual(
            call.call_args.args[0],
            [sys.executable, str(self.here / "source" / "main.py"),
             "--config", str(self.here / "eeg_lab.yaml")])
        self.assertEqual(call.call_args.kwargs["cwd"],
                         str(self.here / "source"))
        # Data beside this file, same as the exe route, and the lab
        # folder's own packages first on the game's path.
        env = call.call_args.kwargs["env"]
        self.assertEqual(env["FINGER_REHAB_DATA_ROOT"], str(self.here))
        self.assertEqual(env["PYTHONPATH"].split(os.pathsep)[0],
                         str(self.mod.package_dir(self.here)))

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

    def test_a_blocked_exe_falls_back_to_source(self) -> None:
        # The exe is unsigned. Smart App Control on Windows 11 refuses
        # unsigned programs outright, so the launch raises instead of
        # running; source/ under PsychoPy's own Python still works.
        self._source_layout()
        exe = self.here / "Finger Rehab.exe"
        exe.write_bytes(b"")
        calls = []

        def call(cmd, cwd=None, env=None):
            calls.append(cmd)
            if cmd == [str(exe)]:
                raise OSError("An Application Control policy has "
                              "blocked this file")
            return 0

        out = io.StringIO()
        with patch.object(self.mod.subprocess, "call", call), \
                patch.object(self.mod, "missing_packages",
                             return_value=[]), redirect_stdout(out):
            rc = self.mod.main(self.here, platform="win32")
        self.assertEqual(rc, 0)
        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[1][0], sys.executable)
        self.assertIn("Running from source instead", out.getvalue())

    def test_a_blocked_exe_with_no_source_fails_plainly(self) -> None:
        exe = self.here / "Finger Rehab.exe"
        exe.write_bytes(b"")
        out = io.StringIO()
        with patch.object(self.mod.subprocess, "call",
                          side_effect=OSError("blocked")), \
                redirect_stdout(out):
            rc = self.mod.main(self.here, platform="win32")
        self.assertEqual(rc, 1)
        self.assertIn("did not start", out.getvalue())

    def test_missing_packages_are_installed_then_the_game_runs(self) -> None:
        # PsychoPy lacks pygame-ce and librosa. The launcher installs
        # them itself, beside this file, and then starts the game:
        # nothing to paste into a terminal, no admin rights.
        self._source_layout()
        with patch.object(self.mod, "missing_packages",
                          side_effect=[["pygame-ce", "librosa"], []]), \
                patch.object(self.mod, "install_packages",
                             return_value=True) as install:
            rc, call, _ = self._run()
        self.assertEqual(rc, 0)
        install.assert_called_once()
        self.assertEqual(install.call_args.args[0], ["pygame-ce", "librosa"])
        self.assertEqual(install.call_args.args[1], self.here)
        self.assertEqual(call.call_args.args[0][1],
                         str(self.here / "source" / "main.py"))

    def test_a_failed_install_never_starts_the_game(self) -> None:
        self._source_layout()
        with patch.object(self.mod, "missing_packages",
                          return_value=["librosa"]), \
                patch.object(self.mod, "install_packages",
                             return_value=False):
            rc, call, _ = self._run()
        self.assertEqual(rc, 1)
        call.assert_not_called()

    def test_still_missing_after_the_install_says_what(self) -> None:
        self._source_layout()
        with patch.object(self.mod, "missing_packages",
                          return_value=["librosa"]), \
                patch.object(self.mod, "install_packages",
                             return_value=True):
            rc, call, out = self._run()
        self.assertEqual(rc, 1)
        call.assert_not_called()
        self.assertIn("Still missing after the install: librosa", out)

    def test_the_probe_sees_what_the_game_will_see(self) -> None:
        # The check runs in a child Python with the game's own
        # environment, so the lab folder's packages count.
        env = self.mod.game_env(self.here)
        done = MagicMock(stdout='{"missing": ["librosa"], "ce": true}\n',
                         stderr="")
        with patch.object(self.mod.subprocess, "run",
                          return_value=done) as run:
            self.assertEqual(self.mod.missing_packages(env), ["librosa"])
        child_env = run.call_args.kwargs["env"]
        self.assertEqual(child_env["PYTHONPATH"], env["PYTHONPATH"])
        self.assertIn("librosa", child_env["FR_PROBE_MODULES"])

    def test_classic_pygame_is_not_accepted(self) -> None:
        # Older PsychoPy ships classic pygame: it imports, but only
        # pygame-ce sets IS_CE.
        done = MagicMock(stdout='{"missing": [], "ce": false}', stderr="")
        with patch.object(self.mod.subprocess, "run", return_value=done):
            self.assertEqual(self.mod.missing_packages({}), ["pygame-ce"])

    def test_the_plan_skips_what_psychopy_already_has(self) -> None:
        # pip cannot see PsychoPy's zipped packages, so its own plan
        # re-downloads numpy and scipy. The launcher keeps only what
        # this Python cannot import at a fitting version.
        report = {"install": [
            {"metadata": {"name": "librosa", "version": "0.11.0",
                          "requires_dist": ["numpy>=1.22.3",
                                            "scipy>=1.6.0", "pooch>=1.1",
                                            "matplotlib>=3.5; extra == 'display'"]}},
            {"metadata": {"name": "numpy", "version": "2.2.6"}},
            {"metadata": {"name": "scipy", "version": "1.15.3"}},
            {"metadata": {"name": "pooch", "version": "1.9.0",
                          "requires_dist": ["platformdirs>=2.5.0"]}},
            {"metadata": {"name": "platformdirs", "version": "4.11.12"}},
        ]}
        have = {"numpy": "2.2.5", "scipy": "1.13.1"}
        plan = self.mod.plan_install(report, ["librosa"], have.get)
        self.assertEqual(sorted(plan), ["librosa==0.11.0", "platformdirs==4.11.12",
                                        "pooch==1.9.0"])

    def test_a_broken_dependency_under_a_working_one_is_fixed(self) -> None:
        # Found by running the lab folder in PsychoPy 2026.2.4 on a Mac:
        # the app carries platformdirs' metadata without its code, so
        # pooch imported fine but librosa failed underneath it.
        report = {"install": [
            {"metadata": {"name": "platformdirs", "version": "4.11.12"}}]}
        have = {"librosa": "0.11.0", "pooch": "1.9.0"}
        requires = {"librosa": ["pooch>=1.1"],
                    "pooch": ["platformdirs>=2.5.0"]}.get
        plan = self.mod.plan_install(report, ["librosa"], have.get,
                                     lambda n: requires(n) or [])
        self.assertIn("platformdirs==4.11.12", plan)
        self.assertNotIn("pooch", " ".join(plan))

    def test_install_is_one_plan_then_one_no_deps_target_install(self) -> None:
        env = self.mod.game_env(self.here)
        calls = []

        def call(cmd, env=None):
            calls.append(cmd)
            if "--dry-run" in cmd:
                report = cmd[cmd.index("--report") + 1]
                Path(report).write_text(
                    '{"install": [{"metadata": {"name": "pygame-ce", '
                    '"version": "2.5.8"}}]}')
            return 0

        out = io.StringIO()
        with patch.object(self.mod.subprocess, "call", call), \
                redirect_stdout(out):
            ok = self.mod.install_packages(["pygame-ce"], self.here, env)
        self.assertTrue(ok)
        self.assertEqual(len(calls), 2)
        final = calls[1]
        self.assertIn("--no-deps", final)
        self.assertEqual(final[final.index("--target") + 1],
                         str(self.mod.package_dir(self.here)))
        self.assertEqual(final[-1], "pygame-ce==2.5.8")
        self.assertIn("needs the internet", out.getvalue())

    def test_packages_are_kept_per_system_and_python(self) -> None:
        # A folder first run on the Mac carries Mac-only compiled
        # packages; the lab's Windows PC must get its own folder rather
        # than trip over them.
        mac = self.mod.package_dir(self.here)
        self.assertEqual(mac.parent, self.here / "python_packages")
        with patch.object(self.mod.sys, "platform", "win32"), \
                patch("platform.machine", return_value="AMD64"):
            win = self.mod.package_dir(self.here)
        self.assertEqual(win.parent, self.here / "python_packages")
        self.assertTrue(win.name.startswith("win32-amd64-py"))
        if sys.platform != "win32":
            self.assertNotEqual(mac, win)
        py = f"py{sys.version_info[0]}{sys.version_info[1]}"
        self.assertTrue(mac.name.endswith(py))

    def test_an_old_psychopy_python_is_refused_plainly(self) -> None:
        self._source_layout()
        with patch.object(self.mod, "OLDEST_PYTHON", (99, 0)):
            rc, call, out = self._run()
        self.assertEqual(rc, 1)
        call.assert_not_called()
        self.assertIn("needs 3.10 or newer", out)

    def test_every_run_time_package_is_checked(self) -> None:
        self.assertEqual(set(self.mod.PACKAGES.values()), NEEDED)

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
        self.pkg = self.repo.parent / "EEG_Lab"
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
            "EEG_Lab/run_in_psychopy.py": "# launcher\n",
            "EEG_Lab/README.txt": "lab readme\n",
        }
        for rel, text in files.items():
            # EEG_Lab sits BESIDE the package root in the real tree, the
            # way app/ and EEG_Lab sit side by side, so the fixture puts
            # it there too rather than inventing a layout of its own.
            base = root.parent if rel.startswith("EEG_Lab/") else root
            p = base / rel
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
        text = (LAB_FOLDER / "README.txt").read_text()
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
        # Most of these live under app/; .github and the top-level
        # launcher sit beside it. Try both rather than making every
        # caller know which.
        for base in (REPO, REPO.parent):
            p = base / rel
            if p.is_file():
                return p.read_text()
        self.skipTest(f"{rel} is not in this checkout")

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
                self.assertNotIn("EEG_Lab", line)
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
        for rule in ("EEG_Lab/*.exe", "EEG_Lab/eeg_lab.yaml",
                     "EEG_Lab/source/"):
            self.assertIn(rule, rules)
        self.assertNotIn("EEG_Lab/eeg_lab_setup.txt", rules)


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
            text = repo_file(name).read_text(encoding="utf-8")
            self.assertNotIn("setup_tool", text, name)
            self.assertNotIn("Finger Rehab Setup", text, name)

    def test_ci_ships_the_three_artefacts(self):
        ci = (REPO.parent / ".github" / "workflows" / "build-apps.yml").read_text()
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
        ci = (REPO.parent / ".github" / "workflows" / "build-apps.yml").read_text()
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
