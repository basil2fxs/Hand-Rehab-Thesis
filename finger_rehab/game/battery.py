"""The study battery: a named protocol preset turned into a plan.

A preset (config protocol.presets.<name>) says which blocks run in
which order for which counterbalancing cell, which hand each block
uses, and which config keys change for the length of the run. This
module turns that into a concrete plan for one participant: the cell
from the code, the hands resolved against the dominant hand entered
at login, the overrides as a nested dict the engine lays over its
config, plus the snapshot needed to put the config back afterwards.

Pure functions over dicts so the plan can be tested without a screen
and the engine's part stays small: start, continue, finish. The
design the shipped preset implements is docs/research/
healthy_baseline_study.txt, Sections 2.2 to 2.4.
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
# three (ModeSelectScreen.NEEDS_HARDWARE reads this constant).
HARDWARE_MODES = frozenset({"force_pilot", "lighthouse", "buzz_hunt"})

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


class BatteryError(ValueError):
    """The preset cannot be turned into a plan for this participant.
    The message is written for the hub's note line."""


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
        raise BatteryError("Battery needs the dominant hand set at login")
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
        steps.append(BatteryStep(
            mode=mode,
            hand=hand,
            hand_requested=requested,
            phase=str(entry.get("phase") or "battery").strip().lower(),
            stretch_before_s=(stretch_s if entry.get("stretch_before")
                              else 0.0),
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


def unplayable_reason(step: BatteryStep, source, one_board: bool) -> str:
    """Why this rig cannot run the step, or an empty string."""
    no_hardware = not getattr(source, "provides_samples", True)
    if no_hardware and step.mode in HARDWARE_MODES:
        return "needs sensor hardware"
    if step.hand == "both" and one_board:
        return "needs a second board"
    return ""
