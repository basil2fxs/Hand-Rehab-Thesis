"""Lighthouse screen. One lantern, warm and calm; the flame is the
feedback channel, so the mode gets its own screen instead of the
lane-strip GameplayScreen.

Layout jobs, in the order a patient meets them:

  MAX PRESS CHECK   one finger named in its colour, presses-remaining
                    dots, a live force bar (the shared probe flow).
  GET READY         the working hand and finger, huge and in the
                    finger's colour, plus what kind of trial is
                    coming. Level moves are announced here in words.
  HOLD TRIALS       the lantern burns mid-screen. Flame height tracks
                    the signed error (too soft and it shrinks, too
                    hard and it stretches), flicker tracks the
                    fluctuation. In dark windows the room goes dark
                    and the lantern shows nothing about the force; on
                    relight the drift is revealed in plain words.
  ECHO TRIALS       feel the glow (lit, with feedback), wait out the
                    delay in the dark, then remake the glow blind.
                    While blind the screen shows only a fixed-size
                    pressing dot, never anything that scales with
                    force.
  TRIAL COMPLETE    the hold or echo numbers in plain words, then who
                    holds next. Failure wording is gentle by design:
                    the flame gutters, nothing blares.

Flame motion is smooth and slow: the sway is a fixed 1.1 Hz sine
whose amplitude follows the mode's smoothed flicker value, and the
size follows an EMA of the error, so nothing here blinks anywhere
near the 3 Hz limit. All alpha scratch surfaces are created once and
reused; steady-state frames allocate no new surfaces.

Screen conventions match the rest of the app: 1280x800 logical
layout, theme-aware, Esc and P handled by the engine's global event
path, GET READY countdown card and paused overlay mirroring
GameplayScreen's.
"""
from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

import pygame

from ..game.modes.force_pilot import FINGER_WORDS
from .screens import ModeSelectScreen, Screen
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


# Warm lantern palette, deliberately independent of the UI theme so
# the flame reads as firelight on both light and dark themes.
FLAME_OUTER = (255, 138, 48)
FLAME_MID = (255, 192, 92)
FLAME_CORE = (255, 241, 205)
GLASS_LINE = (176, 138, 78)
LANTERN_BODY = (92, 74, 52)
EMBER = (140, 92, 56)
DARK_TEXT = (196, 176, 150)


class LighthouseScreen(Screen):

    # Lantern geometry, logical pixels on the 1280x800 surface.
    #
    # Sized up from a 210x280 glass. The lantern is the whole game on
    # this screen and it used to occupy about a sixth of the frame's
    # width, with the flame tip (the thing being held steady) a few
    # dozen pixels tall in the middle of a very large empty page. The
    # flame span grows with the glass, so a percent of max still maps
    # to the same fraction of the glass; only the pixels-per-percent
    # changes, which is what makes a small drift visible.
    LANTERN_CX = 640
    GLASS_TOP = 214
    GLASS_W = 290
    GLASS_H = 372
    # Flame height span inside the glass. frac 0.5 (on target) puts
    # the tip midway between the two target ticks.
    FLAME_MIN_H = 54
    FLAME_MAX_H = 266
    # Glow scratch surface size: big enough for the widest glow.
    GLOW_SIZE = 460

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self._countdown_until = 0.0
        self._dim_cache: pygame.Surface | None = None
        self._dark_cache: pygame.Surface | None = None
        self._glow_scratch: pygame.Surface | None = None

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
        self._glow_scratch = None

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
        # Score under the pill, with the word that names it. Sitting
        # beside the pill it was a bare number 16 px off a filled pill
        # in the same accent, so the two read as one crowded object
        # and nothing on screen said what the number counted. The lane
        # modes have always carried a SCORE label; these four now
        # match, and the band under the pill is empty on all of them.
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
                  "Every lantern target is a percentage of what you "
                  "show here.",
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
        counts = getattr(mode, "probe_counts", 0.0)
        peaks = list(probe.peaks) if probe is not None else []
        scale = max([100.0, counts * 1.15] + [p * 1.15 for p in peaks])
        bar = pygame.Rect(cx - 60, 430, 120, 190)
        base = tuple(max(0, c - 22) for c in self.theme.background)
        pygame.draw.rect(surf, base, bar, border_radius=14)
        h = int(bar.h * max(0.0, min(1.0, counts / scale)))
        if h > 2:
            fill = pygame.Rect(bar.x, bar.bottom - h, bar.w, h)
            pygame.draw.rect(surf, self._finger_colour(mode.probe_finger),
                             fill, border_radius=14)
        pygame.draw.rect(surf, self.theme.muted, bar, 2, border_radius=14)
        if getattr(mode, "signal_waiting", False):
            draw_text(surf, "Waiting for sensor data...",
                      (cx, 650), self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.warning)
        elif mode.phase == "probe_gap":
            draw_text(surf, "Rest for a moment...",
                      (cx, 650), self.theme, self.layout, pt=FONT_BODY,
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
            draw_text(surf, "Keep the lantern lit with this finger.",
                      (cx, 380), self.theme, self.layout, pt=FONT_H2,
                      centre=True, colour=self.theme.foreground)
            _frac_dark, n_dark = _dark_frac_and_windows(mode)
            line = ("Press gently and hold the flame steady."
                    if n_dark == 0 else
                    "Press gently and hold. When the room darkens, "
                    "keep holding by feel.")
            draw_text(surf, line, (cx, 426), self.theme, self.layout,
                      pt=FONT_BODY, centre=True, colour=self.theme.muted)
        elif mode.cross:
            who = self._hand_finger_words(mode.set_hand, mode.set_finger)
            draw_text(surf, "Echo trial, across hands.",
                      (cx, 380), self.theme, self.layout, pt=FONT_H2,
                      centre=True, colour=self.theme.foreground)
            draw_text(surf,
                      f"{who} feels the glow first; this finger "
                      f"repeats it from memory.",
                      (cx, 426), self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.muted)
        else:
            draw_text(surf, "Echo trial: remember the glow.",
                      (cx, 380), self.theme, self.layout, pt=FONT_H2,
                      centre=True, colour=self.theme.foreground)
            draw_text(surf,
                      "Feel the glow, let go, wait, then make the "
                      "same glow again by feel.",
                      (cx, 426), self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.muted)
        if mode.level_msg:
            draw_text(surf, mode.level_msg, (cx, 500), self.theme,
                      self.layout, pt=FONT_H2, centre=True,
                      colour=self.theme.warning)

    # ---- the lantern -------------------------------------------------------
    def _glass_rect(self) -> pygame.Rect:
        return pygame.Rect(self.LANTERN_CX - self.GLASS_W // 2,
                           self.GLASS_TOP, self.GLASS_W, self.GLASS_H)

    def _draw_lantern_frame(self, surf: pygame.Surface,
                            dim: bool = False) -> None:
        """The lantern's body: cap, glass and base. `dim` draws the
        barely-there silhouette used while the room is dark."""
        glass = self._glass_rect()
        body = LANTERN_BODY if not dim else (52, 44, 36)
        line = GLASS_LINE if not dim else (72, 62, 50)
        cap = [(glass.centerx - 46, glass.top - 8),
               (glass.centerx + 46, glass.top - 8),
               (glass.centerx + 26, glass.top - 44),
               (glass.centerx - 26, glass.top - 44)]
        pygame.draw.polygon(surf, body, cap)
        ring = pygame.Rect(0, 0, 40, 18)
        ring.center = (glass.centerx, glass.top - 52)
        pygame.draw.ellipse(surf, line, ring, 3)
        pygame.draw.rect(surf, body,
                         pygame.Rect(glass.x - 14, glass.bottom,
                                     glass.w + 28, 26),
                         border_radius=8)
        pygame.draw.rect(surf, line, glass, 3, border_radius=10)

    # Half-height of the on-target band, in pixels either side of the
    # mid mark.
    TARGET_BAND_DY = 20

    # The three status rows under the lantern, derived from the
    # lantern's own bottom edge rather than fixed. Pinned at 620 they
    # ran through the base slab as soon as the glass grew.
    @property
    def HOLD_ROW_1(self) -> int:
        return self.GLASS_TOP + self.GLASS_H + 62

    @property
    def HOLD_ROW_2(self) -> int:
        return self.HOLD_ROW_1 + 42

    @property
    def HOLD_ROW_3(self) -> int:
        return self.HOLD_ROW_1 + 80

    def _draw_target_ticks(self, surf: pygame.Surface) -> None:
        """The on-target band: a tinted stripe across the glass
        between two etched marks, with the word that names it.

        Four short dashes at the glass edge said nothing on their own,
        and the only sentence explaining them ("bring the flame tip
        between the marks") showed during the ignite step and then
        disappeared for the whole hold. A shaded band reads as a
        target without a caption, and the caption is there anyway.
        """
        glass = self._glass_rect()
        base_y = glass.bottom - 26
        mid_h = (self.FLAME_MIN_H + self.FLAME_MAX_H) // 2
        dy = self.TARGET_BAND_DY
        top = base_y - mid_h - dy
        band = pygame.Surface((glass.w - 6, dy * 2), pygame.SRCALPHA)
        pygame.draw.rect(band, (*GLASS_LINE, 34), band.get_rect())
        surf.blit(band, (glass.left + 3, top))
        for edge_y in (top, top + dy * 2):
            pygame.draw.line(surf, GLASS_LINE, (glass.left - 12, edge_y),
                             (glass.left + 18, edge_y), 3)
            pygame.draw.line(surf, GLASS_LINE, (glass.right - 18, edge_y),
                             (glass.right + 12, edge_y), 3)
        draw_text(surf, "TARGET", (glass.right + 22, base_y - mid_h - 8),
                  self.theme, self.layout, pt=FONT_SMALL,
                  colour=self.theme.muted)

    def _ensure_glow(self) -> pygame.Surface:
        if self._glow_scratch is None:
            self._glow_scratch = self._new_surface(
                (self.GLOW_SIZE, self.GLOW_SIZE), pygame.SRCALPHA)
        return self._glow_scratch

    def _draw_flame(self, surf: pygame.Surface, frac: float,
                    flicker: float, now: float,
                    ember_only: bool = False) -> None:
        """The flame itself. `frac` 0..1 sets the height (0.5 = on
        target), `flicker` 0..1 sets the sway amplitude. The sway is a
        fixed 1.1 Hz sine, well under the flash limit; nothing else
        moves faster than the mode's smoothed inputs."""
        glass = self._glass_rect()
        base_y = glass.bottom - 26
        cx = glass.centerx
        if ember_only:
            pygame.draw.ellipse(surf, EMBER,
                                pygame.Rect(cx - 12, base_y - 10, 24, 14))
            return
        frac = max(0.0, min(1.0, frac))
        h = int(self.FLAME_MIN_H
                + frac * (self.FLAME_MAX_H - self.FLAME_MIN_H))
        sway = math.sin(now * 2.0 * math.pi * 1.1) * (
            2.0 + 10.0 * max(0.0, min(1.0, flicker)))
        tip = (int(cx + sway), base_y - h)
        w = max(18, int(20 + 26 * frac))
        # Soft glow behind the glass, redrawn onto the reused scratch
        # surface (clear + three alpha circles, no allocation).
        glow = self._ensure_glow()
        glow.fill((0, 0, 0, 0))
        gc = self.GLOW_SIZE // 2
        r = int(60 + 90 * frac)
        for radius, alpha in ((r, 26), (int(r * 0.7), 40),
                              (int(r * 0.42), 60)):
            pygame.draw.circle(glow, (*FLAME_MID, alpha), (gc, gc),
                               max(4, radius))
        surf.blit(glow, (cx - gc, base_y - h // 2 - gc))
        # Flame body: three nested teardrops.
        for colour, wf, hf in ((FLAME_OUTER, 1.0, 1.0),
                               (FLAME_MID, 0.62, 0.72),
                               (FLAME_CORE, 0.3, 0.4)):
            ww = max(6, int(w * wf))
            hh = max(8, int(h * hf))
            t = (int(cx + sway * hf), base_y - hh)
            pts = [
                t,
                (cx + ww // 2, base_y - hh // 3),
                (cx + ww // 3, base_y),
                (cx - ww // 3, base_y),
                (cx - ww // 2, base_y - hh // 3),
            ]
            pygame.draw.polygon(surf, colour, pts)
        # Wick.
        pygame.draw.line(surf, (60, 46, 34), (cx, base_y),
                         (cx, base_y + 8), 3)

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

    def _hold_time_left(self, mode, now: float) -> float | None:
        if mode.sub != "hold" or mode.hold_t0 is None:
            return None
        return max(0.0, float(mode.params["hold_s"])
                   - (now - mode.hold_t0))

    def _draw_hold(self, surf: pygame.Surface, mode, now: float) -> None:
        cx = self.layout.width // 2
        if mode.sub == "hold" and not mode.lit_now:
            # The room is dark: the flame burns unseen. Nothing on
            # this branch may depend on the live force.
            surf.blit(self._ensure_dark(surf), (0, 0))
            self._draw_lantern_frame(surf, dim=True)
            draw_text(surf, "Hold steady in the dark",
                      (cx, self.HOLD_ROW_1), self.theme, self.layout,
                      pt=FONT_H2, centre=True, colour=DARK_TEXT)
            draw_text(surf, "The flame is still burning. Trust your "
                      "finger.",
                      (cx, self.HOLD_ROW_2), self.theme, self.layout,
                      pt=FONT_BODY, centre=True, colour=DARK_TEXT)
            left = self._hold_time_left(mode, now)
            if left is not None:
                draw_text(surf, f"{left:.0f}s left",
                          (cx, self.HOLD_ROW_3),
                          self.theme, self.layout, pt=FONT_SMALL,
                          centre=True, colour=DARK_TEXT)
            return
        self._draw_lantern_frame(surf)
        self._draw_target_ticks(surf)
        self._draw_flame(surf, mode.flame_frac, mode.flicker_frac, now)
        self._draw_finger_chip(surf, mode.hand, mode.finger, 130, 90)
        if mode.sub == "ignite":
            draw_text(surf, "Press gently until the flame steadies",
                      (cx, self.HOLD_ROW_1), self.theme, self.layout,
                      pt=FONT_H2, centre=True,
                      colour=self.theme.foreground)
            draw_text(surf,
                      "Bring the flame tip between the marks and "
                      "keep it there.",
                      (cx, self.HOLD_ROW_2), self.theme, self.layout,
                      pt=FONT_BODY, centre=True,
                      colour=self.theme.muted)
            return
        # Sentence case, like every other line on the screen. The
        # lowercase run read as a debug string next to the title-case
        # headings around it.
        word = ("Steady" if mode.in_band_now else
                ("Ease off a little" if mode.flame_frac > 0.5
                 else "A little more"))
        draw_text(surf, word, (cx, self.HOLD_ROW_1), self.theme,
                  self.layout, pt=FONT_H2, centre=True,
                  colour=(self.theme.success if mode.in_band_now
                          else self.theme.muted))
        if mode.reveal_msg:
            draw_text(surf, mode.reveal_msg, (cx, self.HOLD_ROW_2),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self._accent())
        left = self._hold_time_left(mode, now)
        if left is not None:
            draw_text(surf, f"{left:.0f}s left", (cx, self.HOLD_ROW_3),
                      self.theme, self.layout, pt=FONT_SMALL,
                      centre=True, colour=self.theme.muted)

    def _draw_echo(self, surf: pygame.Surface, mode, now: float) -> None:
        cx = self.layout.width // 2
        if mode.sub in ("enter", "study"):
            self._draw_lantern_frame(surf)
            self._draw_target_ticks(surf)
            self._draw_flame(surf, mode.flame_frac, mode.flicker_frac, now)
            self._draw_finger_chip(surf, mode.set_hand, mode.set_finger,
                                   130, 90)
            if mode.sub == "enter":
                draw_text(surf, "Press gently until the flame steadies",
                          (cx, self.HOLD_ROW_1), self.theme, self.layout,
                          pt=FONT_H2, centre=True,
                          colour=self.theme.foreground)
            else:
                draw_text(surf, "Feel this glow. Remember it.",
                          (cx, self.HOLD_ROW_1), self.theme, self.layout,
                          pt=FONT_H2, centre=True,
                          colour=self.theme.foreground)
            return
        # Blind halves: delay and reproduce. Nothing on screen may
        # scale with the live force here.
        surf.blit(self._ensure_dark(surf), (0, 0))
        self._draw_lantern_frame(surf, dim=True)
        self._draw_flame(surf, 0.0, 0.0, now, ember_only=True)
        if mode.sub == "delay":
            # On a cross echo BOTH fingers must let go: the studying
            # hand holding on would carry the reference force through
            # the blind half, so the line names it explicitly.
            msg = ("Both hands off. Remember that glow..."
                   if getattr(mode, "cross", False)
                   else "Let go and remember that glow...")
            draw_text(surf, msg,
                      (cx, self.HOLD_ROW_1), self.theme, self.layout,
                      pt=FONT_H2, centre=True, colour=DARK_TEXT)
            draw_text(surf, f"{mode.delay_left_s:.0f}s",
                      (cx, self.HOLD_ROW_2 + 6), self.theme, self.layout,
                      pt=FONT_H2, centre=True, colour=DARK_TEXT)
            return
        # reproduce
        chip_hand, chip_finger = mode.hand, mode.finger
        self._draw_finger_chip(surf, chip_hand, chip_finger, 130, 90)
        draw_text(surf, "Make the same glow again, by feel",
                  (cx, self.HOLD_ROW_1), self.theme, self.layout,
                  pt=FONT_H2, centre=True, colour=DARK_TEXT)
        draw_text(surf, "Press and hold at the strength you remember.",
                  (cx, self.HOLD_ROW_2), self.theme, self.layout,
                  pt=FONT_BODY, centre=True, colour=DARK_TEXT)
        # Fixed-size pressing dot: says "your press registers" without
        # saying anything about how hard it is.
        dot_colour = (self.theme.success if mode.pressing_now
                      else (70, 62, 54))
        pygame.draw.circle(surf, dot_colour,
                           (cx, self.HOLD_ROW_3 + 6), 9)

    # ---- trial feedback ----------------------------------------------------
    def _draw_feedback(self, surf: pygame.Surface, mode,
                       now: float) -> None:
        cx = self.layout.width // 2
        res = mode._last_result or {}
        label = res.get("label", "")
        guttered = bool(res.get("guttered"))
        if guttered:
            # Child-safe register: the flame gutters, nothing blares.
            title, colour = "THE FLAME SLIPPED AWAY", self.theme.muted
        elif label == "Great":
            title, colour = ("STEADY AS A LIGHTHOUSE!"
                            if res.get("kind") == "hold"
                            else "A PERFECT ECHO!"), self.theme.success
        elif label == "Good":
            title, colour = "A GOOD GLOW", self._accent()
        else:
            title, colour = "THE FLAME WANDERED", self.theme.muted
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
            ("The glow asked", f"{res.get('target', 0.0):.1f}% of max"),
            ("You made", f"{made:.1f}% of max" if made is not None
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
