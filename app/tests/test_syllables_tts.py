"""The Syllables voice the app ships (scripts/syllables_tts.py).

Kokoro makes the sound, but the phonemes are ours: every chunk is said
the way the recording kit tells a speaker to say it, and every made-up
word is its own chunks run together. These tests pin that, and that
what ships in assets/speech is complete for every pool the game
can play, in the mixer's format, and says what made it. None of them
needs Kokoro installed.
"""
from __future__ import annotations

import json
import os
import sys
import unittest
import wave
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import syllables_recording_kit as K  # noqa: E402
import syllables_tts as T  # noqa: E402
from finger_rehab.game.modes.syllables_words import speech_stem  # noqa: E402

SPEECH = ROOT / "assets" / "speech"
# Every pool: the battery's classic profile plays the child bank, and
# the age profiles the rest.
SHIPPED_POOLS = K.ALL_POOLS


class ChunkSounds(unittest.TestCase):

    def test_the_hints_become_the_sounds_they_name(self):
        cases = {
            ("ven", True): "vˈɛn",      # e as in pet
            ("tur", False): "tˈɜː",     # er as in fur
            ("ble", False): "bˈʌl",     # consonant plus le, "bul"
            ("tion", False): "ʃˈʌn",    # shun
            ("ture", False): "ʧˈɜː",    # cher
            ("cept", True): "sˈɛpt",    # c says s
            ("care", True): "kˈɛː",     # air as in care
            ("point", True): "pˈYnt",   # oy as in coin
            ("stand", True): "stˈand",  # a as in cat
            ("mo", True): "mˈQ",        # oh as in go
        }
        for (chunk, stressed), want in cases.items():
            with self.subTest(chunk=chunk):
                self.assertEqual(T.chunk_phonemes(chunk, stressed), want)

    def test_the_kits_unsure_chunks_are_settled_by_hand(self):
        """A "?" in the recording script means the example word decides.
        With no speaker to decide, FIXES does, for every one shipped."""
        chunks, _ = K.bank_items(SHIPPED_POOLS)
        every, _ = K.bank_items(K.ALL_POOLS)
        unsure = [c for c in chunks if K.respell(c, every[c][0])[1]]
        self.assertTrue(unsure)
        for c in unsure:
            with self.subTest(chunk=c):
                self.assertIn(c, T.FIXES)

    def test_a_chunk_uses_the_whole_bank_to_pick_its_vowel(self):
        """mo is never stressed in the adult pool but is in MO-tor, so
        it says oh, the same whichever pool plays it."""
        items = {stem: ps for stem, _k, _t, ps in T.plan_items(SHIPPED_POOLS)}
        self.assertEqual(items["chunks/mo"], "mˈQ")

    def test_every_item_is_in_symbols_kokoro_knows_with_one_stress(self):
        for stem, kind, _text, ps in T.plan_items(SHIPPED_POOLS):
            if ps is None:
                continue                     # a real word, read by espeak
            with self.subTest(stem=stem):
                self.assertFalse(set(ps) - T.KOKORO_SYMBOLS, ps)
                self.assertEqual(ps.count("ˈ"), 1, ps)

    def test_a_made_up_word_is_its_own_chunks(self):
        from finger_rehab.game.modes.syllables_words import load_pools
        items = {stem: ps for stem, _k, _t, ps in T.plan_items(SHIPPED_POOLS)}
        for w in load_pools()["pseudo"]:
            with self.subTest(word=w.word):
                parts = [items[f"chunks/{speech_stem(c.lower())}"]
                         for c in w.syllables]
                word_ps = items[speech_stem(w.word)]
                self.assertEqual(word_ps.replace("ˈ", ""),
                                 "".join(parts).replace("ˈ", ""))
                # Stressed where the bank says: the mark sits in the
                # stressed chunk's share of the string.
                before = sum(len(p) - p.count("ˈ")
                             for p in parts[:w.stress])
                self.assertLessEqual(before, word_ps.index("ˈ"))

    def test_a_chunk_the_rules_cannot_read_stops_the_run(self):
        with self.assertRaises(ValueError):
            T.chunk_phonemes("zzz", False)


class EspeakToKokoro(unittest.TestCase):
    """espeak's British phonemes into the misaki set Kokoro learnt."""

    def test_the_table(self):
        cases = {"dˈe^ɪ": "dˈA", "ɡˈə^ʊ": "ɡˈQ", "hˈe^ə": "hˈɛː",
                 "nˈi^ə": "nˈɪə", "d^ʒˈɛm": "ʤˈɛm", "t^ʃˈɪp": "ʧˈɪp",
                 "ɐdvˈɛnt": "ədvˈɛnt", "bˈa^ɪ": "bˈI", "kˈa^ʊ": "kˈW",
                 "bˈɔ^ɪ": "bˈY", "rˈɛd": "ɹˈɛd"}
        for espeak, want in cases.items():
            with self.subTest(espeak=espeak):
                self.assertEqual(T.to_misaki(espeak), want)


class ShippedVoice(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((SPEECH / "manifest.json")
                                  .read_text(encoding="utf-8"))

    def test_every_item_the_game_can_play_has_a_file(self):
        chunks, words = K.bank_items(SHIPPED_POOLS)
        stems = ([f"chunks/{speech_stem(c)}" for c in chunks]
                 + [speech_stem(w) for w in words])
        for stem in stems:
            with self.subTest(stem=stem):
                self.assertTrue((SPEECH / f"{stem}.wav").is_file())

    def test_the_manifest_says_what_made_it(self):
        m = self.manifest
        self.assertEqual(m["provider"], "kokoro")
        self.assertEqual(m["voice"], T.VOICE)
        self.assertEqual(m["chunk_form"], "spelling")
        self.assertIn("Apache-2.0", m["licence"])
        for key in ("model", "model_sha256", "rendered_on", "accent"):
            with self.subTest(key=key):
                self.assertTrue(m[key])

    def test_each_file_is_the_mixers_format_and_its_manifest_length(self):
        for stem, rec in self.manifest["entries"].items():
            with self.subTest(stem=stem):
                with wave.open(str(SPEECH / f"{stem}.wav"), "rb") as w:
                    self.assertEqual(w.getframerate(), K.RATE)
                    self.assertEqual(w.getnchannels(), 1)
                    self.assertEqual(w.getsampwidth(), 2)
                    ms = w.getnframes() / w.getframerate() * 1000.0
                self.assertAlmostEqual(ms, rec["duration_ms"], delta=1.0)
                self.assertTrue(rec["phonemes"])

    def test_the_files_were_made_from_todays_rules(self):
        """A rule or a FIXES line changed without a new render leaves
        the files saying the old sounds."""
        entries = self.manifest["entries"]
        for stem, _kind, _text, ps in T.plan_items(SHIPPED_POOLS):
            if ps is not None:
                with self.subTest(stem=stem):
                    self.assertEqual(entries[stem]["phonemes"], ps)

    def test_chunks_share_one_level_and_nothing_clips(self):
        for stem, rec in self.manifest["entries"].items():
            with self.subTest(stem=stem):
                self.assertLess(rec["peak_dbfs"], -1.0)
                if stem.startswith("chunks/"):
                    self.assertAlmostEqual(rec["rms_dbfs"],
                                           K.CHUNK_RMS_DBFS, delta=0.5)

    def test_a_windows_device_name_ships_under_its_underscore(self):
        """con.wav cannot be checked out on Windows, which broke the
        build; the con of confidence is chunks/con_.wav, and the game,
        the kit and this script all ask speech_stem for the name."""
        from tests.test_syllables_mode import _build_mode
        self.assertTrue((SPEECH / "chunks" / "con_.wav").is_file())
        self.assertFalse((SPEECH / "chunks" / "con.wav").exists())
        self.assertIn("chunks/con_", self.manifest["entries"])
        _e, m = _build_mode()
        self.assertEqual(m.chunk_speech_path("con"),
                         SPEECH / "chunks" / "con_.wav")
        self.assertAlmostEqual(
            m.speech_seconds(m.chunk_speech_path("con")),
            self.manifest["entries"]["chunks/con_"]["duration_ms"] / 1000.0,
            places=3)
        plan = K.make_plan(pools=("adult",))
        stems = {it["stem"] for page in plan["pages"]
                 for it in page["items"]}
        self.assertIn("chunks/con_", stems)
        self.assertNotIn("chunks/con", stems)

    def test_the_game_finds_them_and_counts_them_as_spelt(self):
        from tests.test_syllables_mode import _build_mode
        _e, m = _build_mode()
        self.assertEqual(m.chunk_speech_path("ven"),
                         SPEECH / "chunks" / "ven.wav")
        self.assertTrue(m.chunks_spelt("ven"))
        self.assertFalse(m.chunks_spelt("zzz"))
        rec = self.manifest["entries"]["chunks/ven"]
        self.assertAlmostEqual(m.speech_seconds(m.chunk_speech_path("ven")),
                               rec["duration_ms"] / 1000.0, places=3)


if __name__ == "__main__":
    unittest.main()
