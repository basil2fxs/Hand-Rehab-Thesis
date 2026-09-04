"""One-click Arduino flashing, and the SingleTact address change.

Why avrdude and not PlatformIO
------------------------------
PlatformIO is a build tool. Nothing on a clinic PC needs to compile the
firmware. What actually writes flash on an ATmega328P Nano is the
bootloader already sitting on the chip plus one small uploader, avrdude,
and a .hex file. So CI compiles the hexes with PlatformIO once, the app
ships the hexes and an avrdude binary, and a flash is a single
subprocess. The command line this module builds is byte for byte the one
PlatformIO would have run:

    avrdude -C avrdude.conf -p atmega328p -c arduino -P <port> \
            -b <baud> -D -U flash:w:<hex>:i

Why the baud is guessed
-----------------------
A Nano carries one of two bootloaders. Boards from 2018 on run Optiboot
at 115200; older boards and most clones run ATmegaBOOT at 57600. The hex
is identical either way and there is no way to ask a board which it has,
so we try one, and on a sync failure try the other, and remember the
winner in user_settings.yaml as firmware.preferred_baud.

Why the app's own serial reader has to stop first
-------------------------------------------------
While the game holds the port open avrdude cannot use it. On Windows a
COM port is exclusive and the second open fails outright. On macOS both
processes can open /dev/cu.* and then split the incoming bytes between
them, which breaks the bootloader handshake in confusing ways. Either
way the engine stops its source (and the port watcher, so autoconnect
cannot grab the port back mid flash) before a job starts and rebuilds it
afterwards.

Threads in here never touch the engine, pygame or the config file. They
publish their state through their own attributes behind a lock and the
screen reads it on the main thread.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path


log = logging.getLogger(__name__)

# The banner the game firmware prints once its self test is done, and
# the one the address tool prints at boot. Both are configurable; these
# are the fallbacks when the config has no firmware section at all.
DEFAULT_GAME_BANNER = "### Setup Complete ###"
DEFAULT_TOOL_BANNER = "### ADDR TOOL"
DEFAULT_BAUD_ORDER = (115200, 57600)

# An ATmega328P Nano has 30720 bytes of usable flash under the
# bootloader. A hex claiming more than that could never be uploaded.
MAX_FLASH_BYTES = 30720


def _platform_dir() -> str:
    """Folder name for this OS inside tools/avrdude/."""
    if sys.platform == "win32":
        return "win32"
    if sys.platform == "darwin":
        return "darwin"
    return "linux"


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------
# Value types
# ---------------------------------------------------------------------

@dataclass
class FirmwareImage:
    """One .hex the app can flash, plus what the manifest says about it."""

    kind: str                       # "game" or "addr_tool"
    path: Path
    sha256: str
    size: int                       # bytes of the hex FILE
    built_utc: str | None = None
    git_sha: str | None = None
    dev_build: bool = False         # built locally, not by CI

    def short_label(self) -> str:
        """For the Settings caption, where the panel is 178 px wide.

        The commit is what identifies a build; the date only says when
        CI ran. Dropping the date is what keeps the line from being
        truncated mid-word, which looks like a bug rather than a
        deliberate trim.
        """
        if self.dev_build:
            return "dev build, not the CI hex"
        if self.git_sha:
            return "hex " + str(self.git_sha)
        return self.path.name

    def label(self) -> str:
        """The longer form, for the dialog card."""
        bits = []
        if self.git_sha:
            bits.append("hex " + str(self.git_sha))
        if self.built_utc:
            bits.append(str(self.built_utc)[:10])
        if not bits:
            bits.append(self.path.name)
        if self.dev_build:
            bits.append("dev build, not the CI hex")
        return ", ".join(bits)


@dataclass
class AvrdudeTool:
    """How to invoke avrdude. `argv` is a list so a test can stand a
    Python script in for the real binary without any other seam."""

    argv: list[str]
    conf: Path | None = None
    origin: str = "bundled"   # bundled / env / config / path / platformio / arduino15


@dataclass
class AvrdudeResult:
    returncode: int | None            # None when it was killed on timeout
    kind: str                         # see classify()
    output: str
    seconds: float


@dataclass
class FlashResult:
    ok: bool
    baud: int | None
    banner_seen: bool
    message: str            # one plain sentence for the status line
    detail: str             # the avrdude output, for the log
    seconds: float
    kind: str = "ok"


# ---------------------------------------------------------------------
# Finding the pieces
# ---------------------------------------------------------------------

def _project_root() -> Path:
    from ..config import PROJECT_ROOT
    return Path(PROJECT_ROOT)


def _user_root() -> Path:
    from ..config import USER_ROOT
    return Path(USER_ROOT)


def _dev_hex_path(kind: str) -> Path:
    """Where PlatformIO leaves the hex in a source checkout."""
    root = _project_root()
    if kind == "game":
        return (root / "arduino" / "firmware_on_device" / ".pio" / "build"
                / "nanoatmega328" / "firmware.hex")
    return (root / "arduino" / "singletact_address_change" / ".pio"
            / "build" / "nanoatmega328new" / "firmware.hex")


def flash_bytes(hex_path: Path) -> int:
    """How many bytes of flash an Intel HEX file writes.

    Only the data records (type 00) count. Used to refuse a hex too big
    for the part before avrdude gets a chance to half write it.
    """
    total = 0
    with open(hex_path, "r", encoding="ascii", errors="replace") as f:
        for raw in f:
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


def find_hex(kind: str, cfg) -> FirmwareImage | None:
    """The .hex for `kind` ("game" or "addr_tool"), or None.

    The bundled copy comes first, and its sha256 must match the
    manifest CI wrote beside it: a torn download must never be handed
    to avrdude, because a half written flash leaves the board with no
    usable firmware at all. A source checkout falls back to whatever
    PlatformIO last built, flagged as a dev build so the caption says
    so.
    """
    key = "firmware.game_hex" if kind == "game" else "firmware.addr_tool_hex"
    default = ("assets/firmware/finger_rehab_nano.hex" if kind == "game"
               else "assets/firmware/singletact_address_change.hex")
    rel = str(cfg.get(key, default) or default)
    path = Path(rel)
    if not path.is_absolute():
        path = _project_root() / path
    manifest = _read_manifest(path.parent)
    if path.exists():
        digest = _sha256_file(path)
        entry = (manifest.get("images") or {}).get(path.name) or {}
        want = entry.get("sha256")
        if want and want != digest:
            log.warning("Bundled %s does not match the manifest sha256; "
                        "refusing to flash it", path.name)
            return None
        return FirmwareImage(
            kind=kind, path=path, sha256=digest, size=path.stat().st_size,
            built_utc=manifest.get("built_utc"),
            git_sha=manifest.get("git_sha"),
        )
    dev = _dev_hex_path(kind)
    if dev.exists() and not getattr(sys, "frozen", False):
        return FirmwareImage(
            kind=kind, path=dev, sha256=_sha256_file(dev),
            size=dev.stat().st_size, dev_build=True,
        )
    return None


def _read_manifest(folder: Path) -> dict:
    p = folder / "manifest.json"
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError) as e:
        log.warning("Could not read %s: %s", p, e)
        return {}


def _conf_beside(binary: Path) -> Path | None:
    """avrdude.conf next to the binary or in the sibling etc/ folder.

    None means do not pass -C at all, which lets avrdude fall back to
    its own compiled-in search. A wrong -C is worse than no -C.
    """
    for cand in (binary.parent / "avrdude.conf",
                 binary.parent.parent / "etc" / "avrdude.conf"):
        if cand.exists():
            return cand
    return None


def _prepare_macos_copy(binary: Path, conf: Path | None) -> tuple[Path, Path | None]:
    """Copy a bundled avrdude out of the .app and clear its quarantine.

    Files that arrive by browser and Archive Utility carry
    com.apple.quarantine, and a helper binary nested in a bundle the
    user approved is not documented as inheriting that approval. The
    copy costs about a megabyte once and takes the guesswork out. Any
    failure here is not fatal: the caller falls back to the original
    path and avrdude either runs or reports its own error.
    """
    try:
        dest_dir = _user_root() / "tools" / ("avrdude-" + _sha256_file(binary)[:8])
        dest = dest_dir / binary.name
        dest_conf = (dest_dir / conf.name) if conf is not None else None
        if not dest.exists() or _sha256_file(dest) != _sha256_file(binary):
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(binary, dest)
            if conf is not None and dest_conf is not None:
                shutil.copyfile(conf, dest_conf)
            os.chmod(dest, os.stat(dest).st_mode | stat.S_IXUSR
                     | stat.S_IXGRP | stat.S_IXOTH)
            # shutil.copyfile gives the copy its own quarantine
            # attribute on current macOS, so copying alone cleans
            # nothing. Removing it needs no privileges on a file the
            # user owns.
            subprocess.run(["/usr/bin/xattr", "-d", "com.apple.quarantine",
                            str(dest)],
                           stdin=subprocess.DEVNULL,
                           stdout=subprocess.DEVNULL,
                           stderr=subprocess.DEVNULL, check=False)
        if dest_conf is not None and not dest_conf.exists() and conf is not None:
            shutil.copyfile(conf, dest_conf)
        return dest, (dest_conf if dest_conf and dest_conf.exists() else conf)
    except OSError as e:
        log.warning("Could not stage avrdude outside the bundle: %s", e)
        return binary, conf


def find_avrdude(cfg) -> AvrdudeTool | None:
    """Locate an avrdude binary, bundled copy first.

    Always an absolute path. A .app launched from Finder gets
    PATH=/usr/bin:/bin:/usr/sbin:/sbin and nothing else, so relying on
    the shell to find avrdude would work on the developer's machine and
    fail on every clinic PC.
    """
    exe = "avrdude.exe" if sys.platform == "win32" else "avrdude"
    candidates: list[tuple[Path, str]] = []

    setting = cfg.get("firmware.avrdude", "auto")
    if setting and str(setting) != "auto":
        candidates.append((Path(str(setting)).expanduser(), "config"))
    env = os.environ.get("FINGER_REHAB_AVRDUDE")
    if env:
        candidates.append((Path(env).expanduser(), "env"))
    bundled = _project_root() / "tools" / "avrdude" / _platform_dir() / exe
    candidates.append((bundled, "bundled"))
    which = shutil.which("avrdude")
    if which:
        candidates.append((Path(which), "path"))
    home = Path.home()
    candidates.append((home / ".platformio" / "packages" / "tool-avrdude"
                       / "bin" / exe, "platformio"))
    candidates.append((home / ".platformio" / "packages" / "tool-avrdude"
                       / exe, "platformio"))
    a15 = [home / "Library" / "Arduino15"]
    local = os.environ.get("LOCALAPPDATA")
    if local:
        a15.append(Path(local) / "Arduino15")
    for base in a15:
        pkg = base / "packages" / "arduino" / "tools" / "avrdude"
        if pkg.is_dir():
            try:
                versions = sorted((d for d in pkg.iterdir() if d.is_dir()),
                                  key=lambda d: d.name, reverse=True)
            except OSError:
                versions = []
            for v in versions:
                candidates.append((v / "bin" / exe, "arduino15"))

    for path, origin in candidates:
        try:
            if not path.is_file():
                continue
        except OSError:
            continue
        path = path.resolve()
        conf = _conf_beside(path)
        # Only worth doing inside a real bundle. In a source checkout
        # USER_ROOT is the repo itself, so staging would drop a copy of
        # avrdude into the working tree to solve a quarantine problem
        # that does not exist there.
        if (origin == "bundled" and sys.platform == "darwin"
                and getattr(sys, "frozen", False)):
            path, conf = _prepare_macos_copy(path, conf)
        return AvrdudeTool(argv=[str(path)], conf=conf, origin=origin)
    return None


def candidate_ports(cfg, source=None) -> list[tuple[str, str]]:
    """(port, label) for every board worth offering, best first.

    Labels carry the hand when the running source has one for that
    port, so a two-board rig can tell them apart. Only VID-matched,
    junk-filtered ports appear: offering the Mac's Bluetooth serial
    port as a flash target would be a trap.
    """
    try:
        from .serial_source import discover_ports
        from .discovery import short_port
    except ImportError:
        return []
    try:
        ports = discover_ports(cfg.get("serial.vendor_ids"), max_ports=8)
    except Exception as e:
        log.warning("Port scan for the flasher failed: %s", e)
        return []
    hands: dict[str, str] = {}
    for h in (getattr(source, "hands", None) or []):
        try:
            hands[h.port] = str(h.hand).upper()
        except AttributeError:
            continue
    out: list[tuple[str, str]] = []
    for p in ports:
        hand = hands.get(p)
        out.append((p, f"{hand} hand, {short_port(p)}" if hand
                    else short_port(p)))
    # The right hand is the one board a single-board rig always has, so
    # it makes the better default pick.
    out.sort(key=lambda item: (0 if item[1].startswith("RIGHT") else
                               1 if item[1].startswith("LEFT") else 2))
    return out


# ---------------------------------------------------------------------
# Running avrdude
# ---------------------------------------------------------------------

def avrdude_argv(tool: AvrdudeTool, port: str, hex_path: Path,
                 baud: int) -> list[str]:
    """PlatformIO's own upload line, rebuilt.

    -D disables the auto erase. A bootloader cannot erase the chip
    anyway, so it changes nothing on this part; it is here so the line
    stays identical to the one the Arduino IDE and PlatformIO run,
    which is the line that is known to work on these boards.
    """
    argv = list(tool.argv)
    if tool.conf is not None:
        argv += ["-C", str(tool.conf)]
    argv += ["-p", "atmega328p", "-c", "arduino", "-P", str(port),
             "-b", str(int(baud)), "-D",
             "-U", f"flash:w:{hex_path}:i"]
    return argv


# Substring tables, checked against the lowercased output. Order
# matters only in that the first table to match wins.
_CLASSIFY_TABLE: tuple[tuple[str, tuple[str, ...]], ...] = (
    # "gone" and "busy" get separate messages. Telling a therapist to
    # close the Arduino IDE when the board is simply unplugged sends
    # them hunting for a program that was never running.
    ("port_missing", (
        "no such file", "no such device",
    )),
    ("port_busy", (
        "access is denied", "permission denied", "resource busy",
        "cannot open port", "can't open device", "unable to open port",
    )),
    ("wrong_chip", (
        "expected signature", "invalid device signature",
        "device signature =",
    )),
    ("verify_failed", (
        "verification mismatch", "verification error", "first mismatch",
    )),
    ("sync_failed", (
        "not responding", "not in sync", "getsync",
        "unable to open programmer",
    )),
)


def classify(output: str, returncode: int | None) -> str:
    """Turn avrdude's chatter into one of a handful of outcomes.

    avrdude prints "avrdude done.  Thank you." even when it failed (the
    line comes after its exit label), so the exit code is what decides
    success, and the strings only say WHY a failure happened.
    """
    if returncode is None:
        return "timeout"
    low = (output or "").lower()
    if returncode == 0:
        # update.c prints "N bytes of flash verified" on a good write.
        # A zero exit with no verify line means something else ran.
        return "ok" if "verified" in low else "unknown"
    for kind, needles in _CLASSIFY_TABLE:
        for n in needles:
            if n in low:
                return kind
    return "unknown"


def run_avrdude(tool: AvrdudeTool, port: str, hex_path: Path, baud: int,
                *, on_line=None, timeout_s: float = 90.0,
                popen=subprocess.Popen) -> AvrdudeResult:
    """One avrdude run, output captured line by line.

    The pipes are passed explicitly because a windowed PyInstaller build
    has sys.stdin / stdout / stderr set to None, and a child inheriting
    those raises rather than running. CREATE_NO_WINDOW keeps a black
    console box from flashing up on Windows.
    """
    argv = avrdude_argv(tool, port, hex_path, baud)
    kwargs: dict = dict(stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT)
    if sys.platform == "win32":
        kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        kwargs["cwd"] = str(Path(hex_path).parent)
    except (TypeError, ValueError):
        pass
    log.info("avrdude: %s", " ".join(argv))
    started = time.perf_counter()
    try:
        proc = popen(argv, **kwargs)
    except OSError as e:
        # errno 86 on macOS is "Bad CPU type in executable": an
        # x86_64 avrdude on an Apple silicon Mac with no Rosetta.
        text = f"{e}"
        kind = "no_rosetta" if getattr(e, "errno", None) == 86 else "tool_missing"
        return AvrdudeResult(returncode=None if kind == "timeout" else 1,
                             kind=kind, output=text,
                             seconds=time.perf_counter() - started)

    chunks: list[str] = []
    pending = ""
    killed = False

    def pump() -> None:
        nonlocal pending
        stream = proc.stdout
        if stream is None:
            return
        while True:
            data = stream.read(1)
            if not data:
                break
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            chunks.append(data)
            # avrdude redraws its progress bar with carriage returns,
            # so a reader that only splits on \n sees one enormous line
            # and the dialog shows nothing until the flash is over.
            if data in ("\r", "\n"):
                if pending.strip() and on_line is not None:
                    try:
                        on_line(pending.strip())
                    except Exception:
                        pass
                pending = ""
            else:
                pending += data

    reader = threading.Thread(target=pump, name="avrdude-out", daemon=True)
    reader.start()
    try:
        proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        killed = True
        try:
            proc.kill()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except Exception:
            pass
    reader.join(timeout=2.0)
    if pending.strip() and on_line is not None:
        try:
            on_line(pending.strip())
        except Exception:
            pass
    output = "".join(chunks)
    rc = None if killed else proc.returncode
    return AvrdudeResult(returncode=rc, kind=classify(output, rc),
                         output=output,
                         seconds=time.perf_counter() - started)


def wait_for_banner(port: str, banner: str, timeout_s: float = 6.0,
                    *, open_port=None):
    """Open the port and wait for the board's start-up line.

    Opening the port drops DTR and resets the board, exactly as the
    game's own SerialSource does, so the banner we are waiting for is
    the one printed by the reset this call causes. Returns
    (seen, port_object); the caller closes the object or keeps it to
    talk to the address tool.
    """
    if open_port is None:
        try:
            import serial as _serial
        except ImportError:
            return False, None
        open_port = _serial.Serial
    try:
        ser = open_port(port, 115200, timeout=0.2)
    except Exception as e:
        log.warning("Could not reopen %s after the flash: %s", port, e)
        return False, None
    deadline = time.perf_counter() + float(timeout_s)
    buf = ""
    while time.perf_counter() < deadline:
        try:
            data = ser.read(256)
        except Exception:
            break
        if data:
            if isinstance(data, bytes):
                data = data.decode("utf-8", errors="replace")
            buf += data
            if banner in buf:
                return True, ser
        else:
            time.sleep(0.02)
    return False, ser


# ---------------------------------------------------------------------
# Messages
# ---------------------------------------------------------------------

_MESSAGES = {
    "ok": "Flashed and verified at {baud} baud.",
    "sync_failed": ("The board did not answer at 115200 or 57600. Check "
                    "the USB cable, unplug and replug, then try again."),
    "port_busy": ("Could not open {short}: another program has it. Close "
                  "the Arduino IDE or serial monitor and try again."),
    "port_missing": ("{short} is not there any more. Plug the board back "
                     "in and try again."),
    "wrong_chip": ("That board is not an ATmega328P Nano. Nothing was "
                   "written."),
    "verify_failed": ("Written but read-back differs. Flash again; if it "
                      "repeats the board may be faulty."),
    "timeout": ("Timed out after {timeout:.0f} s. Unplug and replug the "
                "board and try again."),
    "no_rosetta": ("This Mac needs Rosetta for the flashing tool: run "
                   "softwareupdate --install-rosetta in Terminal, then "
                   "try again."),
    "tool_missing": ("avrdude would not start on this machine. Reinstall "
                     "the app."),
    "unknown": "The flash failed. See the log for what avrdude said.",
}

NO_PORT_MESSAGE = ("No Arduino found. Plug it in. If Windows never shows "
                   "a port, the CH340 driver is missing: install CH341SER "
                   "from wch-ic.com.")
NO_HEX_MESSAGE = ("No firmware in this build. Run builds/build_firmware.py "
                  "(needs PlatformIO) or use a CI build.")
NO_AVRDUDE_MESSAGE = ("avrdude is not in this build. Run "
                      "builds/fetch_avrdude.py or install avrdude.")
BANNER_MISSING_MESSAGE = ("Flashed and verified, but the board did not "
                          "print its start-up banner. Unplug and replug it.")


# ---------------------------------------------------------------------
# One whole flash
# ---------------------------------------------------------------------

def baud_order_for(cfg) -> list[int]:
    """Try the baud that worked last time first, then the others."""
    order: list[int] = []
    raw = cfg.get("firmware.baud_order", list(DEFAULT_BAUD_ORDER))
    try:
        order = [int(b) for b in (raw or DEFAULT_BAUD_ORDER)]
    except (TypeError, ValueError):
        order = list(DEFAULT_BAUD_ORDER)
    if not order:
        order = list(DEFAULT_BAUD_ORDER)
    pref = cfg.get("firmware.preferred_baud")
    try:
        pref = int(pref) if pref is not None else None
    except (TypeError, ValueError):
        pref = None
    if pref is not None:
        order = [pref] + [b for b in order if b != pref]
    return order


def flash_image(tool: AvrdudeTool, port: str, image: FirmwareImage, cfg,
                *, on_status=None, baud_order=None, banner: str | None = None,
                popen=subprocess.Popen, open_port=None) -> FlashResult:
    """Write one hex to one board and confirm it came back up."""
    def say(text: str) -> None:
        if on_status is not None:
            try:
                on_status(text)
            except Exception:
                pass

    try:
        from .discovery import short_port
    except ImportError:
        def short_port(p):    # noqa: E306 - trivial fallback
            return p

    timeout_s = float(cfg.get("firmware.flash_timeout_s", 90) or 90)
    order = list(baud_order) if baud_order else baud_order_for(cfg)
    started = time.perf_counter()
    last: AvrdudeResult | None = None
    for i, baud in enumerate(order):
        which = ("the new bootloader" if int(baud) == 115200
                 else "the old bootloader")
        say(f"Trying {which} ({baud})")
        res = run_avrdude(tool, port, image.path, baud,
                          on_line=lambda ln: say(_progress_line(ln)),
                          timeout_s=timeout_s, popen=popen)
        last = res
        if res.kind == "ok":
            log.info("avrdude output:\n%s", res.output)
            say("Waiting for the board to restart")
            want = banner if banner is not None else str(
                cfg.get("firmware.game_banner", DEFAULT_GAME_BANNER))
            seen, ser = wait_for_banner(
                port, want,
                timeout_s=float(cfg.get("firmware.banner_timeout_s", 6.0)),
                open_port=open_port)
            msg = (_MESSAGES["ok"].format(baud=baud) if seen
                   else BANNER_MISSING_MESSAGE)
            out = FlashResult(
                ok=True, baud=int(baud), banner_seen=bool(seen),
                message=msg, detail=res.output,
                seconds=time.perf_counter() - started, kind="ok")
            if _keep_open(want):
                # The address tool's port stays open so the caller can
                # talk to it. The game firmware's does not: the engine
                # reopens that one itself when it rebuilds the source.
                out.port_object = ser        # type: ignore[attr-defined]
            elif ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass
            return out
        log.warning("avrdude failed (%s):\n%s", res.kind, res.output)
        # Only a sync failure is worth retrying at the other baud. A
        # busy port or a wrong chip fails the same way twice and the
        # second attempt only wastes the user's time.
        if res.kind != "sync_failed" or i == len(order) - 1:
            break
    kind = last.kind if last is not None else "unknown"
    template = _MESSAGES.get(kind, _MESSAGES["unknown"])
    message = template.format(short=short_port(port), timeout=timeout_s,
                              baud=order[0] if order else 0)
    return FlashResult(ok=False, baud=None, banner_seen=False,
                       message=message,
                       detail=last.output if last is not None else "",
                       seconds=time.perf_counter() - started, kind=kind)


def _keep_open(banner: str | None) -> bool:
    """True for the address tool's banner, which is the one flash whose
    port the caller still needs."""
    return bool(banner) and "ADDR TOOL" in str(banner)


def _progress_line(line: str) -> str:
    """Turn one avrdude line into something a therapist can read."""
    low = line.lower()
    if "writing" in low and "flash" in low:
        return "Writing"
    if "reading" in low and "flash" in low:
        return "Reading back"
    if "verified" in low:
        return "Verified"
    if "not in sync" in low or "not responding" in low:
        return "No answer at this speed"
    return "Writing" if line.startswith("#") else line[:60]


# ---------------------------------------------------------------------
# Background jobs
# ---------------------------------------------------------------------

class _Job(threading.Thread):
    """Shared state plumbing for the two jobs.

    Everything the screen reads goes through the lock. The thread never
    touches the engine, pygame or the config file: the screen does that
    on the main thread once `done` is set.
    """

    def __init__(self, name: str) -> None:
        super().__init__(daemon=True, name=name)
        self._lock = threading.Lock()
        self._message = "Starting"
        self.done = False
        self.result: FlashResult | None = None
        self.ok = False
        self.summary = ""
        self.baud: int | None = None

    @property
    def message(self) -> str:
        with self._lock:
            return self._message

    def _say(self, text: str) -> None:
        with self._lock:
            self._message = text


class FirmwareJob(_Job):
    """Flash the game firmware. One click, one board, nothing to answer."""

    def __init__(self, tool: AvrdudeTool, port: str, image: FirmwareImage,
                 cfg, *, popen=subprocess.Popen, open_port=None) -> None:
        super().__init__("FirmwareJob")
        self.tool = tool
        self.port = port
        self.image = image
        self.cfg = cfg
        self._popen = popen
        self._open_port = open_port

    def run(self) -> None:
        try:
            res = flash_image(
                self.tool, self.port, self.image, self.cfg,
                on_status=self._say,
                banner=str(self.cfg.get("firmware.game_banner",
                                        DEFAULT_GAME_BANNER)),
                popen=self._popen, open_port=self._open_port)
            self.result = res
            self.ok = res.ok
            self.baud = res.baud
            self.summary = res.message
            self._say(res.message)
        except Exception as e:                     # never kill the thread silently
            log.exception("Firmware job failed")
            self.ok = False
            self.summary = f"The flash failed: {e}"
            self._say(self.summary)
        finally:
            self.done = True


class AddressJob(_Job):
    """Flash the address tool, drive it, put the game firmware back.

    Three flashes' worth of patience for the user, and the game
    firmware goes back on the board even when the address change itself
    is refused or fails. A board left carrying the address tool would
    silently stop producing FSR lines and look like dead hardware.
    """

    RESTORE_FAILED = ("The GAME firmware is NOT on the board. Press Flash "
                      "firmware before playing.")

    def __init__(self, tool: AvrdudeTool, port: str,
                 tool_image: FirmwareImage, game_image: FirmwareImage, cfg,
                 *, change: bool = False, old: int = 0x04, new: int = 0x05,
                 popen=subprocess.Popen, open_port=None,
                 reply_timeout_s: float = 3.0) -> None:
        super().__init__("AddressJob")
        self.tool = tool
        self.port = port
        self.tool_image = tool_image
        self.game_image = game_image
        self.cfg = cfg
        self.change = bool(change)
        self.old = int(old)
        self.new = int(new)
        self._popen = popen
        self._open_port = open_port
        self._reply_timeout_s = float(reply_timeout_s)
        self.found_before: list[int] = []
        self.found_after: list[int] = []
        self.tool_reply = ""
        self.refused = False

    # -- serial helpers -------------------------------------------------

    @staticmethod
    def _parse_found(line: str) -> list[int]:
        body = line.split(":", 1)[1].strip() if ":" in line else ""
        if not body or body.lower() == "none":
            return []
        out: list[int] = []
        for tok in body.split(","):
            tok = tok.strip()
            if not tok:
                continue
            try:
                # Base 16 either way: Python accepts the 0x prefix here,
                # and the tool prints bare hex for nothing else.
                out.append(int(tok, 16))
            except ValueError:
                continue
        return out

    def _ask(self, ser, command: str, prefixes: tuple[str, ...]) -> str:
        """Send one line, return the first reply that starts with one of
        `prefixes`, or "" if the tool said nothing in time."""
        try:
            ser.write((command + "\n").encode("ascii"))
        except Exception as e:
            log.warning("Writing %s to the address tool failed: %s",
                        command, e)
            return ""
        deadline = time.perf_counter() + self._reply_timeout_s
        buf = ""
        while time.perf_counter() < deadline:
            try:
                data = ser.read(256)
            except Exception:
                break
            if data:
                if isinstance(data, bytes):
                    data = data.decode("utf-8", errors="replace")
                buf += data
                for raw in buf.splitlines():
                    line = raw.strip()
                    if any(line.startswith(p) for p in prefixes):
                        return line
            else:
                time.sleep(0.02)
        return ""

    # -- the sequence ---------------------------------------------------

    def run(self) -> None:
        ser = None
        try:
            self._say("Loading the address tool")
            res = flash_image(
                self.tool, self.port, self.tool_image, self.cfg,
                on_status=self._say,
                banner=str(self.cfg.get("firmware.tool_banner",
                                        DEFAULT_TOOL_BANNER)),
                popen=self._popen, open_port=self._open_port)
            self.result = res
            self.baud = res.baud
            if not res.ok:
                self.ok = False
                self.summary = res.message
                self._say(self.summary)
                return
            ser = getattr(res, "port_object", None)
            if ser is None:
                self.ok = False
                self.summary = ("The address tool is on the board but its "
                                "serial port would not open. Unplug and "
                                "replug the board.")
                self._say(self.summary)
                return
            self._say("Scanning the I2C bus")
            reply = self._ask(ser, "SCAN", ("FOUND:",))
            if not reply:
                self.ok = False
                self.summary = ("The address tool did not answer. Unplug "
                                "and replug the board and try again.")
                self._say(self.summary)
                return
            self.found_before = self._parse_found(reply)
            if self.change:
                self._do_change(ser)
        except Exception as e:
            log.exception("Address job failed")
            self.ok = False
            self.summary = f"The address change failed: {e}"
        finally:
            if ser is not None:
                try:
                    ser.close()
                except Exception:
                    pass
            self._restore()
            self.done = True

    def _do_change(self, ser) -> None:
        others = [a for a in self.found_before if a != 0x04]
        # A write to 0x04 lands on every SingleTact on the bus at once,
        # so a change FROM 0x04 with any addressed sensor attached would
        # move all of them. Refuse rather than warn: the user cannot
        # undo it afterwards without doing each sensor one at a time.
        if self.old == 0x04 and others:
            self.refused = True
            self.ok = False
            self.summary = (
                "Refused: " + ", ".join(f"0x{a:02X}" for a in others)
                + " also answer. A change from 0x04 would re-address all "
                  "of them. Unplug every other sensor and try again.")
            self._say(self.summary)
            return
        self._say(f"Changing 0x{self.old:02X} to 0x{self.new:02X}")
        reply = self._ask(ser, f"CHANGE:0x{self.old:02X},0x{self.new:02X}",
                          ("OK:", "ERR:"))
        self.tool_reply = reply
        if not reply:
            self.ok = False
            self.summary = ("The address tool stopped answering during the "
                            "change. Check the wiring and try again.")
            self._say(self.summary)
            return
        after = self._ask(ser, "SCAN", ("FOUND:",))
        if after:
            self.found_after = self._parse_found(after)
        if reply.startswith("OK:"):
            self.ok = True
            self.summary = (
                f"Sensor moved from 0x{self.old:02X} to 0x{self.new:02X}. "
                + self._bus_line(self.found_after))
        else:
            self.ok = False
            self.summary = self._explain(reply)
        self._say(self.summary)

    @staticmethod
    def _bus_line(addresses) -> str:
        if not addresses:
            return "Nothing answers on the bus now."
        return "On the bus now: " + ", ".join(
            f"0x{a:02X}" for a in sorted(addresses)) + "."

    def _explain(self, reply: str) -> str:
        low = reply.lower()
        if "after the write" in low:
            return ("The sensor did not take the new address. Check the "
                    "wiring, or the sensor may be a calibrated unit that "
                    "locks its settings. Nothing else changed.")
        if "still answers" in low:
            return ("The sensor answered on the old address after the "
                    "write, so the change did not stick.")
        if "nothing answers at" in low:
            return (f"Nothing answers at 0x{self.old:02X}. Check the sensor "
                    "is wired and powered.")
        return reply

    def _restore(self) -> None:
        """Put the game firmware back, whatever happened above."""
        try:
            self._say("Putting the game firmware back")
            res = flash_image(
                self.tool, self.port, self.game_image, self.cfg,
                on_status=self._say,
                banner=str(self.cfg.get("firmware.game_banner",
                                        DEFAULT_GAME_BANNER)),
                popen=self._popen, open_port=self._open_port)
            if res.ok:
                if self.baud is None:
                    self.baud = res.baud
                if self.ok:
                    self.summary += " Game firmware restored."
                return
            self.ok = False
            self.summary = (self.RESTORE_FAILED + " " + self.summary).strip()
            self._say(self.summary)
        except Exception as e:
            log.exception("Restoring the game firmware failed")
            self.ok = False
            self.summary = (self.RESTORE_FAILED + f" ({e})").strip()
