"""The SRT's screen: the lab script's window, drawn as the script drew it.

Black background, four grey squares, the target red for its 100 ms,
the key or finger names under the squares, the one instruction line at
the top, and in practice the feedback word under the squares. Between
blocks, the script's SPACE screens; after the post-test, its recall
screen. Every position and size is the script's, in PsychoPy norm
units laid over the app's 1280 x 800 surface (x -1 to 1 left to
right, y 1 to -1 top to bottom, text heights as a share of the half
height), so nothing here is a design choice of this app.

Colours are PsychoPy's named colours the script used: grey 128,
red, yellow for a recalled square, white text, green (0, 128, 0) for
Correct and lime for the submit line.

Nothing on this screen moves except the stimulus, the practice word
and the recall entries: no score, no timer, no chip. Esc and P are the
engine's, as on every block screen.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .screens import Screen
from .widgets import FONT_H1, draw_text, make_font

if TYPE_CHECKING:
    from ..game.engine import GameEngine


BLACK = (0, 0, 0)
GREY = (128, 128, 128)
RED = (255, 0, 0)
YELLOW = (255, 255, 0)
WHITE = (255, 255, 255)

# The script's text heights and anchors, norm units.
MESSAGE_H = 0.07
MESSAGE_WRAP = 1.6
INSTRUCTION = (0.0, 0.85, 0.05, 1.8)
LABEL_Y = -0.10
LABEL_H = 0.05
FEEDBACK = (0.0, -0.25, 0.055)
RECALL_TEXT = (0.0, 0.6, 0.05, 1.8)
RECALL_PROGRESS = (0.0, -0.35, 0.05)
RECALL_HINT = (0.0, -0.60, 0.045)
SAVED = (0.0, 0.0, 0.06)
# Line pitch as a multiple of the text height, near PsychoPy's.
LINE_SPACING = 1.25


class SRTScreen(Screen):

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self._fonts: dict[int, pygame.font.Font] = {}

    def on_block_start(self) -> None:
        pass

    # ---- plumbing -----------------------------------------------------------
    def _mode(self):
        mode = getattr(self.engine, "mode", None)
        return mode if getattr(mode, "name", "") == "SRT" else None

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.engine.paused:
            return
        mode = self._mode()
        if mode is not None:
            mode.handle_event(e)

    def update(self, dt: float) -> None:
        if self.engine.paused:
            return
        mode = self._mode()
        if mode is not None:
            mode.update(dt)

    # ---- norm units ----------------------------------------------------------
    def _pos(self, x: float, y: float) -> tuple[int, int]:
        w, h = self.layout.width, self.layout.height
        return (int(round((x + 1.0) / 2.0 * w)),
                int(round((1.0 - y) / 2.0 * h)))

    def _font(self, height_norm: float) -> pygame.font.Font:
        px = max(8, int(round(height_norm * self.layout.height / 2.0)))
        font = self._fonts.get(px)
        if font is None:
            font = self._fonts[px] = make_font(px)
        return font

    def _wrap(self, font: pygame.font.Font, text: str,
              max_w: int) -> list[str]:
        lines: list[str] = []
        for para in text.split("\n"):
            if not para:
                lines.append("")
                continue
            line = ""
            for word in para.split(" "):
                trial = f"{line} {word}" if line else word
                if line and font.size(trial)[0] > max_w:
                    lines.append(line)
                    line = word
                else:
                    line = trial
            lines.append(line)
        return lines

    def _text(self, surf: pygame.Surface, text: str, x: float, y: float,
              height: float, colour=WHITE, wrap: float | None = None) -> None:
        """Centred block of lines, centred on (x, y) like a TextStim."""
        font = self._font(height)
        max_w = (int(wrap * self.layout.width / 2.0) if wrap
                 else self.layout.width)
        lines = self._wrap(font, text, max_w)
        px = height * self.layout.height / 2.0
        step = int(round(px * LINE_SPACING))
        cx, cy = self._pos(x, y)
        top = cy - (step * len(lines)) // 2
        for i, line in enumerate(lines):
            if not line:
                continue
            img = font.render(line, True, colour)
            rect = img.get_rect(center=(cx, top + i * step + step // 2))
            surf.blit(img, rect)

    # ---- pieces ------------------------------------------------------------------
    def _squares(self, surf: pygame.Surface, mode, lit: int | None,
                 lit_colour) -> None:
        rects = mode.square_rects(self.layout.width, self.layout.height)
        for i, r in enumerate(rects):
            colour = lit_colour if lit == i + 1 else GREY
            pygame.draw.rect(surf, colour, r)
        font = self._font(LABEL_H)
        _cx, ly = self._pos(0.0, LABEL_Y)
        for r, label in zip(rects, mode.labels()):
            img = font.render(label, True, WHITE)
            surf.blit(img, img.get_rect(center=(r.centerx, ly)))

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(BLACK)
        mode = self._mode()
        if mode is None:
            draw_text(surf, "Starting...",
                      (self.layout.width // 2, self.layout.height // 2),
                      self.theme, self.layout, pt=FONT_H1, centre=True,
                      colour=WHITE)
            return
        step = mode.step
        kind = step.kind if step is not None else ""
        if kind == "message":
            self._text(surf, mode.message_text(step), 0.0, 0.0,
                       MESSAGE_H, wrap=MESSAGE_WRAP)
        elif kind == "block":
            self._squares(surf, mode, mode.flash_square, RED)
            x, y, h, wrap = INSTRUCTION
            self._text(surf, mode.instruction(), x, y, h, wrap=wrap)
            fb = mode.feedback_now
            if fb:
                fx, fy, fh = FEEDBACK
                self._text(surf, fb[0], fx, fy, fh, colour=fb[1],
                           wrap=1.8)
        elif kind == "recall":
            x, y, h, wrap = RECALL_TEXT
            self._text(surf, mode.recall_text(), x, y, h, wrap=wrap)
            self._squares(surf, mode, mode.select_square, YELLOW)
            px_, py_, ph = RECALL_PROGRESS
            self._text(surf, mode.recall_progress(), px_, py_, ph)
            hint = mode.recall_hint()
            if hint:
                hx, hy, hh = RECALL_HINT
                self._text(surf, hint[0], hx, hy, hh, colour=hint[1])
        elif kind == "saved":
            x, y, h = SAVED
            self._text(surf, "Sequence recorded.\n\nSaving your data...",
                       x, y, h)
        if self.engine.paused and not self.engine.exit_overlay_active:
            self._draw_paused_overlay(surf)
