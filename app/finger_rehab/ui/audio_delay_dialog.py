"""The modal behind Settings, Setup, Audio delay.

One card: what the measurement is for and what it needs, the delays
this computer uses now, and one button. While it runs the card shows
each step as it happens; at the end, what was saved or why nothing was.

The dialog starts no threads and owns no hardware. The Settings screen
supplies `on_measure()`, which returns a job
(audio/latency_measure.LatencyJob) or None when it refused, and polls
that job; the board's port and the menu music are handed over and back
on the main thread, as the firmware jobs do.

Keyboard: Tab moves between the buttons, Enter fires the focused one,
Esc closes while idle and does nothing while a measurement runs.
"""
from __future__ import annotations

import sys

import pygame

from .firmware_dialog import _wrap
from .theme import Theme
from .widgets import FONT_BODY, FONT_H2, FONT_SMALL, Button, Layout, draw_text


def needs_taps() -> bool:
    """True where the system cannot report the microphone's own delay
    (everywhere but macOS), so it is timed from taps on the index pad."""
    return sys.platform != "darwin"


class AudioDelayDialog:

    CARD_W = 720
    CARD_H = 430
    BTN_W = 200
    BTN_H = 50
    SHOWN_LINES = 6

    def __init__(self, theme: Theme, layout: Layout, *, now_line: str,
                 has_board: bool, on_measure=None, on_close=None) -> None:
        self.theme = theme
        self.layout = layout
        self.now_line = now_line
        self.has_board = bool(has_board)
        self._on_measure = on_measure
        self._on_close = on_close
        self.job = None
        self.busy = False
        self.finished = False
        self.result_text = ""
        self.result_ok = False
        self.wants_close = False
        self._dim_cache: pygame.Surface | None = None
        self.card = pygame.Rect(0, 0, self.CARD_W, self.CARD_H)
        self.card.center = (layout.width // 2, layout.height // 2)
        self.buttons: list[Button] = []
        self.focus = 0
        self._build_buttons()

    # -- state -------------------------------------------------------------

    def intro_lines(self) -> list[tuple[str, bool]]:
        """(text, is_a_warning) lines for the idle card."""
        lines = [
            ("Times this computer's sound and buzz with its "
             "microphone.", False),
            ("Once per computer or speaker. About two minutes, quiet "
             "room, normal volume.", False),
        ]
        if needs_taps():
            if self.has_board:
                lines.append(("When asked, tap the index pad with a "
                              "fingernail, about once a second.", False))
            else:
                lines.append(("Plug the board in first: the timing "
                              "needs taps on the index pad.", True))
        elif self.has_board:
            lines.append(("The board buzzes each finger ten times at the "
                          "end.", False))
        return lines

    def _build_buttons(self) -> None:
        y = self.card.bottom - self.BTN_H - 24
        self.buttons = []
        if self.busy:
            return
        self.buttons.append(Button(
            pygame.Rect(self.card.x + 28, y, self.BTN_W, self.BTN_H),
            "Close", self.close, self.theme, self.layout,
            font_pt=FONT_BODY))
        self.buttons.append(Button(
            pygame.Rect(self.card.right - self.BTN_W - 28, y,
                        self.BTN_W, self.BTN_H),
            "Measure again" if self.finished else "Measure",
            self._start, self.theme, self.layout, font_pt=FONT_BODY,
            primary=True))
        self.focus = len(self.buttons) - 1

    def _start(self) -> None:
        if self._on_measure is None or self.busy:
            return
        job = self._on_measure()
        if job is None:
            # The screen refused (a block is running); it says why on
            # its own status line.
            self.close()
            return
        self.job = job
        self.busy = True
        self.finished = False
        self.result_text = ""
        self._build_buttons()

    def finish(self, text: str, ok: bool, now_line: str | None = None
               ) -> None:
        """Called by the screen once the job is done and the port is
        back."""
        self.job = None
        self.busy = False
        self.finished = True
        self.result_text = text
        self.result_ok = bool(ok)
        if now_line is not None:
            self.now_line = now_line
        self._build_buttons()

    def close(self) -> None:
        if self.busy:
            return
        self.wants_close = True
        if self._on_close is not None:
            self._on_close()

    # -- input -------------------------------------------------------------

    def on_escape(self) -> bool:
        """True: the dialog swallowed the key. A running measurement
        swallows it without acting on it."""
        if not self.busy:
            self.close()
        return True

    def handle_event(self, e: pygame.event.Event) -> bool:
        """Always True: the dialog is modal."""
        if self.busy:
            return True
        if e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                      pygame.MOUSEBUTTONUP):
            for b in list(self.buttons):
                b.handle_event(e)
            return True
        if e.type == pygame.KEYDOWN and self.buttons:
            if e.key in (pygame.K_TAB, pygame.K_LEFT, pygame.K_RIGHT,
                         pygame.K_UP, pygame.K_DOWN):
                self.focus = (self.focus + 1) % len(self.buttons)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                           pygame.K_SPACE):
                self.buttons[self.focus % len(self.buttons)].on_click()
        return True

    # -- drawing ------------------------------------------------------------

    def draw(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        if (self._dim_cache is None
                or self._dim_cache.get_size() != surf.get_size()):
            self._dim_cache = pygame.Surface(surf.get_size(),
                                             pygame.SRCALPHA)
            self._dim_cache.fill((0, 0, 0, 170))
        surf.blit(self._dim_cache, (0, 0))
        card = self.card
        pygame.draw.rect(surf, th.background, card, border_radius=18)
        pygame.draw.rect(surf, th.muted, card, 2, border_radius=18)
        rule = pygame.Rect(0, 0, 96, 4)
        rule.center = (card.centerx, card.top + 2)
        pygame.draw.rect(surf, th.accent, rule, border_radius=2)
        draw_text(surf, "Audio delay", (card.centerx, card.y + 20), th, ly,
                  pt=FONT_H2, centre=True)
        x, room = card.x + 28, card.w - 56
        y = card.y + 76
        font = ly.font(FONT_BODY)
        if self.busy:
            lines = [(t, th.foreground) for t in
                     (self.job.lines if self.job is not None else [])]
            lines = lines[-self.SHOWN_LINES:] or [("Starting...",
                                                   th.foreground)]
        elif self.finished:
            colour = th.success if self.result_ok else th.error
            lines = [(self.result_text, colour)]
        else:
            lines = [(t, th.warning if warn else th.foreground)
                     for t, warn in self.intro_lines()]
        for text, colour in lines:
            for chunk in _wrap(text, font, room):
                if y > card.bottom - 150:
                    break
                draw_text(surf, chunk, (x, y), th, ly, pt=FONT_BODY,
                          centre=False, colour=colour)
                y += 28
            y += 8
        foot = ("Listening. Keep the room quiet." if self.busy
                else "In use now: " + self.now_line)
        for i, chunk in enumerate(_wrap(foot, ly.font(FONT_SMALL + 2),
                                        room)[:2]):
            draw_text(surf, chunk, (x, card.bottom - 128 + i * 22), th, ly,
                      pt=FONT_SMALL + 2, centre=False, colour=th.muted)
        for b in self.buttons:
            b.draw(surf)
        if self.buttons:
            ring = self.buttons[self.focus % len(self.buttons)].rect \
                .inflate(10, 10)
            pygame.draw.rect(surf, th.accent, ring, 3, border_radius=14)
