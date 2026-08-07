"""Syllable Beats screen. Words and syllable blocks are not a lane
strip, so the mode gets its own screen instead of GameplayScreen.

The layout is built for a child: the word appears as LARGE text cut
into rounded syllable blocks, one block per beat, each block wearing
its finger's colour (index orange, middle light blue, ring black,
little yellow, the same fixed colours the lane tiles use everywhere
else) so the block-to-finger mapping is taught by colour as well as by
position and buzz. Blocks light left to right as the word is
modelled, fill as taps land, and at feedback time an extra tap shows
as an extra grey block while a missing one stays hollow, so count
errors are visible with no text to read.

Letters and reading: the block text shows the word's own chunks at
levels 1 to 5 because showing the word as text IS this build's visual
stimulus (no recorded audio or picture library exists). At level 6 the
blocks show dots while the child taps, and the graphemes only fade in
as feedback after a correct response, per the letters-attached
evidence discussed in the mode docstring: letters are feedback there,
never a prerequisite.

Flash safety: nothing on this screen flashes faster than the 2 Hz
beat, well under the 3 flashes per second limit (WCAG 2.3.1), and
feedback pulses are a single slow swell.

Screen conventions match the rest of the app: 1280x800 logical
layout, theme-aware, Esc and P are handled by the engine's global
event path, and the paused overlay mirrors GameplayScreen's.
"""
from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

import pygame

from ..game.modes._keys import keymap_for_hand, resolve_key
from .screens import ModeSelectScreen, Screen
from .widgets import (
    FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL, FONT_TITLE,
    draw_text, make_font,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


log = logging.getLogger(__name__)


FINGER_NAMES = ("Index", "Middle", "Ring", "Little")


def _text_colour_for(fill: tuple[int, int, int],
                     light: tuple[int, int, int],
                     dark: tuple[int, int, int]) -> tuple[int, int, int]:
    # Same luminance trick LaneStrip uses so the black ring block still
    # carries readable text.
    return dark if sum(fill) / 3 > 140 else light


class SyllablesScreen(Screen):

    # Block row geometry. The row is centred; heights leave room for
    # the message above and the finger row below.
    BLOCK_H = 150
    STRESS_EXTRA = 36          # stressed block drawn taller from L4 up
    BLOCK_GAP = 18
    BLOCK_MIN_W = 120
    EXTRA_W = 84               # the grey "you tapped one too many" block
    ROW_CY = 400               # vertical centre of the block row

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self._held_keys: set[int] = set()

    def _accent(self) -> tuple[int, int, int]:
        """Syllables pink from the mode picker, so the kids' screen
        keeps the same identity colour it was chosen by."""
        return ModeSelectScreen.MODE_ACCENTS.get(
            "syllables", self.theme.accent)

    def on_block_start(self) -> None:
        # Fresh block: drop any keys latched from a previous visit.
        self._held_keys.clear()

    # ---- events ------------------------------------------------------------
    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.KEYDOWN:
            self._held_keys.add(e.key)
        elif e.type == pygame.KEYUP:
            self._held_keys.discard(e.key)
        if self.engine.paused:
            # The engine only gates input for the screens it knows run
            # blocks; belt and braces here so a press during the pause
            # overlay cannot queue into the mode.
            return
        if self.engine.mode and hasattr(self.engine.mode, "handle_event"):
            self.engine.mode.handle_event(e)

    def update(self, dt: float) -> None:
        if self.engine.paused:
            return
        if self.engine.mode and hasattr(self.engine.mode, "update"):
            self.engine.mode.update(dt)

    # ---- draw --------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        mode = self.engine.mode
        if mode is None or getattr(mode, "name", "") != "Syllables":
            draw_text(surf, "Starting...",
                      (self.layout.width // 2, self.layout.height // 2),
                      self.theme, self.layout, pt=FONT_H1, centre=True,
                      colour=self.theme.muted)
            return
        now = time.perf_counter()
        self._draw_top(surf, mode)
        phase = mode.phase
        if phase == "warmup":
            self._draw_warmup(surf, mode, now)
        elif phase == "break":
            self._draw_break(surf, mode, now)
        elif phase == "done":
            pass
        else:
            self._draw_word_trial(surf, mode, now)
        self._draw_finger_row(surf, mode)
        if self.engine.paused:
            self._draw_paused_overlay(surf)

    # ---- top strip ---------------------------------------------------------
    def _draw_top(self, surf: pygame.Surface, mode) -> None:
        # Slim progress bar, same visual language as GameplayScreen.
        done, total = mode.words_done, mode.words_total
        pad, bar_y, bar_h = 30, 14, 6
        bar_w = self.layout.width - pad * 2
        track = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(track, (*self.theme.muted, 70),
                         track.get_rect(), border_radius=bar_h // 2)
        surf.blit(track, (pad, bar_y))
        frac = max(0.0, min(1.0, done / total)) if total else 0.0
        fill_w = int(bar_w * frac)
        if fill_w > 0:
            fill = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
            pygame.draw.rect(fill, (*self._accent(), 220),
                             fill.get_rect(), border_radius=bar_h // 2)
            surf.blit(fill, (pad, bar_y))
        draw_text(surf, f"Word {min(done + 1, total)} of {total}",
                  (pad, 34), self.theme, self.layout, pt=FONT_SMALL,
                  colour=self.theme.muted)
        draw_text(surf, f"Level {mode.level}   Band {mode.band}",
                  (self.layout.width // 2, 40), self.theme, self.layout,
                  pt=FONT_SMALL, centre=True, colour=self.theme.muted)
        score = f"{self.engine.score}"
        draw_text(surf, score,
                  (self.layout.width - pad - 8 * len(score), 30),
                  self.theme, self.layout, pt=FONT_H2,
                  colour=self._accent())

    # ---- warm-up -----------------------------------------------------------
    def _draw_warmup(self, surf: pygame.Surface, mode, now: float) -> None:
        cx = self.layout.width // 2
        draw_text(surf, "Tap along with the beat!",
                  (cx, 180), self.theme, self.layout, pt=FONT_H1,
                  centre=True)
        draw_text(surf, "Any finger. One tap for every tick.",
                  (cx, 230), self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)
        # A circle that swells on each beat: the visual is a helper,
        # the metronome tick is the timing reference. Pink, like the
        # rest of the mode's identity colour.
        phase = (now % mode.ioi_s) / mode.ioi_s
        r = 60 + int(26 * math.exp(-4.0 * phase))
        pygame.draw.circle(surf, self._accent(),
                           (cx, self.ROW_CY), r)
        pygame.draw.circle(surf, self.theme.background,
                           (cx, self.ROW_CY), max(6, r - 16))
        done = getattr(mode, "_warmup_done", 0)
        draw_text(surf, f"{min(done, mode.warmup_total)} of "
                        f"{mode.warmup_total} taps",
                  (cx, self.ROW_CY + 120), self.theme, self.layout,
                  pt=FONT_BODY, centre=True, colour=self.theme.muted)

    # ---- break -------------------------------------------------------------
    def _draw_break(self, surf: pygame.Surface, mode, now: float) -> None:
        cx = self.layout.width // 2
        draw_text(surf, "Great tapping! Shake your hand out.",
                  (cx, 220), self.theme, self.layout, pt=FONT_H1,
                  centre=True)
        left = 0
        if mode._phase_until is not None:
            left = max(0, int(math.ceil(mode._phase_until - now)))
        draw_text(surf, f"Next round in {left}",
                  (cx, 280), self.theme, self.layout, pt=FONT_H2,
                  centre=True, colour=self.theme.muted)
        # Four little blocks bobbing gently in the finger colours, a
        # calm animation rather than anything to respond to.
        for i in range(4):
            bob = int(10 * math.sin(now * 2.0 + i * 0.9))
            rect = pygame.Rect(0, 0, 70, 70)
            rect.center = (cx - 150 + i * 100, self.ROW_CY + bob)
            pygame.draw.rect(surf, self.theme.lane_active[i], rect,
                             border_radius=16)

    # ---- the word and its blocks -------------------------------------------
    def _draw_word_trial(self, surf: pygame.Surface, mode,
                         now: float) -> None:
        word = mode.word
        if word is None:
            return
        cx = self.layout.width // 2
        phase = mode.phase
        # Message line above the blocks: short, kind, phase-driven.
        # At feedback time the title takes the outcome colour (green
        # for a win, warm amber for "so close") so the moment lands
        # for a child before any word is read.
        msg, sub = self._messages(mode)
        title_colour = self.theme.foreground
        if phase == "feedback":
            res = mode._last_result or {}
            title_colour = (self.theme.success if res.get("correct")
                            else self.theme.warning)
        draw_text(surf, msg, (cx, 170), self.theme, self.layout,
                  pt=FONT_H1, centre=True, colour=title_colour)
        if sub:
            draw_text(surf, sub, (cx, 218), self.theme, self.layout,
                      pt=FONT_BODY, centre=True, colour=self.theme.muted)

        if phase == "attend":
            # The whole word, huge, while it is (possibly) spoken.
            font = make_font(int(FONT_TITLE * 1.6), bold=True)
            t = font.render(word.word, True, self.theme.foreground)
            surf.blit(t, t.get_rect(center=(cx, self.ROW_CY)))
            return
        self._draw_blocks(surf, mode, now)
        if phase == "countin":
            self._draw_countin(surf, mode, now)

    def _messages(self, mode) -> tuple[str, str]:
        phase = mode.phase
        if phase == "attend":
            return "Listen...", "How many beats can you hear?"
        if phase == "model":
            return "Watch and feel", "Each block is one beat"
        if phase == "replay":
            return "Watch once more", "Then the next word comes"
        if phase == "countin":
            return "Get ready...", "Tap one beat per tick"
        if phase == "respond":
            if mode.paced:
                return "Your turn!", "Tap the beats in time"
            if mode.order_required:
                return "Your turn!", "Tap the beats, first finger first"
            return "Your turn!", "Tap once for every beat"
        if phase == "feedback":
            res = mode._last_result or {}
            if res.get("correct"):
                return "Wonderful!", ""
            err = res.get("error", "")
            return "So close!", {
                "extra_tap": "One tap too many, see the grey block",
                "missing_tap": "A beat is still empty",
                "wrong_order": "Try starting from the first finger",
                "off_beat": "Try to land right on the tick",
                "wrong_stress": "Press the tall block harder",
                "timeout": "Have a try next time, no rush",
            }.get(err, "Watch once more")
        return "", ""

    def _block_rects(self, mode) -> list[pygame.Rect]:
        """One rect per expected unit, centred as a row. The stressed
        block is taller from level 4 up; level 5 draws the onset small
        and the rime large, the standard onset-rime visual."""
        word = mode.word
        units = mode.units_for(word)
        font = make_font(int(FONT_TITLE * 1.1), bold=True)
        widths = []
        for i, u in enumerate(units):
            text = u if mode.level != 6 else "  "
            w = max(self.BLOCK_MIN_W, font.size(text)[0] + 56)
            if mode.level == 5:
                w = int(w * (0.7 if i == 0 else 1.15))
            widths.append(w)
        total = sum(widths) + self.BLOCK_GAP * (len(units) - 1)
        x = self.layout.width // 2 - total // 2
        rects = []
        for i, w in enumerate(widths):
            h = self.BLOCK_H
            if mode.level == 5:
                h = int(h * (0.72 if i == 0 else 1.0))
            elif mode.level >= 4 and i == word.stress:
                h += self.STRESS_EXTRA
            r = pygame.Rect(x, 0, w, h)
            r.centery = self.ROW_CY
            rects.append(r)
            x += w + self.BLOCK_GAP
        return rects

    def _draw_blocks(self, surf: pygame.Surface, mode, now: float) -> None:
        word = mode.word
        units = mode.units_for(word)
        rects = self._block_rects(mode)
        phase = mode.phase
        res = mode._last_result or {}
        n_taps = len(mode.taps)
        feedback_ok = phase == "feedback" and res.get("correct")
        # One slow swell over the whole feedback window; a single
        # pulse, not a flash.
        swell = 0.0
        if phase == "feedback" and mode._phase_t0 is not None:
            swell = math.sin(min(1.0, (now - mode._phase_t0)
                                 / mode.FEEDBACK_S) * math.pi)
        for i, (u, rect) in enumerate(zip(units, rects)):
            finger = i % 4
            lit = (phase in ("model", "replay")
                   and getattr(mode, "_model_idx", -1) == i)
            filled = (phase == "respond" and i < n_taps) or (
                phase == "feedback" and i < res.get("n_taps", 0))
            hollow = phase == "feedback" and i >= res.get("n_taps", 0)
            if feedback_ok:
                grow = int(6 * swell)
                r = rect.inflate(grow, grow)
                pygame.draw.rect(surf, self.theme.success, r,
                                 border_radius=22)
                fill = self.theme.success
            elif hollow:
                # A beat nobody tapped: outline only, unmissable.
                pygame.draw.rect(surf, self.theme.muted, rect, 4,
                                 border_radius=22)
                fill = self.theme.background
            else:
                fill = (self.theme.lane_active[finger]
                        if (lit or filled)
                        else self.theme.lane_idle[finger])
                pygame.draw.rect(surf, fill, rect, border_radius=22)
                if lit:
                    ring = rect.inflate(14, 14)
                    pygame.draw.rect(surf, self.theme.foreground, ring,
                                     3, border_radius=26)
            # Block text: the chunk itself, except level 6 shows a dot
            # until the graphemes earn their fade-in on success.
            if mode.level == 6 and not feedback_ok:
                dot = _text_colour_for(fill, (255, 255, 255),
                                       self.theme.foreground)
                pygame.draw.circle(surf, dot, rect.center, 10)
            else:
                font = make_font(int(FONT_TITLE * 1.1), bold=True)
                colour = _text_colour_for(
                    fill, (255, 255, 255), self.theme.foreground)
                t = font.render(u, True, colour)
                if mode.level == 6:
                    # Fade the graphemes in over the feedback swell.
                    t.set_alpha(int(255 * min(1.0, swell * 1.6)))
                surf.blit(t, t.get_rect(center=rect.center))
            # A dot under each filled block at feedback time so a
            # correct count reads at a glance.
            if phase == "feedback" and filled and not hollow:
                pygame.draw.circle(surf, self.theme.success,
                                   (rect.centerx, rect.bottom + 20), 7)
        # Extra taps: one grey block per surplus tap, appended to the
        # row, so "too many" is visible without words.
        extra = 0
        if phase == "respond":
            extra = max(0, n_taps - len(units))
        elif phase == "feedback":
            extra = max(0, res.get("n_taps", 0) - len(units))
        if extra and rects:
            x = rects[-1].right + self.BLOCK_GAP
            for _ in range(extra):
                r = pygame.Rect(x, 0, self.EXTRA_W, self.BLOCK_H - 30)
                r.centery = self.ROW_CY
                pygame.draw.rect(surf, self.theme.muted, r,
                                 border_radius=18)
                x += self.EXTRA_W + self.BLOCK_GAP

    def _draw_countin(self, surf: pygame.Surface, mode,
                      now: float) -> None:
        # Big count number under the blocks, stepping with the ticks.
        if mode._phase_t0 is None or mode.count_in_beats <= 0:
            return
        beat = int((now - mode._phase_t0) / mode.ioi_s) + 1
        beat = max(1, min(mode.count_in_beats, beat))
        draw_text(surf, str(beat),
                  (self.layout.width // 2, self.ROW_CY + 140),
                  self.theme, self.layout, pt=FONT_TITLE + 10,
                  centre=True, colour=self._accent())

    # ---- finger row --------------------------------------------------------
    def _draw_finger_row(self, surf: pygame.Surface, mode) -> None:
        """Small tiles along the bottom in the finger colours, lighting
        while that finger is down, so the child can always see which
        finger is which without a lane strip."""
        n = 4
        tile_w, tile_h, gap = 150, 64, 20
        total = tile_w * n + gap * (n - 1)
        x = self.layout.width // 2 - total // 2
        y = self.layout.height - 110
        km = self.engine.cfg.get(keymap_for_hand(self.engine.hand_mode), {})
        for i in range(n):
            lane = mode.lanes[i] if i < len(mode.lanes) else i
            pressed = self._lane_down(lane, km)
            fill = (self.theme.lane_active[i] if pressed
                    else self.theme.lane_idle[i])
            rect = pygame.Rect(x, y, tile_w, tile_h)
            pygame.draw.rect(surf, fill, rect, border_radius=14)
            colour = _text_colour_for(fill, (255, 255, 255),
                                      self.theme.foreground)
            draw_text(surf, FINGER_NAMES[i],
                      (rect.centerx, rect.centery - 10), self.theme,
                      self.layout, pt=FONT_BODY, centre=True,
                      colour=colour)
            key_label = next((k for k, ln in km.items() if ln == lane), "")
            if key_label:
                draw_text(surf, key_label.replace("semicolon", ";"),
                          (rect.centerx, rect.centery + 16), self.theme,
                          self.layout, pt=FONT_SMALL, centre=True,
                          colour=colour)
            x += tile_w + gap

    def _lane_down(self, lane: int, km: dict) -> bool:
        # Keyboard: any bound key currently held. FSR: the detector's
        # live pressed state, same source the lane strips use.
        for key_name, lane_idx in km.items():
            if lane_idx != lane:
                continue
            kc = resolve_key(key_name)
            if kc is not None and kc in self._held_keys:
                return True
        resolved = getattr(self.engine, "_resolve_lane_to_detector", None)
        if callable(resolved):
            mapped = resolved(lane)
            if mapped:
                hand, idx = mapped
                det = self.engine.detectors.get(hand)
                if det is not None:
                    try:
                        return bool(det.pressed[idx])
                    except (IndexError, TypeError):
                        return False
        return False

    # ---- paused ------------------------------------------------------------
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
