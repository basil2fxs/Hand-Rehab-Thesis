#!/usr/bin/env python3
"""Record the Syllables voice: the reading script, the cutter, the check.

    python3 scripts/syllables_recording_kit.py list --out recordings
    python3 scripts/syllables_recording_kit.py list --pools adult,pseudo
    python3 scripts/syllables_recording_kit.py cut --plan \\
        recordings/recording_plan.json --audio-dir recordings \\
        --speaker BT --microphone "USB mic"
    python3 scripts/syllables_recording_kit.py check

WHY A RECORDED VOICE. Speech is the stimulus in this mode: the child
hears a syllable and finds it in print. A system voice reading a lone
spelling is unpredictable, children understand synthetic single words
least well of all, and the Australian Windows voices are not visible
to the speech API the game could call. One adult speaker of general
Australian English, recorded once, gives full control of how each
chunk sounds and raises no licence question once the speaker agrees
in writing to the recordings shipping with the software. The evidence
and the full protocol are in docs/research/new_modes/
syllables-all-ages.md, section D.

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
clipped, then the cleaner one), trims to 10 ms before the onset and
50 ms after the offset with 5 ms fades, and levels it: chunks to one
RMS (-20 dBFS), words to one K-weighted loudness (-23, the BS.1770
filter without gating, since a word is shorter than the 400 ms gating
block), never above -1 dBFS peak. A page whose utterance count is not
two per item is reported with every utterance's time and nothing is
written for it, so a skipped or doubled take can never shift every
file after it by one. Output is 44.1 kHz 16-bit mono WAV, the mixer's
own rate, and manifest.json records the speaker, the accent, the date,
the microphone, chunk_form = spelling, and each file's length and
level. The game stretches its model beat to a chunk's length from
that manifest.

`check` lists every chunk and word in the bank that still has no file.
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
CHUNK_RMS_DBFS = -20.0
WORD_LOUDNESS = -23.0
PEAK_CEILING_DBFS = -1.0
LEAD_S, TAIL_S, FADE_S = 0.010, 0.050, 0.005
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
    chunks, words = bank_items(pools)
    items = []
    for c, (stressed, examples) in sorted(chunks.items()):
        stem = f"chunks/{c}"
        if only_missing and _has_file(speech_dir, stem):
            continue
        hint, unsure = respell(c, stressed)
        items.append({"kind": "chunk", "text": c, "stem": stem,
                      "hint": hint, "unsure": unsure,
                      "examples": examples, "stressed": stressed})
    for w in words:
        if only_missing and _has_file(speech_dir, w):
            continue
        items.append({"kind": "word", "text": w, "stem": w})
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


def finish(x: np.ndarray, span: tuple[int, int], kind: str) -> tuple:
    """The trimmed, faded, levelled clip and its record."""
    a = max(0, span[0] - int(LEAD_S * RATE))
    b = min(len(x), span[1] + int(TAIL_S * RATE))
    y = x[a:b].copy()
    f = max(1, int(FADE_S * RATE))
    ramp = np.linspace(0.0, 1.0, f)
    y[:f] *= ramp
    y[-f:] *= ramp[::-1]
    if kind == "chunk":
        now = 20 * np.log10(np.sqrt(np.mean(y ** 2)) + 1e-12)
        gain_db = CHUNK_RMS_DBFS - now
    else:
        gain_db = WORD_LOUDNESS - k_weighted_db(y)
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
           "limited": bool(limited)}
    if kind == "word":
        rec["loudness"] = round(k_weighted_db(y), 2)
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
                "rate_hz": RATE, "chunk_rms_dbfs": CHUNK_RMS_DBFS,
                "word_loudness": WORD_LOUDNESS, "latency_ms": None,
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


def cmd_check(args) -> int:
    root = Path(args.speech_dir)
    chunks, words = bank_items()
    miss_c = [c for c in sorted(chunks) if not _has_file(root, f"chunks/{c}")]
    miss_w = [w for w in words if not _has_file(root, w)]
    print(f"chunks: {len(chunks) - len(miss_c)} of {len(chunks)} recorded")
    print(f"words:  {len(words) - len(miss_w)} of {len(words)} recorded")
    for label, miss in (("chunks", miss_c), ("words", miss_w)):
        if miss:
            print(f"missing {label} (first 20): {', '.join(miss[:20])}")
    return 0 if not (miss_c or miss_w) else 1


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
    k = sub.add_parser("check", help="what is still missing")
    k.add_argument("--speech-dir", default=str(SPEECH_DIR))
    k.set_defaults(fn=cmd_check)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
