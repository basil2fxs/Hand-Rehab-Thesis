"""Syllables said as they sound in their word (Basil, 29 September 2026).

One spelt file per chunk said the ger of tiger as "jer", the ginger
reading, so the parts never blended back into the word. Now each word's
own phonemes are cut at its chunks (scripts/syllables_tts.py), the game
plays the file the manifest's syllable_map names for that word, the
model ends by saying the whole word again, and a syllable heard with a
weak vowel gets no vowel foil. None of these tests needs Kokoro.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import syllables_recording_kit as K  # noqa: E402
import syllables_tts as T  # noqa: E402
from finger_rehab.game.modes.syllables_words import (  # noqa: E402
    Word, speech_stem)
from tests.test_syllables_mode import (  # noqa: E402
    _build_mode, _run_to_choose)

MANIFEST = json.loads((ROOT / "assets" / "speech" / "manifest.json")
                      .read_text(encoding="utf-8"))["entries"]


def _cut(word, chunks):
    ps = MANIFEST[speech_stem(word)]["phonemes"]
    pieces = T.word_syllables(chunks, ps)
    return [T.said_alone(p) for p in pieces], [T.is_weak(p) for p in pieces]


class TheCut(unittest.TestCase):

    def test_each_part_sounds_as_it_does_in_its_word(self):
        cases = {
            ("tiger", ("ti", "ger")): ["tˈI", "ɡˈə"],
            ("ginger", ("gin", "ger")): ["ʤˈɪn", "ʤˈə"],
            ("finger", ("fin", "ger")): ["fˈɪŋ", "ɡˈə"],
            ("dinosaur", ("di", "no", "saur")): ["dˈI", "nˈə", "sˈɔː"],
            ("banana", ("ba", "na", "na")): ["bˈə", "nˈɑː", "nˈə"],
        }
        for (word, chunks), want in cases.items():
            with self.subTest(word=word):
                self.assertEqual(_cut(word, chunks)[0], want)

    def test_a_double_letter_closes_one_syllable_and_opens_the_next(self):
        self.assertEqual(_cut("rabbit", ("rab", "bit"))[0],
                         ["ɹˈab", "bˈɪt"])
        self.assertEqual(_cut("digger", ("dig", "ger"))[0],
                         ["dˈɪɡ", "ɡˈə"])
        self.assertEqual(_cut("apple", ("ap", "ple"))[0],
                         ["ˈap", "pˈəl"])

    def test_a_syllable_speech_drops_gets_its_vowel_back(self):
        # camera is "cam-ra" in running speech; said part by part a
        # careful speaker gives the e back.
        self.assertEqual(_cut("camera", ("cam", "e", "ra"))[0],
                         ["kˈam", "ˈə", "ɹˈə"])
        self.assertEqual(_cut("different", ("dif", "fer", "ent"))[0],
                         ["dˈɪf", "fˈə", "ɹˈənt"])

    def test_vowels_split_and_join_to_match_the_chunks(self):
        # ɪə across two chunks; a rising vowel and its schwa as one.
        self.assertEqual(_cut("aquarium", ("a", "quar", "i", "um"))[0],
                         ["ˈə", "kwˈɛː", "ɹˈɪ", "ˈəm"])
        self.assertEqual(_cut("firefighter", ("fire", "fight", "er"))[0],
                         ["fˈIə", "fˈIt", "ˈə"])

    def test_weak_vowels_are_flagged(self):
        self.assertEqual(_cut("tiger", ("ti", "ger"))[1], [False, True])
        # The secondary stress of saur keeps its full vowel.
        self.assertEqual(_cut("dinosaur", ("di", "no", "saur"))[1],
                         [False, True, False])

    def test_every_real_word_the_game_can_play_is_cut(self):
        words = [w for w in T.pool_words(K.ALL_POOLS) if w.lex != "pseudo"]
        self.assertGreater(len(words), 800)
        for w in words:
            ps = MANIFEST[speech_stem(w.word)]["phonemes"]
            with self.subTest(word=w.word):
                pieces = T.word_syllables(w.syllables, ps)
                self.assertIsNotNone(pieces)
                self.assertEqual(len(pieces), len(w.syllables))
                for p in pieces:
                    said = T.said_alone(p)
                    self.assertEqual(said.count("ˈ"), 1, said)
                    self.assertFalse(set(said) - T.KOKORO_SYMBOLS, said)


class ThePlan(unittest.TestCase):

    def _plan(self, words):
        every, _ = K.bank_items(K.ALL_POOLS)
        return T.syllable_plan(
            words, lambda w: MANIFEST[speech_stem(w)]["phonemes"],
            lambda c: every[c.lower()][0])

    def test_a_part_that_sounds_like_its_chunk_reuses_the_chunk_file(self):
        smap, new = self._plan([Word("tiger", "A", ("ti", "ger"), 0),
                                Word("rabbit", "A", ("rab", "bit"), 0)])
        self.assertEqual(smap["tiger"]["files"][0], "chunks/ti")
        self.assertEqual(smap["tiger"]["files"][1], "syllables/tiger_1")
        self.assertEqual(new["syllables/tiger_1"], "ɡˈə")
        self.assertEqual(smap["rabbit"]["files"],
                         ["chunks/rab", "chunks/bit"])
        self.assertEqual(smap["tiger"]["weak"], [0, 1])

    def test_one_sound_is_made_once(self):
        smap, new = self._plan([Word("tiger", "A", ("ti", "ger"), 0),
                                Word("digger", "A", ("dig", "ger"), 0)])
        self.assertEqual(smap["digger"]["files"][1], "syllables/tiger_1")
        self.assertEqual(list(new), ["syllables/tiger_1"])

    def test_a_made_up_word_is_said_as_its_chunks(self):
        from finger_rehab.game.modes.syllables_words import load_pools
        made_up = load_pools()["pseudo"][0]
        smap, new = self._plan([made_up])
        self.assertEqual(smap[made_up.word]["files"],
                         [f"chunks/{speech_stem(c.lower())}"
                          for c in made_up.syllables])
        self.assertEqual(new, {})

    def test_the_dry_run_needs_no_model(self):
        import contextlib
        import io
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            self.assertEqual(T.main(["--syllables-only", "--dry-run"]), 0)
        out = buf.getvalue()
        self.assertIn("new sounds", out)
        self.assertTrue(any(line.startswith("tiger ")
                            for line in out.splitlines()))


class TheShippedVoice(unittest.TestCase):

    def test_every_file_the_map_names_ships_for_every_word(self):
        """Once the in-word syllables are rendered, every word the game
        can play has one existing file per syllable. Until then the
        manifest carries no map and the game plays the chunk files."""
        data = json.loads((ROOT / "assets" / "speech" / "manifest.json")
                          .read_text(encoding="utf-8"))
        smap = data.get("syllable_map") or {}
        if not smap:
            self.assertNotIn("syllable_form", data)
            return
        self.assertEqual(data.get("syllable_form"), "word")
        for w in T.pool_words(K.ALL_POOLS):
            with self.subTest(word=w.word):
                got = smap[w.word]
                self.assertEqual(len(got["files"]), len(w.syllables))
                self.assertEqual(len(got["weak"]), len(w.syllables))
                for f in got["files"]:
                    self.assertTrue(
                        (ROOT / "assets" / "speech" / f"{f}.wav").exists(), f)
                    self.assertIn(f, data["entries"])


def _wav(path: Path, seconds: float) -> None:
    from scipy.io import wavfile
    path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(path), K.RATE,
                  np.zeros(int(seconds * K.RATE), dtype=np.int16))


class TheGame(unittest.TestCase):

    def _mode_with_map(self, root: Path, **kw):
        engine, mode = _build_mode(
            speech={"backend": "file", "dir": str(root)}, **kw)
        mode._begin_word(0.0)
        word = mode.word
        files = [f"chunks/{speech_stem(c)}" for c in word.syllables]
        files[-1] = f"syllables/{speech_stem(word.word)}_{mode.n_syll - 1}"
        weak = [0] * mode.n_syll
        weak[-1] = 1
        (root / "manifest.json").write_text(json.dumps({
            "chunk_form": "spelling", "entries": {},
            "syllable_map": {word.word: {"files": files, "weak": weak}}}))
        for f in files:
            _wav(root / f"{f}.wav", 0.4)
        mode._manifest_entries = None
        return engine, mode

    def test_the_map_names_the_file_played(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _e, mode = self._mode_with_map(root)
            last = mode.n_syll - 1
            self.assertEqual(
                mode.syllable_file(last),
                root / "syllables" / f"{speech_stem(mode.word.word)}_{last}.wav")
            self.assertEqual(mode.syllable_file(0).parent.name, "chunks")
            self.assertTrue(mode.heard_weak(last))
            self.assertFalse(mode.heard_weak(0))
            self.assertAlmostEqual(mode.model_ioi_s(last),
                                   max(mode.ioi_s, 0.4 + mode.MODEL_GAP_S),
                                   delta=0.01)

    def test_a_word_the_map_does_not_cover_keeps_its_chunk_files(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            _e, mode = self._mode_with_map(root)
            mode._speech_manifest()
            mode._manifest_syllables = {}
            self.assertIsNone(mode.heard_weak(0))
            chunk = mode.word.syllables[0]
            self.assertEqual(mode.syllable_file(0),
                             root / "chunks" / f"{speech_stem(chunk)}.wav")

    def test_a_weak_syllable_gets_no_vowel_foil_in_any_profile(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for band in ("classic", "6-9", "16+"):
                with self.subTest(profile=band):
                    _e, mode = self._mode_with_map(root, age_band=band)
                    mode.rung = 5            # F2, F3, F4 in the schedule
                    mode.pos = mode.n_syll - 1
                    for _ in range(40):
                        self.assertNotIn("F3", mode._foil_kinds() or ())
            _e, mode = self._mode_with_map(root, age_band="classic")
            mode.rung = 5
            mode.pos = 0
            self.assertIsNone(mode._foil_kinds())


class TheBlend(unittest.TestCase):

    def test_the_model_ends_with_the_whole_word(self):
        _e, mode = _build_mode()
        said = []
        mode._speak_word = lambda: said.append(("word", mode.phase,
                                                mode._model_idx))
        mode._speak_syllable = lambda k: said.append(("syl", k, mode.phase))
        t = 0.0
        blended = False
        while not (mode.phase == "choose" and mode.option_set is not None):
            mode._tick(t)
            blended = blended or mode.blending
            t += 0.02
            self.assertLess(t, 60.0)
        n = mode.n_syll
        self.assertTrue(blended)
        modelled = [s for s in said if s[0] == "syl" and s[2] == "model"]
        self.assertEqual(modelled, [("syl", k, "model") for k in range(n)])
        # The word at ATTEND, then again after the last syllable, and
        # nothing else said in the model after it.
        words = [s for s in said if s[0] == "word"]
        self.assertEqual(len(words), 2)
        self.assertEqual(words[1], ("word", "model", n))
        after = said[said.index(words[1]) + 1:]
        self.assertTrue(all(s[-1] != "model" for s in after), after)
        self.assertFalse(mode.blending)

    def test_the_blend_holds_before_the_first_set(self):
        _e, mode = _build_mode()
        t = 0.0
        start = None
        while not (mode.phase == "choose" and mode.option_set is not None):
            mode._tick(t)
            if mode.blending and start is None:
                start = t
            t += 0.01
        self.assertGreaterEqual(t - start,
                                mode.ioi_s + mode.BLEND_HOLD_S - 0.05)

    def test_the_screen_shows_every_part_at_the_blend(self):
        import time
        from unittest.mock import patch
        import pygame
        pygame.init()
        try:
            from finger_rehab.config import Config
            from finger_rehab.game.engine import GameEngine
            from finger_rehab.hardware.keyboard_source import (
                KeyboardOnlySource)
            cfg = Config.load()
            cfg.data["ui"]["resolution"] = [1280, 800]
            cfg.data["audio"]["enabled"] = False
            cfg.data["syllables"]["age_band"] = "6-9"
            cfg.data["syllables"]["speech"]["backend"] = "off"
            # The blend belongs to the training words, not the probe
            # that opens the sitting.
            cfg.data["syllables"]["probe"] = False
            clock = [100.0]
            with patch.object(time, "perf_counter", lambda: clock[0]):
                eng = GameEngine(cfg, KeyboardOnlySource())
                from unittest.mock import MagicMock
                from finger_rehab.ui.syllables_screen import SyllablesScreen
                eng._screens = {"syllables": SyllablesScreen(eng),
                                "results": MagicMock()}
                eng.begin_syllables_block()
                mode, screen = eng.mode, eng.screen_obj
                for _ in range(3000):
                    mode.update(0.02)
                    if mode.blending:
                        break
                    clock[0] += 0.02
                self.assertTrue(mode.blending)
                self.assertEqual(screen._stage(mode)[1],
                                 "Now the parts together.")
                surf = pygame.Surface((1280, 800))
                screen.draw(surf)
                rects = screen.slot_rects(mode)
                fills = {tuple(surf.get_at((r.x + 6, r.centery)))[:3]
                         for r in rects}
                # Every slot is filled in the accent colour, none is
                # left as an empty outline.
                self.assertEqual(fills, {tuple(screen._accent())[:3]})
                eng._abandon_if_in_block()
        finally:
            pygame.quit()

    def test_the_blend_word_trails_the_print_as_a_syllable_does(self):
        # A child hears each part 175 ms after it is printed; the blend
        # keeps that lead, so the quiet before the word is not cut.
        _e, mode = _build_mode(age_band="6-9")
        heard = []
        mode._speak_word = lambda: heard.append(("word", t))
        mode._speak_syllable = lambda k: heard.append((k, t))
        t, lit = 0.0, None
        while not (mode.phase == "choose" and mode.option_set is not None):
            mode._tick(t)
            if mode.blending and lit is None:
                lit = t
            t += 0.005
        word_t = [at for what, at in heard if what == "word"][-1]
        self.assertAlmostEqual(word_t - lit, mode.sound_lead_s, delta=0.01)

    def test_adults_have_no_model_and_so_no_blend(self):
        _e, mode = _build_mode(age_band="16+")
        t = _run_to_choose(mode)
        self.assertGreater(t, 0.0)
        self.assertFalse(mode.blending)


if __name__ == "__main__":
    unittest.main()
