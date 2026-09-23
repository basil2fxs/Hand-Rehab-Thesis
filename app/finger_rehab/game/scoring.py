"""Trial scoring. Thresholds preserved from Satoru's 2025 schema so historical
sessions stay comparable."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ScoreConfig:
    # Perfect: very fast RT, sub-100 ms by default. Carries the biggest
    # reward so the patient feels a clear hit when they nail a press.
    # Earlier versions only had Great/Good/Late and the spread (3/2/1)
    # was too compressed to feel different - a Late hit gave a third
    # of a Great, which on a single trial doesn't read.
    perfect_ms: int = 100
    perfect_points: int = 10
    great_ms: int = 200
    great_points: int = 6
    good_ms: int = 500
    good_points: int = 3
    late_points: int = 1
    # Misses + early presses default to 0 - the score never goes backwards.
    # The miss still shows up in the Misses counter for the therapist's
    # records, just doesn't drag the score down.
    miss_points: int = 0
    early_penalty: int = 0


@dataclass(frozen=True)
class TrialResult:
    """Outcome of one classified trial.

    Returned by `classify()` (cadence modes) and built by the rhythm
    pipeline from `classify_offset()`. Frozen so the engine can stash
    it in summary dicts without worrying about later mutation.
    """
    # Tier name shown on screen and written to the trial CSV. One of
    # "Perfect" (sub-100 ms), "Great" (sub-200 ms), "Good" (sub-500 ms),
    # "Late" (slower hit), "Miss" (timeout, no press), "Early"
    # (press before stim).
    label: str
    # Score points awarded for this trial. Sourced from `ScoreConfig`
    # so a therapist re-weighting the scheme propagates through.
    points: int
    # Reaction time in milliseconds for a hit. None for Miss / Early
    # so downstream stats (mean RT, RT std) can filter out non-hits
    # cleanly with a None check.
    rt_ms: float | None


def classify(rt_ms: float | None, cfg: ScoreConfig) -> TrialResult:
    if rt_ms is None:
        return TrialResult(label="Miss", points=cfg.miss_points, rt_ms=None)
    # Perfect tier check goes FIRST: a 50 ms RT is also under the Great
    # threshold, but the patient should feel rewarded for the very fast
    # press they actually achieved, not the slower-tier label.
    if rt_ms <= cfg.perfect_ms:
        return TrialResult(label="Perfect", points=cfg.perfect_points, rt_ms=rt_ms)
    if rt_ms <= cfg.great_ms:
        return TrialResult(label="Great", points=cfg.great_points, rt_ms=rt_ms)
    if rt_ms <= cfg.good_ms:
        return TrialResult(label="Good", points=cfg.good_points, rt_ms=rt_ms)
    return TrialResult(label="Late", points=cfg.late_points, rt_ms=rt_ms)


def early_penalty(cfg: ScoreConfig) -> TrialResult:
    return TrialResult(label="Early", points=cfg.early_penalty, rt_ms=None)


@dataclass(frozen=True)
class RhythmWindows:
    perfect_ms: float = 50.0
    great_ms: float = 100.0
    good_ms: float = 175.0
    miss_ms: float = 300.0


def classify_offset(offset_ms: float, w: RhythmWindows,
                    cfg: ScoreConfig | None = None) -> tuple[str, int]:
    """Rhythm-mode scoring. Honours cfg point values so a therapist who
    changes scoring sees the change in both modes."""
    abs_off = abs(offset_ms)
    # Default to 0 for misses (no negative scoring anywhere). cfg can
    # still override if a therapist sets a non-zero miss penalty.
    # Defaults here mirror ScoreConfig so a caller without a cfg gets
    # the same wider spread (10/6/3/1) as a fully-configured engine.
    miss_pts = cfg.miss_points if cfg else 0
    late_pts = cfg.late_points if cfg else 1
    good_pts = cfg.good_points if cfg else 3
    great_pts = cfg.great_points if cfg else 6
    perfect_pts = cfg.perfect_points if cfg else 10
    if abs_off <= w.perfect_ms:
        return "Perfect", perfect_pts
    if abs_off <= w.great_ms:
        return "Great", great_pts
    if abs_off <= w.good_ms:
        return "Good", good_pts
    if abs_off <= w.miss_ms:
        return "Late" if offset_ms > 0 else "Early", late_pts
    return "Miss", miss_pts
