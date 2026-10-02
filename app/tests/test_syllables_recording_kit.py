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
            # Chunks and words share one loudness.
            for r in recs.values():
                if not r["limited"]:
                    self.assertAlmostEqual(r["loudness"], K.SPEECH_LOUDNESS,
                                           delta=0.3)
            # Trimmed to the burst plus 10 ms lead and 30 ms tail.
            self.assertAlmostEqual(recs["chunks/ban"]["duration_ms"],
                                   300 + 40, delta=25)
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


def _voice(dur=0.3, amp=0.3, decay=0.03):
    """A vowel-like tone that dies away over `decay` seconds."""
    t = np.arange(int(dur * RATE)) / RATE
    env = np.minimum(1.0, (dur - t) / decay)
    return amp * env * np.sin(2 * np.pi * 220.0 * t)


def _after(x, *parts):
    return np.concatenate([x] + [np.asarray(p, dtype=float) for p in parts])


def _quiet(s, seed=1):
    return np.random.default_rng(seed).normal(0, 10 ** (-80 / 20),
                                              int(s * RATE))


def _tick(ms=5, amp=0.02, fall_ms=2.0):
    """A click: a broad burst that dies within a few ms."""
    t = np.arange(int(ms / 1000 * RATE)) / RATE
    return amp * np.exp(-t / (fall_ms / 1000)) * np.sin(2 * np.pi * 3000 * t)


def _release(ms=30, amp=0.03, seed=2, tau=0.009):
    """A stop's release: noise that takes about 20 ms to fall 20 dB."""
    t = np.arange(int(ms / 1000 * RATE)) / RATE
    rng = np.random.default_rng(seed)
    return amp * np.exp(-t / tau) * rng.normal(0, 1, len(t))


class TheFinish(unittest.TestCase):
    """The click, tail and loudness steps of 2 October 2026: a tick the
    synthetic voice leaves after a word goes, a stop's release stays."""

    def test_a_tick_after_a_vowel_is_silenced(self):
        x = _after(_voice(), _quiet(0.03), _tick(), _quiet(0.05))
        for ends in ("vowel", "other", "stop"):
            y, hit = K.drop_end_click(x, ends)
            self.assertTrue(hit, ends)
            self.assertLess(np.abs(y[-int(0.06 * RATE):]).max(), 1e-3)
            self.assertTrue(np.array_equal(y[:len(_voice())],
                                           x[:len(_voice())]))

    def test_a_stops_own_release_is_kept(self):
        x = _after(_voice(), _quiet(0.04), _release(), _quiet(0.05))
        y, hit = K.drop_end_click(x, "stop")
        self.assertFalse(hit)
        self.assertTrue(np.array_equal(y, x))

    def test_after_a_release_the_tick_still_goes(self):
        x = _after(_voice(), _quiet(0.04), _release(), _quiet(0.03),
                   _tick(), _quiet(0.04))
        y, hit = K.drop_end_click(x, "stop")
        self.assertTrue(hit)
        n = len(_voice()) + int(0.04 * RATE) + len(_release())
        self.assertTrue(np.array_equal(y[:n], x[:n]))

    def test_a_pop_with_a_tail_goes_only_after_a_long_vowel(self):
        # A pop whose tail stays within 20 dB of it for over 25 ms: only
        # the long-vowel window takes it. After a short vowel the same
        # shape could be a brief uh, so it stays.
        pop = _after(_tick(ms=3, amp=0.08),
                     _release(ms=60, amp=0.02, tau=0.012))
        x = _after(_voice(), _quiet(0.03), pop, _quiet(0.02))
        y, hit = K.clean(x, "vowel")
        self.assertTrue(hit)
        self.assertLess(np.abs(y[len(_voice()):]).max(), 1e-3)
        _y2, hit2 = K.clean(x, "other")
        self.assertFalse(hit2)

    def test_the_end_kind_comes_from_the_last_sound(self):
        self.assertEqual(K.end_kind("ˈaksɪdənt"), "stop")
        self.assertEqual(K.end_kind("tˈɪst"), "stop")
        self.assertEqual(K.end_kind("ˈanʤ"), "stop")
        self.assertEqual(K.end_kind("bˈiː"), "vowel")
        self.assertEqual(K.end_kind("ɡQ"), "vowel")
        self.assertEqual(K.end_kind("lˈadə"), "other")
        self.assertEqual(K.end_kind("mˈɪs"), "other")
        self.assertEqual(K.end_kind(None), "stop")

    def test_the_tail_ends_30_ms_after_the_sound_and_fades(self):
        x = _after(_voice(), _quiet(0.3))
        y = K.trim_tail(x)
        self.assertAlmostEqual(len(y) / RATE, len(_voice()) / RATE + 0.03,
                               delta=0.004)
        self.assertLess(abs(y[-1]), 1e-4)

    def test_tidy_runs_once_and_levels_every_file(self):
        from types import SimpleNamespace
        with tempfile.TemporaryDirectory() as td:
            out = Path(td)
            (out / "chunks").mkdir()
            _write(out / "tiger.wav", _after(_voice(0.5, 0.1), _quiet(0.03),
                                             _tick(), _quiet(0.05)))
            _write(out / "chunks" / "ti.wav", _after(_voice(0.3, 0.4),
                                                     _quiet(0.06)))
            (out / "manifest.json").write_text(json.dumps({
                "provider": "kokoro", "chunk_rms_dbfs": -20.0,
                "word_loudness": -23.0, "entries": {
                    "tiger": {"phonemes": "tˈIɡə", "duration_ms": 1},
                    "chunks/ti": {"phonemes": "tˈI", "duration_ms": 1}}}))
            args = SimpleNamespace(speech_dir=str(out))
            K.cmd_tidy(args)
            first = {p.name: p.read_bytes() for p in out.rglob("*.wav")}
            m = json.loads((out / "manifest.json").read_text())
            self.assertNotIn("chunk_rms_dbfs", m)
            self.assertEqual(m["finish"], K.FINISH_VERSION)
            for stem, rec in m["entries"].items():
                self.assertAlmostEqual(rec["loudness"], K.SPEECH_LOUDNESS,
                                       delta=0.3)
                self.assertEqual(rec["finish"], K.FINISH_VERSION)
                with self.subTest(stem=stem):
                    ms = len(K.read_wav(out / f"{stem}.wav")) / RATE * 1000
                    self.assertAlmostEqual(ms, rec["duration_ms"], delta=1.0)
            self.assertTrue(m["entries"]["tiger"]["click_removed"])
            K.cmd_tidy(args)
            self.assertEqual(first, {p.name: p.read_bytes()
                                     for p in out.rglob("*.wav")})


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
            self.assertEqual(mode.syllable_file(0),
                             root / f"{mode.word.word}_0.wav")
            self.assertAlmostEqual(mode.model_ioi_s(0), max(
                mode.ioi_s, 0.1 + mode.MODEL_GAP_S), delta=0.01)
            _write(root / "chunks" / f"{chunk}.wav",
                   np.zeros(int(0.7 * RATE)))
            self.assertEqual(mode.chunk_speech_path(chunk),
                             root / "chunks" / f"{chunk}.wav")
            self.assertEqual(mode.syllable_file(0),
                             root / "chunks" / f"{chunk}.wav")
            self.assertAlmostEqual(mode.model_ioi_s(0),
                                   0.7 + mode.MODEL_GAP_S, delta=0.01)


if __name__ == "__main__":
    unittest.main()
