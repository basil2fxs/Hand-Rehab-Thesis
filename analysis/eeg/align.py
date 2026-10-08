"""Pair an EEG recording's markers with the game's marker log.

The amplifier and the game run on two clocks that share nothing but
the bytes on the trigger line. Every byte the game writes is a row in
its events.tsv (t_wire, the moment the byte was written) and a rising
edge in the recording's Status channel. Pairing the two, in order,
gives a map from the game's clock to the recording's samples, so any
game event (a flash, a press sample, a force onset, a buzz command)
can be placed in the EEG. The residuals of that map are the marker
timing jitter the thesis reports.

Plain numpy and pandas, so it runs and is tested without MNE.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class Alignment:
    """The pairing of one recording with one game block."""

    n_eeg: int                     # markers found in the recording
    n_game: int                    # bytes the game says reached the wire
    matched: int                   # pairs whose codes agree, in order
    codes_agree: bool              # every pair agrees and none is left over
    slope: float                   # recording seconds per game second
    intercept: float               # recording time at game time zero
    residual_ms: np.ndarray        # recording minus fitted time, per pair
    pairs: pd.DataFrame = field(repr=False)

    @property
    def drift_ppm(self) -> float:
        """How far the two clocks run apart, parts per million."""
        return (self.slope - 1.0) * 1e6

    def to_eeg_seconds(self, t_game) -> np.ndarray:
        """Game perf_counter time to seconds into the recording."""
        return self.intercept + self.slope * np.asarray(t_game, dtype=float)


def wire_rows(events_tsv: pd.DataFrame) -> pd.DataFrame:
    """The rows that reached the wire, in wire order. Failed and dropped
    rows never reached the amplifier; queued bytes leave in priority
    order, so the wire time, not the event time, gives the order the
    recording saw."""
    ev = events_tsv.copy()
    for col in ("failed", "dropped"):
        if col in ev.columns:
            ev = ev[pd.to_numeric(ev[col], errors="coerce").fillna(0) == 0]
    ev = ev[pd.to_numeric(ev["t_wire"], errors="coerce").notna()]
    ev = ev.assign(t_wire=pd.to_numeric(ev["t_wire"]),
                   t_event=pd.to_numeric(ev["t_event"]),
                   value=pd.to_numeric(ev["value"]).astype(int))
    return ev.sort_values("t_wire", kind="stable").reset_index(drop=True)


def align(eeg_samples, eeg_codes, sfreq: float,
          game: pd.DataFrame) -> Alignment:
    """Pair recording markers with the game's wire rows, in order.

    eeg_samples and eeg_codes are the onsets (samples) and values of
    the Status channel's events; game is wire_rows() of the block's
    events.tsv. The pairing is by order: the trigger line carries one
    byte at a time and the box resets to zero between bytes, so the
    k-th rising edge is the k-th byte written. A code mismatch anywhere
    is reported, not repaired. The clock map is a least-squares line of
    recording time on game wire time over the agreeing pairs."""
    s = np.asarray(eeg_samples, dtype=float)
    c = np.asarray(eeg_codes, dtype=int)
    g = game.reset_index(drop=True)
    n = min(len(c), len(g))
    agree = c[:n] == g["value"].to_numpy()[:n]
    matched = int(agree.sum())
    codes_agree = bool(agree.all()) and len(c) == len(g)
    t_eeg = s[:n] / float(sfreq)
    t_game = g["t_wire"].to_numpy()[:n]
    use = agree if agree.any() else np.ones(n, dtype=bool)
    if use.sum() >= 2:
        slope, intercept = np.polyfit(t_game[use], t_eeg[use], 1)
    else:
        slope, intercept = 1.0, float(t_eeg[0] - t_game[0]) if n else 0.0
    fitted = intercept + slope * t_game
    resid = (t_eeg - fitted) * 1000.0
    pairs = pd.DataFrame({
        "k": np.arange(n), "code_eeg": c[:n], "code_game": g["value"][:n],
        "agree": agree, "eeg_s": t_eeg, "t_wire": t_game,
        "resid_ms": resid,
    })
    for col in ("trial_type", "lane", "t_event", "press_offset_ms",
                "onset_offset_ms"):
        if col in g.columns:
            pairs[col] = g[col].to_numpy()[:n]
    return Alignment(n_eeg=len(c), n_game=len(g), matched=matched,
                     codes_agree=codes_agree, slope=float(slope),
                     intercept=float(intercept),
                     residual_ms=resid[use], pairs=pairs)


def shifted_samples(pairs: pd.DataFrame, sfreq: float, column: str) -> np.ndarray:
    """Recording samples of each paired byte moved by a per-row offset
    in ms (events.tsv press_offset_ms or onset_offset_ms). NaN where the
    row has no offset. The trigger box's own fixed delay is the same for
    every byte, so it shifts every epoch alike and is left in."""
    off = pd.to_numeric(pairs[column], errors="coerce").to_numpy()
    return np.where(np.isfinite(off),
                    np.round((pairs["eeg_s"].to_numpy() + off / 1000.0)
                             * sfreq), np.nan)
