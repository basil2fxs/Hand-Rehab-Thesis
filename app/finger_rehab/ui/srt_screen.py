"""The SRT's screen: the lab's task in the app's own look.

The task is the lab script's, trial for trial (game/modes/srt.py): the
same order, counts, timing, tones and markers. The screen is the one
every other game uses: the light page, four finger cards laid out as
the lane games lay theirs out (GameplayScreen), the mode pill at the
top right and, on a keyboard, the Controls note in the corner. Where
the script turned a grey square red for 100 ms, the target card lights
in its finger's stronger colour with the thicker border for the same
100 ms, the way the app's own reaction block lights a card.

Nothing else moves: no score, no timer, no progress bar, no halo and
no glow on a press. The flash stays the one visual event in a trial,
so an EEG epoch has nothing else to explain, as with the script.

Between blocks the script's SPACE screens are a card with the same
words. The recall step shows the cards in a shorter row with the
entered sequence under them; each entry lights its card for the
script's 150 ms, and a click on a card enters it.
"""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pygame

from .screens import GameplayScreen, ModeSelectScreen, Screen
from .widgets import (FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL, Card,
                      LaneStrip, draw_text, keyboard_controls_lines)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


# The lane games' row (GameplayScreen._build_lane_block): 80 px either
# side, 18 px gutters, cards from y 220 down to a shared baseline 140 px
# above the bottom, each card as tall as its finger. The recall row is
# shorter so its words fit above and below it.
MARGIN = 80
GUTTER = 18
TOP = 220
BASELINE_GAP = 140
RECALL_TOP = 262
RECALL_FULL_H = 250
INSTRUCTION_Y = 132
# The practice word, in the page's own colours: the script's white Miss!
# would vanish on the light page.
FEEDBACK_TONE = {"Correct": "success", "Incorrect": "error",
                 "Miss!": "warning"}


class SRTScreen(Screen):

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self._lanes: list[LaneStrip] = []
        self._lane_key: tuple | None = None

    def on_block_start(self) -> None:
        self._lane_key = None

    # ---- plumbing -----------------------------------------------------------
    def _mode(self):
        mode = getattr(self.engine, "mode", None)
        return mode if getattr(mode, "name", "") == "SRT" else None

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.engine.paused:
            return
        mode = self._mode()
        if mode is None:
            return
        step = mode.step
        if (e.type == pygame.MOUSEBUTTONDOWN
                and getattr(e, "button", 0) == 1):
            if step is not None and step.kind == "recall":
                pos = getattr(e, "pos", (-1, -1))
                for i, r in enumerate(self.lane_rects(mode, recall=True)):
                    if r.collidepoint(pos):
                        mode.recall_square(i + 1)
                        break
            return
        mode.handle_event(e)

    def update(self, dt: float) -> None:
        if self.engine.paused:
            return
        mode = self._mode()
        if mode is not None:
            mode.update(dt)

    # ---- the cards -----------------------------------------------------------
    def _square_fingers(self, mode) -> list[tuple[str, int]]:
        """(hand, finger) for squares 1 to 4, left to right: the right
        hand index to little, the left hand little to index, or the
        lab's two hands (left middle, left index, right index, right
        middle)."""
        two = bool(getattr(mode, "two_hands", False))
        hand_mode = getattr(self.engine, "hand_mode", "right")
        out = []
        for square in range(1, 5):
            lane = int(mode.square_to_lane(square))
            if two:
                hand = "left" if lane >= 4 else "right"
            else:
                hand = "left" if hand_mode == "left" else "right"
            out.append((hand, lane % 4))
        return out

    def lane_rects(self, mode, recall: bool = False) -> list[pygame.Rect]:
        """Squares 1 to 4 as the lane games' card rects. The lab's two
        hands get the gap the lane games put between hands, so the left
        pair and the right pair read as two hands."""
        w, h = self.layout.width, self.layout.height
        two = bool(getattr(mode, "two_hands", False))
        mid = GameplayScreen.HAND_BLOCK_GAP if two else GUTTER
        card_w = (w - 2 * MARGIN - GUTTER * 2 - mid) // 4
        if recall:
            top, full_h = RECALL_TOP, RECALL_FULL_H
        else:
            top, full_h = TOP, h - BASELINE_GAP - TOP
        rects = []
        for pos, (_hand, finger) in enumerate(self._square_fingers(mode)):
            x = MARGIN + pos * (card_w + GUTTER) + (mid - GUTTER
                                                    if pos >= 2 else 0)
            rects.append(GameplayScreen._finger_lane_rect(
                x, top, card_w, full_h, finger))
        return rects

    def lanes(self, mode, recall: bool = False) -> list[LaneStrip]:
        """The four cards, rebuilt only when the layout they depend on
        changes."""
        key = (id(mode), recall, self.layout.width, self.layout.height,
               getattr(self.engine, "hand_mode", "right"), id(self.theme))
        if key != self._lane_key:
            self._lane_key = key
            self._lanes = []
            fingers = self._square_fingers(mode)
            for i, (rect, (hand, finger)) in enumerate(
                    zip(self.lane_rects(mode, recall), fingers)):
                ls = LaneStrip(lane=i, rect=rect, theme=self.theme,
                               layout=self.layout, hand=hand, finger=finger)
                # The card lighting is the whole stimulus: no strapline,
                # no readout, no halo, no draining bar.
                ls.show_hand_label = False
                ls.show_value_readout = False
                ls.show_halos = False
                ls.show_timing_bar = False
                self._lanes.append(ls)
        return self._lanes

    def _draw_cards(self, surf: pygame.Surface, mode, lit: int | None,
                    recall: bool = False) -> None:
        now = time.perf_counter()
        for i, ls in enumerate(self.lanes(mode, recall)):
            ls.active = lit == i + 1
            ls.is_pressed = False
            ls.draw(surf, now)

    # ---- words ---------------------------------------------------------------
    @staticmethod
    def _wrap(font: pygame.font.Font, text: str, max_w: int) -> list[str]:
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

    def _lines(self, surf: pygame.Surface, text: str, top: int,
               font: pygame.font.Font, colour, max_w: int,
               gap: int = 10) -> int:
        """Centred lines from `top`; a blank line is a small gap, not a
        whole line. Returns the y under the last line."""
        cx = self.layout.width // 2
        y = top
        step = font.get_linesize()
        for line in self._wrap(font, text, max_w):
            if not line:
                y += gap
                continue
            img = font.render(line, True, colour)
            surf.blit(img, img.get_rect(midtop=(cx, y)))
            y += step
        return y

    def _draw_pill(self, surf: pygame.Surface) -> None:
        accent = ModeSelectScreen.MODE_ACCENTS.get("srt", self.theme.accent)
        font = self.layout.font(FONT_SMALL + 2)
        label = font.render("REACTION", True, (255, 255, 255))
        pill = pygame.Rect(0, 0, label.get_width() + 24,
                           label.get_height() + 8)
        pill.topright = (self.layout.width - 28, 30)
        pygame.draw.rect(surf, accent, pill, border_radius=pill.h // 2)
        surf.blit(label, label.get_rect(center=pill.center))

    def _draw_controls(self, surf: pygame.Surface, mode) -> None:
        """The corner Controls note on a keyboard, as every lane game
        draws it, plus the lab's own V B N M, which answer too."""
        if mode.on_pads:
            return
        lines = keyboard_controls_lines(self.engine, mode)
        lines.append("or V B N M")
        font = self.layout.font(FONT_SMALL)
        right = self.layout.width - 24
        y = self.layout.height - 22 - 18 * len(lines)
        head = font.render("Controls", True, self.theme.muted)
        surf.blit(head, head.get_rect(topright=(right, y - 20)))
        for line in lines:
            img = font.render(line, True, self.theme.muted)
            surf.blit(img, img.get_rect(topright=(right, y)))
            y += 18

    def _draw_message(self, surf: pygame.Surface, text: str) -> None:
        """One of the script's SPACE screens as a card: its first short
        line as the title, the words under it, the Press SPACE line as
        the call to action at the foot."""
        paras = text.split("\n\n") if text else []
        title = ""
        if paras:
            first = paras[0].split("\n")
            if len(first[0]) <= 40:
                title = first[0]
                rest = "\n".join(first[1:])
                paras = ([rest] if rest else []) + paras[1:]
        hint = ""
        if paras and paras[-1].startswith("Press "):
            hint = paras.pop()
        body = "\n\n".join(paras)
        width = 820
        inner = width - 2 * 56
        title_font = self.layout.font(FONT_H1, bold=True)
        body_font = self.layout.font(FONT_BODY + 4)
        hint_font = self.layout.font(FONT_BODY + 2, bold=True)
        body_lines = self._wrap(body_font, body, inner) if body else []
        height = 2 * 48
        if title:
            height += title_font.get_linesize()
        if body_lines:
            height += 24 + sum(10 if not ln else body_font.get_linesize()
                               for ln in body_lines)
        if hint:
            height += 32 + hint_font.get_linesize()
        card = pygame.Rect(0, 0, width, height)
        card.center = (self.layout.width // 2, self.layout.height // 2)
        Card(card, self.theme, layout=self.layout).draw(surf)
        y = card.y + 48
        if title:
            y = self._lines(surf, title, y, title_font, self.theme.foreground,
                            inner)
        if body_lines:
            y = self._lines(surf, body, y + 24, body_font,
                            self.theme.foreground, inner)
        if hint:
            self._lines(surf, hint, y + 32, hint_font, self.theme.accent,
                        inner)

    # ---- draw ----------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        mode = self._mode()
        if mode is None:
            draw_text(surf, "Starting...",
                      (self.layout.width // 2, self.layout.height // 2),
                      self.theme, self.layout, pt=FONT_H1, centre=True)
            return
        self._draw_pill(surf)
        step = mode.step
        kind = step.kind if step is not None else ""
        cx = self.layout.width // 2
        if kind == "message":
            self._draw_message(surf, mode.message_text(step))
        elif kind == "block":
            draw_text(surf, mode.instruction(), (cx, INSTRUCTION_Y),
                      self.theme, self.layout, pt=FONT_BODY + 4, centre=True)
            self._draw_cards(surf, mode, mode.flash_square)
            fb = mode.feedback_now
            if fb:
                tone = FEEDBACK_TONE.get(fb[0], "foreground")
                colour = getattr(self.theme, tone, self.theme.foreground)
                font = self.layout.font(FONT_H2, bold=True)
                img = font.render(fb[0], True, colour)
                baseline = self.layout.height - BASELINE_GAP
                surf.blit(img, img.get_rect(center=(cx, baseline + 62)))
            self._draw_controls(surf, mode)
        elif kind == "recall":
            self._lines(surf, mode.recall_text(), 44,
                        self.layout.font(FONT_BODY + 2),
                        self.theme.foreground, 1000)
            self._draw_cards(surf, mode, mode.select_square, recall=True)
            y = self._lines(surf, mode.recall_progress(),
                            RECALL_TOP + RECALL_FULL_H + 34,
                            self.layout.font(FONT_BODY + 2),
                            self.theme.foreground, 1000)
            hint = mode.recall_hint()
            if hint:
                done = len(mode.recalled) == len(mode.seq)
                self._lines(surf, hint[0], y + 26,
                            self.layout.font(FONT_BODY, bold=done),
                            self.theme.success if done else self.theme.muted,
                            1000)
            self._draw_controls(surf, mode)
        elif kind == "saved":
            self._draw_message(surf,
                               "Sequence recorded.\n\nSaving your data...")
        if self.engine.paused and not self.engine.exit_overlay_active:
            self._draw_paused_overlay(surf)
