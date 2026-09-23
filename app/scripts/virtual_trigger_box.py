"""A stand-in for the lab's trigger box, for testing the EEG build on a
Mac with the real hand device plugged in.

The lab records the game's markers through a NeuroSpec MMBT-S box on a
serial port. This script opens a pseudo-terminal that behaves like one
(a serial path the game can open, which takes one byte per code and
records it) and starts the game from the lab folder's source/ under
PsychoPy's own Python with the lab's eeg_lab.yaml, the way
run_in_psychopy.py does, plus --eeg-port pointed at the box. The hand
device is found the normal way. When the game closes, every
byte the box received is checked against the markers the game logged
in each block's raw.csv, and the byte log is kept.

    python3 scripts/virtual_trigger_box.py                 run the lab game
    python3 scripts/virtual_trigger_box.py --box-only      just the box;
                                                           prints its port
    python3 scripts/virtual_trigger_box.py --psychopy /path/PsychoPy.app
    python3 scripts/virtual_trigger_box.py -- --port /dev/cu.usbserial-310

Anything after -- goes to the game's main.py as it is.

The byte log lands in <lab folder>/sessions/eeg/virtual_box_<time>.csv
beside the sessions the game writes, so one folder holds both. The lab
folder's eeg_lab.yaml is read, never written.
"""
from __future__ import annotations

import argparse
import csv
import os
import select
import subprocess
import sys
import threading
import time
import tty
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent
sys.path.insert(0, str(APP))

DEFAULT_PSYCHOPY = Path.home() / "Applications" / "PsychoPy.app"
DEFAULT_LAB = REPO / "EEG_Lab"


class VirtualBox:
    """A pseudo-terminal pair: the game writes to `port`, this reads
    the other end and keeps every byte with the time it arrived.

    time.perf_counter is the system's monotonic clock on macOS, the
    same one the game stamps its markers with, so an arrival time can
    be set against the marker's own t_wire.
    """

    def __init__(self) -> None:
        self.master, self._slave = os.openpty()
        # Raw, so no byte is translated on the way (a 10 or a 13 would
        # otherwise be a newline to the line discipline).
        tty.setraw(self._slave)
        tty.setraw(self.master)
        self.port = os.ttyname(self._slave)
        self.bytes: list[tuple[float, float, int]] = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._read, daemon=True)

    def start(self) -> "VirtualBox":
        self._thread.start()
        return self

    def _read(self) -> None:
        while not self._stop.is_set():
            ready, _w, _x = select.select([self.master], [], [], 0.05)
            if not ready:
                continue
            try:
                data = os.read(self.master, 4096)
            except OSError:
                time.sleep(0.02)
                continue
            now_perf, now_wall = time.perf_counter(), time.time()
            for b in data:
                self.bytes.append((now_perf, now_wall, b))

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=1.0)
        for fd in (self.master, self._slave):
            try:
                os.close(fd)
            except OSError:
                pass

    def codes(self) -> list[tuple[float, int]]:
        """(arrival t_perf, code) for every non-zero byte: the zeros
        are the line going back to rest after each code."""
        return [(t, b) for t, _w, b in self.bytes if b != 0]

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        from finger_rehab.hardware.eeg_trigger import name_of
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["t_perf", "wall_time", "code", "name"])
            for t, wall, b in self.bytes:
                w.writerow([f"{t:.6f}", f"{wall:.6f}", b,
                            name_of(b) if b else "rest"])


def psychopy_python(app: Path) -> tuple[Path, dict]:
    """PsychoPy's own interpreter and the environment Coder runs it in.
    The app bundle's Python only starts with PYTHONHOME pointing at its
    Resources folder, which the app sets for scripts run from Coder."""
    exe = app / "Contents" / "MacOS" / "python"
    home = app / "Contents" / "Resources"
    if not exe.is_file():
        raise SystemExit(f"No PsychoPy Python at {exe}. Pass --psychopy "
                         "with the path to PsychoPy.app.")
    env = dict(os.environ)
    env["PYTHONHOME"] = str(home)
    return exe, env


def logged_markers(sessions: Path, since_wall: float) -> list[dict]:
    """Every marker the game logged in a block folder written since the
    box opened, in wire order, across all of today's blocks."""
    from finger_rehab.hardware.eeg_trigger import read_marker_rows
    rows: list[dict] = []
    for raw in sorted(sessions.glob("*/*/raw.csv")):
        if raw.stat().st_mtime < since_wall:
            continue
        found, _t0 = read_marker_rows(raw)
        for r in found:
            if r.get("failed") == "1" or r.get("dropped") == "1":
                continue
            try:
                t = float(r.get("t_wire") or r.get("t_event"))
            except (TypeError, ValueError):
                continue
            rows.append({"t_wire": t, "code": int(r["code"]),
                         "name": r["name"], "block": raw.parent.name})
    rows.sort(key=lambda r: r["t_wire"])
    return rows


def compare(box: VirtualBox, markers: list[dict]) -> dict:
    """Pair each logged marker with the next byte of the same code the
    box received, in order. A byte left over is one no block logs: the
    session start and end (240, 241) and a rest or pause code sent
    between games, all in the flow band."""
    got = box.codes()
    used = [False] * len(got)
    lags: list[float] = []
    missing: list[dict] = []
    j = 0
    for m in markers:
        k = j
        while k < len(got) and not (got[k][1] == m["code"]
                                    and not used[k]):
            k += 1
        if k == len(got):
            missing.append(m)
            continue
        used[k] = True
        lags.append((got[k][0] - m["t_wire"]) * 1000.0)
        j = k + 1
    extra = [c for (t, c), u in zip(got, used) if not u]
    lags.sort()
    return {
        "bytes_received": len(box.bytes),
        "codes_received": len(got),
        "markers_logged": len(markers),
        "matched": len(lags),
        "missing": missing,
        "extra_codes": extra,
        "extra_outside_flow_band": [c for c in extra
                                    if not 240 <= c <= 249],
        "lag_ms_median": (lags[len(lags) // 2] if lags else None),
        "lag_ms_max": (lags[-1] if lags else None),
        "blocks": sorted({m["block"] for m in markers}),
    }


def print_report(rep: dict) -> bool:
    from finger_rehab.hardware.eeg_trigger import name_of
    print("\nVirtual trigger box report")
    print(f"  bytes received      {rep['bytes_received']} "
          f"({rep['codes_received']} codes, the rest are the 0 resets)")
    print(f"  markers logged      {rep['markers_logged']} in raw.csv, "
          f"{rep['matched']} found on the wire in order")
    extra = ", ".join(f"{c} {name_of(c)}" for c in rep["extra_codes"])
    print(f"  bytes no block logs {extra or 'none'}")
    if rep["lag_ms_median"] is not None:
        print(f"  logged to received  median {rep['lag_ms_median']:.2f} ms, "
              f"worst {rep['lag_ms_max']:.2f} ms")
    print(f"  blocks              {len(rep['blocks'])}: "
          + ", ".join(rep["blocks"]))
    for m in rep["missing"][:10]:
        print(f"  NOT ON THE WIRE     {m['code']} {m['name']} in {m['block']}")
    if rep["markers_logged"] == 0:
        print("  VERDICT             no game was played, so there is "
              "nothing to compare")
        return False
    ok = not rep["missing"] and not rep["extra_outside_flow_band"]
    print("  VERDICT             " + (
        "every logged marker reached the box, in order" if ok else
        "MISMATCH: read the byte log"))
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--psychopy", type=Path, default=DEFAULT_PSYCHOPY)
    ap.add_argument("--lab", type=Path, default=DEFAULT_LAB)
    ap.add_argument("--box-only", action="store_true",
                    help="run only the box and print its port")
    ap.add_argument("game_args", nargs=argparse.REMAINDER,
                    help="after --, passed to main.py")
    args = ap.parse_args()
    extra = [a for a in args.game_args if a != "--"]
    box = VirtualBox().start()
    opened_wall = time.time()
    print(f"Virtual trigger box on {box.port}")
    stamp = time.strftime("%Y%m%d_%H%M%S")
    log_path = args.lab / "sessions" / "eeg" / f"virtual_box_{stamp}.csv"
    try:
        if args.box_only:
            print("Set eeg.port to that path (Settings, EEG box, or a "
                  "config). Ctrl+C stops the box.")
            try:
                while True:
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
        else:
            exe, env = psychopy_python(args.psychopy)
            cfg = args.lab / "eeg_lab.yaml"
            if not cfg.is_file():
                cfg = args.lab / "source" / "config" / "eeg_lab.yaml"
            env["PYTHONPATH"] = os.pathsep.join(
                [str(args.lab / "python_packages")]
                + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
            env["FINGER_REHAB_DATA_ROOT"] = str(args.lab)
            source = args.lab / "source"
            print(f"Starting the lab game under {exe.parent.parent.parent.name}"
                  f" with eeg.port {box.port}. Close the game to finish.")
            subprocess.call([str(exe), str(source / "main.py"),
                             "--config", str(cfg), "--eeg-port", box.port]
                            + extra, cwd=str(source), env=env)
    finally:
        time.sleep(0.2)
        box.stop()
        box.save(log_path)
        print(f"byte log -> {log_path}")
    if not args.box_only:
        markers = logged_markers(args.lab / "sessions", opened_wall)
        return 0 if print_report(compare(box, markers)) else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
