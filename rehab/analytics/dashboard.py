"""Read persisted session.json files and roll them up for the L/R
dashboard. Pure functions: scan a folder, parse the JSON, derive
per-hand aggregates from the block_summary.per_lane data. UI is in
rehab/ui/screens.py LRDashboardScreen.

What the therapist gets from this is the answer to a thesis-relevant
question: is the affected hand catching up to the unaffected one
across sessions? The asymmetry-index trend over time is the headline
chart; per-hand hit rate / RT / peak force pairs back it up.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path


log = logging.getLogger(__name__)


@dataclass
class HandSummary:
    """One hand's aggregate from a single block's per_lane table."""
    hit_rate: float | None = None
    rt_mean_ms: float | None = None
    peak_force_mean: float | None = None
    n_trials: int = 0


@dataclass
class SessionRow:
    """One row in the dashboard's session-trend table.
    Sorted oldest-first when the loader emits a list."""
    path: Path
    participant: str
    started_at: str
    block: str            # "classic" / "adaptive" / "rhythm" / "mirror"
    hand_mode: str
    right: HandSummary = field(default_factory=HandSummary)
    left: HandSummary = field(default_factory=HandSummary)
    # Asymmetry index (peak_force) from the block_summary if it was
    # computed at finish_block. None for unilateral sessions or for
    # blocks that didn't make it through finish_block (abandoned).
    asymmetry_index_force: float | None = None
    asymmetry_index_rt: float | None = None
    # Force unit ('N' if a calibration constant was set during
    # capture, 'counts' otherwise). The dashboard surfaces this in
    # the axis label so a researcher mixing calibrated and
    # uncalibrated sessions doesn't get confused.
    force_unit: str = "counts"


def _aggregate_hand(per_lane: dict, lane_range: range) -> HandSummary:
    """Pool the per_lane rows for one hand into a single summary.

    Mean is sample-weighted by n_trials so a lane that only had two
    trials doesn't drag the hand-level mean as much as one that had
    twenty. Force / RT means come straight off the block_summary's
    per-lane fields (already computed at finish_block).
    """
    total_rt_weighted = 0.0
    total_force_weighted = 0.0
    total_hits = 0
    total_trials = 0
    n_rt_samples = 0
    n_force_samples = 0
    for lane_idx in lane_range:
        row = per_lane.get(str(lane_idx))
        if not row:
            continue
        n = int(row.get("n_trials", 0) or 0)
        if n <= 0:
            continue
        total_trials += n
        hit_rate = row.get("hit_rate")
        if hit_rate is not None:
            total_hits += hit_rate * n
        rt_mean = row.get("rt_mean_ms")
        if rt_mean is not None:
            total_rt_weighted += rt_mean * n
            n_rt_samples += n
        peak = row.get("peak_force_mean")
        if peak is not None:
            total_force_weighted += peak * n
            n_force_samples += n
    return HandSummary(
        hit_rate=(total_hits / total_trials) if total_trials > 0 else None,
        rt_mean_ms=(total_rt_weighted / n_rt_samples
                     if n_rt_samples > 0 else None),
        peak_force_mean=(total_force_weighted / n_force_samples
                          if n_force_samples > 0 else None),
        n_trials=total_trials,
    )


def parse_session_file(path: Path) -> SessionRow | None:
    """Open one session.json and roll its block_summary up into a
    SessionRow. Returns None if the file is missing / unreadable /
    malformed so a single bad file doesn't break the dashboard
    scan."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        log.warning("Could not read %s: %s", path, e)
        return None
    if not isinstance(data, dict):
        return None
    bs = data.get("block_summary") or {}
    per_lane = bs.get("per_lane") or {}
    # Right is lanes 0-3 (always the right-hand half regardless of
    # whether the session was unilateral right or bilateral). Left
    # is lanes 4-7 (only populated in bilateral sessions).
    right = _aggregate_hand(per_lane, range(0, 4))
    left = _aggregate_hand(per_lane, range(4, 8))
    asym = bs.get("asymmetry_index") or {}
    return SessionRow(
        path=path,
        participant=str(data.get("participant") or "NA"),
        started_at=str(data.get("started_at") or ""),
        block=str(bs.get("block") or ""),
        hand_mode=str(data.get("hand") or "right"),
        right=right,
        left=left,
        asymmetry_index_force=asym.get("peak_force") if asym else None,
        asymmetry_index_rt=asym.get("rt_mean") if asym else None,
        force_unit=str(bs.get("force_unit") or "counts"),
    )


def load_recent_sessions(sessions_dir: Path,
                          limit: int = 10,
                          participant: str | None = None
                          ) -> list[SessionRow]:
    """Scan sessions_dir for metadata.json files, parse the most
    recent `limit` and return them oldest-first. Optionally filter
    to a single participant so the dashboard can show one patient's
    progression without others' sessions cluttering it."""
    if not sessions_dir.exists():
        return []
    candidates: list[Path] = []
    # Sessions live in subfolders like sessions/<name>_<timestamp>/
    # with a metadata.json inside. We accept both shapes - direct
    # JSON files in sessions/, and the subfolder layout the engine
    # actually writes.
    for child in sessions_dir.iterdir():
        if child.is_file() and child.suffix.lower() == ".json":
            candidates.append(child)
        elif child.is_dir():
            md = child / "metadata.json"
            if md.exists():
                candidates.append(md)
    rows: list[SessionRow] = []
    for path in candidates:
        row = parse_session_file(path)
        if row is None:
            continue
        if participant is not None and row.participant != participant:
            continue
        rows.append(row)
    # Sort by started_at then by path as a tiebreak so duplicate
    # timestamps don't shuffle randomly between runs.
    rows.sort(key=lambda r: (r.started_at, str(r.path)))
    if limit > 0 and len(rows) > limit:
        rows = rows[-limit:]
    return rows


def latest_for_participant(sessions_dir: Path,
                            participant: str | None = None
                            ) -> SessionRow | None:
    """Convenience for the dashboard's "latest session" panel.
    Returns the most recent SessionRow or None if none exist."""
    rows = load_recent_sessions(sessions_dir, limit=1,
                                  participant=participant)
    return rows[-1] if rows else None
