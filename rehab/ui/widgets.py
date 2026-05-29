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

    # Soft drop shadow built from three offset rounded-rects with
    # decreasing alpha so the edge fades smoothly instead of cutting
    # off as a hard duplicate. (dy, alpha) per layer.
    _SHADOW_PASSES = ((1, 70), (3, 40), (6, 18))

    def draw(self, surf: pygame.Surface) -> None:
        # Pick the base fill colour by precedence:
        #   explicit colour > primary -> theme accent > muted (default)
        if self.colour is not None:
            base = self.colour
            if self.hover:
                base = tuple(min(255, c + 22) for c in base)
        elif self.primary:
            base = self.theme.accent
            if self.hover:
                base = tuple(min(255, c + 18) for c in base)
        else:
            base = self.theme.muted
            if self.hover:
                base = self.theme.accent
        fill = _darker(base, 0.18) if self.pressed else base

        # Multi-pass soft drop shadow. Each pass is a low-alpha black
        # rect offset slightly more than the last, so the composite
        # reads as a gentle fade rather than a hard duplicate. Pressed
        # state collapses the shadow so the button feels "pushed in".
        if self.pressed:
            passes = ((1, 60),)
        else:
            passes = self._SHADOW_PASSES
        shadow_surf = pygame.Surface(
            (self.rect.w + 12, self.rect.h + 12), pygame.SRCALPHA,
        )
        for dy, alpha in passes:
            pygame.draw.rect(
                shadow_surf, (0, 0, 0, alpha),
                pygame.Rect(6, 6 + dy, self.rect.w, self.rect.h),
                border_radius=self.BORDER_RADIUS,
            )
        surf.blit(shadow_surf, (self.rect.x - 6, self.rect.y - 6))

        # Body fill. Pressed buttons shift down by 1 px so the hand
        # feels the click visually as well.
        body_rect = self.rect.move(0, 1 if self.pressed else 0)
        pygame.draw.rect(surf, fill, body_rect,
                          border_radius=self.BORDER_RADIUS)

        # Subtle top "shine": a narrow inset surface of low-alpha
        # white across the top half. Drawn as its own SRCALPHA
        # surface so the rounded corners feather naturally.
        if not self.pressed:
            shine_h = max(8, body_rect.h // 3)
            shine_surf = pygame.Surface(
                (body_rect.w - 6, shine_h), pygame.SRCALPHA,
            )
            pygame.draw.rect(
                shine_surf, (255, 255, 255, 36),
                shine_surf.get_rect(),
                border_radius=max(2, self.BORDER_RADIUS - 4),
            )
            surf.blit(shine_surf,
                       (body_rect.x + 3, body_rect.y + 3))

        # Subtle bottom inner shadow: a thin dark line just inside
        # the lower edge. Reads as depth without the heavy bevel of a
        # full inset shadow.
        if not self.pressed:
            inner = pygame.Surface(
                (body_rect.w - 4, 4), pygame.SRCALPHA,
            )
            pygame.draw.rect(inner, (0, 0, 0, 35),
                              inner.get_rect(),
                              border_radius=2)
            surf.blit(inner,
                       (body_rect.x + 2, body_rect.bottom - 6))

        # Hover ring: a 2 px outline in white at low alpha so the
        # affordance reads on any background colour. Skipped while
        # pressed because the shifted body would clip the ring.
        if self.hover and not self.pressed:
            ring = pygame.Surface(
                (body_rect.w + 4, body_rect.h + 4), pygame.SRCALPHA,
            )
            pygame.draw.rect(
                ring, (255, 255, 255, 120),
                ring.get_rect(),
                width=2,
                border_radius=self.BORDER_RADIUS + 2,
            )
            surf.blit(ring,
                       (body_rect.x - 2, body_rect.y - 2))

        # Label. Contrast against the fill: dark text on light fills,
        # white on dark.
        if self.label:
            font = self.layout.font(self.font_pt)
            avg = sum(fill) / 3
            text_colour = (self.theme.background
                            if avg > 150 else (255, 255, 255))
            text = font.render(self.label, True, text_colour)
            surf.blit(text, text.get_rect(center=body_rect.center))


class Card:
    """A subtle panel background. Used to group related controls so the
    eye doesn't get lost on a busy screen.

    Visual treatment matches the polished Button: multi-pass soft drop
    shadow, raised body, subtle top-band highlight, thin outline. Cards
    feel like physical panels lifted off the page rather than coloured
    rectangles cut from it.
    """

    BORDER_RADIUS = 18
    # Same shadow recipe the Button uses, just one pass softer.
    _SHADOW_PASSES = ((2, 50), (6, 28), (12, 10))

    def __init__(self, rect: pygame.Rect, theme: Theme,
                 title: str | None = None,
                 layout: Layout | None = None) -> None:
        self.rect = rect
        self.theme = theme
        self.title = title
        self.layout = layout

    def draw(self, surf: pygame.Surface) -> None:
        # Multi-pass soft drop shadow built off-screen so the outermost
        # pass fades smoothly into the page background.
        shadow_surf = pygame.Surface(
            (self.rect.w + 24, self.rect.h + 24), pygame.SRCALPHA,
        )
        for dy, alpha in self._SHADOW_PASSES:
            pygame.draw.rect(
                shadow_surf, (0, 0, 0, alpha),
                pygame.Rect(12, 12 + dy, self.rect.w, self.rect.h),
                border_radius=self.BORDER_RADIUS,
            )
        surf.blit(shadow_surf, (self.rect.x - 12, self.rect.y - 12))
        # Card body: a touch darker than the page background so it
        # reads as a raised panel.
        body_colour = tuple(
            max(0, min(255, c - 8)) for c in self.theme.background
        )
        pygame.draw.rect(surf, body_colour, self.rect,
                          border_radius=self.BORDER_RADIUS)
        # Subtle top-band highlight, same trick as Button: an SRCALPHA
        # inset rect with low-alpha white. Reads as a hint of light
        # from above without going gel-buttony.
        shine_h = max(10, self.rect.h // 6)
        shine_surf = pygame.Surface(
            (self.rect.w - 12, shine_h), pygame.SRCALPHA,
        )
        pygame.draw.rect(
            shine_surf, (255, 255, 255, 28),
            shine_surf.get_rect(),
            border_radius=max(2, self.BORDER_RADIUS - 6),
        )
        surf.blit(shine_surf, (self.rect.x + 6, self.rect.y + 6))
        # Thin 1 px outline so the edge stays crisp.
        outline_colour = tuple(max(0, c - 30) for c in self.theme.background)
        pygame.draw.rect(surf, outline_colour, self.rect, 1,
                          border_radius=self.BORDER_RADIUS)
        # Optional title in the top-left corner.
        if self.title and self.layout:
            font = self.layout.font(FONT_H2)
            t = font.render(self.title, True, self.theme.accent)
            surf.blit(t, (self.rect.x + PADDING, self.rect.y + 18))


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


class Dropdown:
    """Click-to-open selector with a fixed list of options.

    Two-pass rendering: closed-state pill via `draw_closed`, then once
    all other widgets are drawn, an overlay popup via `draw_overlay`
    (skipped when closed). That keeps the open list on top of every
    other on-screen widget without z-ordering tricks.

    `options` is `[(value, label), ...]`. The Dropdown stores `value`
    in `current_value` and shows the matching `label`. `on_change` is
    called with the new value the moment a different option is picked.
    """

    ROW_H = 40
    BORDER_RADIUS = 8

    def __init__(self, rect: pygame.Rect,
                 options: list[tuple[object, str]],
                 current_value: object,
                 on_change: Callable[[object], None],
                 theme: Theme, layout: Layout,
                 placeholder: str = "(none)") -> None:
        self.rect = rect
        self.options = options
        self.current_value = current_value
        self.on_change = on_change
        self.theme = theme
        self.layout = layout
        self.placeholder = placeholder
        self.is_open = False
        self._hover_idx = -1

    def set_options(self, options: list[tuple[object, str]]) -> None:
        """Replace the option list (e.g. after a port re-scan). If the
        previously-selected value isn't in the new list, the dropdown
        falls back to its first option (or None if empty)."""
        self.options = options
        if self.current_value is not None:
            if not any(v == self.current_value for v, _ in options):
                self.current_value = None

    def _current_label(self) -> str:
        for v, l in self.options:
            if v == self.current_value:
                return l
        return self.placeholder

    def _option_rect(self, idx: int) -> pygame.Rect:
        return pygame.Rect(self.rect.x,
                            self.rect.bottom + idx * self.ROW_H,
                            self.rect.w, self.ROW_H)

    def handle_event(self, e: pygame.event.Event) -> bool:
        """Returns True if the event was consumed by this dropdown so
        the caller can skip processing it further (avoids a click on
        an option also hitting a button underneath the popup)."""
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.is_open = not self.is_open
                return True
            if self.is_open:
                for i in range(len(self.options)):
                    if self._option_rect(i).collidepoint(e.pos):
                        v = self.options[i][0]
                        if v != self.current_value:
                            self.current_value = v
                            self.on_change(v)
                        self.is_open = False
                        return True
                # Click anywhere else: close + DO NOT consume the
                # event. Lets the click also do whatever it would do
                # on the page below (closing the dropdown shouldn't
                # block a Save click outside).
                self.is_open = False
        if e.type == pygame.MOUSEMOTION and self.is_open:
            self._hover_idx = -1
            for i in range(len(self.options)):
                if self._option_rect(i).collidepoint(e.pos):
                    self._hover_idx = i
                    break
        return False

    def draw_closed(self, surf: pygame.Surface) -> None:
        """Render the always-visible pill. Call from screen.draw()
        wherever the dropdown's resting position is."""
        bg = tuple(max(0, c - 22) for c in self.theme.background)
        fg = self.theme.foreground
        pygame.draw.rect(surf, bg, self.rect,
                          border_radius=self.BORDER_RADIUS)
        pygame.draw.rect(surf, self.theme.muted, self.rect, 1,
                          border_radius=self.BORDER_RADIUS)
        # Current label, left-aligned with padding.
        label_font = self.layout.font(FONT_BODY)
        label = self._current_label()
        if len(label) > 28:
            label = label[:25] + "..."
        surf.blit(label_font.render(label, True, fg),
                   (self.rect.x + 12, self.rect.centery
                    - label_font.get_height() // 2))
        # Chevron: small triangle on the right edge. Points down when
        # closed, up when open.
        cx = self.rect.right - 16
        cy = self.rect.centery
        if self.is_open:
            points = [(cx - 6, cy + 3), (cx + 6, cy + 3), (cx, cy - 4)]
        else:
            points = [(cx - 6, cy - 3), (cx + 6, cy - 3), (cx, cy + 4)]
        pygame.draw.polygon(surf, fg, points)

    def draw_overlay(self, surf: pygame.Surface) -> None:
        """Draw the popup list. Call AFTER all other widgets so the
        list sits on top. No-op when closed."""
        if not self.is_open:
            return
        # Backplate so the popup reads as a separate layer.
        total_h = self.ROW_H * len(self.options)
        plate = pygame.Rect(self.rect.x, self.rect.bottom,
                             self.rect.w, total_h)
        bg = self.theme.background
        pygame.draw.rect(surf, bg, plate,
                          border_radius=self.BORDER_RADIUS)
        pygame.draw.rect(surf, self.theme.muted, plate, 1,
                          border_radius=self.BORDER_RADIUS)
        label_font = self.layout.font(FONT_BODY)
        for i, (_v, label) in enumerate(self.options):
            r = self._option_rect(i)
            if i == self._hover_idx:
                pygame.draw.rect(surf, self.theme.accent, r,
                                  border_radius=self.BORDER_RADIUS)
                text_colour = (255, 255, 255)
            else:
                text_colour = self.theme.foreground
            disp = label
            if len(disp) > 32:
                disp = disp[:29] + "..."
            surf.blit(label_font.render(disp, True, text_colour),
                       (r.x + 12,
                        r.centery - label_font.get_height() // 2))


# Raster icons loaded once and cached by (path, size, tint, flipped).
# Tint replaces the icon's black pixels with the requested colour while
# keeping its alpha mask, so the same source PNG can render in any theme
# colour without bundling a recoloured asset for each.
_ICON_CACHE: dict[tuple, pygame.Surface] = {}


def load_icon(path: str, size: int,
              tint: tuple[int, int, int] | None = None,
              flip_x: bool = False) -> pygame.Surface | None:
    """Load a PNG icon, optionally tint it to a colour, scale to size,
    and optionally flip horizontally. Returns None if the file can't be
    loaded so callers can gracefully fall back to a primitive glyph.
    Results are cached per (path, size, tint, flip) so repeat draws are
    free."""
    key = (path, size, tint, flip_x)
    cached = _ICON_CACHE.get(key)
    if cached is not None:
        return cached
    try:
        raw = pygame.image.load(path).convert_alpha()
    except (pygame.error, FileNotFoundError):
        return None
    # Recolour: keep the source alpha (which carries the shape) and
    # substitute the RGB channels with the tint. Uses numpy via
    # pygame.surfarray so the result is a clean recolour regardless
    # of whether the source PNG was black, grey, or already coloured.
    if tint is not None:
        tinted = pygame.Surface(raw.get_size(), pygame.SRCALPHA)
        tinted.fill((*tint, 255))
        alpha = pygame.surfarray.array_alpha(raw)
        pygame.surfarray.pixels_alpha(tinted)[:] = alpha
        raw = tinted
    if (size, size) != raw.get_size():
        raw = pygame.transform.smoothscale(raw, (size, size))
    if flip_x:
        raw = pygame.transform.flip(raw, True, False)
    _ICON_CACHE[key] = raw
    return raw


class LaneStrip:
    """One finger lane. Big finger name, hand-coloured border, hit flash."""

    FINGER_LABELS = ["Index", "Middle", "Ring", "Pinky"]
    # Border + badge colours per hand. Blue for right, purple for left.
    # Purple sits opposite blue on the wheel so the two hands read as a
    # clean pair without either fighting the green/orange/red outcome
    # flashes the lanes use during play.
    HAND_BADGE = {
        "right": (37, 99, 235),    # blue
        "left":  (168, 85, 247),   # purple
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
        # `active` means "this lane is the current target (stim has
        # fired, waiting for a press)". Set by GameEngine.on_stim.
        # `is_pressed` is independent: it tracks whether the patient
        # is physically pressing this finger right now, driven by the
        # FSR detector (Arduino path) or held-keys set (keyboard
        # fallback). The two states overlap freely: a lane can be the
        # target AND currently pressed at the same time. Keeping them
        # split means the press feedback never overwrites the "this
        # is the lane you're meant to hit" cue.
        self.active = False
        self.is_pressed = False
        # `pressed_until_min` keeps the press-state visual alive for a
        # minimum window after release so a quick tap (typical for
        # keyboard test mode) still produces a satisfying flash rather
        # than a single-frame blink the eye misses entirely.
        self.pressed_until_min = 0.0
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
        # Diagnostics needs the full label set (hand name, live FSR /
        # baseline readout) so the therapist can confirm each sensor.
        # During actual gameplay both are noise: the hand icon already
        # tells the patient which hand it is, and the 0/0 readout has
        # nothing to do with the rehab task. Screens that don't want
        # them flip these to False after construction.
        self.show_hand_label = True
        self.show_value_readout = True

    def set_pressed(self, is_pressed: bool, now: float,
                     min_hold_s: float = 0.10) -> None:
        """Update the live press state. On a press, latch a minimum-
        visible window so a quick tap (single frame down then up)
        still produces a press flash the patient can see. Holding
        keeps is_pressed True the whole time; release falls back to
        whether `now` is still inside the latched window."""
        if is_pressed:
            self.is_pressed = True
            self.pressed_until_min = max(self.pressed_until_min,
                                           now + min_hold_s)
        else:
            # Not currently held but still inside the latched window.
            if now < self.pressed_until_min:
                self.is_pressed = True
            else:
                self.is_pressed = False

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

    @staticmethod
    def _draw_tiny_hand(surf: pygame.Surface, cx: int, cy: int,
                         kind: str, colour: tuple[int, int, int]) -> None:
        """Mini palm-down hand icon for the lane-strip badge. Uses
        the bundled Material Icons pan_tool PNG (Apache 2.0), tinted
        to the badge's text colour, scaled to fit inside the 22 px
        radius badge. Right hand uses the icon as-is, left hand flips
        horizontally (the PNG natively reads as a right hand)."""
        from ..config import PROJECT_ROOT
        path = str(PROJECT_ROOT / "assets" / "icons" / "pan_tool.png")
        icon = load_icon(path, 30, tint=colour, flip_x=(kind == "left"))
        if icon is not None:
            surf.blit(icon, icon.get_rect(center=(cx, cy + 1)))

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

        border_colour = self.HAND_BADGE.get(self.hand, self.theme.foreground)

        # Target-lane attention pulse. While `active` is True (a stim
        # has fired and we're waiting for a press), wrap the tile in
        # a slow-pulsing outer halo in the hand colour. Reads as
        # "look here NOW" without changing colour mid-trial. Sine
        # period 0.9 s keeps it gentle but visible. Skipped when the
        # tile is also being pressed (the press halo already does
        # the job of attention).
        if self.active and not self.is_pressed:
            import math as _m
            phase = (_m.sin(now * (2 * _m.pi / 0.9)) + 1) * 0.5
            target_halo = self.rect.inflate(36, 36)
            th_surf = pygame.Surface(target_halo.size, pygame.SRCALPHA)
            outer_alpha = int(45 + 65 * phase)   # 45..110
            pygame.draw.rect(th_surf, (*border_colour, outer_alpha),
                              th_surf.get_rect(),
                              border_radius=26)
            # Tighter inner ring to give the halo body.
            inner = th_surf.get_rect().inflate(-16, -16)
            pygame.draw.rect(th_surf, (*border_colour,
                                         int(outer_alpha * 0.75)),
                              inner, border_radius=22)
            surf.blit(th_surf, target_halo.topleft)

        # Press-state outer halo. A wide soft glow in the hand colour
        # sitting around the tile so the patient gets unmistakable
        # "your press registered" feedback even before the timing
        # judges it. Drawn BEFORE the body fill so the body sits on
        # top of the glow rather than the other way round.
        if self.is_pressed:
            press_halo = self.rect.inflate(24, 24)
            ph_surf = pygame.Surface(press_halo.size, pygame.SRCALPHA)
            # Two passes for a soft falloff: a wider faint pass + a
            # tighter brighter inner ring.
            pygame.draw.rect(ph_surf, (*border_colour, 75),
                              ph_surf.get_rect(),
                              border_radius=22)
            inner_rect = ph_surf.get_rect().inflate(-12, -12)
            pygame.draw.rect(ph_surf, (*border_colour, 110),
                              inner_rect,
                              border_radius=18)
            surf.blit(ph_surf, press_halo.topleft)

        # Body fill.
        pygame.draw.rect(surf, fill, self.rect, border_radius=14)

        # Pressed fill highlight: a thin white overlay across the top
        # third of the tile so the press reads as a "lit up" surface
        # rather than just a colour change. Skipped on flash so the
        # outcome colour (green/orange/red) stays pure.
        if self.is_pressed and not (now < self.flash_until):
            lit_h = max(8, self.rect.h // 4)
            lit = pygame.Surface((self.rect.w - 6, lit_h), pygame.SRCALPHA)
            pygame.draw.rect(lit, (255, 255, 255, 60),
                              lit.get_rect(),
                              border_radius=10)
            surf.blit(lit, (self.rect.x + 3, self.rect.y + 3))

        # Border. Thickness scales with state:
        #   idle              -> 3 px
        #   target (active)   -> 6 px
        #   pressed           -> 8 px (visually loudest)
        #   target + pressed  -> 10 px
        if self.is_pressed and self.active:
            border_w = 10
        elif self.is_pressed:
            border_w = 8
        elif self.active:
            border_w = 6
        else:
            border_w = 3
        pygame.draw.rect(surf, border_colour, self.rect, border_w,
                          border_radius=14)
        border = border_colour

        # Hand badge: filled circle top-left with a tiny palm-down hand
        # icon inside. Replaces the old "L" / "R" letter so the badge
        # reads as a piece of finger-rehab iconography instead of plain
        # text. The hand silhouette has its thumb on the screen-side
        # that matches the actual hand (right hand -> thumb on the
        # LEFT of the icon, palm-down view from the patient).
        badge_r = 22
        bx = self.rect.x + badge_r + 8
        by = self.rect.y + badge_r + 8
        pygame.draw.circle(surf, border, (bx, by), badge_r)
        pygame.draw.circle(surf, self.theme.background, (bx, by), badge_r, 3)
        self._draw_tiny_hand(surf, bx, by, self.hand or "right",
                              self.theme.background)

        # Big finger label centred near the bottom of the strip.
        font = self.layout.font(32)
        label_text = self.FINGER_LABELS[self.finger % 4]
        label = font.render(label_text, True, self.theme.foreground)
        surf.blit(label, label.get_rect(midbottom=(
            self.rect.centerx, self.rect.bottom - 44,
        )))

        # Hand strapline below the finger name in the hand colour.
        # Hidden during gameplay (the hand badge icon top-left already
        # carries that information). Diagnostics keeps it on so the
        # therapist always knows which row is which hand.
        if self.show_hand_label:
            hand_font = self.layout.font(FONT_SMALL + 2)
            hand_word = ("Right hand" if self.hand == "right"
                         else "Left hand" if self.hand == "left" else "")
            if hand_word:
                hl = hand_font.render(hand_word, True, border)
                surf.blit(hl, hl.get_rect(midbottom=(
                    self.rect.centerx, self.rect.bottom - 16,
                )))

        # FSR live readout top-right corner. Useful on the Diagnostics
        # screen for confirming the sensor is delivering data; pure
        # noise during a real session, so gameplay screens hide it.
        if self.show_value_readout:
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
            # Clamp so a shorter tile (the pinky lane, scaled down to
            # echo finger length) can never produce a zero or negative
            # bar height on a small window.
            bar_h = max(40, self.rect.height - 200)
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


class HitBurst:
    """Confetti-style particle burst for rhythm-mode hits.

    Each particle is a small filled circle that flies outward from the
    burst origin, shrinks, and fades to nothing over `lifetime_s`. The
    burst as a whole keeps a list of these particles and exposes
    `alive` so the owning screen can prune finished bursts off its
    list once they're done animating.
    """

    def __init__(self, pos: tuple[int, int],
                 colour: tuple[int, int, int],
                 count: int = 9,
                 lifetime_s: float = 0.5,
                 speed_px_s: float = 320.0,
                 r_start: int = 7) -> None:
        import math
        import random
        self.colour = colour
        self.lifetime_s = lifetime_s
        self.born = time.perf_counter()
        self._origin = pos
        self._r_start = r_start
        # Outward velocity for each particle, evenly spread around the
        # circle with a small random jitter on angle + speed so each
        # burst looks different from the last.
        self._vel: list[tuple[float, float]] = []
        for i in range(count):
            angle = (math.tau * i / count
                     + random.uniform(-0.25, 0.25))
            speed = speed_px_s * random.uniform(0.7, 1.15)
            self._vel.append((math.cos(angle) * speed,
                               math.sin(angle) * speed))

    @property
    def alive(self) -> bool:
        return (time.perf_counter() - self.born) < self.lifetime_s

    def draw(self, surf: pygame.Surface) -> None:
        age = time.perf_counter() - self.born
        if age >= self.lifetime_s:
            return
        frac = age / self.lifetime_s
        alpha = int(255 * (1.0 - frac))
        radius = max(1, int(self._r_start * (1.0 - frac * 0.6)))
        ox, oy = self._origin
        # Render every particle onto one SRCALPHA surface so the alpha
        # blends cleanly without us having to per-particle compose.
        size = radius * 2 + 4
        for vx, vy in self._vel:
            x = ox + vx * age
            y = oy + vy * age
            disc = pygame.Surface((size, size), pygame.SRCALPHA)
            pygame.draw.circle(
                disc, (*self.colour, alpha),
                (size // 2, size // 2), radius,
            )
            surf.blit(disc, (int(x) - size // 2, int(y) - size // 2))


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
