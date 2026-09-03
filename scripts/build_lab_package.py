"""Assemble the EEG lab package, the one folder that goes to the lab.

Its top level holds exactly four entries and nothing else:
  Finger Rehab.exe     the frozen game (Windows build or CI)
  eeg_lab.yaml         copy of config/eeg_lab.yaml
  run_in_psychopy.py   committed launcher: runs source/ or the exe
  source/              fresh copy of the game for PsychoPy's own Python

builds/build_app.sh, builds/build_app.bat and the CI workflow all call
this, so the local folder and the CI zip cannot fork. source/ is
deleted and rebuilt every time so it never goes stale, and text files
from earlier package layouts are removed. Anything else found at the
top level fails the build rather than being deleted unseen.

Usage: python scripts/build_lab_package.py [--exe PATH] [--out DIR]
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "docs" / "lab_package"
EXE = "Finger Rehab.exe"
LAUNCHER = "run_in_psychopy.py"
TOP_LEVEL = {EXE, "eeg_lab.yaml", LAUNCHER, "source"}
# What main.py needs to run from source/: the package, the two configs,
# the music and icons. No tests, docs, sessions, calibration or user
# settings.
SOURCE_ITEMS = ("main.py", "requirements.txt", "finger_rehab",
                "config/default.yaml", "config/eeg_lab.yaml", "assets")
# Shipped by earlier package layouts, plus editor and OS cruft.
STALE = ("README.txt", "eeg_lab_setup.txt", "EEG Lab.bat",
         "run_from_source.py", "__pycache__", ".DS_Store")
IGNORE = shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store",
                                ".pytest_cache")


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def make_source(repo: Path, pkg: Path) -> Path:
    """Delete and rebuild pkg/source from the repo."""
    dest = pkg / "source"
    _remove(dest)
    for item in SOURCE_ITEMS:
        src, dst = repo / item, dest / item
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_dir():
            shutil.copytree(src, dst, ignore=IGNORE)
        else:
            shutil.copy2(src, dst)
    return dest


def check(pkg: Path, need_exe: bool = False) -> list[str]:
    """Return the top-level names; fail on anything outside TOP_LEVEL."""
    names = sorted(p.name for p in pkg.iterdir())
    extra = set(names) - TOP_LEVEL
    missing = TOP_LEVEL - set(names)
    if not need_exe:
        missing.discard(EXE)
    if extra or missing:
        raise SystemExit(f"lab package {pkg}: unexpected {sorted(extra)}, "
                         f"missing {sorted(missing)}")
    return names


def assemble(repo: Path = REPO, pkg: Path = PACKAGE,
             exe: Path | None = None) -> list[str]:
    """Build the package folder and return its top-level names."""
    pkg.mkdir(parents=True, exist_ok=True)
    for name in STALE:
        _remove(pkg / name)
    shutil.copy2(repo / "config" / "eeg_lab.yaml", pkg / "eeg_lab.yaml")
    # The launcher lives in docs/lab_package; it only needs copying when
    # the package is assembled somewhere else (CI's zip folder).
    launcher, target = repo / "docs" / "lab_package" / LAUNCHER, pkg / LAUNCHER
    if not (target.exists() and target.samefile(launcher)):
        shutil.copy2(launcher, target)
    make_source(repo, pkg)
    if exe is not None:
        shutil.copy2(exe, pkg / EXE)
    return check(pkg, need_exe=exe is not None)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--exe", type=Path, default=None,
                    help=f"Windows build to copy in as {EXE}")
    ap.add_argument("--out", type=Path, default=PACKAGE,
                    help="package folder (default docs/lab_package)")
    args = ap.parse_args(argv)
    names = assemble(REPO, args.out, args.exe)
    print(f"Lab package {args.out}:")
    for name in names:
        print("  " + name)
    if EXE not in names:
        print(f"  (no {EXE}: build_app.bat or the CI zip supplies it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
