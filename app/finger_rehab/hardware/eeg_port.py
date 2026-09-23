"""Which serial port the EEG trigger box is on, and changing it.

The lab config names the box's port (COM10 on the lab desktop).
Windows numbers COM ports per USB socket, so the same box can come up
as COM7 on another socket or another PC, and then the lab build had no
way forward but a text editor. This module is what the in-game port
picker runs on:

- candidates(): the ports the box could be on, minus the hand boards;
- open_port(): open one exactly as the marker writer would, and say
  why not when it will not open;
- save_port(): keep the choice, on the same `port:` line of the same
  eeg_lab.yaml a person would edit by hand, comments and all.

It also answers the other half of the problem, reserved_port(): the
hand-board discovery used to take any USB serial device when no known
Arduino was plugged in, and in the lab the trigger box is exactly such
a device. On Windows that locked the box's port before the marker
writer could open it; on a Mac both could open it and hand-board
commands would have gone out as trigger codes. Discovery now leaves
the reserved port alone.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from .eeg_trigger import SerialBackend

log = logging.getLogger(__name__)


def reserved_port(get) -> str | None:
    """The trigger box's port while EEG markers are on, else None.

    `get` is a config getter (cfg.get). Hand-board discovery skips
    this port so the two never share one.
    """
    if not get("eeg.enabled", False):
        return None
    port = get("eeg.port", None)
    port = str(port).strip() if port else ""
    return port or None


def same_port(a: str | None, b: str | None) -> bool:
    """Port names compare case-blind: Windows treats com7 and COM7 as
    the same device, and a hand-typed yaml value may use either."""
    if not a or not b:
        return False
    return a.strip().lower() == b.strip().lower()


@dataclass(frozen=True)
class PortChoice:
    device: str
    description: str
    vid: int | None
    pid: int | None

    @property
    def label(self) -> str:
        """One line for the picker: the name people see in Device
        Manager first, then what the driver calls the device."""
        desc = (self.description or "").strip()
        if not desc or desc.lower() in ("n/a", self.device.lower()):
            return self.device
        return f"{self.device}   {desc}"


def candidates(exclude=()) -> list[PortChoice]:
    """Every serial port the box could be on.

    Leaves out the OS's own virtual ports (Bluetooth, debug console)
    and anything in `exclude`, which is the ports the hand boards
    hold. USB devices come first, in name order.
    """
    try:
        from .serial_source import _is_junk_port, list_available_ports
    except ImportError:
        return []
    skip = [str(x) for x in exclude if x]
    out = []
    for p in list_available_ports():
        if _is_junk_port(p.device):
            continue
        if any(same_port(p.device, x) for x in skip):
            continue
        out.append(PortChoice(p.device, p.description, p.vid, p.pid))
    out.sort(key=lambda c: (c.vid is None, _natural(c.device)))
    return out


def _natural(name: str) -> list:
    """COM2 before COM10."""
    return [int(t) if t.isdigit() else t.lower()
            for t in re.split(r"(\d+)", name)]


def plain_reason(error: str) -> str:
    """pyserial's error in the words a researcher needs. The OS text
    is long and differs per platform; what matters is which of three
    things happened."""
    low = (error or "").lower()
    if any(k in low for k in ("no such file", "cannot find the file",
                              "filenotfounderror", "not found")):
        return "not plugged in, or a different COM number"
    if any(k in low for k in ("access is denied", "permission",
                              "resource busy", "in use")):
        return "in use by another program (close it and try again)"
    if not low:
        return "it would not open"
    return error if len(error) <= 60 else error[:57] + "..."


def open_port(port: str, baud: int) -> tuple[SerialBackend | None, str]:
    """Open `port` the way the marker writer does.

    Returns (backend, "") on success, or (None, reason). 1200 baud is
    refused for the same reason writer_from_config refuses it: it
    resets the MMBT-S.
    """
    if int(baud) == 1200:
        return None, "1200 baud resets the trigger box"
    backend = SerialBackend(str(port), int(baud))
    if backend.open():
        return backend, ""
    return None, plain_reason(backend.last_error)


# ---- saving -------------------------------------------------------------

_TOP_KEY = re.compile(r"^(?P<key>[A-Za-z_][\w-]*)\s*:")
_PORT_LINE = re.compile(
    r"^(?P<indent>[ \t]+)port[ \t]*:[ \t]*(?P<value>[^#\r\n]*?)"
    r"(?P<gap>[ \t]*)(?P<comment>#[^\r\n]*)?$")
_PLAIN = re.compile(r"^[A-Za-z0-9/._\\:-]+$")


def _yaml_scalar(port: str) -> str:
    """The port as it should appear after `port: `. Plain for any
    ordinary device name, quoted when yaml would misread it."""
    if _PLAIN.match(port) and yaml.safe_load(port) == port:
        return port
    return '"' + port.replace("\\", "\\\\").replace('"', '\\"') + '"'


def set_port_line(text: str, port: str) -> str:
    """Return `text` with eeg.port set to `port`.

    Edits the one line, so every comment in the file survives and the
    diff is exactly the change. Adds the key under `eeg:` if the block
    has none, and adds the block if the file has none. Line endings
    are kept as found: the lab's copy may have come out of CI with
    Windows ones.
    """
    newline = "\r\n" if "\r\n" in text else "\n"
    lines = text.splitlines()
    value = _yaml_scalar(port)
    eeg_at = None
    for i, line in enumerate(lines):
        m = _TOP_KEY.match(line)
        if m and m.group("key") == "eeg":
            eeg_at = i
            break
    if eeg_at is None:
        body = newline.join(lines)
        if body and not body.endswith(newline):
            body += newline
        return f"{body}eeg:{newline}  port: {value}{newline}"
    # The block runs until the next line that starts at column 0 and is
    # not a comment or blank.
    end = len(lines)
    for j in range(eeg_at + 1, len(lines)):
        line = lines[j]
        if line and not line[0].isspace() and not line.startswith("#"):
            end = j
            break
    block_indent = None
    for j in range(eeg_at + 1, end):
        line = lines[j]
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = line[:len(line) - len(stripped)]
        if block_indent is None:
            block_indent = indent
        if indent != block_indent:
            continue
        m = _PORT_LINE.match(line)
        if m:
            comment = m.group("comment")
            tail = (m.group("gap") or " ") + comment if comment else ""
            lines[j] = f"{m.group('indent')}port: {value}{tail}"
            return newline.join(lines) + newline
    indent = block_indent or "  "
    lines.insert(eeg_at + 1, f"{indent}port: {value}")
    return newline.join(lines) + newline


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(path.name + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        f.write(text)
        f.flush()
        try:
            os.fsync(f.fileno())
        except (OSError, AttributeError):
            pass
    os.replace(tmp, path)


def save_port(cfg, port: str) -> tuple[Path | None, str]:
    """Keep `port` for the next launch and use it for this one.

    Where it goes follows where the lab settings came from:
      - a lab folder's own eeg_lab.yaml (the exe's neighbour, or the
        file run_in_psychopy.py passed): that file's `port:` line;
      - the copy inside the app (Local_Runner): config/eeg_port.yaml
        beside it, because the app's copy is tracked and ships to the
        lab and a Mac port name has no business in it;
      - no lab file at all: user_settings.yaml, like every other
        Settings change.
    Returns (path written or None, one line for the screen).
    """
    from .. import config as config_mod

    cfg.data.setdefault("eeg", {})["port"] = port
    source = getattr(cfg, "source", None)
    try:
        if source is None or Path(source) in (
                config_mod.DEFAULT_CONFIG, config_mod.USER_OVERRIDES):
            path = cfg.save_user_overrides({"eeg.port": port})
        elif config_mod.is_bundled_config(source):
            path = config_mod.EEG_PORT_FILE
            path.parent.mkdir(parents=True, exist_ok=True)
            _write_atomic(path, yaml.safe_dump({"port": port}))
        else:
            path = Path(source)
            raw = path.read_bytes().decode("utf-8")
            updated = set_port_line(raw, port)
            check = yaml.safe_load(updated) or {}
            if (check.get("eeg") or {}).get("port") != port:
                raise ValueError("the edited file did not read back")
            _write_atomic(path, updated)
    except Exception as e:
        log.warning("Could not save the EEG port %s: %s", port, e)
        return None, (f"Not saved ({e}). It holds until the game closes; "
                      f"set port: {port} in eeg_lab.yaml to keep it.")
    log.info("EEG port %s saved to %s", port, path)
    return path, f"Saved to {path.name}."
