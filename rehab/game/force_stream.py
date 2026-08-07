"""Continuous force access and the max-press probe flow.

Research case. The three continuous-force modes (Force Pilot,
Lighthouse, Buzz Hunt's press responses) score the 200 Hz force signal
itself, not threshold crossings. Every paradigm they implement sets
targets as a percentage of the finger's maximal voluntary press: Lodha
2013 (PLOS ONE 8(12):e83468) held 5 / 25 / 50 percent MVC, Li 2015
(Clinical Neurophysiology 126(1):194-201) held a fixed low pinch,
Camacho-Villa 2025 (Scand J Med Sci Sports 35(4):e70040) pooled tasks
at 5 to 25 percent MVC, and Naik 2011 (Exp Brain Res 211:1-15) ramped
at 5 to 20 percent MVC per second. None of that is expressible in raw
ADC counts: SingleTact pads vary unit to unit and the resting load
differs per finger, so a counts target on one rig is a different
demand on another. Hence two pieces here:

  ForceView      per-frame calibrated force per lane, baseline-
                 subtracted counts plus percent of the probed max.
  MaxPressProbe  the in-mode flow that measures that max: cue one
                 finger, take two or three maximal presses, keep the
                 median peak.

Claim limits. The probe measures a maximal PRESS on a flat pad with
the hand resting, not a grip or pinch MVC from the cited protocols;
percent-of-max here therefore matches those studies in construct, not
in absolute newtons. The median of two or three attempts follows
standard MVC practice of repeated attempts, but with fewer repeats
than a formal strength assessment, a deliberate trade against patient
fatigue. SingleTact accuracy and drift at very low force is
uncharacterised on this rig (flagged in the ranked brief); rebaseline
between trials and keep hold segments short until the bench
characterisation exists.

Why the view freezes its reference instead of tracking the detector's
live baseline: the detector's baseline EMA exists to absorb slow
sensor drift, and it only holds still while the finger is PRESSED
(above the on threshold). A Lighthouse hold at 10 percent of max sits
well below that threshold, so the live baseline absorbs a large share
of the held force over a 15 to 20 s hold (the shipped baseline alpha
of 0.0005 at 200 Hz is a time constant near 10 s) and the reading
would sag mid-trial. The view therefore subtracts a frozen reference:
the calibrated resting level by default, or the level captured by
rebaseline() while the hand rests between trials.

The rebaseline capture reads the detector's SMOOTHED VALUE, not its
baseline EMA. The same slowness that makes the baseline absorb a hold
makes it slow to let one go: after a sub-threshold hold it needs tens
of seconds of rest to shed the absorbed force, far longer than the
between-trial gap, so capturing it would freeze part of the previous
trial's force into the next trial's tare (verified in the headless
drive: about 25 counts, 7 percent of max, after one 16 s hold). The
smoothed value tracks the pad within a fraction of a second, so while
the hand rests it IS the current resting level, drift included, which
is also what the notebook's offline tare (median raw level over the
same resting window) measures.
"""
from __future__ import annotations

import logging
import statistics
from typing import NamedTuple


log = logging.getLogger(__name__)


class ForceReading(NamedTuple):
    """One lane's force at one frame."""

    counts: float           # baseline-subtracted, clamped at zero
    percent: float | None   # percent of session max; None before a probe


class ForceView:
    """Per-frame calibrated force per lane, on top of the engine's
    detectors.

    The engine already pumps every sample through the per-hand
    detectors each frame, so this class never touches the serial
    layer: it polls each detector's smoothed value (value EMA, the
    same signal press detection runs on) and subtracts a frozen
    per-lane reference. Modes construct one per block and call read()
    or read_all() once per frame.

    Lane numbering is the engine's: 0..3 unilateral, 0..7 bilateral
    with the left hand at 4..7. Both hands selected means all eight
    lanes are active.
    """

    def __init__(self, engine) -> None:
        self.engine = engine
        # Frozen per-lane reference, captured lazily or by
        # rebaseline(). Keyed by global lane index.
        self._reference: dict[int, float] = {}

    # ---- reference handling ---------------------------------------

    def _profile_for(self, hand: str):
        profiles = getattr(self.engine, "calibration_profiles", None) or {}
        return profiles.get(hand)

    def _resolve(self, lane: int):
        resolver = getattr(self.engine, "_resolve_lane_to_detector", None)
        if resolver is None:
            return None
        mapped = resolver(lane)
        if mapped is None:
            return None
        hand, idx = mapped
        det = (getattr(self.engine, "detectors", None) or {}).get(hand)
        if det is None:
            return None
        return hand, idx, det

    def _reference_for(self, lane: int, hand: str, idx: int,
                        det) -> float | None:
        """The frozen tare point for one lane.

        Priority: an explicit rebaseline() capture, then the
        calibrated resting level, then a one-off capture of the
        detector's current baseline (frozen from then on, see the
        module docstring for why it must not track). None only when
        no sample has arrived yet on an uncalibrated rig.
        """
        if lane in self._reference:
            return self._reference[lane]
        prof = self._profile_for(hand)
        resting = getattr(prof, "resting", None) if prof is not None else None
        if resting and idx < len(resting) and resting[idx] > 0.0:
            return float(resting[idx])
        base = self._rest_level(idx, det)
        if base is None:
            return None
        self._reference[lane] = float(base)
        return self._reference[lane]

    @staticmethod
    def _rest_level(idx: int, det) -> float | None:
        """The lane's current resting level: the detector's smoothed
        value, taken only while the finger is not pressed. NOT the
        baseline EMA: that EMA is slow on purpose (drift absorption),
        so after a sub-threshold hold it still carries part of the
        held force for tens of seconds, and capturing it would tare
        the next trial against the previous trial's press. While the
        hand rests, the smoothed value is the resting level itself,
        drift included, and it matches the offline tare the notebook
        takes over the same resting window."""
        try:
            if idx < len(det.pressed) and det.pressed[idx]:
                return None
            ema = det.val_ema[idx] if idx < len(det.val_ema) else None
        except (AttributeError, TypeError):
            return None
        return None if ema is None else float(ema)

    def rebaseline(self, lanes: list[int] | None = None) -> None:
        """Re-capture the tare point from the resting hand, for every
        active lane or just the given ones. Call between trials while
        the hand rests: it absorbs whatever slow drift accumulated
        during the previous hold, which the frozen reference
        deliberately ignored while scoring was running. A lane whose
        finger is somehow still pressed keeps its old reference
        rather than taring against the press."""
        targets = lanes if lanes is not None else self.active_lanes()
        for lane in targets:
            resolved = self._resolve(lane)
            if resolved is None:
                continue
            _hand, idx, det = resolved
            base = self._rest_level(idx, det)
            if base is not None:
                self._reference[lane] = float(base)

    # ---- reads ----------------------------------------------------

    def active_lanes(self) -> list[int]:
        """Every lane the current hand mode plays: 0..3 for one hand,
        0..7 for both (Basil's rule: both hands means all eight)."""
        try:
            return list(range(int(self.engine.total_lanes)))
        except (AttributeError, TypeError, ValueError):
            return list(range(4))

    def read(self, lane: int) -> ForceReading | None:
        """This lane's force right now: baseline-subtracted counts,
        clamped at zero, plus percent of the probed session max.
        percent is None until the max-press probe has run for the
        finger, so a mode cannot quietly score percent targets
        against nothing. Returns None when no sample has reached the
        lane's detector yet."""
        resolved = self._resolve(lane)
        if resolved is None:
            return None
        hand, idx, det = resolved
        ema = det.val_ema[idx] if idx < len(det.val_ema) else None
        if ema is None:
            return None
        ref = self._reference_for(lane, hand, idx, det)
        if ref is None:
            return None
        counts = max(0.0, float(ema) - ref)
        prof = self._profile_for(hand)
        percent = (prof.percent_of_max(idx, counts)
                   if prof is not None and hasattr(prof, "percent_of_max")
                   else None)
        return ForceReading(counts=counts, percent=percent)

    def read_all(self) -> dict[int, ForceReading]:
        """Every active lane that has data, in one call per frame."""
        out: dict[int, ForceReading] = {}
        for lane in self.active_lanes():
            r = self.read(lane)
            if r is not None:
                out[lane] = r
        return out

    def sample_age_s(self, lane: int, now: float) -> float | None:
        """Seconds since the lane's detector last saw a sample, against
        the caller's perf_counter clock. None before the first sample.
        A mode should treat a reading older than a few frames as a
        source dropout and pause scoring rather than score a flat
        line the patient is not producing."""
        resolved = self._resolve(lane)
        if resolved is None:
            return None
        _hand, _idx, det = resolved
        last = getattr(det, "last_feed_t", None)
        if last is None:
            return None
        return max(0.0, float(now) - float(last))


class MaxPressProbe:
    """State machine for one finger's max-press measurement.

    The mode owns the screen and the cue; this owns the decision
    logic. Feed it the finger's baseline-subtracted counts every
    frame (from ForceView.read) and it collects `n_presses` maximal
    attempts, then reports the median peak. Median rather than max
    because a single overshoot spike (the hand landing, a knock on
    the rig) must not become the denominator of every force target
    in the session; median of three tolerates one bad attempt.

    A press attempt starts when force rises above `floor_counts` and
    ends when it falls back below the larger of `floor_counts` and 20
    percent of that attempt's own peak. Attempts shorter than
    `min_press_s` are discarded as knocks, and `min_rest_s` of quiet
    is required between attempts so one long wobbling push cannot be
    read as two.
    """

    # Fraction of the attempt's own peak the force must drop below
    # (when above the floor) before the attempt is banked. Keeps a
    # tremorous plateau from ending an attempt early.
    RELEASE_FRACTION = 0.20

    def __init__(self, n_presses: int = 3, floor_counts: float = 30.0,
                  min_press_s: float = 0.15,
                  min_rest_s: float = 0.30) -> None:
        if n_presses < 2:
            # One attempt has no protection against a half-effort or a
            # spike; the design floor is two, per the probe flow spec.
            raise ValueError("max-press probe needs at least 2 presses")
        self.n_presses = int(n_presses)
        self.floor_counts = float(floor_counts)
        self.min_press_s = float(min_press_s)
        self.min_rest_s = float(min_rest_s)
        self.peaks: list[float] = []
        self.state = "rest"          # "rest" | "press" | "done"
        self._press_start: float | None = None
        self._press_peak = 0.0
        self._rest_since: float | None = None

    @property
    def presses_remaining(self) -> int:
        return max(0, self.n_presses - len(self.peaks))

    def update(self, t_s: float, counts: float) -> None:
        """Advance on one frame's reading. t_s is any monotonically
        increasing clock in seconds (perf_counter in the app)."""
        if self.state == "done":
            return
        counts = max(0.0, float(counts))
        if self.state == "rest":
            if counts >= self.floor_counts:
                if (self._rest_since is None
                        or t_s - self._rest_since >= self.min_rest_s):
                    self.state = "press"
                    self._press_start = t_s
                    self._press_peak = counts
                # A rise inside the rest window is the tail of the
                # previous attempt still wobbling; ignore it and keep
                # requiring quiet.
            else:
                if self._rest_since is None:
                    self._rest_since = t_s
            return
        # state == "press"
        if counts > self._press_peak:
            self._press_peak = counts
        release_at = max(self.floor_counts,
                          self._press_peak * self.RELEASE_FRACTION)
        if counts < release_at:
            # Explicit None check: a press that started at t_s == 0.0
            # is falsy but real, and `or` would zero its held time and
            # silently drop the first attempt of a block.
            start = self._press_start
            held = t_s - start if start is not None else 0.0
            if held >= self.min_press_s:
                self.peaks.append(self._press_peak)
            # Too-short rises are knocks, not presses: drop them
            # without counting an attempt.
            self.state = "rest"
            self._rest_since = t_s
            self._press_start = None
            self._press_peak = 0.0
            if len(self.peaks) >= self.n_presses:
                self.state = "done"

    def result(self) -> float | None:
        """Median peak across the attempts, or None until done."""
        if self.state != "done" or not self.peaks:
            return None
        return float(statistics.median(self.peaks))


def needs_max_press_probe(profile, max_age_s: float = 6 * 3600.0,
                           now: float | None = None) -> bool:
    """Whether a mode must run the probes before using percent
    targets. True with no profile, no stored max, or a max older than
    `max_age_s` (default six hours: within one session sitting the
    stored value is reusable, but a value persisted from yesterday
    reflects yesterday's strength and fatigue, so it must be
    re-measured)."""
    if profile is None or not getattr(profile, "has_max_press", None):
        return True
    if not profile.has_max_press():
        return True
    age = profile.max_press_age_s(now)
    if age is None:
        # Values exist but the timestamp is unreadable, so freshness
        # cannot be shown; measuring again costs a minute, trusting a
        # stale max skews every target in the block.
        return True
    return age > max_age_s
