"""FSR press detector with per-sensor thresholds.

Same algorithm Satoru's 2025 game used (EMA baseline + delta thresholds + debounce)
but reorganised so it can run per-hand for bilateral support (Thread 3).
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable


log = logging.getLogger(__name__)


# Defaults match what Satoru tuned against patient data in 2025.
DEFAULT_ON_DELTA = [45, 90, 45, 45]
DEFAULT_OFF_DELTA = [35, 70, 35, 35]
DEFAULT_ABS_ON = [320, 400, 320, 320]
DEFAULT_ABS_OFF = [350, 450, 350, 350]


def _pad(vals, n: int, defaults: list[int]) -> list[int]:
    """Coerce vals to a length-n list of ints. Each entry is converted
    via int(); on failure (string that isn't numeric, None, garbage)
    we fall back to defaults[i] so the engine never blows up mid-block
    on a bad config value.

    Without the int coercion, a config like `fsr.on_delta: "weird"` (a
    string instead of a list) would flow through as the chars
    ['w','e','i','r','d'] and crash FSRDetector.feed later with
    `TypeError: float + str` - mid-session, in front of the patient.
    """
    def _fallback(i: int) -> int:
        return defaults[i] if i < len(defaults) else defaults[-1]

    src = list(vals or [])
    out: list[int] = []
    for i in range(n):
        if i < len(src):
            v = src[i]
            try:
                # bool is a subclass of int in Python but we want to
                # treat True/False as 1/0 only when explicit. The cast
                # here happens to do the right thing.
                out.append(int(v))
            except (TypeError, ValueError):
                out.append(_fallback(i))
        else:
            out.append(_fallback(i))
    return out


@dataclass
class Calibration:
    num_sensors: int = 4
    baseline_alpha: float = 0.02
    value_alpha: float = 0.35
    on_delta: list[int] = field(default_factory=lambda: list(DEFAULT_ON_DELTA))
    off_delta: list[int] = field(default_factory=lambda: list(DEFAULT_OFF_DELTA))
    abs_on_min: list[int] = field(default_factory=lambda: list(DEFAULT_ABS_ON))
    abs_off_max: list[int] = field(default_factory=lambda: list(DEFAULT_ABS_OFF))
    debounce_ms: int = 100
    note: str = ""

    def __post_init__(self) -> None:
        # Pad per-sensor lists to num_sensors so a hand-edited file with the
        # wrong length doesn't IndexError on the first sample.
        n = max(1, int(self.num_sensors))
        self.num_sensors = n
        self.on_delta = _pad(self.on_delta, n, DEFAULT_ON_DELTA)
        self.off_delta = _pad(self.off_delta, n, DEFAULT_OFF_DELTA)
        self.abs_on_min = _pad(self.abs_on_min, n, DEFAULT_ABS_ON)
        self.abs_off_max = _pad(self.abs_off_max, n, DEFAULT_ABS_OFF)

    def save(self, path: Path) -> None:
        """Write atomically: serialise to a tmp sibling and replace.
        Without this, a crash mid-write corrupted the researcher's tuned
        thresholds AND there was no recovery (no metadata sibling like
        Session.save has)."""
        path.parent.mkdir(parents=True, exist_ok=True)
        from dataclasses import asdict
        payload = json.dumps(asdict(self), indent=2)
        tmp = path.with_name(path.name + ".tmp")
        with tmp.open("w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            try:
                os.fsync(f.fileno())
            except (OSError, AttributeError):
                pass
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: Path) -> "Calibration | None":
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            # ValueError catches a hand-edited file with non-numeric
            # fields (e.g. num_sensors="four"); without it, __post_init__
            # crashes and the engine can't fall back to defaults.
            return cls(**{k: v for k, v in data.items()
                          if k in cls.__dataclass_fields__})
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as e:
            log.warning("Could not load calibration %s: %s", path, e)
            return None


@dataclass
class PressEvent:
    lane: int
    t_perf: float
    value: int
    baseline: float
    hand: str = "right"   # "left" or "right" for bilateral


@dataclass
class ReleaseEvent:
    lane: int
    t_perf: float
    value: int
    hand: str = "right"


class FSRDetector:
    """Per-hand stateful detector. Wire callbacks then call feed() per sample."""

    def __init__(self, cal: Calibration, hand: str = "right") -> None:
        self.cal = cal
        self.hand = hand
        n = cal.num_sensors
        self.baseline: list[float | None] = [None] * n
        self.val_ema: list[float | None] = [None] * n
        self.pressed: list[bool] = [False] * n
        self.last_event_t: list[float] = [0.0] * n
        self.last_value: list[int] = [0] * n
        self.on_press: Callable[[PressEvent], None] | None = None
        self.on_release: Callable[[ReleaseEvent], None] | None = None

    def reset(self) -> None:
        n = self.cal.num_sensors
        self.baseline = [None] * n
        self.val_ema = [None] * n
        self.pressed = [False] * n
        self.last_event_t = [0.0] * n
        self.last_value = [0] * n

    def feed(self, t_perf: float, vals: tuple[int, ...]) -> None:
        n = self.cal.num_sensors
        cal = self.cal
        for i in range(n):
            v = int(vals[i]) if i < len(vals) else 0
            self.last_value[i] = v
            # Smooth value
            sm = v if self.val_ema[i] is None else (
                cal.value_alpha * v + (1 - cal.value_alpha) * self.val_ema[i]
            )
            self.val_ema[i] = sm
            # Baseline only drifts when not pressed
            if not self.pressed[i]:
                self.baseline[i] = sm if self.baseline[i] is None else (
                    cal.baseline_alpha * sm
                    + (1 - cal.baseline_alpha) * self.baseline[i]
                )
            base = self.baseline[i] if self.baseline[i] is not None else 0.0
            on_thr = max(base + cal.on_delta[i], cal.abs_on_min[i])
            off_thr_raw = min(base + cal.off_delta[i], cal.abs_off_max[i])
            # Hysteresis safety so off threshold never sits at/above on
            off_thr = min(off_thr_raw, on_thr - 10)
            dt_ms = (t_perf - self.last_event_t[i]) * 1000.0
            if not self.pressed[i] and sm >= on_thr and dt_ms >= cal.debounce_ms:
                self.pressed[i] = True
                self.last_event_t[i] = t_perf
                # Callbacks are wrapped: an exception in the engine's
                # press handler (CSV lock, missing screen, mode swap mid-
                # frame) must not skip subsequent sensors in this batch.
                if self.on_press:
                    try:
                        self.on_press(PressEvent(
                            lane=i, t_perf=t_perf, value=v, baseline=base,
                            hand=self.hand,
                        ))
                    except Exception as e:
                        log.warning("on_press(lane=%d, hand=%s) raised: %s",
                                     i, self.hand, e)
            elif self.pressed[i] and sm <= off_thr and dt_ms >= cal.debounce_ms:
                self.pressed[i] = False
                self.last_event_t[i] = t_perf
                if self.on_release:
                    try:
                        self.on_release(ReleaseEvent(
                            lane=i, t_perf=t_perf, value=v, hand=self.hand,
                        ))
                    except Exception as e:
                        log.warning("on_release(lane=%d, hand=%s) raised: %s",
                                     i, self.hand, e)
