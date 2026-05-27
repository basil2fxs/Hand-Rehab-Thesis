"""Pygame widget primitives. Buttons, text, lane strips, font caching.

I bumped the default font sizes up a fair bit so this reads as a proper
clinic-grade app rather than a debug tool. Most numbers below are tuned
against a 1280x800 screen at font_scale=1.0.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable

import pygame

from .theme import Theme


# Standard sizes used across screens. Pulled into constants so I don't end
# up with magic numbers scattered around the file.
FONT_TITLE = 56
FONT_H1 = 36
FONT_H2 = 26
FONT_BODY = 20
FONT_SMALL = 14
FONT_BUTTON = 22

BUTTON_H = 60         # default touch-target height
BUTTON_W = 320
PADDING = 24


@dataclass
class Layout:
    width: int
    height: int
    font_scale: float = 1.0

    def __post_init__(self) -> None:
        # Cache fonts so we don't pay SysFont's lookup cost on every draw call.
        self._fonts: dict[int, pygame.font.Font] = {}

    @property
    def gutter(self) -> int:
        return int(PADDING * self.font_scale)

    def font(self, pt: int) -> pygame.font.Font:
        size = int(pt * self.font_scale)
        f = self._fonts.get(size)
        if f is None:
            # Pick the first SysFont in the list that exists on this machine.
            f = pygame.font.SysFont("Helvetica,Arial,DejaVu Sans", size)
            self._fonts[size] = f
        return f

    def invalidate_fonts(self) -> None:
        self._fonts.clear()


def _darker(c: tuple[int, int, int], amount: float = 0.25) -> tuple[int, int, int]:
    """Quick helper for the drop-shadow / pressed-state colour. Just scales
    the RGB channels down a bit so the shadow reads as the same hue."""
    return (
        max(0, int(c[0] * (1 - amount))),
        max(0, int(c[1] * (1 - amount))),
        max(0, int(c[2] * (1 - amount))),
    )


class Button:
    """Big rounded button with a subtle drop-shadow.

    The shadow is just a second rect offset by a few pixels, drawn in a
    darker version of the fill. Cheap and reads as depth from across the
    room which is what we want for a clinic device.
    """

    SHADOW_OFFSET = 4
    BORDER_RADIUS = 12

    def __init__(self, rect: pygame.Rect, label: str,
                 on_click: Callable[[], None],
                 theme: Theme, layout: Layout,
                 font_pt: int = FONT_BUTTON,
                 primary: bool = False,
                 colour: tuple[int, int, int] | None = None) -> None:
        self.rect = rect
        self.label = label
        self.on_click = on_click
        self.theme = theme
        self.layout = layout
        self.font_pt = font_pt
        # `primary=True` uses the theme accent (blue). `colour=(r,g,b)`
        # overrides everything and pins this button to a specific fill,
        # e.g. green for "GO" actions independent of the theme accent.
        self.primary = primary
        self.colour = colour
        self.hover = False
        self.pressed = False

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.pressed = True
                self.on_click()
        elif e.type == pygame.MOUSEBUTTONUP:
            self.pressed = False

    def draw(self, surf: pygame.Surface) -> None:
        # Explicit override wins. Otherwise primary -> accent, else muted.
        if self.colour is not None:
            base = self.colour
            # Slight brighten on hover so we still feel feedback even
            # without falling back to the theme accent.
            if self.hover:
                base = tuple(min(255, c + 22) for c in base)
        elif self.primary:
            base = self.theme.accent
        else:
            base = self.theme.muted
            if self.hover:
                base = self.theme.accent
        fill = _darker(base, 0.15) if self.pressed else base
        # Shadow rectangle sits below and right of the actual button.
        shadow = self.rect.move(0, self.SHADOW_OFFSET if not self.pressed else 1)
        pygame.draw.rect(surf, _darker(fill, 0.5), shadow,
                          border_radius=self.BORDER_RADIUS)
        # Main button
        pygame.draw.rect(surf, fill, self.rect, border_radius=self.BORDER_RADIUS)
        # Bright top edge to suggest a light source from above
        top_edge = pygame.Rect(self.rect.x + 6, self.rect.y + 4,
                                self.rect.w - 12, 2)
        bright = tuple(min(255, c + 30) for c in fill)
        pygame.draw.rect(surf, bright, top_edge, border_radius=2)

        font = self.layout.font(self.font_pt)
        # Pick a label colour with good contrast against the fill.
        avg = sum(fill) / 3
        text_colour = self.theme.background if avg > 140 else (255, 255, 255)
        text = font.render(self.label, True, text_colour)
        surf.blit(text, text.get_rect(center=self.rect.center))


class Card:
    """A subtle panel background. Used to group related controls so the
    eye doesn't get lost on a busy screen."""

    BORDER_RADIUS = 16

    def __init__(self, rect: pygame.Rect, theme: Theme,
                 title: str | None = None,
                 layout: Layout | None = None) -> None:
        self.rect = rect
        self.theme = theme
        self.title = title
        self.layout = layout

    def draw(self, surf: pygame.Surface) -> None:
        # Soft shadow.
        shadow = self.rect.move(0, 3)
        pygame.draw.rect(surf, _darker(self.theme.muted, 0.6), shadow,
                          border_radius=self.BORDER_RADIUS)
        # The card body uses a slightly different shade from the page bg
        # so it reads as a raised panel.
        body_colour = tuple(
            max(0, min(255, c - 8)) for c in self.theme.background
        )
        pygame.draw.rect(surf, body_colour, self.rect,
                          border_radius=self.BORDER_RADIUS)
        # Optional 1px outline so the card has a clean edge on light themes.
        pygame.draw.rect(surf, self.theme.muted, self.rect, 1,
                          border_radius=self.BORDER_RADIUS)
        if self.title and self.layout:
            font = self.layout.font(FONT_H2)
            t = font.render(self.title, True, self.theme.accent)
            surf.blit(t, (self.rect.x + PADDING, self.rect.y + 16))


def draw_text(surf: pygame.Surface, text: str, pos: tuple[int, int],
              theme: Theme, layout: Layout, pt: int = FONT_BODY,
              centre: bool = False,
              colour: tuple[int, int, int] | None = None) -> pygame.Rect:
    font = layout.font(pt)
    r = font.render(text, True, colour or theme.foreground)
    rect = r.get_rect()
    if centre:
        rect.center = pos
    else:
        rect.topleft = pos
    surf.blit(r, rect)
    return rect


class LaneStrip:
    """One finger lane. Big finger name, hand-coloured border, hit flash."""

    FINGER_LABELS = ["Index", "Middle", "Ring", "Little"]
    # Border + badge colours per hand. Blue for right, teal for left.
    # The left used to be red but that clashed with the miss-flash red,
    # so a left-hand tile in its default state looked like a permanent miss.
    HAND_BADGE = {
        "right": (37, 99, 235),    # blue
        "left":  (13, 148, 136),   # teal
    }

    def __init__(self, lane: int, rect: pygame.Rect,
                 theme: Theme, layout: Layout, hand: str = "right",
                 finger: int | None = None) -> None:
        self.lane = lane
        self.rect = rect
        self.theme = theme
        self.layout = layout
        self.hand = hand
        # `finger` is the within-hand index (0=index..3=little). Without it
        # the global lane number could look like a fifth finger when we wrap
        # past 4 in bilateral mode.
        self.finger = finger if finger is not None else (lane % 4)
        self.active = False
        self.flash_until = 0.0
        self.flash_colour: tuple[int, int, int] | None = None
        # `glow_until` drives a brief halo effect when this lane gets a press.
        # Separate from flash so we can tune them independently.
        self.glow_until = 0.0
        self.value: int = 0
        self.baseline: float = 0.0
        # Timing-bar state. The bar fills the active lane and shrinks down
        # to nothing over the trial's timeout window so the patient can see
        # how long they have left to press. `_timing_stim_t` is the perf
        # counter value when the stim fired; `_timing_timeout` is the
        # window length in seconds. None means no bar is showing.
        self._timing_stim_t: float | None = None
        self._timing_timeout: float = 1.0

    def arm_timing(self, stim_t: float, timeout_s: float) -> None:
        """Start a timing bar on this lane. Called when its stim fires."""
        self._timing_stim_t = stim_t
        self._timing_timeout = max(0.05, timeout_s)

    def clear_timing(self) -> None:
        """Drop the timing bar (trial complete, hit or miss)."""
        self._timing_stim_t = None

    def flash(self, colour: tuple[int, int, int], duration_s: float, now: float) -> None:
        self.flash_colour = colour
        self.flash_until = now + duration_s
        # Add a halo at the same time so the lane really pops when scored.
        self.glow_until = now + duration_s

    def draw(self, surf: pygame.Surface, now: float) -> None:
        # Background fill
        if now < self.flash_until and self.flash_colour:
            fill = self.flash_colour
        elif self.active:
            fill = self.theme.lane_active[self.finger % len(self.theme.lane_active)]
        else:
            fill = self.theme.lane_idle[self.finger % len(self.theme.lane_idle)]

        # Halo behind the strip during the glow window. Larger rect, semi-
        # transparent so the lane appears to pulse outward briefly.
        if now < self.glow_until:
            halo = self.rect.inflate(28, 28)
            ts = pygame.Surface(halo.size, pygame.SRCALPHA)
            alpha = int(150 * (self.glow_until - now) / 0.4)  # fade out
            alpha = max(0, min(180, alpha))
            pygame.draw.rect(ts, (*fill, alpha), ts.get_rect(),
                              border_radius=22)
            surf.blit(ts, halo.topleft)

        pygame.draw.rect(surf, fill, self.rect, border_radius=14)
        border = self.HAND_BADGE.get(self.hand, self.theme.foreground)
        # Thicker border when the lane is the current target so it stands out.
        border_w = 6 if self.active else 3
        pygame.draw.rect(surf, border, self.rect, border_w, border_radius=14)

        # Hand badge: filled circle top-left, big letter inside.
        badge_r = 22
        bx = self.rect.x + badge_r + 8
        by = self.rect.y + badge_r + 8
        pygame.draw.circle(surf, border, (bx, by), badge_r)
        pygame.draw.circle(surf, self.theme.background, (bx, by), badge_r, 3)
        badge_font = self.layout.font(20)
        letter = self.hand[0].upper() if self.hand else "?"
        text = badge_font.render(letter, True, self.theme.background)
        surf.blit(text, text.get_rect(center=(bx, by)))

        # Big finger label centred near the bottom of the strip.
        font = self.layout.font(32)
        label_text = self.FINGER_LABELS[self.finger % 4]
        label = font.render(label_text, True, self.theme.foreground)
        surf.blit(label, label.get_rect(midbottom=(
            self.rect.centerx, self.rect.bottom - 44,
        )))

        # Hand strapline below the finger name in the hand colour.
        hand_font = self.layout.font(FONT_SMALL + 2)
        hand_word = ("Right hand" if self.hand == "right"
                     else "Left hand" if self.hand == "left" else "")
        if hand_word:
            hl = hand_font.render(hand_word, True, border)
            surf.blit(hl, hl.get_rect(midbottom=(
                self.rect.centerx, self.rect.bottom - 16,
            )))

        # FSR live readout top-right corner. Small so it doesn't fight the
        # finger name during gameplay.
        small = self.layout.font(FONT_SMALL)
        info = small.render(f"{int(self.value)}/{int(self.baseline)}",
                            True, self.theme.muted)
        surf.blit(info, info.get_rect(topright=(self.rect.right - 8,
                                                 self.rect.top + 8)))

        # Timing bar. Renders a vertical bar down the right edge of the
        # lane showing how much of the press window is left. Coloured by
        # zone (green = Great timing, yellow = Good, orange = Late) so the
        # patient knows roughly which band their press will land in.
        if self._timing_stim_t is not None:
            elapsed = now - self._timing_stim_t
            remaining = max(0.0, self._timing_timeout - elapsed)
            frac = remaining / self._timing_timeout
            # Bar runs vertically inside the lane on the right edge.
            bar_w = 14
            bar_x = self.rect.right - bar_w - 14
            bar_top = self.rect.top + 70
            bar_h = self.rect.height - 200
            # Background track so the bar is visible even when empty.
            pygame.draw.rect(surf, self.theme.background,
                              (bar_x, bar_top, bar_w, bar_h),
                              border_radius=6)
            pygame.draw.rect(surf, self.theme.muted,
                              (bar_x, bar_top, bar_w, bar_h), 2,
                              border_radius=6)
            # Fill the bar from the top down by `frac` of its height.
            fill_h = int(bar_h * frac)
            # Pick the colour by where in the window we currently are.
            #   first 200ms      = Great (green)
            #   200..500ms       = Good (yellow)
            #   500..end         = Late (orange/red)
            if elapsed <= 0.2:
                bar_colour = self.theme.success
            elif elapsed <= 0.5:
                bar_colour = self.theme.warning
            else:
                bar_colour = self.theme.error
            if fill_h > 0:
                pygame.draw.rect(surf, bar_colour,
                                  (bar_x + 2, bar_top + 2,
                                   bar_w - 4, fill_h - 4),
                                  border_radius=4)


class FloatingText:
    """One-shot floating text that fades up the screen. Drives the
    'Great +3' style hit popups during gameplay, plus the bigger
    encouragement banners like 'Nice!' on a hit streak."""

    def __init__(self, text: str, pos: tuple[int, int],
                 colour: tuple[int, int, int],
                 font_pt: int = 36,
                 lifetime_s: float = 0.9,
                 rise_px: int = 60) -> None:
        self.text = text
        self.start_pos = pos
        self.colour = colour
        self.font_pt = font_pt
        self.lifetime_s = lifetime_s
        self.rise_px = rise_px
        self.born = time.perf_counter()

    @property
    def alive(self) -> bool:
        return (time.perf_counter() - self.born) < self.lifetime_s

    def draw(self, surf: pygame.Surface, layout: Layout) -> None:
        age = time.perf_counter() - self.born
        frac = max(0.0, min(1.0, age / self.lifetime_s))
        y_offset = int(self.rise_px * frac)
        alpha = int(255 * (1.0 - frac))
        font = layout.font(self.font_pt)
        text = font.render(self.text, True, self.colour)
        text.set_alpha(alpha)
        rect = text.get_rect(center=(self.start_pos[0],
                                      self.start_pos[1] - y_offset))
        surf.blit(text, rect)


class TextInput:
    """Single-line text field with a blinking caret. Used on the setup
    screen so the therapist can type the patient's name and age before a
    session starts.

    Click the field to focus, type to add, Backspace to delete, Enter or
    Tab to defocus. Optional `numeric=True` restricts input to digits
    (used for the age field).
    """

    BORDER_RADIUS = 10
    PADDING_X = 14
    CARET_BLINK_S = 0.55

    def __init__(self, rect: pygame.Rect, theme: Theme, layout: Layout,
                 label: str = "",
                 placeholder: str = "",
                 initial: str = "",
                 max_len: int = 32,
                 numeric: bool = False,
                 font_pt: int = FONT_BODY + 2) -> None:
        self.rect = rect
        self.theme = theme
        self.layout = layout
        self.label = label
        self.placeholder = placeholder
        self.text = str(initial)
        self.max_len = max_len
        self.numeric = numeric
        self.font_pt = font_pt
        self.focused = False
        self.hover = False
        self._born = time.perf_counter()

    @property
    def value(self) -> str:
        return self.text.strip()

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.focused = self.rect.collidepoint(e.pos)
        elif e.type == pygame.KEYDOWN and self.focused:
            if e.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif e.key in (pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                # Defocus on Enter / Tab / Esc so global handlers can
                # still react to those keys.
                self.focused = False
            else:
                ch = e.unicode
                # Filter to printable ASCII + space for safety. Names can
                # technically contain unicode but the CSV layer keeps
                # things simple if we stick to ASCII.
                if ch and ch.isprintable() and len(self.text) < self.max_len:
                    if self.numeric and not ch.isdigit():
                        return
                    self.text += ch

    def draw(self, surf: pygame.Surface) -> None:
        # Label sits above the field.
        if self.label:
            lbl_font = self.layout.font(FONT_SMALL + 4)
            lbl = lbl_font.render(self.label, True, self.theme.muted)
            surf.blit(lbl, (self.rect.x, self.rect.y - 26))
        # Border + fill. Brighter accent border when focused so the caret
        # cue is obvious; subtle border at rest.
        border = (self.theme.accent if self.focused
                   else self.theme.foreground if self.hover
                   else self.theme.muted)
        # Field background is a touch darker than the page so it reads
        # like a sunken slot.
        body_colour = tuple(
            max(0, min(255, c - 14)) for c in self.theme.background
        )
        pygame.draw.rect(surf, body_colour, self.rect,
                          border_radius=self.BORDER_RADIUS)
        pygame.draw.rect(surf, border, self.rect,
                          width=2 if self.focused else 1,
                          border_radius=self.BORDER_RADIUS)
        # Text or placeholder.
        font = self.layout.font(self.font_pt)
        display = self.text if self.text else self.placeholder
        text_colour = (self.theme.foreground if self.text
                        else self.theme.muted)
        text_surf = font.render(display, True, text_colour)
        text_rect = text_surf.get_rect(
            midleft=(self.rect.x + self.PADDING_X, self.rect.centery),
        )
        # Clip the text to the field so a long name doesn't bleed out.
        prev_clip = surf.get_clip()
        surf.set_clip(self.rect.inflate(-6, -6))
        surf.blit(text_surf, text_rect)
        surf.set_clip(prev_clip)
        # Blinking caret at the end of the text when focused.
        if self.focused:
            phase = (time.perf_counter() - self._born) % (self.CARET_BLINK_S * 2)
            if phase < self.CARET_BLINK_S:
                caret_x = text_rect.right + 2 if self.text else (
                    self.rect.x + self.PADDING_X
                )
                pygame.draw.line(
                    surf, self.theme.accent,
                    (caret_x, self.rect.y + 10),
                    (caret_x, self.rect.bottom - 10),
                    width=2,
                )


class Slider:
    """Horizontal value slider with a draggable knob. Used on the
    classic-mode setup screen to let the therapist tune the pace
    before starting a block.

    Click anywhere on the track to jump the knob there; click-and-drag
    the knob for fine adjustment. Value is in the half-open range
    [min_value, max_value] and snaps to `step` increments so the
    therapist gets clean numbers like 0.6 / 0.8 / 1.0 s, not 0.7831 s.
    """

    TRACK_H = 6
    KNOB_R = 14
    LABEL_GAP = 30

    def __init__(self, rect: pygame.Rect, theme: Theme, layout: Layout,
                 min_value: float, max_value: float,
                 initial: float,
                 step: float = 0.1,
                 label: str = "",
                 value_format: str = "{:.2f}") -> None:
        self.rect = rect
        self.theme = theme
        self.layout = layout
        self.min_value = float(min_value)
        self.max_value = float(max_value)
        self.step = float(step)
        self.label = label
        self.value_format = value_format
        self.value = self._snap(max(min_value, min(max_value, initial)))
        self._dragging = False
        self._hover = False

    def _snap(self, v: float) -> float:
        # Snap to step grid relative to min_value.
        if self.step <= 0:
            return v
        n = round((v - self.min_value) / self.step)
        return round(self.min_value + n * self.step, 6)

    def _value_to_x(self, v: float) -> int:
        frac = (v - self.min_value) / (self.max_value - self.min_value)
        return int(self.rect.x + frac * self.rect.w)

    def _x_to_value(self, x: int) -> float:
        frac = (x - self.rect.x) / max(1, self.rect.w)
        frac = max(0.0, min(1.0, frac))
        return self._snap(self.min_value
                            + frac * (self.max_value - self.min_value))

    def handle_event(self, e: pygame.event.Event) -> None:
        # Generous hit rect so the knob is easy to grab.
        hit_rect = self.rect.inflate(0, self.KNOB_R * 2)
        if e.type == pygame.MOUSEMOTION:
            self._hover = hit_rect.collidepoint(e.pos)
            if self._dragging:
                self.value = self._x_to_value(e.pos[0])
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if hit_rect.collidepoint(e.pos):
                self._dragging = True
                self.value = self._x_to_value(e.pos[0])
        elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self._dragging = False

    def draw(self, surf: pygame.Surface) -> None:
        # Label above the track.
        if self.label:
            lbl_font = self.layout.font(FONT_SMALL + 4)
            lbl = lbl_font.render(self.label, True, self.theme.muted)
            surf.blit(lbl, (self.rect.x, self.rect.y - self.LABEL_GAP))
            # Current value right-aligned.
            val_font = self.layout.font(FONT_BODY)
            val_text = self.value_format.format(self.value)
            val = val_font.render(val_text, True, self.theme.accent)
            surf.blit(val, val.get_rect(
                topright=(self.rect.right, self.rect.y - self.LABEL_GAP - 2)))
        # Track background (full width, faint).
        track_y = self.rect.centery - self.TRACK_H // 2
        track_rect = pygame.Rect(self.rect.x, track_y,
                                  self.rect.w, self.TRACK_H)
        track_surf = pygame.Surface(track_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(track_surf, (*self.theme.muted, 90),
                          track_surf.get_rect(),
                          border_radius=self.TRACK_H // 2)
        surf.blit(track_surf, track_rect.topleft)
        # Filled portion up to the knob position.
        knob_x = self._value_to_x(self.value)
        fill_w = max(0, knob_x - self.rect.x)
        if fill_w > 0:
            fill_surf = pygame.Surface((fill_w, self.TRACK_H), pygame.SRCALPHA)
            pygame.draw.rect(fill_surf, (*self.theme.accent, 220),
                              fill_surf.get_rect(),
                              border_radius=self.TRACK_H // 2)
            surf.blit(fill_surf, (self.rect.x, track_y))
        # Knob.
        knob_centre = (knob_x, self.rect.centery)
        # Soft shadow.
        shadow_surf = pygame.Surface(
            (self.KNOB_R * 2 + 6, self.KNOB_R * 2 + 6), pygame.SRCALPHA,
        )
        pygame.draw.circle(shadow_surf, (0, 0, 0, 60),
                            (self.KNOB_R + 3, self.KNOB_R + 4),
                            self.KNOB_R + 1)
        surf.blit(shadow_surf,
                   (knob_centre[0] - self.KNOB_R - 3,
                    knob_centre[1] - self.KNOB_R - 3))
        pygame.draw.circle(surf, self.theme.accent, knob_centre, self.KNOB_R)
        # Hover ring.
        if self._hover or self._dragging:
            pygame.draw.circle(surf, self.theme.foreground,
                                knob_centre, self.KNOB_R + 2, 2)
