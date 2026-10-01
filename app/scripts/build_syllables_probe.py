#!/usr/bin/env python3
"""Build the Syllables probe: the fixed sets a case session opens with.

    python3 scripts/build_syllables_probe.py          write the file
    python3 scripts/build_syllables_probe.py --check  exit 1 if the file
                                                      on disk differs

Writes assets/words/syllables_probe.json. The game plays these sets in
this order, the same for every session and every reader of an age
group, with no prompt, no replay, no returns and the same plain close
after every answer (SyllablesMode, the probe section). The in-game
numbers adapt to the reader, so they cannot show change across
sessions; a fixed list given the same way every time can (the deep
review of 1 October 2026, docs/research/deep/syllables.md,
recommendation 3: GraphoGame keeps static assessment levels apart from
training, Richardson and Lyytinen 2014; fixed lists reach an ICC of
0.91, Yeatman et al. 2021; single-case studies draw alternate forms
from item pools, Thurmann-Moe et al. 2021).

WHAT A SET HOLDS. The target syllable, one near foil from one
confusion family and two far foils (F1). Each family gets the same
number of sets (four for children and teens, five for adults), so a
family's sets can be compared with each other across sessions. Half
the targets are heard with a weak vowel where the family allows it (a
vowel foil never sits on a weak syllable: ter, tar and tur all say
"tuh" there). Teens and adults meet made-up words as in training.

TRAINED AND HELD OUT. Every other set of a family is held out: its
word is never drawn in training for that age group, so the probe has
words the reader practises and words they never practise, and a gain
on both is not the practice of those words.

AGE GROUPS. One list for 6 to 9, one for 10 to 15 (both teen
profiles) and one for adults (16 and over, 60 and over, words of up to
four syllables so both can play them). The time per set is the
profile's entry fall and is stored here, so a later change to the
training tables cannot change the probe.

The draw is seeded and the file is rebuilt only on purpose: a changed
probe starts a new series. The items are not calibrated; that needs
readers (after collection).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
OUT = APP / "assets" / "words" / "syllables_probe.json"
SEED = 20261001
VERSION = 1
BUILT_ON = "2026-10-01"

GROUPS = {
    "child": {"profiles": ("6-9",), "per_family": 4},
    "teen": {"profiles": ("10-12", "13-15"), "per_family": 4},
    "adult": {"profiles": ("16+", "60+"), "per_family": 5},
}
# A made-up word every this many sets (teens 20 percent, adults a
# third), as the profiles' pseudo shares; never for children.
PSEUDO_EVERY = {"child": 0, "teen": 5, "adult": 3}


def _candidates(group: str):
    from finger_rehab.game.modes.syllables_profiles import PROFILES
    from finger_rehab.game.modes.syllables_words import (all_words,
                                                         profile_words)
    if group == "child":
        real = [w for w in all_words() if w.band in ("A", "B")]
        return real, []
    prof = PROFILES["10-12" if group == "teen" else "60+"]
    real, pseudo = profile_words(prof, "B")
    return list(real), list(pseudo)


def _speech(root: Path):
    data = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    return dict(data.get("syllable_map") or {})


def _has_audio(root: Path, word: str, files, pos: int) -> bool:
    from finger_rehab.game.modes.syllables_words import speech_stem
    if pos >= len(files):
        return False
    word_ok = any((root / f"{speech_stem(word)}{ext}").exists()
                  for ext in (".ogg", ".wav"))
    base = root / str(files[pos])
    syl_ok = any(base.with_name(base.name + ext).exists()
                 for ext in (".wav", ".ogg"))
    return word_ok and syl_ok


def _slots(group: str, families, per_family: int, rng: random.Random):
    """(family, wants_weak, wants_pseudo) per set, in playing order:
    no family twice running, half weak where the family allows it."""
    slots = []
    for fam in families:
        for k in range(per_family):
            weak = (k % 2 == 1) and fam != "vowel"
            slots.append([fam, weak])
    for _ in range(2000):
        rng.shuffle(slots)
        if all(a[0] != b[0] for a, b in zip(slots, slots[1:])):
            break
    every = PSEUDO_EVERY[group]
    out = []
    for i, (fam, weak) in enumerate(slots):
        pseudo = bool(every) and (i % every == every - 1) and not weak
        out.append((fam, weak, pseudo))
    return out


def build_group(group: str, root: Path, rng: random.Random) -> list[dict]:
    from finger_rehab.game.modes.syllables_foils import (FAMILY_KIND,
                                                         Inventory,
                                                         build_option_set)
    from finger_rehab.game.modes.syllables_profiles import PROFILES
    from finger_rehab.game.modes.syllables_words import (
        pool_syllable_lists, syllable_lists)
    spec = GROUPS[group]
    prof = PROFILES[spec["profiles"][0]]
    smap = _speech(root)
    inv = Inventory(syllable_lists() if group == "child"
                    else pool_syllable_lists())
    real, pseudo = _candidates(group)
    real = sorted(real, key=lambda w: w.word)
    pseudo = sorted(pseudo, key=lambda w: w.word)
    used: set[str] = set()
    tally: dict[int, int] = {}
    recent: list[int] = []
    held_count: dict[str, int] = {}
    items = []
    for fam, want_weak, want_pseudo in _slots(group, prof.families,
                                              spec["per_family"], rng):
        kind = FAMILY_KIND[fam]
        made = None
        for weak_req, pseudo_req in ((want_weak, want_pseudo),
                                     (want_weak, False), (False, False)):
            pool = list(pseudo if pseudo_req else real)
            rng.shuffle(pool)
            for w in pool:
                if w.word in used or w.word not in smap:
                    continue
                entry = smap[w.word]
                weak = list(entry.get("weak") or [])
                files = list(entry.get("files") or [])
                positions = list(range(w.n_syll))
                rng.shuffle(positions)
                for pos in positions:
                    if pos >= len(weak) or bool(weak[pos]) != weak_req:
                        continue
                    if not _has_audio(root, w.word, files, pos):
                        continue
                    trial_rng = random.Random(rng.random())
                    t2, r2 = dict(tally), list(recent)
                    oset = build_option_set(
                        w, pos, 1, trial_rng, inv, [0, 1, 2, 3], t2, r2,
                        kinds=(kind, "F1", "F1"),
                        avoid=(frozenset({"F3"}) if weak_req
                               else frozenset()))
                    kinds = sorted(o.kind for o in oset.options
                                   if o.kind != "target")
                    if kinds != sorted([kind, "F1", "F1"]):
                        continue
                    made = (w, pos, weak_req, oset)
                    break
                if made:
                    break
            if made:
                break
        if made is None:
            raise SystemExit(f"no {group} set could be built for {fam}")
        w, pos, weak, oset = made
        used.add(w.word)
        tally[oset.target_lane] = tally.get(oset.target_lane, 0) + 1
        recent.append(oset.target_lane)
        n_held = held_count.get(fam, 0)
        # Alternate within a family, starting on held out for every
        # other family, so an odd count splits evenly overall.
        held = (n_held + prof.families.index(fam)) % 2 == 0
        held_count[fam] = n_held + 1
        items.append({
            "word": w.word,
            "syllables": list(w.syllables),
            "pos": pos,
            "syl": oset.target,
            "weak": 1 if weak else 0,
            "lex": w.lex,
            "family": fam,
            "near": kind,
            "held_out": held,
            "tlane": oset.target_lane,
            "options": [{"lane": o.lane, "text": o.text, "kind": o.kind}
                        for o in sorted(oset.options,
                                        key=lambda o: o.lane)],
        })
    return items


def build() -> dict:
    from finger_rehab.game.modes.syllables_profiles import PROFILES
    root = APP / "assets" / "speech"
    rng = random.Random(SEED)
    item_sets = {g: build_group(g, root, rng) for g in GROUPS}
    profiles = {}
    for g, spec in GROUPS.items():
        for pid in spec["profiles"]:
            prof = PROFILES[pid]
            if prof.staircase == "fall":
                time_s = prof.fall_start_s
            elif prof.fall_table:
                time_s = prof.fall_table[0]
            else:
                time_s = 6.0
            profiles[pid] = {"items": g, "time_s": time_s}
    return {
        "version": VERSION,
        "seed": SEED,
        "built_on": BUILT_ON,
        "generated_by": "scripts/build_syllables_probe.py",
        "note": ("Fixed probe sets, played in this order with no "
                 "prompt, replay, returns or feedback. Lanes are 0 to 3, "
                 "index to little in the playing hand's desk order. "
                 "held_out words are never drawn in training."),
        "profiles": profiles,
        "item_sets": item_sets,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 if the file on disk differs")
    args = ap.parse_args()
    text = json.dumps(build(), indent=1, ensure_ascii=False) + "\n"
    if args.check:
        same = OUT.exists() and OUT.read_text(encoding="utf-8") == text
        print("probe file is current" if same else "probe file differs")
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8")
    data = json.loads(text)
    for g, items in data["item_sets"].items():
        print(f"{g}: {len(items)} sets, "
              f"{sum(1 for i in items if i['held_out'])} held out, "
              f"{sum(i['weak'] for i in items)} weak, "
              f"{sum(1 for i in items if i['lex'] == 'pseudo')} made up")
    return 0


if __name__ == "__main__":
    sys.exit(main())
