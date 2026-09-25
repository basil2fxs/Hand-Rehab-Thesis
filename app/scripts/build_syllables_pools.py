#!/usr/bin/env python3
"""Build the Syllables word pools for readers past the child bank.

    python3 scripts/build_syllables_pools.py

Writes assets/words/syllables_pools.json with three pools the age
profiles draw (syllables_profiles.py):

  teen    derived and longer words for 10 to 15 year olds, beside the
          child bank's B and C bands, which they draw as well;
  adult   rarer derived and compound words of three to five syllables;
  pseudo  made-up words assembled from the bank's own chunks.

WHY THESE WORDS. Multisyllabic and morphological teaching is what helps
struggling adolescents and adults, and knowing the root is what lets a
reader take apart a long derived word, so at least half of each list
is derived (a real prefix or suffix) or compound. The lists were
chosen by hand for length and morphology. They are NOT checked against
frequency or age-of-acquisition norms (CYP-LEX, SUBTLEX-UK, Kuperman),
which would need those files downloaded; the thesis should say so, and
the norms are the next step if the pools are used in a study.

HOW A WORD IS WRITTEN HERE. Chunks joined by hyphens, the stressed one
in capitals: un-a-VAIL-a-ble. The chunks must join back to the
spelling. Splits follow the syllable, and where a morpheme boundary
lies on a syllable boundary the split keeps it (dis-a-GREE-ment), the
convention recommended for readers of 10 and over. A word already in
the child bank is dropped with a note: the bank's split wins.

THE MADE-UP WORDS. Made-up words are the standard way to measure
decoding apart from word knowledge. Each one is three or four chunks
taken from a short list of bank chunks with one clear spelling
pronunciation (closed short-vowel chunks and r-controlled ones), stress
on the first chunk, drawn with a fixed seed, with any string that is a
word in the bank, the pools or the small exclusion list below thrown
out. The exclusion list is a hand check, not a dictionary: listen to
the recorded list once for anything that sounds like a real word.
"""
from __future__ import annotations

import json
import random
import sys
from datetime import date
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
OUT = APP / "assets" / "words" / "syllables_pools.json"

TEEN = """
dis-COV-er-y un-HAP-py dis-HON-est un-U-su-al POW-er-ful COL-our-ful
GOV-ern-ment en-VI-ron-ment com-pe-TI-tion pop-u-LA-tion CARE-ful-ly
QUI-et-ly SUD-den-ly HON-est-ly un-KIND-ness dis-a-GREE re-PLACE-ment
en-JOY-ment a-MAZE-ment ex-CITE-ment mis-be-HAVE mis-un-der-STAND
re-ar-RANGE pre-DIC-tion pro-TEC-tion col-LEC-tion di-REC-tion
at-TEN-tion in-VEN-tion per-FOR-mance ap-PEAR-ance re-MARK-a-ble
un-BREAK-a-ble re-US-a-ble VIS-i-ble SEN-si-ble HOR-ri-ble MAG-i-cal
PRAC-ti-cal cre-A-tive ex-PEN-sive at-TRAC-tive pro-DUC-tive
me-MO-ri-al CHAM-pi-on CHAM-pi-on-ship MEM-ber-ship PART-ner-ship
LEAD-er-ship NEIGH-bour-hood BROTH-er-hood CIT-i-zen vol-un-TEER
SCI-en-tist mu-SI-cian e-lec-TRI-cian li-BRAR-i-an his-TOR-i-cal
dis-ap-PROVE un-CER-tain in-cor-RECT im-PA-tient in-AC-tive un-TI-dy
dis-o-BEY FEAR-less-ly HOPE-ful-ly USE-ful-ness LONE-li-ness
EMP-ti-ness en-COUR-age en-COUR-age-ment mis-TAK-en un-FIN-ished
un-LUCK-y in-SPEC-tor in-VES-ti-gate op-er-A-tion ex-pla-NA-tion
con-ver-SA-tion sug-GES-tion in-STRUC-tion con-STRUC-tion
sub-TRAC-tion ad-DI-tion di-VI-sion sci-en-TIF-ic IN-ter-net
""".split()

ADULT = """
un-a-VAIL-a-ble dis-a-GREE-ment in-de-PEN-dence mis-un-der-STAND-ing
re-con-STRUC-tion im-PROB-a-ble un-for-GET-ta-ble ir-re-SPON-si-ble
in-ter-NA-tion-al dis-con-NECT-ed un-be-LIEV-a-ble com-mu-ni-CA-tion
or-gan-i-SA-tion de-VEL-op-ment ad-VEN-tur-ous un-CER-tain-ty
pos-si-BIL-i-ty re-LI-a-ble ac-CEPT-a-ble de-ter-mi-NA-tion
i-mag-i-NA-tion con-cen-TRA-tion in-SUR-ance re-SIST-ance ex-IS-tence
CON-fi-dence in-flu-EN-tial es-SEN-tial of-FI-cial fi-NAN-cial
de-FEN-sive oc-CA-sion-al-ly un-FOR-tu-nate-ly im-ME-di-ate-ly
sig-NIF-i-cant un-der-ES-ti-mate o-ver-WHELM-ing out-STAND-ing
ne-ver-the-LESS what-so-EV-er vo-CAB-u-lar-y PAR-lia-ment
AR-chi-tec-ture LIT-er-a-ture AG-ri-cul-ture psy-CHOL-o-gy e-CON-o-my
de-MOC-ra-cy cur-RIC-u-lum ma-TE-ri-al in-DUS-tri-al
op-por-TU-ni-ty u-ni-VER-si-ty per-son-AL-i-ty cu-ri-OS-i-ty
gen-er-OS-i-ty ma-JOR-i-ty se-CU-ri-ty re-LA-tion-ship
CARE-less-ness HELP-less-ness a-WARE-ness ef-FEC-tive-ness
ap-pre-ci-A-tion ad-min-is-TRA-tion qual-i-fi-CA-tion
rec-om-men-DA-tion in-ter-pre-TA-tion ir-REG-u-lar un-re-LI-a-ble
in-AD-e-quate dis-ad-VAN-tage pre-DOM-i-nant in-con-SIS-tent
un-NEC-es-sar-y re-SPON-si-ble ac-com-mo-DA-tion en-thu-si-AS-tic
dis-ap-POINT-ment em-BAR-rass-ment ac-COM-plish-ment es-TAB-lish-ment
ad-VER-tise-ment re-QUIRE-ment in-VEST-ment ap-POINT-ment
mis-in-TER-pret o-ver-ES-ti-mate un-der-de-VEL-oped
coun-ter-pro-DUC-tive pho-to-SYN-the-sis ther-MOM-e-ter MI-cro-scope
TEL-e-vi-sion CAT-e-go-ry hy-POTH-e-sis a-NAL-y-sis
con-sid-er-A-tion
""".split()

# Bank chunks with one clear spelling pronunciation: closed chunks with
# a short vowel, and the r-controlled ones. No c or g before e or i,
# no vowel teams.
PSEUDO_CHUNKS = """
ban bit dol pen cum tin lop sid rum pat mel fin dap tob nus
lan vit kem sop mid rob lub ten mar tor for ber mur
""".split()
# Real words, or near enough, that a draw could hit.
EXCLUDE = {"bandit", "penmar", "timber", "tinder", "lobster", "sidetor",
           "border", "murder", "banter", "fortin", "maribor", "robber"}
N_PSEUDO = 60
SEED = 2026


def parse(entry: str) -> dict:
    chunks = entry.split("-")
    stress = [i for i, c in enumerate(chunks) if c.isupper()]
    if len(stress) != 1:
        raise ValueError(f"{entry}: mark exactly one stressed chunk")
    syls = [c.lower() for c in chunks]
    return {"word": "".join(syls), "syllables": syls, "stress": stress[0]}


def build_pool(entries, pool: str, have: set[str], min_s: int,
               max_s: int) -> tuple[list[dict], list[str]]:
    out, dropped, seen = [], [], set()
    for e in entries:
        w = parse(e)
        if w["word"] in have or w["word"] in seen:
            dropped.append(w["word"])
            continue
        if not (min_s <= len(w["syllables"]) <= max_s):
            raise ValueError(f"{e}: {len(w['syllables'])} syllables, "
                             f"{pool} takes {min_s} to {max_s}")
        for c in w["syllables"]:
            if not (c.isalpha() and c.isascii() and 1 <= len(c) <= 6):
                raise ValueError(f"{e}: chunk {c!r}")
        seen.add(w["word"])
        out.append({**w, "pool": pool, "lex": "word"})
    return out, dropped


def build_pseudo(have: set[str]) -> list[dict]:
    rng = random.Random(SEED)
    out, seen = [], set(have)
    while len(out) < N_PSEUDO:
        n = rng.choice((3, 3, 4))
        syls = rng.sample(PSEUDO_CHUNKS, n)
        word = "".join(syls)
        # No doubled letter across a join (bitter, sopp), which reads
        # as a spelling cue rather than a chunk boundary.
        if any(a[-1] == b[0] for a, b in zip(syls, syls[1:])):
            continue
        if word in seen or any(x in word for x in EXCLUDE):
            continue
        seen.add(word)
        out.append({"word": word, "syllables": syls, "stress": 0,
                    "pool": "pseudo", "lex": "pseudo"})
    return out


def main() -> int:
    from finger_rehab.game.modes.syllables_words import all_words
    have = {w.word for w in all_words()}
    teen, t_drop = build_pool(TEEN, "teen", have, 2, 4)
    adult, a_drop = build_pool(ADULT, "adult", have | {w["word"]
                                                       for w in teen}, 3, 5)
    pseudo = build_pseudo(have | {w["word"] for w in teen + adult})
    data = {
        "licence": "Project word lists, hand-built; see the script.",
        "generated_by": "scripts/build_syllables_pools.py",
        "generated_on": date.today().isoformat(),
        "convention": "chunks join to the spelling; stress is the "
                      "0-based index of the stressed chunk",
        "norms_checked": False,
        "counts": {"teen": len(teen), "adult": len(adult),
                   "pseudo": len(pseudo)},
        "words": teen + adult + pseudo,
    }
    OUT.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"teen {len(teen)} (dropped as already in the bank: "
          f"{', '.join(t_drop) or 'none'})")
    print(f"adult {len(adult)} (dropped: {', '.join(a_drop) or 'none'})")
    print(f"pseudo {len(pseudo)}: "
          f"{', '.join(w['word'] for w in pseudo[:12])} ...")
    print(f"-> {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
