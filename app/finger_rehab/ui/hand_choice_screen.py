"""Which hand, once per session.

Shown straight after login. Every game in the session then uses that
hand without asking again, and calibration measures that hand only.
One board is one hand, so it offers right or left and never both; two
boards and a keyboard offer all three. Also reachable from the game
menu to change hands mid-session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .screens import MuteButton, Screen, SetupScreen, _draw_header
from .widgets import BUTTON_H, FONT_BODY, FONT_H2, Button, draw_text

if TYPE_CHECKING:
    from ..game.engine import GameEngine


class HandChoiceScreen(Screen):
    LABELS = {"right": "Right hand", "left": "Left hand",
              "both": "Both hands"}
    KEYS = {pygame.K_r: "right", pygame.K_l: "left", pygame.K_b: "both"}
    BUTTON_W = 290
    BUTTON_H = 220
    GAP = 32
    TOP = 300

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.options: list[str] = []
        self.buttons: list[Button] = []
        self.back_btn = Button(
            pygame.Rect(40, engine.layout.height - 90, 200, BUTTON_H - 10),
            "Log out", self._back, self.theme, self.layout)
        self.mute_btn = MuteButton(
            engine, pygame.Rect(28, 26, MuteButton.W, MuteButton.H))
        self.enter()

    def enter(self) -> None:
        """Rebuilt each time it opens: the boards attached decide the
        choices, and they can change between visits."""
        options = getattr(self.engine, "session_hand_options", None)
        self.options = (options() if callable(options)
                        else ["right", "left", "both"])
        n = len(self.options)
        total = n * self.BUTTON_W + (n - 1) * self.GAP
        x0 = self.layout.width // 2 - total // 2
        self.buttons = []
        for i, hand in enumerate(self.options):
            rect = pygame.Rect(x0 + i * (self.BUTTON_W + self.GAP), self.TOP,
                               self.BUTTON_W, self.BUTTON_H)
            self.buttons.append(Button(rect, "",
                                       lambda h=hand: self.pick(h),
                                       self.theme, self.layout,
                                       font_pt=FONT_H2))
        chosen = getattr(self.engine, "_session_hand", None)
        self.back_btn.label = "Back" if chosen else "Log out"

    def pick(self, hand: str) -> None:
        self.engine.choose_session_hand(hand)

    def _back(self) -> None:
        if getattr(self.engine, "_session_hand", None):
            self.engine.show_mode_select()
        else:
            self.engine.end_session()
            self.engine.show_title()

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.mute_btn.handle_event(e):
            return
        for b in self.buttons + [self.back_btn]:
            b.handle_event(e)
        if e.type == pygame.KEYDOWN and self.KEYS.get(e.key) in self.options:
            self.pick(self.KEYS[e.key])

    def update(self, dt: float) -> None:
        pass

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        name = getattr(self.engine.session, "participant", "") or ""
        greeting = f"Welcome, {name}. " if name not in ("", "NA") else ""
        _draw_header(surf, "Which hand today?",
                     f"{greeting}Every game this session uses it.",
                     self.theme, self.layout)
        for b, hand in zip(self.buttons, self.options):
            b.draw(surf)
            colour = self._glyph_colour(b)
            SetupScreen._draw_hand_glyph(surf, b.rect.centerx,
                                         b.rect.top + 78, hand, 120, colour)
            draw_text(surf, self.LABELS[hand],
                      (b.rect.centerx, b.rect.bottom - 28),
                      self.theme, self.layout, pt=FONT_H2, centre=True,
                      colour=colour)
        if len(self.options) == 2:
            draw_text(surf, "One board is plugged in: pick the hand it is on.",
                      (self.layout.width // 2,
                       self.TOP + self.BUTTON_H + 40),
                      self.theme, self.layout, pt=FONT_BODY, centre=True,
                      colour=self.theme.muted)
        self.back_btn.draw(surf)
        self.mute_btn.draw(surf, self.theme, self.layout)

    def _glyph_colour(self, b: Button) -> tuple[int, int, int]:
        base = (self.theme.accent if (b.primary or b.hover)
                else self.theme.muted)
        return (self.theme.background if sum(base) / 3 > 140
                else (255, 255, 255))
