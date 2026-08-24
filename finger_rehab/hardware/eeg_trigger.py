"""EEG trigger markers: the single-byte code map and the writer that
puts codes on the wire with a vendor-safe pulse shape.

The amplifier records a trigger channel next to the EEG. Every event
the analysis wants to epoch on (stimulus onsets, presses, block
boundaries) gets one byte here, held high for eeg.pulse_ms and then
reset to 0, so the EEG record can be cut around the game's events.

CODES below is the single source of truth for the map. The full design
rationale lives in the EEG integration spec (band layout, cue-condition
coding, response correctness split, collision and failure policy).

WARNING - old map conflict. This module replaces finger_rehab/hardware/eeg.py
(Aiden's prototype), whose map CONFLICTED with the lab convention:
the prototype used 30 = miss/timeout and 11-18 = stimulus per lane,
while Welber's pipeline epochs on 30 = STIMULUS ONSET. Nothing in this
repository ever called the prototype (zero engine call sites, no
config block), so the map was replaced outright and 30 is a stimulus
onset again. OPEN QUESTION for Welber and Aiden: did any analysis
script outside this repo ever consume the prototype codes (30 = miss,
11-18 stim, 21-28 response)? If one did, its recordings must not be
pooled with recordings made under this map.

Wire protocol, in short:
- bytes([code]), one raw byte. Never chr()/UTF-8: any code over 127
  would become two bytes, and every response, feedback, block and
  session code sits over 127.
- Hold the code for pulse_ms measured on time.perf_counter, then write
  0. The old lab script held by frame counting and actually delivered
  1-4 ms pulses; a 250 Hz amplifier needs at least 8 ms to be sure of
  two samples, so 10 ms is the default.
- A new code only goes out after the line has sat at 0 for gap_ms.
  Colliding events queue by priority (stimulus > response > feedback >
  preparation > boundaries/control) and every emission logs its actual
  wire time, so a delayed marker is late but never wrong.
- Write failures degrade, never crash: after 3 consecutive failures
  the port is reopened once; if that fails the session keeps running,
  markers keep being logged with a failed flag, and the session is
  recorded as EEG-degraded.
"""
from __future__ import annotations

import heapq
import logging
import time
from dataclasses import dataclass


log = logging.getLogger(__name__)


try:
    import serial
    _HAVE_SERIAL = True
except ImportError:
    serial = None   # type: ignore[assignment]
    _HAVE_SERIAL = False


# Bumped whenever the map changes, logged into metadata.json so a
# recording can always be decoded with the map it was made under.
CODES_VERSION = "1.0"

# 0 is the idle line, written after every pulse and in every shutdown
# path. It never labels an event, so it lives outside CODES.
RESET = 0

# The marker map. Base codes carry an additive payload:
#   stim_visual (30)      + 1 tone + 2 buzzer + 4 target-not-shown
#   resp_*_base           + lane (0-7)
#   block_start/end_base  + mode id (MODE_IDS)
# 30 stays a pure stimulus-onset code (screen highlight only) so the
# lab's standing habit of "epoch on 30" still finds stimuli.
CODES: dict[str, int] = {
    # Preparation band (20-29).
    "prep_countdown": 20,        # block GET READY onset
    "prep_foreperiod": 21,       # reaction: wait armed (CNV S1)
    "prep_catch_onset": 25,      # reaction: virtual go on a catch trial
    # Stimulus band (30-39), cue condition in the byte.
    "stim_visual": 30,           # screen highlight only
    "stim_visual_tone": 31,
    "stim_visual_buzz": 32,
    "stim_visual_buzz_tone": 33,  # the shipping default cue mix
    "stim_uncued": 34,           # nothing names the finger
    "stim_tone": 35,
    "stim_buzz": 36,             # tactile isolation condition
    "stim_buzz_tone": 37,
    "stim_buzz_hunt": 38,        # buzz IS the stimulus (perception trials)
    # Pattern-mode stimulus band (40-49), sequence status in the byte.
    "stim_pattern_sequence": 40,
    "stim_pattern_random": 41,
    # Response band (100-131), correctness in the byte, lane added to
    # the bases because hand identity is what the LRP is made of.
    #
    # Buzz Hunt is STIM-MARKER-ONLY for scored trials: its closers log
    # through the continuous-trial path, which sends no response or
    # feedback markers, so 38 (stim_buzz_hunt) is the only per-trial
    # marker a scored localisation/span/gap trial emits. Only its
    # ERROR events (catch false alarms, distractor anticipations) hit
    # the 120 band via log_reaction_event. An analyst hunting for
    # missing 100-band responses in a buzz_hunt block is not looking
    # at a fault; there are none by design.
    "resp_correct_base": 100,    # + lane pressed
    "resp_wrong_base": 110,      # + lane actually pressed
    "resp_anticipation_base": 120,  # + lane (false start / sub-cut press)
    "resp_timeout": 130,         # deadline expired, no press: never
                                 # averaged response-locked
    "resp_idle": 131,            # press while no trial active
    # Feedback band (140-149), only under eeg.feedback_markers.
    "feedback_positive": 140,
    "feedback_negative": 141,
    "feedback_neutral": 142,     # reserved for neutral readouts (FRN control)
    # Block boundaries (200-231), mode id added.
    "block_start_base": 200,
    "block_abandoned": 219,      # keeps the old eeg.py abandoned concept
    "block_end_base": 220,
    # Session and flow (240-249).
    "session_start": 240,
    "session_end": 241,
    "pause": 242,
    "resume": 243,
    "rest_start": 244,
    "rest_end": 245,
}

# Mode ids for the block-boundary bands. The engine's block names are
# the keys. syllables_words currently runs under the "syllables" block
# name in the engine, so id 11 is reserved but unused until that mode
# gets its own block name.
MODE_IDS: dict[str, int] = {
    "reaction": 0,
    "classic": 1,
    "adaptive": 2,
    "rhythm": 3,
    "mirror": 4,
    "pattern": 5,
    "chords": 6,
    "syllables": 7,
    "force_pilot": 8,
    "lighthouse": 9,
    "buzz_hunt": 10,
    "syllables_words": 11,
}

# Documented bands, keyed by the CODES-name prefix that must sit inside
# each. The contract test walks this table.
BANDS: dict[str, tuple[int, int]] = {
    "prep_": (20, 29),
    "stim_pattern_": (40, 49),
    "stim_": (30, 39),
    "resp_": (100, 131),
    "feedback_": (140, 149),
    "block_": (200, 231),
    "session_": (240, 249),
    "pause": (240, 249),
    "resume": (240, 249),
    "rest_": (240, 249),
}


def stim_code(sound_before: bool, buzz_before: bool,
              show_target: bool) -> int:
    """Stimulus code for the cue condition in force.

    The offsets map straight onto the cue_flags switches so the byte
    says which sensory channels announced the stimulus. Visual,
    auditory and tactile stimuli produce different ERPs and must never
    be pooled, which is why the condition rides the byte and the lane
    rides the log row instead.
    """
    return (CODES["stim_visual"]
            + (1 if sound_before else 0)
            + (2 if buzz_before else 0)
            + (4 if not show_target else 0))


def response_code(kind: str, lane: int) -> int | None:
    """Response code for a classified press.

    kind is correct / wrong / anticipation; lane is the finger that
    actually pressed (0-7). Returns None for a lane outside the lane
    space rather than emitting a byte from a neighbouring band.
    """
    base = {
        "correct": CODES["resp_correct_base"],
        "wrong": CODES["resp_wrong_base"],
        "anticipation": CODES["resp_anticipation_base"],
    }.get(kind)
    if base is None or not 0 <= int(lane) <= 7:
        return None
    return base + int(lane)


def block_code(mode_name: str, edge: str) -> int | None:
    """Block-boundary code for a mode, or None for an unknown mode
    name so a future mode cannot silently emit another mode's byte."""
    if edge == "abandoned":
        return CODES["block_abandoned"]
    mode_id = MODE_IDS.get(mode_name)
    if mode_id is None:
        return None
    base = (CODES["block_start_base"] if edge == "start"
            else CODES["block_end_base"])
    return base + mode_id


def priority_for(code: int) -> int:
    """Collision priority; lower emits first when markers queue.

    Stimulus onsets carry the tightest timing requirement, responses
    next; feedback, preparation and boundaries can afford a frame or
    two of delay because their analyses are either coarse or windowed
    away from the delayed edge.
    """
    if 30 <= code <= 49:
        return 0
    if 100 <= code <= 131:
        return 1
    if 140 <= code <= 149:
        return 2
    if 20 <= code <= 29:
        return 3
    return 4


@dataclass
class MarkerEmission:
    """One emission attempt, exactly what the raw.csv eeg row records.

    t_event is the perf_counter time of the physical event (force
    crossing sample time, flip return, state transition); t_wire is
    perf_counter just after serial.write returned, None when the write
    failed or the marker was dropped. Both share the clock the raw
    sample stream uses, which is what lets the offline cross-check
    compare inter-marker intervals against the amplifier's trigger
    channel.
    """

    code: int
    lane: int | None
    t_event: float
    t_wire: float | None
    delayed: bool
    failed: bool
    dropped: bool = False


def format_detail(rec: MarkerEmission) -> str:
    """The raw.csv detail cell for an emission. Fixed field order so
    the notebook can split on ';' and '=' without a parser."""
    t_wire = "" if rec.t_wire is None else f"{rec.t_wire:.6f}"
    return (f"code={rec.code};t_event={rec.t_event:.6f};"
            f"t_wire={t_wire};delayed={1 if rec.delayed else 0};"
            f"failed={1 if rec.failed else 0};"
            f"dropped={1 if rec.dropped else 0}")


class TriggerBackend:
    """Interface the writer drives. open() returns readiness,
    write_code() returns success, close() never raises out."""

    name = "none"

    def open(self) -> bool:
        return False

    def write_code(self, code: int) -> bool:
        raise NotImplementedError

    def reopen(self) -> bool:
        return False

    def close(self) -> None:
        pass


class SerialBackend(TriggerBackend):
    """The real trigger box on a serial port."""

    name = "serial"

    def __init__(self, port: str, baud: int = 115200) -> None:
        self.port = port
        self.baud = baud
        self._serial = None

    @property
    def is_open(self) -> bool:
        return bool(self._serial and self._serial.is_open)

    def open(self) -> bool:
        if not _HAVE_SERIAL:
            log.warning("pyserial not available; EEG trigger port %s "
                        "cannot open", self.port)
            return False
        if self.is_open:
            return True
        try:
            self._serial = serial.Serial(
                self.port, self.baud,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0,
                # A yanked cable or wedged box must not hang the frame
                # loop: any single write is capped at 0.5 s.
                write_timeout=0.5,
            )
            log.info("EEG trigger on %s @ %d", self.port, self.baud)
            return True
        except Exception as e:
            log.warning("Could not open EEG trigger port %s: %s",
                        self.port, e)
            self._serial = None
            return False

    def write_code(self, code: int) -> bool:
        if not self.is_open:
            return False
        try:
            # bytes([code]) is the whole protocol: exactly one raw
            # byte. chr()-based encodings would emit two bytes for any
            # code over 127, which covers every response and boundary
            # code in the map.
            self._serial.write(bytes([code & 0xFF]))
            return True
        except Exception as e:
            log.warning("EEG trigger write failed (code %d): %s", code, e)
            return False

    def reopen(self) -> bool:
        self.close()
        return self.open()

    def close(self) -> None:
        try:
            if self._serial and self._serial.is_open:
                self._serial.close()
        except Exception as e:
            log.debug("EEG trigger close noise: %s", e)
        self._serial = None


class DummyBackend(TriggerBackend):
    """No-hardware backend that keeps every code instead of discarding
    it. A development or demo session still produces a checkable
    marker record (each write is kept here AND flows through the
    normal raw.csv logging path), which the old DummySerial never did.
    """

    name = "dummy"

    def __init__(self) -> None:
        self.written: list[tuple[float, int]] = []

    def open(self) -> bool:
        return True

    def write_code(self, code: int) -> bool:
        self.written.append((time.perf_counter(), code & 0xFF))
        return True

    def reopen(self) -> bool:
        return True


class MarkerWriter:
    """Owns the pulse shape, the inter-marker gap, the collision queue
    and the failure policy. The engine calls send() at event sites and
    tick() once per frame; everything else is internal.

    Built-in silence: when disabled (eeg.enabled false) or without a
    backend, send()/tick()/close() are no-ops the engine never has to
    check, so a non-EEG session pays one attribute test per call and
    writes zero rows.
    """

    def __init__(self, backend: TriggerBackend | None = None,
                 enabled: bool = False,
                 pulse_ms: float = 10.0, gap_ms: float = 10.0,
                 on_emit=None, clock=time.perf_counter,
                 max_queue: int = 3) -> None:
        self.backend = backend
        self.enabled = bool(enabled)
        self.pulse_s = float(pulse_ms) / 1000.0
        self.gap_s = float(gap_ms) / 1000.0
        self.on_emit = on_emit
        self.max_queue = int(max_queue)
        self._clock = clock
        # Line state. _low_since None means nothing was ever sent, so
        # the first marker never waits out a gap that never started.
        self._line = RESET
        self._high_until: float | None = None
        self._low_since: float | None = None
        # Priority queue of (priority, seq, code, lane, t_event). seq
        # keeps FIFO order inside a priority class.
        self._queue: list[tuple[int, int, int, int | None, float]] = []
        self._seq = 0
        # Failure policy state (spec: 3 consecutive failures, one
        # reopen, then degrade and keep logging).
        self.failure_count = 0
        self._consecutive_failures = 0
        self._reopen_tried = False
        self.degraded = False
        self.first_failure_t: float | None = None
        self.delayed_count = 0
        self.dropped_count = 0

    @property
    def active(self) -> bool:
        return self.enabled and self.backend is not None

    # ---- event side --------------------------------------------------------
    def send(self, code: int, lane: int | None = None,
             t_event: float | None = None) -> None:
        """Queue or wire one marker. t_event is the perf_counter time
        of the physical event; default is now, which is right for
        state transitions and wrong for anything with a better
        timestamp (force crossings, flips), so those call sites pass
        their own."""
        if not self.active:
            return
        now = self._clock()
        if t_event is None:
            t_event = now
        if self._line == RESET and not self._queue and self._gap_ok(now):
            self._wire(int(code), lane, t_event, delayed=False)
            return
        heapq.heappush(self._queue, (priority_for(int(code)), self._seq,
                                     int(code), lane, t_event))
        self._seq += 1
        if len(self._queue) > self.max_queue:
            # Shed the lowest-priority entry (largest tuple: worst
            # priority, then newest) and say so in the log. At the
            # game's event rates this should never fire; the
            # validation report states how often it did.
            worst = max(self._queue)
            self._queue.remove(worst)
            heapq.heapify(self._queue)
            self.dropped_count += 1
            _, _, w_code, w_lane, w_t_event = worst
            self._emit(MarkerEmission(code=w_code, lane=w_lane,
                                      t_event=w_t_event, t_wire=None,
                                      delayed=True, failed=False,
                                      dropped=True))

    # ---- frame side --------------------------------------------------------
    def tick(self) -> None:
        """Once per frame: drop the line back to 0 when the pulse has
        run its width, and release the next queued marker once the
        gap rule allows."""
        if not self.active:
            return
        now = self._clock()
        if (self._line != RESET and self._high_until is not None
                and now >= self._high_until):
            self._write_reset()
            now = self._clock()
        if self._queue and self._line == RESET and self._gap_ok(now):
            _, _, code, lane, t_event = heapq.heappop(self._queue)
            self._wire(code, lane, t_event, delayed=True)

    def drain(self, timeout_s: float = 0.25, sleep=time.sleep) -> None:
        """Pump the protocol off the frame loop until the queue is
        empty and the line is back at 0, or the timeout passes. Used
        at block and session end so queued markers land before the
        loggers close; never called from the per-frame path."""
        if not self.active:
            return
        deadline = self._clock() + float(timeout_s)
        while ((self._queue or self._line != RESET)
               and self._clock() < deadline):
            self.tick()
            sleep(0.001)

    def close(self) -> None:
        """Reset the line and release the port. Every shutdown path
        must land here so the trigger lines cannot stay latched high,
        which the old lab script could do on escape."""
        backend = self.backend
        self.backend = None
        self.enabled = False
        self._queue.clear()
        if backend is None:
            return
        try:
            backend.write_code(RESET)
        except Exception as e:
            log.debug("EEG final reset failed: %s", e)
        try:
            backend.close()
        except Exception as e:
            log.debug("EEG backend close failed: %s", e)

    def status(self) -> dict:
        """Snapshot for metadata.json: enough to decode the recording
        and judge the marker channel's health."""
        return {
            "backend": self.backend.name if self.backend else "none",
            "port": getattr(self.backend, "port", None),
            "enabled": self.enabled,
            "pulse_ms": round(self.pulse_s * 1000.0, 3),
            "gap_ms": round(self.gap_s * 1000.0, 3),
            "codes_version": CODES_VERSION,
            "failure_count": self.failure_count,
            "delayed_count": self.delayed_count,
            "dropped_count": self.dropped_count,
            "degraded": self.degraded,
            "first_failure_t": self.first_failure_t,
        }

    # ---- internals ---------------------------------------------------------
    def _gap_ok(self, now: float) -> bool:
        return (self._low_since is None
                or (now - self._low_since) >= self.gap_s)

    def _write_reset(self) -> None:
        try:
            self.backend.write_code(RESET)
        except Exception as e:
            log.debug("EEG reset write failed: %s", e)
        self._line = RESET
        self._high_until = None
        self._low_since = self._clock()

    def _wire(self, code: int, lane: int | None, t_event: float,
              delayed: bool) -> None:
        failed = False
        t_wire: float | None = None
        if self.degraded:
            # Past the point of no return: no more writes (each one
            # would eat the 0.5 s write timeout inside the frame
            # loop), but every intended marker still reaches the log
            # so the analysis knows exactly which trials lost their
            # bytes.
            failed = True
            self.failure_count += 1
        else:
            try:
                ok = self.backend.write_code(code)
            except Exception as e:
                log.warning("EEG marker %d raised: %s", code, e)
                ok = False
            if ok:
                t_wire = self._clock()
                self._consecutive_failures = 0
                self._line = code
                self._high_until = t_wire + self.pulse_s
            else:
                failed = True
                self.failure_count += 1
                self._consecutive_failures += 1
                if self.first_failure_t is None:
                    self.first_failure_t = self._clock()
                self._maybe_reopen()
        if delayed and not failed:
            self.delayed_count += 1
        self._emit(MarkerEmission(code=code, lane=lane, t_event=t_event,
                                  t_wire=t_wire, delayed=delayed,
                                  failed=failed))

    def _maybe_reopen(self) -> None:
        if self._consecutive_failures < 3 or self.degraded:
            return
        if self._reopen_tried:
            # The one reopen has been spent; a repeat failure run means
            # the port is gone for good this session.
            self.degraded = True
            log.warning("EEG markers degraded: repeated write failures "
                        "after the single reopen attempt")
            return
        self._reopen_tried = True
        ok = False
        try:
            ok = self.backend.reopen()
        except Exception as e:
            log.warning("EEG trigger reopen raised: %s", e)
        if ok:
            self._consecutive_failures = 0
            log.info("EEG trigger port reopened after write failures")
        else:
            self.degraded = True
            log.warning("EEG markers degraded: reopen failed; the "
                        "behavioural session keeps running")

    def _emit(self, rec: MarkerEmission) -> None:
        if self.on_emit is None:
            return
        try:
            self.on_emit(rec)
        except Exception as e:
            # The logging side must never take the wire side down.
            log.warning("EEG emission log failed: %s", e)


class TriggerPortError(RuntimeError):
    """Lab mode refusing to start without its trigger box."""


def writer_from_config(get, on_emit=None) -> MarkerWriter:
    """Build the writer the way the config asks.

    `get` is a Config.get-style callable. eeg.enabled false returns an
    inert writer. Enabled with an openable port runs the real backend.
    Enabled without one splits on eeg.require_port, mirroring the old
    lab script's modes: require_port true (the lab preset) raises
    TriggerPortError so the session refuses to start silently
    unmarked; false falls back to the DummyBackend and says so at
    startup, never silently.
    """
    enabled = bool(get("eeg.enabled", False))
    pulse_ms = float(get("eeg.pulse_ms", 10))
    gap_ms = float(get("eeg.gap_ms", 10))
    if not enabled:
        return MarkerWriter(backend=None, enabled=False,
                            pulse_ms=pulse_ms, gap_ms=gap_ms,
                            on_emit=on_emit)
    port = get("eeg.port", None)
    baud = int(get("eeg.baud", 115200))
    require = bool(get("eeg.require_port", False))
    backend: TriggerBackend | None = None
    reason = "no eeg.port configured"
    if port:
        candidate = SerialBackend(str(port), baud)
        if candidate.open():
            backend = candidate
        else:
            reason = f"could not open eeg.port {port}"
    if backend is None:
        if require:
            raise TriggerPortError(
                f"EEG lab mode needs its trigger box: {reason}. "
                "Plug the box in and check eeg.port, or run the "
                "normal game instead of the EEG Lab entry.")
        backend = DummyBackend()
        log.warning("EEG markers live on the DummyBackend (%s); codes "
                    "are logged, nothing reaches an amplifier", reason)
    else:
        log.info("EEG markers live on %s", port)
    return MarkerWriter(backend=backend, enabled=True,
                        pulse_ms=pulse_ms, gap_ms=gap_ms,
                        on_emit=on_emit)
