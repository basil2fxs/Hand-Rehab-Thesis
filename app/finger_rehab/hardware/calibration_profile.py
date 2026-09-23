"""Per-device press calibration, measured in the app and saved with the
sessions that used it.

Why this exists. Thresholds set from an empty device miss the fact that
a hand resting on the pads already loads them, and by different amounts
per finger. On this device the pinky pad carries about thirty counts at
rest while the index carries under three. Setting one threshold from
absolute readings then forces the pinky trigger far higher than a weak
finger can reach.

The fix is to measure three things and store them together:

    empty      nothing touching the device, the true zero
    resting    the hand in position but not pressing, the tare point
    press      a light press per finger, and all fingers at once

Detection then works from the gap between resting and press rather than
from absolute counts, and the resting level is used to prime the
detector's baseline at block start so there is no settling window where
a resting hand can trip the trigger.

The all-fingers step is not just a check. Comparing the sum of the
single-finger presses against the simultaneous one gives the
multi-finger force deficit, which is a documented stroke measure and
which no single-finger prompt can produce.

Every session records the profile it ran under, so an analysis can
convert counts to force and know exactly what the thresholds were,
even years later.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path


N_FINGERS = 4
FINGER_NAMES = ("index", "middle", "ring", "pinky")

# Fraction of the resting-to-press gap a finger must cover to count as a
# press, and the fraction it must fall back below to count as released.
# 0.40 leaves room for a press weaker than the one demonstrated while
# staying clear of the resting load. The release point sits lower so a
# finger hovering near the trigger cannot chatter.
PRESS_FRACTION = 0.40
RELEASE_FRACTION = 0.20

# A press must clear the sensor noise by this multiple whatever the gap
# says, so a finger that barely moved during calibration cannot end up
# with a threshold inside the noise.
MIN_NOISE_MULTIPLE = 8.0

# FSRDetector clamps the release point to (on_thr - DETECTOR_HYSTERESIS) so
# release can never sit at or above press. That clamp is not optional and it
# is applied after our off_delta, so any threshold computed here has to be
# consistent with it.
#
# The consequence is easy to miss and it is severe. off_thr ends up at
# base + min(off_delta, on_delta - 10). If on_delta is under 10 that lands
# BELOW the baseline, which means a finger that has registered one press can
# only release by pressing LIGHTER than a resting hand, i.e. by lifting off
# the device entirely. It stays latched for the rest of the block and every
# later trial on it is scored a miss, which reads in the data as a completely
# paralysed finger rather than as a threshold fault.
#
# So on_delta must stay above the clamp with room to spare, and off_delta has
# to be computed against the clamp rather than independently of it.
DETECTOR_HYSTERESIS = 10
MIN_DELTA_COUNTS = DETECTOR_HYSTERESIS + 2      # 12

# Smallest resting-to-press travel that can carry a valid threshold. Below
# this the press point cannot sit both clear of the noise and far enough
# under the press to be reachable, so the calibration asks for a firmer press
# instead of saving something that will not work.
MIN_USABLE_GAP = 20

# Highest fraction of a finger's own travel the trigger may sit at. Above
# this the patient has to reproduce almost exactly the press they gave at
# calibration, and any weaker attempt is scored a miss.
#
# This matters because the preload floor can demand more than the gap allows.
# A pad carrying 30 counts at rest under a finger that only travels 28 needs
# a floor of 34 to stay clear of a landing hand, which is above the whole
# travel: the trigger would be unreachable and every trial on that finger
# would be logged as a miss, reading as a paralysed finger. That is a pad
# placement problem and it has to be refused rather than saved.
MAX_TRIGGER_FRACTION = 0.70

# How many times the smallest usable gap a calibration press may reach
# before it stops being the LIGHT press these thresholds are meant to be
# set from. on_delta is PRESS_FRACTION of whatever gap gets measured, so
# a press four times the floor sets a trigger four times harder to reach,
# and a finger that is weaker later in the session (fatigue, a bad day)
# cannot get back to it: every trial on it then logs as a miss. Anything
# above this is a press the capture should ask to be eased off, not
# saved.
LIGHT_PRESS_CEILING_MULTIPLE = 4.0

# on_delta is rounded to whole counts and the gap it is compared against
# is a measurement, so a target sitting exactly on usable()'s boundary
# can land the wrong side of it by half a count: the calibration would
# coach a press, accept it, and then reject the profile built from it.
# The band asks for this much more than the bare minimum so hitting it is
# never a near miss.
BAND_MARGIN_COUNTS = 2.0


def press_floor_counts(preload: float, noise: float) -> float:
    """Lowest press threshold a finger can be given, in counts above the
    tracked baseline.

    Pulled out of on_delta so the calibration UI can draw the target it
    is asking for from the same expression the threshold ends up using.
    Two different expressions here would let the screen coach a press
    the maths then rejects.
    """
    return max(float(MIN_DELTA_COUNTS),
               float(noise) * MIN_NOISE_MULTIPLE,
               float(preload) + 3.0 * float(noise))


def target_gap_band(preload: float, noise: float) -> tuple[float, float]:
    """The resting-to-press gap a calibration press should land in, for
    one finger, given how loaded that finger's pad is at rest and how
    noisy its sensor is.

    The floor is the smallest gap that survives BOTH checks usable()
    makes: at least MIN_USABLE_GAP of travel, and a trigger that sits no
    higher than MAX_TRIGGER_FRACTION of that travel. Dividing the press
    floor by MAX_TRIGGER_FRACTION is what turns the second check into a
    gap the player can be asked for. The ceiling is the light-press
    limit above.

    Both ends therefore move with the pad: a preloaded pinky is asked
    for a firmer press than a clean index, because that is exactly what
    its threshold will need.
    """
    floor = press_floor_counts(preload, noise)
    lo = max(float(MIN_USABLE_GAP) + BAND_MARGIN_COUNTS,
             (floor + BAND_MARGIN_COUNTS) / MAX_TRIGGER_FRACTION)
    return lo, lo * LIGHT_PRESS_CEILING_MULTIPLE


@dataclass
class CalibrationProfile:
    """One measurement session for one device."""

    created_at: str = field(
        default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%S"))
    device_port: str = ""
    participant: str = ""
    hand: str = "right"
    # Per-sensor readings, all in raw counts, index order 0..3.
    empty: list[float] = field(default_factory=lambda: [0.0] * N_FINGERS)
    empty_noise: list[float] = field(default_factory=lambda: [0.0] * N_FINGERS)
    resting: list[float] = field(default_factory=lambda: [0.0] * N_FINGERS)
    press: list[float] = field(default_factory=lambda: [0.0] * N_FINGERS)
    # Peak on each sensor when all four pressed together. Compared with
    # `press` this gives the multi-finger deficit.
    press_all: list[float] = field(default_factory=lambda: [0.0] * N_FINGERS)
    # Session max press per finger, in counts ABOVE RESTING (the same
    # reference detection and the continuous force view use), measured
    # by the in-mode max-press probes: two or three maximal presses,
    # median peak kept. Zero means "not measured", which is what every
    # profile saved before this field existed loads as, so old files
    # keep working and old code reading a new file simply drops the
    # field.
    #
    # This is deliberately separate from `press`. The calibration
    # press is a LIGHT press that sets detection thresholds a weak
    # finger can reach; max_press is the ceiling that force targets
    # are percentages of. Conflating them would make "20 percent of
    # max" mean "20 percent of a light press", far below anything the
    # steadiness literature calls 20 percent MVC.
    max_press: list[float] = field(default_factory=lambda: [0.0] * N_FINGERS)
    # When the probes ran, same format as created_at. Max press is a
    # session quantity (it moves with fatigue and day-to-day state),
    # so a mode deciding whether to reuse or re-probe needs the age,
    # not just the values.
    max_press_measured_at: str = ""
    # Which login session probed the max. Anonymous logins all stamp
    # participant "NA", so the name alone cannot stop patient B (also
    # anonymous, same machine, inside the freshness window) inheriting
    # patient A's strength as the denominator of every percent
    # target; the token separates the two logins. Empty on profiles
    # saved before the field existed, which the gate treats as
    # not-provable and re-probes.
    session_token: str = ""
    notes: str = ""

    # ---- derived values -------------------------------------------

    def gap(self) -> list[float]:
        """Counts between a resting finger and a light press. This is
        what detection actually has to resolve."""
        return [max(0.0, self.press[i] - self.resting[i])
                for i in range(N_FINGERS)]

    def preload(self) -> list[float]:
        """How much each pad is loaded by a hand simply resting on it."""
        return [max(0.0, self.resting[i] - self.empty[i])
                for i in range(N_FINGERS)]

    def target_band(self) -> list[tuple[float, float]]:
        """Per finger, the gap the calibration press was asked to land
        in. Derived from this profile's own empty and resting captures,
        so the summary can say whether a press came in light, on target
        or firm using the same numbers the capture coached against."""
        return [target_gap_band(self.preload()[i], self.empty_noise[i])
                for i in range(N_FINGERS)]

    def on_delta(self) -> list[int]:
        """Press threshold per finger, relative to the tracked baseline.

        Because the baseline is primed to the resting level, this only
        has to cover the resting-to-press gap, not the absolute load.
        That is what keeps the pinky usable despite its heavy preload.
        """
        out = []
        for i in range(N_FINGERS):
            # Two floors. The noise floor stops a finger that barely
            # moved from getting a threshold inside the sensor noise.
            # The preload floor covers the one case where the baseline
            # has not yet absorbed the resting load: a block started
            # with the hand off the device, so the hand landing looks
            # like a rise. Neither normally binds.
            floor = press_floor_counts(self.preload()[i],
                                       self.empty_noise[i])
            out.append(int(round(max(floor, self.gap()[i] * PRESS_FRACTION))))
        return out

    def off_delta(self) -> list[int]:
        """Release point per finger, relative to the tracked baseline.

        Capped at (on_delta - DETECTOR_HYSTERESIS) because the detector
        applies that cap anyway. Computing it here as well keeps the saved
        profile honest about what will actually happen at runtime, and the
        floor of 1 keeps the release point strictly above the baseline so a
        pressed finger can always get back down to it.
        """
        out = []
        for i, on in enumerate(self.on_delta()):
            rel = self.gap()[i] * RELEASE_FRACTION
            capped = min(rel, on - DETECTOR_HYSTERESIS, on * 0.6)
            out.append(int(round(max(1.0, capped))))
        return out

    # ---- session max press ----------------------------------------

    def has_max_press(self) -> bool:
        """Whether the max-press probes have run for this profile.
        All-zero (the default, and what pre-field files load as)
        means no."""
        return any(v > 0.0 for v in (self.max_press or []))

    def set_max_press(self, values: list[float],
                       measured_at: str | None = None) -> None:
        """Store the probed session max per finger, counts above
        resting. Values are clamped at zero because a negative max is
        always a probe fault, and a zero entry keeps meaning "not
        measured" for that finger."""
        vals = [max(0.0, float(v)) for v in values[:N_FINGERS]]
        while len(vals) < N_FINGERS:
            vals.append(0.0)
        self.max_press = vals
        self.max_press_measured_at = (
            measured_at or time.strftime("%Y-%m-%dT%H:%M:%S"))

    def percent_of_max(self, finger: int, counts: float) -> float | None:
        """Convert a baseline-subtracted reading on one finger to
        percent of that finger's session max. None when the probe has
        not run for that finger, so a mode cannot silently fall back
        to raw counts: force targets in the continuous modes are
        percentages of the probed max, never counts."""
        if not (0 <= finger < N_FINGERS):
            return None
        m = self.max_press[finger] if finger < len(self.max_press) else 0.0
        if m <= 0.0:
            return None
        return float(counts) / float(m) * 100.0

    def max_press_age_s(self, now: float | None = None) -> float | None:
        """Seconds since the probes ran, or None when they have not.
        Wall-clock based because the timestamp has to survive an app
        restart within the same session day."""
        if not self.max_press_measured_at:
            return None
        try:
            measured = time.mktime(time.strptime(
                self.max_press_measured_at, "%Y-%m-%dT%H:%M:%S"))
        except (ValueError, OverflowError):
            return None
        return max(0.0, (now if now is not None else time.time()) - measured)

    def multi_finger_deficit(self) -> float | None:
        """Sum of the single-finger presses against the simultaneous
        one, as a fraction lost. Positive means each finger produced
        less force when all four pressed together, which is the
        multi-finger deficit reported in the stroke literature.

        Returns None when the all-fingers step was skipped.
        """
        if not any(self.press_all):
            return None
        singles = sum(self.gap())
        together = sum(max(0.0, self.press_all[i] - self.resting[i])
                       for i in range(N_FINGERS))
        if singles <= 0:
            return None
        return round((singles - together) / singles, 4)

    def usable(self) -> tuple[bool, list[str]]:
        """Whether this profile is good enough to run a session on."""
        problems = []
        on = self.on_delta()
        for i in range(N_FINGERS):
            g = self.gap()[i]
            if g > 0 and on[i] > g * MAX_TRIGGER_FRACTION:
                problems.append(
                    f"{FINGER_NAMES[i]}: trigger of {on[i]} counts is "
                    f"{on[i] / g * 100:.0f}% of the {g:.0f} counts this finger "
                    f"actually travels, because the pad carries "
                    f"{self.preload()[i]:.0f} counts at rest. Reposition that "
                    f"pad to reduce the resting load, then calibrate again")
            if g < MIN_USABLE_GAP:
                problems.append(
                    f"{FINGER_NAMES[i]}: only {g:.0f} counts between resting "
                    f"and pressing, needs at least {MIN_USABLE_GAP} for a "
                    f"threshold that can both trigger and release")
            if self.empty[i] <= 1:
                problems.append(
                    f"{FINGER_NAMES[i]}: sensor reads zero when empty, "
                    f"likely an I2C fault")
        return (not problems), problems

    def summary(self) -> dict:
        """Compact form for metadata.json, so a session carries the
        calibration it ran under."""
        return {
            "created_at": self.created_at,
            "device_port": self.device_port,
            # Whose measurement this is: without it metadata.json
            # could not reveal a max press inherited from another
            # patient's profile.
            "participant": self.participant,
            "hand": self.hand,
            "empty": [round(v, 1) for v in self.empty],
            "resting": [round(v, 1) for v in self.resting],
            "press": [round(v, 1) for v in self.press],
            "press_all": [round(v, 1) for v in self.press_all],
            "preload": [round(v, 1) for v in self.preload()],
            "gap": [round(v, 1) for v in self.gap()],
            "on_delta": self.on_delta(),
            "off_delta": self.off_delta(),
            "multi_finger_deficit": self.multi_finger_deficit(),
            # Session max press rides along so metadata.json records
            # what every percent target in the block actually meant in
            # counts. Zeros when the probes never ran.
            "max_press": [round(v, 1) for v in self.max_press],
            "max_press_measured_at": self.max_press_measured_at,
        }

    # ---- persistence ----------------------------------------------

    def save(self, path: Path) -> Path:
        """Atomic write, same pattern the session metadata uses."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(self), indent=2)
        tmp = path.with_name(path.name + ".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                f.write(payload)
                f.flush()
                try:
                    os.fsync(f.fileno())
                except (OSError, AttributeError):
                    pass
            os.replace(tmp, path)
        except BaseException:
            try:
                if tmp.exists():
                    tmp.unlink()
            except OSError:
                pass
            raise
        return path

    @classmethod
    def load(cls, path: Path) -> "CalibrationProfile | None":
        path = Path(path)
        if not path.exists():
            return None
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return None
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in data.items() if k in known})
