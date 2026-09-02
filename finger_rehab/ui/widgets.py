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

from ..game.modes._keys import keymap_for_hand
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
# Tag drawn on a login field whose value was carried over from an
# earlier visit rather than typed today (TextInput and Segmented).
PREFILLED_TAG = "from before"

# Single source of truth for the app's typeface. SysFont walks this comma
# list and uses the first family installed on the host, so the app lands on
# a clean modern sans wherever it runs: Avenir Next / Helvetica Neue on
# macOS, Segoe UI on Windows, DejaVu Sans on Linux, plain Arial as the last
# resort. Keeping it in one constant means every screen, heading and button
# shares the exact same typeface instead of each call site hard-coding its
# own chain (which is how the fonts drifted apart before).
FONT_FAMILY = ("Avenir Next,Helvetica Neue,Segoe UI,Helvetica,"
               "Arial,DejaVu Sans")


def make_font(pt: int, bold: bool = False) -> pygame.font.Font:
    """Resolve FONT_FAMILY at the given point size. Used directly by the
    few call sites that need a one-off bold heading; everything else goes
    through Layout.font() which adds caching and font_scale."""
    return pygame.font.SysFont(FONT_FAMILY, pt, bold=bold)


@dataclass
class Layout:
    width: int
    height: int
    font_scale: float = 1.0

    def __post_init__(self) -> None:
        # Cache fonts so we don't pay SysFont's lookup cost on every draw call.
        # Keyed by (size, bold) so regular and bold cuts cache separately.
        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}

    @property
    def gutter(self) -> int:
        return int(PADDING * self.font_scale)

    def font(self, pt: int, bold: bool = False) -> pygame.font.Font:
        size = int(pt * self.font_scale)
        key = (size, bold)
        f = self._fonts.get(key)
        if f is None:
            f = pygame.font.SysFont(FONT_FAMILY, size, bold=bold)
            self._fonts[key] = f
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
    # decreasing alpha so the edge fades smoothly instead of cutting off
    # as a hard duplicate. Kept low and tight so buttons read as flat
    # modern surfaces sitting just above the page, not glossy 3-D pills.
    # (dy, alpha) per layer.
    _SHADOW_PASSES = ((2, 28), (5, 14), (9, 6))
    BORDER_RADIUS = 14

    def draw(self, surf: pygame.Surface) -> None:
        # Pick the base fill colour by precedence:
        #   explicit colour > primary -> theme accent > muted (default)
        if self.colour is not None:
            base = self.colour
            if self.hover:
                base = tuple(min(255, c + 16) for c in base)
        elif self.primary:
            base = self.theme.accent
            if self.hover:
                base = tuple(min(255, c + 14) for c in base)
        else:
            base = self.theme.muted
            if self.hover:
                base = self.theme.accent
        fill = _darker(base, 0.12) if self.pressed else base

        # Single soft drop shadow that fades out downward. Pressed state
        # collapses it to almost nothing so the button reads as pushed in.
        passes = ((2, 22),) if self.pressed else self._SHADOW_PASSES
        shadow_surf = pygame.Surface(
            (self.rect.w + 24, self.rect.h + 24), pygame.SRCALPHA,
        )
        for dy, alpha in passes:
            pygame.draw.rect(
                shadow_surf, (15, 23, 42, alpha),
                pygame.Rect(12, 12 + dy, self.rect.w, self.rect.h),
                border_radius=self.BORDER_RADIUS,
            )
        surf.blit(shadow_surf, (self.rect.x - 12, self.rect.y - 12))

        # Flat body fill. Pressed buttons shift down by 1 px so the click
        # registers visually as well as audibly. No gloss gradient, no
        # bevel: the soft shadow alone carries the depth, which is the
        # look modern clinical and mobile apps use.
        body_rect = self.rect.move(0, 1 if self.pressed else 0)
        pygame.draw.rect(surf, fill, body_rect,
                          border_radius=self.BORDER_RADIUS)

        # One-pixel top highlight: a hairline of low-alpha white along the
        # very top edge only. Gives the surface a faint lift without the
        # old half-height "shine" that made it look like a glass pill.
        if not self.pressed:
            hi = pygame.Surface((body_rect.w - 10, 2), pygame.SRCALPHA)
            pygame.draw.rect(hi, (255, 255, 255, 40), hi.get_rect(),
                             border_radius=1)
            surf.blit(hi, (body_rect.x + 5, body_rect.y + 2))

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


class ConfirmDialog:
    """Modal are-you-sure card: full-screen dim, a centred question,
    one safe button and one destructive button.

    Layout and colours copy the quick calibration Esc guard so every
    confirm in the app reads the same. The safe action is the primary
    button AND owns keyboard focus when the dialog opens, so a reflex
    Enter (or a stray double-press of whatever raised the dialog) lands
    on the harmless choice. Reaching the destructive button takes a
    deliberate move: a direct click on it, or Tab / an arrow key to
    shift focus and THEN Enter.

    Esc is deliberately NOT handled here. The engine owns Esc and
    treats it as "dismiss" while a dialog is up, so the key that raised
    the dialog can only ever back out of it, never through it.

    Everything drawn is static (no flashing): a dim layer, the card,
    text, buttons, and a steady focus ring around the focused button.
    """

    CARD_W = 640
    CARD_H = 240
    BTN_W = 230
    BTN_H = 56

    def __init__(self, question: str, detail: str,
                 safe_label: str, danger_label: str,
                 on_safe: Callable[[], None],
                 on_danger: Callable[[], None],
                 theme: Theme, layout: Layout,
                 accent: tuple[int, int, int] | None = None) -> None:
        self.question = question
        self.detail = detail
        self.theme = theme
        self.layout = layout
        # The raiser's accent (the running mode's colour) tops the card
        # so the dialog visibly belongs to the game it interrupted.
        self.accent = accent or theme.accent
        cx = layout.width // 2
        y = layout.height // 2 + 40
        self.safe_btn = Button(
            pygame.Rect(cx - 250, y, self.BTN_W, self.BTN_H),
            safe_label, on_safe, theme, layout, primary=True)
        self.danger_btn = Button(
            pygame.Rect(cx + 20, y, self.BTN_W, self.BTN_H),
            danger_label, on_danger, theme, layout)
        # 0 = safe, 1 = danger. Focus starts on the safe choice.
        self.focus = 0
        self._dim_cache: pygame.Surface | None = None

    def _buttons(self) -> tuple[Button, Button]:
        return (self.safe_btn, self.danger_btn)

    def handle_event(self, e: pygame.event.Event) -> None:
        """Mouse goes to the two buttons; the keyboard moves focus and
        fires the focused button. Esc is ignored on purpose (the caller
        handles it as dismiss before this method ever runs)."""
        if e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                      pygame.MOUSEBUTTONUP):
            for b in self._buttons():
                b.handle_event(e)
            return
        if e.type != pygame.KEYDOWN:
            return
        if e.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT,
                     pygame.K_UP, pygame.K_DOWN):
            # Two buttons, so any move flips to the other one.
            self.focus = 1 - self.focus
        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                       pygame.K_SPACE):
            self._buttons()[self.focus].on_click()

    def draw(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        # Full-screen dim behind the card, cached: draw runs every
        # frame and a fresh SRCALPHA surface per frame is an allocation
        # the draw hot path does not need.
        if (self._dim_cache is None
                or self._dim_cache.get_size() != surf.get_size()):
            self._dim_cache = pygame.Surface(surf.get_size(),
                                             pygame.SRCALPHA)
            self._dim_cache.fill((0, 0, 0, 160))
        surf.blit(self._dim_cache, (0, 0))
        cx, cy = ly.width // 2, ly.height // 2
        card = pygame.Rect(cx - self.CARD_W // 2, cy - 130,
                           self.CARD_W, self.CARD_H)
        pygame.draw.rect(surf, th.background, card, border_radius=18)
        pygame.draw.rect(surf, th.muted, card, 2, border_radius=18)
        # Slim accent rule along the card's top edge, in the raising
        # mode's colour, mirroring the header underline convention.
        rule = pygame.Rect(0, 0, 96, 4)
        rule.center = (cx, card.top + 2)
        pygame.draw.rect(surf, self.accent, rule, border_radius=2)
        draw_text(surf, self.question, (cx, cy - 80), th, ly,
                  pt=FONT_H2, centre=True)
        if self.detail:
            # Detail can carry explicit newlines: a 640-wide card fits
            # about 65 body-font characters per line, and a longer
            # sentence drawn as one line runs past the card edges.
            # The block stays centred on the single-line anchor so
            # existing one-line dialogs render exactly as before.
            lines = self.detail.split("\n")
            y0 = cy - 35 - (len(lines) - 1) * 13
            for i, line in enumerate(lines):
                draw_text(surf, line, (cx, y0 + i * 26), th, ly,
                          pt=FONT_BODY, centre=True, colour=th.muted)
        for b in self._buttons():
            b.draw(surf)
        # Steady focus ring so a keyboard-only player can see where
        # Enter will land. Drawn outside the button so it never fights
        # the hover ring. Theme accent, NOT the mode accent: a red
        # mode's ring around Keep playing would read as a warning.
        focused = self._buttons()[self.focus]
        ring = focused.rect.inflate(12, 12)
        pygame.draw.rect(surf, self.theme.accent, ring, 3,
                         border_radius=Button.BORDER_RADIUS + 4)


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


class ToggleMenu:
    """Dropdown whose rows are checkboxes rather than one choice.

    Same two-pass draw as Dropdown (`draw_closed` then `draw_overlay`
    after everything else) so the open list sits on top. The difference
    is that a row click flips that row and the menu STAYS OPEN, because
    the point is setting several switches in one visit.

    `rows` is `[(key, label, help_text), ...]`. State lives outside the
    widget: `get_value(key)` is asked what a row currently is on every
    draw, and `on_toggle(key, new_value)` is told when one flips. That
    keeps the config the single source of truth, so a value changed
    somewhere else still shows correctly here.

    A row whose key is None is a separator: it draws its label as a
    heading and cannot be clicked.
    """

    ROW_H = 34
    HEAD_H = 26
    BORDER_RADIUS = 8

    def __init__(self, rect: pygame.Rect,
                 rows: list[tuple[str | None, str, str]],
                 get_value: Callable[[str], bool],
                 on_toggle: Callable[[str, bool], None],
                 theme: Theme, layout: Layout,
                 title: str = "Sensory Cues",
                 open_upwards: bool = False) -> None:
        self.rect = rect
        self.rows = rows
        self.get_value = get_value
        self.on_toggle = on_toggle
        self.theme = theme
        self.layout = layout
        self.title = title
        # Rows above the pill rather than below it. Needed where the
        # pill sits low on the screen, since a list opening downward
        # would run off the bottom and the rows past the edge could not
        # be clicked at all.
        self.open_upwards = open_upwards
        self.is_open = False
        self._hover_idx = -1

    def _list_height(self) -> int:
        return sum(self.ROW_H if key is not None else self.HEAD_H
                   for key, _l, _h in self.rows)

    def _list_top(self) -> int:
        """Where the row list starts, in screen coordinates."""
        if self.open_upwards:
            return self.rect.top - 4 - self._list_height()
        return self.rect.bottom + 4

    @property
    def width(self) -> int:
        return self.rect.w

    def _row_rect(self, idx: int) -> pygame.Rect:
        y = self._list_top()
        for i, (key, _label, _help) in enumerate(self.rows):
            h = self.ROW_H if key is not None else self.HEAD_H
            if i == idx:
                return pygame.Rect(self.rect.x, y, self.rect.w, h)
            y += h
        return pygame.Rect(self.rect.x, y, self.rect.w, 0)

    def _total_h(self) -> int:
        return sum(self.ROW_H if k is not None else self.HEAD_H
                   for k, _l, _h in self.rows) + 8

    def hover_help(self) -> str:
        """Help text of the row under the cursor, empty when none. The
        screen paints this in its status line so each switch can explain
        what the patient will actually experience without the row itself
        needing room for a paragraph."""
        if not self.is_open or not (0 <= self._hover_idx < len(self.rows)):
            return ""
        return self.rows[self._hover_idx][2]

    def handle_event(self, e: pygame.event.Event) -> bool:
        """True when the event was consumed, so the caller can stop
        dispatching it (a click on a row must not also hit whatever is
        drawn underneath the popup)."""
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.rect.collidepoint(e.pos):
                self.is_open = not self.is_open
                return True
            if self.is_open:
                for i, (key, _label, _help) in enumerate(self.rows):
                    if key is None:
                        continue
                    if self._row_rect(i).collidepoint(e.pos):
                        self.on_toggle(key, not bool(self.get_value(key)))
                        # Deliberately left open: the four switches are
                        # usually set as a group, and closing after each
                        # one would mean four trips through the menu.
                        return True
                # Anywhere else closes it, and the click is consumed so
                # a control sitting under the popup does not also fire.
                plate = pygame.Rect(self.rect.x, self._list_top(),
                                     self.rect.w, self._total_h())
                self.is_open = False
                if plate.collidepoint(e.pos):
                    return True
        if e.type == pygame.MOUSEMOTION and self.is_open:
            self._hover_idx = -1
            for i, (key, _label, _help) in enumerate(self.rows):
                if key is not None and self._row_rect(i).collidepoint(e.pos):
                    self._hover_idx = i
                    break
        return False

    def _on_count(self) -> tuple[int, int]:
        keys = [k for k, _l, _h in self.rows if k is not None]
        return sum(1 for k in keys if self.get_value(k)), len(keys)

    def draw_closed(self, surf: pygame.Surface) -> None:
        """The always-visible pill. Shows how many switches are on, so
        the state is readable without opening the menu."""
        on, total = self._on_count()
        bg = tuple(max(0, c - 22) for c in self.theme.background)
        pygame.draw.rect(surf, bg, self.rect,
                          border_radius=self.BORDER_RADIUS)
        outline = self.theme.accent if on else self.theme.muted
        pygame.draw.rect(surf, outline, self.rect, 2,
                          border_radius=self.BORDER_RADIUS)
        font = self.layout.font(FONT_SMALL + 2)
        label = f"{self.title.upper()}  {on}/{total}"
        surf.blit(font.render(label, True, self.theme.foreground),
                   (self.rect.x + 12,
                    self.rect.centery - font.get_height() // 2))
        cx = self.rect.right - 16
        cy = self.rect.centery
        if self.is_open:
            points = [(cx - 6, cy + 3), (cx + 6, cy + 3), (cx, cy - 4)]
        else:
            points = [(cx - 6, cy - 3), (cx + 6, cy - 3), (cx, cy + 4)]
        pygame.draw.polygon(surf, self.theme.foreground, points)

    def draw_overlay(self, surf: pygame.Surface) -> None:
        """The open list. Call after every other widget. No-op closed."""
        if not self.is_open:
            return
        # Starts where the rows start, so the panel, the rows and the
        # click shield all agree about which way the list opened.
        plate = pygame.Rect(self.rect.x, self._list_top() - 4,
                             self.rect.w, self._total_h())
        pygame.draw.rect(surf, self.theme.background, plate,
                          border_radius=self.BORDER_RADIUS)
        pygame.draw.rect(surf, self.theme.muted, plate, 1,
                          border_radius=self.BORDER_RADIUS)
        font = self.layout.font(FONT_SMALL + 2)
        head_font = self.layout.font(FONT_SMALL)
        for i, (key, label, _help) in enumerate(self.rows):
            r = self._row_rect(i)
            if key is None:
                surf.blit(head_font.render(label.upper(), True,
                                            self.theme.muted),
                           (r.x + 12,
                            r.centery - head_font.get_height() // 2))
                continue
            on = bool(self.get_value(key))
            if i == self._hover_idx:
                hov = tuple(min(255, c + 18) for c in self.theme.background)
                pygame.draw.rect(surf, hov, r, border_radius=6)
            # Checkbox: filled green with a tick when on, hollow when
            # off. A colour-only difference would be hard to read on a
            # projector, hence the tick.
            box = pygame.Rect(r.x + 12, r.centery - 8, 16, 16)
            if on:
                pygame.draw.rect(surf, (34, 197, 94), box, border_radius=4)
                pygame.draw.lines(
                    surf, (255, 255, 255), False,
                    [(box.x + 4, box.centery),
                     (box.centerx, box.bottom - 5),
                     (box.right - 3, box.y + 4)], 2)
            else:
                pygame.draw.rect(surf, self.theme.muted, box, 2,
                                  border_radius=4)
            colour = (self.theme.foreground if on else self.theme.muted)
            surf.blit(font.render(label, True, colour),
                       (box.right + 10,
                        r.centery - font.get_height() // 2))


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


def keyboard_controls_lines(engine, mode) -> list[str]:
    """Keyboard hints for the corner Controls note, one line per playing
    hand, in keyboard reading order. Empty when the input is the real
    sensors: fingers sit on the pads, a legend would only be noise.

    Shared by every gameplay screen (syllables, GameplayScreen,
    RhythmScreen) so the keyboard-fallback convention reads the same
    everywhere a keyboard session can land, not just syllables. Reads
    `mode.hands` when the mode tracks hands explicitly (chords,
    syllables); everything else falls back to `mode.lanes`, split
    0-3 right / 4-7 left when there are eight lanes (the bimanual
    convention used across the suite), or treated as one hand's four
    lanes otherwise.
    """
    source = getattr(engine, "source", None)
    if source is None or getattr(source, "provides_samples", True):
        return []
    km = engine.cfg.get(keymap_for_hand(engine.hand_mode), {})
    if not km:
        return []
    by_lane = {lane: key for key, lane in km.items()}
    hands = getattr(mode, "hands", None)
    if not isinstance(hands, dict) or not hands:
        raw_lanes = getattr(mode, "lanes", None)
        if raw_lanes is None:
            # Mode doesn't keep its own lane list (rhythm reads lanes
            # off the beatmap / screen instead) -- fall back to the
            # full lane set implied by hand_mode so a bilateral
            # session still gets both hands' keys, not just four.
            mode_lanes = (list(range(8)) if engine.hand_mode == "both"
                          else list(range(4)))
        else:
            mode_lanes = list(raw_lanes)
        if len(mode_lanes) > 4:
            hands = {"right": mode_lanes[:4], "left": mode_lanes[4:]}
        else:
            hands = {"right": mode_lanes}
    lines: list[str] = []
    for hand in ("left", "right"):
        lanes = hands.get(hand)
        if not lanes:
            continue
        # Left hand reads right-to-left on the keyboard (a s d f is
        # little to index), so reverse it into reading order.
        order = list(reversed(lanes)) if hand == "left" else list(lanes)
        keys = [by_lane.get(lane, "?") for lane in order]
        keys = [k.replace("semicolon", ";").upper() for k in keys]
        lines.append(f"{hand.capitalize()} hand: {' '.join(keys)}")
    return lines


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

    def _label_colour(self, fill: tuple[int, int, int]
                       ) -> tuple[int, int, int]:
        """Readable text colour for a given tile fill. Uses the standard
        luminance weighting and flips to white once the fill is dark
        enough that the theme's near-black text would disappear (the
        ring finger's black tile, or any flash colour)."""
        r, g, b = fill[0], fill[1], fill[2]
        luminance = 0.299 * r + 0.587 * g + 0.114 * b
        if luminance < 140:
            return (255, 255, 255)
        return self.theme.foreground

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

        # Big finger label centred near the bottom of the strip. The
        # text colour follows the tile fill rather than the theme, so
        # the label stays readable on a dark finger colour (the ring
        # finger's black tile would swallow near-black text).
        # Point size steps down until the word fits inside the tile
        # with a real margin. A bilateral row is eight tiles wide, and
        # at the fixed 32 pt "Middle" ran edge to edge with the border
        # touching both ends of the word.
        label_text = self.FINGER_LABELS[self.finger % 4]
        max_w = max(24, self.rect.w - 20)
        for pt in (32, 30, 28, 26, 24, 22, 20, 18):
            font = self.layout.font(pt)
            if font.size(label_text)[0] <= max_w:
                break
        label = font.render(label_text, True, self._label_colour(fill))
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
                 font_pt: int = FONT_BODY + 2,
                 signed: bool = False) -> None:
        self.rect = rect
        self.theme = theme
        self.layout = layout
        self.label = label
        self.placeholder = placeholder
        self.text = str(initial)
        self.max_len = max_len
        self.numeric = numeric
        # A numeric field that may start with a minus sign (the
        # Edinburgh laterality quotient runs -100 to +100).
        self.signed = signed
        self.font_pt = font_pt
        self.focused = False
        self.hover = False
        # Type-over state for a field pre-filled with a SUGGESTION (the
        # next free participant code): the first character typed
        # replaces the whole text instead of appending to it, so a
        # name is one keystroke away from a suggested code. Cleared by
        # any edit, and by a click into the field.
        self.select_all = False
        # Filled from an earlier visit's metadata (hand size on the
        # login screen). Drawn with a small tag so the RA can see the
        # value was not typed today, and typed over as a whole, the
        # same way a suggestion is. Cleared by any edit.
        self.prefilled = False
        self._born = time.perf_counter()

    @property
    def value(self) -> str:
        return self.text.strip()

    def set_prefilled(self, text: str) -> None:
        """Fill the field from an earlier record and mark it so."""
        self.text = str(text)
        self.prefilled = bool(self.text)
        self.select_all = False

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.focused = self.rect.collidepoint(e.pos)
            if self.focused:
                self.select_all = False
        elif e.type == pygame.KEYDOWN and self.focused:
            replace_whole = self.select_all or self.prefilled
            if e.key == pygame.K_BACKSPACE:
                self.text = "" if replace_whole else self.text[:-1]
                self.select_all = False
                self.prefilled = False
            elif e.key in (pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                # Defocus on Enter / Tab / Esc so global handlers can
                # still react to those keys.
                self.focused = False
            else:
                ch = e.unicode
                # Filter to printable ASCII + space for safety. Names can
                # technically contain unicode but the CSV layer keeps
                # things simple if we stick to ASCII.
                if not ch or not ch.isprintable():
                    return
                if self.numeric and not ch.isdigit():
                    if not (self.signed and ch == "-"
                            and (replace_whole or not self.text)):
                        return
                if replace_whole:
                    self.text = ""
                    self.select_all = False
                    self.prefilled = False
                if len(self.text) < self.max_len:
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
        if self.prefilled and self.text:
            # Where the value came from, inside the field at the right,
            # so an RA reading the screen sees it was carried over and
            # not measured today.
            tag_font = self.layout.font(FONT_SMALL)
            tag = tag_font.render(PREFILLED_TAG, True, self.theme.muted)
            surf.blit(tag, tag.get_rect(
                midright=(self.rect.right - self.PADDING_X,
                          self.rect.centery)))
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


class Segmented:
    """A row of mutually exclusive options, one lit: sex and dominant
    hand on the login screen.

    Click a segment to pick it. When the control has keyboard focus
    (Tab reaches it like a text field) Left and Right move the pick,
    each option's hotkey letter picks it outright, and Enter, Tab or
    Esc hand focus back, the same contract TextInput keeps so the
    login screen can walk one focus order across both kinds of field.
    `value` is the picked option's key, or None while nothing is
    picked, which is what a required field starts as.
    """

    BORDER_RADIUS = 10

    def __init__(self, rect: pygame.Rect, theme: Theme, layout: Layout,
                 options: list[tuple[str, str]],
                 label: str = "",
                 initial: str | None = None,
                 hotkeys: dict[str, str] | None = None,
                 font_pt: int = FONT_BODY) -> None:
        self.rect = rect
        self.theme = theme
        self.layout = layout
        self.options = list(options)          # (key, caption)
        self.label = label
        self.value: str | None = (initial if any(k == initial for k, _c
                                                 in self.options)
                                  else None)
        # hotkey character -> option key
        self.hotkeys = dict(hotkeys or {})
        self.font_pt = font_pt
        self.focused = False
        self.hover = False
        # Picked from an earlier visit's record rather than by a click
        # today (main hand and sex on the login screen). Any pick
        # clears it; the tag beside the label says where it came from.
        self.prefilled = False

    def set_prefilled(self, key: str | None) -> None:
        self.set(key)
        self.prefilled = self.value is not None

    def _index(self) -> int:
        for i, (k, _c) in enumerate(self.options):
            if k == self.value:
                return i
        return -1

    def _segment_rects(self) -> list[pygame.Rect]:
        n = max(1, len(self.options))
        w = self.rect.w / n
        return [pygame.Rect(int(self.rect.x + i * w), self.rect.y,
                            int(w) if i < n - 1
                            else self.rect.right - int(self.rect.x + i * w),
                            self.rect.h)
                for i in range(n)]

    def set(self, key: str | None) -> None:
        self.value = key if any(k == key for k, _c in self.options) else None

    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            self.focused = self.rect.collidepoint(e.pos)
            if self.focused:
                for r, (k, _c) in zip(self._segment_rects(), self.options):
                    if r.collidepoint(e.pos):
                        self.value = k
                        self.prefilled = False
                        break
        elif e.type == pygame.KEYDOWN and self.focused:
            if e.key in (pygame.K_RETURN, pygame.K_TAB, pygame.K_ESCAPE):
                self.focused = False
            elif e.key in (pygame.K_LEFT, pygame.K_RIGHT):
                i = self._index()
                step = 1 if e.key == pygame.K_RIGHT else -1
                if i < 0:
                    i = 0 if step > 0 else len(self.options) - 1
                else:
                    i = (i + step) % len(self.options)
                self.value = self.options[i][0]
                self.prefilled = False
            else:
                ch = (e.unicode or "").lower()
                if ch and ch in self.hotkeys:
                    self.set(self.hotkeys[ch])
                    self.prefilled = False

    def draw(self, surf: pygame.Surface) -> None:
        if self.label:
            lbl_font = self.layout.font(FONT_SMALL + 4)
            lbl = lbl_font.render(self.label, True, self.theme.muted)
            surf.blit(lbl, (self.rect.x, self.rect.y - 26))
        if self.prefilled and self.value is not None:
            # Same tag TextInput draws, on the label row so the
            # segments themselves stay uncluttered.
            tag_font = self.layout.font(FONT_SMALL)
            tag = tag_font.render(PREFILLED_TAG, True, self.theme.muted)
            surf.blit(tag, tag.get_rect(
                topright=(self.rect.right, self.rect.y - 24)))
        body_colour = tuple(
            max(0, min(255, c - 14)) for c in self.theme.background)
        pygame.draw.rect(surf, body_colour, self.rect,
                         border_radius=self.BORDER_RADIUS)
        font = self.layout.font(self.font_pt)
        rects = self._segment_rects()
        for r, (k, caption) in zip(rects, self.options):
            picked = (k == self.value)
            if picked:
                pygame.draw.rect(surf, self.theme.accent, r.inflate(-4, -6),
                                 border_radius=self.BORDER_RADIUS - 2)
            colour = (255, 255, 255) if picked else self.theme.foreground
            text = font.render(caption, True, colour)
            prev_clip = surf.get_clip()
            surf.set_clip(r.inflate(-4, -4))
            surf.blit(text, text.get_rect(center=r.center))
            surf.set_clip(prev_clip)
        border = (self.theme.accent if self.focused
                  else self.theme.foreground if self.hover
                  else self.theme.muted)
        pygame.draw.rect(surf, border, self.rect,
                         width=2 if self.focused else 1,
                         border_radius=self.BORDER_RADIUS)


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
