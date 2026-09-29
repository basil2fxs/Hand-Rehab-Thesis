#!/usr/bin/env python3
"""Make the Syllables voice with Kokoro, a free text-to-speech model.

    python3.12 -m venv tts && tts/bin/pip install kokoro-onnx scipy
    tts/bin/python scripts/syllables_tts.py --model kokoro-v1.0.onnx \\
        --voices voices-v1.0.bin
    tts/bin/python scripts/syllables_tts.py --only chunks/ven,tiger \\
        --out /tmp/try          # a few items somewhere else, to listen
    tts/bin/python scripts/syllables_tts.py --syllables-only \\
        --model kokoro-v1.0.onnx --voices voices-v1.0.bin
    python3 scripts/syllables_tts.py --syllables-only --dry-run
                                # each word's syllables, no model needed

kokoro-v1.0.onnx (310 MB) and voices-v1.0.bin (26 MB) are the
model-files-v1.0 release of github.com/thewh1teagle/kokoro-onnx. Neither
belongs in git; only the files this writes do.

WHY THIS VOICE. Kokoro-82M's weights are Apache 2.0, so audio made with
it can ship inside the app. It runs on a laptop CPU in well under a
second per item, and it takes phonemes as well as text, which is what a
lone chunk needs: read as text, "ous" comes out as "ooze" and "tle" as
three letter names. It has no Australian voice. The only free model
that does (MeloTTS, EN-AU) reads text only, so every chunk would be a
guess. bf_emma is the best graded of Kokoro's British voices (B-, the
model card's VOICES.md). A recorded Australian speaker is still the
better stimulus (docs/research/new_modes/syllables-all-ages.md, D1);
syllables_recording_kit.py cut replaces these files when one exists.

HOW A CHUNK IS SAID. Exactly as the recording kit tells a speaker to
say it: a spelling pronunciation, built from the kit's own hint rules
(respell), worked out over the whole bank so a chunk sounds the same
whichever age pool asks for it. FIXES holds the few chunks where the
rules misread a spelling (qu, wh, a second vowel) and the kit's "?"
chunks, settled by their example words. A chunk the rules cannot turn
into sounds stops the run rather than being guessed.

HOW A WORD IS SAID. A real word is read naturally from text by
espeak-ng (British). A made-up word is its own chunks run together,
stressed where the bank says, so it holds exactly the chunks the game
plays for it: espeak guesses at them and read "dol" as "dole" in one
word and "doll" in the next.

HOW A WORD'S SYLLABLES ARE SAID (29 September 2026). As they sound
in that word, not as spelt: the word's own phonemes are cut at its
written chunks (word_syllables) and each piece is said on its own,
stressed so it is clear. So the "ger" of tiger is "guh" and the "ger"
of ginger is "juh", where one spelt file said "jer" for both. This is
the graphosyllabic method the mode rests on (Bhattacharya and Ehri
2004): each syllable as close as it can be to its sound in the whole
word, then the syllables blended back into the word. The cut matches
the consonant sounds each chunk's letters spell against the word's
phonemes (a double letter closes one syllable and opens the next:
rab-bit), and a syllable running speech drops is given back the
vowel a careful speaker says (cam-e-ra). A piece that sounds exactly
like its chunk's spelt file reuses that file, so only the syllables
that differ are made (--syllables-only). The manifest's syllable_map
names each word's files in order and which of them have a weak vowel
(uh, ih), where ter, tar and tur sound alike and the game stops
offering vowel foils.

Both then go into Kokoro in the phoneme symbols it was trained on (the
misaki set: "A" for the vowel in day, "Q" for the one in go, "ʤ" for
the j in jam), through the kit's own trim, fade and level (finish), and
out as 44.1 kHz 16-bit mono WAV beside a manifest.json naming the
model, the voice, the date and each file's phonemes, length and level.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import date
from pathlib import Path

import numpy as np

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP / "scripts"))

import syllables_recording_kit as kit  # noqa: E402

VOICE = "bf_emma"

# The kit's vowel hints, as sounds. Every hint respell() can give has to
# be here: a new one fails loudly instead of being said wrong.
HINT_SOUND = {
    "a as in cat": "a", "e as in pet": "ɛ", "i as in sit": "ɪ",
    "o as in hot": "ɒ", "u as in cup": "ʌ", "i as in gym": "ɪ",
    "ay as in day": "A", "ee as in see": "iː", "eye as in pie": "I",
    "oh as in go": "Q", "you as in cute": "juː", "eye as in my": "I",
    "eye as in high": "I", "air as in hair": "ɛː", "air as in care": "ɛː",
    "ear as in near": "ɪə", "ear as in deer": "ɪə", "our as in sour": "Wə",
    "or as in door": "ɔː", "or as in more": "ɔː", "or as in roar": "ɔː",
    "ar as in car": "ɑː", "er as in her": "ɜː", "er as in bird": "ɜː",
    "er as in fur": "ɜː", "or as in for": "ɔː", "ee as in sea": "iː",
    "ay as in rain": "A", "oh as in boat": "Q", "oh as in toe": "Q",
    "oo as in moon": "uː", "ow as in out": "W", "ow as in cow": "W",
    "oy as in coin": "Y", "oy as in boy": "Y", "or as in sauce": "ɔː",
    "or as in saw": "ɔː", "oo as in blue": "uː", "oo as in new": "uː",
    "ay as in vein": "A", "ee as in key": "iː", "ee as in happy": "iː",
    "o as in want?": "ɒ",
}
# The kit's endings (tion, ture, ous...) as sounds.
ENDING_SOUND = {"shun": "ʃˈʌn", "cher": "ʧˈɜː", "shul": "ʃˈʌl",
                "us as in famous": "ˈʌs"}

# Chunks said by hand, each for a reason the rules cannot see.
FIXES = {
    # qu is one consonant pair; respell() takes its u for the vowel.
    "qual": "kwˈɒl", "quate": "kwˈAt", "quire": "kwˈIə",
    # wh plus a says o, as the kit already does for wa and qua.
    "what": "wˈɒt",
    # A second vowel the rules never reach.
    "lia": "lˈɪə", "oped": "ˈɒpt",
    # The "?" chunks, settled by their example words. Listed even where
    # the rules already agree, so the choice is written down once.
    "coun": "kˈWn",           # coun-ter-pro-DUC-tive
    "gen": "ʤˈɛn",            # GEN-er-al, e-mer-GEN-cy
    "get": "ɡˈɛt",            # un-for-GET-ta-ble
    "gy": "ʤˈiː",             # psy-CHOL-o-gy
    "liev": "lˈiːv",          # un-be-LIEV-a-ble
    "out": "ˈWt",             # out-STAND-ing
    "sion": "ʒˈʌn",           # oc-CA-sion-al-ly
    "sive": "sˈɪv",           # de-FEN-sive
    "tage": "tˈAʤ",           # dis-ad-VAN-tage
    "tise": "tˈIz",           # ad-VER-tise-ment
    "tive": "tˈɪv",           # coun-ter-pro-DUC-tive
    "y": "ˈiː",               # a-NAL-y-sis, un-NEC-es-sar-y
    # The child and teen bank. First the spellings the rules cannot
    # parse (a second vowel, qu, an ending after more letters).
    "beau": "bjˈuː", "cious": "ʃˈʌs", "cuit": "kˈɪt", "ery": "ˈɛɹi",
    "fire": "fˈIə", "gua": "ɡwˈɑː", "gui": "ɡˈɪ", "guin": "ɡwˈɪn",
    "ion": "jˈʌn", "ished": "ˈɪʃt", "juic": "ʤˈuːs", "lion": "ljˈʌn",
    "quan": "kwˈɒn", "quar": "kwˈɛː", "qui": "kwˈI", "quo": "kwˈɒ",
    "quok": "kwˈɒk", "ques": "kwˈɛs", "squir": "skwˈɪ", "sure": "ʒˈɜː",
    "dles": "dˈʌlz", "chute": "ʃˈuːt", "tech": "tˈɛk", "cean": "ʃˈʌn",
    "tient": "ʃˈʌnt", "view": "vjˈuː", "friend": "fɹˈɛnd",
    "wave": "wˈAv",
    # An s that says z, as the example words say it.
    "cise": "sˈIz", "ise": "ˈIz", "ers": "ˈɜːz", "pers": "pˈɜːz",
    "sers": "sˈɜːz", "lars": "lˈɑːz", "dals": "dˈalz", "sors": "sˈɔːz",
    "news": "njˈuːz", "nois": "nˈYz", "toise": "tˈYz", "tens": "tˈɛnz",
    # The child bank's "?" chunks, settled by their example words.
    "age": "ˈAʤ", "ange": "ˈanʤ", "bage": "bˈAʤ", "lage": "lˈAʤ",
    "rage": "ɹˈAʤ", "sage": "sˈAʤ", "range": "ɹˈAnʤ",
    "bey": "bˈA", "eigh": "ˈA", "neigh": "nˈA", "rein": "ɹˈAn",
    "ea": "ˈiː", "pea": "pˈiː", "sea": "sˈiː", "tea": "tˈiː",
    "dream": "dɹˈiːm", "lead": "lˈiːd", "read": "ɹˈiːd",
    "sneak": "snˈiːk", "break": "bɹˈAk", "bread": "bɹˈɛd",
    "head": "hˈɛd", "hea": "hˈɛ", "fea": "fˈɛ", "trea": "tɹˈɛ",
    "fear": "fˈɪə", "pear": "pˈɪə",
    "ey": "ˈiː", "key": "kˈiː", "ney": "nˈiː",
    "boo": "bˈuː", "coot": "kˈuːt", "doo": "dˈuː", "moon": "mˈuːn",
    "noo": "nˈuː", "noon": "nˈuːn", "poo": "pˈuː", "proof": "pɹˈuːf",
    "roo": "ɹˈuː", "room": "ɹˈuːm", "roon": "ɹˈuːn", "roos": "ɹˈuːs",
    "scoot": "skˈuːt", "spoon": "spˈuːn", "too": "tˈuː",
    "tooth": "tˈuːθ", "foot": "fˈʊt", "hood": "hˈʊd", "kook": "kˈʊk",
    "bou": "bˈuː", "cou": "kˈʌ", "cour": "kˈʌ", "bour": "bˈWə",
    "our": "ˈWə", "vour": "vˈWə", "cloud": "klˈWd", "ground": "ɡɹˈWnd",
    "moun": "mˈWn", "trou": "tɹˈW", "shoul": "ʃˈQl",
    "bow": "bˈQ", "dow": "dˈQ", "low": "lˈQ", "ow": "ˈQ", "row": "ɹˈQ",
    "snow": "snˈQ", "flow": "flˈW", "pow": "pˈW", "tow": "tˈW",
    "cine": "sˈIn", "cite": "sˈIt", "dile": "dˈIl", "dise": "dˈIs",
    "fice": "fˈIs", "gine": "ʤˈIn", "ite": "ˈIt", "lite": "lˈIt",
    "mime": "mˈIm", "mite": "mˈIt", "nine": "nˈIn", "pie": "pˈI",
    "pine": "pˈIn", "rice": "ɹˈIs", "shine": "ʃˈIn",
    "ine": "ˈiːn", "line": "lˈiːn", "rine": "ɹˈiːn", "zine": "zˈiːn",
    "ge": "ʤˈɛ", "gec": "ɡˈɛk", "ger": "ʤˈɜː", "ges": "ʤˈɛs",
    "gi": "ʤˈI", "gin": "ɡˈɪn", "ging": "ʤˈɪŋ",
    "wa": "wˈɒ", "wal": "wˈɒl",
    # A stressed chunk said as it sounds in its word (the kit's rule 1),
    # where the letter rules give another vowel.
    "bull": "bˈʊl", "cush": "kˈʊʃ", "won": "wˈʌn", "cov": "kˈʌv",
    "gov": "ɡˈʌv", "shov": "ʃˈʌv", "some": "sˈʌm", "love": "lˈʌv",
    "have": "hˈav", "prove": "pɹˈuːv", "gold": "ɡˈQld", "kind": "kˈInd",
    "hind": "hˈInd",
    # Sight words and patterns every reader knows, which the letter
    # rules misread: come, one, ball, fall, paste, cue, few, fly.
    "come": "kˈʌm", "one": "wˈʌn", "ball": "bˈɔːl", "fall": "fˈɔːl",
    "paste": "pˈAst", "cue": "kjˈuː", "ew": "ˈjuː", "fly": "flˈI",
    "fy": "fˈI",
}
# Real words espeak misreads, said as Australians say them.
WORD_FIXES = {"echidna": "ɪkˈɪdnə", "cassowary": "kˈasəwɛːɹi",
              "galah": "ɡəlˈɑː"}
# Onsets whose letters have two common readings, settled by the words
# the chunk comes from.
ONSET_FIXES = {"chi": "k", "chol": "k", "the": "ð", "chor": "k",
               "ches": "k", "char": "k", "chan": "k", "chid": "k"}

VOWELS = kit.VOWELS
DIGRAPHS = (("tch", "ʧ"), ("sch", "sk"), ("ch", "ʧ"), ("sh", "ʃ"),
            ("th", "θ"), ("ph", "f"), ("wh", "w"), ("ck", "k"), ("ng", "ŋ"),
            ("nk", "ŋk"), ("qu", "kw"), ("gh", ""), ("kn", "n"),
            ("wr", "ɹ"), ("ps", "s"), ("gn", "n"), ("dg", "ʤ"), ("rh", "ɹ"),
            ("mn", "m"))
# British English drops the y sound of "you" after these (ruler, super).
NO_YOD_AFTER = ("ɹ", "l", "s", "z", "ʧ", "ʤ", "j")
LETTER = {"b": "b", "c": "k", "d": "d", "f": "f", "g": "ɡ", "h": "h",
          "j": "ʤ", "k": "k", "l": "l", "m": "m", "n": "n", "p": "p",
          "q": "k", "r": "ɹ", "s": "s", "t": "t", "v": "v", "w": "w",
          "x": "ks", "y": "j", "z": "z"}
# Only these reach the model, so a symbol outside them is a mistake here.
KOKORO_SYMBOLS = set("AIQTWYabdefhijklmnopstuvwzæðŋɑɒɔəɛɜɡɪɹʃʊʌʒʤʧθːˈˌᵊ")


def consonants(letters: str, after: str = "") -> str:
    """Consonant letters as sounds. `after` is whatever follows them in
    the chunk, for a soft c or g (cept, gen, tage)."""
    out, i = [], 0
    while i < len(letters):
        soft = (letters[i + 2:] + after)[:1] in ("e", "i", "y")
        if letters.startswith("ng", i) and soft:
            out.append("nʤ")                 # range, orange
            i += 2
            continue
        if letters.startswith("sc", i) and soft:
            out.append("s")                  # science, scissors
            i += 2
            continue
        if letters.startswith("gh", i) and i == 0:
            out.append("ɡ")                  # spaghetti, yoghurt
            i += 2
            continue
        for dg, sound in DIGRAPHS:
            if letters.startswith(dg, i) and not (dg == "ps" and i > 0):
                out.append(sound)
                i += len(dg)
                break
        else:
            ch = letters[i]
            nxt = (letters[i + 1:] + after)[:1]
            if i + 1 < len(letters) and letters[i + 1] == ch:
                i += 1                       # a double letter says one
                continue
            if ch == "c" and nxt in ("e", "i", "y"):
                out.append("s")
            elif ch == "g" and nxt in ("e", "i", "y"):
                out.append("ʤ")
            elif ch in LETTER:
                out.append(LETTER[ch])
            else:
                raise ValueError(f"no sound for {ch!r} in {letters!r}")
            i += 1
    return "".join(out)


def chunk_phonemes(chunk: str, stressed: bool) -> str:
    """One chunk's spelling pronunciation as Kokoro phonemes, stress
    mark before the vowel as espeak writes it (vˈɛn)."""
    c = chunk.lower()
    if c in FIXES:
        return FIXES[c]
    hint = kit.respell(c, stressed)[0]
    if len(c) >= 3 and c.endswith("le") and c[-3] not in VOWELS:
        return consonants(c[:-2]) + "ˈʌl"          # ble, tle: "bul"
    for end, sound, _doubt in kit.ENDINGS:
        if c.endswith(end):
            if c[:-len(end)]:
                raise ValueError(f"{c!r}: an ending after more letters; "
                                 f"add it to FIXES")
            return ENDING_SOUND[sound]
    first = next((i for i, ch in enumerate(c) if ch in VOWELS
                  and not (ch == "y" and i == 0)), None)
    if first is None:
        raise ValueError(f"{c!r} has no vowel the rules can read; "
                         f"add it to FIXES")
    vowel = HINT_SOUND[hint.split(",")[0].strip()]
    onset = c[:first]
    for team, _sound, _doubt in kit.TEAMS:
        if c.startswith(team, first):
            rest = c[first + len(team):]
            break
    else:
        rest = c[first + 1:]
    after = ""
    if len(rest) >= 2 and rest.endswith("e") and rest[-2] not in VOWELS:
        rest, after = rest[:-1], "e"                   # the e is silent
    if any(ch in VOWELS for ch in rest):
        raise ValueError(f"{c!r}: a second vowel the rules never reach; "
                         f"add it to FIXES")
    lead = ONSET_FIXES.get(c)
    lead = lead if lead is not None else consonants(onset, c[first])
    if vowel == "juː" and lead.endswith(NO_YOD_AFTER):
        vowel = "uː"
    # An r after the vowel is silent: British and Australian English
    # are not rhotic, and a chunk is said on its own (DI-no-saur).
    return lead + "ˈ" + vowel + consonants(rest.replace("r", ""), after)


# ---- whole words -------------------------------------------------------------

# espeak's British phonemes into the misaki set Kokoro was trained on:
# misaki's own EspeakFallback table (github.com/hexgrad/misaki,
# espeak.py), with its British lines. The SQUARE vowel goes first, before
# the lone e turns into A under it.
E2M = sorted({
    "a^ɪ": "I", "a^ʊ": "W", "d^ʒ": "ʤ", "e^ɪ": "A", "e": "A",
    "t^ʃ": "ʧ", "ɔ^ɪ": "Y", "ə^l": "ᵊl", "ɚ": "əɹ", "r": "ɹ", "x": "k",
    "ç": "k", "ɐ": "ə", "ɬ": "l", "\u0303": "",
}.items(), key=lambda kv: -len(kv[0]))


def to_misaki(ps: str) -> str:
    ps = ps.replace("e^ə", "ɛː")
    for old, new in E2M:
        ps = ps.replace(old, new)
    ps = re.sub("(\\S)\u0329", "ᵊ\\1", ps)
    ps = ps.replace("i^ə", "ɪə").replace("iə", "ɪə")
    ps = ps.replace("ə^ʊ", "Q").replace("o", "ɔ")
    # Kokoro v1.0 predates misaki's own symbols for these two.
    ps = ps.replace("ɾ", "T").replace("ʔ", "t")
    return ps.replace("^", "")


def pseudo_phonemes(syllables, stress: int, stressed_anywhere) -> str:
    """A made-up word from its chunks' own sounds, primary stress on the
    bank's stressed syllable and nowhere else."""
    parts = []
    for k, chunk in enumerate(syllables):
        ps = chunk_phonemes(chunk, stressed_anywhere(chunk))
        parts.append(ps if k == stress else ps.replace("ˈ", ""))
    return "".join(parts)


# ---- a word's own syllables --------------------------------------------------

# Vowel symbols of the misaki set; ᵊ marks a syllabic l or n (bottle).
VOWEL_SOUNDS = frozenset("AIQWYaæeiouɑɒɔəɛɜɪʊʌᵊ")
STRESS_MARKS = "ˈˌ"
# A vowel that loses its letter's sound when unstressed: ter, tar and
# tur all come out as "tuh", be and bi as "bih".
WEAK_VOWELS = frozenset({"ə", "ᵊ", "ɪ", "i"})
# Sounds one spelling gives in different words, so a mismatch between
# them costs half a substitution: n before k or g (finger), s as z
# (lars), t or s as sh or ch (tion, ture, sure), soft and hard c and g.
NEAR = frozenset(frozenset(p) for p in (
    ("n", "ŋ"), ("s", "z"), ("s", "ʃ"), ("t", "ʧ"), ("d", "ʤ"), ("z", "ʒ"),
    ("s", "ʒ"), ("t", "ʃ"), ("k", "ʃ"), ("ɡ", "ʤ"), ("k", "s")))
# A vowel put back into a syllable running speech drops (cam-e-ra):
# the one its letter suggests.
PUT_BACK = {"i": "ɪ", "y": "i"}


def phoneme_tokens(ps: str) -> list[tuple[str, str, str]]:
    """(V or C, sound, stress mark) per sound. A long mark joins its
    vowel; ɪə and ʊə are one vowel until the chunks say otherwise."""
    out, pending, i = [], "", 0
    while i < len(ps):
        ch = ps[i]
        if ch in STRESS_MARKS:
            pending = ch
            i += 1
            continue
        if ch in VOWEL_SOUNDS:
            sound = ch
            i += 1
            if i < len(ps) and ps[i] == "ː":
                sound += "ː"
                i += 1
            if sound in ("ɪ", "ʊ") and i < len(ps) and ps[i] == "ə":
                sound += "ə"
                i += 1
            out.append(("V", sound, pending))
            pending = ""
            continue
        out.append(("C", "t" if ch == "T" else ch, ""))
        i += 1
    return out


def letter_edges(chunk: str, last: bool = True) -> tuple[str, str, str]:
    """(onset letters, coda letters, first vowel letter) of a chunk.
    A final consonant plus le is its own syllable only at a word's end
    (ta-ble, noo-dles, not cle-ver); a silent final e leaves the
    consonant before it as the coda (some, tive)."""
    c = chunk.lower()
    vowel = []
    for i, ch in enumerate(c):
        v = ch in "aeiou" or (ch == "y" and not (
            i == 0 and i + 1 < len(c) and c[i + 1] in "aeiou"))
        if ch == "w" and i > 0 and c[i - 1] in "aeo":
            v = True                          # aw, ew, ow
        vowel.append(v)
    if not any(vowel):
        return c, "", ""
    a = vowel.index(True)
    b = len(c) - vowel[::-1].index(True)
    onset, coda = c[:a], c[b:]
    base = c[:-1] if c.endswith("les") else c
    if (last and base.endswith("le") and len(base) >= 3
            and base[-3] not in "aeiou"):
        onset, coda = base[:-2], "l" + c[len(base):]
    elif len(c) >= 3 and c.endswith("e") and not vowel[-2] and any(
            vowel[:-2]):
        j = len(c) - 1
        while j > 0 and not vowel[j - 1]:
            j -= 1
        coda = c[j:-1]
    return onset, coda, c[a]


def _spelt(letters: str, after: str = "") -> list[str]:
    if not letters:
        return []
    try:
        return [s for s in consonants(letters, after)]
    except ValueError:
        return list(letters)


def _edges(chunk: str, nxt: str) -> tuple:
    """The consonant sounds a chunk's letters spell at each edge. An r
    after the vowel is silent (non-rhotic) but may link to the next
    syllable (fer-ent, rent); a u may carry a y sound (u-ni, cu-cum)."""
    onset, coda, v = letter_edges(chunk, last=not nxt)
    on = _spelt(onset, v)
    co = [s for s in _spelt(coda, nxt[:1]) if s != "ɹ"]
    return on, co, "r" in coda, v


def _dist(want, got, free_first=(), free_last=()) -> float:
    """Edit distance between spelt and heard sounds: substitute 2, a
    near sound 1, add or drop 1. A linking r first in `got`, or a y
    sound last before its vowel, costs nothing."""
    want, got = list(want), list(got)
    if got and got[0] in free_first and (not want or want[0] != got[0]):
        got = got[1:]
    if got and got[-1] in free_last and (not want or want[-1] != got[-1]):
        got = got[:-1]
    d = [[float(i + j) if i == 0 or j == 0 else 0.0
          for j in range(len(got) + 1)] for i in range(len(want) + 1)]
    for i in range(1, len(want) + 1):
        for j in range(1, len(got) + 1):
            a, b = want[i - 1], got[j - 1]
            sub = 0 if a == b else (1 if frozenset((a, b)) in NEAR else 2)
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1,
                          d[i - 1][j - 1] + sub)
    return d[-1][-1]


def _cut(tokens, chunks):
    """(pieces, cost) with one vowel per chunk, or None."""
    vi = [i for i, t in enumerate(tokens) if t[0] == "V"]
    if len(vi) != len(chunks):
        return None
    low = [c.lower() for c in chunks]
    edges = [_edges(c, low[k + 1] if k + 1 < len(low) else "")
             for k, c in enumerate(low)]
    cost = _dist(edges[0][0], [t[1] for t in tokens[:vi[0]]])
    cost += _dist(edges[-1][1], [t[1] for t in tokens[vi[-1] + 1:]])
    starts, ends = [0], []
    for k in range(len(low) - 1):
        a, b = vi[k], vi[k + 1]
        cluster = [t[1] for t in tokens[a + 1:b]]
        coda_want, on_want = edges[k][1], edges[k + 1][0]
        link = ("ɹ",) if edges[k][2] else ()
        yod = ("j",) if edges[k + 1][3] == "u" else ()
        left = letter_edges(low[k], last=False)[1]
        right = letter_edges(low[k + 1], last=k + 2 == len(low))[0]
        double = bool(left and right and left[-1] == right[0])
        options = []
        for s in range(len(cluster) + 1):
            c = (_dist(coda_want, cluster[:s])
                 + _dist(on_want, cluster[s:], link, yod))
            options.append((c, 0.5 if double else 0.0, s, s))
            if s >= 1:
                # One sound closes this syllable and opens the next.
                c = (_dist(coda_want, cluster[:s])
                     + _dist(on_want, cluster[s - 1:], link, yod))
                options.append((c, 0.0 if double else 0.5, s, s - 1))
        c, _tie, end, start = min(options)
        cost += c
        ends.append(a + 1 + end)
        starts.append(a + 1 + start)
    ends.append(len(tokens))
    return [tokens[s:e] for s, e in zip(starts, ends)], cost


def _variants(tokens, n: int):
    """The token lists one step nearer n vowels, each with its cost."""
    have = sum(1 for t in tokens if t[0] == "V")
    out = []
    if have > n:
        # fire, sour, require: a rising vowel and its schwa are one.
        for i in range(len(tokens) - 1):
            a, b = tokens[i], tokens[i + 1]
            if (a[0] == b[0] == "V" and a[1] in ("I", "W")
                    and b[1] == "ə"):
                out.append((tokens[:i] + [("V", a[1] + "ə", a[2])]
                            + tokens[i + 2:], 0))
    elif have < n:
        # a-quar-i-um, cu-ri-ous: ɪə across two syllables.
        for i, t in enumerate(tokens):
            if t[0] == "V" and t[1] in ("ɪə", "ʊə"):
                out.append((tokens[:i] + [("V", t[1][0], t[2]),
                                          ("V", "ə", "")] + tokens[i + 1:],
                            0))
        # cam-e-ra, choc-o-late: a vowel speech drops, put back.
        for i in range(1, len(tokens)):
            for v in ("ə", "ɪ"):
                out.append((tokens[:i] + [("V", v, "+")] + tokens[i:], 2))
    return out


def word_syllables(chunks, phonemes: str):
    """A word's own phonemes cut into its written chunks: a list of
    token pieces, one per chunk, or None when no cut fits."""
    n = len(chunks)
    frontier, seen, best = [(phoneme_tokens(phonemes), 0)], set(), None
    while frontier:
        tokens, extra = frontier.pop()
        key = tuple(tokens)
        if key in seen:
            continue
        seen.add(key)
        if sum(1 for t in tokens if t[0] == "V") != n:
            frontier.extend((t, extra + c) for t, c in _variants(tokens, n))
            continue
        got = _cut(tokens, chunks)
        if got is None:
            continue
        pieces, cost = got
        cost += extra
        for piece, chunk in zip(pieces, chunks):
            for kind, sound, mark in piece:
                if kind == "V" and mark == "+":
                    letter = next((ch for ch in chunk.lower()
                                   if ch in "aeiouy"), "e")
                    if (sound == "ɪ") != (letter in "iy"):
                        cost += 1
        if best is None or cost < best[1]:
            best = (pieces, cost)
    return best[0] if best else None


def said_alone(piece) -> str:
    """One syllable as its own utterance: primary stress on its vowel,
    so a weak one is still clear, and a syllabic l said with a schwa."""
    return "".join(("ˈ" + ("ə" if s == "ᵊ" else s)) if k == "V" else s
                   for k, s, _mark in piece)


def is_weak(piece) -> bool:
    """The syllable's vowel is unstressed and weak in the word, so a
    vowel foil would sound the same as the answer."""
    _k, sound, mark = next(t for t in piece if t[0] == "V")
    return mark in ("", "+") and sound in WEAK_VOWELS


def syllable_plan(words, word_phonemes, stressed_anywhere):
    """Each word's syllable files and weak flags, and the new sounds
    to render.

    words: Word records; word_phonemes(word) gives a real word's
    phonemes or None; stressed_anywhere(chunk) as in pseudo_phonemes.
    Returns (syllable_map, new) where syllable_map[word] is
    {"files": [...], "weak": [0 or 1, ...]} and new maps a file stem
    to the phonemes it must say. A piece that says exactly what its
    chunk's spelt file says reuses that file; any other sound is made
    once, named after the first word that needs it."""
    from finger_rehab.game.modes.syllables_words import speech_stem
    syllable_map, new, by_sound = {}, {}, {}
    for w in words:
        chunks = [c.lower() for c in w.syllables]
        spelt = [chunk_phonemes(c, stressed_anywhere(c)) for c in chunks]
        pieces = None
        if w.lex != "pseudo":
            ps = word_phonemes(w.word)
            pieces = word_syllables(chunks, ps) if ps else None
        if pieces is None:
            # A made-up word is said as its chunks, so its syllables
            # are theirs. A word with no cut keeps the spelt files.
            said = spelt
            weak = [0] * len(chunks)
        else:
            said = [said_alone(p) for p in pieces]
            weak = [1 if is_weak(p) else 0 for p in pieces]
        files = []
        for k, (chunk, sound, own) in enumerate(zip(chunks, said, spelt)):
            if sound == own:
                files.append(f"chunks/{speech_stem(chunk)}")
                continue
            stem = by_sound.get(sound)
            if stem is None:
                stem = f"syllables/{speech_stem(w.word)}_{k}"
                by_sound[sound] = stem
                new[stem] = sound
            files.append(stem)
        syllable_map[w.word] = {"files": files, "weak": weak}
    return syllable_map, new


# ---- the engine --------------------------------------------------------------

class Voice:
    """Kokoro plus espeak, loaded once."""

    def __init__(self, model: Path, voices: Path, voice: str = VOICE):
        import espeakng_loader
        # espeak keeps its data path in a fixed-size buffer, and a venv
        # under a long folder name overflows it, so espeak falls back to
        # the path its builder had. A relative path cannot overflow.
        os.chdir(Path(espeakng_loader.get_data_path()).parent)
        os.environ["ESPEAK_DATA_PATH"] = "."
        from kokoro_onnx import Kokoro
        from phonemizer.backend import EspeakBackend
        from phonemizer.backend.espeak.wrapper import EspeakWrapper
        self.kokoro = Kokoro(str(model), str(voices))
        EspeakWrapper._ESPEAK_DATA_PATH = None
        self.espeak = EspeakBackend(language="en-gb",
                                    preserve_punctuation=True,
                                    with_stress=True, tie="^")
        self.voice = voice

    def word_phonemes(self, word: str) -> str:
        return to_misaki(self.espeak.phonemize([word])[0].strip())

    def say(self, phonemes: str) -> np.ndarray:
        """The utterance at kit.RATE, float in -1..1."""
        from math import gcd
        from scipy.signal import resample_poly
        y, rate = self.kokoro.create(phonemes, voice=self.voice, speed=1.0,
                                     is_phonemes=True)
        g = gcd(int(rate), kit.RATE)
        return resample_poly(np.asarray(y, dtype=np.float64),
                             kit.RATE // g, int(rate) // g)


def plan_items(pools, only=None):
    """(stem, kind, text, phonemes) for every item in `pools`, phonemes
    None for a real word espeak reads at render time. Chunk rules read
    the whole bank; the pools only choose what is made."""
    every, _ = kit.bank_items(kit.ALL_POOLS)
    chunks, words = kit.bank_items(pools)
    from finger_rehab.game.modes.syllables_words import (load_pools,
                                                         speech_stem)
    pseudo = {w.word: w for w in load_pools().get("pseudo", ())}
    items = []
    for c in sorted(chunks):
        items.append((f"chunks/{speech_stem(c)}", "chunk", c,
                      chunk_phonemes(c, every[c][0])))
    for w in words:
        made_up = pseudo.get(w)
        ps = (pseudo_phonemes(made_up.syllables, made_up.stress,
                              lambda c: every[c.lower()][0])
              if made_up is not None else WORD_FIXES.get(w))
        items.append((speech_stem(w), "word", w, ps))
    if only:
        items = [it for it in items if it[0] in only]
    return items


def say_to_file(voice: Voice, stem: str, ps: str, out: Path,
                kind: str) -> dict:
    """One item said, trimmed, levelled and written as out/stem.wav;
    returns its manifest record."""
    from scipy.io import wavfile
    bad = set(ps) - KOKORO_SYMBOLS
    if bad:
        raise ValueError(f"{stem}: symbols Kokoro was not trained on "
                         f"{sorted(bad)} in {ps!r}")
    x = voice.say(ps)
    spans = kit.utterances(x)
    if not spans:
        raise ValueError(f"{stem}: Kokoro returned silence for {ps!r}")
    y, rec = kit.finish(x, (spans[0][0], spans[-1][1]), kind)
    rec["phonemes"] = ps
    path = out / f"{stem}.wav"
    path.parent.mkdir(parents=True, exist_ok=True)
    wavfile.write(str(path), kit.RATE,
                  np.clip(y * 32767.0, -32768, 32767).astype(np.int16))
    return rec


def render(items, voice: Voice, out: Path, meta: dict) -> dict:
    records = {}
    for stem, kind, text, extra in items:
        ps = extra if extra is not None else voice.word_phonemes(text)
        records[stem] = say_to_file(voice, stem, ps, out, kind)
    manifest_path = out / "manifest.json"
    manifest = dict(meta, entries={})
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if old.get("provider") == meta["provider"]:
            manifest["entries"] = dict(old.get("entries") or {})
            manifest["pools"] = sorted(set(old.get("pools") or [])
                                       | set(meta["pools"]))
        elif old.get("entries"):
            raise SystemExit(f"{manifest_path} holds {old.get('provider')!r} "
                             f"audio; move it aside first")
    manifest["entries"].update(records)
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True),
                             encoding="utf-8")
    return records


def pool_words(pools):
    """The Word records behind kit.bank_items(pools), in its order."""
    from finger_rehab.game.modes.syllables_words import all_words, load_pools
    loaded = load_pools()
    child = list(all_words()) if "child" in pools else []
    pooled = [w for name in pools if name != "child"
              for w in loaded.get(name, ())]
    out, seen = [], set()
    for w in child + pooled:
        if len(w.syllables) < 2 or w.word in seen:
            continue
        seen.add(w.word)
        out.append(w)
    return out


def render_syllables(voice, out: Path, pools, dry_run: bool = False) -> dict:
    """Every word's syllables as they sound in it: the new sounds made,
    and the manifest's syllable_map written, with the chunk and word
    files left as they are. Real words are cut from the phonemes the
    manifest already holds for them, so no espeak is needed."""
    from finger_rehab.game.modes.syllables_words import speech_stem
    manifest_path = out / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get("entries") or {}
    every, _ = kit.bank_items(kit.ALL_POOLS)
    words = pool_words(pools)
    syllable_map, new = syllable_plan(
        words,
        lambda w: (entries.get(speech_stem(w)) or {}).get("phonemes"),
        lambda c: every[c.lower()][0])
    if dry_run:
        for w in words:
            got = syllable_map[w.word]
            said = [new.get(f) or (entries.get(f) or {}).get("phonemes", "?")
                    for f in got["files"]]
            print(f"{w.word:18s} " + " | ".join(
                f"{p}{'*' if f in new else ''}{'.' if weak else ''}"
                for f, p, weak in zip(got["files"], said, got["weak"])))
        print(f"{len(new)} new sounds (*), weak vowels marked (.)")
        return {}
    records = {stem: say_to_file(voice, stem, ps, out, "chunk")
               for stem, ps in sorted(new.items())}
    entries.update(records)
    manifest["entries"] = entries
    manifest["syllable_map"] = dict(
        manifest.get("syllable_map") or {}, **syllable_map)
    manifest["syllable_form"] = "word"
    manifest["syllables_rendered_on"] = date.today().isoformat()
    manifest_path.write_text(json.dumps(manifest, indent=1, sort_keys=True),
                             encoding="utf-8")
    return records


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", help="kokoro-v1.0.onnx")
    ap.add_argument("--voices", help="voices-v1.0.bin")
    ap.add_argument("--voice", default=VOICE)
    ap.add_argument("--pools", default=",".join(kit.ALL_POOLS),
                    help="child, teen, adult, pseudo (the battery's classic "
                         "profile plays the child bank; 16+ plays adult and "
                         "pseudo)")
    ap.add_argument("--only", default="",
                    help="comma list of stems, e.g. chunks/ven,tiger")
    ap.add_argument("--out", default=str(kit.SPEECH_DIR))
    ap.add_argument("--dry-run", action="store_true",
                    help="print each item's phonemes, write nothing")
    ap.add_argument("--syllables-only", action="store_true",
                    help="make only the syllables that sound different in "
                         "their word, and the syllable_map")
    args = ap.parse_args(argv)
    out = Path(args.out).resolve()
    pools = tuple(p.strip() for p in args.pools.split(",") if p.strip())
    if args.syllables_only and args.dry_run:
        render_syllables(None, out, pools, dry_run=True)
        return 0
    if not (args.model and args.voices):
        ap.error("--model and --voices are needed to make sound")
    model, voices = Path(args.model).resolve(), Path(args.voices).resolve()
    if args.syllables_only:
        made = render_syllables(Voice(model, voices, args.voice), out, pools)
        print(f"{len(made)} syllable files written to {out / 'syllables'}")
        return 0
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    items = plan_items(pools, only)
    if args.dry_run:
        for stem, _kind, _text, ps in items:
            print(f"{stem:28s} {ps or '(read by espeak)'}")
        return 0
    meta = {"provider": "kokoro", "voice": args.voice,
            "model": "Kokoro-82M v1.0 (kokoro-onnx model-files-v1.0)",
            "model_sha256": _sha256(model), "voices_sha256": _sha256(voices),
            "licence": "Apache-2.0 (model weights)", "accent": "en-GB",
            "chunk_form": "spelling", "rendered_on": date.today().isoformat(),
            "pools": list(pools), "rate_hz": kit.RATE,
            "chunk_rms_dbfs": kit.CHUNK_RMS_DBFS,
            "word_loudness": kit.WORD_LOUDNESS, "latency_ms": None}
    voice = Voice(model, voices, args.voice)
    records = render(items, voice, out, meta)
    longest = max((r["duration_ms"] for s, r in records.items()
                   if s.startswith("chunks/")), default=0.0)
    print(f"{len(records)} files written to {out}; longest chunk "
          f"{longest:.0f} ms")
    if not only:
        made = render_syllables(voice, out, pools)
        print(f"{len(made)} syllable files written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
