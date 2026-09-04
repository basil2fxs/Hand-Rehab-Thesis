"""The study battery: a named protocol preset turned into a plan.

A preset (config protocol.presets.<name>) says which blocks run in
which order for which counterbalancing cell, which hand each block
uses, and which config keys change for the length of the run. This
module turns that into a concrete plan for one participant: the cell
from the code, the hands resolved against the dominant hand entered
at login, the overrides as a nested dict the engine lays over its
config, plus the snapshot needed to put the config back afterwards.

Pure functions over dicts so the plan can be tested without a screen
and the engine's part stays small: start, continue, finish.

The design the shipped preset implements is ONE PASS in one sitting:
eleven blocks, ten modes, every mode played once. Data Collection
Plan.md of 4 September 2026, and the amendment at the top of
docs/research/healthy_baseline_study.txt. Section 1 of that document,
what each mode measures, still carries the design; its Sections 2, 4
Sections 2 to 5 describe this one-pass design.
module knows about passes or phases beyond copying the preset's phase
word onto the step, so a design change is a config edit, not a code
change.
"""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path

from ..data.intake import cell_for, normalise_code


# Modes whose every stage needs a real force signal or the motors.
# On a keyboard-only source they refuse at their first tick, so a
# battery skips them up front and says so, rather than opening a
# block that can only be abandoned. The hub's cards badge the same
# two (ModeSelectScreen.NEEDS_HARDWARE reads this constant).
HARDWARE_MODES = frozenset({"force_pilot", "buzz_hunt"})

HAND_WORDS = ("hand1", "hand2", "dominant", "non_dominant",
              "both", "left", "right")

DEFAULT_PRESET = "study_battery"


@dataclass
class BatteryStep:
    mode: str
    hand: str                   # left / right / both, resolved
    hand_requested: str         # what the preset said (hand1, dominant...)
    phase: str = "battery"
    stretch_before_s: float = 0.0
    # A scheduled rest before this step. rest_before_s is how long the
    # card counts down; rest_min_s is the floor the Start button holds
    # for. Both zero on a step with no rest. Kept apart from the
    # stretch because the two behave differently on the card: a
    # stretch is a suggestion, a rest is enforced to its floor.
    rest_before_s: float = 0.0
    rest_min_s: float = 0.0
    track: str | None = None    # rhythm only: file name in the music dir
    difficulty: str | None = None
    position: int = 0           # 1-based, set by build_plan

    @property
    def label(self) -> str:
        """Human line for a card: mode, hand, and why that hand."""
        hand = {"left": "left hand", "right": "right hand",
                "both": "both hands"}.get(self.hand, self.hand)
        if self.hand_requested in ("hand1", "hand2", "dominant",
                                   "non_dominant"):
            role = self.hand_requested.replace("_", "-")
            if self.hand_requested.startswith("hand"):
                role = f"hand {self.hand_requested[-1]}"
            return f"{self.mode}, {hand} ({role})"
        return f"{self.mode}, {hand}"


@dataclass
class BatteryPlan:
    id: str
    preset: str
    cell: dict
    dominant_hand: str
    steps: list[BatteryStep]
    overrides: dict = field(default_factory=dict)
    budget_min: float = 0.0
    stretch_s: float = 0.0
    rest_s: float = 0.0
    rest_min_s: float = 0.0
    # Where the run sheet stops the session. 0 means "no hard stop",
    # which is what a preset without the key gets.
    hard_stop_min: float = 0.0


class BatteryError(ValueError):
    """The preset cannot be turned into a plan for this participant.
    The message is written for the hub's note line, under the PLAY ALL
    button (the hub's name for the battery)."""


def load_preset(cfg, preset: str = DEFAULT_PRESET) -> dict | None:
    """The raw preset mapping, or None when the config has none."""
    node = cfg.get(f"protocol.presets.{preset}")
    return node if isinstance(node, dict) else None


def other_hand(hand: str) -> str:
    return "left" if str(hand).lower() == "right" else "right"


def resolve_hand(requested: str, dominant_hand: str,
                 hand_first: str) -> str:
    """Turn a preset hand word into left / right / both.

    hand1 is the counterbalanced first hand (dominant or non-dominant
    per the cell), hand2 the other; dominant and non_dominant read
    against the login's dominant hand; both, left and right are
    literal.
    """
    word = str(requested or "").strip().lower()
    dom = str(dominant_hand or "").strip().lower()
    if word in ("both", "left", "right"):
        return word
    if dom not in ("left", "right"):
        # Worded for the hub's note line, in the login screen's words.
        raise BatteryError("Play all needs a main hand: pick one at login")
    first = dom if hand_first == "dominant" else other_hand(dom)
    if word == "hand1":
        return first
    if word == "hand2":
        return other_hand(first)
    if word == "dominant":
        return dom
    if word == "non_dominant":
        return other_hand(dom)
    raise BatteryError(f"Battery step has an unknown hand '{requested}'")


def build_plan(cfg, participant: str, dominant_hand: str,
               preset: str = DEFAULT_PRESET) -> BatteryPlan:
    """The concrete plan for one participant.

    The cell comes from the code (data/intake.cell_for), then the
    preset's cells table says which order runs and which hand goes
    first. The hands in every step are resolved here, once, so the
    engine and the screens never have to know what hand1 meant.
    """
    raw = load_preset(cfg, preset)
    if raw is None:
        raise BatteryError(f"No protocol preset named '{preset}'")
    who = normalise_code(participant)
    cell = cell_for(who)
    cells = raw.get("cells") or {}
    # YAML keys arrive as ints; be tolerant of strings too.
    cell_cfg = None
    for key, val in cells.items():
        try:
            if int(key) == cell["index"] and isinstance(val, dict):
                cell_cfg = val
                break
        except (TypeError, ValueError):
            continue
    if cell_cfg is None:
        raise BatteryError(f"Preset '{preset}' has no cell for code "
                           f"index {cell['index']}")
    order_key = str(cell_cfg.get("order") or cell["mode_order"])
    hand_first = str(cell_cfg.get("hand1") or cell["hand_first"])
    orders = raw.get("orders") or {}
    order = orders.get(order_key)
    if not isinstance(order, list) or not order:
        raise BatteryError(f"Preset '{preset}' has no order '{order_key}'")
    cell = dict(cell, mode_order=order_key, hand_first=hand_first)
    stretch_s = float(raw.get("stretch_s", 0.0) or 0.0)
    rest_s = float(raw.get("rest_s", 0.0) or 0.0)
    rest_min_s = min(float(raw.get("rest_min_s", 0.0) or 0.0), rest_s)
    steps: list[BatteryStep] = []
    for entry in order:
        if not isinstance(entry, dict):
            continue
        mode = str(entry.get("mode") or "").strip().lower()
        if not mode:
            continue
        requested = str(entry.get("hand") or "both").strip().lower()
        hand = resolve_hand(requested, dominant_hand, hand_first)
        if mode == "mirror":
            # Bilateral by definition, whatever the preset says.
            hand = "both"
        # A rest and a stretch before the same step would show two
        # countdowns on one card; the rest is the enforced one, so it
        # wins and the stretch is dropped.
        rest_before = bool(entry.get("rest_before")) and rest_s > 0
        steps.append(BatteryStep(
            mode=mode,
            hand=hand,
            hand_requested=requested,
            phase=str(entry.get("phase") or "battery").strip().lower(),
            stretch_before_s=(stretch_s if entry.get("stretch_before")
                              and not rest_before else 0.0),
            rest_before_s=(rest_s if rest_before else 0.0),
            rest_min_s=(rest_min_s if rest_before else 0.0),
            track=(str(entry["track"]) if entry.get("track") else None),
            difficulty=(str(entry["difficulty"])
                        if entry.get("difficulty") else None),
            position=len(steps) + 1,
        ))
    if not steps:
        raise BatteryError(f"Preset '{preset}' order '{order_key}' is empty")
    overrides = raw.get("overrides") or {}
    if not isinstance(overrides, dict):
        overrides = {}
    return BatteryPlan(
        id=str(raw.get("id") or preset),
        preset=preset,
        cell=cell,
        dominant_hand=str(dominant_hand).strip().lower(),
        steps=steps,
        overrides=copy.deepcopy(overrides),
        budget_min=float(raw.get("budget_min", 0.0) or 0.0),
        stretch_s=stretch_s,
        rest_s=rest_s,
        rest_min_s=rest_min_s,
        hard_stop_min=float(raw.get("hard_stop_min", 0.0) or 0.0),
    )


# Sentinel for a key the config did not have before the override, so
# the restore removes it rather than writing None into it.
_ABSENT = object()


def _flatten(node: dict, prefix: str = "") -> dict[str, object]:
    out: dict[str, object] = {}
    for k, v in node.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict) and v:
            out.update(_flatten(v, key + "."))
        else:
            out[key] = v
    return out


def apply_overrides(data: dict, overrides: dict) -> dict:
    """Lay `overrides` over the live config dict in place and return
    the snapshot restore_overrides needs to undo it.

    Leaf by leaf on purpose: a nested override of reaction.block_trials
    must not replace the whole reaction section, or every key the
    preset did not mention would vanish for the length of the run.
    """
    snapshot: dict[str, object] = {}
    for dotted, value in _flatten(overrides).items():
        parts = dotted.split(".")
        node = data
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                node[part] = {}
            node = node[part]
        leaf = parts[-1]
        snapshot[dotted] = (copy.deepcopy(node[leaf]) if leaf in node
                            else _ABSENT)
        node[leaf] = copy.deepcopy(value)
    return snapshot


def restore_overrides(data: dict, snapshot: dict) -> None:
    """Put back what apply_overrides changed. Keys that did not exist
    before are removed again."""
    for dotted, prev in snapshot.items():
        parts = dotted.split(".")
        node = data
        ok = True
        for part in parts[:-1]:
            if not isinstance(node.get(part), dict):
                ok = False
                break
            node = node[part]
        if not ok:
            continue
        leaf = parts[-1]
        if prev is _ABSENT:
            node.pop(leaf, None)
        else:
            node[leaf] = prev


def find_track(cfg, name: str | None) -> Path | None:
    """The pinned rhythm track inside audio.music_dir, or None when it
    is not there (the engine then falls back to the song screen)."""
    if not name:
        return None
    try:
        music_dir = cfg.resolve_path(cfg.get("audio.music_dir",
                                             "assets/music"))
    except Exception:
        return None
    cand = Path(music_dir) / name
    if cand.is_file():
        return cand
    # Case-insensitive fallback: a track renamed Easy_lemon.mp3 on a
    # study laptop should still be found.
    try:
        for p in Path(music_dir).iterdir():
            if p.name.lower() == str(name).lower() and p.is_file():
                return p
    except OSError:
        pass
    return None


# ---------------------------------------------------------------------
# Session so far: first go against latest go, per mode and hand
# ---------------------------------------------------------------------
# One comparison, made the same way everywhere: the mode's own
# headline number from the FIRST completed block of the session
# against the LATEST one, on the same hand, with the direction and the
# wording the vs-last-time chip already uses (data/history). Nothing
# here reads the disk: the session log the engine keeps is this
# session and only this session, so "your first go today" cannot
# quietly become a block from a week ago.
#
# Under the one-pass battery this has less to say than it used to.
# Every mode and hand is played exactly once, so inside the battery
# every row comes back n = 1 with no comparison, and the SO FAR strip
# stays empty until somebody replays a mode freely from the hub. That
# is the honest reading of one pass: there is no second block to
# compare against. Showing a participant their own improvement inside
# a single block would need a first-trials-against-last-trials split
# written into each mode's block summary, which no mode writes today
# (only pattern's per_take is ordered), so the within-block story
# currently lives in the analysis notebook and not on this screen.
#
# The wording tails in data/history end in "than last time" / "on last
# time" because that chip compares across sessions. Inside one sitting
# the honest tail is "than your first go", and the strip wants the
# words with no tail at all, so both are made from the one string
# rather than from a second table that could drift out of step.
_HISTORY_TAILS = (" than last time", " on last time")

# What the screen says when a mode moved by less than its display
# precision. Not "no change": the number moved, it just did not move
# enough to print, and calling that an improvement would be a lie.
SAME_SHORT = "about the same"
SAME_TEXT = "about the same as your first go"


# How each mode's comparable number is printed on the progress panel.
# data/history knows the direction and the wording; it does not print
# the value itself, so the unit lives here. Kept as a table rather
# than guessed from the number, because a fraction (0.89 steady) and a
# count (span 7) are both small and would print identically. A test
# pins this table's keys against history's rule table so a mode cannot
# gain a chip and lose its unit.
PROGRESS_UNITS = {
    "classic": "percent",
    "adaptive": "bpm",
    "mirror": "ms",
    "reaction": "ms",
    "pattern": "percent",
    "chords": "percent",
    "syllables": "percent",
    "force_pilot": "percent",
    "buzz_hunt": "percent",
    "echo": "count",
    "rhythm": "ms",
}


def value_text(mode: str, value) -> str:
    """One of this mode's numbers, in the units the screen shows."""
    if value is None:
        return ""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    unit = PROGRESS_UNITS.get(str(mode), "count")
    if unit == "percent":
        return f"{v * 100:.0f}%"
    if unit == "ms":
        return f"{v:.0f} ms"
    if unit == "bpm":
        return f"{v:.0f} BPM"
    return f"{v:.0f}"


def _retail(text: str, tail: str) -> str:
    for old in _HISTORY_TAILS:
        if text.endswith(old):
            return text[: -len(old)] + tail
    return text


def progress_rows(log_rows) -> list[dict]:
    """Per mode and hand, this session's first completed block against
    its latest one, in the order the modes were first played.

    Takes the engine's session log (session_games_log), so it is pure
    and testable without a screen or a sessions tree. Rows the chip
    cannot speak about (a mode with no comparable number, an abandoned
    block, a first-and-only go) still appear with n and the values, so
    a caller can show "played once" rather than dropping the mode.
    """
    from ..data import history
    runs: dict[tuple[str, str], list[dict]] = {}
    order: list[tuple[str, str]] = []
    for row in log_rows or []:
        if not isinstance(row, dict) or row.get("status") != "completed":
            continue
        mode = str(row.get("mode") or "")
        hand = str(row.get("hand") or "")
        summary = row.get("summary")
        if not mode or not isinstance(summary, dict):
            continue
        if history.comparable_value(mode, summary) is None:
            continue
        key = (mode, hand)
        if key not in runs:
            runs[key] = []
            order.append(key)
        runs[key].append(summary)
    out: list[dict] = []
    for mode, hand in order:
        blocks = runs[(mode, hand)]
        row = {
            "mode": mode,
            "hand": hand,
            "n": len(blocks),
            "first": history.comparable_value(mode, blocks[0]),
            "latest": history.comparable_value(mode, blocks[-1]),
            "first_text": value_text(
                mode, history.comparable_value(mode, blocks[0])),
            "latest_text": value_text(
                mode, history.comparable_value(mode, blocks[-1])),
            "chip": None,
            "text": "",
            "short": "",
            "better": None,
            "delta": 0.0,
        }
        if len(blocks) >= 2:
            chip = history.chip_for(mode, blocks[-1], blocks[0])
            if chip is None:
                # chip_for returns nothing when the change rounds away
                # at display precision. That is a real answer here.
                row["text"] = SAME_TEXT
                row["short"] = SAME_SHORT
            else:
                row["chip"] = chip
                row["better"] = bool(chip.get("better"))
                row["delta"] = float(chip.get("delta") or 0.0)
                row["text"] = _retail(str(chip.get("text") or ""),
                                      " than your first go")
                row["short"] = _retail(str(chip.get("text") or ""), "")
        out.append(row)
    return out


def unplayable_reason(step: BatteryStep, source, one_board: bool) -> str:
    """Why this rig cannot run the step, or an empty string."""
    no_hardware = not getattr(source, "provides_samples", True)
    if no_hardware and step.mode in HARDWARE_MODES:
        return "needs sensor hardware"
    if step.hand == "both" and one_board:
        return "needs a second board"
    return ""
