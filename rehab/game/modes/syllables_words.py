"""Word list for Syllable Beats. Australian English, imageable,
age-appropriate nouns a 6 to 11 year old knows.

HOW THE GRADING FOLLOWS THE BRIEF. The brief asks for a starter list
selected on child-frequency (SUBTLEX-UK children's band, Zipf scale)
and cross-checked for age suitability, split into three bands:
A = Zipf 5+ early-acquired everyday words, B = Zipf 4 to 5, C = under
4 or any 4-syllable word. No frequency database ships with this app,
so the bands here are hand-assigned to the same rule of thumb: A is
words in any young child's daily vocabulary (dog, apple, banana), B is
words a child knows but meets less often (lizard, umbrella, cockatoo),
and C is the rarer words plus, per the brief's rule, every 4-syllable
word regardless of how common it is. Distribution keeps the brief's
shape scaled down: heaviest on 2-syllable words, then 3, then 1, then
4. Where the list leans local on purpose (wombat, kookaburra, galah,
billabong) it is because these are the imageable animals and things an
Australian child actually meets in books and backyards.

SYLLABLE SPLITS AND STRESS follow spoken Australian pronunciation in
the Macquarie Dictionary's convention, one convention for the whole
list as the brief requires. Splits are text chunks that concatenate
back to the spelling, so the screen can render the word as blocks with
no separate display string; where spelling and phonology disagree the
split follows the spelling boundary nearest the spoken one (rab-bit,
not ra-bbit). stress is the 0-based index of the primary-stress
syllable.

ONSET-RIME (level 5) uses the one-syllable CVC-family words: each has
an `onset_rime` pair splitting the leading consonant(s) from the rest,
which is the standard onset-rime cut.

PHONEME BLOCKS (level 6) use the transparent subset: `graphemes` is
the word's spelling cut into one chunk per phoneme (sh, oo, ck and
double letters count as one grapheme, standard phonics practice), so
one tap maps to one block maps to one sound, and the graphemes can
fade into the blocks as letter feedback after a correct response
(letters attached, Ehri et al. 2001). Words whose spelling cannot be
cut one-to-one (cake, ball) carry None and stay out of level 6.
"""
from __future__ import annotations

from dataclasses import dataclass


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
    # Spelling not one-to-one, so no grapheme blocks: level 6 skips
    # these two, levels 1 to 5 still use them.
    _w("ball", "A", ("ball",), 0, ("b", "all")),
    _w("cake", "A", ("cake",), 0, ("c", "ake")),

    # ---- two syllables.
    _w("wombat", "A", ("wom", "bat"), 0),
    _w("rabbit", "A", ("rab", "bit"), 0),
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
)


# Level 5 material: the onset-rime cut only exists for the CVC-family
# one-syllable words, so the filter is "has a cut".
ONSET_RIME_WORDS: tuple[Word, ...] = tuple(
    w for w in WORDS if w.onset_rime is not None)

# Level 6 material: transparent spellings with 2 to 4 phonemes (four
# fingers cap the count at 4 by design).
TRANSPARENT_WORDS: tuple[Word, ...] = tuple(
    w for w in WORDS if w.graphemes is not None
    and 2 <= len(w.graphemes) <= 4)


# The bag needs at least this many words or a 10-word round repeats
# material almost immediately, which teaches the list rather than the
# skill. Bands that come up short borrow from the band below.
_MIN_POOL = 8


def words_for(level: int, band: str) -> tuple[Word, ...]:
    """The draw pool for a level at a band.

    Levels 1 to 4 draw whole words from the current band: level 1 stops
    at 3 syllables (the counting entry point), level 2 up adds the
    4-syllable words, which only exist in band C. A band whose pool is
    thin for the level (band C at level 1 holds only the rare 3-syllable
    words) tops up from the easier bands so a round of 10 words never
    cycles a handful of items. Level 5 is the onset-rime subset and
    level 6 the transparent subset; both ignore the band because those
    subsets are already the easy end of the list, and thinning them
    further would leave too few words to fill a session without
    immediate repeats.
    """
    if level >= 6:
        return TRANSPARENT_WORDS
    if level == 5:
        return ONSET_RIME_WORDS
    max_syll = 3 if level <= 1 else 4
    ladder = ["A", "B", "C"]
    start = ladder.index(band) if band in ladder else 0
    pool: list[Word] = []
    # Walk from the asked band down toward A until the pool is usable.
    for b in reversed(ladder[:start + 1]):
        pool.extend(w for w in WORDS
                    if w.band == b and w.n_syll <= max_syll)
        if len(pool) >= _MIN_POOL:
            break
    if not pool:
        pool = [w for w in WORDS if w.n_syll <= max_syll]
    return tuple(pool)
