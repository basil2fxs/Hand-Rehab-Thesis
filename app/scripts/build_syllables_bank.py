#!/usr/bin/env python3
"""Build assets/words/syllables_bank.json from assets/words/syllables_source.txt.

Run it after editing the source list:

    python3 scripts/build_syllables_bank.py

Deterministic: the same source file always produces the same JSON,
sorted by word, so a rebuild shows up in git only when the source
actually changed.

WHY A HAND-WRITTEN SOURCE. The research note for this mode lists the
open resources a larger bank could be assembled from (cmudict for
stress and syllable counts, Moby Hyphenator II for written splits,
Kuperman age-of-acquisition ratings and a children's frequency list
for the filter). All of them have to be downloaded and none of them
can be redistributed without carrying its own licence terms into this
repo, and two of the obvious shortcuts are not usable at all: the
Oxford Wordlist is copyright Oxford University Press, and Wiktionary
splits would make the bank share-alike. So the shipped bank is
written by hand for this project against ordinary Australian usage,
which owes nothing to anyone, and this script stays the place where a
generated bank would be merged in if that route is ever taken: add a
loader beside _read_source, merge on the word, and let the hand
entries win on conflict.

VALIDATION. Every line has to pass, or the build fails and writes
nothing:
  - band A, B or C, then one hyphenated token;
  - the chunks join to a lower-case a-z spelling;
  - 2 to 4 chunks (one chunk has no boundary to hear; past four is
    memory span, not segmentation);
  - every chunk holds a vowel letter (a e i o u y), the Year 1
    curriculum rule AC9E1LY12;
  - exactly one chunk is capitalised, which is where the stress sits;
  - no duplicate words.
Four-syllable words are forced to band C whatever the source says
(the brief's banding rule), and the script reports the per-count
totals against the targets in the research note.
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE = REPO / "assets" / "words" / "syllables_source.txt"
OUT = REPO / "assets" / "words" / "syllables_bank.json"

VOWELS = set("aeiouy")
BANDS = ("A", "B", "C")
MIN_SYLL, MAX_SYLL = 2, 4
# The research note's targets: enough two-syllable words that a block
# never cycles the same handful, and enough long ones that band C is a
# real step up rather than the same six words.
TARGETS = {2: 300, 3: 200, 4: 100}

LICENCE_LINE = (
    "Hand-written for this project. No third-party word list, "
    "dictionary or corpus was copied. See assets/words/LICENCE.txt.")


def _parse_line(line: str, lineno: int) -> tuple[dict, str | None]:
    """One source line to a bank entry, or (entry, error)."""
    parts = line.split()
    if len(parts) != 2:
        return {}, f"line {lineno}: expected '<band> <split>', got {line!r}"
    band, token = parts
    if band not in BANDS:
        return {}, f"line {lineno}: band {band!r} is not A, B or C"
    chunks = token.split("-")
    if not (MIN_SYLL <= len(chunks) <= MAX_SYLL):
        return {}, (f"line {lineno}: {token!r} has {len(chunks)} chunks, "
                    f"needs {MIN_SYLL} to {MAX_SYLL}")
    stressed = [i for i, c in enumerate(chunks) if c.isupper()]
    if len(stressed) != 1:
        return {}, (f"line {lineno}: {token!r} marks {len(stressed)} "
                    "stressed chunks, needs exactly one in CAPITALS")
    lower = [c.lower() for c in chunks]
    for c in lower:
        if not c.isalpha() or not c.isascii():
            return {}, f"line {lineno}: chunk {c!r} is not plain a-z"
        if not (set(c) & VOWELS):
            return {}, (f"line {lineno}: chunk {c!r} has no vowel letter "
                        "(AC9E1LY12: a syllable must contain a vowel)")
    word = "".join(lower)
    n = len(lower)
    entry = {
        "word": word,
        "band": "C" if n == MAX_SYLL else band,
        "syllables": lower,
        "stress": stressed[0],
        "sources": ["manual"],
        "reviewer": "",
    }
    return entry, None


def _read_source(path: Path) -> tuple[list[dict], list[str]]:
    entries: list[dict] = []
    errors: list[str] = []
    for lineno, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        entry, err = _parse_line(line, lineno)
        if err:
            errors.append(err)
        else:
            entries.append(entry)
    seen: dict[str, int] = {}
    for e in entries:
        seen[e["word"]] = seen.get(e["word"], 0) + 1
    for word, n in sorted(seen.items()):
        if n > 1:
            errors.append(f"{word!r} appears {n} times")
    return entries, errors


def main() -> int:
    entries, errors = _read_source(SOURCE)
    if errors:
        for e in errors:
            print("ERROR", e, file=sys.stderr)
        print(f"{len(errors)} problem(s); nothing written", file=sys.stderr)
        return 1
    entries.sort(key=lambda e: e["word"])
    counts = Counter(len(e["syllables"]) for e in entries)
    bank = {
        "licence": LICENCE_LINE,
        "generated_by": "scripts/build_syllables_bank.py",
        "generated_on": date.today().isoformat(),
        "source": "assets/words/syllables_source.txt",
        "convention": ("Australian English. Splits follow spoken "
                       "syllables cut at the nearest spelling "
                       "boundary; stress is the 0-based index of the "
                       "primary-stress syllable."),
        "counts": {str(k): counts[k] for k in sorted(counts)},
        "words": entries,
    }
    OUT.write_text(json.dumps(bank, indent=1, sort_keys=False) + "\n")
    print(f"wrote {OUT.relative_to(REPO)}: {len(entries)} words")
    for n in sorted(TARGETS):
        got, want = counts.get(n, 0), TARGETS[n]
        flag = "ok" if got >= want else "SHORT"
        print(f"  {n} syllables: {got} (target {want}) {flag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
