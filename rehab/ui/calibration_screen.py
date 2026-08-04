"""Guided calibration, run from the menu before a session.

The therapist is walked through a short sequence and never has to open a
terminal or edit a config file:

    1  hand off the device        gives the true zero and the noise level
    2  hand resting, no press     gives the tare point per finger
    3  each finger, light press    gives the resting-to-press gap
    4  all four together           gives the multi-finger deficit
    5  buzzers, one channel at a   learns which STIM channel reaches
       time (optional)             which finger

Everything is measured from real samples off the device. Nothing here is
a guessed constant. The result is written to disk and stamped into every
session recorded afterwards, so an analysis months later can still say
exactly what a press meant on the day.

Step 5 exists because the firmware is fixed. Arduino_20251111.ino maps
STIM:1..4 onto pins 3,4,5,6 in that order, and it is not being
reflashed. If a motor is wired to a different pin than that order
assumes, the wrong finger buzzes. Instead of changing the sketch, this
step buzzes one channel at a time and asks which finger felt it, then
saves the mapping so the game sends whichever channel actually reaches
the finger it means.
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
        self._rebuild_buttons()

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

    def _toggle_hand(self) -> None:
        self.hand = "left" if self.hand == "right" else "right"
        self._begin()
        self.step = STEP_INTRO
        self._status = f"Calibrating the {self.hand} hand."
        self._status_colour = self.theme.foreground
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
            self.step = STEP_BUZZ
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

    def unmapped_fingers(self) -> list[str]:
        """Fingers whose channel was never confirmed by feel. Shown on the
        review screen so a guessed mapping is never mistaken for a
        measured one."""
        confirmed = set(self._felt.values())
        return [FINGER_NAMES[i] for i in range(N_FINGERS)
                if i not in confirmed]

    # ---- saving ---------------------------------------------------------

    def _save(self) -> None:
        cfg = self.engine.cfg
        self.profile.participant = getattr(
            self.engine.session, "participant", "") or ""
        self.profile.hand = self.hand
        try:
            self.profile.device_port = str(
                getattr(self.engine.source, "port", "") or "")
        except Exception:
            self.profile.device_port = ""

        on_d = self.profile.on_delta()
        off_d = self.profile.off_delta()
        cmap = self.channel_map()

        try:
            # Per hand, so calibrating one hand never overwrites the
            # other's profile on a bilateral rig.
            path = cfg.resolve_path(
                f"config/calibration/current_{self.profile.hand}.json")
            self.profile.save(path)
            # Keep a dated copy so a calibration is never silently lost
            # when the next one is taken.
            stamp = self.profile.created_at.replace(":", "").replace("-", "")
            self.profile.save(cfg.resolve_path(
                f"config/calibration/history/{stamp}.json"))
            self._saved_path = path
        except OSError as e:
            log.warning("calibration save failed: %s", e)
            self._status = f"Could not save: {e}"
            self._status_colour = self.theme.error
            return

        # Push into the live config so the very next block uses it, and
        # persist so it survives a restart.
        # Only the buzzer map goes into the shared config. The force
        # thresholds are per hand and are held on the engine instead, because
        # a config value is read by BOTH detectors when they are rebuilt.
        cfg.data.setdefault("motor", {})["channel_map"] = cmap
        try:
            cfg.save_user_overrides({"motor.channel_map": cmap})
        except Exception as e:
            log.warning("could not persist calibration to settings: %s", e)

        # Hand it to the engine so detectors pick it up and every
        # session from now on records which calibration it ran under.
        if hasattr(self.engine, "apply_calibration"):
            self.engine.apply_calibration(self.profile)

        self._status = "Calibration saved and applied."
        self._status_colour = self.theme.success
        self._rebuild_buttons()

    # ---- buttons --------------------------------------------------------

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
            if self._both_hands_possible():
                add("Start calibration", self._begin, cx - 180, 300,
                    primary=True)
                other = "left" if self.hand == "right" else "right"
                add(f"Switch to {other} hand", self._toggle_hand, cx + 190,
                    260)
            else:
                add("Start calibration", self._begin, cx, 300, primary=True)
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
            if self._saved_path is None:
                add("Save and use", self._save, cx - 160, 280, primary=True)
                add("Start over", self._begin, cx + 160, 240)
            else:
                add("Done", self.engine.show_title, cx, 260, primary=True)

        # Back is always available so nobody is trapped mid-flow.
        self._buttons.append(Button(
            pygame.Rect(40, ly.height - 80, 160, 48), "Back",
            self._back, th, ly, font_pt=FONT_SMALL + 4))

    def _begin(self) -> None:
        self.profile = CalibrationProfile()
        self.step = STEP_EMPTY
        self.finger_idx = 0
        self.buzz_channel = 1
        self._felt = {}
        self._saved_path = None
        self._status = ""
        self._status_colour = None
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
        self._abort_collection()
        self.hand = self._default_hand()
        self._begin()
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

    def _instruction(self) -> tuple[str, str]:
        """Heading and body for the current step."""
        if self.step == STEP_INTRO:
            return (f"Before you start   ({self.hand} hand)",
                    "This measures what a press means on this device today. "
                    "It takes about a minute and the patient stays seated. "
                    "Each hand is measured separately, because the pads sit "
                    "differently on each.")
        if self.step == STEP_EMPTY:
            return ("Step 1 of 5   Hand off the device",
                    "Take the hand right off, nothing touching any pad. "
                    "This reads the true zero and the noise level.")
        if self.step == STEP_RESTING:
            return ("Step 2 of 5   Hand resting, no press",
                    "Rest the hand in its normal position on the pads. "
                    "Do not press. This is the point every threshold "
                    "is measured from.")
        if self.step == STEP_PRESS:
            f = FINGER_NAMES[self.finger_idx].title()
            return (f"Step 3 of 5   {f} finger, light press",
                    f"Press with the {f.lower()} finger only, as lightly as "
                    f"the patient can manage and still mean it. Hold until "
                    f"the timer runs out. Other fingers may move, that is "
                    f"fine and is measured separately.")
        if self.step == STEP_ALL:
            return ("Step 4 of 5   All four fingers together",
                    "Press all four lightly at the same time and hold. "
                    "Comparing this against the single presses gives the "
                    "multi-finger deficit.")
        if self.step == STEP_BUZZ:
            return (f"Step 5 of 5   Buzzer channel {self.buzz_channel}",
                    "Press Buzz, then say which finger felt it. This learns "
                    "the wiring without changing the Arduino.")
        return ("Review", "Check these look sensible, then save.")

    def draw(self, surf: pygame.Surface) -> None:
        from .screens import _draw_header
        th, ly = self.theme, self.layout
        surf.fill(th.background)
        _draw_header(surf, "Calibration", "", th, ly)

        head, body = self._instruction()
        cx = ly.width // 2
        draw_text(surf, head, (cx, 170), th, ly, pt=FONT_H2, centre=True)
        self._draw_wrapped(surf, body, cx, 212, ly.width - 260)

        if self.step == STEP_REVIEW:
            self._draw_review(surf)
        elif self._collecting:
            self._draw_timer(surf)
        elif self.step != STEP_INTRO:
            self._draw_live(surf)

        if self._status:
            self._draw_wrapped(surf, self._status, cx, ly.height - 205,
                               ly.width - 260,
                               colour=self._status_colour or th.muted)

        for b in self._buttons:
            b.draw(surf)

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
        ok, problems = self.profile.usable()
        gaps = self.profile.gap()
        pre = self.profile.preload()
        on_d = self.profile.on_delta()
        cmap = self.channel_map()

        x = 150
        y = 270
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

        deficit = self.profile.multi_finger_deficit()
        if deficit is not None:
            draw_text(
                surf,
                f"Multi-finger deficit: {deficit * 100:.0f}% "
                f"(force lost when all four press together)",
                (ly.width // 2, y + 34 + N_FINGERS * 40 + 20), th, ly,
                pt=FONT_SMALL + 2, centre=True, colour=th.muted)

        if not ok:
            self._draw_wrapped(surf, problems[0], ly.width // 2,
                               y + 34 + N_FINGERS * 40 + 48,
                               ly.width - 300, colour=th.warning,
                               pt=FONT_SMALL + 2)
