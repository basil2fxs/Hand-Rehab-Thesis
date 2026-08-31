"""Force Pilot screen. The corridor is the stimulus, so the mode gets
its own screen instead of the lane-strip GameplayScreen.

Drawn as a clinical tracking instrument, in the band-and-marker
grammar quick calibration teaches at login: a goal band, a live
marker, one focal element per phase. The corridor is the goal band
scrolled through time; the patient's force is a plain trace ending in
a marker on a fixed now-line. No craft, no halo: the trace IS the
patient, and nothing decorative carries data.

Layout jobs, in the order a patient meets them:

  MAX PRESS CHECK   one finger named in its colour, presses-remaining
                    dots, a live force bar; the probe asks for maximal
                    presses and the screen only ever asks for one
                    finger at a time.
  GET READY         the working hand and finger, huge and in the
                    finger's colour, so the active finger is
                    unmistakable before the corridor starts moving.
                    Difficulty moves are announced here in words.
  THE RUN           the corridor band scrolls right to left under a
                    percent-of-max grid; the force trace ends at a
                    fixed now-line. Every section announces itself in
                    words (LOW HOLD, PRESS RAMP, RELEASE RAMP...),
                    both as a steady headline and as labels baked
                    into the scrolling band, and release sections
                    draw in a visibly different colour. Time in
                    corridor reads as one large percentage.
  RUN COMPLETE      time in corridor, mean error, rings, release
                    error, then who flies next.

Corridor rendering is cached: the whole run's corridor band, its
section boundaries and their word labels are drawn ONCE per run onto
a wide surface at run start, and every frame after that is a single
area-blit window onto it, so nothing rebuilds per-frame geometry.
Rings and the trace are primitive draws on top.

Stall feedback is a steady state change (red marker, a STALL tag with
the direction to correct), not a flash: nothing on this screen blinks
faster than the 3 Hz limit, and the corridor's own waveforms top out
at 0.6 Hz by design.

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

from ..game.modes.force_pilot import (
    FINGER_WORDS, SECTION_LABELS, target_pct,
)
from .screens import ModeSelectScreen, Screen, draw_skip_chip
from .widgets import (
    FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL, FONT_TITLE,
    draw_text, make_font,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


log = logging.getLogger(__name__)


# What each section asks of the finger, said under the section's name
# so the announcement is an instruction and not just a label.
SECTION_COACH = {
    "hold_in": "hold it steady",
    "ramp_up": "press a little harder",
    "hold_top": "hold it steady",
    "release": "ease off smoothly",
    "sine": "follow the wave",
    "pre_assess": "follow the line",
    "assess_sos": "follow the wave",
}


class ForcePilotScreen(Screen):

    # Corridor plot geometry, logical pixels on the 1280x800 surface.
    PLOT_TOP = 170
    PLOT_BOTTOM = 610
    MARKER_X = 300
    # Scroll speed. 120 px/s puts about 8 seconds of corridor on screen
    # ahead of the marker: enough preview to plan a ramp, not so much
    # that the assessment section reads as a memorisable map.
    PX_PER_S = 120
    # Column step for the one-off corridor render. 2 px at 120 px/s is
    # a target sample every ~17 ms, well inside the smoothness the
    # sub-1 Hz waveforms need.
    COL_STEP = 2

    # The results band under the plot: the hero percentage in the
    # middle, the two side counts, then the label row.
    HERO_Y = 706
    HERO_LABEL_Y = 762
    SIDE_STAT_DX = 340
    HERO_PT = 62

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self._countdown_until = 0.0
        self._dim_cache: pygame.Surface | None = None
        # The per-run corridor render and the key that owns it.
        self._corridor_surf: pygame.Surface | None = None
        self._corridor_key: tuple | None = None
        # Force trace: (t_run, pct) pairs, newest last. Fixed length so
        # the run never grows memory; 200 frames covers the 2.5 s the
        # 300 px behind the now-line can show at 120 px/s.
        self._trace: deque[tuple[float, float]] = deque(maxlen=200)
        self._trace_run: int | None = None

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
        self._trace.clear()
        self._trace_run = None

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

    def _y(self, pct: float, span: float) -> int:
        span = max(1.0, span)
        frac = max(0.0, min(1.0, pct / span))
        return int(self.PLOT_BOTTOM
                   - frac * (self.PLOT_BOTTOM - self.PLOT_TOP))

    def _hand_finger_words(self, hand: str, finger: int) -> str:
        return f"{str(hand).upper()} {FINGER_WORDS[finger % 4]}"

    @staticmethod
    def _section_at(sections, t: float):
        """The RunSection the run is inside at run time t."""
        if not sections:
            return None
        for sec in sections:
            if t < sec.end_s:
                return sec
        return sections[-1]

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
            # Say what is being counted: the centre panel counts
            # presses for THIS finger, so a bare number here read as
            # a contradiction of it.
            n_fingers = len(mode._probe_queue)
            left = (f"Max press check: {n_fingers} "
                    f"finger{'s' if n_fingers != 1 else ''} to go")
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
        # The dots are a count of presses, which nothing said. A row of
        # circles under a "press as hard as you can" heading could as
        # easily have been a loading spinner.
        draw_text(surf, f"{max(0, remaining)} OF {total} PRESSES TO GO",
                  (cx, 418), self.theme, self.layout, pt=FONT_SMALL,
                  centre=True, colour=self.theme.muted)
        # Live force bar: how hard the finger is pressing right now,
        # scaled against the best press seen so the bar visibly tops
        # out when the patient beats their own peak.
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
        # Best press so far, marked on the bar with the word for it: a
        # line to beat is the whole point of a maximal-press probe.
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

    # ---- run announcement --------------------------------------------------
    def _draw_announce(self, surf: pygame.Surface, mode) -> None:
        cx = self.layout.width // 2
        colour = self._finger_colour(mode.finger)
        font = make_font(int(FONT_TITLE * 1.5), bold=True)
        t = font.render(self._hand_finger_words(mode.hand, mode.finger),
                        True, colour)
        surf.blit(t, t.get_rect(center=(cx, 300)))
        draw_text(surf, "Track the corridor with this finger.",
                  (cx, 390), self.theme, self.layout, pt=FONT_H2,
                  centre=True, colour=self.theme.foreground)
        draw_text(surf,
                  "Press harder to rise, ease off to sink. "
                  "Keep your line inside the band.",
                  (cx, 436), self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)
        if mode.level_msg:
            draw_text(surf, mode.level_msg, (cx, 500), self.theme,
                      self.layout, pt=FONT_H2, centre=True,
                      colour=self.theme.warning)

    # ---- the corridor run --------------------------------------------------
    def _corridor_colours(self) -> dict:
        """Corridor tints, all derived from the theme so the band
        stays quiet on every colour theme. Release sections use the
        page's own greys instead of the accent: the one visibly
        different stretch of band is the one asking for the opposite
        movement."""
        accent = self._accent()
        bg = self.theme.background
        return {
            "band": self._mix(accent, bg, 0.82),
            "edge": self._mix(accent, bg, 0.35),
            "band_release": self._mix(self.theme.muted, bg, 0.80),
            "edge_release": self._mix(self.theme.muted, bg, 0.25),
            "boundary": self._mix(self.theme.muted, bg, 0.55),
        }

    def _build_corridor(self, mode) -> pygame.Surface:
        """Render the whole run's corridor once: band, edges, section
        boundaries and their word labels. The surface spans the
        marker's lead-in plus the full run plus one screen of tail, so
        every frame of the run is a plain window onto it."""
        w_screen = self.layout.width
        lead_s = self.MARKER_X / self.PX_PER_S
        width = int(mode.duration_s * self.PX_PER_S) + w_screen
        height = self.PLOT_BOTTOM - self.PLOT_TOP
        cs = self._new_surface((max(1, width), max(1, height)),
                               pygame.SRCALPHA)
        cols = self._corridor_colours()
        hw = mode.corridor_hw
        span = mode.span_pct
        sections = mode.sections

        def release_at(t: float) -> bool:
            sec = self._section_at(sections, t)
            return sec is not None and sec.name == "release"

        # Band fill plus per-section edge polylines, so the release
        # stretch changes colour cleanly at its boundaries.
        edge_pts: list[tuple[bool, list, list]] = []
        cur_rel: bool | None = None
        for x in range(0, width, self.COL_STEP):
            t = x / self.PX_PER_S - lead_s
            tgt = target_pct(sections, t)
            yu = self._y(tgt + hw, span) - self.PLOT_TOP
            yl = self._y(tgt - hw, span) - self.PLOT_TOP
            rel = release_at(t)
            band = cols["band_release"] if rel else cols["band"]
            pygame.draw.line(cs, band, (x, yu), (x, yl), self.COL_STEP)
            if rel != cur_rel:
                edge_pts.append((rel, [], []))
                cur_rel = rel
            edge_pts[-1][1].append((x, yu))
            edge_pts[-1][2].append((x, yl))
        for rel, pts_u, pts_l in edge_pts:
            edge = cols["edge_release"] if rel else cols["edge"]
            if len(pts_u) > 1:
                pygame.draw.lines(cs, edge, False, pts_u, 3)
                pygame.draw.lines(cs, edge, False, pts_l, 3)
        # Section boundaries and their names, baked so the words
        # scroll in with the band they describe. The release label
        # carries a down arrow: that stretch asks for the opposite
        # movement and has to read differently at a glance.
        label_font = make_font(int(FONT_SMALL + 2), bold=True)
        for sec in sections:
            x = int((sec.start_s + lead_s) * self.PX_PER_S)
            if x > 0:
                pygame.draw.line(cs, cols["boundary"], (x, 0),
                                 (x, height), 1)
            word = SECTION_LABELS.get(sec.name, sec.name).upper()
            t_lab = label_font.render(word, True, self.theme.muted)
            lx = x + 8
            cs.blit(t_lab, (lx, 6))
            if sec.name == "release":
                ax = lx + t_lab.get_width() + 10
                pygame.draw.polygon(cs, self.theme.muted,
                                    [(ax, 8), (ax + 10, 8),
                                     (ax + 5, 18)])
        return cs

    def _ensure_corridor(self, mode) -> pygame.Surface:
        key = (mode.trial_counter, mode.run_seed, mode.level)
        if self._corridor_surf is None or self._corridor_key != key:
            self._corridor_surf = self._build_corridor(mode)
            self._corridor_key = key
            self._trace.clear()
        return self._corridor_surf

    def _draw_grid(self, surf: pygame.Surface, span: float,
                   labels: bool = False) -> None:
        """Percent-of-max gridlines behind the corridor, labelled on
        the left, so altitude reads as force and not as arbitrary
        screen space. Lines go under the band; labels are drawn in a
        second pass over it, or the band hides them whenever it runs
        along the left edge."""
        grid = self._mix(self.theme.muted, self.theme.background, 0.78)
        step = 10.0
        v = 0.0
        while v <= span:
            y = self._y(v, span)
            if labels:
                draw_text(surf, f"{v:.0f}%", (8, y - 18), self.theme,
                          self.layout, pt=FONT_SMALL,
                          colour=self.theme.muted)
            else:
                pygame.draw.line(surf, grid, (0, y),
                                 (self.layout.width, y), 1)
            v += step

    def _draw_run(self, surf: pygame.Surface, mode, now: float) -> None:
        corridor = self._ensure_corridor(mode)
        t_run = 0.0
        if mode.run_t0 is not None:
            t_run = max(0.0, now - mode.run_t0)
        span = mode.span_pct
        self._draw_grid(surf, span)
        src_x = int(t_run * self.PX_PER_S)
        src_x = max(0, min(src_x, corridor.get_width()
                           - self.layout.width))
        surf.blit(corridor, (0, self.PLOT_TOP),
                  area=pygame.Rect(src_x, 0, self.layout.width,
                                   corridor.get_height()))
        self._draw_grid(surf, span, labels=True)
        frame_col = self._mix(self.theme.muted, self.theme.background,
                              0.55)
        pygame.draw.line(surf, frame_col, (0, self.PLOT_TOP - 1),
                         (self.layout.width, self.PLOT_TOP - 1), 1)
        pygame.draw.line(surf, frame_col, (0, self.PLOT_BOTTOM + 1),
                         (self.layout.width, self.PLOT_BOTTOM + 1), 1)
        # Run progress along the plot's bottom edge: the time story in
        # one thin line instead of a competing readout.
        if mode.duration_s > 0:
            frac = max(0.0, min(1.0, t_run / mode.duration_s))
            pygame.draw.line(
                surf, self._mix(self._accent(), self.theme.background,
                                0.45),
                (0, self.PLOT_BOTTOM + 5),
                (int(self.layout.width * frac), self.PLOT_BOTTOM + 5), 4)
        self._draw_rings(surf, mode, t_run)
        self._draw_trace(surf, mode, t_run)
        self._draw_section_words(surf, mode, t_run)
        # The steady who-is-flying chip plus the results band.
        self._draw_finger_chip(surf, mode.hand, mode.finger, 130, 90)
        self._draw_run_stats(surf, mode, t_run)
        if mode.signal_stale:
            draw_text(surf, "SIGNAL LOST - check the sensor connection",
                      (self.layout.width // 2, self.PLOT_TOP - 24),
                      self.theme, self.layout, pt=FONT_BODY, centre=True,
                      colour=self.theme.warning)

    def _draw_section_words(self, surf: pygame.Surface, mode,
                            t_run: float) -> None:
        """The current section announced in words, with its coaching
        line, steady between the top strip and the plot. Changes only
        at section boundaries, so nothing here can flash."""
        sec = self._section_at(mode.sections, t_run)
        if sec is None:
            return
        cx = self.layout.width // 2
        word = SECTION_LABELS.get(sec.name, sec.name).upper()
        colour = (self.theme.muted if sec.name == "release"
                  else self.theme.foreground)
        draw_text(surf, word, (cx, 108), self.theme, self.layout,
                  pt=FONT_H2 + 4, centre=True, colour=colour)
        draw_text(surf, SECTION_COACH.get(sec.name, ""), (cx, 142),
                  self.theme, self.layout, pt=FONT_SMALL + 2,
                  centre=True, colour=self.theme.muted)

    def _draw_rings(self, surf: pygame.Surface, mode,
                    t_run: float) -> None:
        """Bonus rings as chart checkpoints on the corridor centre:
        hollow accent ahead, filled green once collected, small grey
        once missed."""
        span = mode.span_pct
        for i, t_ring in enumerate(mode.ring_times):
            x = int(self.MARKER_X + (t_ring - t_run) * self.PX_PER_S)
            if x < -30 or x > self.layout.width + 30:
                continue
            y = self._y(target_pct(mode.sections, t_ring), span)
            state = mode.ring_state[i] if i < len(mode.ring_state) else None
            if state is None:
                # Pulled toward the ink so an upcoming checkpoint
                # stands clear of the pale band it sits on.
                ahead = self._mix(self._accent(), self.theme.foreground,
                                  0.35)
                pygame.draw.circle(surf, ahead, (x, y), 9, 3)
            elif state:
                pygame.draw.circle(surf, self.theme.success, (x, y), 9)
            else:
                pygame.draw.circle(surf, self.theme.muted, (x, y), 6, 2)

    def _draw_trace(self, surf: pygame.Surface, mode,
                    t_run: float) -> None:
        """The patient's force as a plain trace ending in a marker on
        the fixed now-line. The trace is drawn in the page's own ink;
        the marker wears the finger's colour so who is flying stays
        glanceable next to the chip."""
        span = mode.span_pct
        run_key = mode.trial_counter
        if self._trace_run != run_key:
            self._trace.clear()
            self._trace_run = run_key
        pct = mode.craft_display_pct
        self._trace.append((t_run, float(pct)))
        # Thin vertical now-line: where scoring happens.
        now_col = self._mix(self.theme.muted, self.theme.background, 0.6)
        pygame.draw.line(surf, now_col, (self.MARKER_X, self.PLOT_TOP),
                         (self.MARKER_X, self.PLOT_BOTTOM), 1)
        pts = []
        for t_i, p_i in self._trace:
            x = int(self.MARKER_X - (t_run - t_i) * self.PX_PER_S)
            if x < 0:
                continue
            pts.append((x, self._y(p_i, span)))
        if len(pts) > 1:
            pygame.draw.lines(surf, self.theme.foreground, False, pts, 2)
        y = self._y(pct, span)
        marker = (self.theme.error if mode.stalled
                  else self._finger_colour(mode.finger))
        pygame.draw.line(surf, marker, (self.MARKER_X - 14, y),
                         (self.MARKER_X + 14, y), 3)
        pygame.draw.circle(surf, marker, (self.MARKER_X, y), 9)
        pygame.draw.circle(surf, self.theme.foreground,
                           (self.MARKER_X, y), 9, 2)
        if mode.stalled:
            # Steady tag with the direction to correct. Above or below
            # the marker, away from the band, so it never sits on the
            # thing it is talking about.
            tgt = target_pct(mode.sections, t_run)
            below = pct < tgt
            word = ("STALL - press harder" if below
                    else "STALL - ease off")
            ty = y - 40 if below else y + 24
            ty = max(self.PLOT_TOP + 8, min(self.PLOT_BOTTOM - 30, ty))
            draw_text(surf, word, (self.MARKER_X + 26, ty), self.theme,
                      self.layout, pt=FONT_BODY, colour=self.theme.error)

    def _draw_run_stats(self, surf: pygame.Surface, mode,
                        t_run: float) -> None:
        """The results band: time in corridor as the one large number,
        rings and stalls small either side, time left small under the
        plot's progress line."""
        tic = 0.0
        if mode._scored_s > 0:
            tic = mode._in_c_s / mode._scored_s
        cx = self.layout.width // 2
        draw_text(surf, f"{tic * 100.0:.0f}%", (cx, self.HERO_Y),
                  self.theme, self.layout, pt=self.HERO_PT, centre=True,
                  colour=self.theme.foreground)
        draw_text(surf, "TIME IN CORRIDOR", (cx, self.HERO_LABEL_Y),
                  self.theme, self.layout, pt=FONT_SMALL, centre=True,
                  colour=self.theme.muted)
        rings_total = len(getattr(mode, "ring_times", ()) or ())
        rings = (f"{mode._rings_collected} of {rings_total}"
                 if rings_total else f"{mode._rings_collected}")
        for dx, value, label in (
                (-self.SIDE_STAT_DX, rings, "RINGS"),
                (self.SIDE_STAT_DX, f"{mode._stalls}", "STALLS")):
            draw_text(surf, value, (cx + dx, self.HERO_Y + 10),
                      self.theme, self.layout, pt=FONT_H2, centre=True,
                      colour=self.theme.foreground)
            draw_text(surf, label, (cx + dx, self.HERO_LABEL_Y),
                      self.theme, self.layout, pt=FONT_SMALL, centre=True,
                      colour=self.theme.muted)
        left = max(0.0, mode.duration_s - t_run)
        lf = self.layout.font(FONT_SMALL)
        t_left = lf.render(f"{left:.0f}s left", True, self.theme.muted)
        surf.blit(t_left, t_left.get_rect(
            topright=(self.layout.width - 12, self.PLOT_BOTTOM + 12)))

    # ---- run feedback ------------------------------------------------------
    def _draw_feedback(self, surf: pygame.Surface, mode,
                       now: float) -> None:
        cx = self.layout.width // 2
        res = mode._last_result or {}
        label = res.get("label", "")
        if label == "Great":
            title, colour = "GREAT RUN", self.theme.success
        elif label == "Good":
            title, colour = "GOOD RUN", self._accent()
        elif label == "NoSignal":
            # A signal-starved run is a hardware event: showing a
            # rough-run title with 'Mean error 0.0%' blamed the
            # patient for a dead sensor.
            title, colour = "SIGNAL LOST", self.theme.error
        else:
            title, colour = "A ROUGH RUN", self.theme.warning
        draw_text(surf, title, (cx, 170), self.theme, self.layout,
                  pt=FONT_H1 + 10, centre=True, colour=colour)
        who = self._hand_finger_words(res.get("hand", mode.hand),
                                      int(res.get("finger", 0)))
        draw_text(surf, who, (cx, 232), self.theme, self.layout,
                  pt=FONT_BODY + 2, centre=True, colour=self.theme.muted)
        if label == "NoSignal":
            rows = [
                ("Sensor data", "missing for this run"),
                ("The run", "was not scored"),
            ]
        else:
            tic = (res.get("tic") or 0.0) * 100.0
            mae = res.get("mae") or 0.0
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
            self.draw_next_countdown(
                surf, f"Next run in {left:.0f}s", y + 96)

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
