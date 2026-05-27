"""EEG marker output. Some labs run an EEG amplifier alongside motor
tasks and want a sync trigger on every event. This module opens an
independent serial port (separate from the Arduino sensor port) and
emits single-byte event codes:

    1   block start
    2   block end
    3   block abandoned
    11..18   stimulus on lane 0..7
    21..28   response (correct press) on lane 0..7
    30       miss / timeout
    0        reset (sent shortly after each code so the amplifier
             returns to its idle line)

The output is OPTIONAL: if eeg.enabled is false in the config OR the
port can't be opened, every send_* method is a no-op. The engine
calls these methods without checking - the silence is built in.

Protocol matches Aiden's prototype so a single amplifier setup works
for both pipelines.
"""
from __future__ import annotations

import logging
import threading
import time


log = logging.getLogger(__name__)


try:
    import serial
    _HAVE_SERIAL = True
except ImportError:
    serial = None   # type: ignore[assignment]
    _HAVE_SERIAL = False


# Event-code numbering. Stim and response share an offset scheme so a
# downstream analysis script can compute (lane = code - STIM_BASE) or
# (lane = code - RESP_BASE) directly.
CODE_BLOCK_START = 1
CODE_BLOCK_END = 2
CODE_BLOCK_ABANDONED = 3
CODE_MISS = 30
STIM_BASE = 11      # +lane -> 11..18 for lanes 0..7
RESP_BASE = 21      # +lane -> 21..28 for lanes 0..7
CODE_RESET = 0      # idle line; sent after each marker


class EEGMarker:
    """Single-byte serial marker emitter for EEG sync. Safe to construct
    even when there's no amplifier - if `init()` fails, every method
    silently no-ops."""

    def __init__(self, port: str | None = None,
                 baud: int = 115200,
                 reset_after_s: float = 0.020,
                 enabled: bool = True) -> None:
        self.port = port
        self.baud = baud
        self.reset_after_s = reset_after_s
        self.enabled = enabled
        self._serial = None
        self._lock = threading.Lock()
        self._pending_resets: list[float] = []

    def init(self) -> bool:
        """Open the port. Returns True if ready to send, False if not
        (e.g. disabled, no pyserial, port unavailable). Idempotent."""
        if not self.enabled:
            log.info("EEG markers disabled in config")
            return False
        if not _HAVE_SERIAL:
            log.warning("pyserial not available; EEG markers disabled")
            return False
        if not self.port:
            log.info("No EEG port configured; markers disabled")
            return False
        if self._serial is not None and self._serial.is_open:
            return True
        try:
            self._serial = serial.Serial(
                self.port, self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0,
                # write_timeout caps any single write at 0.5s so a wedged
                # amp or yanked cable can't hang close() (which calls
                # _send_byte under the lock) or the per-frame tick().
                write_timeout=0.5,
            )
            log.info("EEG markers on %s @ %d", self.port, self.baud)
            return True
        except Exception as e:
            log.warning("Could not open EEG port %s: %s", self.port, e)
            self._serial = None
            return False

    def close(self) -> None:
        with self._lock:
            try:
                if self._serial and self._serial.is_open:
                    self._send_byte(CODE_RESET)
                    self._serial.close()
            except Exception as e:
                log.debug("EEG close noise: %s", e)
            self._serial = None
            self._pending_resets.clear()

    @property
    def is_open(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    # ---- Event sends ----

    def block_start(self) -> None:
        self._send(CODE_BLOCK_START)

    def block_end(self) -> None:
        self._send(CODE_BLOCK_END)

    def block_abandoned(self) -> None:
        self._send(CODE_BLOCK_ABANDONED)

    def stim(self, lane: int) -> None:
        if 0 <= lane <= 7:
            self._send(STIM_BASE + lane)

    def response(self, lane: int) -> None:
        if 0 <= lane <= 7:
            self._send(RESP_BASE + lane)

    def miss(self) -> None:
        self._send(CODE_MISS)

    # ---- Reset tick ----

    def tick(self) -> None:
        """Call once per frame from the engine main loop. Sends a reset
        byte after `reset_after_s` so the amplifier line drops back to
        the idle level between markers (otherwise the next marker rides
        on top of the previous code and pulse-shape analysis fails)."""
        if not self.is_open or not self._pending_resets:
            return
        now = time.perf_counter()
        with self._lock:
            still = []
            should_reset = False
            for due in self._pending_resets:
                if now >= due:
                    should_reset = True
                else:
                    still.append(due)
            self._pending_resets = still
            if should_reset:
                self._send_byte(CODE_RESET)

    # ---- Internals ----

    def _send(self, code: int) -> None:
        if not self.is_open:
            return
        with self._lock:
            self._send_byte(code & 0xFF)
            if self.reset_after_s > 0:
                self._pending_resets.append(
                    time.perf_counter() + self.reset_after_s)

    def _send_byte(self, code: int) -> None:
        try:
            self._serial.write(bytes([code & 0xFF]))
        except Exception as e:
            log.warning("EEG write failed: %s", e)
