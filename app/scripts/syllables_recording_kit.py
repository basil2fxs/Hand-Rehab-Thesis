#!/usr/bin/env python3
"""Record the Syllables voice: the reading script, the cutter, the check.

    python3 scripts/syllables_recording_kit.py list --out recordings
    python3 scripts/syllables_recording_kit.py list --pools adult,pseudo
    python3 scripts/syllables_recording_kit.py cut --plan \\
        recordings/recording_plan.json --audio-dir recordings \\
        --speaker BT --microphone "USB mic"
    python3 scripts/syllables_recording_kit.py check
    python3 scripts/syllables_recording_kit.py tidy
    python3 scripts/syllables_recording_kit.py listen --listener L1 \
        --device "closed headphones, model" --level "laptop at 60 percent"
    python3 scripts/syllables_recording_kit.py listen --report

WHY A RECORDED VOICE. Speech is the stimulus in this mode: the child
hears a syllable and finds it in print. A system voice reading a lone
spelling is unpredictable, children understand synthetic single words
least well of all, and the Australian Windows voices are not visible
to the speech API the game could call. One adult speaker of general
Australian English, recorded once, gives full control of how each
chunk sounds and raises no licence question once the speaker agrees
in writing to the recordings shipping with the software. The evidence
and the full protocol are in docs/research/new_modes/
syllables-all-ages.md, section D. What ships today is synthetic
(scripts/syllables_tts.py, made to these same rules); cut replaces it,
with --force over the synthetic manifest.

HOW A CHUNK IS SPOKEN. Once per unique chunk, reused in every word
that holds it (assets/speech/chunks/<chunk>.wav), as a SPELLING
PRONUNCIATION: the way a reader decodes that chunk on its own, never
an "uh". A reduced vowel inside a word sounds the same under ter, tar
and tur, so only the spelt form keeps the four options answerable by
ear. The rules the hints below follow:
  1. A chunk that carries its word's stress: as it sounds in the word,
     on its own (the "ti" of tiger rhymes with tie).
  2. An unstressed chunk: the vowel its letters spell. Short in a
     closed chunk (pen, bit, dol); ar as in car; er, ir and ur as in
     her; or as in for. An open chunk takes the vowel it has where it
     is stressed elsewhere in the bank, otherwise the short vowel.
  3. Consonant plus le (tle, ble, ple): one light form, "tul".
The hints are rules, not a dictionary: a line marked "?" has two
common readings, and the speaker's own reading of the example word
settles it. Words are read naturally, citation form, normal rate.

THE SESSION. `list` writes recording_list.md, pages of about sixty
items in shuffled order (a list read in order drifts into list
intonation), and recording_plan.json. Record one WAV per page
(page_01.wav and so on): each item twice with about a second between
the takes and about two between items. 44.1 kHz, 16-bit, mono, peaks
near -6 dBFS, the microphone 15 to 20 cm away and a little off-axis.

WHAT `cut` DOES. Finds the utterances in each page by their energy,
pairs them with the page's items in order, keeps the better take (not
clipped, then the cleaner one), trims to 10 ms before the onset (5 ms
fade in) and 30 ms after the last audible sound (25 ms fade out),
silences a click left after the speech (drop_end_click), and levels
every file, chunk or word, to one K-weighted loudness (-22, the
BS.1770 filter without gating, since a clip is shorter than the
400 ms gating block), never above -1 dBFS peak. A page whose
utterance count is not two per item is reported with every
utterance's time and nothing is written for it, so a skipped or
doubled take can never shift every file after it by one. Output is
44.1 kHz 16-bit mono WAV, the mixer's own rate, and manifest.json
records the speaker, the accent, the date, the microphone,
chunk_form = spelling, and each file's length and level. The game
stretches its model beat to a chunk's length from that manifest.

`check` lists every chunk and word in the bank that still has no file.

`tidy` puts the files already in assets/speech through the same click,
tail and loudness steps without recording or rendering anything again,
updating each manifest entry; a file already at FINISH_VERSION is left
alone. The synthetic voice went through it on 2 October 2026.

WHAT `listen` DOES. Before a heard syllable becomes part of a measure,
two adult listeners of Australian English check it (the deep review of
1 October 2026: no study has validated synthetic speech for lone
syllables or made-up words, children follow an unfamiliar accent less
well, and readers with dyslexia lose most in noise). Every probe set's
syllable is played as the game plays it, sound only, with its own four
options on screen; the listener types the number of the one heard (r
hears it once more). Answers go to assets/speech/listener_check.json
with the listener's code, the date, the playback device and the level.
`listen --report` prints each listener's score and every set fewer
than 90 percent of answers got right: re-render or drop those before
the probe is used, and report the check, the voice, the device and the
level in the methods.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from datetime import date
from pathlib import Path

import numpy as np

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

RATE = 44100
# One loudness for every file, words and chunks alike: the K-weighted
# BS.1770 filter without gating, since a clip is shorter than the
# 400 ms gating block. Until 2 October 2026 chunks were set to an RMS
# of -20 dBFS and words to -23, which left every syllable about 3 dB
# louder than the word it came from.
SPEECH_LOUDNESS = -22.0
PEAK_CEILING_DBFS = -1.0
# 10 ms kept before the onset with a 5 ms fade in; 30 ms kept after the
# last audible frame, under a 25 ms raised-cosine fade out.
LEAD_S, TAIL_S, FADE_S, FADE_OUT_S = 0.010, 0.030, 0.005, 0.025
# An end click (drop_end_click): at most CLICK_MAX_S long, falling
# 20 dB within CLICK_DECAY_S; up to POP_MAX_S long when the item cannot
# end in a release (its last sound is not a stop), and up to
# VOWEL_POP_MAX_S, a pop and its tail, when it ends in a vowel.
CLICK_MAX_S, CLICK_DECAY_S = 0.012, 0.010
POP_MAX_S, VOWEL_POP_MAX_S = 0.025, 0.060
# Sounds in the phoneme symbols the voice was made from: an item ending
# in a stop or an affricate may end in a real release, and one ending
# in a long vowel or a diphthong (the length mark, or the letters the
# voice uses for the vowels of day, eye, boy, go, cow and near) cannot
# end in a short burst of speech. A short vowel can: the uh of ladder
# follows a closure and may be brief.
STOP_PHONES = frozenset("ptkbdgɡʔ") | {"ʧ", "ʤ"}
LONG_VOWEL_PHONES = frozenset("ːAIOQWY")
# Which finish a file went through, kept on its manifest entry: 2 is
# the click, tail and loudness pass of 2 October 2026 (tidy).
FINISH_VERSION = 2
FRAME_S = 0.010
MERGE_GAP_S = 0.18     # a stop closure inside a word, not a new take
MIN_UTTER_S = 0.06
PAGE_SIZE = 60
SPEECH_DIR = APP / "assets" / "speech"

# ---- the hints -----------------------------------------------------------

SHORT = {"a": "a as in cat", "e": "e as in pet", "i": "i as in sit",
         "o": "o as in hot", "u": "u as in cup", "y": "i as in gym"}
LONG = {"a": "ay as in day", "e": "ee as in see", "i": "eye as in pie",
        "o": "oh as in go", "u": "you as in cute", "y": "eye as in my"}
# Longest first, so "air" is found before "ai". The marked teams have
# two common readings (bread and bead, book and moon, cow and snow).
TEAMS = (
    ("igh", "eye as in high", False), ("air", "air as in hair", False),
    ("are", "air as in care", False), ("ear", "ear as in near", True),
    ("eer", "ear as in deer", False), ("our", "our as in sour", True),
    ("oor", "or as in door", True), ("ore", "or as in more", False),
    ("oar", "or as in roar", False), ("ar", "ar as in car", False),
    ("er", "er as in her", False), ("ir", "er as in bird", False),
    ("ur", "er as in fur", False), ("or", "or as in for", False),
    ("ah", "ar as in car", False),
    ("ee", "ee as in see", False), ("ea", "ee as in sea", True),
    ("ai", "ay as in rain", False), ("ay", "ay as in day", False),
    ("oa", "oh as in boat", False), ("oe", "oh as in toe", False),
    ("oo", "oo as in moon", True), ("ou", "ow as in out", True),
    ("ow", "ow as in cow", True), ("oi", "oy as in coin", False),
    ("oy", "oy as in boy", False), ("au", "or as in sauce", False),
    ("aw", "or as in saw", False), ("ie", "eye as in pie", True),
    ("ue", "oo as in blue", False), ("ew", "oo as in new", False),
    ("ei", "ay as in vein", True), ("ey", "ee as in key", True),
)
ENDINGS = (
    ("tion", "shun", False), ("sion", "shun", True), ("ture", "cher", False),
    ("cial", "shul", False), ("tial", "shul", False), ("cian", "shun", False),
    ("ous", "us as in famous", False),
)
VOWELS = "aeiouy"


def respell(chunk: str, stressed: bool) -> tuple[str, bool]:
    """(how to say the chunk's vowel, whether the hint is unsure)."""
    c = chunk.lower()
    notes: list[str] = []
    unsure = False
    for i, ch in enumerate(c[:-1]):
        if ch == "c" and c[i + 1] in "eiy":
            notes.append("c says s")
        if ch == "g" and c[i + 1] in "eiy":
            notes.append("g as in gem or get?")
            unsure = True
    if len(c) >= 3 and c.endswith("le") and c[-3] not in VOWELS:
        return f"{c[:-2]}ul (light, as in little)", unsure
    for end, sound, doubt in ENDINGS:
        if c.endswith(end):
            head = c[:-len(end)]
            hint = f"{head} + {sound}" if head else sound
            return ", ".join([hint] + notes), unsure or doubt
    first = next((i for i, ch in enumerate(c) if ch in VOWELS
                  and not (ch == "y" and i == 0)), None)
    if first is None:
        return ", ".join(["say it as spelt"] + notes), True
    hint = None
    for team, sound, doubt in TEAMS:
        if c.startswith(team, first):
            hint, unsure = sound, unsure or doubt
            break
    if hint is None:
        v = c[first]
        rest = c[first + 1:]
        if len(rest) == 2 and rest[0] not in VOWELS and rest[1] == "e":
            hint = LONG[v]                          # bake, time, cute
            # marine and machine say ee: the example word decides.
            unsure = unsure or v == "i"
        elif rest and rest[0] not in VOWELS:
            hint = SHORT[v]                         # closed: ban, ter's
        elif v == "y":
            hint = LONG["y"] if stressed else "ee as in happy"
        else:
            hint = LONG[v] if stressed else SHORT[v]
        if c.startswith(("wa", "qua")) and v == "a":
            hint, unsure = "o as in want?", True
    return ", ".join([hint] + notes), unsure


# ---- the material ----------------------------------------------------------

def shown(word, stress: int) -> str:
    """A word split into its chunks with the stressed one in capitals
    (com-MU-ni-ty), so the reader sees whether the chunk carries the
    stress there (rule 1) or is read as spelt (rule 2)."""
    return "-".join(s.upper() if i == stress else s
                    for i, s in enumerate(word.syllables))


ALL_POOLS = ("child", "teen", "adult", "pseudo")


def bank_items(pools=ALL_POOLS):
    """(chunks, words) from everything the game can draw: the child
    bank and the age pools. chunks maps each unique chunk to (stressed
    anywhere, up to three example words shown split, stressed examples
    first)."""
    from finger_rehab.game.modes.syllables_words import all_words, load_pools
    chunks: dict[str, list] = {}
    words = []
    # The child bank first, then the teen, adult and made-up pools the
    # age profiles draw: every one of them is spoken.
    loaded = load_pools()
    pooled = [w for name in pools if name != "child"
              for w in loaded.get(name, ())]
    child = list(all_words()) if "child" in pools else []
    for w in child + pooled:
        if len(w.syllables) < 2:
            continue
        words.append(w.word)
        for k, s in enumerate(w.syllables):
            entry = chunks.setdefault(s.lower(), [False, [], []])
            entry[0] = entry[0] or k == w.stress
            (entry[1] if k == w.stress else entry[2]).append(
                shown(w, w.stress))
    out = {c: (st, (on + off)[:3]) for c, (st, on, off) in chunks.items()}
    return out, sorted(set(words))


def make_plan(seed: int = 2026, page_size: int = PAGE_SIZE,
              only_missing: bool = False, speech_dir: Path = SPEECH_DIR,
              pools=ALL_POOLS):
    from finger_rehab.game.modes.syllables_words import speech_stem
    chunks, words = bank_items(pools)
    items = []
    for c, (stressed, examples) in sorted(chunks.items()):
        stem = f"chunks/{speech_stem(c)}"
        if only_missing and _has_file(speech_dir, stem):
            continue
        hint, unsure = respell(c, stressed)
        items.append({"kind": "chunk", "text": c, "stem": stem,
                      "hint": hint, "unsure": unsure,
                      "examples": examples, "stressed": stressed})
    for w in words:
        if only_missing and _has_file(speech_dir, speech_stem(w)):
            continue
        items.append({"kind": "word", "text": w, "stem": speech_stem(w)})
    random.Random(seed).shuffle(items)
    pages = []
    for p, start in enumerate(range(0, len(items), page_size), 1):
        page = items[start:start + page_size]
        for n, item in enumerate(page, 1):
            item["n"] = n
        pages.append({"page": p, "file": f"page_{p:02d}.wav",
                      "items": page})
    return {"created": date.today().isoformat(), "seed": seed,
            "takes": 2, "pages": pages}


def _has_file(root: Path, stem: str) -> bool:
    return any((root / f"{stem}{ext}").exists() for ext in (".wav", ".ogg"))


def write_list(plan: dict, out: Path) -> Path:
    lines = ["# Syllables recording script", "",
             "Each line twice, about a second between the takes and two "
             "between lines. Words naturally. A chunk in capitals in "
             "its example (MU-sic) carries the stress there: say it as "
             "it sounds in that word, on its own. Otherwise say it as "
             "spelt, never 'uh'. A '?' marks a hint with two common "
             "readings: the example word decides.", ""]
    for page in plan["pages"]:
        lines += [f"## Page {page['page']} ({page['file']})", ""]
        for it in page["items"]:
            if it["kind"] == "chunk":
                mark = " ?" if it["unsure"] else ""
                lines.append(f"{it['n']}. **{it['text']}**: {it['hint']}"
                             f"{mark} (in {', '.join(it['examples'])})")
            else:
                lines.append(f"{it['n']}. {it['text']} (whole word)")
        lines.append("")
    path = out / "recording_list.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


# ---- the cutter --------------------------------------------------------------

def read_wav(path: Path) -> np.ndarray:
    """Mono float in -1..1 at RATE, whatever the file's format."""
    from scipy.io import wavfile
    rate, x = wavfile.read(str(path))
    x = np.asarray(x)
    if x.dtype.kind == "i":
        x = x.astype(np.float64) / float(np.iinfo(x.dtype).max)
    elif x.dtype.kind == "u":
        x = (x.astype(np.float64) - 128.0) / 128.0
    else:
        x = x.astype(np.float64)
    if x.ndim > 1:
        x = x.mean(axis=1)
    if rate != RATE:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(int(rate), RATE)
        x = resample_poly(x, RATE // g, int(rate) // g)
    return x


def utterances(x: np.ndarray) -> list[tuple[int, int]]:
    """(start, end) sample spans of speech: frames 12 dB over the
    page's noise floor (its 10th percentile frame), gaps under
    MERGE_GAP_S joined, anything under MIN_UTTER_S dropped."""
    hop = int(FRAME_S * RATE)
    n = len(x) // hop
    if n == 0:
        return []
    frames = x[:n * hop].reshape(n, hop)
    rms = np.sqrt((frames ** 2).mean(axis=1)) + 1e-12
    db = 20 * np.log10(rms)
    floor = np.percentile(db, 10)
    on = db > max(floor + 12.0, -60.0)
    spans, start = [], None
    for i, v in enumerate(on):
        if v and start is None:
            start = i
        elif not v and start is not None:
            spans.append([start, i])
            start = None
    if start is not None:
        spans.append([start, n])
    merged: list[list[int]] = []
    for s in spans:
        if merged and (s[0] - merged[-1][1]) * FRAME_S < MERGE_GAP_S:
            merged[-1][1] = s[1]
        else:
            merged.append(s)
    return [(a * hop, b * hop) for a, b in merged
            if (b - a) * FRAME_S >= MIN_UTTER_S]


def k_weighted_db(y: np.ndarray) -> float:
    """Mean-square loudness through the BS.1770 K filter (high shelf
    +4 dB at 1500 Hz, high pass at 38 Hz), no gating."""
    from scipy.signal import lfilter

    def biquad(kind, gain_db, q, fc):
        a_ = 10 ** (gain_db / 40.0)
        w0 = 2 * np.pi * fc / RATE
        alpha = np.sin(w0) / (2 * q)
        cw = np.cos(w0)
        if kind == "shelf":
            b = [a_ * ((a_ + 1) + (a_ - 1) * cw + 2 * np.sqrt(a_) * alpha),
                 -2 * a_ * ((a_ - 1) + (a_ + 1) * cw),
                 a_ * ((a_ + 1) + (a_ - 1) * cw - 2 * np.sqrt(a_) * alpha)]
            a = [(a_ + 1) - (a_ - 1) * cw + 2 * np.sqrt(a_) * alpha,
                 2 * ((a_ - 1) - (a_ + 1) * cw),
                 (a_ + 1) - (a_ - 1) * cw - 2 * np.sqrt(a_) * alpha]
        else:
            b = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2]
            a = [1 + alpha, -2 * cw, 1 - alpha]
        return np.array(b) / a[0], np.array(a) / a[0]

    z = y
    for kind, g, q, fc in (("shelf", 4.0, 1 / np.sqrt(2), 1500.0),
                           ("pass", 0.0, 0.5, 38.0)):
        b, a = biquad(kind, g, q, fc)
        z = lfilter(b, a, z)
    return -0.691 + 10 * np.log10(np.mean(z ** 2) + 1e-20)


def _frames_db(y: np.ndarray) -> np.ndarray:
    """Level of each 1 ms frame, dBFS."""
    hop = max(1, int(0.001 * RATE))
    n = len(y) // hop
    if n == 0:
        return np.zeros(0)
    frames = y[:n * hop].reshape(n, hop)
    return 20 * np.log10(np.sqrt((frames ** 2).mean(axis=1)) + 1e-12)


def end_kind(phonemes: str | None) -> str:
    """How an item's clip may end: 'stop' when its last sound is a stop
    or an affricate (a real release can follow), 'vowel' when it is a
    long vowel or a diphthong, else 'other'. 'stop' when the phonemes
    are not known, which keeps the careful rule."""
    sounds = [c for c in (phonemes or "") if c.isalpha()]
    if not sounds or sounds[-1] in STOP_PHONES:
        return "stop"
    return "vowel" if sounds[-1] in LONG_VOWEL_PHONES else "other"


def drop_end_click(y: np.ndarray,
                   ends: str = "stop") -> tuple[np.ndarray, bool]:
    """Silence a click left after the speech has ended, and say whether
    there was one. The synthetic voice often ends a clip with a tick or
    a pop just after the last sound (2 October 2026: 945 of the 2201
    shipped files, the loudest 3 dB under the voice, some with a second
    pop before the tick): an event after at least 12 ms of quiet 15 dB
    under it, in the last 120 ms of the clip, at least 10 dB under the
    loudest frame, or, for an item not ending in a stop, a pop on the
    dying tail of its last sound (_tail_pop). `ends` is the item's
    end_kind. For 'stop' (or nothing known) the event must also be at
    most CLICK_MAX_S long and fall 20 dB within CLICK_DECAY_S, and only
    the last event is looked at: a stop's own release takes 13 to 39 ms
    to fall that far in these files, so a final t or d stays. Otherwise
    anything up to POP_MAX_S goes, and after a long vowel a pop and its
    tail up to VOWEL_POP_MAX_S (peaking within 8 ms of its onset and
    6 dB down 10 ms later, which a vowel never is), up to three times
    over, since nothing after a vowel, a nasal or a fricative has died
    away is speech."""
    found = False
    for k in range(1 if ends == "stop" else 3):
        # The pop on a tail is looked for once only: after it goes, the
        # end of the speech itself is what a second look would see.
        y, hit = _drop_once(y, ends, tail_pop=(k == 0))
        if not hit:
            break
        found = True
    return y, found


def _drop_once(y: np.ndarray, ends: str,
               tail_pop: bool = True) -> tuple[np.ndarray, bool]:
    db = _frames_db(y)
    n = len(db)
    if n == 0:
        return y, False
    loud = np.flatnonzero(db > db.max() - 45.0)
    if not len(loud) or loud[-1] < n - 120:
        return y, False
    end = int(loud[-1])
    # (window, keep a release, need a pop's shape): the click rule
    # first, then a pop with its tail after a vowel.
    tries = {"stop": ((CLICK_MAX_S, True, False),),
             "vowel": ((POP_MAX_S, False, False),
                       (VOWEL_POP_MAX_S, False, True))
             }.get(ends, ((POP_MAX_S, False, False),))
    cuts = (_end_event(db, end, int(round(w * 1000)), keep_release, pop)
            for w, keep_release, pop in tries)
    if ends != "stop" and tail_pop:
        cuts = (*cuts, _tail_pop(db, end))
    for cut in cuts:
        if cut is not None:
            # Silence from the quietest point before the event, after a
            # 5 ms fade, so no sliver of its rise is left standing.
            hop = int(0.001 * RATE)
            a = cut * hop
            f = min(a, 5 * hop)
            out = y.copy()
            out[a - f:a] *= 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, f)))
            out[a:] = 0.0
            return out, True
    return y, False


def _tail_pop(db: np.ndarray, end: int) -> int | None:
    """A pop riding on a sound's dying tail, where no quiet comes first:
    peaking in the last 25 ms of sound (to `end`, the last audible
    frame), a rise of 12 dB or more within 6 ms to a peak at least 6 dB
    under the loudest frame, down 10 dB again within 10 ms, out of
    20 ms that sat 8 dB under it. Vowels, nasals and fricatives fade;
    they never jump and fall like this. The frame to cut at, or None."""
    n = len(db)
    for i in range(end, max(end - 25, 26), -1):
        if db[i] > db.max() - 6.0 or (i + 1 < n and db[i + 1] > db[i]):
            continue
        if db[i] - db[i - 6:i].min() < 12.0:
            continue
        if db[i + 1:i + 11].min(initial=db[i]) > db[i] - 10.0:
            continue
        # The 20 ms before the jump must sit 8 dB under it: a voice's own
        # flicker at the end of a vowel stays near its level.
        lead_in = db[max(0, i - 26):i - 6]
        if len(lead_in) and np.median(lead_in) > db[i] - 8.0:
            continue
        return i - 10 + int(np.argmin(db[i - 10:i]))
    return None


def _end_event(db: np.ndarray, end: int, width: int, keep_release: bool,
               pop: bool = False) -> int | None:
    """Where to cut, a frame in the middle of the quiet before the
    event ending at `end`, when it is one drop_end_click silences, else
    None."""
    lo = max(0, end - width)
    top = lo + int(np.argmax(db[lo:end + 1]))
    ev_db = db[top]
    if ev_db > db.max() - 10.0:
        return None
    start = top
    while start > 0 and db[start - 1] >= ev_db - 20.0:
        start -= 1
    if end - start + 1 > width:
        return None
    quiet, k = 0, start - 1
    while k >= 0 and db[k] < ev_db - 15.0:
        quiet += 1
        k -= 1
    if quiet < 12:
        return None
    fall = top
    while fall + 1 < len(db) and db[fall + 1] > ev_db - 20.0:
        fall += 1
    if keep_release and fall - top + 1 > int(round(CLICK_DECAY_S * 1000)):
        return None
    if pop and (top - start > 8 or (top + 10 < len(db)
                                    and db[top + 10] > ev_db - 6.0)):
        return None
    return start - quiet // 2


def trim_tail(y: np.ndarray) -> np.ndarray:
    """End the clip TAIL_S after its last audible frame (45 dB under the
    loudest) under a FADE_OUT_S raised-cosine fade, so it closes
    smoothly and the next sound is not kept waiting on silence."""
    db = _frames_db(y)
    loud = np.flatnonzero(db > db.max() - 45.0) if len(db) else []
    if not len(loud):
        return y
    stop = min(len(y), (int(loud[-1]) + 1) * int(0.001 * RATE)
               + int(TAIL_S * RATE))
    out = y[:stop].copy()
    f = min(len(out), max(1, int(FADE_OUT_S * RATE)))
    out[-f:] *= 0.5 * (1.0 + np.cos(np.linspace(0.0, np.pi, f)))
    return out


def clean(y: np.ndarray, ends: str = "stop") -> tuple[np.ndarray, bool]:
    """The tail trimmed, any end click silenced, and the tail trimmed
    again. Trimming first matters: a pop's faint tail can run to the
    end of an untrimmed clip and hide the pop from drop_end_click."""
    y, clicked = drop_end_click(trim_tail(y), ends)
    return (trim_tail(y) if clicked else y), clicked


def level(y: np.ndarray) -> tuple[np.ndarray, dict]:
    """The clip at SPEECH_LOUDNESS, never above PEAK_CEILING_DBFS, and
    its record."""
    gain_db = SPEECH_LOUDNESS - k_weighted_db(y)
    peak = np.max(np.abs(y)) + 1e-12
    ceiling = 10 ** (PEAK_CEILING_DBFS / 20.0)
    limited = peak * 10 ** (gain_db / 20.0) > ceiling
    if limited:
        gain_db = 20 * np.log10(ceiling / peak)
    y = y * 10 ** (gain_db / 20.0)
    rec = {"duration_ms": round(len(y) / RATE * 1000.0, 1),
           "rms_dbfs": round(20 * np.log10(np.sqrt(np.mean(y ** 2))
                                           + 1e-12), 2),
           "peak_dbfs": round(20 * np.log10(np.max(np.abs(y)) + 1e-12), 2),
           "loudness": round(k_weighted_db(y), 2),
           "limited": bool(limited), "finish": FINISH_VERSION}
    return y, rec


def finish(x: np.ndarray, span: tuple[int, int], kind: str,
           phonemes: str | None = None) -> tuple:
    """The trimmed, faded, levelled clip and its record. Chunks and
    words are finished alike; `kind` is kept for the callers, and the
    phonemes, when known, say whether the clip may end in a release."""
    a = max(0, span[0] - int(LEAD_S * RATE))
    b = min(len(x), span[1] + int(TAIL_S * RATE))
    y = x[a:b].copy()
    f = max(1, int(FADE_S * RATE))
    y[:f] *= np.linspace(0.0, 1.0, f)
    y, clicked = clean(y, end_kind(phonemes))
    y, rec = level(y)
    rec["click_removed"] = clicked
    return y, rec


def pick_take(x: np.ndarray, spans) -> int:
    """Index of the better take: not clipped, then the higher level over
    the page's noise, the later take on a tie."""
    best, best_score = len(spans) - 1, -np.inf
    for i, (a, b) in enumerate(spans):
        seg = x[a:b]
        clipped = np.max(np.abs(seg)) >= 0.99
        score = (-1e9 if clipped else 0.0) + 20 * np.log10(
            np.sqrt(np.mean(seg ** 2)) + 1e-12)
        if score >= best_score - 0.5:
            best, best_score = i, max(score, best_score)
    return best


def cut_page(page: dict, audio: Path, out: Path, takes: int = 2) -> dict:
    """Write one page's files; returns {stem: record}. Raises
    ValueError, naming every utterance, when the count is off."""
    from scipy.io import wavfile
    x = read_wav(audio)
    spans = utterances(x)
    want = len(page["items"]) * takes
    if len(spans) != want:
        times = ", ".join(f"{a / RATE:.1f}-{b / RATE:.1f}s" for a, b in spans)
        raise ValueError(f"{audio.name}: {len(spans)} utterances, expected "
                         f"{want} ({len(page['items'])} items x {takes}). "
                         f"Heard at: {times}")
    records = {}
    for i, item in enumerate(page["items"]):
        group = spans[i * takes:(i + 1) * takes]
        k = pick_take(x, group)
        y, rec = finish(x, group[k], item["kind"])
        rec["take"] = k + 1
        path = out / f"{item['stem']}.wav"
        path.parent.mkdir(parents=True, exist_ok=True)
        wavfile.write(str(path), RATE,
                      np.clip(y * 32767.0, -32768, 32767).astype(np.int16))
        records[item["stem"]] = rec
    return records


def write_manifest(out: Path, records: dict, speaker: str,
                   microphone: str, force: bool = False) -> Path:
    path = out / "manifest.json"
    manifest = {"provider": "recorded", "voice": speaker,
                "speaker": speaker, "accent": "en-AU",
                "chunk_form": "spelling", "microphone": microphone,
                "recorded_on": date.today().isoformat(),
                "rate_hz": RATE, "loudness": SPEECH_LOUDNESS,
                "finish": FINISH_VERSION, "latency_ms": None,
                "entries": {}}
    if path.exists():
        old = json.loads(path.read_text(encoding="utf-8"))
        if old.get("provider") not in (None, "recorded") and not force:
            raise SystemExit(f"{path} holds {old.get('provider')!r} audio; "
                             f"pass --force to replace it with recordings")
        if old.get("provider") == "recorded":
            manifest["entries"] = dict(old.get("entries") or {})
            manifest["latency_ms"] = old.get("latency_ms")
    manifest["entries"].update(records)
    path.write_text(json.dumps(manifest, indent=1, sort_keys=True),
                    encoding="utf-8")
    return path


# ---- commands ----------------------------------------------------------------

def cmd_list(args) -> int:
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    plan = make_plan(args.seed, args.page_size, args.only_missing,
                     Path(args.speech_dir),
                     tuple(x.strip() for x in args.pools.split(",")))
    (out / "recording_plan.json").write_text(json.dumps(plan, indent=1),
                                             encoding="utf-8")
    listing = write_list(plan, out)
    n = sum(len(p["items"]) for p in plan["pages"])
    unsure = sum(1 for p in plan["pages"] for i in p["items"]
                 if i.get("unsure"))
    print(f"{n} items on {len(plan['pages'])} pages -> {listing}")
    print(f"{unsure} chunk hints marked '?' (two common readings)")
    return 0


def cmd_cut(args) -> int:
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    audio_dir = Path(args.audio_dir)
    out = Path(args.speech_dir)
    records, problems = {}, []
    for page in plan["pages"]:
        audio = audio_dir / page["file"]
        if not audio.exists():
            continue
        try:
            records.update(cut_page(page, audio, out, plan.get("takes", 2)))
        except ValueError as exc:
            problems.append(str(exc))
    if records:
        write_manifest(out, records, args.speaker, args.microphone,
                       args.force)
    print(f"{len(records)} files written to {out}")
    for p in problems:
        print("NOT CUT: " + p)
    return 1 if problems else 0


def cmd_tidy(args) -> int:
    """The shipped files through drop_end_click, trim_tail and level,
    in place, with their manifest entries brought up to date."""
    from scipy.io import wavfile
    out = Path(args.speech_dir)
    path = out / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    entries = manifest.get("entries") or {}
    done = clicks = 0
    for stem, rec in sorted(entries.items()):
        wav = out / f"{stem}.wav"
        if not wav.exists() or int(rec.get("finish", 1)) >= FINISH_VERSION:
            continue
        y, clicked = clean(read_wav(wav), end_kind(rec.get("phonemes")))
        y, new = level(y)
        wavfile.write(str(wav), RATE,
                      np.clip(y * 32767.0, -32768, 32767).astype(np.int16))
        rec.update(new)
        rec["click_removed"] = clicked
        done += 1
        clicks += int(clicked)
    for key in ("chunk_rms_dbfs", "word_loudness"):
        manifest.pop(key, None)
    manifest["loudness"] = SPEECH_LOUDNESS
    manifest["finish"] = FINISH_VERSION
    if done:
        manifest["finished_on"] = date.today().isoformat()
    path.write_text(json.dumps(manifest, indent=1, sort_keys=True),
                    encoding="utf-8")
    print(f"{done} files finished again, {clicks} end clicks silenced")
    return 0


def cmd_check(args) -> int:
    root = Path(args.speech_dir)
    from finger_rehab.game.modes.syllables_words import speech_stem
    chunks, words = bank_items()
    miss_c = [c for c in sorted(chunks)
              if not _has_file(root, f"chunks/{speech_stem(c)}")]
    miss_w = [w for w in words if not _has_file(root, speech_stem(w))]
    print(f"chunks: {len(chunks) - len(miss_c)} of {len(chunks)} recorded")
    print(f"words:  {len(words) - len(miss_w)} of {len(words)} recorded")
    for label, miss in (("chunks", miss_c), ("words", miss_w)):
        if miss:
            print(f"missing {label} (first 20): {', '.join(miss[:20])}")
    return 0 if not (miss_c or miss_w) else 1


LISTEN_SEED = 1001
LISTEN_PASS = 0.9


def probe_listen_items(speech_dir: Path,
                       probe_file: Path | None = None) -> list[dict]:
    """Every probe set's heard syllable, its four options in lane order
    and its file, in one fixed shuffled order (the same for every
    listener)."""
    probe_file = probe_file or (APP / "assets" / "words"
                                / "syllables_probe.json")
    data = json.loads(probe_file.read_text(encoding="utf-8"))
    smap = {}
    try:
        smap = json.loads((speech_dir / "manifest.json").read_text(
            encoding="utf-8")).get("syllable_map") or {}
    except FileNotFoundError:
        pass
    items = []
    for group, sets in (data.get("item_sets") or {}).items():
        for it in sets:
            pos = int(it.get("pos", 0))
            files = (smap.get(it["word"]) or {}).get("files") or []
            path = None
            if pos < len(files):
                for ext in (".wav", ".ogg"):
                    cand = speech_dir / f"{files[pos]}{ext}"
                    if cand.exists():
                        path = cand
                        break
            items.append({
                "key": f"{group}:{it['word']}:{pos}",
                "syl": str(it.get("syl", "")),
                "options": [str(o.get("text", "")) for o in sorted(
                    it.get("options") or [], key=lambda o: o["lane"])],
                "file": str(path) if path else None,
            })
    random.Random(LISTEN_SEED).shuffle(items)
    return items


def _play_file(path: str) -> None:
    """Play one file through pygame's mixer and wait for it to end."""
    import pygame
    if not pygame.mixer.get_init():
        pygame.mixer.init()
    channel = pygame.mixer.Sound(path).play()
    while channel is not None and channel.get_busy():
        pygame.time.wait(20)


def run_listen(items: list[dict], ask=input, play=_play_file) -> dict:
    """One listener's answers, {item key: the option text chosen}, or
    None for a set with no file. One more hearing on request."""
    answers: dict = {}
    for k, it in enumerate(items, 1):
        if it["file"] is None:
            answers[it["key"]] = None
            continue
        play(it["file"])
        again = 0
        line = "  ".join(f"{i}: {text}"
                         for i, text in enumerate(it["options"], 1))
        while True:
            got = str(ask(f"[{k}/{len(items)}] {line}  (1 to 4, r to "
                          f"hear it again) ")).strip().lower()
            if got == "r" and again < 1:
                again += 1
                play(it["file"])
                continue
            if got in ("1", "2", "3", "4") and int(got) <= len(
                    it["options"]):
                answers[it["key"]] = it["options"][int(got) - 1]
                break
    return answers


def listen_summary(record: dict, items: list[dict]) -> dict:
    """Each listener's share right, and every set fewer than
    LISTEN_PASS of the answers got right."""
    target = {it["key"]: it["syl"] for it in items}
    per_listener = {}
    for code, entry in (record.get("listeners") or {}).items():
        got = {k: v for k, v in (entry.get("answers") or {}).items()
               if v is not None and k in target}
        per_listener[code] = (round(sum(1 for k, v in got.items()
                                        if v == target[k]) / len(got), 3)
                              if got else None)
    flagged = []
    for key, syl in target.items():
        picks = [entry.get("answers", {}).get(key)
                 for entry in (record.get("listeners") or {}).values()]
        picks = [p for p in picks if p is not None]
        if picks and sum(1 for p in picks if p == syl) / len(picks) \
                < LISTEN_PASS:
            flagged.append({"key": key, "syl": syl, "heard_as": picks})
    return {"listeners": per_listener, "flagged": flagged}


def cmd_listen(args) -> int:
    root = Path(args.speech_dir)
    items = probe_listen_items(root)
    out = Path(args.out) if args.out else root / "listener_check.json"
    record = (json.loads(out.read_text(encoding="utf-8"))
              if out.exists() else {"listeners": {}})
    if not args.report:
        if not args.listener:
            print("listen needs --listener, a code such as L1")
            return 2
        answers = run_listen(items)
        record.setdefault("listeners", {})[args.listener] = {
            "date": date.today().isoformat(), "device": args.device,
            "level": args.level, "answers": answers}
        out.write_text(json.dumps(record, indent=1) + "\n",
                       encoding="utf-8")
    summary = listen_summary(record, items)
    for code, share in summary["listeners"].items():
        print(f"listener {code}: {share} right")
    for f in summary["flagged"]:
        print(f"under {LISTEN_PASS:.0%}: {f['key']} ({f['syl']}) heard "
              f"as {', '.join(f['heard_as'])}")
    return 0 if not summary["flagged"] else 1


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("list", help="write the reading script")
    a.add_argument("--out", default="recordings")
    a.add_argument("--seed", type=int, default=2026)
    a.add_argument("--page-size", type=int, default=PAGE_SIZE)
    a.add_argument("--only-missing", action="store_true")
    a.add_argument("--pools", default=",".join(ALL_POOLS),
                   help="which material: child, teen, adult, pseudo "
                        "(adult,pseudo is the 16+ profile, about 380 "
                        "items)")
    a.add_argument("--speech-dir", default=str(SPEECH_DIR))
    a.set_defaults(fn=cmd_list)
    c = sub.add_parser("cut", help="cut recorded pages into files")
    c.add_argument("--plan", required=True)
    c.add_argument("--audio-dir", required=True)
    c.add_argument("--speaker", required=True,
                   help="a code, not a name, e.g. BT")
    c.add_argument("--microphone", default="")
    c.add_argument("--speech-dir", default=str(SPEECH_DIR))
    c.add_argument("--force", action="store_true")
    c.set_defaults(fn=cmd_cut)
    t = sub.add_parser("tidy", help="the shipped files through the "
                                    "click, tail and loudness steps")
    t.add_argument("--speech-dir", default=str(SPEECH_DIR))
    t.set_defaults(fn=cmd_tidy)
    k = sub.add_parser("check", help="what is still missing")
    k.add_argument("--speech-dir", default=str(SPEECH_DIR))
    k.set_defaults(fn=cmd_check)
    s = sub.add_parser("listen", help="listeners check the probe's "
                                      "syllables by ear")
    s.add_argument("--listener", default="",
                   help="a code, not a name, e.g. L1")
    s.add_argument("--device", default="",
                   help="the headphones or speakers used")
    s.add_argument("--level", default="",
                   help="the playback level, as set")
    s.add_argument("--report", action="store_true",
                   help="print the results so far, play nothing")
    s.add_argument("--out", default="")
    s.add_argument("--speech-dir", default=str(SPEECH_DIR))
    s.set_defaults(fn=cmd_listen)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
