"""Tests for the syllables word bank.

The bank IS the stimulus set. A split that does not join back to the
spelling renders a broken word on screen; a stress index out of range
would be a silent lie in the data; a chunk with no vowel letter breaks
the one curriculum rule the mode leans on (AC9E1LY12, a syllable must
contain a vowel sound); a duplicate word means the shuffle bag repeats
material inside a round. The build script checks all of that when it
writes the file, and this checks the file that is actually committed,
because the file is what ships.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from finger_rehab.game.modes.syllables_words import (  # noqa: E402
    MAX_SYLLABLES, MIN_SYLLABLES, WORDS, all_words, load_bank,
    syllable_lists, words_for)

BANK_FILE = REPO / "assets" / "words" / "syllables_bank.json"
SOURCE_FILE = REPO / "assets" / "words" / "syllables_source.txt"
LICENCE_FILE = REPO / "assets" / "words" / "LICENCE.txt"
VOWELS = set("aeiouy")


class BankFileTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(BANK_FILE.read_text())
        cls.entries = cls.data["words"]

    def test_the_bank_ships_with_its_licence_and_its_source(self) -> None:
        # The list is hand-written for this project and says so; the
        # source file is what a reviewer edits and the JSON is built
        # from it, so a bank with no source cannot be maintained.
        self.assertTrue(SOURCE_FILE.exists())
        self.assertTrue(LICENCE_FILE.exists())
        self.assertIn("licence", self.data)
        self.assertIn("LICENCE.txt", self.data["licence"])
        text = LICENCE_FILE.read_text()
        self.assertIn("Oxford Wordlist", text)
        self.assertIn("Macquarie", text)

    def test_size_and_shape_targets(self) -> None:
        counts = Counter(len(e["syllables"]) for e in self.entries)
        self.assertGreaterEqual(len(self.entries), 600, counts)
        self.assertGreaterEqual(counts[2], 300, counts)
        self.assertGreaterEqual(counts[3], 200, counts)
        self.assertGreaterEqual(counts[4], 100, counts)
        self.assertEqual(set(counts), {2, 3, 4}, counts)

    def test_every_entry_is_well_formed(self) -> None:
        for e in self.entries:
            word = e["word"]
            syls = e["syllables"]
            with self.subTest(word=word):
                self.assertEqual("".join(syls), word)
                self.assertTrue(word.isalpha() and word.isascii())
                self.assertTrue(word.islower())
                self.assertIn(e["band"], ("A", "B", "C"))
                self.assertTrue(0 <= e["stress"] < len(syls))
                self.assertTrue(MIN_SYLLABLES <= len(syls) <= MAX_SYLLABLES)
                for chunk in syls:
                    self.assertTrue(chunk.isalpha() and chunk.isascii())
                    self.assertTrue(chunk.islower())
                    self.assertTrue(
                        set(chunk) & VOWELS,
                        f"{word}: chunk {chunk!r} has no vowel letter")
                self.assertIn("sources", e)
                self.assertIn("reviewer", e)

    def test_no_duplicates(self) -> None:
        dupes = [w for w, n in Counter(e["word"] for e in self.entries
                                       ).items() if n > 1]
        self.assertEqual(dupes, [])

    def test_every_four_syllable_word_is_band_c(self) -> None:
        # The brief's banding rule: length overrules frequency.
        for e in self.entries:
            if len(e["syllables"]) == 4:
                self.assertEqual(e["band"], "C", e["word"])

    def test_sorted_so_a_rebuild_is_a_clean_diff(self) -> None:
        words = [e["word"] for e in self.entries]
        self.assertEqual(words, sorted(words))

    def test_no_excluded_material(self) -> None:
        # A short banned list standing in for the exclusion pass: no
        # proper nouns (capitalised), no Americanisms the source file
        # says are mapped out, nothing a parent would query.
        banned = {"candy", "cookie", "trash", "diaper", "soccerball",
                  "blood", "gun", "dead", "kill", "toilet"}
        present = {e["word"] for e in self.entries} & banned
        self.assertEqual(present, set())


class LoaderTests(unittest.TestCase):

    def test_loader_reads_the_shipped_bank(self) -> None:
        bank = load_bank()
        self.assertGreaterEqual(len(bank), 600)
        for w in bank[:50]:
            self.assertEqual("".join(w.syllables), w.word)

    def test_hand_list_words_survive_the_merge(self) -> None:
        # The hand list is the seed and the review set: every one of
        # its playable words has to be reachable, and where the two
        # sources disagree the hand entry wins.
        merged = {w.word: w for w in all_words()}
        for w in WORDS:
            if MIN_SYLLABLES <= w.n_syll <= MAX_SYLLABLES:
                self.assertIn(w.word, merged, w.word)
                self.assertEqual(merged[w.word].syllables, w.syllables,
                                 w.word)
                self.assertEqual(merged[w.word].stress, w.stress, w.word)

    def test_local_words_are_there(self) -> None:
        merged = {w.word for w in all_words()}
        for word in ("wombat", "kookaburra", "galah", "billabong",
                     "echidna", "budgerigar", "barramundi", "wallaby",
                     "platypus", "didgeridoo"):
            self.assertIn(word, merged, word)

    def test_one_and_five_syllable_words_never_reach_the_pool(self) -> None:
        # One syllable has no boundary to hear; five is memory span.
        for w in all_words():
            self.assertTrue(MIN_SYLLABLES <= w.n_syll <= MAX_SYLLABLES,
                            w.word)

    def test_a_missing_bank_leaves_the_hand_list_playable(self) -> None:
        # A packaging slip must degrade the material, never stop a
        # child mid-session.
        missing = REPO / "assets" / "words" / "does_not_exist.json"
        self.assertEqual(load_bank(missing), ())

    def test_a_broken_entry_is_skipped_not_fatal(self) -> None:
        import tempfile
        bad = {"words": [
            {"word": "banana", "band": "A",
             "syllables": ["ba", "na", "na"], "stress": 1},
            {"word": "broken", "band": "A",
             "syllables": ["bro"], "stress": 0},          # does not join
            {"word": "toolong", "band": "A",
             "syllables": ["to", "o", "lo", "n", "g"], "stress": 0},
            {"word": "badstress", "band": "A",
             "syllables": ["bad", "stress"], "stress": 5},
        ]}
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "bank.json"
            p.write_text(json.dumps(bad))
            got = load_bank(p)
        self.assertEqual([w.word for w in got], ["banana"])


class PoolTests(unittest.TestCase):

    def test_bands_walk_the_syllable_ladder(self) -> None:
        counts = {b: Counter(w.n_syll for w in words_for(b))
                  for b in ("A", "B", "C")}
        # A is mostly two syllables, B mixes two and three, C is where
        # the four-syllable words live.
        self.assertGreater(counts["A"][2], counts["A"][3])
        self.assertEqual(counts["A"][4], 0)
        self.assertGreater(counts["B"][3], 0)
        self.assertGreater(counts["C"][4], 90)

    def test_every_pool_is_big_enough_for_a_round(self) -> None:
        for band in ("A", "B", "C"):
            for bilateral in (False, True):
                pool = words_for(band, bilateral=bilateral)
                self.assertGreaterEqual(len(pool), 40, (band, bilateral))

    def test_hand_count_no_longer_changes_the_material(self) -> None:
        # Under the tapping design a long word needed adjacent
        # fingers, so bilateral play widened the pool. In the choice
        # task every syllable is one set of four tiles, so it cannot.
        for band in ("A", "B", "C"):
            self.assertEqual(
                sorted(w.word for w in words_for(band, bilateral=False)),
                sorted(w.word for w in words_for(band, bilateral=True)))

    def test_syllable_inventory_covers_the_pool(self) -> None:
        chunks = {c for syls in syllable_lists() for c in syls}
        for w in words_for("C"):
            for c in w.syllables:
                self.assertIn(c, chunks, w.word)


if __name__ == "__main__":
    unittest.main()
