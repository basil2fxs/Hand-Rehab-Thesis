"""The SRT's screen: the lab's task in the app's own look.

The task is the lab script's, trial for trial (game/modes/srt.py): the
same order, counts, timing, tones and markers. The screen is the one
every other game uses: the light page, four finger cards laid out as
the lane games lay theirs out (GameplayScreen), the mode pill at the
top right and, on a keyboard, the Controls note in the corner. The
waiting cards are a neutral grey, as the script's squares were; where
the script turned a grey square red for 100 ms, the target card lights
in its finger's colour with the thicker border for the same 100 ms,
so the flash is the only colour on the row.

Nothing else moves: no score, no timer, no progress bar, no halo and
no glow on a press. The flash stays the one visual event in a trial,
so an EEG epoch has nothing else to explain, as with the script.

Between blocks the script's SPACE screens are a card with the same
words. The recall step shows the cards in a shorter row with the
entered sequence under them; each entry lights its card for the
script's 150 ms, and a click on a card enters it.

THE LAB LOOK (srt.look: lab, the lab build's setting since 1 October
2026). For EEG recordings the screen draws the script's own display
instead: a black page, four grey squares 0.13 of the half-width and
half-height across, centred 0.075 and 0.225 of the half-width either
side of the middle, the key or finger names under them, the target
turning red for the flash, and the script's white text. The script
set its squares close together to limit eye movements during EEG
(its lines 18-19), and its flash is a grey-to-red change of about the
same luminance at every location, where the app's outer cards sit
about three times further out and each lights a different brightness
(the SRT deep review, docs/research/deep/srt.md). Timing is the same
in both looks.

srt.photodiode_patch (off by default) draws a small patch in the
bottom-left corner on flash frames only, for a light sensor timing the
flash against the 30 on the amplifier: in the lab look the red square
is about as bright as the grey one, so a sensor on the square itself
would see little.
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

# The lab script's display (SRT_Sequence_learning_Final_v2.py 139-175),
# in PsychoPy's norm units: the page runs from -1 to 1 each way, so a
# size is a fraction of the half-width or the half-height, and y is up.
LAB_SQUARE = 0.13
LAB_X = (-0.225, -0.075, 0.075, 0.225)
LAB_LABEL_Y = -0.10
LAB_INSTRUCTION_Y = 0.85
LAB_FEEDBACK_Y = -0.25
LAB_RECALL_TEXT_Y = 0.6
LAB_PROGRESS_Y = -0.35
LAB_HINT_Y = -0.60
LAB_PAGE = (0, 0, 0)
LAB_GREY = (128, 128, 128)
LAB_RED = (255, 0, 0)
LAB_YELLOW = (255, 255, 0)
LAB_WHITE = (255, 255, 255)
# The light sensor's patch, in logical pixels.
PATCH = 44


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

    def look(self) -> str:
        """'lab' for the script's own display (srt.look), else 'app'."""
        v = self.engine.cfg.get("srt.look", "app")
        return ("lab" if isinstance(v, str) and v.strip().lower() == "lab"
                else "app")

    def _norm(self, x: float, y: float) -> tuple[int, int]:
        """A point in the script's norm units on this page."""
        w, h = self.layout.width, self.layout.height
        return (int(round(w / 2 + x * w / 2)),
                int(round(h / 2 - y * h / 2)))

    def _lab_rects(self) -> list[pygame.Rect]:
        w, h = self.layout.width, self.layout.height
        size = (int(round(LAB_SQUARE * w / 2)),
                int(round(LAB_SQUARE * h / 2)))
        rects = []
        for x in LAB_X:
            r = pygame.Rect((0, 0), size)
            r.center = self._norm(x, 0.0)
            rects.append(r)
        return rects

    def lane_rects(self, mode, recall: bool = False) -> list[pygame.Rect]:
        """Squares 1 to 4 as the lane games' card rects. The lab's two
        hands get the gap the lane games put between hands, so the left
        pair and the right pair read as two hands. In the lab look, the
        script's four squares, recall included."""
        if self.look() == "lab":
            return self._lab_rects()
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
                ls.neutral_idle = True
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
        draws it: the same keys, and only those."""
        if mode.on_pads:
            return
        lines = keyboard_controls_lines(self.engine, mode)
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

    # ---- the lab look ----------------------------------------------------------
    def _text_at(self, surf: pygame.Surface, text: str, y_norm: float,
                 font: pygame.font.Font, colour) -> None:
        """Centred text whose block is centred on y_norm, as a PsychoPy
        TextStim is placed."""
        lines = self._wrap(font, text, int(self.layout.width * 0.8))
        height = sum(10 if not ln else font.get_linesize() for ln in lines)
        top = self._norm(0.0, y_norm)[1] - height // 2
        self._lines(surf, text, top, font, colour,
                    int(self.layout.width * 0.8))

    def _draw_lab_squares(self, surf: pygame.Surface, mode, lit,
                          lit_colour) -> None:
        font = self.layout.font(FONT_BODY + 4)
        labels = mode.labels()
        for i, rect in enumerate(self._lab_rects()):
            colour = lit_colour if lit == i + 1 else LAB_GREY
            pygame.draw.rect(surf, colour, rect)
            if i < len(labels):
                img = font.render(str(labels[i]), True, LAB_WHITE)
                surf.blit(img, img.get_rect(
                    center=self._norm(LAB_X[i], LAB_LABEL_Y)))

    def _draw_lab(self, surf: pygame.Surface, mode) -> None:
        """The script's own display: black page, grey squares, red
        flash, white words (srt.look: lab)."""
        surf.fill(LAB_PAGE)
        step = mode.step
        kind = step.kind if step is not None else ""
        body = self.layout.font(FONT_BODY + 4)
        if kind == "message":
            self._text_at(surf, mode.message_text(step), 0.0,
                          self.layout.font(FONT_BODY + 8), LAB_WHITE)
        elif kind == "block":
            self._text_at(surf, mode.instruction(), LAB_INSTRUCTION_Y,
                          body, LAB_WHITE)
            self._draw_lab_squares(surf, mode, mode.flash_square, LAB_RED)
            fb = mode.feedback_now
            if fb:
                font = self.layout.font(FONT_H2, bold=True)
                img = font.render(fb[0], True, fb[1])
                surf.blit(img, img.get_rect(
                    center=self._norm(0.0, LAB_FEEDBACK_Y)))
        elif kind == "recall":
            self._text_at(surf, mode.recall_text(), LAB_RECALL_TEXT_Y,
                          body, LAB_WHITE)
            self._draw_lab_squares(surf, mode, mode.select_square,
                                   LAB_YELLOW)
            self._text_at(surf, mode.recall_progress(), LAB_PROGRESS_Y,
                          body, LAB_WHITE)
            hint = mode.recall_hint()
            if hint:
                self._text_at(surf, hint[0], LAB_HINT_Y,
                              self.layout.font(FONT_BODY), hint[1])
        elif kind == "saved":
            self._text_at(surf, "Sequence recorded.\n\nSaving your data...",
                          0.0, self.layout.font(FONT_BODY + 8), LAB_WHITE)

    def _draw_patch(self, surf: pygame.Surface, mode, colour) -> None:
        """The light sensor's patch, bottom left, on flash frames only
        (srt.photodiode_patch, off by default)."""
        if self.engine.cfg.get("srt.photodiode_patch", False) is not True:
            return
        if mode.flash_square is None:
            return
        h = self.layout.height
        pygame.draw.rect(surf, colour, pygame.Rect(0, h - PATCH, PATCH, PATCH))

    # ---- draw ----------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        mode = self._mode()
        if mode is not None and self.look() == "lab":
            self._draw_lab(surf, mode)
            self._draw_patch(surf, mode, LAB_WHITE)
            if self.engine.paused and not self.engine.exit_overlay_active:
                self._draw_paused_overlay(surf)
            return
        surf.fill(self.theme.background)
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
        self._draw_patch(surf, mode, (0, 0, 0))
        if self.engine.paused and not self.engine.exit_overlay_active:
            self._draw_paused_overlay(surf)
