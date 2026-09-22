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
import subprocess
import sys
from pathlib import Path

# import name -> pip name. The game imports most of these lazily:
# scipy in the block metrics and force filters, librosa and soundfile
# in rhythm's beat tracking, matplotlib in the block report. A Python
# missing one opens the game and then fails mid-session, so all eight
# are checked before anything starts.
PACKAGES = {"pygame": "pygame-ce", "serial": "pyserial", "yaml": "pyyaml",
            "numpy": "numpy", "scipy": "scipy", "librosa": "librosa",
            "soundfile": "soundfile", "matplotlib": "matplotlib"}


def _pygame_is_ce() -> bool:
    """True only for pygame-ce. PsychoPy ships classic pygame, which
    imports under the same name and then dies on a pygame-ce call, so
    an import check is not enough; only pygame-ce sets IS_CE."""
    try:
        import pygame
    except Exception:
        return False
    return bool(getattr(pygame, "IS_CE", False))


def missing_packages() -> list[str]:
    """pip names of the packages this Python lacks, pygame-ce first."""
    missing = [pip for mod, pip in PACKAGES.items()
               if mod != "pygame" and importlib.util.find_spec(mod) is None]
    if not _pygame_is_ce():
        missing.insert(0, "pygame-ce")
    return missing


def _run_exe(exe: Path, here: Path) -> int:
    # The frozen exe loads the eeg_lab.yaml beside it on its own and
    # writes sessions/ next to itself.
    print(f"Starting {exe.name}. Data lands in {here / 'sessions'}.")
    try:
        return subprocess.call([str(exe)], cwd=str(here))
    except OSError:
        print(f"{exe.name} did not start; it only runs on Windows.")
        return 1


def _run_source(source: Path, here: Path) -> int:
    missing = missing_packages()
    if missing:
        # Ready to paste. sys.executable is PsychoPy's own Python when
        # run from Coder, so the install lands where the game will
        # look; pythonw would install without showing anything, so
        # name the console build. PsychoPy's classic pygame owns the
        # same package name as pygame-ce, so it has to go first or the
        # install leaves a broken mix of the two.
        py = sys.executable.replace("pythonw", "python")
        print("Missing packages. Run:")
        if "pygame-ce" in missing:
            print(f'  "{py}" -m pip uninstall -y pygame')
        print(f'  "{py}" -m pip install ' + " ".join(missing))
        return 1
    # The lab's own copy of the config wins so an edited eeg.port is
    # honoured; the copy inside source/ is the fallback.
    cfg = here / "eeg_lab.yaml"
    if not cfg.is_file():
        cfg = source / "config" / "eeg_lab.yaml"
    print(f"Starting from source. Data lands in {source / 'sessions'}.")
    # A subprocess, not an import: the game must own its process and
    # its pygame window. cwd=source keeps its log next to its files.
    return subprocess.call([sys.executable, str(source / "main.py"),
                            "--config", str(cfg)], cwd=str(source))


def main(here: Path | None = None, platform: str = sys.platform) -> int:
    here = here or Path(__file__).resolve().parent
    source = here / "source"
    exe = here / "Finger Rehab.exe"
    has_source = (source / "main.py").is_file()

    # Windows with the exe: the route that needs nothing installed.
    if exe.is_file() and platform == "win32":
        return _run_exe(exe, here)
    if has_source:
        return _run_source(source, here)
    if exe.is_file():
        return _run_exe(exe, here)
    print("Nothing to run: no source/ folder and no Finger Rehab.exe "
          "beside this file.")
    return 1


if __name__ == "__main__":
    if importlib.util.find_spec("psychopy") is not None:
        print("PsychoPy found in this Python. That is fine: this is a "
              "plain script, not a PsychoPy experiment.")
    rc = main()
    if rc != 0:
        print(f"Exit code {rc}. A game that refused to start says why "
              "above; 'needs its trigger box' means the COM number in "
              "eeg_lab.yaml is wrong or the box is unplugged.")
    # Keep a double-clicked console open on failure. Under PsychoPy or
    # any other pipe stdin never answers, so do not wait there.
    if rc != 0 and sys.stdin is not None and sys.stdin.isatty():
        input("Press Enter to close.")
    sys.exit(rc)
