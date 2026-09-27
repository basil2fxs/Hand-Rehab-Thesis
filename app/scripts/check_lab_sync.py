"""Is the EEG lab folder the same game as the app?

EEG_Lab/source must be a copy of what build_lab_package.py ships
(finger_rehab, main.py, requirements.txt, config/default.yaml,
config/eeg_lab.yaml, assets) and EEG_Lab/eeg_lab.yaml a copy of
config/eeg_lab.yaml. Only the lab's own additions may differ: the
eeg_lab.yaml overlay beside the exe, run_in_psychopy.py, README.txt.

Exit 1 with the differences listed; --fix rebuilds source/ and the
yaml copy from the working tree. The exe is not touched: only a
Windows build (build_app.bat or the build-apps run on GitHub) supplies
it, and the same run supplies the installers, so the three are one
commit when they are downloaded together. The dates printed at the end
show whether that has been done.

Run from app/:  python3 scripts/check_lab_sync.py [--fix]
"""
from __future__ import annotations

import argparse
import hashlib
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_lab_package as lab  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
SKIP = {"__pycache__", ".DS_Store", ".pytest_cache"}


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def _files(root: Path) -> dict[str, Path]:
    if root.is_file():
        return {root.name: root}
    out = {}
    for p in root.rglob("*"):
        if p.is_file() and not (set(p.relative_to(root).parts) & SKIP
                                or p.suffix == ".pyc"):
            out[str(p.relative_to(root))] = p
    return out


def differences(repo: Path = REPO, pkg: Path | None = None) -> list[str]:
    """Paths under the lab folder that differ from the app, one line
    each, empty when the lab folder is the app."""
    pkg = pkg or lab.lab_folder(repo)
    out: list[str] = []
    yaml_copy = pkg / "eeg_lab.yaml"
    if not yaml_copy.exists():
        out.append("eeg_lab.yaml missing")
    elif _digest(yaml_copy) != _digest(repo / "config" / "eeg_lab.yaml"):
        out.append("eeg_lab.yaml differs from config/eeg_lab.yaml")
    source = pkg / "source"
    if not source.is_dir():
        return out + ["source/ missing"]
    for item in lab.SOURCE_ITEMS:
        want, have = _files(repo / item), _files(source / item)
        prefix = "" if (repo / item).is_file() else item + "/"
        for rel in sorted(set(want) | set(have)):
            w, h = want.get(rel), have.get(rel)
            if w is None:
                out.append(f"source/{prefix}{rel}: not in the app")
            elif h is None:
                out.append(f"source/{prefix}{rel}: missing")
            elif _digest(w) != _digest(h):
                out.append(f"source/{prefix}{rel}: differs")
    return out


def _when(path: Path) -> str:
    if not path.exists():
        return "absent"
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(path.stat().st_mtime))


def builds_report(repo: Path = REPO) -> list[str]:
    pkg = lab.lab_folder(repo)
    top = repo.parent
    try:
        head = subprocess.run(["git", "log", "-1", "--format=%h %ad",
                               "--date=short"], cwd=repo, text=True,
                              capture_output=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        head = "unknown"
    return [
        f"working tree           {head}",
        f"EEG_Lab exe            {_when(pkg / lab.EXE)}",
        f"Windows installer      {_when(top / 'Installers' / 'Windows' / 'FingerRehab-Setup-Windows.exe')}",
        f"macOS disk image       {_when(top / 'Installers' / 'macOS' / 'FingerRehab-macOS.dmg')}",
        f"Mac app (builds/Mac)   {_when(repo / 'builds' / 'Mac' / 'Finger Rehab.app')}",
    ]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--fix", action="store_true",
                    help="rebuild EEG_Lab/source and eeg_lab.yaml from the app")
    args = ap.parse_args(argv)
    pkg = lab.lab_folder(REPO)
    if args.fix:
        lab.assemble(REPO, pkg, None)
    diffs = differences(REPO, pkg)
    if diffs:
        print(f"EEG_Lab is not the app: {len(diffs)} difference(s)")
        for line in diffs[:40]:
            print("  " + line)
        if len(diffs) > 40:
            print(f"  ... {len(diffs) - 40} more")
        print("run: python3 scripts/check_lab_sync.py --fix")
    else:
        print("EEG_Lab source and eeg_lab.yaml match the app.")
    print("\nbuild dates (the exe and the two installers should come from "
          "one build-apps run):")
    for line in builds_report(REPO):
        print("  " + line)
    return 1 if diffs else 0


if __name__ == "__main__":
    sys.exit(main())
