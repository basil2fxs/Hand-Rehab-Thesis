"""CSV writers. Schema preserved from Satoru's 2025 game so old analysis tools
still read new sessions, with `hand` column added for bilateral mode (Thread 3)."""
from __future__ import annotations

import csv
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


log = logging.getLogger(__name__)


TRIAL_COLUMNS = [
    # Identity + context.
    "iso_ts",                  # wall-clock timestamp at trial close
    "block_t_s",               # seconds since block started
    "participant", "age", "hand", "block",
    # Trial identity.
    "trial", "lane",
    # Outcome.
    # time_difference_ms is the reaction time for classic / adaptive
    # (positive ms from stim to press), and the timing offset for
    # rhythm (signed ms from beat; negative = early, positive = late).
    "time_difference_ms", "early_late", "points", "feedback", "error_type",
    # Press behaviour: what the patient pressed + any wrong-finger presses.
    "keys_pressed", "correct_keys", "num_presses",
    "had_incorrect_press", "first_incorrect_ms", "first_incorrect_lane",
    # Engine state at the moment the trial closed. Empty when not
    # applicable (e.g. bpm_at_trial outside adaptive mode).
    "bpm_at_trial",            # adaptive engine BPM when stim fired
    "streak_at_trial",         # hit streak going INTO this trial
    "in_recovery",             # was adaptive recovery mode active
    "song_time_s",             # rhythm mode: position in the song
    # Peak force on the target sensor during the press window. Units
    # depend on whether a force calibration constant is present in
    # the config (`fsr.force_calibration_n_per_count`): newtons when
    # set, raw ADC counts otherwise. session.json records the active
    # unit under `block_summary.force_unit` so downstream analysis
    # knows how to interpret the column.
    "peak_force_n",
    # Force-time integral (impulse) over the press window: integral
    # of (smoothed force - baseline) dt from rising edge to falling
    # edge. Newton-seconds when a force calibration is configured,
    # ADC-count-seconds otherwise (same unit context as peak_force_n).
    # Measures total effort delivered, not just peak strength - a
    # patient who presses softly but holds doesn't look the same
    # as a sharp peak with quick release.
    "impulse_n",
    # Optional protocol phase ("pretest" / "main" / "aftertest" or
    # empty when no protocol is running). Lets a learning-effects
    # analysis split the trial CSV by phase without re-deriving
    # which block was which from the timestamps.
    "phase",
]

# Raw schema gains fsr5-fsr8 so the bilateral case fits without a new file format.
RAW_COLUMNS = [
    "iso_ts", "t_perf", "sample_idx",
    "fsr1", "fsr2", "fsr3", "fsr4",
    "fsr5", "fsr6", "fsr7", "fsr8",
    "hand", "event", "lane", "detail",
]


def _pad_vals(vals: tuple[int, ...] | list[int], n: int) -> list[int]:
    out = list(vals[:n])
    while len(out) < n:
        out.append(0)
    return out


@dataclass
class SessionPaths:
    root: Path
    trials_csv: Path
    raw_csv: Path
    metadata_json: Path

    @classmethod
    def for_session(cls, data_dir: Path,
                    participant: str) -> "SessionPaths":
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = (participant or "NA").replace("/", "_").replace(" ", "_")
        # Folder name is just {participant}_{timestamp}/. The participant
        # is set once on the title screen and reused for every block they
        # play, so multiple blocks from the same patient land in sibling
        # folders that share a common name prefix.
        base = f"{safe}_{ts}"
        cand = data_dir / base
        i = 0
        while cand.exists():
            i += 1
            cand = data_dir / f"{base}_{i}"
        cand.mkdir(parents=True, exist_ok=False)
        return cls(
            root=cand,
            trials_csv=cand / "trials.csv",
            raw_csv=cand / "raw.csv",
            metadata_json=cand / "metadata.json",
        )


class TrialLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._writer: csv.DictWriter | None = None
        self._file = None
        self._lock = threading.Lock()
        # Once close() is called, _closed flips and any further write()
        # is a no-op. Without this, a stray write after close would hit
        # _ensure() and reopen the file in mode "w", silently TRUNCATING
        # every trial already written for the block.
        self._closed = False

    def _ensure(self) -> None:
        if self._writer is None:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._file = self.path.open("w", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._file, fieldnames=TRIAL_COLUMNS)
            self._writer.writeheader()
            self._file.flush()

    def write(self, row: dict) -> None:
        with self._lock:
            if self._closed:
                # Drop late writes rather than re-opening (which would
                # truncate the file we just finalised).
                log.warning("TrialLogger write after close, row dropped")
                return
            self._ensure()
            clean = {k: row.get(k, "") for k in TRIAL_COLUMNS}
            self._writer.writerow(clean)
            self._file.flush()

    def close(self) -> None:
        with self._lock:
            self._closed = True
            if self._file:
                self._file.flush()
                self._file.close()
                self._file = None
                self._writer = None


class RawLogger:
    """Threaded raw FSR logger. Producers call queue_sample / queue_event,
    a flusher thread writes to disk so the game loop doesn't block on IO."""

    def __init__(self, path: Path, num_sensors: int = 4) -> None:
        self.path = path
        self.num_sensors = num_sensors      # 4 for one hand, 8 for both
        self._queue: deque[tuple] = deque()
        self._lock = threading.Lock()
        self._writer: csv.writer | None = None
        self._file = None
        self._idx = 0
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()

    def start(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._file = self.path.open("w", newline="", encoding="utf-8")
        self._writer = csv.writer(self._file)
        self._writer.writerow(RAW_COLUMNS)
        self._file.flush()
        self._thread = threading.Thread(target=self._flush_loop, daemon=True,
                                        name="RawLogger")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        thread_hung = False
        if self._thread:
            self._thread.join(timeout=2.0)
            if self._thread.is_alive():
                # The flusher won't exit (rare: a syscall is stuck).
                # We still must close the file - early-returning here
                # used to leak the handle AND drop everything still in
                # the queue. Best-effort drain + close, accepting that
                # we may race the zombie thread.
                thread_hung = True
                log.warning("RawLogger thread did not exit cleanly; "
                             "closing file anyway to avoid handle leak")
        with self._lock:
            if self._writer and self._queue:
                try:
                    for row in self._queue:
                        self._writer.writerow(row[1:])
                except (ValueError, OSError) as e:
                    # ValueError comes from writing to a closed file.
                    # Race with the hung thread is the only realistic
                    # cause - log it and move on so the close still runs.
                    log.warning("RawLogger final drain failed: %s", e)
                self._queue.clear()
            if self._file:
                try:
                    self._file.flush()
                    self._file.close()
                except (OSError, ValueError) as e:
                    log.warning("RawLogger close: %s", e)
                self._file = None
                self._writer = None
        if thread_hung:
            # Surface this to the engine so it knows raw data may be
            # incomplete - it can still finalise the trial CSV cleanly.
            log.warning("RawLogger stop completed despite hung thread")

    def queue_sample(self, t_perf: float, vals: tuple[int, ...],
                     hand: str = "right") -> None:
        padded = _pad_vals(vals, 8)
        with self._lock:
            self._idx += 1
            self._queue.append((
                "sample",
                datetime.now().isoformat(timespec="milliseconds"),
                f"{t_perf:.6f}",
                str(self._idx),
                *(str(v) for v in padded),
                hand, "", "", "",
            ))

    def queue_event(self, event: str, lane: int | None = None,
                    detail: str = "", t_perf: float | None = None,
                    fsr_vals: tuple[int, ...] | None = None,
                    hand: str = "right") -> None:
        if t_perf is None:
            t_perf = time.perf_counter()
        vals = _pad_vals(fsr_vals or (), 8)
        with self._lock:
            self._idx += 1
            self._queue.append((
                "event",
                datetime.now().isoformat(timespec="milliseconds"),
                f"{t_perf:.6f}",
                str(self._idx),
                *(str(v) for v in vals),
                hand,
                event,
                "" if lane is None else str(lane),
                detail,
            ))

    def _flush_loop(self) -> None:
        while not self._stop.is_set():
            self._drain()
            time.sleep(0.05)

    def _drain(self) -> None:
        with self._lock:
            if not self._writer:
                return
            batch = list(self._queue)
            self._queue.clear()
            if not batch:
                return
            for row in batch:
                # Drop the leading marker, the rest matches RAW_COLUMNS.
                self._writer.writerow(row[1:])
            if self._file:
                self._file.flush()
