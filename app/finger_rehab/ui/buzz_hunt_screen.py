"""Buzz Hunt screen. Near-empty ON PURPOSE: the stimulus lives in the
hand, so the eyes must have nothing to learn from. Tactile-first
design, stated plainly: during a trial the screen shows a calm focus
point and nothing else, no lane tiles, no finger names, no meter that
could leak which finger buzzed or when. Response feedback appears
only AFTER the press (or after the window closes), on the feedback
card, which is the SENSe feedback principle without ever becoming a
visual cue.

Layout jobs, in the order a player meets them:

  STAGE CARD      what the coming stage asks, in plain words, with
                  the hands-flat reminder. Shown once per stage.
  GET READY       the shared countdown card (engine prep path).
  TRIAL           the focus point only: a soft dot that breathes at
                  0.15 Hz, far below the 3 Hz flash limit. The wait,
                  the buzz and the response window all look identical
                  by design; even the response window has no visual
                  onset, because a visible "now answer" flash would
                  time-lock responses to the screen instead of the
                  buzz.
  FEEDBACK        only now do words appear: what happened, which
                  finger buzzed and which was pressed (localisation),
                  the replayed pattern (span), one-or-two (gap).
                  Steady text, no flashing.
  RESULTS         the shared results screen reads block_stats.

All alpha scratch surfaces are created once and reused; steady-state
frames allocate no new surfaces. Screen conventions match the rest of
the app: 1280x800 logical layout, theme-aware, Esc and P handled by
the engine's global event path, paused overlay mirroring
GameplayScreen's.
"""
from __future__ import annotations

import logging
import math
import time
from typing import TYPE_CHECKING

import pygame

from ..game.modes.force_pilot import FINGER_WORDS
from . import feedback_bank
from .screens import ModeSelectScreen, Screen, draw_skip_chip
from .widgets import (
    FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL, FONT_TITLE,
    draw_text, make_font,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


log = logging.getLogger(__name__)


STAGE_LINES = {
    "loc": ("One finger will buzz. Press that finger.",
            "Hands flat on the pads. Eyes on the dot. "
            "Sometimes nothing buzzes: then the right move is to wait."),
    "distractor": ("Two buzzes: a decoy, then the real one.",
                   "The decoy lands on the other hand first. "
                   "Press where the LAST buzz was."),
    "span": ("Feel the pattern, then replay it.",
             "The pads play a sequence of buzzes. When it ends, "
             "press the same fingers in the same order."),
    "gap": ("One buzz or two?",
            "Tap the finger that buzzed: once for one buzz, "
            "twice if you felt two."),
}


class BuzzHuntScreen(Screen):

    # Focus point geometry, logical pixels on the 1280x800 surface.
    DOT_CX = 640
    DOT_CY = 400
    DOT_R = 10
    # Breathing halo: radius sways at 0.15 Hz between these bounds,
    # a slow tide rather than anything that could read as a cue.
    HALO_MIN = 26
    HALO_MAX = 40
    BREATHE_HZ = 0.15
    HALO_SIZE = 120

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self._countdown_until = 0.0
        self._dim_cache: pygame.Surface | None = None
        self._halo_scratch: pygame.Surface | None = None

    # ---- shared furniture --------------------------------------------------
    def start_countdown(self, seconds: float) -> None:
        """Pre-start GET READY card, same contract as GameplayScreen."""
        self._countdown_until = time.perf_counter() + max(0.0, seconds)

    def _countdown_remaining(self) -> float:
        return max(0.0, self._countdown_until - time.perf_counter())

    def _accent(self) -> tuple[int, int, int]:
        return ModeSelectScreen.MODE_ACCENTS.get(
            "buzz_hunt", self.theme.accent)

    def on_block_start(self) -> None:
        self._halo_scratch = None

    def _new_surface(self, size: tuple[int, int],
                     flags: int = 0) -> pygame.Surface:
        """Every Surface this screen creates comes through here, so a
        test can pin that steady-state frames allocate none."""
        return pygame.Surface(size, flags)

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

    # ---- helpers -----------------------------------------------------------
    def _finger_colour(self, lane: int) -> tuple[int, int, int]:
        pal = self.theme.lane_active
        return pal[(lane % 4) % len(pal)]

    def _lane_words(self, lane: int) -> str:
        mode = self.engine.mode
        hand = "right"
        if mode is not None:
            for h, lanes in getattr(mode, "hands", {}).items():
                if lane in lanes:
                    hand = h
                    break
        return f"{hand.upper()} {FINGER_WORDS[lane % 4]}"

    def _draw_lane_chip(self, surf: pygame.Surface, lane: int,
                        cx: int, cy: int) -> None:
        colour = self._finger_colour(lane)
        pf = self.layout.font(FONT_BODY, bold=True)
        text = pf.render(self._lane_words(lane), True,
                         _text_colour_for(colour))
        pill = pygame.Rect(0, 0, text.get_width() + 34,
                           text.get_height() + 14)
        pill.center = (cx, cy)
        pygame.draw.rect(surf, colour, pill,
                         border_radius=pill.height // 2)
        surf.blit(text, text.get_rect(center=pill.center))

    # ---- draw --------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        mode = self.engine.mode
        if mode is None or getattr(mode, "name", "") != "Buzz Hunt":
            draw_text(surf, "Starting...",
                      (self.layout.width // 2, self.layout.height // 2),
                      self.theme, self.layout, pt=FONT_H1, centre=True,
                      colour=self.theme.muted)
            return
        now = time.perf_counter()
        phase = mode.phase
        if phase == "no_input":
            self._draw_top(surf, mode)
            self._draw_no_input(surf)
        elif phase == "stage":
            self._draw_top(surf, mode)
            self._draw_stage_card(surf, mode)
        elif phase == "announce":
            self._draw_top(surf, mode)
            self._draw_announce(surf, mode, now)
        elif phase == "trial":
            # The near-empty promise still holds around the dot: the
            # centre of the screen carries the focus point and nothing
            # else, and nothing drawn here reflects the stimulus or
            # the response.
            #
            # What DID change: a bare dot on an otherwise empty field
            # left the patient no way to tell a running trial from a
            # frozen app, no sense of how far through the block they
            # were, and no reminder of what this stage asks (the
            # instruction had scrolled by on the announce card a
            # second earlier). All three now sit at the edges, out of
            # the fixation zone, and every one of them is constant for
            # the whole trial: the counter and the bar only step
            # between trials, and the foot line is the stage's own
            # sentence, already read on the announce card, so it
            # reveals nothing the patient was not just told.
            self._draw_top(surf, mode)
            self._draw_focus_point(surf, now)
            self._draw_trial_prompt(surf, mode)
            self._draw_status_line(surf, mode)
        elif phase == "feedback":
            self._draw_top(surf, mode)
            self._draw_feedback(surf, mode, now)
            self._draw_status_line(surf, mode)
        else:
            self._draw_top(surf, mode)
        remaining = self._countdown_remaining()
        if remaining > 0:
            self._draw_countdown_card(surf, remaining)
        # One skip control for every enforced wait, drawn last so it
        # sits over the countdown card and the rest material alike.
        draw_skip_chip(surf, self.layout, self.theme, self.engine)
        # Skipped under either exit guard (the engine draws the
        # session dialog or the end-game chip above this screen),
        # matching GameplayScreen.
        if self.engine.paused and not self.engine.exit_overlay_active:
            self._draw_paused_overlay(surf)

    # ---- top strip (never drawn during a trial) ----------------------------
    def _draw_top(self, surf: pygame.Surface, mode) -> None:
        done, total = mode.trials_done, mode.total_trials
        pad, bar_y, bar_h = 30, 14, 6
        bar_w = self.layout.width - pad * 2
        track = pygame.Rect(pad, bar_y, bar_w, bar_h)
        base = tuple(max(0, c - 26) for c in self.theme.background)
        pygame.draw.rect(surf, base, track, border_radius=bar_h // 2)
        frac = max(0.0, min(1.0, done / total)) if total else 0.0
        fill_w = int(bar_w * frac)
        if fill_w > 0:
            pygame.draw.rect(surf, self._accent(),
                             pygame.Rect(pad, bar_y, fill_w, bar_h),
                             border_radius=bar_h // 2)
        draw_text(surf, f"Trial {min(done + 1, total)} of {total}",
                  (pad, 34), self.theme, self.layout,
                  pt=FONT_SMALL, colour=self.theme.muted)
        title = mode.STAGE_TITLES.get(mode.stage, "")
        draw_text(surf, title, (self.layout.width // 2, 40),
                  self.theme, self.layout, pt=FONT_SMALL, centre=True,
                  colour=self.theme.muted)
        accent = self._accent()
        pf = self.layout.font(FONT_SMALL + 2)
        pill_label = pf.render("BUZZ HUNT", True, (255, 255, 255))
        pill_rect = pygame.Rect(0, 0, pill_label.get_width() + 24,
                                pill_label.get_height() + 8)
        pill_rect.topright = (self.layout.width - 28, 30)
        pygame.draw.rect(surf, accent, pill_rect,
                         border_radius=pill_rect.height // 2)
        surf.blit(pill_label,
                  pill_label.get_rect(center=pill_rect.center))
        # Score under the pill, with the word that names it. Sitting
        # beside the pill it was a bare number 16 px off a filled pill
        # in the same accent, so the two read as one crowded object
        # and nothing on screen said what the number counted. The lane
        # modes have always carried a SCORE label; these four now
        # match, and the band under the pill is empty on all of them.
        sf = self.layout.font(FONT_H2, bold=True)
        score_surf = sf.render(f"{self.engine.score}", True, accent)
        lf = self.layout.font(FONT_SMALL)
        score_label = lf.render("SCORE", True, self.theme.muted)
        score_rect = score_surf.get_rect(
            topright=(pill_rect.right, pill_rect.bottom + 10))
        surf.blit(score_surf, score_rect)
        surf.blit(score_label, score_label.get_rect(
            midright=(score_rect.left - 10, score_rect.centery)))

    # ---- no input ----------------------------------------------------------
    def _draw_no_input(self, surf: pygame.Surface) -> None:
        cx = self.layout.width // 2
        draw_text(surf, "BUZZ HUNT NEEDS THE BUZZERS",
                  (cx, 300), self.theme, self.layout, pt=FONT_H1,
                  centre=True, colour=self.theme.warning)
        draw_text(surf,
                  "The buzz IS the game, and a keyboard cannot buzz "
                  "a finger.",
                  (cx, 370), self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)
        draw_text(surf,
                  "Connect the sensor device, then start the block "
                  "again. Esc leaves.",
                  (cx, 404), self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)

    # ---- stage card --------------------------------------------------------
    def _draw_stage_card(self, surf: pygame.Surface, mode) -> None:
        cx = self.layout.width // 2
        stage = mode.stage_shown or mode.stage
        title = mode.STAGE_TITLES.get(stage, stage.upper())
        head, body = STAGE_LINES.get(stage, ("", ""))
        font = make_font(int(FONT_TITLE * 1.2), bold=True)
        t = font.render(title, True, self._accent())
        surf.blit(t, t.get_rect(center=(cx, 250)))
        draw_text(surf, head, (cx, 350), self.theme, self.layout,
                  pt=FONT_H2, centre=True, colour=self.theme.foreground)
        draw_text(surf, body, (cx, 400), self.theme, self.layout,
                  pt=FONT_BODY, centre=True, colour=self.theme.muted)
        draw_text(surf, "Hands flat. Eyes on the dot. Feel, then press.",
                  (cx, 470), self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)

    # ---- announce ----------------------------------------------------------
    def _stage_prompt(self, mode) -> str:
        """The one sentence this stage asks for. Shared by the
        announce card and the trial's foot line so the patient reads
        the same wording in both places, and so neither can drift into
        naming a finger or a hand (a screen test pins that for the
        trial frames)."""
        return {
            "loc": "Press the finger that buzzes. Nothing? Wait.",
            "distractor": "Ignore the first buzz. Press where the "
                          "last one was.",
            "span": f"A pattern of {mode.span_len} buzzes is coming.",
            "gap": "Tap once for one buzz, twice for two.",
        }.get(mode.stage, "")

    def _draw_trial_prompt(self, surf: pygame.Surface, mode) -> None:
        """The stage's sentence, quiet, at the foot of the screen.

        Placed 320 px below the focus point so it sits outside the
        fixation zone, and drawn in the muted tone at small size so it
        can be read on purpose without pulling the eye off the dot."""
        line = self._stage_prompt(mode)
        if not line:
            return
        draw_text(surf, line,
                  (self.layout.width // 2, self.layout.height - 64),
                  self.theme, self.layout, pt=FONT_BODY, centre=True,
                  colour=self.theme.muted)

    def _draw_status_line(self, surf: pygame.Surface, mode) -> None:
        """What the block is waiting for, and how often it has had to
        stop waiting.

        A quiet gate that keeps resetting (a finger resting on a pad,
        a fidgeting hand) used to show nothing at all: no banner, no
        skip chip, and a score frozen at whatever it was. The
        therapist had no way to tell a running block from a dead one.
        The gate's own instruction goes above the stage sentence, and
        the count of trials the wall had to force sits in the corner.

        Neither line ever hints that a buzz is coming. The foreperiod
        is part of the stimulus, so a countdown or a "get ready" here
        would hand over the onset the jitter exists to hide: the gate
        line only shows while the gate is CLOSED, and the counter only
        changes after a trial has already been forced."""
        msg = getattr(mode, "stage_msg", "")
        if msg:
            draw_text(surf, str(msg),
                      (self.layout.width // 2, self.layout.height - 104),
                      self.theme, self.layout, pt=FONT_BODY, centre=True,
                      colour=self.theme.warning)
        forced = int(getattr(mode, "forced_starts", 0) or 0)
        if forced:
            draw_text(surf, f"Forced starts: {forced}",
                      (30, self.layout.height - 40), self.theme,
                      self.layout, pt=FONT_SMALL,
                      colour=self.theme.muted)

    def _draw_announce(self, surf: pygame.Surface, mode,
                       now: float) -> None:
        cx = self.layout.width // 2
        draw_text(surf, "Get ready...", (cx, 300), self.theme,
                  self.layout, pt=FONT_H2, centre=True,
                  colour=self.theme.foreground)
        draw_text(surf, self._stage_prompt(mode), (cx, 350), self.theme,
                  self.layout, pt=FONT_BODY, centre=True,
                  colour=self.theme.muted)
        self._draw_focus_point(surf, now, dim=True)

    # ---- the focus point ---------------------------------------------------
    def _ensure_halo(self) -> pygame.Surface:
        if self._halo_scratch is None:
            self._halo_scratch = self._new_surface(
                (self.HALO_SIZE, self.HALO_SIZE), pygame.SRCALPHA)
        return self._halo_scratch

    def _draw_focus_point(self, surf: pygame.Surface, now: float,
                          dim: bool = False) -> None:
        """The calm centre. The halo breathes at 0.15 Hz (a 6.7 s
        cycle), nothing else moves, and nothing here ever reflects
        the stimulus or the response state."""
        accent = self._accent()
        breathe = 0.5 + 0.5 * math.sin(
            now * 2.0 * math.pi * self.BREATHE_HZ)
        r = int(self.HALO_MIN + breathe * (self.HALO_MAX - self.HALO_MIN))
        halo = self._ensure_halo()
        halo.fill((0, 0, 0, 0))
        hc = self.HALO_SIZE // 2
        alpha = 26 if not dim else 14
        for radius, a in ((r, alpha), (int(r * 0.7), alpha + 14)):
            pygame.draw.circle(halo, (*accent, a), (hc, hc),
                               max(4, radius))
        surf.blit(halo, (self.DOT_CX - hc, self.DOT_CY - hc))
        dot_colour = accent if not dim else self.theme.muted
        pygame.draw.circle(surf, dot_colour,
                           (self.DOT_CX, self.DOT_CY), self.DOT_R)

    # ---- feedback ----------------------------------------------------------
    def _title_for(self, res: dict, situation: str) -> str:
        """A title from the phrase bank, drawn ONCE per feedback phase.

        This screen redraws every frame, so a fresh random draw here
        would make the words flicker sixty times a second. The picked
        line is cached against the phase's own end time, which changes
        exactly when the feedback card changes.
        """
        mode = self.engine.mode
        stage = str(res.get("stage", ""))
        key = (situation, stage, getattr(mode, "_phase_until", None),
               res.get("lane"), res.get("taps"))
        if getattr(self, "_title_key", None) == key:
            return self._title_cache
        if situation == "wrong" and stage == "gap":
            asked = "TWO BUZZES" if res.get("two") else "ONE BUZZ"
            text = self._phrase("wrong_count", ASKED=asked)
        elif situation == "wrong":
            text = self._phrase(
                "wrong",
                TARGET=FINGER_WORDS[int(res.get("lane", 0)) % 4])
        else:
            text = self._phrase(situation)
        self._title_key = key
        self._title_cache = text
        return text

    def _phrase(self, situation: str, **slots) -> str:
        return feedback_bank.phrase_via(
            self.engine, situation, "line", "buzz_hunt", **slots)

    def _draw_feedback(self, surf: pygame.Surface, mode,
                       now: float) -> None:
        cx = self.layout.width // 2
        res = mode._last_result or {}
        stage = res.get("stage", mode.stage)
        correct = bool(res.get("correct"))
        label = str(res.get("label", ""))
        if label == "CatchOk":
            title, colour = "GOOD WAITING", self.theme.success
        elif label == "FalseAlarm":
            title, colour = "NOTHING BUZZED THAT TIME", self.theme.muted
        elif correct:
            title, colour = {
                "loc": "FOUND IT!",
                "distractor": "DECOY IGNORED!",
                "span": "PATTERN REPLAYED!",
                "gap": "RIGHT CALL!",
            }.get(stage, "CORRECT!"), self.theme.success
        elif not res.get("responded", True) and stage != "span":
            title = self._title_for(res, "no_response")
            colour = self.theme.muted
        else:
            # Never a "that was the wrong one" label. The title says
            # where the buzz actually was, which is the same
            # information said forwards, and the chips below still
            # show the two lanes side by side.
            title = self._title_for(res, "wrong")
            colour = self.theme.muted
        draw_text(surf, title, (cx, 170), self.theme, self.layout,
                  pt=FONT_H1 + 6, centre=True, colour=colour)
        y = 250
        if stage in ("loc", "distractor") and not res.get("catch"):
            draw_text(surf, "The buzz was on", (cx - 160, y),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.muted)
            self._draw_lane_chip(surf, int(res.get("lane", 0)),
                                 cx - 160, y + 40)
            press = res.get("press_lane")
            draw_text(surf, "You pressed", (cx + 160, y),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.muted)
            if press is None:
                draw_text(surf, "no press", (cx + 160, y + 40),
                          self.theme, self.layout, pt=FONT_H2,
                          centre=True, colour=self.theme.muted)
            else:
                self._draw_lane_chip(surf, int(press), cx + 160, y + 40)
            y += 100
            rt = res.get("rt_ms")
            if correct and rt is not None:
                draw_text(surf, f"{rt:.0f} ms", (cx, y), self.theme,
                          self.layout, pt=FONT_H2, centre=True,
                          colour=self.theme.foreground)
                y += 46
        elif stage == "span":
            played = res.get("played") or []
            pressed = res.get("pressed") or []
            draw_text(surf, f"Pattern of {len(played)}:", (cx, y),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.muted)
            y += 44
            self._draw_lane_row(surf, played, cx, y)
            y += 52
            draw_text(surf, "You replayed:", (cx, y), self.theme,
                      self.layout, pt=FONT_BODY, centre=True,
                      colour=self.theme.muted)
            y += 44
            if pressed:
                self._draw_lane_row(surf, pressed, cx, y)
            else:
                draw_text(surf, "no presses", (cx, y), self.theme,
                          self.layout, pt=FONT_H2, centre=True,
                          colour=self.theme.muted)
            y += 60
        elif stage == "gap":
            asked = "two buzzes" if res.get("two") else "one buzz"
            taps = int(res.get("taps", 0))
            said = ("no answer" if taps == 0
                    else "one buzz" if taps == 1 else "two buzzes")
            draw_text(surf, f"It was {asked}. You tapped: {said}.",
                      (cx, y + 20), self.theme, self.layout,
                      pt=FONT_H2, centre=True,
                      colour=self.theme.foreground)
            y += 90
        elif res.get("catch"):
            line = ("Waiting was exactly right."
                    if label == "CatchOk" else
                    "When nothing buzzes, the right move is to wait.")
            draw_text(surf, line, (cx, y + 20), self.theme, self.layout,
                      pt=FONT_H2, centre=True,
                      colour=self.theme.foreground)
            y += 90
        if mode._phase_until is not None:
            left = max(0.0, mode._phase_until - now)
            self.draw_next_countdown(
                surf, f"Next trial in {left:.0f}s", y)

    def _draw_lane_row(self, surf: pygame.Surface, lanes: list[int],
                       cx: int, cy: int) -> None:
        """A row of small finger chips for span feedback. Capped so a
        long sequence stays inside the frame."""
        shown = list(lanes)[:8]
        n = len(shown)
        if n == 0:
            return
        gap = 10
        pf = self.layout.font(FONT_SMALL, bold=True)
        widths = []
        for lane in shown:
            text = pf.render(self._lane_words(lane), True, (0, 0, 0))
            widths.append(text.get_width() + 22)
        total = sum(widths) + gap * (n - 1)
        x = cx - total // 2
        for lane, w in zip(shown, widths):
            colour = self._finger_colour(lane)
            text = pf.render(self._lane_words(lane), True,
                             _text_colour_for(colour))
            pill = pygame.Rect(x, cy - 14, w, 28)
            pygame.draw.rect(surf, colour, pill, border_radius=14)
            surf.blit(text, text.get_rect(center=pill.center))
            x += w + gap

    # ---- countdown card and pause ------------------------------------------
    def _draw_countdown_card(self, surf: pygame.Surface,
                             remaining: float) -> None:
        if (self._dim_cache is None
                or self._dim_cache.get_size() != surf.get_size()):
            self._dim_cache = self._new_surface(surf.get_size(),
                                               pygame.SRCALPHA)
            self._dim_cache.fill((0, 0, 0, 60))
        surf.blit(self._dim_cache, (0, 0))
        accent = self._accent()
        card_rect = pygame.Rect(0, 0, 420, 240)
        card_rect.center = (self.layout.width // 2,
                            self.layout.height // 2)
        fill_surf = self._new_surface(card_rect.size, pygame.SRCALPHA)
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

    # _draw_paused_overlay comes from Screen: one card, one resume
    # line, identical on every screen a block runs on.


def _text_colour_for(fill: tuple[int, int, int]) -> tuple[int, int, int]:
    # Same luminance rule the lane tiles use, so chip text stays
    # readable on any finger colour.
    return (15, 23, 42) if sum(fill) / 3 > 140 else (255, 255, 255)
