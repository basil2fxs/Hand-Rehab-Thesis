"""Syllable Beats screen. Words and syllable blocks are not a lane
strip, so the mode gets its own screen instead of GameplayScreen.

The screen is built so that a seven year old, or the parent across
the table, always knows two things without reading anything twice:
whose turn it is, and why what just happened happened. Every phase
announces itself with one big stage title and one short instruction:

  WARM UP      tap along with the tick, any finger
  LISTEN...    the word appears huge and is spoken once
  WATCH        the blocks light in turn; hands off is said outright,
               and in bilateral play a tag under the sounding block
               names the hand carrying the buzz, so the buzz hopping
               between hands is explained on screen as it happens
  GET READY... paced levels count DOWN 4 3 2 1 to GO, so the ticks
               the child waits through cannot be mistaken for the
               ticks the child taps on
  YOUR TURN!   the blocks drain to hollow outlines waiting to be
               filled, a big GO! marks the start, and in bilateral
               play a line says either hand counts
  feedback     WONDERFUL! with a green swell on success; a kind SO
               CLOSE! (or HAVE ANOTHER LOOK on no taps) naming the
               one thing to change, then the replay demonstrates it

Between words the screen never goes dead: the gap says the next word
is coming. The model and the response also LOOK different, not just
read different: model blocks are solid and light up, response blocks
are hollow outlines that fill as taps land, so a beat to copy and a
beat already copied cannot be confused.

There is no finger row under the blocks. Keyboard key hints live in
a small Controls note in the bottom corner, only when the input IS
the keyboard; with the real sensors the child's fingers sit on the
pads and a legend would only pull eyes away from the blocks. The
block-to-finger mapping is taught where it matters: by the buzz on
the finger while its block lights, and by the fixed finger colours
the blocks wear everywhere else in the app.

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

from .screens import ModeSelectScreen, Screen
from .widgets import (
    FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL, FONT_TITLE,
    draw_text, keyboard_controls_lines, make_font,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


log = logging.getLogger(__name__)


class SyllablesScreen(Screen):

    # Block row geometry. The row is centred; heights leave room for
    # the stage title above and the GO! / count-down slot below.
    BLOCK_H = 150
    STRESS_EXTRA = 36          # stressed block drawn taller from L4 up
    BLOCK_GAP = 18
    BLOCK_MIN_W = 120
    EXTRA_W = 84               # the grey "you tapped one too many" block
    ROW_CY = 400               # vertical centre of the block row
    TITLE_Y = 168              # stage title ("YOUR TURN!")
    SUB_Y = 222                # one-line instruction under the title
    HINT_Y = 258               # bilateral either-hand line
    UNDER_Y = ROW_CY + 150     # GO! and the count-down number
    # How long the GO! stays up at the start of the response phase
    # when no tap has landed yet. Long enough to read, short enough
    # that it is gone before the first paced beat needs the space.
    GO_S = 0.7

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        # Animation trackers, all read-side: the mode stays the single
        # source of truth and the screen just notices changes.
        # Which block last lit during model/replay, and when, so the
        # sounding block can bounce once per beat.
        self._last_model_idx = -1
        self._model_lit_t = 0.0
        # Tap count last frame, so a landed tap can pop its block.
        self._last_tap_count = 0
        self._tap_pops: list[tuple[int, float]] = []
        # Cached success glow (sized to the block row) so the feedback
        # swell does not allocate a fresh surface per frame.
        self._glow_cache: pygame.Surface | None = None
        self._glow_key: tuple[int, int] | None = None
        # Pre-start countdown, same contract as GameplayScreen: while
        # perf_counter() is below this the GET READY card shows and the
        # mode's update is held back, so the warm-up beat cannot start
        # until the child has had the one 3 s prep every mode gets.
        self._countdown_until = 0.0
        self._dim_cache: pygame.Surface | None = None

    def start_countdown(self, seconds: float) -> None:
        """Begin the pre-start GET READY countdown. Called by the
        engine when the block begins, exactly as on GameplayScreen."""
        self._countdown_until = time.perf_counter() + max(0.0, seconds)

    def _countdown_remaining(self) -> float:
        return max(0.0, self._countdown_until - time.perf_counter())

    def _accent(self) -> tuple[int, int, int]:
        """Syllables pink from the mode picker, so the kids' screen
        keeps the same identity colour it was chosen by."""
        return ModeSelectScreen.MODE_ACCENTS.get(
            "syllables", self.theme.accent)

    def on_block_start(self) -> None:
        # Fresh block: drop every animation tracker so nothing pops on
        # frame one of a new visit.
        self._last_model_idx = -1
        self._last_tap_count = 0
        self._tap_pops.clear()

    # ---- events ------------------------------------------------------------
    def handle_event(self, e: pygame.event.Event) -> None:
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
        # Hold the mode back while the GET READY countdown runs, same
        # as GameplayScreen, so the warm-up's first beat lands the
        # instant the card clears rather than under it.
        if (self.engine.mode and hasattr(self.engine.mode, "update")
                and self._countdown_remaining() <= 0):
            self.engine.mode.update(dt)

    # ---- stage copy --------------------------------------------------------
    # One title, one instruction, one colour per phase. The title is
    # the single focal announcement; a child who reads nothing else
    # still gets whose turn it is from the colour and the size.
    ERROR_SUBS = {
        "extra_tap": "One tap too many. See the grey block.",
        "missing_tap": "One beat is still empty.",
        "wrong_order": "Start from the first finger.",
        "off_beat": "Try to land right on the tick.",
        "wrong_stress": "Press the tall block harder.",
    }

    def _stage(self, mode) -> tuple[str, str, str]:
        """(title, instruction, colour name) for the current phase.
        Colour names resolve through _stage_colour so the copy can be
        unit-tested without a display."""
        phase = mode.phase
        if phase == "warmup":
            return ("WARM UP", "Tap along with the tick. Any finger.",
                    "accent")
        if phase == "attend":
            return ("LISTEN...", "How many beats does it have?", "accent")
        if phase == "model":
            return ("WATCH", "Hands off. See and feel how it taps.",
                    "accent")
        if phase == "replay":
            return ("WATCH AGAIN", "See how it goes. Next word after this.",
                    "warning")
        if phase == "countin":
            return ("GET READY...", "Start tapping on GO. One tap each tick.",
                    "accent")
        if phase == "respond":
            if mode.paced:
                sub = "Tap with the ticks."
            elif mode.order_required:
                sub = "Tap the beats. First finger first."
            else:
                sub = "Tap once for every beat."
            return ("YOUR TURN!", sub, "success")
        if phase == "feedback":
            res = mode._last_result or {}
            if res.get("correct"):
                return ("WONDERFUL!", "", "success")
            err = res.get("error", "")
            if err == "timeout":
                # Nothing landed, so "so close" would be untrue. Kind
                # and plain instead, and the replay follows.
                return ("HAVE ANOTHER LOOK",
                        "No rush. Watch how it goes.", "warning")
            return ("SO CLOSE!",
                    self.ERROR_SUBS.get(err, "Watch once more."), "warning")
        if phase == "break":
            hands = "hands" if getattr(mode, "bilateral", False) else "hand"
            return ("REST TIME",
                    f"Round {mode.words_done // mode.round_size} done! "
                    f"Shake your {hands} out.", "foreground")
        return ("", "", "muted")

    def _either_hand_line(self, mode) -> str:
        """The bilateral promise, said where the child acts on it."""
        if getattr(mode, "bilateral", False) and mode.phase in (
                "countin", "respond"):
            return "Left or right: either hand counts."
        return ""

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
                  pt=FONT_H1 + 12, centre=True,
                  colour=self._stage_colour(colour))
        if sub:
            draw_text(surf, sub, (cx, self.SUB_Y), self.theme, self.layout,
                      pt=FONT_BODY + 2, centre=True,
                      colour=self.theme.muted)
        hint = self._either_hand_line(mode)
        if hint:
            draw_text(surf, hint, (cx, self.HINT_Y), self.theme,
                      self.layout, pt=FONT_BODY, centre=True,
                      colour=self._accent())

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
        self._draw_controls_note(surf, mode)
        remaining = self._countdown_remaining()
        if remaining > 0:
            self._draw_countdown_card(surf, remaining)
        if self.engine.paused:
            self._draw_paused_overlay(surf)

    def _draw_countdown_card(self, surf: pygame.Surface,
                             remaining: float) -> None:
        """GET READY card matching GameplayScreen's, in this mode's
        pink, so the pre-start moment looks the same on every screen."""
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
        """What the top-left counter says. During the warm-up and the
        rest no word is in play, and saying "Word 1 of 50" then would
        be a counter moving for no visible reason."""
        if mode.phase == "warmup":
            return "Warm up"
        if mode.phase == "break":
            return "Rest"
        done, total = mode.words_done, mode.words_total
        return f"Word {min(done + 1, total)} of {total}"

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
        draw_text(surf, self._top_label(mode),
                  (pad, 34), self.theme, self.layout, pt=FONT_SMALL,
                  colour=self.theme.muted)
        draw_text(surf, f"Level {mode.level}   Band {mode.band}",
                  (self.layout.width // 2, 40), self.theme, self.layout,
                  pt=FONT_SMALL, centre=True, colour=self.theme.muted)
        # Mode pill top-right, same spot and styling as every other
        # in-play screen, with the score sitting just left of it. The
        # old free-floating pink number drifted with digit count.
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
        surf.blit(score_surf, score_surf.get_rect(
            midright=(pill_rect.left - 16, pill_rect.centery)))

    # ---- warm-up -----------------------------------------------------------
    def _draw_warmup(self, surf: pygame.Surface, mode, now: float) -> None:
        cx = self.layout.width // 2
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
        left = 0
        if mode._phase_until is not None:
            left = max(0, int(math.ceil(mode._phase_until - now)))
        draw_text(surf, f"Next round in {left}",
                  (cx, self.HINT_Y + 28), self.theme, self.layout,
                  pt=FONT_H2, centre=True, colour=self.theme.muted)
        # Four little blocks bobbing gently in the finger colours, a
        # calm animation rather than anything to respond to.
        for i in range(4):
            bob = int(10 * math.sin(now * 2.0 + i * 0.9))
            rect = pygame.Rect(0, 0, 70, 70)
            rect.center = (cx - 150 + i * 100, self.ROW_CY + bob)
            pygame.draw.rect(surf, self.theme.lane_active[i], rect,
                             border_radius=16)

    # ---- between words -----------------------------------------------------
    def _draw_gap(self, surf: pygame.Surface, mode, now: float) -> None:
        """The inter-trial gap used to be a dead screen: top strip,
        finger row, nothing else, for most of a second. A child (or a
        parent) staring at a blank screen cannot tell if the game
        stalled. Now the gap says what is coming."""
        cx = self.layout.width // 2
        nxt = min(mode.words_done + 1, mode.words_total)
        draw_text(surf, f"Here comes word {nxt}...",
                  (cx, self.ROW_CY - 30), self.theme, self.layout,
                  pt=FONT_H1, centre=True, colour=self.theme.muted)
        # A slow breathing dot, so the screen visibly lives while the
        # word loads. One cycle per second, far under the flash limit.
        r = 12 + int(5 * math.sin(now * math.pi))
        pygame.draw.circle(surf, self._accent(), (cx, self.ROW_CY + 60), r)

    # ---- the word and its blocks -------------------------------------------
    def _draw_word_trial(self, surf: pygame.Surface, mode,
                         now: float) -> None:
        word = mode.word
        if word is None:
            return
        cx = self.layout.width // 2
        phase = mode.phase
        self._draw_header(surf, mode)
        if phase == "attend":
            # The whole word, huge, while it is (possibly) spoken.
            font = make_font(int(FONT_TITLE * 1.6), bold=True)
            t = font.render(word.word, True, self.theme.foreground)
            surf.blit(t, t.get_rect(center=(cx, self.ROW_CY)))
            return
        self._draw_blocks(surf, mode, now)
        if phase == "countin":
            self._draw_countin(surf, mode, now)
        elif phase == "respond":
            self._draw_go(surf, mode, now)

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
        # The response phase draws WAITING blocks as hollow outlines
        # that fill solid as taps land, so "a beat to copy" (solid,
        # lighting up in the model) and "a beat waiting for you" can
        # never be confused. The count-in shows the same hollow row:
        # it belongs to the child's turn, the blocks are already
        # theirs to fill.
        waiting_style = phase in ("respond", "countin")
        # One slow swell over the whole feedback window; a single
        # pulse, not a flash.
        swell = 0.0
        if phase == "feedback" and mode._phase_t0 is not None:
            swell = math.sin(min(1.0, (now - mode._phase_t0)
                                 / mode.FEEDBACK_S) * math.pi)
        # Bounce tracker: note the moment the sounding block changes so
        # it can hop once per beat, like a bouncing-ball singalong.
        model_idx = getattr(mode, "_model_idx", -1)
        if phase in ("model", "replay"):
            if model_idx != self._last_model_idx:
                self._last_model_idx = model_idx
                self._model_lit_t = now
        else:
            self._last_model_idx = -1
        # Tap pops: a landed tap fills its block with a quick grow-and-
        # settle so the fill feels earned, not just recoloured.
        if phase == "respond":
            if n_taps > self._last_tap_count:
                for idx in range(self._last_tap_count, n_taps):
                    if rects:
                        self._tap_pops.append(
                            (min(idx, len(rects) - 1), now))
            self._last_tap_count = n_taps
        elif phase not in ("feedback",):
            self._last_tap_count = 0
        if self._tap_pops:
            self._tap_pops = [(i, t) for (i, t) in self._tap_pops
                              if now - t < 0.28]
        # Success glow: one soft light behind the whole row, riding the
        # same slow swell as the blocks. Cached; alpha set per frame.
        if feedback_ok and rects:
            row_left = rects[0].left
            row_right = rects[-1].right
            glow_w = row_right - row_left + 160
            glow_h = self.BLOCK_H + 170
            key = (glow_w, glow_h)
            if self._glow_cache is None or self._glow_key != key:
                g = pygame.Surface((glow_w, glow_h), pygame.SRCALPHA)
                centre_rect = g.get_rect()
                for inset, alpha in ((0, 22), (30, 30), (60, 38)):
                    pygame.draw.ellipse(
                        g, (*self.theme.success, alpha),
                        centre_rect.inflate(-inset * 2, -inset * 2))
                self._glow_cache = g
                self._glow_key = key
            # set_alpha applies at blit time, so the cached surface can
            # ride the swell with no per-frame copy.
            self._glow_cache.set_alpha(int(255 * swell))
            surf.blit(self._glow_cache,
                      ((row_left + row_right) // 2 - glow_w // 2,
                       self.ROW_CY - glow_h // 2))
        lit_rect: pygame.Rect | None = None
        for i, (u, rect) in enumerate(zip(units, rects)):
            finger = i % 4
            lit = (phase in ("model", "replay")
                   and getattr(mode, "_model_idx", -1) == i)
            # The sounding block hops: up and back down over 0.4 s,
            # one arc per beat, no repeat until the next block lights.
            if lit and self._model_lit_t > 0:
                b_frac = min(1.0, (now - self._model_lit_t) / 0.4)
                rect = rect.move(0, -int(16 * math.sin(b_frac * math.pi)))
            if lit:
                lit_rect = rect
            # A fresh tap pops its block outward for a beat.
            for pi, pt0 in self._tap_pops:
                if pi == i:
                    p_frac = min(1.0, (now - pt0) / 0.28)
                    grow = int(14 * math.sin(p_frac * math.pi))
                    rect = rect.inflate(grow, grow)
                    break
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
            elif waiting_style and not filled:
                # Waiting to be tapped: an empty outline in the
                # finger's colour. The next paced beat pulses its
                # outline so the child sees which block is due when.
                width = 4
                r = rect
                if (phase == "respond" and mode.paced
                        and i == n_taps and mode._beat_times):
                    ph = ((now - mode._respond_t0) % mode.ioi_s
                          ) / mode.ioi_s if mode._respond_t0 else 0.0
                    r = rect.inflate(int(10 * math.exp(-3.0 * ph)),
                                     int(10 * math.exp(-3.0 * ph)))
                    width = 6
                pygame.draw.rect(surf, self.theme.lane_active[finger],
                                 r, width, border_radius=22)
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
                dot = (self.theme.lane_active[finger]
                       if fill == self.theme.background
                       else _text_colour_for(fill, (255, 255, 255),
                                             self.theme.foreground))
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
        # In bilateral play, name the hand carrying the buzz under the
        # sounding block, as it sounds: the buzz hops between hands on
        # purpose (both hands get modelled equally) and the hop should
        # be explained on screen the moment it happens.
        if (lit_rect is not None and getattr(mode, "bilateral", False)
                and getattr(mode, "model_hand", None)):
            self._draw_hand_tag(surf, lit_rect, mode.model_hand)
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

    def _draw_hand_tag(self, surf: pygame.Surface, rect: pygame.Rect,
                       hand: str) -> None:
        label = f"{hand.upper()} HAND"
        pf = self.layout.font(FONT_SMALL + 2)
        text = pf.render(label, True, (255, 255, 255))
        pill = pygame.Rect(0, 0, text.get_width() + 22,
                           text.get_height() + 8)
        pill.center = (rect.centerx, rect.bottom + 34)
        pygame.draw.rect(surf, self._accent(), pill,
                         border_radius=pill.height // 2)
        surf.blit(text, text.get_rect(center=pill.center))

    # ---- count-down and GO -------------------------------------------------
    def countin_remaining(self, mode, now: float) -> int:
        """Ticks left before the child's first beat, counting DOWN.
        The old display counted up 1 2 3 4 with no endpoint on
        screen, so a waiting tick was indistinguishable from a
        tapping tick until too late."""
        if mode._phase_t0 is None or mode.count_in_beats <= 0:
            return 0
        elapsed = int((now - mode._phase_t0) / mode.ioi_s)
        return max(1, min(mode.count_in_beats,
                          mode.count_in_beats - elapsed))

    def _draw_countin(self, surf: pygame.Surface, mode,
                      now: float) -> None:
        left = self.countin_remaining(mode, now)
        if left <= 0:
            return
        draw_text(surf, str(left),
                  (self.layout.width // 2, self.UNDER_Y),
                  self.theme, self.layout, pt=FONT_TITLE + 10,
                  centre=True, colour=self._accent())

    def _draw_go(self, surf: pygame.Surface, mode, now: float) -> None:
        """A big green GO! the instant the response phase opens, gone
        as soon as the first tap lands. The count-down promises GO,
        so GO must actually appear, or the child is left waiting for
        a starting gun that never fires."""
        if mode.taps or mode._respond_t0 is None:
            return
        if now - mode._respond_t0 > self.GO_S:
            return
        draw_text(surf, "GO!",
                  (self.layout.width // 2, self.UNDER_Y),
                  self.theme, self.layout, pt=FONT_TITLE + 10,
                  centre=True, colour=self.theme.success)

    # ---- corner controls note ----------------------------------------------
    def controls_lines(self, mode) -> list[str]:
        """Keyboard hints for the corner note, one line per playing
        hand, in keyboard reading order. Empty when the input is the
        real sensors: fingers sit on the pads, a legend would only
        pull the child's eyes off the blocks.

        Delegates to the shared widgets.keyboard_controls_lines so
        every gameplay screen renders the same convention (audit
        finding #110)."""
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


def _text_colour_for(fill: tuple[int, int, int],
                     light: tuple[int, int, int],
                     dark: tuple[int, int, int]) -> tuple[int, int, int]:
    # Same luminance trick LaneStrip uses so the black ring block still
    # carries readable text.
    return dark if sum(fill) / 3 > 140 else light
