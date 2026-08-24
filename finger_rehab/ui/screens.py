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
    Button, Card, FloatingText, LaneStrip, Layout, Slider, TextInput,
    ToggleMenu,
    FONT_TITLE, FONT_H1, FONT_H2, FONT_BODY, FONT_SMALL,
    BUTTON_H, BUTTON_W, PADDING, draw_text, keyboard_controls_lines,
    make_font,
)

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
         "Nothing on a timeout or a wrong finger."),
        ("cue.sound_after", "Cue Sound after press",
         "A chime confirms a correct press. Off also silences the "
         "thunk that a miss makes, so nothing is heard after a press."),
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


class TitleScreen(Screen):
    # Session protocol shown in the Info overlay. Every participant runs
    # the same core modes, in the same order, the same number of times, so
    # the final analysis compares like with like. Reaction took Classic's
    # place as the baseline: Classic's fixed pattern was learnable in
    # seconds, so half of what it measured was anticipation.
    INFO_TITLE = "Session protocol"
    INFO_STEPS = [
        "1. Enter the participant name and age, then press LOG IN.",
        "2. Run the four core modes in this order, once each per session:",
        "      Reaction  (baseline eye-to-hand speed, random waits)",
        "      Adaptive  (40 trials, pace adjusts to the participant)",
        "      Rhythm  (one full song, press on the beat)",
        "      Mirror  (40 trials, both hands together)",
        "3. Training modes as prescribed for the participant:",
        "      Muscle Memory, Chords, Syllables, Force Pilot, Lighthouse,",
        "      Buzz Hunt",
        "4. Finish every block. Quitting early leaves gaps in the data.",
    ]
    INFO_FOOTER = ("The four core blocks give the comparable data; the "
                   "training modes add their own measures on top.")

    # Vertical rhythm, in logical pixels against the 1280x800 render
    # surface. Held as constants because the card, the two inputs and the
    # start button have to move together: the card is drawn from these and
    # so are the controls inside it, so neither can drift from the other.
    ICON_Y = 110
    WORDMARK_Y = 234
    TAGLINE_Y = 300
    CARD_TOP = 348
    CARD_W = 660
    CARD_H = 262
    # Utility strip along the bottom: one row of equal-height pills on a
    # single baseline, with a hairline rule above it.
    PILL_H = 44
    PILL_W = 150
    EDGE = 28

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        cx = engine.layout.width // 2
        w, h = engine.layout.width, engine.layout.height

        # Participant name + age inputs. Set once on the title screen
        # and reused for every block the patient plays this app
        # session, so every CSV row + every session folder is tagged
        # with the same name. Pre-fill from any persisted values so
        # quitting and reopening the title screen doesn't blank them
        # out.
        prefill_name = str(engine.cfg.get("session.participant") or "")
        if prefill_name in ("None", "NA"):
            prefill_name = ""
        prefill_age = str(engine.cfg.get("session.age") or "")
        if prefill_age in ("None", "NA"):
            prefill_age = ""
        # The two fields and the start button sit inside one card, so the
        # screen reads as "fill this in, then press go" rather than as
        # three unrelated controls floating on a background.
        self.card_rect = pygame.Rect(cx - self.CARD_W // 2, self.CARD_TOP,
                                     self.CARD_W, self.CARD_H)
        # Side-by-side row: wide name field + compact age field. The
        # age input is a research-metadata field (demographic cohort
        # matters for stroke rehab outcomes), so it's smaller and
        # paired with the name rather than getting its own row.
        name_w = 400
        age_w = 140
        gap = 20
        row_w = name_w + gap + age_w
        row_x = cx - row_w // 2
        field_y = self.CARD_TOP + 70
        self.name_input = TextInput(
            pygame.Rect(row_x, field_y, name_w, 54),
            self.theme, self.layout,
            label="PARTICIPANT NAME",
            placeholder="Name for this session",
            initial=prefill_name,
            max_len=40,
        )
        self.age_input = TextInput(
            pygame.Rect(row_x + name_w + gap, field_y, age_w, 54),
            self.theme, self.layout,
            label="AGE",
            placeholder="Years",
            initial=prefill_age,
            max_len=4,
        )

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
            pygame.Rect(cx - BUTTON_W // 2, self.CARD_TOP + 152,
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

    def _begin(self) -> None:
        name = self.name_input.value or "NA"
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
        self.engine.begin_session(name, age)

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
        """Re-sync the name + age fields with the current cfg values.
        Called by engine.show_title() so coming BACK to the login
        screen (a session just ended, which clears the participant)
        shows the cleared state instead of the stale text from last
        time."""
        prefill_name = str(self.engine.cfg.get("session.participant") or "")
        if prefill_name in ("None", "NA"):
            prefill_name = ""
        prefill_age = str(self.engine.cfg.get("session.age") or "")
        if prefill_age in ("None", "NA"):
            prefill_age = ""
        self.name_input.text = prefill_name
        self.name_input.focused = False
        self.age_input.text = prefill_age
        self.age_input.focused = False
        self._na_warned = False
        self.begin_note = ""

    def handle_event(self, e: pygame.event.Event) -> None:
        # When the info overlay is open it is modal: any click or Esc
        # closes it, and nothing underneath gets the event. This keeps
        # the protocol card from accidentally starting a session.
        if self._show_info:
            if (e.type == pygame.MOUSEBUTTONDOWN and e.button == 1) or (
                    e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
                self._show_info = False
            return
        # Tab, pressed with neither field focused, is the only way a
        # keyboard-only session (no mouse at all, audit finding #113)
        # can reach the name field: TextInput.handle_event only
        # accepts KEYDOWN while self.focused is already True, and the
        # only way to SET focused=True is a mouse click inside the
        # rect. Claim it here, before dispatch, so the field the Tab
        # was meant for gets it instead of the keystroke being
        # silently dropped.
        tab_pressed = e.type == pygame.KEYDOWN and e.key == pygame.K_TAB
        was_name_focused = self.name_input.focused
        was_age_focused = self.age_input.focused
        if tab_pressed and not (was_name_focused or was_age_focused):
            self.name_input.focused = True
            return
        # Text inputs first so a click in either field claims focus
        # before any button hit-test runs underneath. Order matters
        # only in that whichever input handles the event first will
        # also be the one to GET focus; we dispatch to both so a
        # second click outside the field can still defocus it.
        self.name_input.handle_event(e)
        self.age_input.handle_event(e)
        self.start_btn.handle_event(e)
        # Tab cycles name -> age -> (defocused, ready for Enter).
        # TextInput's own Tab handling above already defocused
        # whichever field had it; pick up the baton and focus the
        # next one in the row.
        if tab_pressed and was_name_focused and not self.age_input.focused:
            self.age_input.focused = True
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
        self.name_input.draw(surf)
        self.age_input.draw(surf)
        self.start_btn.draw(surf)
        if self.begin_note:
            # The blank-name warning, directly under the card so it
            # reads as part of the log-in flow.
            draw_text(surf, self.begin_note,
                      (cx, self.card_rect.bottom + 16),
                      self.theme, self.layout, pt=FONT_SMALL + 1,
                      centre=True, colour=self.theme.warning)

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
         "Tap the beats inside spoken words. Builds the sound "
         "awareness reading rests on."),
        ("mirror", "Mirror",
         "Same finger, both hands, pressed as one. Practises moving "
         "the hands together."),
        ("force_pilot", "Force Pilot",
         "Steer a craft with gentle finger pressure. Trains smooth "
         "force control."),
        ("lighthouse", "Lighthouse",
         "Hold a soft press dead steady, even in the dark. Trains a "
         "steady touch by feel."),
        ("buzz_hunt", "Buzz Hunt",
         "Feel which finger buzzed and press it. Measures and trains "
         "the sense of touch."),
    ]
    # Every stage of these three needs a real analogue signal (a
    # continuous force trace or the vibration motors themselves) --
    # there is no keyboard-equivalent play for any of them, by design
    # (see each mode's docstring). On a keyboard-only source, picking
    # one used to run setup and the GET READY countdown all the way to
    # the mode's own first-tick refusal, leaving an abandoned session
    # folder behind with zero trial rows and no warning before the
    # click (audit finding #111). Badged on the card instead.
    NEEDS_HARDWARE = {"force_pilot", "lighthouse", "buzz_hunt"}
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
        # Warm lantern gold, kept gentle on purpose: the mode itself
        # is calm and low-force, so its accent must not shout.
        "lighthouse": (214, 158, 46),
        # Orange for the buzz: warm and tactile, and the only strong
        # orange on the grid so the tenth card reads distinct.
        "buzz_hunt": (249, 115, 22),
    }

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.buttons: list[Button] = []
        cx = engine.layout.width // 2
        # A two-column grid, filled left to right so the reading order
        # matches the MODES order. Sized for TEN cards (five rows):
        # rows end at y = 673, clear of the back button at 710. Card
        # height 88 gives the two-line descriptions (title + what you
        # do + what it trains) room without shrinking the title.
        card_w = 590
        card_h = 88
        gap = 12
        for i, (key, _title, _desc) in enumerate(self.MODES):
            col = i % 2
            row = i // 2
            x0 = cx - card_w - gap // 2 + col * (card_w + gap)
            y = 185 + row * (card_h + gap)
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
        self.back_btn = Button(
            pygame.Rect(40, engine.layout.height - 90, 180, BUTTON_H - 10),
            "End session", engine.request_end_session,
            self.theme, self.layout,
        )

    def _second_board_missing(self) -> bool:
        """True when a hardware source cannot serve both hands (one
        board attached). Mirror is bilateral-only, and with one board
        the left lanes can never fire from the sensors: every trial
        missed on the left and the block recorded as total bimanual
        failure of the patient. Keyboard sources play mirror fine
        (both hands live on the keys)."""
        src = self.engine.source
        if not getattr(src, "provides_samples", True):
            return False
        avail = getattr(src, "hand_modes_available", None)
        return isinstance(avail, set) and "both" not in avail

    def _pick(self, mode_key: str) -> None:
        self.engine.cfg.data.setdefault("game", {})["mode"] = mode_key
        # Mirror mode is bilateral-only, so skip the hand-pick step
        # and go straight into the block. Setting hand_mode here
        # means the gameplay screen builds with 8 lane tiles ready
        # before begin_mirror_block fires.
        if mode_key == "mirror" and self._second_board_missing():
            # Refuse before anything is touched: the card wears a
            # NEEDS SECOND BOARD badge saying why.
            return
        if mode_key == "mirror":
            self.engine.cfg.data.setdefault(
                "bilateral", {})["hand"] = "both"
            self.engine.hand_mode = "both"
            self.engine.session.hand = "both"
            self.engine._build_detectors()
            for key in ("gameplay", "rhythm"):
                sc = self.engine._screens.get(key)
                if sc and hasattr(sc, "rebuild_lanes"):
                    sc.rebuild_lanes()
            # Same session gate every other game gets via the setup
            # screen. Mirror skips the hand-pick step, so without this
            # call it was the ONE start path that never ran quick
            # calibration: a session whose first game was Mirror ran
            # both hands on config defaults or the previous session's
            # saved thresholds, which directly bias the per-hand
            # latencies the mode measures.
            if self.engine.maybe_start_quick_calibration(
                    self.engine.begin_mirror_block):
                return
            self.engine.begin_mirror_block()
            return
        self.engine.show_setup()

    # Number-key shortcuts for the ten cards, 1-9 then 0 for the
    # tenth, matching reading order (audit finding #113: mode select
    # was mouse-click only, so a keyboard-only session could not get
    # past this screen at all).
    _DIGIT_KEYS = (
        pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4, pygame.K_5,
        pygame.K_6, pygame.K_7, pygame.K_8, pygame.K_9, pygame.K_0,
    )

    def handle_event(self, e: pygame.event.Event) -> None:
        for b in self.buttons + [self.back_btn]:
            b.handle_event(e)
        if e.type == pygame.KEYDOWN and e.key in self._DIGIT_KEYS:
            idx = self._DIGIT_KEYS.index(e.key)
            if idx < len(self.MODES):
                self._pick(self.MODES[idx][0])

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
        elif kind == "lighthouse":
            # A lantern: glass box with a teardrop flame inside.
            box = pygame.Rect(0, 0, size * 2 // 3, size * 3 // 4)
            box.center = (cx, cy + size // 12)
            pygame.draw.rect(surf, colour, box, 2, border_radius=4)
            pygame.draw.line(surf, colour,
                             (box.left + 4, box.top - size // 6),
                             (box.right - 4, box.top - size // 6), 2)
            pygame.draw.line(surf, colour, (cx, box.top - size // 6),
                             (cx, box.top), 2)
            flame = [(cx, box.centery - size // 4),
                     (cx + size // 8, box.centery + size // 12),
                     (cx, box.centery + size // 5),
                     (cx - size // 8, box.centery + size // 12)]
            pygame.draw.polygon(surf, colour, flame)
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

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        _draw_header(surf, "Pick a game",
                     "Every game comes back here when it ends.",
                     self.theme, self.layout)
        # Only relevant with no live sensor source: a serial device
        # gives every mode real input, so there is nothing to warn
        # about. On a keyboard-only fallback, Force Pilot / Lighthouse
        # / Buzz Hunt cannot be played at all (finding #111).
        src = getattr(self.engine, "source", None)
        no_hardware = not getattr(src, "provides_samples", True)
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
        self.back_btn.draw(surf)


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

    def _second_board_missing(self) -> bool:
        """Same rule as the mode-select mirror card: a hardware source
        that cannot serve both hands (one board) must not start a
        bilateral block, or the missing hand's lanes read constant
        zeros and every one of its trials records as an honest-looking
        patient miss."""
        src = self.engine.source
        if not getattr(src, "provides_samples", True):
            return False
        avail = getattr(src, "hand_modes_available", None)
        return isinstance(avail, set) and "both" not in avail

    def _pick(self, hand: str) -> None:
        # Update hand mode + rebuild detectors / lane strips for the new
        # layout, then start the block in whichever mode the user picked.
        # Participant name was already pushed into session/config by the
        # title screen so we don't touch it here.
        if hand == "both" and self._second_board_missing():
            # Refused up front; the card wears a NEEDS SECOND BOARD
            # badge saying why.
            return
        self.engine.cfg.data.setdefault("bilateral", {})["hand"] = hand
        self.engine.hand_mode = hand
        self.engine.session.hand = hand
        self.engine._build_detectors()
        for key in ("gameplay", "rhythm"):
            sc = self.engine._screens.get(key)
            if sc and hasattr(sc, "rebuild_lanes"):
                sc.rebuild_lanes()
        mode = self.engine.cfg.get("game.mode", "adaptive")
        if mode == "classic":
            # Persist the slider's chosen pace into the config so the
            # ClassicMode constructor reads it back when the block starts.
            self.engine.cfg.data.setdefault("game", {})[
                "trigger_interval_s"] = self.pace_slider.value
        starters = {
            "classic": self.engine.begin_classic_block,
            "rhythm": self.engine.show_rhythm_setup,
            "reaction": self.engine.begin_reaction_block,
            "pattern": self.engine.begin_pattern_block,
            "chords": self.engine.begin_chords_block,
            "syllables": self.engine.begin_syllables_block,
            "force_pilot": self.engine.begin_force_pilot_block,
            "lighthouse": self.engine.begin_lighthouse_block,
            "buzz_hunt": self.engine.begin_buzz_hunt_block,
        }
        start = starters.get(mode, self.engine.begin_adaptive_block)
        # Calibration is a session event: the first game that needs a
        # hand this session gets the quick flow first, which teaches
        # the light press and measures it in one go, with the block
        # start handed over as the continuation. Every later game in
        # the session (and any keyboard session) sails straight
        # through: the gate returns False without showing anything.
        if self.engine.maybe_start_quick_calibration(start):
            return
        start()

    # Keyboard shortcut for each hand card, first letter of its key
    # (audit finding #113: this screen was mouse-click only, so a
    # keyboard-only session could not get past hand-pick at all).
    _HAND_KEYS = {
        pygame.K_l: "left", pygame.K_r: "right", pygame.K_b: "both",
    }

    def handle_event(self, e: pygame.event.Event) -> None:
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
        self.back_btn.draw(surf)


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
        # Cached translucent overlay for the reaction hold state (a
        # full-width band is an allocation too big for the draw loop).
        self._hold_dim: pygame.Surface | None = None
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
                   popup_text: str | None = None) -> None:
        for ls in self.lanes:
            if ls.lane == lane:
                ls.flash(colour, duration_s, now)
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
                      text: str) -> None:
        if not text:
            return
        # Points appended to the label make the feedback feel chunky and
        # game-like rather than clinical only.
        x = lane.rect.centerx
        # Above the tile, on the page background. Inside the tile the
        # popup landed on the outcome flash in its own colour (green
        # text on a green tile) and vanished.
        y = lane.rect.top - 28
        self._popups.append(FloatingText(text, (x, y), colour, font_pt=42))

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
        cx = self.layout.width // 2
        self._popups.append(FloatingText(
            text, (cx, self.layout.height - 88), self.theme.success,
            font_pt=FONT_TITLE - 4,
            lifetime_s=1.8,
            rise_px=30,
        ))

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

        # Score-pulse trigger: kick the animation any time the engine's
        # score actually changes so the patient sees the number react.
        if self.engine.score != self._last_score_seen:
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
        draw_text(surf, f"{self.engine.score}",
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
        streak = self.engine.hit_streak
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

        # Mode message chip: whatever the mode asked the patient to
        # read right now ("142 ms  NEW BEST", "Too soon", "Level up",
        # "Press any finger when ready"). Rendered as a tinted pill
        # with a short pop-in so the feedback visibly ARRIVES, and the
        # tint carries the meaning (gold best, amber caution, green
        # reward) before the words are read. Lives in the gap between
        # the streak pill and the tallest lane tile. Suppressed while
        # the pattern rest card is up: the card says the same thing
        # with more room.
        block = getattr(self.engine, "current_block", "")
        pattern_resting = (
            block == "pattern" and self.engine.mode is not None
            and getattr(self.engine.mode, "phase", "") == "rest")
        if (self.message and time.perf_counter() < self.message_until
                and not pattern_resting):
            age = time.perf_counter() - self._message_born
            # Reaction's chip IS the mode's feedback (the RT number is
            # the PVT's self-motivating loop), so it renders a step
            # larger and stronger there than the shared default, and
            # sits a little higher so the bigger chip still clears the
            # tallest lane tile (top = 220).
            base_pt = 34 if block == "reaction" else 30
            chip_cy = 188 if block == "reaction" else 201
            chip_alpha = 42 if block == "reaction" else 30
            pt = base_pt
            if age < 0.18:
                pt = int(base_pt * (1.0 + 0.22 * (1.0 - age / 0.18)))
            _chip(surf, self.layout, (cx, chip_cy), self.message,
                  self._message_colour(), bg_alpha=chip_alpha,
                  pad_x=24, pad_y=10, font_pt=pt)

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
        if self.engine.hand_mode == "both" and not in_mirror:
            mid_x = self.layout.width // 2
            pygame.draw.line(surf, self.theme.muted,
                              (mid_x, 215),
                              (mid_x, self.layout.height - 80), 2)

        now = time.perf_counter()
        for ls in self.lanes:
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

        self._draw_ignitions(surf, now)

        # Downward chevron + PRESS label above the target lane so the
        # patient never has to guess which tile to push. The chevron
        # bobs vertically a few pixels per cycle to draw the eye
        # without being distracting. Drawn AFTER the lanes so it
        # always sits on top (no clipping by neighbouring tiles).
        self._draw_target_indicator(surf, now)

        # Floating hit/miss popups
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
        """The wait must feel tense and the stimulus electric. During
        the foreperiod (and a catch wait, which must be identical) the
        whole lane band drops behind a translucent veil, so the arm
        moment reads as the lights coming back on. A slow breathing
        dot row says "hold" without words; the session best sits
        quietly at the foot of the screen so "faster" always has a
        target."""
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
        phase = getattr(m, "_phase", "")
        if phase in ("foreperiod", "catch"):
            top = min(ls.rect.top for ls in self.lanes) - 48
            bottom = max(ls.rect.bottom for ls in self.lanes) + 34
            size = (self.layout.width, bottom - top)
            if self._hold_dim is None or self._hold_dim.get_size() != size:
                self._hold_dim = pygame.Surface(size, pygame.SRCALPHA)
                # Alpha 175: at the old 140 the pastel tiles read
                # almost full-brightness through the wash, so the
                # "lights come back on" moment had nothing to come
                # back FROM (before/after screenshots in the upgrade
                # folder). Still translucent enough that the lane
                # positions stay visible for hand placement.
                self._hold_dim.fill((*self.theme.background, 175))
            surf.blit(self._hold_dim, (0, top))
            # Three dots breathing at 0.55 Hz: calm, deliberate, and
            # visibly not yet the stimulus. Sized up (r=7, wider
            # spacing, higher peak alpha) so the hold signal reads
            # from a metre away over the stronger veil.
            if not (self.message and now < self.message_until):
                pulse = (math.sin(now * (2 * math.pi / 1.8)) + 1) * 0.5
                alpha = int(90 + 130 * pulse)
                r = 7
                dot = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
                pygame.draw.circle(dot, (*self.theme.muted, alpha),
                                   (r, r), r)
                cx = self.layout.width // 2
                for dx in (-34, 0, 34):
                    surf.blit(dot, (cx + dx - r, 201 - r))
        best = None
        if hasattr(m, "session_best_ms"):
            try:
                best = m.session_best_ms()
            except Exception:
                best = None
        # isinstance rather than truthiness: a test double's mode
        # returns a MagicMock here, which must not reach the format.
        # bg_alpha 32 (was 24): the target the patient is chasing was
        # nearly invisible against the light background.
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
        # Warm-up / wind-down banner: while the single-finger probes
        # run, a persistent counter pill says so, bottom-centre (the
        # same spot reaction parks its SESSION BEST chip). Without it
        # the probes look like the game itself, and a player who
        # leaves early reports that chords mode only ever asks for
        # one finger at a time.
        ws_fn = getattr(m, "warmup_state", None)
        if callable(ws_fn):
            try:
                ws = ws_fn()
            except Exception:
                ws = None
            if ws:
                word = "WARM-UP" if ws[0] == "warmup" else "WIND-DOWN"
                label = (f"{word}  SINGLE FINGERS  "
                         f"{min(ws[1] + 1, ws[2])} OF {ws[2]}")
                _chip(surf, self.layout,
                      (self.layout.width // 2, self.layout.height - 42),
                      label, accent, bg_alpha=36, pad_x=16, pad_y=6,
                      font_pt=FONT_SMALL + 2)
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
        if seg.kind == "warmup":
            label = "WARM-UP"
        else:
            label = f"TAKE {seg.label} OF {m.n_takes}"
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
        # In-take progress under the chip.
        total = max(1, len(getattr(seg, "fingers", []) or []))
        done = min(total, int(getattr(m, "_trial_in_seg", 0) or 0))
        track = pygame.Surface((chip_w, 4), pygame.SRCALPHA)
        pygame.draw.rect(track, (*self.theme.muted, 80),
                         track.get_rect(), border_radius=2)
        surf.blit(track, (chip_rect.x, chip_rect.bottom + 6))
        fill_w = int(chip_w * done / total)
        if fill_w > 0:
            fill = pygame.Surface((fill_w, 4), pygame.SRCALPHA)
            pygame.draw.rect(fill, (*accent, 230), fill.get_rect(),
                             border_radius=2)
            surf.blit(fill, (chip_rect.x, chip_rect.bottom + 6))

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
        card_w, card_h = 480, 260
        card_rect = pygame.Rect(0, 0, card_w, card_h)
        card_rect.center = (cx, cy)
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
        forced = getattr(m, "_rest_kind", "between") == "forced"
        if forced:
            title = "Take a breather"
        elif seg.kind == "warmup":
            title = "Warm-up done"
        else:
            title = f"Take {seg.label} done"
        draw_text(surf, title, (cx, card_rect.y + 52), self.theme,
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
                      (cx, card_rect.y + 168), self.theme, self.layout,
                      pt=FONT_H2, centre=True, colour=self.theme.muted)
        else:
            pulse = (math.sin(now * (2 * math.pi / 2.0)) + 1) * 0.5
            font = self.layout.font(FONT_H2)
            t = font.render("Press any finger when ready", True,
                            self.theme.foreground)
            t.set_alpha(int(150 + 105 * pulse))
            surf.blit(t, t.get_rect(center=(cx, card_rect.y + 168)))
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
                centre = (x0 + i * gap, card_rect.y + 218)
                if i < done_takes:
                    pygame.draw.circle(surf, accent, centre, 6)
                else:
                    pygame.draw.circle(surf, self.theme.muted, centre,
                                       6, 2)

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
        self._popups.append(FloatingText(
            text, (cx, 250), self.theme.success,
            font_pt=FONT_TITLE - 4,
            lifetime_s=1.8,
            rise_px=30,
        ))

    def flash_lane(self, lane: int, colour, duration_s: float, now: float) -> None:
        for ls in self.lanes:
            if ls.lane == lane:
                ls.flash(colour, duration_s, now)
                if self.message:
                    # Above the strike ring, not on it: at the lane
                    # top the judgement text sat right across the ring
                    # the patient is aiming the next note at.
                    strike_y = self.layout.height - 290
                    self._popups.append(FloatingText(
                        self.message, (ls.rect.centerx, strike_y - 64),
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
            song_t = self.engine.mode.song_time
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
                    song_t = self.engine.mode.song_time
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

        # Skipped under either exit guard, same as GameplayScreen: the
        # guard is the frame's one message.
        if self.engine.paused and not self.engine.exit_overlay_active:
            overlay = pygame.Surface(
                (self.layout.width, self.layout.height), pygame.SRCALPHA,
            )
            overlay.fill((0, 0, 0, 160))
            surf.blit(overlay, (0, 0))
            draw_text(surf, "PAUSED",
                      (cx, self.layout.height // 2 - 30),
                      self.theme, self.layout, pt=FONT_TITLE + 20,
                      centre=True, colour=self.theme.warning)


class RhythmSetupScreen(Screen):
    """Two-column song-select style: track list on the left, song details
    + difficulty + preview/start on the right. Mirrors what music rhythm
    games like osu! and Guitar Hero do, which felt the most readable when
    I tried them. No BPM clutter, the track's own tempo is used."""

    DIFFICULTIES = ("easy", "medium", "hard")
    PREVIEW_S = 8.0

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self._tracks: list = []
        self._track_rects: list[tuple[pygame.Rect, object]] = []
        self._selected_track: str | None = None
        self._selected_difficulty = engine.cfg.get("rhythm.difficulty", "medium")
        self._previewing: bool = False
        self._preview_stop_at: float = 0.0
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

    def _toggle_preview(self) -> None:
        # Already playing? Cut it short.
        if self._previewing:
            self._stop_preview()
            return
        if not self._selected_track or self.engine.audio is None:
            return
        if self.engine.audio.play_song(self._selected_track):
            self._previewing = True
            self._preview_stop_at = time.perf_counter() + self.PREVIEW_S

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
        # Auto-stop the preview after PREVIEW_S seconds.
        if self._previewing and time.perf_counter() >= self._preview_stop_at:
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
                    new_selection = str(path) if path is not None else None
                    if new_selection != self._selected_track:
                        self._stop_preview()
                    self._selected_track = new_selection
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
                     "Choose a track and difficulty, then press START.",
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
        btn_w = 210
        gap = 16
        total_w = btn_w * 4 + gap * 3
        x = cx - total_w // 2
        # Buttons pushed down from y=640 -> y=696 to clear the per-lane
        # histograms that now sit between the stat cards and the
        # saved-to footer. Bottom margin ~46 px at h=58 keeps them
        # from feeling glued to the screen edge.
        y = 696
        h = BUTTON_H + 4
        self.retry_btn = Button(
            pygame.Rect(x, y, btn_w, h),
            "Retry",
            engine.retry_last_block,
            self.theme, self.layout, font_pt=FONT_H2,
            primary=True,
        )
        x += btn_w + gap
        self.again_btn = Button(
            pygame.Rect(x, y, btn_w, h),
            "Play again", engine.show_mode_select,
            self.theme, self.layout, font_pt=FONT_H2,
        )
        x += btn_w + gap
        self.folder_btn = Button(
            pygame.Rect(x, y, btn_w, h),
            "Data folder", engine.open_last_session_folder,
            self.theme, self.layout, font_pt=FONT_H2,
        )
        x += btn_w + gap
        self.title_btn = Button(
            pygame.Rect(x, y, btn_w, h),
            "End session", engine.request_end_session,
            self.theme, self.layout, font_pt=FONT_H2,
        )

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

        # When the screen was last entered, for the one-shot entry
        # animation (ring sweep + stat count-up). Zero means "never
        # notified", which draws the finished state so a bare draw()
        # in a test never renders a half-swept ring.
        self._shown_t = 0.0

    def on_show(self) -> None:
        """Engine hook: a block just landed here, restart the entry
        animation."""
        self._shown_t = time.perf_counter()

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
        self.retry_btn.handle_event(e)
        self.again_btn.handle_event(e)
        self.folder_btn.handle_event(e)
        self.title_btn.handle_event(e)
        # Enter confirms the primary (Retry) action, same convention as
        # the title screen's START shortcut (audit finding #113: this
        # screen was mouse-click only, so a keyboard-only session could
        # not continue past its own results screen).
        if e.type == pygame.KEYDOWN and e.key == pygame.K_RETURN:
            self.engine.retry_last_block()

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
            return "C", "Keep practising"
        if rate >= 0.30:
            return "D", "Tough one - try again"
        return "E", "Reset and have another go"

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

    def _lighthouse_summary(self) -> dict | None:
        """The lighthouse section of the block summary, or None for
        every other mode. Same read path as _force_pilot_summary:
        session.block_summary first, live mode stats as fallback."""
        if str(getattr(self.engine, "current_block", "")) != "lighthouse":
            return None
        summary = getattr(getattr(self.engine, "session", None),
                          "block_summary", None)
        if isinstance(summary, dict):
            lh = summary.get("lighthouse")
            if isinstance(lh, dict):
                return lh
        stats_fn = getattr(getattr(self.engine, "mode", None),
                           "block_stats", None)
        if callable(stats_fn):
            try:
                lh = stats_fn()
                return lh if isinstance(lh, dict) else None
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
                         value_colour: tuple[int, int, int]) -> None:
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
        # Small label up top.
        draw_text(surf, label, (rect.centerx, rect.y + 22),
                  self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)
        # Big value, bold so it pops as the stat's headline number.
        # Shrink the font until it fits the card so a value with a unit
        # (e.g. "262 ms") never spills past the card edge the way a bare
        # number like "1840" does.
        max_w = rect.w - 24
        pt = int(FONT_TITLE * self.layout.font_scale)
        val_font = make_font(pt, bold=True)
        val_surf = val_font.render(value, True, value_colour)
        while val_surf.get_width() > max_w and pt > 12:
            pt -= 2
            val_font = make_font(pt, bold=True)
            val_surf = val_font.render(value, True, value_colour)
        surf.blit(val_surf,
                   val_surf.get_rect(center=(rect.centerx, rect.y + 78)))

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

        # Top banner. Bold via the shared SysFont call so the header
        # matches the rest of the menu screens. The accent bar and the
        # block pill wear the finished mode's accent so the results
        # carry the same identity the patient just played under.
        # str() because a test double can leave current_block as a
        # non-string; an unknown block just falls back to the theme
        # accent.
        block_name = str(self.engine.current_block)
        mode_accent = ModeSelectScreen.MODE_ACCENTS.get(
            block_name.lower(), self.theme.accent)
        title_font = make_font(int((FONT_H1 + 6) * self.layout.font_scale),
            bold=True,
        )
        title_surf = title_font.render(self.RESULTS_TITLE, True,
                                        self.theme.foreground)
        title_rect = title_surf.get_rect(center=(cx, 80))
        surf.blit(title_surf, title_rect)
        # Accent bar under the title (matches _draw_header).
        bar_w = max(72, title_rect.w // 3)
        bar_rect = pygame.Rect(0, 0, bar_w, 4)
        bar_rect.center = (cx, title_rect.bottom + 12)
        pygame.draw.rect(surf, mode_accent, bar_rect, border_radius=2)
        # Mode pill top-right, same furniture as the in-play screens.
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
        pygame.draw.rect(surf, mode_accent, pill_rect,
                         border_radius=pill_rect.height // 2)
        surf.blit(mt_label, mt_label.get_rect(center=pill_rect.center))

        # Grade letter inside a ring. Big celebratory moment, the part
        # the patient and therapist see first. The ring sweeps closed
        # over the entry animation, then the blurb sits directly under
        # it so the praise reads as part of the grade (it used to
        # collide with the glow from above).
        grade_centre = (cx, 240)
        ring_r = 90
        # Soft glow behind the ring, fading in with the sweep.
        glow = pygame.Surface((ring_r * 2 + 40, ring_r * 2 + 40),
                               pygame.SRCALPHA)
        for i, alpha in ((20, 30), (12, 50), (4, 80)):
            pygame.draw.circle(glow, (*grade_colour,
                                      int(alpha * entry)),
                                (ring_r + 20, ring_r + 20), ring_r + i)
        surf.blit(glow, (grade_centre[0] - ring_r - 20,
                          grade_centre[1] - ring_r - 20))
        if entry >= 1.0:
            pygame.draw.circle(surf, grade_colour, grade_centre,
                               ring_r, 6)
        else:
            arc_rect = pygame.Rect(0, 0, ring_r * 2, ring_r * 2)
            arc_rect.center = grade_centre
            start = math.pi / 2
            pygame.draw.arc(surf, grade_colour, arc_rect,
                            start, start + entry * 2 * math.pi, 6)
        # Letter itself, oversized + bold so the visual weight matches
        # the heavy ring around it, fading in with the sweep.
        gfont = make_font(int(120 * self.layout.font_scale),
            bold=True,
        )
        gtext = gfont.render(grade, True, grade_colour)
        if entry < 1.0:
            gtext.set_alpha(int(255 * entry))
        surf.blit(gtext, gtext.get_rect(center=grade_centre))
        draw_text(surf, blurb,
                  (cx, grade_centre[1] + ring_r + 24),
                  self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)

        # Stat cards row - score, hits, hit rate, misses, plus the two
        # reaction-time cards the patient sees as a game-style headline
        # (average + personal best for the round). Six slimmer cards
        # (180 px) keep the row inside the 1280-wide logical surface.
        is_rhythm = (self.engine.current_block == "rhythm")
        fp = self._force_pilot_summary()
        lh = self._lighthouse_summary()
        bh = self._buzz_hunt_summary()
        rx = self._reaction_summary()
        pat = self._pattern_summary()
        ch = self._chords_summary()
        sy = self._syllables_summary()
        mir = self._mirror_summary()
        adp = self._adaptive_summary()
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
                (f"MEAN ERROR{level_note}",
                 (f"{mae:.1f}%" if mae is not None else "n/a"),
                 self.theme.foreground),
                ("STALLS", f"{overall.get('stalls', 0)}",
                 self.theme.error),
                ("BEST SECTION", str(best_sec), self.theme.success),
            ]
        elif lh is not None:
            # Lighthouse has no reaction times, so the cards say what
            # a hold block actually measured: lit steadiness, drift in
            # the dark, the lit-dark delta headline and the echo
            # reproduction error.
            overall = lh.get("overall") or {}
            echo_all = (lh.get("echo") or {}).get("overall") or {}
            cov = overall.get("lit_cov")
            drift = overall.get("dark_drift_pct")
            delta = overall.get("lit_dark_delta_pct")
            echo_err = echo_all.get("abs_err_pct")
            # Same rule as Force Pilot's pooled cards: when the level
            # ladder moved during the block, the pooled lit-dark delta
            # compares holds measured under different dark exposure
            # (25% vs 45% dark), so the card says so instead of
            # reading as one clean measurement.
            lh_trace = (lh.get("levels") or {}).get("trace") or []
            lh_note = (" (mixed levels)"
                       if len(set(lh_trace)) > 1 else "")
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("HOLDS",
                 f"{int(round((lh.get('holds') or 0) * entry))}",
                 self.theme.success),
                # cov is the coefficient of variation: HIGHER means
                # LESS steady. "LIT STEADINESS" alone reads as
                # higher-is-better, the opposite of what the number
                # means (audit finding #107); the per-lane chart below
                # already carries the "(CoV)" qualifier this card was
                # missing.
                ("LIT VARIABILITY (CoV)",
                 (f"{cov * 100:.1f}%" if cov is not None else "n/a"),
                 self.theme.foreground),
                ("DARK DRIFT",
                 (f"{drift:.1f}%" if drift is not None else "n/a"),
                 self.theme.foreground),
                (f"LIT VS DARK{lh_note}",
                 (f"{delta:+.1f}%" if delta is not None else "n/a"),
                 self.theme.foreground),
                ("ECHO ERROR",
                 (f"{echo_err:.1f}%" if echo_err is not None else "n/a"),
                 self.theme.success),
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
            cards += self._buzz_hunt_hand_cards(
                "THRESHOLD", bh.get("threshold") or {})
            cards += self._buzz_hunt_hand_cards(
                "GAP", (bh.get("gap") or {}).get("threshold") or {})
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
                ("MISSES", f"{int(round(self.engine.misses * entry))}",
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
                ("MISSES", f"{int(round(self.engine.misses * entry))}",
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
            level = sy.get("level")
            paced_level = level in (3, 4)
            acc = sy.get("accuracy")
            acc_str = f"{acc * 100:.0f}%" if acc is not None else "n/a"
            band = sy.get("band_final") or "n/a"
            if paced_level:
                amean = sy.get("asyn_mean_ms")
                asd = sy.get("asyn_sd_ms")
                offset_str = (f"{abs(amean):.0f} ms"
                              if amean is not None else "n/a")
                sd_str = f"{asd:.0f} ms" if asd is not None else "n/a"
                fifth = ("AVG OFFSET", offset_str, self.theme.foreground)
                sixth = ("OFFSET SD", sd_str, self.theme.success)
            else:
                fifth = ("AVG RT", avg_str, self.theme.foreground)
                sixth = ("BEST RT", best_str, self.theme.success)
            cards = [
                ("SCORE", f"{int(round(self.engine.score * entry))}",
                 self.theme.accent),
                ("WORDS CORRECT", acc_str, self.theme.success),
                ("BAND", str(band), self.theme.foreground),
                ("MISSES", f"{int(round(self.engine.misses * entry))}",
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
                ("MISSES", f"{int(round(self.engine.misses * entry))}",
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
                ("MISSES", f"{int(round(self.engine.misses * entry))}",
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
                ("MISSES", f"{int(round(self.engine.misses * entry))}",
                 self.theme.error),
                (avg_label, avg_str, self.theme.foreground),
                (best_label, best_str, self.theme.success),
            ]
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
                "MEAN TRACKING ERROR PER FINGER",
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
        elif lh is not None:
            # Lighthouse charts: lit steadiness per finger and the
            # lit-dark delta per finger, the mode's headline metric.
            # A negative delta (steadier in the dark) draws as zero;
            # the exact value lives in metadata.json.
            per_lane = lh.get("per_lane") or {}
            covs = [0.0] * n_lanes
            deltas = [0.0] * n_lanes
            for key, stats in per_lane.items():
                try:
                    lane = int(key)
                except (TypeError, ValueError):
                    continue
                if 0 <= lane < n_lanes and isinstance(stats, dict):
                    cov_val = stats.get("lit_cov")
                    covs[lane] = (float(cov_val) * 100.0
                                  if cov_val is not None else 0.0)
                    delta_val = stats.get("delta_pct")
                    deltas[lane] = max(0.0, float(delta_val or 0.0))
            self._draw_per_lane_chart(
                surf,
                pygame.Rect(left_x, chart_y, chart_w, chart_h),
                "LIT STEADINESS PER FINGER (CoV)",
                covs, unit="%", high_is_bad=True,
            )
            self._draw_per_lane_chart(
                surf,
                pygame.Rect(left_x + chart_w + chart_gap, chart_y,
                             chart_w, chart_h),
                "LIT-DARK ERROR DELTA PER FINGER",
                deltas, unit="% of max", high_is_bad=True,
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
                "MISSES + WRONG PRESSES PER FINGER",
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
                "MISSES + WRONG PRESSES PER FINGER",
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
            mf_text = ("Miss-trial force: needs the force sensors "
                       "(not available in keyboard mode)")
        elif mf_count > 0:
            mf_text = (
                f"Miss-trial force: {mf_total:.0f} sensor units over "
                f"{mf_count} missed trials (avg {mf_total / mf_count:.0f} "
                f"per miss, all fingers, first {mf_window} ms)")
        else:
            mf_text = "Miss-trial force: no missed trials this round"
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

        self.retry_btn.draw(surf)
        self.again_btn.draw(surf)
        self.folder_btn.draw(surf)
        self.title_btn.draw(surf)

        # Sensory-cues menu. handle_event has routed clicks to this
        # menu since the pill was added, but the pill itself was never
        # drawn, leaving an invisible click target floating over the
        # screen. Pill first, overlay last so the open rows sit on top
        # of the buttons they cover.
        self._cue_menu.draw_closed(surf)
        self._cue_menu.draw_overlay(surf)


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
        from .widgets import Dropdown
        self._port_dropdowns: dict[str, Dropdown] = {}
        # Test Mode toggle. Rect is sized + positioned every frame in
        # `draw` (depends on the rendered label width), and the click
        # handler in handle_event consults this rect to flip the cfg
        # flag. Storing it as an instance var keeps the click test
        # consistent with what was drawn last frame.
        self._test_mode_rect: pygame.Rect = pygame.Rect(0, 0, 0, 0)
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
                           self.layout.width - self.BAND_X - self.DATA_X,
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
        for i, (key, label, cfgkey, dflt) in enumerate(specs):
            rect = pygame.Rect(x0 + i * (sw + gap), track_y, sw,
                               self.SLIDER_H)
            self._vol_sliders[key] = Slider(
                rect, self.theme, self.layout,
                min_value=0.0, max_value=1.0,
                initial=float(self.engine.cfg.get(cfgkey, dflt)),
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
                    "lane, or plug an Arduino in and hit Refresh.")
        elif state_text == "DISCONNECTED":
            sub = ("Source not connected. Plug the Arduino in and "
                    "click Refresh.")
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
        cap_y = self._ports_row_y(1)
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
        draw_text(surf, "one folder per day, newest last",
                  (cap_x, cap_y + 44),
                  self.theme, self.layout, pt=FONT_SMALL,
                  centre=False, colour=self.theme.muted)
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
        self._cue_menu.draw_overlay(surf)
        # Footer hint.
        draw_text(surf, "Esc returns to the title screen",
                  (self.layout.width // 2, self.layout.height - 30),
                  self.theme, self.layout, pt=FONT_SMALL + 2,
                  centre=True, colour=self.theme.muted)
