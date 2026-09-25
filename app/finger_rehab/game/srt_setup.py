"""Setups for the lab's serial reaction time task (the srt mode).

A setup is the part of the task the lab changes between groups: the
timing group, the learning-block interval and the sequence. Everything
else (48 random trials either side, 8 learning blocks of 10 repeats,
the 100 ms flash, the 2.5 s deadline) is the lab's protocol and lives
in the srt block of config/default.yaml.

The setups file keeps the current setup and any the researcher saved,
so a group's timing survives between participants and between
launches. It lives beside the sessions (config/srt_setups.json under
the data root) rather than in user_settings.yaml, because the lab
build loads eeg_lab.yaml over the defaults and never reads
user_settings.yaml.

Rules copied from the lab's script (archive/Webler EEG past program/
SRT_Sequence_learning_Final_v2.py):

- The lab sequence is v n b v m n b m v n, squares 1-3-2-1-4-3-2-4-1-3
  counted left to right.
- Random blocks draw each square equally often (12 each in 48) with no
  square twice in a row, from the same shuffle-and-pick routine.
- Constant: every interval is the learning interval. Cyclical: the
  intervals follow the sequence position, 250 500 750 three times then
  500. Random: each run of ten is 250 x3, 500 x4 and 750 x3, shuffled.
  All three average 500 ms.

The three groups are the random, constant and response-locked RSI
conditions of Shin (2008, Psychological Research), who found the order
learnt equally under all three and the predictable timing only making
responses faster; others disagree (research file, Section 6).

What is new here is that the learning interval can move. Cyclical and
random then scale with it (half, equal and one and a half times the
interval) so every group still averages the chosen interval, which is
what made the lab's three groups comparable. A sequence of another
length keeps the same rule: the half, equal, one and a half cycle runs
over whole threes and any positions left over sit at the interval.
"""
from __future__ import annotations

import json
import logging
import os
import random
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# The lab's four keys, left to right. The CSVs the lab's analysis
# reads name squares by these letters, so the exports keep them.
LETTERS = ("v", "b", "n", "m")

# The lab sequence, squares counted 1 to 4 from the left.
LAB_SEQUENCE = (1, 3, 2, 1, 4, 3, 2, 4, 1, 3)

GROUPS = ("constant", "cyclical", "random")

# Interval ratios for the cyclical and random groups. At 500 ms these
# are the lab's 250, 500 and 750.
SHORT_RATIO = 0.5
LONG_RATIO = 1.5

ISI_MIN_MS = 200
ISI_MAX_MS = 2000
SEQ_MIN_LEN = 4
SEQ_MAX_LEN = 16

MUSICAL_EXPERIENCE = (
    "0 - no experience",
    "1 - less than 6 months",
    "2 - 6 months to 1 year",
    "3 - 1 to 2 years",
    "4 - 2 to 3 years",
    "5 - 3+ years",
)


def sequence_text(seq, letters: bool = False) -> str:
    """1-3-2-1-4 style, or v n b v m with letters=True."""
    if letters:
        return " ".join(LETTERS[s - 1] for s in seq)
    return "-".join(str(s) for s in seq)


def parse_sequence(text: str) -> tuple[tuple[int, ...] | None, str]:
    """Read a typed sequence: digits 1 to 4 or the letters v b n m,
    with or without spaces, commas or dashes between them. Returns
    (sequence, "") or (None, why)."""
    raw = re.sub(r"[\s,\-/.]+", "", str(text or "").lower())
    if not raw:
        return None, "Type the sequence, for example 1321432413"
    out = []
    for ch in raw:
        if ch in "1234":
            out.append(int(ch))
        elif ch in LETTERS:
            out.append(LETTERS.index(ch) + 1)
        else:
            return None, f"'{ch}' is not a square: use 1 to 4 or v b n m"
    seq = tuple(out)
    why = sequence_problem(seq)
    return (None, why) if why else (seq, "")


def sequence_problem(seq) -> str:
    """Why a sequence cannot run, or "".

    All four squares must appear, or the learning blocks become a
    three-choice task against four-choice random blocks and the RT
    difference reads fewer alternatives as learning. No square may
    follow itself, including last to first where the sequence wraps,
    because a repeat is primed and the lab's random blocks never
    repeat either."""
    try:
        seq = tuple(int(s) for s in seq)
    except (TypeError, ValueError):
        return "The sequence holds something that is not a square"
    if not SEQ_MIN_LEN <= len(seq) <= SEQ_MAX_LEN:
        return (f"Use {SEQ_MIN_LEN} to {SEQ_MAX_LEN} items "
                f"(this one has {len(seq)})")
    if any(s not in (1, 2, 3, 4) for s in seq):
        return "Squares are numbered 1 to 4"
    if set(seq) != {1, 2, 3, 4}:
        missing = sorted({1, 2, 3, 4} - set(seq))
        return ("Every square must appear; missing "
                + ", ".join(str(m) for m in missing))
    for i in range(len(seq)):
        if seq[i] == seq[i - 1]:
            where = ("the last and the first" if i == 0
                     else f"items {i} and {i + 1}")
            return f"No square twice in a row ({where} match)"
    return ""


def cyclical_pattern(isi_ms: int, length: int) -> list[int]:
    """The interval after each sequence position in the cyclical
    group. For the lab sequence at 500 ms: 250 500 750 250 500 750
    250 500 750 500, the script's CYCLICAL_ISI."""
    whole = 3 * (length // 3)
    ratios = (SHORT_RATIO, 1.0, LONG_RATIO)
    return [int(round(isi_ms * (ratios[i % 3] if i < whole else 1.0)))
            for i in range(length)]


def random_chunk(isi_ms: int, length: int, rng: random.Random) -> list[int]:
    """One shuffled run of intervals for the random group: 3 short, 4
    equal and 3 long in ten, as in the script, scaled to the length.
    Short and long counts match so the run averages isi_ms."""
    n_short = int(length * 0.3 + 0.5)
    n_mid = length - 2 * n_short
    chunk = ([int(round(isi_ms * SHORT_RATIO))] * n_short
             + [int(isi_ms)] * n_mid
             + [int(round(isi_ms * LONG_RATIO))] * n_short)
    rng.shuffle(chunk)
    return chunk


def isi_list(group: str, isi_ms: int, n_trials: int, seq_len: int,
             rng: random.Random) -> list[int]:
    """The interval after each trial of a learning block, the script's
    generate_isi_list with the interval and length as inputs."""
    if group == "cyclical":
        pattern = cyclical_pattern(isi_ms, seq_len)
        return [pattern[i % seq_len] for i in range(n_trials)]
    if group == "random":
        out: list[int] = []
        while len(out) < n_trials:
            out.extend(random_chunk(isi_ms, seq_len, rng))
        return out[:n_trials]
    return [int(isi_ms)] * n_trials


def random_targets(n_trials: int, rng: random.Random,
                   squares: int = 4) -> list[int]:
    """Squares (1-based) for a random block: equal counts, the spare
    trials on randomly chosen squares, never the same square twice in
    a row. The script's generate_random_sequence, step for step, on a
    seeded generator so a block can be rebuilt from its seed."""
    fingers = list(range(1, squares + 1))
    n_each = n_trials // squares
    remainder = n_trials % squares
    pool = fingers * n_each + rng.sample(fingers, remainder)
    for _ in range(200):
        result: list[int] = []
        remaining = list(pool)
        rng.shuffle(remaining)
        ok = True
        while remaining:
            cands = [i for i, x in enumerate(remaining)
                     if not result or x != result[-1]]
            if not cands:
                ok = False
                break
            result.append(remaining.pop(rng.choice(cands)))
        if ok:
            return result
    raise RuntimeError("Could not draw a random block without repeats")


def recall_scores(recalled, seq) -> dict:
    """Three scores for a recalled order against the repeating
    sequence.

    positional: items matching the sequence position by position from
    position 1, the script's own 'correct' column. It undercounts a
    right order started mid-cycle, which scores 0 to 3 of 10.
    triplet: the share of the recalled runs of three that occur
    anywhere in the repeating sequence (the triplet scoring of
    Destrebecqz et al. 2005), blind to where the recall started.
    longest_run: the longest stretch that follows the repeating
    sequence from any point in it.

    Chance, from 100,000 random 10-item recalls of the lab sequence
    (research file Section 4): positional 2.5 (95th percentile 5);
    triplet 0.28 with no key repeated (95th percentile about 0.63);
    longest run 3 to 3.5 items (95th percentile 4 to 5)."""
    rec = [int(x) for x in recalled]
    seq = [int(x) for x in seq]
    n = len(seq)
    out = {"positional": sum(1 for a, b in zip(rec, seq) if a == b),
           "triplet": None, "longest_run": 0}
    if n >= 3 and len(rec) >= 3:
        known = {tuple(seq[(i + k) % n] for k in range(3))
                 for i in range(n)}
        runs = [tuple(rec[i:i + 3]) for i in range(len(rec) - 2)]
        out["triplet"] = round(sum(1 for t in runs if t in known)
                               / len(runs), 3)
    best = 0
    for start in range(len(rec)):
        for off in range(n):
            k = 0
            while (start + k < len(rec)
                   and rec[start + k] == seq[(off + k) % n]):
                k += 1
            best = max(best, k)
    out["longest_run"] = best
    return out


@dataclass(frozen=True)
class SRTSetup:
    name: str
    group: str = "constant"
    isi_ms: int = 500
    sequence: tuple[int, ...] = LAB_SEQUENCE

    def problem(self) -> str:
        if self.group not in GROUPS:
            return f"Unknown timing group '{self.group}'"
        if not ISI_MIN_MS <= int(self.isi_ms) <= ISI_MAX_MS:
            return (f"Interval must be {ISI_MIN_MS} to {ISI_MAX_MS} ms")
        return sequence_problem(self.sequence)

    @property
    def is_lab_sequence(self) -> bool:
        return tuple(self.sequence) == LAB_SEQUENCE

    def summary(self) -> str:
        """One line for the setup screen and the logs."""
        seq = ("lab sequence" if self.is_lab_sequence
               else f"custom sequence of {len(self.sequence)}")
        return f"{self.group.capitalize()}, {int(self.isi_ms)} ms, {seq}"

    def to_dict(self) -> dict:
        return {"name": self.name, "group": self.group,
                "isi_ms": int(self.isi_ms),
                "sequence": [int(s) for s in self.sequence]}

    @classmethod
    def from_dict(cls, d) -> "SRTSetup | None":
        """A setup from the file, or None when the entry is unusable
        (a hand-edited file must never stop the task opening)."""
        if not isinstance(d, dict):
            return None
        try:
            setup = cls(name=str(d.get("name") or "").strip()[:40],
                        group=str(d.get("group") or "constant"),
                        isi_ms=int(d.get("isi_ms", 500)),
                        sequence=tuple(int(s) for s in
                                       d.get("sequence") or LAB_SEQUENCE))
        except (TypeError, ValueError):
            return None
        if not setup.name or setup.problem():
            return None
        return setup


# Ready-made setups for the lab's three groups. Always listed, never
# deleted, so a fresh install can run any group with one click.
BUILT_INS = (
    SRTSetup("Lab constant 500", "constant", 500, LAB_SEQUENCE),
    SRTSetup("Lab cyclical 500", "cyclical", 500, LAB_SEQUENCE),
    SRTSetup("Lab random 500", "random", 500, LAB_SEQUENCE),
)
DEFAULT_SETUP = BUILT_INS[0]


def store_path(cfg) -> Path:
    """srt.setups_file when set (tests point it at a temp folder),
    else config/srt_setups.json under the data root."""
    custom = cfg.get("srt.setups_file", None) if cfg is not None else None
    if custom:
        return Path(str(custom)).expanduser()
    from ..config import USER_ROOT
    return USER_ROOT / "config" / "srt_setups.json"


class SetupStore:
    """The current setup plus the saved ones, kept in one JSON file.

    Every change is written straight away (atomic replace), so the
    setup in force is the one on disk, whichever screen or build
    starts the next block."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self.current: SRTSetup = DEFAULT_SETUP
        self.saved: list[SRTSetup] = []
        self.load()

    def load(self) -> None:
        self.current = DEFAULT_SETUP
        self.saved = []
        if not self.path.is_file():
            return
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            log.warning("Could not read %s (%s); using the lab setup",
                        self.path, e)
            return
        if not isinstance(raw, dict):
            return
        cur = SRTSetup.from_dict(raw.get("current"))
        if cur is not None:
            self.current = cur
        names = {b.name.lower() for b in BUILT_INS}
        for item in raw.get("saved") or []:
            s = SRTSetup.from_dict(item)
            if s is not None and s.name.lower() not in names:
                names.add(s.name.lower())
                self.saved.append(s)

    def save(self) -> None:
        payload = {"version": 1, "current": self.current.to_dict(),
                   "saved": [s.to_dict() for s in self.saved]}
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_name(self.path.name + ".tmp")
            tmp.write_text(json.dumps(payload, indent=2) + "\n",
                           encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError as e:
            log.warning("Could not save the SRT setups to %s: %s",
                        self.path, e)

    def all(self) -> list[SRTSetup]:
        return list(BUILT_INS) + list(self.saved)

    def find(self, name: str) -> SRTSetup | None:
        key = str(name or "").strip().lower()
        for s in self.all():
            if s.name.lower() == key:
                return s
        return None

    def is_built_in(self, name: str) -> bool:
        key = str(name or "").strip().lower()
        return any(b.name.lower() == key for b in BUILT_INS)

    def set_current(self, setup: SRTSetup) -> str:
        why = setup.problem()
        if why:
            return why
        self.current = setup
        self.save()
        return ""

    def save_as(self, name: str, setup: SRTSetup) -> str:
        """Save `setup` under `name` (replacing a saved one of the same
        name) and make it current. Returns "" or why not."""
        name = str(name or "").strip()[:40]
        if not name:
            return "Give the setup a name"
        if self.is_built_in(name):
            return "That name belongs to a lab setup; pick another"
        named = SRTSetup(name, setup.group, int(setup.isi_ms),
                         tuple(setup.sequence))
        why = named.problem()
        if why:
            return why
        self.saved = [s for s in self.saved
                      if s.name.lower() != name.lower()] + [named]
        self.current = named
        self.save()
        return ""

    def delete(self, name: str) -> str:
        if self.is_built_in(name):
            return "Lab setups cannot be deleted"
        before = len(self.saved)
        self.saved = [s for s in self.saved
                      if s.name.lower() != str(name).strip().lower()]
        if len(self.saved) == before:
            return "No saved setup by that name"
        self.save()
        return ""


def protocol_counts(cfg) -> dict:
    """The lab's protocol constants from the srt config block."""
    g = (lambda k, d: cfg.get(f"srt.{k}", d)) if cfg is not None \
        else (lambda k, d: d)
    return {
        "random_trials": int(g("random_trials", 48)),
        "learning_blocks": int(g("learning_blocks", 8)),
        "learning_reps": int(g("learning_reps", 10)),
        "random_isi_ms": int(g("random_isi_ms", 500)),
        "first_wait_ms": int(g("first_wait_ms", 1000)),
        "feedback_ms": int(g("feedback_ms", 200)),
    }


def estimate_minutes(setup: SRTSetup, counts: dict,
                     mean_rt_ms: float = 420.0,
                     message_s: float = 5.0,
                     recall_s: float = 45.0) -> float:
    """Rough session length for the setup screen. Each trial is its
    interval plus a typical response; practice adds its 200 ms
    feedback; every block starts with the 1 s wait; fourteen SPACE
    screens and the recall take the rest. The lab setup comes to
    about 15 to 16 minutes, the lab's own figure."""
    n_rand = counts["random_trials"]
    n_learn = (counts["learning_blocks"] * counts["learning_reps"]
               * len(setup.sequence))
    rt = mean_rt_ms / 1000.0
    rand_isi = counts["random_isi_ms"] / 1000.0
    total = n_rand * (rand_isi + rt + counts["feedback_ms"] / 1000.0)
    total += n_learn * (int(setup.isi_ms) / 1000.0 + rt)
    total += n_rand * (rand_isi + rt)
    total += (counts["learning_blocks"] + 2) * counts["first_wait_ms"] / 1000.0
    total += (counts["learning_blocks"] + 6) * message_s + recall_s
    return total / 60.0
