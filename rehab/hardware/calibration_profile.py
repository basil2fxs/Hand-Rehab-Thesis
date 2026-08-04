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
MIN_DELTA_COUNTS = 6


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
            floor = max(MIN_DELTA_COUNTS,
                        self.empty_noise[i] * MIN_NOISE_MULTIPLE,
                        self.preload()[i] + 3.0 * self.empty_noise[i])
            out.append(int(round(max(floor, self.gap()[i] * PRESS_FRACTION))))
        return out

    def off_delta(self) -> list[int]:
        out = []
        for i, on in enumerate(self.on_delta()):
            rel = max(self.gap()[i] * RELEASE_FRACTION, MIN_DELTA_COUNTS / 2)
            # Keep a real distance below the press point or the finger
            # chatters around the threshold.
            out.append(int(round(min(rel, on * 0.6))))
        return out

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
        for i in range(N_FINGERS):
            g = self.gap()[i]
            if g < 10:
                problems.append(
                    f"{FINGER_NAMES[i]}: only {g:.0f} counts between resting "
                    f"and pressing, too little to detect reliably")
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
