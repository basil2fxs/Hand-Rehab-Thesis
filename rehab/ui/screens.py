"""Screen classes. Title, mode select, setup, gameplay, rhythm, results.

I keep the same Screen base + subclass pattern Satoru used, but the
layouts are heavier on the fonts and use the Card / Button widgets so it
feels like a finished app instead of a debug dashboard.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pygame

from .theme import Theme
from .widgets import (
    Button, Card, FloatingText, LaneStrip, Layout, Slider, TextInput,
    FONT_TITLE, FONT_H1, FONT_H2, FONT_BODY, FONT_SMALL,
    BUTTON_H, BUTTON_W, PADDING, draw_text,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


class Screen:
    def __init__(self, engine: "GameEngine") -> None:
        self.engine = engine
        self.theme: Theme = engine.theme
        self.layout: Layout = engine.layout

    def handle_event(self, e: pygame.event.Event) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surf: pygame.Surface) -> None: ...


def _draw_header(surf: pygame.Surface, title: str, subtitle: str,
                 theme: Theme, layout: Layout) -> None:
    """Reused at the top of every menu screen so they all match."""
    cx = layout.width // 2
    draw_text(surf, title, (cx, 90), theme, layout,
              pt=FONT_H1 + 4, centre=True, colour=theme.accent)
    if subtitle:
        draw_text(surf, subtitle, (cx, 140), theme, layout,
                  pt=FONT_BODY, centre=True, colour=theme.muted)


class TitleScreen(Screen):
    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        cx = engine.layout.width // 2

        # Participant name input. Set once on the title screen and reused
        # for every block the patient plays this app session, so every
        # CSV row + every session folder is tagged with the same name.
        # Pre-fill from any persisted value so quitting and reopening the
        # title screen doesn't blank out the name.
        prefill = str(engine.cfg.get("session.participant") or "")
        if prefill in ("None", "NA"):
            prefill = ""
        input_w = 460
        self.name_input = TextInput(
            pygame.Rect(cx - input_w // 2, 430, input_w, 54),
            self.theme, self.layout,
            label="",
            placeholder="Type a name for this session",
            initial=prefill,
            max_len=40,
        )

        # Primary action. Pushes the typed name into the session + config
        # before navigating to mode select. Filled in green (independent
        # of the blue theme accent) so it reads as a "go" action.
        self.start_btn = Button(
            pygame.Rect(cx - BUTTON_W // 2, 520, BUTTON_W, BUTTON_H + 12),
            "START SESSION", self._begin,
            self.theme, self.layout,
            font_pt=FONT_H2,
            colour=(34, 197, 94),     # green
        )
        # Quit stays as a small text link below the START button.
        self.quit_rect = pygame.Rect(cx - 60, 605, 120, 32)
        # Settings moved to the bottom-right corner so it stays out of
        # the way of the primary START flow. It opens the diagnostics +
        # COM port mapping screen for verifying FSR sensors / keyboard
        # fallback before a session.
        sw, sh = 160, 36
        self.settings_rect = pygame.Rect(
            engine.layout.width - sw - 24,
            engine.layout.height - sh - 24,
            sw, sh,
        )

    def _begin(self) -> None:
        name = self.name_input.value or "NA"
        self.engine.cfg.data.setdefault("session", {})["participant"] = name
        self.engine.session.participant = name
        self.engine.show_mode_select()

    def refresh(self) -> None:
        """Re-sync the name field with the current cfg value. Called by
        engine.show_title() so coming BACK to the title (e.g. via Esc on
        mode select, which clears the participant) shows the cleared
        state instead of the stale text from last time."""
        prefill = str(self.engine.cfg.get("session.participant") or "")
        if prefill in ("None", "NA"):
            prefill = ""
        self.name_input.text = prefill
        self.name_input.focused = False

    def handle_event(self, e: pygame.event.Event) -> None:
        # Text input first so a click in the field claims focus before any
        # button hit-test runs underneath.
        self.name_input.handle_event(e)
        self.start_btn.handle_event(e)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.quit_rect.collidepoint(e.pos):
                self.engine.request_quit()
            elif self.settings_rect.collidepoint(e.pos):
                self.engine.show_diagnostics()
        # Enter key on the focused name field acts as a shortcut for Start
        # so a therapist on a keyboard doesn't have to grab the mouse.
        if (e.type == pygame.KEYDOWN
                and e.key == pygame.K_RETURN
                and self.name_input.focused):
            self._begin()

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        cx = self.layout.width // 2

        # Decorative concentric rings behind the title. The outermost
        # ring pulses gently so the page feels alive without distracting
        # from the START button. Phase comes from time.perf_counter so
        # it's smooth even when the screen idles.
        ring_centre = (cx, 230)
        import math
        pulse_phase = time.perf_counter() * 0.5         # ~0.5 Hz
        pulse = (math.sin(pulse_phase) + 1.0) * 0.5     # 0..1
        for r, base_alpha, pulse_amt in (
            (230, 14, 14),
            (180, 24, 10),
            (130, 36, 6),
            (80,  50, 0),
        ):
            alpha = int(base_alpha + pulse_amt * pulse)
            ring_surf = pygame.Surface(
                (r * 2 + 8, r * 2 + 8), pygame.SRCALPHA,
            )
            pygame.draw.circle(ring_surf,
                                (*self.theme.accent, alpha),
                                (r + 4, r + 4), r, 3)
            surf.blit(ring_surf, (ring_centre[0] - r - 4,
                                    ring_centre[1] - r - 4))

        # Big bold title. Subtle drop-shadow under the letters for a
        # slight sense of depth without going gamey.
        title_text = "FINGER REHAB"
        title_font = self.layout.font(FONT_TITLE + 18)
        shadow = title_font.render(title_text, True,
                                    (*self.theme.accent, 60))
        shadow.set_alpha(70)
        surf.blit(shadow, shadow.get_rect(center=(cx + 3, 233)))
        draw_text(surf, title_text,
                  (cx, 230), self.theme, self.layout,
                  pt=FONT_TITLE + 18, centre=True, colour=self.theme.accent)
        # Tagline.
        draw_text(surf, "Multi-modal finger rehabilitation",
                  (cx, 305), self.theme, self.layout,
                  pt=FONT_BODY + 4, centre=True, colour=self.theme.muted)

        # Mode pill row. Three rounded pills in violet so they read as
        # the three modes the patient can pick from on the next screen,
        # not as buttons themselves. A small caption under the row sets
        # that expectation explicitly.
        pills = ["ADAPTIVE", "CLASSIC", "RHYTHM"]
        pill_font = self.layout.font(FONT_SMALL + 2)
        pill_w = []
        for name in pills:
            tw = pill_font.render(name, True, (255, 255, 255)).get_width()
            pill_w.append(tw + 32)
        pill_h = 30
        gap = 14
        row_w = sum(pill_w) + gap * (len(pills) - 1)
        x = cx - row_w // 2
        py = 350
        pill_colour = (139, 92, 246)      # violet
        for w, name in zip(pill_w, pills):
            r = pygame.Rect(x, py, w, pill_h)
            pygame.draw.rect(surf, pill_colour, r,
                              border_radius=pill_h // 2)
            text = pill_font.render(name, True, (255, 255, 255))
            surf.blit(text, text.get_rect(center=r.center))
            x += w + gap

        # Participant name input sits between the mode pills and the
        # Start button. Patient types here once and every game logs to
        # the same name.
        self.name_input.draw(surf)

        # Primary Start button - the only obvious thing to do.
        self.start_btn.draw(surf)

        # Quit stays as a low-key text link under the START button.
        mx, my = pygame.mouse.get_pos()
        hover_q = self.quit_rect.collidepoint((mx, my))
        col_q = self.theme.foreground if hover_q else self.theme.muted
        draw_text(surf, "Quit", self.quit_rect.center,
                  self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=col_q)
        if hover_q:
            pygame.draw.line(surf, col_q,
                              (self.quit_rect.centerx - 22,
                               self.quit_rect.centery + 14),
                              (self.quit_rect.centerx + 22,
                               self.quit_rect.centery + 14), 1)

        # Settings sits in the bottom-right corner as a small pill with
        # a cog glyph + label. Filled background so it reads as a button,
        # not a footer text link.
        hover_s = self.settings_rect.collidepoint((mx, my))
        bg = (self.theme.accent if hover_s
              else tuple(max(0, c - 30) for c in self.theme.background))
        fg = ((255, 255, 255) if hover_s else self.theme.muted)
        pygame.draw.rect(surf, bg, self.settings_rect, border_radius=10)
        # Cog glyph + label. Using a circle + cross-hair as a tiny icon
        # so we don't depend on a Unicode glyph being available in the
        # default pygame font.
        icon_cx = self.settings_rect.x + 22
        icon_cy = self.settings_rect.centery
        pygame.draw.circle(surf, fg, (icon_cx, icon_cy), 9, 2)
        pygame.draw.circle(surf, fg, (icon_cx, icon_cy), 3)
        draw_text(surf, "Settings",
                  (self.settings_rect.x + 44, icon_cy - 1),
                  self.theme, self.layout, pt=FONT_BODY,
                  centre=False, colour=fg)

        # Footer credit, anchored to the bottom.
        draw_text(surf, "Thesis - Basil Toufexis - 19757049",
                  (cx, self.layout.height - 40),
                  self.theme, self.layout, pt=FONT_SMALL,
                  centre=True, colour=self.theme.muted)


class ModeSelectScreen(Screen):
    """Pick adaptive / classic / rhythm. Each option is a card with a
    short description so a clinician can pick without prior knowledge."""

    MODES = [
        ("adaptive", "Adaptive",
         "Difficulty adjusts to keep you in the 70-80% hit band."),
        ("classic", "Classic",
         "Fixed pace, set finger pattern. Best for baseline measures."),
        ("rhythm", "Rhythm",
         "Press to the beat of music. Engaging and motor-rhythm focused."),
    ]

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.buttons: list[Button] = []
        cx = engine.layout.width // 2
        card_w = 560
        # One big card per mode, stacked. Click anywhere on the card to pick.
        # No default highlight so the therapist makes an active choice.
        for i, (key, title, _desc) in enumerate(self.MODES):
            y = 230 + i * 130
            self.buttons.append(Button(
                pygame.Rect(cx - card_w // 2, y, card_w, 100),
                title, lambda k=key: self._pick(k),
                self.theme, self.layout,
                font_pt=FONT_H2 + 2,
            ))
        self.back_btn = Button(
            pygame.Rect(40, engine.layout.height - 90, 180, BUTTON_H - 10),
            "Back", engine.show_title,
            self.theme, self.layout,
        )

    def _pick(self, mode_key: str) -> None:
        self.engine.cfg.data.setdefault("game", {})["mode"] = mode_key
        self.engine.show_setup()

    def handle_event(self, e: pygame.event.Event) -> None:
        for b in self.buttons + [self.back_btn]:
            b.handle_event(e)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        _draw_header(surf, "PICK A MODE",
                     "Which training pattern do you want this session to use?",
                     self.theme, self.layout)
        # Draw each card-style button plus its description text overlaid
        # underneath the title inside the button rect.
        for i, (b, (_, title, desc)) in enumerate(zip(self.buttons, self.MODES)):
            b.draw(surf)
            # The button draws the title; here we add the description on
            # a second line of its own.
            draw_text(surf, desc,
                      (b.rect.centerx, b.rect.bottom - 22),
                      self.theme, self.layout, pt=FONT_BODY - 2,
                      centre=True,
                      colour=self.theme.background if b.hover or b.primary
                      else self.theme.foreground)
        self.back_btn.draw(surf)


class SetupScreen(Screen):
    """Hand picker. The participant name was already set on the title
    screen and is reused for every block this app session, so this
    screen has nothing to type, just three big buttons."""

    HANDS = [
        ("right", "Right hand", "4 fingers, index to little"),
        ("left",  "Left hand",  "4 fingers, index to little"),
        ("both",  "Both hands", "8 fingers, bilateral training"),
    ]

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        cx = engine.layout.width // 2

        # Pace slider for classic mode. Pre-fill from the config so a
        # therapist who's tweaked the value in YAML sees their choice.
        # Range 0.4 s to 3.0 s in 0.1 s steps - matches the slowest the
        # adaptive engine can crawl (~3 s per stim) up to a snappy pace
        # for stronger patients.
        initial = float(engine.cfg.get("game.trigger_interval_s", 1.2))
        slider_w = 520
        self.pace_slider = Slider(
            pygame.Rect(cx - slider_w // 2, 240, slider_w, 30),
            self.theme, self.layout,
            min_value=0.4, max_value=3.0,
            initial=initial, step=0.1,
            label="CLASSIC PACE  (seconds between stimuli)",
            value_format="{:.1f} s",
        )

        self.buttons: list[Button] = []
        button_w = 300
        button_gap = 28
        button_total_w = button_w * 3 + button_gap * 2
        start_x = cx - button_total_w // 2
        button_y = 360
        for i, (key, label, _desc) in enumerate(self.HANDS):
            r = pygame.Rect(start_x + i * (button_w + button_gap), button_y,
                            button_w, 190)
            self.buttons.append(Button(
                r, label, lambda k=key: self._pick(k),
                self.theme, self.layout,
                font_pt=FONT_H2,
                # No default selection - therapist makes an active pick.
            ))
        self.back_btn = Button(
            pygame.Rect(40, engine.layout.height - 90, 180, BUTTON_H - 10),
            "Back", engine.show_mode_select,
            self.theme, self.layout,
        )

    def _pick(self, hand: str) -> None:
        # Update hand mode + rebuild detectors / lane strips for the new
        # layout, then start the block in whichever mode the user picked.
        # Participant name was already pushed into session/config by the
        # title screen so we don't touch it here.
        self.engine.cfg.data.setdefault("bilateral", {})["hand"] = hand
        self.engine.hand_mode = hand
        self.engine.session.hand = hand
        self.engine._build_detectors()
        for key in ("gameplay", "rhythm"):
            sc = self.engine._screens.get(key)
            if sc and hasattr(sc, "rebuild_lanes"):
                sc.rebuild_lanes()
        mode = self.engine.cfg.get("game.mode", "adaptive")
        if mode == "classic":
            # Persist the slider's chosen pace into the config so the
            # ClassicMode constructor reads it back when the block starts.
            self.engine.cfg.data.setdefault("game", {})[
                "trigger_interval_s"] = self.pace_slider.value
            self.engine.begin_classic_block()
        elif mode == "rhythm":
            self.engine.show_rhythm_setup()
        else:
            self.engine.begin_adaptive_block()

    def handle_event(self, e: pygame.event.Event) -> None:
        # Slider first so a click on the knob isn't intercepted by an
        # adjacent button hit-test. Only let it respond when classic
        # mode is the active pick.
        if self.engine.cfg.get("game.mode") == "classic":
            self.pace_slider.handle_event(e)
        for b in self.buttons + [self.back_btn]:
            b.handle_event(e)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        # Header tells the therapist which patient this session belongs to
        # so they have one more reminder before kicking off a block under
        # the wrong name.
        name = self.engine.session.participant or "NA"
        _draw_header(surf, "WHICH HAND?",
                     f"Session for {name}. Pick a hand to begin.",
                     self.theme, self.layout)
        # Classic mode gets a pace slider above the hand buttons so the
        # therapist can tune trigger_interval_s without editing YAML.
        if self.engine.cfg.get("game.mode") == "classic":
            self.pace_slider.draw(surf)
        for b, (_, _, desc) in zip(self.buttons, self.HANDS):
            b.draw(surf)
            draw_text(surf, desc,
                      (b.rect.centerx, b.rect.bottom + 26),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.muted)
        self.back_btn.draw(surf)


class GameplayScreen(Screen):
    """Classic + Adaptive view. Big score top-centre, lane strips, hit popups."""

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.message = ""
        self.message_until = 0.0
        self.lanes: list[LaneStrip] = []
        # Floating "+3 Great!" popups go in here and fade themselves out.
        self._popups: list[FloatingText] = []
        # Score pulse: when the score jumps we kick off a short scale-up
        # animation on the big number so the patient sees a real reaction.
        self._last_score_seen = 0
        self._score_pulse_t = 0.0
        self.rebuild_lanes()

    # How much empty space sits between the two hand blocks in bilateral
    # mode. Big enough that the two hand groups read as clearly separate.
    HAND_BLOCK_GAP = 120

    def rebuild_lanes(self) -> None:
        """4 strips unilateral, 8 strips bilateral.

        Bilateral layout mirrors the patient: left hand on the LEFT side of
        the screen (little finger on the outer edge, index closest to
        centre, matching `a s d f` on a keyboard); right hand on the RIGHT
        side (index nearest centre, little on the outer edge, matching
        `j k l ;`).

        We keep `self.lanes[i].lane == i` so any lookup elsewhere that
        indexes by lane number still works. Only the per-lane rect moves.
        """
        self.lanes = []
        hand = self.engine.hand_mode
        if hand == "both":
            half_w = (self.layout.width - self.HAND_BLOCK_GAP) // 2
            block_w = half_w - 40
            gutter = 18
            n = 4
            w = (block_w - gutter * (n - 1)) // n
            y = 220
            h = self.layout.height - 360
            # Pre-compute the rect for each lane number, then append the
            # strips in lane-number order so self.lanes[i].lane == i.
            rects: dict[int, pygame.Rect] = {}
            # Left hand sits on the LEFT side. Reading left-to-right the
            # visual order is little, ring, middle, index (lanes 7,6,5,4).
            left_x_start = 40
            for pos in range(n):
                lane_num = 7 - pos      # pos 0 -> 7, pos 3 -> 4
                rects[lane_num] = pygame.Rect(
                    left_x_start + pos * (w + gutter), y, w, h,
                )
            # Right hand sits on the RIGHT side. Reading left-to-right the
            # visual order is index, middle, ring, little (lanes 0,1,2,3).
            right_x_start = half_w + self.HAND_BLOCK_GAP
            for pos in range(n):
                lane_num = pos          # pos 0 -> 0, pos 3 -> 3
                rects[lane_num] = pygame.Rect(
                    right_x_start + pos * (w + gutter), y, w, h,
                )
            for i in range(8):
                is_left = i >= 4
                # finger is the within-hand finger index (0=index, 3=little).
                finger = i - 4 if is_left else i
                self.lanes.append(LaneStrip(
                    lane=i, rect=rects[i],
                    theme=self.theme, layout=self.layout,
                    hand="left" if is_left else "right",
                    finger=finger,
                ))
        else:
            self._build_lane_block(hand, lane_offset=0, n=4,
                                    x_start=80,
                                    block_w=self.layout.width - 160)

    def _build_lane_block(self, hand: str, lane_offset: int, n: int,
                          x_start: int, block_w: int) -> None:
        """Lay out a single hand's lanes. For the LEFT hand we mirror the
        visual order so the little finger sits on the outer (left) edge
        and the index sits closest to the centre, matching how the left
        hand rests on a s d f."""
        gutter = 18
        w = (block_w - gutter * (n - 1)) // n
        y = 220
        h = self.layout.height - 360
        # Visual order of lane numbers across the block, left-to-right.
        if hand == "left":
            order = [n - 1 - i for i in range(n)]    # e.g. [3, 2, 1, 0]
        else:
            order = list(range(n))                    # [0, 1, 2, 3]
        # Pre-compute each lane's rect, then append in lane-number order so
        # self.lanes[i].lane == i for any downstream lookup-by-id code.
        rects: dict[int, pygame.Rect] = {}
        for pos, lane_num in enumerate(order):
            rects[lane_num] = pygame.Rect(
                x_start + pos * (w + gutter), y, w, h,
            )
        for i in range(n):
            self.lanes.append(LaneStrip(
                lane=lane_offset + i,
                rect=rects[i],
                theme=self.theme, layout=self.layout,
                hand=hand,
                finger=i,
            ))

    def flash_lane(self, lane: int, colour: tuple[int, int, int],
                   duration_s: float, now: float) -> None:
        for ls in self.lanes:
            if ls.lane == lane:
                ls.flash(colour, duration_s, now)
                # Float a quick popup above the lane that just scored.
                self._spawn_popup(ls, colour)

    def _spawn_popup(self, lane: LaneStrip,
                      colour: tuple[int, int, int]) -> None:
        if not self.message:
            return
        # Points appended to the label make the feedback feel chunky and
        # game-like rather than clinical only.
        text = self.message
        x = lane.rect.centerx
        y = lane.rect.top + 30
        self._popups.append(FloatingText(text, (x, y), colour, font_pt=42))

    def set_message(self, text: str, duration_s: float) -> None:
        self.message = text
        self.message_until = time.perf_counter() + duration_s

    def add_encouragement(self, text: str) -> None:
        # Encouragement banners sit centred just below the score HUD so they
        # don't overlap the lane strips. Bigger, brighter, and stick around
        # longer than the per-trial "Great +3" popups.
        cx = self.layout.width // 2
        self._popups.append(FloatingText(
            text, (cx, 200), self.theme.success,
            font_pt=FONT_TITLE - 4,
            lifetime_s=1.8,
            rise_px=40,
        ))

    def update(self, dt: float) -> None:
        if self.engine.paused:
            return
        # Garbage-collect dead popups so we don't keep rendering them.
        self._popups = [p for p in self._popups if p.alive]
        if self.engine.mode and hasattr(self.engine.mode, "update"):
            self.engine.mode.update(dt)

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.engine.mode and hasattr(self.engine.mode, "handle_event"):
            self.engine.mode.handle_event(e)

    # ---- HUD helpers -------------------------------------------------------
    def _progress(self) -> tuple[int, int]:
        """Return (done, total) trials for the active mode. Classic uses the
        sequence index; adaptive tracks `completed` and `total_trials`."""
        m = self.engine.mode
        if m is None:
            return (0, 0)
        if hasattr(m, "total_trials") and hasattr(m, "completed"):
            return (int(m.completed), int(m.total_trials))
        if hasattr(m, "sequence") and hasattr(m, "idx"):
            return (int(m.idx), len(m.sequence))
        return (0, 0)

    def _draw_chip(self, surf: pygame.Surface,
                    centre: tuple[int, int],
                    text: str,
                    fg: tuple[int, int, int],
                    bg_alpha: int = 38,
                    pad_x: int = 16, pad_y: int = 6,
                    font_pt: int = FONT_BODY) -> None:
        """Small rounded pill background behind a label. Used for the
        hits / misses / streak / multiplier counters so they read as
        discrete chunks of information instead of free-floating text."""
        font = self.layout.font(font_pt)
        text_surf = font.render(text, True, fg)
        chip_w = text_surf.get_width() + pad_x * 2
        chip_h = text_surf.get_height() + pad_y * 2
        chip_rect = pygame.Rect(0, 0, chip_w, chip_h)
        chip_rect.center = centre
        chip_surf = pygame.Surface(chip_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(chip_surf, (*fg, bg_alpha),
                          chip_surf.get_rect(), border_radius=chip_h // 2)
        surf.blit(chip_surf, chip_rect.topleft)
        surf.blit(text_surf, text_surf.get_rect(center=centre))

    def _draw_progress_bar(self, surf: pygame.Surface,
                            done: int, total: int) -> None:
        """Slim full-width bar near the top of the screen that fills as the
        session progresses. Tells the patient how much is left without
        forcing them to count trials."""
        if total <= 0:
            return
        pad = 30
        bar_y = 14
        bar_h = 6
        bar_w = self.layout.width - pad * 2
        frac = max(0.0, min(1.0, done / total))
        # Track (full width, faint).
        track_surf = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(track_surf, (*self.theme.muted, 70),
                          track_surf.get_rect(), border_radius=bar_h // 2)
        surf.blit(track_surf, (pad, bar_y))
        # Fill (accent colour, proportional width).
        fill_w = max(0, int(bar_w * frac))
        if fill_w > 0:
            fill_surf = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
            pygame.draw.rect(fill_surf, (*self.theme.accent, 220),
                              fill_surf.get_rect(), border_radius=bar_h // 2)
            surf.blit(fill_surf, (pad, bar_y))

    # ---- draw --------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        cx = self.layout.width // 2

        # Score-pulse trigger: kick the animation any time the engine's
        # score actually changes so the patient sees the number react.
        if self.engine.score != self._last_score_seen:
            self._score_pulse_t = time.perf_counter()
            self._last_score_seen = self.engine.score

        # ---- Top HUD ----
        # Layout target: panel from y=10 to y=210, lane strips start at
        # y=220. Everything inside the panel uses y-coords < 210.
        done, total = self._progress()
        hud_panel = pygame.Rect(cx - 420, 10, 840, 200)
        panel_surf = pygame.Surface(hud_panel.size, pygame.SRCALPHA)
        pygame.draw.rect(panel_surf, (*self.theme.muted, 32),
                          panel_surf.get_rect(), border_radius=18)
        surf.blit(panel_surf, hud_panel.topleft)

        # Progress bar runs along the top edge of the panel.
        self._draw_progress_bar(surf, done, total)

        # Top-left corner: patient name + trial counter.
        name = self.engine.session.participant or "NA"
        draw_text(surf, name, (30, 28),
                  self.theme, self.layout, pt=FONT_SMALL + 4,
                  colour=self.theme.muted)
        if total > 0:
            draw_text(surf, f"Trial {done}/{total}",
                      (30, 52), self.theme, self.layout,
                      pt=FONT_BODY, colour=self.theme.foreground)

        # Top-right corner: mode badge + adaptive pace.
        mode_label = self.engine.current_block.title().upper()
        mf = self.layout.font(FONT_SMALL + 4)
        mt_label = mf.render(mode_label, True, self.theme.muted)
        surf.blit(mt_label,
                   mt_label.get_rect(topright=(self.layout.width - 30, 28)))
        if (self.engine.mode is not None
                and hasattr(self.engine.mode, "adapter")):
            bpm = getattr(self.engine.mode.adapter, "bpm", None)
            pl = (self.engine.mode.adapter.pace_label()
                   if hasattr(self.engine.mode.adapter, "pace_label")
                   else "")
            if bpm and pl:
                pace_text = f"{pl}   {int(bpm)} BPM"
                pf = self.layout.font(FONT_BODY)
                pst = pf.render(pace_text, True, self.theme.accent)
                surf.blit(pst,
                           pst.get_rect(topright=(self.layout.width - 30, 52)))

        # Centre: big score with a brief pulse on change.
        draw_text(surf, "SCORE",
                  (cx, 32), self.theme, self.layout, pt=FONT_SMALL + 2,
                  centre=True, colour=self.theme.muted)
        age_pulse = time.perf_counter() - self._score_pulse_t
        if age_pulse < 0.35 and self._score_pulse_t > 0:
            pulse_scale = 1.0 + (1.0 - age_pulse / 0.35) * 0.18
            score_pt = int(FONT_TITLE * pulse_scale)
        else:
            score_pt = FONT_TITLE
        draw_text(surf, f"{self.engine.score}",
                  (cx, 82), self.theme, self.layout, pt=score_pt,
                  centre=True, colour=self.theme.accent)

        # Stats chips: hits / hit-rate / misses on a single row.
        total_trials_done = self.engine.hits + self.engine.misses
        rate = (self.engine.hits / total_trials_done
                 if total_trials_done else 0.0)
        # Chip row sits below the big score; streak row sits below that.
        # The y-coords are tight so the chips don't collide with the
        # bilateral hand header drawn at y=192 below.
        chip_y = 140
        self._draw_chip(surf, (cx - 200, chip_y),
                         f"HITS  {self.engine.hits}",
                         self.theme.success)
        if total_trials_done > 0:
            rate_colour = (self.theme.success if rate >= 0.7
                            else self.theme.warning if rate >= 0.5
                            else self.theme.error)
            self._draw_chip(surf, (cx, chip_y),
                             f"{rate * 100:.0f}% HIT RATE",
                             rate_colour)
        self._draw_chip(surf, (cx + 200, chip_y),
                         f"MISSES  {self.engine.misses}",
                         self.theme.error)

        # Streak + multiplier row. Hidden when there's nothing useful to
        # report so a fresh block doesn't have stale chips on screen.
        streak = self.engine.hit_streak
        streak_y = chip_y + 30
        if streak >= 1:
            streak_colour = (self.theme.success if streak >= 3
                              else self.theme.foreground)
            self._draw_chip(surf, (cx - 100, streak_y),
                             f"STREAK  {streak}",
                             streak_colour,
                             font_pt=FONT_SMALL + 4)
        mult = (self.engine._pace_multiplier()
                * self.engine._streak_multiplier())
        if mult > 1.05:
            mc = (self.theme.success if mult >= 1.5
                   else self.theme.warning)
            self._draw_chip(surf, (cx + 100, streak_y),
                             f"x{mult:.1f}", mc,
                             font_pt=FONT_SMALL + 4)

        # Bilateral hand headers sit ABOVE the lane strips, below the HUD.
        # Left hand is on the LEFT side of the screen, right hand on the
        # RIGHT, mirroring the patient.
        if self.engine.hand_mode == "both":
            right_colour = LaneStrip.HAND_BADGE["right"]
            left_colour = LaneStrip.HAND_BADGE["left"]
            draw_text(surf, "LEFT", (self.layout.width // 4, 192),
                      self.theme, self.layout, pt=FONT_H2,
                      centre=True, colour=left_colour)
            draw_text(surf, "RIGHT", (self.layout.width * 3 // 4, 192),
                      self.theme, self.layout, pt=FONT_H2,
                      centre=True, colour=right_colour)
            mid_x = self.layout.width // 2
            pygame.draw.line(surf, self.theme.muted,
                              (mid_x, 215),
                              (mid_x, self.layout.height - 80), 2)

        now = time.perf_counter()
        for ls in self.lanes:
            ls.draw(surf, now)

        # Floating hit/miss popups
        for p in self._popups:
            p.draw(surf, self.layout)

        # No footer hint. Patient is using the Arduino sensor device, so
        # any on-screen mention of keyboard shortcuts would be noise.

        if self.engine.paused:
            self._draw_paused_overlay(surf)

    def _draw_paused_overlay(self, surf: pygame.Surface) -> None:
        overlay = pygame.Surface(
            (self.layout.width, self.layout.height), pygame.SRCALPHA,
        )
        overlay.fill((0, 0, 0, 160))
        surf.blit(overlay, (0, 0))
        draw_text(surf, "PAUSED",
                  (self.layout.width // 2, self.layout.height // 2 - 30),
                  self.theme, self.layout, pt=FONT_TITLE + 20, centre=True,
                  colour=self.theme.warning)


class RhythmScreen(Screen):
    """Falling notes view for rhythm mode. 4 or 8 strike lanes depending
    on whether the session is bilateral."""

    LOOKAHEAD_S = 1.5

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.lanes: list[LaneStrip] = []
        self.message = ""
        self.message_until = 0.0
        self._popups: list[FloatingText] = []
        self.rebuild_lanes()

    HAND_BLOCK_GAP = 100   # bilateral spacing between right + left blocks

    def rebuild_lanes(self) -> None:
        """Strike lanes for the falling-note view. Layout mirrors the
        patient: left hand on the left of the screen, right hand on the
        right, with each hand's little finger on the outer edge.
        `self.lanes[i].lane == i` is preserved so the falling-note pipe
        (which looks up lanes by id) keeps working."""
        self.lanes = []
        hand_mode = self.engine.hand_mode
        gutter = 14
        # Strike lanes sit at the bottom third of the screen.
        y = self.layout.height - 240
        h = 180
        if hand_mode == "both":
            half_w = (self.layout.width - self.HAND_BLOCK_GAP) // 2
            n = 4
            block_w = half_w - 40
            w = (block_w - gutter * (n - 1)) // n
            rects: dict[int, pygame.Rect] = {}
            # Left hand on the LEFT: lanes 7, 6, 5, 4 reading left-to-right.
            left_x_start = 40
            for pos in range(n):
                lane_num = 7 - pos
                rects[lane_num] = pygame.Rect(
                    left_x_start + pos * (w + gutter), y, w, h,
                )
            # Right hand on the RIGHT: lanes 0, 1, 2, 3 reading left-to-right.
            right_x_start = half_w + self.HAND_BLOCK_GAP
            for pos in range(n):
                lane_num = pos
                rects[lane_num] = pygame.Rect(
                    right_x_start + pos * (w + gutter), y, w, h,
                )
            for i in range(8):
                is_left = i >= 4
                finger = i - 4 if is_left else i
                self.lanes.append(LaneStrip(
                    lane=i, rect=rects[i],
                    theme=self.theme, layout=self.layout,
                    hand="left" if is_left else "right",
                    finger=finger,
                ))
        else:
            n = 4
            w = (self.layout.width - 160 - gutter * (n - 1)) // n
            # Left-hand unilateral mirrors the block: little finger on the
            # outer left, index closest to centre.
            if hand_mode == "left":
                order = [n - 1 - i for i in range(n)]
            else:
                order = list(range(n))
            rects: dict[int, pygame.Rect] = {}
            for pos, lane_num in enumerate(order):
                rects[lane_num] = pygame.Rect(
                    80 + pos * (w + gutter), y, w, h,
                )
            for i in range(n):
                self.lanes.append(LaneStrip(
                    lane=i, rect=rects[i],
                    theme=self.theme, layout=self.layout,
                    hand=hand_mode, finger=i,
                ))

    def set_message(self, text: str, duration_s: float) -> None:
        self.message = text
        self.message_until = time.perf_counter() + duration_s

    @staticmethod
    def _fmt_mmss(seconds: float) -> str:
        """Format a duration as MM:SS, clamped to non-negative."""
        s = max(0, int(seconds))
        return f"{s // 60:d}:{s % 60:02d}"

    def _draw_song_progress(self, surf: pygame.Surface,
                             elapsed_s: float, total_s: float) -> None:
        """Thin progress bar plus an MM:SS readout so the patient knows
        how long is left in a rhythm session. Sits at the very top of
        the screen so it doesn't fight the lane area for attention."""
        pad = 30
        bar_y = 12
        bar_h = 6
        bar_w = self.layout.width - pad * 2
        frac = max(0.0, min(1.0, elapsed_s / total_s if total_s > 0 else 0.0))
        # Faint track behind the fill.
        track_surf = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(track_surf, (*self.theme.muted, 70),
                          track_surf.get_rect(), border_radius=bar_h // 2)
        surf.blit(track_surf, (pad, bar_y))
        fill_w = int(bar_w * frac)
        if fill_w > 0:
            fill_surf = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
            pygame.draw.rect(fill_surf, (*self.theme.accent, 220),
                              fill_surf.get_rect(), border_radius=bar_h // 2)
            surf.blit(fill_surf, (pad, bar_y))
        # Time readout right-aligned to the bar's end. Manual right-align
        # via font.render so the MM:SS sits flush with the screen edge.
        time_text = f"{self._fmt_mmss(elapsed_s)} / {self._fmt_mmss(total_s)}"
        tf = self.layout.font(FONT_SMALL + 2)
        ts = tf.render(time_text, True, self.theme.muted)
        surf.blit(ts, ts.get_rect(topright=(self.layout.width - pad,
                                              bar_y + bar_h + 6)))

    def add_encouragement(self, text: str) -> None:
        # Match the gameplay screen's banner placement (just below the
        # score) so the user gets the same visual rhythm in both modes.
        cx = self.layout.width // 2
        self._popups.append(FloatingText(
            text, (cx, 200), self.theme.success,
            font_pt=FONT_TITLE - 4,
            lifetime_s=1.8,
            rise_px=40,
        ))

    def flash_lane(self, lane: int, colour, duration_s: float, now: float) -> None:
        for ls in self.lanes:
            if ls.lane == lane:
                ls.flash(colour, duration_s, now)
                if self.message:
                    self._popups.append(FloatingText(
                        self.message, (ls.rect.centerx, ls.rect.top - 10),
                        colour, font_pt=36,
                    ))

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.engine.mode and hasattr(self.engine.mode, "handle_event"):
            self.engine.mode.handle_event(e)

    def update(self, dt: float) -> None:
        if self.engine.paused:
            return
        self._popups = [p for p in self._popups if p.alive]
        if self.engine.mode and hasattr(self.engine.mode, "update"):
            self.engine.mode.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        cx = self.layout.width // 2

        # Top HUD: progress bar, big score, song title.
        bm = getattr(self.engine.mode, "beatmap", None)
        # Song progress bar across the top of the screen. The patient can
        # see how far through the song they are without us tying it to
        # the score block. Skipped during the pre-roll countdown so we
        # don't display "song is over" before it's started.
        countdown_remaining = (
            getattr(self.engine.mode, "countdown_remaining_s", 0.0)
            if self.engine.mode else 0.0
        )
        if bm and bm.duration_s > 0 and countdown_remaining <= 0:
            song_t = getattr(self.engine.mode, "song_time", 0.0) or 0.0
            elapsed = max(0.0, min(song_t, bm.duration_s))
            self._draw_song_progress(surf, elapsed, bm.duration_s)

        if bm:
            draw_text(surf, bm.title, (cx, 40),
                      self.theme, self.layout, pt=FONT_BODY + 2,
                      centre=True, colour=self.theme.muted)
        draw_text(surf, "SCORE",
                  (cx, 70), self.theme, self.layout, pt=FONT_SMALL + 2,
                  centre=True, colour=self.theme.muted)
        draw_text(surf, f"{self.engine.score}",
                  (cx, 110), self.theme, self.layout, pt=FONT_TITLE,
                  centre=True, colour=self.theme.accent)
        # Streak counter beside the score so the patient can see their
        # current run. Green once they hit 3+ in a row.
        streak = self.engine.hit_streak
        streak_colour = (self.theme.success if streak >= 3
                          else self.theme.muted)
        streak_text = (f"STREAK  {streak}" if streak > 0
                        else "STREAK  -")
        draw_text(surf, streak_text,
                  (cx, 160), self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=streak_colour)

        # Countdown banner before the music kicks in.
        if self.engine.mode:
            countdown = getattr(self.engine.mode, "countdown_remaining_s", 0.0)
            if countdown > 0:
                draw_text(surf, "GET READY",
                          (cx, self.layout.height // 2 - 60),
                          self.theme, self.layout, pt=FONT_H1,
                          centre=True, colour=self.theme.muted)
                draw_text(surf, f"{countdown:.1f}",
                          (cx, self.layout.height // 2 + 40),
                          self.theme, self.layout, pt=140,
                          centre=True, colour=self.theme.accent)

        # Strike line is the y-coordinate the falling notes are aiming at.
        # I moved it up above the lane strips so the press-target rings
        # sit cleanly above the finger labels with no overlap.
        TARGET_R = 36
        now = time.perf_counter()
        strike_y = self.layout.height - 290

        # Falling notes first, BEFORE the strips. Each note slides from
        # top_y down to the strike line. The user presses when the falling
        # circle lands inside the target ring drawn below.
        if self.engine.mode and hasattr(self.engine.mode, "upcoming"):
            upcoming = self.engine.mode.upcoming(self.LOOKAHEAD_S)
            song_t = self.engine.mode.song_time
            top_y = 170
            for s in upcoming:
                ahead = s.note.t - song_t
                frac = 1.0 - max(0.0, min(1.0, ahead / self.LOOKAHEAD_S))
                y = int(top_y + (strike_y - top_y) * frac)
                if 0 <= s.note.lane < len(self.lanes):
                    ls = self.lanes[s.note.lane]
                    cx_note = ls.rect.centerx
                    near_target = abs(s.note.t - song_t) < 0.3
                    note_r = 30 if not near_target else 34
                    pygame.draw.circle(surf, self.theme.accent,
                                        (cx_note, y), note_r)
                    pygame.draw.circle(surf, self.theme.foreground,
                                        (cx_note, y), note_r, 3)
                    pygame.draw.circle(surf, self.theme.background,
                                        (cx_note, y), 12)

        # Now the lane strips (finger labels). Target rings get drawn last
        # so they sit on top of everything and the user can always see
        # exactly where to land the press.
        for ls in self.lanes:
            ls.draw(surf, now)

        # Target rings on top of everything. Outline only (not filled) so
        # the falling note remains visible inside the ring just before
        # the press lands. When the lane below is mid-flash from a
        # press outcome, the ring adopts the outcome colour AND fills
        # with a semi-transparent disc so the green / orange / red is
        # impossible to miss - the patient's eye is on the ring, not
        # the strip below.
        for ls in self.lanes:
            cx_t = ls.rect.centerx
            # Default ring style; thickens up and grows slightly when a
            # note is in the press window so the eye gets pulled there.
            ring_r = TARGET_R
            thickness = 5
            if self.engine.mode and hasattr(self.engine.mode, "upcoming"):
                upcoming = self.engine.mode.upcoming(self.LOOKAHEAD_S)
                close = [s for s in upcoming if s.note.lane == ls.lane]
                if close:
                    song_t = self.engine.mode.song_time
                    ahead = close[0].note.t - song_t
                    if -0.2 <= ahead <= 0.4:
                        ring_r = TARGET_R + 5
                        thickness = 9
            # Outcome flash overrides the hand colour so the press
            # result reads at a glance.
            is_flashing = (now < ls.flash_until
                            and ls.flash_colour is not None)
            if is_flashing:
                border_colour = ls.flash_colour
                # Filled disc inside the ring in the outcome colour at
                # high alpha so the ring really pops on the press.
                fill_surf = pygame.Surface(
                    (ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA,
                )
                pygame.draw.circle(fill_surf, (*ls.flash_colour, 170),
                                    (ring_r + 2, ring_r + 2), ring_r)
                surf.blit(fill_surf,
                           (cx_t - ring_r - 2, strike_y - ring_r - 2))
                thickness = max(thickness, 9)
            else:
                border_colour = ls.HAND_BADGE.get(ls.hand,
                                                    self.theme.foreground)
            # Faint outer halo so the ring really pops off the page.
            halo_surf = pygame.Surface(
                ((ring_r + 8) * 2, (ring_r + 8) * 2), pygame.SRCALPHA,
            )
            halo_alpha = 110 if is_flashing else 50
            pygame.draw.circle(halo_surf, (*border_colour, halo_alpha),
                                (ring_r + 8, ring_r + 8), ring_r + 8)
            surf.blit(halo_surf,
                       (cx_t - ring_r - 8, strike_y - ring_r - 8))
            # Outer ring outline in the active colour.
            pygame.draw.circle(surf, border_colour,
                                (cx_t, strike_y), ring_r, thickness)
            # Inner contrast ring for high-readability on any theme.
            # Skip during flash so the filled disc inside the ring stays
            # uninterrupted by a thin background ring.
            if not is_flashing:
                pygame.draw.circle(surf, self.theme.background,
                                    (cx_t, strike_y), ring_r - thickness, 2)

        # Floating hit/miss popups.
        for p in self._popups:
            p.draw(surf, self.layout)

        # No keyboard hints on screen. The patient is meant to be using
        # the Arduino device by this point.

        if self.engine.paused:
            overlay = pygame.Surface(
                (self.layout.width, self.layout.height), pygame.SRCALPHA,
            )
            overlay.fill((0, 0, 0, 160))
            surf.blit(overlay, (0, 0))
            draw_text(surf, "PAUSED",
                      (cx, self.layout.height // 2 - 30),
                      self.theme, self.layout, pt=FONT_TITLE + 20,
                      centre=True, colour=self.theme.warning)


class RhythmSetupScreen(Screen):
    """Two-column song-select style: track list on the left, song details
    + difficulty + preview/start on the right. Mirrors what music rhythm
    games like osu! and Guitar Hero do, which felt the most readable when
    I tried them. No BPM clutter, the track's own tempo is used."""

    DIFFICULTIES = ("easy", "medium", "hard")
    PREVIEW_S = 8.0

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self._tracks: list = []
        self._track_rects: list[tuple[pygame.Rect, object]] = []
        self._selected_track: str | None = None
        self._selected_difficulty = engine.cfg.get("rhythm.difficulty", "medium")
        self._previewing: bool = False
        self._preview_stop_at: float = 0.0
        self._scroll_y = 0
        self.refresh()
        # Layout: left half is the track list card, right half is the
        # song-detail panel with difficulty + preview + start.
        w = engine.layout.width
        h = engine.layout.height
        self._list_rect = pygame.Rect(40, 180, w // 2 - 60, h - 280)
        self._detail_rect = pygame.Rect(w // 2 + 20, 180, w // 2 - 60, h - 280)

        # Right-panel buttons. All positioned relative to the detail rect.
        dx = self._detail_rect.x
        dw = self._detail_rect.w
        # Difficulty pills, evenly spaced inside the panel.
        diff_y = self._detail_rect.bottom - 260
        pill_w = (dw - PADDING * 4) // 3
        self.easy_btn = Button(
            pygame.Rect(dx + PADDING, diff_y, pill_w, 56),
            "Easy", lambda: self._set_difficulty("easy"),
            self.theme, self.layout, font_pt=FONT_H2,
        )
        self.med_btn = Button(
            pygame.Rect(dx + PADDING * 2 + pill_w, diff_y, pill_w, 56),
            "Medium", lambda: self._set_difficulty("medium"),
            self.theme, self.layout, font_pt=FONT_H2,
        )
        self.hard_btn = Button(
            pygame.Rect(dx + PADDING * 3 + pill_w * 2, diff_y, pill_w, 56),
            "Hard", lambda: self._set_difficulty("hard"),
            self.theme, self.layout, font_pt=FONT_H2,
        )

        # Preview + start row.
        action_y = self._detail_rect.bottom - 90
        self.preview_btn = Button(
            pygame.Rect(dx + PADDING, action_y, dw // 2 - PADDING * 2, BUTTON_H),
            "Preview", self._toggle_preview,
            self.theme, self.layout, font_pt=FONT_H2,
        )
        self.start_btn = Button(
            pygame.Rect(dx + dw // 2 + PADDING // 2, action_y,
                         dw // 2 - PADDING * 2, BUTTON_H + 4),
            "START", self._start,
            self.theme, self.layout,
            font_pt=FONT_H2, primary=True,
        )

        # Footer buttons.
        self.back_btn = Button(
            pygame.Rect(40, h - 80, 180, BUTTON_H - 10),
            "Back", self._back_to_modes, self.theme, self.layout,
        )
        self.refresh_btn = Button(
            pygame.Rect(w - 220, h - 80, 180, BUTTON_H - 10),
            "Rescan", self.refresh,
            self.theme, self.layout, font_pt=FONT_BODY,
        )

    def refresh(self) -> None:
        music_dir = self.engine.cfg.resolve_path(
            self.engine.cfg.get("audio.music_dir", "assets/music")
        )
        found: list = []
        if music_dir.exists():
            for p in sorted(music_dir.iterdir()):
                if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".flac"):
                    found.append(p)
        self._tracks = found
        if not hasattr(self, "_durations"):
            self._durations = {}
        # Drop cache entries for tracks that vanished.
        live_keys = {str(p) for p in self._tracks}
        for k in list(self._durations.keys()):
            if k not in live_keys:
                del self._durations[k]
        # Pre-pick the first available track so the user can hit Start
        # straight away if the previous selection is gone.
        if self._selected_track and not any(str(t) == self._selected_track
                                             for t in self._tracks):
            self._selected_track = None
        if self._selected_track is None and self._tracks:
            self._selected_track = str(self._tracks[0])
        # Kick off duration probing in the background so the UI stays
        # responsive (librosa.get_duration is fast per-track but adds
        # up across many tracks). Rows show "..." until the worker
        # fills the cache.
        self._spawn_duration_worker()

    def _spawn_duration_worker(self) -> None:
        # Already running? Skip - the existing worker will pick up new
        # entries on its next iteration (it re-reads self._tracks each
        # time so a Rescan during scanning isn't a problem).
        thread = getattr(self, "_dur_thread", None)
        if thread is not None and thread.is_alive():
            return
        import threading
        try:
            import librosa
        except ImportError:
            librosa = None

        def _probe():
            if librosa is None:
                # Mark all tracks as "unknown" so the UI shows --:-- and
                # doesn't try again.
                for p in list(self._tracks):
                    self._durations.setdefault(str(p), None)
                return
            for p in list(self._tracks):
                key = str(p)
                if key in self._durations:
                    continue
                try:
                    self._durations[key] = float(
                        librosa.get_duration(path=key))
                except Exception:
                    self._durations[key] = None

        self._dur_thread = threading.Thread(
            target=_probe, daemon=True, name="rhythm-dur-probe",
        )
        self._dur_thread.start()

    @staticmethod
    def _fmt_mmss(seconds: float | None) -> str:
        if seconds is None or seconds <= 0:
            return "--:--"
        s = int(round(seconds))
        return f"{s // 60:d}:{s % 60:02d}"

    def _set_difficulty(self, d: str) -> None:
        if d in self.DIFFICULTIES:
            self._selected_difficulty = d

    def _stop_preview(self) -> None:
        if self.engine.audio and self._previewing:
            try:
                self.engine.audio.stop()
            except Exception:
                pass
        self._previewing = False
        self._preview_stop_at = 0.0

    def _toggle_preview(self) -> None:
        # Already playing? Cut it short.
        if self._previewing:
            self._stop_preview()
            return
        if not self._selected_track or self.engine.audio is None:
            return
        if self.engine.audio.play_song(self._selected_track):
            self._previewing = True
            self._preview_stop_at = time.perf_counter() + self.PREVIEW_S

    def _back_to_modes(self) -> None:
        self._stop_preview()
        self.engine.show_mode_select()

    def _start(self) -> None:
        from ..audio.beatmap import extract_beatmap
        self._stop_preview()
        if not self._selected_track:
            # Nothing selected. Refuse to start so the user picks one
            # from the list. The list pre-fills the first track on
            # refresh, so this only fires if the music folder is empty.
            return
        diff = self._selected_difficulty
        bm = extract_beatmap(self._selected_track,
                              difficulty=diff,
                              num_lanes=self.engine.total_lanes)
        self.engine.cfg.data.setdefault("rhythm", {})["difficulty"] = diff
        self.engine.begin_rhythm_block(bm)

    def update(self, dt: float) -> None:
        # Auto-stop the preview after PREVIEW_S seconds.
        if self._previewing and time.perf_counter() >= self._preview_stop_at:
            self._stop_preview()

    def handle_event(self, e: pygame.event.Event) -> None:
        for b in (self.easy_btn, self.med_btn, self.hard_btn,
                  self.preview_btn, self.start_btn,
                  self.back_btn, self.refresh_btn):
            b.handle_event(e)
        if e.type == pygame.MOUSEWHEEL:
            # Scroll the track list when the cursor is hovering it.
            mx, my = pygame.mouse.get_pos()
            if self._list_rect.collidepoint((mx, my)):
                self._scroll_y = max(0, self._scroll_y - e.y * 30)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for rect, path in self._track_rects:
                if rect.collidepoint(e.pos):
                    new_selection = str(path) if path is not None else None
                    if new_selection != self._selected_track:
                        self._stop_preview()
                    self._selected_track = new_selection
                    return

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        _draw_header(surf, "PICK A SONG",
                     "Choose a track and difficulty, then press START.",
                     self.theme, self.layout)
        self._draw_track_list(surf)
        self._draw_detail_panel(surf)
        self.back_btn.draw(surf)
        self.refresh_btn.draw(surf)

    def _draw_track_list(self, surf: pygame.Surface) -> None:
        # Left-half card with a scrolling track list. Each row is a card-
        # style tile rather than a plain rectangle so the selected one
        # stands out clearly.
        list_card = Card(self._list_rect, self.theme,
                          title="Tracks", layout=self.layout)
        list_card.draw(surf)
        self._track_rects = []
        # Clip the track rows to the inside of the card so they don't
        # bleed over the header / footer.
        inner = self._list_rect.inflate(-PADDING * 2, -PADDING * 2)
        inner.y = self._list_rect.y + 60
        inner.h = self._list_rect.h - 70
        surf.set_clip(inner)
        rows: list[tuple[str, object]] = [
            (p.name, p) for p in self._tracks
        ]
        row_h = 56
        y = inner.y - self._scroll_y
        for label, path in rows:
            r = pygame.Rect(inner.x, y, inner.w, row_h - 6)
            self._track_rects.append((r, path))
            selected = (
                (path is None and self._selected_track is None)
                or (path is not None and str(path) == self._selected_track)
            )
            # Soft background for every row, accent fill for the selected.
            if selected:
                pygame.draw.rect(surf, self.theme.accent, r, border_radius=8)
            else:
                pygame.draw.rect(surf, self.theme.muted, r, 1,
                                  border_radius=8)
            # Track name on the left, file extension chip on the right so
            # the row reads at a glance.
            text_colour = (self.theme.background if selected
                            else self.theme.foreground)
            draw_text(surf, label, (r.x + 16, r.y + 14),
                      self.theme, self.layout, pt=FONT_BODY,
                      colour=text_colour)
            if path is not None:
                # Show the song duration on the right. "..." while the
                # background probe is still working on it. Right-align
                # via the font's render rect so 0:47 and 4:32 line up.
                key = str(path)
                if key in self._durations:
                    dur_text = self._fmt_mmss(self._durations[key])
                else:
                    dur_text = "..."
                dfont = self.layout.font(FONT_SMALL + 2)
                dsurf = dfont.render(dur_text, True, text_colour)
                surf.blit(dsurf, dsurf.get_rect(
                    midright=(r.right - 16, r.centery)))
            y += row_h
        surf.set_clip(None)

    def _draw_detail_panel(self, surf: pygame.Surface) -> None:
        # Right-half card with the current selection's name, difficulty
        # buttons, and the preview / start actions.
        detail_card = Card(self._detail_rect, self.theme,
                            title="Selected", layout=self.layout)
        detail_card.draw(surf)
        dx = self._detail_rect.x
        dy = self._detail_rect.y
        dw = self._detail_rect.w

        # Track name. With the "No music" option gone there should always
        # be a real track selected when the music folder is populated.
        if self._selected_track:
            title = self._selected_track.rsplit("/", 1)[-1]
            if "." in title:
                title = title.rsplit(".", 1)[0].replace("_", " ")
        else:
            title = "No tracks found"
        draw_text(surf, title,
                  (dx + dw // 2, dy + 80),
                  self.theme, self.layout, pt=FONT_H2,
                  centre=True, colour=self.theme.foreground)
        subtitle = ("Beats detected from this track"
                     if self._selected_track
                     else "Drop an .mp3 into the music folder and rescan")
        draw_text(surf, subtitle,
                  (dx + dw // 2, dy + 120),
                  self.theme, self.layout, pt=FONT_BODY - 2,
                  centre=True, colour=self.theme.muted)

        # Difficulty label + pill buttons. The selected one shows primary
        # styling so it pops.
        draw_text(surf, "Difficulty",
                  (dx + dw // 2, self.easy_btn.rect.y - 36),
                  self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)
        for b, key in ((self.easy_btn, "easy"),
                        (self.med_btn, "medium"),
                        (self.hard_btn, "hard")):
            b.primary = (key == self._selected_difficulty)
            b.draw(surf)
        # Brief one-liner explaining what each difficulty does.
        diff_text = {
            "easy":   "Every 4th beat. Gentle pace for beginners.",
            "medium": "Every 2nd beat. Standard rehab pacing.",
            "hard":   "Every beat. Full tempo, more presses per minute.",
        }[self._selected_difficulty]
        draw_text(surf, diff_text,
                  (dx + dw // 2, self.easy_btn.rect.bottom + 22),
                  self.theme, self.layout, pt=FONT_SMALL + 2,
                  centre=True, colour=self.theme.foreground)

        # Preview + start buttons.
        self.preview_btn.label = (
            "Stop preview" if self._previewing else "Preview"
        )
        self.preview_btn.draw(surf)
        if self._selected_track is None and not self._previewing:
            overlay = pygame.Surface(self.preview_btn.rect.size,
                                      pygame.SRCALPHA)
            overlay.fill((128, 128, 128, 130))
            surf.blit(overlay, self.preview_btn.rect.topleft)
        self.start_btn.draw(surf)

        if self._previewing:
            remaining = max(0.0, self._preview_stop_at - time.perf_counter())
            draw_text(surf,
                      f"Previewing - {remaining:.1f}s",
                      (dx + dw // 4, self.preview_btn.rect.bottom + 18),
                      self.theme, self.layout, pt=FONT_SMALL + 2,
                      centre=True, colour=self.theme.accent)


class ResultsScreen(Screen):
    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        cx = engine.layout.width // 2
        self.again_btn = Button(
            pygame.Rect(cx - 250, 640, 220, BUTTON_H + 4),
            "Play again", engine.show_mode_select,
            self.theme, self.layout, font_pt=FONT_H2,
            primary=True,
        )
        self.title_btn = Button(
            pygame.Rect(cx + 30, 640, 220, BUTTON_H + 4),
            "Back to title", engine.show_title,
            self.theme, self.layout, font_pt=FONT_H2,
        )

    def handle_event(self, e: pygame.event.Event) -> None:
        self.again_btn.handle_event(e)
        self.title_btn.handle_event(e)

    # Grade thresholds from hit rate. S+ for near-perfect runs, D for low
    # accuracy. Same letter scheme rhythm games use.
    @staticmethod
    def _grade_for(rate: float) -> tuple[str, str]:
        if rate >= 0.95:
            return "S", "Outstanding work"
        if rate >= 0.85:
            return "A", "Great session"
        if rate >= 0.70:
            return "B", "Solid effort"
        if rate >= 0.50:
            return "C", "Keep practising"
        if rate >= 0.30:
            return "D", "Tough one - try again"
        return "E", "Reset and have another go"

    def _grade_colour(self, letter: str) -> tuple[int, int, int]:
        if letter == "S":
            return (255, 196, 0)               # gold
        if letter == "A":
            return self.theme.success
        if letter == "B":
            return self.theme.accent
        if letter == "C":
            return self.theme.warning
        return self.theme.error

    def _draw_stat_card(self, surf: pygame.Surface, rect: pygame.Rect,
                         label: str, value: str,
                         value_colour: tuple[int, int, int]) -> None:
        # Card body
        body = tuple(max(0, min(255, c - 8)) for c in self.theme.background)
        pygame.draw.rect(surf, body, rect, border_radius=14)
        pygame.draw.rect(surf, self.theme.muted, rect, 1, border_radius=14)
        # Small label up top, large value below.
        draw_text(surf, label, (rect.centerx, rect.y + 22),
                  self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)
        draw_text(surf, value, (rect.centerx, rect.y + 70),
                  self.theme, self.layout, pt=FONT_TITLE,
                  centre=True, colour=value_colour)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        cx = self.layout.width // 2

        total = self.engine.hits + self.engine.misses
        rate = 0.0 if total == 0 else self.engine.hits / total
        grade, blurb = self._grade_for(rate)
        grade_colour = self._grade_colour(grade)

        # Top banner.
        draw_text(surf, "SESSION COMPLETE",
                  (cx, 70), self.theme, self.layout, pt=FONT_H1,
                  centre=True, colour=self.theme.accent)
        draw_text(surf, blurb,
                  (cx, 115), self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)

        # Grade letter inside a ring. Big celebratory moment, the part the
        # patient and therapist see first.
        grade_centre = (cx, 240)
        ring_r = 90
        # Soft glow behind the ring.
        glow = pygame.Surface((ring_r * 2 + 40, ring_r * 2 + 40),
                               pygame.SRCALPHA)
        for i, alpha in ((20, 30), (12, 50), (4, 80)):
            pygame.draw.circle(glow, (*grade_colour, alpha),
                                (ring_r + 20, ring_r + 20), ring_r + i)
        surf.blit(glow, (grade_centre[0] - ring_r - 20,
                          grade_centre[1] - ring_r - 20))
        pygame.draw.circle(surf, grade_colour, grade_centre, ring_r, 6)
        # Letter itself, oversized.
        gfont = self.layout.font(110)
        gtext = gfont.render(grade, True, grade_colour)
        surf.blit(gtext, gtext.get_rect(center=grade_centre))

        # Stat cards row - score, hits, hit rate, misses.
        card_w = 200
        card_h = 130
        gap = 24
        total_w = card_w * 4 + gap * 3
        cards_x = cx - total_w // 2
        cards_y = 380
        self._draw_stat_card(
            surf,
            pygame.Rect(cards_x, cards_y, card_w, card_h),
            "SCORE", f"{self.engine.score}", self.theme.accent,
        )
        self._draw_stat_card(
            surf,
            pygame.Rect(cards_x + (card_w + gap), cards_y, card_w, card_h),
            "HITS", f"{self.engine.hits}", self.theme.success,
        )
        self._draw_stat_card(
            surf,
            pygame.Rect(cards_x + (card_w + gap) * 2, cards_y, card_w, card_h),
            "HIT RATE", f"{rate * 100:.0f}%", self.theme.foreground,
        )
        self._draw_stat_card(
            surf,
            pygame.Rect(cards_x + (card_w + gap) * 3, cards_y, card_w, card_h),
            "MISSES", f"{self.engine.misses}", self.theme.error,
        )

        # Path to saved session for the therapist's records.
        if self.engine.last_session_root:
            path = self.engine.last_session_root
            if len(path) > 90:
                path = "..." + path[-87:]
            draw_text(surf, f"Saved to: {path}",
                      (cx, 560), self.theme, self.layout, pt=FONT_SMALL + 2,
                      centre=True, colour=self.theme.muted)

        self.again_btn.draw(surf)
        self.title_btn.draw(surf)


class DiagnosticsScreen(Screen):
    """Settings + hardware test screen reachable from the title.

    Three jobs:
    1. Live FSR readout per lane (or keyboard-press feedback in keyboard
       mode) so the therapist can verify each finger before a session.
    2. Detect available COM ports and let the user assign which port
       belongs to the LEFT hand and which to the RIGHT. Saves to
       config/user_settings.yaml.
    3. A "Test STIM" button per hand that fires STIM:1..4 in sequence
       so the therapist can confirm each motor reacts.
    """

    # How long between sequential STIM:n pulses during the test. The
    # Arduino's stim pulse is 150 ms so 250 ms gives a clean gap.
    STIM_TEST_INTERVAL_S = 0.25

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.back_btn = Button(
            pygame.Rect(40, engine.layout.height - 90, 180, BUTTON_H - 10),
            "Back", engine.show_title,
            self.theme, self.layout,
        )
        self.lanes: list[LaneStrip] = []
        # Held-key tracker for keyboard mode. Key id -> pygame.K_*.
        self._held_keys: set[int] = set()
        # Hardware panel state -------------------------------------------
        self._detected_ports: list[str] = []   # latest port scan
        self._port_status: str = ""             # info / error banner
        # In-flight STIM test sequencer. Holds the queue of (hand_prefix,
        # lane_num) tuples and the time each should fire. Drained in
        # update() one entry at a time so the motors don't all pulse at
        # once.
        self._stim_queue: list[tuple[str, int, float]] = []
        # Buttons for the hardware panel built in `rebuild_panel`.
        self._panel_buttons: list[Button] = []
        self.rebuild_lanes()
        self.refresh_ports()
        self.rebuild_panel()

    # The bottom panel takes ~170 px so lanes shrink to fit. Without
    # this the hardware panel would overlap the lane strips.
    PANEL_HEIGHT = 170
    PANEL_GAP = 20

    def _lanes_bottom_y(self) -> int:
        return self.layout.height - 100 - self.PANEL_HEIGHT - self.PANEL_GAP

    def rebuild_lanes(self) -> None:
        """Show 4 or 8 lanes depending on the hand mode the user has
        configured. Mirrors the gameplay layout so the diagnostics
        screen LOOKS like the real game - if a lane is misbehaving in
        here, the same one will misbehave during play."""
        self.lanes = []
        hand = self.engine.hand_mode
        y = 220
        h = self._lanes_bottom_y() - y
        if hand == "both":
            # Same bilateral layout as GameplayScreen.
            half_w = (self.layout.width - 120) // 2
            block_w = half_w - 40
            gutter = 18
            n = 4
            w = (block_w - gutter * (n - 1)) // n
            rects: dict[int, pygame.Rect] = {}
            for pos in range(n):
                rects[7 - pos] = pygame.Rect(
                    40 + pos * (w + gutter), y, w, h)
            for pos in range(n):
                rects[pos] = pygame.Rect(
                    half_w + 120 + pos * (w + gutter), y, w, h)
            for i in range(8):
                is_left = i >= 4
                finger = i - 4 if is_left else i
                self.lanes.append(LaneStrip(
                    lane=i, rect=rects[i],
                    theme=self.theme, layout=self.layout,
                    hand="left" if is_left else "right",
                    finger=finger,
                ))
        else:
            gutter = 18
            n = 4
            w = (self.layout.width - 160 - gutter * (n - 1)) // n
            order = ([n - 1 - i for i in range(n)] if hand == "left"
                      else list(range(n)))
            rects = {lane_num: pygame.Rect(
                        80 + pos * (w + gutter), y, w, h)
                     for pos, lane_num in enumerate(order)}
            for i in range(n):
                self.lanes.append(LaneStrip(
                    lane=i, rect=rects[i],
                    theme=self.theme, layout=self.layout,
                    hand=hand, finger=i,
                ))

    # ---- hardware port mapping panel --------------------------------------

    def refresh_ports(self) -> None:
        """Re-scan the OS for available serial ports. Stores the result
        in self._detected_ports so the assignment buttons can cycle
        through them on next click."""
        try:
            from ..hardware.serial_source import list_available_ports
            self._detected_ports = [p.device for p in list_available_ports()]
        except Exception as e:
            self._detected_ports = []
            self._port_status = f"Port scan failed: {e}"

    def _current_port(self, hand: str) -> str | None:
        return self.engine.cfg.get(f"serial.{hand}_port")

    def _cycle_port(self, hand: str) -> None:
        """Click handler: cycle through detected ports + (unassigned)
        for the named hand and persist the new value."""
        options: list[str | None] = [None] + list(self._detected_ports)
        current = self._current_port(hand)
        try:
            idx = options.index(current)
        except ValueError:
            idx = 0
        new = options[(idx + 1) % len(options)]
        try:
            self.engine.cfg.save_user_overrides(
                {f"serial.{hand}_port": new})
            self._port_status = (
                f"Saved {hand}_port = {new or '(auto)'}. "
                "Restart to apply to the source."
            )
        except Exception as e:
            self._port_status = f"Save failed: {e}"
        self.rebuild_panel()

    def _start_stim_test(self, hand: str) -> None:
        """Queue STIM:1..N test pulses on the named hand. Sequenced so
        the patient can see each motor fire on its own."""
        n_per_hand = int(self.engine.cfg.get(
            "fsr.num_sensors_per_hand", 4))
        now = time.perf_counter()
        # Filter out any prior queue for this hand so a double-click
        # doesn't stack two tests.
        prefix = hand.upper()
        self._stim_queue = [(p, lane, t) for (p, lane, t)
                             in self._stim_queue if p != prefix]
        for i in range(n_per_hand):
            due = now + (i * self.STIM_TEST_INTERVAL_S)
            self._stim_queue.append((prefix, i + 1, due))
        self._port_status = (
            f"Testing {hand} hand: firing STIM:1..{n_per_hand} "
            f"with {int(self.STIM_TEST_INTERVAL_S * 1000)} ms gaps."
        )

    @staticmethod
    def _short_port(p: str) -> str:
        """Strip /dev/cu. and /dev/tty. prefixes so port labels fit in
        a button without the noisy path repeating every row."""
        for prefix in ("/dev/cu.", "/dev/tty.", "/dev/", "\\\\.\\"):
            if p.startswith(prefix):
                return p[len(prefix):]
        return p

    def _hand_button_label(self, hand: str) -> str:
        """Build the cycle-button label for one hand. Three states:
          - "(auto)" if no port saved -> picker will auto-detect
          - "<short port>" if the saved port is currently detected
          - "<short port> (missing)" if the saved port is set but not
            visible to the OS right now (Arduino unplugged since save)
        """
        current = self._current_port(hand)
        if current is None:
            return f"{hand.upper()}: (auto)"
        short = self._short_port(current)
        if current not in self._detected_ports:
            return f"{hand.upper()}: {short} (missing)"
        return f"{hand.upper()}: {short}"

    def rebuild_panel(self) -> None:
        """Build the bottom-panel buttons. Called on init + after any
        port-list change so labels reflect the current assignment."""
        self._panel_buttons = []
        panel_y = self.layout.height - 100 - self.PANEL_HEIGHT
        # Layout: header text + two rows (left, right) with the assign
        # cycle button + STIM test button + the refresh button.
        row_h = 40
        row_gap = 8
        rows_x = 40
        row_w = self.layout.width - 80
        # Cycle buttons (one per hand).
        for i, hand in enumerate(("left", "right")):
            y = panel_y + 50 + i * (row_h + row_gap)
            label = self._hand_button_label(hand)
            # Truncate if still too long after the short-port + prefix
            # work above. Rare on Mac, more likely on Windows COM1234
            # type names.
            if len(label) > 40:
                label = label[:37] + "..."
            self._panel_buttons.append(Button(
                pygame.Rect(rows_x, y, row_w // 2 - 10, row_h),
                label, lambda h=hand: self._cycle_port(h),
                self.theme, self.layout, font_pt=FONT_BODY - 2,
            ))
            self._panel_buttons.append(Button(
                pygame.Rect(rows_x + row_w // 2 + 10, y,
                             (row_w // 2 - 100), row_h),
                f"Test {hand.upper()} STIM",
                lambda h=hand: self._start_stim_test(h),
                self.theme, self.layout, font_pt=FONT_BODY - 2,
            ))
            self._panel_buttons.append(Button(
                pygame.Rect(rows_x + row_w - 80, y, 80, row_h),
                "Refresh" if i == 0 else "",
                self._rescan_ports if i == 0 else (lambda: None),
                self.theme, self.layout, font_pt=FONT_SMALL + 2,
            ))

    def _rescan_ports(self) -> None:
        self.refresh_ports()
        self._port_status = (
            f"Re-scanned. Found {len(self._detected_ports)} port(s)."
        )
        self.rebuild_panel()

    def handle_event(self, e: pygame.event.Event) -> None:
        self.back_btn.handle_event(e)
        for b in self._panel_buttons:
            b.handle_event(e)
        # Track held keys so the visual responds even when the source
        # doesn't push samples (keyboard mode).
        if e.type == pygame.KEYDOWN:
            self._held_keys.add(e.key)
        elif e.type == pygame.KEYUP:
            self._held_keys.discard(e.key)

    def _key_pressed_for_lane(self, lane: int, hand: str) -> bool:
        """In keyboard mode, decide whether the key bound to this lane
        is currently held. Looks up the active hand's keymap."""
        from ..game.modes._keys import keymap_for_hand, resolve_key
        km = self.engine.cfg.get(
            keymap_for_hand(self.engine.hand_mode), {},
        )
        for key_name, lane_idx in km.items():
            if lane_idx != lane:
                continue
            kc = resolve_key(key_name)
            if kc is not None and kc in self._held_keys:
                return True
        return False

    def update(self, dt: float) -> None:
        # Drain any queued STIM test pulses that have come due.
        if self._stim_queue:
            now = time.perf_counter()
            still: list[tuple[str, int, float]] = []
            for prefix, lane, due in self._stim_queue:
                if now >= due:
                    cmd = f"{prefix}:STIM:{lane}"
                    try:
                        ok = self.engine.source.send_command(cmd)
                        if not ok:
                            # Most likely no Arduino on that hand; surface
                            # the result so the therapist knows the test
                            # didn't actually fire.
                            self._port_status = (
                                f"{cmd} not delivered. Check the Arduino "
                                "is plugged in and assigned."
                            )
                    except Exception as e:
                        self._port_status = f"STIM send error: {e}"
                else:
                    still.append((prefix, lane, due))
            self._stim_queue = still
        # Mirror live FSR values from the source onto the lane strips.
        # On keyboard mode the values stay at 0 and we use _held_keys
        # to drive the active flag instead.
        if not self.lanes:
            return
        # Pull one sample if the source is pushing them.
        if self.engine.source.provides_samples:
            s = self.engine.source.get_sample(timeout=0)
            if s is not None:
                n_per_hand = int(self.engine.cfg.get(
                    "fsr.num_sensors_per_hand", 4))
                for i, ls in enumerate(self.lanes):
                    if i < len(s.values):
                        ls.value = s.values[i]
                        det = self.engine.detectors.get(ls.hand)
                        if det:
                            local = i % n_per_hand
                            b = det.baseline[local]
                            ls.baseline = b if b is not None else 0.0
                            # Active = currently pressed per detector.
                            ls.active = bool(det.pressed[local])
        # Keyboard fallback: light up via held keys.
        if not self.engine.source.provides_samples:
            for ls in self.lanes:
                ls.active = self._key_pressed_for_lane(ls.lane, ls.hand)

    def _connection_state(self) -> tuple[str, tuple[int, int, int]]:
        """Pick the status text + colour for the top-right badge.

        Four states:
          - KEYBOARD: source doesn't provide samples (no Arduino).
          - DISCONNECTED: source claims to provide samples but is_connected is False.
          - NO DATA: port is open but no FSR samples have arrived in the
            last ~1.5 s. This is the case Mac hits when it auto-grabs
            /dev/cu.Bluetooth-Incoming-Port, opens it fine, but never
            receives any data because there's no Arduino on the wire.
          - CONNECTED: port open AND samples flowing.
        """
        src = self.engine.source
        if not src.provides_samples:
            return ("KEYBOARD", self.theme.muted)
        if not src.is_connected:
            return ("DISCONNECTED", self.theme.error)
        has_data = getattr(src, "has_recent_data", None)
        if callable(has_data) and not has_data(1.5):
            return ("NO DATA", self.theme.error)
        return ("CONNECTED", self.theme.success)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        # Header.
        source_name = getattr(self.engine.source, "name", "?")
        state_text, state_colour = self._connection_state()
        sub = ("Press each finger in turn. The matching box should "
                "light up and the FSR reading should climb.")
        if state_text == "KEYBOARD":
            sub = ("Keyboard mode active. Press the keys for each "
                    "finger and the matching box will light up.")
        elif state_text == "DISCONNECTED":
            sub = ("Source not connected. Plug the Arduino in and "
                    "click Back / Start to retry.")
        elif state_text == "NO DATA":
            sub = ("Port is open but no FSR data is arriving. "
                    "Check the Arduino is sending FSR: lines. "
                    "Keyboard still works as a backup.")
        _draw_header(surf, "SENSOR TEST", sub, self.theme, self.layout)
        # Source name pill top-right. Strip "Source(...)" wrappers so
        # long names like KeyboardOnlySource don't clip off the edge.
        clean_name = source_name
        if "Source" in clean_name:
            clean_name = clean_name.replace("OnlySource", "")
            clean_name = clean_name.replace("Source", "")
        nfont = self.layout.font(FONT_SMALL + 4)
        nsurf = nfont.render(clean_name, True, self.theme.muted)
        surf.blit(nsurf,
                   nsurf.get_rect(topright=(self.layout.width - 30, 28)))
        sfont = self.layout.font(FONT_BODY)
        st = sfont.render(state_text, True, state_colour)
        surf.blit(st, st.get_rect(
            topright=(self.layout.width - 30, 50)))
        now = time.perf_counter()
        # Bilateral hand headers like the gameplay screen.
        if self.engine.hand_mode == "both":
            draw_text(surf, "LEFT", (self.layout.width // 4, 192),
                      self.theme, self.layout, pt=FONT_H2, centre=True,
                      colour=LaneStrip.HAND_BADGE["left"])
            draw_text(surf, "RIGHT", (self.layout.width * 3 // 4, 192),
                      self.theme, self.layout, pt=FONT_H2, centre=True,
                      colour=LaneStrip.HAND_BADGE["right"])
        for ls in self.lanes:
            ls.draw(surf, now)
        # Hardware port panel ------------------------------------------------
        panel_y = self.layout.height - 100 - self.PANEL_HEIGHT
        panel_rect = pygame.Rect(
            30, panel_y, self.layout.width - 60, self.PANEL_HEIGHT,
        )
        # Soft background card so the panel reads as a discrete block.
        bg = tuple(max(0, c - 14) for c in self.theme.background)
        pygame.draw.rect(surf, bg, panel_rect, border_radius=12)
        # Panel header.
        draw_text(surf,
                  "ARDUINO PORT ASSIGNMENT",
                  (panel_rect.x + 18, panel_rect.y + 8),
                  self.theme, self.layout, pt=FONT_SMALL + 4,
                  centre=False, colour=self.theme.muted)
        # Detected ports list, right-aligned in the header row. Show
        # short names (the basename after /dev/cu.) so multiple Mac
        # ports fit on one line.
        if self._detected_ports:
            shorts = [self._short_port(p) for p in self._detected_ports]
            detected_label = "Detected: " + ", ".join(shorts)
        else:
            detected_label = "No serial ports detected"
        if len(detected_label) > 110:
            detected_label = detected_label[:107] + "..."
        df = self.layout.font(FONT_SMALL + 2)
        ds = df.render(detected_label, True, self.theme.muted)
        surf.blit(ds, ds.get_rect(
            topright=(panel_rect.right - 18, panel_rect.y + 10)))
        # Buttons (cycle assignment, test STIM, refresh).
        for b in self._panel_buttons:
            b.draw(surf)
        # Status / info line at the bottom of the panel.
        if self._port_status:
            status = self._port_status
            if len(status) > 120:
                status = status[:117] + "..."
            draw_text(surf, status,
                      (panel_rect.centerx, panel_rect.bottom - 14),
                      self.theme, self.layout, pt=FONT_SMALL + 2,
                      centre=True, colour=self.theme.foreground)
        self.back_btn.draw(surf)
        # Footer hint.
        draw_text(surf, "Esc returns to the title screen",
                  (self.layout.width // 2, self.layout.height - 30),
                  self.theme, self.layout, pt=FONT_SMALL + 2,
                  centre=True, colour=self.theme.muted)
