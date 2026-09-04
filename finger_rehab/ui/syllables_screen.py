"""Syllables screen: a word being built at the top, four written
chunks falling over four fingers below it. Words and falling tiles are
not a lane strip, so the mode gets its own screen instead of
GameplayScreen.

The screen is built so that a seven year old, or the parent across the
table, always knows two things without reading anything twice: whose
turn it is, and why what just happened happened. Every phase announces
itself with one big stage title and one short instruction:

  WARM UP      tap along with the tick, any finger
  LISTEN...    the word appears huge and is spoken, and the strip at
               the top shows one empty slot per syllable
  WATCH        each slot lights in turn with its chunk while the
               syllable is spoken and the whole hand feels one roll;
               then the slots empty again, because the next phase is
               remembering, not copying
  WHICH ONE?   four chunks fall slowly down the four lanes over the
               child's fingers. One is the syllable that comes next.
               Press the finger under it
  WONDERFUL!   every slot filled, the word swells and is spoken whole

THE TILES CARRY NO CLUE. All four are drawn identically: same size,
same neutral card colour, same weight of text, all lower case. The
only thing that says which finger answers a tile is WHERE the tile is,
which is the spatial code the mode's docstring defends (Fitts and
Seeger 1953). So this screen must never colour the target tile, ring
it, put it in a fixed lane, or start its fade earlier than the others.
The finger colours live under the lanes in the seat row, where they
name the FINGER and not the answer.

Letters are widely tracked (Zorzi et al. 2012, PNAS: extra-large
letter spacing improved dyslexic children's reading on the fly) in the
app's ordinary sans font (Wery and Diliberto 2017; Kuster et al. 2018:
special dyslexia fonts do not help).

FEEDBACK IS LOUD WHEN IT IS GOOD AND QUIET WHEN IT IS NOT. A correct
press lifts its tile up into the word strip and fills that slot in the
finger's colour. A wrong press turns that one tile grey and lets it
drift away; nothing flashes, nothing sounds, no cross appears, and the
other tiles keep falling, so the child can still get it. A set that
falls off the bottom unanswered shows the right tile glowing once as
it goes, which is the corrective display, and it lands seconds after
any wrong press rather than on top of it.

THE REWARD LAYER the screen draws (the mode owns every decision; see
THE REWARD LAYER in syllables.py): up to three stars in the
bottom-left corner at fixed word streaks, peripheral on purpose so
they reward without stealing the focal point; the break screen is the
journey, one stop per round on a walking strip with the round's
sticker stamped on it; a band promotion shows a one-shot "Bigger
words!" card on the next between-word screen and a demotion shows
nothing at all.

The break screen also carries one line for the adult: the review of
this whole family of games found supportive adult interaction to be
the only moderator that mattered (McTigue, Solheim, Zimmer and Uppstad
2020), so the rest is where the screen asks for it.

Flash safety: nothing on this screen repeats faster than 2 Hz; the
lift, the grey drift and the miss glow are one-shot animations (WCAG
2.3.1).

Screen conventions match the rest of the app: 1280x800 logical layout,
theme-aware, Esc and P are handled by the engine's global event path,
and the paused overlay mirrors GameplayScreen's.
"""
from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

import pygame

from .screens import ModeSelectScreen, Screen, draw_skip_chip
from .widgets import (
    FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL, FONT_TITLE,
    draw_text, keyboard_controls_lines, make_font,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


log = logging.getLogger(__name__)


# Streak-star gold, fixed across themes: the stars are a reward mark,
# not a theme element, and the same gold reads on light and dark alike.
STAR_GOLD = (245, 191, 66)

# The word bands' identity colours for the promotion card.
BAND_COLOURS = {
    "A": (34, 197, 94),
    "B": (59, 130, 246),
    "C": (168, 85, 247),
}

# The one fiction shell (never rotated): the session is a bush walk and
# every round is a stop on it.
JOURNEY_STOPS = ("The Creek", "Big Rock", "The Lookout",
                 "The Waterfall", "The Cave", "Old Bridge",
                 "The Meadow", "The Summit")


def _star_points(cx: float, cy: float, r_outer: float,
                 r_inner: float) -> list[tuple[float, float]]:
    """A five-point star's polygon, point up."""
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        r = r_outer if i % 2 == 0 else r_inner
        pts.append((cx + r * math.cos(ang), cy + r * math.sin(ang)))
    return pts


def _mix(a: tuple[int, int, int], b: tuple[int, int, int],
         t: float) -> tuple[int, int, int]:
    return tuple(int(x + (y - x) * t) for x, y in zip(a, b))


class SyllablesScreen(Screen):

    # ---- geometry, in the 1280x800 logical layout ----
    STRIP_Y = 112              # centre of the word-building strip
    STRIP_H = 80
    SLOT_GAP = 14
    SLOT_MIN_W = 120
    SLOT_MAX_W = 220
    TITLE_Y = 186              # stage title
    SUB_Y = 226                # one-line instruction under it
    TOP_Y = 306                # where a tile enters
    EXIT_Y = 606               # where a tile leaves
    TILE_W = 196
    TILE_H = 90
    LANE_PAD = 90              # tile field inset from the screen edges
    SEAT_Y = 672               # the finger seats under the lanes
    SEAT_R = 11
    # Letter tracking on the tiles and the strip, as a fraction of the
    # point size (Zorzi et al. 2012).
    TRACKING = 0.12
    # How long the newest star's one-shot pop runs.
    STAR_FLASH_S = 0.9
    STAMP_FLASH_S = 1.0

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        # Animation trackers, all read-side: the mode stays the single
        # source of truth and the screen just notices changes.
        self._last_model_idx = -1
        self._model_lit_t = 0.0
        # Pre-start countdown, same contract as GameplayScreen.
        self._countdown_until = 0.0
        self._dim_cache: pygame.Surface | None = None
        self._tile_fonts: dict[int, pygame.font.Font] = {}

    def start_countdown(self, seconds: float) -> None:
        """Begin the pre-start GET READY countdown. Called by the
        engine when the block begins, exactly as on GameplayScreen."""
        self._countdown_until = time.perf_counter() + max(0.0, seconds)

    def _countdown_remaining(self) -> float:
        return max(0.0, self._countdown_until - time.perf_counter())

    def _accent(self) -> tuple[int, int, int]:
        """Syllables pink from the mode picker, so the kids' screen
        keeps the identity colour it was chosen by."""
        return ModeSelectScreen.MODE_ACCENTS.get(
            "syllables", self.theme.accent)

    def _card(self) -> tuple[int, int, int]:
        """The tile fill: one neutral card colour for all four tiles in
        every theme. Never a finger colour and never per option, so no
        tile can be told from another before it is pressed."""
        return _mix(self.theme.background, self.theme.foreground, 0.10)

    def on_block_start(self) -> None:
        self._last_model_idx = -1

    # ---- events ------------------------------------------------------------
    def handle_event(self, e: pygame.event.Event) -> None:
        if self.engine.paused:
            return
        if self.engine.mode and hasattr(self.engine.mode, "handle_event"):
            self.engine.mode.handle_event(e)

    def update(self, dt: float) -> None:
        if self.engine.paused:
            return
        if (self.engine.mode and hasattr(self.engine.mode, "update")
                and self._countdown_remaining() <= 0):
            self.engine.mode.update(dt)

    # ---- stage copy --------------------------------------------------------
    def _stage(self, mode) -> tuple[str, str, str]:
        """(title, instruction, colour name) for the current phase.
        Colour names resolve through _stage_colour so the copy can be
        unit-tested without a display."""
        phase = mode.phase
        if phase == "warmup":
            return ("WARM UP", "Tap along with the tick. Any finger.",
                    "accent")
        if phase == "attend":
            return ("LISTEN...", "Here is the word.", "accent")
        if phase == "model":
            return ("WATCH", "Hands off. See and hear each part.",
                    "accent")
        if phase == "choose":
            return ("WHICH ONE?",
                    "Press the finger under the part that comes next.",
                    "success")
        if phase == "complete":
            return ("WONDERFUL!", "", "success")
        if phase == "break":
            hands = "hands" if getattr(mode, "bilateral", False) else "hand"
            return ("REST TIME",
                    f"Round {mode.words_done // mode.round_size} done! "
                    f"Shake your {hands} out.", "foreground")
        return ("", "", "muted")

    def _hands_line(self, mode) -> str:
        """One short sentence naming the hand this word plays on, said
        at ATTEND before any tile exists so it can never be read as a
        hint about which tile is right. A single-hand session needs no
        line at all."""
        if mode.phase not in ("attend", "model"):
            return ""
        if not getattr(mode, "bilateral", False):
            return ""
        return f"{str(mode.word_hand).capitalize()} hand this time."

    def _stage_colour(self, name: str) -> tuple[int, int, int]:
        if name == "accent":
            return self._accent()
        return getattr(self.theme, name, self.theme.foreground)

    def _draw_header(self, surf: pygame.Surface, mode) -> None:
        title, sub, colour = self._stage(mode)
        if not title:
            return
        cx = self.layout.width // 2
        draw_text(surf, title, (cx, self.TITLE_Y), self.theme, self.layout,
                  pt=FONT_H1 + 6, centre=True,
                  colour=self._stage_colour(colour))
        if sub:
            draw_text(surf, sub, (cx, self.SUB_Y), self.theme, self.layout,
                      pt=FONT_BODY + 2, centre=True,
                      colour=self.theme.muted)

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
            self._draw_header(surf, mode)
            self._draw_warmup(surf, mode, now)
        elif phase == "break":
            self._draw_header(surf, mode)
            self._draw_break(surf, mode, now)
        elif phase == "gap":
            self._draw_gap(surf, mode, now)
        elif phase == "done":
            pass
        else:
            self._draw_word_trial(surf, mode, now)
        if phase in ("attend", "model", "choose", "complete", "gap"):
            self._draw_streak_stars(surf, mode, now)
        self._draw_controls_note(surf, mode)
        remaining = self._countdown_remaining()
        if remaining > 0:
            self._draw_countdown_card(surf, remaining)
        draw_skip_chip(surf, self.layout, self.theme, self.engine)
        if self.engine.paused and not self.engine.exit_overlay_active:
            self._draw_paused_overlay(surf)

    def _draw_countdown_card(self, surf: pygame.Surface,
                             remaining: float) -> None:
        """GET READY card matching GameplayScreen's, in this mode's
        pink, so the pre-start moment looks the same everywhere."""
        if (self._dim_cache is None
                or self._dim_cache.get_size() != surf.get_size()):
            self._dim_cache = pygame.Surface(surf.get_size(),
                                             pygame.SRCALPHA)
            self._dim_cache.fill((0, 0, 0, 60))
        surf.blit(self._dim_cache, (0, 0))
        accent = self._accent()
        card_rect = pygame.Rect(0, 0, 420, 240)
        card_rect.center = (self.layout.width // 2,
                            self.layout.height // 2)
        fill_surf = pygame.Surface(card_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(fill_surf, (*self.theme.background, 245),
                         fill_surf.get_rect(), border_radius=22)
        pygame.draw.rect(fill_surf, (*accent, 150),
                         fill_surf.get_rect(), 3, border_radius=22)
        surf.blit(fill_surf, card_rect.topleft)
        draw_text(surf, "GET READY",
                  (card_rect.centerx, card_rect.y + 56),
                  self.theme, self.layout, pt=FONT_H1,
                  centre=True, colour=self.theme.muted)
        draw_text(surf, f"{remaining:.1f}",
                  (card_rect.centerx, card_rect.y + 156),
                  self.theme, self.layout, pt=140,
                  centre=True, colour=accent)

    # ---- top strip ---------------------------------------------------------
    def _top_label(self, mode) -> str:
        if mode.phase == "warmup":
            return "Warm up"
        if mode.phase == "break":
            return "Rest"
        done, total = mode.words_done, mode.words_total
        return f"Word {min(done + 1, total)} of {total}"

    def _draw_top(self, surf: pygame.Surface, mode) -> None:
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
        draw_text(surf, self._top_label(mode),
                  (pad, 34), self.theme, self.layout, pt=FONT_SMALL,
                  colour=self.theme.muted)
        draw_text(surf, f"Band {mode.band}   Level {mode.rung} of "
                        f"{mode.rung_max}",
                  (self.layout.width // 2, 40), self.theme, self.layout,
                  pt=FONT_SMALL, centre=True, colour=self.theme.muted)
        accent = self._accent()
        pf = self.layout.font(FONT_SMALL + 2)
        pill_label = pf.render("SYLLABLES", True, (255, 255, 255))
        pill_rect = pygame.Rect(0, 0, pill_label.get_width() + 24,
                                pill_label.get_height() + 8)
        pill_rect.topright = (self.layout.width - 28, 30)
        pygame.draw.rect(surf, accent, pill_rect,
                         border_radius=pill_rect.height // 2)
        surf.blit(pill_label,
                  pill_label.get_rect(center=pill_rect.center))
        sf = self.layout.font(FONT_H2, bold=True)
        score_surf = sf.render(f"{self.engine.score}", True, accent)
        lf = self.layout.font(FONT_SMALL)
        score_label = lf.render("SCORE", True, self.theme.muted)
        score_rect = score_surf.get_rect(
            topright=(pill_rect.right, pill_rect.bottom + 10))
        surf.blit(score_surf, score_rect)
        surf.blit(score_label, score_label.get_rect(
            midright=(score_rect.left - 10, score_rect.centery)))

    # ---- warm-up -----------------------------------------------------------
    def _draw_warmup(self, surf: pygame.Surface, mode, now: float) -> None:
        cx = self.layout.width // 2
        cy = (self.TOP_Y + self.EXIT_Y) // 2
        # A circle that swells on each beat, phased off the beat GRID
        # rather than the wall clock, so a child cueing off the circle
        # instead of the metronome does not tap with a constant offset
        # against the very asynchronies this probe measures.
        beats = getattr(mode, "_warmup_beats", None)
        anchor = beats[0] if beats else now
        phase = ((now - anchor) % mode.ioi_s) / mode.ioi_s
        r = 60 + int(26 * math.exp(-4.0 * phase))
        pygame.draw.circle(surf, self._accent(), (cx, cy), r)
        pygame.draw.circle(surf, self.theme.background, (cx, cy),
                           max(6, r - 16))
        done = getattr(mode, "_warmup_done", 0)
        draw_text(surf, f"{min(done, mode.warmup_total)} of "
                        f"{mode.warmup_total} taps",
                  (cx, cy + 120), self.theme, self.layout,
                  pt=FONT_BODY, centre=True, colour=self.theme.muted)

    # ---- break -------------------------------------------------------------
    def stop_name(self, k: int) -> str:
        """Stop `k` (0-based round index) on the session's walk. One
        fiction shell, never rotated: the same walk every session."""
        return JOURNEY_STOPS[k % len(JOURNEY_STOPS)]

    def _draw_break(self, surf: pygame.Surface, mode, now: float) -> None:
        cx = self.layout.width // 2
        left = 0
        if mode._phase_until is not None:
            left = max(0, int(math.ceil(mode._phase_until - now)))
        draw_text(surf, f"Next round in {left}",
                  (cx, self.SUB_Y + 40), self.theme, self.layout,
                  pt=FONT_H2, centre=True, colour=self.theme.muted)
        band = getattr(mode, "band_celebrate", None)
        if band:
            draw_text(surf, "Bigger words next round!",
                      (cx, self.SUB_Y + 76), self.theme, self.layout,
                      pt=FONT_BODY + 2, centre=True,
                      colour=BAND_COLOURS.get(band, self._accent()))
        self._draw_journey(surf, mode, now)
        n = int(getattr(mode, "stickers", 0) or 0)
        if n:
            draw_text(surf,
                      f"Sticker earned! {self.stop_name(n - 1)} stamped.",
                      (cx, self.EXIT_Y - 20), self.theme, self.layout,
                      pt=FONT_BODY + 2, centre=True, colour=self._accent())
        # The adult line. McTigue et al. (2020) found supportive adult
        # interaction to be the only moderator that reliably mattered
        # in this family of games, so the rest screen asks for it.
        draw_text(surf, "Sit with your child and say the syllables "
                        "together.",
                  (cx, self.EXIT_Y + 10), self.theme, self.layout,
                  pt=FONT_BODY, centre=True, colour=self.theme.muted)

    def _draw_journey(self, surf: pygame.Surface, mode,
                      now: float) -> None:
        """The walking strip: one circle per round, joined by a path.
        Finished stops are stamped (accent fill, white star), the next
        stop waits as an outline with its number, and the newest stamp
        lands with a single settle."""
        n_rounds = int(getattr(mode, "n_rounds", 4) or 4)
        stickers = int(getattr(mode, "stickers", 0) or 0)
        flash_t = getattr(mode, "sticker_flash_t", None)
        r = 34
        spacing = (min(170, (self.layout.width - 240) // (n_rounds - 1))
                   if n_rounds > 1 else 0)
        x0 = self.layout.width // 2 - spacing * (n_rounds - 1) // 2
        cy = (self.TOP_Y + self.EXIT_Y) // 2
        if n_rounds > 1:
            pygame.draw.line(surf, self.theme.muted,
                             (x0, cy), (x0 + spacing * (n_rounds - 1),
                                        cy), 3)
        for k in range(n_rounds):
            x = x0 + k * spacing
            if k < stickers:
                rr = float(r)
                if (k == stickers - 1 and flash_t is not None
                        and now - flash_t < self.STAMP_FLASH_S):
                    p = (now - flash_t) / self.STAMP_FLASH_S
                    rr *= 1.0 + 0.8 * (1.0 - p) ** 2
                pygame.draw.circle(surf, self._accent(), (x, cy), int(rr))
                pts = _star_points(x, cy, rr * 0.55, rr * 0.25)
                pygame.draw.polygon(surf, (255, 255, 255), pts)
            else:
                current = k == stickers
                colour = self._accent() if current else self.theme.muted
                pygame.draw.circle(surf, self.theme.background, (x, cy), r)
                pygame.draw.circle(surf, colour, (x, cy), r,
                                   4 if current else 2)
                draw_text(surf, str(k + 1), (x, cy), self.theme,
                          self.layout, pt=FONT_H2, centre=True,
                          colour=colour)
            draw_text(surf, self.stop_name(k), (x, cy + r + 24),
                      self.theme, self.layout, pt=FONT_SMALL,
                      centre=True, colour=self.theme.muted)

    # ---- between words -----------------------------------------------------
    def _draw_gap(self, surf: pygame.Surface, mode, now: float) -> None:
        """The inter-word gap says what is coming, so a child (or a
        parent) never watches a dead screen wondering if the game
        stalled. A band promotion borrows the whole gap for its card."""
        cx = self.layout.width // 2
        cy = (self.TOP_Y + self.EXIT_Y) // 2
        band = getattr(mode, "band_celebrate", None)
        if band:
            self._draw_band_card(surf, mode, band, now)
            return
        nxt = min(mode.words_done + 1, mode.words_total)
        draw_text(surf, f"Here comes word {nxt}...",
                  (cx, cy - 30), self.theme, self.layout,
                  pt=FONT_H1, centre=True, colour=self.theme.muted)
        r = 12 + int(5 * math.sin(now * math.pi))
        pygame.draw.circle(surf, self._accent(), (cx, cy + 60), r)

    def _draw_band_card(self, surf: pygame.Surface, mode, band: str,
                        now: float) -> None:
        """The promotion card: the band gate already moved (and was
        logged); this makes the earned step visible for exactly one
        between-word gap. Demotion never reaches this method."""
        colour = BAND_COLOURS.get(band, self._accent())
        cx = self.layout.width // 2
        cy = (self.TOP_Y + self.EXIT_Y) // 2
        t0 = mode._phase_t0 if mode._phase_t0 is not None else now
        p = min(1.0, max(0.0, (now - t0) / 0.25))
        w = int(560 * (0.85 + 0.15 * p))
        h = int(200 * (0.85 + 0.15 * p))
        card = pygame.Rect(0, 0, w, h)
        card.center = (cx, cy - 10)
        fill = pygame.Surface(card.size, pygame.SRCALPHA)
        pygame.draw.rect(fill, (*self.theme.background, 245),
                         fill.get_rect(), border_radius=24)
        pygame.draw.rect(fill, (*colour, 220), fill.get_rect(), 4,
                         border_radius=24)
        surf.blit(fill, card.topleft)
        draw_text(surf, "BIGGER WORDS!", (cx, card.y + int(h * 0.42)),
                  self.theme, self.layout, pt=FONT_H1 + 8, centre=True,
                  colour=colour)
        draw_text(surf, f"You reached band {band}. Wonderful reading!",
                  (cx, card.y + int(h * 0.72)), self.theme, self.layout,
                  pt=FONT_BODY + 2, centre=True, colour=self.theme.muted)

    # ---- tracked text ------------------------------------------------------
    def _tile_font(self, pt: int) -> pygame.font.Font:
        font = self._tile_fonts.get(pt)
        if font is None:
            font = make_font(pt, bold=True)
            self._tile_fonts[pt] = font
        return font

    def _tracked_width(self, font: pygame.font.Font, text: str,
                       track: int) -> int:
        if not text:
            return 0
        return (sum(font.size(ch)[0] for ch in text)
                + track * (len(text) - 1))

    def _draw_tracked(self, surf: pygame.Surface, text: str,
                      font: pygame.font.Font, colour, centre,
                      alpha: int = 255) -> None:
        """One chunk with wide letter spacing, drawn letter by letter.
        Tracking is the one typographic choice with direct evidence
        behind it for this population (Zorzi et al. 2012), and pygame
        has no tracking control, so the letters are placed by hand."""
        track = max(2, int(font.get_height() * self.TRACKING))
        total = self._tracked_width(font, text, track)
        x = centre[0] - total // 2
        for ch in text:
            glyph = font.render(ch, True, colour)
            if alpha < 255:
                glyph.set_alpha(alpha)
            surf.blit(glyph, glyph.get_rect(
                midleft=(x, centre[1])))
            x += glyph.get_width() + track

    def _fitted_tile_font(self, text: str, max_w: int,
                          pt: int) -> pygame.font.Font:
        """The largest size from `pt` down whose tracked render of
        `text` fits `max_w`. A five-letter chunk shrinks instead of
        spilling out of its tile."""
        while True:
            font = self._tile_font(pt)
            track = max(2, int(font.get_height() * self.TRACKING))
            if pt <= 18 or self._tracked_width(font, text, track) <= max_w:
                return font
            pt -= 4

    # ---- the word strip ----------------------------------------------------
    def slot_rects(self, mode) -> list[pygame.Rect]:
        """One rect per syllable of the word, left to right across the
        top. The strip is the word being built: it says how many parts
        there are, which one is being asked for, and what has already
        been won."""
        n = max(1, mode.n_syll)
        longest = max((len(s) for s in (mode.word.syllables if mode.word
                                        else ("aa",))), default=2)
        w = max(self.SLOT_MIN_W,
                min(self.SLOT_MAX_W, 56 + longest * 34))
        total = w * n + self.SLOT_GAP * (n - 1)
        x = (self.layout.width - total) // 2
        rects = []
        for _ in range(n):
            r = pygame.Rect(x, 0, w, self.STRIP_H)
            r.centery = self.STRIP_Y
            rects.append(r)
            x += w + self.SLOT_GAP
        return rects

    def _draw_word_strip(self, surf: pygame.Surface, mode,
                         now: float) -> None:
        word = mode.word
        if word is None:
            return
        phase = mode.phase
        rects = self.slot_rects(mode)
        model_idx = getattr(mode, "_model_idx", -1)
        if phase == "model":
            if model_idx != self._last_model_idx:
                self._last_model_idx = model_idx
                self._model_lit_t = now
        else:
            self._last_model_idx = -1
        swell = 0.0
        if phase == "complete" and mode._phase_t0 is not None:
            swell = math.sin(min(1.0, (now - mode._phase_t0)
                                 / mode.complete_s) * math.pi)
        for i, rect in enumerate(rects):
            chunk = None
            # A filled slot wears the colour of the FINGER that won
            # it, which is a fact the child can act on. The lit slot
            # during the model has no finger behind it yet, so it
            # wears the mode's own accent instead of borrowing a
            # finger colour that would mean nothing.
            fill = self._accent()
            lit = phase == "model" and model_idx == i
            if lit:
                chunk = word.syllables[i]
                b = min(1.0, (now - self._model_lit_t) / 0.4)
                rect = rect.move(0, -int(10 * math.sin(b * math.pi)))
            elif phase in ("choose", "complete", "attend"):
                filled = getattr(mode, "filled", [])
                lanes = getattr(mode, "filled_lanes", [])
                if i < len(filled):
                    chunk = filled[i]
                if chunk is not None and i < len(lanes) and lanes[i] is not None:
                    fill = self.theme.lane_active[
                        mode._finger_of_lane(lanes[i])]
            if chunk is not None:
                if phase == "complete":
                    grow = int(6 * swell)
                    rect = rect.inflate(grow, grow)
                pygame.draw.rect(surf, fill, rect, border_radius=18)
                font = self._fitted_tile_font(chunk, rect.width - 26,
                                              int(FONT_TITLE * 0.8))
                self._draw_tracked(
                    surf, chunk, font,
                    _text_colour_for(fill, (255, 255, 255),
                                     self.theme.foreground),
                    rect.center)
            else:
                waiting = (phase == "choose" and i == mode.pos)
                width = 4
                r = rect
                if waiting:
                    # The slot being asked for breathes gently. It says
                    # WHICH PART of the word is wanted; it says nothing
                    # about which lane holds it.
                    p = (now * 0.8) % 1.0
                    grow = int(8 * math.sin(p * math.pi))
                    r = rect.inflate(grow, grow)
                    width = 5
                pygame.draw.rect(surf, self.theme.muted if not waiting
                                 else self._accent(), r, width,
                                 border_radius=18)
        if getattr(mode, "bilateral", False):
            self._draw_hand_tag(surf, rects[-1], str(mode.word_hand))

    def _draw_hand_tag(self, surf: pygame.Surface, rect: pygame.Rect,
                       hand: str) -> None:
        label = f"{hand.upper()} HAND"
        pf = self.layout.font(FONT_SMALL + 2)
        text = pf.render(label, True, (255, 255, 255))
        pill = pygame.Rect(0, 0, text.get_width() + 22,
                           text.get_height() + 8)
        pill.midleft = (rect.right + 18, rect.centery)
        pygame.draw.rect(surf, self._accent(), pill,
                         border_radius=pill.height // 2)
        surf.blit(text, text.get_rect(center=pill.center))

    # ---- the lanes and the falling tiles -----------------------------------
    def lane_centres(self, mode) -> list[int]:
        """The x centre of each of the four lanes, in the playing
        hand's desk order (leftmost lane = leftmost finger)."""
        lanes = mode.active_lanes()
        n = max(1, len(lanes))
        usable = self.layout.width - 2 * self.LANE_PAD
        step = usable // n
        return [self.LANE_PAD + step // 2 + i * step for i in range(n)]

    def _draw_lane_guides(self, surf: pygame.Surface, mode) -> None:
        for x in self.lane_centres(mode):
            pygame.draw.line(surf, _mix(self.theme.background,
                                        self.theme.muted, 0.28),
                             (x, self.TOP_Y - self.TILE_H // 2 - 16),
                             (x, self.EXIT_Y + 6), 2)
        pygame.draw.line(surf, _mix(self.theme.background,
                                    self.theme.muted, 0.45),
                         (self.LANE_PAD // 2, self.EXIT_Y + 6),
                         (self.layout.width - self.LANE_PAD // 2,
                          self.EXIT_Y + 6), 2)

    def _draw_seats(self, surf: pygame.Surface, mode) -> None:
        """One coloured dot per playing finger under its lane, and a
        quiet dot for each finger of the resting hand: the child sees
        which four fingers this word wants without a labelled row
        pulling their eyes off the tiles."""
        centres = self.lane_centres(mode)
        for x, lane in zip(centres, mode.active_lanes()):
            finger = mode._finger_of_lane(lane)
            pygame.draw.circle(surf, self.theme.lane_active[finger],
                               (x, self.SEAT_Y), self.SEAT_R)
        if not getattr(mode, "bilateral", False):
            return
        resting = [h for h in mode.hand_names if h != mode.word_hand]
        if not resting:
            return
        lanes = mode.hands.get(resting[0], [])
        x0 = self.layout.width // 2 - (len(lanes) - 1) * 18 // 2
        for i, lane in enumerate(lanes):
            finger = mode._finger_of_lane(lane)
            pygame.draw.circle(surf, self.theme.lane_idle[finger],
                               (x0 + i * 18, self.SEAT_Y + 46), 6)
        draw_text(surf, f"{resting[0]} hand resting",
                  (self.layout.width // 2, self.SEAT_Y + 74),
                  self.theme, self.layout, pt=FONT_SMALL, centre=True,
                  colour=self.theme.muted)

    def tile_layout(self, mode, now: float) -> list[dict]:
        """Where each tile of the current set is and what state it is
        in, as plain data so a test can read the frame without a
        display. One dict per option:
        {option, rect, state, alpha}, state in falling | dead | lifted
        | glow | fading."""
        oset = getattr(mode, "option_set", None)
        spawn = getattr(mode, "_spawn_t", None)
        if oset is None or spawn is None:
            return []
        lanes = mode.active_lanes()
        centres = self.lane_centres(mode)
        by_lane = {lane: x for lane, x in zip(lanes, centres)}
        fall = max(0.1, float(mode.fall_s))
        p = max(0.0, min(1.0, (now - spawn) / fall))
        base_y = self.TOP_Y + p * (self.EXIT_Y - self.TOP_Y)
        lockout = max(0.01, float(mode.spawn_lockout_s))
        fade_in = max(0.0, min(1.0, (now - spawn) / lockout))
        dead = set(getattr(mode, "_dead_lanes", set()) or set())
        correct_t = getattr(mode, "_correct_t", None)
        glow_t = getattr(mode, "_glow_t", None)
        slots = self.slot_rects(mode)
        out: list[dict] = []
        for opt in oset.options:
            x = by_lane.get(opt.lane)
            if x is None:
                continue
            rect = pygame.Rect(0, 0, self.TILE_W, self.TILE_H)
            rect.center = (x, int(base_y))
            state = "falling"
            alpha = int(255 * fade_in)
            if correct_t is not None and opt.lane == oset.target_lane:
                # The winning tile lifts into its slot in the strip.
                lift = max(0.0, min(1.0, (now - correct_t)
                                    / max(0.05, mode.CORRECT_HOLD_S)))
                slot = slots[min(mode.pos, len(slots) - 1)]
                rect.center = (
                    int(x + (slot.centerx - x) * lift),
                    int(rect.centery
                        + (slot.centery - rect.centery) * lift))
                state = "lifted"
            elif correct_t is not None:
                state = "fading"
                alpha = int(255 * max(0.0, 1.0 - (now - correct_t) / 0.3))
            elif opt.lane in dead:
                state = "dead"
                # Grey and drifting out to the nearer side, so the tile
                # visibly leaves rather than blinking out.
                gone = max(0.0, min(1.0, (now - spawn) / fall))
                side = -1 if x < self.layout.width // 2 else 1
                rect.centerx = int(x + side * 160 * gone)
                alpha = int(255 * max(0.15, 1.0 - gone))
            elif glow_t is not None and opt.lane == oset.target_lane:
                state = "glow"
                rect.centery = self.EXIT_Y
            elif glow_t is not None:
                # The set was missed: the foils leave quietly so the
                # only thing left on screen is the answer.
                state = "fading"
                alpha = int(255 * max(0.0, 1.0 - (now - glow_t)
                                      / max(0.05, mode.MISS_GLOW_S)))
            out.append({"option": opt, "rect": rect, "state": state,
                        "alpha": max(0, min(255, alpha))})
        return out

    def _draw_tiles(self, surf: pygame.Surface, mode, now: float) -> None:
        card = self._card()
        border = _mix(self.theme.background, self.theme.muted, 0.55)
        glow_t = getattr(mode, "_glow_t", None)
        for item in self.tile_layout(mode, now):
            rect, state, alpha = item["rect"], item["state"], item["alpha"]
            text = item["option"].text
            if state == "dead":
                fill = _mix(self.theme.background, self.theme.muted, 0.45)
                ink = self.theme.muted
            else:
                fill = card
                ink = self.theme.foreground
            tile = pygame.Surface(rect.size, pygame.SRCALPHA)
            pygame.draw.rect(tile, (*fill, 255), tile.get_rect(),
                             border_radius=20)
            pygame.draw.rect(tile, (*border, 255), tile.get_rect(), 3,
                             border_radius=20)
            if alpha < 255:
                tile.set_alpha(alpha)
            surf.blit(tile, rect.topleft)
            font = self._fitted_tile_font(text, rect.width - 30,
                                          int(FONT_TITLE * 0.75))
            self._draw_tracked(surf, text, font, ink, rect.center,
                               alpha=alpha)
            if state == "glow" and glow_t is not None:
                # The corrective display: one slow swell around the
                # tile that was right, as it leaves. No sound, no red,
                # nothing to read.
                p = max(0.0, min(1.0, (now - glow_t) / mode.MISS_GLOW_S))
                ring = rect.inflate(int(10 + 26 * p), int(10 + 26 * p))
                width = max(2, int(6 * (1.0 - p)))
                pygame.draw.rect(surf, self._accent(), ring, width,
                                 border_radius=26)

    # ---- the word in play --------------------------------------------------
    def _draw_word_trial(self, surf: pygame.Surface, mode,
                         now: float) -> None:
        word = mode.word
        if word is None:
            return
        cx = self.layout.width // 2
        phase = mode.phase
        self._draw_word_strip(surf, mode, now)
        self._draw_header(surf, mode)
        hint = self._hands_line(mode)
        if hint:
            draw_text(surf, hint, (cx, self.SUB_Y + 36), self.theme,
                      self.layout, pt=FONT_BODY, centre=True,
                      colour=self._accent())
        self._draw_seats(surf, mode)
        if phase in ("attend", "model"):
            # The whole word, large, while it is spoken and modelled.
            font = make_font(int(FONT_TITLE * 1.4), bold=True)
            self._draw_tracked(surf, word.word, font,
                               self.theme.foreground,
                               (cx, (self.TOP_Y + self.EXIT_Y) // 2))
            return
        if phase == "complete":
            # The whole word, said and seen together: the payoff for
            # the parts, and the pairing the mode is training.
            font = make_font(int(FONT_TITLE * 1.4), bold=True)
            self._draw_tracked(surf, word.word, font,
                               self.theme.foreground,
                               (cx, (self.TOP_Y + self.EXIT_Y) // 2))
            draw_text(surf, "You built the whole word!",
                      (cx, (self.TOP_Y + self.EXIT_Y) // 2 + 96),
                      self.theme, self.layout, pt=FONT_H2, centre=True,
                      colour=self.theme.success)
            return
        self._draw_lane_guides(surf, mode)
        self._draw_tiles(surf, mode, now)

    # ---- streak stars ------------------------------------------------------
    def _draw_streak_stars(self, surf: pygame.Surface, mode,
                           now: float) -> None:
        """The round's earned streak stars, bottom-left: one, two,
        three at the fixed milestones. Peripheral on purpose, and
        nothing draws when no star is earned."""
        stars = int(getattr(mode, "round_stars", 0) or 0)
        if stars <= 0:
            return
        flash_t = getattr(mode, "star_flash_t", None)
        flashing = (flash_t is not None
                    and now - flash_t < self.STAR_FLASH_S)
        x0 = 52
        cy = self.layout.height - 64
        for k in range(stars):
            r = 16.0
            if flashing and k == stars - 1:
                p = (now - flash_t) / self.STAR_FLASH_S
                r *= 1.0 + 0.7 * math.sin(min(1.0, p) * math.pi)
            pts = _star_points(x0 + k * 46, cy, r, r * 0.45)
            pygame.draw.polygon(surf, STAR_GOLD, pts)
        if flashing:
            milestones = getattr(mode, "STREAK_MILESTONES", (3, 5, 8))
            n = milestones[min(stars, len(milestones)) - 1]
            draw_text(surf, f"{n} words in a row!",
                      (x0 - 16, cy + 28), self.theme, self.layout,
                      pt=FONT_SMALL + 2, colour=STAR_GOLD)

    # ---- corner controls note ----------------------------------------------
    def controls_lines(self, mode) -> list[str]:
        """Keyboard hints for the corner note, one line per playing
        hand, in keyboard reading order. Empty when the input is the
        real sensors: fingers sit on the pads, a legend would only pull
        the child's eyes off the tiles."""
        return keyboard_controls_lines(self.engine, mode)

    def _draw_controls_note(self, surf: pygame.Surface, mode) -> None:
        lines = self.controls_lines(mode)
        if not lines:
            return
        pf = self.layout.font(FONT_SMALL)
        right = self.layout.width - 24
        y = self.layout.height - 22 - 18 * len(lines)
        head = pf.render("Controls", True, self.theme.muted)
        surf.blit(head, head.get_rect(topright=(right, y - 20)))
        for line in lines:
            t = pf.render(line, True, self.theme.muted)
            surf.blit(t, t.get_rect(topright=(right, y)))
            y += 18

    # ---- paused ------------------------------------------------------------
    # _draw_paused_overlay comes from Screen: one card, one resume
    # line, identical on every screen a block runs on.


def _text_colour_for(fill: tuple[int, int, int],
                     light: tuple[int, int, int],
                     dark: tuple[int, int, int]) -> tuple[int, int, int]:
    # Same luminance trick LaneStrip uses so the black ring block still
    # carries readable text.
    return dark if sum(fill) / 3 > 140 else light
