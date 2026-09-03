"""Vs-last-time lookup: this game against the participant's previous one.

The results screen shows one small chip next to the headline number
("12 ms faster than last time"). Everything behind that chip lives
here so the maths is testable without a screen: which prior game
counts as "last time", which number each mode is compared on, and
which direction of change is an improvement.

The lookup reads the same sessions tree the analysis notebook
catalogues, with the same conventions: the participant and hand come
from metadata.json's top level, the mode and status from its
block_summary. Only status "completed" counts; an abandoned game is
not a result to be measured against. "Same game" means same
participant AND same mode AND same hand mode, because a right-hand
reaction block against a bilateral one compares different tasks.

Direction is per mode and deliberate: reaction time and the mirror
sync gap improve DOWN, accuracy-flavoured numbers improve UP, and
rhythm is compared on the mean absolute beat offset (a signed mean
would let early and late presses cancel into a fake improvement).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path


log = logging.getLogger(__name__)


def _num(v) -> float | None:
    try:
        if v is None:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def _pattern_accuracy(summary: dict) -> float | None:
    """Overall press accuracy across the block's real takes, the same
    quantity the results screen's ACCURACY card shows: warmup takes
    excluded, each take weighted by its press count."""
    pat = summary.get("pattern")
    if not isinstance(pat, dict):
        return None
    n_correct = 0
    n_total = 0
    for take in pat.get("per_take") or []:
        if not isinstance(take, dict) or take.get("kind") == "warmup":
            continue
        acc = _num(take.get("accuracy"))
        n = _num(take.get("n"))
        if acc is None or n is None or n <= 0:
            continue
        n_correct += int(round(acc * n))
        n_total += int(n)
    if n_total <= 0:
        return None
    return n_correct / n_total


def _chords_clean_rate(summary: dict) -> float | None:
    """Clean-chord rate out of every within-scope chord outcome, the
    results screen's CLEAN HIT RATE."""
    ch = summary.get("chords")
    if not isinstance(ch, dict):
        return None
    classes = (ch.get("chord_outcome_classes")
               or ch.get("outcome_classes") or {})
    if not isinstance(classes, dict):
        return None
    try:
        n_all = sum(int(v) for v in classes.values())
    except (TypeError, ValueError):
        return None
    if n_all <= 0:
        return None
    return int(classes.get("hit", 0)) / n_all


def comparable_value(mode: str, summary: dict) -> float | None:
    """The one number a game of `mode` is compared on, pulled from its
    block_summary, or None when the block did not produce it."""
    if not isinstance(summary, dict):
        return None
    mode = str(mode)
    if mode == "classic":
        return _num(summary.get("hit_rate"))
    if mode == "adaptive":
        return _num(summary.get("bpm_max"))
    if mode == "mirror":
        return _num((summary.get("mirror") or {}).get("mean_gap_ms"))
    if mode == "reaction":
        return _num((summary.get("reaction") or {}).get("median_rt_ms"))
    if mode == "pattern":
        return _pattern_accuracy(summary)
    if mode == "chords":
        return _chords_clean_rate(summary)
    if mode == "syllables":
        return _num((summary.get("syllables") or {}).get("accuracy"))
    if mode == "force_pilot":
        return _num(((summary.get("force_pilot") or {})
                     .get("overall") or {}).get("time_in_corridor"))
    if mode == "buzz_hunt":
        return _num(((summary.get("buzz_hunt") or {})
                     .get("loc") or {}).get("accuracy"))
    if mode == "echo":
        # The span headline, but never across the ladder / cumulative
        # divide: a cumulative (classic Simon) block rehearses every
        # prefix and its span is inflated by design, so comparing one
        # against a ladder block would report the game rule change as
        # patient change.
        ec = summary.get("echo") or {}
        if not isinstance(ec, dict) or ec.get("cumulative"):
            return None
        return _num(ec.get("span"))
    if mode == "rhythm":
        return _num((summary.get("beat_offset_stats") or {})
                    .get("beat_offset_abs_mean_ms"))
    return None


# mode -> (lower_is_better, to display units, decimals,
#          better wording, worse wording). {d} is the magnitude of the
# change in display units.
_ACC = ("{d}% more accurate than last time",
        "{d}% less accurate than last time")
_RULES: dict[str, tuple[bool, float, int, str, str]] = {
    "classic": (False, 100.0, 0, *_ACC),
    "adaptive": (False, 1.0, 0,
                 "{d} BPM faster pace than last time",
                 "{d} BPM slower pace than last time"),
    "mirror": (True, 1.0, 0,
               "{d} ms tighter sync than last time",
               "{d} ms looser sync than last time"),
    "reaction": (True, 1.0, 0,
                 "{d} ms faster than last time",
                 "{d} ms slower than last time"),
    "pattern": (False, 100.0, 0, *_ACC),
    "chords": (False, 100.0, 0,
               "{d}% more clean hits than last time",
               "{d}% fewer clean hits than last time"),
    "syllables": (False, 100.0, 0, *_ACC),
    "force_pilot": (False, 100.0, 0,
                    "{d}% steadier than last time",
                    "{d}% less steady than last time"),
    "buzz_hunt": (False, 100.0, 0, *_ACC),
    "echo": (False, 1.0, 0,
             "longest echo up {d} on last time",
             "longest echo down {d} on last time"),
    "rhythm": (True, 1.0, 0,
               "{d} ms tighter timing than last time",
               "{d} ms looser timing than last time"),
}


def chip_for(mode: str, current: dict, previous: dict) -> dict | None:
    """The chip data for this game against the previous one, or None
    when there is nothing honest to say (either side lacks the number,
    or the change rounds away to zero at display precision).

    Returns {"text", "better", "delta"} where delta is signed in the
    mode's display units and better already accounts for the mode's
    direction.
    """
    rule = _RULES.get(str(mode))
    if rule is None:
        return None
    lower_better, scale, decimals, up_text, down_text = rule
    cur = comparable_value(mode, current)
    prev = comparable_value(mode, previous)
    if cur is None or prev is None:
        return None
    delta = (cur - prev) * scale
    magnitude = round(abs(delta), decimals)
    if magnitude == 0:
        # "0 ms faster" is noise, not feedback.
        return None
    better = (delta < 0) if lower_better else (delta > 0)
    d_str = (f"{magnitude:.{decimals}f}" if decimals
             else f"{int(magnitude)}")
    text = (up_text if better else down_text).format(d=d_str)
    return {"text": text, "better": better, "delta": round(delta, 3)}


def previous_block_summary(data_dir: Path | str, participant: str,
                           mode: str, hand: str,
                           exclude_root: Path | str | None = None
                           ) -> dict | None:
    """The newest completed block_summary in the sessions tree for the
    same participant, mode and hand, or None on a first play.

    `exclude_root` is the current game's own session folder, which is
    already on disk (metadata is saved at block start) and must never
    be its own history. Ordering uses metadata's finished_at ISO
    string (started_at as fallback), which sorts lexicographically.
    Unreadable or half-written metadata files are skipped: this feeds
    a results-screen chip, not an analysis, so a broken folder should
    cost a log line at most.
    """
    root = Path(data_dir)
    if not root.exists():
        return None
    exclude = Path(exclude_root).resolve() if exclude_root else None
    best: dict | None = None
    best_key = ""
    for meta_path in root.rglob("metadata.json"):
        if exclude is not None and meta_path.parent.resolve() == exclude:
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if not isinstance(meta, dict):
            continue
        summary = meta.get("block_summary")
        if not isinstance(summary, dict):
            continue
        if summary.get("status") != "completed":
            continue
        if str(meta.get("participant") or "") != str(participant):
            continue
        if str(summary.get("block") or "") != str(mode):
            continue
        if str(meta.get("hand") or "") != str(hand):
            continue
        key = (str(meta.get("finished_at") or "")
               or str(meta.get("started_at") or ""))
        if best is None or key > best_key:
            best = summary
            best_key = key
    return best
