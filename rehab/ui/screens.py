"""Screen classes. Title, mode select, setup, gameplay, rhythm, results.

I keep the same Screen base + subclass pattern Satoru used, but the
layouts are heavier on the fonts and use the Card / Button widgets so it
feels like a finished app instead of a debug dashboard.
"""
from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import pygame


log = logging.getLogger(__name__)

from .theme import Theme
from .widgets import (
    Button, Card, FloatingText, LaneStrip, Layout, Slider, TextInput,
    FONT_TITLE, FONT_H1, FONT_H2, FONT_BODY, FONT_SMALL,
    BUTTON_H, BUTTON_W, PADDING, draw_text,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


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


def _draw_header(surf: pygame.Surface, title: str, subtitle: str,
                 theme: Theme, layout: Layout) -> None:
    """Reused at the top of every menu screen so they all match.

    Title is rendered bold via the same Helvetica Neue Bold cut the
    title-screen wordmark uses, plus a short accent-coloured underline
    bar so every menu shares the visual language.
    """
    cx = layout.width // 2
    title_pt = int((FONT_H1 + 6) * layout.font_scale)
    title_font = pygame.font.SysFont(
        "Helvetica Neue,Helvetica,Arial,DejaVu Sans",
        title_pt, bold=True,
    )
    title_surf = title_font.render(title, True, theme.accent)
    title_rect = title_surf.get_rect(center=(cx, 80))
    surf.blit(title_surf, title_rect)
    # Thin accent bar centred under the title. Width matches the
    # rendered text so different-length titles still feel balanced.
    bar_w = max(60, title_rect.w // 3)
    bar_rect = pygame.Rect(0, 0, bar_w, 3)
    bar_rect.center = (cx, title_rect.bottom + 10)
    pygame.draw.rect(surf, theme.accent, bar_rect, border_radius=2)
    if subtitle:
        draw_text(surf, subtitle, (cx, title_rect.bottom + 32),
                  theme, layout, pt=FONT_BODY, centre=True,
                  colour=theme.muted)


class TitleScreen(Screen):
    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        cx = engine.layout.width // 2

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
        # Side-by-side row: wide name field + compact age field. The
        # age input is a research-metadata field (demographic cohort
        # matters for stroke rehab outcomes), so it's smaller and
        # paired with the name rather than getting its own row.
        name_w = 400
        age_w = 160
        gap = 20
        row_w = name_w + gap + age_w
        row_x = cx - row_w // 2
        self.name_input = TextInput(
            pygame.Rect(row_x, 380, name_w, 54),
            self.theme, self.layout,
            label="",
            placeholder="Name for this session",
            initial=prefill_name,
            max_len=40,
        )
        self.age_input = TextInput(
            pygame.Rect(row_x + name_w + gap, 380, age_w, 54),
            self.theme, self.layout,
            label="",
            placeholder="Age",
            initial=prefill_age,
            max_len=4,
        )

        # Primary action. Pushes the typed name into the session + config
        # before navigating to mode select. Filled in green (independent
        # of the blue theme accent) so it reads as a "go" action.
        self.start_btn = Button(
            pygame.Rect(cx - BUTTON_W // 2, 470, BUTTON_W, BUTTON_H + 12),
            "START SESSION", self._begin,
            self.theme, self.layout,
            font_pt=FONT_H2,
            colour=(34, 197, 94),     # green
        )
        # Quit + Settings sit as matching compact pills in the bottom
        # corners. Quit (left) is the destructive action so it gets a
        # muted red; Settings (right) uses the theme accent on hover.
        # Same dimensions + edge margins so they line up.
        sw, sh = 150, 44
        self.quit_rect = pygame.Rect(
            28,
            engine.layout.height - sh - 28,
            sw, sh,
        )
        self.settings_rect = pygame.Rect(
            engine.layout.width - sw - 28,
            engine.layout.height - sh - 28,
            sw, sh,
        )

    def _begin(self) -> None:
        name = self.name_input.value or "NA"
        # Age is optional; an empty string is its own valid value
        # meaning "not provided" (patient declined, or the therapist
        # didn't type it). Stored as a raw string so the CSV column
        # round-trips whatever was typed instead of coercing to int
        # and rejecting unusual inputs like "65y".
        age = self.age_input.value or ""
        self.engine.cfg.data.setdefault("session", {})["participant"] = name
        self.engine.cfg.data.setdefault("session", {})["age"] = age
        self.engine.session.participant = name
        self.engine.session.age = age
        self.engine.show_mode_select()

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
        Called by engine.show_title() so coming BACK to the title
        (e.g. via Esc on mode select, which clears the participant)
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

    def handle_event(self, e: pygame.event.Event) -> None:
        # Text inputs first so a click in either field claims focus
        # before any button hit-test runs underneath. Order matters
        # only in that whichever input handles the event first will
        # also be the one to GET focus; we dispatch to both so a
        # second click outside the field can still defocus it.
        self.name_input.handle_event(e)
        self.age_input.handle_event(e)
        self.start_btn.handle_event(e)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            if self.quit_rect.collidepoint(e.pos):
                self.engine.request_quit()
            elif self.settings_rect.collidepoint(e.pos):
                self.engine.show_diagnostics()
        # Enter key on either focused field acts as a shortcut for
        # Start so a therapist on a keyboard doesn't have to grab the
        # mouse to commit.
        if (e.type == pygame.KEYDOWN
                and e.key == pygame.K_RETURN
                and (self.name_input.focused or self.age_input.focused)):
            self._begin()

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        cx = self.layout.width // 2

        # Finger-sensor device graphic above the title. Four vertical
        # sensor pads with LED-style dots sitting on a curved base
        # plate. Mirrors what the actual hardware looks like, rather
        # than the old abstract concentric rings.
        self._draw_device_icon(surf, cx, 105)

        # Big bold title. Helvetica Neue / Helvetica with bold=True
        # gives a heavy stroke AND keeps the wide proportional letter
        # spacing that condensed display faces (Impact / Arial Black)
        # squashed together until adjacent letters touched. Drop-shadow
        # uses the same font + size so it tracks every letterform.
        title_text = "FINGER REHAB"
        title_pt = int((FONT_TITLE + 14) * self.layout.font_scale)
        title_font = pygame.font.SysFont(
            "Helvetica Neue,Helvetica,Arial,DejaVu Sans",
            title_pt,
            bold=True,
        )
        shadow = title_font.render(title_text, True,
                                    (*self.theme.accent, 60))
        shadow.set_alpha(70)
        surf.blit(shadow, shadow.get_rect(center=(cx + 3, 233)))
        main = title_font.render(title_text, True, self.theme.accent)
        surf.blit(main, main.get_rect(center=(cx, 230)))
        # Tagline.
        draw_text(surf, "Multi-modal finger rehabilitation",
                  (cx, 300), self.theme, self.layout,
                  pt=FONT_BODY + 4, centre=True, colour=self.theme.muted)

        # Participant name input. Patient types here once and every
        # game logs to the same name.
        self.name_input.draw(surf)
        self.age_input.draw(surf)

        # Primary Start button - the only obvious thing to do.
        self.start_btn.draw(surf)

        mx, my = pygame.mouse.get_pos()

        # Quit pill, bottom-left. Mirrors the Settings pill on the
        # other corner so the two utility actions live at the same
        # visual height. Uses a muted red because Quit is destructive
        # (closes the app) and the patient / therapist needs that
        # difference at a glance.
        hover_q = self.quit_rect.collidepoint((mx, my))
        # Muted red at rest, brighter red on hover. Pulled from
        # theme.error if it exists, else a fixed (200, 60, 60).
        base_red = getattr(self.theme, "error", (200, 60, 60))
        red_rest = tuple(int(c * 0.85) for c in base_red)
        red_hover = base_red
        bg_q = red_hover if hover_q else red_rest
        fg_q = (255, 255, 255)
        pygame.draw.rect(surf, bg_q, self.quit_rect, border_radius=12)
        # Quit icon: small X made of two diagonal lines so it reads
        # as "close / exit" without needing a Unicode glyph.
        label_text = "Quit"
        label_font = self.layout.font(FONT_BODY)
        label_surf = label_font.render(label_text, True, fg_q)
        icon_r = 8
        gap = 10
        total_w = (icon_r * 2) + gap + label_surf.get_width()
        start_x = self.quit_rect.centerx - total_w // 2
        cy = self.quit_rect.centery
        icon_cx = start_x + icon_r
        # Draw the X. Two thick lines crossing through the icon centre.
        pygame.draw.line(surf, fg_q,
                          (icon_cx - icon_r + 2, cy - icon_r + 2),
                          (icon_cx + icon_r - 2, cy + icon_r - 2), 3)
        pygame.draw.line(surf, fg_q,
                          (icon_cx + icon_r - 2, cy - icon_r + 2),
                          (icon_cx - icon_r + 2, cy + icon_r - 2), 3)
        surf.blit(label_surf, label_surf.get_rect(
            midleft=(icon_cx + icon_r + gap, cy)))

        # Settings pill, bottom-right.
        hover_s = self.settings_rect.collidepoint((mx, my))
        bg_s = (self.theme.accent if hover_s
                else tuple(max(0, c - 30) for c in self.theme.background))
        fg_s = ((255, 255, 255) if hover_s else self.theme.foreground)
        pygame.draw.rect(surf, bg_s, self.settings_rect, border_radius=12)
        s_label = "Settings"
        s_font = self.layout.font(FONT_BODY)
        s_surf = s_font.render(s_label, True, fg_s)
        s_total = (icon_r * 2) + gap + s_surf.get_width()
        s_start = self.settings_rect.centerx - s_total // 2
        s_cy = self.settings_rect.centery
        s_icon_cx = s_start + icon_r
        # Tiny cog: hollow outer ring + filled centre.
        pygame.draw.circle(surf, fg_s, (s_icon_cx, s_cy), icon_r, 2)
        pygame.draw.circle(surf, fg_s, (s_icon_cx, s_cy), 3)
        surf.blit(s_surf, s_surf.get_rect(
            midleft=(s_icon_cx + icon_r + gap, s_cy)))

        # Credit tucked under the Start button.
        draw_text(surf, "Thesis - Basil Toufexis - 19757049",
                  (cx, 570),
                  self.theme, self.layout, pt=FONT_SMALL,
                  centre=True, colour=self.theme.muted)


class ModeSelectScreen(Screen):
    """Pick adaptive / classic / rhythm / mirror. Each option is a
    card with a short description so a clinician can pick without
    prior knowledge."""

    MODES = [
        ("adaptive", "Adaptive",
         "Difficulty adjusts to keep you in the 70-80% hit band."),
        ("classic", "Classic",
         "Fixed pace, set finger pattern. Best for baseline measures."),
        ("rhythm", "Rhythm",
         "Press to the beat of music. Motor-rhythm focused."),
        ("mirror", "Mirror",
         "Press both hands' same finger together. Bilateral training."),
    ]
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
    }

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.buttons: list[Button] = []
        cx = engine.layout.width // 2
        card_w = 720
        # Card height shrunk from 120 to 100 so the four mode cards
        # (with mirror added in Thread C) all fit between the header
        # at y=200 and the Back button at y=height-90. The previous
        # 120 px cards left no room for a fourth row.
        card_h = 100
        gap = 18
        for i, (key, _title, _desc) in enumerate(self.MODES):
            y = 195 + i * (card_h + gap)
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
                pygame.Rect(cx - card_w // 2, y, card_w, card_h),
                "", lambda k=key: self._pick(k),
                self.theme, self.layout,
                font_pt=FONT_H2 + 2,
                colour=pastel,
            ))
        self.back_btn = Button(
            pygame.Rect(40, engine.layout.height - 90, 180, BUTTON_H - 10),
            "Back", engine.show_title,
            self.theme, self.layout,
        )

    def _pick(self, mode_key: str) -> None:
        self.engine.cfg.data.setdefault("game", {})["mode"] = mode_key
        # Mirror mode is bilateral-only, so skip the hand-pick step
        # and go straight into the block. Setting hand_mode here
        # means the gameplay screen builds with 8 lane tiles ready
        # before begin_mirror_block fires.
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
            self.engine.begin_mirror_block()
            return
        self.engine.show_setup()

    def handle_event(self, e: pygame.event.Event) -> None:
        for b in self.buttons + [self.back_btn]:
            b.handle_event(e)

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

    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        _draw_header(surf, "Pick a mode",
                     "Which training pattern for this session?",
                     self.theme, self.layout)
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
            # repeats. Larger than before so it carries the card.
            icon_size = 60
            icon_cx = b.rect.x + 80
            icon_cy = b.rect.centery
            self._draw_mode_icon(surf, key, icon_cx, icon_cy,
                                  icon_size, accent)
            # Title rendered bold via SysFont so it pops as the card's
            # primary affordance. Description follows in regular weight.
            text_x = b.rect.x + 150
            title_pt = int((FONT_H2 + 4) * self.layout.font_scale)
            title_font = pygame.font.SysFont(
                "Helvetica Neue,Helvetica,Arial,DejaVu Sans",
                title_pt, bold=True,
            )
            title_surf = title_font.render(title, True, fg)
            surf.blit(title_surf,
                       title_surf.get_rect(
                           midleft=(text_x, b.rect.centery - 18)))
            draw_text(surf, desc, (text_x, b.rect.centery + 14),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=False, colour=muted_fg)
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

        # Pace slider for classic mode. Pre-fill from the config so a
        # therapist who's tweaked the value in YAML sees their choice.
        # Range 0.4 s to 3.0 s in 0.1 s steps - matches the slowest the
        # adaptive engine can crawl (~3 s per stim) up to a snappy pace
        # for stronger patients.
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

    def _pick(self, hand: str) -> None:
        # Update hand mode + rebuild detectors / lane strips for the new
        # layout, then start the block in whichever mode the user picked.
        # Participant name was already pushed into session/config by the
        # title screen so we don't touch it here.
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
            self.engine.begin_classic_block()
        elif mode == "rhythm":
            self.engine.show_rhythm_setup()
        else:
            self.engine.begin_adaptive_block()

    def handle_event(self, e: pygame.event.Event) -> None:
        # Slider first so a click on the knob isn't intercepted by an
        # adjacent button hit-test. Only let it respond when classic
        # mode is the active pick.
        if self.engine.cfg.get("game.mode") == "classic":
            self.pace_slider.handle_event(e)
        for b in self.buttons + [self.back_btn]:
            b.handle_event(e)

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
        _draw_header(surf, "Choose your hand",
                     f"{greeting}  Which hand will you train this session?",
                     self.theme, self.layout)
        # Classic mode gets a pace slider above the hand buttons so the
        # therapist can tune trigger_interval_s without editing YAML.
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
        self.back_btn.draw(surf)


class GameplayScreen(Screen):
    """Classic + Adaptive view. Big score top-centre, lane strips, hit popups."""

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.message = ""
        self.message_until = 0.0
        self.lanes: list[LaneStrip] = []
        # Floating "+3 Great!" popups go in here and fade themselves out.
        self._popups: list[FloatingText] = []
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
                   duration_s: float, now: float) -> None:
        for ls in self.lanes:
            if ls.lane == lane:
                ls.flash(colour, duration_s, now)
                # Float a quick popup above the lane that just scored.
                self._spawn_popup(ls, colour)

    def _spawn_popup(self, lane: LaneStrip,
                      colour: tuple[int, int, int]) -> None:
        if not self.message:
            return
        # Points appended to the label make the feedback feel chunky and
        # game-like rather than clinical only.
        text = self.message
        x = lane.rect.centerx
        y = lane.rect.top + 30
        self._popups.append(FloatingText(text, (x, y), colour, font_pt=42))

    def set_message(self, text: str, duration_s: float) -> None:
        self.message = text
        self.message_until = time.perf_counter() + duration_s

    def add_encouragement(self, text: str) -> None:
        # Encouragement banners sit centred just below the score HUD so they
        # don't overlap the lane strips. Bigger, brighter, and stick around
        # longer than the per-trial "Great +3" popups.
        cx = self.layout.width // 2
        self._popups.append(FloatingText(
            text, (cx, 200), self.theme.success,
            font_pt=FONT_TITLE - 4,
            lifetime_s=1.8,
            rise_px=40,
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
        # fingers during the GET READY window.
        if (self.engine.mode and hasattr(self.engine.mode, "update")
                and self._countdown_remaining() <= 0):
            self.engine.mode.update(dt)

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
                            done: int, total: int) -> None:
        """Slim full-width bar near the top of the screen that fills as the
        session progresses. Tells the patient how much is left without
        forcing them to count trials."""
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
            fill_surf = pygame.Surface((fill_w, bar_h), pygame.SRCALPHA)
            pygame.draw.rect(fill_surf, (*self.theme.accent, 220),
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

        # Slim progress bar across the top of the screen.
        self._draw_progress_bar(surf, done, total)

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
            if streak >= 10:
                streak_colour = self.theme.success    # bright green
                streak_label = f"x{streak} STREAK"
            elif streak >= 5:
                streak_colour = (255, 196, 0)         # gold
                streak_label = f"x{streak} STREAK"
            else:
                streak_colour = self.theme.foreground
                streak_label = f"x{streak} STREAK"
            in_mirror = (getattr(self.engine, "current_block", None)
                          == "mirror")
            if in_mirror:
                # Render the chip pre-sized so we can right-edge it
                # against the same 28 px margin the mode pill uses.
                # Anchored top-left at vertical level ~38 so it lines
                # up with the mode pill's centre on the other side.
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
        mode_accent = ModeSelectScreen.MODE_ACCENTS.get(
            self.engine.current_block.lower(), self.theme.accent,
        )
        mode_label = self.engine.current_block.title().upper()
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
        if self.engine.hand_mode == "both" and not in_mirror:
            mid_x = self.layout.width // 2
            pygame.draw.line(surf, self.theme.muted,
                              (mid_x, 215),
                              (mid_x, self.layout.height - 80), 2)

        now = time.perf_counter()
        for ls in self.lanes:
            ls.draw(surf, now)

        # Downward chevron + PRESS label above the target lane so the
        # patient never has to guess which tile to push. The chevron
        # bobs vertically a few pixels per cycle to draw the eye
        # without being distracting. Drawn AFTER the lanes so it
        # always sits on top (no clipping by neighbouring tiles).
        self._draw_target_indicator(surf, now)

        # Floating hit/miss popups
        for p in self._popups:
            p.draw(surf, self.layout)

        # No footer hint. Patient is using the Arduino sensor device, so
        # any on-screen mention of keyboard shortcuts would be noise.

        # Pre-start countdown card. Drawn near-last so it sits over the
        # lanes and reads as the clear "wait, don't press yet" focal
        # point. Matches the rhythm-mode countdown styling.
        remaining = self._countdown_remaining()
        if remaining > 0:
            self._draw_countdown_card(surf, remaining)

        if self.engine.paused:
            self._draw_paused_overlay(surf)

    def _draw_countdown_card(self, surf: pygame.Surface,
                             remaining: float) -> None:
        """GET READY card with the seconds remaining, styled to match
        the rhythm-mode countdown so the pre-start moment looks the
        same across every game mode."""
        cx = self.layout.width // 2
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
        pygame.draw.rect(fill_surf, (*self.theme.accent, 110),
                          fill_surf.get_rect(), 3, border_radius=22)
        surf.blit(fill_surf, card_rect.topleft)
        draw_text(surf, "GET READY",
                  (card_rect.centerx, card_rect.y + 56),
                  self.theme, self.layout, pt=FONT_H1,
                  centre=True, colour=self.theme.muted)
        draw_text(surf, f"{remaining:.1f}",
                  (card_rect.centerx, card_rect.y + 156),
                  self.theme, self.layout, pt=140,
                  centre=True, colour=self.theme.accent)

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
        xs = sorted(t.rect.centerx for t in targets)
        x_left = xs[0]
        x_right = xs[-1]
        # Y comes off any target's tile top (they're all aligned).
        any_target = targets[0]
        y_base = any_target.rect.top - 22 + bob - 12
        colour = self._MIRROR_PAIR_COLOUR
        # Horizontal bar across the top.
        pygame.draw.line(surf, colour,
                          (x_left, y_base),
                          (x_right, y_base), 3)
        # Short downward stubs at each end so the bracket reads
        # closed at the corners.
        stub_h = 10
        pygame.draw.line(surf, colour,
                          (x_left, y_base),
                          (x_left, y_base + stub_h), 3)
        pygame.draw.line(surf, colour,
                          (x_right, y_base),
                          (x_right, y_base + stub_h), 3)
        # "TOGETHER" label centred above the bar so the patient
        # knows the bracket means "press these as a pair". Pulsing
        # alpha so the cue is visible but doesn't fight the lane
        # tiles for focus.
        import math as _m
        alpha_phase = (_m.sin(now * (2 * _m.pi / 1.2)) + 1) * 0.5
        alpha = int(160 + 60 * alpha_phase)
        label_font = self.layout.font(FONT_SMALL + 2)
        label = label_font.render("PRESS TOGETHER", True, colour)
        label.set_alpha(alpha)
        x_mid = (x_left + x_right) // 2
        surf.blit(label, label.get_rect(
            midbottom=(x_mid, y_base - 4)))

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
            pygame.draw.rect(fill_surf, (*self.theme.accent, 220),
                              fill_surf.get_rect(), border_radius=bar_h // 2)
            surf.blit(fill_surf, (pad, bar_y))
        # Time readout right-aligned to the bar's end. Manual right-align
        # via font.render so the MM:SS sits flush with the screen edge.
        time_text = f"{self._fmt_mmss(elapsed_s)} / {self._fmt_mmss(total_s)}"
        tf = self.layout.font(FONT_SMALL + 2)
        ts = tf.render(time_text, True, self.theme.muted)
        surf.blit(ts, ts.get_rect(topright=(self.layout.width - pad,
                                              bar_y + bar_h + 6)))

    def add_encouragement(self, text: str) -> None:
        # Match the gameplay screen's banner placement (just below the
        # score) so the user gets the same visual rhythm in both modes.
        cx = self.layout.width // 2
        self._popups.append(FloatingText(
            text, (cx, 200), self.theme.success,
            font_pt=FONT_TITLE - 4,
            lifetime_s=1.8,
            rise_px=40,
        ))

    def flash_lane(self, lane: int, colour, duration_s: float, now: float) -> None:
        for ls in self.lanes:
            if ls.lane == lane:
                ls.flash(colour, duration_s, now)
                if self.message:
                    self._popups.append(FloatingText(
                        self.message, (ls.rect.centerx, ls.rect.top - 10),
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
        # Streak pill - only shown when streak >= 2 so a fresh run
        # doesn't have a permanent "STREAK -" widget burning pixels
        # in the patient's focal area. Mirrors the gameplay screen's
        # streak treatment for consistency between modes.
        streak = self.engine.hit_streak
        if streak >= 2:
            if streak >= 10:
                streak_colour = self.theme.success
            elif streak >= 5:
                streak_colour = (255, 196, 0)         # gold tier
            else:
                streak_colour = self.theme.foreground
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
                # area underneath; the inner accent ring ties it to
                # the rhythm UI's blue palette.
                fill_surf = pygame.Surface(card_rect.size, pygame.SRCALPHA)
                fill = (*self.theme.background, 245)
                pygame.draw.rect(fill_surf, fill,
                                  fill_surf.get_rect(), border_radius=22)
                pygame.draw.rect(fill_surf, (*self.theme.accent, 110),
                                  fill_surf.get_rect(), 3, border_radius=22)
                surf.blit(fill_surf, card_rect.topleft)
                draw_text(surf, "GET READY",
                          (card_rect.centerx, card_rect.y + 56),
                          self.theme, self.layout, pt=FONT_H1,
                          centre=True, colour=self.theme.muted)
                draw_text(surf, f"{countdown:.1f}",
                          (card_rect.centerx, card_rect.y + 156),
                          self.theme, self.layout, pt=140,
                          centre=True, colour=self.theme.accent)

        # No keyboard hints on screen. The patient is meant to be using
        # the Arduino device by this point.

        if self.engine.paused:
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
                    self._durations[key] = float(
                        librosa.get_duration(path=key))
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
        if e.type == pygame.MOUSEWHEEL:
            # Scroll the track list when the cursor is hovering it.
            # Clamped at both ends so the wheel stops at top + bottom
            # rather than drifting into empty space below the last row.
            mx, my = pygame.mouse.get_pos()
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
        title_font = pygame.font.SysFont(
            "Helvetica Neue,Helvetica,Arial,DejaVu Sans",
            title_pt, bold=True,
        )
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
    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        cx = engine.layout.width // 2
        # Three buttons centred on the screen:
        # Retry (primary, re-runs the same block) | Play again
        # (back to mode select) | Back to title.
        btn_w = 220
        gap = 20
        total_w = btn_w * 3 + gap * 2
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
        self.title_btn = Button(
            pygame.Rect(x, y, btn_w, h),
            "Back to title", engine.show_title,
            self.theme, self.layout, font_pt=FONT_H2,
        )

    def handle_event(self, e: pygame.event.Event) -> None:
        self.retry_btn.handle_event(e)
        self.again_btn.handle_event(e)
        self.title_btn.handle_event(e)

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

    # Per-finger labels for the histogram x-axis. Order matches the
    # within-hand finger index used everywhere else (0=index..3=pinky).
    _FINGER_SHORT = ("I", "M", "R", "P")

    def _draw_per_lane_chart(self, surf: pygame.Surface,
                              rect: pygame.Rect, title: str,
                              values: list[float],
                              unit: str,
                              high_is_bad: bool) -> None:
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
            draw_text(surf, label,
                      (bar_x + bar_w // 2, bar_bottom + 14),
                      self.theme, self.layout, pt=FONT_SMALL,
                      centre=True, colour=self.theme.muted)
        # Unit hint in the bottom-right corner of the card so the
        # reader knows what the bar heights mean.
        if unit:
            draw_text(surf, unit,
                      (rect.right - 24, rect.y + rect.h - 12),
                      self.theme, self.layout, pt=FONT_SMALL,
                      colour=self.theme.muted)

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
        val_font = pygame.font.SysFont(
            "Helvetica Neue,Helvetica,Arial,DejaVu Sans",
            int(FONT_TITLE * self.layout.font_scale),
            bold=True,
        )
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

        # Top banner. Bold via the shared SysFont call so the header
        # matches the rest of the menu screens.
        title_font = pygame.font.SysFont(
            "Helvetica Neue,Helvetica,Arial,DejaVu Sans",
            int((FONT_H1 + 6) * self.layout.font_scale),
            bold=True,
        )
        title_surf = title_font.render("Session complete", True,
                                        self.theme.accent)
        title_rect = title_surf.get_rect(center=(cx, 80))
        surf.blit(title_surf, title_rect)
        # Accent bar under the title (matches _draw_header).
        bar_w = max(60, title_rect.w // 3)
        bar_rect = pygame.Rect(0, 0, bar_w, 3)
        bar_rect.center = (cx, title_rect.bottom + 10)
        pygame.draw.rect(surf, self.theme.accent, bar_rect, border_radius=2)
        draw_text(surf, blurb,
                  (cx, title_rect.bottom + 32),
                  self.theme, self.layout, pt=FONT_BODY,
                  centre=True, colour=self.theme.muted)

        # Grade letter inside a ring. Big celebratory moment, the part the
        # patient and therapist see first.
        grade_centre = (cx, 240)
        ring_r = 90
        # Soft glow behind the ring.
        glow = pygame.Surface((ring_r * 2 + 40, ring_r * 2 + 40),
                               pygame.SRCALPHA)
        for i, alpha in ((20, 30), (12, 50), (4, 80)):
            pygame.draw.circle(glow, (*grade_colour, alpha),
                                (ring_r + 20, ring_r + 20), ring_r + i)
        surf.blit(glow, (grade_centre[0] - ring_r - 20,
                          grade_centre[1] - ring_r - 20))
        pygame.draw.circle(surf, grade_colour, grade_centre, ring_r, 6)
        # Letter itself, oversized + bold so the visual weight matches
        # the heavy ring around it. A regular-weight 110pt letter
        # looked thin and disconnected from the surrounding circle.
        gfont = pygame.font.SysFont(
            "Helvetica Neue,Helvetica,Arial,DejaVu Sans",
            int(120 * self.layout.font_scale),
            bold=True,
        )
        gtext = gfont.render(grade, True, grade_colour)
        surf.blit(gtext, gtext.get_rect(center=grade_centre))

        # Stat cards row - score, hits, hit rate, misses. Slimmer
        # cards (110 px instead of 130) free the vertical space the
        # per-lane histograms need below.
        card_w = 200
        card_h = 110
        gap = 24
        total_w = card_w * 4 + gap * 3
        cards_x = cx - total_w // 2
        cards_y = 380
        self._draw_stat_card(
            surf,
            pygame.Rect(cards_x, cards_y, card_w, card_h),
            "SCORE", f"{self.engine.score}", self.theme.accent,
        )
        self._draw_stat_card(
            surf,
            pygame.Rect(cards_x + (card_w + gap), cards_y, card_w, card_h),
            "HITS", f"{self.engine.hits}", self.theme.success,
        )
        self._draw_stat_card(
            surf,
            pygame.Rect(cards_x + (card_w + gap) * 2, cards_y, card_w, card_h),
            "HIT RATE", f"{rate * 100:.0f}%", self.theme.foreground,
        )
        self._draw_stat_card(
            surf,
            pygame.Rect(cards_x + (card_w + gap) * 3, cards_y, card_w, card_h),
            "MISSES", f"{self.engine.misses}", self.theme.error,
        )

        # Per-lane histograms below the stat-card row. Two charts
        # side-by-side: mean RT per lane (where slow fingers stand
        # out) + miss + wrong-press count per lane (where mistake
        # fingers stand out). Together they let a therapist see
        # which finger is slow vs which is failing entirely.
        n_lanes = (8 if self.engine.hand_mode == "both" else 4)
        # `getattr` defaults shield against an engine state where the
        # per-lane dicts weren't populated (a fresh engine before any
        # block, or a __new__-built engine in some test paths). Empty
        # dicts just produce zero-height bars.
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
        chart_y = 510
        chart_h = 130
        chart_gap = 24
        total_chart_w = self.layout.width - 80
        chart_w = (total_chart_w - chart_gap) // 2
        left_x = (self.layout.width - total_chart_w) // 2
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
        self.title_btn.draw(surf)


class DiagnosticsScreen(Screen):
    """Settings + hardware test screen reachable from the title.

    Three jobs:
    1. Live FSR readout per lane (or keyboard-press feedback in keyboard
       mode) so the therapist can verify each finger before a session.
    2. Detect available COM ports and let the user assign which port
       belongs to the LEFT hand and which to the RIGHT. Saves to
       config/user_settings.yaml.
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
        self.rebuild_lanes()
        self.refresh_ports()
        self.rebuild_panel()

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

    # The bottom panel takes ~170 px so lanes shrink to fit. Without
    # this the hardware panel would overlap the lane strips.
    PANEL_HEIGHT = 170
    PANEL_GAP = 20

    def _lanes_bottom_y(self) -> int:
        return self.layout.height - 100 - self.PANEL_HEIGHT - self.PANEL_GAP

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
        y = 220
        h = self._lanes_bottom_y() - y
        # Bilateral layout: right hand on the right half of the
        # screen with index closest to centre, left hand on the
        # left half mirrored. Same arrangement the gameplay screen
        # uses in bilateral mode so what the therapist sees here
        # matches what the patient will see when the block starts.
        half_w = (self.layout.width - 120) // 2
        block_w = half_w - 40
        gutter = 18
        n = 4
        w = (block_w - gutter * (n - 1)) // n
        rects: dict[int, pygame.Rect] = {}
        # Left hand on the LEFT of the screen: lanes 7,6,5,4 reading
        # left-to-right (little finger outermost).
        for pos in range(n):
            rects[7 - pos] = pygame.Rect(
                40 + pos * (w + gutter), y, w, h)
        # Right hand on the RIGHT: lanes 0,1,2,3 reading left-to-right.
        for pos in range(n):
            rects[pos] = pygame.Rect(
                half_w + 120 + pos * (w + gutter), y, w, h)
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
            self._port_status = (
                "Saved. Restart the app for the new ports to take "
                "effect on the next session."
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

    @staticmethod
    def _short_port(p: str) -> str:
        """Strip /dev/cu. and /dev/tty. prefixes so port labels fit
        comfortably in a dropdown row."""
        for prefix in ("/dev/cu.", "/dev/tty.", "/dev/", "\\\\.\\"):
            if p.startswith(prefix):
                return p[len(prefix):]
        return p

    def _dropdown_options(self) -> list[tuple[object, str]]:
        """Options shown in each hand's port dropdown:
          - ('None', sentinel for unassigned)
          - one entry per detected Arduino-family port
        Junk Mac ports (debug-console, Bluetooth-Incoming-Port, etc.)
        are filtered upstream in discover_ports so they cannot appear
        here even if the user clicks Refresh while one is present.
        """
        options: list[tuple[object, str]] = [(None, "None (no Arduino)")]
        for p in self._detected_ports:
            options.append((p, self._short_port(p)))
        return options

    def rebuild_panel(self) -> None:
        """(Re)build the bottom hardware panel: two port dropdowns,
        two STIM test buttons, a Refresh button + a Save button.

        Called on init AND after every port re-scan so the dropdown
        options reflect what was just detected."""
        from .widgets import Dropdown
        self._panel_buttons = []
        panel_y = self.layout.height - 100 - self.PANEL_HEIGHT
        row_h = 40
        row_gap = 12
        rows_x = 40
        # Per-hand row layout:
        #   [HAND label] [dropdown ......]   [Test STIM]
        # Save + Refresh go on the right side, spanning both rows.
        dropdown_w = 290
        test_w = 170
        # Build / update the two dropdowns.
        options = self._dropdown_options()
        for i, hand in enumerate(("left", "right")):
            y = panel_y + 50 + i * (row_h + row_gap)
            dd_rect = pygame.Rect(rows_x + 70, y, dropdown_w, row_h)
            existing = self._port_dropdowns.get(hand)
            current = self._current_port(hand)
            if existing is None:
                self._port_dropdowns[hand] = Dropdown(
                    dd_rect, options, current,
                    on_change=(lambda v, h=hand:
                                self._on_port_chosen(h, v)),
                    theme=self.theme, layout=self.layout,
                    placeholder="None (no Arduino)",
                )
            else:
                existing.rect = dd_rect
                existing.set_options(options)
                existing.current_value = current
            # Test STIM button per hand.
            self._panel_buttons.append(Button(
                pygame.Rect(rows_x + 70 + dropdown_w + 20, y,
                             test_w, row_h),
                f"Test {hand.upper()} STIM",
                lambda h=hand: self._start_stim_test(h),
                self.theme, self.layout, font_pt=FONT_BODY - 2,
            ))
        # Refresh + Save buttons on the right side.
        refresh_x = rows_x + 70 + dropdown_w + 20 + test_w + 20
        self._panel_buttons.append(Button(
            pygame.Rect(refresh_x, panel_y + 50, 100, row_h),
            "Refresh", self._rescan_ports,
            self.theme, self.layout, font_pt=FONT_BODY - 2,
        ))
        # Save button. Green when unsaved changes exist so it stands
        # out as the next thing to click, muted when there's nothing
        # to save.
        save_colour = ((34, 197, 94) if self._has_unsaved
                       else None)
        self._panel_buttons.append(Button(
            pygame.Rect(refresh_x, panel_y + 50 + row_h + row_gap,
                         100, row_h),
            "Save", self._save_ports,
            self.theme, self.layout, font_pt=FONT_BODY - 2,
            colour=save_colour,
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
        for dd in self._port_dropdowns.values():
            if dd.handle_event(e):
                consumed = True
        # If a dropdown is open and the click landed inside its popup,
        # don't dispatch the event further (otherwise a buttons sitting
        # behind the popup would also fire).
        if consumed:
            return
        self.back_btn.handle_event(e)
        for b in self._panel_buttons:
            b.handle_event(e)
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
        # Pull one sample if the source is pushing them.
        if self.engine.source.provides_samples:
            s = self.engine.source.get_sample(timeout=0)
            if s is not None:
                n_per_hand = int(self.engine.cfg.get(
                    "fsr.num_sensors_per_hand", 4))
                for i, ls in enumerate(self.lanes):
                    if i < len(s.values):
                        ls.value = s.values[i]
                        det = self.engine.detectors.get(ls.hand)
                        if det:
                            local = i % n_per_hand
                            b = det.baseline[local]
                            ls.baseline = b if b is not None else 0.0
                            # Active = currently pressed per detector.
                            ls.active = bool(det.pressed[local])
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
        sub = ("Press each finger to verify the sensor. "
                "Pick which Arduino feeds each hand below, then Save.")
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
        now = time.perf_counter()
        # Bilateral hand headers, always rendered because Settings
        # always shows all 8 lanes (even when the session-level
        # hand_mode is left or right only). Without the labels the
        # therapist wouldn't know which half of the screen is which
        # hand.
        draw_text(surf, "LEFT", (self.layout.width // 4, 192),
                  self.theme, self.layout, pt=FONT_H2, centre=True,
                  colour=LaneStrip.HAND_BADGE["left"])
        draw_text(surf, "RIGHT", (self.layout.width * 3 // 4, 192),
                  self.theme, self.layout, pt=FONT_H2, centre=True,
                  colour=LaneStrip.HAND_BADGE["right"])
        for ls in self.lanes:
            ls.draw(surf, now)
        # Hardware port panel ------------------------------------------------
        panel_y = self.layout.height - 100 - self.PANEL_HEIGHT
        panel_rect = pygame.Rect(
            30, panel_y, self.layout.width - 60, self.PANEL_HEIGHT,
        )
        # Soft background card so the panel reads as a discrete block.
        bg = tuple(max(0, c - 14) for c in self.theme.background)
        pygame.draw.rect(surf, bg, panel_rect, border_radius=12)
        # Panel header.
        draw_text(surf,
                  "ARDUINO PORT ASSIGNMENT",
                  (panel_rect.x + 18, panel_rect.y + 8),
                  self.theme, self.layout, pt=FONT_SMALL + 4,
                  centre=False, colour=self.theme.muted)
        # Detected ports list, right-aligned in the header row. Show
        # short names (the basename after /dev/cu.) so multiple Mac
        # ports fit on one line.
        if self._detected_ports:
            shorts = [self._short_port(p) for p in self._detected_ports]
            detected_label = "Detected: " + ", ".join(shorts)
        else:
            detected_label = "No serial ports detected"
        if len(detected_label) > 110:
            detected_label = detected_label[:107] + "..."
        df = self.layout.font(FONT_SMALL + 2)
        ds = df.render(detected_label, True, self.theme.muted)
        surf.blit(ds, ds.get_rect(
            topright=(panel_rect.right - 18, panel_rect.y + 10)))
        # Per-hand row labels (LEFT / RIGHT) next to each dropdown.
        row_h = 40
        row_gap = 12
        for i, hand in enumerate(("left", "right")):
            y = panel_y + 50 + i * (row_h + row_gap)
            colour = LaneStrip.HAND_BADGE.get(hand, self.theme.foreground)
            draw_text(surf, hand.upper(),
                      (panel_rect.x + 18, y + row_h // 2 - 9),
                      self.theme, self.layout, pt=FONT_BODY,
                      centre=False, colour=colour)
        # Buttons (test STIM, refresh, save).
        for b in self._panel_buttons:
            b.draw(surf)
        # Dropdown rests on top of any underlying card / button rect.
        for dd in self._port_dropdowns.values():
            dd.draw_closed(surf)
        # Status / info line at the bottom of the panel. Coloured by
        # state: orange when unsaved, normal otherwise.
        if self._port_status:
            status = self._port_status
            if len(status) > 120:
                status = status[:117] + "..."
            status_colour = (self.theme.warning
                              if self._has_unsaved
                              else self.theme.foreground)
            draw_text(surf, status,
                      (panel_rect.centerx, panel_rect.bottom - 14),
                      self.theme, self.layout, pt=FONT_SMALL + 2,
                      centre=True, colour=status_colour)
        self.back_btn.draw(surf)
        # Dropdown popup overlays drawn LAST so they sit on top of
        # everything else, including the back button.
        for dd in self._port_dropdowns.values():
            dd.draw_overlay(surf)
        # Footer hint.
        draw_text(surf, "Esc returns to the title screen",
                  (self.layout.width // 2, self.layout.height - 30),
                  self.theme, self.layout, pt=FONT_SMALL + 2,
                  centre=True, colour=self.theme.muted)
