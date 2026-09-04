#!/usr/bin/env python3
"""Compile the two Arduino hexes and stage them for the app to ship.

The app never runs PlatformIO. It runs avrdude against a .hex, so the
compiling happens once here (and in CI on every push) and the products
land in assets/firmware/ where finger_rehab/hardware/flasher.py looks
for them. assets/ is already a PyInstaller data folder and is already
copied into the EEG lab package, so the hexes reach both deliverables
without any further plumbing.

manifest.json beside them carries a sha256 per file. The app refuses to
flash a hex whose sha does not match: a torn download handed to avrdude
leaves a board with no working firmware at all, which is a much worse
failure than "no firmware in this build".

Usage:
    python3 builds/build_firmware.py                  build both
    python3 builds/build_firmware.py --check-only     verify what is there
    python3 builds/build_firmware.py --out DIR        stage somewhere else

Exit codes: 0 built or already good, 1 could not produce the hexes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DEFAULT = ROOT / "assets" / "firmware"

# (project folder, PlatformIO env, output name). The env only decides
# the upload baud PlatformIO itself would use, which we never use: the
# compiled hex is the same for both Nano bootloaders.
PROJECTS = (
    ("arduino/firmware_on_device", "nanoatmega328",
     "finger_rehab_nano.hex"),
    ("arduino/singletact_address_change", "nanoatmega328new",
     "singletact_address_change.hex"),
)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def flash_bytes(path: Path) -> int:
    """Bytes of flash an Intel HEX writes: the data records only."""
    total = 0
    for raw in path.read_text(encoding="ascii", errors="replace").splitlines():
        line = raw.strip()
        if len(line) < 11 or not line.startswith(":"):
            continue
        try:
            count = int(line[1:3], 16)
            rectype = int(line[7:9], 16)
        except ValueError:
            continue
        if rectype == 0:
            total += count
    return total


def pio_command() -> list[str] | None:
    exe = shutil.which("pio") or shutil.which("platformio")
    if exe:
        return [exe]
    try:
        subprocess.run([sys.executable, "-m", "platformio", "--version"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=True)
        return [sys.executable, "-m", "platformio"]
    except (OSError, subprocess.CalledProcessError):
        return None


def git_sha() -> str:
    try:
        out = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "--short",
                              "HEAD"],
                             capture_output=True, text=True, check=True)
        return out.stdout.strip() or "unknown"
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_one(pio: list[str], folder: str, env: str) -> Path:
    project = ROOT / folder
    print(f"  pio run -d {folder} -e {env}")
    subprocess.run(pio + ["run", "-d", str(project), "-e", env], check=True)
    hex_path = project / ".pio" / "build" / env / "firmware.hex"
    if not hex_path.exists():
        raise FileNotFoundError(f"PlatformIO produced no hex at {hex_path}")
    return hex_path


def describe(path: Path, board: str) -> dict:
    return {
        "sha256": sha256_file(path),
        "bytes": path.stat().st_size,
        "flash_bytes": flash_bytes(path),
        "board": board,
    }


def check_only(out: Path) -> int:
    manifest_path = out / "manifest.json"
    if not manifest_path.exists():
        print(f"No manifest at {manifest_path}")
        return 1
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    bad = 0
    for name, entry in (manifest.get("images") or {}).items():
        path = out / name
        if not path.exists():
            print(f"  MISSING  {name}")
            bad += 1
            continue
        digest = sha256_file(path)
        if digest != entry.get("sha256"):
            print(f"  SHA MISMATCH  {name}")
            bad += 1
            continue
        print(f"  ok  {name}  {entry.get('flash_bytes')} bytes of flash")
    return 1 if bad else 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=str(OUT_DEFAULT),
                    help="where the hexes and manifest.json land")
    ap.add_argument("--check-only", action="store_true",
                    help="verify an existing folder, build nothing")
    args = ap.parse_args(argv)
    out = Path(args.out)

    if args.check_only:
        return check_only(out)

    pio = pio_command()
    if pio is None:
        # A machine without PlatformIO can still build the app, as long
        # as the hexes are already staged (CI downloads them as an
        # artefact). Only a machine with neither is a failure.
        if (out / "manifest.json").exists():
            print("PlatformIO not found; keeping the hexes already in "
                  f"{out}")
            return check_only(out)
        print("PlatformIO not found and no hexes staged. Install it with "
              "'pip install platformio', or download the firmware-hex "
              "artefact from a CI run.", file=sys.stderr)
        return 1

    out.mkdir(parents=True, exist_ok=True)
    images: dict[str, dict] = {}
    print("Building firmware:")
    for folder, env, name in PROJECTS:
        try:
            built = build_one(pio, folder, env)
        except (subprocess.CalledProcessError, FileNotFoundError) as e:
            print(f"Build failed for {folder}: {e}", file=sys.stderr)
            return 1
        dest = out / name
        shutil.copyfile(built, dest)
        images[name] = describe(dest, env)
        print(f"  -> {dest.relative_to(ROOT)}  "
              f"{images[name]['flash_bytes']} bytes of flash")

    manifest = {
        "built_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "git_sha": git_sha(),
        "images": images,
    }
    (out / "manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {(out / 'manifest.json').relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
