"""Option sets for the syllables choice task: one written syllable
that is right and three that are wrong for a reason.

WHY FOILS ARE BUILT TO A RULE. A wrong option drawn at random can be
rejected on a single letter, so a child clears the set without reading
the target. The confusions that matter are the ones poor readers
actually make, and each has a study behind it:

- vowel identity. Vowel letters carry the least consistent mappings in
  English (Ziegler and Goswami 2005, psycholinguistic grain size
  theory), and vowel errors are the common phonologically plausible
  error class in dyslexic spelling. Foil F3 keeps the onset and the
  coda and moves the vowel (ban -> bin, bun, ben);
- onset and coda consonants. Bruck and Treiman (1990) found dyslexic
  children and younger typical readers drop the second consonant of
  an initial cluster. F2 swaps the onset, F7 swaps or adds the coda;
- reversible letters. Terepocki, Kruk and Willows (2002) found ten
  year olds with reading disability made more b/d, p/q orientation
  errors than average readers across detection, recognition and
  production. F4 flips one of b/d, p/q, n/u, m/w;
- letter position. Kohnen, Nickels, Castles, Friedmann and McArthur
  (2012) describe English children whose reading error is letter
  migration (slime read as smile); Kirkby et al. (2025) found dyslexic
  readers less sensitive to transposed letters. F5 swaps two adjacent
  letters;
- order inside the word. F6 offers a syllable that belongs to this
  word at a DIFFERENT position, which tests that the child is tracking
  where they are in the word (the word strip at the top scaffolds it);
- spelling knowledge. F8 is the pseudohomophone (ka for ca), which
  can only be rejected by knowing how the word is written. Off by
  default; the hardest rung.

F1 is the far foil: a real chunk from the bank that shares nothing
much with the target. It is the entry rung, where the child is
learning the task itself rather than the contrast.

WHAT KEEPS A FOIL LEGAL (every generated string is checked):
not the target, not another syllable of this word unless it is F6,
plain a-z, one to five letters, at least one vowel letter (the Year 1
curriculum rule AC9E1LY12), and every letter pair in it must occur
somewhere in the bank's own syllable inventory. That last test is a
cheap stand-in for a phonotactics library: it keeps "psi" and "tlo"
out without anybody writing English phonotactics down. A generator
that cannot produce a legal distinct foil in 20 tries falls back to
another kind, and finally to F1; the kind that is LOGGED is the kind
actually produced, so the notebook's confusion chart cannot credit a
foil type with a capture it never made.

THE DRAW IS SEEDED. Every random choice here comes from the caller's
Random, which is the mode's block seed, so a seed replays a block's
option sets exactly. Nothing in this module touches pygame, the
engine or the clock: it is pure text, which is what makes it testable
2,000 draws at a time.

NO LANE INFORMATION LEAKS. The target lane is drawn by the same
least-cued deficit rule the old sliding window used, so every finger
takes its turn as the answer across a block, and the draw never puts
the target on the same lane three sets running. Nothing else about the
set (its kinds, its order) correlates with the answer: the foils fill
the remaining lanes in random order.
"""
from __future__ import annotations

import random
from dataclasses import dataclass

VOWEL_LETTERS = frozenset("aeiouy")
# Vowel digraphs swap as a unit, so "beach" does not become "bech".
VOWEL_DIGRAPHS = ("ea", "ee", "oo", "ai", "ou", "oa", "ie", "au",
                  "ay", "oy", "ow", "ei", "oi", "ue")
# The onsets F2 draws from: single consonants plus the clusters an
# Australian child meets in print. Kept as a fixed list rather than
# mined from the bank so a rare split cannot introduce a cluster no
# child would read.
ONSETS = ("b", "c", "d", "f", "g", "h", "j", "k", "l", "m", "n", "p",
          "r", "s", "t", "v", "w", "y", "z",
          "bl", "br", "cl", "cr", "dr", "fl", "fr", "gl", "gr", "pl",
          "pr", "sc", "sk", "sl", "sm", "sn", "sp", "st", "sw", "tr",
          "tw", "ch", "sh", "th", "wh")
CODAS = ("b", "ck", "d", "f", "g", "l", "ll", "m", "n", "ng", "p",
         "r", "s", "ss", "t", "sh", "ch", "th", "nd", "nt", "st",
         "mp", "lk", "sk", "ft", "lt", "rt", "rd", "x")
REVERSALS = {"b": "d", "d": "b", "p": "q", "q": "p",
             "n": "u", "u": "n", "m": "w", "w": "m"}

FOIL_KINDS = ("F1", "F2", "F3", "F4", "F5", "F6", "F7", "F8")
TARGET = "target"

# Which three foil kinds a rung asks for, before they are shuffled
# into lanes. Rung 1 is three far foils (learn the task), rung 8 is
# three near ones (reversal, transposition, and the word's own other
# syllable).
RUNG_SCHEDULE: dict[int, tuple[str, str, str]] = {
    1: ("F1", "F1", "F1"),
    2: ("F1", "F1", "F2"),
    3: ("F1", "F2", "F3"),
    4: ("F2", "F3", "F7"),
    5: ("F2", "F3", "F4"),
    6: ("F3", "F4", "F6"),
    7: ("F3", "F4", "F5"),
    8: ("F4", "F5", "F6"),
}
# Where a generator goes when it cannot make a legal foil. Every chain
# ends at F1, which can always be satisfied from the bank.
FALLBACK: dict[str, str] = {
    "F2": "F1", "F3": "F1", "F4": "F3", "F5": "F7",
    "F6": "F2", "F7": "F3", "F8": "F3",
}
# Tries per generator before the fallback. Twenty is generous: the
# vowel and onset swaps have well under twenty candidates each, so
# this only ever bites on the near foils.
MAX_TRIES = 20
MIN_RUNG, MAX_RUNG = 1, 8
N_OPTIONS = 4


@dataclass(frozen=True)
class Option:
    """One falling tile: what it says, which finger answers it, and
    what kind of wrong it is (or "target")."""
    text: str
    lane: int
    kind: str


@dataclass(frozen=True)
class OptionSet:
    """The four tiles for one syllable of one word."""
    word: str
    pos: int
    target: str
    options: tuple[Option, ...]
    target_lane: int
    rung: int

    def option_for_lane(self, lane: int) -> Option | None:
        for o in self.options:
            if o.lane == lane:
                return o
        return None

    def kind_for_lane(self, lane: int) -> str | None:
        o = self.option_for_lane(lane)
        return o.kind if o is not None else None


class Inventory:
    """The bank's own syllable material: which chunks exist, which
    letter pairs occur inside them, and which codas are actually used.
    Built once per block from the loaded word bank."""

    def __init__(self, syllable_lists) -> None:
        chunks: set[str] = set()
        for syls in syllable_lists:
            for s in syls:
                s = str(s).lower()
                if s.isalpha() and s.isascii():
                    chunks.add(s)
        self.chunks: tuple[str, ...] = tuple(sorted(chunks))
        bigrams: set[str] = set()
        for c in self.chunks:
            for i in range(len(c) - 1):
                bigrams.add(c[i:i + 2])
        self.bigrams: frozenset[str] = frozenset(bigrams)
        self.by_length: dict[int, tuple[str, ...]] = {}
        for c in self.chunks:
            self.by_length.setdefault(len(c), tuple())
        for n in list(self.by_length):
            self.by_length[n] = tuple(c for c in self.chunks
                                      if len(c) == n)

    def pronounceable(self, text: str) -> bool:
        """Every letter pair in `text` occurs somewhere in the bank's
        chunks. A one-letter string passes by construction."""
        return all(text[i:i + 2] in self.bigrams
                   for i in range(len(text) - 1))


# ---- letter helpers ------------------------------------------------------

def vowel_span(text: str) -> tuple[int, int] | None:
    """(start, end) of the first vowel unit: a digraph if one starts
    there, otherwise a single vowel letter. None when the chunk has no
    vowel letter at all (the bank forbids that, but a generated string
    can lose one)."""
    for i, ch in enumerate(text):
        if ch in VOWEL_LETTERS:
            two = text[i:i + 2]
            if two in VOWEL_DIGRAPHS:
                return i, i + 2
            return i, i + 1
    return None


def split_onset(text: str) -> tuple[str, str]:
    """(leading consonants, the rest). An empty onset is legal:
    "ap" and "e" both start on their vowel."""
    v = vowel_span(text)
    if v is None:
        return text, ""
    return text[:v[0]], text[v[0]:]


def split_coda(text: str) -> tuple[str, str]:
    """(everything up to the final consonant run, that run). The run
    is empty for a chunk ending in a vowel."""
    i = len(text)
    while i > 0 and text[i - 1] not in VOWEL_LETTERS:
        i -= 1
    return text[:i], text[i:]


def is_legal(text: str, target: str, word_syllables, kind: str,
             inv: Inventory) -> bool:
    """The legality rules in the module docstring, in the order they
    are cheapest to check."""
    if not text or text == target:
        return False
    if not (1 <= len(text) <= 5):
        return False
    if not (text.isalpha() and text.isascii() and text.islower()):
        return False
    if not (set(text) & VOWEL_LETTERS):
        return False
    if kind != "F6" and text in tuple(word_syllables):
        return False
    return inv.pronounceable(text)


# ---- the generators ------------------------------------------------------
# Each returns a candidate string or None. Legality is checked by the
# caller, which also handles the retry and the fallback, so a
# generator can stay a one-liner about its own confusion.

def _f1_far(target: str, syls, pos: int, inv: Inventory,
            rng: random.Random) -> str | None:
    """A real chunk that shares little with the target: different
    first letter, different vowel letters, length within one."""
    t_v = set(target) & VOWEL_LETTERS
    n = len(target)
    pool = [c for c in inv.chunks
            if abs(len(c) - n) <= 1
            and c[0] != target[0]
            and not (set(c) & VOWEL_LETTERS & t_v)]
    return rng.choice(pool) if pool else None


def _f2_onset(target: str, syls, pos: int, inv: Inventory,
              rng: random.Random) -> str | None:
    onset, rest = split_onset(target)
    if not rest:
        return None
    pool = [o for o in ONSETS if o != onset]
    return rng.choice(pool) + rest if pool else None


def _f3_vowel(target: str, syls, pos: int, inv: Inventory,
              rng: random.Random) -> str | None:
    span = vowel_span(target)
    if span is None:
        return None
    a, b = span
    cur = target[a:b]
    if len(cur) == 2:
        pool = [d for d in VOWEL_DIGRAPHS if d != cur]
    else:
        pool = [v for v in "aeiou" if v != cur]
    if not pool:
        return None
    return target[:a] + rng.choice(pool) + target[b:]


def _f4_reversal(target: str, syls, pos: int, inv: Inventory,
                 rng: random.Random) -> str | None:
    for i, ch in enumerate(target):
        if ch in REVERSALS:
            return target[:i] + REVERSALS[ch] + target[i + 1:]
    return None


def _f5_transpose(target: str, syls, pos: int, inv: Inventory,
                  rng: random.Random) -> str | None:
    """Swap one adjacent pair. Consonant pairs first (tur -> tru is
    the migration error the literature names), then any pair."""
    pairs = [i for i in range(len(target) - 1)
             if target[i] != target[i + 1]]
    clusters = [i for i in pairs
                if target[i] not in VOWEL_LETTERS
                and target[i + 1] not in VOWEL_LETTERS]
    for i in list(clusters) + [p for p in pairs if p not in clusters]:
        cand = (target[:i] + target[i + 1] + target[i]
                + target[i + 2:])
        if is_legal(cand, target, syls, "F5", inv):
            return cand
    return None


def _f6_other_position(target: str, syls, pos: int, inv: Inventory,
                       rng: random.Random) -> str | None:
    others = [s for i, s in enumerate(syls) if i != pos and s != target]
    return rng.choice(others) if others else None


def _f7_coda(target: str, syls, pos: int, inv: Inventory,
             rng: random.Random) -> str | None:
    head, coda = split_coda(target)
    if not coda:
        # A chunk ending in a vowel gets a coda instead (ba -> bat).
        return target + rng.choice(CODAS)
    pool = [c for c in CODAS if c != coda]
    return head + rng.choice(pool) if pool else None


_HOMOPHONE_MAP = (("ph", "f"), ("f", "ph"))


def _f8_homophone(target: str, syls, pos: int, inv: Inventory,
                  rng: random.Random) -> str | None:
    """Same sound, wrong spelling: c/k before a, o, u; s/c before
    e, i; f/ph anywhere."""
    cands: list[str] = []
    for i, ch in enumerate(target):
        nxt = target[i + 1] if i + 1 < len(target) else ""
        if ch == "c" and nxt in "aou":
            cands.append(target[:i] + "k" + target[i + 1:])
        elif ch == "k" and nxt in "aou":
            cands.append(target[:i] + "c" + target[i + 1:])
        elif ch == "s" and nxt in "ei":
            cands.append(target[:i] + "c" + target[i + 1:])
        elif ch == "c" and nxt in "ei":
            cands.append(target[:i] + "s" + target[i + 1:])
    for a, b in _HOMOPHONE_MAP:
        if a in target:
            cands.append(target.replace(a, b, 1))
    return rng.choice(cands) if cands else None


GENERATORS = {
    "F1": _f1_far,
    "F2": _f2_onset,
    "F3": _f3_vowel,
    "F4": _f4_reversal,
    "F5": _f5_transpose,
    "F6": _f6_other_position,
    "F7": _f7_coda,
    "F8": _f8_homophone,
}


def make_foil(kind: str, target: str, syls, pos: int, inv: Inventory,
              rng: random.Random, taken: set[str]) -> tuple[str, str]:
    """One legal foil and the kind that actually produced it.

    Walks the fallback chain when a kind cannot deliver (a target with
    no b, d, p, q, n, u, m or w has no reversal; a one-syllable-word
    set has no other position). The returned kind is what gets logged,
    so a fallback can never be read as evidence for a confusion type
    that was never on screen."""
    seen_kinds: list[str] = []
    cur = kind
    while cur is not None and cur not in seen_kinds:
        seen_kinds.append(cur)
        gen = GENERATORS[cur]
        for _ in range(MAX_TRIES):
            cand = gen(target, syls, pos, inv, rng)
            if (cand and cand not in taken
                    and is_legal(cand, target, syls, cur, inv)):
                return cand, cur
        cur = FALLBACK.get(cur)
    # F1 is the floor: any chunk in the bank that is legal and unused.
    pool = [c for c in inv.chunks
            if c not in taken and is_legal(c, target, syls, "F1", inv)]
    if pool:
        return rng.choice(pool), "F1"
    # Nothing in the bank fits (a bank small enough that every chunk
    # is already on screen, which only happens in a test). Build a
    # consonant-vowel filler instead. It skips the bigram test on
    # purpose: that test asks the BANK whether a letter pair occurs,
    # and a bank this small has no opinion, while "ba" and "ta" are
    # pronounceable by construction. A set short of an option would be
    # unanswerable, which is worse than a plain filler.
    for letter in "aeiou":
        for cons in "bcdfgklmnprst":
            cand = cons + letter
            if cand in taken or cand == target:
                continue
            if cand in tuple(syls):
                continue
            return cand, "F1"
    raise RuntimeError("no legal foil could be built for "
                       f"{target!r}")


def kinds_for_rung(rung: int, homophone_foils: bool = False
                   ) -> tuple[str, str, str]:
    """The three kinds the rung asks for. At rungs 7 and 8, with the
    homophone foil enabled, F8 replaces one of them."""
    rung = max(MIN_RUNG, min(MAX_RUNG, int(rung)))
    kinds = list(RUNG_SCHEDULE[rung])
    if homophone_foils and rung >= 7:
        for prefer in ("F3", "F4"):
            if prefer in kinds:
                kinds[kinds.index(prefer)] = "F8"
                break
    return tuple(kinds)


def draw_target_lane(lanes, tally: dict[int, int], recent,
                     rng: random.Random) -> int:
    """Which finger holds the answer this set.

    The same least-cued deficit draw the old sliding window used:
    score every candidate lane by how often it has already been the
    target this block and pick uniformly among the lowest, so every
    finger takes its turn as the answer instead of the draw drifting
    onto one hand. A lane that was the target for the last two sets is
    excluded, so the child can never sit on one finger and be right
    three times running. The tie-break is random, so the next target
    stays unpredictable, which is the whole point: nothing may name
    the answer before the press."""
    lanes = [int(l) for l in lanes]
    if not lanes:
        raise ValueError("no lanes to draw a target from")
    candidates = list(lanes)
    tail = list(recent)[-2:]
    if len(tail) == 2 and tail[0] == tail[1]:
        blocked = [l for l in candidates if l != tail[0]]
        if blocked:
            candidates = blocked
    low = min(tally.get(l, 0) for l in candidates)
    return rng.choice([l for l in candidates
                       if tally.get(l, 0) == low])


def build_option_set(word, pos: int, rung: int, rng: random.Random,
                     inv: Inventory, lanes, tally: dict[int, int],
                     recent, homophone_foils: bool = False) -> OptionSet:
    """The four tiles for syllable `pos` of `word`.

    Exactly four options with pairwise distinct texts, the target
    present exactly once, on a lane drawn by the deficit rule; the
    three foils take the remaining lanes in random order. Nothing in
    the returned set marks which option is the target except
    `target_lane`, which the mode keeps to itself until a press
    arrives."""
    syls = tuple(word.syllables)
    if not (0 <= pos < len(syls)):
        raise IndexError(f"position {pos} outside {word.word!r}")
    target = syls[pos]
    rung = max(MIN_RUNG, min(MAX_RUNG, int(rung)))
    taken = {target}
    foils: list[tuple[str, str]] = []
    for kind in kinds_for_rung(rung, homophone_foils):
        text, made = make_foil(kind, target, syls, pos, inv, rng, taken)
        taken.add(text)
        foils.append((text, made))
    target_lane = draw_target_lane(lanes, tally, recent, rng)
    rest = [l for l in lanes if l != target_lane]
    rng.shuffle(rest)
    options = [Option(text=target, lane=target_lane, kind=TARGET)]
    for lane, (text, made) in zip(rest, foils):
        options.append(Option(text=text, lane=lane, kind=made))
    options.sort(key=lambda o: o.lane)
    return OptionSet(word=word.word, pos=pos, target=target,
                     options=tuple(options), target_lane=target_lane,
                     rung=rung)
