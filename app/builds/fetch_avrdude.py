#!/usr/bin/env python3
"""Download the avrdude the app ships, and its licence.

avrdude is the twenty-year-old uploader every Arduino IDE runs. Bundling
it is what makes "Flash firmware" a single click on a clinic PC with no
developer tools installed. These are Arduino's own packages, the exact
binaries Arduino IDE 2 runs on the same kinds of machine, with the
checksums published in Arduino's package index.

avrdude is GPL-2.0-or-later. Redistributing the binary means shipping
the licence text with it and pointing at the corresponding source, so
this script writes both LICENSE.txt (from inside the archive) and a
SOURCE.txt naming the upstream tarball. The game links nothing from
avrdude and only spawns it as a separate process, which is the "mere
aggregation" case section 2 of the GPL describes, so the game's own
licensing is unaffected.

Usage:
    python3 builds/fetch_avrdude.py                    this OS
    python3 builds/fetch_avrdude.py --platform win32   cross fetch
    python3 builds/fetch_avrdude.py --offline          accept what is there

Exit codes: 0 the files are in place, 1 they are not.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import stat
import subprocess
import sys
import tarfile
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools" / "avrdude"
CACHE = ROOT / "bin" / "dl"

VERSION = "8.0-arduino.1"
UPSTREAM_SOURCE = (
    "https://github.com/avrdudes/avrdude/archive/refs/tags/v8.0.tar.gz")
PACKAGING_SOURCE = "https://github.com/arduino/avrdude-packing"

# One row per platform. Swapping to the avrdude project's own v8.2
# static tarballs is a row change and nothing else: their archives use
# the identical bin/ + etc/avrdude.conf + LICENSE.txt layout.
#   binary   the member to extract as the executable
#   extras   (member, name on disk) pairs for the data files
BUILDS = {
    "win32": {
        "url": ("https://downloads.arduino.cc/tools/"
                "avrdude_8.0-arduino.1_Windows_32bit.tar.gz"),
        "sha256": ("833aa1a66a8e70cd597fcfdbd7e559a9"
                   "1a00eca1d7aa3be2ce9bcadf7ccb987c"),
        "binary": ("avrdude_Windows_32bit/bin/avrdude.exe", "avrdude.exe"),
        "extras": (
            ("avrdude_Windows_32bit/etc/avrdude.conf", "avrdude.conf"),
            ("avrdude_Windows_32bit/LICENSE.txt", "LICENSE.txt"),
        ),
        "note": ("32-bit build; it runs on 64-bit Windows too, which is "
                 "what Arduino IDE ships."),
    },
    "darwin": {
        "url": ("https://downloads.arduino.cc/tools/"
                "avrdude_8.0-arduino.1_macOS_64bit.tar.gz"),
        "sha256": ("8a36cf441a3ce21622eb30b40f0b71d2"
                   "7864b30ea851cb795ae654ee10e2c132"),
        "binary": ("avrdude_macOS_64bit/bin/avrdude", "avrdude"),
        "extras": (
            ("avrdude_macOS_64bit/etc/avrdude.conf", "avrdude.conf"),
            ("avrdude_macOS_64bit/LICENSE.txt", "LICENSE.txt"),
        ),
        "note": ("x86_64 only. Nobody publishes an arm64 avrdude, so on "
                 "Apple silicon it runs under Rosetta 2. macOS offers to "
                 "install Rosetta the first time an Intel-only program "
                 "runs; softwareupdate --install-rosetta does it from a "
                 "terminal."),
    },
}


def this_platform() -> str:
    if sys.platform == "win32":
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _ssl_context():
    """Verified TLS, using certifi's bundle when the interpreter has no
    usable one of its own.

    A framework Python on macOS ships without a certificate store until
    somebody runs Install Certificates.command, and the failure looks
    like the download being blocked rather than a local setup problem.
    Verification is never turned off: the archive is executable code
    that gets pointed at a serial port.
    """
    import ssl
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:
        return ssl.create_default_context()


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  downloading {url}")
    try:
        with urllib.request.urlopen(url, timeout=120,
                                    context=_ssl_context()) as r, \
                open(dest, "wb") as f:
            shutil.copyfileobj(r, f)
        return
    except urllib.error.URLError as e:
        curl = shutil.which("curl")
        if curl is None:
            raise
        print(f"  urllib could not fetch it ({e}); trying curl")
    subprocess.run([shutil.which("curl"), "-sSL", "--fail", "-o", str(dest),
                    url], check=True)


def already_there(out: Path, spec: dict) -> bool:
    names = [spec["binary"][1]] + [n for _, n in spec["extras"]]
    return all((out / n).exists() for n in names)


def extract(archive: Path, spec: dict, out: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    wanted = {spec["binary"][0]: spec["binary"][1]}
    wanted.update({member: name for member, name in spec["extras"]})
    with tarfile.open(archive, "r:gz") as tf:
        for member, name in wanted.items():
            try:
                src = tf.extractfile(member)
            except KeyError:
                src = None
            if src is None:
                raise FileNotFoundError(
                    f"{member} is not in {archive.name}")
            with src, open(out / name, "wb") as f:
                shutil.copyfileobj(src, f)
    exe = out / spec["binary"][1]
    exe.chmod(exe.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP
              | stat.S_IXOTH)


def write_source_note(out: Path, plat: str, spec: dict) -> None:
    (out / "SOURCE.txt").write_text(
        "avrdude " + VERSION + " for " + plat + "\n"
        "\n"
        "Binary: " + spec["url"] + "\n"
        "SHA-256: " + spec["sha256"] + "\n"
        "\n"
        "Licence: GPL-2.0-or-later. The full text is in LICENSE.txt in\n"
        "this folder.\n"
        "\n"
        "Corresponding source:\n"
        "  " + UPSTREAM_SOURCE + "\n"
        "  " + PACKAGING_SOURCE + "  (Arduino's packaging of it)\n"
        "\n"
        "Finger Rehab runs avrdude as a separate program. It links no\n"
        "avrdude code and shares no address space with it.\n"
        "\n"
        "Note: " + spec["note"] + "\n",
        encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--platform", default=this_platform(),
                    choices=sorted(BUILDS) + ["linux"],
                    help="which OS to fetch for (default: this one)")
    ap.add_argument("--offline", action="store_true",
                    help="succeed if the files are already in place")
    args = ap.parse_args(argv)
    plat = args.platform

    if plat not in BUILDS:
        # Linux is out of scope: the app is built for macOS and Windows.
        # A Linux developer's own avrdude on PATH is found at run time.
        print(f"No bundled avrdude for {plat}; the app falls back to one "
              "on PATH.")
        return 0

    spec = BUILDS[plat]
    out = TOOLS / plat
    if already_there(out, spec):
        print(f"avrdude for {plat} is already in {out.relative_to(ROOT)}")
        return 0
    if args.offline:
        print(f"Offline and {out.relative_to(ROOT)} is incomplete.",
              file=sys.stderr)
        return 1

    archive = CACHE / Path(spec["url"]).name
    if not archive.exists() or sha256_file(archive) != spec["sha256"]:
        download(spec["url"], archive)
    digest = sha256_file(archive)
    if digest != spec["sha256"]:
        # Never unpack an archive that is not the one whose contents
        # were checked. A tampered or truncated avrdude would be handed
        # a serial port and a board.
        print(f"Checksum mismatch for {archive.name}:\n"
              f"  expected {spec['sha256']}\n  got      {digest}",
              file=sys.stderr)
        archive.unlink(missing_ok=True)
        return 1

    extract(archive, spec, out)
    write_source_note(out, plat, spec)
    print(f"avrdude {VERSION} for {plat} -> {out.relative_to(ROOT)}")
    for name in sorted(p.name for p in out.iterdir()):
        print(f"  {name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
