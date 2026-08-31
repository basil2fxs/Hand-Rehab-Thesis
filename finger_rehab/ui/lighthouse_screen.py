"""Lighthouse screen. A precision hold is the whole game, so the mode
gets its own screen instead of the lane-strip GameplayScreen.

Drawn in the band-and-marker grammar quick calibration teaches at
login: one large vertical gauge, the target band on it, the live
force as a marker, zone words down the side. The old lantern-and-
flame picture carried the data in a metaphor ("how big is that flame
exactly?"); the gauge says the same thing without asking the patient
to decode anything. The mode keeps its name and its warm gold accent;
nothing decorative carries data any more.

Layout jobs, in the order a patient meets them:

  MAX PRESS CHECK   one finger named in its colour, presses-remaining
                    dots, a live force bar (the shared probe flow).
  GET READY         the working hand and finger, huge and in the
                    finger's colour, plus what kind of trial is
                    coming. Level moves are announced here in words.
  HOLD TRIALS       the gauge burns mid-screen: target band, live
                    marker, TOO HARD / TARGET / TOO SOFT zones. A
                    thin plan strip under it shows the whole hold
                    with its dark windows and a moving playhead. In
                    dark windows the gauge visibly shutters: no fill,
                    no marker, a large HOLD BY FEEL instruction and a
                    countdown to relight. On relight the drift is
                    revealed in plain words.
  ECHO TRIALS       three named stages, SHOW then WAIT then
                    REPRODUCE, on a steady stage rail. SHOW is the
                    lit gauge; WAIT and REPRODUCE are shuttered, and
                    while blind the screen shows only a fixed-size
                    pressing dot, never anything that scales with
                    force.
  TRIAL COMPLETE    the hold or echo numbers in plain words, then who
                    holds next. Failure wording is gentle by design:
                    the hold slips away, nothing blares.

Every colour change here is state-driven (the fill's three zones, the
stage rail, the coach line) so none of them can oscillate on their
own, and the marker follows the same smoothed detector value the mode
scores on; nothing here blinks anywhere near the 3 Hz limit. The two
alpha surfaces (dark overlay, countdown dim) are created once and
reused; steady-state frames allocate no new surfaces.

Screen conventions match the rest of the app: 1280x800 logical
layout, theme-aware, Esc and P handled by the engine's global event
path, GET READY countdown card and paused overlay mirroring
GameplayScreen's.
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING

import pygame

from ..game.modes.force_pilot import FINGER_WORDS
from .screens import ModeSelectScreen, Screen, draw_skip_chip
from .widgets import (
    FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL, FONT_TITLE,
    draw_text, make_font,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


log = logging.getLogger(__name__)


def _dark_frac_and_windows(mode) -> tuple[float, int]:
    """The dark share and window count the top strip and the announce
    line should quote.

    The level's dark_windows/dark_fraction config is what the ladder
    is aiming for, but draw_hold_params drops windows a short-
    configured hold_s cannot fit (audit finding #87), so a hold that
    is about to run (or just ran) can carry FEWER dark windows than
    the level implies. When the current trial is a hold, read the
    windows it actually drew; otherwise (an echo trial, or before any
    trial has been prepared) fall back to the level's configured
    share, which is the best available answer there."""
    if mode.kind == "hold" and mode.params:
        hold_s = float(mode.params.get("hold_s", 0.0))
        n = int(round(float(mode.params.get("n_dark", 0))))
        dark_s = float(mode.params.get("dark_s", 0.0))
        frac = (n * dark_s / hold_s) if hold_s > 0 else 0.0
        return frac, n
    return mode.dark_frac_by_level[mode.level - 1], \
        mode.dark_windows_by_level[mode.level - 1]


# Text and line colours for the blind halves. The dark overlay is
# near-black whatever the theme, so these are fixed warm greys rather
# than theme colours.
DARK_TEXT = (196, 176, 150)
SHUTTER_LINE = (86, 76, 62)
SHUTTER_EDGE = (120, 106, 86)


class LighthouseScreen(Screen):

    # Gauge geometry, logical pixels on the 1280x800 surface. One
    # tall bar, centred: the same shape and scale logic as the quick
    # calibration bar the patient met at login.
    GAUGE = pygame.Rect(566, 196, 148, 390)

    # The hold plan strip and the rows under the gauge.
    PLAN_RECT = pygame.Rect(360, 640, 560, 12)
    ROW_COACH = 690
    ROW_SUB = 728
    ROW_TIME = 760

    # Echo stage rail geometry.
    RAIL_Y = 152
    RAIL_SEG_W = 150
    RAIL_GAP = 14

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self._countdown_until = 0.0
        self._dim_cache: pygame.Surface | None = None
        self._dark_cache: pygame.Surface | None = None

    # ---- shared furniture --------------------------------------------------
    def start_countdown(self, seconds: float) -> None:
        """Pre-start GET READY card, same contract as GameplayScreen."""
        self._countdown_until = time.perf_counter() + max(0.0, seconds)

    def _countdown_remaining(self) -> float:
        return max(0.0, self._countdown_until - time.perf_counter())

    def _accent(self) -> tuple[int, int, int]:
        return ModeSelectScreen.MODE_ACCENTS.get(
            "lighthouse", self.theme.accent)

    def on_block_start(self) -> None:
        self._dark_cache = None

    def _new_surface(self, size: tuple[int, int],
                     flags: int = 0) -> pygame.Surface:
        """Every Surface this screen creates comes through here, so a
        test can pin that steady-state frames allocate none."""
        return pygame.Surface(size, flags)

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.engine.paused:
            return
        if self.engine.mode and hasattr(self.engine.mode, "handle_event"):
            self.engine.mode.handle_event(e)

    def update(self, dt: float) -> None:
        if self.engine.paused:
            return
        if (self.engine.mode and hasattr(self.engine.mode, "update")
                and self._countdown_remaining() <= 0):
            self.engine.mode.update(dt)

    # ---- helpers -----------------------------------------------------------
    @staticmethod
    def _mix(a, b, t: float) -> tuple[int, int, int]:
        """Blend a toward b. Every tint here derives from the theme
        this way, so all three colour themes stay readable without a
        single per-frame alpha surface."""
        return tuple(int(a[k] + (b[k] - a[k]) * t) for k in range(3))

    def _finger_colour(self, finger: int) -> tuple[int, int, int]:
        pal = self.theme.lane_active
        return pal[finger % len(pal)]

    def _hand_finger_words(self, hand: str, finger: int) -> str:
        return f"{str(hand).upper()} {FINGER_WORDS[finger % 4]}"

    def _draw_finger_chip(self, surf: pygame.Surface, hand: str,
                          finger: int, cx: int, cy: int) -> None:
        """The active hand and finger as one coloured pill, same
        promise as Force Pilot's: the working finger is unmistakable
        because the chip wears its lane colour and says the hand."""
        colour = self._finger_colour(finger)
        pf = self.layout.font(FONT_BODY, bold=True)
        text = pf.render(self._hand_finger_words(hand, finger), True,
                         _text_colour_for(colour))
        pill = pygame.Rect(0, 0, text.get_width() + 34,
                           text.get_height() + 14)
        pill.center = (cx, cy)
        pygame.draw.rect(surf, colour, pill,
                         border_radius=pill.height // 2)
        surf.blit(text, text.get_rect(center=pill.center))

    # ---- draw --------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        mode = self.engine.mode
        if mode is None or getattr(mode, "name", "") != "Lighthouse":
            draw_text(surf, "Starting...",
                      (self.layout.width // 2, self.layout.height // 2),
                      self.theme, self.layout, pt=FONT_H1, centre=True,
                      colour=self.theme.muted)
            return
        now = time.perf_counter()
        phase = mode.phase
        if phase == "no_input":
            self._draw_top(surf, mode)
            self._draw_no_input(surf)
        elif phase in ("probe_gap", "probe"):
            self._draw_top(surf, mode)
            self._draw_probe(surf, mode)
        elif phase == "announce":
            self._draw_top(surf, mode)
            self._draw_announce(surf, mode)
        elif phase == "trial":
            self._draw_trial(surf, mode, now)
            self._draw_top(surf, mode)
        elif phase == "feedback":
            self._draw_top(surf, mode)
            self._draw_feedback(surf, mode, now)
        else:
            self._draw_top(surf, mode)
        remaining = self._countdown_remaining()
        if remaining > 0:
            self._draw_countdown_card(surf, remaining)
        # One skip control for every enforced wait, drawn last so it
        # sits over the countdown card and the rest material alike.
        draw_skip_chip(surf, self.layout, self.theme, self.engine)
        # Skipped under either exit guard (the engine draws the
        # session dialog or the end-game chip above this screen),
        # matching GameplayScreen.
        if self.engine.paused and not self.engine.exit_overlay_active:
            self._draw_paused_overlay(surf)

    # ---- top strip ---------------------------------------------------------
    def _draw_top(self, surf: pygame.Surface, mode) -> None:
        done, total = mode.trials_done, mode.total_trials
        pad, bar_y, bar_h = 30, 14, 6
        bar_w = self.layout.width - pad * 2
        track = pygame.Rect(pad, bar_y, bar_w, bar_h)
        base = tuple(max(0, c - 26) for c in self.theme.background)
        pygame.draw.rect(surf, base, track, border_radius=bar_h // 2)
        frac = max(0.0, min(1.0, done / total)) if total else 0.0
        fill_w = int(bar_w * frac)
        if fill_w > 0:
            pygame.draw.rect(surf, self._accent(),
                             pygame.Rect(pad, bar_y, fill_w, bar_h),
                             border_radius=bar_h // 2)
        if mode.phase in ("probe_gap", "probe"):
            left = f"Max press check: {len(mode._probe_queue)} to go"
        else:
            left = f"Trial {min(done + 1, total)} of {total}"
        draw_text(surf, left, (pad, 34), self.theme, self.layout,
                  pt=FONT_SMALL, colour=self.theme.muted)
        frac_dark, _n_dark = _dark_frac_and_windows(mode)
        draw_text(surf,
                  f"Level {mode.level} of {mode.max_level}   "
                  f"Dark {frac_dark * 100:.0f}% of each hold",
                  (self.layout.width // 2, 40), self.theme, self.layout,
                  pt=FONT_SMALL, centre=True, colour=self.theme.muted)
        accent = self._accent()
        pf = self.layout.font(FONT_SMALL + 2)
        pill_label = pf.render("LIGHTHOUSE", True, (255, 255, 255))
        pill_rect = pygame.Rect(0, 0, pill_label.get_width() + 24,
                                pill_label.get_height() + 8)
        pill_rect.topright = (self.layout.width - 28, 30)
        pygame.draw.rect(surf, accent, pill_rect,
                         border_radius=pill_rect.height // 2)
        surf.blit(pill_label,
                  pill_label.get_rect(center=pill_rect.center))
        # Score under the pill, with the word that names it, matching
        # the lane modes.
        sf = self.layout.font(FONT_H2, bold=True)
        score_surf = sf.render(f"{self.engine.score}", True, accent)
        lf = self.layout.font(FONT_SMALL)
        score_label = lf.render("SCORE", True, self.theme.muted)
        score_rect = score_surf.get_rect(
            topright=(pill_rect.right, pill_rect.bottom + 10))
        surf.blit(score_surf, score_rect)
        surf.blit(score_label, score_label.get_rect(
            midright=(score_rect.left - 10, score_rect.centery)))

    # ---- no input ----------------------------------------------------------
    def _draw_no_input(self, surf: pygame.Surface) -> None:
        cx = self.layout.width // 2
        draw_text(surf, "LIGHTHOUSE NEEDS THE FORCE PADS",
                  (cx, 300), self.theme, self.layout, pt=FONT_H1,
                  centre=True, colour=self.theme.warning)
        draw_text(surf,
                  "This mode lives on a held force, which the keyboard "
                  "cannot produce.",
                  (cx, 370), self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)
        draw_text(surf,
                  "Connect the sensor device, then start the block "
                  "again. Esc leaves.",
                  (cx, 404), self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)

    # ---- max press probe ---------------------------------------------------
    def _draw_probe(self, surf: pygame.Surface, mode) -> None:
        cx = self.layout.width // 2
        draw_text(surf, "MAX PRESS CHECK", (cx, 150), self.theme,
                  self.layout, pt=FONT_H1 + 8, centre=True,
                  colour=self._accent())
        draw_text(surf,
                  "Press as hard as you can, then let go and rest.",
                  (cx, 212), self.theme, self.layout, pt=FONT_BODY + 2,
                  centre=True, colour=self.theme.muted)
        draw_text(surf,
                  "Every target in this game is a percentage of what "
                  "you show here.",
                  (cx, 244), self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)
        self._draw_finger_chip(surf, mode.probe_hand, mode.probe_finger,
                               cx, 320)
        probe = mode.probe
        remaining = (probe.presses_remaining if probe is not None
                     else mode.probe_presses)
        total = mode.probe_presses
        dot_gap = 46
        x0 = cx - (total - 1) * dot_gap // 2
        for i in range(total):
            filled = i < (total - remaining)
            colour = (self.theme.success if filled else self.theme.muted)
            pygame.draw.circle(surf, colour, (x0 + i * dot_gap, 390),
                               12, 0 if filled else 3)
        draw_text(surf, f"{max(0, remaining)} OF {total} PRESSES TO GO",
                  (cx, 418), self.theme, self.layout, pt=FONT_SMALL,
                  centre=True, colour=self.theme.muted)
        counts = getattr(mode, "probe_counts", 0.0)
        peaks = list(probe.peaks) if probe is not None else []
        scale = max([100.0, counts * 1.15] + [p * 1.15 for p in peaks])
        bar = pygame.Rect(cx - 60, 446, 120, 190)
        base = tuple(max(0, c - 22) for c in self.theme.background)
        pygame.draw.rect(surf, base, bar, border_radius=14)
        h = int(bar.h * max(0.0, min(1.0, counts / scale)))
        if h > 2:
            fill = pygame.Rect(bar.x, bar.bottom - h, bar.w, h)
            pygame.draw.rect(surf, self._finger_colour(mode.probe_finger),
                             fill, border_radius=14)
        pygame.draw.rect(surf, self.theme.muted, bar, 2, border_radius=14)
        if peaks:
            best = max(peaks)
            by = bar.bottom - int(bar.h * max(0.0, min(1.0,
                                                       best / scale)))
            pygame.draw.line(surf, self.theme.foreground,
                             (bar.left - 14, by), (bar.right + 14, by), 3)
            draw_text(surf, "BEST", (bar.right + 22, by - 9), self.theme,
                      self.layout, pt=FONT_SMALL,
                      colour=self.theme.foreground)
        draw_text(surf, "YOUR PRESS", (cx, bar.bottom + 12), self.theme,
                  self.layout, pt=FONT_SMALL, centre=True,
                  colour=self.theme.muted)
        if getattr(mode, "signal_waiting", False):
            draw_text(surf, "Waiting for sensor data...",
                      (cx, 690), self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.warning)
        elif mode.phase == "probe_gap":
            draw_text(surf, "Rest for a moment...",
                      (cx, 690), self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.muted)

    # ---- trial announcement ------------------------------------------------
    def _draw_announce(self, surf: pygame.Surface, mode) -> None:
        cx = self.layout.width // 2
        colour = self._finger_colour(mode.finger)
        font = make_font(int(FONT_TITLE * 1.5), bold=True)
        t = font.render(self._hand_finger_words(mode.hand, mode.finger),
                        True, colour)
        surf.blit(t, t.get_rect(center=(cx, 290)))
        if mode.kind == "hold":
            draw_text(surf, "Hold a steady press with this finger.",
                      (cx, 380), self.theme, self.layout, pt=FONT_H2,
                      centre=True, colour=self.theme.foreground)
            _frac_dark, n_dark = _dark_frac_and_windows(mode)
            line = ("Keep the marker inside the target band."
                    if n_dark == 0 else
                    "Keep the marker in the band. When the screen "
                    "darkens, hold by feel.")
            draw_text(surf, line, (cx, 426), self.theme, self.layout,
                      pt=FONT_BODY, centre=True, colour=self.theme.muted)
        elif mode.cross:
            who = self._hand_finger_words(mode.set_hand, mode.set_finger)
            draw_text(surf, "Echo trial, across hands.",
                      (cx, 380), self.theme, self.layout, pt=FONT_H2,
                      centre=True, colour=self.theme.foreground)
            draw_text(surf,
                      f"{who} feels the press first; this finger "
                      f"repeats it from memory.",
                      (cx, 426), self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.muted)
        else:
            draw_text(surf, "Echo trial: remember the press.",
                      (cx, 380), self.theme, self.layout, pt=FONT_H2,
                      centre=True, colour=self.theme.foreground)
            draw_text(surf,
                      "Feel the press, let go, wait, then make the "
                      "same press again by feel.",
                      (cx, 426), self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.muted)
        if mode.level_msg:
            draw_text(surf, mode.level_msg, (cx, 500), self.theme,
                      self.layout, pt=FONT_H2, centre=True,
                      colour=self.theme.warning)

    # ---- the gauge ---------------------------------------------------------
    def _gauge_span(self, mode) -> float:
        """Full scale of the gauge in percent of max. Headroom above
        the band so an overshoot visibly climbs out of the goal
        instead of pinning at the top with nothing left to show, the
        same rule the quick calibration bar uses."""
        return max(12.0, (mode.target_pct + mode.tol_pct) * 1.45)

    def _y_pct(self, pct: float, span: float) -> int:
        frac = max(0.0, min(1.0, pct / max(1.0, span)))
        return int(self.GAUGE.bottom - frac * self.GAUGE.h)

    def _draw_gauge_frame(self, surf: pygame.Surface, mode) -> None:
        """Trough, outline and the percent scale: the parts of the
        gauge that never depend on the live force."""
        th = self.theme
        g = self.GAUGE
        trough = g.inflate(16, 16)
        pygame.draw.rect(surf, self._mix(th.muted, th.background, 0.93),
                         trough, border_radius=22)
        pygame.draw.rect(surf, self._mix(th.muted, th.background, 0.55),
                         g, 2, border_radius=16)
        span = self._gauge_span(mode)
        step = 5.0 if span <= 32.0 else 10.0
        grid = self._mix(th.muted, th.background, 0.75)
        v = step
        while v < span:
            y = self._y_pct(v, span)
            pygame.draw.line(surf, grid, (g.x + 4, y),
                             (g.right - 4, y), 1)
            v += step

    def _band_rect(self, mode) -> pygame.Rect:
        span = self._gauge_span(mode)
        top = self._y_pct(mode.target_pct + mode.tol_pct, span)
        bot = self._y_pct(mode.target_pct - mode.tol_pct, span)
        return pygame.Rect(self.GAUGE.x + 3, top,
                           self.GAUGE.w - 6, max(4, bot - top))

    def _draw_gauge_lit(self, surf: pygame.Surface, mode,
                        pct: float | None) -> None:
        """Band, live fill and marker: the explicit read-out. `pct` is
        the smoothed force in percent of max, or None when the signal
        is missing (the fill and marker simply stay away)."""
        th = self.theme
        g = self.GAUGE
        span = self._gauge_span(mode)
        band = self._band_rect(mode)
        in_band = (pct is not None
                   and abs(pct - mode.target_pct) <= mode.tol_pct)
        over = pct is not None and pct - mode.target_pct > mode.tol_pct
        under = pct is not None and mode.target_pct - pct > mode.tol_pct

        # Goal band tint under the fill, outline on top of it, exactly
        # the quick calibration layering.
        pygame.draw.rect(surf, self._mix(th.success, th.background,
                                         0.55 if in_band else 0.80),
                         band, border_radius=8)
        zone = (th.warning if over
                else th.success if in_band else th.accent)
        if pct is not None:
            fill_top = self._y_pct(pct, span)
            if fill_top < g.bottom - 4:
                pygame.draw.rect(
                    surf, zone,
                    pygame.Rect(g.x + 5, fill_top, g.w - 10,
                                g.bottom - fill_top - 3),
                    border_radius=12)
        pygame.draw.rect(surf, th.success if in_band else self._mix(
            th.success, th.background, 0.25), band, 3, border_radius=8)
        if pct is not None:
            fill_top = self._y_pct(pct, span)
            pygame.draw.line(surf, th.foreground,
                             (g.x - 8, fill_top), (g.right + 8,
                                                   fill_top), 3)
            vf = self.layout.font(FONT_BODY, bold=True)
            v = vf.render(f"{max(0.0, pct):.0f}%", True, zone)
            vy = max(g.y + 10, min(g.bottom - 10, fill_top))
            surf.blit(v, v.get_rect(midright=(g.x - 38, vy)))

        # Zone words down the right, each against its own stretch of
        # the gauge; the active zone carries its full colour.
        lx = g.right + 26
        hard_c = th.warning if over else self._mix(
            th.warning, th.background, 0.45)
        soft_c = th.accent if under else self._mix(
            th.accent, th.background, 0.45)
        hf = self.layout.font(FONT_SMALL + 4, bold=True)
        t = hf.render("TOO HARD", True, hard_c)
        surf.blit(t, (lx, (g.y + band.top) // 2 - 10))
        tf = self.layout.font(FONT_H2, bold=True)
        t = tf.render("TARGET", True, th.success)
        surf.blit(t, (lx, band.centery - 26))
        draw_text(surf,
                  f"{mode.target_pct - mode.tol_pct:.0f} to "
                  f"{mode.target_pct + mode.tol_pct:.0f}% of max",
                  (lx, band.centery + 6), self.theme, self.layout,
                  pt=FONT_SMALL + 2, colour=th.muted)
        t = hf.render("TOO SOFT", True, soft_c)
        surf.blit(t, (lx, (band.bottom + g.bottom) // 2 - 10))

    def _draw_gauge_shuttered(self, surf: pygame.Surface, mode) -> None:
        """The gauge with its shutters down: outline, slats, and the
        target band as a ghost. Nothing here may depend on the live
        force; the shape stays so the patient knows exactly what has
        been taken away and where it will come back."""
        g = self.GAUGE
        pygame.draw.rect(surf, SHUTTER_EDGE, g, 2, border_radius=16)
        for k in range(1, 8):
            y = g.y + k * g.h // 8
            pygame.draw.line(surf, SHUTTER_LINE, (g.x + 6, y),
                             (g.right - 6, y), 3)
        band = self._band_rect(mode)
        for edge_y in (band.top, band.bottom):
            pygame.draw.line(surf, SHUTTER_EDGE, (g.x - 8, edge_y),
                             (g.x + 22, edge_y), 3)
            pygame.draw.line(surf, SHUTTER_EDGE, (g.right - 22, edge_y),
                             (g.right + 8, edge_y), 3)

    def _draw_plan_strip(self, surf: pygame.Surface, mode, now: float,
                         dim: bool) -> None:
        """The whole hold as a thin strip: lit stretches, dark
        windows, and a playhead. The dark windows stop being an
        ambush; the patient can see the next one coming and how long
        it lasts."""
        windows = getattr(mode, "hold_windows", None)
        if not windows or mode.params is None:
            return
        hold_s = float(mode.params.get("hold_s", 0.0))
        if hold_s <= 0:
            return
        r = self.PLAN_RECT
        th = self.theme
        if dim:
            lit_c = self._mix(DARK_TEXT, (0, 0, 0), 0.45)
            dark_c = self._mix(SHUTTER_LINE, (0, 0, 0), 0.2)
            edge_c = SHUTTER_EDGE
            text_c = DARK_TEXT
        else:
            lit_c = self._mix(self._accent(), th.background, 0.45)
            dark_c = self._mix(th.foreground, th.background, 0.35)
            edge_c = self._mix(th.muted, th.background, 0.45)
            text_c = th.muted
        for name, a, b in windows:
            x0 = r.x + int(r.w * max(0.0, a) / hold_s)
            x1 = r.x + int(r.w * min(hold_s, b) / hold_s)
            colour = dark_c if name.startswith("dark") else lit_c
            pygame.draw.rect(surf, colour,
                             pygame.Rect(x0, r.y, max(1, x1 - x0), r.h))
        pygame.draw.rect(surf, edge_c, r, 1)
        t_h = 0.0
        if mode.hold_t0 is not None:
            t_h = max(0.0, min(hold_s, now - mode.hold_t0))
        px = r.x + int(r.w * t_h / hold_s)
        pygame.draw.line(surf, th.foreground if not dim else DARK_TEXT,
                         (px, r.y - 4), (px, r.bottom + 4), 2)
        lf = self.layout.font(FONT_SMALL)
        lab = lf.render("THIS HOLD", True, text_c)
        surf.blit(lab, lab.get_rect(midright=(r.x - 14, r.centery)))
        left = max(0.0, hold_s - t_h)
        rl = lf.render(f"{left:.0f}s left", True, text_c)
        surf.blit(rl, rl.get_rect(midleft=(r.right + 14, r.centery)))

    def _relight_in_s(self, mode, now: float) -> float | None:
        """Seconds until the current dark window ends, or None when
        that cannot be read. Model-clock maths only; nothing here
        touches the force."""
        windows = getattr(mode, "hold_windows", None)
        if not windows or mode.hold_t0 is None:
            return None
        idx = min(int(getattr(mode, "_win_idx", 0)), len(windows) - 1)
        _name, _a, b = windows[idx]
        return max(0.0, (mode.hold_t0 + b) - now)

    def _ensure_dark(self, surf: pygame.Surface) -> pygame.Surface:
        if (self._dark_cache is None
                or self._dark_cache.get_size() != surf.get_size()):
            self._dark_cache = self._new_surface(surf.get_size(),
                                                 pygame.SRCALPHA)
            self._dark_cache.fill((4, 3, 8, 226))
        return self._dark_cache

    # ---- the trial itself --------------------------------------------------
    def _draw_trial(self, surf: pygame.Surface, mode, now: float) -> None:
        if mode.kind == "hold":
            self._draw_hold(surf, mode, now)
        else:
            self._draw_echo(surf, mode, now)
        if mode.signal_stale and mode.lit_now:
            draw_text(surf, "SIGNAL LOST - check the sensor connection",
                      (self.layout.width // 2, 96), self.theme,
                      self.layout, pt=FONT_BODY, centre=True,
                      colour=self.theme.warning)

    def _draw_hold(self, surf: pygame.Surface, mode, now: float) -> None:
        cx = self.layout.width // 2
        if mode.sub == "hold" and not mode.lit_now:
            # The screen is dark: the hold continues unseen. Nothing
            # on this branch may depend on the live force.
            surf.blit(self._ensure_dark(surf), (0, 0))
            self._draw_gauge_shuttered(surf, mode)
            self._draw_plan_strip(surf, mode, now, dim=True)
            draw_text(surf, "HOLD BY FEEL", (cx, self.ROW_COACH),
                      self.theme, self.layout, pt=FONT_H1, centre=True,
                      colour=DARK_TEXT)
            draw_text(surf, "Keep the same press going. Trust your "
                      "finger.",
                      (cx, self.ROW_SUB), self.theme, self.layout,
                      pt=FONT_BODY, centre=True, colour=DARK_TEXT)
            relight = self._relight_in_s(mode, now)
            if relight is not None:
                draw_text(surf, f"Relight in {relight:.0f}s",
                          (cx, self.ROW_TIME + 4), self.theme,
                          self.layout, pt=FONT_BODY, centre=True,
                          colour=DARK_TEXT)
            return
        self._draw_gauge_frame(surf, mode)
        self._draw_gauge_lit(surf, mode, mode.force_pct_now)
        self._draw_plan_strip(surf, mode, now, dim=False)
        self._draw_finger_chip(surf, mode.hand, mode.finger, 130, 90)
        if mode.sub == "ignite":
            draw_text(surf, "Press gently into the target band",
                      (cx, self.ROW_COACH), self.theme, self.layout,
                      pt=FONT_H2, centre=True,
                      colour=self.theme.foreground)
            draw_text(surf,
                      "Bring the marker into the band and keep it "
                      "there.",
                      (cx, self.ROW_SUB), self.theme, self.layout,
                      pt=FONT_BODY, centre=True,
                      colour=self.theme.muted)
            return
        word = ("Steady" if mode.in_band_now else
                ("Ease off a little" if mode.flame_frac > 0.5
                 else "A little more"))
        draw_text(surf, word, (cx, self.ROW_COACH), self.theme,
                  self.layout, pt=FONT_H2, centre=True,
                  colour=(self.theme.success if mode.in_band_now
                          else self.theme.muted))
        if mode.reveal_msg:
            # The relight verdict: what the hand did while the gauge
            # was shuttered, in plain words.
            draw_text(surf, mode.reveal_msg, (cx, self.ROW_SUB),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self._accent())

    # ---- echo trials -------------------------------------------------------
    _STAGES = ("SHOW", "WAIT", "REPRODUCE")

    def _draw_stage_rail(self, surf: pygame.Surface, here: int,
                         dim: bool) -> None:
        """The three echo stages named on a steady rail, so the
        patient always knows which part of the memory task this is
        and what comes next."""
        th = self.theme
        w, gap = self.RAIL_SEG_W, self.RAIL_GAP
        total = len(self._STAGES) * w + (len(self._STAGES) - 1) * gap
        x0 = self.layout.width // 2 - total // 2
        y = self.RAIL_Y
        for k, label in enumerate(self._STAGES):
            x = x0 + k * (w + gap)
            done = k < here
            now_ = k == here
            if dim:
                colour = DARK_TEXT if now_ else SHUTTER_EDGE
            else:
                colour = (th.success if done
                          else th.accent if now_ else th.muted)
            bar = pygame.Rect(x, y, w, 5)
            if dim:
                bar_c = colour if now_ else SHUTTER_LINE
            else:
                bar_c = (colour if (done or now_)
                         else self._mix(th.muted, th.background, 0.6))
            pygame.draw.rect(surf, bar_c, bar, border_radius=3)
            draw_text(surf, label, (x + w // 2, y + 18), self.theme,
                      self.layout, pt=FONT_SMALL, centre=True,
                      colour=colour if now_ else (
                          SHUTTER_EDGE if dim else th.muted))

    def _draw_echo(self, surf: pygame.Surface, mode, now: float) -> None:
        cx = self.layout.width // 2
        if mode.sub in ("enter", "study"):
            self._draw_gauge_frame(surf, mode)
            self._draw_gauge_lit(surf, mode, mode.force_pct_now)
            self._draw_stage_rail(surf, 0, dim=False)
            self._draw_finger_chip(surf, mode.set_hand, mode.set_finger,
                                   130, 90)
            if mode.sub == "enter":
                draw_text(surf, "Press gently into the target band",
                          (cx, self.ROW_COACH), self.theme, self.layout,
                          pt=FONT_H2, centre=True,
                          colour=self.theme.foreground)
            else:
                draw_text(surf, "Feel this press. Remember it.",
                          (cx, self.ROW_COACH), self.theme, self.layout,
                          pt=FONT_H2, centre=True,
                          colour=self.theme.foreground)
                t0 = getattr(mode, "_study_t0", None)
                if t0 is not None:
                    left = max(0.0, mode.echo_show_s - (now - t0))
                    draw_text(surf, f"Lights out in {left:.0f}s",
                              (cx, self.ROW_SUB), self.theme,
                              self.layout, pt=FONT_SMALL + 2,
                              centre=True, colour=self.theme.muted)
            return
        # Blind halves: delay and reproduce. Nothing on screen may
        # scale with the live force here.
        surf.blit(self._ensure_dark(surf), (0, 0))
        self._draw_gauge_shuttered(surf, mode)
        if mode.sub == "delay":
            self._draw_stage_rail(surf, 1, dim=True)
            # On a cross echo BOTH fingers must let go: the studying
            # hand holding on would carry the reference force through
            # the blind half, so the line names it explicitly.
            msg = ("Both hands off. Remember that press."
                   if getattr(mode, "cross", False)
                   else "Let go and remember that press.")
            draw_text(surf, msg,
                      (cx, self.ROW_COACH), self.theme, self.layout,
                      pt=FONT_H2, centre=True, colour=DARK_TEXT)
            draw_text(surf, f"{mode.delay_left_s:.0f}s",
                      (cx, self.ROW_SUB + 10), self.theme, self.layout,
                      pt=FONT_H1, centre=True, colour=DARK_TEXT)
            return
        # reproduce
        self._draw_stage_rail(surf, 2, dim=True)
        self._draw_finger_chip(surf, mode.hand, mode.finger, 130, 90)
        draw_text(surf, "Make the same press again, by feel",
                  (cx, self.ROW_COACH), self.theme, self.layout,
                  pt=FONT_H2, centre=True, colour=DARK_TEXT)
        draw_text(surf, "Press and hold at the strength you remember.",
                  (cx, self.ROW_SUB), self.theme, self.layout,
                  pt=FONT_BODY, centre=True, colour=DARK_TEXT)
        # Fixed-size pressing dot: says "your press registers" without
        # saying anything about how hard it is.
        dot_colour = (self.theme.success if mode.pressing_now
                      else (70, 62, 54))
        pygame.draw.circle(surf, dot_colour,
                           (cx, self.ROW_TIME + 6), 9)

    # ---- trial feedback ----------------------------------------------------
    def _draw_feedback(self, surf: pygame.Surface, mode,
                       now: float) -> None:
        cx = self.layout.width // 2
        res = mode._last_result or {}
        label = res.get("label", "")
        guttered = bool(res.get("guttered"))
        if guttered:
            # Child-safe register: the hold slips away, nothing blares.
            title, colour = "THE HOLD SLIPPED AWAY", self.theme.muted
        elif label == "Great":
            title, colour = ("STEADY AS A LIGHTHOUSE!"
                            if res.get("kind") == "hold"
                            else "A PERFECT ECHO!"), self.theme.success
        elif label == "Good":
            title, colour = "A GOOD HOLD", self._accent()
        else:
            title, colour = "THE HOLD WANDERED", self.theme.muted
        draw_text(surf, title, (cx, 170), self.theme, self.layout,
                  pt=FONT_H1 + 6, centre=True, colour=colour)
        who = self._hand_finger_words(res.get("hand", mode.hand),
                                      int(res.get("finger", 0)))
        draw_text(surf, who, (cx, 232), self.theme, self.layout,
                  pt=FONT_BODY + 2, centre=True, colour=self.theme.muted)
        if guttered:
            draw_text(surf, "No harm done. Have another go next turn.",
                      (cx, 300), self.theme, self.layout, pt=FONT_H2,
                      centre=True, colour=self.theme.muted)
            y = 360
        elif res.get("kind") == "hold":
            y = self._feedback_rows(surf, cx, self._hold_rows(res))
        else:
            y = self._feedback_rows(surf, cx, self._echo_rows(res))
        if mode.level_msg:
            draw_text(surf, mode.level_msg, (cx, y + 16), self.theme,
                      self.layout, pt=FONT_H2, centre=True,
                      colour=self.theme.warning)
            y += 56
        draw_text(surf, "Next up", (cx, y + 30), self.theme, self.layout,
                  pt=FONT_SMALL, centre=True, colour=self.theme.muted)
        self._draw_finger_chip(surf, mode.hand, mode.finger, cx, y + 70)
        if mode._phase_until is not None:
            left = max(0.0, mode._phase_until - now)
            self.draw_next_countdown(
                surf, f"Next trial in {left:.0f}s", y + 96)

    @staticmethod
    def _hold_rows(res: dict) -> list[tuple[str, str]]:
        def pct(v, signed=False):
            if v is None:
                return "n/a"
            return f"{v:+.1f}% of max" if signed else f"{v:.1f}% of max"

        rows = [
            ("Time on target", f"{res.get('tib', 0.0) * 100:.0f}%"),
            ("Lit steadiness",
             (f"{res['lit_cov'] * 100:.1f}% CoV"
              if res.get("lit_cov") is not None else "n/a")),
        ]
        drifts = res.get("drifts") or []
        if drifts:
            rows.append(("Drift in the dark", pct(
                sum(drifts) / len(drifts), signed=True)))
            rows.append(("Lit vs dark", pct(res.get("delta"))))
        return rows

    @staticmethod
    def _echo_rows(res: dict) -> list[tuple[str, str]]:
        made = res.get("made")
        err = res.get("signed_err")
        return [
            ("Waited", f"{res.get('delay_s', 0.0):.0f}s"),
            ("Target", f"{res.get('target', 0.0):.1f}% of max"),
            ("You held", f"{made:.1f}% of max" if made is not None
             else "n/a"),
            ("Off by", f"{err:+.1f}%" if err is not None else "n/a"),
        ]

    def _feedback_rows(self, surf: pygame.Surface, cx: int,
                       rows: list[tuple[str, str]]) -> int:
        y = 300
        name_font = self.layout.font(FONT_H2)
        value_font = self.layout.font(FONT_H2, bold=True)
        for name, value in rows:
            n = name_font.render(name, True, self.theme.muted)
            surf.blit(n, n.get_rect(topright=(cx - 30, y)))
            v = value_font.render(value, True, self.theme.foreground)
            surf.blit(v, v.get_rect(topleft=(cx + 30, y)))
            y += 52
        return y

    # ---- countdown card and pause ------------------------------------------
    def _draw_countdown_card(self, surf: pygame.Surface,
                             remaining: float) -> None:
        if (self._dim_cache is None
                or self._dim_cache.get_size() != surf.get_size()):
            self._dim_cache = self._new_surface(surf.get_size(),
                                               pygame.SRCALPHA)
            self._dim_cache.fill((0, 0, 0, 60))
        surf.blit(self._dim_cache, (0, 0))
        accent = self._accent()
        card_rect = pygame.Rect(0, 0, 420, 240)
        card_rect.center = (self.layout.width // 2,
                            self.layout.height // 2)
        fill_surf = self._new_surface(card_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(fill_surf, (*self.theme.background, 245),
                         fill_surf.get_rect(), border_radius=22)
        pygame.draw.rect(fill_surf, (*accent, 150),
                         fill_surf.get_rect(), 3, border_radius=22)
        surf.blit(fill_surf, card_rect.topleft)
        draw_text(surf, "GET READY",
                  (card_rect.centerx, card_rect.y + 56),
                  self.theme, self.layout, pt=FONT_H1,
                  centre=True, colour=self.theme.muted)
        draw_text(surf, f"{remaining:.1f}",
                  (card_rect.centerx, card_rect.y + 156),
                  self.theme, self.layout, pt=140,
                  centre=True, colour=accent)

    # _draw_paused_overlay comes from Screen: one card, one resume
    # line, identical on every screen a block runs on.


def _text_colour_for(fill: tuple[int, int, int]) -> tuple[int, int, int]:
    # Same luminance rule the lane tiles use, so chip text stays
    # readable on any finger colour.
    return (15, 23, 42) if sum(fill) / 3 > 140 else (255, 255, 255)
