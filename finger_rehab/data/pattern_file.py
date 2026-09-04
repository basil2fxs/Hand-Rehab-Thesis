"""Researcher-supplied sequence files for Patterns (Muscle Memory).

WHAT THIS IS. A YAML file that describes the whole Patterns session:
which fingers light in which order, how long the pause after each
press is, how many times each block repeats, and how long the rest
after it lasts. Load one and it replaces the built-in hidden riff and
the ten-take layout for every Patterns block from then on, in every
session, until another file is loaded or Clear is pressed. Nothing
about a loaded file is per participant: it describes the TASK, so
every participant on that machine plays the same one, which is the
only way blocks from different people can be compared.

WHY A FILE AND NOT SETTINGS. The thing a researcher wants to change
here is a list of 8 to 64 numbers plus a matching list of gaps. That
is a document, not a switch, and it has to survive app restarts and
be copyable between machines with the participant data untouched. A
file also leaves an audit trail: every import is archived under the
drop folder with a timestamp, and the sha256 of the exact bytes that
ran rides in every block's metadata.json.

WHY THE TIMING MATTERS, AND WHY IT IS FIXED PER FILE. Timing is part
of what gets learnt, not decoration. Shin and Ivry (2002, JEP:LMC
28:445-457) found a temporal sequence is learnt only when it is
correlated with the spatial one; O'Reilly, McCarthy, Capizzi and
Nobre (2008, J Neurophysiol 99:2731-2735) found a predictable
temporal structure helps an ordinal sequence get learnt but is not
learnt on its own; Ullen and Bengtsson (2003, J Neurophysiol
90:3725-3735) and Kornysheva and Diedrichsen (2014, eLife 3:e03043)
showed the two are represented partly separately. So a gap list is
only useful if it is played identically on every repeat and in every
session, which is what this module guarantees, and a probe block
should carry the SAME gaps as the trained blocks it is scored
against, or the probe changes order and timing at once and the
rebound is no longer the Reed and Johnson (1994) contrast. Changing
the gaps between sessions is a change of task; the file's schedule_id
(the first 12 hex characters of its sha256) rides every block so the
notebook never pools two different tasks.

EXPLICIT PRACTICE. `explicit: true` marks a file as one where the
participant is told the riff, the discrete sequence production design
(Abrahamse, Ruitenberg, de Kleine and Verwey 2013, Front Hum Neurosci
7:82). It is off by default because Boyd and Winstein (2003, Phys
Ther 83:976-989; 2004, Learn Mem 11:388-396; 2006, J Neurol Phys Ther
30:46-57) found explicit information about the sequence IMPAIRS
implicit motor learning after stroke. With explicit false nothing on
screen changes: takes and stars, never the word sequence. The flag is
stamped in the block summary so explicit games are never pooled with
implicit ones in the analysis.

GAP SEMANTICS. A gap is the pause AFTER a press before the next key
lights: the response-to-stimulus interval the mode already calls RSI.
A file with a single default gap of 500 ms reproduces today's
behaviour exactly. Verified working range in the literature is 0 to
500 ms (250 ms in Destrebecqz and Cleeremans 2001 and Eberhardt et al
2025; 0 ms in the discrete sequence production task), and the schema
allows 0 to 5000 so a slow stroke-affected hand can be given room.
Metronome-style fixed onset-to-onset pacing is NOT implemented; see
the deferred list at the bottom of this docstring.

WHERE THE FILES LIVE (all under config/, all writable, none of them
config/user_settings.yaml, which describes the machine and is read
into every session snapshot):
  config/pattern_sequence.yaml   the active file, byte-for-byte the
                                 copy that was imported, comments and
                                 all, so it can be read back later
  config/pattern_sequence.json   the pointer: where it came from, when
                                 it was imported, its sha256, name,
                                 hands and block count
  config/pattern_sequences/      the drop folder. Templates are
                                 written here; a file saved here as
                                 current.yaml is imported on its own
                                 the next time a menu screen opens
  config/pattern_sequences/history/  every import, timestamped

DEFERRED, on purpose, so nobody hunts for them: fixed onset-to-onset
pacing; per-block timeouts (one timeout per file keeps the notebook's
consistency key one value per game); R1..R4 / L1..L4 lane tokens;
per-participant files; an editor inside the app.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml


log = logging.getLogger(__name__)

# Config keys and their defaults. Anything here has to be on
# config.resolve_path's writable whitelist or the frozen exe cannot
# write it (it would try to write inside the read-only bundle).
ACTIVE_KEY = "pattern.sequence_file"
POINTER_KEY = "pattern.sequence_pointer"
DROP_KEY = "pattern.sequence_drop_dir"
ENABLED_KEY = "pattern.sequence_file_enabled"

DEFAULT_ACTIVE = "config/pattern_sequence.yaml"
DEFAULT_POINTER = "config/pattern_sequence.json"
DEFAULT_DROP = "config/pattern_sequences"

# The name a researcher saves into the drop folder to load a file
# without touching the app at all.
DROP_NAME = "current.yaml"

SCHEMA_VERSION = 1
# A sequence file is a few kilobytes. The cap stops a stray drop of a
# video or a dataset from being read into memory and parsed.
MAX_BYTES = 256 * 1024

# Schema bounds, in one place so the validator and the error
# sentences cannot drift apart.
MAX_BLOCKS = 40
MAX_TOTAL_TRIALS = 2000
NAME_MAX = 40
BLOCK_NAME_MAX = 24
SEQ_MIN, SEQ_MAX = 2, 64
TRIALS_MIN, TRIALS_MAX = 1, 400
REPEATS_MIN, REPEATS_MAX = 1, 50
GAP_MIN_MS, GAP_MAX_MS = 0, 5000
REST_MIN_S, REST_MAX_S = 0.0, 300.0
TIMEOUT_MIN_MS, TIMEOUT_MAX_MS = 300, 10000

DEFAULT_GAP_MS = 500
DEFAULT_REST_S = 10.0
DEFAULT_TIMEOUT_MS = 2000

# What the estimate assumes a press takes. Only used for the "about N
# minutes" line on Settings, so a 40-minute file is noticed before a
# participant sits down; nothing in the analysis reads it.
NOMINAL_RESPONSE_S = 0.6
# The mode's gap between announcing a take and its first stimulus.
BLOCK_LEAD_S = 1.5

KINDS = ("warmup", "random", "seq", "probe")
SEQ_KINDS = ("seq", "probe")

TOP_KEYS = ("pattern_file", "name", "hands", "explicit", "show_sequence",
            "allow_repeats", "timeout_ms", "defaults", "blocks", "notes")
DEFAULTS_KEYS = ("gaps_ms", "rest_after_s")
BLOCK_KEYS = ("name", "kind", "sequence", "trials", "repeats",
              "gaps_ms", "rest_after_s")

_BLOCK_NAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,%d}$" % BLOCK_NAME_MAX)


class SequenceFileError(ValueError):
    """A file that could not become a plan. `errors` is the list of
    plain sentences to put on screen, one per problem, so the
    researcher fixes everything in one pass instead of one error per
    reload."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = list(errors)
        super().__init__("; ".join(self.errors) if self.errors
                         else "sequence file rejected")


@dataclass
class PlanBlock:
    """One block of the file, ready for the mode to lay out."""
    name: str
    kind: str                       # warmup | random | seq | probe
    # 0-based lane INDEX into the plan's lane list. Empty for warmup
    # and random, whose material is drawn fresh per block by the
    # mode's balanced shuffle-bag.
    sequence: list[int]
    trials: int                     # total presses this block plays
    repeats: int
    # Per item of ONE cycle (seq, probe) or per trial (warmup,
    # random). Seconds, because that is what the mode's clock uses.
    gaps_s: list[float]
    rest_after_s: float

    @property
    def gaps_ms(self) -> list[int]:
        return [int(round(g * 1000.0)) for g in self.gaps_s]

    def lanes_1based(self) -> list[int]:
        """The researcher's own numbers, for metadata and for the
        on-screen digits when show_sequence is on."""
        return [i + 1 for i in self.sequence]

    def expanded_gaps_s(self) -> list[float]:
        """One gap per trial of the whole block, repeats included.
        This is what the mode hands to each Segment."""
        if not self.gaps_s:
            return []
        out: list[float] = []
        while len(out) < self.trials:
            out.extend(self.gaps_s)
        return out[:self.trials]


@dataclass
class SequencePlan:
    """A validated file. Everything the mode, the screens and the
    metadata need, with no further reference to the YAML."""
    schema: int
    name: str
    hands: str                      # one | both
    n_lanes: int                    # 4 or 8
    explicit: bool
    show_sequence: bool
    allow_repeats: bool
    timeout_s: float
    default_gap_s: float
    default_rest_s: float
    blocks: list[PlanBlock]
    cycle_len: int
    sha256: str = ""
    file_name: str = ""
    source_path: str = ""
    imported_at: str = ""
    warnings: list[str] = field(default_factory=list)
    notes: str = ""

    @property
    def schedule_id(self) -> str:
        """Short identity of the exact bytes that ran. The notebook
        splits games on it the same way it splits on rsi_ms: two
        different files are two different tasks and must never pool."""
        return self.sha256[:12] if self.sha256 else ""

    @property
    def total_trials(self) -> int:
        return sum(b.trials for b in self.blocks)

    def labels(self) -> list[str]:
        """Take labels in play order: W for the warm-up if there is
        one, then 1..N. Same convention the built-in layout uses, so
        the notebook's b= grouping needs no change."""
        out: list[str] = []
        n = 0
        for b in self.blocks:
            if b.kind == "warmup":
                out.append("W")
            else:
                n += 1
                out.append(str(n))
        return out

    def seq_blocks(self) -> list[PlanBlock]:
        return [b for b in self.blocks if b.kind == "seq"]

    def probe_blocks(self) -> list[PlanBlock]:
        return [b for b in self.blocks if b.kind == "probe"]

    def estimated_minutes(self) -> float:
        """Rough wall clock: every item costs its gap plus a nominal
        response, every block costs its lead-in, and every rest but
        the last one costs its floor. A participant slower than the
        nominal response takes longer; this is a planning number, not
        a measurement."""
        total = 0.0
        for i, b in enumerate(self.blocks):
            gaps = b.expanded_gaps_s()
            total += sum(gaps) + b.trials * NOMINAL_RESPONSE_S
            total += BLOCK_LEAD_S
            if i < len(self.blocks) - 1:
                total += b.rest_after_s
        return round(total / 60.0, 2)

    def summary(self) -> dict:
        """What block_stats stores in metadata.json. The schedule the
        session actually ran, in the researcher's own 1-based lane
        numbers, so the notebook reads the layout from the data
        instead of assuming the built-in ten-take one."""
        labels = self.labels()
        return {
            "schema": self.schema,
            "name": self.name,
            "file_name": self.file_name,
            "source_path": self.source_path,
            "imported_at": self.imported_at,
            "sha256": self.sha256,
            "schedule_id": self.schedule_id,
            "hands": self.hands,
            "n_lanes": self.n_lanes,
            "explicit": self.explicit,
            "show_sequence": self.show_sequence,
            "allow_repeats": self.allow_repeats,
            "timeout_ms": int(round(self.timeout_s * 1000.0)),
            "default_gap_ms": int(round(self.default_gap_s * 1000.0)),
            "default_rest_after_s": self.default_rest_s,
            "cycle_len": self.cycle_len,
            "total_trials": self.total_trials,
            "estimated_minutes": self.estimated_minutes(),
            "notes": self.notes,
            "blocks": [
                {
                    "name": b.name,
                    "kind": b.kind,
                    "label": labels[i],
                    "trials": b.trials,
                    "repeats": b.repeats,
                    "sequence": b.lanes_1based(),
                    "gaps_ms": b.gaps_ms,
                    "rest_after_s": b.rest_after_s,
                }
                for i, b in enumerate(self.blocks)
            ],
            "warnings": list(self.warnings),
        }

    def headline(self) -> str:
        """One line for the Settings status and the hub card."""
        takes = sum(1 for b in self.blocks if b.kind != "warmup")
        return (f"{self.name} ({self.hands} hand"
                f"{'s' if self.hands == 'both' else ''}, {takes} takes, "
                f"about {self.estimated_minutes():.0f} min)")


# ---- validation ------------------------------------------------------------
def _is_int(v) -> bool:
    # bool is an int in Python and yaml gives real bools for yes/true,
    # so a stray "repeats: true" must not read as 1.
    return isinstance(v, int) and not isinstance(v, bool)


def _is_num(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _unknown_keys(data: dict, allowed, where: str) -> list[str]:
    """Typos are the whole reason unknown keys are an error: YAML
    accepts `gap_ms` silently and the researcher would run a whole
    cohort on default timings without ever being told."""
    out = []
    for k in data:
        if k not in allowed:
            out.append(f"Unknown key {k} at {where}. "
                       f"Allowed keys: {', '.join(allowed)}.")
    return out


def _canonical_rotation(seq: list[int]) -> tuple[int, ...]:
    n = len(seq)
    return min(tuple(seq[i:] + seq[:i]) for i in range(n)) if n else ()


def _gaps_for(raw, n: int, block_name: str, default_s: float,
              errors: list[str]) -> list[float]:
    """One gap per item, from a single number or a list of exactly n."""
    if raw is None:
        return [default_s] * n
    msg = (f"Block {block_name}: gaps_ms must be one number or a list "
           f"of exactly {n} numbers, each {GAP_MIN_MS} to {GAP_MAX_MS}.")
    if _is_num(raw):
        if not GAP_MIN_MS <= float(raw) <= GAP_MAX_MS:
            errors.append(msg)
            return [default_s] * n
        return [float(raw) / 1000.0] * n
    if isinstance(raw, list):
        if len(raw) != n or not all(_is_num(g) for g in raw):
            errors.append(msg)
            return [default_s] * n
        if not all(GAP_MIN_MS <= float(g) <= GAP_MAX_MS for g in raw):
            errors.append(msg)
            return [default_s] * n
        return [float(g) / 1000.0 for g in raw]
    errors.append(msg)
    return [default_s] * n


def validate(data) -> tuple[SequencePlan | None, list[str], list[str]]:
    """Turn parsed YAML into a plan, or into a list of plain
    sentences. Total by design: a file either loads whole or changes
    nothing, so the app can never end up half configured."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(data, dict) or "pattern_file" not in data:
        return None, ["The file must be a mapping with pattern_file: 1 "
                      "at the top."], []
    errors.extend(_unknown_keys(data, TOP_KEYS, "the top level"))

    schema = data.get("pattern_file")
    if not _is_int(schema) or int(schema) != SCHEMA_VERSION:
        errors.append(f"pattern_file must be {SCHEMA_VERSION} "
                      f"(this build reads version {SCHEMA_VERSION}).")

    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= NAME_MAX:
        errors.append(f"name is required (1 to {NAME_MAX} characters).")
        name = str(name or "")[:NAME_MAX]
    name = name.strip()

    hands = data.get("hands")
    if hands not in ("one", "both"):
        errors.append("hands must be one or both.")
        hands = "one"
    n_lanes = 8 if hands == "both" else 4

    def flag(key: str) -> bool:
        v = data.get(key, False)
        if not isinstance(v, bool):
            errors.append(f"{key} must be true or false.")
            return False
        return v

    explicit = flag("explicit")
    show_sequence = flag("show_sequence")
    allow_repeats = flag("allow_repeats")
    if show_sequence and not explicit:
        errors.append("show_sequence needs explicit: true.")

    timeout_ms = data.get("timeout_ms", DEFAULT_TIMEOUT_MS)
    if (not _is_int(timeout_ms)
            or not TIMEOUT_MIN_MS <= int(timeout_ms) <= TIMEOUT_MAX_MS):
        errors.append(f"timeout_ms must be a whole number from "
                      f"{TIMEOUT_MIN_MS} to {TIMEOUT_MAX_MS}.")
        timeout_ms = DEFAULT_TIMEOUT_MS

    notes = data.get("notes", "")
    if not isinstance(notes, str):
        errors.append("notes must be text.")
        notes = ""

    defaults = data.get("defaults", {})
    default_gap_s = DEFAULT_GAP_MS / 1000.0
    default_rest_s = DEFAULT_REST_S
    if defaults is None:
        defaults = {}
    if not isinstance(defaults, dict):
        errors.append("defaults must be a mapping with gaps_ms and "
                      "rest_after_s.")
        defaults = {}
    else:
        errors.extend(_unknown_keys(defaults, DEFAULTS_KEYS, "defaults"))
        g = defaults.get("gaps_ms", DEFAULT_GAP_MS)
        if not _is_num(g) or not GAP_MIN_MS <= float(g) <= GAP_MAX_MS:
            errors.append(f"defaults.gaps_ms must be a number from "
                          f"{GAP_MIN_MS} to {GAP_MAX_MS}.")
        else:
            default_gap_s = float(g) / 1000.0
        r = defaults.get("rest_after_s", DEFAULT_REST_S)
        if not _is_num(r) or not REST_MIN_S <= float(r) <= REST_MAX_S:
            errors.append(f"defaults.rest_after_s must be a number from "
                          f"{REST_MIN_S:.0f} to {REST_MAX_S:.0f}.")
        else:
            default_rest_s = float(r)

    raw_blocks = data.get("blocks")
    if (not isinstance(raw_blocks, list)
            or not 1 <= len(raw_blocks) <= MAX_BLOCKS):
        errors.append(f"blocks must be a list of 1 to {MAX_BLOCKS} blocks.")
        return None, errors, warnings

    blocks: list[PlanBlock] = []
    seen_names: dict[str, int] = {}
    cycle_len = 0
    cycle_owner = ""

    for i, raw in enumerate(raw_blocks):
        if not isinstance(raw, dict):
            errors.append(f"Block {i + 1} needs a name (letters, digits, "
                          f"_ or -, up to {BLOCK_NAME_MAX}).")
            continue
        bname = raw.get("name")
        if not isinstance(bname, str) or not _BLOCK_NAME_RE.match(bname):
            errors.append(f"Block {i + 1} needs a name (letters, digits, "
                          f"_ or -, up to {BLOCK_NAME_MAX}).")
            bname = f"block{i + 1}"
        elif bname in seen_names:
            errors.append(f"Block {bname} repeats the name of block "
                          f"{seen_names[bname] + 1}; names must be unique.")
        seen_names.setdefault(bname, i)
        errors.extend(_unknown_keys(raw, BLOCK_KEYS, f"block {bname}"))

        kind = raw.get("kind")
        if kind not in KINDS:
            errors.append(f"Block {bname}: kind must be warmup, random, "
                          f"seq or probe.")
            continue

        # Keys that belong to the other kind of block are refused
        # rather than ignored: a `trials: 60` on a seq block means the
        # researcher expects 60 presses and would never be told the
        # number did nothing.
        for key, kinds in (("sequence", SEQ_KINDS), ("repeats", SEQ_KINDS),
                           ("trials", ("warmup", "random"))):
            if key in raw and kind not in kinds:
                errors.append(f"Block {bname}: {key} does not apply to a "
                              f"{kind} block.")

        sequence: list[int] = []
        repeats = 1
        trials = 0
        if kind in SEQ_KINDS:
            seq = raw.get("sequence")
            ok = (isinstance(seq, list)
                  and SEQ_MIN <= len(seq) <= SEQ_MAX
                  and all(_is_int(x) and 1 <= int(x) <= n_lanes
                          for x in seq))
            if not ok:
                errors.append(
                    f"Block {bname}: sequence must be a list of {SEQ_MIN} "
                    f"to {SEQ_MAX} lane numbers between 1 and {n_lanes}.")
                continue
            sequence = [int(x) - 1 for x in seq]
            if not allow_repeats:
                n = len(sequence)
                for j in range(n):
                    if sequence[j] == sequence[(j + 1) % n]:
                        errors.append(
                            f"Block {bname}: lane {sequence[j] + 1} follows "
                            f"itself at item {j + 1} (set allow_repeats: "
                            f"true to permit this).")
                        break
            if cycle_len == 0:
                cycle_len, cycle_owner = len(sequence), bname
            elif len(sequence) != cycle_len:
                errors.append(
                    f"Block {bname}: sequence has {len(sequence)} items but "
                    f"block {cycle_owner} has {cycle_len}; every seq and "
                    f"probe sequence must be the same length.")
            rp = raw.get("repeats", 1)
            if not _is_int(rp) or not REPEATS_MIN <= int(rp) <= REPEATS_MAX:
                errors.append(f"Block {bname}: repeats must be a whole "
                              f"number from {REPEATS_MIN} to {REPEATS_MAX}.")
                rp = 1
            repeats = int(rp)
            trials = len(sequence) * repeats
            gaps = _gaps_for(raw.get("gaps_ms"), len(sequence), bname,
                             default_gap_s, errors)
        else:
            tr = raw.get("trials")
            if not _is_int(tr) or not TRIALS_MIN <= int(tr) <= TRIALS_MAX:
                errors.append(f"Block {bname}: trials must be a whole "
                              f"number from {TRIALS_MIN} to {TRIALS_MAX}.")
                continue
            trials = int(tr)
            gaps = _gaps_for(raw.get("gaps_ms"), trials, bname,
                             default_gap_s, errors)
            if trials % n_lanes != 0:
                warnings.append(
                    f"Block {bname}: {trials} trials does not divide "
                    f"evenly across {n_lanes} lanes, so the lanes are only "
                    f"balanced to within one trial.")

        rest = raw.get("rest_after_s", default_rest_s)
        if not _is_num(rest) or not REST_MIN_S <= float(rest) <= REST_MAX_S:
            errors.append(f"Block {bname}: rest_after_s must be a number "
                          f"from {REST_MIN_S:.0f} to {REST_MAX_S:.0f}.")
            rest = default_rest_s

        blocks.append(PlanBlock(
            name=bname, kind=kind, sequence=sequence, trials=trials,
            repeats=repeats, gaps_s=gaps, rest_after_s=float(rest)))

    # ---- structure, once every block is known -----------------------
    warm = [i for i, b in enumerate(blocks) if b.kind == "warmup"]
    if len(warm) > 1 or (warm and warm[0] != 0):
        errors.append("Only one warmup block is allowed and it must be "
                      "first.")
    seqs = [b for b in blocks if b.kind == "seq"]
    if not seqs:
        errors.append("The file has no seq block, so there is nothing to "
                      "learn.")
    trained_rotations = {_canonical_rotation(b.sequence): b.name
                         for b in seqs}
    for b in blocks:
        if b.kind != "probe":
            continue
        owner = trained_rotations.get(_canonical_rotation(b.sequence))
        if owner:
            errors.append(f"Probe {b.name} is the trained riff ({owner}) "
                          f"rotated; a probe must be a different order.")

    total = sum(b.trials for b in blocks)
    if total > MAX_TOTAL_TRIALS:
        errors.append(f"The file has {total} trials in total; the limit "
                      f"is {MAX_TOTAL_TRIALS}.")

    # ---- warnings: never block a load -------------------------------
    seq_gap_sets = {tuple(b.gaps_s) for b in seqs}
    for i, b in enumerate(blocks):
        if b.kind != "probe":
            continue
        before = any(x.kind == "seq" for x in blocks[:i])
        after = any(x.kind == "seq" for x in blocks[i + 1:])
        if not (before and after):
            warnings.append(
                f"Probe {b.name} has no trained block on both sides, so it "
                f"cannot be scored against flanking takes.")
        if seq_gap_sets and tuple(b.gaps_s) not in seq_gap_sets:
            warnings.append(
                f"Probe {b.name} uses different gaps from every seq block, "
                f"so it changes the timing as well as the order.")
    if n_lanes == 8:
        for b in blocks:
            if b.kind != "seq" or not b.sequence:
                continue
            right = sum(1 for x in b.sequence if x < 4)
            left = len(b.sequence) - right
            if abs(right - left) > 1:
                warnings.append(
                    f"Block {b.name} gives the right hand {right} items and "
                    f"the left {left}; the hands are not balanced.")

    if errors:
        return None, errors, warnings
    return SequencePlan(
        schema=SCHEMA_VERSION, name=name, hands=hands, n_lanes=n_lanes,
        explicit=explicit, show_sequence=show_sequence,
        allow_repeats=allow_repeats,
        timeout_s=float(timeout_ms) / 1000.0,
        default_gap_s=default_gap_s, default_rest_s=default_rest_s,
        blocks=blocks, cycle_len=cycle_len, notes=notes,
        warnings=warnings), [], warnings


def parse_plan(text: str, *, file_name: str = "") -> SequencePlan:
    """Text to plan, or SequenceFileError carrying every problem."""
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as e:
        mark = getattr(e, "problem_mark", None)
        where = (f" (line {mark.line + 1}, column {mark.column + 1})"
                 if mark is not None else "")
        detail = getattr(e, "problem", None) or str(e).splitlines()[0]
        raise SequenceFileError(
            [f"The file is not valid YAML{where}: {detail}."]) from e
    plan, errors, _warnings = validate(data)
    if plan is None:
        raise SequenceFileError(errors)
    plan.sha256 = hashlib.sha256(text.encode("utf-8")).hexdigest()
    plan.file_name = file_name or ""
    return plan


def cap_warning(plan: SequencePlan, cap_min: float) -> str | None:
    """The one warning that needs the config: a file longer than the
    mode's session cap will be cut off mid-run."""
    est = plan.estimated_minutes()
    if cap_min and est > float(cap_min):
        return (f"This file runs about {est:.0f} minutes but the session "
                f"cap is {float(cap_min):.0f}; the block ends at the cap.")
    return None


def hand_mismatch(plan: SequencePlan | None, hand_mode: str) -> str | None:
    """Refusal sentence when a file cannot run on the picked hand, or
    None. Refused rather than remapped: a both-hands riff squeezed
    onto four lanes is different material, and silently changing the
    task under a participant is how a cohort ends up unusable."""
    if plan is None:
        return None
    if plan.hands == "both" and hand_mode != "both":
        return ("This riff file needs both hands. Pick Both hands, or "
                "load a one-hand file.")
    if plan.hands == "one" and hand_mode == "both":
        return ("This riff file is for one hand. Pick Left or Right, or "
                "load a both-hands file.")
    return None


# ---- paths -----------------------------------------------------------------
def active_path(cfg) -> Path:
    return cfg.resolve_path(cfg.get(ACTIVE_KEY, DEFAULT_ACTIVE))


def pointer_path(cfg) -> Path:
    return cfg.resolve_path(cfg.get(POINTER_KEY, DEFAULT_POINTER))


def drop_dir(cfg) -> Path:
    return cfg.resolve_path(cfg.get(DROP_KEY, DEFAULT_DROP))


def is_enabled(cfg) -> bool:
    return bool(cfg.get(ENABLED_KEY, True))


def _atomic_write(path: Path, data: bytes) -> None:
    """Same tmp-then-replace the session metadata uses: a crash or a
    yanked USB drive mid-write leaves the old file, never half a new
    one that would then fail to parse at the next block start."""
    tmp = path.with_name(path.name + ".tmp")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        try:
            os.fsync(f.fileno())
        except (OSError, AttributeError):
            pass
    os.replace(tmp, path)


def pointer(cfg) -> dict | None:
    """Where the active file came from, or None. Unreadable is the
    same as absent: the pointer is a convenience, and the active YAML
    is the thing that actually runs."""
    try:
        raw = json.loads(pointer_path(cfg).read_text(encoding="utf-8"))
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


@dataclass
class ImportResult:
    ok: bool
    plan: SequencePlan | None = None
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    file_name: str = ""
    path: Path | None = None
    archived: Path | None = None

    def message(self) -> str:
        """One line for a status bar. The full error list goes to the
        log, so a file with six problems does not need a six-line
        popup to be fixable."""
        if self.ok and self.plan is not None:
            extra = (f", {len(self.warnings)} warning"
                     f"{'s' if len(self.warnings) != 1 else ''}"
                     if self.warnings else "")
            return f"Loaded {self.plan.headline()}{extra}"
        first = self.errors[0] if self.errors else "file rejected"
        n = len(self.errors)
        more = f" ({n} problems, see log)" if n > 1 else ""
        return f"{self.file_name or 'file'} not loaded: {first}{more}"


def read_and_parse(src: Path) -> tuple[SequencePlan | None, list[str], bytes]:
    """Bytes to plan without writing anything. Split out so import and
    load share one reader and cannot disagree about what a valid file
    is."""
    src = Path(src)
    try:
        raw = src.read_bytes()
    except OSError as e:
        return None, [f"The file could not be read: {e}."], b""
    if len(raw) > MAX_BYTES:
        return None, [f"The file is {len(raw) // 1024} KB; a sequence file "
                      f"is a few KB and the limit is "
                      f"{MAX_BYTES // 1024} KB."], raw
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return None, ["The file is not UTF-8 text; save it as plain text."], raw
    try:
        plan = parse_plan(text, file_name=src.name)
    except SequenceFileError as e:
        return None, e.errors, raw
    return plan, [], raw


def import_file(src: Path, cfg) -> ImportResult:
    """Validate a file and, only if it is whole, make it the active
    one. A rejected file changes nothing on disk, so a bad drop can
    never take the built-in riff away mid-study.

    Every accepted import is archived under the drop folder with a
    timestamp before it becomes active, so the thesis can say which
    schedule ran on which day without trusting anyone's memory."""
    src = Path(src)
    plan, errors, raw = read_and_parse(src)
    if plan is None:
        for line in errors:
            log.warning("pattern sequence file rejected (%s): %s",
                        src.name, line)
        return ImportResult(ok=False, errors=errors, file_name=src.name)

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    archived: Path | None = None
    try:
        hist = drop_dir(cfg) / "history"
        hist.mkdir(parents=True, exist_ok=True)
        archived = hist / f"{stamp}_{src.name}"
        # Two imports inside the same second are ordinary (fix a typo,
        # save, reload), and the second must not quietly erase the
        # first entry in the audit trail.
        n = 1
        while archived.exists():
            n += 1
            archived = hist / f"{stamp}-{n}_{src.name}"
        archived.write_bytes(raw)
    except OSError as e:
        # An unwritable archive folder is worth a log line, not a
        # refusal: the researcher's file is still good and the active
        # copy below is the one that runs.
        log.warning("pattern sequence archive not written: %s", e)
        archived = None

    dest = active_path(cfg)
    try:
        _atomic_write(dest, raw)
    except OSError as e:
        return ImportResult(ok=False, file_name=src.name,
                            errors=[f"The file could not be saved into the "
                                    f"app: {e}."])
    plan.source_path = str(src)
    plan.imported_at = datetime.now().isoformat(timespec="seconds")
    try:
        _atomic_write(pointer_path(cfg), json.dumps({
            "version": 1,
            "source_path": plan.source_path,
            "imported_at": plan.imported_at,
            "sha256": plan.sha256,
            "file_name": src.name,
            "name": plan.name,
            "hands": plan.hands,
            "n_blocks": len(plan.blocks),
            "schema": plan.schema,
        }, indent=2, sort_keys=True).encode("utf-8"))
    except OSError as e:
        log.warning("pattern sequence pointer not written: %s", e)
    log.info("pattern sequence file loaded: %s (%s, %d blocks, %s)",
             src.name, plan.hands, len(plan.blocks), plan.schedule_id)
    for line in plan.warnings:
        log.warning("pattern sequence file warning (%s): %s", src.name, line)
    return ImportResult(ok=True, plan=plan, warnings=plan.warnings,
                        file_name=src.name, path=dest, archived=archived)


def load_active_plan(cfg) -> tuple[SequencePlan | None, str]:
    """The plan every Patterns block starts from, re-read and
    re-validated at each block start. Re-reading matters: someone can
    edit the active file in place between blocks, and a block must
    either run the file that is there now or say plainly that it fell
    back to the built-in riff."""
    path = active_path(cfg)
    if not path.exists():
        return None, "no sequence file loaded"
    plan, errors, _raw = read_and_parse(path)
    if plan is None:
        return None, (f"{path.name} is not valid: "
                      f"{errors[0] if errors else 'unreadable'}")
    ptr = pointer(cfg) or {}
    if ptr.get("sha256") == plan.sha256:
        plan.source_path = str(ptr.get("source_path", ""))
        plan.imported_at = str(ptr.get("imported_at", ""))
        plan.file_name = str(ptr.get("file_name", "") or plan.file_name)
    return plan, ""


def sync_drop_folder(cfg) -> ImportResult | None:
    """Import config/pattern_sequences/current.yaml when its contents
    differ from what is already active. This is the no-click route: a
    researcher saves the file into the folder and the next menu screen
    picks it up. Never creates the folder, so a machine that has never
    used a sequence file stays exactly as it was."""
    src = drop_dir(cfg) / DROP_NAME
    try:
        if not src.is_file():
            return None
        raw = src.read_bytes()
    except OSError:
        return None
    if len(raw) <= MAX_BYTES:
        sha = hashlib.sha256(raw).hexdigest()
        ptr = pointer(cfg) or {}
        if ptr.get("sha256") == sha and active_path(cfg).exists():
            return None
    return import_file(src, cfg)


def clear_active(cfg) -> None:
    """Back to the built-in riff. The archive is kept: a study needs
    to be able to say what ran, including after someone cleared it."""
    for p in (active_path(cfg), pointer_path(cfg)):
        try:
            p.unlink(missing_ok=True)
        except OSError as e:
            log.warning("pattern sequence file not cleared (%s): %s", p, e)


def write_templates(cfg) -> list[Path]:
    """Write both templates into the drop folder and return their
    paths. Written from string constants rather than dumped from a
    dict because the comments ARE the documentation: a researcher who
    opens the file should not have to read this module to fill it in."""
    out: list[Path] = []
    folder = drop_dir(cfg)
    folder.mkdir(parents=True, exist_ok=True)
    for name, text in (("template_one_hand.yaml", TEMPLATE_ONE_HAND),
                       ("template_both_hands.yaml", TEMPLATE_BOTH_HANDS)):
        p = folder / name
        _atomic_write(p, text.encode("utf-8"))
        out.append(p)
    return out


# ---- templates -------------------------------------------------------------
_HOW_TO = """\
# Finger Rehab: Muscle Memory sequence file (pattern_file 1)
#
# HOW TO USE
#   1. Copy this file, edit the blocks below, keep the .yaml ending.
#   2. Load it: drag it onto the game window on any menu screen, OR
#      save it as config/pattern_sequences/current.yaml, OR use
#      Load pattern file on the Settings screen.
#   3. It now runs for every Muscle Memory block, every session,
#      until you load another file or press Clear on Settings.
#
# TIMING: gaps_ms is the pause AFTER each press before the next key
#   lights (0 to 5000). Give one number for every item, or one number
#   for the whole block. The list is played the same way on every
#   repeat and in every session; that repetition is what makes the
#   timing learnable, so change it only when you mean to start a new
#   task. Probes should keep the trained block's gaps so that only
#   the order changes.
#
# KINDS: warmup (random, not analysed, at most one, first), random
#   (balanced baseline), seq (the trained riff), probe (an unfamiliar
#   riff of the SAME length; scored against the seq blocks either
#   side of it). Every seq and probe sequence must be the same length
#   and no lane may follow itself.
#
# WHAT THE PARTICIPANT SEES: takes and stars, never the word riff or
#   sequence, unless explicit is true.
"""

TEMPLATE_ONE_HAND = _HOW_TO + """\
#
# LANES (one hand): 1 index, 2 middle, 3 ring, 4 little of the hand
#   picked at setup. Keyboard: right hand J K L ;  left hand F D S A.
# For both hands set hands: both and use 1..4 for the right hand and
#   5..8 for the left hand, index to little.

pattern_file: 1
name: My riff                 # shown on Settings and the game hub, 40 chars max
hands: one                    # one or both
explicit: false               # true = you will tell them the riff; the data is stamped explicit
show_sequence: false          # true (needs explicit true) shows the riff digits during play
timeout_ms: 2000              # how long a lit key waits for its press, 300 to 10000
defaults:
  gaps_ms: 500                # default pause after a press
  rest_after_s: 10            # default rest floor after a block (self-paced past it)

blocks:
  - name: warm
    kind: warmup
    trials: 12

  - name: base
    kind: random
    trials: 32

  - name: riff_1
    kind: seq
    sequence: [2, 4, 1, 3, 4, 2, 3, 1]
    gaps_ms:  [500, 500, 500, 500, 500, 500, 500, 500]
    repeats: 5

  - name: riff_2
    kind: seq
    sequence: [2, 4, 1, 3, 4, 2, 3, 1]
    gaps_ms:  [500, 500, 500, 500, 500, 500, 500, 500]
    repeats: 5

  - name: fresh
    kind: probe
    sequence: [3, 1, 4, 2, 1, 3, 2, 4]
    gaps_ms:  [500, 500, 500, 500, 500, 500, 500, 500]
    repeats: 5

  - name: riff_3
    kind: seq
    sequence: [2, 4, 1, 3, 4, 2, 3, 1]
    gaps_ms:  [500, 500, 500, 500, 500, 500, 500, 500]
    repeats: 5
    rest_after_s: 30
"""

TEMPLATE_BOTH_HANDS = _HOW_TO + """\
#
# LANES (both hands): 1 2 3 4 are the RIGHT hand index to little
#   (keyboard J K L ;) and 5 6 7 8 the LEFT hand index to little
#   (keyboard F D S A). Keep the two hands evenly used inside a seq
#   block or one hand gets more practice than the other.

pattern_file: 1
name: My two-hand riff        # shown on Settings and the game hub, 40 chars max
hands: both                   # one or both
explicit: false               # true = you will tell them the riff; the data is stamped explicit
show_sequence: false          # true (needs explicit true) shows the riff digits during play
timeout_ms: 2000              # how long a lit key waits for its press, 300 to 10000
defaults:
  gaps_ms: 500                # default pause after a press
  rest_after_s: 10            # default rest floor after a block (self-paced past it)

blocks:
  - name: warm
    kind: warmup
    trials: 16

  - name: base
    kind: random
    trials: 32

  - name: riff_1
    kind: seq
    sequence: [1, 5, 2, 6, 3, 7, 4, 8, 1, 6, 2, 7, 3, 8, 4, 5]
    gaps_ms: 500
    repeats: 4

  - name: riff_2
    kind: seq
    sequence: [1, 5, 2, 6, 3, 7, 4, 8, 1, 6, 2, 7, 3, 8, 4, 5]
    gaps_ms: 500
    repeats: 4

  - name: fresh
    kind: probe
    sequence: [5, 1, 6, 2, 7, 3, 8, 4, 6, 1, 7, 2, 8, 3, 5, 4]
    gaps_ms: 500
    repeats: 4

  - name: riff_3
    kind: seq
    sequence: [1, 5, 2, 6, 3, 7, 4, 8, 1, 6, 2, 7, 3, 8, 4, 5]
    gaps_ms: 500
    repeats: 4
    rest_after_s: 30
"""
