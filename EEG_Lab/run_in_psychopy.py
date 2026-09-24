"""Run the lab task from PsychoPy: open this file in Coder, press Run.

The game is pygame, not PsychoPy, so there is no .psyexp to open.
Coder runs any Python script under PsychoPy's own interpreter, in this
file's folder, with its output in the Runner pane. On the lab's
Windows desktop this starts the Finger Rehab.exe beside this file,
which carries its own Python and needs nothing installed. Anywhere
else it starts the game from the source/ folder beside this file under
PsychoPy's Python with eeg_lab.yaml applied, once that Python has the
packages the game needs.
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

# import name -> pip name. The game imports most of these lazily:
# scipy in the block metrics and force filters, librosa and soundfile
# in rhythm's beat tracking, matplotlib in the block report. A Python
# missing one opens the game and then fails mid-session, so all eight
# are checked before anything starts.
PACKAGES = {"pygame": "pygame-ce", "serial": "pyserial", "yaml": "pyyaml",
            "numpy": "numpy", "scipy": "scipy", "librosa": "librosa",
            "soundfile": "soundfile", "matplotlib": "matplotlib"}

# Where a run from source keeps the packages PsychoPy lacks: beside
# this file, so no admin rights are needed, nothing outside the lab
# folder changes, and deleting the folder undoes it. PsychoPy's own
# site-packages sits in Program Files on Windows and inside the app on
# a Mac, and a pip line pasted into a terminal cannot even start the
# Mac app's Python. One subfolder per system, chip and Python version
# (darwin-arm64-py310, win32-amd64-py310): the compiled parts only load
# where they were built, so a folder tried on a Mac first still starts
# clean on the lab's Windows PC.
PACKAGE_DIR = "python_packages"


def package_dir(here: Path) -> Path:
    """This Python's own package folder inside PACKAGE_DIR."""
    import platform
    tag = (f"{sys.platform}-{platform.machine().lower()}-"
           f"py{sys.version_info[0]}{sys.version_info[1]}")
    return here / PACKAGE_DIR / tag

# Run by the same Python, with the same environment, the game will get,
# so what it reports is exactly what the game will find. Classic
# pygame (older PsychoPy ships it) imports under the same name and then
# dies on a pygame-ce call, so only IS_CE counts.
_PROBE = """
import importlib.util, json, os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
mods = json.loads(os.environ["FR_PROBE_MODULES"])
out = [m for m in mods if m != "pygame" and importlib.util.find_spec(m) is None]
if "librosa" not in out:
    try:
        import librosa.core.audio
    except Exception:
        out.append("librosa")
try:
    import pygame
    ce = bool(getattr(pygame, "IS_CE", False))
except Exception:
    ce = False
print(json.dumps({"missing": out, "ce": ce}))
"""


def game_env(here: Path) -> dict:
    """The environment the game runs in: the lab folder's packages
    first on the path, and its data beside this file."""
    env = dict(os.environ)
    parts = [str(package_dir(here))]
    if env.get("PYTHONPATH"):
        parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(parts)
    # Same data folder as the exe route: sessions/, the log and any
    # calibration land beside this file, never inside source/.
    env["FINGER_REHAB_DATA_ROOT"] = str(here)
    return env


def missing_packages(env: dict | None = None) -> list[str]:
    """pip names of the packages the game would not find, pygame-ce
    first."""
    probe_env = dict(env if env is not None else os.environ)
    probe_env["FR_PROBE_MODULES"] = json.dumps(list(PACKAGES))
    out = subprocess.run([sys.executable, "-c", _PROBE], env=probe_env,
                         capture_output=True, text=True)
    try:
        found = json.loads(out.stdout.strip().splitlines()[-1])
    except (IndexError, ValueError):
        print(out.stderr.strip())
        return list(PACKAGES.values())
    missing = [PACKAGES[m] for m in found["missing"]]
    if not found["ce"]:
        missing.insert(0, "pygame-ce")
    return missing


def _canon(name: str) -> str:
    return name.lower().replace("_", "-").replace(".", "-")


def _requirement_class():
    try:
        from packaging.requirements import Requirement
    except ImportError:
        try:
            from pip._vendor.packaging.requirements import Requirement
        except ImportError:
            return None
    return Requirement


def plan_install(report: dict, wanted: list[str], installed,
                 requires=lambda name: []) -> list[str]:
    """What to install: the wanted packages plus every dependency, at
    any depth, that this Python cannot already import at a version
    that fits.

    pip's own plan cannot see the packages PsychoPy keeps zipped inside
    its app, so it re-downloads numpy, scipy and friends (376 MB for
    two packages); following it blindly is wasteful, and trusting
    metadata alone is wrong (see _installed_version). `installed(name)`
    returns an importable version or None; `requires(name)` lists an
    installed package's own requirements, so a working package with a
    broken dependency underneath still gets that dependency fixed.
    Pins come from pip's plan where it has one.
    """
    items = {_canon(i["metadata"]["name"]): i["metadata"]
             for i in report.get("install", [])}
    Requirement = _requirement_class()
    if Requirement is None:
        return [f"{m['name']}=={m['version']}" for m in items.values()]
    wanted_set = {_canon(w) for w in wanted}
    keep: dict[str, str] = {}
    seen: set[str] = set()
    queue = [(name, None) for name in wanted_set]
    while queue:
        name, req = queue.pop()
        have = installed(name)
        fits = (name not in wanted_set and have is not None
                and (req is None
                     or req.specifier.contains(have, prereleases=True)))
        if not fits:
            meta = items.get(name)
            keep[name] = (f"{meta['name']}=={meta['version']}" if meta
                          else name)
        if name in seen:
            continue
        seen.add(name)
        if not fits and name in items:
            texts = items[name].get("requires_dist") or []
        else:
            texts = requires(name) or []
        for text in texts:
            dep = Requirement(text)
            if dep.marker is not None and not dep.marker.evaluate(
                    {"extra": ""}):
                continue
            queue.append((_canon(dep.name), dep))
    return list(keep.values())


def _requires(name: str) -> list[str]:
    import importlib.metadata as md
    try:
        return list(md.distribution(name).requires or [])
    except md.PackageNotFoundError:
        return []


def _installed_version(env: dict):
    """installed(name) as this Python plus the lab packages sees it.

    A version counts only when the package also imports: PsychoPy's
    Mac app carries platformdirs' metadata without its code, and
    trusting the metadata left librosa unable to load.
    """
    folder = env["PYTHONPATH"].split(os.pathsep)[0]
    if folder not in sys.path:
        sys.path.insert(0, folder)
    importlib.invalidate_caches()
    import importlib.metadata as md

    def installed(name):
        try:
            dist = md.distribution(name)
        except md.PackageNotFoundError:
            return None
        tops = (dist.read_text("top_level.txt") or "").split()
        if not tops:
            tops = [name.replace("-", "_")]
        for top in tops:
            try:
                if importlib.util.find_spec(top) is None:
                    return None
            except (ImportError, ValueError):
                return None
        return dist.version
    return installed


def install_packages(missing: list[str], here: Path, env: dict) -> bool:
    """One-time install of what is missing into this Python's folder
    inside PACKAGE_DIR."""
    folder = package_dir(here)
    shown = f"{PACKAGE_DIR}/{folder.name}"
    print(f"One-time set-up: installing {', '.join(missing)} into "
          f"{shown} beside this file. This needs the internet and "
          "takes a few minutes.")
    pip = [sys.executable, "-m", "pip", "install",
           "--disable-pip-version-check", "--no-input"]
    with tempfile.TemporaryDirectory() as td:
        report_path = Path(td) / "report.json"
        rc = subprocess.call(pip + ["--dry-run", "--quiet", "--report",
                                    str(report_path)] + missing, env=env)
        if rc != 0 or not report_path.is_file():
            print("pip could not work out the packages. Check the "
                  "internet connection and press Run again.")
            return False
        report = json.loads(report_path.read_text(encoding="utf-8"))
    wanted = plan_install(report, missing, _installed_version(env),
                          _requires)
    folder.mkdir(parents=True, exist_ok=True)
    rc = subprocess.call(pip + ["--no-deps", "--upgrade", "--target",
                                str(folder)] + wanted, env=env)
    if rc != 0:
        print(f"The install stopped (pip exit code {rc}). Press Run again; "
              f"if it keeps failing, delete {shown} and retry.")
        return False
    return True


def _run_exe(exe: Path, here: Path) -> int | None:
    """Run the exe; None when Windows would not start it at all."""
    # The frozen exe loads the eeg_lab.yaml beside it on its own and
    # writes sessions/ next to itself.
    print(f"Starting {exe.name}. Data lands in {here / 'sessions'}.")
    try:
        return subprocess.call([str(exe)], cwd=str(here))
    except OSError as e:
        # Not on Windows, or Windows refused it. The exe is unsigned,
        # and Smart App Control on Windows 11 blocks unsigned programs
        # outright, wherever they were copied from.
        print(f"{exe.name} did not start ({e}).")
        return None


def _run_source(source: Path, here: Path) -> int:
    if sys.version_info < OLDEST_PYTHON:
        # The exe carries its own Python; source/ needs 3.10, which
        # PsychoPy ships from 2023.2 on.
        print(f"This PsychoPy runs Python {sys.version.split()[0]}; the "
              "game needs 3.10 or newer. Install a current PsychoPy, or "
              "run Finger Rehab.exe on Windows.")
        return 1
    env = game_env(here)
    missing = missing_packages(env)
    if missing:
        if not install_packages(missing, here, env):
            return 1
        missing = missing_packages(env)
        if missing:
            print("Still missing after the install: " + ", ".join(missing))
            return 1
    # The lab's own copy of the config wins so an edited eeg.port is
    # honoured; the copy inside source/ is the fallback.
    cfg = here / "eeg_lab.yaml"
    if not cfg.is_file():
        cfg = source / "config" / "eeg_lab.yaml"
    print(f"Starting from source. Data lands in {here / 'sessions'}.")
    # A subprocess, not an import: the game must own its process and
    # its pygame window.
    return subprocess.call([sys.executable, str(source / "main.py"),
                            "--config", str(cfg)], cwd=str(source), env=env)


OLDEST_PYTHON = (3, 10)


def main(here: Path | None = None, platform: str = sys.platform) -> int:
    here = here or Path(__file__).resolve().parent
    source = here / "source"
    exe = here / "Finger Rehab.exe"
    has_source = (source / "main.py").is_file()

    # Windows with the exe: the route that needs nothing installed.
    if exe.is_file() and platform == "win32":
        rc = _run_exe(exe, here)
        if rc is not None:
            return rc
        if not has_source:
            return 1
        # Blocked: the same game from source/ under PsychoPy's own
        # Python, which Windows already trusts.
        print("Running from source instead.")
    if has_source:
        return _run_source(source, here)
    if exe.is_file():
        rc = _run_exe(exe, here)
        return 1 if rc is None else rc
    print("Nothing to run: no source/ folder and no Finger Rehab.exe "
          "beside this file.")
    return 1


if __name__ == "__main__":
    if importlib.util.find_spec("psychopy") is not None:
        print("PsychoPy found in this Python. That is fine: this is a "
              "plain script, not a PsychoPy experiment.")
    rc = main()
    if rc != 0:
        # The exe has no console, so its reason is in its log file;
        # a source run prints it into this pane.
        print(f"Exit code {rc}. A game that refused to start says why "
              "in sessions/rehab.log beside this file, and a source run "
              "also prints it above.")
    # Keep a double-clicked console open on failure. Under PsychoPy or
    # any other pipe stdin never answers, so do not wait there.
    if rc != 0 and sys.stdin is not None and sys.stdin.isatty():
        input("Press Enter to close.")
    sys.exit(rc)
