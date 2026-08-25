"""CSV writers. Schema preserved from Satoru's 2025 game so old analysis tools
still read new sessions, with `hand` column added for bilateral mode (Thread 3)."""
from __future__ import annotations

import csv
import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


log = logging.getLogger(__name__)


# Hard ceiling on rows in one raw.csv. A real session samples at
# fsr.sample_rate_hz (200) and every mode caps itself at ~30 min via
# session_cap_min, so a legitimate file lands near 360k rows - this sits
# well above that and is never reached in normal use. It is a backstop:
# _pump_source drains `while True` until the source returns None, so a
# source that never empties (a stuck harness, a wedged serial reader)
# queues rows in an unbounded loop. With no ceiling that silently fills
# the disk - one such run reached 243 GB of all-zero rows before it was
# noticed. Overridable per-logger for tests.
MAX_RAW_ROWS = 20_000_000


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
    # Mirror mode fires the same finger on both hands in a single trial
    # and scores it on the LATER of the two presses (time_difference_ms),
    # because the clinical question is whether the movement was
    # synchronised. That collapses which hand did what: the row's own
    # `lane` is always the right-hand copy (1..4) and `hand` is always
    # "both", so no per-hand split was recoverable from the row. These
    # two hold each side's OWN press latency in ms from stim to press,
    # independent of the shared scored RT above. The right lane is
    # `lane`, the left lane is always `lane + 4` (mirror always pairs
    # a finger with its same-finger opposite), so no extra lane column
    # is needed to say which side each number belongs to. Empty when
    # that side never pressed (a Miss on that side) or outside mirror
    # mode, where both stay blank.
    "mirror_right_rt_ms", "mirror_left_rt_ms",
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
    # TRUE when this trial's cue + feedback played at the boosted
    # loudness (audio.loud_trial). The boost is a stimulus property,
    # so any RT analysis needs this column to control for it.
    "loud_trial",
    # Response window for this trial in ms (the RT censoring limit).
    # Varies per trial in adaptive mode (cadence x timeout_factor);
    # rhythm logs its miss_ms classify boundary here.
    "timeout_ms",
    # All-finger force over the post-stim window (metrics.
    # miss_force_window_ms): sum of each finger's peak above baseline,
    # and the per-finger breakdown as "lane:peak;..." (1-indexed lanes,
    # only fingers that rose above baseline). Same unit context as
    # peak_force_n. Empty when no FSR samples arrived in the window
    # (keyboard mode); "0.000" means samples flowed but no finger rose
    # above baseline. Feeds miss-force and individuation analyses.
    "force_window_sum",
    "force_window_peaks",
    # TRUE/FALSE whether this trial's buzzer command was successfully
    # written to the serial port; empty when the cue was disabled.
    #
    # Read this as "the host sent it", NOT "the patient felt it". The
    # firmware sends no acknowledgement for
    # STIM, so the software cannot confirm a motor actually ran, only
    # that the command left the host. FALSE therefore means a real
    # transport failure (board unplugged mid-block) and those trials
    # must not be analysed as ordinary misses. TRUE does not by itself
    # prove the patient received a cue: verify the motors physically
    # with the Settings buzzer test before a session.
    "stim_delivered",
    # Which sensory cues the patient got on this trial, as the four
    # independent cue.* switches packed into one field.
    #
    # Format: "<before>/<after>", each half being the buzzer slot then
    # the sound slot. A letter means that channel fired, "-" means it
    # was off:
    #
    #   BS/BS   everything on (the default)
    #   B-/--   buzzer cue only, no sound anywhere, no confirmation
    #   -S/-S   sound cue and sound confirmation, no buzzer
    #   --/--   nothing but the screen
    #
    # So position 1 is cue.buzz_before, 2 is cue.sound_before, 4 is
    # cue.buzz_after and 5 is cue.sound_after. Sixteen values are
    # possible and all of them are valid. Replaces the older cue_mode
    # column, which only had "both" / "visual" / "vibration".
    #
    # Set in Settings and constant for a block, but logged per trial so
    # blocks run under different settings can be pooled and split again
    # without going back to the config snapshot.
    "cue_flags",
    # What was shown on this trial beyond a lane highlight. Empty for
    # modes that only light a finger. Syllables mode records the word;
    # chords mode records the chord as lane numbers, e.g. "1+3+4".
    "stimulus",
    # TRUE when this trial's lane came from the repeating sequence,
    # FALSE when it came from a random probe block, empty outside
    # pattern mode. The whole point of pattern mode is the difference
    # between those two labels: sequence learning is random-trial RT
    # minus repeating-trial RT, and without this column the two kinds
    # of trial are indistinguishable afterwards.
    "pattern_trial",
    # TRUE when the gameplay screen highlighted the target finger on
    # this trial (cue.show_target), FALSE when the tile stayed neutral
    # and the finger had to be found from the buzzer alone. Separate
    # from cue_flags because the screen is not one of the four cue
    # channels: it is there in every trial either way, the only
    # question is whether it names the finger. FALSE with a "B-" in
    # cue_flags is the tactile-only condition.
    "cue_target_shown",
    # ---- continuous-force / stimulus-suite trial description ---------
    # The next four columns exist so a trial whose stimulus is a whole
    # trajectory or a timed pulse train, not a single lane highlight,
    # can be rebuilt EXACTLY offline. The threshold modes leave all
    # four empty. The rule for the continuous modes is: waveform +
    # waveform_params + waveform_seed must be sufficient to regenerate
    # the target the patient saw sample for sample, and segment_times
    # must let the notebook cut the raw 200 Hz trace into the scored
    # windows without re-deriving them from screen timing.
    #
    # What the target trajectory was: a short type name such as
    # "plateau", "ramp", "sine", "sum_of_sines", "prbs", "hold",
    # "reproduce", or a stimulus descriptor like "buzz" for pulse
    # trials. Empty outside the continuous / stimulus modes.
    "waveform",
    # The numbers that pin the trajectory down, packed as
    # "key=value;key=value" via pack_waveform_params (sorted keys, so
    # two rows with the same parameters produce the same string).
    # Percent values are percent of the session max press
    # (calibration max_press), never raw counts. Includes
    # max_press_counts itself when force targets are in play, so a
    # mid-session re-probe cannot silently change what a percent
    # meant.
    "waveform_params",
    # Seed for any pseudorandom element of the trajectory. Empty when
    # the waveform is fully determined by its parameters.
    "waveform_seed",
    # Per-segment timestamps as "name:start:end;..." (pack_segments),
    # start/end in raw-stream t_perf seconds, 6 decimal places. Same
    # clock as raw.csv's t_perf column, so the notebook can slice the
    # sample stream between these bounds directly. The engine also
    # writes segment_start / segment_end event rows into raw.csv
    # around each scored segment as a cross-check.
    "segment_times",
]

# Raw schema gains fsr5-fsr8 so the bilateral case fits without a new file format.
RAW_COLUMNS = [
    "iso_ts", "t_perf", "sample_idx",
    "fsr1", "fsr2", "fsr3", "fsr4",
    "fsr5", "fsr6", "fsr7", "fsr8",
    "hand", "event", "lane", "detail",
]


def pack_waveform_params(params: dict) -> str:
    """One CSV cell for a trial's waveform parameters.

    "key=value;key=value" with keys sorted, floats trimmed to 6
    significant digits. Sorted so the string is a stable fingerprint:
    two trials run under the same parameters pack to the same cell,
    which lets the notebook group trials by condition with a plain
    equality test instead of parsing every row first. Keys and values
    must not contain "=" or ";" (they are the field separators); a
    value that does raises here, at logging time, rather than
    producing a cell the notebook mis-splits weeks later.
    """
    parts = []
    for key in sorted(params):
        val = params[key]
        if isinstance(val, float):
            text = f"{val:.6g}"
        else:
            text = str(val)
        if "=" in str(key) or ";" in str(key) or "=" in text or ";" in text:
            raise ValueError(
                f"waveform param {key!r}={text!r} contains a separator")
        parts.append(f"{key}={text}")
    return ";".join(parts)


def parse_waveform_params(cell: str) -> dict:
    """Inverse of pack_waveform_params, values as float where they
    parse and string otherwise. Lives here so the round-trip can be
    pinned by a test; the notebook carries its own copy because it
    travels without this package."""
    out: dict = {}
    for part in (cell or "").split(";"):
        if not part or "=" not in part:
            continue
        key, _, text = part.partition("=")
        try:
            out[key] = float(text)
        except ValueError:
            out[key] = text
    return out


def pack_segments(segments: list[tuple[str, float, float]]) -> str:
    """One CSV cell for a trial's scored segments.

    "name:start:end;..." with start/end in raw-stream t_perf seconds
    at 6 decimal places (microsecond resolution, matching the raw
    logger's own t_perf formatting). Segment names must not contain
    ":" or ";". Order is preserved: segments are logged in the order
    they ran, which is itself information for ramp trials.
    """
    parts = []
    for name, start, end in segments:
        name = str(name)
        if ":" in name or ";" in name:
            raise ValueError(f"segment name {name!r} contains a separator")
        parts.append(f"{name}:{float(start):.6f}:{float(end):.6f}")
    return ";".join(parts)


@dataclass
class ContinuousTrialLog:
    """What a continuous-force or stimulus-suite trial must hand to
    log_trial so the notebook can rebuild it. waveform names the
    trajectory or stimulus type, params pins its numbers (percent
    values are percent of the session max press; include
    max_press_counts so a mid-session re-probe stays visible), seed
    covers any pseudorandom element, and segments are the scored
    windows in raw-stream t_perf seconds."""

    waveform: str
    params: dict = field(default_factory=dict)
    seed: int | None = None
    segments: list = field(default_factory=list)


def parse_segments(cell: str) -> list[tuple[str, float, float]]:
    """Inverse of pack_segments. Malformed entries are dropped rather
    than raising: this side runs on data read back from disk, where a
    truncated row should cost one trial, not the whole analysis."""
    out: list[tuple[str, float, float]] = []
    for part in (cell or "").split(";"):
        bits = part.split(":")
        if len(bits) != 3:
            continue
        try:
            out.append((bits[0], float(bits[1]), float(bits[2])))
        except ValueError:
            continue
    return out


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
                    participant: str, mode: str = "") -> "SessionPaths":
        now = datetime.now()
        day = now.strftime("%Y-%m-%d")
        ts = now.strftime("%H%M%S")
        safe = (participant or "NA").replace("/", "_").replace(" ", "_")
        # Layout: sessions/YYYY-MM-DD/{participant}_{HHMMSS}_{mode}/.
        # Grouping by day keeps a long trial campaign navigable: open
        # one date folder and every block recorded that day is there,
        # sorted by participant then time. The mode suffix says what
        # each block was without opening metadata.json. Full timestamps
        # still live inside (metadata.json, trials.csv iso_ts), so a
        # folder copied out of its day directory stays traceable.
        base = f"{safe}_{ts}"
        mode_safe = (mode or "").strip().replace("/", "_").replace(" ", "_")
        if mode_safe:
            base = f"{base}_{mode_safe}"
        day_dir = data_dir / day
        cand = day_dir / base
        i = 0
        while cand.exists():
            i += 1
            cand = day_dir / f"{base}_{i}"
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

    def __init__(self, path: Path, num_sensors: int = 4,
                 max_rows: int = MAX_RAW_ROWS) -> None:
        self.path = path
        self.num_sensors = num_sensors      # 4 for one hand, 8 for both
        self.max_rows = max_rows
        self._capped = False
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

    def _cap_reached(self) -> bool:
        """True once this file has hit its row ceiling.

        Caller must already hold _lock. Logs once on the transition and
        stays quiet after: a runaway producer reaches this at loop speed,
        so logging every call would just trade a huge CSV for a huge log.
        """
        if self._idx < self.max_rows:
            return False
        if not self._capped:
            self._capped = True
            log.error(
                "RawLogger hit its %d-row ceiling for %s and is dropping "
                "further rows. The sample producer is almost certainly "
                "stuck draining a source that never returns None.",
                self.max_rows, self.path)
        return True

    def queue_sample(self, t_perf: float, vals: tuple[int, ...],
                     hand: str = "right") -> None:
        padded = _pad_vals(vals, 8)
        with self._lock:
            if self._cap_reached():
                return
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
            if self._cap_reached():
                return
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
