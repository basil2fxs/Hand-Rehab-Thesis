"""Patient-facing feedback wording, in one place.

Why this module exists. The scoring labels ("Perfect", "Great",
"Good", "Late", "Early", "Miss") are DATA: they go into trials.csv,
they pick the 140/141 EEG feedback marker, and tests/test_scoring.py,
tests/test_metrics.py and tests/test_eeg_contract.py pin them. They
are not words for a patient to read. Showing the raw label put "Miss"
in 42 pt above the lane on every trial a patient got wrong, which is
the one thing a rehabilitation tool should never do.

So the labels stay and the DISPLAY MAPPING moves here. Every screen
and mode draws its wording from this bank instead of writing its own
verdict, which means the whole app can be checked against one banned
list (tests/test_feedback_wording.py) rather than string by string.

House rules for every entry (see docs/research notes, feedback lane):
  R1  Never "too" followed by another word. "lighter is fine too" is
      allowed: that is "too" meaning "also" at the end of a clause.
  R2  Never a judgement word as a label. Direction is said as "ahead
      of" / "behind" / "after the beat", not "early" / "late".
  R3  Every non-hit line names the next action or the good part.
      Nothing ends on the shortfall.
  R4  Process, not person. Name the finger, the beat, the count.
      Never a trait ("Unstoppable!").
  R5  Truthful. "Almost" only when something landed; no fake norms.
  R6  Comparisons are self-referenced only.
  R7  Popup at most three words, message chip at most nine.
  R8  No immediate repeats (PhraseDeck below).
  R9  Placeholders come from the trial, and a missing one raises
      rather than reaching the screen as "{target}".
  R10 Australian English, plain ASCII.

Evidence, in short. Feedback given after good trials produces better
delayed retention and higher self-efficacy than feedback after poor
ones (Chiviacowsky and Wulf 2007, Res Q Exerc Sport; Saemi et al 2012,
Psychol Sport Exerc). Feedback aimed at the task and the next action
helps, feedback aimed at the person is the kind that backfires
(Kluger and DeNisi 1996, Psychol Bull; Hattie and Timperley 2007, Rev
Educ Res). Positive feedback raises free-choice persistence
(Deci, Koestner and Ryan 1999, Psychol Bull). The retention benefit of
the motivational account is contested (McKay et al 2023, Psychon Bull
Rev), which is why the wording keeps every bit of ERROR INFORMATION
(which finger, which direction, how far) and drops only the verdict.
"""
from __future__ import annotations

import random
import re
from string import Formatter

# ---------------------------------------------------------------------------
# Banned vocabulary
# ---------------------------------------------------------------------------

# Whole words, case-insensitive. "too" is handled separately because
# "too" meaning "also" is fine; "too" + another word is the judgement.
BANNED: tuple[str, ...] = (
    "wrong", "wrongly", "miss", "missed", "misses", "late", "early",
    "slow", "slower", "slowly", "fail", "failed", "failure", "bad",
    "badly", "oops", "error", "errors", "incorrect", "poor", "poorly",
    "weak", "rough", "tough", "terrible", "stall", "stalled",
    "stalls", "timeout", "timeouts", "sloppy", "worse", "nope",
)

# "Time's up" is a phrase, not a word, so it needs its own pattern.
_PHRASES: tuple[str, ...] = ("time's up", "times up")

_WORD_RE = {w: re.compile(r"\b" + re.escape(w) + r"\b", re.I)
            for w in BANNED}
# "too" only counts when a word follows it: "too slow" is out,
# "lighter is fine too." is in.
_TOO_RE = re.compile(r"\btoo\s+\w", re.I)


def offending(text: str) -> list[str]:
    """Banned words found in `text`, in the order they are listed.

    Empty list means the string is safe to show a patient. Used by the
    bank's own tests and by tests/test_feedback_wording.py, which
    walks every call site that pushes text at a screen.
    """
    if not text:
        return []
    found: list[str] = []
    for word, pattern in _WORD_RE.items():
        if pattern.search(text):
            found.append(word)
    if _TOO_RE.search(text):
        found.append("too")
    low = text.lower()
    for phrase in _PHRASES:
        if phrase in low:
            found.append("time's up")
            break
    return found


# ---------------------------------------------------------------------------
# Finger names
# ---------------------------------------------------------------------------

# Lower case for mid-sentence use ("That was the ring. Middle next.").
# Lanes 0..3 are the right hand, 4..7 the left, which is the same
# ordering the detectors and the lane strips use.
FINGER_WORDS: tuple[str, ...] = ("index", "middle", "ring", "little")


def finger_words(lane: int | None) -> str:
    """Finger name for a lane index, or "" when there is no lane.

    Falls back to "" rather than raising: a feedback line with a
    missing finger is a wording problem, not a reason to drop a trial.
    """
    if lane is None:
        return ""
    try:
        return FINGER_WORDS[int(lane) % 4]
    except (TypeError, ValueError):
        return ""


# ---------------------------------------------------------------------------
# The bank
# ---------------------------------------------------------------------------

SITUATIONS: tuple[str, ...] = (
    "hit", "near", "miss", "timeout", "early", "late", "wrong_finger",
    "block_end", "personal_best", "no_change", "dip",
)

# POPUP: the floating text above the lane. Short enough to read in the
# 0.9 s it lives for, which is why nothing here runs past three words.
POPUP: dict[str, tuple[str, ...]] = {
    "hit": ("Spot on", "Clean", "Got it", "Right on", "Nice one",
            "Steady", "Sharp", "That's it"),
    "near": ("Close", "Nearly", "Almost", "Just about", "Counted",
             "A touch off"),
    "miss": ("Next one", "Fresh start", "Keep going", "Onward",
             "Next", "Stay ready"),
    "timeout": ("Next cue", "Stay ready", "Coming again",
                "Hands ready", "Watch for it", "Next one"),
    "early": ("Ahead", "Wait for it", "Jumped in", "Hold on",
              "Let it come", "A touch ahead"),
    "late": ("Just after", "A touch behind", "Counted", "Landed",
             "Nearly", "Got there"),
    # The popup is 42 pt above the lane, so the finger is title case
    # here (the engine passes a capitalised {target} for the popup
    # form). Mid-sentence in a LINE it stays lower case.
    "wrong_finger": ("{target} next", "Try {target}", "{target} for this",
                     "Switch to {target}", "{target}, go",
                     "{target} this time"),
}

# LINE: the message chip under the lanes. One sentence, nine words or
# fewer, always ending on what to do next or what went well.
LINE: dict[str, tuple[str, ...]] = {
    "hit": ("Spot on, {target}.", "Clean press.", "Right on the cue.",
            "That's the one.", "Nice and steady.", "Quick and clean.",
            "{target} landed right on it.", "On the beat."),
    "near": ("Nearly on the beat. Same finger again.",
             "Close, a touch after the cue.",
             "Almost there. Keep that finger ready.",
             "Just behind the tick. You're on it.",
             "Close one. One more like that.",
             "So close. Go on the buzz next time."),
    "miss": ("That one got past. The next one's yours.",
             "Fresh start on the next cue.",
             "Keep your hands ready, next one's coming.",
             "The next press is a new go.",
             "Shake it out. Next buzz.",
             "On to the next one."),
    "timeout": ("No press that time. Stay ready for the next.",
                "That one slipped by. Hands on the pads.",
                "Next cue is coming. Rest your fingers.",
                "Wait for the buzz, then press.",
                "Ready for the next one.",
                "Nothing landed. The next one counts."),
    "early": ("A touch ahead of the cue. Wait for it.",
              "Wait for the buzz, then go.",
              "Ahead of the cue that time. Let it come.",
              "Hold until you feel it.",
              "Let the cue land first.",
              "Jumped in a little ahead. The buzz is your go."),
    "late": ("In the window, a moment after the cue.",
             "Got there. Go as soon as you feel the buzz.",
             "Landed a touch behind. Press on the buzz.",
             "That counted. Go the instant you feel it.",
             "Just after the beat. Aim for the tick.",
             "On it, a beat behind. Go on the buzz."),
    "wrong_finger": ("That was the {pressed}. {target} next.",
                     "{target} for this one.",
                     "Nearly: {target}, not {pressed}.",
                     "The cue was on the {target}.",
                     "Try the {target} for that cue.",
                     "{pressed} pressed. The buzz was on the {target}."),
    "block_end": ("Block done. {n} presses of practice.",
                  "That's the block. Good work.",
                  "Done. Every press counted.",
                  "Block finished. Rest the hand.",
                  "All done for this round.",
                  "Finished. Nice work today."),
    # Self-referenced only (R6): best so far this session, never a
    # comparison with other people and never an invented norm.
    "personal_best": ("Best so far: {value}.", "New best: {value}.",
                      "That beats your earlier best.", "Fastest yet.",
                      "Your best {stat} this session.",
                      "Top {stat} for today."),
    "no_change": ("Held steady. Same as last block.",
                  "Level with your earlier round.",
                  "Steady round. Consistency counts.",
                  "About the same as before. That's fine.",
                  "Holding your level.",
                  "Same as last time. Steady hands."),
    # The dip bank never says the round was worse than the last one.
    # It names the reason a round dips near the end of a session and
    # what to do about it, which is rest.
    "dip": ("A bit under your earlier round. Rest helps.",
            "Under your last round. Fatigue counts, rest up.",
            "Normal near the end of a session. Rest up."),
}

# Mode sub-banks. Keyed by mode, then by the mode's own situation
# name, for wording no generic situation covers (a chord finger that
# came in behind the others is not the same event as a late press).
MODE_LINES: dict[str, dict[str, tuple[str, ...]]] = {
    "reaction": {
        # A press at or past lapse_ms. Keeps the number (the
        # information) and drops the verdict.
        "lapse": ("{ms} ms. Go the instant you feel it.",
                  "{ms} ms. Fingers ready, next one.",
                  "{ms} ms. Watch for the cue.",
                  "{ms} ms. On the buzz next time."),
    },
    "chords": {
        "over_force": ("Lighter is enough.",
                       "A lighter press does it.",
                       "Ease the press, keep the timing."),
        "late_chord": ("{target} landed after the others. Press together.",
                       "{target} came in behind. All at once.",
                       "Bring the {target} in with the rest."),
        "no_hold": ("{target} lifted first. Keep it down.",
                    "Keep {target} down a moment longer.",
                    "{target} let go. Keep them down together."),
        # Every entry names the finger, because the caller always has
        # one: a variant without {target} would quietly drop the one
        # piece of information the line exists to carry.
        "leak_fail": ("{target} joined in. Keep it still.",
                      "{target} moved. Rest it on the pad.",
                      "Rest the {target} on its pad."),
        "partial": ("{target} still to land.",
                    "One finger still to come: {target}.",
                    "Bring the {target} down with the rest."),
    },
    "echo": {
        # Per-item credit stays: an echo that got 2 of 5 got 2.
        "omission": ("Time. {n} of {of}.",
                     "{n} of {of}. Next echo coming.",
                     "{n} of {of} that time. Watch the next one."),
    },
    "syllables": {
        "extra_tap": ("One tap over. See the grey block.",
                      "One extra tap. Match the blocks.",
                      "Count the blocks, one tap each."),
    },
    "buzz_hunt": {
        # Titles, so upper case. The informational chips underneath
        # ("The buzz was on" / "You pressed") do the detail.
        "wrong": ("IT WAS THE {TARGET}", "{TARGET} THAT TIME",
                  "THE BUZZ LANDED ON THE {TARGET}"),
        "wrong_count": ("IT WAS {ASKED}", "{ASKED} THAT TIME",
                        "THE ANSWER WAS {ASKED}"),
        "no_response": ("THE BUZZ CAME AND WENT", "THAT ONE SLIPPED BY",
                        "NEXT BUZZ COMING"),
    },
    "force_pilot": {
        # Live corridor tags. Colour still says "outside the band";
        # the word now says which way to move.
        "lift": ("LIFT: press a little more",),
        "ease": ("EASE: let off a little",),
        "run_done": ("RUN DONE",),
    },
}

# Neutral (EEG lab) style draws one physically identical glyph per
# outcome instead of words: same size, same position, same colour,
# same lifetime, so nothing about the FEEDBACK differs between
# outcomes except the fill. Emotional words produce an ERP of their
# own in the 200 to 300 ms window (the early posterior negativity,
# Kissler et al 2007, Biol Psychol), which is the same window the
# feedback-related negativity lives in.
NEUTRAL_GLYPH: dict[str, str] = {
    "hit": "full",
    "near": "half",
    "late": "half",
    "early": "half",
    "miss": "open",
    "timeout": "open",
    "wrong_finger": "open",
}

GLYPHS: tuple[str, ...] = ("full", "half", "open")

STYLES: tuple[str, ...] = ("encouraging", "neutral")

# Bounds on the neutral-style feedback delay. Under 500 ms the glyph
# lands inside the response-locked window the FRN is measured in;
# past 5 s the participant has stopped attending. Enforced at config
# load so a mis-set lab file fails at launch, not mid-block.
NEUTRAL_DELAY_MIN_MS = 500
NEUTRAL_DELAY_MAX_MS = 5000


# ---------------------------------------------------------------------------
# Drawing a phrase
# ---------------------------------------------------------------------------

class PhraseDeck:
    """Shuffle bag per (situation, form), so wording never repeats
    back to back and every variant is seen before any is seen twice.

    A plain random.choice gives "Next one" three trials running about
    one time in thirty-six, which reads as the app not noticing. The
    bag empties before it refills, and the first draw of a fresh bag
    is redrawn if it matches the last draw of the old one.
    """

    def __init__(self) -> None:
        self._bags: dict[tuple[str, str], list[str]] = {}
        self._last: dict[tuple[str, str], str] = {}

    @staticmethod
    def _pool(situation: str, form: str,
              mode: str | None) -> tuple[str, ...]:
        if mode:
            sub = MODE_LINES.get(mode, {})
            if situation in sub:
                return sub[situation]
        table = POPUP if form == "popup" else LINE
        return table.get(situation, ())

    def draw(self, situation: str, form: str = "line",
             rng: random.Random | None = None,
             mode: str | None = None) -> str:
        """One phrase for `situation`. `form` is "popup" or "line".

        `mode` looks in that mode's sub-bank first, so chords can ask
        for "no_hold" and reaction for "lapse" through the same call.
        Returns "" when a situation has no entries, which lets a
        caller fall back to its own text rather than crash a block.
        """
        pool = self._pool(situation, form, mode)
        if not pool:
            return ""
        key = (f"{mode}.{situation}" if mode else situation, form)
        rng = rng or random
        bag = self._bags.get(key)
        if not bag:
            bag = list(pool)
            rng.shuffle(bag)
            last = self._last.get(key)
            # Fresh bag whose first card equals the card just played:
            # swap it with the next one so no phrase repeats across
            # the reshuffle boundary either.
            if last is not None and len(bag) > 1 and bag[-1] == last:
                bag[-1], bag[-2] = bag[-2], bag[-1]
            self._bags[key] = bag
        # pop() from the end, which is why the "first card" check
        # above looks at bag[-1].
        phrase = bag.pop()
        self._last[key] = phrase
        return phrase


class _StrictFormatter(Formatter):
    """Formatter that refuses an unknown placeholder.

    A silent miss puts a literal "{target}" on the screen, which is
    worse than a caught exception in a test.
    """

    def get_value(self, key, args, kwargs):  # type: ignore[override]
        if isinstance(key, str) and key not in kwargs:
            raise KeyError(key)
        return super().get_value(key, args, kwargs)


_FORMATTER = _StrictFormatter()


def render(template: str, **slots) -> str:
    """Fill a template's placeholders. Raises KeyError on a missing
    one so no "{target}" ever reaches a patient."""
    if not template:
        return ""
    return _FORMATTER.vformat(template, (), slots)


def phrase(deck: PhraseDeck, situation: str, form: str = "line",
           rng: random.Random | None = None,
           mode: str | None = None, **slots) -> str:
    """Draw and render in one call. Returns "" when the bank has
    nothing for the situation."""
    template = deck.draw(situation, form, rng, mode)
    if not template:
        return ""
    return render(template, **slots)


# Fallback deck for callers whose engine is a test double. Keeping one
# module-level deck means a stubbed run still gets varied wording and
# still never repeats a line back to back.
_FALLBACK_DECK = PhraseDeck()


def phrase_via(engine, situation: str, form: str = "line",
               mode: str | None = None, **slots) -> str:
    """A phrase from the engine's own seeded deck when there is one.

    Modes call this rather than reaching into the engine directly. A
    MagicMock engine answers `feedback_phrase` with another mock, so
    anything that is not a real string falls through to the module
    deck instead of putting a mock's repr on the screen.
    """
    fn = getattr(engine, "feedback_phrase", None)
    if fn is not None:
        try:
            text = fn(situation, form, mode, **slots)
        except TypeError:
            text = None
        if isinstance(text, str) and text:
            return text
    return phrase(_FALLBACK_DECK, situation, form, None, mode, **slots)


# ---------------------------------------------------------------------------
# Label to situation
# ---------------------------------------------------------------------------

def situation_for(label: str, *, pressed: bool = True,
                  incorrect: bool = False,
                  rt_ms: float | None = None,
                  mode: str = "") -> str:
    """Map a scoring label plus the trial's shape onto a situation.

    The label alone cannot tell the three kinds of "Miss" apart, and
    they need three different things said to them: a wrong finger
    needs the right finger named, a timeout needs "stay ready", and a
    press outside the window needs "next one". `pressed` is whether
    anything was pressed at all; `incorrect` is whether a
    not-cued finger was pressed.
    """
    if label in ("Perfect", "Great", "Good"):
        # A rhythm "Good" well off the centre of its window reads as
        # a near, not a clean hit. rt_ms carries the signed offset
        # for rhythm, so the caller decides by passing it.
        if mode == "rhythm" and rt_ms is not None and abs(rt_ms) > 120.0:
            return "near"
        return "hit"
    if label == "Late":
        return "late"
    if label == "Early":
        return "early"
    if label == "Miss":
        if incorrect:
            return "wrong_finger"
        if not pressed:
            return "timeout"
        return "miss"
    # CatchOk and anything a future mode adds: treat as a hit, which
    # is warm and true (a catch trial survived is a good outcome).
    return "hit"


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

def style(cfg) -> str:
    """"encouraging" (default) or "neutral" (the EEG lab)."""
    value = str(cfg.get("ui.feedback_style", "encouraging") or
                "encouraging").strip().lower()
    if value not in STYLES:
        return "encouraging"
    return value


def delay_ms(cfg) -> int:
    """Milliseconds between the response and the feedback glyph.

    0 in encouraging style, which is today's behaviour exactly.
    """
    try:
        return max(0, int(cfg.get("ui.feedback_delay_ms", 0) or 0))
    except (TypeError, ValueError):
        return 0


def check_style_config(cfg) -> None:
    """Refuse a lab config that would record unusable feedback ERPs.

    Raises ValueError at load, naming the bound, so an RA finds out at
    launch rather than after a session of data.
    """
    value = str(cfg.get("ui.feedback_style", "encouraging") or
                "encouraging").strip().lower()
    if value not in STYLES:
        raise ValueError(
            f"ui.feedback_style must be one of {STYLES}, got {value!r}")
    if value != "neutral":
        return
    raw = cfg.get("ui.feedback_delay_ms", 0)
    try:
        delay = int(raw or 0)
    except (TypeError, ValueError):
        raise ValueError(
            "ui.feedback_delay_ms must be a whole number of "
            f"milliseconds, got {raw!r}") from None
    if not (NEUTRAL_DELAY_MIN_MS <= delay <= NEUTRAL_DELAY_MAX_MS):
        raise ValueError(
            "ui.feedback_style: neutral needs ui.feedback_delay_ms "
            f"between {NEUTRAL_DELAY_MIN_MS} and {NEUTRAL_DELAY_MAX_MS} "
            f"ms (feedback inside 500 ms lands in the response-locked "
            f"window); got {delay}")
