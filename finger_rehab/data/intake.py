"""Participant intake: study codes, the next free code, the visit
number, the counterbalancing cell, and the carry-over of hand size
and pickers from an identity's last game.

The login screen asks for a participant code or a name. A study
participant is a code (P01, P02, ...) and never a name: the code keys
every session folder, the sessions index, the notebook's who column
and the hidden sequences in pattern, buzz hunt and echo (all three
seed from the trimmed, case-folded identity, so P01 at visit 1 and
P01 at visit 2 get the same trained material while P01 and P1 would
not). Everything here is pure functions over the sessions tree so it
can be tested without a screen and reused by the analysis.

Where the facts come from. A game folder is named
<participant>_<HHMMSS>_<mode> inside a YYYY-MM-DD day folder
(data/logger.SessionPaths). Reading the folder names is enough to know
which codes exist and on which days they played, and it costs no file
reads, which matters on a cloud-synced tree where every open is slow.
Names with spaces were written with underscores, so for a NAME the
day count is approximate; for a code it is exact, and codes are the
only identity the study path uses.
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path


# A study code: one to three letters then two to four digits. P01 to
# P32 for the healthy baseline study; the prefix is free so a second
# cohort (S01, HC01) can share the tree without colliding.
CODE_RE = re.compile(r"^([A-Za-z]{1,3})(\d{2,4})$")
DEFAULT_PREFIX = "P"
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
GAME_RE = re.compile(r"^(.*)_(\d{6})(?:_(.*))?$")

# Counterbalancing cells by code number mod 4, from the study design
# (docs/research/healthy_baseline_study.txt, Section 2.2): two mode
# orders crossed with two hand orders, seven per cell at n = 28.
#   1: order A, dominant hand first
#   2: order B, dominant hand first
#   3: order A, non-dominant hand first
#   0: order B, non-dominant hand first
CELLS: dict[int, tuple[str, str]] = {
    1: ("A", "dominant"),
    2: ("B", "dominant"),
    3: ("A", "non_dominant"),
    0: ("B", "non_dominant"),
}


def parse_code(text: str | None) -> tuple[str, int] | None:
    """(prefix, number) for a study code, or None for anything else
    (a name, blank, NA)."""
    s = str(text or "").strip()
    m = CODE_RE.match(s)
    if not m:
        return None
    return m.group(1).upper(), int(m.group(2))


def is_study_code(text: str | None) -> bool:
    return parse_code(text) is not None


def normalise_code(text: str | None) -> str:
    """The canonical spelling of a code: upper-case prefix, digits as
    typed. p01 becomes P01; a name comes back trimmed and unchanged.
    The digits are kept verbatim because P01 and P001 seed different
    hidden sequences, and silently rewriting one to the other would
    split a participant's data in two."""
    s = str(text or "").strip()
    m = CODE_RE.match(s)
    if not m:
        return s
    return m.group(1).upper() + m.group(2)


def format_code(prefix: str, number: int, width: int = 2) -> str:
    return f"{prefix.upper()}{number:0{width}d}"


def scan_participants(data_dir: Path | str | None) -> dict[str, set[str]]:
    """Every participant identity in the sessions tree, mapped to the
    days it played on, read from folder names alone.

    Missing or unreadable trees are an empty answer, never an error:
    this runs on the login screen, where a broken folder should cost
    nothing more than an empty suggestion.
    """
    out: dict[str, set[str]] = {}
    if not data_dir:
        return out
    root = Path(data_dir)
    try:
        if not root.is_dir():
            return out
        day_dirs = [d for d in root.iterdir()
                    if d.is_dir() and DAY_RE.match(d.name)]
    except OSError:
        return out
    for day_dir in day_dirs:
        try:
            games = [g for g in day_dir.iterdir() if g.is_dir()]
        except OSError:
            continue
        for game in games:
            m = GAME_RE.match(game.name)
            if not m:
                continue
            who = m.group(1)
            if not who:
                continue
            out.setdefault(who, set()).add(day_dir.name)
    return out


def known_codes(data_dir: Path | str | None,
                prefix: str = DEFAULT_PREFIX) -> dict[str, set[str]]:
    """The study codes with the given prefix already in the tree,
    canonical spelling, mapped to their days."""
    want = prefix.upper()
    out: dict[str, set[str]] = {}
    for who, days in scan_participants(data_dir).items():
        parsed = parse_code(who)
        if parsed is None or parsed[0] != want:
            continue
        out.setdefault(normalise_code(who), set()).update(days)
    return out


def suggest_next_code(data_dir: Path | str | None,
                      prefix: str = DEFAULT_PREFIX) -> str:
    """The next unused code: one past the highest number on disk, or
    P01 on an empty tree. Gaps are not refilled on purpose: a code
    that was assigned and never played (a no-show) must stay retired,
    or two people could end up sharing it."""
    highest = 0
    width = 2
    for code in known_codes(data_dir, prefix):
        parsed = parse_code(code)
        if parsed is None:
            continue
        _p, n = parsed
        highest = max(highest, n)
        width = max(width, len(code) - len(prefix))
    return format_code(prefix, highest + 1, width)


def suggest_visit(data_dir: Path | str | None, participant: str | None,
                  today: str | None = None) -> int:
    """The visit number this login most likely is: one more than the
    number of earlier DAYS this identity has played on.

    A session is one person on one day (the notebook's rule), so days
    are visits. Today is excluded so relaunching the app mid-visit
    (a crash, a restart between blocks) keeps suggesting the visit
    that is under way rather than the next one.
    """
    who = normalise_code(participant)
    if not who or who == "NA":
        return 1
    today = today or time.strftime("%Y-%m-%d")
    days: set[str] = set()
    for name, played in scan_participants(data_dir).items():
        if normalise_code(name) == who:
            days.update(played)
    days.discard(today)
    return len(days) + 1


def cell_for(participant: str | None) -> dict:
    """The counterbalancing cell for an identity.

    A study code uses its number mod 4, as the design specifies, so
    the RA can read the cell off the code. A name has no number, so it
    hashes (SHA-256 of the trimmed, case-folded name, the same seed
    rule the hidden sequences use) and the hash takes the number's
    place. Either way the cell is fixed for the identity across visits,
    which is what the test-retest design needs.
    """
    parsed = parse_code(participant)
    if parsed is not None:
        n = parsed[1]
        source = "code"
    else:
        s = str(participant or "").strip().casefold()
        digest = hashlib.sha256(s.encode("utf-8")).digest()
        n = int.from_bytes(digest[:4], "big")
        source = "hash"
    order, hand_first = CELLS[n % 4]
    return {
        "index": n % 4,
        "mode_order": order,
        "hand_first": hand_first,
        "source": source,
    }


# Intake fields worth carrying from one visit to the next. Hand size
# does not change between visits, the main hand and sex do not either,
# so an RA should not have to look them up on the intake sheet twice.
# Age is left out on purpose: it is part of the match key for a name.
CARRY_FIELDS = ("hand_length_mm", "hand_breadth_mm", "dominant_hand",
                "sex")


def _folder_identity(text: str) -> str:
    """How a typed identity appears in a game folder name: the logger
    writes spaces as underscores (data/logger.SessionPaths)."""
    return normalise_code(text).replace("/", "_").replace(" ", "_")


def previous_intake(data_dir: Path | str | None, participant: str | None,
                    age: str | None = None) -> dict | None:
    """The carry-over intake of this identity's most recent earlier
    game, or None when there is none.

    A study code matches on the code alone. A name is not unique, so a
    name matches only when the age typed matches the age recorded:
    two Sams of different ages stay two people, and the wrong hand
    size never lands on the wrong person. Match failures cost
    nothing; only folders belonging to the identity are opened, so a
    large tree of other people is never read.

    Returns the CARRY_FIELDS that were recorded (empty ones skipped),
    plus "day" (the folder day it came from) and "who". Newest game
    first, by folder day and clock, so a corrected hand size on a
    later visit wins over the first entry.
    """
    who = normalise_code(participant)
    if not who or who == "NA" or not data_dir:
        return None
    root = Path(data_dir)
    try:
        if not root.is_dir():
            return None
        day_dirs = sorted((d for d in root.iterdir()
                           if d.is_dir() and DAY_RE.match(d.name)),
                          key=lambda d: d.name, reverse=True)
    except OSError:
        return None
    coded = is_study_code(who)
    want_folder = _folder_identity(who)
    want_age = str(age or "").strip()
    for day_dir in day_dirs:
        try:
            games = sorted((g for g in day_dir.iterdir() if g.is_dir()),
                           key=lambda g: g.name, reverse=True)
        except OSError:
            continue
        for game in games:
            m = GAME_RE.match(game.name)
            if not m:
                continue
            folder_who = m.group(1)
            if coded:
                if normalise_code(folder_who) != who:
                    continue
            elif folder_who.casefold() != want_folder.casefold():
                continue
            meta_path = game / "metadata.json"
            try:
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeDecodeError):
                continue
            if not isinstance(meta, dict):
                continue
            if not coded:
                # A name: the recorded name and age both have to match.
                rec_who = str(meta.get("participant") or "").strip()
                rec_age = str(meta.get("age") or "").strip()
                if rec_who.casefold() != who.casefold():
                    continue
                if rec_age != want_age:
                    continue
            found = {}
            for key in CARRY_FIELDS:
                val = str(meta.get(key) or "").strip()
                if val:
                    found[key] = val
            if not found:
                # An older game with no intake recorded; keep looking
                # back for one that has it.
                continue
            found["day"] = day_dir.name
            found["who"] = str(meta.get("participant") or who)
            return found
    return None
