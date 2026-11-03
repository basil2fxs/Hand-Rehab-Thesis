"""How long from the port opening to the first force sample, on a simulated
board that behaves as the logged start-ups say the real one does.

Opening the port resets the Nano. Its bootloader runs, then the firmware's
setup, then the stream. The 2026-09 firmware buzzed the four motors one at a
time before streaming (0.5 s, 4 x 0.4 s, 0.5 s: 2.6 s), and the software
slept a fixed 3 s after the open and threw away what had arrived. Every
valid logged start-up was 4.24 s or 3.01 s (the reconnect fault's negative
values are left out), which fits a bootloader of 1.64 s, or of under 0.4 s
on the few boards where the 3 s wait outlasted the boot.

The simulated port below replays that boot in real time behind the real
SerialSource. The old firmware with the old 3 s wait has to reproduce the
logs first, which is the check that the model is the board; then the new
firmware (stream first, self-test buzzing while it streams) with the new
read (no fixed wait, the first FSR line is the start) gives the time a
board flashed from this build should take.

    cd analysis
    python3 startup_sim.py [SESSION_ROOT ...] [--reps 5] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import sys
import threading
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import finger_rehab.hardware.serial_source as ss  # noqa: E402

LINE_S = 0.005                      # the board's 200 Hz stream
FIRMWARE_SETUP_S = {"2026-09": 2.6,  # 0.5 s, four motors 0.4 s each, 0.5 s
                    "2026-11": 0.1}  # 0.1 s, then stream; the self-test runs alongside


class SimBoard:
    """Stands in for serial.Serial: the open resets the board, and bytes
    become readable when the boot the logs imply would have sent them."""

    boot_s = 1.64
    firmware = "2026-09"

    def __init__(self, *_a, **kw) -> None:
        self.t0 = time.perf_counter()
        self.timeout = float(kw.get("timeout") or 0.02)
        self.is_open = True
        self.sent = 0                      # lines already handed over
        self.dropped_before = 0.0          # reset_input_buffer discards up to here
        self.written: list[tuple[float, bytes]] = []
        self.stream_t = self.boot_s + FIRMWARE_SETUP_S[self.firmware]

    def _due(self, now: float) -> int:
        """Lines the board has sent by now: the banner, then the stream."""
        if now < self.stream_t:
            return 0
        return 1 + int((now - self.stream_t) / LINE_S)

    def _line(self, k: int) -> bytes:
        return b"### Setup Complete ###\n" if k == 0 else b"FSR: 265,270,268,290\n"

    @property
    def in_waiting(self) -> int:
        now = time.perf_counter() - self.t0
        first = max(self.sent, self._due(self.dropped_before))
        return sum(len(self._line(k)) for k in range(first, self._due(now)))

    def read(self, n: int) -> bytes:
        deadline = time.perf_counter() + self.timeout
        while True:
            now = time.perf_counter() - self.t0
            self.sent = max(self.sent, self._due(self.dropped_before))
            due = self._due(now)
            if due > self.sent:
                out = b"".join(self._line(k) for k in range(self.sent, due))
                self.sent = due
                return out[:max(n, len(out))]
            if time.perf_counter() >= deadline:
                return b""
            time.sleep(0.001)

    def reset_input_buffer(self) -> None:
        self.dropped_before = time.perf_counter() - self.t0

    def write(self, data: bytes) -> int:
        self.written.append((time.perf_counter() - self.t0, bytes(data)))
        return len(data)

    def close(self) -> None:
        self.is_open = False


def one_start(boot_s: float, firmware: str, settle_s: float) -> float:
    """Open a SerialSource on the simulated board; seconds to its first sample."""
    SimBoard.boot_s, SimBoard.firmware = boot_s, firmware
    real = ss.serial.Serial
    ss.serial.Serial = SimBoard
    try:
        src = ss.SerialSource(port="/dev/sim", baud=115200)
        src.boot_settle_s = settle_s
        src.start()
        t_end = time.perf_counter() + 8.0
        while src.get_startup_latency_ms() is None and time.perf_counter() < t_end:
            time.sleep(0.005)
        ms = src.get_startup_latency_ms()
        src.stop()
    finally:
        ss.serial.Serial = real
    return float("nan") if ms is None else ms / 1000.0


def logged(roots: list[Path]) -> list[float]:
    """Every valid logged start-up, in s: the block summaries' first-sample
    latency, the negative values of the fixed reconnect fault left out."""
    out = []
    for root in roots:
        for m in root.rglob("metadata.json"):
            try:
                d = json.loads(m.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            v = (d.get("block_summary") or {}).get("startup_latency_ms")
            vals = list(v.values()) if isinstance(v, dict) else [v]
            out += [float(x) / 1000.0 for x in vals if isinstance(x, (int, float)) and x > 0]
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("roots", nargs="*", type=Path, help="folders of session folders, read for the logged start-ups")
    ap.add_argument("--reps", type=int, default=5)
    ap.add_argument("--json", type=Path)
    args = ap.parse_args(argv)
    res: dict = {}
    if args.roots:
        log_s = logged(args.roots)
        res["logged"] = {"n": len(log_s), "values_s": sorted({round(x, 2) for x in log_s}),
                         "counts": {f"{x:.2f}": int(sum(abs(y - x) < 0.015 for y in log_s))
                                    for x in sorted({round(y, 2) for y in log_s})}}
        print(f"logged start-ups: {len(log_s)}, {res['logged']['counts']}")
    # the two bootloaders the logs imply: 4.24 s less the 2.6 s setup, and one
    # short enough that the 3 s wait outlasted the whole boot
    boots = {"slow bootloader (1.64 s)": 1.64, "fast bootloader (0.3 s)": 0.3}
    cases = [("old firmware, old 3 s wait", "2026-09", 3.0),
             ("new firmware, old 3 s wait", "2026-11", 3.0),
             ("old firmware, new read", "2026-09", 0.0),
             ("new firmware, new read", "2026-11", 0.0)]
    for bname, boot in boots.items():
        for cname, fw, settle in cases:
            xs = [one_start(boot, fw, settle) for _ in range(args.reps)]
            res.setdefault(bname, {})[cname] = {"median_s": float(np.median(xs)), "max_s": float(np.max(xs))}
            print(f"{bname:26s} {cname:28s} first sample {np.median(xs):.2f} s (max {np.max(xs):.2f})")
    if args.json:
        args.json.write_text(json.dumps(res, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
