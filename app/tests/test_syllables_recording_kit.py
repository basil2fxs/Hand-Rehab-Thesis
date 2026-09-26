"""The Syllables recording kit and the game's side of it.

A recorded voice only helps if every file lands under the right name:
one page with a skipped take would otherwise shift every later chunk
by one, and a child would hear "tur" under the tile that says "bin".
So the cutter refuses a page whose utterance count is off and names
every utterance it heard, and these tests feed it synthetic pages
whose answers are known. The game side: a recorded chunk is played
for every word that holds it, ahead of any older per-word render, and
the model beat waits for a long chunk to finish.
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
from tests.test_syllables_mode import _build_mode  # noqa: E402

RATE = K.RATE


def _page(bursts, noise_db=-70.0, seed=0):
    """A synthetic page: (length s, amplitude, gap after s) tone bursts
    over a faint noise floor."""
    rng = np.random.default_rng(seed)
    out = [np.zeros(int(0.5 * RATE))]
    for dur, amp, gap in bursts:
        t = np.arange(int(dur * RATE)) / RATE
        out.append(amp * np.sin(2 * np.pi * 220.0 * t))
        out.append(np.zeros(int(gap * RATE)))
    x = np.concatenate(out)
    return x + rng.normal(0, 10 ** (noise_db / 20.0), len(x))


def _write(path, x):
    from scipy.io import wavfile
    wavfile.write(str(path), RATE,
                  np.clip(x * 32767, -32768, 32767).astype(np.int16))


PAGE = {"page": 1, "file": "page_01.wav", "items": [
    {"n": 1, "kind": "chunk", "text": "ter", "stem": "chunks/ter"},
    {"n": 2, "kind": "word", "text": "tiger", "stem": "tiger"},
    {"n": 3, "kind": "chunk", "text": "ban", "stem": "chunks/ban"},
]}


class Hints(unittest.TestCase):
    def test_the_rules_the_speaker_reads(self):
        self.assertEqual(K.respell("ter", False)[0], "er as in her")
        self.assertEqual(K.respell("ban", False)[0], "a as in cat")
        self.assertEqual(K.respell("ti", True)[0], "eye as in pie")
        self.assertEqual(K.respell("ti", False)[0], "i as in sit")
        self.assertEqual(K.respell("ty", False)[0], "ee as in happy")
        self.assertEqual(K.respell("tle", False)[0],
                         "tul (light, as in little)")
        self.assertEqual(K.respell("tion", False)[0], "shun")
        self.assertIn("c says s", K.respell("cer", False)[0])

    def test_two_readings_are_flagged(self):
        for chunk in ("bread", "cou", "rine", "gen"):
            self.assertTrue(K.respell(chunk, False)[1], chunk)
        for chunk in ("ter", "ban", "cum"):
            self.assertFalse(K.respell(chunk, False)[1], chunk)


class ThePlan(unittest.TestCase):
    def test_every_chunk_and_word_once_and_repeatable(self):
        chunks, words = K.bank_items()
        plan = K.make_plan(seed=5, page_size=50)
        stems = [i["stem"] for p in plan["pages"] for i in p["items"]]
        self.assertEqual(len(stems), len(set(stems)))
        # File names, so a Windows device name (con) carries its
        # underscore.
        from finger_rehab.game.modes.syllables_words import speech_stem
        self.assertEqual(set(stems),
                         {f"chunks/{speech_stem(c)}" for c in chunks}
                         | {speech_stem(w) for w in words})
        again = K.make_plan(seed=5, page_size=50)
        self.assertEqual(plan["pages"], again["pages"])
        self.assertTrue(all(len(p["items"]) <= 50 for p in plan["pages"]))

    def test_examples_show_where_the_stress_falls(self):
        chunks, _w = K.bank_items()
        stressed, examples = chunks["mu"]
        self.assertTrue(stressed)
        self.assertTrue(any("MU" in e for e in examples))


class TheCutter(unittest.TestCase):
    def test_a_clean_page_lands_every_file_under_its_name(self):
        # Two takes per item; the first take of "ter" is clipped, so
        # the second must be kept.
        x = _page([(0.25, 1.2, 0.9), (0.25, 0.3, 1.8),
                   (0.6, 0.2, 0.9), (0.6, 0.25, 1.8),
                   (0.3, 0.1, 0.9), (0.3, 0.12, 1.5)])
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write(td / "page_01.wav", x)
            recs = K.cut_page(PAGE, td / "page_01.wav", td / "speech")
            self.assertEqual(set(recs), {"chunks/ter", "tiger",
                                         "chunks/ban"})
            self.assertEqual(recs["chunks/ter"]["take"], 2)
            for stem, rec in recs.items():
                self.assertTrue((td / "speech" / f"{stem}.wav").exists())
                self.assertLessEqual(rec["peak_dbfs"],
                                     K.PEAK_CEILING_DBFS + 0.05)
            for stem in ("chunks/ter", "chunks/ban"):
                r = recs[stem]
                if not r["limited"]:
                    self.assertAlmostEqual(r["rms_dbfs"], K.CHUNK_RMS_DBFS,
                                           delta=0.3)
            # Trimmed to the burst plus 10 ms lead and 50 ms tail.
            self.assertAlmostEqual(recs["chunks/ban"]["duration_ms"],
                                   300 + 60, delta=25)
            from scipy.io import wavfile
            rate, y = wavfile.read(str(td / "speech" / "tiger.wav"))
            self.assertEqual(rate, RATE)
            self.assertEqual(y.dtype, np.int16)
            self.assertEqual(y.ndim, 1)

    def test_a_missing_take_writes_nothing_and_says_where(self):
        x = _page([(0.25, 0.3, 0.9), (0.25, 0.3, 1.8),
                   (0.6, 0.2, 1.8),
                   (0.3, 0.1, 0.9), (0.3, 0.12, 1.5)])
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write(td / "page_01.wav", x)
            with self.assertRaises(ValueError) as cm:
                K.cut_page(PAGE, td / "page_01.wav", td / "speech")
            self.assertIn("5 utterances, expected 6", str(cm.exception))
            self.assertFalse((td / "speech").exists())

    def test_a_pause_inside_a_word_is_not_a_new_take(self):
        # kangaroo's stop closures leave gaps well under 180 ms.
        x = _page([(0.2, 0.3, 0.08), (0.2, 0.3, 0.9), (0.4, 0.3, 1.5)])
        with tempfile.TemporaryDirectory() as td:
            _write(Path(td) / "p.wav", x)
            spans = K.utterances(K.read_wav(Path(td) / "p.wav"))
        self.assertEqual(len(spans), 2)

    def test_the_manifest_keeps_earlier_pages_and_guards_other_audio(self):
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            K.write_manifest(out, {"chunks/ter": {"duration_ms": 300}},
                             "BT", "USB")
            K.write_manifest(out, {"tiger": {"duration_ms": 600}}, "BT",
                             "USB")
            m = json.loads((out / "manifest.json").read_text())
            self.assertEqual(set(m["entries"]), {"chunks/ter", "tiger"})
            self.assertEqual(m["chunk_form"], "spelling")
            self.assertEqual(m["accent"], "en-AU")
            (out / "manifest.json").write_text(json.dumps(
                {"provider": "google", "entries": {}}))
            with self.assertRaises(SystemExit):
                K.write_manifest(out, {}, "BT", "USB")


class TheGameSide(unittest.TestCase):
    def test_a_recorded_chunk_wins_and_stretches_the_beat(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "chunks").mkdir()
            _engine, mode = _build_mode(
                speech={"backend": "file", "dir": str(root)})
            mode._begin_word(0.0)
            chunk = mode.word.syllables[0]
            _write(root / f"{mode.word.word}_0.wav", np.zeros(RATE // 10))
            self.assertEqual(mode.chunk_speech_path(chunk), None)
            self.assertAlmostEqual(mode.model_ioi_s(0), mode.ioi_s)
            _write(root / "chunks" / f"{chunk}.wav",
                   np.zeros(int(0.7 * RATE)))
            self.assertEqual(mode.chunk_speech_path(chunk),
                             root / "chunks" / f"{chunk}.wav")
            self.assertAlmostEqual(mode.model_ioi_s(0), 0.85, delta=0.01)


if __name__ == "__main__":
    unittest.main()
