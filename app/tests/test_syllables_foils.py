"""Tests for the syllables option-set builder.

The option set IS the trial: four written chunks, one right, three
wrong for a reason. Everything pinned here is something a child would
feel immediately if it broke. Four options with distinct texts, or the
same chunk appears twice and the task is unanswerable. The target
present exactly once, or there is no right answer. Every foil legal
(pronounceable, a vowel in it, not another syllable of the word unless
it is the F6 kind), or the game shows a child a string that is not a
word part. The kind LOGGED being the kind actually produced, or the
notebook's confusion chart credits a foil type with a capture it never
made. The target lane spread across the fingers and never the same
lane three sets running, or a child can sit on one finger. And the
same seed producing the same sets, or a block can never be replayed.
"""
from __future__ import annotations

import os
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from finger_rehab.game.modes import syllables_foils as F  # noqa: E402
from finger_rehab.game.modes.syllables_words import (  # noqa: E402
    all_words, syllable_lists)

INV = F.Inventory(syllable_lists())
WORDS = all_words()
LANES = [0, 1, 2, 3]


def _draw(word, pos, rung, seed=0, homophone=False):
    rng = random.Random(seed)
    return F.build_option_set(word, pos, rung, rng, INV, LANES, {}, [],
                              homophone_foils=homophone)


class ShapeTests(unittest.TestCase):

    def test_every_set_has_four_distinct_options_one_target(self) -> None:
        # 2,000 seeded draws across the bank, every position and every
        # rung: the shape can never depend on the word or the rung.
        rng = random.Random(4242)
        n = 0
        while n < 2000:
            word = rng.choice(WORDS)
            pos = rng.randrange(word.n_syll)
            rung = rng.randint(F.MIN_RUNG, F.MAX_RUNG)
            oset = _draw(word, pos, rung, seed=n)
            with self.subTest(word=word.word, pos=pos, rung=rung):
                self.assertEqual(len(oset.options), F.N_OPTIONS)
                texts = [o.text for o in oset.options]
                self.assertEqual(len(set(texts)), F.N_OPTIONS, texts)
                targets = [o for o in oset.options if o.kind == F.TARGET]
                self.assertEqual(len(targets), 1, texts)
                self.assertEqual(targets[0].text, word.syllables[pos])
                self.assertEqual(targets[0].lane, oset.target_lane)
                self.assertIn(oset.target_lane, LANES)
                self.assertEqual(sorted(o.lane for o in oset.options),
                                 sorted(LANES))
            n += 1

    def test_every_foil_is_legal(self) -> None:
        rng = random.Random(77)
        for i in range(600):
            word = rng.choice(WORDS)
            pos = rng.randrange(word.n_syll)
            rung = rng.randint(F.MIN_RUNG, F.MAX_RUNG)
            oset = _draw(word, pos, rung, seed=1000 + i)
            target = word.syllables[pos]
            for opt in oset.options:
                if opt.kind == F.TARGET:
                    continue
                with self.subTest(word=word.word, foil=opt.text,
                                  kind=opt.kind):
                    self.assertTrue(opt.text.isalpha() and opt.text.isascii())
                    self.assertTrue(opt.text.islower())
                    self.assertTrue(1 <= len(opt.text) <= 5)
                    self.assertTrue(set(opt.text) & F.VOWEL_LETTERS,
                                    "a syllable must contain a vowel")
                    self.assertNotEqual(opt.text, target)
                    self.assertTrue(INV.pronounceable(opt.text))

    def test_only_f6_repeats_another_syllable_of_the_word(self) -> None:
        # F6 is the "you are in the wrong place in the word" foil and
        # is the ONLY kind allowed to show a chunk that belongs to
        # this word somewhere else.
        rng = random.Random(9)
        seen_f6 = 0
        for i in range(800):
            word = rng.choice([w for w in WORDS if w.n_syll >= 3])
            pos = rng.randrange(word.n_syll)
            oset = _draw(word, pos, 8, seed=2000 + i)
            for opt in oset.options:
                if opt.kind == F.TARGET:
                    continue
                inside = opt.text in word.syllables
                if opt.kind == "F6":
                    seen_f6 += inside
                else:
                    self.assertFalse(
                        inside,
                        f"{opt.kind} foil {opt.text!r} is a syllable of "
                        f"{word.word!r}")
        self.assertGreater(seen_f6, 0, "F6 never produced a real one")


class RungTests(unittest.TestCase):

    def test_schedule_covers_every_rung_with_three_kinds(self) -> None:
        for rung in range(F.MIN_RUNG, F.MAX_RUNG + 1):
            kinds = F.kinds_for_rung(rung)
            self.assertEqual(len(kinds), 3, rung)
            for k in kinds:
                self.assertIn(k, F.FOIL_KINDS)

    def test_produced_kinds_are_the_schedule_or_a_declared_fallback(
            self) -> None:
        # A generator that cannot deliver falls back down a declared
        # chain, and the LOGGED kind is what was actually produced.
        rng = random.Random(31)
        for i in range(400):
            word = rng.choice(WORDS)
            pos = rng.randrange(word.n_syll)
            rung = rng.randint(F.MIN_RUNG, F.MAX_RUNG)
            wanted = list(F.kinds_for_rung(rung))
            oset = _draw(word, pos, rung, seed=3000 + i)
            got = [o.kind for o in oset.options if o.kind != F.TARGET]
            for kind in got:
                self.assertIn(kind, F.FOIL_KINDS)
            for kind in got:
                if kind in wanted:
                    wanted.remove(kind)
                    continue
                # Not the asked-for kind: it must be reachable down a
                # fallback chain from one of them.
                reachable = set()
                for w in wanted:
                    cur = w
                    while cur is not None:
                        reachable.add(cur)
                        cur = F.FALLBACK.get(cur)
                reachable.add("F1")
                self.assertIn(kind, reachable,
                              f"{kind} is not a declared fallback of "
                              f"{wanted} ({word.word} rung {rung})")

    def test_rung_one_is_far_foils_and_rung_eight_is_near(self) -> None:
        self.assertEqual(F.kinds_for_rung(1), ("F1", "F1", "F1"))
        self.assertEqual(F.kinds_for_rung(8), ("F4", "F5", "F6"))
        # Out-of-range rungs clamp instead of raising.
        self.assertEqual(F.kinds_for_rung(0), F.kinds_for_rung(1))
        self.assertEqual(F.kinds_for_rung(99), F.kinds_for_rung(8))

    def test_homophone_foil_only_enters_at_the_top_rungs(self) -> None:
        for rung in range(1, 7):
            self.assertNotIn("F8", F.kinds_for_rung(rung, True), rung)
        for rung in (7, 8):
            self.assertIn("F8", F.kinds_for_rung(rung, True), rung)
        # Off by default at every rung.
        for rung in range(1, 9):
            self.assertNotIn("F8", F.kinds_for_rung(rung, False), rung)


class GeneratorTests(unittest.TestCase):
    """Each foil kind does the thing its literature says it does."""

    def setUp(self) -> None:
        self.rng = random.Random(5)

    def test_vowel_swap_keeps_the_frame(self) -> None:
        out = F._f3_vowel("ban", (), 0, INV, self.rng)
        self.assertEqual(len(out), 3)
        self.assertEqual((out[0], out[2]), ("b", "n"))
        self.assertNotEqual(out[1], "a")

    def test_vowel_digraphs_swap_as_a_unit(self) -> None:
        out = F._f3_vowel("beat", (), 0, INV, self.rng)
        self.assertTrue(out.startswith("b") and out.endswith("t"), out)
        self.assertNotEqual(out, "beat")
        self.assertEqual(len(out), 4)

    def test_reversal_flips_one_reversible_letter(self) -> None:
        self.assertEqual(F._f4_reversal("bat", (), 0, INV, self.rng), "dat")
        self.assertEqual(F._f4_reversal("pig", (), 0, INV, self.rng), "qig")
        # No reversible letter: the generator declines and the caller
        # falls back (F4 -> F3).
        self.assertIsNone(F._f4_reversal("cat", (), 0, INV, self.rng))

    def test_transposition_swaps_adjacent_letters(self) -> None:
        out = F._f5_transpose("tur", (), 0, INV, self.rng)
        self.assertIsNotNone(out)
        self.assertEqual(sorted(out), sorted("tur"))
        self.assertNotEqual(out, "tur")

    def test_coda_swap_adds_a_coda_to_an_open_syllable(self) -> None:
        out = F._f7_coda("ba", (), 0, INV, self.rng)
        self.assertTrue(out.startswith("ba"), out)
        self.assertGreater(len(out), 2)

    def test_onset_swap_keeps_the_rime(self) -> None:
        out = F._f2_onset("ban", (), 0, INV, self.rng)
        self.assertTrue(out.endswith("an"), out)
        self.assertNotEqual(out, "ban")

    def test_same_word_other_position(self) -> None:
        out = F._f6_other_position("ba", ("ba", "na", "na"), 0, INV,
                                   self.rng)
        self.assertEqual(out, "na")
        # A two-chunk word where both chunks are the same has no other
        # position to offer.
        self.assertIsNone(F._f6_other_position(
            "na", ("na", "na"), 0, INV, self.rng))

    def test_homophone_swaps_the_spelling_not_the_sound(self) -> None:
        out = F._f8_homophone("ca", (), 0, INV, self.rng)
        self.assertEqual(out, "ka")

    def test_legality_rejects_the_obvious_bad_strings(self) -> None:
        self.assertFalse(F.is_legal("", "ba", ("ba",), "F1", INV))
        self.assertFalse(F.is_legal("ba", "ba", ("ba",), "F1", INV))
        self.assertFalse(F.is_legal("bcd", "ba", ("ba",), "F1", INV),
                         "no vowel letter")
        self.assertFalse(F.is_legal("abcdef", "ba", ("ba",), "F1", INV),
                         "too long")
        self.assertFalse(F.is_legal("Ba", "ba", ("ba",), "F1", INV),
                         "upper case")
        self.assertFalse(F.is_legal("na", "ba", ("ba", "na"), "F1", INV),
                         "another syllable of the word, and not F6")
        self.assertTrue(F.is_legal("na", "ba", ("ba", "na"), "F6", INV))


class TargetLaneTests(unittest.TestCase):

    def test_lane_balance_over_a_block(self) -> None:
        # Across a 40-word block every finger takes its turn as the
        # answer: the deficit draw keeps the counts within one.
        rng = random.Random(1234)
        tally: dict[int, int] = {}
        recent: list[int] = []
        for _ in range(120):
            lane = F.draw_target_lane(LANES, tally, recent, rng)
            tally[lane] = tally.get(lane, 0) + 1
            recent.append(lane)
        self.assertEqual(sorted(tally), LANES)
        self.assertLessEqual(max(tally.values()) - min(tally.values()), 1,
                             tally)

    def test_never_the_same_lane_three_sets_running(self) -> None:
        rng = random.Random(5)
        tally: dict[int, int] = {}
        recent: list[int] = []
        for _ in range(400):
            lane = F.draw_target_lane(LANES, tally, recent, rng)
            tally[lane] = tally.get(lane, 0) + 1
            recent.append(lane)
        for i in range(2, len(recent)):
            self.assertFalse(
                recent[i] == recent[i - 1] == recent[i - 2],
                f"lane {recent[i]} was the target three sets running "
                f"at set {i}")

    def test_a_one_lane_hand_still_draws(self) -> None:
        # Degenerate but must not raise: the block-three-in-a-row rule
        # cannot starve the draw of candidates.
        rng = random.Random(0)
        self.assertEqual(F.draw_target_lane([2], {2: 9}, [2, 2], rng), 2)


class SeedTests(unittest.TestCase):

    def test_same_seed_same_sets(self) -> None:
        word = [w for w in WORDS if w.word == "banana"][0]
        a = [_draw(word, p, 5, seed=99) for p in range(word.n_syll)]
        b = [_draw(word, p, 5, seed=99) for p in range(word.n_syll)]
        self.assertEqual(
            [[(o.lane, o.text, o.kind) for o in s.options] for s in a],
            [[(o.lane, o.text, o.kind) for o in s.options] for s in b])

    def test_different_seeds_differ(self) -> None:
        word = [w for w in WORDS if w.word == "banana"][0]
        a = _draw(word, 0, 5, seed=1)
        b = _draw(word, 0, 5, seed=2)
        self.assertNotEqual([(o.lane, o.text) for o in a.options],
                            [(o.lane, o.text) for o in b.options])


class InventoryTests(unittest.TestCase):

    def test_inventory_is_built_from_the_bank(self) -> None:
        self.assertGreater(len(INV.chunks), 200)
        self.assertIn("ba", INV.chunks)
        self.assertTrue(INV.pronounceable("ban"))
        # "ps" does not open any chunk in an English children's bank,
        # so a transposition that produced it is rejected.
        self.assertFalse(INV.pronounceable("psi"))

    def test_a_tiny_bank_still_produces_a_full_set(self) -> None:
        # The floor path: an inventory with almost nothing in it must
        # still return four distinct legal options rather than raise.
        tiny = F.Inventory([("ba", "na")])
        from finger_rehab.game.modes.syllables_words import Word
        word = Word(word="banana", band="A",
                    syllables=("ba", "na", "na"), stress=1)
        oset = F.build_option_set(word, 0, 8, random.Random(3), tiny,
                                  LANES, {}, [])
        self.assertEqual(len({o.text for o in oset.options}), 4)


if __name__ == "__main__":
    unittest.main()
