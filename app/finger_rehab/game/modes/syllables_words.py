"""Word material for Syllables. Australian English, imageable,
age-appropriate words a 6 to 11 year old knows.

TWO SOURCES, ONE POOL. The bank is assets/words/syllables_bank.json
(built from assets/words/syllables_source.txt by
scripts/build_syllables_bank.py, about 690 words of 2 to 4
syllables). The hand list WORDS below is the seed and the review set:
it is the material the mode was designed and tested against, it holds
the local words a child here actually meets (wombat, kookaburra,
galah, billabong, echidna, budgerigar), and where a word appears in
both, the hand entry wins. Loading is cached, and a missing or broken
bank file leaves the hand list alone rather than taking the game down
with it.

HOW THE BANDS WORK. A is everyday words, mostly two syllables; B is
words a child knows but meets less often, two and three syllables; C
is the rarer words and, per the brief's rule, every four-syllable word
whatever its frequency. Promotion (8 of the last 10 right) therefore
walks the child 2, 3, 4 syllables without the mode ever asking for a
word length directly. No band draws a one-syllable word: one syllable
has no boundary to hear, so MIN_SYLLABLES is two.

SYLLABLE SPLITS AND STRESS follow spoken Australian pronunciation in
the Macquarie Dictionary's convention, one convention for the whole
list. Splits are text chunks that concatenate back to the spelling, so
the screen renders the word as chunks with no separate display string;
where spelling and phonology disagree the split follows the spelling
boundary nearest the spoken one (rab-bit, not ra-bbit). stress is the
0-based index of the primary-stress syllable.

WHY THE SPLIT IS NEVER THE QUESTION. English syllable division in
print is a convention, not a fact: Kearns (2020, Reading Research
Quarterly) analysed 14,844 words from Grade 1 to 8 texts and found the
two taught division rules fit 70.6 percent (VC|CV, rab-bit) and 30.5
percent (V|CV, ti-ger) of the words they apply to. So the bank stores
ONE split per word, chosen by the spoken boundary, and the game never
asks a child to place a boundary: it asks them to pick the chunk that
was spoken. That is also why the spoken syllable and the printed chunk
have to be the same thing (the speech assets are rendered per chunk).

WHAT THE OLD SUB-SYLLABLE MATERIAL IS DOING HERE. onset_rime and
graphemes are kept on the Word record and the one-syllable entries are
kept in WORDS, because they cost nothing and the retired level ladder
may come back as a separate mode. Neither is drawn by the syllables
choice task: `words_for` returns whole words of two or more syllables
only.

HAND COUNT NO LONGER CHANGES THE MATERIAL. Under the old tapping task
a word of n syllables needed n adjacent fingers, so long words existed
only in bilateral play. In the choice task each syllable is one set of
four tiles over four fingers, so a four-syllable word plays exactly as
well on one hand as on two. `bilateral` is kept on the signature
because the caller has it and because the hand rotation reads better
when the two live side by side, but it no longer widens the pool.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Word:
    word: str
    band: str                              # A | B | C
    syllables: tuple[str, ...]             # chunks that join to `word`
    stress: int                            # 0-based primary stress index
    onset_rime: tuple[str, str] | None = None   # level 5 material
    graphemes: tuple[str, ...] | None = None    # level 6 material

    @property
    def n_syll(self) -> int:
        return len(self.syllables)


def _w(word: str, band: str, syllables: tuple[str, ...], stress: int = 0,
       onset_rime: tuple[str, str] | None = None,
       graphemes: tuple[str, ...] | None = None) -> Word:
    return Word(word=word, band=band, syllables=syllables, stress=stress,
                onset_rime=onset_rime, graphemes=graphemes)


WORDS: tuple[Word, ...] = (
    # ---- one syllable. The CVC-family entries carry the onset-rime
    # cut for level 5; the transparently spelt ones carry grapheme
    # blocks for level 6.
    _w("dog", "A", ("dog",), 0, ("d", "og"), ("d", "o", "g")),
    _w("cat", "A", ("cat",), 0, ("c", "at"), ("c", "a", "t")),
    _w("sun", "A", ("sun",), 0, ("s", "un"), ("s", "u", "n")),
    _w("pig", "A", ("pig",), 0, ("p", "ig"), ("p", "i", "g")),
    _w("cup", "A", ("cup",), 0, ("c", "up"), ("c", "u", "p")),
    _w("hat", "A", ("hat",), 0, ("h", "at"), ("h", "a", "t")),
    _w("bus", "A", ("bus",), 0, ("b", "us"), ("b", "u", "s")),
    _w("bed", "A", ("bed",), 0, ("b", "ed"), ("b", "e", "d")),
    _w("net", "B", ("net",), 0, ("n", "et"), ("n", "e", "t")),
    _w("jam", "A", ("jam",), 0, ("j", "am"), ("j", "a", "m")),
    _w("leg", "A", ("leg",), 0, ("l", "eg"), ("l", "e", "g")),
    _w("mud", "A", ("mud",), 0, ("m", "ud"), ("m", "u", "d")),
    _w("bug", "A", ("bug",), 0, ("b", "ug"), ("b", "u", "g")),
    _w("map", "B", ("map",), 0, ("m", "ap"), ("m", "a", "p")),
    _w("fish", "A", ("fish",), 0, ("f", "ish"), ("f", "i", "sh")),
    _w("duck", "A", ("duck",), 0, ("d", "uck"), ("d", "u", "ck")),
    _w("frog", "A", ("frog",), 0, ("fr", "og"), ("f", "r", "o", "g")),
    _w("drum", "B", ("drum",), 0, ("dr", "um"), ("d", "r", "u", "m")),
    _w("crab", "B", ("crab",), 0, ("cr", "ab"), ("c", "r", "a", "b")),
    _w("milk", "A", ("milk",), 0, ("m", "ilk"), ("m", "i", "l", "k")),
    _w("hand", "A", ("hand",), 0, ("h", "and"), ("h", "a", "n", "d")),
    _w("nest", "B", ("nest",), 0, ("n", "est"), ("n", "e", "s", "t")),
    _w("shell", "B", ("shell",), 0, ("sh", "ell"), ("sh", "e", "ll")),
    _w("moon", "A", ("moon",), 0, ("m", "oon"), ("m", "oo", "n")),
    _w("star", "A", ("star",), 0, ("st", "ar"), ("s", "t", "ar")),
    _w("tree", "A", ("tree",), 0, ("tr", "ee"), ("t", "r", "ee")),
    _w("boat", "A", ("boat",), 0, ("b", "oat"), ("b", "oa", "t")),
    _w("rain", "A", ("rain",), 0, ("r", "ain"), ("r", "ai", "n")),
    _w("foot", "A", ("foot",), 0, ("f", "oot"), ("f", "oo", "t")),
    # Five-grapheme cluster words: transparent CCVCC/CCVC+C spellings
    # for the bilateral read-across row at level 6 (a single hand's
    # four fingers never draw them). The onset-rime cut still works,
    # so levels 1 to 5 use them like any one-syllable word.
    _w("stamp", "A", ("stamp",), 0, ("st", "amp"),
       ("s", "t", "a", "m", "p")),
    _w("plant", "A", ("plant",), 0, ("pl", "ant"),
       ("p", "l", "a", "n", "t")),
    _w("drink", "A", ("drink",), 0, ("dr", "ink"),
       ("d", "r", "i", "n", "k")),
    _w("frost", "B", ("frost",), 0, ("fr", "ost"),
       ("f", "r", "o", "s", "t")),
    _w("crust", "B", ("crust",), 0, ("cr", "ust"),
       ("c", "r", "u", "s", "t")),
    _w("twist", "B", ("twist",), 0, ("tw", "ist"),
       ("t", "w", "i", "s", "t")),
    # Spelling not one-to-one, so no grapheme blocks: level 6 skips
    # these two, levels 1 to 5 still use them.
    _w("ball", "A", ("ball",), 0, ("b", "all")),
    _w("cake", "A", ("cake",), 0, ("c", "ake")),

    # ---- two syllables.
    _w("wombat", "A", ("wom", "bat"), 0),
    _w("rabbit", "A", ("rab", "bit"), 0,
       graphemes=("r", "a", "bb", "i", "t")),
    _w("monkey", "A", ("mon", "key"), 0),
    _w("tiger", "A", ("ti", "ger"), 0),
    _w("spider", "A", ("spi", "der"), 0),
    _w("apple", "A", ("ap", "ple"), 0),
    _w("teddy", "A", ("ted", "dy"), 0),
    _w("puppy", "A", ("pup", "py"), 0),
    _w("kitten", "A", ("kit", "ten"), 0),
    _w("water", "A", ("wa", "ter"), 0),
    _w("dinner", "A", ("din", "ner"), 0),
    _w("doctor", "A", ("doc", "tor"), 0),
    _w("garden", "A", ("gar", "den"), 0),
    _w("jumper", "A", ("jum", "per"), 0),
    _w("pillow", "A", ("pil", "low"), 0),
    _w("carrot", "A", ("car", "rot"), 0),
    _w("rocket", "A", ("rock", "et"), 0),
    _w("robot", "A", ("ro", "bot"), 0),
    _w("turtle", "A", ("tur", "tle"), 0),
    _w("zebra", "A", ("ze", "bra"), 0),
    _w("emu", "A", ("e", "mu"), 0),
    _w("joey", "B", ("jo", "ey"), 0),
    _w("bucket", "B", ("buck", "et"), 0),
    _w("dolphin", "B", ("dol", "phin"), 0),
    _w("lizard", "B", ("liz", "ard"), 0),
    _w("parrot", "B", ("par", "rot"), 0),
    _w("possum", "B", ("pos", "sum"), 0),
    _w("penguin", "B", ("pen", "guin"), 0),
    _w("galah", "B", ("ga", "lah"), 1),
    _w("guitar", "B", ("gui", "tar"), 1),
    # Two-syllable words with transparent 5-6 grapheme spellings: the
    # core of the bilateral level 6 row pool. Ordinary words for the
    # syllable levels too, banded on frequency like everything else.
    _w("muffin", "A", ("muf", "fin"), 0,
       graphemes=("m", "u", "ff", "i", "n")),
    _w("pocket", "A", ("pock", "et"), 0,
       graphemes=("p", "o", "ck", "e", "t")),
    _w("basket", "A", ("bas", "ket"), 0,
       graphemes=("b", "a", "s", "k", "e", "t")),
    _w("picnic", "A", ("pic", "nic"), 0,
       graphemes=("p", "i", "c", "n", "i", "c")),
    _w("insect", "B", ("in", "sect"), 0,
       graphemes=("i", "n", "s", "e", "c", "t")),
    _w("sunset", "B", ("sun", "set"), 0,
       graphemes=("s", "u", "n", "s", "e", "t")),
    # The 7-8 grapheme stretch pool: these recruit the little fingers
    # on the read-across row, so they only enter the bilateral level 6
    # draw at band C (the stretch band), gated in words_for.
    _w("blanket", "A", ("blan", "ket"), 0,
       graphemes=("b", "l", "a", "n", "k", "e", "t")),
    _w("sandpit", "B", ("sand", "pit"), 0,
       graphemes=("s", "a", "n", "d", "p", "i", "t")),
    _w("breakfast", "A", ("break", "fast"), 0,
       graphemes=("b", "r", "ea", "k", "f", "a", "s", "t")),

    # ---- three syllables. Stress varies here, which is what makes
    # this the working range for level 4.
    _w("kangaroo", "A", ("kan", "ga", "roo"), 2),
    _w("elephant", "A", ("el", "e", "phant"), 0),
    _w("banana", "A", ("ba", "na", "na"), 1),
    _w("koala", "A", ("ko", "a", "la"), 1),
    _w("potato", "A", ("po", "ta", "to"), 1),
    _w("tomato", "A", ("to", "ma", "to"), 1),
    _w("butterfly", "A", ("but", "ter", "fly"), 0),
    _w("dinosaur", "A", ("di", "no", "saur"), 0),
    _w("computer", "A", ("com", "pu", "ter"), 1),
    _w("strawberry", "B", ("straw", "ber", "ry"), 0),
    _w("umbrella", "B", ("um", "brel", "la"), 1),
    _w("crocodile", "B", ("croc", "o", "dile"), 0),
    _w("octopus", "B", ("oc", "to", "pus"), 0),
    _w("wallaby", "B", ("wal", "la", "by"), 0),
    _w("platypus", "B", ("plat", "y", "pus"), 0),
    _w("cockatoo", "B", ("cock", "a", "too"), 2),
    _w("gorilla", "B", ("go", "ril", "la"), 1),
    _w("ladybird", "B", ("la", "dy", "bird"), 0),
    _w("hamburger", "B", ("ham", "bur", "ger"), 0),
    _w("newspaper", "B", ("news", "pa", "per"), 0),
    _w("pyjamas", "B", ("py", "ja", "mas"), 1),
    _w("echidna", "C", ("e", "chid", "na"), 1),
    _w("billabong", "C", ("bill", "a", "bong"), 0),

    # ---- four syllables, all band C per the brief's rule.
    _w("kookaburra", "C", ("kook", "a", "bur", "ra"), 0),
    _w("helicopter", "C", ("hel", "i", "cop", "ter"), 0),
    _w("caterpillar", "C", ("cat", "er", "pil", "lar"), 0),
    _w("watermelon", "C", ("wa", "ter", "mel", "on"), 0),
    _w("avocado", "C", ("av", "o", "ca", "do"), 2),
    _w("didgeridoo", "C", ("didg", "er", "i", "doo"), 3),
    _w("barramundi", "C", ("bar", "ra", "mun", "di"), 2),
    _w("budgerigar", "C", ("budg", "er", "i", "gar"), 0),
    _w("television", "C", ("tel", "e", "vi", "sion"), 0),
    _w("motorcycle", "C", ("mo", "tor", "cy", "cle"), 0),
    _w("alligator", "C", ("al", "li", "ga", "tor"), 0),

    # ---- five syllables: a token band C pool for the bilateral
    # read-across row at levels 2 to 4. Deliberately tiny: five
    # syllables is where English child vocabulary tops out, and
    # anything longer would test memory span, not segmentation.
    _w("hippopotamus", "C", ("hip", "po", "pot", "a", "mus"), 2),
    _w("refrigerator", "C", ("re", "frig", "er", "a", "tor"), 1),
)




# Level 5 material from the retired tapping ladder: the onset-rime cut
# only exists for the CVC-family one-syllable words. Unused by the
# choice task, kept because the cut is real material and costs
# nothing.
ONSET_RIME_WORDS: tuple[Word, ...] = tuple(
    w for w in WORDS if w.onset_rime is not None)

# Level 6 material from the retired ladder: transparent spellings cut
# one chunk per phoneme. Also unused by the choice task.
TRANSPARENT_WORDS: tuple[Word, ...] = tuple(
    w for w in WORDS if w.graphemes is not None
    and 2 <= len(w.graphemes) <= 4)


# The bag needs at least this many words or a 10-word round repeats
# material almost immediately, which teaches the list rather than the
# skill. Bands that come up short borrow from the band below.
_MIN_POOL = 12

# The shortest and longest word the mode ever draws. One syllable has
# no boundary to hear; past four is memory span, not segmentation
# (English child vocabulary tops out near five syllables and verbal
# span at 5 to 8 years sits around four to five items, Gathercole,
# Pickering, Ambridge and Wearing 2004), and a five-syllable word is
# five option sets in a row before the child sees a finished word.
MIN_SYLLABLES = 2
MAX_SYLLABLES = 4

BANK_PATH = ("assets", "words", "syllables_bank.json")

_BANK_CACHE: tuple[Word, ...] | None = None
_ALL_CACHE: tuple[Word, ...] | None = None


def _bank_file() -> Path:
    """Where the built bank lives, in a source checkout and inside the
    frozen app alike (config._bundle_root resolves _MEIPASS)."""
    try:
        from ...config import _bundle_root
        root = _bundle_root()
    except Exception:
        root = Path(__file__).resolve().parents[3]
    return root.joinpath(*BANK_PATH)


def load_bank(path: Path | None = None) -> tuple[Word, ...]:
    """The built word bank, cached. Returns an empty tuple (and logs
    once) when the file is missing or unreadable: the hand list below
    is a complete, playable pool on its own, so a packaging slip
    degrades the material instead of stopping a child mid-session.

    Entries are validated the way the build script validates them,
    because a hand-edited JSON is exactly the file nobody rebuilds:
    the chunks must join to the word, the stress index must be inside
    the word, and the syllable count must be in range."""
    global _BANK_CACHE
    if path is None and _BANK_CACHE is not None:
        return _BANK_CACHE
    target = path or _bank_file()
    out: list[Word] = []
    try:
        data = json.loads(target.read_text())
        for e in data.get("words", []):
            syls = tuple(str(s) for s in e.get("syllables", ()))
            word = str(e.get("word", ""))
            band = str(e.get("band", "A"))
            stress = int(e.get("stress", 0))
            if (not syls or "".join(syls) != word
                    or band not in ("A", "B", "C")
                    or not (0 <= stress < len(syls))
                    or not (MIN_SYLLABLES <= len(syls) <= MAX_SYLLABLES)):
                continue
            out.append(Word(word=word, band=band, syllables=syls,
                            stress=stress))
    except FileNotFoundError:
        log.warning("Syllables word bank not found at %s; "
                    "playing the built-in list only", target)
    except Exception as e:
        log.warning("Syllables word bank at %s could not be read (%s); "
                    "playing the built-in list only", target, e)
    result = tuple(out)
    if path is None:
        _BANK_CACHE = result
    return result


def all_words() -> tuple[Word, ...]:
    """Bank plus hand list, hand entries winning on conflict, filtered
    to the syllable range the mode plays. Sorted by word so a block's
    material order depends on the seed and nothing else."""
    global _ALL_CACHE
    if _ALL_CACHE is not None:
        return _ALL_CACHE
    merged: dict[str, Word] = {}
    for w in load_bank():
        merged[w.word] = w
    for w in WORDS:
        if MIN_SYLLABLES <= w.n_syll <= MAX_SYLLABLES:
            merged[w.word] = w
    _ALL_CACHE = tuple(sorted(
        (w for w in merged.values()
         if MIN_SYLLABLES <= w.n_syll <= MAX_SYLLABLES),
        key=lambda w: w.word))
    return _ALL_CACHE


def syllable_lists() -> tuple[tuple[str, ...], ...]:
    """Every word's chunks, for the foil generator's inventory: the
    set of syllables the game is allowed to show, and the letter pairs
    that count as pronounceable."""
    return tuple(w.syllables for w in all_words())


def words_for(band: str, bilateral: bool = False) -> tuple[Word, ...]:
    """The draw pool for a band.

    A and B stay at two and three syllables, C adds the four-syllable
    words; a band whose own pool is thin tops up from the band below,
    so a round of ten words never cycles a handful of items. The
    `bilateral` flag is accepted and ignored: word length no longer
    depends on how many hands are connected (module docstring)."""
    ladder = ["A", "B", "C"]
    if band not in ladder:
        band = "A"
    max_syll = MAX_SYLLABLES if band == "C" else 3
    words = all_words()
    pool: list[Word] = []
    start = ladder.index(band)
    for b in reversed(ladder[:start + 1]):
        pool.extend(w for w in words
                    if w.band == b
                    and MIN_SYLLABLES <= w.n_syll <= max_syll)
        if len(pool) >= _MIN_POOL:
            break
    if not pool:
        pool = [w for w in words
                if MIN_SYLLABLES <= w.n_syll <= max_syll]
    return tuple(pool)
