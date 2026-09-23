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
  Colliding events queue by priority (session and block starts >
  stimulus > response > feedback > preparation > closing boundaries and
  control) and every emission logs its actual wire time, so a delayed
  marker is late but never wrong. Openers go first so nothing that
  belongs inside a block can reach the wire before the block does.
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
# 1.1: echo mode id 12 added, so block bytes 212 and 232 now occur;
# every code that existed under 1.0 is unchanged.
# 1.2: prep_buzz_lead 22 added for rhythm's leading buzz, and a beat
# whose buzz went out earlier carries the stimulus code WITHOUT the
# buzzer bit (33 becomes 31). No existing code changed meaning.
# 1.3: the choice-set band 50-59 added for syllables' option sets
# (50 first attempt, 51 returned word). Nothing else changed: the
# syllables model roll still carries an ordinary 30-band code.
# 1.4: prep_run_start 23 and prep_segment_edge 24 added for Force
# Pilot, whose runs had no per-run byte at all. Every raw.csv eeg row
# also carries name=<code name> from this version. No existing code
# changed meaning.
CODES_VERSION = "1.4"

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
    # Rhythm: the tactile pulse sent AHEAD of the beat (rhythm.tactile_mode
    # lead, or any non-zero motor rise compensation). Marked at the
    # STIM command, so the felt vibration follows it by the buzzer
    # latency recorded in metadata.json (eeg.marker_offsets_ms). The
    # beat's own stimulus code then drops the buzzer bit: the
    # somatosensory ERP locks here, the auditory and visual ERPs lock
    # to the 30-band, and the two are never pooled.
    "prep_buzz_lead": 22,
    # Force Pilot: a run has no stimulus onset, so its first scored
    # frame is marked here and every section boundary after it (the
    # plateau-to-ramp edges the notebook cuts on, and the run's end)
    # gets 24. Written from the mode with the model-clock time the
    # trial row's segment_times also carries, so the two agree.
    "prep_run_start": 23,
    "prep_segment_edge": 24,
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
    # Choice-set band (50-59): four written options fall over four
    # fingers and NOTHING names the target finger, so these are not
    # cued stimuli and must never be pooled with the 30-band. The byte
    # says whether the word is on its first attempt or has come back
    # after a miss, because a returned word is a second retrieval of
    # material the child has already met.
    "stim_choice_set": 50,
    "stim_choice_set_return": 51,
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
# gets its own block name. Ids can grow to 18 before the start band
# reaches the reserved 219; see the block_ band note below.
#
# Id 9 belonged to Lighthouse, retired in September 2026. It stays
# reserved so no later mode inherits 209 / 229 and a recording made
# under the old map can never be confused with a new mode's block.
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
    "buzz_hunt": 10,
    "syllables_words": 11,
    "echo": 12,
}

# Ids that once belonged to a mode and must never be reissued. The
# contract test checks no live mode sits on one of these.
RETIRED_MODE_IDS: dict[str, int] = {
    "lighthouse": 9,
}

# Documented bands, keyed by the CODES-name prefix that must sit inside
# each. The contract test walks this table.
BANDS: dict[str, tuple[int, int]] = {
    "prep_": (20, 29),
    # Both of these sit before the general "stim_" row on purpose: the
    # table is walked in order and the first matching prefix wins.
    "stim_pattern_": (40, 49),
    "stim_choice_": (50, 59),
    "stim_": (30, 39),
    "resp_": (100, 131),
    "feedback_": (140, 149),
    # Widened from 231 when echo took id 12: block-end 220 + 12 = 232.
    # Start codes stay under the reserved 219 (block_abandoned) until
    # id 19, and end codes stay clear of the session band (240) until
    # id 20, so ids up to 18 fit without another change.
    "block_": (200, 238),
    "session_": (240, 249),
    "pause": (240, 249),
    "resume": (240, 249),
    "rest_": (240, 249),
}

# Band label per code range, for the exported code table and the
# events file. Same ranges as BANDS, keyed the way an analyst reads
# them rather than by CODES prefix.
BAND_LABELS: tuple[tuple[int, int, str], ...] = (
    (20, 29, "prep"),
    (30, 39, "stim"),
    (40, 49, "stim_pattern"),
    (50, 59, "stim_choice"),
    (100, 131, "resp"),
    (140, 149, "feedback"),
    (200, 238, "block"),
    (240, 249, "flow"),
)

# What each code locks to and what it means, for the code table shipped
# with every session (markers_codes.csv). Keyed by CODES name; the
# additive codes (responses, block edges) are described once on their
# base. locks_to says which physical moment t_event is; offset_key
# names the marker_offsets_ms entry that shifts a byte-locked epoch
# onto the stimulus. The notes carry the per-mode rules an epoching
# script must know and cannot read off the byte.
CODE_NOTES: dict[str, tuple[str, str, str, str]] = {
    "prep_countdown": (
        "state", "", "GET READY card shown at block start",
        "Sent back to back with the block-start byte; the two can "
        "leave in either order when the line is busy, so sort by "
        "t_event, not wire order."),
    "prep_foreperiod": (
        "state", "", "reaction: ready cue shown, wait armed (CNV S1)",
        "Fixed 2.5 s ahead of the go in the lab preset."),
    "prep_buzz_lead": (
        "STIM command", "prep_buzz_lead",
        "rhythm: tactile pulse sent ahead of the beat",
        "The beat's own byte then drops the buzzer bit (31, not 33)."),
    "prep_run_start": (
        "first scored frame", "",
        "force_pilot: tracking run starts",
        "One per run, one trials.csv row per run. No stimulus or "
        "response byte exists for a run: a corridor is continuous."),
    "prep_segment_edge": (
        "model clock", "",
        "force_pilot: section boundary inside a run, including its end",
        "Same times as the row's segment_times column."),
    "prep_catch_onset": (
        "state", "", "reaction: virtual go on a catch trial",
        "No stimulus followed; a press after it is a 120-band byte."),
    "stim_visual": (
        "flip", "stim_visual", "cue shown, screen highlight only",
        "30-37 code the cue mix in the byte: +1 tone, +2 buzzer, "
        "+4 target not shown. Lane is on the raw.csv row."),
    "stim_visual_tone": ("flip", "stim_visual", "cue: screen and tone", ""),
    "stim_visual_buzz": (
        "flip", "stim_buzz", "cue: screen and buzzer",
        "The STIM command left before the flip; felt vibration is "
        "buzzer_ms after the command."),
    "stim_visual_buzz_tone": (
        "flip", "stim_buzz", "cue: screen, buzzer and tone (default mix)",
        "Chords: one byte per chord on its lowest lane, never per "
        "finger. Syllables: also the model roll, one per syllable, "
        "no trials.csv row. Echo: one per playback item. Mirror: one "
        "per pair. The byte says which cues were configured, not "
        "that the motor ran: join stim_delivered from trials.csv."),
    "stim_uncued": ("flip", "stim_visual", "cue: nothing names the finger", ""),
    "stim_tone": ("flip", "stim_tone", "cue: tone only", ""),
    "stim_buzz": ("flip", "stim_buzz", "cue: buzzer only", ""),
    "stim_buzz_tone": ("flip", "stim_buzz", "cue: buzzer and tone", ""),
    "stim_buzz_hunt": (
        "pulse_motor command", "stim_buzz_hunt",
        "buzz_hunt: a pulse the participant must locate",
        "One byte per trial, at the FIRST pulse of its train: a span "
        "or gap row has more pulse_motor raw events than 38s, and the "
        "later pulses of the train are only in raw.csv. Scored trials "
        "carry no response byte; only false alarms reach the 120 "
        "band. Catch trials write no 38 at all."),
    "stim_pattern_sequence": (
        "flip", "stim_visual", "pattern: item from the trained sequence", ""),
    "stim_pattern_random": (
        "flip", "stim_visual", "pattern: random or probe item", ""),
    "stim_choice_set": (
        "flip", "stim_visual",
        "syllables: four options spawn, word on its first attempt",
        "Nothing names the target finger; never pool with the 30 "
        "band. The spawn is the cue onset; tiles fall for fall_s."),
    "stim_choice_set_return": (
        "flip", "stim_visual",
        "syllables: options spawn for a word that came back after a miss",
        ""),
    "resp_correct_base": (
        "press sample", "response", "correct press, + lane pressed (0-7)",
        "Mirror sends one per hand (right 0-3, left 4-7). Chords sends "
        "one on the primary lane when the chord completes; per-finger "
        "onsets are only in the mode's own log. Echo sends one per "
        "reproduced item."),
    "resp_wrong_base": (
        "press sample", "response",
        "wrong finger, + lane actually pressed",
        "Rhythm sends it for the wrong finger pressed while another "
        "finger's note was due, so rhythm supplies ERN error trials. "
        "Chords sends it for a discrete wrong-finger press; force that "
        "leaks into a neighbour without registering as a press is "
        "enslavement, not a perceived error, and stays a correct "
        "byte."),
    "resp_anticipation_base": (
        "press sample", "response",
        "press before the go or under the anticipation cut, + lane", ""),
    "resp_timeout": (
        "state", "", "response window closed with no press",
        "Bookkeeping only; never average response-locked on it. In "
        "rhythm it lands when the miss window closes, inside the "
        "next note's 22-31 span, and belongs to the earlier note. "
        "Mirror misses send no 130: both hand bytes still go out."),
    "resp_idle": (
        "press sample", "response", "press with no trial active",
        "Rhythm sends it only when no note in any lane was due. A "
        "wrong finger on the beat is resp_wrong_base instead."),
    "feedback_positive": (
        "flip", "", "outcome glyph or chime for a hit",
        "Only under eeg.feedback_markers. Lab style draws the glyph "
        "feedback_delay_ms after the press and marks that flip. A "
        "feedback byte inside one frame of the block-end byte was "
        "drained at block close and the results screen followed it; "
        "leave it out of FRN averages."),
    "feedback_negative": (
        "flip", "", "outcome glyph for a miss; force_pilot: corridor-exit buzz",
        "Same rule as 140."),
    "feedback_neutral": ("flip", "", "reserved", ""),
    "block_start_base": (
        "state", "", "block starts, + mode id",
        "reaction 0, classic 1, adaptive 2, rhythm 3, mirror 4, "
        "pattern 5, chords 6, syllables 7, force_pilot 8, buzz_hunt "
        "10, echo 12; 9 retired, 11 reserved."),
    "block_abandoned": ("state", "", "block abandoned mid-way (Esc)", ""),
    "block_end_base": ("state", "", "block completed, + mode id", ""),
    "session_start": (
        "state", "", "participant logged in",
        "Outside any block: on the wire and in the app log, never in "
        "raw.csv or events.tsv."),
    "session_end": ("state", "", "session ended or app closed", "Same as 240."),
    "pause": ("state", "", "block paused", ""),
    "resume": ("state", "", "block resumed", ""),
    "rest_start": ("state", "", "rest card shown", ""),
    "rest_end": ("state", "", "rest card dismissed", ""),
}


def band_of(code: int) -> str:
    """Band label for a code, or "unknown" outside every band."""
    for lo, hi, label in BAND_LABELS:
        if lo <= int(code) <= hi:
            return label
    return "unknown"


def name_of(code: int) -> str:
    """Human name for a byte, with the additive parts resolved:
    resp_correct_lane3, block_start_reaction. Bases with an unknown
    remainder still name their band (block_start_id17) rather than
    returning nothing, so a row can never lose its byte."""
    code = int(code)
    for name, value in CODES.items():
        # A base shares its byte with lane 0 or mode id 0; the resolved
        # form below is the one the row should carry.
        if value == code and not name.endswith("_base"):
            return name
    modes = {v: k for k, v in MODE_IDS.items()}
    for base, prefix in (("resp_correct_base", "resp_correct_lane"),
                         ("resp_wrong_base", "resp_wrong_lane"),
                         ("resp_anticipation_base", "resp_anticipation_lane")):
        lane = code - CODES[base]
        if 0 <= lane <= 7:
            return f"{prefix}{lane}"
    for base, prefix in (("block_start_base", "block_start_"),
                         ("block_end_base", "block_end_")):
        mode_id = code - CODES[base]
        if 0 <= mode_id <= 18:
            return prefix + modes.get(mode_id, f"id{mode_id}")
    return "unknown"


def stim_code(sound_before: bool, buzz_before: bool,
              show_target: bool, buzz_now: bool = True) -> int:
    """Stimulus code for the cue condition in force.

    The offsets map straight onto the cue_flags switches so the byte
    says which sensory channels announced the stimulus. Visual,
    auditory and tactile stimuli produce different ERPs and must never
    be pooled, which is why the condition rides the byte and the lane
    rides the log row instead.

    `buzz_now` is whether the buzzer fired WITH this stimulus. Rhythm
    sends its buzz ahead of the beat (marked separately as 22), so the
    beat byte must not claim a tactile onset that happened earlier:
    the bit is set only when the buzzer channel is on AND it fired at
    this onset.
    """
    return (CODES["stim_visual"]
            + (1 if sound_before else 0)
            + (2 if (buzz_before and buzz_now) else 0)
            + (4 if not show_target else 0))


def marker_offsets(buzzer_ms: float, visual_ms: float,
                   tone_ms: float) -> dict:
    """Marker-to-stimulus offsets per event class, for metadata.json.

    Positive means the physical stimulus FOLLOWS the wire byte by that
    many milliseconds, so an epoch locked to the byte shifts later by
    the value to lock to the stimulus. The constants come from the
    latency.* config block; whether they were bench-measured on this
    rig rides next to them in the same metadata section.

    stim_visual   30-band and 40-band bytes go out straight after the
                  flip that shows the stimulus; the panel then takes
                  visual_ms to change (scan to mid-screen plus pixel
                  response).
    stim_tone     the cue tone is queued at dispatch and heard after
                  the mixer buffer, tone_ms.
    stim_buzz     bytes with the buzzer bit set (32, 33, 36, 37): the
                  STIM command left in the same frame BEFORE the flip,
                  so the felt vibration is buzzer_ms after the command
                  and between buzzer_ms minus one frame and buzzer_ms
                  after the byte. Rhythm's beat bytes never carry the
                  bit when the buzz was sent earlier.
    prep_buzz_lead  22 is written at the STIM command itself, so the
                  felt vibration is buzzer_ms after the byte.
    stim_buzz_hunt  38 is written at the pulse_motor command, same
                  rule as 22.
    response      t_event on the eeg row is the crossing sample; the
                  byte trails it by the queue drain (0 to one frame)
                  and the row carries both times, so 0 here.
    """
    return {
        "stim_visual": round(float(visual_ms), 1),
        "stim_tone": round(float(tone_ms), 1),
        "stim_buzz": round(float(buzzer_ms), 1),
        "stim_buzz_frame_note": "buzz command precedes the byte by the "
                                "draw time, 0 to one frame",
        "prep_buzz_lead": round(float(buzzer_ms), 1),
        "stim_buzz_hunt": round(float(buzzer_ms), 1),
        "response": 0.0,
    }


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

    Opening a container comes before anything inside it: a session
    start (240) and a block start (200 to 218) go first. The engine
    sends a block start and its GET READY in the same frame, and when
    block starts sat at the bottom of this list the queue put GET READY
    ahead of them, so every block on the recording opened with a 20
    that fell just OUTSIDE the block it belonged to. Anyone segmenting
    a BDF from 2xx to 22x lost it. Giving the openers first place costs
    stimulus timing nothing: a block start is sent seconds before that
    block's first stimulus exists, so the two never compete.

    After those, stimulus onsets carry the tightest timing requirement,
    responses next; feedback, preparation and the closing boundaries
    can afford a frame or two of delay because their analyses are
    either coarse or windowed away from the delayed edge.
    """
    if code == CODES["session_start"] or (
            CODES["block_start_base"] <= code < CODES["block_abandoned"]):
        return -1
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
            f"dropped={1 if rec.dropped else 0};"
            f"name={name_of(rec.code)}")


def parse_detail(detail: str) -> dict[str, str]:
    """Inverse of format_detail: the key=value pairs as strings."""
    out: dict[str, str] = {}
    for part in (detail or "").split(";"):
        key, _, val = part.partition("=")
        if key:
            out[key] = val
    return out


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
                 max_queue: int = 3,
                 box: str | None = None,
                 box_mode: str | None = None) -> None:
        self.backend = backend
        self.enabled = bool(enabled)
        self.pulse_s = float(pulse_ms) / 1000.0
        self.gap_s = float(gap_ms) / 1000.0
        # Documentation only, copied into metadata.json: which trigger
        # box and which switch position the session was recorded
        # with. The MMBT-S in Pulse Mode holds every code 8 ms and
        # resets itself whatever pulse_ms says; recording the mode is
        # what lets an analyst know which number the wire obeyed.
        self.box = box
        self.box_mode = box_mode
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
            "box": self.box,
            "box_mode": self.box_mode,
            "codes_version": CODES_VERSION,
            # The map itself travels with every block, so a session
            # folder decodes on its own even if this module moves on.
            "codes": dict(CODES),
            "mode_ids": dict(MODE_IDS),
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
    box = get("eeg.box", None)
    box_mode = get("eeg.box_mode", None)
    box = str(box) if box else None
    box_mode = str(box_mode) if box_mode else None
    if not enabled:
        return MarkerWriter(backend=None, enabled=False,
                            pulse_ms=pulse_ms, gap_ms=gap_ms,
                            on_emit=on_emit, box=box, box_mode=box_mode)
    port = get("eeg.port", None)
    baud = int(get("eeg.baud", 115200))
    if baud == 1200:
        # The NeuroSpec MMBT-S manual (section 3.3): setting the baud
        # to 1200 RESETS the box, which then drops off the bus. On a
        # virtual COM port the baud never sets the speed, so there is
        # no reason to send this value and one very good reason not to.
        raise TriggerPortError(
            "eeg.baud 1200 is refused: the MMBT-S trigger box resets "
            "and disappears from Device Manager when a port opens at "
            "1200 baud. Use 9600 (the documented rate) or leave the "
            "default.")
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
                        on_emit=on_emit, box=box, box_mode=box_mode)


# ---- events export -----------------------------------------------------------
# The lab side of the record. raw.csv holds every emission as an eeg
# row on the force-sample clock, which is what the notebook audits;
# the files below are the same rows in the shape an EEG pipeline
# imports: a BIDS events.tsv with its json sidecar, and the code table
# the recording was made under. Written at block end for EEG blocks
# and rebuildable from any session folder with export_events().

EVENTS_TSV = "events.tsv"
EVENTS_JSON = "events.json"
CODES_CSV = "markers_codes.csv"
# onset and duration first, as BIDS requires; value is the byte, so
# mne_bids reads it as the event id; the rest are ours and the
# sidecar describes them.
EVENT_COLUMNS = ["onset", "duration", "trial_type", "value", "sample",
                 "lane", "hand", "t_event", "t_wire", "delayed", "failed",
                 "dropped"]
CODES_COLUMNS = ["code", "name", "band", "locks_to", "offset_key",
                 "meaning", "notes", "codes_version"]
NA = "n/a"


def codes_table() -> list[dict]:
    """Every byte the map can produce, one row each, sorted by code.
    Built from CODES, MODE_IDS and CODE_NOTES so it cannot drift from
    the map it documents."""
    rows: list[dict] = []
    modes = sorted(MODE_IDS.values())
    for name, code in CODES.items():
        locks, offset, meaning, notes = CODE_NOTES.get(name, ("", "", "", ""))
        if name.startswith("resp_") and name.endswith("_base"):
            expand = [code + lane for lane in range(8)]
        elif name.startswith("block_") and name.endswith("_base"):
            expand = [code + mid for mid in modes]
        else:
            expand = [code]
        for c in expand:
            rows.append({"code": c, "name": name_of(c), "band": band_of(c),
                         "locks_to": locks, "offset_key": offset,
                         "meaning": meaning, "notes": notes,
                         "codes_version": CODES_VERSION})
    rows.sort(key=lambda r: r["code"])
    return rows


def write_codes_table(path) -> None:
    import csv
    from pathlib import Path
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CODES_COLUMNS)
        w.writeheader()
        for row in codes_table():
            w.writerow(row)


def read_marker_rows(raw_csv) -> tuple[list[dict], float | None]:
    """The eeg rows of a raw.csv, detail parsed, plus the onset
    reference: the t_perf of the block's first force sample, or of
    the block_start event when the block ran on the keyboard, or of
    the first eeg row when neither exists. None when there are no
    eeg rows at all."""
    import csv
    from pathlib import Path
    rows: list[dict] = []
    t0: float | None = None
    t0_kind = 3
    with Path(raw_csv).open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            event = r.get("event", "")
            try:
                t_perf = float(r.get("t_perf", ""))
            except ValueError:
                continue
            if event == "" and t0_kind > 0:
                t0, t0_kind = t_perf, 0
            elif event == "block_start" and t0_kind > 1:
                t0, t0_kind = t_perf, 1
            elif event == "eeg":
                d = parse_detail(r.get("detail", ""))
                try:
                    code = int(d.get("code", ""))
                except ValueError:
                    continue
                if t0_kind > 2:
                    t0, t0_kind = t_perf, 2
                rows.append({
                    "code": code,
                    "name": d.get("name") or name_of(code),
                    "lane": r.get("lane", ""),
                    "hand": r.get("hand", ""),
                    "t_event": d.get("t_event", "") or f"{t_perf:.6f}",
                    "t_wire": d.get("t_wire", ""),
                    "delayed": d.get("delayed", "0"),
                    "failed": d.get("failed", "0"),
                    "dropped": d.get("dropped", "0"),
                })
    return rows, t0


def _sidecar(eeg_meta: dict, t0_note: str, rate) -> dict:
    return {
        "onset": {
            "Description": "Seconds from the block's first raw.csv force "
                           "sample (t_perf), the game's own clock. The "
                           "amplifier's zero is unknown to the game: "
                           "align by matching inter-marker intervals to "
                           "the Status channel, then shift. " + t0_note,
            "Units": "s"},
        "duration": {"Description": "Marker pulse width, eeg.pulse_ms.",
                     "Units": "s"},
        "trial_type": {"Description": "Code name from markers_codes.csv, "
                                      "lane or mode resolved."},
        "value": {"Description": "The byte on the trigger line, the low "
                                 "byte of the BioSemi Status channel."},
        "sample": {"Description": "round(onset * amplifier rate); n/a "
                                  "when eeg.amplifier_rate_hz is unset.",
                   "AmplifierRateHz": rate},
        "lane": {"Description": "Finger 0-7 the marker belongs to, right "
                                "hand 0-3, left 4-7; empty for state "
                                "markers."},
        "hand": {"Description": "Hand mode of the block."},
        "t_event": {"Description": "perf_counter time of the physical "
                                   "event on the force-sample clock.",
                    "Units": "s"},
        "t_wire": {"Description": "perf_counter just after the byte was "
                                  "written; empty when it never was.",
                   "Units": "s"},
        "delayed": {"Description": "1 when the byte waited for the line "
                                   "(pulse plus gap) behind another "
                                   "marker; t_event is still the event."},
        "failed": {"Description": "1 when the write failed: the row is "
                                  "the intended marker, nothing reached "
                                  "the amplifier."},
        "dropped": {"Description": "1 when the queue shed the marker; "
                                   "never on the wire."},
        "CodesVersion": eeg_meta.get("codes_version", CODES_VERSION),
        "PulseMs": eeg_meta.get("pulse_ms"),
        "GapMs": eeg_meta.get("gap_ms"),
        "Box": eeg_meta.get("box"),
        "BoxMode": eeg_meta.get("box_mode"),
        "Backend": eeg_meta.get("backend"),
        "Degraded": eeg_meta.get("degraded"),
        "MarkerOffsetsMs": eeg_meta.get("marker_offsets_ms"),
        "SessionMarkers": "240 and 241 fire outside any block and are "
                          "not in this file.",
    }


def export_events(root, sample_rate_hz=None) -> dict:
    """Write events.tsv, events.json and markers_codes.csv into a
    session folder from its raw.csv and metadata.json. Returns the
    three paths. Rows are sorted by t_event, the intended time, because
    two markers inside pulse plus gap of each other leave the wire in
    priority order, not event order. Failed and dropped rows stay in,
    flagged, so a trial that lost its byte is visible rather than
    silently absent."""
    import csv
    import json
    from pathlib import Path
    root = Path(root)
    raw = root / "raw.csv"
    if not raw.is_file():
        raise FileNotFoundError(raw)
    eeg_meta: dict = {}
    meta_path = root / "metadata.json"
    if meta_path.is_file():
        try:
            eeg_meta = json.loads(meta_path.read_text(encoding="utf-8")).get(
                "eeg", {}) or {}
        except (OSError, ValueError):
            eeg_meta = {}
    rows, t0 = read_marker_rows(raw)
    pulse_ms = float(eeg_meta.get("pulse_ms") or 10.0)
    rate = float(sample_rate_hz) if sample_rate_hz else None
    if t0 is None:
        t0 = 0.0
        t0_note = "This block has no eeg rows; onset is raw t_event."
    else:
        t0_note = f"Reference t_perf {t0:.6f}."
    rows.sort(key=lambda r: float(r["t_event"]))
    tsv = root / EVENTS_TSV
    with tsv.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")
        w.writerow(EVENT_COLUMNS)
        for r in rows:
            onset = float(r["t_event"]) - t0
            w.writerow([
                f"{onset:.6f}",
                f"{pulse_ms / 1000.0:.3f}",
                r["name"],
                r["code"],
                int(round(onset * rate)) if rate else NA,
                r["lane"] if r["lane"] != "" else NA,
                r["hand"] or NA,
                r["t_event"],
                r["t_wire"] or NA,
                r["delayed"], r["failed"], r["dropped"],
            ])
    sidecar = root / EVENTS_JSON
    sidecar.write_text(json.dumps(_sidecar(eeg_meta, t0_note, rate),
                                  indent=2), encoding="utf-8")
    codes = root / CODES_CSV
    write_codes_table(codes)
    return {"events": tsv, "sidecar": sidecar, "codes": codes}
