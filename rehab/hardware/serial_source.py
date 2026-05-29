"""Arduino serial source with auto-port discovery (Thread 4)."""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

try:
    import serial
    from serial.tools import list_ports
    _HAVE_SERIAL = True
except ImportError:
    serial = None         # type: ignore[assignment]
    list_ports = None     # type: ignore[assignment]
    _HAVE_SERIAL = False

from .source import BaseQueueSource


log = logging.getLogger(__name__)


# Old firmware sent FSR:v1,v2,v3,v4. New firmware can extend to 8 for bilateral.
# Matching 4 or 8 lets us avoid two regexes.
_LINE_RE = re.compile(
    rb"FSR:\s*(-?\d+)(?:\s*,\s*(-?\d+))(?:\s*,\s*(-?\d+))(?:\s*,\s*(-?\d+))"
    rb"(?:\s*,\s*(-?\d+))?(?:\s*,\s*(-?\d+))?(?:\s*,\s*(-?\d+))?(?:\s*,\s*(-?\d+))?"
)


@dataclass
class PortInfo:
    device: str
    description: str
    vid: int | None
    pid: int | None


def list_available_ports() -> list[PortInfo]:
    if not _HAVE_SERIAL:
        return []
    out: list[PortInfo] = []
    for p in list_ports.comports():
        out.append(PortInfo(
            device=p.device,
            description=p.description or "",
            vid=p.vid,
            pid=p.pid,
        ))
    return out


def discover_port(expected_vids: list[str] | None) -> str | None:
    """Pick the Arduino-family port, or None if zero/multiple match.

    Falls back to "the only port present" if there's exactly one and no VID match.
    """
    ports = list_available_ports()
    if not ports:
        log.warning("No serial ports found")
        return None

    vid_set: set[int] = set()
    for v in expected_vids or []:
        try:
            vid_set.add(int(v, 16) if isinstance(v, str) else int(v))
        except (TypeError, ValueError):
            log.warning("Bad VID in config: %r", v)

    matches = []
    log.info("Detected ports:")
    for p in ports:
        marker = ""
        if p.vid is not None and p.vid in vid_set:
            marker = "  <-- arduino-family"
            matches.append(p)
        vid_str = f"0x{p.vid:04x}" if p.vid is not None else "?"
        pid_str = f"0x{p.pid:04x}" if p.pid is not None else "?"
        log.info("  %s vid=%s pid=%s %s%s",
                 p.device, vid_str, pid_str, p.description, marker)

    if len(matches) == 1:
        log.info("Auto-selected %s", matches[0].device)
        return matches[0].device
    if len(matches) > 1:
        log.warning("Multiple Arduino-family ports: %s. Pass --port to pick one.",
                    [m.device for m in matches])
        return None
    if len(ports) == 1:
        log.info("Only one port present, using %s", ports[0].device)
        return ports[0].device
    return None


# macOS exposes a few always-present virtual serial ports that have no
# USB vendor / product ID: the kernel debug console and Bluetooth
# RFCOMM endpoints. Without a denylist the no-VID fallback in
# discover_ports happily picked these up as "Arduinos", which then sat
# open forever sending nothing while the diagnostics screen showed
# CONNECTED. The list isn't exhaustive but covers stock macOS.
_KNOWN_JUNK_PORTS = (
    "debug-console",
    "Bluetooth-Incoming-Port",
    "Bluetooth-Outgoing-Port",
    "wlan-debug",
)


def _is_junk_port(device: str) -> bool:
    return any(j in device for j in _KNOWN_JUNK_PORTS)


def discover_ports(expected_vids: list[str] | None,
                    max_ports: int = 2) -> list[str]:
    """Return Arduino-family ports the host can see, up to max_ports.

    Priority:
      1. Ports whose USB VID matches a known Arduino-family vendor
         (Arduino LLC, Adafruit, SiLabs, CH340, FTDI by default).
      2. Otherwise, ports that have ANY VID set, i.e. real USB
         devices just not on the vendor list. Catches unbranded
         clones.
      3. Otherwise empty, so the engine falls back to keyboard mode
         instead of opening a random Mac virtual port.

    Junk ports (debug-console, Bluetooth-Incoming-Port, etc.) are
    filtered at every step so they never get picked automatically.
    The user can still assign them manually in the Settings screen if
    they really want to.
    """
    ports = list_available_ports()
    if not ports:
        return []
    vid_set: set[int] = set()
    for v in expected_vids or []:
        try:
            vid_set.add(int(v, 16) if isinstance(v, str) else int(v))
        except (TypeError, ValueError):
            log.warning("Bad VID in config: %r", v)

    # Pass 1: VID matches a known Arduino-family vendor.
    vid_matches = [p.device for p in ports
                    if p.vid is not None and p.vid in vid_set
                    and not _is_junk_port(p.device)]
    if vid_matches:
        return vid_matches[:max_ports]

    # Pass 2: any port that has a VID and isn't junk.
    any_real_usb = [p.device for p in ports
                    if p.vid is not None
                    and not _is_junk_port(p.device)]
    if any_real_usb:
        return any_real_usb[:max_ports]

    # No real USB serial device. Don't fall back to junk ports.
    return []


def _require_serial() -> None:
    if not _HAVE_SERIAL:
        raise RuntimeError(
            "pyserial not installed. Run `pip install pyserial` "
            "or use --source keyboard."
        )


class SerialSource(BaseQueueSource):
    def __init__(self, port: str, baud: int = 115200,
                 num_sensors: int = 4, read_timeout_s: float = 0.02,
                 open_retries: int = 3, retry_delay_s: float = 1.0) -> None:
        _require_serial()
        super().__init__()
        self.port = port
        self.baud = baud
        self.num_sensors = num_sensors  # 4 for unilateral, 8 for bilateral
        self.read_timeout_s = read_timeout_s
        self.open_retries = open_retries
        self.retry_delay_s = retry_delay_s
        self._serial: serial.Serial | None = None
        # Startup-latency capture. `_port_open_ts` is stamped the
        # instant pyserial returns from serial.Serial(...). It
        # captures the kernel-level enumeration latency for this
        # port. `_first_sample_ts` is stamped the first time the
        # firmware sends a parseable FSR: line. The difference is
        # the time-to-first-sample latency that lives in
        # session.json's `startup_latency_ms` field.
        self._port_open_ts: float | None = None
        self._first_sample_ts: float | None = None

    @property
    def name(self) -> str:
        return f"SerialSource({self.port}@{self.baud})"

    def _open(self) -> "serial.Serial":
        for attempt in range(1, self.open_retries + 1):
            try:
                s = serial.Serial(
                    self.port, self.baud,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    timeout=self.read_timeout_s,
                    write_timeout=0.5,
                )
                # Stamp the open timestamp here, not before the 1.8 s
                # Arduino-reset sleep. The latency we want to measure
                # is "open -> first valid FSR sample", which includes
                # the firmware's own boot delay - that's part of the
                # patient's perceived wait.
                self._port_open_ts = time.perf_counter()
                time.sleep(1.8)  # Arduino reset settle
                s.reset_input_buffer()
                log.info("Opened %s @ %d", self.port, self.baud)
                return s
            except serial.SerialException as e:
                log.warning("Open %s failed (try %d/%d): %s",
                            self.port, attempt, self.open_retries, e)
                # Skip the wait after the final attempt; we're about to
                # raise anyway and the patient is already waiting.
                if attempt < self.open_retries:
                    time.sleep(self.retry_delay_s)
        raise serial.SerialException(
            f"Could not open {self.port} after {self.open_retries} tries"
        )

    def _run(self) -> None:
        try:
            self._serial = self._open()
            self._connected = True
        except serial.SerialException as e:
            log.error("Serial source failed to start: %s", e)
            self._connected = False
            return

        buf = bytearray()
        try:
            while not self._stop.is_set():
                try:
                    chunk = self._serial.read(256)
                except (serial.SerialException, OSError) as e:
                    log.error("Serial read error: %s", e)
                    break
                if not chunk:
                    continue
                buf.extend(chunk)
                self._consume(buf)
        finally:
            self._connected = False
            try:
                if self._serial:
                    self._serial.close()
            except (Exception,) as e:
                # serial.SerialException isn't always importable on
                # the no-pyserial test path so we keep the catch
                # broad but log at debug. Close-on-shutdown failures
                # are expected when the OS already reclaimed the
                # port (USB unplug) and aren't actionable.
                log.debug("Serial close raised %s: %s",
                            type(e).__name__, e)
            log.info("Serial source stopped")

    def _consume(self, buf: bytearray) -> None:
        while True:
            nl = buf.find(b"\n")
            if nl < 0:
                if len(buf) > 4096:
                    del buf[:-256]   # garbage protection
                return
            line = bytes(buf[:nl])
            del buf[:nl + 1]
            m = _LINE_RE.search(line)
            if not m:
                continue
            vals: list[int] = []
            for i in range(self.num_sensors):
                g = m.group(i + 1)
                if g is None:
                    vals.append(0)
                else:
                    try:
                        vals.append(int(g))
                    except ValueError:
                        vals.append(0)
            # Stamp the first-sample timestamp the moment we get a
            # parseable FSR line. Set-once - subsequent samples don't
            # overwrite. Pairs with _port_open_ts for the startup-
            # latency stat surfaced in session.json. getattr guard
            # tolerates __new__-built test fixtures that skip
            # __init__.
            if getattr(self, "_first_sample_ts", None) is None:
                self._first_sample_ts = time.perf_counter()
            self._push(tuple(vals))

    def get_startup_latency_ms(self) -> float | None:
        """Time-to-first-sample latency in ms. Returns None until both
        the port_open and first_sample timestamps are stamped (a
        source that never received a valid frame, or one that hasn't
        opened yet)."""
        if (self._port_open_ts is None
                or self._first_sample_ts is None):
            return None
        return (self._first_sample_ts - self._port_open_ts) * 1000.0

    def send_command(self, cmd: str) -> bool:
        if not self._serial or not self._serial.is_open:
            return False
        try:
            data = cmd.encode("ascii", errors="ignore")
            if not data.endswith(b"\n"):
                data += b"\n"
            self._serial.write(data)
            return True
        except (serial.SerialException, OSError) as e:
            log.warning("Serial write failed: %s", e)
            return False
