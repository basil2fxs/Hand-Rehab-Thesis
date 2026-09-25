"""Who a Syllables block is set up for: four age bands and the study's
own profile. Sources, with codes, are in docs/research/new_modes/
syllables-all-ages.md (verified 25 September 2026).

WHY AGE CHANGES THE GAME. The mode was built for 6 to 9 year olds:
familiar words, the word printed before the choice, a late buzz on the
right finger, falls of 4.0 down to 2.5 s. Each of those is right for a
young reader and wrong for an older one.

- Speed. Children are about 1.8 times slower than adults at 10 and 1.5
  times at 12, and a 15 year old is as fast as an adult (Hale 1990);
  choice time slows again through later adulthood (Der and Deary
  2006). Speed is also where adult dyslexia shows most, more than
  accuracy (Reis, Araujo, Morais and Faisca 2020; Callens, Tops and
  Brysbaert 2012). So falls shorten from 10, and an adult's fall time
  is the thing measured, not a floor.
- Material. Older struggling readers are helped by multisyllabic and
  morphological work (for adults, Gray, Ehri and Locke 2018), root
  knowledge drives reading of long derived words (Kearns 2015), and
  made-up words are the standard way to measure decoding apart from
  word knowledge (Herrmann, Matyas and Pratt 2006; van IJzendoorn and
  Bus 1994). Adults read familiar child words at a glance. So teens add derived words and 20 percent made-up words, and
  adults read rarer derived words of three to five syllables with a
  third made up.
- Print before the choice. Seeing and hearing a chunk together is a
  reasonable teaching step for a young child, but an adult holds two
  to four printed chunks with ease and can answer from the print just
  shown without listening at all; support that helps novices hinders
  skilled learners (Kalyuga, Ayres, Chandler and Sweller 2003). So print fades above rung 3 for children and
  adults hear the word without seeing it.
- The buzz. On the developer's own bench runs a player could wait for
  the buzz and hold the easiest rung (32 of 44 sets), so adults play
  without it and teens keep only its later steps.
- Sound after print. Integration is strongest near synchrony in adults
  (Froyen, Van Atteveldt, Bonte and Blomert 2008) and children after
  four years of reading integrate at a 200 ms letter lead (Froyen,
  Bonte, van Atteveldt and Blomert 2009), so the sound trails the
  print a little for children and not at all for adults.
  Neural integration studies, not teaching trials: design values.

THE STUDY'S PROFILE. `classic` is the design exactly as the healthy
baseline study pre-registered it (Section 1.4, S6 and S7), and the
study battery pins it, so no participant's age can change the block
the checks were written for. Every other profile is for play and for
later studies.

WHAT THE NUMBERS ARE. The fall tables scale the child table by those
speed ratios; the foil shares follow the error literature; none is a
measured optimum for this task, and the thesis must report them as
design choices.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# Foil shares, as weights over the three foil slots of a set. F9 is the
# morphological swap (un for dis, ment for ness), for readers old
# enough to meet derived words. Adults get no far foils (almost nobody
# picks them), no reversals (few readers past 10 reverse), no
# same-word syllables (trivial with the word strip on screen) and no
# pseudohomophones (adults who see misspellings spell worse after).
TEEN_FOILS = {"F3": 30, "F7": 20, "F9": 20, "F5": 10, "F2": 10,
              "F6": 5, "F4": 5}
ADULT_FOILS = {"F3": 35, "F9": 25, "F7": 20, "F5": 10, "F2": 10}


@dataclass(frozen=True)
class Profile:
    pid: str
    # Word material: "child" is the bank (bands A to C), then the
    # extra pools in assets/words. child_bands limits the bank.
    pools: tuple[str, ...] = ("child",)
    child_bands: tuple[str, ...] | None = None
    min_syll: int = 2
    max_syll: int = 4
    pseudo_share: float = 0.0
    # None keeps the configured table and the class floor.
    fall_table: tuple[float, ...] | None = None
    min_fall_s: float = 2.5
    # "rung": 3-down-1-up on first-press correctness moves the rung.
    # "fall": the rung and the foil mix stay put and only the fall time
    # moves, 4-down-1-up (84.1 percent, Levitt 1971), +step_up after
    # an error or a miss, -step_down after four unaided right.
    staircase: str = "rung"
    fall_start_s: float = 2.4
    fall_lo_s: float = 1.0
    fall_hi_s: float = 3.0
    fall_step_up_s: float = 0.20
    fall_step_down_s: float = 0.17
    fall_down_after: int = 4
    # Print before the choice: shown at rungs up to print_rungs (8 is
    # always, 0 never). model False skips the MODEL phase: the word is
    # heard at ATTEND and each chunk at its set's spawn.
    print_rungs: int = 8
    model: bool = True
    respeak_rungs: tuple[int, ...] | None = None
    prompt: bool | None = None
    prompt_steps: tuple[float, ...] | None = None
    returns: bool = True
    sound_lead_ms: int = 0
    rewards: str = "child"                  # child | neutral | adult
    foil_weights: dict = field(default_factory=dict)
    far_foils_rung1_only: bool = False
    tile_scale: float = 1.0
    # Vowel foils on an unstressed syllable only when the chunk audio
    # is spelt: spoken reduced, ter, tar and tur all sound like 'tuh'.
    guard_unstressed_vowels: bool = False


PROFILES: dict[str, Profile] = {
    "classic": Profile("classic"),
    "6-9": Profile("6-9", print_rungs=3, sound_lead_ms=175,
                   guard_unstressed_vowels=True),
    "10-12": Profile(
        "10-12", pools=("child", "teen"), child_bands=("B", "C"),
        pseudo_share=0.2,
        fall_table=(3.2, 3.2, 2.8, 2.8, 2.4, 2.4, 2.0, 2.0),
        min_fall_s=2.0, print_rungs=2, respeak_rungs=(1, 2, 3, 4),
        prompt=True, prompt_steps=(0.75, 0.9), sound_lead_ms=100,
        rewards="neutral", foil_weights=TEEN_FOILS,
        far_foils_rung1_only=True, guard_unstressed_vowels=True),
    "13-15": Profile(
        "13-15", pools=("child", "teen"), child_bands=("B", "C"),
        pseudo_share=0.2,
        fall_table=(2.8, 2.8, 2.4, 2.4, 2.0, 2.0, 1.7, 1.6),
        min_fall_s=1.6, print_rungs=2, respeak_rungs=(1, 2, 3, 4),
        prompt=True, prompt_steps=(0.75, 0.9), sound_lead_ms=100,
        rewards="neutral", foil_weights=TEEN_FOILS,
        far_foils_rung1_only=True, guard_unstressed_vowels=True),
    "16+": Profile(
        "16+", pools=("adult",), min_syll=3, max_syll=5, pseudo_share=0.4,
        min_fall_s=1.0, staircase="fall", print_rungs=0, model=False,
        respeak_rungs=tuple(range(1, 9)), prompt=False, rewards="adult",
        foil_weights=ADULT_FOILS),
    "60+": Profile(
        "60+", pools=("adult",), min_syll=3, max_syll=4, pseudo_share=0.3,
        fall_table=(2.8, 2.8, 2.4, 2.4, 2.0, 2.0, 1.7, 1.6),
        min_fall_s=1.6, print_rungs=0, model=False,
        respeak_rungs=tuple(range(1, 9)), prompt=False, rewards="adult",
        foil_weights=ADULT_FOILS, tile_scale=1.3),
}
AGE_BANDS = ("6-9", "10-15", "16+", "60+")


def band_for_age(age) -> str | None:
    """The profile for an intake age, None when the age is blank or
    not a number. 10 to 12 and 13 to 15 are one band with two tables,
    because a 15 year old is as fast as an adult and a 10 year old is
    not."""
    try:
        years = float(str(age).strip())
    except (TypeError, ValueError):
        return None
    if years < 10:
        return "6-9"
    if years < 13:
        return "10-12"
    if years < 16:
        return "13-15"
    if years < 60:
        return "16+"
    return "60+"


def resolve(age_band, age=None) -> Profile:
    """The profile a block plays. `age_band` is the config value:
    classic, a band, or auto (the intake age, and 6-9 when it is
    blank, the design this mode was built on). An unknown value plays
    classic rather than guessing."""
    key = str(age_band or "auto").strip()
    if key == "auto":
        key = band_for_age(age) or "6-9"
    if key == "10-15":
        key = band_for_age(age) if band_for_age(age) in (
            "10-12", "13-15") else "10-12"
    return PROFILES.get(key, PROFILES["classic"])
