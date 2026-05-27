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
    # Peak-force stats over the press window (rising-edge to falling-
    # edge). Both default to None so a caller that builds a
    # ReleaseEvent in a test fixture without going through the
    # detector still constructs cleanly.
    #   peak_raw          = max smoothed value seen during the press
    #   peak_minus_baseline = peak_raw minus the baseline at press
    #                          start (the part attributable to the
    #                          patient's effort, not sensor offset)
    peak_raw: float | None = None
    peak_minus_baseline: float | None = None
    # Force-time integral (impulse) over the press window.
    # `impulse_raw` is the trapezoidal integral of the smoothed
    # force value across the press; `impulse_minus_baseline` is the
    # same integral with the press-start baseline subtracted at
    # every sample, which is the clinically meaningful quantity
    # (total effort delivered above sensor offset).
    # Units are (signal-unit * seconds); newton-seconds when a
    # force calibration constant is configured, ADC-count-seconds
    # otherwise. The Session.json's `force_unit` field carries that
    # context.
    impulse_raw: float | None = None
    impulse_minus_baseline: float | None = None
    # Duration of the press window in seconds, useful for
    # normalising impulse to a force average if a researcher wants
    # impulse / duration rather than the raw impulse.
    duration_s: float | None = None


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
        # Per-sensor peak-force tracking. `_peak_raw` is the max
        # smoothed value seen since the current press began; it's
        # only meaningful while pressed[i] is True. `_peak_baseline`
        # records the baseline AT THE MOMENT of the rising edge so
        # the peak-minus-baseline computation uses the right
        # reference (not a baseline that has wandered since).
        self._peak_raw: list[float | None] = [None] * n
        self._peak_baseline: list[float | None] = [None] * n
        # Force-time integral (impulse) accumulators. Built up as
        # samples arrive during a press via trapezoidal integration:
        #   _impulse_raw   = running sum(force[i] * dt[i])
        #   _impulse_minus = running sum((force[i] - baseline) * dt[i])
        # The press-start timestamp lives in _press_start_t so the
        # release event can also report duration_s = release - start.
        # `_last_sample_t` records the t_perf of the previous sample
        # so dt can be computed against the next one.
        self._impulse_raw: list[float | None] = [None] * n
        self._impulse_minus: list[float | None] = [None] * n
        self._press_start_t: list[float | None] = [None] * n
        self._last_sample_t: list[float | None] = [None] * n
        self.on_press: Callable[[PressEvent], None] | None = None
        self.on_release: Callable[[ReleaseEvent], None] | None = None

    def reset(self) -> None:
        n = self.cal.num_sensors
        self.baseline = [None] * n
        self.val_ema = [None] * n
        self.pressed = [False] * n
        self.last_event_t = [0.0] * n
        self.last_value = [0] * n
        self._peak_raw = [None] * n
        self._peak_baseline = [None] * n
        self._impulse_raw = [None] * n
        self._impulse_minus = [None] * n
        self._press_start_t = [None] * n
        self._last_sample_t = [None] * n

    def baseline_value(self, sensor_idx: int) -> float | None:
        """Live baseline EMA for one sensor. Used by the per-sensor
        drift sampler in the session loop (samples every 30 s and
        feeds drift_slope at finish_block). Returns None when no
        sample has been fed yet for this sensor."""
        if 0 <= sensor_idx < len(self.baseline):
            return self.baseline[sensor_idx]
        return None

    def current_peak(self, sensor_idx: int
                       ) -> tuple[float, float] | None:
        """Live peak-force snapshot for an in-progress press. Returns
        (peak_raw, peak_minus_baseline) if the sensor is currently
        pressed, else None. Used by the engine at log_trial time:
        log_trial runs when the correct press arrives but BEFORE
        the release event, so the ReleaseEvent payload isn't
        available yet. This accessor reads the running peak (the max
        smoothed value seen between rising edge and now).
        """
        if not (0 <= sensor_idx < len(self._peak_raw)):
            return None
        if not self.pressed[sensor_idx]:
            return None
        peak_raw = self._peak_raw[sensor_idx]
        peak_base = self._peak_baseline[sensor_idx]
        if peak_raw is None or peak_base is None:
            return None
        return (float(peak_raw), float(peak_raw - peak_base))

    def current_impulse(self, sensor_idx: int
                          ) -> tuple[float, float] | None:
        """Live force-time integral for an in-progress press. Returns
        (impulse_raw, impulse_minus_baseline) accumulated between
        the rising edge and the most recent sample, or None when
        the sensor isn't pressed. Same shape as current_peak so the
        engine can grab both at log_trial time."""
        if not (0 <= sensor_idx < len(self._impulse_raw)):
            return None
        if not self.pressed[sensor_idx]:
            return None
        raw = self._impulse_raw[sensor_idx]
        minus = self._impulse_minus[sensor_idx]
        if raw is None or minus is None:
            return None
        return (float(raw), float(minus))

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
                # Start tracking the peak for this press. The rising-
                # edge sample is the first candidate; subsequent
                # samples in the while-pressed branch will replace it
                # if they exceed it. _peak_baseline is frozen here so
                # peak_minus_baseline uses the reference the patient
                # actually started from.
                self._peak_raw[i] = float(sm)
                self._peak_baseline[i] = float(base)
                # Start the impulse accumulator at zero. The first
                # in-press sample after this contributes a trapezoid
                # of (sm + sm_now) / 2 * dt to both impulse channels
                # (raw uses sm, minus uses sm - base).
                self._impulse_raw[i] = 0.0
                self._impulse_minus[i] = 0.0
                self._press_start_t[i] = float(t_perf)
                self._last_sample_t[i] = float(t_perf)
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
                # Finalise the peak. _peak_raw was last updated on the
                # most recent in-press sample (see below). Compute
                # peak-minus-baseline from the snapshot taken at the
                # rising edge so a slow baseline drift mid-press
                # doesn't change the answer.
                peak_raw = self._peak_raw[i]
                peak_base = self._peak_baseline[i]
                peak_minus = None
                if peak_raw is not None and peak_base is not None:
                    peak_minus = peak_raw - peak_base
                # Finalise the impulse. The current sample contributes
                # one last trapezoid before the press ends. This makes
                # impulse_minus_baseline = integral of (force - baseline)
                # across the whole press window.
                if (self._impulse_raw[i] is not None
                        and self._last_sample_t[i] is not None):
                    dt = float(t_perf) - float(self._last_sample_t[i])
                    if dt > 0:
                        # Treat the falling-edge sample as also at
                        # value sm so the trapezoid is well-defined.
                        self._impulse_raw[i] += float(sm) * dt
                        self._impulse_minus[i] += (
                            float(sm) - float(peak_base
                                                if peak_base is not None
                                                else base)) * dt
                impulse_raw = self._impulse_raw[i]
                impulse_minus = self._impulse_minus[i]
                duration_s = None
                if self._press_start_t[i] is not None:
                    duration_s = float(t_perf) - float(self._press_start_t[i])
                # Clear so the next press starts fresh.
                self._peak_raw[i] = None
                self._peak_baseline[i] = None
                self._impulse_raw[i] = None
                self._impulse_minus[i] = None
                self._press_start_t[i] = None
                self._last_sample_t[i] = None
                if self.on_release:
                    try:
                        self.on_release(ReleaseEvent(
                            lane=i, t_perf=t_perf, value=v, hand=self.hand,
                            peak_raw=peak_raw,
                            peak_minus_baseline=peak_minus,
                            impulse_raw=impulse_raw,
                            impulse_minus_baseline=impulse_minus,
                            duration_s=duration_s,
                        ))
                    except Exception as e:
                        log.warning("on_release(lane=%d, hand=%s) raised: %s",
                                     i, self.hand, e)
            elif self.pressed[i]:
                # In-press sample. Update the rolling peak so the
                # ReleaseEvent at the falling edge reflects the
                # maximum smoothed value seen across the whole press
                # window, not just the rising / falling edges.
                if (self._peak_raw[i] is None
                        or sm > self._peak_raw[i]):
                    self._peak_raw[i] = float(sm)
                # Trapezoidal integration over dt between this sample
                # and the previous one. Done with the smoothed value
                # `sm` so spike noise gets filtered out by the EMA
                # that's already in place upstream.
                last_t = self._last_sample_t[i]
                if (last_t is not None
                        and self._impulse_raw[i] is not None
                        and self._peak_baseline[i] is not None):
                    dt = float(t_perf) - float(last_t)
                    if dt > 0:
                        self._impulse_raw[i] += float(sm) * dt
                        self._impulse_minus[i] += (
                            float(sm)
                            - float(self._peak_baseline[i])) * dt
                self._last_sample_t[i] = float(t_perf)
