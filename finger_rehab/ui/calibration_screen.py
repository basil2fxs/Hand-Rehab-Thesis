"""Guided calibration, run from the menu before a session.

The therapist picks two things on the opening screen, then is walked
through only what they asked for and never has to open a terminal or
edit a config file:

    which hand      left or right. A profile describes one hand's pads,
                    so a bilateral rig is calibrated once per hand. The
                    choice is only offered when a second hand exists.
    which job       sensors, buzzers, or both.

The sensor job measures:

    1  hand off the device        gives the true zero and the noise level
    2  hand resting, no press     gives the tare point per finger
    3  each finger, light press   gives the resting-to-press gap
    4  all four together          gives the multi-finger deficit

The buzzer job buzzes one channel at a time and asks which finger felt
it, then saves the mapping so the game sends whichever channel actually
reaches the finger it means. That step exists because the firmware is
fixed: it maps STIM:1..4 onto its motor pins in a fixed order and is not
being reflashed, so if a motor is wired to a different pin the host has
to send a different channel instead.

The firmware on the device drives index D11, middle D10, ring D9 and
pinky D6, in finger order, so straight through is what it expects. The
earlier handover sketch drove D3 to D6 instead, which is why nothing
buzzed on this wiring: only the pinky pin overlapped at all.

Everything is measured from real samples off the device. Nothing here is
a guessed constant. The result is written to disk and stamped into every
session recorded afterwards, so an analysis months later can still say
exactly what a press meant on the day.

The two jobs save to different places and a run only writes the one it
measured, so calibrating the buzzers never disturbs the sensor
thresholds and calibrating the sensors never disturbs the channel map.
"""
from __future__ import annotations

import logging
import statistics
import time

import pygame

from .widgets import (
    Button, Layout, FONT_H2, FONT_BODY, FONT_SMALL, draw_text,
)
from ..hardware.calibration_profile import (
    CalibrationProfile, FINGER_NAMES, N_FINGERS, MIN_USABLE_GAP,
)


log = logging.getLogger(__name__)


def _percentile(values, q: float) -> float:
    """Linear-interpolated percentile. Used instead of max() so a single
    corrupt sample cannot define a press level."""
    xs = sorted(values)
    if not xs:
        return 0.0
    if len(xs) == 1:
        return float(xs[0])
    pos = q * (len(xs) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(xs) - 1)
    frac = pos - lo
    return float(xs[lo] * (1 - frac) + xs[hi] * frac)

# How long each measurement runs. The steady steps need long enough to
# average out sensor noise without the patient's hand drifting; the
# press steps need long enough to reach and hold a press but short
# enough that a weak hand is not fatigued by the end of calibration.
HOLD_SECONDS = 3.0
PRESS_SECONDS = 3.0

# The firmware holds each STIM for this long, set in the sketch as
# STIM_ON_MS and not changeable from the host.
FIRMWARE_STIM_MS = 150
# How long a test buzz should actually run. Long enough that an impaired
# hand registers it rather than reporting nothing felt.
BUZZ_TEST_MS = 600

# Ordered steps. Each press step names the finger it measures.
STEP_INTRO = "intro"
STEP_EMPTY = "empty"
STEP_RESTING = "resting"
STEP_PRESS = "press"
STEP_ALL = "all"
STEP_BUZZ = "buzz"
STEP_REVIEW = "review"

# What a run covers. Sensors and buzzers are independent jobs that save
# to different places, so either can be run on its own without touching
# the other's saved result.
JOB_SENSORS = "sensors"
JOB_BUZZERS = "buzzers"
JOB_BOTH = "both"

JOB_LABELS = {
    JOB_SENSORS: "sensors only",
    JOB_BUZZERS: "buzzers only",
    JOB_BOTH: "sensors and buzzers",
}


class CalibrationScreen:
    """Step-through calibration. Mouse only, same as the rest of the app."""

    def __init__(self, engine) -> None:
        self.engine = engine
        self.theme = engine.theme
        self.layout = engine.layout

        self.step = STEP_INTRO
        self.finger_idx = 0          # which finger the press step is on
        self.buzz_channel = 1        # which STIM channel the buzz step is on
        self.profile = CalibrationProfile()
        # Which hand is on the device right now. With two boards the sample
        # vector is [right 0..3, left 4..7], so reading the first four values
        # regardless of hand would measure the RIGHT board's idle sensors
        # while the patient presses with their left. That produces a profile
        # of near-zero gaps taken from a hand nobody touched, and applying it
        # would set every threshold from the wrong pads. The hand therefore
        # picks the slice, and each hand is calibrated in its own run.
        self.hand = self._default_hand()
        # What this run covers. Both by default, which is the first-time
        # case and what a full setup needs.
        self.job = JOB_BOTH
        # The saved profile for this hand, loaded when the run is not
        # measuring the sensors. It supplies the numbers the review shows
        # and makes plain that they are being kept, not re-measured.
        self._kept: CalibrationProfile | None = None
        # The menu's "what stays as it is" line is drawn every frame, and
        # it needs the saved profile's date. Cached per hand so that is
        # not a file read at 60 Hz.
        self._kept_cache_hand: str | None = None
        self._kept_cache: CalibrationProfile | None = None

        # Sample collection state.
        self._collecting = False
        self._collect_until = 0.0
        self._buffer: list[list[float]] = []
        self._status = ""
        self._status_colour = None

        # Buzzer discovery: felt[channel] = finger index that felt it.
        self._felt: dict[int, int] = {}

        self._buttons: list[Button] = []
        self._saved_path = None
        self._saved = False
        self._rebuild_buttons()

    # ---- what this run covers -------------------------------------------

    def _does(self, job: str) -> bool:
        return self.job in (job, JOB_BOTH)

    def _plan(self) -> list[str]:
        """The steps this run will walk through, in order. Drives both
        the transitions and the "Step 2 of 4" counter, so a shorter run
        never claims steps it is not going to ask for."""
        steps: list[str] = []
        if self._does(JOB_SENSORS):
            steps += [STEP_EMPTY, STEP_RESTING, STEP_PRESS, STEP_ALL]
        if self._does(JOB_BUZZERS):
            steps.append(STEP_BUZZ)
        return steps

    def _next_step(self, current: str) -> str:
        plan = self._plan()
        try:
            i = plan.index(current)
        except ValueError:
            return STEP_REVIEW
        return plan[i + 1] if i + 1 < len(plan) else STEP_REVIEW

    def _step_label(self, step: str) -> str:
        plan = self._plan()
        try:
            return f"Step {plan.index(step) + 1} of {len(plan)}"
        except ValueError:
            return ""

    # ---- which hand, and therefore which sensors ------------------------

    def _default_hand(self) -> str:
        try:
            hm = str(self.engine.cfg.get("bilateral.hand", "right") or "right")
        except Exception:
            hm = "right"
        # "both" is not a hand you can put on the pads. Start on the right and
        # let the therapist switch, so a bilateral rig is calibrated twice.
        return "left" if hm == "left" else "right"

    def _sensor_offset(self) -> int:
        """Where this hand's four sensors start in the sample vector."""
        if self.hand != "left":
            return 0
        try:
            n = int(self.engine.cfg.get("fsr.num_sensors_per_hand", 4))
        except (TypeError, ValueError):
            n = N_FINGERS
        return n

    def _pick_hand(self, hand: str) -> None:
        if hand == self.hand:
            return
        self.hand = hand
        # Anything already measured came off the other hand's pads.
        self._reset_measurements()
        self._rebuild_buttons()

    def _pick_job(self, job: str) -> None:
        if job == self.job:
            return
        self.job = job
        self._reset_measurements()
        self._rebuild_buttons()

    def _both_hands_possible(self) -> bool:
        """Whether there is a second hand to switch to.

        A bilateral rig has to be calibrated once per hand, because a profile
        describes one hand's pads. Without a way to switch, only the right
        hand could ever be measured and every left-hand press in the study
        would run on the right hand's thresholds.
        """
        try:
            if str(self.engine.cfg.get("bilateral.hand", "")) == "both":
                return True
            return len(self.engine.detectors or {}) > 1
        except Exception:
            return False

    # ---- sample intake -------------------------------------------------

    def on_sample(self, t_perf: float, values) -> None:
        """Called by the engine's sample pump for every sample, not once
        per frame. At 200 Hz that is roughly three times the frame rate,
        so averaging over a step sees every reading rather than a
        thin slice of them."""
        if not self._collecting:
            return
        off = self._sensor_offset()
        vals = list(values[off:off + N_FINGERS])
        while len(vals) < N_FINGERS:
            vals.append(0.0)
        self._buffer.append([float(v) for v in vals])

    def _start_collecting(self, seconds: float) -> None:
        self._buffer = []
        self._collecting = True
        self._collect_until = time.perf_counter() + seconds

    def _seconds_left(self) -> float:
        return max(0.0, self._collect_until - time.perf_counter())

    # ---- step machine --------------------------------------------------

    def update(self, dt: float) -> None:
        if self._collecting and self._seconds_left() <= 0:
            self._collecting = False
            self._finish_collection()
            self._rebuild_buttons()

    def _finish_collection(self) -> None:
        if not self._buffer:
            self._status = ("No samples arrived. Check the device is "
                            "connected, then try this step again.")
            self._status_colour = self.theme.error
            return
        cols = list(zip(*self._buffer))
        if self.step == STEP_EMPTY:
            self.profile.empty = [statistics.fmean(c) for c in cols]
            self.profile.empty_noise = [
                statistics.pstdev(c) if len(c) > 1 else 0.0 for c in cols]
            self._status = "Zero recorded."
            self._status_colour = self.theme.success
            self.step = STEP_RESTING
        elif self.step == STEP_RESTING:
            self.profile.resting = [statistics.fmean(c) for c in cols]
            self._status = "Resting level recorded."
            self._status_colour = self.theme.success
            self.step = STEP_PRESS
            self.finger_idx = 0
        elif self.step == STEP_PRESS:
            # Only this finger's peak is taken from this step. The other
            # sensors are moving too (that is enslavement, and the game
            # measures it per trial), but the threshold for THIS finger
            # comes from THIS finger.
            i = self.finger_idx
            # A high percentile, not the maximum. A single corrupt I2C frame
            # reading 800 counts would otherwise become the press level, and
            # a threshold derived from it is one the finger can never reach:
            # every trial on that finger would score a miss. The 95th
            # percentile of a held press sits on the plateau and ignores a
            # lone spike.
            self.profile.press[i] = _percentile(cols[i], 0.95)
            gap = self.profile.press[i] - self.profile.resting[i]
            if gap < MIN_USABLE_GAP:
                self._status = (
                    f"{FINGER_NAMES[i].title()} only moved {gap:.0f} counts. "
                    f"Press a little firmer and record it again.")
                self._status_colour = self.theme.warning
                return          # stay on this finger
            self._status = f"{FINGER_NAMES[i].title()} recorded, {gap:.0f} counts."
            self._status_colour = self.theme.success
            self.finger_idx += 1
            if self.finger_idx >= N_FINGERS:
                self.step = STEP_ALL
        elif self.step == STEP_ALL:
            self.profile.press_all = [_percentile(c, 0.95) for c in cols]
            self._status = "All-finger press recorded."
            self._status_colour = self.theme.success
            self.step = self._next_step(STEP_ALL)
            self.buzz_channel = 1
            self._felt = {}

    # ---- buzzer discovery ----------------------------------------------

    def _buzz_now(self) -> None:
        """Pulse the channel under test, long enough to be felt.

        triggerStimMotor sets an absolute deadline, stimOffAt = millis() +
        STIM_ON_MS, so commands sent back to back inside one 150 ms window
        all resolve to the same stop time and the motor runs ONCE. Repeats
        have to be spaced to actually extend the buzz. A patient with
        post-stroke sensory impairment can easily miss a single 150 ms
        pulse, and a missed pulse gets recorded as "felt nothing", which
        silently leaves that finger on the wrong channel.
        """
        sent = 0
        repeats = max(1, int(round(BUZZ_TEST_MS / FIRMWARE_STIM_MS)))
        for k in range(repeats):
            try:
                if self.engine.source.send_command(f"STIM:{self.buzz_channel}"):
                    sent += 1
            except Exception as e:
                log.warning("buzz test channel %d: %s", self.buzz_channel, e)
                break
            if k < repeats - 1:
                # Re-arm just before the firmware would switch the motor off.
                time.sleep((FIRMWARE_STIM_MS - 20) / 1000.0)
        if sent:
            self._status = (f"Channel {self.buzz_channel} pulsed. "
                            f"Which finger did you feel?")
            self._status_colour = self.theme.foreground
        else:
            self._status = ("Nothing was sent. Check the device is "
                            "connected on the Settings screen.")
            self._status_colour = self.theme.error

    def _record_felt(self, finger: int | None) -> None:
        if finger is not None:
            self._felt[self.buzz_channel] = finger
            self._status = (f"Channel {self.buzz_channel} drives the "
                            f"{FINGER_NAMES[finger]}.")
            self._status_colour = self.theme.success
        else:
            self._status = (f"Channel {self.buzz_channel} felt on no finger. "
                            f"That motor is probably not wired.")
            self._status_colour = self.theme.warning
        self.buzz_channel += 1
        if self.buzz_channel > N_FINGERS:
            self.step = STEP_REVIEW
        self._rebuild_buttons()

    def channel_map(self) -> list[int]:
        """Turn "channel C was felt on finger F" into "to buzz finger F,
        send channel C".

        The result must be a permutation: every finger on its own channel.
        Two things break that. A channel answered "felt nothing" leaves its
        finger on a straight-through default that another channel may already
        own, and the same finger named for two channels leaves the displaced
        channel unassigned. Either way two fingers end up sharing a channel,
        so cueing one buzzes the other and the patient presses the wrong
        finger while the data records it as their error.

        Confirmed answers win. Whatever is left over is filled from the
        unused channels, so the map is always a permutation even when the
        therapist could not identify every motor.
        """
        cmap: list[int | None] = [None] * N_FINGERS
        # Later answers win for a given channel, but a finger already
        # assigned is not overwritten: the first confirmed answer holds.
        for channel, finger in sorted(self._felt.items()):
            if 0 <= finger < N_FINGERS and cmap[finger] is None:
                cmap[finger] = channel
        used = {c for c in cmap if c is not None}
        spare = [c for c in range(1, N_FINGERS + 1) if c not in used]
        for i in range(N_FINGERS):
            if cmap[i] is None:
                cmap[i] = spare.pop(0) if spare else (i + 1)
        return [int(c) for c in cmap]

    def saved_channel_map(self) -> list[int]:
        """The buzzer map already in use, straight-through if there is
        none or the saved one is malformed. This is what a run that does
        not touch the buzzers leaves alone."""
        straight = list(range(1, N_FINGERS + 1))
        try:
            raw = self.engine.cfg.get("motor.channel_map", None)
        except Exception:
            return straight
        try:
            cmap = [int(c) for c in raw]
        except (TypeError, ValueError):
            return straight
        if sorted(cmap) != straight:
            return straight
        return cmap

    def effective_channel_map(self) -> list[int]:
        """What the game will send after this run: the newly discovered
        map when the buzzers were part of the job, the saved one
        otherwise."""
        if self._does(JOB_BUZZERS):
            return self.channel_map()
        return self.saved_channel_map()

    def unmapped_fingers(self) -> list[str]:
        """Fingers whose channel was never confirmed by feel. Shown on the
        review screen so a guessed mapping is never mistaken for a
        measured one."""
        confirmed = set(self._felt.values())
        return [FINGER_NAMES[i] for i in range(N_FINGERS)
                if i not in confirmed]

    # ---- saving ---------------------------------------------------------

    def _profile_path(self):
        return self.engine.cfg.calibration_path(
            f"current_{self.hand}.json")

    def _load_saved_profile(self) -> CalibrationProfile | None:
        """The profile already on disk for this hand, or None."""
        try:
            return CalibrationProfile.load(self._profile_path())
        except Exception as e:
            log.warning("could not read saved %s calibration: %s",
                        self.hand, e)
            return None

    def _saved_profile(self) -> CalibrationProfile | None:
        """Cached read of the saved profile for the current hand."""
        if self._kept_cache_hand != self.hand:
            self._kept_cache_hand = self.hand
            self._kept_cache = self._load_saved_profile()
        return self._kept_cache

    def _has_sensor_data(self) -> bool:
        """Whether the profile in hand carries real sensor measurements,
        taken this run or kept from the saved one."""
        return bool(any(self.profile.press) and any(self.profile.resting))

    def _save(self) -> None:
        """Write only what this run measured.

        The two jobs live in different files. Sensor thresholds are per
        hand and go to config/calibration/current_<hand>.json; the buzzer
        map is a config value the game reads at cue time. Writing both on
        every run would mean a buzzer-only visit blanked the thresholds
        with the zeros of a profile nobody measured, and a sensor-only
        visit reset the discovered map back to straight-through. Either
        one silently ruins the next session, so each is written only when
        it was actually measured.
        """
        cfg = self.engine.cfg
        wrote = []

        if self._does(JOB_BUZZERS):
            cmap = self.channel_map()
            cfg.data.setdefault("motor", {})["channel_map"] = cmap
            try:
                cfg.save_user_overrides({"motor.channel_map": cmap})
            except Exception as e:
                log.warning("could not persist channel map: %s", e)
                self._status = f"Could not save the buzzer map: {e}"
                self._status_colour = self.theme.error
                return
            wrote.append("buzzer map")

        if self._does(JOB_SENSORS):
            self.profile.participant = getattr(
                self.engine.session, "participant", "") or ""
            self.profile.hand = self.hand
            try:
                self.profile.device_port = str(
                    getattr(self.engine.source, "port", "") or "")
            except Exception:
                self.profile.device_port = ""
            try:
                # Per hand, so calibrating one hand never overwrites the
                # other's profile on a bilateral rig.
                path = self._profile_path()
                self.profile.save(path)
                # Keep a dated copy so a calibration is never silently lost
                # when the next one is taken.
                stamp = self.profile.created_at.replace(":", "").replace("-", "")
                self.profile.save(cfg.calibration_path(
                    f"history/{stamp}.json"))
                self._saved_path = path
            except OSError as e:
                log.warning("calibration save failed: %s", e)
                self._status = f"Could not save: {e}"
                self._status_colour = self.theme.error
                return
            # Hand it to the engine so detectors pick it up and every
            # session from now on records which calibration it ran under.
            # Only the thresholds go to the engine; they are never written
            # into the shared config, because a config value is read by
            # BOTH detectors when they are rebuilt.
            if hasattr(self.engine, "apply_calibration"):
                self.engine.apply_calibration(self.profile)
            wrote.append(f"{self.hand} hand thresholds")

        self._saved = True
        self._kept_cache_hand = None       # the file on disk just changed
        self._status = "Saved and applied: " + " and ".join(wrote) + "."
        self._status_colour = self.theme.success
        self._rebuild_buttons()

    # ---- buttons --------------------------------------------------------

    def _intro_geometry(self) -> dict:
        """Row positions for the opening menu.

        One source for both the labels drawn and the buttons hit-tested,
        so a control can never be clickable somewhere other than where it
        was drawn.
        """
        rows: dict[str, int] = {}
        y = 322
        if self._both_hands_possible():
            rows["hand_label"] = y
            rows["hand_buttons"] = y + 30
            y += 116
        rows["job_label"] = y
        rows["job_buttons"] = y + 30
        y += 116
        rows["summary"] = y
        rows["note"] = y + 26
        rows["start"] = y + 72
        return rows

    def _choice_button(self, rect: pygame.Rect, label: str, cb,
                       selected: bool) -> Button:
        """One option in a pick-one row. The chosen one is filled in the
        accent colour so the current setting is readable at a glance
        rather than having to be remembered."""
        return Button(rect, label, cb, self.theme, self.layout,
                      font_pt=FONT_BODY,
                      colour=self.theme.accent if selected else None)

    def _rebuild_buttons(self) -> None:
        th, ly = self.theme, self.layout
        self._buttons = []
        cx = ly.width // 2
        y = ly.height - 150

        def add(label, cb, x, w=260, primary=False, colour=None):
            self._buttons.append(Button(
                pygame.Rect(x - w // 2, y, w, 56), label, cb, th, ly,
                primary=primary, colour=colour))

        if self.step == STEP_INTRO:
            g = self._intro_geometry()
            if "hand_buttons" in g:
                for i, hand in enumerate(("left", "right")):
                    self._buttons.append(self._choice_button(
                        pygame.Rect(cx - 230 + i * 240, g["hand_buttons"],
                                    220, 56),
                        f"{hand.title()} hand",
                        (lambda h=hand: self._pick_hand(h)),
                        self.hand == hand))
            jobs = ((JOB_SENSORS, "Sensors only"),
                    (JOB_BUZZERS, "Buzzers only"),
                    (JOB_BOTH, "Both"))
            for i, (key, label) in enumerate(jobs):
                self._buttons.append(self._choice_button(
                    pygame.Rect(cx - 328 + i * 224, g["job_buttons"],
                                208, 56),
                    label, (lambda k=key: self._pick_job(k)),
                    self.job == key))
            self._buttons.append(Button(
                pygame.Rect(cx - 170, g["start"], 340, 64),
                "Start calibration", self._begin, th, ly, primary=True))
            # The gamified quick flow, one click away for a deliberate
            # redo without waiting for the next session gate. Sensors
            # only, so it is pointless without a force signal.
            if getattr(self.engine.source, "provides_samples", True):
                self._buttons.append(Button(
                    pygame.Rect(cx + 210, g["start"], 250, 64),
                    "Quick calibrate", self._quick_calibrate, th, ly))
        elif self.step in (STEP_EMPTY, STEP_RESTING, STEP_ALL):
            if not self._collecting:
                add("Record", lambda: self._start_collecting(
                    PRESS_SECONDS if self.step == STEP_ALL else HOLD_SECONDS),
                    cx, 260, primary=True)
        elif self.step == STEP_PRESS:
            if not self._collecting:
                add("Record", lambda: self._start_collecting(PRESS_SECONDS),
                    cx, 260, primary=True)
        elif self.step == STEP_BUZZ:
            add("Buzz this channel", self._buzz_now, cx - 300, 280,
                primary=True)
            # One button per finger, plus "felt nothing".
            bw = 150
            gap = 12
            total = N_FINGERS * bw + (N_FINGERS - 1) * gap
            x0 = cx + 120 - total // 2
            for i in range(N_FINGERS):
                self._buttons.append(Button(
                    pygame.Rect(x0 + i * (bw + gap), y, bw, 56),
                    FINGER_NAMES[i].title(),
                    (lambda f=i: self._record_felt(f)), th, ly,
                    colour=th.lane_active[i] if i < len(th.lane_active) else None))
            self._buttons.append(Button(
                pygame.Rect(cx + 120 - 90, y + 68, 180, 44),
                "Felt nothing", lambda: self._record_felt(None), th, ly,
                font_pt=FONT_SMALL + 2))
        elif self.step == STEP_REVIEW:
            if not self._saved:
                add("Save and use", self._save, cx - 160, 280, primary=True)
                add("Start over", self._to_menu, cx + 160, 240)
            else:
                add("Done", self.engine.show_title, cx, 260, primary=True)

        # Back is always available so nobody is trapped mid-flow.
        self._buttons.append(Button(
            pygame.Rect(40, ly.height - 80, 160, 48), "Back",
            self._back, th, ly, font_pt=FONT_SMALL + 4))

    def _reset_measurements(self) -> None:
        """Drop everything measured so far. Used when the hand or the job
        changes, since neither the samples nor the felt-channel answers
        carry over to a different hand or a different run."""
        self._abort_collection()
        self.profile = CalibrationProfile()
        self._kept = None
        self.finger_idx = 0
        self.buzz_channel = 1
        self._felt = {}
        self._saved_path = None
        self._saved = False
        self._status = ""
        self._status_colour = None

    def _begin(self) -> None:
        """Start the chosen run."""
        self._reset_measurements()
        # When the sensors are not part of this run, work from the saved
        # profile so the review shows the numbers the device will actually
        # keep running on rather than a table of zeros. A run that does
        # measure them starts fresh, so the new profile is stamped with
        # today's date instead of inheriting the old one's.
        if not self._does(JOB_SENSORS):
            kept = self._saved_profile()
            if kept is not None:
                self.profile = kept
                self._kept = kept
        self.step = self._plan()[0]
        self._rebuild_buttons()

    def _quick_calibrate(self) -> None:
        """Hand over to the gamified quick flow for the session's
        hands. It saves through the same profile path this screen
        uses, so coming back here afterwards shows its result."""
        if hasattr(self.engine, "show_quick_calibration"):
            self.engine.show_quick_calibration()

    def _to_menu(self) -> None:
        """Back to the opening menu with the same hand and job still
        picked, so redoing a run is one click."""
        self._reset_measurements()
        self.step = STEP_INTRO
        self._rebuild_buttons()

    def _abort_collection(self) -> None:
        """Throw away a part-finished measurement. Without this, leaving
        the screen mid-step leaves the timer running and the partial buffer
        intact, and the next visit's first update() writes those samples in
        as though the step had completed."""
        self._collecting = False
        self._collect_until = 0.0
        self._buffer = []

    def reset(self) -> None:
        """Put the screen back to its opening state. Called every time
        Calibrate is opened, so a second participant does not land on the
        previous participant's review table with only a Done button."""
        self._kept_cache_hand = None
        self.hand = self._default_hand()
        self.job = JOB_BOTH
        self._reset_measurements()
        self.step = STEP_INTRO
        self._rebuild_buttons()

    def _back(self) -> None:
        self._abort_collection()
        try:
            self.engine.stop_all_motors()
        except Exception:
            pass
        self.engine.show_title()

    # ---- event / draw ---------------------------------------------------

    def handle_event(self, e: pygame.event.Event) -> None:
        for b in self._buttons:
            b.handle_event(e)

    def _job_summary(self) -> str:
        return f"{self.hand.title()} hand  |  {JOB_LABELS[self.job]}"

    def _keep_note(self) -> str:
        """What this run will leave alone. Says it out loud on the menu so
        nobody avoids a quick buzzer check for fear of losing the sensor
        calibration."""
        if self.job == JOB_SENSORS:
            return "The buzzer channel map stays exactly as it is."
        if self.job == JOB_BUZZERS:
            saved = self._saved_profile()
            if saved is None:
                return (f"No sensor calibration is saved for the "
                        f"{self.hand} hand yet. Run the sensors when you can.")
            return (f"Sensor thresholds measured on "
                    f"{saved.created_at[:10]} stay exactly as they are.")
        return "Takes about a minute. The patient stays seated throughout."

    def _instruction(self) -> tuple[str, str]:
        """Heading and body for the current step."""
        if self.step == STEP_INTRO:
            return ("Set up the calibration",
                    "Pick the hand on the device and what needs measuring. "
                    "Each hand is measured separately, because the pads sit "
                    "differently on each.")
        if self.step == STEP_EMPTY:
            return (f"{self._step_label(STEP_EMPTY)}   Hand off the device",
                    "Take the hand right off, nothing touching any pad. "
                    "This reads the true zero and the noise level.")
        if self.step == STEP_RESTING:
            return (f"{self._step_label(STEP_RESTING)}   "
                    f"Hand resting, no press",
                    "Rest the hand in its normal position on the pads. "
                    "Do not press. This is the point every threshold "
                    "is measured from.")
        if self.step == STEP_PRESS:
            f = FINGER_NAMES[self.finger_idx].title()
            return (f"{self._step_label(STEP_PRESS)}   {f} finger, "
                    f"light press",
                    f"Press with the {f.lower()} finger only, as lightly as "
                    f"the patient can manage and still mean it. Hold until "
                    f"the timer runs out. Other fingers may move, that is "
                    f"fine and is measured separately.")
        if self.step == STEP_ALL:
            return (f"{self._step_label(STEP_ALL)}   "
                    f"All four fingers together",
                    "Press all four lightly at the same time and hold. "
                    "Comparing this against the single presses gives the "
                    "multi-finger deficit.")
        if self.step == STEP_BUZZ:
            return (f"{self._step_label(STEP_BUZZ)}   "
                    f"Buzzer channel {self.buzz_channel}",
                    "Press Buzz, then say which finger felt it. This learns "
                    "the wiring without changing the Arduino.")
        return ("Review", "Check these look sensible, then save.")

    def draw(self, surf: pygame.Surface) -> None:
        from .screens import _draw_header
        th, ly = self.theme, self.layout
        surf.fill(th.background)
        # The hand and the job ride along in the header, so what is about
        # to happen is on screen at every step and not only on the menu.
        _draw_header(surf, "Calibration", self._job_summary(), th, ly)

        head, body = self._instruction()
        cx = ly.width // 2
        draw_text(surf, head, (cx, 190), th, ly, pt=FONT_H2, centre=True)
        self._draw_wrapped(surf, body, cx, 232, ly.width - 260)

        if self.step == STEP_INTRO:
            self._draw_menu(surf)
        elif self.step == STEP_REVIEW:
            self._draw_review(surf)
        elif self._collecting:
            self._draw_timer(surf)
        else:
            self._draw_live(surf)

        # The menu carries its own summary line where the status would
        # otherwise land, so it is not drawn twice.
        if self._status and self.step != STEP_INTRO:
            self._draw_wrapped(surf, self._status, cx, ly.height - 205,
                               ly.width - 260,
                               colour=self._status_colour or th.muted)

        for b in self._buttons:
            b.draw(surf)

    def _draw_menu(self, surf) -> None:
        """Row labels and the plain-English summary for the opening
        menu. The buttons themselves come from _rebuild_buttons, off the
        same geometry."""
        th, ly = self.theme, self.layout
        cx = ly.width // 2
        g = self._intro_geometry()
        n = 1
        if "hand_label" in g:
            draw_text(surf, "1.  WHICH HAND", (cx, g["hand_label"]), th, ly,
                      pt=FONT_SMALL + 2, centre=True, colour=th.muted)
            n = 2
        draw_text(surf, f"{n}.  WHAT TO CALIBRATE", (cx, g["job_label"]),
                  th, ly, pt=FONT_SMALL + 2, centre=True, colour=th.muted)
        draw_text(surf, f"About to calibrate: {self._job_summary()}",
                  (cx, g["summary"]), th, ly, pt=FONT_BODY, centre=True,
                  colour=th.foreground)
        self._draw_wrapped(surf, self._keep_note(), cx, g["note"],
                           ly.width - 300, pt=FONT_SMALL + 2)

    def _draw_wrapped(self, surf, text, cx, y, max_w, colour=None,
                      pt=FONT_BODY) -> int:
        font = self.layout.font(pt)
        words, line, lines = text.split(), "", []
        for w in words:
            trial = f"{line} {w}".strip()
            if font.size(trial)[0] > max_w and line:
                lines.append(line)
                line = w
            else:
                line = trial
        if line:
            lines.append(line)
        for i, ln in enumerate(lines):
            draw_text(surf, ln, (cx, y + i * (pt + 8)), self.theme,
                      self.layout, pt=pt, centre=True,
                      colour=colour or self.theme.muted)
        return y + len(lines) * (pt + 8)

    def _draw_timer(self, surf) -> None:
        th, ly = self.theme, self.layout
        left = self._seconds_left()
        cx, cy = ly.width // 2, 400
        pygame.draw.circle(surf, th.accent, (cx, cy), 76, 5)
        draw_text(surf, f"{left:.1f}", (cx, cy), th, ly,
                  pt=FONT_H2 + 14, centre=True, colour=th.accent)
        draw_text(surf, f"{len(self._buffer)} samples", (cx, cy + 100),
                  th, ly, pt=FONT_SMALL, centre=True, colour=th.muted)

    def _draw_live(self, surf) -> None:
        """Current reading per finger, so the therapist can see the
        device is alive before committing to a measurement."""
        th, ly = self.theme, self.layout
        det = None
        try:
            det = self.engine.detectors.get(self.hand)
        except Exception:
            det = None
        cx = ly.width // 2
        bw, gap = 150, 16
        total = N_FINGERS * bw + (N_FINGERS - 1) * gap
        x0 = cx - total // 2
        for i in range(N_FINGERS):
            r = pygame.Rect(x0 + i * (bw + gap), 330, bw, 120)
            fill = (th.lane_idle[i] if i < len(th.lane_idle)
                    else th.muted)
            # Highlight the finger this step is actually measuring.
            if self.step == STEP_PRESS and i == self.finger_idx:
                fill = (th.lane_active[i] if i < len(th.lane_active) else fill)
            pygame.draw.rect(surf, fill, r, border_radius=14)
            lum = 0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]
            fg = (255, 255, 255) if lum < 140 else (15, 23, 42)
            draw_text(surf, FINGER_NAMES[i].title(), (r.centerx, r.y + 26),
                      th, ly, pt=FONT_SMALL + 2, centre=True, colour=fg)
            val = "n/a"
            if det is not None and i < len(det.last_value):
                v = det.val_ema[i]
                if v is None:
                    v = det.last_value[i]
                if v is not None:
                    val = f"{v:.0f}"
            draw_text(surf, val, (r.centerx, r.centery + 18), th, ly,
                      pt=FONT_H2, centre=True, colour=fg)

    def _draw_review(self, surf) -> None:
        th, ly = self.theme, self.layout
        cmap = self.effective_channel_map()
        y = 270

        if not self._has_sensor_data():
            # A buzzer-only run on a hand that has never had its sensors
            # measured. Say so plainly rather than showing a table of
            # zeros that looks like a broken measurement.
            self._draw_wrapped(
                surf,
                f"Buzzer map only. Channels for index to pinky: "
                f"{', '.join(str(c) for c in cmap)}.",
                ly.width // 2, y, ly.width - 300, colour=th.foreground)
            self._draw_wrapped(
                surf,
                f"No sensor calibration is saved for the {self.hand} hand, "
                f"so presses will run on the config defaults. Run the "
                f"sensor calibration before recording a session.",
                ly.width // 2, y + 60, ly.width - 300, colour=th.warning,
                pt=FONT_SMALL + 2)
            return

        ok, problems = self.profile.usable()
        gaps = self.profile.gap()
        pre = self.profile.preload()
        on_d = self.profile.on_delta()

        x = 150
        draw_text(surf, "Finger", (x, y), th, ly, pt=FONT_SMALL,
                  colour=th.muted)
        for j, h in enumerate(("Rest load", "Press gap", "Trigger",
                               "Buzz channel")):
            draw_text(surf, h, (x + 220 + j * 170, y), th, ly,
                      pt=FONT_SMALL, colour=th.muted)
        for i in range(N_FINGERS):
            ry = y + 34 + i * 40
            colour = (th.lane_active[i] if i < len(th.lane_active)
                      else th.foreground)
            draw_text(surf, FINGER_NAMES[i].title(), (x, ry), th, ly,
                      pt=FONT_BODY, colour=colour)
            cells = [f"{pre[i]:.0f}", f"{gaps[i]:.0f}", f"{on_d[i]}",
                     str(cmap[i])]
            for j, c in enumerate(cells):
                warn = (j == 1 and gaps[i] < 10)
                draw_text(surf, c, (x + 220 + j * 170, ry), th, ly,
                          pt=FONT_BODY,
                          colour=th.error if warn else th.foreground)

        # Say which columns came from this run and which are being kept,
        # so a number on this table is never mistaken for a fresh
        # measurement it is not.
        notes = []
        if not self._does(JOB_SENSORS):
            notes.append(f"thresholds kept from "
                         f"{self.profile.created_at[:10]}")
        if not self._does(JOB_BUZZERS):
            notes.append("buzzer map kept as saved")
        below = y + 34 + N_FINGERS * 40 + 16
        if notes:
            draw_text(surf, "Not measured this run: " + ", ".join(notes),
                      (ly.width // 2, below), th, ly, pt=FONT_SMALL + 2,
                      centre=True, colour=th.muted)
            below += 26

        deficit = self.profile.multi_finger_deficit()
        if deficit is not None:
            draw_text(
                surf,
                f"Multi-finger deficit: {deficit * 100:.0f}% "
                f"(force lost when all four press together)",
                (ly.width // 2, below), th, ly,
                pt=FONT_SMALL + 2, centre=True, colour=th.muted)
            below += 26

        if not ok:
            self._draw_wrapped(surf, problems[0], ly.width // 2, below + 6,
                               ly.width - 300, colour=th.warning,
                               pt=FONT_SMALL + 2)
