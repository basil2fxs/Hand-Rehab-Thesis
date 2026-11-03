"""The game's first sample comes as soon as the board streams.

Opening the port resets the Nano. The software used to sleep 3 s after the
open and flush what had arrived, and the firmware buzzed its motors for
2.6 s before it streamed, so every logged start-up took 4.24 s (3.01 s on a
quick bootloader) against the 2 s target. Now the reader starts at once,
skips the boot banner as it skips any line that is not FSR, and the first
FSR line is the start; nothing is written to the board before it, since
bytes sent during the bootloader are read as upload commands
(3 November 2026; analysis/startup_sim.py replays the logged boots).
"""
from __future__ import annotations

import time

import finger_rehab.hardware.serial_source as ss


class BootingPort:
    """A port whose board streams boot_s after the open, banner first."""

    boot_s = 0.25

    def __init__(self, *_a, **kw):
        self.t0 = time.perf_counter()
        self.timeout = float(kw.get("timeout") or 0.02)
        self.is_open = True
        self.written: list[bytes] = []
        self._sent = 0

    def _due(self) -> int:
        dt = time.perf_counter() - self.t0 - self.boot_s
        return 0 if dt < 0 else 1 + int(dt / 0.005)

    @property
    def in_waiting(self) -> int:
        return 0

    def read(self, _n):
        end = time.perf_counter() + self.timeout
        while time.perf_counter() < end:
            due = self._due()
            if due > self._sent:
                lines = [b"### Setup Complete ###\n" if k == 0 else b"FSR: 265,270,268,290\n"
                         for k in range(self._sent, due)]
                self._sent = due
                return b"".join(lines)
            time.sleep(0.001)
        return b""

    def write(self, data):
        self.written.append(bytes(data))
        return len(data)

    def reset_input_buffer(self):
        pass

    def close(self):
        self.is_open = False


def _start(monkeypatch, settle_s=None):
    monkeypatch.setattr(ss.serial, "Serial", BootingPort)
    src = ss.SerialSource(port="/dev/sim", baud=115200)
    if settle_s is not None:
        src.boot_settle_s = settle_s
    src.start()
    return src


def _first_sample_s(src, limit_s=3.0):
    end = time.perf_counter() + limit_s
    while src.get_startup_latency_ms() is None and time.perf_counter() < end:
        time.sleep(0.002)
    ms = src.get_startup_latency_ms()
    return None if ms is None else ms / 1000.0


def test_no_fixed_wait_after_the_open(monkeypatch):
    assert ss.BOOT_SETTLE_S == 0.0
    src = _start(monkeypatch)
    try:
        s = _first_sample_s(src)
        assert s is not None and BootingPort.boot_s <= s < BootingPort.boot_s + 0.1
    finally:
        src.stop()


def test_the_old_wait_can_be_put_back_for_the_simulation(monkeypatch):
    src = _start(monkeypatch, settle_s=0.6)
    try:
        s = _first_sample_s(src)
        assert s is not None and s >= 0.6
    finally:
        src.stop()


def test_nothing_is_written_before_the_board_streams(monkeypatch):
    src = _start(monkeypatch)
    try:
        end = time.perf_counter() + 1.0
        while src._serial is None and time.perf_counter() < end:
            time.sleep(0.001)
        assert src._first_sample_ts is None
        assert src.send_command("STIM:1") is False
        assert src._serial.written == []
        assert _first_sample_s(src) is not None
        assert src.send_command("STIM:1") is True
        assert src._serial.written == [b"STIM:1\n"]
    finally:
        src.stop()
