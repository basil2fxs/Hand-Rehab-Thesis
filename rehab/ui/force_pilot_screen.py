"""Force Pilot screen. The corridor is the stimulus, so the mode gets
its own screen instead of the lane-strip GameplayScreen.

Layout jobs, in the order a patient meets them:

  MAX PRESS CHECK   one finger named in its colour, presses-remaining
                    dots, a live force bar; the probe asks for maximal
                    presses and the screen only ever asks for one
                    finger at a time.
  GET READY         the working hand and finger, huge and in the
                    finger's colour, so the active finger is
                    unmistakable before the corridor starts moving.
                    Difficulty moves are announced here in words.
  THE RUN           the corridor scrolls right to left; the craft sits
                    at a fixed x and only its altitude answers to the
                    finger's force. A steady chip keeps naming the
                    hand and finger for the whole run.
  RUN COMPLETE      time in corridor, mean error, rings, release
                    error, then who flies next.

Corridor rendering is cached: the whole run's corridor band is drawn
ONCE per run onto a wide surface at run start, and every frame after
that is a single area-blit window onto it, so nothing rebuilds
per-frame geometry. Rings and the craft are primitive draws on top.

Stall feedback is a steady state change (red craft, STALL tag), not a
flash: nothing on this screen blinks faster than the 3 Hz limit, and
the corridor's own waveforms top out at 0.6 Hz by design.

Screen conventions match the rest of the app: 1280x800 logical
layout, theme-aware, Esc and P handled by the engine's global event
path, GET READY countdown card and paused overlay mirroring
GameplayScreen's.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from typing import TYPE_CHECKING

import pygame

from ..game.modes.force_pilot import FINGER_WORDS, target_pct
from .screens import ModeSelectScreen, Screen
from .widgets import (
    FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL, FONT_TITLE,
    draw_text, make_font,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


log = logging.getLogger(__name__)


class ForcePilotScreen(Screen):

    # Corridor plot geometry, logical pixels on the 1280x800 surface.
    PLOT_TOP = 170
    PLOT_BOTTOM = 640
    CRAFT_X = 300
    # Scroll speed. 120 px/s puts about 8 seconds of corridor on screen
    # ahead of the craft: enough preview to plan a ramp, not so much
    # that the assessment section reads as a memorisable map.
    PX_PER_S = 120
    # Column step for the one-off corridor render. 2 px at 120 px/s is
    # a target sample every ~17 ms, well inside the smoothness the
    # sub-1 Hz waveforms need.
    COL_STEP = 2

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self._countdown_until = 0.0
        self._dim_cache: pygame.Surface | None = None
        # The per-run corridor render and the key that owns it.
        self._corridor_surf: pygame.Surface | None = None
        self._corridor_key: tuple | None = None
        # Craft trail: recent displayed altitudes, newest last. Fixed
        # length so the run never grows memory.
        self._trail: deque[float] = deque(maxlen=42)
        self._trail_run: int | None = None

    # ---- shared furniture --------------------------------------------------
    def start_countdown(self, seconds: float) -> None:
        """Pre-start GET READY card, same contract as GameplayScreen."""
        self._countdown_until = time.perf_counter() + max(0.0, seconds)

    def _countdown_remaining(self) -> float:
        return max(0.0, self._countdown_until - time.perf_counter())

    def _accent(self) -> tuple[int, int, int]:
        return ModeSelectScreen.MODE_ACCENTS.get(
            "force_pilot", self.theme.accent)

    def on_block_start(self) -> None:
        self._corridor_surf = None
        self._corridor_key = None
        self._trail.clear()
        self._trail_run = None

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

    def _y(self, pct: float, span: float) -> int:
        span = max(1.0, span)
        frac = max(0.0, min(1.0, pct / span))
        return int(self.PLOT_BOTTOM
                   - frac * (self.PLOT_BOTTOM - self.PLOT_TOP))

    def _hand_finger_words(self, hand: str, finger: int) -> str:
        return f"{str(hand).upper()} {FINGER_WORDS[finger % 4]}"

    # ---- draw --------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        mode = self.engine.mode
        if mode is None or getattr(mode, "name", "") != "Force Pilot":
            draw_text(surf, "Starting...",
                      (self.layout.width // 2, self.layout.height // 2),
                      self.theme, self.layout, pt=FONT_H1, centre=True,
                      colour=self.theme.muted)
            return
        now = time.perf_counter()
        self._draw_top(surf, mode)
        phase = mode.phase
        if phase == "no_input":
            self._draw_no_input(surf)
        elif phase in ("probe_gap", "probe"):
            self._draw_probe(surf, mode)
        elif phase == "announce":
            self._draw_announce(surf, mode)
        elif phase == "run":
            self._draw_run(surf, mode, now)
        elif phase == "feedback":
            self._draw_feedback(surf, mode, now)
        remaining = self._countdown_remaining()
        if remaining > 0:
            self._draw_countdown_card(surf, remaining)
        # Skipped under the exit dialog (engine draws it above this
        # screen with its own dim), matching GameplayScreen.
        if self.engine.paused and not self.engine.exit_confirm_active:
            self._draw_paused_overlay(surf)

    # ---- top strip ---------------------------------------------------------
    def _draw_top(self, surf: pygame.Surface, mode) -> None:
        done, total = mode.runs_done, mode.total_runs
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
            left = f"Run {min(done + 1, total)} of {total}"
        draw_text(surf, left, (pad, 34), self.theme, self.layout,
                  pt=FONT_SMALL, colour=self.theme.muted)
        hw = getattr(mode, "corridor_hw", 0.0)
        draw_text(surf,
                  f"Level {mode.level} of {mode.max_level}   "
                  f"Corridor +/- {hw:.0f}%",
                  (self.layout.width // 2, 40), self.theme, self.layout,
                  pt=FONT_SMALL, centre=True, colour=self.theme.muted)
        accent = self._accent()
        pf = self.layout.font(FONT_SMALL + 2)
        pill_label = pf.render("FORCE PILOT", True, (255, 255, 255))
        pill_rect = pygame.Rect(0, 0, pill_label.get_width() + 24,
                                pill_label.get_height() + 8)
        pill_rect.topright = (self.layout.width - 28, 30)
        pygame.draw.rect(surf, accent, pill_rect,
                         border_radius=pill_rect.height // 2)
        surf.blit(pill_label,
                  pill_label.get_rect(center=pill_rect.center))
        sf = self.layout.font(FONT_H2, bold=True)
        score_surf = sf.render(f"{self.engine.score}", True, accent)
        surf.blit(score_surf, score_surf.get_rect(
            midright=(pill_rect.left - 16, pill_rect.centery)))

    def _draw_finger_chip(self, surf: pygame.Surface, hand: str,
                          finger: int, cx: int, cy: int) -> None:
        """The active hand and finger as one coloured pill. This chip
        is the unmistakable-finger promise: it wears the finger's own
        lane colour and says the hand in words."""
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

    # ---- no input ----------------------------------------------------------
    def _draw_no_input(self, surf: pygame.Surface) -> None:
        cx = self.layout.width // 2
        draw_text(surf, "FORCE PILOT NEEDS THE FORCE PADS",
                  (cx, 300), self.theme, self.layout, pt=FONT_H1,
                  centre=True, colour=self.theme.warning)
        draw_text(surf,
                  "This mode flies on the continuous force signal, "
                  "which the keyboard cannot produce.",
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
        # One dot per press still owed, filled as they land.
        total = mode.probe_presses
        dot_gap = 46
        x0 = cx - (total - 1) * dot_gap // 2
        for i in range(total):
            filled = i < (total - remaining)
            colour = (self.theme.success if filled else self.theme.muted)
            pygame.draw.circle(surf, colour, (x0 + i * dot_gap, 390),
                               12, 0 if filled else 3)
        # Live force bar: how hard the finger is pressing right now,
        # scaled against the best press seen so the bar visibly tops
        # out when the patient beats their own peak.
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

    # ---- run announcement --------------------------------------------------
    def _draw_announce(self, surf: pygame.Surface, mode) -> None:
        cx = self.layout.width // 2
        colour = self._finger_colour(mode.finger)
        font = make_font(int(FONT_TITLE * 1.5), bold=True)
        t = font.render(self._hand_finger_words(mode.hand, mode.finger),
                        True, colour)
        surf.blit(t, t.get_rect(center=(cx, 300)))
        draw_text(surf, "Fly the corridor with this finger.",
                  (cx, 390), self.theme, self.layout, pt=FONT_H2,
                  centre=True, colour=self.theme.foreground)
        draw_text(surf,
                  "Press harder to climb, ease off to descend. "
                  "Stay between the walls.",
                  (cx, 436), self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)
        if mode.level_msg:
            draw_text(surf, mode.level_msg, (cx, 500), self.theme,
                      self.layout, pt=FONT_H2, centre=True,
                      colour=self.theme.warning)

    # ---- the corridor run --------------------------------------------------
    def _corridor_colours(self) -> tuple:
        accent = self._accent()
        band = tuple(int(c * 0.35 + b * 0.65) for c, b in
                     zip(accent, self.theme.background))
        edge = accent
        centre = tuple(min(255, c + 60) for c in accent)
        return band, edge, centre

    def _build_corridor(self, mode) -> pygame.Surface:
        """Render the whole run's corridor once. The surface spans the
        craft's lead-in plus the full run plus one screen of tail, so
        every frame of the run is a plain window onto it."""
        w_screen = self.layout.width
        lead_s = self.CRAFT_X / self.PX_PER_S
        width = int(mode.duration_s * self.PX_PER_S) + w_screen
        height = self.PLOT_BOTTOM - self.PLOT_TOP
        cs = self._new_surface((max(1, width), max(1, height)),
                               pygame.SRCALPHA)
        band, edge, centre = self._corridor_colours()
        hw = mode.corridor_hw
        span = mode.span_pct
        pts_c: list[tuple[int, int]] = []
        pts_u: list[tuple[int, int]] = []
        pts_l: list[tuple[int, int]] = []
        for x in range(0, width, self.COL_STEP):
            t = x / self.PX_PER_S - lead_s
            tgt = target_pct(mode.sections, t)
            yu = self._y(tgt + hw, span) - self.PLOT_TOP
            yl = self._y(tgt - hw, span) - self.PLOT_TOP
            pygame.draw.line(cs, (*band, 200), (x, yu), (x, yl),
                             self.COL_STEP)
            pts_u.append((x, yu))
            pts_l.append((x, yl))
            pts_c.append((x, self._y(tgt, span) - self.PLOT_TOP))
        if len(pts_u) > 1:
            pygame.draw.lines(cs, edge, False, pts_u, 3)
            pygame.draw.lines(cs, edge, False, pts_l, 3)
            pygame.draw.lines(cs, (*centre, 130), False, pts_c, 1)
        return cs

    def _ensure_corridor(self, mode) -> pygame.Surface:
        key = (mode.trial_counter, mode.run_seed, mode.level)
        if self._corridor_surf is None or self._corridor_key != key:
            self._corridor_surf = self._build_corridor(mode)
            self._corridor_key = key
            self._trail.clear()
        return self._corridor_surf

    def _draw_run(self, surf: pygame.Surface, mode, now: float) -> None:
        corridor = self._ensure_corridor(mode)
        t_run = 0.0
        if mode.run_t0 is not None:
            t_run = max(0.0, now - mode.run_t0)
        src_x = int(t_run * self.PX_PER_S)
        src_x = max(0, min(src_x, corridor.get_width()
                           - self.layout.width))
        surf.blit(corridor, (0, self.PLOT_TOP),
                  area=pygame.Rect(src_x, 0, self.layout.width,
                                   corridor.get_height()))
        span = mode.span_pct
        # Frame lines and the percent scale, so altitude reads as
        # force and not as arbitrary screen space.
        frame_col = tuple(max(0, c - 30) for c in self.theme.background)
        pygame.draw.line(surf, frame_col, (0, self.PLOT_TOP - 1),
                         (self.layout.width, self.PLOT_TOP - 1), 1)
        pygame.draw.line(surf, frame_col, (0, self.PLOT_BOTTOM + 1),
                         (self.layout.width, self.PLOT_BOTTOM + 1), 1)
        draw_text(surf, f"{span:.0f}% of max", (10, self.PLOT_TOP - 24),
                  self.theme, self.layout, pt=FONT_SMALL,
                  colour=self.theme.muted)
        draw_text(surf, "0%", (10, self.PLOT_BOTTOM + 8), self.theme,
                  self.layout, pt=FONT_SMALL, colour=self.theme.muted)
        self._draw_rings(surf, mode, t_run)
        self._draw_craft(surf, mode)
        # The steady who-is-flying chip plus live run stats.
        self._draw_finger_chip(surf, mode.hand, mode.finger, 130, 90)
        self._draw_run_stats(surf, mode, t_run)
        if mode.signal_stale:
            draw_text(surf, "SIGNAL LOST - check the sensor connection",
                      (self.layout.width // 2, self.PLOT_TOP - 24),
                      self.theme, self.layout, pt=FONT_BODY, centre=True,
                      colour=self.theme.warning)

    def _draw_rings(self, surf: pygame.Surface, mode,
                    t_run: float) -> None:
        span = mode.span_pct
        gold = (255, 196, 0)
        for i, t_ring in enumerate(mode.ring_times):
            x = int(self.CRAFT_X + (t_ring - t_run) * self.PX_PER_S)
            if x < -30 or x > self.layout.width + 30:
                continue
            y = self._y(target_pct(mode.sections, t_ring), span)
            state = mode.ring_state[i] if i < len(mode.ring_state) else None
            if state is None:
                pygame.draw.circle(surf, gold, (x, y), 13, 3)
            elif state:
                pygame.draw.circle(surf, self.theme.success, (x, y), 13)
            else:
                pygame.draw.circle(surf, self.theme.muted, (x, y), 10, 2)

    def _draw_craft(self, surf: pygame.Surface, mode) -> None:
        span = mode.span_pct
        y = self._y(mode.craft_display_pct, span)
        run_key = mode.trial_counter
        if self._trail_run != run_key:
            self._trail.clear()
            self._trail_run = run_key
        self._trail.append(float(y))
        # Trail: one segment per stored frame, stepping back from the
        # craft. Reads as motion without any surface work.
        trail_col = self._finger_colour(mode.finger)
        pts = list(self._trail)
        for k in range(1, len(pts)):
            x1 = self.CRAFT_X - (len(pts) - k) * 3
            x0 = x1 - 3
            if x0 < 0:
                continue
            pygame.draw.line(surf, trail_col,
                             (x0, int(pts[k - 1])), (x1, int(pts[k])), 2)
        colour = (self.theme.error if mode.stalled
                  else self._finger_colour(mode.finger))
        body = [(self.CRAFT_X - 18, y - 12), (self.CRAFT_X - 18, y + 12),
                (self.CRAFT_X + 20, y)]
        pygame.draw.polygon(surf, colour, body)
        pygame.draw.polygon(surf, self.theme.foreground, body, 2)
        if mode.stalled:
            draw_text(surf, "STALL", (self.CRAFT_X + 34, y - 10),
                      self.theme, self.layout, pt=FONT_BODY,
                      colour=self.theme.error)

    def _draw_run_stats(self, surf: pygame.Surface, mode,
                        t_run: float) -> None:
        tic = 0.0
        if mode._scored_s > 0:
            tic = mode._in_c_s / mode._scored_s
        left = max(0.0, mode.duration_s - t_run)
        line = (f"In corridor {tic * 100.0:.0f}%   "
                f"Rings {mode._rings_collected}   "
                f"Stalls {mode._stalls}   "
                f"{left:.0f}s left")
        draw_text(surf, line,
                  (self.layout.width // 2, self.PLOT_BOTTOM + 34),
                  self.theme, self.layout, pt=FONT_BODY, centre=True,
                  colour=self.theme.muted)

    # ---- run feedback ------------------------------------------------------
    def _draw_feedback(self, surf: pygame.Surface, mode,
                       now: float) -> None:
        cx = self.layout.width // 2
        res = mode._last_result or {}
        label = res.get("label", "")
        if label == "Great":
            title, colour = "GREAT FLYING!", self.theme.success
        elif label == "Good":
            title, colour = "GOOD RUN", self._accent()
        else:
            title, colour = "ROUGH RIDE", self.theme.warning
        draw_text(surf, title, (cx, 170), self.theme, self.layout,
                  pt=FONT_H1 + 10, centre=True, colour=colour)
        who = self._hand_finger_words(res.get("hand", mode.hand),
                                      int(res.get("finger", 0)))
        draw_text(surf, who, (cx, 232), self.theme, self.layout,
                  pt=FONT_BODY + 2, centre=True, colour=self.theme.muted)
        tic = res.get("tic", 0.0) * 100.0
        mae = res.get("mae", 0.0)
        rings = res.get("rings", 0)
        rings_total = res.get("rings_total", 0)
        rel = res.get("release_mae")
        rows = [
            ("Time in corridor", f"{tic:.0f}%"),
            ("Mean error", f"{mae:.1f}% of max"),
            ("Rings", f"{rings} of {rings_total}"),
            ("Release control",
             f"{rel:.1f}% of max" if rel is not None else "n/a"),
        ]
        y = 310
        name_font = self.layout.font(FONT_H2)
        value_font = self.layout.font(FONT_H2, bold=True)
        for name, value in rows:
            n = name_font.render(name, True, self.theme.muted)
            surf.blit(n, n.get_rect(topright=(cx - 30, y)))
            v = value_font.render(value, True, self.theme.foreground)
            surf.blit(v, v.get_rect(topleft=(cx + 30, y)))
            y += 52
        if mode.level_msg:
            draw_text(surf, mode.level_msg, (cx, y + 16), self.theme,
                      self.layout, pt=FONT_H2, centre=True,
                      colour=self.theme.warning)
            y += 56
        # Who flies next, already picked, so the rest is also prep.
        draw_text(surf, "Next up", (cx, y + 30), self.theme, self.layout,
                  pt=FONT_SMALL, centre=True, colour=self.theme.muted)
        self._draw_finger_chip(surf, mode.hand, mode.finger, cx, y + 70)
        if mode._phase_until is not None:
            left = max(0.0, mode._phase_until - now)
            draw_text(surf, f"Next run in {left:.0f}s",
                      (cx, self.layout.height - 60), self.theme,
                      self.layout, pt=FONT_BODY, centre=True,
                      colour=self.theme.muted)

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

    def _draw_paused_overlay(self, surf: pygame.Surface) -> None:
        overlay = self._new_surface(
            (self.layout.width, self.layout.height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 160))
        surf.blit(overlay, (0, 0))
        draw_text(surf, "PAUSED",
                  (self.layout.width // 2, self.layout.height // 2 - 30),
                  self.theme, self.layout, pt=FONT_TITLE + 20, centre=True,
                  colour=self.theme.warning)


def _text_colour_for(fill: tuple[int, int, int]) -> tuple[int, int, int]:
    # Same luminance rule the lane tiles use, so chip text stays
    # readable on any finger colour.
    return (15, 23, 42) if sum(fill) / 3 > 140 else (255, 255, 255)
