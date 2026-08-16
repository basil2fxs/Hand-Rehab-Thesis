"""Quick calibration, run automatically after the hand pick the first
time a session needs a hand.

Why this exists. The clinical CalibrationScreen on the menu is right
for a therapist doing a deliberate measurement, but it is the wrong
first minute for a new player: nothing on it says how hard a press is
meant to be, and a session started without any profile runs on config
defaults measured on a different hand. This screen closes both gaps at
once: it collects the exact same three captures the clinical flow
collects (empty, resting, a light press per finger), and it teaches
the light press by making the capture itself the game. The player
presses a big vertical bar into a glowing band and holds it there; the
level they hold IS the light press the profile stores, so the press
they just learned is the press every mode will score.

What it deliberately is not: a fork of the threshold maths. Every
number saved here goes through CalibrationProfile, the same class the
clinical screen fills in, saved to the same per-hand file and applied
through the same engine.apply_calibration path. If the threshold rules
ever change, both flows change together.

Flow, kept under a minute per hand:

    hands off      one short capture, gives zero + noise
    hands resting  one short capture, gives the tare point
    per finger     press the bar into the band, hold to fill, pop
    summary        one kind line per finger, then straight to the game

Both rest captures cover EVERY hand in the run at once: with two
boards all eight sensors ride in the same sample vector, so a
bilateral run pays the waiting cost once, not twice. Only the
per-finger game repeats per hand, left hand first, matching the lane
strips which put the left hand on the left of the screen.

The skip rules mirror the rest of the app. A keyboard session never
sees this screen at all (there is no force to calibrate, and the game
notice for that lives on mode select, not here). Calibration is a
session event: each hand runs the flow once, the first time a game in
the session needs it, and every later game in that session skips it,
hand-mode changes included; the trigger decision is the engine's, in
maybe_start_quick_calibration, with the per-session memory held on
the engine and cleared when the session ends. "Skip for now" is
always on screen and leaves whatever profile was saved before
completely untouched. Esc asks before abandoning, so a stray key
cannot throw away a half-done run.

Flash safety: the in-zone glow is state-driven (on while the press sits
in the band), the completion pop is a one-shot, and nothing else
repeats, so nothing here flashes at any rate, let alone above 3 Hz.
Screen conventions match the rest of the app: 1280x800 logical layout,
theme-aware, Esc handled through the engine's global event path.
"""
from __future__ import annotations

import logging
import statistics
import time
from typing import TYPE_CHECKING, Callable

import pygame

from .screens import Screen, _draw_header
from .widgets import (
    Button, FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL, FONT_TITLE,
    draw_text,
)
from .calibration_screen import _percentile
from ..hardware.calibration_profile import (
    CalibrationProfile, FINGER_NAMES, MIN_USABLE_GAP, N_FINGERS,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine

log = logging.getLogger(__name__)

PHASE_OFF = "hands_off"
PHASE_REST = "resting"
PHASE_PRESS = "press"
PHASE_DONE = "done"

# How long the completion pop and the GOT IT! text stay up before the
# next finger takes over. Long enough to feel like a reward, short
# enough that eight fingers still finish inside a minute.
POP_S = 0.7

# Bar geometry. One big bar in the middle of the screen; everything
# else (instruction above, tick row below) keys off these.
BAR_W = 150
BAR_TOP = 250
BAR_BOTTOM = 640


class QuickCalibrationScreen(Screen):
    """Gamified light-press capture. Fills a CalibrationProfile per
    hand through play, then saves and applies it exactly as the
    clinical screen would."""

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.hands: list[str] = ["right"]
        self._continue: Callable[[], None] | None = None
        self.phase = PHASE_OFF

        # Captures per hand, raw counts, same shape the clinical flow
        # measures. press starts at zeros and is filled one finger at
        # a time by the bar game.
        self._captures: dict[str, dict[str, list[float]]] = {}

        # Rest-capture state (hands off / hands resting). The buffer
        # holds one row of four values per hand per sample.
        self._collecting = False
        self._collect_until = 0.0
        self._rest_buffers: dict[str, list[list[float]]] = {}

        # Press-game state.
        self._hand_idx = 0
        self._finger_idx = 0
        self._hold = 0.0               # 0..1 fill of the hold meter
        self._in_zone = False
        self._zone_buffer: list[float] = []
        self._landed = False           # this finger's press captured
        self._advance_at = 0.0         # when to move to the next finger
        self._pop_at = 0.0             # when the completion pop started
        self._started_finger_at = 0.0  # for the struggling-finger hint

        # Built once the whole run has captured, so the summary and the
        # save button work off the same objects.
        self._profiles: dict[str, CalibrationProfile] = {}
        self._problems: list[str] = []

        self._confirm = False          # Esc guard overlay
        self._dim_cache: pygame.Surface | None = None

        self._status = ""
        self._buttons: list[Button] = []
        self._confirm_buttons: list[Button] = []
        self._rebuild_buttons()

    # ---- tunables --------------------------------------------------------

    def _cfgf(self, key: str, default: float) -> float:
        try:
            return float(self.engine.cfg.get(f"quick_cal.{key}", default))
        except (TypeError, ValueError):
            return default

    def _rest_capture_s(self) -> float:
        return max(0.5, self._cfgf("rest_capture_s", 2.0))

    def _hold_s(self) -> float:
        return max(0.3, self._cfgf("hold_s", 1.0))

    def _zone_lo(self) -> float:
        # Floored just above MIN_USABLE_GAP so a press held anywhere in
        # the band gives a gap the profile maths will accept, and the
        # "press a touch firmer" retry below almost never fires.
        return max(float(MIN_USABLE_GAP) + 4.0,
                   self._cfgf("zone_min_counts", 24.0))

    def _zone_hi(self) -> float:
        return max(self._zone_lo() + 20.0,
                   self._cfgf("zone_max_counts", 110.0))

    def _bar_max(self) -> float:
        # Headroom above the band so a press that overshoots visibly
        # climbs out of the glow instead of pinning at the top.
        return self._zone_hi() * 1.4

    # ---- entry -----------------------------------------------------------

    def begin(self, hands: list[str],
              continue_cb: Callable[[], None] | None = None) -> None:
        """Start a run over the given hands. continue_cb is what
        happens when the run finishes or is skipped; the engine passes
        the block start when the flow gates a session, and the menu
        passes nothing, which lands back on the title."""
        wanted = [h for h in hands if h in ("left", "right")]
        # Left first: the lane strips put the left hand on the left of
        # the screen, so the flow reads in the same order the lanes do.
        self.hands = (sorted(set(wanted), key=lambda h: h != "left")
                      or ["right"])
        self._continue = continue_cb or self.engine.show_title
        self._captures = {
            h: {"empty": [0.0] * N_FINGERS,
                "empty_noise": [0.0] * N_FINGERS,
                "resting": [0.0] * N_FINGERS,
                "press": [0.0] * N_FINGERS}
            for h in self.hands
        }
        self.phase = PHASE_OFF
        self._collecting = False
        self._rest_buffers = {}
        self._hand_idx = 0
        self._finger_idx = 0
        self._reset_finger_state()
        self._profiles = {}
        self._problems = []
        self._confirm = False
        self._status = ""
        self._rebuild_buttons()

    def _reset_finger_state(self) -> None:
        self._hold = 0.0
        self._in_zone = False
        self._zone_buffer = []
        self._landed = False
        self._advance_at = 0.0
        self._pop_at = 0.0
        self._started_finger_at = time.perf_counter()

    # ---- who is being measured ------------------------------------------

    def _current_hand(self) -> str:
        return self.hands[min(self._hand_idx, len(self.hands) - 1)]

    def _finger_no(self) -> tuple[int, int]:
        """1-based (current, total) across the whole run, for the
        "Finger 3 of 8" counter."""
        return (self._hand_idx * N_FINGERS + self._finger_idx + 1,
                len(self.hands) * N_FINGERS)

    def _hand_slice(self, values, hand: str) -> list[float]:
        """One hand's four raw values out of the sample vector.

        Mirrors _feed_detectors' rule exactly: an 8-value sample is
        right then left, and a short sample in a left-only session IS
        the left board. Slicing right-first here regardless would
        measure the idle right board while the player presses with
        their left, the same fault the clinical screen documents.
        """
        try:
            n = int(self.engine.cfg.get("fsr.num_sensors_per_hand", 4))
        except (TypeError, ValueError):
            n = N_FINGERS
        vals = list(values)
        if hand == "left":
            if self.engine.hand_mode == "left" and len(vals) < n * 2:
                sl = vals[:n]
            else:
                sl = vals[n:n * 2]
        else:
            sl = vals[:n]
        out = [float(v) for v in sl[:N_FINGERS]]
        while len(out) < N_FINGERS:
            out.append(0.0)
        return out

    def _live_counts(self) -> float:
        """The current finger's smoothed reading above its captured
        resting level. This is the bar's height and the in-zone test,
        read from the same detector value the game itself scores on."""
        hand = self._current_hand()
        det = (self.engine.detectors or {}).get(hand)
        if det is None:
            return 0.0
        i = self._finger_idx
        try:
            v = det.val_ema[i]
            if v is None:
                v = float(det.last_value[i])
        except (AttributeError, IndexError, TypeError):
            return 0.0
        rest = self._captures[hand]["resting"][i]
        return float(v) - rest

    # ---- sample intake ---------------------------------------------------

    def on_sample(self, t_perf: float, values) -> None:
        """Every sample off the device, pushed by the engine's pump,
        exactly as the clinical screen receives them. Rest captures
        buffer all hands at once; the press game buffers only the
        current finger, and only while the press sits in the band, so
        the 95th percentile lands on the held plateau."""
        if self._confirm:
            return
        if self._collecting and self.phase in (PHASE_OFF, PHASE_REST):
            for hand in self.hands:
                self._rest_buffers.setdefault(hand, []).append(
                    self._hand_slice(values, hand))
        elif (self.phase == PHASE_PRESS and self._in_zone
                and not self._landed):
            hand = self._current_hand()
            self._zone_buffer.append(
                self._hand_slice(values, hand)[self._finger_idx])

    def _start_collecting(self) -> None:
        self._rest_buffers = {}
        self._collecting = True
        self._collect_until = time.perf_counter() + self._rest_capture_s()
        self._rebuild_buttons()

    def _seconds_left(self) -> float:
        return max(0.0, self._collect_until - time.perf_counter())

    # ---- flow ------------------------------------------------------------

    def update(self, dt: float) -> None:
        if self._confirm:
            return
        if self._collecting and self._seconds_left() <= 0:
            self._collecting = False
            self._finish_rest_capture()
            self._rebuild_buttons()
            return
        if self.phase == PHASE_PRESS:
            self._update_press_game(dt)

    def _finish_rest_capture(self) -> None:
        empty_step = self.phase == PHASE_OFF
        for hand in self.hands:
            rows = self._rest_buffers.get(hand) or []
            if not rows:
                self._status = ("No samples arrived. Check the device on "
                                "the Settings screen, then try again.")
                return
            cols = list(zip(*rows))
            cap = self._captures[hand]
            if empty_step:
                # Same reduction the clinical flow uses: mean for the
                # level, population SD for the noise floor.
                cap["empty"] = [statistics.fmean(c) for c in cols]
                cap["empty_noise"] = [
                    statistics.pstdev(c) if len(c) > 1 else 0.0
                    for c in cols]
            else:
                cap["resting"] = [statistics.fmean(c) for c in cols]
        self._status = ""
        if empty_step:
            self.phase = PHASE_REST
        else:
            self.phase = PHASE_PRESS
            self._hand_idx = 0
            self._finger_idx = 0
            self._reset_finger_state()

    def _update_press_game(self, dt: float) -> None:
        now = time.perf_counter()
        if self._landed:
            if now >= self._advance_at:
                self._advance_finger()
            return
        live = self._live_counts()
        self._in_zone = self._zone_lo() <= live <= self._zone_hi()
        if self._in_zone:
            self._hold = min(1.0, self._hold + dt / self._hold_s())
        else:
            # Drain rather than reset: a wobble out of the band costs a
            # moment, not the whole hold. A drained meter also clears
            # the buffer so a stale plateau cannot leak into the next
            # attempt's percentile.
            self._hold = max(0.0, self._hold - dt / (self._hold_s() * 0.6))
            if self._hold <= 0.0:
                self._zone_buffer = []
        if self._hold >= 1.0 and self._zone_buffer:
            self._capture_press()

    def _capture_press(self) -> None:
        hand = self._current_hand()
        i = self._finger_idx
        # 95th percentile of the held plateau, the same statistic the
        # clinical flow takes, for the same reason: one corrupt frame
        # must not become the press level.
        press = _percentile(self._zone_buffer, 0.95)
        gap = press - self._captures[hand]["resting"][i]
        if gap < MIN_USABLE_GAP:
            # The band floor makes this nearly unreachable, but a noisy
            # buffer can still land short. Ask again rather than saving
            # a threshold that cannot both trigger and release.
            self._status = "Almost! Press a touch firmer this time."
            self._hold = 0.0
            self._zone_buffer = []
            return
        self._captures[hand]["press"][i] = press
        self._status = ""
        self._landed = True
        now = time.perf_counter()
        self._pop_at = now
        self._advance_at = now + POP_S

    def _advance_finger(self) -> None:
        self._finger_idx += 1
        if self._finger_idx >= N_FINGERS:
            self._finger_idx = 0
            self._hand_idx += 1
            if self._hand_idx >= len(self.hands):
                self._enter_summary()
                return
        self._reset_finger_state()

    def _enter_summary(self) -> None:
        """Build one CalibrationProfile per hand from the captures.
        Built here, once, so the summary text and the save button work
        off the same objects and the same usable() verdict."""
        self.phase = PHASE_DONE
        self._profiles = {}
        self._problems = []
        for hand in self.hands:
            cap = self._captures[hand]
            prof = CalibrationProfile(
                hand=hand,
                participant=getattr(self.engine.session, "participant",
                                    "") or "",
                empty=list(cap["empty"]),
                empty_noise=list(cap["empty_noise"]),
                resting=list(cap["resting"]),
                press=list(cap["press"]),
            )
            try:
                prof.device_port = str(
                    getattr(self.engine.source, "port", "") or "")
            except Exception:
                prof.device_port = ""
            self._profiles[hand] = prof
            ok, problems = prof.usable()
            if not ok:
                self._problems.extend(problems)
        self._rebuild_buttons()

    # ---- finish / skip / abandon ----------------------------------------

    def _finish(self) -> None:
        """Save every hand's profile through the same path the clinical
        screen uses, apply through the engine, then hand over to
        whatever the run was gating."""
        cfg = self.engine.cfg
        for hand, prof in self._profiles.items():
            try:
                path = cfg.resolve_path(
                    f"config/calibration/current_{hand}.json")
                prof.save(path)
                # Dated copy, same convention as the clinical save, so
                # a quick calibration never silently destroys the one
                # before it.
                stamp = prof.created_at.replace(":", "").replace("-", "")
                prof.save(cfg.resolve_path(
                    f"config/calibration/history/{stamp}.json"))
            except OSError as e:
                log.warning("quick calibration save failed for %s: %s",
                            hand, e)
                self._status = f"Could not save: {e}"
                return
            self.engine.apply_calibration(prof)
        log.info("quick calibration saved and applied for %s",
                 ", ".join(self._profiles))
        self._go_on()

    def _skip(self) -> None:
        """Proceed without measuring. Anything saved earlier stays
        exactly as it was; the session runs on whatever thresholds are
        already applied. Deliberate escape hatch for a hurried
        clinician, so it must never write anything."""
        log.info("quick calibration skipped")
        self._go_on()

    def _go_on(self) -> None:
        cb = self._continue or self.engine.show_title
        self._continue = None
        cb()

    def _retry(self) -> None:
        self.begin(list(self.hands), self._continue)

    def on_escape(self) -> None:
        """Esc asks before abandoning. First Esc raises the guard,
        Esc again (or the Stop button) confirms; Keep going lowers it.
        Abandoning discards the run and lands where the player came
        from: game select mid-session (the flow gated a game start),
        the login screen otherwise (a menu launch before any login)."""
        if self._confirm:
            self._abandon()
        else:
            self._confirm = True
            self._rebuild_buttons()

    def _keep_going(self) -> None:
        self._confirm = False
        self._rebuild_buttons()

    def _abandon(self) -> None:
        self._confirm = False
        self._continue = None
        if getattr(self.engine, "_session_active", False):
            self.engine.show_mode_select()
        else:
            self.engine.show_title()

    # ---- buttons ---------------------------------------------------------

    def _rebuild_buttons(self) -> None:
        th, ly = self.theme, self.layout
        cx = ly.width // 2
        self._buttons = []
        self._confirm_buttons = []
        if self._confirm:
            y = ly.height // 2 + 40
            self._confirm_buttons = [
                Button(pygame.Rect(cx - 250, y, 230, 56), "Keep going",
                       self._keep_going, th, ly, primary=True),
                Button(pygame.Rect(cx + 20, y, 230, 56), "Stop",
                       self._abandon, th, ly),
            ]
            return
        if self.phase == PHASE_OFF and not self._collecting:
            self._buttons.append(Button(
                pygame.Rect(cx - 170, 560, 340, 64), "Hands off, ready",
                self._start_collecting, th, ly, primary=True))
        elif self.phase == PHASE_REST and not self._collecting:
            label = ("Hands resting, go" if len(self.hands) > 1
                     else "Hand resting, go")
            self._buttons.append(Button(
                pygame.Rect(cx - 170, 560, 340, 64), label,
                self._start_collecting, th, ly, primary=True))
        elif self.phase == PHASE_DONE:
            if self._problems:
                self._buttons.append(Button(
                    pygame.Rect(cx - 170, ly.height - 130, 340, 64),
                    "Try again", self._retry, th, ly, primary=True))
            else:
                self._buttons.append(Button(
                    pygame.Rect(cx - 170, ly.height - 130, 340, 64),
                    "Let's play", self._finish, th, ly, primary=True))
        # Skip is small and out of the way, but always there: keyboard
        # hands, a hurried clinician, a flaky sensor. It never writes.
        self._buttons.append(Button(
            pygame.Rect(ly.width - 220, ly.height - 70, 180, 48),
            "Skip for now", self._skip, th, ly, font_pt=FONT_SMALL + 2))

    def handle_event(self, e: pygame.event.Event) -> None:
        # Esc arrives through the engine's global path (on_escape), so
        # the KEYDOWN that follows it here must not double-handle.
        if e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
            return
        if self._confirm:
            for b in self._confirm_buttons:
                b.handle_event(e)
            return
        for b in self._buttons:
            b.handle_event(e)

    # ---- drawing ---------------------------------------------------------

    def _hand_word(self) -> str:
        if len(self.hands) == 1:
            return f"{self.hands[0]} hand"
        return "both hands"

    def draw(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        surf.fill(th.background)
        _draw_header(surf, "Quick calibration",
                     f"Learning your light press  |  {self._hand_word()}",
                     th, ly)
        if self.phase in (PHASE_OFF, PHASE_REST):
            self._draw_rest_step(surf)
        elif self.phase == PHASE_PRESS:
            self._draw_press_game(surf)
        else:
            self._draw_summary(surf)
        if self._status and self.phase != PHASE_DONE:
            draw_text(surf, self._status, (ly.width // 2, ly.height - 120),
                      th, ly, pt=FONT_BODY, centre=True, colour=th.warning)
        for b in self._buttons:
            b.draw(surf)
        if self._confirm:
            self._draw_confirm(surf)

    def _draw_rest_step(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        cx = ly.width // 2
        if self.phase == PHASE_OFF:
            head = "First: hands right off the pads"
            body = "Nothing touching. This reads the sensors' zero."
        else:
            head = ("Now rest your hands on the pads"
                    if len(self.hands) > 1
                    else f"Now rest your {self.hands[0]} hand on the pads")
            body = "Relax, no pressing. This is your starting level."
        draw_text(surf, head, (cx, 250), th, ly, pt=FONT_H1, centre=True)
        draw_text(surf, body, (cx, 305), th, ly, pt=FONT_BODY,
                  centre=True, colour=th.muted)
        if self._collecting:
            left = self._seconds_left()
            frac = (1.0 - left / self._rest_capture_s()
                    if self._rest_capture_s() > 0 else 1.0)
            cy = 445
            pygame.draw.circle(surf, th.muted, (cx, cy), 62, 4)
            # Arc sweeps as the capture fills; continuous, not a flash.
            if frac > 0:
                pygame.draw.arc(
                    surf, th.accent,
                    pygame.Rect(cx - 62, cy - 62, 124, 124),
                    1.5708 - frac * 6.2832, 1.5708, 8)
            draw_text(surf, f"{left:.1f}", (cx, cy), th, ly,
                      pt=FONT_H2 + 10, centre=True, colour=th.accent)
            draw_text(surf, "hold still...", (cx, cy + 96), th, ly,
                      pt=FONT_SMALL + 2, centre=True, colour=th.muted)
        step = "1 of 2" if self.phase == PHASE_OFF else "2 of 2"
        draw_text(surf, f"Setup {step}", (ly.width - 130, 150), th, ly,
                  pt=FONT_SMALL + 2, centre=True, colour=th.muted)

    @staticmethod
    def _mix(a: tuple[int, int, int], b: tuple[int, int, int],
             t: float) -> tuple[int, int, int]:
        """Blend a toward b. Used so the band's idle and glowing looks
        derive from the theme instead of hard-coding a palette."""
        return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))

    def _bar_rect(self) -> pygame.Rect:
        cx = self.layout.width // 2
        return pygame.Rect(cx - BAR_W // 2, BAR_TOP, BAR_W,
                           BAR_BOTTOM - BAR_TOP)

    def _y_for_counts(self, counts: float) -> int:
        bar = self._bar_rect()
        frac = max(0.0, min(1.0, counts / self._bar_max()))
        return int(bar.bottom - frac * bar.height)

    def _draw_press_game(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        hand = self._current_hand()
        i = self._finger_idx
        cx = ly.width // 2

        # Big friendly instruction, hand-tagged in a bilateral run.
        prefix = f"{hand.upper()} HAND  -  " if len(self.hands) > 1 else ""
        draw_text(surf, f"{prefix}Press with your "
                  f"{FINGER_NAMES[i].upper()} finger",
                  (cx, 195), th, ly, pt=FONT_H1, centre=True)
        cur, total = self._finger_no()
        draw_text(surf, f"Finger {cur} of {total}",
                  (ly.width - 130, 150), th, ly, pt=FONT_SMALL + 2,
                  centre=True, colour=th.muted)

        bar = self._bar_rect()
        zone_top = self._y_for_counts(self._zone_hi())
        zone_bot = self._y_for_counts(self._zone_lo())
        zone = pygame.Rect(bar.x - 14, zone_top, bar.w + 28,
                           zone_bot - zone_top)

        # Bar trough, then the target band behind the fill. The band is
        # always green so the target is readable before the first
        # press, and it glows (stronger fill, thicker border) while the
        # press sits in it: state-driven, so it cannot flash.
        pygame.draw.rect(surf, th.muted, bar, 2, border_radius=16)
        in_band = self._in_zone or self._landed
        band_fill = self._mix(th.success, th.background,
                              0.55 if in_band else 0.82)
        band_edge = (th.success if in_band
                     else self._mix(th.success, th.background, 0.35))
        pygame.draw.rect(surf, band_fill, zone, border_radius=10)
        pygame.draw.rect(surf, band_edge, zone, 4 if in_band else 2,
                         border_radius=10)

        # Live force fill, in this finger's own lane colour.
        live = self._live_counts()
        fill_top = self._y_for_counts(live)
        if fill_top < bar.bottom - 2:
            colour = (th.lane_active[i] if i < len(th.lane_active)
                      else th.accent)
            fr = pygame.Rect(bar.x + 4, fill_top, bar.w - 8,
                             bar.bottom - fill_top - 2)
            pygame.draw.rect(surf, colour, fr, border_radius=12)

        # Hold meter beside the bar: fills top-down while the press
        # holds in the band.
        meter = pygame.Rect(bar.right + 40, zone_top, 26,
                            zone_bot - zone_top)
        pygame.draw.rect(surf, th.muted, meter, 2, border_radius=8)
        if self._hold > 0:
            mh = int(meter.height * self._hold)
            pygame.draw.rect(
                surf, th.success,
                pygame.Rect(meter.x + 3, meter.bottom - mh - 2,
                            meter.w - 6, mh), border_radius=6)
        draw_text(surf, "HOLD", (meter.centerx, meter.bottom + 22), th, ly,
                  pt=FONT_SMALL, centre=True, colour=th.muted)

        # One-shot completion pop: a ring growing out of the band.
        now = time.perf_counter()
        if self._landed and now - self._pop_at < POP_S:
            t = (now - self._pop_at) / POP_S
            radius = int(40 + t * 90)
            width = max(2, int(10 * (1.0 - t)))
            pygame.draw.circle(surf, th.success,
                               (bar.centerx, zone.centery), radius, width)
            draw_text(surf, "GOT IT!", (cx, zone.centery - 130), th, ly,
                      pt=FONT_TITLE, centre=True, colour=th.success)

        # Coaching line under the bar.
        if self._landed:
            msg, colour = "Lovely light touch.", th.success
        elif live > self._zone_hi():
            msg, colour = "Easy! A little lighter.", th.warning
        elif self._in_zone:
            msg, colour = "Hold it right there...", th.success
        else:
            msg, colour = "Press gently into the glowing band.", th.muted
        draw_text(surf, msg, (cx, bar.bottom + 34), th, ly,
                  pt=FONT_H2, centre=True, colour=colour)
        # Nudge a finger that has been at it a while toward the way out.
        if (not self._landed
                and now - self._started_finger_at > 12.0):
            draw_text(surf, "Not registering? Skip for now keeps the "
                      "saved settings.", (cx, bar.bottom + 70), th, ly,
                      pt=FONT_SMALL + 2, centre=True, colour=th.muted)

        self._draw_tick_row(surf)

    def _draw_tick_row(self, surf: pygame.Surface) -> None:
        """One chip per finger in the run, ticked as each press lands,
        so progress is visible without counting."""
        th, ly = self.theme, self.layout
        total = len(self.hands) * N_FINGERS
        cw, gap = (84, 10) if total > 4 else (120, 14)
        row_w = total * cw + (total - 1) * gap
        x0 = ly.width // 2 - row_w // 2
        y = ly.height - 68
        done_upto = self._hand_idx * N_FINGERS + self._finger_idx
        for k in range(total):
            hand = self.hands[k // N_FINGERS]
            fi = k % N_FINGERS
            r = pygame.Rect(x0 + k * (cw + gap), y, cw, 46)
            is_done = k < done_upto or (k == done_upto and self._landed)
            is_now = k == done_upto and not is_done
            fill = (th.lane_idle[fi] if fi < len(th.lane_idle)
                    else th.muted)
            pygame.draw.rect(surf, fill, r, border_radius=10)
            if is_now:
                pygame.draw.rect(surf, th.accent, r, 3, border_radius=10)
            lum = 0.299 * fill[0] + 0.587 * fill[1] + 0.114 * fill[2]
            fg = (255, 255, 255) if lum < 140 else (15, 23, 42)
            label = (f"{hand[0].upper()} {FINGER_NAMES[fi][:3]}"
                     if len(self.hands) > 1 else FINGER_NAMES[fi])
            draw_text(surf, label, (r.centerx, r.y + 12), th, ly,
                      pt=FONT_SMALL, centre=True, colour=fg)
            if is_done:
                # Tick drawn as two strokes, no glyph dependency.
                pygame.draw.lines(
                    surf, th.success, False,
                    [(r.centerx - 10, r.y + 30), (r.centerx - 3, r.y + 37),
                     (r.centerx + 11, r.y + 23)], 4)
            else:
                # Hollow slot where the tick will land, so "not done
                # yet" is visibly a pending state, not a blank chip.
                pygame.draw.circle(surf, fg, (r.centerx, r.y + 32), 6, 2)

    @staticmethod
    def _kind_words(gap: float) -> str:
        if gap <= 55:
            return "a lovely light touch"
        if gap <= 100:
            return "a nice steady press"
        return "a strong press, lighter is fine too"

    def _draw_summary(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        cx = ly.width // 2
        name = getattr(self.engine.session, "participant", "") or ""
        head = (f"All set, {name}!" if name not in ("", "NA")
                else "All set!")
        if self._problems:
            head = "Nearly there"
        draw_text(surf, head, (cx, 220), th, ly, pt=FONT_H1, centre=True)
        y = 285
        for hand in self.hands:
            prof = self._profiles.get(hand)
            if prof is None:
                continue
            if len(self.hands) > 1:
                draw_text(surf, f"{hand.upper()} HAND", (cx, y), th, ly,
                          pt=FONT_SMALL + 2, centre=True, colour=th.muted)
                y += 30
            gaps = prof.gap()
            for i in range(N_FINGERS):
                colour = (th.lane_active[i] if i < len(th.lane_active)
                          else th.foreground)
                draw_text(surf, f"{FINGER_NAMES[i].title()}:", (cx - 260, y),
                          th, ly, pt=FONT_BODY, colour=colour)
                draw_text(surf,
                          f"{self._kind_words(gaps[i])}"
                          f"  ({gaps[i]:.0f} counts)",
                          (cx - 140, y), th, ly, pt=FONT_BODY,
                          colour=th.foreground)
                y += 32
            y += 12
        if self._problems:
            draw_text(surf, self._problems[0], (cx, y + 8), th, ly,
                      pt=FONT_SMALL + 2, centre=True, colour=th.warning)
        else:
            draw_text(surf, "That light touch is all the game ever needs.",
                      (cx, y + 8), th, ly, pt=FONT_BODY, centre=True,
                      colour=th.muted)

    def _draw_confirm(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        if (self._dim_cache is None
                or self._dim_cache.get_size() != (ly.width, ly.height)):
            self._dim_cache = pygame.Surface((ly.width, ly.height),
                                             pygame.SRCALPHA)
            self._dim_cache.fill((0, 0, 0, 160))
        surf.blit(self._dim_cache, (0, 0))
        cx, cy = ly.width // 2, ly.height // 2
        card = pygame.Rect(cx - 320, cy - 130, 640, 240)
        pygame.draw.rect(surf, th.background, card, border_radius=18)
        pygame.draw.rect(surf, th.muted, card, 2, border_radius=18)
        draw_text(surf, "Stop calibrating?", (cx, cy - 80), th, ly,
                  pt=FONT_H2, centre=True)
        draw_text(surf, "Nothing measured so far will be saved.",
                  (cx, cy - 35), th, ly, pt=FONT_BODY, centre=True,
                  colour=th.muted)
        for b in self._confirm_buttons:
            b.draw(surf)
