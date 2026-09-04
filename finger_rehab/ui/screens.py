"""Screen classes. Title, mode select, setup, gameplay, rhythm, results.

I keep the same Screen base + subclass pattern Satoru used, but the
layouts are heavier on the fonts and use the Card / Button widgets so it
feels like a finished app instead of a debug dashboard.
"""
from __future__ import annotations

import logging
import math
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pygame


log = logging.getLogger(__name__)

from .theme import Theme
from .widgets import (
    Button, Card, FloatingText, LaneStrip, Layout, Segmented, Slider,
    TextInput, ToggleMenu,
    FONT_TITLE, FONT_H1, FONT_H2, FONT_BODY, FONT_SMALL,
    BUTTON_H, BUTTON_W, PADDING, draw_text, keyboard_controls_lines,
    make_font,
)

from ..game.battery import HARDWARE_MODES

if TYPE_CHECKING:
    from ..game.engine import GameEngine



# The Sensory Cues switches, in the order the patient meets them: the
# things that happen before the press, then the ones after a correct
# one. Each entry is (config key, row label, what the patient
# experiences); the help text lands in the status line on hover.
#
# Module level because two screens show this menu. Settings has it for
# setting up, and the results screen has it so the cue condition can be
# changed between two blocks without walking back through the menus,
# which is exactly when a researcher wants to change it.
CUE_ROWS: tuple[tuple[str | None, str, str], ...] = (
        (None, "Before the press", ""),
        ("cue.buzz_before", "Cue Buzzer before press",
         "The motor under the target finger buzzes when the trial "
         "starts, so the finger to press can be felt."),
        ("cue.sound_before", "Cue Sound before press",
         "A tone plays when the trial starts, in every mode including "
         "rhythm, so the go signal can be heard."),
        ("cue.show_target", "Show on screen before press",
         "Off leaves the tile neutral so the finger has to be found "
         "from the buzzer alone. This is the tactile-only condition."),
        (None, "After a correct press", ""),
        ("cue.buzz_after", "Cue Buzzer after press",
         "The finger that was just pressed correctly buzzes back. "
         "Nothing when no press lands, or when another finger goes."),
        ("cue.sound_after", "Cue Sound after press",
         "A chime confirms a correct press. Off also silences the "
         "thunk when a streak ends, so nothing sounds after a press."),
        # Note row, not a switch: in Buzz Hunt the buzz IS the
        # stimulus, so its pulses ignore the before-press switches by
        # design (the after-press switches still apply there).
        (None, "Buzz Hunt stimuli skip Before cues", ""),
)


def apply_cue_setting(engine, key: str, value: bool) -> None:
    """Write one cue switch to the live config and to disk.

    In memory first so it applies to the next block without a restart,
    then persisted to the same user_settings.yaml the ports use. A
    failed save leaves the in-memory value alone: the therapist asked
    for it, so the session should honour it even if the file could not
    be written.
    """
    section, _, leaf = key.partition(".")
    engine.cfg.data.setdefault(section, {})[leaf] = bool(value)
    if leaf == "buzz_before" and not value:
        # Drop anything already queued so nothing buzzes after the
        # switch goes off.
        try:
            engine.stop_all_motors()
        except Exception:
            pass
    try:
        engine.cfg.save_user_overrides({key: bool(value)})
    except Exception as e:
        log.warning("Could not persist %s: %s", key, e)


class Screen:
    def __init__(self, engine: "GameEngine") -> None:
        self.engine = engine
        self.theme: Theme = engine.theme
        self.layout: Layout = engine.layout

    def handle_event(self, e: pygame.event.Event) -> None: ...
    def update(self, dt: float) -> None: ...
    def draw(self, surf: pygame.Surface) -> None: ...

    # How far below the last line of content the "next thing in Ns"
    # line sits, and how close to the bottom edge it may be pushed.
    NEXT_LINE_GAP = 56
    NEXT_LINE_FLOOR = 60

    def draw_next_countdown(self, surf: pygame.Surface, text: str,
                            after_y: int) -> None:
        """The between-trials countdown, placed under the content.

        Force Pilot and Buzz Hunt each pinned this line to
        height - 60 whatever their result block ended at, so a short
        result (a caught trial, a two-row hold) left 300 to 400 px of
        blank page between the last number and the countdown, and the
        two read as unrelated. Anchoring it to the content keeps the
        card whole; the floor keeps a long result from pushing it off
        the bottom.
        """
        y = min(after_y + self.NEXT_LINE_GAP,
                self.layout.height - self.NEXT_LINE_FLOOR)
        draw_text(surf, text, (self.layout.width // 2, y),
                  self.theme, self.layout, pt=FONT_BODY, centre=True,
                  colour=self.theme.muted)

    # Size of the paused card, logical pixels. Tall enough for the
    # word at FONT_TITLE plus the resume line under it with real air
    # between them, so neither rides the border.
    PAUSED_CARD = (480, 158)

    def _draw_paused_overlay(self, surf: pygame.Surface) -> None:
        """The one paused overlay, for every screen a block runs on.

        Two things were wrong with the five hand-written copies this
        replaces. They painted the bare word at the screen's centre
        with nothing behind it, so on the max-press probe screen
        (Force Pilot) it landed straight across the live
        "RIGHT INDEX" chip and the presses-to-go dots. And none of
        them said how to get going again, which on a clinic machine
        with no keyboard legend is a dead end: the therapist can see
        the game has stopped and not that P restarts it. A card gives
        the word its own ground whatever is underneath, and the line
        under it names the key.
        """
        w, h = self.PAUSED_CARD
        # Through the screen's own allocator where it has one: Force
        # Pilot and Buzz Hunt route every Surface they make
        # through _new_surface so a test can pin that a steady frame
        # allocates none, and a shared helper reaching past that hook
        # would put allocations back out of its sight.
        alloc = getattr(self, "_new_surface", None)
        size = (self.layout.width, self.layout.height)
        overlay = (alloc(size, pygame.SRCALPHA) if alloc is not None
                   else pygame.Surface(size, pygame.SRCALPHA))
        overlay.fill((0, 0, 0, 160))
        surf.blit(overlay, (0, 0))
        card = pygame.Rect(0, 0, w, h)
        card.center = (self.layout.width // 2, self.layout.height // 2)
        # Fully opaque, not a tint: the probe screens put a saturated
        # orange chip right where the card lands, and at any alpha
        # under 255 its letters read straight through the word on top
        # of them.
        panel = (alloc(card.size, pygame.SRCALPHA) if alloc is not None
                 else pygame.Surface(card.size, pygame.SRCALPHA))
        pygame.draw.rect(panel, self.theme.background, panel.get_rect(),
                         border_radius=22)
        surf.blit(panel, card.topleft)
        pygame.draw.rect(surf, self.theme.warning, card, 3,
                         border_radius=22)
        draw_text(surf, "PAUSED", (card.centerx, card.y + 52),
                  self.theme, self.layout, pt=FONT_TITLE, centre=True,
                  colour=self.theme.warning)
        draw_text(surf, "Press P to carry on",
                  (card.centerx, card.bottom - 38),
                  self.theme, self.layout, pt=FONT_BODY, centre=True,
                  colour=self.theme.muted)


# Bottom-centre band the skip control sits in, measured up from the
# bottom edge. Above the mode message chip (height - 42) on the
# gameplay screen and above Buzz Hunt's own bottom line, so the three
# never stack on each other.
SKIP_CHIP_BOTTOM_GAP = 110


def draw_skip_chip(surf: pygame.Surface, layout: Layout, theme: Theme,
                   engine) -> None:
    """The one skip control, drawn the same on every block screen.

    Reads the wait straight off the engine, so a mode that arms a wait
    gets the control for free and no screen has to know which waits
    exist. The rect it draws at is stored on the engine, which is what
    a click is tested against: what the patient aims at is what
    answers. Waits too short to aim at draw nothing (see
    rest_skip.DEFAULT_CHIP_MIN_S), and the keyboard skip still works
    on those.
    """
    engine._skip_chip_rect = None
    try:
        view = engine.current_wait_view()
    except Exception:
        return
    if not view or not view.get("show"):
        return
    if getattr(engine, "paused", False):
        # A paused block is already frozen; offering to skip a wait
        # that is not counting down would be a lie.
        return
    remaining = max(0.0, float(view.get("remaining", 0.0) or 0.0))
    label = f"{view.get('label', 'Skip')}  (Space)   {remaining:.0f}s"
    font = layout.font(FONT_BODY)
    text_surf = font.render(label, True, theme.accent)
    pad_x, pad_y = 20, 10
    rect = pygame.Rect(0, 0,
                       text_surf.get_width() + pad_x * 2,
                       text_surf.get_height() + pad_y * 2)
    rect.center = (layout.width // 2,
                   layout.height - SKIP_CHIP_BOTTOM_GAP)
    pill = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(pill, (*theme.accent, 40), pill.get_rect(),
                     border_radius=rect.height // 2)
    pygame.draw.rect(pill, (*theme.accent, 170), pill.get_rect(), 2,
                     border_radius=rect.height // 2)
    surf.blit(pill, rect.topleft)
    surf.blit(text_surf, text_surf.get_rect(center=rect.center))
    engine._skip_chip_rect = rect


def _chip(surf: pygame.Surface, layout: Layout,
           centre: tuple[int, int], text: str,
           fg: tuple[int, int, int],
           bg_alpha: int = 38,
           pad_x: int = 16, pad_y: int = 6,
           font_pt: int = FONT_BODY) -> None:
    """Small rounded pill background behind a label. Module-level so
    it can be used from any screen rather than only GameplayScreen.
    The pill background is the foreground colour at low alpha, which
    keeps the chip visually tied to its content (a green text gets a
    green-tinted pill, red gets red, etc.)."""
    font = layout.font(font_pt)
    text_surf = font.render(text, True, fg)
    chip_w = text_surf.get_width() + pad_x * 2
    chip_h = text_surf.get_height() + pad_y * 2
    chip_rect = pygame.Rect(0, 0, chip_w, chip_h)
    chip_rect.center = centre
    chip_surf = pygame.Surface(chip_rect.size, pygame.SRCALPHA)
    pygame.draw.rect(chip_surf, (*fg, bg_alpha),
                      chip_surf.get_rect(), border_radius=chip_h // 2)
    surf.blit(chip_surf, chip_rect.topleft)
    surf.blit(text_surf, text_surf.get_rect(center=centre))


def _fit_text(text: str, font: pygame.font.Font, max_w: int) -> str:
    """Trim `text` until it renders inside `max_w`, ending in a full stop
    run so the cut is visible. Measured against the font rather than
    counted in characters, because a port list and a sentence of help
    text have very different widths per character and a fixed character
    budget overflows on one while cutting the other short."""
    if max_w <= 0:
        return ""
    if font.size(text)[0] <= max_w:
        return text
    ell = "..."
    lo, hi = 0, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if font.size(text[:mid] + ell)[0] <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return (text[:lo].rstrip() + ell) if lo else ""


def _draw_header(surf: pygame.Surface, title: str, subtitle: str,
                 theme: Theme, layout: Layout) -> None:
    """Reused at the top of every menu screen so they all match.

    Title is rendered bold via the same Helvetica Neue Bold cut the
    title-screen wordmark uses, plus a short accent-coloured underline
    bar so every menu shares the visual language.
    """
    cx = layout.width // 2
    title_pt = int((FONT_H1 + 6) * layout.font_scale)
    title_font = make_font(title_pt, bold=True)
    title_surf = title_font.render(title, True, theme.foreground)
    title_rect = title_surf.get_rect(center=(cx, 80))
    surf.blit(title_surf, title_rect)
    # Thin accent bar centred under the title. Width matches the
    # rendered text so different-length titles still feel balanced.
    # Slightly rounded and a touch wider than before so it reads as a
    # deliberate accent rule rather than a stray underline.
    bar_w = max(72, title_rect.w // 3)
    bar_rect = pygame.Rect(0, 0, bar_w, 4)
    bar_rect.center = (cx, title_rect.bottom + 12)
    pygame.draw.rect(surf, theme.accent, bar_rect, border_radius=2)
    if subtitle:
        draw_text(surf, subtitle, (cx, title_rect.bottom + 32),
                  theme, layout, pt=FONT_BODY, centre=True,
                  colour=theme.muted)


class MuteButton:
    """The menu-music mute, one small pill in a corner of every menu
    screen (login, hub, hand picker, results, Settings).

    It flips the logged-in person's own mute (engine.toggle_menu_music_mute,
    remembered per participant in data/prefs.py), not the machine-wide
    switch in Settings: a participant who wants quiet menus gets them
    at every visit without the RA changing the laptop's setup. Sound
    is on by default. The pill draws its state from the engine every
    frame, so five screens can never disagree about it. M toggles it
    from the keyboard on every screen that hosts one; the login screen
    passes M through to a focused field first, since M is also the
    letter that types "male" or a name.
    """

    # Wide enough for "MUSIC OFF  (M)" with the glyph, so the label
    # never hangs past the pill.
    W = 168
    H = 34
    HOTKEY = pygame.K_m

    def __init__(self, engine, rect: pygame.Rect) -> None:
        self.engine = engine
        self.rect = rect
        self.hover = False

    def muted(self) -> bool:
        try:
            return bool(self.engine.menu_music_muted())
        except Exception:
            return False

    def toggle(self) -> None:
        try:
            self.engine.toggle_menu_music_mute()
        except Exception as e:
            log.warning("menu mute toggle failed: %s", e)

    def handle_event(self, e: pygame.event.Event,
                     allow_key: bool = True) -> bool:
        """True when the event was the pill's (a click on it, or M)."""
        if e.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(e.pos)
            return False
        if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                and self.rect.collidepoint(e.pos)):
            self.toggle()
            return True
        if (allow_key and e.type == pygame.KEYDOWN
                and e.key == self.HOTKEY):
            self.toggle()
            return True
        return False

    def draw(self, surf: pygame.Surface, theme: Theme,
             layout: Layout) -> None:
        muted = self.muted()
        label = "MUSIC OFF  (M)" if muted else "MUSIC ON  (M)"
        r = self.rect
        if muted:
            bg = tuple(max(0, c - 30) for c in theme.background)
            fg = theme.muted
        else:
            bg = theme.accent if self.hover else tuple(
                max(0, c - 30) for c in theme.background)
            fg = (255, 255, 255) if self.hover else theme.foreground
        if muted and self.hover:
            bg = tuple(max(0, c - 48) for c in theme.background)
        pygame.draw.rect(surf, bg, r, border_radius=r.h // 2)
        font = layout.font(FONT_SMALL + 1)
        text = font.render(label, True, fg)
        # A small speaker glyph, crossed when muted, then the label.
        gx = r.x + 14
        gy = r.centery
        pygame.draw.polygon(surf, fg, [(gx, gy - 3), (gx + 4, gy - 3),
                                       (gx + 9, gy - 8), (gx + 9, gy + 8),
                                       (gx + 4, gy + 3), (gx, gy + 3)])
        if muted:
            pygame.draw.line(surf, fg, (gx - 1, gy - 9), (gx + 12, gy + 9),
                             2)
        else:
            pygame.draw.arc(surf, fg, pygame.Rect(gx + 6, gy - 7, 12, 14),
                            -0.9, 0.9, 2)
        surf.blit(text, text.get_rect(midleft=(gx + 24, gy)))


# ---- session continuity helpers ------------------------------------------
# One login is one session, and a session is meant to FLOW: finish a
# game, see one suggestion, press once, play it. These helpers are
# module level because both ends of that loop need them -- the results
# screen picks the suggestion and draws the strip, game select draws
# the same strip and ticks the cards already played.


def mode_title(key: str) -> str:
    """Patient-facing name for a mode key. Falls back to the key with
    underscores opened out, which is what an unknown block (a test
    double, an old session) should read as."""
    for k, title, _desc in ModeSelectScreen.MODES:
        if k == key:
            return title
    return str(key).replace("_", " ").title()


def mode_accent(key: str, theme: Theme) -> tuple[int, int, int]:
    """The mode's accent colour, or the theme accent for a key that
    has none (classic, or a test double's numeric block)."""
    return ModeSelectScreen.MODE_ACCENTS.get(str(key).lower(),
                                             theme.accent)


def playable_modes(engine) -> list[str]:
    """Mode keys this rig can actually start right now, in card order.

    The same two refusals the cards badge up front: three modes need
    real sensor hardware (there is no keyboard-equivalent play for a
    force trace or a vibration motor), and mirror needs a second
    board. A suggestion the patient cannot press would be worse than
    no suggestion.
    """
    src = getattr(engine, "source", None)
    no_hardware = not getattr(src, "provides_samples", True)
    try:
        one_board = bool(engine.second_board_missing())
    except Exception:
        one_board = False
    out = []
    for key, _title, _desc in ModeSelectScreen.MODES:
        if no_hardware and key in ModeSelectScreen.NEEDS_HARDWARE:
            continue
        if key == "mirror" and one_board:
            continue
        out.append(key)
    return out


def next_up_mode(engine, after: str | None = None) -> str | None:
    """Which game to suggest next, or None when nothing is playable.

    Unplayed modes come first: the point of the suggestion is variety
    across a session, and a patient who has already done Reaction
    twice gains nothing from being pointed at it a third time. The
    search starts at the card AFTER the one just played and wraps, so
    consecutive suggestions rotate through the grid instead of always
    landing on the first unplayed card. Once every mode has been
    played the rotation carries on, just never suggesting the game
    that has only this second finished.
    """
    order = playable_modes(engine)
    if not order:
        return None
    try:
        played = set(engine.session_modes_played())
    except Exception:
        played = set()
    start = order.index(after) + 1 if after in order else 0
    rotated = order[start:] + order[:start]
    for key in rotated:
        if key not in played:
            return key
    for key in rotated:
        if key != after:
            return key
    return rotated[0]


def _strip_pill(surf: pygame.Surface, layout: Layout, left: int, cy: int,
                text: str, fg: tuple[int, int, int],
                font_pt: int = FONT_SMALL,
                filled: bool = False) -> int:
    """Left-anchored rounded pill. Returns the width it used, so a row
    of chips can be laid out by walking x along. (_chip centres on a
    point, which a run of chips cannot use.)"""
    font = layout.font(font_pt)
    label_colour = (255, 255, 255) if filled else fg
    text_surf = font.render(text, True, label_colour)
    w = text_surf.get_width() + 20
    h = text_surf.get_height() + 8
    rect = pygame.Rect(left, cy - h // 2, w, h)
    if filled:
        pygame.draw.rect(surf, fg, rect, border_radius=h // 2)
    else:
        tint = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(tint, (*fg, 46), tint.get_rect(),
                         border_radius=h // 2)
        surf.blit(tint, rect.topleft)
        pygame.draw.rect(surf, fg, rect, 1, border_radius=h // 2)
    surf.blit(text_surf, text_surf.get_rect(center=rect.center))
    return w


# Games played before the strip stops drawing a chip per game and
# starts counting the overflow. Ten cards on the grid, so a long
# session can pass this; the tail reads "+3 more" rather than running
# off the edge.
STRIP_MAX_CHIPS = 7

# The strip is one row, and both screens size their rect to it.
SESSION_STRIP_H = 52


def draw_session_strip(surf: pygame.Surface, rect: pygame.Rect,
                       engine, theme: Theme, layout: Layout,
                       show_flourish: bool = False) -> None:
    """The quiet session line: what has been played, and the running
    totals.

    The same drawing on game select and on the results screen, so the
    patient reads one continuous session rather than a set of
    unrelated games. Everything it shows comes from the engine's
    session log, which is written in the same two places that count a
    game for the End-session dialog, so the chips can never disagree
    with that count.
    """
    body = tuple(max(0, min(255, c - 6)) for c in theme.background)
    pygame.draw.rect(surf, body, rect, border_radius=14)
    outline = tuple(max(0, c - 26) for c in theme.background)
    pygame.draw.rect(surf, outline, rect, 1, border_radius=14)

    try:
        rows = engine.session_games_log()
        points = engine.session_points()
        stars = engine.session_stars()
    except Exception:
        # A bare engine (test doubles build one with __new__ and no
        # session state) must not take the screen down with it.
        rows, points, stars = [], 0, 0

    cy = rect.centery
    # Totals first: they hold the right-hand column whatever the chips
    # do, and the chip run needs to know where to stop. Stars are the
    # light session-wide progression, the same 0-3 the grade ring
    # already earned, added up.
    n_games = len(rows)
    totals = (f"{n_games} game{'' if n_games == 1 else 's'}"
              f"   {stars} star{'' if stars == 1 else 's'}"
              f"   {points} pts")
    tfont = layout.font(FONT_BODY)
    tw = tfont.size(totals)[0]
    totals_x = rect.right - 18 - tw
    draw_text(surf, totals, (totals_x, cy - tfont.get_height() // 2),
              theme, layout, pt=FONT_BODY, centre=False,
              colour=theme.foreground)

    # Three games in is a real session's worth of work for a patient
    # who tires quickly, so it gets a quiet acknowledgement and
    # nothing more. This is a clinic tool: no levels, no confetti.
    right_limit = totals_x - 16
    if show_flourish and n_games >= 3:
        note = "Good session"
        nw = layout.font(FONT_SMALL).size(note)[0] + 20
        _strip_pill(surf, layout, right_limit - nw, cy, note,
                    (255, 196, 0), filled=True)
        right_limit -= nw + 16

    x = rect.x + 18
    # PLAY ALL progress leads the strip while the battery is running:
    # the one line the RA checks against the run sheet. Filled so it
    # reads as status, not as another game chip.
    try:
        progress = engine.battery_progress()
    except Exception:
        progress = None
    if isinstance(progress, dict):
        if progress.get("finished"):
            text = f"PLAY ALL DONE {progress['done']}/{progress['of']}"
        else:
            text = f"PLAY ALL {progress['done']}/{progress['of']}"
            nxt = progress.get("next")
            if isinstance(nxt, dict) and nxt.get("mode"):
                text += f"  next {mode_title(str(nxt['mode']))}"
        x += _strip_pill(surf, layout, x, cy, text, theme.accent,
                         filled=True) + 12
        # The session clock, next to the step count. One long sitting
        # has a design target and a hard stop (the preset's budget_min
        # and hard_stop_min), and the RA's only cue that the session is
        # running late used to be their own watch. Muted inside the
        # budget, amber past it, red past the hard stop.
        minutes = float(progress.get("minutes") or 0.0)
        budget = float(progress.get("budget_min") or 0.0)
        hard_stop = float(progress.get("hard_stop_min") or 0.0)
        if budget > 0 or minutes > 0:
            if hard_stop > 0 and minutes > hard_stop:
                clock_colour = theme.error
            elif budget > 0 and minutes > budget:
                clock_colour = theme.warning
            else:
                clock_colour = theme.muted
            x += _strip_pill(surf, layout, x, cy,
                             f"{minutes:.0f} min", clock_colour) + 12
    if not rows:
        draw_text(surf, "No games played yet",
                  (x, cy - tfont.get_height() // 2),
                  theme, layout, pt=FONT_BODY, centre=False,
                  colour=theme.muted)
        return
    shown = 0
    # Room kept back for the overflow chip, so a long session's last
    # chips are replaced by "+3 more" rather than running over the
    # totals on the right.
    tail_w = layout.font(FONT_SMALL).size("+99 more")[0] + 28
    for i, row in enumerate(rows[:STRIP_MAX_CHIPS]):
        key = str(row.get("mode") or "")
        label = mode_title(key)
        width = layout.font(FONT_SMALL).size(label)[0] + 20
        last = i == len(rows) - 1
        if x + width > (right_limit if last else right_limit - tail_w):
            break
        # Darkened accent for the chip text: the pale end of the mode
        # palette (syllables pink, force pilot lime) does not carry
        # small type on a light page at full chroma.
        ink = tuple(int(c * 0.68) for c in mode_accent(key, theme))
        _strip_pill(surf, layout, x, cy, label, ink)
        x += width + 8
        shown += 1
    extra = len(rows) - shown
    if extra > 0:
        _strip_pill(surf, layout, x, cy, f"+{extra} more", theme.muted)


class TitleScreen(Screen):
    # Session protocol shown in the Info overlay. Every participant runs
    # the same core modes, in the same order, the same number of times, so
    # the final analysis compares like with like. Reaction took Classic's
    # place as the baseline: Classic's fixed pattern was learnable in
    # seconds, so half of what it measured was anticipation.
    INFO_TITLE = "Session protocol"
    INFO_STEPS = [
        "1. Enter the participant code (or name), age and main hand,",
        "      then press LOG IN. A study visit presses PLAY ALL on the hub.",
        "2. Run the four core modes in this order, once each per session:",
        "      Reaction  (baseline eye-to-hand speed, random waits)",
        "      Adaptive  (40 trials, pace adjusts to the participant)",
        "      Rhythm  (one full song, press on the beat)",
        "      Mirror  (40 trials, both hands together)",
        "3. Training modes as prescribed for the participant:",
        "      Muscle Memory, Chords, Syllables, Force Pilot,",
        "      Buzz Hunt, Echo",
        "4. Finish every block. Quitting early leaves gaps in the data.",
    ]
    INFO_FOOTER = ("The four core blocks give the comparable data; the "
                   "training modes add their own measures on top.")

    # Vertical rhythm, in logical pixels against the 1280x800 render
    # surface. Held as constants because the card, the inputs and the
    # start button have to move together: the card is drawn from these
    # and so are the controls inside it, so neither can drift from the
    # other. The intake card is two rows of fields plus the button, so
    # the wordmark sits higher than it did with one row.
    ICON_Y = 92
    WORDMARK_Y = 196
    TAGLINE_Y = 246
    CARD_TOP = 282
    CARD_W = 940
    CARD_H = 372
    # Field rows inside the card, offsets from CARD_TOP. Labels draw 26
    # px above each field.
    ROW1_Y = 70
    ROW2_Y = 160
    BUTTON_Y = 240
    NOTE_Y = 330
    FIELD_H = 54
    # Utility strip along the bottom: one row of equal-height pills on a
    # single baseline, with a hairline rule above it.
    PILL_H = 44
    PILL_W = 150
    EDGE = 28

    # Sex options: key is what metadata records, caption what the RA
    # reads. Empty key is "prefer not to say", the default, so a
    # participant who declines costs no keystroke.
    SEX_OPTIONS = [("", "Not said"), ("female", "Female"),
                   ("male", "Male"), ("other", "Other")]
    SEX_HOTKEYS = {"n": "", "f": "female", "m": "male", "o": "other"}
    HAND_OPTIONS = [("left", "Left"), ("right", "Right")]
    HAND_HOTKEYS = {"l": "left", "r": "right"}

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        cx = engine.layout.width // 2
        w, h = engine.layout.width, engine.layout.height

        # The intake card. Row one is the identity (code or name, age,
        # sex); row two is what the study needs per person (main hand,
        # hand size). Everything is set once here and reused for every
        # block the participant plays this session, so every CSV row
        # and every session folder is tagged the same way. The visit
        # number is not a field: it is worked out from the days this
        # identity has already played on and recorded on its own, and
        # the Edinburgh score is not asked at all (the Session keeps
        # the column for old data). Basil's call: fewer fields, and
        # the main hand as a plain left / right choice.
        self.card_rect = pygame.Rect(cx - self.CARD_W // 2, self.CARD_TOP,
                                     self.CARD_W, self.CARD_H)
        x0 = self.card_rect.x + 40
        r1 = self.CARD_TOP + self.ROW1_Y
        r2 = self.CARD_TOP + self.ROW2_Y
        fh = self.FIELD_H
        # `name_input` keeps its name: the identity field is the same
        # field it always was, it just accepts a study code as well.
        self.name_input = TextInput(
            pygame.Rect(x0, r1, 330, fh),
            self.theme, self.layout,
            label="PARTICIPANT CODE OR NAME",
            placeholder="P01, or a name",
            max_len=40,
        )
        self.age_input = TextInput(
            pygame.Rect(x0 + 346, r1, 110, fh),
            self.theme, self.layout,
            label="AGE",
            placeholder="Years",
            max_len=4,
        )
        self.sex_seg = Segmented(
            pygame.Rect(x0 + 472, r1, 388, fh),
            self.theme, self.layout,
            options=self.SEX_OPTIONS, label="SEX  (optional)",
            initial="", hotkeys=self.SEX_HOTKEYS,
        )
        # `hand_seg` keeps its name and the metadata key stays
        # dominant_hand, so old sessions and the analysis read on.
        self.hand_seg = Segmented(
            pygame.Rect(x0, r2, 260, fh),
            self.theme, self.layout,
            options=self.HAND_OPTIONS, label="MAIN HAND",
            initial=None, hotkeys=self.HAND_HOTKEYS,
        )
        self.length_input = TextInput(
            pygame.Rect(x0 + 300, r2, 260, fh),
            self.theme, self.layout,
            label="HAND LENGTH mm", placeholder="optional",
            max_len=3, numeric=True,
        )
        self.breadth_input = TextInput(
            pygame.Rect(x0 + 600, r2, 260, fh),
            self.theme, self.layout,
            label="HAND BREADTH mm", placeholder="optional",
            max_len=3, numeric=True,
        )
        # One focus order for Tab, text fields and pickers alike.
        self._fields = [self.name_input, self.age_input, self.sex_seg,
                        self.hand_seg, self.length_input,
                        self.breadth_input]
        # Carry-over bookkeeping: the (identity, age) the fields were
        # last filled for, and what was written, so a value the RA
        # typed by hand is never overwritten by the lookup and a
        # carried value is dropped again when the identity changes.
        self._prefill_for: tuple[str, str] | None = None
        self._prefill_source: dict | None = None
        self.refresh()

        # Blank-name guard state: the first LOG IN with no name shows
        # a warning line instead of starting; the second click
        # proceeds anonymously (a deliberate choice, not a slip).
        self._na_warned = False
        self.begin_note = ""
        # Primary action. Logs the participant in: the identity set
        # here persists across every game until the session ends on
        # game select. Filled in green (independent of the blue theme
        # accent) so it reads as a "go" action.
        self.start_btn = Button(
            pygame.Rect(cx - BUTTON_W // 2, self.CARD_TOP + self.BUTTON_Y,
                        BUTTON_W, BUTTON_H + 12),
            "LOG IN", self._begin,
            self.theme, self.layout,
            font_pt=FONT_H2,
            colour=(34, 197, 94),     # green
        )
        # Utility pills, one row along the bottom. Quit is on its own at
        # the far left because it is the destructive one; the three
        # setup actions group at the right in the order a therapist
        # meets them, Info then Calibrate then Settings.
        row_y = h - self.PILL_H - 34
        self.quit_rect = pygame.Rect(self.EDGE, row_y,
                                     self.PILL_W, self.PILL_H)
        self.settings_rect = pygame.Rect(w - self.EDGE - self.PILL_W, row_y,
                                         self.PILL_W, self.PILL_H)
        # Calibration is meant to be run BEFORE a session, which is why it
        # sits out here on the way in rather than buried inside Settings.
        self.calibrate_rect = pygame.Rect(
            self.settings_rect.x - 12 - self.PILL_W, row_y,
            self.PILL_W, self.PILL_H)
        # Info opens a modal listing the session protocol, so a therapist
        # running the trial knows which modes to run, in what order and
        # how many times, and every participant produces the same data.
        iw = 130
        self.info_rect = pygame.Rect(self.calibrate_rect.x - 12 - iw, row_y,
                                     iw, self.PILL_H)
        # One list drives both the drawing and the hit test, so a pill can
        # never be clickable somewhere other than where it was drawn.
        self._pills = [
            (self.quit_rect, "Quit", "close", self.engine.request_quit),
            (self.info_rect, "Info", "info", self._open_info),
            (self.calibrate_rect, "Calibrate", "tune",
             self.engine.show_calibration),
            (self.settings_rect, "Settings", "cog",
             self.engine.show_diagnostics),
        ]
        # Whether the info overlay is currently open. Click the Info
        # pill (or anywhere on the overlay, or Esc) to toggle it.
        self._show_info = False
        # Menu-music mute, top-left corner, the same pill every menu
        # screen carries. Before login it applies to whoever is typed
        # into the identity field (engine.pref_identity).
        self.mute_btn = MuteButton(
            engine, pygame.Rect(self.EDGE, 26, MuteButton.W, MuteButton.H))

    def pending_identity(self) -> str:
        """The identity typed so far, for preferences before login."""
        return self.name_input.value

    def _open_info(self) -> None:
        self._show_info = True

    def _hardware_status(self) -> tuple[str, tuple[int, int, int]]:
        """One line saying which port each hand got, for the strip above
        the utility pills. Boards auto-assign by plug order (first =
        right, second = left) and this is where that result is said out
        loud, so the login screen answers "did both hands connect?"
        without a trip into Settings. Amber when a stale saved port was
        ignored, so the fallback is visible rather than silent."""
        src = self.engine.source
        hands = getattr(src, "hands", None)
        if not getattr(src, "provides_samples", False) or not hands:
            return ("No Arduino detected: keyboard mode "
                    "(right J K L ;  left F D S A)", self.theme.muted)
        from ..hardware.discovery import short_port
        bits = "   ".join(f"{h.hand.upper()} = {short_port(h.port)}"
                          for h in hands)
        note = getattr(src, "assignment_note", "")
        if "ignored" in note:
            return (f"Arduino: {bits}   "
                    "(saved port ignored, see Settings)",
                    self.theme.warning)
        return (f"Arduino: {bits}", self.theme.muted)

    # ---- intake helpers ---------------------------------------------------
    def _data_dir(self):
        """The sessions tree the suggestions read, or None on an
        engine with no config (a bare test double)."""
        try:
            cfg = self.engine.cfg
            return cfg.resolve_path(cfg.get("session.data_dir", "sessions"))
        except Exception:
            return None

    def _cfg_str(self, key: str) -> str:
        try:
            v = self.engine.cfg.get(key)
        except Exception:
            return ""
        s = str(v if v is not None else "").strip()
        return "" if s in ("None", "NA") else s

    def _suggested_code(self) -> str:
        """The next free study code, or '' when the config says not to
        suggest one (or, in auto mode, when nobody on this machine has
        ever logged in with a code, so a clinic never sees one)."""
        from ..data.intake import known_codes, suggest_next_code
        mode = self._cfg_str("session.suggest_code").lower() or "auto"
        if mode == "never":
            return ""
        data_dir = self._data_dir()
        if mode == "auto" and not known_codes(data_dir):
            return ""
        return suggest_next_code(data_dir)

    # Which login field carries each carried-over intake key.
    def _carry_targets(self) -> dict:
        return {"hand_length_mm": self.length_input,
                "hand_breadth_mm": self.breadth_input,
                "dominant_hand": self.hand_seg,
                "sex": self.sex_seg}

    def _refresh_prefill(self) -> None:
        """Fill hand size, main hand and sex from this identity's last
        recorded game, and take the fill back when the identity
        changes to someone with no record.

        Runs once per change of (identity, age), never per frame. A
        field only takes a carried value while it is empty or still
        holding the last carried value: anything the RA typed stands.
        The lookup is data/intake.previous_intake, which opens only
        this identity's own folders.
        """
        from ..data.intake import previous_intake
        key = (self.name_input.value, self.age_input.value)
        if key == self._prefill_for:
            return
        self._prefill_for = key
        found = previous_intake(self._data_dir(), key[0], key[1])
        for name, field in self._carry_targets().items():
            carried = bool(getattr(field, "prefilled", False))
            if isinstance(field, Segmented):
                # Sex's "not said" is the empty key; the hand has no
                # pick at all until one is made.
                blank = "" if name == "sex" else None
                empty = field.value in (None, "")
            else:
                blank = ""
                empty = not field.text
            if not (empty or carried):
                continue          # typed by hand today: leave it
            value = (found or {}).get(name, "")
            if value:
                field.set_prefilled(value)
            elif carried:
                if isinstance(field, Segmented):
                    field.set(blank)
                else:
                    field.text = blank
                field.prefilled = False
        self._prefill_source = found

    def _prefill_note(self) -> str:
        """One line under the button saying what was carried over and
        from when, or '' when nothing on screen is carried."""
        src = self._prefill_source
        if not src:
            return ""
        words = {"hand_length_mm": "hand length",
                 "hand_breadth_mm": "hand breadth",
                 "dominant_hand": "main hand", "sex": "sex"}
        carried = [words[k] for k, f in self._carry_targets().items()
                   if getattr(f, "prefilled", False)]
        if not carried:
            return ""
        return (", ".join(carried).capitalize()
                + f" filled from {src.get('who', '')}'s last visit "
                + f"({src.get('day', '')}). Type over to change.")

    def _derived_visit(self, name: str) -> str:
        """The visit this login is: a pre-fill from a yaml passed as
        --config wins, otherwise one more than the earlier days this
        identity has played on (data/intake.suggest_visit)."""
        from ..data.intake import suggest_visit
        pre = self._cfg_str("session.visit")
        if pre:
            return pre
        return str(suggest_visit(self._data_dir(), name))

    def update(self, dt: float) -> None:
        self._refresh_prefill()

    def _begin(self) -> None:
        from ..data.intake import is_study_code, normalise_code
        name = normalise_code(self.name_input.value) or "NA"
        # A blank name pools this session into the shared NA identity:
        # every anonymous session on the machine merges into one
        # improvement trace, so cross-session tracking for this
        # patient becomes meaningless. Say so ONCE and require a
        # second deliberate click, rather than silently accepting the
        # most common data-entry slip in a hurried clinic.
        if name == "NA" and not self._na_warned:
            self._na_warned = True
            self.begin_note = ("No name entered: sessions will pool "
                               "under NA and cannot be tracked per "
                               "patient. Begin again to continue "
                               "anonymously.")
            return
        # The RA may type the code and press Enter inside one frame;
        # the carry-over (main hand included) has to land before the
        # checks below and before the commit.
        self._refresh_prefill()
        # A study code needs the main hand: the play-all hand order
        # and the analysis's hand contrast both hang off it, and it
        # cannot be recovered after the visit. A name (the clinic
        # path) is not held to this.
        if is_study_code(name) and self.hand_seg.value is None:
            self.begin_note = ("Pick the main hand for a study code "
                               "(click Left or Right, or Tab to the "
                               "field and press L or R).")
            return
        self._na_warned = False
        self.begin_note = ""
        # Age is optional; an empty string is its own valid value
        # meaning "not provided" (patient declined, or the therapist
        # didn't type it). Stored as a raw string so the CSV column
        # round-trips whatever was typed instead of coercing to int
        # and rejecting unusual inputs like "65y".
        age = self.age_input.value or ""
        # The engine owns the session lifecycle: identity into cfg +
        # session metadata, the EEG session-start marker, then game
        # select as home base for as many games as the player wants.
        # Nothing is passed for edinburgh_lq: the screen no longer
        # asks it, so the config's value (a yaml pre-fill, or nothing)
        # is what the Session records.
        self.engine.begin_session(
            name, age,
            sex=self.sex_seg.value or "",
            dominant_hand=self.hand_seg.value or "",
            visit=self._derived_visit(name),
            hand_length_mm=self.length_input.value,
            hand_breadth_mm=self.breadth_input.value,
        )

    def _draw_device_icon(self, surf: pygame.Surface,
                           cx: int, cy: int) -> None:
        """Stylised render of the finger-rehab device. Four vertical
        sensor pads with LED dots on top, sitting on a curved base
        plate. One pad at a time goes dark blue (cycling through the
        four) to read as "this finger is selected", which is exactly
        what the lane strips do in-game when a stim fires.
        """
        pad_w = 26
        pad_h = 86
        gap = 18
        n = 4
        block_w = pad_w * n + gap * (n - 1)
        x0 = cx - block_w // 2
        accent = self.theme.accent
        # Pad colours: default matches the title text below so the icon
        # and the wordmark read as one unit. Active pad goes dark blue
        # so the cycling animation reads as a single pad being picked
        # rather than a separate LED blinking.
        default_body = accent
        active_body = tuple(max(0, int(c * 0.30)) for c in accent)
        # Tiny inner highlight stripe to give the bright pads a hint of
        # depth without making them look gel-buttony.
        highlight = tuple(min(255, int(c + (255 - c) * 0.35)) for c in accent)
        # Cycle: one pad at a time, full sweep every 2 s.
        phase = (time.perf_counter() % 2.0) / 2.0
        active_pad = int(phase * n) % n

        for i in range(n):
            x = x0 + i * (pad_w + gap)
            pad_rect = pygame.Rect(x, cy - pad_h // 2, pad_w, pad_h)
            is_active = (i == active_pad)
            body = active_body if is_active else default_body
            pygame.draw.rect(surf, body, pad_rect, border_radius=10)
            # Highlight stripe only on default pads. The active pad
            # stays clean dark blue so it really pops as selected.
            if not is_active:
                pygame.draw.rect(surf, highlight,
                                  pygame.Rect(x + 2, cy - pad_h // 2 + 4,
                                              3, pad_h - 8),
                                  border_radius=2)
            # Small LED dot on top of each pad. Colour matches the pad
            # below so the dot reads as part of the same sensor unit.
            led_cx = x + pad_w // 2
            led_cy = cy - pad_h // 2 - 8
            pygame.draw.circle(surf, body, (led_cx, led_cy), 6)

        # Base plate that the pads sit on. Wider than the pad block so
        # it reads as a device housing, with a slight downward curve
        # via a rounded rect with bigger radius on the bottom.
        base_w = block_w + 60
        base_h = 22
        base_x = cx - base_w // 2
        base_y = cy + pad_h // 2 + 4
        base_body = tuple(int(c * 0.4) for c in accent)
        pygame.draw.rect(surf, base_body,
                          pygame.Rect(base_x, base_y, base_w, base_h),
                          border_radius=11)
        # Brand strip on the base: small darker line down the centre
        # for a sense of detail.
        pygame.draw.line(surf, base_body,
                          (base_x + 10, base_y + base_h - 3),
                          (base_x + base_w - 10, base_y + base_h - 3),
                          1)

    def refresh(self) -> None:
        """Re-sync every field with the current cfg values. Called by
        engine.show_title() so coming BACK to the login screen (a
        session just ended, which clears the participant) shows the
        cleared state instead of the stale text from last time, and
        re-reads the sessions tree for the next free code."""
        prefill_name = self._cfg_str("session.participant")
        self.name_input.select_all = False
        if not prefill_name:
            prefill_name = self._suggested_code()
            # A suggestion is typed over, not appended to.
            self.name_input.select_all = bool(prefill_name)
        self.name_input.text = prefill_name
        self.age_input.text = self._cfg_str("session.age")
        self.sex_seg.set(self._cfg_str("session.sex").lower())
        hand = self._cfg_str("session.dominant_hand").lower()
        self.hand_seg.set(hand if hand in ("left", "right") else None)
        self.length_input.text = self._cfg_str("session.hand_length_mm")
        self.breadth_input.text = self._cfg_str("session.hand_breadth_mm")
        for f in self._fields:
            f.focused = False
            f.prefilled = False
        # A fresh screen carries nothing yet; the first update fills
        # from the tree for whatever identity the field opens with.
        self._prefill_for = None
        self._prefill_source = None
        self._refresh_prefill()
        self._na_warned = False
        self.begin_note = ""

    def _focus_move(self, step: int) -> None:
        """Tab (step 1) or Shift+Tab (step -1) through the fields, in
        reading order; off the end lands on nothing, ready for Enter."""
        cur = next((i for i, f in enumerate(self._fields) if f.focused), -1)
        for f in self._fields:
            f.focused = False
        if cur < 0:
            nxt = 0 if step > 0 else len(self._fields) - 1
        else:
            nxt = cur + step
        if 0 <= nxt < len(self._fields):
            self._fields[nxt].focused = True

    def handle_event(self, e: pygame.event.Event) -> None:
        # When the info overlay is open it is modal: any click or Esc
        # closes it, and nothing underneath gets the event. This keeps
        # the protocol card from accidentally starting a session.
        if self._show_info:
            if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1) or (
                    e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                self._show_info = False
            return
        # Tab walks the focus order, claimed here before dispatch so a
        # keyboard-only session (no mouse at all, audit finding #113)
        # can reach every field: a field only takes keys once focused,
        # and a click used to be the only way to focus one.
        if e.type == pygame.KEYDOWN and e.key == pygame.K_TAB:
            shift = bool(getattr(e, "mod", 0) & pygame.KMOD_SHIFT)
            self._focus_move(-1 if shift else 1)
            return
        # The mute pill: a click on it is its own, and M is its key
        # only while no field has focus (a focused field is typing).
        field_focused = any(f.focused for f in self._fields)
        if self.mute_btn.handle_event(e, allow_key=not field_focused):
            return
        # Fields first so a click in one claims focus before any button
        # hit-test runs underneath; every field sees the event so a
        # click outside can defocus the one that had it.
        for f in self._fields:
            f.handle_event(e)
        self.start_btn.handle_event(e)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for rect, _label, _icon, action in self._pills:
                if rect.collidepoint(e.pos):
                    action()
                    break
        # Enter always starts the session, whether or not a field was
        # focused: this used to be gated on "a field is (still)
        # focused after the dispatch above", but TextInput's own Enter
        # handling defocuses the field on the very same event, so that
        # check always read False and Enter never fired (audit finding
        # #113's "keyboard-only start" requirement caught this: a
        # keyboard-only session had no way to leave this screen at
        # all). Checking the PRE-dispatch focus state, or simply
        # firing unconditionally on Enter, both fix it; unconditional
        # also covers the fresh-screen case where the participant
        # never focused a field and just wants to start with the
        # default name.
        if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
            self._begin()

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        cx = self.layout.width // 2

        # Finger-sensor device graphic above the title. Four vertical
        # sensor pads with LED-style dots sitting on a curved base
        # plate. Mirrors what the actual hardware looks like, rather
        # than the old abstract concentric rings.
        self._draw_device_icon(surf, cx, self.ICON_Y)

        # Big bold wordmark in the app typeface. A soft neutral shadow
        # one pixel below the text gives a faint lift without the old
        # heavy accent-coloured offset that read as a 3-D drop. The main
        # text carries the accent colour on its own.
        title_text = "FINGER REHAB"
        title_pt = int((FONT_TITLE + 14) * self.layout.font_scale)
        title_font = make_font(title_pt, bold=True)
        shadow = title_font.render(title_text, True, (15, 23, 42))
        shadow.set_alpha(28)
        surf.blit(shadow, shadow.get_rect(center=(cx, self.WORDMARK_Y + 2)))
        main = title_font.render(title_text, True, self.theme.accent)
        surf.blit(main, main.get_rect(center=(cx, self.WORDMARK_Y)))
        # Tagline.
        draw_text(surf, "Multi-modal finger rehabilitation",
                  (cx, self.TAGLINE_Y), self.theme, self.layout,
                  pt=FONT_BODY + 4, centre=True, colour=self.theme.muted)

        # Card holding the whole "start a session" job: who is playing,
        # how old they are, and the button that begins. Grouping them
        # means the eye lands on one block instead of three loose
        # controls, and the button can never drift away from the fields
        # it commits.
        Card(self.card_rect, self.theme, layout=self.layout).draw(surf)
        draw_text(surf, "SESSION LOG IN",
                  (cx, self.card_rect.y + 20), self.theme, self.layout,
                  pt=FONT_SMALL + 2, centre=True, colour=self.theme.muted)
        for f in self._fields:
            f.draw(surf)
        self.start_btn.draw(surf)
        if self.begin_note:
            # The blank-name or missing-hand warning, inside the card
            # under the button so it reads as part of the log-in flow.
            draw_text(surf, self.begin_note,
                      (cx, self.card_rect.y + self.NOTE_Y),
                      self.theme, self.layout, pt=FONT_SMALL + 1,
                      centre=True, colour=self.theme.warning)
        elif self.name_input.select_all and self.name_input.text:
            draw_text(surf, f"Next free code {self.name_input.text} "
                      "suggested. Type to replace it, Enter to use it.",
                      (cx, self.card_rect.y + self.NOTE_Y),
                      self.theme, self.layout, pt=FONT_SMALL + 1,
                      centre=True, colour=self.theme.muted)
        elif self._prefill_note():
            draw_text(surf, self._prefill_note(),
                      (cx, self.card_rect.y + self.NOTE_Y),
                      self.theme, self.layout, pt=FONT_SMALL + 1,
                      centre=True, colour=self.theme.muted)

        # Utility strip. A hairline rule separates the session job above
        # from the setup actions below, so the bottom row reads as tools
        # rather than as part of the flow.
        rule_y = self.quit_rect.top - 26
        rule_colour = tuple(max(0, c - 22) for c in self.theme.background)
        pygame.draw.line(surf, rule_colour,
                         (self.EDGE, rule_y),
                         (self.layout.width - self.EDGE, rule_y), 1)
        # Hardware line just above the rule: which port went to which
        # hand (auto plug order: first board = right, second = left),
        # or the keyboard fallback. Lives on the login screen so a
        # therapist knows both hands connected before starting.
        hw_line, hw_colour = self._hardware_status()
        draw_text(surf, hw_line, (cx, rule_y - 22),
                  self.theme, self.layout, pt=FONT_SMALL + 1,
                  centre=True, colour=hw_colour)
        mouse = self.engine._to_logical(pygame.mouse.get_pos())
        for rect, label, icon, _action in self._pills:
            self._draw_pill(surf, rect, label, icon,
                            rect.collidepoint(mouse))
        self.mute_btn.draw(surf, self.theme, self.layout)

        # Footer: author, institution and the version this build records
        # into every session's metadata.
        from ..data.session import SOFTWARE_VERSION
        draw_text(surf,
                  f"Basil Toufexis | Curtin University 2026 "
                  f"| v{SOFTWARE_VERSION}",
                  (cx, self.layout.height - 20), self.theme, self.layout,
                  pt=FONT_SMALL + 1, centre=True, colour=self.theme.muted)

        # Modal protocol overlay, drawn last so it sits on top of
        # everything else when open.
        if self._show_info:
            self._draw_info_overlay(surf)

    def _draw_pill(self, surf: pygame.Surface, rect: pygame.Rect,
                   label: str, icon: str, hovered: bool) -> None:
        """One utility pill: icon plus word, centred as a unit.

        Quit is filled red at rest because it closes the app and that
        difference has to be readable at a glance; the rest sit quiet
        until hovered.
        """
        if icon == "close":
            base_red = getattr(self.theme, "error", (200, 60, 60))
            bg = base_red if hovered else tuple(int(c * 0.85)
                                                for c in base_red)
            fg = (255, 255, 255)
        else:
            bg = (self.theme.accent if hovered
                  else tuple(max(0, c - 30) for c in self.theme.background))
            fg = (255, 255, 255) if hovered else self.theme.foreground
        pygame.draw.rect(surf, bg, rect, border_radius=12)
        font = self.layout.font(FONT_BODY)
        text = font.render(label, True, fg)
        icon_r, gap = 8, 10
        total_w = icon_r * 2 + gap + text.get_width()
        icx = rect.centerx - total_w // 2 + icon_r
        icy = rect.centery
        if icon == "close":
            # An X, so the pill reads as "exit" without a Unicode glyph.
            pygame.draw.line(surf, fg, (icx - icon_r + 2, icy - icon_r + 2),
                             (icx + icon_r - 2, icy + icon_r - 2), 3)
            pygame.draw.line(surf, fg, (icx + icon_r - 2, icy - icon_r + 2),
                             (icx - icon_r + 2, icy + icon_r - 2), 3)
        elif icon == "cog":
            pygame.draw.circle(surf, fg, (icx, icy), icon_r, 2)
            pygame.draw.circle(surf, fg, (icx, icy), 3)
        elif icon == "tune":
            # A slider track with a handle part way along it.
            pygame.draw.line(surf, fg, (icx - icon_r, icy),
                             (icx + icon_r, icy), 2)
            pygame.draw.circle(surf, fg, (icx + 2, icy), 4)
        else:
            # Lowercase i in a ring.
            pygame.draw.circle(surf, fg, (icx, icy), icon_r, 2)
            pygame.draw.circle(surf, fg, (icx, icy - 3), 1)
            pygame.draw.line(surf, fg, (icx, icy - 1), (icx, icy + 4), 2)
        surf.blit(text, text.get_rect(
            midleft=(icx + icon_r + gap, icy)))

    def _draw_info_overlay(self, surf: pygame.Surface) -> None:
        """Dim the screen and draw a centred card listing the session
        protocol. Mirrors the paused-overlay pattern used in-game."""
        w, h = self.layout.width, self.layout.height
        overlay = pygame.Surface((w, h), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surf.blit(overlay, (0, 0))

        # Card. Sized to hold the title, the step lines and the footer.
        card_w = min(720, w - 120)
        card_h = 470
        card = pygame.Rect(w // 2 - card_w // 2, h // 2 - card_h // 2,
                           card_w, card_h)
        panel = tuple(min(255, c + 8) for c in self.theme.background)
        pygame.draw.rect(surf, panel, card, border_radius=16)
        pygame.draw.rect(surf, self.theme.accent, card, 2, border_radius=16)

        pad = 36
        x = card.left + pad
        y = card.top + pad
        draw_text(surf, self.INFO_TITLE, (card.centerx, y),
                  self.theme, self.layout, pt=FONT_H2, centre=True,
                  colour=self.theme.accent)
        y += 54
        for line in self.INFO_STEPS:
            indented = line.startswith("      ")
            draw_text(surf, line.strip() if indented else line,
                      (x + (28 if indented else 0), y),
                      self.theme, self.layout, pt=FONT_BODY,
                      colour=(self.theme.muted if indented
                              else self.theme.foreground))
            y += 38 if not indented else 32
        y += 8
        # Footer wraps to the card width.
        draw_text(surf, self.INFO_FOOTER, (x, y),
                  self.theme, self.layout, pt=FONT_SMALL,
                  colour=self.theme.muted)
        draw_text(surf, "Click anywhere or press Esc to close",
                  (card.centerx, card.bottom - 26),
                  self.theme, self.layout, pt=FONT_SMALL, centre=True,
                  colour=self.theme.muted)


class ModeSelectScreen(Screen):
    """Pick adaptive / classic / rhythm / mirror. Each option is a
    card with a short description so a clinician can pick without
    prior knowledge."""

    # Reaction replaces Classic as the baseline mode. Classic's fixed
    # 6-trial loop was learnable in seconds, so half of what it measured
    # was anticipation; Reaction randomises the wait so the number it
    # produces is actually a reaction time. begin_classic_block survives
    # for old sessions and tests, it just is not offered here.
    #
    # Card descriptions follow one line pattern: what you do + what it
    # helps with, in patient-readable words. Each claim is drawn from
    # the mode's own docstring research case and never overclaims:
    # measurement modes (Reaction, Buzz Hunt) say "measures", training
    # modes say "trains" or "builds" only where the docstring's
    # evidence base carries it (Taud 2021 for force tracking, Carey
    # 2011 for touch discrimination, the National Reading Panel
    # meta-analysis for sound awareness). Rhythm and Mirror say
    # "practise" because their docstrings mark the therapy evidence
    # contested. A layout test pins every description inside its card
    # in both columns.
    MODES = [
        ("reaction", "Reaction",
         "Press the key that lights up, fast. Measures eye-to-hand speed."),
        ("adaptive", "Adaptive",
         "Hit cued keys as the pace adapts to you. Keeps practice at "
         "the right challenge."),
        # The pattern card must not mention that a sequence repeats, or
        # even use the word "pattern": the patient can read this
        # screen, and explicit knowledge of the sequence impairs the
        # implicit learning the mode measures (Boyd and Winstein
        # 2003/2004; see modes/pattern.py). Titled "Muscle Memory"
        # rather than "Patterns" for the same reason (audit finding
        # #10) -- the internal mode key stays "pattern".
        ("pattern", "Muscle Memory",
         "Record takes of a piano riff, session by session. Builds "
         "muscle memory."),
        ("chords", "Chords",
         "Press 2-4 keys as one chord. Trains fingers to move "
         "together, and to stay still."),
        ("rhythm", "Rhythm",
         "Press in time with a song. Practises movement timing to "
         "a beat."),
        ("syllables", "Syllables",
         "Catch the right part of the word as it falls. Builds the "
         "sound skills reading rests on."),
        ("mirror", "Mirror",
         "Same finger, both hands, pressed as one. Practises moving "
         "the hands together."),
        ("force_pilot", "Force Pilot",
         "Keep your press inside a moving corridor. Trains smooth "
         "force control."),
        ("buzz_hunt", "Buzz Hunt",
         "Feel which finger buzzed and press it. Measures and trains "
         "the sense of touch."),
        # Echo is measurement-first like Reaction and Buzz Hunt, so
        # the card says "measures" and promises nothing therapeutic.
        # Unlike the pattern card there is no secret to keep: explicit
        # memorising IS the task here.
        ("echo", "Echo",
         "Watch the keys light up, then play them back in order. "
         "Measures memory span."),
    ]
    # Every stage of these two needs a real analogue signal (a
    # continuous force trace or the vibration motors themselves) --
    # there is no keyboard-equivalent play for any of them, by design
    # (see each mode's docstring). On a keyboard-only source, picking
    # one used to run setup and the GET READY countdown all the way to
    # the mode's own first-tick refusal, leaving an abandoned session
    # folder behind with zero trial rows and no warning before the
    # click (audit finding #111). Badged on the card instead.
    NEEDS_HARDWARE = set(HARDWARE_MODES)
    # Per-mode accent colours. The vertical strip on the left of each
    # card uses these, plus the icon takes the same colour as a subtle
    # repeated cue.
    MODE_ACCENTS = {
        "adaptive": (16, 185, 129),   # emerald green - "growth"
        "classic":  (99, 102, 241),   # indigo - "steady, structured"
        "rhythm":   (168, 85, 247),   # purple - "music"
        # Mirror gets a teal / cyan so the four cards form a clear
        # colour ladder (green -> indigo -> purple -> teal) without
        # overlapping any of the lane-tile finger pastels.
        "mirror":   (20, 184, 166),   # teal - "synchronised hands"
        "reaction": (239, 68, 68),    # red - "speed"
        "pattern":  (245, 158, 11),   # amber - "a path forming"
        "chords":   (14, 165, 233),   # sky blue - "keys together"
        "syllables": (236, 72, 153),  # pink - "language, playful"
        "force_pilot": (132, 204, 22),  # lime - "altitude, lift"
        # Orange for the buzz: warm and tactile, and the only strong
        # orange on the grid so the card reads distinct.
        "buzz_hunt": (249, 115, 22),
        # Indigo for Echo: classic's retired colour returns to the
        # grid, and nothing else on it sits between the sky blue and
        # the purple, so the card reads distinct.
        "echo": (99, 102, 241),
    }

    # Game select is the session hub, so the header gives its subtitle
    # line over to the session strip: "every game comes back here"
    # was a promise, the strip is the evidence. The grid drops to
    # GRID_TOP to make the room. Ten cards need five rows; the cards
    # keep the 86 px height and 6 px gap sized for the six-row grid
    # they used to fill (five rows end at 642, the bottom buttons sit
    # at 742), because 86 is the floor for a card that still fits a
    # two-line description at the shared type sizes and a taller card
    # would only add empty pastel.
    STRIP_TOP = 132
    GRID_TOP = 188

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.buttons: list[Button] = []
        cx = engine.layout.width // 2
        # A two-column grid, filled left to right so the reading order
        # matches the MODES order. Sized for TEN cards (five rows).
        # Card height 86 is the minimum that still holds a title plus
        # a two-line description at the shared type sizes; the layout
        # test renders every description and fails below that.
        card_w = 590
        card_h = 86
        gap = 6
        for i, (key, _title, _desc) in enumerate(self.MODES):
            col = i % 2
            row = i // 2
            x0 = cx - card_w - gap // 2 + col * (card_w + gap)
            y = self.GRID_TOP + row * (card_h + gap)
            # Each card gets a softened tint of its own mode accent
            # as its rest fill, so the row reads as three clearly
            # different cards instead of three identical muted-grey
            # slabs. Lightening factor 0.55 keeps enough chroma for
            # the colour identity to be obvious while staying light
            # enough that dark foreground text on top still hits
            # WCAG AA contrast. Earlier attempts at 0.78 came out so
            # pale that the cards looked the same washed white that
            # prompted this fix.
            accent = self.MODE_ACCENTS.get(key, self.theme.accent)
            pastel = tuple(
                int(c + (255 - c) * 0.55) for c in accent
            )
            # Button label is empty - the title + icon + description
            # are rendered manually so we get a cleaner icon-left,
            # text-right layout than Button's auto-centred label.
            self.buttons.append(Button(
                pygame.Rect(x0, y, card_w, card_h),
                "", lambda k=key: self._pick(k),
                self.theme, self.layout,
                font_pt=FONT_H2 + 2,
                colour=pastel,
            ))
        # Leaving game select for the login screen is what ends the
        # session, so the button says so and routes through the
        # engine's End-session dialog rather than jumping straight
        # out. Mid-game quits land back HERE, never on the login.
        # The button row sits at height - 58 with a slightly shorter
        # button since the six-row grid took the old row's space; the
        # layout test keeps the two apart.
        self.back_btn = Button(
            pygame.Rect(40, engine.layout.height - 58, 180,
                        BUTTON_H - 16),
            "End session", engine.request_end_session,
            self.theme, self.layout,
        )
        # Calibration on demand. Logging in already put every
        # attached hand through the flow once; this is for the times a
        # therapist wants it again (the strap moved, a different
        # patient's hand, a press that stopped registering) without
        # ending the session. Re-running re-captures and re-applies
        # through the same path.
        self.cal_btn = Button(
            pygame.Rect(236, engine.layout.height - 58, 200,
                        BUTTON_H - 16),
            "Calibrate", self._calibrate,
            self.theme, self.layout,
        )
        # Set when the button is pressed on a rig that cannot be
        # calibrated; drawn under the button instead of silently
        # doing nothing.
        self.cal_note = ""
        # PLAY ALL: one press runs the fixed block order for this
        # participant (game/battery.py, the study battery; the button
        # says "play all" because that is what it does, and the study
        # wording stays in the config and the docs), stopping at
        # results between blocks. Sits right of the calibrate note's
        # room so the two never overlap on a keyboard rig. Skip only
        # shows while a step is pending, for a block that cannot be
        # run.
        self.battery_btn = Button(
            pygame.Rect(720, engine.layout.height - 58, 300,
                        BUTTON_H - 16),
            "PLAY ALL  (A)", self._battery,
            self.theme, self.layout,
        )
        self.skip_btn = Button(
            pygame.Rect(1036, engine.layout.height - 58, 150,
                        BUTTON_H - 16),
            "Skip step  (S)", self._skip_step,
            self.theme, self.layout,
        )
        self.battery_note = ""
        # Menu-music mute, top-left, the same pill as the login screen.
        self.mute_btn = MuteButton(
            engine, pygame.Rect(28, 26, MuteButton.W, MuteButton.H))

    CAL_UNAVAILABLE = "Calibration needs the sensor hardware"

    def _battery_pending(self) -> bool:
        try:
            return self.engine.pending_protocol_step() is not None
        except Exception:
            return False

    def _battery_state(self) -> tuple[bool, str, str]:
        """(available, label, reason) for the battery button."""
        try:
            progress = self.engine.battery_progress()
        except Exception:
            progress = None
        if isinstance(progress, dict):
            if progress.get("finished"):
                return False, "PLAY ALL DONE", ""
            return (True, f"PLAY ALL {progress['done']}/"
                          f"{progress['of']}  (A)", "")
        try:
            ok, reason = self.engine.battery_available()
        except Exception as e:
            ok, reason = False, str(e)
        return ok, "PLAY ALL  (A)", ("" if ok else reason)

    def _battery(self) -> None:
        ok, _label, reason = self._battery_state()
        if not ok:
            self.battery_note = reason
            return
        self.battery_note = ""
        if not self.engine.start_battery():
            self.battery_note = "Play all could not start"

    def _skip_step(self) -> None:
        if self._battery_pending():
            self.engine.skip_protocol_step()

    def _can_calibrate(self) -> bool:
        try:
            return bool(self.engine.calibratable_hands())
        except Exception:
            return False

    def _calibrate(self) -> None:
        """Open the quick flow, or say why it cannot run. A keyboard
        session has no force signal to measure, so the button explains
        itself instead of opening a screen whose only exit is Skip."""
        if not self.engine.start_manual_calibration():
            self.cal_note = self.CAL_UNAVAILABLE

    def _second_board_missing(self) -> bool:
        """True when a hardware source cannot serve both hands (one
        board attached). Mirror is bilateral-only, and with one board
        the left lanes can never fire from the sensors: every trial
        missed on the left and the block recorded as total bimanual
        failure of the patient. The rule itself lives on the engine so
        the cards, the hand picker and the NEXT UP button all read one
        answer."""
        return self.engine.second_board_missing()

    def _pick(self, mode_key: str) -> None:
        # Mirror is bilateral-only, so it skips the hand-pick step and
        # goes straight into the block through the shared start path
        # (which sets both hands and rebuilds the lanes, the same as
        # every other game). Everything else still asks which hand
        # first.
        if mode_key == "mirror":
            self.engine.begin_game("mirror")
            return
        self.engine.cfg.data.setdefault("game", {})["mode"] = mode_key
        self.engine.show_setup()

    # Number-key shortcuts for the ten cards, 1-9 then 0, matching
    # reading order (audit finding #113: mode select was mouse-click
    # only, so a keyboard-only session could not get past this screen
    # at all). Echo also answers to its initial, E, below: it was the
    # eleventh card before Lighthouse was retired and the key stays so
    # a hand that learned it still works.
    _DIGIT_KEYS = (
        pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
        pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0,
    )

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.mute_btn.handle_event(e):
            return
        controls = self.buttons + [self.back_btn, self.cal_btn,
                                   self.battery_btn]
        if self._battery_pending():
            controls.append(self.skip_btn)
        for b in controls:
            b.handle_event(e)
        if e.type == pygame.KEYDOWN and e.key in self._DIGIT_KEYS:
            idx = self._DIGIT_KEYS.index(e.key)
            if idx < len(self.MODES):
                self._pick(self.MODES[idx][0])
        # E for Echo, kept alongside its digit.
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_e:
            self._pick("echo")
        # C for calibrate, so the hub is fully keyboard-drivable: the
        # digits cover the ten cards and Esc raises the End-session
        # dialog, which left the new button as the only mouse-only
        # control on the screen.
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_c:
            self._calibrate()
        # A starts or continues PLAY ALL, S skips its pending step, so
        # the study path is keyboard-only too.
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_a:
            self._battery()
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_s:
            self._skip_step()

    # Descriptions render as up to two wrapped lines under the title.
    # The cap is part of the card contract: a description that needs a
    # third line would silently vanish, so the layout test renders
    # every card in both columns and fails if any wraps past two.
    DESC_MAX_LINES = 2

    @staticmethod
    def _wrap_desc(font: pygame.font.Font, text: str,
                   max_w: int) -> list[str]:
        """Greedy word wrap. Returns every line the text needs; the
        card draws only the first DESC_MAX_LINES, and the layout test
        asserts no description ever needs more."""
        lines: list[str] = []
        line = ""
        for word in text.split():
            trial = f"{line} {word}".strip()
            if line and font.size(trial)[0] > max_w:
                lines.append(line)
                line = word
            else:
                line = trial
        if line:
            lines.append(line)
        return lines

    @staticmethod
    def _draw_mode_icon(surf: pygame.Surface, kind: str,
                         cx: int, cy: int, size: int,
                         colour: tuple[int, int, int]) -> None:
        """Tiny inline icon for each mode card. Drawn from primitives
        so no extra asset is needed:
          - adaptive: rising bar-chart (three bars of increasing height)
          - classic: metronome (3 dots in a line)
          - rhythm: musical eighth note (stem + filled head + flag)
        """
        if kind == "adaptive":
            # Three bars, ascending heights, sitting on a baseline.
            bar_w = size // 5
            gap_w = size // 10
            base_y = cy + size // 2
            heights = (size // 3, size * 2 // 3, size)
            total_w = bar_w * 3 + gap_w * 2
            x = cx - total_w // 2
            for h in heights:
                bar = pygame.Rect(x, base_y - h, bar_w, h)
                pygame.draw.rect(surf, colour, bar, border_radius=2)
                x += bar_w + gap_w
            # Baseline line.
            pygame.draw.line(surf, colour,
                              (cx - total_w // 2 - 2, base_y),
                              (cx + total_w // 2 + 2, base_y), 2)
        elif kind == "classic":
            # Metronome arc + three pendulum dots underneath.
            arc_rect = pygame.Rect(0, 0, size, size // 2)
            arc_rect.center = (cx, cy - size // 6)
            pygame.draw.arc(surf, colour, arc_rect, 3.14, 2 * 3.14, 3)
            dot_r = size // 12
            dot_gap = size // 5
            for i, dx in enumerate((-dot_gap, 0, dot_gap)):
                pygame.draw.circle(surf, colour,
                                    (cx + dx, cy + size // 4), dot_r)
        elif kind == "rhythm":
            # Eighth note: oval head + vertical stem + flag.
            head_w = size // 2
            head_h = size // 3
            head_rect = pygame.Rect(0, 0, head_w, head_h)
            head_rect.center = (cx - size // 8, cy + size // 4)
            pygame.draw.ellipse(surf, colour, head_rect)
            stem_top = cy - size // 2
            stem_bottom = head_rect.centery
            stem_x = head_rect.right - 3
            pygame.draw.line(surf, colour,
                              (stem_x, stem_top),
                              (stem_x, stem_bottom), 3)
            # Flag curving off the top of the stem.
            flag_pts = [
                (stem_x, stem_top),
                (stem_x + size // 3, stem_top + size // 6),
                (stem_x + size // 4, stem_top + size // 3),
                (stem_x, stem_top + size // 5),
            ]
            pygame.draw.polygon(surf, colour, flag_pts)
        elif kind == "reaction":
            # Lightning bolt: speed.
            s = size
            pts = [(cx + s // 6, cy - s // 2), (cx - s // 4, cy + s // 12),
                   (cx - s // 24, cy + s // 12), (cx - s // 6, cy + s // 2),
                   (cx + s // 4, cy - s // 24), (cx + s // 24, cy - s // 24)]
            pygame.draw.polygon(surf, colour, pts)
        elif kind == "pattern":
            # Four dots joined by a path: a sequence forming.
            r = max(3, size // 10)
            pts = [(cx - size // 2 + r, cy + size // 4),
                   (cx - size // 6, cy - size // 4),
                   (cx + size // 6, cy + size // 6),
                   (cx + size // 2 - r, cy - size // 3)]
            for a, b2 in zip(pts, pts[1:]):
                pygame.draw.line(surf, colour, a, b2, 3)
            for pt in pts:
                pygame.draw.circle(surf, colour, pt, r)
        elif kind == "chords":
            # Three close vertical bars pressed at once, like piano keys
            # going down together.
            bar_w = max(4, size // 6)
            gap2 = max(3, size // 10)
            x = cx - (bar_w * 3 + gap2 * 2) // 2
            for dy in (size // 8, -size // 8, size // 8):
                bar = pygame.Rect(x, cy - size // 3 + dy,
                                  bar_w, size * 2 // 3)
                pygame.draw.rect(surf, colour, bar, border_radius=3)
                x += bar_w + gap2
        elif kind == "syllables":
            # A word split into blocks with a dot between: syllable
            # boundaries made visible.
            blk_h = size // 3
            blk_w = size // 3
            y0 = cy - blk_h // 2
            pygame.draw.rect(surf, colour,
                             pygame.Rect(cx - size // 2, y0, blk_w, blk_h),
                             border_radius=4)
            pygame.draw.circle(surf, colour, (cx, cy), max(3, size // 12))
            pygame.draw.rect(surf, colour,
                             pygame.Rect(cx + size // 6, y0, blk_w, blk_h),
                             border_radius=4)
        elif kind == "mirror":
            # Two mirrored circles connected by a thin line, reading
            # as "two hands moving as one". I went with circles + a
            # bridge over a literal hand outline because the mode-
            # select cards already carry the pan_tool icon elsewhere
            # and a second hand graphic looked too busy.
            r = size // 5
            bridge_w = size // 2
            left_c = (cx - bridge_w // 2 - r, cy)
            right_c = (cx + bridge_w // 2 + r, cy)
            # Connecting bar through the middle.
            pygame.draw.line(surf, colour,
                              left_c, right_c, 3)
            # Each "hand" disc with a thin inner ring so the icon
            # reads at distance even at small sizes.
            for c in (left_c, right_c):
                pygame.draw.circle(surf, colour, c, r)
                pygame.draw.circle(surf, colour, c, r + 4, 2)
        elif kind == "force_pilot":
            # A craft between two corridor walls: force as altitude.
            off = size // 3
            for sign in (-1, 1):
                pts = [(cx - size // 2, cy + sign * off),
                       (cx - size // 8, cy + sign * (off + size // 9)),
                       (cx + size // 4, cy + sign * (off - size // 9)),
                       (cx + size // 2, cy + sign * off)]
                pygame.draw.lines(surf, colour, False, pts, 3)
            tri = [(cx - size // 5, cy - size // 8),
                   (cx - size // 5, cy + size // 8),
                   (cx + size // 4, cy)]
            pygame.draw.polygon(surf, colour, tri)
        elif kind == "buzz_hunt":
            # A dot with vibration ripples either side: the buzz as
            # the thing itself, not a decoration on a tile.
            pygame.draw.circle(surf, colour, (cx, cy), size // 6)
            for i, r in enumerate((size // 3, size // 2)):
                arc = pygame.Rect(0, 0, r * 2, r * 2)
                arc.center = (cx, cy)
                span = 0.9 - i * 0.15
                pygame.draw.arc(surf, colour, arc, -span, span, 2)
                pygame.draw.arc(surf, colour, arc, 3.14159 - span,
                                3.14159 + span, 2)
        elif kind == "echo":
            # Three tiles fading left to right: a sequence just
            # played, hanging in memory. Filled, then outlined twice,
            # so the repeat reads as an echo rather than a bar chart.
            blk = size // 3
            y0 = cy - blk // 2
            x = cx - size // 2
            gap3 = size // 8
            pygame.draw.rect(surf, colour,
                             pygame.Rect(x, y0, blk, blk),
                             border_radius=4)
            pygame.draw.rect(surf, colour,
                             pygame.Rect(x + blk + gap3, y0, blk, blk),
                             2, border_radius=4)
            pygame.draw.rect(surf, colour,
                             pygame.Rect(x + 2 * (blk + gap3), y0,
                                         blk, blk),
                             1, border_radius=4)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        # No subtitle: the strip below says what the old line claimed
        # ("every game comes back here"), and says it with the games
        # actually played.
        _draw_header(surf, "Pick a game", "", self.theme, self.layout)
        draw_session_strip(
            surf,
            pygame.Rect(40, self.STRIP_TOP, self.layout.width - 80,
                        SESSION_STRIP_H),
            self.engine, self.theme, self.layout,
            show_flourish=True,
        )
        try:
            played = set(self.engine.session_modes_played())
        except Exception:
            played = set()
        # Only relevant with no live sensor source: a serial device
        # gives every mode real input, so there is nothing to warn
        # about. On a keyboard-only fallback, Force Pilot and Buzz
        # Hunt cannot be played at all (finding #111).
        src = getattr(self.engine, "source", None)
        no_hardware = not getattr(src, "provides_samples", True)
        # Read once per frame, not once per card: it stats a file.
        riff_name = ""
        try:
            line = self.engine.pattern_plan_headline()
            riff_name = line.split(" (", 1)[0] if line else ""
        except Exception:
            riff_name = ""
        for b, (key, title, desc) in zip(self.buttons, self.MODES):
            b.draw(surf)
            accent = self.MODE_ACCENTS.get(key, self.theme.accent)
            # Vertical accent strip on the left edge of the card. Reads
            # as a colour code for the mode without overpowering the
            # button's default fill. Slightly inset so the rounded
            # corner still feels rounded behind it.
            strip = pygame.Rect(b.rect.x + 8, b.rect.y + 14,
                                 6, b.rect.h - 28)
            pygame.draw.rect(surf, accent, strip, border_radius=3)
            # Card fill is now a light pastel of the mode accent, so
            # dark theme.foreground reads with strong contrast against
            # any of the three. Description follows in the same dark
            # tone (no longer dropping to muted on rest) so the body
            # text actually reads at a glance rather than fading
            # against the card. Hover doesn't need to flip the colour
            # because the pastel fill stays light in both states.
            fg = self.theme.foreground
            muted_fg = self.theme.foreground
            # Mode icon, in the mode's accent colour so the colour cue
            # repeats. Sized to the ten-card row height.
            icon_size = 40
            icon_cx = b.rect.x + 50
            icon_cy = b.rect.centery
            self._draw_mode_icon(surf, key, icon_cx, icon_cy,
                                  icon_size, accent)
            # Title rendered bold via SysFont so it pops as the card's
            # primary affordance. Description follows in regular
            # weight, wrapped to at most two lines inside the card
            # (the what-you-do + what-it-trains line is longer than
            # one row of FONT_BODY, and clipping it would eat the
            # claim the card exists to make).
            text_x = b.rect.x + 92
            title_pt = int((FONT_H2 + 2) * self.layout.font_scale)
            title_font = make_font(title_pt, bold=True)
            title_surf = title_font.render(title, True, fg)
            surf.blit(title_surf,
                       title_surf.get_rect(
                           midleft=(text_x, b.rect.y + 26)))
            desc_font = self.layout.font(FONT_SMALL + 2)
            desc_max_w = b.rect.right - 14 - text_x
            for li, line in enumerate(self._wrap_desc(
                    desc_font, desc, desc_max_w)[:self.DESC_MAX_LINES]):
                draw_text(surf, line,
                          (text_x, b.rect.y + 44 + li * 20),
                          self.theme, self.layout, pt=FONT_SMALL + 2,
                          centre=False, colour=muted_fg)
            if key == "pattern" and riff_name:
                # A researcher's sequence file is running, so this card
                # is not the shipped game any more and the RA should
                # see that before pressing it. "riff" and not
                # "sequence": the patient reads this screen too, and
                # naming a sequence is the one thing this mode must
                # never do (Boyd and Winstein; see modes/pattern.py).
                tag_font = self.layout.font(FONT_SMALL)
                # Top-right, where the hardware badges sit. Under the
                # card it would land on the second line of the
                # description, which wraps on this card.
                tag = _fit_text(f"custom riff: {riff_name}", tag_font, 260)
                draw_text(surf, tag,
                          (b.rect.right - 14 - tag_font.size(tag)[0],
                           b.rect.y + 14),
                          self.theme, self.layout, pt=FONT_SMALL,
                          centre=False, colour=self.theme.foreground)
            if no_hardware and key in self.NEEDS_HARDWARE:
                # Said up front, before the click: these three cannot
                # run on a keyboard-only source at all (every stage
                # needs the sensor pads or the vibration motors), so
                # picking one used to run all the way to the mode's
                # own refusal screen with nothing said here first.
                badge = "NEEDS SENSOR HARDWARE"
                badge_font = self.layout.font(FONT_SMALL)
                badge_w = badge_font.size(badge)[0]
                draw_text(surf, badge,
                          (b.rect.right - 14 - badge_w, b.rect.y + 14),
                          self.theme, self.layout, pt=FONT_SMALL,
                          centre=False, colour=self.theme.error)
            if key == "mirror" and self._second_board_missing():
                # Same up-front rule for mirror on a one-board rig:
                # bilateral-only, so with one board the second hand's
                # lanes can never fire and the pick is refused.
                badge = "NEEDS SECOND BOARD"
                badge_font = self.layout.font(FONT_SMALL)
                badge_w = badge_font.size(badge)[0]
                draw_text(surf, badge,
                          (b.rect.right - 14 - badge_w, b.rect.y + 14),
                          self.theme, self.layout, pt=FONT_SMALL,
                          centre=False, colour=self.theme.error)
            elif key in played and not (
                    no_hardware and key in self.NEEDS_HARDWARE):
                # A tick, not a lock: a played mode is still one press
                # away, the mark only says the session has covered it.
                # Small and in the mode's own accent so it reads as
                # part of the card rather than an alert. Never drawn
                # over a badge: both live in the card's top-right.
                self._draw_done_tick(surf, b.rect.right - 26,
                                     b.rect.y + 22, accent)
        self.back_btn.draw(surf)
        # Said before the click, the same rule the cards' badges
        # follow: on a keyboard rig there is nothing to calibrate, so
        # the button reads inactive and the reason sits beside it
        # rather than waiting for a press that does nothing.
        note = self.cal_note
        if not self._can_calibrate():
            note = self.CAL_UNAVAILABLE
            self.cal_btn.colour = tuple(
                int(c + (255 - c) * 0.55) for c in self.theme.muted)
        else:
            self.cal_btn.colour = None
        self.cal_btn.draw(surf)
        if note:
            draw_text(surf, note,
                      (self.cal_btn.rect.right + 18,
                       self.cal_btn.rect.centery - 8),
                      self.theme, self.layout, pt=FONT_SMALL,
                      centre=False, colour=self.theme.muted)
        # Battery button: label follows the battery's state, and an
        # unavailable battery reads inactive with its reason beside
        # it, the same rule the calibrate button follows.
        ok, label, reason = self._battery_state()
        self.battery_btn.label = label
        if ok:
            self.battery_btn.colour = None
            self.battery_btn.primary = self._battery_pending()
        else:
            self.battery_btn.primary = False
            self.battery_btn.colour = tuple(
                int(c + (255 - c) * 0.55) for c in self.theme.muted)
        self.battery_btn.draw(surf)
        if self._battery_pending():
            self.skip_btn.draw(surf)
        else:
            bnote = self.battery_note or reason
            if bnote:
                draw_text(surf, bnote,
                          (self.battery_btn.rect.right + 16,
                           self.battery_btn.rect.centery - 8),
                          self.theme, self.layout, pt=FONT_SMALL,
                          centre=False, colour=self.theme.muted)
        self.mute_btn.draw(surf, self.theme, self.layout)

    @staticmethod
    def _draw_done_tick(surf: pygame.Surface, cx: int, cy: int,
                        colour: tuple[int, int, int]) -> None:
        """Small ringed tick marking a mode already played this
        session."""
        pygame.draw.circle(surf, colour, (cx, cy), 11, 2)
        pygame.draw.lines(surf, colour, False,
                          [(cx - 5, cy), (cx - 1, cy + 4),
                           (cx + 6, cy - 5)], 2)


class SetupScreen(Screen):
    """Hand picker. The participant name was already set on the title
    screen and is reused for every block this app session, so this
    screen has nothing to type, just three big buttons."""

    HANDS = [
        ("left",  "Left hand",  "4 fingers, index to little"),
        ("right", "Right hand", "4 fingers, index to little"),
        ("both",  "Both hands", "8 fingers, bilateral training"),
    ]

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        cx = engine.layout.width // 2

        # Pace slider for classic mode ONLY (the game.mode == "classic"
        # gates in handle_event and draw enforce that). It must never
        # show for reaction: reaction's whole design is that the wait
        # before each stimulus is randomised so the patient cannot time
        # it, and a visible pace knob would claim the opposite. The
        # other modes set their own cadence (adaptive/mirror from the
        # engine BPM, rhythm from the song). Pre-fill from the config
        # so a therapist who's tweaked the value in YAML sees their
        # choice. Range 0.4 s to 3.0 s in 0.1 s steps - matches the
        # slowest the adaptive engine can crawl (~3 s per stim) up to a
        # snappy pace for stronger patients.
        initial = float(engine.cfg.get("game.trigger_interval_s", 1.2))
        slider_w = 520
        self.pace_slider = Slider(
            pygame.Rect(cx - slider_w // 2, 240, slider_w, 30),
            self.theme, self.layout,
            min_value=0.4, max_value=3.0,
            initial=initial, step=0.1,
            label="CLASSIC PACE  (seconds between stimuli)",
            value_format="{:.1f} s",
        )

        self.buttons: list[Button] = []
        button_w = 290
        button_gap = 32
        button_total_w = button_w * 3 + button_gap * 2
        start_x = cx - button_total_w // 2
        # Buttons pulled up from y=360 to fill the dead space that used
        # to sit between the header and the row. With the slider stacked
        # above for classic mode, the slider stays at y=240 (ending ~270)
        # and the buttons start at y=300 with a small breathing gap.
        button_y = 300
        for i, (key, label, _desc) in enumerate(self.HANDS):
            r = pygame.Rect(start_x + i * (button_w + button_gap), button_y,
                            button_w, 220)
            # Button label is empty - we render the hand icon + the
            # label text ourselves so the layout reads as icon-on-top,
            # text-below rather than Button's auto-centred text. The
            # rect still gets the click + hover behaviour for free.
            self.buttons.append(Button(
                r, "", lambda k=key: self._pick(k),
                self.theme, self.layout,
                font_pt=FONT_H2,
                # No default selection - therapist makes an active pick.
            ))
            # Stash the real label on the button so draw() can render it
            # at the right spot without re-looking-up.
            self.buttons[-1]._real_label = label  # type: ignore[attr-defined]
        self.back_btn = Button(
            pygame.Rect(40, engine.layout.height - 90, 180, BUTTON_H - 10),
            "Back", engine.show_mode_select,
            self.theme, self.layout,
        )
        # Menu-music mute, top-left, the same pill as the hub.
        self.mute_btn = MuteButton(
            engine, pygame.Rect(28, 26, MuteButton.W, MuteButton.H))

    def _second_board_missing(self) -> bool:
        """Same rule as the mode-select mirror card: a hardware source
        that cannot serve both hands (one board) must not start a
        bilateral block, or the missing hand's lanes read constant
        zeros and every one of its trials records as an honest-looking
        patient miss. Answered by the engine so every screen agrees."""
        return self.engine.second_board_missing()

    def _pick(self, hand: str) -> None:
        # Participant name was already pushed into session/config by
        # the title screen so we don't touch it here. Everything after
        # the pace slider is the shared start path on the engine: hand
        # mode, detectors, lane strips, then the mode's own starter.
        # No calibration step hangs off this any more: the session
        # calibrated its hands at login.
        mode = self.engine.cfg.get("game.mode", "adaptive")
        if mode == "classic":
            # Persist the slider's chosen pace into the config so the
            # ClassicMode constructor reads it back when the block starts.
            self.engine.cfg.data.setdefault("game", {})[
                "trigger_interval_s"] = self.pace_slider.value
        self.engine.begin_game(mode, hand)

    # Keyboard shortcut for each hand card, first letter of its key
    # (audit finding #113: this screen was mouse-click only, so a
    # keyboard-only session could not get past hand-pick at all).
    _HAND_KEYS = {
        pygame.K_l: "left", pygame.K_r: "right", pygame.K_b: "both",
    }

    def handle_event(self, e: pygame.event.Event) -> None:
        if self.mute_btn.handle_event(e):
            return
        # Slider first so a click on the knob isn't intercepted by an
        # adjacent button hit-test. Only let it respond when classic
        # mode is the active pick.
        if self.engine.cfg.get("game.mode") == "classic":
            self.pace_slider.handle_event(e)
        for b in self.buttons + [self.back_btn]:
            b.handle_event(e)
        if e.type == pygame.KEYDOWN and e.key in self._HAND_KEYS:
            self._pick(self._HAND_KEYS[e.key])

    def _button_glyph_colour(self, b: Button) -> tuple[int, int, int]:
        """Pick a glyph colour that contrasts with whatever fill the
        Button just rendered. Mirrors Button.draw's own text-colour
        decision so the hand icon never goes invisible on hover."""
        if b.colour is not None:
            base = b.colour
        elif b.primary:
            base = self.theme.accent
        else:
            base = self.theme.muted if not b.hover else self.theme.accent
        avg = sum(base) / 3
        return self.theme.background if avg > 140 else (255, 255, 255)

    @staticmethod
    def _hand_icon_path() -> str:
        """Absolute path to the bundled Material Icons pan_tool PNG.
        Works for both source runs and PyInstaller frozen builds via
        Config's resolve_path helper."""
        from ..config import PROJECT_ROOT
        return str(PROJECT_ROOT / "assets" / "icons" / "pan_tool.png")

    @staticmethod
    def _draw_hand_glyph(surf: pygame.Surface, cx: int, cy: int,
                          kind: str, h: int,
                          colour: tuple[int, int, int]) -> None:
        """Stylised palm-down hand, rendered from the Material Icons
        pan_tool PNG (Apache 2.0). The source icon already shows a
        hand with thumb on the LEFT of the frame, which matches our
        "right hand" convention; left hand is the same icon flipped
        horizontally. `kind` is 'left' / 'right' / 'both'."""
        from .widgets import load_icon
        path = SetupScreen._hand_icon_path()
        if kind == "both":
            sub_h = int(h * 0.90)
            offset = int(h * 0.42)
            left_icon = load_icon(path, sub_h, tint=colour, flip_x=True)
            right_icon = load_icon(path, sub_h, tint=colour, flip_x=False)
            if left_icon is not None:
                surf.blit(left_icon,
                           left_icon.get_rect(center=(cx - offset, cy)))
            if right_icon is not None:
                surf.blit(right_icon,
                           right_icon.get_rect(center=(cx + offset, cy)))
            return
        flip = (kind == "left")
        icon = load_icon(path, h, tint=colour, flip_x=flip)
        if icon is not None:
            surf.blit(icon, icon.get_rect(center=(cx, cy)))

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        # Friendly header: tells the patient + therapist whose session
        # this is, then asks the only question on the screen. Less abrupt
        # than the bare "WHICH HAND?" we had before.
        name = self.engine.session.participant or "NA"
        greeting = (f"Welcome, {name}." if name not in ("NA", "")
                     else "Welcome.")
        # "this game", not "this session": the hand is picked fresh on
        # every pass through setup, and a session can mix games and
        # hands. Saying session here implied the pick was locked in.
        _draw_header(surf, "Choose your hand",
                     f"{greeting}  Which hand will you train this game?",
                     self.theme, self.layout)
        # Classic mode gets a pace slider above the hand buttons so the
        # therapist can tune trigger_interval_s without editing YAML.
        # Strictly classic-only: reaction randomises its wait on
        # purpose, so it must not offer a pace control (see __init__).
        if self.engine.cfg.get("game.mode") == "classic":
            self.pace_slider.draw(surf)
        # A Muscle Memory riff file, when one is loaded and this pick is
        # for that mode. Read once per frame: it stats a file.
        riff_line = ""
        riff_blocked: set[str] = set()
        riff_hand_tag = ""
        if self.engine.cfg.get("game.mode") == "pattern":
            try:
                plan, _reason = self.engine._pattern_plan()
            except Exception:
                plan = None
            if plan is not None:
                riff_line = f"Riff file: {plan.headline()}"
                if plan.hands == "both":
                    riff_blocked = {"left", "right"}
                    riff_hand_tag = "RIFF FILE NEEDS BOTH HANDS"
                else:
                    riff_blocked = {"both"}
                    riff_hand_tag = "RIFF FILE IS FOR ONE HAND"
        for b, (key, label, desc) in zip(self.buttons, self.HANDS):
            b.draw(surf)
            # Hand icon centred in the upper ~60% of the button.
            glyph_h = 120
            glyph_cy = b.rect.top + glyph_h // 2 + 18
            self._draw_hand_glyph(
                surf, b.rect.centerx, glyph_cy, key, glyph_h,
                self._button_glyph_colour(b),
            )
            # Real label below the icon, inside the button rect.
            draw_text(surf, label,
                      (b.rect.centerx, b.rect.bottom - 28),
                      self.theme, self.layout, pt=FONT_H2,
                      centre=True,
                      colour=self._button_glyph_colour(b))
            # Description below the button.
            draw_text(surf, desc,
                      (b.rect.centerx, b.rect.bottom + 22),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.muted)
            if key == "both" and self._second_board_missing():
                # Said before the click: one board cannot serve both
                # hands, so a bilateral pick is refused rather than
                # recording the missing hand's silence as misses.
                draw_text(surf, "NEEDS SECOND BOARD",
                          (b.rect.centerx, b.rect.top - 18),
                          self.theme, self.layout, pt=FONT_SMALL,
                          centre=True, colour=self.theme.error)
            if key in riff_blocked:
                # A loaded Muscle Memory riff file is for one hand or
                # for both, and Patterns refuses the mismatch rather
                # than remapping the material. Said here, before the
                # click, for the same reason the second-board warning
                # is: a refusal after the click is a dead end.
                draw_text(surf, riff_hand_tag,
                          (b.rect.centerx, b.rect.top - 18),
                          self.theme, self.layout, pt=FONT_SMALL,
                          centre=True, colour=self.theme.warning)
        if riff_line:
            draw_text(surf, riff_line,
                      (self.layout.width // 2, self.buttons[0].rect.top - 44),
                      self.theme, self.layout, pt=FONT_SMALL + 2,
                      centre=True, colour=self.theme.muted)
        refusal = (getattr(self.engine, "pattern_refusal", "")
                   if self.engine.cfg.get("game.mode") == "pattern" else "")
        if refusal:
            draw_text(surf, refusal,
                      (self.layout.width // 2,
                       self.buttons[0].rect.bottom + 56),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=True, colour=self.theme.warning)
        self.back_btn.draw(surf)
        self.mute_btn.draw(surf, self.theme, self.layout)


class GameplayScreen(Screen):
    """Classic + Adaptive view. Big score top-centre, lane strips, hit popups."""

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.message = ""
        self.message_until = 0.0
        # How the message line is tinted. Modes tag their messages so a
        # "NEW BEST" lands gold, a "Too soon" lands amber, and a plain
        # instruction stays neutral. `_message_born` drives the short
        # pop-in so a fresh message visibly arrives instead of just
        # replacing the old text between frames.
        self.message_kind = "info"
        self._message_born = 0.0
        self.lanes: list[LaneStrip] = []
        # Floating "+3 Great!" popups go in here and fade themselves out.
        self._popups: list[FloatingText] = []
        # Stim ignition ring. When a lane goes active (the arm moment)
        # an expanding outline fires once around that tile so the
        # stimulus lands hard, which matters most in reaction mode
        # where the whole trial is "respond to this instant". Keyed by
        # rising edge of ls.active, so with cue.show_target off the
        # edge never happens and nothing on screen names the finger.
        self._prev_active: dict[int, bool] = {}
        self._ignitions: list[tuple[int, float]] = []
        # Reaction's static stage. From the frame the mode arms a wait
        # to a beat after the response, every number the HUD draws is
        # read out of this snapshot instead of live off the engine, so
        # the frame cannot move while an EEG epoch is open. None means
        # not holding; see _update_reaction_hold.
        self._react_hold: dict | None = None
        self._react_hold_until = 0.0
        # Score pulse: when the score jumps we kick off a short scale-up
        # animation on the big number so the patient sees a real reaction.
        self._last_score_seen = 0
        self._score_pulse_t = 0.0
        # Keyboard-mode press tracker. The game modes consume KEYDOWN
        # for scoring, but the LANE STRIP visual wants a "currently
        # held" signal too so the tile lights up while the key is
        # down (not just on the discrete press event). We track keys
        # at the screen level and drive ls.is_pressed in update().
        self._held_keys: set[int] = set()
        # Pre-start countdown. When perf_counter() is below this value a
        # "GET READY" card is shown and the mode's update is held back so
        # no stim fires until the patient has had a moment to settle.
        # Zero means no countdown active. Set by start_countdown(), which
        # the engine calls when a cadence-mode block begins.
        self._countdown_until = 0.0
        # Full-screen dim behind the countdown card, built once and
        # reused (draw runs at 60 fps; no per-frame surface builds).
        self._dim_cache: pygame.Surface | None = None
        # Set per frame in draw(): True when the mode message chip took
        # the bottom band because a pair bracket owns the band above
        # the tiles. Anything else that parks in that slot reads it
        # so the two never land on top of each other.
        self._msg_in_bottom_band = False
        self.rebuild_lanes()

    # How much empty space sits between the two hand blocks in bilateral
    # mode. Big enough that the two hand groups read as clearly separate.
    HAND_BLOCK_GAP = 120

    def start_countdown(self, seconds: float) -> None:
        """Begin a pre-start countdown of `seconds`. While it runs the
        mode is frozen (no stim fires) and a GET READY card shows over
        the lanes. Called by the engine at the start of a classic /
        adaptive / mirror block."""
        self._countdown_until = time.perf_counter() + max(0.0, seconds)
        # A block start is a hard reset for transient chrome: a message
        # or popup left over from the previous block must not bleed
        # into the first seconds of this one.
        self.message = ""
        self.message_until = 0.0
        self._popups.clear()
        self._ignitions.clear()
        self._prev_active.clear()

    def _countdown_remaining(self) -> float:
        """Seconds left on the pre-start countdown, 0 when not counting."""
        return max(0.0, self._countdown_until - time.perf_counter())

    # Relative finger lengths as a fraction of the middle finger (the
    # longest). Indexed by within-hand finger number
    # (0=index, 1=middle, 2=ring, 3=little). Lane tile heights scale by
    # these so the row of tiles echoes the shape of a real hand: middle
    # tallest, pinky shortest. The idea is to help the patient make the
    # mental finger-to-tile connection without reading the label. Values
    # are rounded from standard hand-anthropometry finger-length data.
    # Rhythm mode does NOT use this (its falling notes need equal-height
    # lanes to line up).
    FINGER_LENGTH_RATIO = (0.92, 1.00, 0.96, 0.79)

    @classmethod
    def _finger_lane_rect(cls, x: int, base_top: int, w: int,
                          full_h: int, finger: int) -> pygame.Rect:
        """Rect for one finger lane, scaled to its relative length.

        All lanes share a common BOTTOM baseline (base_top + full_h),
        which is where the finger labels sit, so the labels read on one
        line. The TOP varies per finger so the tile heights fan out like
        fingertips. `finger` is the within-hand index (0=index..3=little);
        `full_h` is the height the longest finger (middle) would use.
        """
        ratio = cls.FINGER_LENGTH_RATIO[finger % 4]
        lane_h = int(full_h * ratio)
        baseline = base_top + full_h
        return pygame.Rect(x, baseline - lane_h, w, lane_h)

    def rebuild_lanes(self) -> None:
        """4 strips unilateral, 8 strips bilateral.

        Bilateral layout mirrors the patient: left hand on the LEFT side of
        the screen (little finger on the outer edge, index closest to
        centre, matching `a s d f` on a keyboard); right hand on the RIGHT
        side (index nearest centre, little on the outer edge, matching
        `j k l ;`).

        We keep `self.lanes[i].lane == i` so any lookup elsewhere that
        indexes by lane number still works. Only the per-lane rect moves.
        """
        self.lanes = []
        hand = self.engine.hand_mode
        if hand == "both":
            half_w = (self.layout.width - self.HAND_BLOCK_GAP) // 2
            block_w = half_w - 40
            gutter = 18
            n = 4
            w = (block_w - gutter * (n - 1)) // n
            y = 220
            h = self.layout.height - 360
            # Pre-compute the rect for each lane number, then append the
            # strips in lane-number order so self.lanes[i].lane == i.
            rects: dict[int, pygame.Rect] = {}
            # Left hand sits on the LEFT side. Reading left-to-right the
            # visual order is little, ring, middle, index (lanes 7,6,5,4).
            # Tile height scales by finger length: finger index for a
            # left-hand lane number L is (L - 4).
            left_x_start = 40
            for pos in range(n):
                lane_num = 7 - pos      # pos 0 -> 7, pos 3 -> 4
                rects[lane_num] = self._finger_lane_rect(
                    left_x_start + pos * (w + gutter), y, w, h,
                    finger=lane_num - 4,
                )
            # Right hand sits on the RIGHT side. Reading left-to-right the
            # visual order is index, middle, ring, little (lanes 0,1,2,3).
            right_x_start = half_w + self.HAND_BLOCK_GAP
            for pos in range(n):
                lane_num = pos          # pos 0 -> 0, pos 3 -> 3
                rects[lane_num] = self._finger_lane_rect(
                    right_x_start + pos * (w + gutter), y, w, h,
                    finger=lane_num,
                )
            for i in range(8):
                is_left = i >= 4
                # finger is the within-hand finger index (0=index, 3=little).
                finger = i - 4 if is_left else i
                ls = LaneStrip(
                    lane=i, rect=rects[i],
                    theme=self.theme, layout=self.layout,
                    hand="left" if is_left else "right",
                    finger=finger,
                )
                # Gameplay hides the hand strapline + 0/0 readout so the
                # lane reads as a clean tile. The icon top-left already
                # tells the patient which hand it is.
                ls.show_hand_label = False
                ls.show_value_readout = False
                self.lanes.append(ls)
        else:
            self._build_lane_block(hand, lane_offset=0, n=4,
                                    x_start=80,
                                    block_w=self.layout.width - 160)

    def _build_lane_block(self, hand: str, lane_offset: int, n: int,
                          x_start: int, block_w: int) -> None:
        """Lay out a single hand's lanes. For the LEFT hand we mirror the
        visual order so the little finger sits on the outer (left) edge
        and the index sits closest to the centre, matching how the left
        hand rests on a s d f."""
        gutter = 18
        w = (block_w - gutter * (n - 1)) // n
        y = 220
        h = self.layout.height - 360
        # Visual order of lane numbers across the block, left-to-right.
        if hand == "left":
            order = [n - 1 - i for i in range(n)]    # e.g. [3, 2, 1, 0]
        else:
            order = list(range(n))                    # [0, 1, 2, 3]
        # Pre-compute each lane's rect, then append in lane-number order so
        # self.lanes[i].lane == i for any downstream lookup-by-id code.
        # Tile height scales by finger length (lane_num doubles as the
        # within-hand finger index in the unilateral case).
        rects: dict[int, pygame.Rect] = {}
        for pos, lane_num in enumerate(order):
            rects[lane_num] = self._finger_lane_rect(
                x_start + pos * (w + gutter), y, w, h,
                finger=lane_num,
            )
        for i in range(n):
            ls = LaneStrip(
                lane=lane_offset + i,
                rect=rects[i],
                theme=self.theme, layout=self.layout,
                hand=hand,
                finger=i,
            )
            # Gameplay tile has no need for the hand strapline (the
            # hand icon already covers that) or the live 0/0 FSR
            # readout (only useful on the Diagnostics sensor check).
            ls.show_hand_label = False
            ls.show_value_readout = False
            self.lanes.append(ls)

    def flash_lane(self, lane: int, colour: tuple[int, int, int],
                   duration_s: float, now: float,
                   popup_text: str | None = None,
                   popup_glyph: str | None = None) -> None:
        for ls in self.lanes:
            if ls.lane == lane:
                ls.flash(colour, duration_s, now)
                # Lab style: one ring glyph per outcome instead of
                # words. Handled before the text path so the neutral
                # popup can never pick up a stale message. Always the
                # page ink, never the outcome colour: this glyph is
                # the feedback event the ERP is measured on, so the
                # only thing that may differ between outcomes is its
                # fill. The tile flash keeps its colour, as it always
                # did, and is a separate event.
                if popup_glyph:
                    self._spawn_popup(ls, self.theme.foreground, "",
                                       glyph=popup_glyph)
                    continue
                # Float a quick popup above the lane that just scored.
                # `popup_text` (the outcome label) wins over whatever
                # message happens to be live, so the popup always
                # describes THIS trial. Reaction skips the popup: its
                # RT chip is the trial feedback (bigger there, tinted
                # by outcome), and the rising tier text crossed the
                # chip at exactly the moment the patient should read
                # the number (before/after screenshots, upgrade
                # folder). The tile flash stays.
                if getattr(self.engine, "current_block", "") != "reaction":
                    self._spawn_popup(ls, colour,
                                      popup_text or self.message)

    def _spawn_popup(self, lane: LaneStrip,
                      colour: tuple[int, int, int],
                      text: str, glyph: str | None = None) -> None:
        if not text and not glyph:
            return
        # Points appended to the label make the feedback feel chunky and
        # game-like rather than clinical only.
        x = lane.rect.centerx
        # Above the tile, on the page background. Inside the tile the
        # popup landed on the outcome flash in its own colour (green
        # text on a green tile) and vanished.
        y = lane.rect.top - 28
        self._popups.append(FloatingText(text, (x, y), colour, font_pt=42,
                                          glyph=glyph))

    def set_message(self, text: str, duration_s: float,
                    kind: str = "info") -> None:
        """`kind` tints the message chip: info (neutral), success
        (green), warn (amber), error (red), best (gold). Only a text
        change restarts the pop-in, so a throttled repeat of the same
        prompt does not visibly re-arrive every refresh."""
        if text != self.message:
            self._message_born = time.perf_counter()
        self.message = text
        self.message_until = time.perf_counter() + duration_s
        self.message_kind = kind

    def _message_colour(self) -> tuple[int, int, int]:
        return {
            "success": self.theme.success,
            "warn": self.theme.warning,
            "error": self.theme.error,
            "best": (255, 196, 0),
        }.get(self.message_kind, self.theme.foreground)

    def add_encouragement(self, text: str) -> None:
        # Encouragement banners live in the empty band BELOW the lane
        # tiles. The old spot just under the score collided with the
        # streak pill at the exact moment both fire (a streak
        # threshold is always a fresh pill render too). Down here the
        # banner has the whole strip to itself.
        # One banner at a time. The thresholds sit two trials apart at
        # the bottom of the table (3 then 5), which at rhythm's cadence
        # is inside the 1.8 s lifetime, so the second banner used to
        # land on top of the first at this exact point and render both
        # as one unreadable smear. The newest count is the true one, so
        # the older banner retires rather than sharing the strip.
        cx = self.layout.width // 2
        self._popups = [p for p in self._popups
                        if not getattr(p, "is_banner", False)]
        banner = FloatingText(
            text, (cx, self.layout.height - 88), self.theme.success,
            font_pt=FONT_TITLE - 4,
            lifetime_s=1.8,
            rise_px=30,
        )
        banner.is_banner = True
        self._popups.append(banner)

    def update(self, dt: float) -> None:
        if self.engine.paused:
            return
        # Garbage-collect dead popups so we don't keep rendering them.
        self._popups = [p for p in self._popups if p.alive]
        # Keyboard-mode press feedback: walk each lane and ask "is
        # the key bound to this lane currently held?". The Arduino
        # path drives ls.is_pressed from the detector instead (see
        # GameEngine._pump_source) so this loop is a no-op there.
        if not self.engine.source.provides_samples:
            now = time.perf_counter()
            for ls in self.lanes:
                held = self._key_held_for_lane(ls.lane, ls.hand)
                ls.set_pressed(held, now)
        # Hold the mode back while the pre-start countdown is running so
        # the first stim fires the instant it hits zero, not before. Lane
        # press visuals above still update so the patient can test their
        # fingers during the GET READY window. A mode with research
        # gating of its own gets prep_tick during the hold, so that
        # gating runs INSIDE the prep instead of stacking a second wait
        # on top: chords accumulates its baseline-quiet clock here and
        # a hand that settled during the card fires its first chord at
        # zero.
        if self.engine.mode and hasattr(self.engine.mode, "update"):
            if self._countdown_remaining() <= 0:
                self.engine.mode.update(dt)
            elif hasattr(self.engine.mode, "prep_tick"):
                self.engine.mode.prep_tick(dt)

    def _key_held_for_lane(self, lane: int, hand: str) -> bool:
        """In keyboard mode, decide whether any key bound to this
        lane is in the held set. Same lookup the Diagnostics screen
        uses, factored onto the screen so the visual response is
        consistent across screens."""
        from ..game.modes._keys import keymap_for_hand, resolve_key
        km = self.engine.cfg.get(
            keymap_for_hand(self.engine.hand_mode), {},
        )
        for key_name, lane_idx in km.items():
            if lane_idx != lane:
                continue
            kc = resolve_key(key_name)
            if kc is not None and kc in self._held_keys:
                return True
        return False

    def handle_event(self, e: pygame.event.Event) -> None:
        # Track key-held state for the lane-strip press visual.
        # KEYUP is critical: without it, releasing a key would leave
        # the lane stuck "pressed" until the screen was torn down.
        if e.type == pygame.KEYDOWN:
            self._held_keys.add(e.key)
        elif e.type == pygame.KEYUP:
            self._held_keys.discard(e.key)
        if self.engine.mode and hasattr(self.engine.mode, "handle_event"):
            self.engine.mode.handle_event(e)

    # ---- HUD helpers -------------------------------------------------------
    def _progress(self) -> tuple[int, int]:
        """Return (done, total) trials for the active mode. Classic uses the
        sequence index; adaptive tracks `completed` and `total_trials`."""
        m = self.engine.mode
        if m is None:
            return (0, 0)
        if hasattr(m, "total_trials") and hasattr(m, "completed"):
            return (int(m.completed), int(m.total_trials))
        if hasattr(m, "sequence") and hasattr(m, "idx"):
            return (int(m.idx), len(m.sequence))
        return (0, 0)

    # ---- reaction's static stage ------------------------------------------
    # Seconds the frozen frame is held AFTER the trial closes. The
    # response lands inside the stimulus phase, so unfreezing on the
    # phase change would move the screen a few hundred ms after the
    # press, which is the middle of the epoch the press is being read
    # in. A beat later is out of it.
    REACT_EPOCH_TAIL_S = 1.0

    def _reaction_stage(self) -> bool:
        """Whether this block gets the static treatment.

        Reaction only. Every other mode wants the score to jump, the
        chevron to bob and the ring to fly out of the tile, because
        nothing downstream of them is reading microvolts. Here the
        screen IS the stimulus apparatus: anything else that changes
        brightness while a trial is open lands in the same epoch as
        the cue and cannot be told apart from it afterwards.
        """
        return getattr(self.engine, "current_block", "") == "reaction"

    def _reaction_trial_open(self) -> bool:
        """True from the frame the mode arms a wait (the S1 marker) to
        the frame the trial closes, catch trials included."""
        return getattr(self.engine.mode, "_phase", "") in (
            "foreperiod", "catch", "stim")

    def _reaction_best(self) -> float | None:
        m = self.engine.mode
        if not hasattr(m, "session_best_ms"):
            return None
        try:
            best = m.session_best_ms()
        except Exception:
            return None
        # isinstance rather than truthiness: a test double's mode
        # returns a MagicMock here, which must not reach the format.
        return best if isinstance(best, (int, float)) else None

    def _reaction_snapshot(self) -> dict:
        """Every mutable number the stage draws, frozen as one."""
        done, total = self._progress()
        # Same shifted window the stage draws with, or a chip inside
        # the shift would blink off the moment the snapshot was taken.
        live_msg = (self.message
                    if self.message and time.perf_counter()
                    < self.message_until + self.REACT_EPOCH_TAIL_S else "")
        return {
            "score": self.engine.score,
            "streak": self.engine.hit_streak,
            "done": done,
            "total": total,
            "msg": live_msg,
            "msg_colour": self._message_colour(),
            "best": self._reaction_best(),
        }

    def _update_reaction_hold(self, now: float) -> None:
        """Take the snapshot when a trial opens, drop it a beat after
        it closes. Called once at the top of draw so any render path,
        headless included, goes through the same state machine."""
        if not self._reaction_stage():
            self._react_hold = None
            self._react_hold_until = 0.0
            return
        if self._reaction_trial_open():
            if self._react_hold is None:
                self._react_hold = self._reaction_snapshot()
            self._react_hold_until = 0.0
        elif self._react_hold is not None:
            if self._react_hold_until <= 0.0:
                self._react_hold_until = now + self.REACT_EPOCH_TAIL_S
            elif now >= self._react_hold_until:
                self._react_hold = None
                self._react_hold_until = 0.0

    def _held(self, key: str, live):
        """The frozen value while a trial is open, the live one
        otherwise. Every mutable thing the reaction stage draws goes
        through here, which is what makes the frame-difference
        contract in tests/test_reaction_mode.py provable rather than a
        list of things somebody remembered to suppress."""
        hold = self._react_hold
        if hold is not None and key in hold:
            return hold[key]
        return live

    def _draw_chip(self, surf: pygame.Surface,
                    centre: tuple[int, int],
                    text: str,
                    fg: tuple[int, int, int],
                    bg_alpha: int = 38,
                    pad_x: int = 16, pad_y: int = 6,
                    font_pt: int = FONT_BODY) -> None:
        """Backwards-compat instance shim. New callers should prefer
        the module-level `_chip` helper so the same rendering is
        usable from any screen, not just GameplayScreen."""
        _chip(surf, self.layout, centre, text, fg,
               bg_alpha=bg_alpha, pad_x=pad_x, pad_y=pad_y,
               font_pt=font_pt)

    def _draw_progress_bar(self, surf: pygame.Surface,
                            done: int, total: int,
                            fill_colour: tuple[int, int, int] | None = None,
                            ) -> None:
        """Slim full-width bar near the top of the screen that fills as the
        session progresses. Tells the patient how much is left without
        forcing them to count trials. `fill_colour` lets a mode tint
        the fill with its own accent; None keeps the theme accent."""
        if total <= 0:
            return
        pad = 30
        bar_y = 14
        bar_h = 6
        bar_w = self.layout.width - pad * 2
        frac = max(0.0, min(1.0, done / total))
        # Track (full width, faint).
        track_surf = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(track_surf, (*self.theme.muted, 70),
                          track_surf.get_rect(), border_radius=bar_h // 2)
        surf.blit(track_surf, (pad, bar_y))
        # Fill (accent colour, proportional width).
        fill_w = max(0, int(bar_w * frac))
        if fill_w > 0:
            fc = fill_colour or self.theme.accent
            fill_surf = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
            pygame.draw.rect(fill_surf, (*fc, 220),
                              fill_surf.get_rect(), border_radius=bar_h // 2)
            surf.blit(fill_surf, (pad, bar_y))

    # ---- draw --------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        cx = self.layout.width // 2
        block = getattr(self.engine, "current_block", "")
        # Reaction runs on a frame that must not move while a trial is
        # open. `static` says this is that block at all; `frozen` says
        # a trial is open right now, which is when every HUD number
        # comes out of the snapshot instead of off the engine.
        static = self._reaction_stage()
        self._update_reaction_hold(time.perf_counter())
        frozen = static and self._react_hold is not None

        # Score-pulse trigger: kick the animation any time the engine's
        # score actually changes so the patient sees the number react.
        # Never in reaction: a number that grows and shrinks is a
        # brightness change with no marker behind it.
        if self.engine.score != self._last_score_seen:
            if not static:
                self._score_pulse_t = time.perf_counter()
            self._last_score_seen = self.engine.score

        # ---- Top HUD ----
        # Stripped-down HUD: progress bar + big score + streak (when
        # it's actually motivating) + a tiny mode pill. Everything
        # else (HITS, MISSES, HIT RATE, multiplier, BPM, patient
        # name, "Trial 12/40" text) was carrying therapist-only info
        # the patient didn't need mid-session and lived on the
        # Results screen anyway. Less noise on screen means more
        # focus on the lane tiles where the actual work happens.
        done, total = self._progress()
        done = self._held("done", done)
        total = self._held("total", total)

        # The mode's accent colour (the same one its mode-select card
        # uses) tints the progress bar, streak pill and countdown so
        # every mode keeps its own identity in play, not just on the
        # picker. Computed once here; the pill below reuses it.
        mode_accent = ModeSelectScreen.MODE_ACCENTS.get(
            self.engine.current_block.lower(), self.theme.accent,
        )

        # Slim progress bar across the top of the screen.
        self._draw_progress_bar(surf, done, total, fill_colour=mode_accent)

        # Centre: big SCORE with a brief pulse on change. Single
        # focal element above the lane row so the patient's eye
        # always returns here for "how am I doing".
        draw_text(surf, "SCORE",
                  (cx, 36), self.theme, self.layout, pt=FONT_SMALL + 2,
                  centre=True, colour=self.theme.muted)
        age_pulse = time.perf_counter() - self._score_pulse_t
        if age_pulse < 0.35 and self._score_pulse_t > 0:
            pulse_scale = 1.0 + (1.0 - age_pulse / 0.35) * 0.18
            score_pt = int(FONT_TITLE * pulse_scale)
        else:
            score_pt = FONT_TITLE
        draw_text(surf, f"{self._held('score', self.engine.score)}",
                  (cx, 96), self.theme, self.layout, pt=score_pt,
                  centre=True, colour=self.theme.accent)

        # Streak pill. Only shows when streak >= 2 - a streak of 1
        # is just "one correct press in a row", which isn't worth
        # celebrating yet, and an empty streak chip is dead pixels
        # in the patient's focal area. Goes gold at 5+ to mark the
        # "you're really on a run" moment.
        #
        # Mirror mode parks the chip at the top-LEFT (mirroring the
        # mode pill at the top-right) so the centre column under the
        # score stays clear for the "PRESS TOGETHER" bracket + label.
        # Before, the chip at (cx, 170) collided with the bracket
        # sitting just above the lane tiles in bilateral layout. All
        # other modes keep the centred chip - the bracket only
        # appears when 2+ lanes are lit at once.
        streak = self._held("streak", self.engine.hit_streak)
        if streak >= 2:
            streak_label = f"x{streak} STREAK"
            if streak >= 10:
                streak_colour = self.theme.success    # bright green
            elif streak >= 5:
                streak_colour = (255, 196, 0)         # gold
            else:
                # Base tier wears the mode's accent so even a small
                # streak reinforces which game the patient is in.
                streak_colour = mode_accent
            # Mirror AND chords park the chip top-left: both draw the
            # PRESS TOGETHER bracket above the tiles, and the centred
            # chip sat exactly where the bracket bar + label go.
            # Reaction parks it top-RIGHT under the mode pill instead:
            # its feedback chip renders larger and higher (the RT
            # number is the mode's whole feedback loop), and the
            # centred streak chip at (cx, 170) sat inside it.
            block_now = getattr(self.engine, "current_block", None)
            side_chip = block_now in ("mirror", "chords")
            under_pill = block_now == "reaction"
            if side_chip or under_pill:
                # Render the chip pre-sized so it can be edge-anchored
                # against the same 28 px margin the mode pill uses:
                # left at the mode-pill height for mirror/chords,
                # right just below the mode pill for reaction.
                chip_pt = FONT_SMALL + 2
                chip_font = self.layout.font(chip_pt)
                chip_text = chip_font.render(
                    streak_label, True, (255, 255, 255))
                pad_x = 12
                pad_y = 4
                chip_w = chip_text.get_width() + pad_x * 2
                chip_h = chip_text.get_height() + pad_y * 2
                chip_rect = pygame.Rect(28, 30 - chip_h // 2 + 12,
                                         chip_w, chip_h)
                if under_pill:
                    chip_rect.topright = (self.layout.width - 28, 66)
                pygame.draw.rect(surf, streak_colour, chip_rect,
                                  border_radius=chip_h // 2)
                surf.blit(chip_text,
                           chip_text.get_rect(center=chip_rect.center))
            else:
                self._draw_chip(surf, (cx, 170),
                                 streak_label,
                                 streak_colour,
                                 font_pt=FONT_BODY)

        # Mode badge top-right. Small pill in the mode's accent
        # colour. Keeps the visual identity from the mode-select
        # cards consistent so a therapist glancing at the screen
        # knows which mode is running without reading text.
        # "pattern" reads as "MUSCLE MEMORY" here too (audit finding
        # #10) -- the in-play pill must match the mode-select card and
        # results pill, or the patient sees the word "pattern" on the
        # one screen they're staring at for the whole session.
        mode_label = ("MUSCLE MEMORY"
                      if self.engine.current_block == "pattern"
                      else self.engine.current_block.title().upper())
        mf = self.layout.font(FONT_SMALL + 2)
        mt_label = mf.render(mode_label, True, (255, 255, 255))
        pill_pad_x = 12
        pill_pad_y = 4
        pill_w = mt_label.get_width() + pill_pad_x * 2
        pill_h = mt_label.get_height() + pill_pad_y * 2
        pill_rect = pygame.Rect(0, 0, pill_w, pill_h)
        pill_rect.topright = (self.layout.width - 28, 30)
        pygame.draw.rect(surf, mode_accent, pill_rect,
                          border_radius=pill_h // 2)
        surf.blit(mt_label,
                   mt_label.get_rect(center=pill_rect.center))

        # Bilateral mid-divider: thin grey line between the two hand
        # blocks so the eye reads them as separate groups. The LEFT /
        # RIGHT text labels that used to sit above the lanes are gone:
        # the hand-coloured badge icon on each tile already tells the
        # patient which hand it is, and the extra labels just crowded
        # the HUD chip row underneath the score.
        #
        # Skipped in mirror mode: the whole point of mirror is that
        # the two hands act as a single paired unit, so visually
        # splitting them with a divider works against the concept.
        # The PRESS TOGETHER bracket between the two active chevrons
        # is the connector that matters here.
        in_mirror = (getattr(self.engine, "current_block", None)
                      == "mirror")
        # Extent comes from the lanes themselves rather than two fixed
        # numbers. The fixed pair ran from 215 (inside the message
        # chip, which is centred on the same x, so the line cut its
        # underside) down to height-80, a good 60 px past the tile
        # baseline where it dangled into empty space. Tied to the
        # tiles it can do neither. Drawn ahead of the message chip for
        # the same reason: painted after it, the line ran across the
        # chip's underside.
        if self.engine.hand_mode == "both" and not in_mirror and self.lanes:
            mid_x = self.layout.width // 2
            top = min(ls.rect.top for ls in self.lanes)
            bottom = max(ls.rect.bottom for ls in self.lanes)
            pygame.draw.line(surf, self.theme.muted,
                              (mid_x, top), (mid_x, bottom), 2)

        # Mode message chip: whatever the mode asked the patient to
        # read right now ("142 ms  NEW BEST", "Too soon", "Level up",
        # "Press any finger when ready"). Rendered as a tinted pill
        # with a short pop-in so the feedback visibly ARRIVES, and the
        # tint carries the meaning (gold best, amber caution, green
        # reward) before the words are read. Lives in the gap between
        # the streak pill and the tallest lane tile. Suppressed while
        # the pattern rest card is up: the card says the same thing
        # with more room.
        pattern_resting = (
            block == "pattern" and self.engine.mode is not None
            and getattr(self.engine.mode, "phase", "") == "rest")
        # Two or more lanes lit means _draw_target_indicator will put
        # a pair bracket over the tiles, and the whole bracket (label,
        # bar, stubs, chevrons) lives inside the band the centred chip
        # occupies. Chords hit this on every chord: "Warm-up done.
        # Chords: press together" rendered straight through the
        # chevron and the PRESS TOGETHER label, and neither was
        # readable. The bracket says which tiles to press and cannot
        # move away from them, so the chip yields and takes the quiet
        # bottom band instead.
        bracket_up = sum(1 for ls in self.lanes if ls.active) >= 2
        self._msg_in_bottom_band = False
        # Also suppressed under either exit guard. The guard is meant
        # to be the frozen frame's ONE message; a mode chip left
        # sitting under it made two.
        # Reaction's feedback is set ON the response and the stage
        # stays frozen for a beat after that, so its window has to
        # start when the freeze lets go or the RT number would show
        # for whatever fraction of a second was left of it. Shifted,
        # not shortened.
        msg_until = self.message_until + (
            self.REACT_EPOCH_TAIL_S if static else 0.0)
        msg_text = (self.message
                    if self.message and time.perf_counter() < msg_until
                    else "")
        msg_colour = self._message_colour()
        if static:
            # Held from the moment the wait armed. A chip that arrives
            # or times out mid-trial is a luminance step in the middle
            # of the epoch, and the record cannot tell it from the
            # stimulus afterwards. In the EEG variant the chip carries
            # the visible S1, so holding it also stops the ready cue
            # vanishing 800 ms into a 2.5 s wait.
            msg_text = self._held("msg", msg_text)
            msg_colour = self._held("msg_colour", msg_colour)
        if (msg_text and not pattern_resting
                and not self.engine.exit_overlay_active):
            age = time.perf_counter() - self._message_born
            # Reaction's chip IS the mode's feedback (the RT number is
            # the PVT's self-motivating loop), so it renders a step
            # larger and stronger there than the shared default, and
            # sits a little higher so the bigger chip still clears the
            # tallest lane tile (top = 220).
            base_pt = 34 if block == "reaction" else 30
            chip_cy = 188 if block == "reaction" else 201
            chip_alpha = 42 if block == "reaction" else 30
            if bracket_up:
                self._msg_in_bottom_band = True
                base_pt = 26
                chip_cy = self.layout.height - 42
                chip_alpha = 36
            pt = base_pt
            # The pop-in is a scale animation, so reaction never gets
            # it: the chip is drawn at one size or not at all.
            if age < 0.18 and not static:
                pt = int(base_pt * (1.0 + 0.22 * (1.0 - age / 0.18)))
            _chip(surf, self.layout, (cx, chip_cy), msg_text,
                  msg_colour, bg_alpha=chip_alpha,
                  pad_x=24, pad_y=10, font_pt=pt)

        now = time.perf_counter()
        for ls in self.lanes:
            # Halos, glows and the target pulse all render OUTSIDE the
            # tile rect, and the target pulse is a sine on top of that.
            # In reaction the lit tile has to be the whole of what
            # changed, and it has to change once.
            ls.show_halos = not static
            # The window bar drains and sweeps colour inside the tile
            # for the whole response window. Reaction states its
            # window in words at the top of the screen instead, so the
            # lit tile is a step and then nothing.
            ls.show_timing_bar = not static
            ls.draw(surf, now)

        # Stim ignition: catch the frame a lane goes active and fire a
        # one-shot expanding ring so the arm moment lands hard. Rising-
        # edge only, so with cue.show_target off no lane ever goes
        # active and the ring cannot leak the finger.
        for ls in self.lanes:
            if ls.active and not self._prev_active.get(ls.lane, False):
                self._ignitions.append((ls.lane, now))
            self._prev_active[ls.lane] = ls.active
        if self._ignitions:
            self._ignitions = [(l, t) for (l, t) in self._ignitions
                               if now - t < self.IGNITE_S]

        # Per-mode layers: the wait-state treatment in reaction, the
        # chord baseline + press-window bar in chords, the take chip +
        # rest card in patterns. Kept out of the shared path so every
        # other mode pays nothing for them.
        if block == "reaction":
            self._draw_reaction_layer(surf, now)
        elif block == "chords":
            self._draw_chords_layer(surf, now)
        elif block == "pattern":
            self._draw_pattern_layer(surf, now)

        # Both of these live outside the tile and both are animated:
        # the ignition ring grows out past the rect, the chevron bobs
        # on a sine. Reaction gets neither, so the tile going from its
        # idle colour to its active one is the only thing that moves.
        if not static:
            self._draw_ignitions(surf, now)

            # Downward chevron + PRESS label above the target lane so
            # the patient never has to guess which tile to push. The
            # chevron bobs vertically a few pixels per cycle to draw
            # the eye without being distracting. Drawn AFTER the lanes
            # so it always sits on top (no clipping by neighbouring
            # tiles).
            self._draw_target_indicator(surf, now)

        # Floating hit/miss popups. Held back while the pattern rest
        # card is up: the card dims the stage, and a "Miss" from the
        # last trial floating at full strength over that dim was the
        # brightest thing on a screen whose whole job is "stop and
        # rest".
        # Reaction has no tier popup to rise (flash_lane refuses one),
        # but encouragement banners still land in _popups, and a
        # banner floating up the screen mid-trial is exactly the kind
        # of uncued movement the static stage exists to remove.
        if not pattern_resting and not static:
            for p in self._popups:
                p.draw(surf, self.layout)

        # Corner Controls note: only drawn in keyboard-fallback sessions
        # (see keyboard_controls_lines), silent on the real sensor device
        # where the comment above used to claim this legend would only
        # be noise -- that premise is false whenever the Arduino isn't
        # actually connected (audit finding #110).
        self._draw_controls_note(surf)

        # Pre-start countdown card. Drawn near-last so it sits over the
        # lanes and reads as the clear "wait, don't press yet" focal
        # point. Matches the rhythm-mode countdown styling.
        remaining = self._countdown_remaining()
        if remaining > 0:
            self._draw_countdown_card(surf, remaining)

        # One skip control for every enforced wait, drawn last so it
        # sits over the countdown card and the rest material alike.
        # Held back while a reaction trial is open: reaction arms its
        # waits between trials (the settle gate), so the chip has
        # nothing to offer there and its countdown text would be the
        # one thing on the frame still ticking.
        if not frozen:
            draw_skip_chip(surf, self.layout, self.theme, self.engine)

        # Either exit guard (engine-drawn, above this screen) is the
        # frame's one message; stacking PAUSED under the session
        # dialog or the end-game chip would put two messages on one
        # frozen frame.
        if self.engine.paused and not self.engine.exit_overlay_active:
            self._draw_paused_overlay(surf)

    def _draw_controls_note(self, surf: pygame.Surface) -> None:
        """Corner Controls note for keyboard-fallback sessions, shared
        with SyllablesScreen and RhythmScreen via
        widgets.keyboard_controls_lines. Empty (draws nothing) whenever
        the source is the real sensors."""
        lines = keyboard_controls_lines(self.engine, self.engine.mode)
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

    def _draw_countdown_card(self, surf: pygame.Surface,
                             remaining: float) -> None:
        """GET READY card with the seconds remaining, styled to match
        the rhythm-mode countdown so the pre-start moment looks the
        same across every game mode. The ring and number take the
        mode's accent so even the countdown says which game this is."""
        cx = self.layout.width // 2
        # Faint backdrop dim so the card is the single focal point and
        # the idle tiles behind it recede. Cached: a fresh full-screen
        # SRCALPHA surface every frame would be an allocation in the
        # draw hot path.
        if (self._dim_cache is None
                or self._dim_cache.get_size() != surf.get_size()):
            self._dim_cache = pygame.Surface(surf.get_size(),
                                              pygame.SRCALPHA)
            self._dim_cache.fill((0, 0, 0, 60))
        surf.blit(self._dim_cache, (0, 0))
        accent = ModeSelectScreen.MODE_ACCENTS.get(
            getattr(self.engine, "current_block", "").lower(),
            self.theme.accent,
        )
        card_w = 420
        card_h = 240
        card_rect = pygame.Rect(0, 0, card_w, card_h)
        card_rect.center = (cx, self.layout.height // 2)
        # Soft drop shadow built off-screen for a smooth fade.
        shadow_surf = pygame.Surface(
            (card_w + 24, card_h + 24), pygame.SRCALPHA,
        )
        for dy, alpha in ((2, 50), (6, 28), (12, 10)):
            pygame.draw.rect(
                shadow_surf, (0, 0, 0, alpha),
                pygame.Rect(12, 12 + dy, card_w, card_h),
                border_radius=22,
            )
        surf.blit(shadow_surf, (card_rect.x - 12, card_rect.y - 12))
        # Near-solid themed fill + accent ring.
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

    def _draw_target_indicator(self, surf: pygame.Surface,
                                now: float) -> None:
        """Down-arrow above EVERY active lane plus a pair-bracket
        connector when two are lit at once. Many of our patients
        aren't gamers; without an explicit cue they spend the first
        few trials hunting for the changed tile. The bracket reads
        as "press these two together" in mirror mode where left +
        right of the same finger fire at the same time."""
        import math as _m
        targets = [ls for ls in self.lanes if ls.active]
        if not targets:
            return
        # Bob the indicator a few pixels with a sine wave so the eye
        # is drawn to motion. Shared phase across all chevrons in
        # mirror mode so they pulse in sync, which reinforces the
        # "together" message.
        bob = int(_m.sin(now * (2 * _m.pi / 0.8)) * 4)
        size = 18
        # Draw the connecting bracket FIRST so the chevrons sit on
        # top of it. Only kicks in when there are 2+ active lanes
        # (mirror mode) - classic / adaptive get one chevron only.
        if len(targets) >= 2:
            self._draw_pair_bracket(surf, targets, now, bob)
        for target in targets:
            border = target.HAND_BADGE.get(
                target.hand, self.theme.foreground)
            cx_t = target.rect.centerx
            cy_t = target.rect.top - 22 + bob
            tip = (cx_t, cy_t + size)
            left_pt = (cx_t - size, cy_t - 2)
            right_pt = (cx_t + size, cy_t - 2)
            pygame.draw.polygon(surf, border,
                                 [left_pt, right_pt, tip])
            # White outline so the chevron pops on any background
            # tone.
            pygame.draw.polygon(surf, (255, 255, 255),
                                 [left_pt, right_pt, tip], 2)

    # Mirror-mode pair colour matches the mode's accent on the
    # ModeSelectScreen so the connecting bracket reads as the same
    # "synchronised hands" identity the patient picked.
    _MIRROR_PAIR_COLOUR = (20, 184, 166)   # teal

    def _draw_pair_bracket(self, surf: pygame.Surface,
                            targets: list,
                            now: float, bob: int) -> None:
        """Horizontal bracket connecting the two paired chevrons in
        mirror mode. Two short vertical stubs at each chevron + a
        thin line across the top, like a music staccato slur. Sits
        slightly above the chevrons so it doesn't crash into them."""
        # Use the leftmost + rightmost active tiles as the bracket
        # anchors so the bracket spans the gap between hands even
        # if more than two lanes were lit at once.
        by_x = sorted(targets, key=lambda t: t.rect.centerx)
        left_t = by_x[0]
        right_t = by_x[-1]
        x_left = left_t.rect.centerx
        x_right = right_t.rect.centerx
        # The bar clears EVERY tile, not just the anchors' own tops.
        # Anchored to the pair tiles it used to slice straight across
        # any taller tile between them: the finger-length heights make
        # a pinky pair's bar cross the middle and ring tiles.
        row_top = min(ls.rect.top for ls in self.lanes)
        y_base = row_top - 34 + bob
        # Bracket wears the mode's accent (teal in mirror, sky in
        # chords) so the pair cue carries the same identity as the
        # mode pill.
        colour = ModeSelectScreen.MODE_ACCENTS.get(
            getattr(self.engine, "current_block", "").lower(),
            self._MIRROR_PAIR_COLOUR,
        )
        # Horizontal bar across the top.
        pygame.draw.line(surf, colour,
                          (x_left, y_base),
                          (x_right, y_base), 3)
        # Stubs from the bar down toward each anchor's chevron so the
        # bracket points at the tiles to press. Clamped so an anchor
        # that IS the tallest tile still shows a visible stub.
        for t in (left_t, right_t):
            stub_end = max(y_base + 10, t.rect.top - 44 + bob)
            pygame.draw.line(surf, colour,
                              (t.rect.centerx, y_base),
                              (t.rect.centerx, stub_end), 3)
        # "TOGETHER" label centred above the bar so the patient
        # knows the bracket means "press these as a pair". Pulsing
        # alpha so the cue is visible but doesn't fight the lane
        # tiles for focus. The streak chip parks top-left in the
        # bracket modes, so this centre spot stays clear.
        import math as _m
        alpha_phase = (_m.sin(now * (2 * _m.pi / 1.2)) + 1) * 0.5
        alpha = int(160 + 60 * alpha_phase)
        label_font = self.layout.font(FONT_SMALL + 2)
        label = label_font.render("PRESS TOGETHER", True, colour)
        label.set_alpha(alpha)
        x_mid = (x_left + x_right) // 2
        surf.blit(label, label.get_rect(
            midbottom=(x_mid, y_base - 6)))

    # One-shot ignition ring lifetime. Short and single so nothing here
    # counts as a flash sequence (WCAG 2.3.1 needs three per second;
    # this is one ring per stim, stims arrive seconds apart).
    IGNITE_S = 0.35

    def _draw_ignitions(self, surf: pygame.Surface, now: float) -> None:
        """Expanding outline around a lane that just went active. The
        tile colour snapping to lane_active says WHICH finger; this
        says NOW."""
        if not self._ignitions:
            return
        by_lane = {ls.lane: ls for ls in self.lanes}
        for lane, t0 in self._ignitions:
            ls = by_lane.get(lane)
            if ls is None:
                continue
            frac = (now - t0) / self.IGNITE_S
            if not 0.0 <= frac < 1.0:
                continue
            grow = int(16 + 56 * frac)
            alpha = int(220 * (1.0 - frac))
            ring = ls.rect.inflate(grow, grow)
            rs = pygame.Surface(ring.size, pygame.SRCALPHA)
            colour = ls.HAND_BADGE.get(ls.hand, self.theme.accent)
            pygame.draw.rect(rs, (*colour, alpha), rs.get_rect(),
                             width=6, border_radius=26)
            surf.blit(rs, ring.topleft)

    # ---- reaction ----------------------------------------------------------
    def _draw_reaction_layer(self, surf: pygame.Surface,
                             now: float) -> None:
        """Reaction's own furniture, and deliberately almost none of it.

        This layer used to drop the whole lane band behind a
        translucent veil for the foreperiod and breathe a row of dots
        under it, so the stimulus read as the lights coming back on.
        It looked good and it is unusable for EEG: the veil is a
        full-width luminance step at the start of every wait and
        another at every stimulus, and the dots are a 0.55 Hz
        oscillation over the whole screen through the epoch. Neither
        is time-locked to anything the record can subtract. What the
        stage keeps is what does not move: the level and window pill,
        and the session best at the foot of the screen so "faster"
        always has a target, held with the rest of the HUD while a
        trial is open.
        """
        m = self.engine.mode
        if m is None or not self.lanes:
            return
        # Level + response window. Reaction has no force or amplitude
        # difficulty axis (see reaction.py's PROGRESSION docstring
        # section) - the response window is the ONLY difficulty lever,
        # yet nothing on screen said which window was in force, so a
        # block feeling harder had no visible cause. Drawn as a quiet
        # pill top-LEFT (mirroring the mode pill top-right): the old
        # centred line at y=40 sat directly on the SCORE label and the
        # two rendered through each other. The label text still goes
        # through draw_text so the on-screen contract test keeps
        # seeing the exact "Level X of Y" / "Window Ns" strings.
        level = getattr(m, "level", None)
        max_level = getattr(m, "max_level", None)
        window_s = getattr(m, "response_window", None)
        if (isinstance(level, int) and isinstance(max_level, int)
                and isinstance(window_s, (int, float))):
            label = (f"Level {level} of {max_level}   "
                     f"Window {window_s:.1f}s")
            lf = self.layout.font(FONT_SMALL)
            lw, lh = lf.size(label)
            pad_x, pad_y = 12, 5
            pill = pygame.Rect(28, 30 - (lh + pad_y * 2) // 2 + 12,
                               lw + pad_x * 2, lh + pad_y * 2)
            pill_bg = pygame.Surface(pill.size, pygame.SRCALPHA)
            pygame.draw.rect(pill_bg, (*self.theme.muted, 36),
                             pill_bg.get_rect(),
                             border_radius=pill.height // 2)
            surf.blit(pill_bg, pill.topleft)
            draw_text(surf, label, (pill.x + pad_x, pill.y + pad_y),
                      self.theme, self.layout, pt=FONT_SMALL,
                      centre=False, colour=self.theme.muted)
        # bg_alpha 32 (was 24): the target the patient is chasing was
        # nearly invisible against the light background. Held while a
        # trial is open, because a new best lands ON the response and
        # would repaint this the moment the press was made.
        best = self._held("best", self._reaction_best())
        if isinstance(best, (int, float)):
            _chip(surf, self.layout,
                  (self.layout.width // 2, self.layout.height - 42),
                  f"SESSION BEST  {best:.0f} ms",
                  self.theme.muted, bg_alpha=32, pad_x=16, pad_y=6,
                  font_pt=FONT_SMALL + 2)

    # ---- chords ------------------------------------------------------------
    def _draw_chords_layer(self, surf: pygame.Surface,
                           now: float) -> None:
        """Make the chord read as ONE gesture: a glowing baseline
        joins the target tiles from below, a press-window bar drains
        from the first onset, a ring on each held tile fills over the
        hold so the patient watches the hold complete WHILE pressing,
        and a green tick lands on each quiet finger when the
        cross-talk stayed low."""
        m = self.engine.mode
        if m is None or not self.lanes:
            return
        accent = ModeSelectScreen.MODE_ACCENTS.get(
            "chords", self.theme.accent)
        targets = [ls for ls in self.lanes if ls.active]
        trial = getattr(m, "active", None)
        self._draw_chord_hold(surf, m, trial, targets, accent)
        if len(targets) >= 2:
            left = min(ls.rect.left for ls in targets) + 10
            right = max(ls.rect.right for ls in targets) - 10
            base_y = max(ls.rect.bottom for ls in targets) + 14
            # Baseline glow pulses at ~0.7 Hz, well under the flash
            # limit, so the group cue breathes rather than blinks.
            pulse = (math.sin(now * (2 * math.pi / 1.4)) + 1) * 0.5
            alpha = int(140 + 80 * pulse)
            bar = pygame.Surface((max(2, right - left), 8),
                                 pygame.SRCALPHA)
            pygame.draw.rect(bar, (*accent, alpha), bar.get_rect(),
                             border_radius=4)
            surf.blit(bar, (left, base_y))
            for ls in targets:
                pygame.draw.line(surf, accent,
                                 (ls.rect.centerx, ls.rect.bottom + 4),
                                 (ls.rect.centerx, base_y + 4), 3)
            # Press-window bar: the togetherness budget. Idles faint
            # until the first finger lands, then drains over w_ms so
            # the patient sees the window closing.
            w_ms = 0.0
            if trial is not None:
                raw_w = getattr(trial, "w_ms", 0.0)
                if isinstance(raw_w, (int, float)):
                    w_ms = float(raw_w)
            if trial is not None and w_ms > 0:
                bw, bh = 260, 10
                bx = (left + right) // 2 - bw // 2
                by = base_y + 20
                track = pygame.Surface((bw, bh), pygame.SRCALPHA)
                pygame.draw.rect(track, (*self.theme.muted, 70),
                                 track.get_rect(), border_radius=bh // 2)
                surf.blit(track, (bx, by))
                onsets = getattr(trial, "onsets", None) or {}
                if onsets:
                    rem = 1.0 - (now - min(onsets.values())) * 1000.0 / w_ms
                    rem = max(0.0, min(1.0, rem))
                    if rem > 0:
                        fill_col = (self.theme.success if rem > 0.35
                                    else self.theme.warning)
                        fill = pygame.Surface((max(2, int(bw * rem)), bh),
                                              pygame.SRCALPHA)
                        pygame.draw.rect(fill, (*fill_col, 230),
                                         fill.get_rect(),
                                         border_radius=bh // 2)
                        surf.blit(fill, (bx, by))
                else:
                    fill = pygame.Surface((bw, bh), pygame.SRCALPHA)
                    pygame.draw.rect(fill, (*accent, 70),
                                     fill.get_rect(),
                                     border_radius=bh // 2)
                    surf.blit(fill, (bx, by))
                draw_text(surf, f"TOGETHER WITHIN {w_ms:.0f} ms",
                          (bx + bw // 2, by + bh + 14),
                          self.theme, self.layout, pt=FONT_SMALL,
                          centre=True, colour=self.theme.muted)
        # Quiet-fingers reward: the tick appears over the still fingers
        # for a beat after a clean chord, then fades. One event per
        # trial, no repeats, so nothing here can flash.
        tick_t = getattr(m, "_quiet_tick_t", None)
        if isinstance(tick_t, (int, float)) and 0.0 <= now - tick_t < 0.9:
            frac = (now - tick_t) / 0.9
            alpha = int(235 * (1.0 - frac))
            lanes_ok = getattr(m, "_quiet_tick_lanes", ()) or ()
            for ls in self.lanes:
                if ls.lane not in lanes_ok:
                    continue
                cx_t = ls.rect.centerx
                cy_t = ls.rect.top + ls.rect.h // 3
                ds = pygame.Surface((60, 60), pygame.SRCALPHA)
                pygame.draw.circle(ds, (*self.theme.success,
                                        int(alpha * 0.30)),
                                   (30, 30), 28)
                pygame.draw.lines(ds, (*self.theme.success, alpha),
                                  False,
                                  [(17, 31), (27, 41), (44, 20)], 5)
                surf.blit(ds, (cx_t - 30, cy_t - 30))

    def _draw_chord_hold(self, surf: pygame.Surface, m, trial,
                         targets: list, accent) -> None:
        """The hold made visible. While the chord is down, a ring on
        each held tile fills from empty to full over hold_ms; success
        lands exactly when the ring completes, so "hold" means "keep
        this ring filling". Before the chord completes, fingers
        already down wear the empty track so the patient sees they
        are registered and must stay down; a finger that lifts loses
        its track the moment the mode withdraws its onset. With
        cue.show_target off no lane may be singled out, so a single
        centred bar carries the same progress without naming any
        lane. When no hold is required (keyboard play skips it),
        nothing draws: no progress shown means no hold asked."""
        if getattr(m, "hold_required", None) is not True:
            return
        prog = None
        hp = getattr(m, "hold_progress", None)
        if callable(hp):
            try:
                p = hp()
            except Exception:
                p = None
            if isinstance(p, (int, float)):
                prog = max(0.0, min(1.0, float(p)))
        if prog is not None:
            if targets:
                for ls in targets:
                    self._draw_hold_ring(surf, ls, prog, accent)
            else:
                self._draw_hold_bar(surf, prog, accent)
            return
        # Chord still forming: empty tracks on the fingers that are
        # down, nothing on the ones still to land.
        onsets = getattr(trial, "onsets", None)
        if isinstance(onsets, dict) and onsets and targets:
            for ls in targets:
                if ls.lane in onsets:
                    self._draw_hold_ring(surf, ls, 0.0, accent)

    def _draw_hold_ring(self, surf: pygame.Surface, ls, frac: float,
                        colour) -> None:
        """Progress ring centred on a held tile. The faint track says
        a hold is part of this press; the thick arc sweeps clockwise
        from 12 o'clock and closes at hold_ms. Drawn as a polygon
        strip rather than pygame.draw.arc because wide arcs render
        with moire holes."""
        r_out = max(20, min(34, min(ls.rect.w, ls.rect.h) // 3))
        thick = 7
        pad = 4
        size = (r_out + pad) * 2
        ds = pygame.Surface((size, size), pygame.SRCALPHA)
        c = (r_out + pad, r_out + pad)
        pygame.draw.circle(ds, (255, 255, 255, 70), c, r_out, 3)
        if frac > 0:
            sweep = 2 * math.pi * frac
            steps = max(3, int(60 * frac))
            outer = []
            inner = []
            for k in range(steps + 1):
                a = math.pi / 2 - sweep * k / steps
                outer.append((c[0] + r_out * math.cos(a),
                              c[1] - r_out * math.sin(a)))
                inner.append((c[0] + (r_out - thick) * math.cos(a),
                              c[1] - (r_out - thick) * math.sin(a)))
            pygame.draw.polygon(ds, (*colour, 235),
                                outer + inner[::-1])
        surf.blit(ds, (ls.rect.centerx - c[0],
                       ls.rect.centery - c[1]))

    def _draw_hold_bar(self, surf: pygame.Surface, frac: float,
                       accent) -> None:
        """The tactile-condition twin of the hold ring: one centred
        bar above the lane band filling over hold_ms. Lane-agnostic
        on purpose: with the screen reveal off, per-lane progress
        would name the fingers the cue may not."""
        bw, bh = 300, 12
        bx = self.layout.width // 2 - bw // 2
        row_top = min(ls.rect.top for ls in self.lanes)
        by = row_top - 64
        track = pygame.Surface((bw, bh), pygame.SRCALPHA)
        pygame.draw.rect(track, (*self.theme.muted, 70),
                         track.get_rect(), border_radius=bh // 2)
        surf.blit(track, (bx, by))
        if frac > 0:
            fill = pygame.Surface((max(2, int(bw * frac)), bh),
                                  pygame.SRCALPHA)
            pygame.draw.rect(fill, (*accent, 235), fill.get_rect(),
                             border_radius=bh // 2)
            surf.blit(fill, (bx, by))
        draw_text(surf, "KEEP HOLDING", (bx + bw // 2, by + bh + 14),
                  self.theme, self.layout, pt=FONT_SMALL,
                  centre=True, colour=self.theme.muted)

    # ---- patterns ----------------------------------------------------------
    def _draw_pattern_layer(self, surf: pygame.Surface,
                            now: float) -> None:
        """The recording-studio frame: a REC take chip with in-take
        progress while playing, and a breathing rest card between
        takes. Nothing here reads seg.kind beyond the warm-up label the
        mode itself already announces, so trained and probe takes stay
        pixel-identical."""
        m = self.engine.mode
        if m is None:
            return
        segs = getattr(m, "segments", None)
        idx = getattr(m, "_seg_idx", 0)
        # isinstance guards keep MagicMock modes in tests out of the
        # len() and index arithmetic below.
        if (not isinstance(segs, list) or not isinstance(idx, int)
                or not (0 <= idx < len(segs))):
            return
        seg = segs[idx]
        accent = ModeSelectScreen.MODE_ACCENTS.get(
            "pattern", self.theme.accent)
        phase = getattr(m, "phase", "")
        if phase == "play":
            self._draw_take_chip(surf, now, m, seg, accent)
        elif phase == "rest":
            self._draw_pattern_rest_card(surf, now, m, seg, accent)

    def _draw_take_chip(self, surf: pygame.Surface, now: float,
                        m, seg, accent: tuple[int, int, int]) -> None:
        """Top-left studio chip: pulsing REC dot, take label, and a
        thin bar filling as the take is laid down."""
        # The bar under the chip is the position WITHIN the take, and
        # a bare unfilled track next to a black pill read as a
        # rendering artifact rather than a meter. Putting the same
        # count in words inside the chip gives the bar a name.
        total = max(1, len(getattr(seg, "fingers", []) or []))
        done = min(total, int(getattr(m, "_trial_in_seg", 0) or 0))
        if seg.kind == "warmup":
            label = f"WARM-UP  {done}/{total}"
        else:
            label = f"TAKE {seg.label} OF {m.n_takes}  {done}/{total}"
        font = self.layout.font(FONT_SMALL + 2)
        text = font.render(label, True, (255, 255, 255))
        dot_r = 6
        pad_x = 12
        chip_h = text.get_height() + 12
        chip_w = pad_x * 2 + dot_r * 2 + 8 + text.get_width()
        chip_rect = pygame.Rect(28, 26, chip_w, chip_h)
        pygame.draw.rect(surf, self.theme.foreground, chip_rect,
                         border_radius=chip_h // 2)
        # REC dot breathes at ~0.6 Hz, the studio "we are rolling"
        # signal. Alpha swing only, never off, so it cannot flash.
        pulse = (math.sin(now * (2 * math.pi / 1.6)) + 1) * 0.5
        dot = pygame.Surface((dot_r * 2, dot_r * 2), pygame.SRCALPHA)
        pygame.draw.circle(dot, (239, 68, 68, int(140 + 115 * pulse)),
                           (dot_r, dot_r), dot_r)
        surf.blit(dot, (chip_rect.x + pad_x,
                        chip_rect.centery - dot_r))
        surf.blit(text, (chip_rect.x + pad_x + dot_r * 2 + 8,
                         chip_rect.centery - text.get_height() // 2))
        # In-take progress, tucked under the chip and inset to the
        # chip's own rounded ends so it reads as part of the same
        # object rather than a line that happens to sit near it.
        bar_x = chip_rect.x + chip_h // 2
        bar_w = max(24, chip_w - chip_h)
        bar_y = chip_rect.bottom + 5
        track = pygame.Surface((bar_w, 5), pygame.SRCALPHA)
        pygame.draw.rect(track, (*self.theme.muted, 110),
                         track.get_rect(), border_radius=3)
        surf.blit(track, (bar_x, bar_y))
        fill_w = int(bar_w * done / total)
        if fill_w > 0:
            fill = pygame.Surface((fill_w, 5), pygame.SRCALPHA)
            pygame.draw.rect(fill, (*accent, 230), fill.get_rect(),
                             border_radius=3)
            surf.blit(fill, (bar_x, bar_y))
        # The riff's finger numbers, ONLY when a loaded sequence file
        # says explicit AND show_sequence. The mode gates both; this
        # asks it rather than deciding for itself, so the secrecy rule
        # lives in one place. The word sequence still never appears.
        digits = ""
        getter = getattr(m, "sequence_digits", None)
        if callable(getter):
            try:
                digits = getter() or ""
            except Exception:
                digits = ""
        if digits:
            draw_text(surf, f"Fingers: {digits}",
                      (chip_rect.x, bar_y + 12),
                      self.theme, self.layout, pt=FONT_SMALL + 2,
                      centre=False, colour=accent)

    def _draw_star_row(self, surf: pygame.Surface, centre_x: int,
                       y: int, earned: int) -> None:
        """Three accuracy stars, gold when earned, outline when not.
        Drawn as polygons so no glyph font dependency sneaks in."""
        r_out, r_in, gap = 16, 7, 46
        for i in range(3):
            cx = centre_x + (i - 1) * gap
            pts = []
            for k in range(10):
                ang = -math.pi / 2 + k * math.pi / 5
                r = r_out if k % 2 == 0 else r_in
                pts.append((cx + r * math.cos(ang),
                            y + r * math.sin(ang)))
            if i < earned:
                pygame.draw.polygon(surf, (255, 196, 0), pts)
            else:
                pygame.draw.polygon(surf, self.theme.muted, pts, 2)

    def _draw_pattern_rest_card(self, surf: pygame.Surface, now: float,
                                m, seg,
                                accent: tuple[int, int, int]) -> None:
        """Between-take rest card. Breathes at 0.25 Hz (a slow halo
        swell), shows the finished take's stars, counts the rest floor
        down, then invites the next take."""
        cx = self.layout.width // 2
        cy = self.layout.height // 2 + 20
        # Dim the stage behind the card, same cache the countdown uses.
        if (self._dim_cache is None
                or self._dim_cache.get_size() != surf.get_size()):
            self._dim_cache = pygame.Surface(surf.get_size(),
                                             pygame.SRCALPHA)
            self._dim_cache.fill((0, 0, 0, 60))
        surf.blit(self._dim_cache, (0, 0))
        forced = getattr(m, "_rest_kind", "between") == "forced"
        # A forced fatigue rest has no stars and no star streak to
        # show, so the fixed 260 tall card left a 116 px hole between
        # the title and the countdown. Height follows the rows that
        # actually render.
        card_w = 480
        card_h = 200 if forced else 260
        card_rect = pygame.Rect(0, 0, card_w, card_h)
        card_rect.center = (cx, cy)
        # Row baselines, measured from the card top. The forced card
        # drops the two star rows and closes the gap they leave.
        if forced:
            y_title, y_status, y_dots = 50, 112, 162
        else:
            y_title, y_status, y_dots = 52, 168, 218
        # The breath: a soft accent halo swelling over 4 s.
        breath = (math.sin(now * (2 * math.pi / 4.0)) + 1) * 0.5
        grow = int(10 + 16 * breath)
        halo_rect = card_rect.inflate(grow, grow)
        halo = pygame.Surface(halo_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(halo, (*accent, int(40 + 50 * breath)),
                         halo.get_rect(), border_radius=28)
        surf.blit(halo, halo_rect.topleft)
        # Card body, same recipe as the countdown card.
        shadow = pygame.Surface((card_w + 24, card_h + 24),
                                pygame.SRCALPHA)
        for dy, alpha in ((2, 50), (6, 28), (12, 10)):
            pygame.draw.rect(shadow, (0, 0, 0, alpha),
                             pygame.Rect(12, 12 + dy, card_w, card_h),
                             border_radius=22)
        surf.blit(shadow, (card_rect.x - 12, card_rect.y - 12))
        body = pygame.Surface(card_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(body, (*self.theme.background, 246),
                         body.get_rect(), border_radius=22)
        pygame.draw.rect(body, (*accent, 150), body.get_rect(), 3,
                         border_radius=22)
        surf.blit(body, card_rect.topleft)
        if forced:
            title = "Take a breather"
        elif seg.kind == "warmup":
            title = "Warm-up done"
        else:
            title = f"Take {seg.label} done"
        draw_text(surf, title, (cx, card_rect.y + y_title), self.theme,
                  self.layout, pt=FONT_H1, centre=True)
        if not forced:
            stars = len(m._stars(seg)) if hasattr(m, "_stars") else 0
            self._draw_star_row(surf, cx, card_rect.y + 108, stars)
            # 3-star streak across takes: reward-flavoured feedback
            # that stays accuracy-only (the stars never read speed,
            # so neither can their streak). Shown from 2 up; a streak
            # of 1 is just "one good take".
            run = getattr(m, "star_streak", 0)
            if isinstance(run, int) and run >= 2:
                draw_text(surf, f"{run} takes at 3 stars in a row",
                          (cx, card_rect.y + 140), self.theme,
                          self.layout, pt=FONT_SMALL, centre=True,
                          colour=(255, 196, 0))
        # Rest floor countdown, then the self-paced invitation.
        rest_until = getattr(m, "_rest_min_until", None)
        if rest_until is not None and now < rest_until:
            left = int(math.ceil(rest_until - now))
            draw_text(surf, f"Rest for {left}s",
                      (cx, card_rect.y + y_status), self.theme,
                      self.layout, pt=FONT_H2, centre=True,
                      colour=self.theme.muted)
        else:
            pulse = (math.sin(now * (2 * math.pi / 2.0)) + 1) * 0.5
            font = self.layout.font(FONT_H2)
            t = font.render("Press any finger when ready", True,
                            self.theme.foreground)
            t.set_alpha(int(150 + 105 * pulse))
            surf.blit(t, t.get_rect(
                center=(cx, card_rect.y + y_status)))
        # Take dots: the session at a glance, current position filled.
        takes = [s for s in m.segments if s.kind != "warmup"]
        if takes:
            n = len(takes)
            gap = 22
            x0 = cx - (n - 1) * gap // 2
            done_takes = sum(
                1 for s in takes
                if s.n_done >= len(s.fingers) and len(s.fingers) > 0)
            for i in range(n):
                centre = (x0 + i * gap, card_rect.y + y_dots)
                if i < done_takes:
                    pygame.draw.circle(surf, accent, centre, 6)
                else:
                    pygame.draw.circle(surf, self.theme.muted, centre,
                                       6, 2)

    # _draw_paused_overlay comes from Screen: one card, one resume
    # line, identical on every screen a block runs on.


class RhythmScreen(Screen):
    """Falling notes view for rhythm mode. 4 or 8 strike lanes depending
    on whether the session is bilateral."""

    # How far ahead of the strike line a note is shown. Bumped from
    # the original 1.5 s to 2.2 s after testing showed patients had
    # too little reaction time when the song picked up tempo. The
    # extra 0.7 s of travel gives a clearer "incoming" cue while the
    # press window itself (set by the rhythm-mode timing model) is
    # unchanged - this only affects how early the note becomes
    # visible.
    LOOKAHEAD_S = 2.2

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.lanes: list[LaneStrip] = []
        self.message = ""
        self.message_until = 0.0
        self._popups: list[FloatingText] = []
        # Particle bursts spawned by flash_lane on Perfect/Great/Good
        # rhythm hits. Pruned each frame in update().
        from .widgets import HitBurst
        self._bursts: list[HitBurst] = []
        # Held-key set for the keyboard fallback path. Same role as
        # the gameplay-screen tracker - drives ls.is_pressed each
        # frame so the lane lights up while the key is down.
        self._held_keys: set[int] = set()
        # Cached full-screen dim for the countdown card (no per-frame
        # surface builds in draw).
        self._dim_cache: pygame.Surface | None = None
        self.rebuild_lanes()

    HAND_BLOCK_GAP = 100   # bilateral spacing between right + left blocks

    def rebuild_lanes(self) -> None:
        """Strike lanes for the falling-note view. Layout mirrors the
        patient: left hand on the left of the screen, right hand on the
        right, with each hand's little finger on the outer edge.
        `self.lanes[i].lane == i` is preserved so the falling-note pipe
        (which looks up lanes by id) keeps working."""
        self.lanes = []
        hand_mode = self.engine.hand_mode
        gutter = 14
        # Strike lanes sit at the bottom third of the screen.
        y = self.layout.height - 240
        h = 180
        if hand_mode == "both":
            half_w = (self.layout.width - self.HAND_BLOCK_GAP) // 2
            n = 4
            block_w = half_w - 40
            w = (block_w - gutter * (n - 1)) // n
            rects: dict[int, pygame.Rect] = {}
            # Left hand on the LEFT: lanes 7, 6, 5, 4 reading left-to-right.
            left_x_start = 40
            for pos in range(n):
                lane_num = 7 - pos
                rects[lane_num] = pygame.Rect(
                    left_x_start + pos * (w + gutter), y, w, h,
                )
            # Right hand on the RIGHT: lanes 0, 1, 2, 3 reading left-to-right.
            right_x_start = half_w + self.HAND_BLOCK_GAP
            for pos in range(n):
                lane_num = pos
                rects[lane_num] = pygame.Rect(
                    right_x_start + pos * (w + gutter), y, w, h,
                )
            for i in range(8):
                is_left = i >= 4
                finger = i - 4 if is_left else i
                ls = LaneStrip(
                    lane=i, rect=rects[i],
                    theme=self.theme, layout=self.layout,
                    hand="left" if is_left else "right",
                    finger=finger,
                )
                # Gameplay tile stays clean: the hand icon already
                # signals which hand it is, and the 0/0 FSR readout
                # belongs on the Diagnostics screen, not in-game.
                ls.show_hand_label = False
                ls.show_value_readout = False
                self.lanes.append(ls)
        else:
            n = 4
            w = (self.layout.width - 160 - gutter * (n - 1)) // n
            # Left-hand unilateral mirrors the block: little finger on the
            # outer left, index closest to centre.
            if hand_mode == "left":
                order = [n - 1 - i for i in range(n)]
            else:
                order = list(range(n))
            rects: dict[int, pygame.Rect] = {}
            for pos, lane_num in enumerate(order):
                rects[lane_num] = pygame.Rect(
                    80 + pos * (w + gutter), y, w, h,
                )
            for i in range(n):
                ls = LaneStrip(
                    lane=i, rect=rects[i],
                    theme=self.theme, layout=self.layout,
                    hand=hand_mode, finger=i,
                )
                # Same clean-tile rule as the bilateral branch above.
                ls.show_hand_label = False
                ls.show_value_readout = False
                self.lanes.append(ls)

    def set_message(self, text: str, duration_s: float) -> None:
        self.message = text
        self.message_until = time.perf_counter() + duration_s

    @staticmethod
    def _fmt_mmss(seconds: float) -> str:
        """Format a duration as MM:SS, clamped to non-negative."""
        s = max(0, int(seconds))
        return f"{s // 60:d}:{s % 60:02d}"

    def _draw_song_progress(self, surf: pygame.Surface,
                             elapsed_s: float, total_s: float) -> None:
        """Thin progress bar plus an MM:SS readout so the patient knows
        how long is left in a rhythm session. Sits at the very top of
        the screen so it doesn't fight the lane area for attention."""
        pad = 30
        bar_y = 12
        bar_h = 6
        bar_w = self.layout.width - pad * 2
        frac = max(0.0, min(1.0, elapsed_s / total_s if total_s > 0 else 0.0))
        # Faint track behind the fill.
        track_surf = pygame.Surface((bar_w, bar_h), pygame.SRCALPHA)
        pygame.draw.rect(track_surf, (*self.theme.muted, 70),
                          track_surf.get_rect(), border_radius=bar_h // 2)
        surf.blit(track_surf, (pad, bar_y))
        fill_w = int(bar_w * frac)
        if fill_w > 0:
            fill_surf = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
            pygame.draw.rect(fill_surf, (*self._mode_accent(), 220),
                              fill_surf.get_rect(), border_radius=bar_h // 2)
            surf.blit(fill_surf, (pad, bar_y))
        # Time readout top-LEFT under the bar. The top-right corner
        # belongs to the mode pill, same as every other in-play screen.
        time_text = f"{self._fmt_mmss(elapsed_s)} / {self._fmt_mmss(total_s)}"
        tf = self.layout.font(FONT_SMALL + 2)
        ts = tf.render(time_text, True, self.theme.muted)
        surf.blit(ts, ts.get_rect(topleft=(pad, bar_y + bar_h + 6)))

    def _mode_accent(self) -> tuple[int, int, int]:
        """Rhythm's purple from the mode picker, with the theme accent
        as the fallback if the accent table ever loses the key."""
        return ModeSelectScreen.MODE_ACCENTS.get(
            "rhythm", self.theme.accent)

    def add_encouragement(self, text: str) -> None:
        # Below the streak pill, above the falling-note run. The old
        # spot at y=200 rose straight up into the streak pill at the
        # exact moment a streak threshold refreshed it.
        cx = self.layout.width // 2
        # One banner at a time, same reason as the cadence screen: two
        # thresholds inside the 1.8 s lifetime drew on top of each other
        # here and read as a smear.
        self._popups = [p for p in self._popups
                        if not getattr(p, "is_banner", False)]
        banner = FloatingText(
            text, (cx, 250), self.theme.success,
            font_pt=FONT_TITLE - 4,
            lifetime_s=1.8,
            rise_px=30,
        )
        banner.is_banner = True
        self._popups.append(banner)

    def flash_lane(self, lane: int, colour, duration_s: float, now: float,
                   popup_text: str | None = None,
                   popup_glyph: str | None = None) -> None:
        for ls in self.lanes:
            if ls.lane == lane:
                ls.flash(colour, duration_s, now)
                # Above the strike ring, not on it: at the lane top
                # the feedback sat right across the ring the patient
                # is aiming the next note at.
                strike_y = self.layout.height - 290
                if popup_glyph:
                    # Lab style: one ring per outcome, no words, in
                    # the page ink so size, position, colour and
                    # lifetime are identical for every outcome.
                    self._popups.append(FloatingText(
                        "", (ls.rect.centerx, strike_y - 64),
                        self.theme.foreground, font_pt=36,
                        glyph=popup_glyph,
                    ))
                elif popup_text or self.message:
                    self._popups.append(FloatingText(
                        popup_text or self.message,
                        (ls.rect.centerx, strike_y - 64),
                        colour, font_pt=36,
                    ))
                # Particle burst centred on the strike-line ring for
                # this lane. Skip on the "Miss" red flash (a satisfying
                # hit shouldn't be the same celebration as missing). The
                # strike-line y matches what draw() uses.
                from .widgets import HitBurst
                is_hit = colour != self.theme.lane_miss
                if is_hit:
                    strike_y = self.layout.height - 290
                    self._bursts.append(HitBurst(
                        pos=(ls.rect.centerx, strike_y),
                        colour=colour,
                        count=11,
                        lifetime_s=0.45,
                        speed_px_s=360.0,
                        r_start=8,
                    ))

    def handle_event(self, e: pygame.event.Event) -> None:
        # KEYDOWN/KEYUP feed the held-keys tracker so the lane-strip
        # press visual can light up while the patient holds the key.
        # KEYUP is essential: without it a release would leave the
        # lane stuck "on".
        if e.type == pygame.KEYDOWN:
            self._held_keys.add(e.key)
        elif e.type == pygame.KEYUP:
            self._held_keys.discard(e.key)
        if self.engine.mode and hasattr(self.engine.mode, "handle_event"):
            self.engine.mode.handle_event(e)

    def _key_held_for_lane(self, lane: int, hand: str) -> bool:
        """Mirror of GameplayScreen._key_held_for_lane. Looks up
        which key the active keymap binds to this lane, then checks
        whether it's still in the held-set."""
        from ..game.modes._keys import keymap_for_hand, resolve_key
        km = self.engine.cfg.get(
            keymap_for_hand(self.engine.hand_mode), {},
        )
        for key_name, lane_idx in km.items():
            if lane_idx != lane:
                continue
            kc = resolve_key(key_name)
            if kc is not None and kc in self._held_keys:
                return True
        return False

    def update(self, dt: float) -> None:
        if self.engine.paused:
            return
        self._popups = [p for p in self._popups if p.alive]
        self._bursts = [b for b in self._bursts if b.alive]
        # Drive lane-strip press visual from held keys in keyboard
        # mode. Arduino path is handled by GameEngine._pump_source
        # via the per-hand FSRDetector pressed[] array.
        if not self.engine.source.provides_samples:
            now = time.perf_counter()
            for ls in self.lanes:
                held = self._key_held_for_lane(ls.lane, ls.hand)
                ls.set_pressed(held, now)
        if self.engine.mode and hasattr(self.engine.mode, "update"):
            self.engine.mode.update(dt)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        cx = self.layout.width // 2

        # Top HUD: progress bar, big score, song title.
        bm = getattr(self.engine.mode, "beatmap", None)
        # Song progress bar across the top of the screen. Skipped during
        # the countdown AND the pre-song lead window so we don't show
        # "song is 5% in" while there's nothing playing yet.
        countdown_remaining = (
            getattr(self.engine.mode, "countdown_remaining_s", 0.0)
            if self.engine.mode else 0.0
        )
        audio_started = (
            getattr(self.engine.mode, "_audio_started", True)
            if self.engine.mode else True
        )
        if (bm and bm.duration_s > 0
                and countdown_remaining <= 0
                and audio_started):
            song_t = getattr(self.engine.mode, "song_time", 0.0) or 0.0
            elapsed = max(0.0, min(song_t, bm.duration_s))
            self._draw_song_progress(surf, elapsed, bm.duration_s)

        # SCORE focal element. Song title dropped from the HUD: the
        # patient picked the track 5 seconds ago and the song itself
        # is already playing, so a label restating its name only
        # competes with the falling-note area for attention.
        draw_text(surf, "SCORE",
                  (cx, 40), self.theme, self.layout, pt=FONT_SMALL + 2,
                  centre=True, colour=self.theme.muted)
        draw_text(surf, f"{self.engine.score}",
                  (cx, 92), self.theme, self.layout, pt=FONT_TITLE,
                  centre=True, colour=self.theme.accent)
        # Mode pill top-right, same spot and styling as the gameplay
        # screen so switching between modes never moves the header
        # furniture. Rhythm was the one in-play screen without it.
        accent = self._mode_accent()
        mf = self.layout.font(FONT_SMALL + 2)
        mt_label = mf.render("RHYTHM", True, (255, 255, 255))
        pill_rect = pygame.Rect(0, 0, mt_label.get_width() + 24,
                                 mt_label.get_height() + 8)
        pill_rect.topright = (self.layout.width - 28, 30)
        pygame.draw.rect(surf, accent, pill_rect,
                          border_radius=pill_rect.height // 2)
        surf.blit(mt_label,
                   mt_label.get_rect(center=pill_rect.center))
        # Streak pill - only shown when streak >= 2 so a fresh run
        # doesn't have a permanent "STREAK -" widget burning pixels
        # in the patient's focal area. Mirrors the gameplay screen's
        # streak treatment for consistency between modes: mode accent
        # base tier, gold at 5+, green at 10+.
        streak = self.engine.hit_streak
        if streak >= 2:
            if streak >= 10:
                streak_colour = self.theme.success
            elif streak >= 5:
                streak_colour = (255, 196, 0)         # gold tier
            else:
                streak_colour = accent
            _chip(surf, self.layout, (cx, 152),
                   f"x{streak} STREAK",
                   streak_colour,
                   font_pt=FONT_BODY)

        # Strike line is the y-coordinate the falling notes are aiming at.
        # I moved it up above the lane strips so the press-target rings
        # sit cleanly above the finger labels with no overlap.
        TARGET_R = 36
        now = time.perf_counter()
        strike_y = self.layout.height - 290

        # `top_y` is where each note becomes visible at the top of the
        # screen. Pulled UP from 190 to 140 so notes appear just below
        # the big SCORE number (which sits around y=110). The longer
        # visual run-up gives the patient more time to spot each ball
        # and aim for the right finger. The streak HUD line at y=160
        # is just text on the background, so a ball briefly passing
        # through it is acceptable - it's the focal moving object,
        # the streak number is static info.
        top_y = 140

        # Faint vertical guide lines down each lane from top_y to the
        # strike-line ring. Reads as "this is where the ball coming for
        # this finger will land" without overpowering the lane strip
        # itself. Drawn BEFORE the falling notes so the notes always
        # sit on top of their own guide line.
        for ls in self.lanes:
            cx_g = ls.rect.centerx
            base = ls.HAND_BADGE.get(ls.hand, self.theme.foreground)
            guide = pygame.Surface((4, strike_y - top_y),
                                     pygame.SRCALPHA)
            pygame.draw.rect(guide, (*base, 55),
                              guide.get_rect(), border_radius=2)
            surf.blit(guide, (cx_g - 2, top_y))

        # Falling notes first, BEFORE the strips. Each note slides from
        # top_y down to the strike line. The user presses when the falling
        # circle lands inside the target ring drawn below.
        # Note colour matches the FINGER'S lane tile (per-finger pastel
        # from theme.lane_idle) rather than the hand badge colour, so a
        # ball coming for the ring finger reads as the same yellow as
        # the ring-finger lane below it. Makes the visual cue per-lane
        # instead of per-hand, which is what the rehab task actually
        # tests.
        if self.engine.mode and hasattr(self.engine.mode, "upcoming"):
            upcoming = self.engine.mode.upcoming(self.LOOKAHEAD_S)
            # display_song_time, not song_time: the note has to reach
            # the strike line on the RETINA on the audible beat, so
            # the drawing clock runs ahead by the panel's lag and
            # behind by the audio path (see RhythmMode).
            song_t = getattr(self.engine.mode, "display_song_time",
                             self.engine.mode.song_time)
            for s in upcoming:
                ahead = s.note.t - song_t
                frac = 1.0 - max(0.0, min(1.0, ahead / self.LOOKAHEAD_S))
                y = int(top_y + (strike_y - top_y) * frac)
                if 0 <= s.note.lane < len(self.lanes):
                    ls = self.lanes[s.note.lane]
                    cx_note = ls.rect.centerx
                    # Per-finger lane_idle pastel. theme.lane_idle is a
                    # 4-tuple keyed by within-hand finger index; ls.finger
                    # is already that index even in bilateral mode.
                    if ls.finger is not None and self.theme.lane_idle:
                        idle = self.theme.lane_idle
                        note_colour = idle[ls.finger % len(idle)]
                    else:
                        note_colour = ls.HAND_BADGE.get(
                            ls.hand, self.theme.accent,
                        )
                    near_target = abs(s.note.t - song_t) < 0.3
                    note_r = 30 if not near_target else 34
                    # Soft glow halo for notes within 0.4 s of the
                    # strike line. Builds anticipation - the closer the
                    # note, the brighter the halo grows.
                    if abs(s.note.t - song_t) < 0.4:
                        prox = 1.0 - (abs(s.note.t - song_t) / 0.4)
                        halo_r = note_r + 14
                        halo_alpha = int(110 * prox)
                        halo = pygame.Surface(
                            (halo_r * 2, halo_r * 2), pygame.SRCALPHA,
                        )
                        pygame.draw.circle(halo,
                                            (*note_colour, halo_alpha),
                                            (halo_r, halo_r), halo_r)
                        surf.blit(halo, (cx_note - halo_r, y - halo_r))
                    pygame.draw.circle(surf, note_colour,
                                        (cx_note, y), note_r)
                    pygame.draw.circle(surf, self.theme.foreground,
                                        (cx_note, y), note_r, 3)
                    pygame.draw.circle(surf, self.theme.background,
                                        (cx_note, y), 12)

        # Now the lane strips (finger labels). Target rings get drawn last
        # so they sit on top of everything and the user can always see
        # exactly where to land the press.
        for ls in self.lanes:
            ls.draw(surf, now)

        # Target rings on top of everything. Outline only (not filled) so
        # the falling note remains visible inside the ring just before
        # the press lands. When the lane below is mid-flash from a
        # press outcome, the ring adopts the outcome colour AND fills
        # with a semi-transparent disc so the green / orange / red is
        # impossible to miss - the patient's eye is on the ring, not
        # the strip below.
        for ls in self.lanes:
            cx_t = ls.rect.centerx
            # Default ring style; thickens up and grows slightly when a
            # note is in the press window so the eye gets pulled there.
            ring_r = TARGET_R
            thickness = 5
            if self.engine.mode and hasattr(self.engine.mode, "upcoming"):
                upcoming = self.engine.mode.upcoming(self.LOOKAHEAD_S)
                close = [s for s in upcoming if s.note.lane == ls.lane]
                if close:
                    song_t = getattr(self.engine.mode,
                                     "display_song_time",
                                     self.engine.mode.song_time)
                    ahead = close[0].note.t - song_t
                    if -0.2 <= ahead <= 0.4:
                        ring_r = TARGET_R + 5
                        thickness = 9
            # Outcome flash overrides the hand colour so the press
            # result reads at a glance.
            is_flashing = (now < ls.flash_until
                            and ls.flash_colour is not None)
            if is_flashing:
                border_colour = ls.flash_colour
                # Filled disc inside the ring in the outcome colour at
                # high alpha so the ring really pops on the press.
                fill_surf = pygame.Surface(
                    (ring_r * 2 + 4, ring_r * 2 + 4), pygame.SRCALPHA,
                )
                pygame.draw.circle(fill_surf, (*ls.flash_colour, 170),
                                    (ring_r + 2, ring_r + 2), ring_r)
                surf.blit(fill_surf,
                           (cx_t - ring_r - 2, strike_y - ring_r - 2))
                thickness = max(thickness, 9)
            else:
                border_colour = ls.HAND_BADGE.get(ls.hand,
                                                    self.theme.foreground)
            # Faint outer halo so the ring really pops off the page.
            halo_surf = pygame.Surface(
                ((ring_r + 8) * 2, (ring_r + 8) * 2), pygame.SRCALPHA,
            )
            halo_alpha = 110 if is_flashing else 50
            pygame.draw.circle(halo_surf, (*border_colour, halo_alpha),
                                (ring_r + 8, ring_r + 8), ring_r + 8)
            surf.blit(halo_surf,
                       (cx_t - ring_r - 8, strike_y - ring_r - 8))
            # Outer ring outline in the active colour.
            pygame.draw.circle(surf, border_colour,
                                (cx_t, strike_y), ring_r, thickness)
            # Inner contrast ring for high-readability on any theme.
            # Skip during flash so the filled disc inside the ring stays
            # uninterrupted by a thin background ring.
            if not is_flashing:
                pygame.draw.circle(surf, self.theme.background,
                                    (cx_t, strike_y), ring_r - thickness, 2)

        # Particle bursts from hits. Drawn AFTER the lane strips +
        # rings so they fly out over the top of everything.
        for b in self._bursts:
            b.draw(surf)
        # Floating hit/miss popups.
        for p in self._popups:
            p.draw(surf, self.layout)

        # Countdown card before the music kicks in. Rendered LAST so
        # it sits on top of every other layer (guide lines, strike
        # rings, lane strips) and reads as the clear focal point of
        # the "get ready" moment - the patient should know not to
        # press yet. An earlier version sat between the guide lines
        # and the rings, which let the rings poke through the card
        # and undercut the "wait" message.
        if self.engine.mode:
            countdown = getattr(self.engine.mode, "countdown_remaining_s", 0.0)
            if countdown > 0:
                # Faint backdrop dim so the card owns the moment.
                # Cached surface: draw runs every frame.
                if (self._dim_cache is None
                        or self._dim_cache.get_size() != surf.get_size()):
                    self._dim_cache = pygame.Surface(surf.get_size(),
                                                      pygame.SRCALPHA)
                    self._dim_cache.fill((0, 0, 0, 60))
                surf.blit(self._dim_cache, (0, 0))
                card_w = 420
                card_h = 240
                card_rect = pygame.Rect(0, 0, card_w, card_h)
                card_rect.center = (cx, self.layout.height // 2)
                # Soft drop shadow built off-screen so the fade is
                # smooth into the page background.
                shadow_surf = pygame.Surface(
                    (card_w + 24, card_h + 24), pygame.SRCALPHA,
                )
                for dy, alpha in ((2, 50), (6, 28), (12, 10)):
                    pygame.draw.rect(
                        shadow_surf, (0, 0, 0, alpha),
                        pygame.Rect(12, 12 + dy, card_w, card_h),
                        border_radius=22,
                    )
                surf.blit(shadow_surf,
                           (card_rect.x - 12, card_rect.y - 12))
                # Themed fill at high alpha so the card reads as a
                # solid panel while still showing a hint of the lane
                # area underneath; the ring and the number wear
                # rhythm's purple so even the countdown carries the
                # mode's identity.
                accent = self._mode_accent()
                fill_surf = pygame.Surface(card_rect.size, pygame.SRCALPHA)
                fill = (*self.theme.background, 245)
                pygame.draw.rect(fill_surf, fill,
                                  fill_surf.get_rect(), border_radius=22)
                pygame.draw.rect(fill_surf, (*accent, 150),
                                  fill_surf.get_rect(), 3, border_radius=22)
                surf.blit(fill_surf, card_rect.topleft)
                draw_text(surf, "GET READY",
                          (card_rect.centerx, card_rect.y + 56),
                          self.theme, self.layout, pt=FONT_H1,
                          centre=True, colour=self.theme.muted)
                draw_text(surf, f"{countdown:.1f}",
                          (card_rect.centerx, card_rect.y + 156),
                          self.theme, self.layout, pt=140,
                          centre=True, colour=accent)

        # Corner Controls note: silent on the real sensor device, drawn
        # only in keyboard-fallback sessions (audit finding #110 --
        # the old comment here assumed the Arduino is always connected
        # by this point, which is false in a keyboard-fallback session).
        lines = keyboard_controls_lines(self.engine, self.engine.mode)
        if lines:
            pf = self.layout.font(FONT_SMALL)
            right = self.layout.width - 24
            y = self.layout.height - 22 - 18 * len(lines)
            head = pf.render("Controls", True, self.theme.muted)
            surf.blit(head, head.get_rect(topright=(right, y - 20)))
            for line in lines:
                t = pf.render(line, True, self.theme.muted)
                surf.blit(t, t.get_rect(topright=(right, y)))
                y += 18

        # One skip control for every enforced wait. Rhythm's own wait
        # is the countdown and silent lead welded to the front of the
        # note-fall timeline, armed by the mode.
        draw_skip_chip(surf, self.layout, self.theme, self.engine)

        # Skipped under either exit guard, same as GameplayScreen: the
        # guard is the frame's one message.
        if self.engine.paused and not self.engine.exit_overlay_active:
            self._draw_paused_overlay(surf)


class RhythmSetupScreen(Screen):
    """Two-column song-select style: track list on the left, song details
    + difficulty + preview/start on the right. Mirrors what music rhythm
    games like osu! and Guitar Hero do, which felt the most readable when
    I tried them. No BPM clutter, the track's own tempo is used."""

    DIFFICULTIES = ("easy", "medium", "hard")
    # The selected song plays itself for this long, then stops: on
    # entry (the default pick included), and again on every pick.
    # Four seconds says which song it is without playing the intro
    # the block is about to play. Basil's number.
    PREVIEW_S = 4.0

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self._tracks: list = []
        self._track_rects: list[tuple[pygame.Rect, object]] = []
        self._selected_track: str | None = None
        self._selected_difficulty = engine.cfg.get("rhythm.difficulty", "medium")
        self._previewing: bool = False
        self._preview_stop_at: float = 0.0
        # A preview owed to the current pick that has not started yet:
        # it waits for the menu playlist to finish fading (the two
        # share one stream, and a hard cut over the fade is what
        # "colliding" sounds like). update() starts it.
        self._preview_pending: bool = False
        # Swappable clock so tests can step past the four seconds.
        self._clock = time.perf_counter
        self._scroll_y = 0
        # Scrollbar drag state. Rect is set every frame by
        # _draw_track_list so handle_event can collide against it; None
        # means the list fits on screen and no bar is shown.
        self._scrollbar_track_rect: pygame.Rect | None = None
        self._scrollbar_dragging = False
        self.refresh()
        # Layout: left half is the track list card, right half is the
        # song-detail panel with difficulty + preview + start.
        w = engine.layout.width
        h = engine.layout.height
        self._list_rect = pygame.Rect(40, 180, w // 2 - 60, h - 280)
        self._detail_rect = pygame.Rect(w // 2 + 20, 180, w // 2 - 60, h - 280)

        # Right-panel buttons. All positioned relative to the detail rect.
        dx = self._detail_rect.x
        dw = self._detail_rect.w
        # Difficulty pills, evenly spaced inside the panel.
        diff_y = self._detail_rect.bottom - 260
        pill_w = (dw - PADDING * 4) // 3
        self.easy_btn = Button(
            pygame.Rect(dx + PADDING, diff_y, pill_w, 56),
            "Easy", lambda: self._set_difficulty("easy"),
            self.theme, self.layout, font_pt=FONT_H2,
        )
        self.med_btn = Button(
            pygame.Rect(dx + PADDING * 2 + pill_w, diff_y, pill_w, 56),
            "Medium", lambda: self._set_difficulty("medium"),
            self.theme, self.layout, font_pt=FONT_H2,
        )
        self.hard_btn = Button(
            pygame.Rect(dx + PADDING * 3 + pill_w * 2, diff_y, pill_w, 56),
            "Hard", lambda: self._set_difficulty("hard"),
            self.theme, self.layout, font_pt=FONT_H2,
        )

        # Preview + start row.
        action_y = self._detail_rect.bottom - 90
        self.preview_btn = Button(
            pygame.Rect(dx + PADDING, action_y, dw // 2 - PADDING * 2, BUTTON_H),
            "Play preview", self._toggle_preview,
            self.theme, self.layout, font_pt=FONT_H2,
        )
        self.start_btn = Button(
            pygame.Rect(dx + dw // 2 + PADDING // 2, action_y,
                         dw // 2 - PADDING * 2, BUTTON_H + 4),
            "START", self._start,
            self.theme, self.layout,
            font_pt=FONT_H2, primary=True,
        )

        # Footer buttons.
        self.back_btn = Button(
            pygame.Rect(40, h - 80, 180, BUTTON_H - 10),
            "Back", self._back_to_modes, self.theme, self.layout,
        )
        self.refresh_btn = Button(
            pygame.Rect(w - 220, h - 80, 180, BUTTON_H - 10),
            "Rescan", self.refresh,
            self.theme, self.layout, font_pt=FONT_BODY,
        )

    def refresh(self) -> None:
        music_dir = self.engine.cfg.resolve_path(
            self.engine.cfg.get("audio.music_dir", "assets/music")
        )
        found: list = []
        if music_dir.exists():
            for p in sorted(music_dir.iterdir()):
                if p.suffix.lower() in (".mp3", ".wav", ".ogg", ".flac"):
                    found.append(p)
        self._tracks = found
        if not hasattr(self, "_durations"):
            self._durations = {}
        # Drop cache entries for tracks that vanished.
        live_keys = {str(p) for p in self._tracks}
        for k in list(self._durations.keys()):
            if k not in live_keys:
                del self._durations[k]
        # Pre-pick the first available track so the user can hit Start
        # straight away if the previous selection is gone.
        if self._selected_track and not any(str(t) == self._selected_track
                                             for t in self._tracks):
            self._selected_track = None
        if self._selected_track is None and self._tracks:
            self._selected_track = str(self._tracks[0])
        # Kick off duration probing in the background so the UI stays
        # responsive (librosa.get_duration is fast per-track but adds
        # up across many tracks). Rows show "..." until the worker
        # fills the cache.
        self._spawn_duration_worker()
        # Landing here (or a rescan) owes the pick a preview, the
        # default pick included: the RA hears which song START will
        # play without having to press anything.
        self._stop_preview()
        self._preview_pending = bool(self._selected_track)

    def _spawn_duration_worker(self) -> None:
        # Already running? Skip - the existing worker will pick up new
        # entries on its next iteration (it re-reads self._tracks each
        # time so a Rescan during scanning isn't a problem).
        thread = getattr(self, "_dur_thread", None)
        if thread is not None and thread.is_alive():
            return
        import threading
        from ..audio.beatmap import DECODE_LOCK
        try:
            import librosa
        except ImportError:
            librosa = None

        def _probe():
            if librosa is None:
                # Mark all tracks as "unknown" so the UI shows --:-- and
                # doesn't try again.
                for p in list(self._tracks):
                    self._durations.setdefault(str(p), None)
                return
            for p in list(self._tracks):
                key = str(p)
                if key in self._durations:
                    continue
                try:
                    # Held for the same reason extract_beatmap holds it:
                    # get_duration opens the file through soundfile, and
                    # two threads inside sf_open on an mp3 at once kill
                    # the process with SIGBUS. The guard above only stops
                    # THIS screen starting a second worker, so two
                    # screens (or a screen and a beatmap extraction)
                    # still overlap without the lock.
                    with DECODE_LOCK:
                        dur = float(librosa.get_duration(path=key))
                    self._durations[key] = dur
                except (FileNotFoundError, OSError, RuntimeError,
                        ValueError):
                    # File missing, unreadable, or unsupported audio
                    # codec. None marks the row so the UI shows
                    # `--:--` and the user can re-pick.
                    self._durations[key] = None

        self._dur_thread = threading.Thread(
            target=_probe, daemon=True, name="rhythm-dur-probe",
        )
        self._dur_thread.start()

    @staticmethod
    def _fmt_mmss(seconds: float | None) -> str:
        if seconds is None or seconds <= 0:
            return "--:--"
        s = int(round(seconds))
        return f"{s // 60:d}:{s % 60:02d}"

    def _set_difficulty(self, d: str) -> None:
        if d in self.DIFFICULTIES:
            self._selected_difficulty = d

    def _stop_preview(self) -> None:
        self._preview_pending = False
        if self.engine.audio and self._previewing:
            try:
                self.engine.audio.stop()
            except (AttributeError, RuntimeError, OSError) as e:
                # Audio engine already torn down or pygame mixer
                # uninitialised (test path). Either way the stop is
                # a no-op and we just need to clear the local
                # previewing state below.
                log.debug("audio.stop during preview teardown: %s", e)
        self._previewing = False
        self._preview_stop_at = 0.0

    def _menu_music_faded(self) -> bool:
        """Whether the menu playlist has left the stream. The preview
        waits for this so it never lands over the fade."""
        player = getattr(self.engine, "menu_music", None)
        return player is None or getattr(player, "state", "idle") == "idle"

    def _start_preview(self) -> None:
        """Play the selected song from the top for PREVIEW_S. A pick
        while one is playing starts over from the new pick."""
        self._stop_preview()
        if not self._selected_track or self.engine.audio is None:
            return
        if not self._menu_music_faded():
            self._preview_pending = True
            return
        if self.engine.audio.play_song(self._selected_track):
            self._previewing = True
            self._preview_stop_at = self._clock() + self.PREVIEW_S

    def _toggle_preview(self) -> None:
        # The button: stop a running preview, or play the pick again.
        if self._previewing:
            self._stop_preview()
            return
        self._start_preview()

    def _back_to_modes(self) -> None:
        self._stop_preview()
        self.engine.show_mode_select()

    def _start(self) -> None:
        from ..audio.beatmap import extract_beatmap
        self._stop_preview()
        if not self._selected_track:
            # Nothing selected. Refuse to start so the user picks one
            # from the list. The list pre-fills the first track on
            # refresh, so this only fires if the music folder is empty.
            return
        diff = self._selected_difficulty
        bm = extract_beatmap(self._selected_track,
                              difficulty=diff,
                              num_lanes=self.engine.total_lanes)
        self.engine.cfg.data.setdefault("rhythm", {})["difficulty"] = diff
        self.engine.begin_rhythm_block(bm)

    def update(self, dt: float) -> None:
        # A preview owed to the pick starts once the menu playlist has
        # faded off the shared stream.
        if self._preview_pending and self._menu_music_faded():
            self._start_preview()
        # Auto-stop the preview after PREVIEW_S seconds.
        if self._previewing and self._clock() >= self._preview_stop_at:
            self._stop_preview()

    def _max_scroll(self) -> int:
        """Largest scroll offset that still keeps the bottom row visible.
        Used to clamp wheel + scrollbar drag so the list doesn't fly past
        the end into empty space."""
        inner_h = self._list_rect.h - 70
        row_h = 56
        content_h = len(self._tracks) * row_h
        return max(0, content_h - inner_h)

    def handle_event(self, e: pygame.event.Event) -> None:
        for b in (self.easy_btn, self.med_btn, self.hard_btn,
                  self.preview_btn, self.start_btn,
                  self.back_btn, self.refresh_btn):
            b.handle_event(e)
        if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
            # Same as clicking START: refresh() already pre-selects the
            # first track and a difficulty default comes from config, so
            # a keyboard-only session (audit finding #113: this screen
            # was mouse-click only for both track pick and START) can
            # still start straight away without ever picking a
            # different track.
            self._start()
            return
        if e.type == pygame.MOUSEWHEEL:
            # Scroll the track list when the cursor is hovering it.
            # Clamped at both ends so the wheel stops at top + bottom
            # rather than drifting into empty space below the last row.
            mx, my = self.engine._to_logical(pygame.mouse.get_pos())
            if self._list_rect.collidepoint((mx, my)):
                step = e.y * 30
                self._scroll_y = max(
                    0, min(self._max_scroll(), self._scroll_y - step),
                )
        # Scrollbar drag: click anywhere on the track of the scrollbar
        # to jump to that fraction, or click+drag the thumb. We track
        # drag state across MOUSEMOTION events.
        if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                and self._scrollbar_track_rect is not None
                and self._scrollbar_track_rect.collidepoint(e.pos)):
            self._scrollbar_dragging = True
            self._scroll_y = self._scroll_y_for_mouse_y(e.pos[1])
            return
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self._scrollbar_dragging = False
        if (e.type == pygame.MOUSEMOTION
                and getattr(self, "_scrollbar_dragging", False)):
            self._scroll_y = self._scroll_y_for_mouse_y(e.pos[1])
            return
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for rect, path in self._track_rects:
                if rect.collidepoint(e.pos):
                    # Any pick, the same song included, plays its
                    # preview again from the top.
                    self._selected_track = (str(path) if path is not None
                                            else None)
                    self._start_preview()
                    return

    def _scroll_y_for_mouse_y(self, mouse_y: int) -> int:
        """Map a click / drag y-position on the scrollbar track into a
        clamped _scroll_y value. The mouse y is mapped to the middle of
        the thumb so the cursor doesn't snap to the top of the thumb on
        a click in the middle of the track."""
        track = self._scrollbar_track_rect
        if track is None or track.h <= 0:
            return self._scroll_y
        max_s = self._max_scroll()
        if max_s <= 0:
            return 0
        frac = (mouse_y - track.y) / track.h
        frac = max(0.0, min(1.0, frac))
        return int(frac * max_s)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        _draw_header(surf, "Pick a song",
                     "The picked song plays a 4 second preview. Choose "
                     "a difficulty, then press START.",
                     self.theme, self.layout)
        self._draw_track_list(surf)
        self._draw_detail_panel(surf)
        self.back_btn.draw(surf)
        self.refresh_btn.draw(surf)

    def _draw_track_list(self, surf: pygame.Surface) -> None:
        # Left-half card with a scrolling track list. Each row is a card-
        # style tile rather than a plain rectangle so the selected one
        # stands out clearly.
        list_card = Card(self._list_rect, self.theme,
                          title="Tracks", layout=self.layout)
        list_card.draw(surf)
        # Count chip in the top-right of the card so the user knows
        # how many tracks were detected without scrolling. Sits next
        # to the card title that Card.draw renders at the top-left.
        n = len(self._tracks)
        chip_label = f"{n} track" if n == 1 else f"{n} tracks"
        chip_font = self.layout.font(FONT_SMALL + 2)
        chip_text = chip_font.render(chip_label, True,
                                      self.theme.background)
        chip_pad_x = 14
        chip_w = chip_text.get_width() + chip_pad_x * 2
        chip_h = 26
        chip_rect = pygame.Rect(
            self._list_rect.right - PADDING - chip_w,
            self._list_rect.y + 22,
            chip_w, chip_h,
        )
        pygame.draw.rect(surf, self.theme.accent, chip_rect,
                          border_radius=chip_h // 2)
        surf.blit(chip_text, chip_text.get_rect(center=chip_rect.center))
        self._track_rects = []
        # Clamp scroll first so a list shrink (e.g. after Refresh) can't
        # leave _scroll_y past the new end.
        self._scroll_y = max(0, min(self._max_scroll(), self._scroll_y))
        # Clip the track rows to the inside of the card so they don't
        # bleed over the header / footer. Leave a small right-edge gap
        # for the scrollbar when one is needed.
        inner = self._list_rect.inflate(-PADDING * 2, -PADDING * 2)
        inner.y = self._list_rect.y + 60
        inner.h = self._list_rect.h - 70
        needs_bar = self._max_scroll() > 0
        if needs_bar:
            inner.w -= 14   # leave room for the bar gutter
        surf.set_clip(inner)
        rows: list[tuple[str, object]] = [
            (p.name, p) for p in self._tracks
        ]
        row_h = 56
        y = inner.y - self._scroll_y
        for label, path in rows:
            r = pygame.Rect(inner.x, y, inner.w, row_h - 6)
            self._track_rects.append((r, path))
            selected = (
                (path is None and self._selected_track is None)
                or (path is not None and str(path) == self._selected_track)
            )
            # Soft background for every row, accent fill for the selected.
            if selected:
                pygame.draw.rect(surf, self.theme.accent, r, border_radius=8)
            else:
                pygame.draw.rect(surf, self.theme.muted, r, 1,
                                  border_radius=8)
            # Track name on the left, file extension chip on the right so
            # the row reads at a glance.
            text_colour = (self.theme.background if selected
                            else self.theme.foreground)
            draw_text(surf, label, (r.x + 16, r.y + 14),
                      self.theme, self.layout, pt=FONT_BODY,
                      colour=text_colour)
            if path is not None:
                # Show the song duration on the right. "..." while the
                # background probe is still working on it. Right-align
                # via the font's render rect so 0:47 and 4:32 line up.
                key = str(path)
                if key in self._durations:
                    dur_text = self._fmt_mmss(self._durations[key])
                else:
                    dur_text = "..."
                dfont = self.layout.font(FONT_SMALL + 2)
                dsurf = dfont.render(dur_text, True, text_colour)
                surf.blit(dsurf, dsurf.get_rect(
                    midright=(r.right - 16, r.centery)))
            y += row_h
        surf.set_clip(None)
        # Scrollbar on the right edge of the card. Drawn outside the
        # clip so the track itself + thumb show up even when the rows
        # are clipped.
        if needs_bar:
            bar_x = inner.right + 4
            bar_w = 8
            track_top = inner.y
            track_h = inner.h
            track_rect = pygame.Rect(bar_x, track_top, bar_w, track_h)
            self._scrollbar_track_rect = track_rect
            # Faint background track.
            pygame.draw.rect(surf,
                              tuple(max(0, c - 16)
                                    for c in self.theme.background),
                              track_rect, border_radius=bar_w // 2)
            # Thumb. Its length is the visible-fraction of total
            # content; its top is the scroll-fraction down the track.
            content_h = len(self._tracks) * row_h
            visible_frac = max(0.15, min(1.0, inner.h / max(1, content_h)))
            thumb_h = max(30, int(track_h * visible_frac))
            max_top_offset = track_h - thumb_h
            max_s = self._max_scroll()
            scroll_frac = (self._scroll_y / max_s) if max_s > 0 else 0
            thumb_y = track_top + int(max_top_offset * scroll_frac)
            thumb_rect = pygame.Rect(bar_x, thumb_y, bar_w, thumb_h)
            thumb_colour = (self.theme.accent
                            if self._scrollbar_dragging
                            else self.theme.muted)
            pygame.draw.rect(surf, thumb_colour, thumb_rect,
                              border_radius=bar_w // 2)
        else:
            self._scrollbar_track_rect = None

    def _draw_detail_panel(self, surf: pygame.Surface) -> None:
        # Right-half card with the current selection's name, difficulty
        # buttons, and the preview / start actions.
        detail_card = Card(self._detail_rect, self.theme,
                            title="Selected", layout=self.layout)
        detail_card.draw(surf)
        dx = self._detail_rect.x
        dy = self._detail_rect.y
        dw = self._detail_rect.w

        # Track name. With the "No music" option gone there should always
        # be a real track selected when the music folder is populated.
        if self._selected_track:
            title = self._selected_track.rsplit("/", 1)[-1]
            if "." in title:
                title = title.rsplit(".", 1)[0].replace("_", " ")
        else:
            title = "No tracks found"
        # Bold title rendered via SysFont so the selection reads as the
        # focal point of the panel.
        title_pt = int(FONT_H2 * self.layout.font_scale)
        title_font = make_font(title_pt, bold=True)
        title_surf = title_font.render(title, True, self.theme.foreground)
        surf.blit(title_surf,
                   title_surf.get_rect(center=(dx + dw // 2, dy + 86)))
        # Duration line below the title when we have it cached, else
        # the friendly fallback subtitle.
        if (self._selected_track
                and self._durations.get(self._selected_track) is not None):
            dur = self._fmt_mmss(self._durations[self._selected_track])
            subtitle = f"Length {dur}"
        elif self._selected_track:
            subtitle = "Loading length..."
        else:
            subtitle = "Drop an .mp3 into the music folder and rescan"
        draw_text(surf, subtitle,
                  (dx + dw // 2, dy + 124),
                  self.theme, self.layout, pt=FONT_BODY - 2,
                  centre=True, colour=self.theme.muted)

        # Difficulty section. Bigger label so it reads as a real
        # heading inside the card, with the description living right
        # under the pills for direct association.
        draw_text(surf, "DIFFICULTY",
                  (dx + dw // 2, self.easy_btn.rect.y - 30),
                  self.theme, self.layout, pt=FONT_SMALL + 4,
                  centre=True, colour=self.theme.muted)
        for b, key in ((self.easy_btn, "easy"),
                        (self.med_btn, "medium"),
                        (self.hard_btn, "hard")):
            b.primary = (key == self._selected_difficulty)
            b.draw(surf)
        # Brief one-liner explaining what each difficulty does.
        diff_text = {
            "easy":   "Every 4th beat. Gentle pace for beginners.",
            "medium": "Every 2nd beat. Standard rehab pacing.",
            "hard":   "Every beat. Full tempo, more presses per minute.",
        }[self._selected_difficulty]
        draw_text(surf, diff_text,
                  (dx + dw // 2, self.easy_btn.rect.bottom + 22),
                  self.theme, self.layout, pt=FONT_SMALL + 2,
                  centre=True, colour=self.theme.foreground)

        # Preview + start buttons. Label swaps to "Stop preview" so
        # the same button serves as both the toggle and the live state
        # indicator. (No countdown text below; the button itself says
        # everything the patient needs.)
        self.preview_btn.label = (
            "Stop preview" if self._previewing else "Play preview"
        )
        self.preview_btn.draw(surf)
        if self._selected_track is None and not self._previewing:
            overlay = pygame.Surface(self.preview_btn.rect.size,
                                      pygame.SRCALPHA)
            overlay.fill((128, 128, 128, 130))
            surf.blit(overlay, self.preview_btn.rect.topleft)
        self.start_btn.draw(surf)


class ResultsScreen(Screen):
    # Header for a finished game. It must never claim the SESSION is
    # over: a game's natural end lands back on game select with the
    # player still logged in, and the only thing that ends a session
    # is the End-session dialog. "Session complete" here contradicted
    # the buttons right under it (Play again / End session).
    RESULTS_TITLE = "Game complete"

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        cx = engine.layout.width // 2
        # Four buttons centred on the screen:
        # Retry (primary, re-runs the same block) | Play again
        # (back to game select) | Data folder (opens the game's
        # folder in Finder / Explorer so the researcher can reach the
        # CSVs + report without hunting) | End session (routes through
        # the engine's End-session dialog, the same warning game
        # select's own button raises, since leaving for the login
        # screen ends the whole session from here too).
        btn_w = 190
        gap = 14
        total_w = btn_w * 5 + gap * 4
        x = cx - total_w // 2
        y = 696
        h = BUTTON_H + 4
        self.retry_btn = Button(
            pygame.Rect(x, y, btn_w, h),
            "Retry",
            engine.retry_last_block,
            self.theme, self.layout, font_pt=FONT_H2,
        )
        x += btn_w + gap
        # Named for where it goes, not for what it used to say: the
        # NEXT UP card is now the "play again" affordance, and this
        # is the way back to the hub.
        self.again_btn = Button(
            pygame.Rect(x, y, btn_w, h),
            "Game menu", engine.show_mode_select,
            self.theme, self.layout, font_pt=FONT_H2,
        )
        x += btn_w + gap
        self.folder_btn = Button(
            pygame.Rect(x, y, btn_w, h),
            "Data folder", engine.open_last_session_folder,
            self.theme, self.layout, font_pt=FONT_H2,
        )
        x += btn_w + gap
        self.detail_btn = Button(
            pygame.Rect(x, y, btn_w, h),
            "More detail", self._toggle_details,
            self.theme, self.layout, font_pt=FONT_H2,
        )
        x += btn_w + gap
        self.title_btn = Button(
            pygame.Rect(x, y, btn_w, h),
            "End session", engine.request_end_session,
            self.theme, self.layout, font_pt=FONT_H2,
        )
        # The NEXT UP button lives inside its card, not in the row: it
        # is the one action the screen is steering towards, and a
        # sixth button in a row of five would read as just another
        # option. Label and colour are set per suggestion at draw time.
        nx, ny, nw, _nh = self.NEXT_CARD_RECT
        self.next_btn = Button(
            pygame.Rect(nx + 32, ny + 256, nw - 64, BUTTON_H + 14),
            "Start", self._start_next_up,
            self.theme, self.layout, font_pt=FONT_H2,
            primary=True,
        )
        # Slim by default. The full read-out (every card the mode
        # produces plus the per-finger charts) is one press away and
        # never sticks: a fresh game lands on the slim screen again.
        self.show_details = False

        # Sensory Cues, here as well as in Settings.
        #
        # Between two blocks is exactly when the cue condition gets
        # changed: run one with the buzzer, run the next without, and
        # compare. Making that a trip back to the title screen and into
        # Settings put four clicks between the researcher and the thing
        # they came here to do, and the setting is recorded per trial
        # anyway, so the two blocks stay separable afterwards.
        #
        # Lives top-left as a header utility (balancing the mode pill
        # top-right) and opens downward over the empty flank beside
        # the grade ring. Its old spot low-right sat on the saved-to
        # footer and clipped its own label.
        self._cue_menu = ToggleMenu(
            pygame.Rect(28, 26, 306, 44),
            list(CUE_ROWS),
            get_value=lambda k: bool(self.engine.cfg.get(k, True)),
            on_toggle=lambda k, v: apply_cue_setting(self.engine, k, v),
            theme=self.theme, layout=self.layout,
            title="Cues for the next block",
        )
        # Menu-music mute, on the same top row right of the cue pill
        # (the corner itself is the pill's).
        self.mute_btn = MuteButton(
            engine, pygame.Rect(28 + 306 + 12, 31, MuteButton.W,
                                MuteButton.H))

        # When the screen was last entered, for the one-shot entry
        # animation (ring sweep + stat count-up). Zero means "never
        # notified", which draws the finished state so a bare draw()
        # in a test never renders a half-swept ring.
        self._shown_t = 0.0
        # This session's per-mode first-go-against-latest rows, rebuilt
        # on every on_show. None means "not built yet".
        self._progress_rows: list[dict] | None = None

    def on_show(self) -> None:
        """Engine hook: a block just landed here, restart the entry
        animation and fold the detail view away so the next game ends
        on the slim screen it was designed to end on."""
        self._shown_t = time.perf_counter()
        self.show_details = False
        self.detail_btn.label = "More detail"
        # The session-so-far row is rebuilt once per block, not per
        # frame: it walks every game of the session and reads a
        # summary per mode.
        self._progress_rows = None

    # ---- session so far ---------------------------------------------------
    # The single long session's whole point is that a participant sees
    # their own numbers move inside one sitting (docs/research/
    # healthy_baseline_study.txt Section 2.1). This row is where they
    # see it: the mode just played against that person's FIRST go at it
    # today, in the mode's own words, and a short chip for every other
    # mode with two goes behind it. Only this session's log is read, so
    # nothing here can compare against a different day.
    PROGRESS_LABEL = "SO FAR"
    PROGRESS_MAX_CHIPS = 6

    def _progress(self) -> list[dict]:
        rows = getattr(self, "_progress_rows", None)
        if rows is None:
            try:
                from ..game.battery import progress_rows
                rows = progress_rows(self.engine.session_games_log())
            except Exception:
                # A bare engine in a test double must not take the
                # results screen down with it.
                rows = []
            self._progress_rows = rows
        return rows

    def _progress_row_for(self, mode: str, hand: str) -> dict | None:
        for row in self._progress():
            if row.get("mode") == mode and row.get("hand") == hand:
                return row
        return None

    def _progress_colour(self, better) -> tuple[int, int, int]:
        """Green for better, amber for worse, grey for a change too
        small to print. Grey is not a failure state: it is the honest
        answer when the number did not move."""
        if better is None:
            return self.theme.muted
        return self.theme.success if better else self.theme.warning

    @staticmethod
    def _progress_label(mode: str, hand: str) -> str:
        side = {"left": " L", "right": " R"}.get(str(hand), "")
        return f"{mode_title(mode)}{side}"

    def _battery_done(self) -> bool:
        """True on the results screen of the LAST PLAY ALL block.

        The card then has no next step to offer, and the last thing a
        study participant should be looking at is a rotation
        suggestion, so it becomes the TODAY table instead. A free game
        played afterwards is an ordinary game and gets NEXT UP back,
        which is why the last logged game has to be a battery block
        and not merely the battery being over.
        """
        try:
            progress = self.engine.battery_progress()
            if not (isinstance(progress, dict) and progress.get("finished")):
                return False
            log = self.engine.session_games_log()
        except Exception:
            return False
        return bool(log) and int(log[-1].get("battery_pos") or 0) > 0

    # Rows the TODAY panel can fit above the button.
    TODAY_MAX_ROWS = 9
    TODAY_ROW_H = 24

    def _draw_today_panel(self, surf: pygame.Surface,
                          rect: pygame.Rect) -> None:
        """PLAY ALL DONE: every mode played today, first go against
        latest, in the mode's own words.

        Only this participant's own numbers, and no comparison with
        anybody else, because the point of the panel is that a person
        can see their own session move. A mode played once says so
        rather than being dropped, so nobody wonders where it went.
        """
        draw_text(surf, "TODAY", (rect.x + 30, rect.y + 26),
                  self.theme, self.layout, pt=FONT_SMALL, centre=False,
                  colour=self.theme.accent)
        rows = self._progress()
        if not rows:
            draw_text(surf, "No finished games to compare yet.",
                      (rect.x + 30, rect.y + 70), self.theme, self.layout,
                      pt=FONT_BODY, centre=False, colour=self.theme.muted)
            return
        y = rect.y + 58
        name_x = rect.x + 30
        value_x = rect.x + 170
        change_x = rect.x + 320
        for row in rows[:self.TODAY_MAX_ROWS]:
            label = self._progress_label(str(row["mode"]), str(row["hand"]))
            # Measured against the gap to the value column, not a round
            # number: "Muscle Memory R" is wider than 140 px and ran
            # straight into the "100% to 100%" beside it.
            draw_text(surf, _fit_text(label, self.layout.font(FONT_SMALL + 2),
                                      value_x - name_x - 12),
                      (name_x, y), self.theme, self.layout,
                      pt=FONT_SMALL + 2, centre=False,
                      colour=self.theme.foreground)
            if int(row.get("n") or 0) >= 2:
                pair = f"{row['first_text']} to {row['latest_text']}"
                change = str(row.get("short") or "")
                colour = self._progress_colour(row.get("better"))
            else:
                pair = str(row.get("latest_text") or "")
                change = "played once"
                colour = self.theme.muted
            draw_text(surf, pair, (value_x, y), self.theme, self.layout,
                      pt=FONT_SMALL + 2, centre=False,
                      colour=self.theme.muted)
            draw_text(surf, _fit_text(change,
                                      self.layout.font(FONT_SMALL + 2),
                                      rect.right - 30 - change_x),
                      (change_x, y), self.theme, self.layout,
                      pt=FONT_SMALL + 2, centre=False, colour=colour)
            y += self.TODAY_ROW_H
        extra = len(rows) - self.TODAY_MAX_ROWS
        if extra > 0:
            draw_text(surf, f"+{extra} more", (name_x, y), self.theme,
                      self.layout, pt=FONT_SMALL, centre=False,
                      colour=self.theme.muted)
            y += self.TODAY_ROW_H
        draw_text(surf,
                  "Compared with your own first go today.",
                  (name_x, y + 4), self.theme, self.layout, pt=FONT_SMALL,
                  centre=False, colour=self.theme.muted)

    def _draw_progress_row(self, surf: pygame.Surface, left: int, cy: int,
                           right_limit: int) -> None:
        rows = [r for r in self._progress() if int(r.get("n") or 0) >= 2]
        if not rows:
            return
        here = (str(self.engine.current_block),
                str(getattr(self.engine, "hand_mode", "")))
        x = left
        # The mode just played leads, with the whole sentence: it is
        # the number the participant is looking at right now.
        lead = next((r for r in rows if (r["mode"], r["hand"]) == here),
                    None)
        if lead is not None and lead.get("text"):
            x += _strip_pill(surf, self.layout, x, cy, str(lead["text"]),
                             self._progress_colour(lead.get("better")),
                             font_pt=FONT_SMALL + 2) + 14
        others = [r for r in rows if r is not lead and r.get("short")]
        if not others:
            return
        label_font = self.layout.font(FONT_SMALL)
        draw_text(surf, self.PROGRESS_LABEL,
                  (x, cy - label_font.get_height() // 2),
                  self.theme, self.layout, pt=FONT_SMALL, centre=False,
                  colour=self.theme.muted)
        x += label_font.size(self.PROGRESS_LABEL)[0] + 12
        shown = 0
        # Room kept back for the overflow chip. Without it a mode that
        # did not fit vanished with nothing to say it had been cut,
        # and a participant would think the game had been forgotten.
        tail_w = self.layout.font(FONT_SMALL).size("+9 more")[0] + 28
        for row in others[:self.PROGRESS_MAX_CHIPS]:
            text = (f"{self._progress_label(str(row['mode']), str(row['hand']))}"
                    f"  {row['short']}")
            width = self.layout.font(FONT_SMALL).size(text)[0] + 20
            last = shown == len(others) - 1
            limit = right_limit if last else right_limit - tail_w
            if x + width > limit:
                break
            _strip_pill(surf, self.layout, x, cy, text,
                        self._progress_colour(row.get("better")))
            x += width + 8
            shown += 1
        extra = len(others) - shown
        if extra > 0:
            _strip_pill(surf, self.layout, x, cy, f"+{extra} more",
                        self.theme.muted)

    def _toggle_details(self) -> None:
        self.show_details = not self.show_details
        self.detail_btn.label = ("Hide detail" if self.show_details
                                 else "More detail")

    def _entry_frac(self) -> float:
        """0..1 cubic ease-out over the first 0.8 s on screen."""
        if self._shown_t <= 0:
            return 1.0
        t = (time.perf_counter() - self._shown_t) / 0.8
        if t >= 1.0:
            return 1.0
        t = max(0.0, t)
        return 1.0 - (1.0 - t) ** 3

    def handle_event(self, e: pygame.event.Event) -> None:
        # The menu gets first refusal. When it is open its rows sit over
        # the buttons, and a click landing on both would flip a switch
        # and start a block at the same time.
        if self._cue_menu.handle_event(e):
            return
        if self.mute_btn.handle_event(e):
            return
        self.retry_btn.handle_event(e)
        self.again_btn.handle_event(e)
        self.folder_btn.handle_event(e)
        self.detail_btn.handle_event(e)
        self.title_btn.handle_event(e)
        # The button is not drawn once PLAY ALL is done (the card is
        # the TODAY table then), so it must not take clicks either.
        if not self.show_details and not self._battery_done():
            self.next_btn.handle_event(e)
        # Enter confirms the primary (Retry) action, same convention as
        # the title screen's START shortcut (audit finding #113: this
        # screen was mouse-click only, so a keyboard-only session could
        # not continue past its own results screen).
        if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
            self.engine.retry_last_block()
        # Every other control on the screen gets a letter, so a
        # keyboard-only session can take the NEXT UP suggestion, walk
        # back to the hub or open the detail view without a mouse. G
        # for the game menu: M is the mute on every menu screen.
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_n:
            self._start_next_up()
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_g:
            self.engine.show_mode_select()
        elif e.type == pygame.KEYDOWN and e.key == pygame.K_d:
            self._toggle_details()

    # Grade thresholds from hit rate. S+ for near-perfect runs, D for low
    # accuracy. Same letter scheme rhythm games use.
    @staticmethod
    def _grade_for(rate: float) -> tuple[str, str]:
        if rate >= 0.95:
            return "S", "Outstanding work"
        if rate >= 0.85:
            return "A", "Great session"
        if rate >= 0.70:
            return "B", "Solid effort"
        if rate >= 0.50:
            return "C", "Good practice. Keep at it"
        # The bottom two letters are where a patient is most likely to
        # stop coming back, so the blurb credits the effort and names
        # the next step instead of grading the person.
        if rate >= 0.30:
            return "D", "Big effort. Rest, then again"
        return "E", "Every press was practice. Rest up"

    def _grade_colour(self, letter: str) -> tuple[int, int, int]:
        if letter == "S":
            return (255, 196, 0)               # gold
        if letter == "A":
            return self.theme.success
        if letter == "B":
            return self.theme.accent
        if letter == "C":
            return self.theme.warning
        return self.theme.error

    def _force_pilot_summary(self) -> dict | None:
        """The force_pilot section of the block summary, or None for
        every other mode. Read from session.block_summary (written at
        finish_block) so the screen does not re-run mode scoring per
        frame; falls back to the live mode's stats for a results view
        drawn before the summary landed."""
        if str(getattr(self.engine, "current_block", "")) != "force_pilot":
            return None
        summary = getattr(getattr(self.engine, "session", None),
                          "block_summary", None)
        if isinstance(summary, dict):
            fp = summary.get("force_pilot")
            if isinstance(fp, dict):
                return fp
        stats_fn = getattr(getattr(self.engine, "mode", None),
                           "block_stats", None)
        if callable(stats_fn):
            try:
                fp = stats_fn()
                return fp if isinstance(fp, dict) else None
            except Exception:
                return None
        return None

    def _mirror_summary(self) -> dict | None:
        """The mirror section of the block summary (mean sync gap +
        per-hand mean RT), or None for every other mode. Mirror has no
        mode.block_stats -- the gap is accumulated on the engine as
        trials log (see GameEngine.log_trial), so this only reads
        session.block_summary, no live fallback needed."""
        if str(getattr(self.engine, "current_block", "")) != "mirror":
            return None
        summary = getattr(getattr(self.engine, "session", None),
                          "block_summary", None)
        if isinstance(summary, dict):
            mir = summary.get("mirror")
            if isinstance(mir, dict):
                return mir
        return None

    def _adaptive_summary(self) -> dict | None:
        """The adaptive pace numbers (bpm_final / bpm_max, top level
        of the block summary), or None for every other mode. Pace is
        adaptive's trained quantity: the controller holds hit rate in
        a fixed band by design, so improvement moves BPM, not the hit
        rate the generic cards showed. Without a pace card the one
        number that says "you got better" was invisible in the app."""
        if str(getattr(self.engine, "current_block", "")) != "adaptive":
            return None
        summary = getattr(getattr(self.engine, "session", None),
                          "block_summary", None)
        if isinstance(summary, dict) and (
                summary.get("bpm_final") is not None
                or summary.get("bpm_max") is not None):
            return summary
        # Live fallback for a results view drawn before finish_block
        # persisted the summary.
        adapter = getattr(getattr(self.engine, "mode", None),
                          "adapter", None)
        if adapter is not None:
            try:
                return {
                    "bpm_final": round(float(adapter.bpm), 1),
                    "bpm_max": getattr(self.engine, "_block_bpm_max",
                                       None),
                }
            except (TypeError, ValueError):
                return None
        return None

    def _reaction_summary(self) -> dict | None:
        """The reaction section of the block summary, or None for
        every other mode. Same read path as _force_pilot_summary:
        session.block_summary first, live mode stats as fallback."""
        if str(getattr(self.engine, "current_block", "")) != "reaction":
            return None
        summary = getattr(getattr(self.engine, "session", None),
                          "block_summary", None)
        if isinstance(summary, dict):
            rx = summary.get("reaction")
            if isinstance(rx, dict):
                return rx
        stats_fn = getattr(getattr(self.engine, "mode", None),
                           "block_stats", None)
        if callable(stats_fn):
            try:
                rx = stats_fn()
                return rx if isinstance(rx, dict) else None
            except Exception:
                return None
        return None

    def _buzz_hunt_summary(self) -> dict | None:
        """The buzz_hunt section of the block summary, or None for
        every other mode. Same read path as _force_pilot_summary:
        session.block_summary first, live mode stats as fallback."""
        if str(getattr(self.engine, "current_block", "")) != "buzz_hunt":
            return None
        summary = getattr(getattr(self.engine, "session", None),
                          "block_summary", None)
        if isinstance(summary, dict):
            bh = summary.get("buzz_hunt")
            if isinstance(bh, dict):
                return bh
        stats_fn = getattr(getattr(self.engine, "mode", None),
                           "block_stats", None)
        if callable(stats_fn):
            try:
                bh = stats_fn()
                return bh if isinstance(bh, dict) else None
            except Exception:
                return None
        return None

    def _pattern_summary(self) -> dict | None:
        """The pattern section of the block summary, or None for every
        other mode. Same read path as _force_pilot_summary:
        session.block_summary first, live mode stats as fallback."""
        if str(getattr(self.engine, "current_block", "")) != "pattern":
            return None
        summary = getattr(getattr(self.engine, "session", None),
                          "block_summary", None)
        if isinstance(summary, dict):
            pat = summary.get("pattern")
            if isinstance(pat, dict):
                return pat
        stats_fn = getattr(getattr(self.engine, "mode", None),
                           "block_stats", None)
        if callable(stats_fn):
            try:
                pat = stats_fn()
                return pat if isinstance(pat, dict) else None
            except Exception:
                return None
        return None

    def _chords_summary(self) -> dict | None:
        """The chords section of the block summary, or None for every
        other mode. Same read path as _force_pilot_summary:
        session.block_summary first, live mode stats as fallback."""
        if str(getattr(self.engine, "current_block", "")) != "chords":
            return None
        summary = getattr(getattr(self.engine, "session", None),
                          "block_summary", None)
        if isinstance(summary, dict):
            ch = summary.get("chords")
            if isinstance(ch, dict):
                return ch
        stats_fn = getattr(getattr(self.engine, "mode", None),
                           "block_stats", None)
        if callable(stats_fn):
            try:
                ch = stats_fn()
                return ch if isinstance(ch, dict) else None
            except Exception:
                return None
        return None

    def _syllables_summary(self) -> dict | None:
        """The syllables section of the block summary, or None for
        every other mode. Same read path as _force_pilot_summary:
        session.block_summary first, live mode stats as fallback."""
        if str(getattr(self.engine, "current_block", "")) != "syllables":
            return None
        summary = getattr(getattr(self.engine, "session", None),
                          "block_summary", None)
        if isinstance(summary, dict):
            sy = summary.get("syllables")
            if isinstance(sy, dict):
                return sy
        stats_fn = getattr(getattr(self.engine, "mode", None),
                           "block_stats", None)
        if callable(stats_fn):
            try:
                sy = stats_fn()
                return sy if isinstance(sy, dict) else None
            except Exception:
                return None
        return None

    @staticmethod
    def _syllables_advice(sy: dict) -> str | None:
        """One supervisor-facing line off the block's first-press
        accuracy, which is what the mode's own staircase steers: it
        aims near 80 percent (the GraphoGame target and the
        convergence point of a 3-down-1-up rule) against a 25 percent
        chance floor. A block that lands well below chance-plus-a-bit
        means the child was guessing and the band or the foil rung
        wants a look; one that lands near perfect means the material
        stopped asking anything. Advice only, and never a claim about
        reading."""
        first = sy.get("first_press_accuracy")
        if first is None:
            first = sy.get("accuracy")
        if first is None:
            return None
        if first < 0.45:
            return ("Supervisor: close to guessing. An easier band "
                    "and a lower level next session.")
        if first > 0.95:
            return ("Supervisor: try the next band next session; the "
                    "words stopped asking anything.")
        return None

    def _draw_sticker_strip(self, surf: pygame.Surface) -> None:
        """Today's stickers on the finished screen: the last round's
        sticker has no break screen after it, so the full strip is
        shown here, once, before the session moves on. Session-local
        by design (the app keeps no cross-session history), which is
        why the label says today."""
        sy = self._syllables_summary()
        n = min(8, int((sy or {}).get("stickers") or 0))
        if n <= 0:
            return
        # Runtime import: syllables_screen imports this module at
        # load, so the stamp shape (shared so the sticker looks the
        # same here as on the break screen) has to come in here at
        # call time.
        from .syllables_screen import _star_points
        accent = mode_accent("syllables", self.theme)
        nx, ny, nw, nh = self.NEXT_CARD_RECT
        cy = ny + nh + 24
        r = 17
        spacing = 46
        label = self.layout.font(FONT_SMALL).render(
            "TODAY'S STICKERS", True, self.theme.muted)
        total = label.get_width() + 16 + 2 * r + spacing * (n - 1)
        x = nx + nw // 2 - total // 2
        surf.blit(label, label.get_rect(midleft=(x, cy)))
        x += label.get_width() + 16 + r
        for _ in range(n):
            pygame.draw.circle(surf, accent, (x, cy), r)
            pygame.draw.polygon(
                surf, (255, 255, 255),
                _star_points(x, cy, r * 0.55, r * 0.25))
            x += spacing

    def _echo_summary(self) -> dict | None:
        """The echo section of the block summary, or None for every
        other mode. Same read path as _force_pilot_summary:
        session.block_summary first, live mode stats as fallback."""
        if str(getattr(self.engine, "current_block", "")) != "echo":
            return None
        summary = getattr(getattr(self.engine, "session", None),
                          "block_summary", None)
        if isinstance(summary, dict):
            ec = summary.get("echo")
            if isinstance(ec, dict):
                return ec
        stats_fn = getattr(getattr(self.engine, "mode", None),
                           "block_stats", None)
        if callable(stats_fn):
            try:
                ec = stats_fn()
                return ec if isinstance(ec, dict) else None
            except Exception:
                return None
        return None

    def _buzz_hunt_hand_cards(self, label: str,
                               entries: dict) -> list[tuple]:
        """One stat card per hand for a buzz_hunt staircase (the
        duration threshold or the gap threshold): the two hands run
        independent staircases at different levels (bilateral play
        can easily be, say, right 300 ms vs left 120 ms), so a single
        averaged number represents neither hand, the same reasoning
        the notebook already applies to its own per-hand splits.
        A hand needs at least 2 reversals before its final staircase
        level counts as an estimate (Staircase.estimate's own rule);
        short of that the level is still descending from the config
        start, not a measured threshold, so the card says so plainly
        instead of showing the number (which, at the floor, would
        read as a real 40 ms threshold)."""
        hands = sorted(h for h, e in entries.items() if isinstance(e, dict))
        out = []
        for hand in hands:
            e = entries[hand]
            tag = (f"{label} {hand[0].upper()}"
                  if len(hands) > 1 else label)
            n_rev = e.get("n_reversals") or 0
            est = e.get("estimate_ms")
            if n_rev >= 2 and est is not None:
                out.append((tag, f"{float(est):.0f} ms",
                           self.theme.foreground))
            else:
                out.append((tag, "not reached", self.theme.muted))
        if not out:
            out.append((label, "n/a", self.theme.foreground))
        return out

    def _buzz_hunt_window_cards(self, window: dict) -> list[tuple]:
        """One WINDOW card per hand for the response-window ladder
        (2026-09, the localisation difficulty in place of the pulse
        staircase): the shortest window the hand reached, with the
        level it stands for. Per hand for the same reason the
        threshold cards were: bilateral hands climb independently and
        an average represents neither."""
        per_hand = window.get("per_hand") or {}
        levels = window.get("levels_s") or []
        hands = sorted(h for h, e in per_hand.items()
                       if isinstance(e, dict))
        out = []
        for hand in hands:
            e = per_hand[hand]
            tag = f"WINDOW {hand[0].upper()}" if len(hands) > 1 else "WINDOW"
            top = e.get("top_window_s")
            lvl = e.get("top_level")
            if top is None:
                out.append((tag, "n/a", self.theme.foreground))
                continue
            text = f"{float(top):.1f} s"
            if lvl is not None and levels:
                text += f" (L{int(lvl) + 1}/{len(levels)})"
            out.append((tag, text, self.theme.foreground))
        return out

    # Per-finger labels for the histogram x-axis. Order matches the
    # within-hand finger index used everywhere else (0=index..3=pinky).
    _FINGER_SHORT = ("I", "M", "R", "P")

    def _draw_per_lane_chart(self, surf: pygame.Surface,
                              rect: pygame.Rect, title: str,
                              values: list[float],
                              unit: str,
                              high_is_bad: bool,
                              levels: list[int] | None = None) -> None:
        """Render one bar chart inside `rect`.

        `values` is a per-lane list of length N (4 unilateral, 8
        bilateral). One bar per lane, bar height proportional to
        the value vs the max. Bar fill colour comes from
        theme.lane_idle for the within-hand finger index so the
        chart's visual identity matches the in-game lane tiles.

        `high_is_bad`: when True (misclick chart), the bar's outline
        goes red if the value is the worst in the chart, so the
        therapist's eye is pulled to problem fingers. When False
        (RT chart) the colour stays neutral - faster is better but
        a slow finger is data, not a problem.

        `levels`: optional per-lane corridor level (Force Pilot only).
        block_stats' own docstring warns that pooling a lane's stats
        across corridor levels misrepresents both (a narrower corridor
        mechanically lowers time-in-corridor for the same skill), so
        when two fingers in the same chart sit at different levels the
        bars are not the same measurement even though they are drawn
        on one axis; each finger's final level is appended to its
        x-axis label (audit finding #80) so that is visible at a
        glance instead of silent. None (every other mode) draws plain
        finger labels as before.
        """
        # Card-like background + outline (matches stat-card visual
        # treatment so the chart reads as a Results panel element).
        body = tuple(max(0, min(255, c - 8)) for c in self.theme.background)
        pygame.draw.rect(surf, body, rect, border_radius=14)
        outline = tuple(max(0, c - 30) for c in self.theme.background)
        pygame.draw.rect(surf, outline, rect, 1, border_radius=14)
        # Title across the top of the card.
        draw_text(surf, title, (rect.centerx, rect.y + 16),
                  self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)
        n = len(values)
        if n == 0:
            return
        # Bar area: leave room above (title) + below (x-labels +
        # value numbers).
        inner = rect.inflate(-24, 0)
        bar_top = rect.y + 38
        bar_bottom = rect.y + rect.h - 36
        bar_h_max = max(8, bar_bottom - bar_top)
        # Bar widths: split horizontal space evenly across bars with a
        # small gap. Bilateral (n=8) gets a tighter gap so the bars
        # don't go pencil-thin.
        gap = 6 if n > 4 else 12
        # Bilateral: a wider centre gap separates the two hand groups so
        # the chart reads as a left-hand block then a right-hand block,
        # matching the gameplay layout. Unilateral has no centre split.
        center_gap = 28 if n > 4 else 0
        bar_w = max(8, (inner.w - gap * (n - 1) - center_gap) // n)
        max_val = max(values) if max(values) > 0 else 1.0
        # Worst lane index for the red-outline cue (only used when
        # high_is_bad). values is lane-indexed, so this is a lane number.
        worst_lane = values.index(max(values)) if high_is_bad else -1
        # Left-to-right bar positions mapped to lane indices. Bilateral
        # mirrors the gameplay layout so the LEFT hand sits on the left
        # of the chart (lanes 7,6,5,4 = pinky..index) and the RIGHT hand
        # on the right (lanes 0,1,2,3 = index..pinky). Unilateral is just
        # lanes 0..3 in order.
        order = [7, 6, 5, 4, 0, 1, 2, 3] if n > 4 else list(range(n))
        for pos, lane in enumerate(order):
            v = values[lane]
            finger = lane % 4
            # The right-hand group (second four bars) shifts right by the
            # centre gap so the two hands read as separate blocks.
            extra = center_gap if (n > 4 and pos >= 4) else 0
            bar_x = inner.x + pos * (bar_w + gap) + extra
            # Bar height proportional to value vs max (clamped to
            # bar_h_max - 4 so the top of the tallest bar stays a
            # touch inside the chart frame).
            h = int(round((v / max_val) * (bar_h_max - 4))) if v > 0 else 0
            bar_rect = pygame.Rect(bar_x, bar_bottom - h, bar_w, h)
            # Bar fill = lane_idle pastel for this finger.
            fill = self.theme.lane_idle[finger % len(self.theme.lane_idle)]
            if h > 0:
                pygame.draw.rect(surf, fill, bar_rect, border_radius=4)
            # Red outline on the worst-performing lane (misclick chart
            # only). 2 px stroke so it pops without overpowering the
            # pastel fill.
            if lane == worst_lane and v > 0:
                pygame.draw.rect(surf, self.theme.error, bar_rect,
                                  width=2, border_radius=4)
            # Value text above the bar (showing "245" or "3" etc.).
            if v > 0:
                val_str = f"{int(round(v))}"
                draw_text(surf, val_str,
                          (bar_x + bar_w // 2, bar_top - 4),
                          self.theme, self.layout, pt=FONT_SMALL,
                          centre=True, colour=self.theme.foreground)
            # X-axis finger label. Bilateral charts use a tiny L / R
            # prefix so the therapist knows which hand the bar belongs
            # to (lanes 4..7 are left in bilateral). Unilateral skips
            # the prefix.
            label = self._FINGER_SHORT[finger]
            if n > 4:
                hand_letter = "L" if lane >= 4 else "R"
                label = f"{hand_letter}{label}"
            if levels and 0 <= lane < len(levels) and levels[lane]:
                # Corridor level suffix (finding #80): fingers at
                # different levels are not the same measurement, so
                # say which level each bar came from right on the
                # axis rather than only in the stored metadata.
                label = f"{label}{levels[lane]}"
            draw_text(surf, label,
                      (bar_x + bar_w // 2, bar_bottom + 14),
                      self.theme, self.layout, pt=FONT_SMALL,
                      centre=True, colour=self.theme.muted)
        # Unit hint in the bottom-right corner of the card so the
        # reader knows what the bar heights mean. Right-aligned so a
        # longer unit ("% of max") stays inside the card.
        if unit:
            uf = self.layout.font(FONT_SMALL)
            u = uf.render(unit, True, self.theme.muted)
            surf.blit(u, u.get_rect(
                bottomright=(rect.right - 10, rect.y + rect.h - 6)))

    def _draw_stat_card(self, surf: pygame.Surface, rect: pygame.Rect,
                         label: str, value: str,
                         value_colour: tuple[int, int, int],
                         value_pt: int = FONT_TITLE) -> None:
        # Card body + soft shadow underneath (single pass since the
        # cards are small and on a flat background; the multi-pass
        # Card shadow would be overkill at this scale).
        shadow = pygame.Surface((rect.w + 8, rect.h + 8), pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 35),
                          pygame.Rect(4, 6, rect.w, rect.h),
                          border_radius=14)
        surf.blit(shadow, (rect.x - 4, rect.y - 4))
        body = tuple(max(0, min(255, c - 8)) for c in self.theme.background)
        pygame.draw.rect(surf, body, rect, border_radius=14)
        outline = tuple(max(0, c - 30) for c in self.theme.background)
        pygame.draw.rect(surf, outline, rect, 1, border_radius=14)
        # Small label up top, shrunk until it fits. A pooled Force
        # Pilot card carries its "(mixed levels)" flag in the label,
        # and a label wider than the card silently ran off both edges
        # rather than dropping the disclosure it exists to make.
        max_label_w = rect.w - 16
        label_pt = FONT_BODY
        while (label_pt > 10
               and self.layout.font(label_pt).size(label)[0] > max_label_w):
            label_pt -= 1
        draw_text(surf, label, (rect.centerx, rect.y + 22),
                  self.theme, self.layout, pt=label_pt,
                  centre=True, colour=self.theme.muted)
        # Big value, bold so it pops as the stat's headline number.
        # Shrink the font until it fits the card so a value with a unit
        # (e.g. "262 ms") never spills past the card edge the way a bare
        # number like "1840" does.
        max_w = rect.w - 24
        pt = int(value_pt * self.layout.font_scale)
        val_font = make_font(pt, bold=True)
        val_surf = val_font.render(value, True, value_colour)
        while val_surf.get_width() > max_w and pt > 12:
            pt -= 2
            val_font = make_font(pt, bold=True)
            val_surf = val_font.render(value, True, value_colour)
        # Value sits at a fixed fraction of the card rather than a
        # fixed 78 px, so the taller headline card on the slim screen
        # centres its number instead of hugging the label.
        surf.blit(val_surf,
                   val_surf.get_rect(
                       center=(rect.centerx,
                               rect.y + int(rect.h * 0.71))))

    # Slim-view geometry. The left column carries the grade and the
    # three numbers; the right column carries NEXT UP.
    SLIM_CX = 330
    SLIM_RING_CENTRE = (330, 252)
    SLIM_RING_R = 86
    SLIM_CARD_TOP = 402
    SLIM_CARD_H = 128
    NEXT_CARD_RECT = (650, 160, 570, 370)
    SLIM_STRIP_RECT = (60, 578, 1160, SESSION_STRIP_H)

    def _draw_results_header(self, surf: pygame.Surface, cx: int,
                             block_name: str,
                             accent: tuple[int, int, int]) -> None:
        """Title, accent rule and the mode pill. Same furniture as the
        in-play screens so the results carry the identity the patient
        just played under."""
        title_font = make_font(
            int((FONT_H1 + 6) * self.layout.font_scale), bold=True)
        title_surf = title_font.render(self.RESULTS_TITLE, True,
                                       self.theme.foreground)
        title_rect = title_surf.get_rect(center=(cx, 80))
        surf.blit(title_surf, title_rect)
        bar_w = max(72, title_rect.w // 3)
        bar_rect = pygame.Rect(0, 0, bar_w, 4)
        bar_rect.center = (cx, title_rect.bottom + 12)
        pygame.draw.rect(surf, accent, bar_rect, border_radius=2)
        # Underscores come out as spaces so force_pilot reads as the
        # mode's on-screen name, not its config key. "pattern" is a
        # special case: the mode-select card is titled "Muscle Memory"
        # so the patient never sees the word "pattern" (audit finding
        # #10), and the results pill has to say the same thing or the
        # rename leaks right back in on the very next screen.
        mode_label = ("MUSCLE MEMORY" if block_name.lower() == "pattern"
                      else block_name.replace("_", " ").upper())
        mf = self.layout.font(FONT_SMALL + 2)
        mt_label = mf.render(mode_label, True, (255, 255, 255))
        pill_rect = pygame.Rect(0, 0, mt_label.get_width() + 24,
                                mt_label.get_height() + 8)
        pill_rect.topright = (self.layout.width - 28, 30)
        pygame.draw.rect(surf, accent, pill_rect,
                         border_radius=pill_rect.height // 2)
        surf.blit(mt_label, mt_label.get_rect(center=pill_rect.center))

    def _draw_grade_ring(self, surf: pygame.Surface,
                         centre: tuple[int, int], ring_r: int,
                         grade: str, blurb: str,
                         grade_colour: tuple[int, int, int],
                         entry: float) -> None:
        """Grade letter inside a ring: the celebratory moment, and the
        part the patient and therapist see first. The ring sweeps
        closed over the entry animation with the blurb directly under
        it, so the praise reads as part of the grade."""
        glow = pygame.Surface((ring_r * 2 + 40, ring_r * 2 + 40),
                              pygame.SRCALPHA)
        for i, alpha in ((20, 30), (12, 50), (4, 80)):
            pygame.draw.circle(glow, (*grade_colour, int(alpha * entry)),
                               (ring_r + 20, ring_r + 20), ring_r + i)
        surf.blit(glow, (centre[0] - ring_r - 20,
                         centre[1] - ring_r - 20))
        if entry >= 1.0:
            pygame.draw.circle(surf, grade_colour, centre, ring_r, 6)
        else:
            arc_rect = pygame.Rect(0, 0, ring_r * 2, ring_r * 2)
            arc_rect.center = centre
            start = math.pi / 2
            pygame.draw.arc(surf, grade_colour, arc_rect,
                            start, start + entry * 2 * math.pi, 6)
        gfont = make_font(
            int(ring_r * 1.33 * self.layout.font_scale), bold=True)
        gtext = gfont.render(grade, True, grade_colour)
        if entry < 1.0:
            gtext.set_alpha(int(255 * entry))
        surf.blit(gtext, gtext.get_rect(center=centre))
        draw_text(surf, blurb, (centre[0], centre[1] + ring_r + 24),
                  self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)

    def _hand_phrase(self, hand: str) -> str:
        return {"left": "Left hand", "right": "Right hand",
                "both": "Both hands"}.get(hand, "Right hand")

    def _pending_step(self) -> dict | None:
        """The battery step waiting to run, if a battery is mid-way.
        It takes the NEXT UP card over: the suggestion is the study's,
        not the rotation's, until the battery is done."""
        try:
            step = self.engine.pending_protocol_step()
        except Exception:
            return None
        return step if isinstance(step, dict) else None

    def _next_up_plan(self) -> tuple[str | None, str]:
        """Which game to offer next, and on which hand.

        A pending battery step wins outright, hand included. Otherwise
        the same hand as the game that just ended, so the one press
        really is one press: no hand picker in between. Mirror is the
        exception the mode itself makes, being bilateral-only.
        """
        step = self._pending_step()
        if step is not None:
            hand = str(step.get("hand") or getattr(self.engine, "hand_mode",
                                                   "right") or "right")
            return str(step["mode"]), hand
        after = str(getattr(self.engine, "current_block", "") or "")
        key = next_up_mode(self.engine, after)
        if key is None:
            return None, ""
        hand = str(getattr(self.engine, "hand_mode", "right") or "right")
        if key == "mirror":
            hand = "both"
        return key, hand

    def _start_next_up(self) -> None:
        """One press from here to the suggested game's prep.

        A pending battery step continues the protocol, which starts
        the block through engine.begin_game. A free suggestion goes
        straight through engine.begin_game itself, the same path the
        hand picker takes: same hand-mode switch, same lane rebuild,
        same starter. Nothing about the block (its EEG markers
        included) can differ from a game started the long way round.
        """
        if self._battery_done():
            return
        step = self._pending_step()
        if step is not None:
            # A scheduled rest holds the button (and N) until its
            # floor. Nothing else on the screen is blocked: the RA can
            # still open the data folder, read the detail view or end
            # the session.
            if self._rest_lock(step)[0]:
                return
            self.engine.continue_protocol()
            return
        key, hand = self._next_up_plan()
        if key is None:
            return
        self.engine.begin_game(key, hand)

    def _card_elapsed(self) -> float:
        """Seconds the between-blocks card has been up.

        Taken from the engine's own stamp (set in show_results) rather
        than from this screen's animation clock, so the countdown the
        participant reads and the rest length the battery log records
        are the same number. Falls back to the animation clock, and to
        zero before the first on_show, which is what a bare test draw
        gets.
        """
        shown = float(getattr(self.engine, "_step_card_t", 0.0) or 0.0)
        if shown <= 0:
            shown = self._shown_t
        return time.perf_counter() - shown if shown > 0 else 0.0

    def _rest_lock(self, step: dict | None) -> tuple[bool, float]:
        """(button held, seconds of the scheduled rest still to run)
        for a pending step.

        A stretch never holds the button: it is a suggestion, and a
        participant who is ready outranks a tidy 60 s. A scheduled REST
        does hold it, for rest_min_s only. The two rests in the single
        long session sit where the design needs them (after the first
        pass, and at the second pass's set boundary); letting the RA
        click straight through would quietly remove the one thing
        separating the two halves of the session. Past the floor the
        button comes back and says so, so nobody is trapped.
        """
        if not isinstance(step, dict):
            return False, 0.0
        try:
            rest_s = float(step.get("rest_s") or 0.0)
            floor_s = float(step.get("rest_min_s") or 0.0)
        except (TypeError, ValueError):
            return False, 0.0
        if rest_s <= 0:
            return False, 0.0
        elapsed = self._card_elapsed()
        return elapsed < floor_s, max(0.0, rest_s - elapsed)

    @staticmethod
    def _mmss(seconds: float) -> str:
        total = int(max(0.0, seconds) + 0.5)
        return f"{total // 60}:{total % 60:02d}"

    def _battery_card_lines(self, step: dict) -> tuple[str, str, str]:
        """(heading, reason pill, wait line) for a pending battery
        step.

        The wait line is the stretch countdown on a stretch step and
        the rest countdown on a rest step, both measured from the
        moment this screen was shown. The stretch never locks the
        button; the rest holds it until its floor (see _rest_lock).
        """
        try:
            progress = self.engine.battery_progress() or {}
        except Exception:
            progress = {}
        of = int(progress.get("of") or 0)
        pos = int(step.get("position") or 0)
        heading = f"PLAY ALL  step {pos} of {of}" if of else "PLAY ALL"
        requested = str(step.get("hand_requested") or "")
        role = {"hand1": "hand 1", "hand2": "hand 2",
                "dominant": "main hand",
                "non_dominant": "other hand"}.get(requested, "")
        reason = f"Play all step {pos}" + (f", {role}" if role else "")
        wait = ""
        try:
            stretch_s = float(step.get("stretch_s") or 0.0)
            rest_s = float(step.get("rest_s") or 0.0)
        except (TypeError, ValueError):
            stretch_s = rest_s = 0.0
        elapsed = self._card_elapsed()
        if rest_s > 0:
            left = max(0.0, rest_s - elapsed)
            wait = (f"Rest: {self._mmss(left)} left" if left > 0
                    else "Rest done")
        elif stretch_s > 0:
            left = max(0.0, stretch_s - elapsed)
            wait = (f"Stretch break first: {left:.0f} s left"
                    if left > 0 else "Stretch break done")
        return heading, reason, wait

    def _draw_next_up(self, surf: pygame.Surface,
                      rect: pygame.Rect) -> None:
        """The continuity card: one suggestion, one button.

        One suggestion rather than a menu on purpose. The patient has
        just finished a game and is being asked to keep going; a grid
        of ten is a decision, and a single named game with the hand
        already set is an invitation.
        """
        body = tuple(max(0, min(255, c - 6)) for c in self.theme.background)
        shadow = pygame.Surface((rect.w + 12, rect.h + 12),
                                pygame.SRCALPHA)
        pygame.draw.rect(shadow, (0, 0, 0, 30),
                         pygame.Rect(6, 8, rect.w, rect.h),
                         border_radius=18)
        surf.blit(shadow, (rect.x - 6, rect.y - 6))
        pygame.draw.rect(surf, body, rect, border_radius=18)
        outline = tuple(max(0, c - 26) for c in self.theme.background)
        pygame.draw.rect(surf, outline, rect, 1, border_radius=18)

        if self._battery_done():
            self._draw_today_panel(surf, rect)
            return
        key, hand = self._next_up_plan()
        step = self._pending_step()
        heading, step_reason, stretch = "NEXT UP", "", ""
        if step is not None:
            heading, step_reason, stretch = self._battery_card_lines(step)
        held, rest_left = self._rest_lock(step)
        draw_text(surf, heading, (rect.x + 30, rect.y + 26),
                  self.theme, self.layout, pt=FONT_SMALL,
                  centre=False,
                  colour=(self.theme.accent if step is not None
                          else self.theme.muted))
        if key is None:
            # A keyboard rig with nothing playable left. Say so rather
            # than offering a button that refuses.
            draw_text(surf, "Nothing else this rig can run.",
                      (rect.x + 30, rect.y + 70),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=False, colour=self.theme.muted)
            return
        accent = mode_accent(key, self.theme)
        strip = pygame.Rect(rect.x + 30, rect.y + 62, 6, 92)
        pygame.draw.rect(surf, accent, strip, border_radius=3)
        ModeSelectScreen._draw_mode_icon(
            surf, key, rect.x + 84, rect.y + 96, 44, accent)
        title_font = make_font(int(FONT_H1 * self.layout.font_scale),
                               bold=True)
        title_surf = title_font.render(mode_title(key), True,
                                       self.theme.foreground)
        surf.blit(title_surf,
                  title_surf.get_rect(midleft=(rect.x + 126,
                                               rect.y + 88)))
        desc = next((d for k, _t, d in ModeSelectScreen.MODES
                     if k == key), "")
        desc_font = self.layout.font(FONT_SMALL + 2)
        desc_w = rect.right - 30 - (rect.x + 126)
        for li, line in enumerate(
                ModeSelectScreen._wrap_desc(desc_font, desc, desc_w)[:2]):
            draw_text(surf, line,
                      (rect.x + 126, rect.y + 110 + li * 22),
                      self.theme, self.layout, pt=FONT_SMALL + 2,
                      centre=False, colour=self.theme.muted)
        # Why this one. The suggestion rotates for variety, so saying
        # which of the two reasons is in play stops it reading as an
        # arbitrary pick, and stops a therapist wondering whether the
        # app is steering the session towards something.
        try:
            played = set(self.engine.session_modes_played())
        except Exception:
            played = set()
        reason = ("Not played yet this session" if key not in played
                  else "Coming round again")
        if step_reason:
            reason = step_reason
        pill_w = _strip_pill(surf, self.layout, rect.x + 30, rect.y + 186,
                             reason,
                             self.theme.accent if step_reason
                             else self.theme.muted)
        if stretch:
            _strip_pill(surf, self.layout, rect.x + 30 + pill_w + 10,
                        rect.y + 186, stretch, self.theme.warning)
        draw_text(surf, f"{self._hand_phrase(hand)}, already set up",
                  (rect.x + 30, rect.y + 216),
                  self.theme, self.layout, pt=FONT_BODY,
                  centre=False, colour=self.theme.foreground)
        # During a scheduled rest the button says how long is left and
        # does nothing; past the floor it says the rest can be cut
        # short, so the RA never has to guess whether pressing early
        # is allowed.
        if held:
            self.next_btn.label = f"Rest: {self._mmss(rest_left)}"
            self.next_btn.colour = self.theme.muted
        elif rest_left > 0:
            self.next_btn.label = f"Start now: {mode_title(key)}   (N)"
            self.next_btn.colour = accent
        else:
            self.next_btn.label = f"Start {mode_title(key)}   (N)"
            self.next_btn.colour = accent
        self.next_btn.draw(surf)

    def _draw_slim(self, surf: pygame.Surface, cards: list,
                   entry: float) -> None:
        """The finished screen: the mode's headline, at most two
        supporting numbers, one suggestion, and the session so far."""
        picks = self._slim_cards(cards)
        # Headline card wider and taller than the two beside it, so
        # which number matters is a matter of size rather than of
        # reading six labels.
        widths = (230, 145, 145)
        x = self.SLIM_CX - 270
        for i, (lbl, val, col) in enumerate(picks[:3]):
            w = widths[i] if i < len(widths) else 145
            self._draw_stat_card(
                surf,
                pygame.Rect(x, self.SLIM_CARD_TOP, w, self.SLIM_CARD_H),
                lbl, val, col,
                value_pt=FONT_TITLE + (14 if i == 0 else -6),
            )
            x += w + 10
        # Vs-last-time chip under the headline card: this game against
        # the same participant's previous completed game of the same
        # mode and hand (engine.finish_block computed it from the
        # sessions tree). One chip, not a table: the slim screen's one
        # job is the headline, and the chip is its trend arrow. A
        # first-time game has no chip at all rather than an empty one.
        #
        # In a session that plays a mode twice (the study battery does)
        # the honest comparison is this session's own first go, not
        # some block from another day, so the SO FAR row takes the
        # line when it has something to say and the vs-last chip keeps
        # it otherwise.
        chip_left = self.SLIM_CX - 270
        chip_y = self.SLIM_CARD_TOP + self.SLIM_CARD_H + 24
        chip_right = self.SLIM_STRIP_RECT[0] + self.SLIM_STRIP_RECT[2]
        here = self._progress_row_for(
            str(self.engine.current_block),
            str(getattr(self.engine, "hand_mode", "")))
        if here is not None and int(here.get("n") or 0) >= 2:
            self._draw_progress_row(surf, chip_left, chip_y, chip_right)
        else:
            chip = getattr(self.engine, "vs_last", None)
            if isinstance(chip, dict) and chip.get("text"):
                chip_colour = (self.theme.success if chip.get("better")
                               else self.theme.warning)
                used = _strip_pill(surf, self.layout, chip_left, chip_y,
                                   str(chip["text"]), chip_colour,
                                   font_pt=FONT_SMALL + 2)
                self._draw_progress_row(surf, chip_left + used + 14,
                                        chip_y, chip_right)
            else:
                self._draw_progress_row(surf, chip_left, chip_y,
                                        chip_right)
        self._draw_next_up(surf, pygame.Rect(*self.NEXT_CARD_RECT))
        if str(self.engine.current_block) == "syllables":
            self._draw_sticker_strip(surf)
        draw_session_strip(surf, pygame.Rect(*self.SLIM_STRIP_RECT),
                           self.engine, self.theme, self.layout)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        cx = self.layout.width // 2
        total = self.engine.hits + self.engine.misses
        rate = 0.0 if total == 0 else self.engine.hits / total
        grade, blurb = self._grade_for(rate)
        grade_colour = self._grade_colour(grade)
        # Entry animation progress: 1.0 when settled (or in a bare
        # test draw with no on_show notification).
        entry = self._entry_frac()
        # str() because a test double can leave current_block as a
        # non-string; an unknown block falls back to the theme accent.
        block_name = str(self.engine.current_block)
        accent = mode_accent(block_name, self.theme)
        self._draw_results_header(surf, cx, block_name, accent)
        cards = self._stat_cards(entry)
        if self.show_details:
            self._draw_grade_ring(surf, (cx, 240), 90, grade, blurb,
                                  grade_colour, entry)
            self._draw_details(surf, cards, entry)
        else:
            self._draw_grade_ring(surf, self.SLIM_RING_CENTRE,
                                  self.SLIM_RING_R, grade, blurb,
                                  grade_colour, entry)
            self._draw_slim(surf, cards, entry)

        # The syllables supervisor nudge sits under either view: one
        # line, drawn only when the block's accuracy landed outside
        # the productive zone, so most sessions never see it.
        if block_name == "syllables":
            sy_note = self._syllables_advice(
                self._syllables_summary() or {})
            if sy_note:
                draw_text(surf, sy_note, (cx, 658), self.theme,
                          self.layout, pt=FONT_SMALL + 2, centre=True,
                          colour=self.theme.warning)

        self.retry_btn.draw(surf)
        self.again_btn.draw(surf)
        self.folder_btn.draw(surf)
        self.detail_btn.draw(surf)
        self.title_btn.draw(surf)

        # Sensory-cues menu. Pill first, overlay last so the open rows
        # sit on top of the buttons they cover.
        self._cue_menu.draw_closed(surf)
        self.mute_btn.draw(surf, self.theme, self.layout)
        self._cue_menu.draw_overlay(surf)

    # Which of _stat_cards' entries reach the finished screen, as
    # (headline, support, support) indices into that mode's list.
    #
    # The choices themselves are unchanged and stay research-driven
    # (median RT for reaction, accuracy rather than RT for Muscle
    # Memory, the sync gap for mirror, pace for adaptive): only the
    # DENSITY changes. A six-card wall after every game buried the one
    # number that mattered among five that did not, and a patient
    # reading it had no way to tell which was which. Everything else
    # each mode measures is still computed below, still written to the
    # session folder and the report, and still one press away behind
    # the More detail toggle.
    SLIM_CARDS = {
        "force_pilot": (2, 3, 0),     # in corridor | mean error | score
        "buzz_hunt": (1, 2, 0),       # localisation | span | score
        "echo": (1, 2, 0),            # longest echo | items right | score
        "pattern": (2, 4, 1),         # accuracy | stars | takes
        "reaction": (2, 4, 0),        # median RT | accuracy or p10
        "chords": (1, 2, 0),          # clean hit rate | median ER
        "syllables": (1, 2, 0),       # words correct | band | score
        "mirror": (2, 0, 1),          # sync gap | score | hits
        "adaptive": (2, 4, 0),        # top pace | final pace | score
    }
    # Classic, rhythm and anything unrecognised fall on the generic
    # list: score, then hit rate, then the timing figure.
    SLIM_CARDS_DEFAULT = (0, 2, 4)

    def _mode_summaries(self) -> dict:
        """Every mode-specific block summary in one read, keyed by the
        short names the card branches use. One call so the cards and
        the detail charts cannot end up looking at different data."""
        return {
            "fp": self._force_pilot_summary(),
            "bh": self._buzz_hunt_summary(),
            "ec": self._echo_summary(),
            "rx": self._reaction_summary(),
            "pat": self._pattern_summary(),
            "ch": self._chords_summary(),
            "sy": self._syllables_summary(),
            "mir": self._mirror_summary(),
            "adp": self._adaptive_summary(),
        }

    def _stat_cards(self, entry: float = 1.0
                    ) -> list[tuple[str, str, tuple[int, int, int]]]:
        """Every number this block could report, as (label, value,
        colour), in each mode's own vocabulary.

        `entry` rides the screen's entry ease so counting stats land
        with the ring sweep; timing readouts stay static because a
        reaction time counting up through wrong values would read as
        data. The full list is what the More detail view draws and
        what the mode tests assert on; the finished screen shows the
        three SLIM_CARDS picks out of it.
        """
        total = self.engine.hits + self.engine.misses
        rate = 0.0 if total == 0 else self.engine.hits / total
        _sums = self._mode_summaries()
        fp = _sums["fp"]
        bh = _sums["bh"]
        ec = _sums["ec"]
        rx = _sums["rx"]
        pat = _sums["pat"]
        ch = _sums["ch"]
        sy = _sums["sy"]
        mir = _sums["mir"]
        adp = _sums["adp"]
        # Stat cards row - score, hits, hit rate, misses, plus the two
        # reaction-time cards the patient sees as a game-style headline
        # (average + personal best for the round). Six slimmer cards
        # (180 px) keep the row inside the 1280-wide logical surface.
        is_rhythm = (self.engine.current_block == "rhythm")
        avg_rt = self.engine.overall_mean_rt()
        best_rt = self.engine.overall_best_rt()
        avg_str = f"{avg_rt:.0f} ms" if avg_rt > 0 else "n/a"
        best_str = f"{best_rt:.0f} ms" if best_rt > 0 else "n/a"
        # In rhythm mode the numbers are beat offsets, not reaction
        # times, so relabel rather than mislead.
        avg_label = "AVG OFFSET" if is_rhythm else "AVG RT"
        best_label = "BEST OFFSET" if is_rhythm else "BEST RT"
        # The counting stats ride the entry ease so the numbers land
        # with the ring sweep. The two RT cards stay static: a timing
        # readout counting up through wrong values would read as data.
        if fp is not None:
            # Force Pilot has no reaction times and "hits" are runs, so
            # the cards say what a tracking block actually measured:
            # corridor time, mean tracking error and the section the
            # patient controlled best.
            overall = fp.get("overall") or {}
            tic = overall.get("time_in_corridor")
            mae = overall.get("mae_pct")
            best_sec = fp.get("best_section") or "n/a"
            # IN CORRIDOR / MEAN ERROR pool every played finger's runs
            # into one number. block_stats' own docstring says pooling
            # a lane's stats across corridor levels misrepresents both
            # (a narrower corridor mechanically lowers time-in-corridor
            # for the same skill); pooling ACROSS FINGERS has the same
            # problem whenever those fingers sit at different levels,
            # which the per-finger charts below now show. Flag the
            # pooled cards with a level-mix note rather than let them
            # read as one clean measurement when they are not (finding
            # #80).
            fp_levels_raw = fp.get("levels") or {}
            fp_per_lane = fp.get("per_lane") or {}
            played_levels = set()
            for lane_str in fp_per_lane:
                try:
                    lane = int(lane_str)
                except (TypeError, ValueError):
                    continue
                hand_word = "right" if lane < 4 else "left"
                lvl_entry = fp_levels_raw.get(f"{hand_word}:{lane % 4}")
                if isinstance(lvl_entry, dict) and lvl_entry.get("final"):
                    played_levels.add(int(lvl_entry["final"]))
            level_note = " (mixed levels)" if len(played_levels) > 1 else ""
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("RUNS", f"{int(round((fp.get('runs') or 0) * entry))}",
                 self.theme.success),
                (f"IN CORRIDOR{level_note}",
                 (f"{tic * 100:.0f}%" if tic is not None else "n/a"),
                 self.theme.foreground),
                (f"OFF THE LINE{level_note}",
                 (f"{mae:.1f}%" if mae is not None else "n/a"),
                 self.theme.foreground),
                ("EXITS", f"{overall.get('stalls', 0)}",
                 self.theme.error),
                ("BEST SECTION", str(best_sec), self.theme.success),
            ]
        elif bh is not None:
            # Buzz Hunt has its own outcome vocabulary: localisation
            # accuracy, the duration threshold estimate, the span
            # reached and the catch-trial false alarms. THRESHOLD and
            # GAP used to average the two hands into one number and
            # fall back to the current staircase level under two
            # reversals, so a clean bilateral block could show a
            # number that represented neither hand, and a short block
            # could show the 40 ms hardware floor labelled as a
            # measured threshold (audit finding #94). Each hand gets
            # its own card instead, and a hand short of 2 reversals
            # reads "not reached" rather than its still-adapting
            # level.
            loc = bh.get("loc") or {}
            acc = loc.get("accuracy")
            span = (bh.get("span") or {}).get("max_correct")
            fa = (loc.get("catch") or {}).get("false_alarms")
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("LOCALISATION",
                 (f"{acc * 100:.0f}%" if acc is not None else "n/a"),
                 self.theme.success),
                ("SPAN", (f"{span}" if span else "n/a"),
                 self.theme.foreground),
                ("FALSE ALARMS",
                 (f"{fa}" if fa is not None else "n/a"),
                 self.theme.error),
            ]
            # The window ladder is the localisation difficulty now;
            # the THRESHOLD cards only exist for a block that ran the
            # legacy duration staircase (block_stats then carries a
            # non-empty threshold dict and no active window).
            window = bh.get("window") or {}
            if window.get("active", False) and window.get("per_hand"):
                cards += self._buzz_hunt_window_cards(window)
            else:
                cards += self._buzz_hunt_hand_cards(
                    "THRESHOLD", bh.get("threshold") or {})
            cards += self._buzz_hunt_hand_cards(
                "GAP", (bh.get("gap") or {}).get("threshold") or {})
        elif ec is not None:
            # Echo's own vocabulary: the longest echo (span) is the
            # headline. Under the Simon rule the support cards are
            # the items reproduced (partial credit included) and what
            # became of the spare life; under the legacy ladder they
            # stay the Kessels pair (correct sequences and the span x
            # correct product). Nothing here reads speed:
            # reproduction is untimed by design, so no RT card can
            # exist for this mode. Counts stay static rather than
            # riding the entry ease: "3 of 7" counting up through
            # wrong ratios would read as data.
            span = ec.get("span") or 0
            n_ok = ec.get("total_correct") or 0
            n_tr = ec.get("n_trials") or 0
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("LONGEST ECHO", (f"{span}" if span else "n/a"),
                 self.theme.success),
            ]
            if str(ec.get("rule") or "ladder") == "simon":
                games = ec.get("games_played") or []
                spent = [g for g in games
                         if isinstance(g, dict)
                         and g.get("life_used_at") is not None]
                if spent:
                    life = ", ".join(f"{g.get('life_used_at')}"
                                     for g in spent)
                    life_txt = f"used at {life}"
                else:
                    life_txt = "kept"
                # Card order is load-bearing: SLIM_CARDS picks the
                # first three by index, so ITEMS RIGHT stays at 2 and
                # the game count goes on the end where only the More
                # detail view reads it.
                cards += [
                    ("ITEMS RIGHT", f"{ec.get('total_items') or 0}",
                     self.theme.foreground),
                    ("LIFE", life_txt, self.theme.foreground),
                ]
                if len(games) > 1:
                    cards.append(("GAMES", f"best of {len(games)}",
                                  self.theme.foreground))
            else:
                cards += [
                    ("SEQUENCES", f"{n_ok} of {n_tr}",
                     self.theme.foreground),
                    ("SPAN x CORRECT", f"{ec.get('product_score') or 0}",
                     self.theme.foreground),
                ]
            cards.append(
                ("NO REPLY", f"{ec.get('n_omissions') or 0}",
                 self.theme.error))
        elif pat is not None:
            # Pattern's own docstring (WHAT THE PATIENT SEES) is
            # explicit that "RT numbers are never shown": Boyd and
            # Winstein found explicit sequence knowledge impairs
            # implicit learning after stroke, and an RT number here
            # would show the patient exactly the anticipation reward
            # the mode is trying not to teach (audit finding #9). Cards
            # stay accuracy-flavoured: takes completed and stars earned
            # are the same feedback the between-take rest screen gives.
            per_take = [t for t in (pat.get("per_take") or [])
                        if isinstance(t, dict) and t.get("kind") != "warmup"]
            n_takes = len(per_take)
            total_stars = sum(
                (3 if (t.get("accuracy") or 0) >= 0.95 else
                 2 if (t.get("accuracy") or 0) >= 0.85 else
                 1 if (t.get("accuracy") or 0) >= 0.70 else 0)
                for t in per_take)
            n_correct = sum(int(round((t.get("accuracy") or 0)
                                       * (t.get("n") or 0)))
                            for t in per_take)
            n_total = sum(t.get("n") or 0 for t in per_take)
            overall_acc = (n_correct / n_total) if n_total else None
            acc_str = (f"{overall_acc * 100:.0f}%"
                       if overall_acc is not None else "n/a")
            # End-of-session recap stays reward-flavoured and
            # accuracy-only (Abe 2011; Wulf and Lewthwaite 2016, via
            # the mode's research brief): stars, takes, and the best
            # run of 3-star takes. The old sixth card was the raw
            # press streak, which the stars already summarise better.
            best_run = pat.get("three_star_streak_best")
            run_str = (f"{int(best_run)} takes"
                       if isinstance(best_run, (int, float)) else "n/a")
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("TAKES", f"{n_takes}", self.theme.success),
                ("ACCURACY", acc_str, self.theme.foreground),
                ("NOT CAUGHT", f"{int(round(self.engine.misses * entry))}",
                 self.theme.error),
                ("STARS EARNED", f"{total_stars} / {n_takes * 3}",
                 self.theme.success),
                ("BEST 3-STAR RUN", run_str, (255, 196, 0)),
            ]
        elif rx is not None:
            # Reaction's own research case (reaction.py's module
            # docstring, Ratcliff 1993; Whelan 2008) names the median
            # as the headline because RT distributions are
            # right-skewed and a mean gets dragged by lapses; AVG RT
            # was the only figure shown here, so the headline never
            # matched the design. p10 (the mode's "best consistent
            # speed") replaces raw BEST RT for the same reason.
            median_rt = rx.get("median_rt_ms")
            p10_rt = rx.get("p10_rt_ms")
            median_str = (f"{median_rt:.0f} ms"
                          if median_rt is not None else "n/a")
            p10_str = f"{p10_rt:.0f} ms" if p10_rt is not None else "n/a"
            # Choice-RT accuracy below 80% means the patient is
            # guessing a favourite finger fast rather than responding,
            # and the RT that survives is not interpretable (the
            # brief's threshold; reaction.py names accuracy "a
            # headline metric for choice RT"). Below 90% is still
            # worth a soft flag. Simple sub-mode has no wrong-choice
            # concept so accuracy is None there and the card is
            # skipped in favour of MISSES.
            accuracy = rx.get("accuracy")
            acc_colour = self.theme.foreground
            acc_str = "n/a"
            if accuracy is not None:
                acc_str = f"{accuracy * 100:.0f}%"
                if accuracy < 0.80:
                    acc_colour = self.theme.error
                elif accuracy < 0.90:
                    acc_colour = self.theme.warning
                else:
                    acc_colour = self.theme.success
            fifth = (("ACCURACY", acc_str, acc_colour)
                     if accuracy is not None
                     else ("FASTEST (P10)", p10_str, self.theme.success))
            sixth = (("FASTEST (P10)", p10_str, self.theme.success)
                     if accuracy is not None
                     else ("AVG RT (not headline)", avg_str,
                           self.theme.muted))
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("HITS", f"{int(round(self.engine.hits * entry))}",
                 self.theme.success),
                ("MEDIAN RT", median_str, self.theme.foreground),
                ("NOT CAUGHT", f"{int(round(self.engine.misses * entry))}",
                 self.theme.error),
                fifth,
                sixth,
            ]
        elif ch is not None:
            # Chords has its own outcome vocabulary (audit finding
            # #23): the generic HIT RATE counts every non-Miss, which
            # includes late chords, measured leak fails, broken holds
            # and over-force trials as "hits", and AVG RT mixes probe
            # RTs with chord completion times on a per-lane chart keyed
            # to each chord's lowest lane. Cards here read the mode's
            # own classes instead: only "hit" is a clean chord, ER is
            # the trained cross-talk quantity, and leak fails / over
            # -force are shown as counts rather than folded into a
            # misleadingly generic hit rate.
            # Within-scope chords only: dividing by every record let
            # the near-guaranteed single-finger probes (and the cross
            # chords on their own ladder) dilute the number, so the
            # headline moved with the session's probe:chord mix, not
            # skill. chord_outcome_classes is the scope-pure count;
            # outcome_classes remains as the fallback for summaries
            # written before it existed.
            classes = (ch.get("chord_outcome_classes")
                       or ch.get("outcome_classes") or {})
            n_all = sum(int(v) for v in classes.values())
            clean_hits = int(classes.get("hit", 0))
            clean_rate = (clean_hits / n_all) if n_all else None
            clean_str = (f"{clean_rate * 100:.0f}%"
                        if clean_rate is not None else "n/a")
            median_er = ch.get("median_er")
            er_str = (f"{median_er * 100:.0f}%"
                      if median_er is not None else "n/a")
            level_highest = ch.get("level_highest")
            leak_fails = int(classes.get("leak_fail", 0))
            over_force = int(ch.get("over_force_trials") or 0)
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("CLEAN HIT RATE", clean_str, self.theme.success),
                ("MEDIAN ER", er_str, self.theme.foreground),
                ("HIGHEST LEVEL",
                 (f"{level_highest}" if level_highest is not None
                  else "n/a"), self.theme.foreground),
                ("LEAK FAILS", f"{leak_fails}", self.theme.error),
                ("OVER-FORCE", f"{over_force}", self.theme.warning),
            ]
        elif sy is not None:
            # Syllables' own outcome vocabulary (audit finding #30):
            # on paced blocks (levels 3-4) rt_ms is the MEAN SIGNED
            # beat asynchrony, not a reaction time, so the generic
            # AVG RT / BEST RT cards read a personal-best "RT" out of
            # the most anticipatory word and can print an impossibly
            # fast RT for a positive (late) mean. Read straight from
            # the mode's own asyn_mean_ms/asyn_sd_ms instead of
            # engine.overall_mean_rt, and take the absolute value the
            # way rhythm's cards do, so an early or late mean reads
            # the same on the card. Free-paced levels (1, 2, 5, 6)
            # keep AVG RT / BEST RT, which are real first-tap RTs.
            acc = sy.get("accuracy")
            acc_str = f"{acc * 100:.0f}%" if acc is not None else "n/a"
            band = sy.get("band_final") or "n/a"
            # The choice task's own measures. FIRST TRY is the number
            # the mode is steered by (the staircase holds it near 80
            # percent against a 25 percent chance floor); LEVEL is the
            # foil rung it finished on. A block with neither (an old
            # session, or one that logged nothing) falls back to the
            # generic RT pair rather than printing n/a twice.
            first = sy.get("first_press_accuracy")
            rung = sy.get("rung_final")
            if first is not None or rung is not None:
                first_str = (f"{first * 100:.0f}%"
                             if first is not None else "n/a")
                rung_str = str(rung) if rung is not None else "n/a"
                fifth = ("FIRST TRY", first_str, self.theme.foreground)
                sixth = ("LEVEL", rung_str, self.theme.success)
            else:
                fifth = ("AVG RT", avg_str, self.theme.foreground)
                sixth = ("BEST RT", best_str, self.theme.success)
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("WORDS CORRECT", acc_str, self.theme.success),
                ("BAND", str(band), self.theme.foreground),
                ("NOT CAUGHT", f"{int(round(self.engine.misses * entry))}",
                 self.theme.error),
                fifth,
                sixth,
            ]
        elif mir is not None:
            # Mirror's whole training goal is bimanual SYNCHRONY, not
            # raw press speed, so the headline is the mean |right -
            # left| gap (audit finding #68) rather than AVG RT, which
            # only ever showed the later-of-two-presses speed and
            # never told the patient or clinician how in-sync the
            # pair actually landed.
            gap_ms = mir.get("mean_gap_ms")
            gap_str = f"{gap_ms:.0f} ms" if gap_ms is not None else "n/a"
            r_rt = mir.get("right_hand_mean_rt_ms")
            l_rt = mir.get("left_hand_mean_rt_ms")
            r_str = f"{r_rt:.0f} ms" if r_rt is not None else "n/a"
            l_str = f"{l_rt:.0f} ms" if l_rt is not None else "n/a"
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("HITS", f"{int(round(self.engine.hits * entry))}",
                 self.theme.success),
                ("SYNC GAP", gap_str, self.theme.foreground),
                ("NOT CAUGHT", f"{int(round(self.engine.misses * entry))}",
                 self.theme.error),
                ("RIGHT HAND RT", r_str, self.theme.foreground),
                ("LEFT HAND RT", l_str, self.theme.foreground),
            ]
        elif adp is not None:
            # Adaptive's controller holds hit rate in a fixed band by
            # design, so the trained quantity is the PACE the block
            # settled at: an improving patient's bpm climbs while the
            # hit rate stays put. The pace cards replace the two RT
            # cards, which repeated what the (controller-regulated)
            # hit rate already said.
            top = adp.get("bpm_max")
            fin = adp.get("bpm_final")
            top_str = f"{float(top):.0f} BPM" if top is not None else "n/a"
            fin_str = f"{float(fin):.0f} BPM" if fin is not None else "n/a"
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("HITS", f"{int(round(self.engine.hits * entry))}",
                 self.theme.success),
                ("TOP PACE", top_str, self.theme.success),
                ("NOT CAUGHT", f"{int(round(self.engine.misses * entry))}",
                 self.theme.error),
                ("FINAL PACE", fin_str, self.theme.foreground),
                ("HIT RATE", f"{rate * 100 * entry:.0f}%",
                 self.theme.foreground),
            ]
        else:
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("HITS", f"{int(round(self.engine.hits * entry))}",
                 self.theme.success),
                ("HIT RATE", f"{rate * 100 * entry:.0f}%",
                 self.theme.foreground),
                ("NOT CAUGHT", f"{int(round(self.engine.misses * entry))}",
                 self.theme.error),
                (avg_label, avg_str, self.theme.foreground),
                (best_label, best_str, self.theme.success),
            ]
        return cards

    def _slim_cards(self, cards: list) -> list:
        """The three that reach the finished screen: headline first,
        then at most two supporting numbers. Indices that fall off the
        end of a shorter list (buzz_hunt grows a card per hand) are
        skipped rather than clamped onto the wrong number."""
        picks = self.SLIM_CARDS.get(str(self.engine.current_block).lower(),
                                    self.SLIM_CARDS_DEFAULT)
        out = []
        for idx in picks:
            if 0 <= idx < len(cards):
                out.append(cards[idx])
        if not out:
            out = cards[:3]
        return out

    def _draw_details(self, surf: pygame.Surface, cards: list,
                      entry: float) -> None:
        """The full read-out: every card the mode produces, plus the
        per-finger charts and the footers.

        Off by default (the finished screen shows three numbers), but
        kept in the app rather than sent to the data folder alone,
        because several of these panels carry disclosures the audit
        put there on purpose: the mixed-levels flag on the pooled
        Force Pilot numbers, the per-hand buzz_hunt
        thresholds, and the panels that explain why a per-finger chart
        would be misleading for chords, syllables and Muscle Memory. A
        clinician mid-session should not have to open a CSV to see
        them.
        """
        cx = self.layout.width // 2
        _sums = self._mode_summaries()
        fp = _sums["fp"]
        bh = _sums["bh"]
        pat = _sums["pat"]
        ch = _sums["ch"]
        sy = _sums["sy"]
        mir = _sums["mir"]
        card_w = 180
        card_h = 110
        gap = 20
        n_cards = len(cards)
        total_w = card_w * n_cards + gap * (n_cards - 1)
        cards_x = cx - total_w // 2
        cards_y = 380
        for i, (lbl, val, col) in enumerate(cards):
            self._draw_stat_card(
                surf,
                pygame.Rect(cards_x + i * (card_w + gap), cards_y,
                             card_w, card_h),
                lbl, val, col,
            )

        # Per-lane histograms below the stat-card row. Two charts
        # side-by-side: mean RT per lane (where slow fingers stand
        # out) + miss + wrong-press count per lane (where mistake
        # fingers stand out). Together they let a therapist see
        # which finger is slow vs which is failing entirely. Force
        # Pilot has neither RTs nor wrong presses, so its charts show
        # the per-finger tracking summary instead: mean tracking error
        # and time in corridor.
        n_lanes = (8 if self.engine.hand_mode == "both" else 4)
        chart_y = 502
        chart_h = 124
        chart_gap = 24
        total_chart_w = self.layout.width - 80
        chart_w = (total_chart_w - chart_gap) // 2
        left_x = (self.layout.width - total_chart_w) // 2
        if fp is not None:
            per_lane = fp.get("per_lane") or {}
            maes = [0.0] * n_lanes
            tics = [0.0] * n_lanes
            for key, stats in per_lane.items():
                try:
                    lane = int(key)
                except (TypeError, ValueError):
                    continue
                if 0 <= lane < n_lanes and isinstance(stats, dict):
                    maes[lane] = float(stats.get("mae_pct") or 0.0)
                    tic_val = stats.get("time_in_corridor")
                    tics[lane] = (float(tic_val) * 100.0
                                  if tic_val is not None else 0.0)
            # Corridor level per lane (finding #80): block_stats keys
            # levels by "hand:finger", not by lane, and its own
            # docstring says pooling a lane across levels misrepresents
            # both -- so a chart pooling FINGERS at different levels
            # needs the same disclosure. Lane 0..3 is the right hand,
            # 4..7 the left, matching the hand_letter convention just
            # below.
            fp_levels_raw = fp.get("levels") or {}
            fp_levels = [0] * n_lanes
            for lane in range(n_lanes):
                hand_word = "right" if lane < 4 else "left"
                lvl_entry = fp_levels_raw.get(f"{hand_word}:{lane % 4}")
                if isinstance(lvl_entry, dict) and lvl_entry.get("final"):
                    fp_levels[lane] = int(lvl_entry["final"])
            self._draw_per_lane_chart(
                surf,
                pygame.Rect(left_x, chart_y, chart_w, chart_h),
                "MEAN DISTANCE FROM THE LINE PER FINGER",
                maes, unit="% of max", high_is_bad=True,
                levels=fp_levels,
            )
            self._draw_per_lane_chart(
                surf,
                pygame.Rect(left_x + chart_w + chart_gap, chart_y,
                             chart_w, chart_h),
                "TIME IN CORRIDOR PER FINGER",
                tics, unit="%", high_is_bad=False,
                levels=fp_levels,
            )
        elif bh is not None:
            # Buzz Hunt charts: localisation accuracy per finger and
            # misreferrals per finger (trials where that finger buzzed
            # and a different finger was pressed), the on-screen
            # shadow of the confusion matrix in metadata.json.
            per_lane = (bh.get("loc") or {}).get("per_lane") or {}
            accs = [0.0] * n_lanes
            misref = [0.0] * n_lanes
            for key, stats in per_lane.items():
                try:
                    lane = int(key)
                except (TypeError, ValueError):
                    continue
                if 0 <= lane < n_lanes and isinstance(stats, dict):
                    acc_val = stats.get("accuracy")
                    accs[lane] = (float(acc_val) * 100.0
                                  if acc_val is not None else 0.0)
            confusion = bh.get("confusion") or {}
            for key, row in confusion.items():
                try:
                    lane = int(key)
                except (TypeError, ValueError):
                    continue          # the "none" catch row
                if 0 <= lane < n_lanes and isinstance(row, dict):
                    misref[lane] = float(sum(
                        n for resp, n in row.items()
                        if resp not in (key, "none")))
            self._draw_per_lane_chart(
                surf,
                pygame.Rect(left_x, chart_y, chart_w, chart_h),
                "LOCALISATION ACCURACY PER FINGER",
                accs, unit="%", high_is_bad=False,
            )
            self._draw_per_lane_chart(
                surf,
                pygame.Rect(left_x + chart_w + chart_gap, chart_y,
                             chart_w, chart_h),
                "MISREFERRALS PER FINGER",
                misref, unit="count", high_is_bad=True,
            )
        elif ch is not None:
            # The generic per-lane RT/miss chart keys every trial on
            # the row's single lane column, which for a chord is the
            # LOWEST target finger (chords.py's own "known
            # simplification"): 7 of the 11 chords contain the index
            # finger, so the chart would concentrate every chord's
            # timing on lane 1 regardless of which finger actually lagged.
            # Rather than draw a chart that reads as per-finger data
            # and is not, this panel is skipped for chords; the clean
            # per-chord and per-hand numbers are in the cards above and
            # in the session_analysis notebook's chord chapter.
            note_rect = pygame.Rect(left_x, chart_y,
                                    total_chart_w, chart_h)
            body = tuple(max(0, min(255, c - 8))
                        for c in self.theme.background)
            pygame.draw.rect(surf, body, note_rect, border_radius=14)
            outline = tuple(max(0, c - 30) for c in self.theme.background)
            pygame.draw.rect(surf, outline, note_rect, 1, border_radius=14)
            note_lines = [
                "Per-finger timing charts don't apply to chords: each",
                "row is keyed to one lane per chord, not one per",
                "finger. See the cards above, or the chords chapter in",
                "the session analysis notebook, for the per-chord and",
                "per-hand numbers.",
            ]
            line_h = FONT_SMALL + 6
            start_y = note_rect.centery - (len(note_lines) - 1) * line_h // 2
            for i, line in enumerate(note_lines):
                draw_text(
                    surf, line,
                    (note_rect.centerx, start_y + i * line_h),
                    self.theme, self.layout, pt=FONT_SMALL, centre=True,
                    colour=self.theme.muted,
                )
        elif sy is not None:
            # Per-lane charts don't apply to syllables either (audit
            # finding #30): every trial is keyed to the word's first
            # required position, so a per-finger RT chart would pile
            # every word on lane 1 regardless of which finger actually
            # carried each syllable. The stimulus field carries the
            # real per-tap detail; the notebook's syllables chapter is
            # where that lives.
            note_rect = pygame.Rect(left_x, chart_y,
                                    total_chart_w, chart_h)
            body = tuple(max(0, min(255, c - 8))
                        for c in self.theme.background)
            pygame.draw.rect(surf, body, note_rect, border_radius=14)
            outline = tuple(max(0, c - 30) for c in self.theme.background)
            pygame.draw.rect(surf, outline, note_rect, 1, border_radius=14)
            note_lines = [
                "Per-finger timing charts don't apply to syllables: each",
                "row is keyed to the word's first required position, not",
                "one lane per finger. See the cards above, or the",
                "syllables chapter in the session analysis notebook, for",
                "accuracy by syllable count and beat-synchronisation SD.",
            ]
            line_h = FONT_SMALL + 6
            start_y = note_rect.centery - (len(note_lines) - 1) * line_h // 2
            for i, line in enumerate(note_lines):
                draw_text(
                    surf, line,
                    (note_rect.centerx, start_y + i * line_h),
                    self.theme, self.layout, pt=FONT_SMALL, centre=True,
                    colour=self.theme.muted,
                )
        elif pat is not None:
            # No per-finger RT chart for Muscle Memory: the mode's own
            # docstring rules that RT numbers are never shown to the
            # patient (Boyd and Winstein; audit finding #9 closed the
            # stat cards, but this chart still printed a per-finger
            # mean RT axis on the same screen). The panel instead says
            # what the mode trains, in the research brief's
            # patient-safe terms: practice, accuracy, and speed that
            # arrives on its own. Nothing here may hint that hidden
            # material exists.
            note_rect = pygame.Rect(left_x, chart_y,
                                    total_chart_w, chart_h)
            body = tuple(max(0, min(255, c - 8))
                        for c in self.theme.background)
            pygame.draw.rect(surf, body, note_rect, border_radius=14)
            outline = tuple(max(0, c - 30) for c in self.theme.background)
            pygame.draw.rect(surf, outline, note_rect, 1, border_radius=14)
            note_lines = [
                "Muscle Memory trains finger skill the way a musician",
                "practises: lay down clean takes, session after session,",
                "and the riff settles into the hand without you thinking",
                "about it. Stars reward accuracy, never speed, so play",
                "cleanly and let quickness arrive on its own.",
            ]
            line_h = FONT_SMALL + 6
            start_y = note_rect.centery - (len(note_lines) - 1) * line_h // 2
            for i, line in enumerate(note_lines):
                draw_text(
                    surf, line,
                    (note_rect.centerx, start_y + i * line_h),
                    self.theme, self.layout, pt=FONT_SMALL, centre=True,
                    colour=self.theme.muted,
                )
        elif mir is not None:
            # Mirror always keys its per-lane histogram on the
            # right-hand copy of the finger (log_trial's lane() only
            # ever returns 0..3, see PendingMirrorTrial.lane()), so
            # the generic 8-lane split below would draw lanes 4-7 as
            # empty and read as "the left hand did nothing" -- a
            # lane-keying convention, not a real hand asymmetry (audit
            # finding #69). Draw 4 bars for "both hands together" per
            # finger instead; the SYNC GAP card above + the notebook's
            # mirror asynchrony section are the real per-hand view.
            rts_dict = getattr(self.engine, "_per_lane_rts", {}) or {}
            miss_dict = getattr(self.engine, "_per_lane_misses", {}) or {}
            wrong_dict = getattr(self.engine, "_per_lane_wrong", {}) or {}
            rts4 = [
                (sum(rts_dict.get(i, [])) / len(rts_dict[i]))
                if rts_dict.get(i) else 0.0
                for i in range(4)
            ]
            miscounts4 = [
                float(miss_dict.get(i, 0) + wrong_dict.get(i, 0))
                for i in range(4)
            ]
            self._draw_per_lane_chart(
                surf,
                pygame.Rect(left_x, chart_y, chart_w, chart_h),
                "MEAN RT PER FINGER (BOTH HANDS, LATER PRESS)",
                rts4, unit="ms", high_is_bad=False,
            )
            self._draw_per_lane_chart(
                surf,
                pygame.Rect(left_x + chart_w + chart_gap, chart_y,
                             chart_w, chart_h),
                "NOT CAUGHT + OTHER-FINGER PRESSES PER FINGER",
                miscounts4, unit="count", high_is_bad=True,
            )
        else:
            # `getattr` defaults shield against an engine state where
            # the per-lane dicts weren't populated (a fresh engine
            # before any block, or a __new__-built engine in some test
            # paths). Empty dicts just produce zero-height bars.
            rts_dict = getattr(self.engine, "_per_lane_rts", {}) or {}
            miss_dict = getattr(self.engine, "_per_lane_misses", {}) or {}
            wrong_dict = getattr(self.engine, "_per_lane_wrong", {}) or {}
            rts = [
                (sum(rts_dict.get(i, [])) / len(rts_dict[i]))
                if rts_dict.get(i) else 0.0
                for i in range(n_lanes)
            ]
            miscounts = [
                float(miss_dict.get(i, 0) + wrong_dict.get(i, 0))
                for i in range(n_lanes)
            ]
            self._draw_per_lane_chart(
                surf,
                pygame.Rect(left_x, chart_y, chart_w, chart_h),
                ("MEAN REACTION TIME PER FINGER"
                  if self.engine.current_block != "rhythm"
                  else "MEAN BEAT-OFFSET PER FINGER"),
                rts, unit="ms", high_is_bad=False,
            )
            self._draw_per_lane_chart(
                surf,
                pygame.Rect(left_x + chart_w + chart_gap, chart_y,
                             chart_w, chart_h),
                "NOT CAUGHT + OTHER-FINGER PRESSES PER FINGER",
                miscounts, unit="count", high_is_bad=True,
            )

        # Miss-trial force readout. Sums each finger's peak above baseline
        # over the first second of every MISSED trial, across all fingers,
        # so it answers "how hard was the patient pushing the whole hand
        # when they failed the trial". Only real with the force sensors;
        # keyboard mode has no force so it says so plainly.
        src = getattr(self.engine, "source", None)
        has_force = bool(src is not None and getattr(src, "provides_samples", False))
        mf_total = getattr(self.engine, "_miss_force_total", 0.0)
        mf_count = getattr(self.engine, "_miss_force_count", 0)
        mf_window = int(getattr(self.engine, "_force_window_ms", 1000))
        if not has_force:
            mf_text = ("Force on uncaught cues: needs the force "
                       "sensors (not available in keyboard mode)")
        elif mf_count > 0:
            mf_text = (
                f"Force on uncaught cues: {mf_total:.0f} sensor units "
                f"over {mf_count} cues (avg {mf_total / mf_count:.0f} "
                f"each, all fingers, first {mf_window} ms)")
        else:
            mf_text = "Force on uncaught cues: every cue was caught"
        draw_text(surf, mf_text, (cx, 650), self.theme, self.layout,
                  pt=FONT_SMALL, centre=True, colour=self.theme.muted)

        # Path to saved session for the therapist's records. Below
        # the histograms now; smaller font since this is footer info.
        if self.engine.last_session_root:
            path = self.engine.last_session_root
            if len(path) > 90:
                path = "..." + path[-87:]
            draw_text(surf, f"Saved to: {path}",
                      (cx, 666), self.theme, self.layout, pt=FONT_SMALL,
                      centre=True, colour=self.theme.muted)

class DiagnosticsScreen(Screen):
    """Settings + hardware test screen reachable from the title.

    Three jobs:
    1. Live FSR readout per lane (or keyboard-press feedback in keyboard
       mode) so the therapist can verify each finger before a session.
    2. Show which port each hand got. Boards auto-assign by plug
       order (first detected = right, second = left); the dropdowns
       exist only to pin a specific port to a hand when plug order is
       not enough. Saves to config/user_settings.yaml. A saved port
       that no longer exists is ignored at boot and that hand falls
       back to plug order.
    3. A "Test STIM" button per hand that fires STIM:1..4 in sequence
       so the therapist can confirm each motor reacts.
    """

    # How long between sequential STIM:n pulses during the test. The
    # Arduino's stim pulse is 150 ms so 250 ms gives a clean gap.
    STIM_TEST_INTERVAL_S = 0.25

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.back_btn = Button(
            pygame.Rect(40, engine.layout.height - 90, 180, BUTTON_H - 10),
            "Back", engine.show_title,
            self.theme, self.layout,
        )
        self.lanes: list[LaneStrip] = []
        # Held-key tracker for keyboard mode. Key id -> pygame.K_*.
        self._held_keys: set[int] = set()
        # Hardware panel state -------------------------------------------
        self._detected_ports: list[str] = []   # latest port scan
        self._port_status: str = ""             # info / error banner
        # Last port-watcher generation this panel redrew itself for. The
        # engine's watcher scans on its own thread; the panel only reads
        # the counter, so a board plugged in while Settings is open
        # appears in the dropdowns without a Refresh press and without
        # the frame ever waiting on the OS.
        self._port_watch_gen = 0
        # Pending dropdown selections (not written to disk until the
        # user hits Save). Empty = "no changes from saved".
        self._pending_ports: dict[str, str | None] = {}
        self._has_unsaved = False
        # In-flight STIM test sequencer. Holds the queue of (hand_prefix,
        # lane_num) tuples and the time each should fire. Drained in
        # update() one entry at a time so the motors don't all pulse at
        # once.
        self._stim_queue: list[tuple[str, int, float]] = []
        # Dropdowns + buttons for the hardware panel; (re)built in
        # `rebuild_panel` whenever the port list changes.
        self._panel_buttons: list[Button] = []
        # The firmware modal, and the three things it needs. All None
        # until a firmware button is pressed: locating avrdude touches
        # the filesystem and the port list, which is not work the screen
        # should do just because somebody opened Settings.
        self._dialog = None
        self._firmware_tool = None
        self._firmware_game = None
        self._firmware_addr = None
        # The Muscle Memory sequence file card and the one button that
        # opens it. Kept out of _panel_buttons because that list is
        # hit-tested against the ports panel; this button lives in the
        # session data panel with its own list.
        from .pattern_file_panel import PatternFilePanel
        self._riff_panel = PatternFilePanel(engine, self.theme, self.layout)
        self._riff_buttons: list[Button] = []
        from .widgets import Dropdown
        self._port_dropdowns: dict[str, Dropdown] = {}
        # Test Mode toggle. Rect is sized + positioned every frame in
        # `draw` (depends on the rendered label width), and the click
        # handler in handle_event consults this rect to flip the cfg
        # flag. Storing it as an instance var keeps the click test
        # consistent with what was drawn last frame.
        self._test_mode_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        # Menu-music on/off pill, same pattern: rect cached from the
        # draw pass, hit-tested in handle_event. That pill is the
        # machine's switch; the corner MuteButton below is the logged-
        # in person's own mute, the same pill every menu screen has.
        self._menu_music_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
        self.mute_btn = MuteButton(
            engine, pygame.Rect(28, 26, MuteButton.W, MuteButton.H))
        # Sensory Cues menu: the four cue.* switches plus the screen
        # reveal, each on or off on its own. Replaces the old buzzer
        # on/off pill and the both/visual/vibration cycling pill, which
        # between them could only reach three of the sixteen states.
        self._cue_menu = self._build_cue_menu()
        # Audio volume sliders (master / cue / feedback). _vol_dirty
        # guards the save so we only write user_settings.yaml when a
        # level actually changed.
        self._vol_dirty = False
        self._vol_sliders: dict = {}
        self._build_volume_sliders()
        self.rebuild_lanes()
        self.refresh_ports()
        self.rebuild_panel()
        # Open with the boot assignment on the status line, so the
        # plug-order result (and any ignored stale saved port) greets
        # the therapist instead of hiding in the log.
        note = getattr(engine.source, "assignment_note", "")
        if note and not self._port_status:
            self._port_status = note
        # Open in step with the watcher so the boot note is not wiped by
        # a "ports changed" line on the very first frame.
        self._port_watch_gen = getattr(
            getattr(engine, "port_watcher", None), "generation", 0)

    # ---- screen groups ----------------------------------------------------
    # Five labelled panels in three rows: the cue switches beside the
    # levels, then the eight finger tiles, then the Arduino ports beside
    # the data folder. Every control is positioned from the numbers below
    # and every panel is drawn from them, so a control can never sit
    # outside the group it belongs to and a hit box can never land where
    # nothing was drawn. The screen had grown to eleven loose controls on
    # a plain background and a therapist had to already know where each
    # one was; the grouping is what makes it findable.
    BAND_X = 30
    BAND_PAD = 18

    # Row 1, side by side: what the patient feels and hears, then how loud
    # and how long it is.
    # Starts below the header subtitle, which runs to about y=146.
    ROW1_TOP = 156
    ROW1_H = 112
    ROW1_GAP = 16
    CUES_W = 360
    # Shared centre line for the cue pill and the slider tracks, so the
    # row reads as one line of controls rather than two stacks that
    # nearly line up. Slider.draw puts its caption LABEL_GAP above the
    # track, which lands the captions clear of the panel headings.
    CUES_ROW_MID = 236
    CUE_PILL_W = 324
    CUE_PILL_H = 42
    CUE_HINT_Y = 188
    SLIDER_H = 24
    SLIDER_GAP = 36

    # Row 2, the eight finger tiles.
    FINGERS_TOP = 278
    FINGERS_H = 244
    HAND_LABEL_Y = 320
    LANES_TOP = 344
    LANES_PAD = 14
    LANES_GUTTER = 18       # between two tiles of the same hand
    LANES_SPLIT = 64        # between the two hands

    # Row 3, side by side: which Arduino is on which hand, then where the
    # recordings land. Sits on the bottom of the usable height, above the
    # Back button and the footer.
    PANEL_HEIGHT = 170
    PANEL_BOTTOM_GAP = 100
    PORTS_W = 724
    PORTS_LABEL_X = 48
    PORTS_LABEL_W = 70
    PORTS_DROPDOWN_W = 290
    PORTS_TEST_W = 170
    PORTS_ROW_H = 40
    PORTS_ROW_GAP = 12
    PORTS_BTN_W = 100
    PORTS_COL_GAP = 20
    DATA_X = 770
    DATA_BTN_W = 210
    # The data panel used to run to the right edge. It now stops at a
    # fixed width so the firmware panel can have the rest. 246 is the
    # floor: "Open data folder" is DATA_BTN_W wide inside BAND_PAD each
    # side, and a button that pokes out of its band is a real bug (a
    # click lands where nothing was drawn), which test_screen_layout
    # pins.
    DATA_W = 250
    FIRMWARE_BTN_H = 40

    def _cues_rect(self) -> pygame.Rect:
        return pygame.Rect(self.BAND_X, self.ROW1_TOP,
                           self.CUES_W, self.ROW1_H)

    def _levels_rect(self) -> pygame.Rect:
        x = self.BAND_X + self.CUES_W + self.ROW1_GAP
        return pygame.Rect(x, self.ROW1_TOP,
                           self.layout.width - self.BAND_X - x, self.ROW1_H)

    def _fingers_rect(self) -> pygame.Rect:
        return pygame.Rect(self.BAND_X, self.FINGERS_TOP,
                           self.layout.width - self.BAND_X * 2,
                           self.FINGERS_H)

    def _panel_top(self) -> int:
        return self.layout.height - self.PANEL_BOTTOM_GAP - self.PANEL_HEIGHT

    def _ports_rect(self) -> pygame.Rect:
        return pygame.Rect(self.BAND_X, self._panel_top(),
                           self.PORTS_W, self.PANEL_HEIGHT)

    def _data_rect(self) -> pygame.Rect:
        return pygame.Rect(self.DATA_X, self._panel_top(),
                           self.DATA_W, self.PANEL_HEIGHT)

    # The sequence-file button sits on the last free line of the data
    # panel, under the sessions path. Shorter than the buttons above it
    # (28 against 40) because that is the room the panel has left, and
    # it opens a card rather than doing anything on its own.
    RIFF_BTN_H = 28

    def _riff_btn_rect(self) -> pygame.Rect:
        d = self._data_rect()
        return pygame.Rect(d.x + self.BAND_PAD, self._ports_row_y(1) + 38,
                           self.DATA_BTN_W, self.RIFF_BTN_H)

    def _refresh_riff_button(self) -> None:
        """Build the button if it is missing and keep its label in step
        with what is loaded. Rebuilt on draw rather than on a port
        rescan because the file can change from the card, from a drop
        on the window, or from the drop folder."""
        try:
            line = self.engine.pattern_plan_headline()
        except Exception:
            line = ""
        name = line.split(" (", 1)[0] if line else ""
        label = f"Riff file: {name}" if name else "Riff file: built-in"
        rect = self._riff_btn_rect()
        font = self.layout.font(FONT_BODY - 4)
        label = _fit_text(label, font, rect.w - 16) or "Riff file"
        if not self._riff_buttons:
            self._riff_buttons = [Button(
                rect, label, self._open_riff_panel,
                self.theme, self.layout, font_pt=FONT_BODY - 4)]
        else:
            self._riff_buttons[0].rect = rect
            self._riff_buttons[0].label = label

    def _open_riff_panel(self) -> None:
        self._riff_panel.show()

    def set_status(self, text: str) -> None:
        """Put a line on the screen's message bar. The engine calls this
        when a file is dropped on the window, so the drop lands
        somewhere visible instead of only in the log."""
        if text:
            self._port_status = str(text)
            if self._riff_panel.open:
                self._riff_panel.status = str(text)

    def _firmware_x(self) -> int:
        return self.DATA_X + self.DATA_W + self.ROW1_GAP

    def _firmware_rect(self) -> pygame.Rect:
        """The Arduino firmware panel, right of the data folder. Takes
        whatever the row has left, which is 214 px at the 1280 wide
        render size ui.resolution fixes."""
        x = self._firmware_x()
        return pygame.Rect(x, self._panel_top(),
                           self.layout.width - self.BAND_X - x,
                           self.PANEL_HEIGHT)

    def _ports_row_y(self, i: int) -> int:
        """Top of port row i. Used by rebuild_panel for the dropdown and
        the buttons, and by draw for the LEFT / RIGHT label beside them,
        so the label always sits on the row it names."""
        return (self._panel_top() + 50
                + i * (self.PORTS_ROW_H + self.PORTS_ROW_GAP))

    def _status_pos(self) -> tuple[int, int]:
        """Where the message line goes: the bottom strip, starting to the
        right of the Back button. It carries messages from every group
        (cue help, a saved level, a port write, a buzzer test), so it
        belongs to the screen rather than to any one panel."""
        return (self.back_btn.rect.right + 20,
                self.back_btn.rect.centery - 10)

    def _draw_band(self, surf: pygame.Surface, rect: pygame.Rect,
                   title: str, hint: str = "") -> None:
        """Soft panel plus its heading. One look for all five groups so
        the screen reads as a handful of jobs rather than a wall of
        controls. `hint` is right-aligned in the heading row and is
        truncated to whatever space the heading leaves."""
        bg = tuple(max(0, c - 14) for c in self.theme.background)
        pygame.draw.rect(surf, bg, rect, border_radius=12)
        head_font = self.layout.font(FONT_SMALL + 4)
        head = head_font.render(title, True, self.theme.muted)
        surf.blit(head, (rect.x + self.BAND_PAD, rect.y + 8))
        if hint:
            f = self.layout.font(FONT_SMALL + 2)
            room = (rect.w - self.BAND_PAD * 2 - head.get_width() - 24)
            hint = _fit_text(hint, f, room)
            if hint:
                s = f.render(hint, True, self.theme.muted)
                surf.blit(s, s.get_rect(
                    topright=(rect.right - self.BAND_PAD, rect.y + 10)))

    def _build_volume_sliders(self) -> None:
        """Four sliders in the levels panel: master scales the whole
        game, cue is the pre-press click, feedback the post-press chime,
        and buzzer is how long a cue pulse runs. Initial values come from
        the merged config so a saved level shows up on reopen."""
        # Labels stay short: four sliders across one panel leaves little
        # room before a label runs into its right-aligned value.
        specs = (
            ("master", "MASTER", "audio.master_volume", 0.8),
            ("cue", "CUE", "audio.cue_volume", 1.0),
            ("feedback", "FEEDBACK", "audio.feedback_volume", 1.0),
            # Menu playlist level. The on/off switch for it is the
            # MENU MUSIC pill in the top-right metadata column.
            ("music", "MUSIC", "audio.menu_music_volume", 0.5),
        )
        n = len(specs) + 1     # + the buzzer cue-length slider
        gap = self.SLIDER_GAP
        panel = self._levels_rect()
        x0 = panel.x + self.BAND_PAD
        total_w = panel.right - self.BAND_PAD - x0
        sw = (total_w - gap * (n - 1)) // n
        # Same vertical centre as the cue pill in the panel alongside, so
        # the whole row reads as one line of controls rather than as two
        # stacks that nearly line up.
        track_y = self.CUES_ROW_MID - self.SLIDER_H // 2
        self._vol_sliders = {}
        from ..audio.menu_music import menu_music_level
        for i, (key, label, cfgkey, dflt) in enumerate(specs):
            rect = pygame.Rect(x0 + i * (sw + gap), track_y, sw,
                               self.SLIDER_H)
            if key == "music":
                # The shipped default is derived (half as loud as the
                # game music), so the knob opens on that level rather
                # than on a number the config does not hold.
                initial = menu_music_level(self.engine.cfg)
            else:
                initial = float(self.engine.cfg.get(cfgkey, dflt))
            self._vol_sliders[key] = Slider(
                rect, self.theme, self.layout,
                min_value=0.0, max_value=1.0,
                initial=initial,
                step=0.05, label=label, value_format="{:.0%}",
            )
        # Buzzer cue length. Vibration STRENGTH is fixed in the firmware
        # (STIM_PWM is a compile-time constant and there is no command to
        # change it), so length is the only thing the host can vary, and
        # it is what makes a cue easy or hard to feel. Range matches the
        # vibrotactile literature: 150 ms is one firmware pulse, beyond
        # about 400 ms the cue starts overlapping the patient's response.
        rect = pygame.Rect(x0 + len(specs) * (sw + gap), track_y, sw,
                           self.SLIDER_H)
        self._vol_sliders["buzz"] = Slider(
            rect, self.theme, self.layout,
            min_value=150.0, max_value=450.0,
            initial=float(self.engine.cfg.get("motor.cue_ms", 250)),
            step=50.0, label="BUZZER",
            value_format="{:.0f} ms",
        )

    def _apply_volumes_live(self) -> None:
        """Push the current slider values into the in-memory config and
        the running audio engine so a drag is heard immediately, no
        restart needed. Marks the levels dirty so _save_volumes writes
        them on mouse-up."""
        m = self._vol_sliders["master"].value
        c = self._vol_sliders["cue"].value
        f = self._vol_sliders["feedback"].value
        au = self.engine.cfg.data.setdefault("audio", {})
        au["master_volume"] = m
        au["cue_volume"] = c
        au["feedback_volume"] = f
        # The menu player reads this off cfg on every tick, so writing
        # it here is the whole live path.
        au["menu_music_volume"] = self._vol_sliders["music"].value
        if self.engine.audio is not None:
            self.engine.audio.set_volumes(master=m, cue=c, feedback=f)
        # Buzzer cue length lives under motor.*, not audio.*.
        self.engine.cfg.data.setdefault("motor", {})["cue_ms"] = int(
            self._vol_sliders["buzz"].value)
        self._vol_dirty = True

    def _save_volumes(self) -> None:
        """Persist the three levels to user_settings.yaml (same file the
        port assignments use) so they survive a restart."""
        try:
            self.engine.cfg.save_user_overrides({
                "audio.master_volume": self._vol_sliders["master"].value,
                "audio.cue_volume": self._vol_sliders["cue"].value,
                "audio.feedback_volume": self._vol_sliders["feedback"].value,
                "audio.menu_music_volume": self._vol_sliders["music"].value,
                "motor.cue_ms": int(self._vol_sliders["buzz"].value),
            })
            self._vol_dirty = False
            self._port_status = "Audio and buzzer settings saved."
        except Exception as e:
            self._port_status = f"Audio save failed: {e}"

    # The Sensory Cues menu, in the order the patient meets them: the
    # two things that happen before the press, then the two that happen
    # after a correct one, then the screen. Each entry is
    # (config key, row label, what the patient experiences). The help
    # text lands in the status line while the row is hovered.
    CUE_ROWS = CUE_ROWS

    def _cue_pill_rect(self) -> pygame.Rect:
        """Where the closed cue pill sits: filling the cues panel's
        control row. One source for the widget's rect, which is what it
        draws AND what it hit-tests."""
        return pygame.Rect(self._cues_rect().x + self.BAND_PAD,
                           self.CUES_ROW_MID - self.CUE_PILL_H // 2,
                           self.CUE_PILL_W, self.CUE_PILL_H)

    def _build_cue_menu(self) -> ToggleMenu:
        """The Sensory Cues menu.

        Four independent cue channels plus the screen reveal, any
        combination allowed. This is the comparison the project line
        started from: Palmer found reaction time differed between an
        LED-only cue and all cues together, and one switch per channel
        is what lets a block isolate any one of them. Each trial row
        records the state in cue_flags, so blocks run under different
        settings can be pooled and split again in the analysis.

        It is a menu rather than five checkboxes laid out on the panel
        because five rows plus their labels do not fit a panel that also
        has to leave room for the finger tiles below. Opening it covers
        those tiles, which is harmless: they are for testing hardware and
        nothing is being tested while the cues are being set. The pill
        carries the on-count so the state is readable without opening it.

        The pill is titled for what it counts rather than repeating the
        panel heading above it.
        """
        return ToggleMenu(
            self._cue_pill_rect(), list(self.CUE_ROWS),
            get_value=lambda k: bool(self.engine.cfg.get(k, True)),
            on_toggle=self._set_cue,
            theme=self.theme, layout=self.layout,
            title="Channels on",
        )

    def _set_cue(self, key: str, value: bool) -> None:
        apply_cue_setting(self.engine, key, value)
        self._port_status = ""

    def _toggle_test_mode(self) -> None:
        """Flip game.test_mode_enabled and persist it through the
        same user_settings.yaml the port assignments use. Persistence
        means turning Test Mode on once survives an app restart - so
        a researcher who left it on accidentally won't think the
        software is broken when the next block is only 6 trials."""
        current = bool(self.engine.cfg.get("game.test_mode_enabled", False))
        new_value = not current
        self.engine.cfg.data.setdefault(
            "game", {})["test_mode_enabled"] = new_value
        try:
            self.engine.cfg.save_user_overrides({
                "game.test_mode_enabled": new_value,
            })
        except Exception as e:
            self._port_status = f"Test Mode save failed: {e}"
            return
        n = int(self.engine.cfg.get("game.test_mode_trials", 6))
        self._port_status = (
            f"Test Mode ON. Next block runs {n} trials so you can "
            f"demo the full pipeline in under a minute."
            if new_value else
            "Test Mode OFF. Blocks run their normal full length."
        )

    def _toggle_menu_music(self) -> None:
        """Flip audio.menu_music_enabled and persist it the same way
        Test Mode persists. The playlist itself follows on its next
        tick (it reads cfg live); the stop_now here is only so OFF is
        heard the instant it is clicked rather than a fade later."""
        new_value = not bool(
            self.engine.cfg.get("audio.menu_music_enabled", True))
        self.engine.cfg.data.setdefault(
            "audio", {})["menu_music_enabled"] = new_value
        try:
            self.engine.cfg.save_user_overrides({
                "audio.menu_music_enabled": new_value,
            })
        except Exception as e:
            self._port_status = f"Menu music save failed: {e}"
            return
        player = getattr(self.engine, "menu_music", None)
        if not new_value and player is not None:
            player.stop_now()
        self._port_status = (
            "Menu music ON. Plays on the menu screens, never in a game."
            if new_value else "Menu music OFF."
        )

    def _lanes_bottom_y(self) -> int:
        """Bottom of the finger tiles: the inside of the finger panel."""
        return self._fingers_rect().bottom - self.LANES_PAD

    def _hand_block_x(self, hand: str) -> int:
        """Left edge of one hand's block of four tiles. Used for the
        tiles themselves and for the LEFT / RIGHT heading over them, so
        the heading always sits over the tiles it names."""
        panel = self._fingers_rect()
        return (panel.x + self.BAND_PAD if hand == "left"
                else panel.right - self.BAND_PAD - self._hand_block_w())

    def _hand_block_w(self) -> int:
        panel = self._fingers_rect()
        inner = panel.w - self.BAND_PAD * 2
        return (inner - self.LANES_SPLIT) // 2

    def rebuild_lanes(self) -> None:
        """Always render all 8 finger tiles in Settings, regardless of
        the current hand_mode. The Settings screen is the place a
        therapist verifies the hardware before a block; cutting it
        down to 4 tiles when hand_mode=left/right would hide the
        other Arduino's sensors and you'd have no way to test them
        without changing modes first. Lanes for a hand that isn't
        actually plugged in just sit idle (their FSR feed stays at
        zero) so the layout is harmless even on a single-Arduino
        rig."""
        self.lanes = []
        y = self.LANES_TOP
        h = self._lanes_bottom_y() - y
        # Bilateral layout: right hand on the right half of the
        # screen with index closest to centre, left hand on the
        # left half mirrored. Same arrangement the gameplay screen
        # uses in bilateral mode so what the therapist sees here
        # matches what the patient will see when the block starts.
        gutter = self.LANES_GUTTER
        n = 4
        w = (self._hand_block_w() - gutter * (n - 1)) // n
        rects: dict[int, pygame.Rect] = {}
        # Left hand on the LEFT of the screen: lanes 7,6,5,4 reading
        # left-to-right (little finger outermost).
        left_x = self._hand_block_x("left")
        for pos in range(n):
            rects[7 - pos] = pygame.Rect(
                left_x + pos * (w + gutter), y, w, h)
        # Right hand on the RIGHT: lanes 0,1,2,3 reading left-to-right.
        right_x = self._hand_block_x("right")
        for pos in range(n):
            rects[pos] = pygame.Rect(
                right_x + pos * (w + gutter), y, w, h)
        for i in range(8):
            is_left = i >= 4
            finger = i - 4 if is_left else i
            self.lanes.append(LaneStrip(
                lane=i, rect=rects[i],
                theme=self.theme, layout=self.layout,
                hand="left" if is_left else "right",
                finger=finger,
            ))

    # ---- hardware port mapping panel --------------------------------------

    def refresh_ports(self) -> None:
        """Re-scan the OS for Arduino-family serial ports. Uses
        discover_ports (VID-matched + junk-filtered) rather than the
        raw list_available_ports so random macOS virtual ports never
        appear in the dropdown the user can pick from."""
        try:
            from ..hardware.serial_source import discover_ports
            vids = self.engine.cfg.get("serial.vendor_ids")
            # max_ports=8 so a future setup with multiple chained
            # Arduinos still shows them all in the dropdown.
            self._detected_ports = discover_ports(vids, max_ports=8)
        except Exception as e:
            self._detected_ports = []
            self._port_status = f"Port scan failed: {e}"

    def _current_port(self, hand: str) -> str | None:
        # Read the IN-MEMORY override (set by the dropdown) so the
        # dropdown reflects pending unsaved changes too.
        if hand in self._pending_ports:
            return self._pending_ports[hand]
        return self.engine.cfg.get(f"serial.{hand}_port")

    def _on_port_chosen(self, hand: str, value: object) -> None:
        """Dropdown callback. Stages the change in _pending_ports
        without writing to disk - the user has to hit Save."""
        new_value = value if value else None
        self._pending_ports[hand] = new_value
        self._has_unsaved = True
        self._port_status = (
            "Unsaved changes. Hit Save to remember them, or click "
            "another dropdown option to undo."
        )

    def _save_ports(self) -> None:
        """Write pending dropdown selections to user_settings.yaml so
        they persist across runs of the app."""
        try:
            self.engine.cfg.save_user_overrides({
                f"serial.{hand}_port": self._pending_ports.get(
                    hand, self.engine.cfg.get(f"serial.{hand}_port"))
                for hand in ("left", "right")
            })
            self._has_unsaved = False
            # Apply it now. Telling a therapist to restart the app
            # between two blocks of a session is a rotten answer, and it
            # used to be the only one.
            self._port_status = "Saved. Connecting..."
            try:
                self._port_status = f"Saved. {self.engine.reconnect_source()}"
            except Exception as e:
                log.warning("Live reconnect failed: %s", e)
                self._port_status = (
                    f"Saved, but could not connect now ({e}). "
                    f"It will be used next time the app starts."
                )
        except Exception as e:
            self._port_status = f"Save failed: {e}"

    def _start_stim_test(self, hand: str) -> None:
        """Queue STIM:1..N test pulses on the named hand. Sequenced so
        the patient can see each motor fire on its own."""
        n_per_hand = int(self.engine.cfg.get(
            "fsr.num_sensors_per_hand", 4))
        now = time.perf_counter()
        # Filter out any prior queue for this hand so a double-click
        # doesn't stack two tests.
        prefix = hand.upper()
        self._stim_queue = [(p, lane, t) for (p, lane, t)
                             in self._stim_queue if p != prefix]
        for i in range(n_per_hand):
            due = now + (i * self.STIM_TEST_INTERVAL_S)
            self._stim_queue.append((prefix, i + 1, due))
        self._port_status = (
            f"Testing {hand} hand: firing STIM:1..{n_per_hand} "
            f"with {int(self.STIM_TEST_INTERVAL_S * 1000)} ms gaps."
        )

    def _buzz_finger(self, ls: LaneStrip) -> None:
        """Fire a single STIM pulse on ONE finger so the therapist can
        check that finger's buzzer on its own. Sends the hand-prefixed
        command (LEFT:/RIGHT:) so multi_serial routes it to the matching
        board. The per-hand sequence button still tests all four at once.
        Flashes the tile and reports delivery either way."""
        labels = LaneStrip.FINGER_LABELS
        finger_name = labels[ls.finger % len(labels)]
        # Route through the engine's channel map so this tests exactly
        # what a session will send. Testing STIM:finger+1 directly would
        # verify a mapping the game does not use.
        try:
            ch = self.engine._stim_channel(ls.finger)
        except Exception:
            ch = ls.finger + 1
        cmd = f"{ls.hand.upper()}:STIM:{ch}"
        try:
            ok = self.engine.source.send_command(cmd)
            # One board only: it defaults to the "right" label, so a
            # LEFT:-prefixed command matches nothing and silently fails
            # even though the single device physically IS the hand being
            # tested (a left-hand session on one Arduino). Fall back to
            # the plain form, which multi_serial forwards to whichever
            # single board is connected. Same behaviour the in-game stim
            # path already relies on.
            if not ok and self._single_board():
                ok = self.engine.source.send_command(f"STIM:{ch}")
        except (OSError, AttributeError, RuntimeError) as err:
            self._port_status = f"Buzzer send error: {err}"
            return
        # Flash the tile regardless of delivery so the therapist sees
        # which finger they clicked even when no buzz comes out.
        ls.flash(LaneStrip.HAND_BADGE.get(ls.hand, self.theme.accent),
                 0.35, time.perf_counter())
        if ok:
            self._port_status = (
                f"Buzzing {ls.hand} {finger_name}. No buzz? Check that "
                f"hand's Arduino is assigned and plugged in.")
        else:
            self._port_status = (
                f"{cmd} not delivered. Assign the {ls.hand} Arduino "
                f"(buzzers need the hardware; keyboard mode has none).")

    def _single_board(self) -> bool:
        """True when exactly one Arduino is connected. Used to decide
        whether a hand-prefixed command should fall back to the plain
        form."""
        hands = getattr(self.engine.source, "hands", None)
        return bool(hands is not None and len(hands) == 1)

    @staticmethod
    def _short_port(p: str) -> str:
        """Strip /dev/cu. and /dev/tty. prefixes so port labels fit
        comfortably in a dropdown row. Delegates to discovery so the
        status lines and the dropdowns shorten names the same way."""
        from ..hardware.discovery import short_port
        return short_port(p)

    def _dropdown_options(self) -> list[tuple[object, str]]:
        """Options shown in each hand's port dropdown:
          - (None, the default: no override, plug order decides)
          - one entry per detected Arduino-family port
        Junk Mac ports (debug-console, Bluetooth-Incoming-Port, etc.)
        are filtered upstream in discover_ports so they cannot appear
        here even if the user clicks Refresh while one is present.
        """
        options: list[tuple[object, str]] = [(None, "Auto (plug order)")]
        for p in self._detected_ports:
            options.append((p, self._short_port(p)))
        return options

    def rebuild_panel(self) -> None:
        """(Re)build the bottom row: two port dropdowns, two STIM test
        buttons, Refresh and Save in the Arduino panel, and the folder
        button in the data panel.

        Called on init AND after every port re-scan so the dropdown
        options reflect what was just detected. Every rect comes off the
        group geometry, so a button is hit-tested exactly where the panel
        drew it."""
        from .widgets import Dropdown
        self._panel_buttons = []
        row_h = self.PORTS_ROW_H
        # Per-hand row layout:
        #   [HAND label] [dropdown ......]   [Test STIM]
        # Refresh sits on the first row and Save under it, so the two
        # write actions are one above the other rather than lost among
        # the per-hand controls.
        dd_x = self.PORTS_LABEL_X + self.PORTS_LABEL_W
        test_x = dd_x + self.PORTS_DROPDOWN_W + self.PORTS_COL_GAP
        btn_x = test_x + self.PORTS_TEST_W + self.PORTS_COL_GAP
        options = self._dropdown_options()
        for i, hand in enumerate(("left", "right")):
            y = self._ports_row_y(i)
            dd_rect = pygame.Rect(dd_x, y, self.PORTS_DROPDOWN_W, row_h)
            existing = self._port_dropdowns.get(hand)
            current = self._current_port(hand)
            if existing is None:
                self._port_dropdowns[hand] = Dropdown(
                    dd_rect, options, current,
                    on_change=(lambda v, h=hand:
                                self._on_port_chosen(h, v)),
                    theme=self.theme, layout=self.layout,
                    placeholder="Auto (plug order)",
                )
            else:
                existing.rect = dd_rect
                existing.set_options(options)
                existing.current_value = current
            # Test STIM button per hand.
            self._panel_buttons.append(Button(
                pygame.Rect(test_x, y, self.PORTS_TEST_W, row_h),
                f"Test {hand.upper()} STIM",
                lambda h=hand: self._start_stim_test(h),
                self.theme, self.layout, font_pt=FONT_BODY - 2,
            ))
        self._panel_buttons.append(Button(
            pygame.Rect(btn_x, self._ports_row_y(0),
                        self.PORTS_BTN_W, row_h),
            "Refresh", self._rescan_ports,
            self.theme, self.layout, font_pt=FONT_BODY - 2,
        ))
        # Save button. Green when unsaved changes exist so it stands
        # out as the next thing to click, muted when there's nothing
        # to save.
        save_colour = ((34, 197, 94) if self._has_unsaved
                       else None)
        self._panel_buttons.append(Button(
            pygame.Rect(btn_x, self._ports_row_y(1),
                        self.PORTS_BTN_W, row_h),
            "Save", self._save_ports,
            self.theme, self.layout, font_pt=FONT_BODY - 2,
            colour=save_colour,
        ))
        # Opens the sessions folder in Finder / Explorer so the
        # researcher can reach every recording without hunting through
        # the filesystem. Lives in the data panel, away from the port
        # controls, because it has nothing to do with the hardware.
        self._panel_buttons.append(Button(
            pygame.Rect(self._data_rect().x + self.BAND_PAD,
                        self._ports_row_y(0), self.DATA_BTN_W, row_h),
            "Open data folder", self.engine.open_sessions_folder,
            self.theme, self.layout, font_pt=FONT_BODY - 2,
        ))
        # Firmware panel. Writing the Arduino used to mean the Arduino
        # IDE, a PlatformIO project and four manual uploads per sensor
        # swap; these two buttons are that job with the developer tools
        # taken out of it.
        fw = self._firmware_rect()
        fw_x = fw.x + self.BAND_PAD
        fw_w = fw.w - self.BAND_PAD * 2
        self._panel_buttons.append(Button(
            pygame.Rect(fw_x, self._ports_row_y(0), fw_w, row_h),
            "Flash firmware", self._open_flash_dialog,
            self.theme, self.layout, font_pt=FONT_BODY - 2,
        ))
        self._panel_buttons.append(Button(
            pygame.Rect(fw_x, self._ports_row_y(1), fw_w, row_h),
            "Sensor address", self._open_address_dialog,
            self.theme, self.layout, font_pt=FONT_BODY - 2,
        ))

    # ---- firmware flashing ------------------------------------------------

    def _firmware_bits(self):
        """(avrdude tool, game hex, address-tool hex) or a refusal.

        Returns (tool, game, addr, None) when everything is present and
        (None, None, None, "why not") when it is not, so both click
        handlers refuse the same way and the reason lands on the status
        line rather than inside a dialog nobody asked for.
        """
        from ..hardware import flasher
        tool = flasher.find_avrdude(self.engine.cfg)
        if tool is None:
            return None, None, None, flasher.NO_AVRDUDE_MESSAGE
        game = flasher.find_hex("game", self.engine.cfg)
        addr = flasher.find_hex("addr_tool", self.engine.cfg)
        if game is None:
            return None, None, None, flasher.NO_HEX_MESSAGE
        return tool, game, addr, None

    def _open_firmware_dialog(self, mode: str) -> None:
        from ..hardware import flasher
        from .firmware_dialog import FirmwareDialog
        why = self.engine.firmware_job_allowed()
        if why:
            self._port_status = why
            return
        tool, game, addr, refusal = self._firmware_bits()
        if refusal:
            self._port_status = refusal
            return
        if mode == "address" and addr is None:
            self._port_status = flasher.NO_HEX_MESSAGE
            return
        ports = flasher.candidate_ports(self.engine.cfg, self.engine.source)
        if not ports:
            self._port_status = flasher.NO_PORT_MESSAGE
            return
        self._firmware_tool = tool
        self._firmware_game = game
        self._firmware_addr = addr
        self._dialog = FirmwareDialog(
            mode, self.theme, self.layout, ports=ports,
            firmware_label=game.label(),
            on_flash=self._start_firmware_job,
            on_address=self._start_address_job,
            on_close=self._close_firmware_dialog,
        )

    def _open_flash_dialog(self) -> None:
        self._open_firmware_dialog("flash")

    def _open_address_dialog(self) -> None:
        self._open_firmware_dialog("address")

    def _close_firmware_dialog(self) -> None:
        self._dialog = None

    def _start_firmware_job(self, port: str):
        """Hand the port to avrdude, then start the thread.

        begin_firmware_job runs here on the main thread on purpose: the
        job thread must never touch the engine, and the source has to be
        closed BEFORE avrdude opens the same port.
        """
        from ..hardware.flasher import FirmwareJob
        why = self.engine.firmware_job_allowed()
        if why:
            self._port_status = why
            return None
        self.engine.begin_firmware_job()
        job = FirmwareJob(self._firmware_tool, port, self._firmware_game,
                          self.engine.cfg)
        job.start()
        return job

    def _start_address_job(self, port: str, change: bool,
                           old: int | None, new: int | None):
        from ..hardware.flasher import AddressJob
        why = self.engine.firmware_job_allowed()
        if why:
            self._port_status = why
            return None
        if self._firmware_addr is None:
            self._port_status = "No address tool firmware in this build."
            return None
        self.engine.begin_firmware_job()
        job = AddressJob(
            self._firmware_tool, port, self._firmware_addr,
            self._firmware_game, self.engine.cfg,
            change=change, old=old if old is not None else 0x04,
            new=new if new is not None else 0x05)
        job.start()
        return job

    def _poll_firmware_job(self) -> None:
        """One frame's worth of watching the job. Called from update.

        Everything that touches the engine or the config file happens
        here, on the main thread, once the thread has set `done`.
        """
        dlg = self._dialog
        if dlg is None or dlg.job is None or not dlg.job.done:
            return
        job = dlg.job
        # Remember the bootloader that answered, so the next flash tries
        # the right speed first instead of failing at the wrong one for
        # a second and a half.
        if job.baud:
            try:
                self.engine.cfg.save_user_overrides(
                    {"firmware.preferred_baud": int(job.baud)})
            except Exception as e:
                log.warning("Could not remember the flash baud: %s", e)
        reconnected = self.engine.end_firmware_job()
        text = (job.summary or job.message).strip()
        if reconnected:
            text = f"{text} {reconnected}".strip()
        dlg.finish(text, bool(job.ok))
        self._port_status = text

    @property
    def firmware_dialog_open(self) -> bool:
        return self._dialog is not None

    def on_escape(self) -> bool:
        """Esc while a firmware dialog is up belongs to the dialog.

        Returns True when it was swallowed, so the engine leaves the
        Settings screen alone.
        """
        dlg = self._dialog
        if dlg is None:
            return False
        return dlg.on_escape()

    def _sync_with_port_watcher(self) -> None:
        """Redraw the Arduino panel when the watcher says the port list
        moved. The engine has already done (or queued) the connecting;
        this is only the panel keeping up with it."""
        w = getattr(self.engine, "port_watcher", None)
        if w is None:
            return
        gen = w.generation
        if gen == self._port_watch_gen:
            return
        # Hold off while a port dropdown is open. Growing the option
        # list under an open popup shifts the rows out from under the
        # cursor, so the click the therapist is halfway through lands
        # on a different port than the one they aimed at. The refresh
        # happens on the frame after they close it.
        if any(dd.is_open for dd in self._port_dropdowns.values()):
            return
        self._port_watch_gen = gen
        self.refresh_ports()
        self.rebuild_panel()
        note = ""
        getter = getattr(self.engine, "autoconnect_notice", None)
        if callable(getter):
            note = getter() or ""
        if note:
            self._port_status = note
            return
        n = len(self._detected_ports)
        self._port_status = (
            f"Ports changed. {n} Arduino-family port(s) detected."
            if n > 0 else
            "Arduino unplugged. Plug it back in and it reconnects "
            "on its own."
        )

    def _rescan_ports(self) -> None:
        self.refresh_ports()
        n = len(self._detected_ports)
        self._port_status = (
            f"Re-scanned. Found {n} Arduino-family port(s)."
            if n > 0 else
            "Re-scanned. No Arduino detected - keyboard fallback "
            "will run when you start a session."
        )
        self.rebuild_panel()

    def handle_event(self, e: pygame.event.Event) -> None:
        # The firmware modal eats everything while it is up. Nothing
        # under a dim layer may react: a stray click on Back mid flash
        # would leave the source stopped and the port with avrdude.
        if self._dialog is not None:
            self._dialog.handle_event(e)
            if self._dialog is not None and self._dialog.wants_close:
                self._dialog = None
            return
        # The sequence-file card is modal too: while it is up a click
        # must not reach a port dropdown or a finger tile drawn under
        # the dim layer.
        if self._riff_panel.handle_event(e):
            return
        # Dropdowns first so an open dropdown's option click is
        # consumed before the underlying STIM / Save button can fire.
        consumed = False
        # Sensory Cues menu goes first for the same reason: while it is
        # open its rows overlap the lane tiles, and a row click must not
        # also buzz the finger drawn underneath it.
        if self._cue_menu.handle_event(e):
            consumed = True
        for dd in self._port_dropdowns.values():
            if dd.handle_event(e):
                consumed = True
        # If a dropdown is open and the click landed inside its popup,
        # don't dispatch the event further (otherwise a buttons sitting
        # behind the popup would also fire).
        if consumed:
            return
        if self.mute_btn.handle_event(e):
            return
        # Volume sliders. Snapshot values so we only apply / save when a
        # level actually moved (a stray click on the track still counts).
        before = {k: s.value for k, s in self._vol_sliders.items()}
        for s in self._vol_sliders.values():
            s.handle_event(e)
        if any(self._vol_sliders[k].value != v for k, v in before.items()):
            self._apply_volumes_live()
        if (e.type == pygame.MOUSEBUTTONUP and e.button == 1
                and self._vol_dirty):
            self._save_volumes()
        self.back_btn.handle_event(e)
        for b in self._panel_buttons:
            b.handle_event(e)
        # Built lazily on the first draw, so a headless click before any
        # frame has rendered gets it built here too.
        if not self._riff_buttons:
            self._refresh_riff_button()
        for b in self._riff_buttons:
            b.handle_event(e)
        # Click a finger tile to buzz JUST that finger (fire its STIM
        # motor on its own). Press-to-test-sensor and click-to-test-buzzer
        # sit side by side: a physical press drives the FSR readout, a
        # mouse click pulses that finger's actuator.
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for ls in self.lanes:
                if ls.rect.collidepoint(e.pos):
                    self._buzz_finger(ls)
                    return
        # Test Mode toggle pill in the top-right. Hand-rolled hit-test
        # rather than a Button widget because the pill style (filled
        # green or muted with a coloured outline) is bespoke.
        if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                and self._test_mode_rect.w > 0
                and self._test_mode_rect.collidepoint(e.pos)):
            self._toggle_test_mode()
            return
        # Menu-music on/off pill, directly below Test Mode.
        if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1
                and self._menu_music_rect.w > 0
                and self._menu_music_rect.collidepoint(e.pos)):
            self._toggle_menu_music()
            return
        # Track held keys so the visual responds even when the source
        # doesn't push samples (keyboard mode).
        if e.type == pygame.KEYDOWN:
            self._held_keys.add(e.key)
        elif e.type == pygame.KEYUP:
            self._held_keys.discard(e.key)

    def _key_pressed_for_lane(self, lane: int, hand: str) -> bool:
        """Keyboard-mode press lookup. Always uses the BILATERAL
        keymap (FDSA + JKL;) so the therapist can press-test all
        eight fingers from Settings regardless of which hand_mode
        the next session will use. Without this, a unilateral
        hand_mode would only register half the keys here and the
        therapist would think the other hand's sensors were dead."""
        from ..game.modes._keys import keymap_for_hand, resolve_key
        km = self.engine.cfg.get(
            keymap_for_hand("both"), {},
        )
        for key_name, lane_idx in km.items():
            if lane_idx != lane:
                continue
            kc = resolve_key(key_name)
            if kc is not None and kc in self._held_keys:
                return True
        return False

    def update(self, dt: float) -> None:
        # A firmware job holds the port. Polling the watcher, driving
        # the STIM queue or reading the detectors would all be talking
        # to a source that is deliberately stopped, so the whole frame
        # is just the job while a dialog is up.
        if self._dialog is not None:
            self._poll_firmware_job()
            return
        # Keep the port panel current on its own.
        self._sync_with_port_watcher()
        # Drain any queued STIM test pulses that have come due.
        if self._stim_queue:
            now = time.perf_counter()
            still: list[tuple[str, int, float]] = []
            for prefix, lane, due in self._stim_queue:
                if now >= due:
                    cmd = f"{prefix}:STIM:{lane}"
                    try:
                        ok = self.engine.source.send_command(cmd)
                        # With one board (labelled "right" by default) a
                        # LEFT:-prefixed command matches nothing. Retry
                        # plain so testing the hand actually in the device
                        # works. Same fallback as _buzz_finger.
                        if not ok and self._single_board():
                            ok = self.engine.source.send_command(
                                f"STIM:{lane}")
                        if not ok:
                            # Most likely no Arduino on that hand; surface
                            # the result so the therapist knows the test
                            # didn't actually fire.
                            self._port_status = (
                                f"{cmd} not delivered. Check the Arduino "
                                "is plugged in and assigned."
                            )
                    except (OSError, AttributeError, RuntimeError) as e:
                        # OSError covers serial port faults (USB
                        # unplug mid-test). AttributeError covers
                        # the keyboard-only path where source has no
                        # send_command. RuntimeError covers pyserial
                        # closed-port edge cases. Surface the message
                        # so the therapist sees it in the status pill.
                        self._port_status = f"STIM send error: {e}"
                else:
                    still.append((prefix, lane, due))
            self._stim_queue = still
        # Mirror live FSR values from the source onto the lane strips.
        # On keyboard mode the values stay at 0 and we use _held_keys
        # to drive the active flag instead.
        if not self.lanes:
            return
        # Live sensor readout. The engine's _pump_source drains the
        # sample queue every frame and writes ls.value / ls.baseline /
        # ls.set_pressed for this screen, so we must NOT call
        # get_sample() here: doing so would race the pump and any
        # sample we grabbed would never reach the detectors.
        #
        # We do own the tile fill: reading the detector's live pressed
        # flag each frame turns the whole tile its active colour the
        # instant a finger goes down, which is the feedback the
        # therapist is looking for when checking the hardware.
        if self.engine.source.provides_samples:
            n_per_hand = int(self.engine.cfg.get(
                "fsr.num_sensors_per_hand", 4))
            for i, ls in enumerate(self.lanes):
                det = self.engine.detectors.get(ls.hand)
                if not det:
                    continue
                local = i % n_per_hand
                try:
                    ls.active = bool(det.pressed[local])
                    b = det.baseline[local]
                    ls.baseline = b if b is not None else 0.0
                    # Fallback for the value readout in case the pump
                    # has not written one yet this frame.
                    if not ls.value:
                        ls.value = int(det.last_value[local])
                except (IndexError, TypeError):
                    continue
        # Keyboard fallback: light up via held keys.
        if not self.engine.source.provides_samples:
            for ls in self.lanes:
                ls.active = self._key_pressed_for_lane(ls.lane, ls.hand)

    def _connection_state(self) -> tuple[str, tuple[int, int, int]]:
        """Pick the status text + colour for the top-right badge.

        Four states:
          - KEYBOARD: source doesn't provide samples (no Arduino).
          - DISCONNECTED: source claims to provide samples but is_connected is False.
          - NO DATA: port is open but no FSR samples have arrived in the
            last ~1.5 s. This is the case Mac hits when it auto-grabs
            /dev/cu.Bluetooth-Incoming-Port, opens it fine, but never
            receives any data because there's no Arduino on the wire.
          - CONNECTED: port open AND samples flowing.
        """
        src = self.engine.source
        if not src.provides_samples:
            return ("KEYBOARD", self.theme.muted)
        if not src.is_connected:
            return ("DISCONNECTED", self.theme.error)
        has_data = getattr(src, "has_recent_data", None)
        if callable(has_data) and not has_data(1.5):
            return ("NO DATA", self.theme.error)
        return ("CONNECTED", self.theme.success)

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        # Header.
        source_name = getattr(self.engine.source, "name", "?")
        state_text, state_colour = self._connection_state()
        sub = ("Press a finger to test its sensor, or click it to buzz "
                "that finger. Ports auto-assign by plug order; "
                "override below only if needed.")
        if state_text == "KEYBOARD":
            sub = ("Keyboard mode. Press FDSA / JKL; to test each "
                    "lane, or plug an Arduino in: it connects itself.")
        elif state_text == "DISCONNECTED":
            sub = ("Source not connected. Plug the Arduino in and it "
                    "reconnects on its own; Refresh forces a re-scan.")
        elif state_text == "NO DATA":
            sub = ("Port is open but no FSR data is arriving. "
                    "Check the Arduino is sending FSR: lines.")
        _draw_header(surf, "Settings", sub, self.theme, self.layout)
        # Source name pill top-right. Strip "Source(...)" wrappers so
        # long names like KeyboardOnlySource don't clip off the edge.
        clean_name = source_name
        if "Source" in clean_name:
            clean_name = clean_name.replace("OnlySource", "")
            clean_name = clean_name.replace("Source", "")
        nfont = self.layout.font(FONT_SMALL + 4)
        nsurf = nfont.render(clean_name, True, self.theme.muted)
        surf.blit(nsurf,
                   nsurf.get_rect(topright=(self.layout.width - 30, 28)))
        sfont = self.layout.font(FONT_BODY)
        st = sfont.render(state_text, True, state_colour)
        surf.blit(st, st.get_rect(
            topright=(self.layout.width - 30, 50)))
        # Test Mode toggle pill. Sits below the state text in the same
        # top-right metadata column. Green filled when on (matches the
        # Start Session "go" pill on the title screen so the visual
        # language for "active / live" carries over), muted-outlined
        # when off so it reads as an inactive switch. Click toggles.
        tm_on = bool(self.engine.cfg.get("game.test_mode_enabled", False))
        n_trials = int(self.engine.cfg.get("game.test_mode_trials", 6))
        tm_label = (f"TEST MODE  ON ({n_trials})" if tm_on
                     else "TEST MODE  OFF")
        tm_font = self.layout.font(FONT_SMALL + 2)
        tm_text_colour = ((255, 255, 255) if tm_on
                           else self.theme.foreground)
        tm_text = tm_font.render(tm_label, True, tm_text_colour)
        tm_pad_x = 14
        tm_pad_y = 5
        tm_w = tm_text.get_width() + tm_pad_x * 2
        tm_h = tm_text.get_height() + tm_pad_y * 2
        tm_rect = pygame.Rect(0, 0, tm_w, tm_h)
        tm_rect.topright = (self.layout.width - 30, 78)
        # Fill colour: green when on, transparent (background) when off.
        if tm_on:
            pygame.draw.rect(surf, (34, 197, 94), tm_rect,
                              border_radius=tm_h // 2)
        else:
            pygame.draw.rect(surf, self.theme.muted, tm_rect,
                              width=2, border_radius=tm_h // 2)
        surf.blit(tm_text, tm_text.get_rect(center=tm_rect.center))
        # Cache rect for the hit-test in handle_event.
        self._test_mode_rect = tm_rect
        # Menu-music pill, same visual language directly underneath:
        # filled accent when the playlist is on, muted outline when
        # off. The level lives on the MUSIC slider in the levels
        # panel; this is only the switch.
        mm_on = bool(self.engine.cfg.get("audio.menu_music_enabled", True))
        mm_label = "MENU MUSIC  ON" if mm_on else "MENU MUSIC  OFF"
        mm_text = tm_font.render(
            mm_label, True,
            (255, 255, 255) if mm_on else self.theme.foreground)
        mm_rect = pygame.Rect(0, 0, mm_text.get_width() + tm_pad_x * 2,
                              mm_text.get_height() + tm_pad_y * 2)
        mm_rect.topright = (self.layout.width - 30, tm_rect.bottom + 8)
        if mm_on:
            pygame.draw.rect(surf, self.theme.accent, mm_rect,
                             border_radius=mm_rect.h // 2)
        else:
            pygame.draw.rect(surf, self.theme.muted, mm_rect,
                             width=2, border_radius=mm_rect.h // 2)
        surf.blit(mm_text, mm_text.get_rect(center=mm_rect.center))
        self._menu_music_rect = mm_rect
        # Group 1, what the patient feels and hears. The five switches
        # live behind one pill because the panel has to leave room for
        # the tiles below; the pill carries the on-count so the state is
        # readable without opening it. Closed pill here, open list in the
        # overlay pass at the end of draw so it covers the tiles rather
        # than sliding under them.
        cues_rect = self._cues_rect()
        self._draw_band(surf, cues_rect, "SENSORY CUES")
        draw_text(surf, "Buzzer, sound and screen, each on its own",
                  (cues_rect.x + self.BAND_PAD, self.CUE_HINT_Y),
                  self.theme, self.layout, pt=FONT_SMALL,
                  colour=self.theme.muted)
        self._cue_menu.draw_closed(surf)
        # Group 2, how loud and how long those cues are. Master scales
        # the whole game; cue is the pre-press click; feedback is the
        # post-press chime; buzzer is the pulse length. Drag to set; it
        # applies live and saves on release.
        self._draw_band(surf, self._levels_rect(), "LEVELS",
                        "drag to set, saves on release")
        for s in self._vol_sliders.values():
            s.draw(surf)
        # Group 3, the finger tiles.
        now = time.perf_counter()
        fingers_rect = self._fingers_rect()
        finger_hint = ("press a finger to test its sensor, "
                       "click a tile to buzz it")
        if not self.engine.source.provides_samples:
            finger_hint = "keyboard mode: press FDSA / JKL; to test a lane"
        self._draw_band(surf, fingers_rect, "FINGER TEST", finger_hint)
        # Bilateral hand headings, always rendered because Settings
        # always shows all 8 lanes (even when the session-level
        # hand_mode is left or right only). Without them the therapist
        # wouldn't know which half of the panel is which hand. Centred
        # over the block of tiles they name rather than over the screen
        # quarter, so the heading moves with the tiles.
        half = self._hand_block_w() // 2
        for hand in ("left", "right"):
            draw_text(surf, hand.upper(),
                      (self._hand_block_x(hand) + half, self.HAND_LABEL_Y),
                      self.theme, self.layout, pt=FONT_H2, centre=True,
                      colour=LaneStrip.HAND_BADGE[hand])
        for ls in self.lanes:
            ls.draw(surf, now)
        # Group 4, which Arduino is on which hand. The heading row
        # states the auto rule, then the detected ports as short names
        # (the basename after /dev/cu.) so several fit on one line.
        ports_rect = self._ports_rect()
        auto_rule = "auto: first board = right, second = left"
        if self._detected_ports:
            shorts = [self._short_port(p) for p in self._detected_ports]
            detected_label = auto_rule + " | detected: " + ", ".join(shorts)
        else:
            detected_label = auto_rule + " | none detected"
        self._draw_band(surf, ports_rect, "ARDUINO PORTS", detected_label)
        # Per-hand row labels (LEFT / RIGHT) beside each dropdown, off
        # the same row geometry the dropdown was built from.
        for i, hand in enumerate(("left", "right")):
            y = self._ports_row_y(i)
            colour = LaneStrip.HAND_BADGE.get(hand, self.theme.foreground)
            draw_text(surf, hand.upper(),
                      (self.PORTS_LABEL_X, y + self.PORTS_ROW_H // 2 - 9),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=False, colour=colour)
        # Live result line: the port each hand actually has right now,
        # so the auto assignment (or an override) is never a mystery.
        live_hands = getattr(self.engine.source, "hands", None)
        if live_hands:
            now_txt = "now: " + "   ".join(
                f"{h.hand.upper()} = {self._short_port(h.port)}"
                for h in live_hands)
        else:
            now_txt = "now: keyboard (no Arduino connected)"
        draw_text(surf, now_txt,
                  (self.PORTS_LABEL_X, ports_rect.bottom - 24),
                  self.theme, self.layout, pt=FONT_SMALL,
                  centre=False, colour=self.theme.muted)
        # Group 5, where the recordings land. Says the path out loud next
        # to the button that opens it so the location is never a mystery.
        data_rect = self._data_rect()
        self._draw_band(surf, data_rect, "SESSION DATA")
        try:
            sessions_dir = str(self.engine.cfg.resolve_path(
                self.engine.cfg.get("session.data_dir", "sessions")))
        except Exception:
            sessions_dir = "sessions"
        cap_x = data_rect.x + self.BAND_PAD
        cap_w = data_rect.right - self.BAND_PAD - cap_x
        cap_font = self.layout.font(FONT_SMALL)
        # Pulled up eight pixels from the port row it used to line up
        # with: the riff button now takes the bottom line of this
        # panel, and the path was sitting on top of it.
        cap_y = self._ports_row_y(1) - 8
        draw_text(surf, "Every session is saved here:", (cap_x, cap_y),
                  self.theme, self.layout, pt=FONT_SMALL,
                  centre=False, colour=self.theme.muted)
        # Tail of the path, since the full one is usually longer than the
        # panel. Trimmed from the left so the session folder itself, the
        # part that identifies it, always stays visible.
        shown = sessions_dir
        while shown and cap_font.size("..." + shown)[0] > cap_w:
            shown = shown[1:]
        if shown != sessions_dir:
            shown = "..." + shown
        draw_text(surf, shown, (cap_x, cap_y + 20),
                  self.theme, self.layout, pt=FONT_SMALL,
                  centre=False, colour=self.theme.foreground)
        # The one button for the Muscle Memory sequence file. It sits
        # here rather than in a panel of its own because a loaded file
        # says what the recordings are OF, and the bottom row has no
        # width left for a seventh group. It replaced the "one folder
        # per day" caption, which said nothing the path above it does
        # not already show.
        # Its label carries the answer to the only question a therapist
        # asks about it in passing (is a custom riff loaded, and which
        # one), so the panel needs no extra caption row for it.
        self._refresh_riff_button()
        for b in self._riff_buttons:
            b.draw(surf)
        # Group 6, writing the Arduino. The caption says which firmware
        # is in this build, so a therapist can tell whether the board
        # already has it without flashing to find out.
        fw_rect = self._firmware_rect()
        self._draw_band(surf, fw_rect, "ARDUINO FIRMWARE")
        fw_caption, fw_colour = self._firmware_caption()
        # bottom - 24 clears the second button by four pixels. At -30 the
        # caption's first row of pixels lands inside the button above it,
        # which reads as a label belonging to the button rather than to
        # the panel.
        draw_text(surf, _fit_text(fw_caption,
                                  self.layout.font(FONT_SMALL),
                                  fw_rect.w - self.BAND_PAD * 2),
                  (fw_rect.x + self.BAND_PAD, fw_rect.bottom - 24),
                  self.theme, self.layout, pt=FONT_SMALL,
                  centre=False, colour=fw_colour)
        # Buttons for both bottom panels (test STIM, refresh, save, open
        # folder), then the dropdowns on top of whatever they overlap.
        for b in self._panel_buttons:
            b.draw(surf)
        for dd in self._port_dropdowns.values():
            dd.draw_closed(surf)
        self.back_btn.draw(surf)
        # Message line along the bottom, running right from the Back
        # button. Coloured orange while a port change is unsaved. A
        # hovered cue row takes the line over so the switch can say what
        # the patient will actually experience.
        status_line = self._cue_menu.hover_help() or self._port_status
        if status_line:
            sx, sy = self._status_pos()
            status_font = self.layout.font(FONT_SMALL + 2)
            status = _fit_text(status_line, status_font,
                               self.layout.width - self.BAND_X - sx)
            status_colour = (self.theme.warning
                              if self._has_unsaved
                              else self.theme.foreground)
            draw_text(surf, status, (sx, sy),
                      self.theme, self.layout, pt=FONT_SMALL + 2,
                      centre=False, colour=status_colour)
        # Dropdown popup overlays drawn LAST so they sit on top of
        # everything else, including the back button.
        for dd in self._port_dropdowns.values():
            dd.draw_overlay(surf)
        self.mute_btn.draw(surf, self.theme, self.layout)
        self._cue_menu.draw_overlay(surf)
        # Footer hint.
        draw_text(surf, "Esc returns to the title screen",
                  (self.layout.width // 2, self.layout.height - 30),
                  self.theme, self.layout, pt=FONT_SMALL + 2,
                  centre=True, colour=self.theme.muted)
        # The firmware modal last of all: it dims the whole screen, so
        # anything drawn after it would float above the dim layer and
        # look clickable when it is not.
        if self._dialog is not None:
            self._dialog.draw(surf)
        # Same rule for the sequence-file card.
        self._riff_panel.draw(surf)

    def _firmware_caption(self) -> tuple[str, tuple[int, int, int]]:
        """What is under the two firmware buttons, and in what colour.

        Read once and cached: this runs on the draw path and finding
        avrdude walks the filesystem. A missing piece is a warning
        colour, because the button above it will refuse when pressed.
        """
        cached = getattr(self, "_firmware_caption_cache", None)
        if cached is not None:
            return cached
        try:
            from ..hardware import flasher
            image = flasher.find_hex("game", self.engine.cfg)
            if image is None:
                out = ("no firmware bundled", self.theme.warning)
            elif flasher.find_avrdude(self.engine.cfg) is None:
                out = ("no avrdude found", self.theme.warning)
            else:
                out = (image.short_label(), self.theme.muted)
        except Exception as e:
            log.warning("Could not describe the bundled firmware: %s", e)
            out = ("firmware state unknown", self.theme.warning)
        self._firmware_caption_cache = out
        return out
