"""The SRT setup screen: what the Reaction card opens.

The researcher picks this participant's timing here and starts the
task. Everything on it is kept (game/srt_setup.py): the current setup
is written to the setups file on every change, so the next participant
in the same group needs one click, and named setups hold each group's
timing for good. The lab's three groups at 500 ms are always listed.

The sequence stays hidden until Show is pressed. The participant is
often sitting in front of this screen, and knowing the order is
exactly what the task must not hand them before it starts (explicit
knowledge changes what an SRT measures).

Musical experience is the lab script's 0 to 5 question. It belongs to
the person logged in, not to the setup, so it is kept for this login
only and written into the performance file with every trial.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ..game.srt_setup import (
    DEFAULT_SETUP, GROUPS, ISI_MAX_MS, ISI_MIN_MS, LAB_SEQUENCE,
    MUSICAL_EXPERIENCE, SRTSetup, SetupStore, estimate_minutes,
    parse_sequence, protocol_counts, sequence_text, store_path,
)
from .screens import Screen
from .widgets import (
    BUTTON_H, FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL, Button, Card,
    Segmented, TextInput, draw_text,
)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


GROUP_LINES = {
    "constant": "Every interval is the learning interval.",
    "cyclical": ("Intervals follow the sequence position: half, equal, "
                 "one and a half times, repeating."),
    "random": ("Intervals shuffle within every pass of the sequence: "
               "half, equal, one and a half times."),
}
UNSAVED = "Unsaved setup"
ISI_STEP_MS = 50


class SRTSetupScreen(Screen):

    LEFT = pygame.Rect(40, 132, 700, 560)
    RIGHT = pygame.Rect(760, 132, 480, 560)
    ROW_H = 56
    ROWS_TOP = 188
    ROWS_SHOWN = 5

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.store: SetupStore | None = None
        self.group = DEFAULT_SETUP.group
        self.isi_ms = int(DEFAULT_SETUP.isi_ms)
        self.sequence = tuple(DEFAULT_SETUP.sequence)
        self.show_sequence = False
        self.editing = False
        self.note = ""
        self.note_bad = False
        self._delete_armed: str | None = None
        self._scroll = 0
        self._row_rects: list[tuple[pygame.Rect, SRTSetup]] = []
        lx, ly = self.LEFT.x + 30, self.LEFT.y
        self.group_seg = Segmented(
            pygame.Rect(lx, ly + 80, 640, 52), self.theme, self.layout,
            [(g, g.capitalize()) for g in GROUPS], label="Timing group",
            initial=self.group)
        self.minus_btn = Button(pygame.Rect(lx, ly + 196, 60, 52), "-",
                                lambda: self._nudge(-ISI_STEP_MS),
                                self.theme, self.layout, font_pt=FONT_H2)
        self.isi_input = TextInput(
            pygame.Rect(lx + 70, ly + 196, 130, 52), self.theme,
            self.layout, label="Learning interval (ms)",
            initial=str(self.isi_ms), max_len=4, numeric=True)
        self.plus_btn = Button(pygame.Rect(lx + 210, ly + 196, 60, 52),
                               "+", lambda: self._nudge(ISI_STEP_MS),
                               self.theme, self.layout, font_pt=FONT_H2)
        self.show_btn = Button(pygame.Rect(lx + 330, ly + 306, 100, 44),
                               "Show", self._toggle_show, self.theme,
                               self.layout, font_pt=FONT_BODY)
        self.edit_btn = Button(pygame.Rect(lx + 440, ly + 306, 90, 44),
                               "Edit", self._toggle_edit, self.theme,
                               self.layout, font_pt=FONT_BODY)
        self.lab_btn = Button(pygame.Rect(lx + 540, ly + 306, 100, 44),
                              "Lab", self._lab_sequence, self.theme,
                              self.layout, font_pt=FONT_BODY)
        self.seq_input = TextInput(
            pygame.Rect(lx, ly + 364, 520, 48), self.theme, self.layout,
            placeholder="1321432413 or v n b v m n b m v n",
            max_len=40)
        self.use_btn = Button(pygame.Rect(lx + 530, ly + 364, 110, 48),
                              "Use", self._use_typed, self.theme,
                              self.layout, font_pt=FONT_BODY, primary=True)
        self.music_seg = Segmented(
            pygame.Rect(lx, ly + 452, 360, 48), self.theme, self.layout,
            [(str(i), str(i)) for i in range(6)],
            label="Musical experience (this participant)",
            hotkeys={str(i): str(i) for i in range(6)})
        rx = self.RIGHT.x + 24
        self.name_input = TextInput(
            pygame.Rect(rx, self.RIGHT.bottom - 160, 300, 48), self.theme,
            self.layout, label="Save these settings as",
            placeholder="e.g. Constant 300", max_len=40)
        self.save_btn = Button(
            pygame.Rect(rx + 310, self.RIGHT.bottom - 160, 122, 48),
            "Save", self._save_as, self.theme, self.layout,
            font_pt=FONT_BODY)
        self.delete_btn = Button(
            pygame.Rect(rx, self.RIGHT.bottom - 92, 200, 44),
            "Delete setup", self._delete, self.theme, self.layout,
            font_pt=FONT_BODY)
        h = engine.layout.height
        w = engine.layout.width
        self.back_btn = Button(pygame.Rect(40, h - 88, 180, BUTTON_H - 10),
                               "Back", self._back, self.theme, self.layout)
        self.start_btn = Button(pygame.Rect(w - 260, h - 94, 220, BUTTON_H),
                                "START", self._start, self.theme,
                                self.layout, font_pt=FONT_H2, primary=True)

    # ---- state ----------------------------------------------------------------
    def enter(self) -> None:
        """Fresh read of the setups file every visit, so a setup saved
        on another launch (or edited by hand) is what shows."""
        self.store = SetupStore(store_path(self.engine.cfg))
        cur = self.store.current
        self.group = cur.group
        self.isi_ms = int(cur.isi_ms)
        self.sequence = tuple(cur.sequence)
        self.group_seg.set(self.group)
        self.isi_input.text = str(self.isi_ms)
        self.isi_input.focused = False
        self.show_sequence = False
        self.editing = False
        self.seq_input.text = ""
        self.seq_input.focused = False
        self.name_input.text = ""
        self.name_input.focused = False
        self._delete_armed = None
        self._scroll = 0
        me = getattr(self.engine, "_srt_musical_experience", None)
        self.music_seg.set(None if me is None else str(me))
        self.note = ""
        self.note_bad = False

    def _values(self, name: str | None = None) -> SRTSetup:
        return SRTSetup(name or self._matching_name(), self.group,
                        int(self.isi_ms), tuple(self.sequence))

    def _matching_name(self) -> str:
        store = self.store
        if store is None:
            return UNSAVED
        for s in store.all():
            if (s.group == self.group and int(s.isi_ms) == int(self.isi_ms)
                    and tuple(s.sequence) == tuple(self.sequence)):
                return s.name
        return UNSAVED

    def _commit(self) -> None:
        """Write the values on screen as the current setup."""
        if self.store is None:
            return
        why = self.store.set_current(self._values())
        if why:
            self._say(why, bad=True)

    def _say(self, text: str, bad: bool = False) -> None:
        self.note = text
        self.note_bad = bad

    # ---- controls ----------------------------------------------------------------
    def _nudge(self, delta: int) -> None:
        self._read_isi_field()
        self._set_isi(int(self.isi_ms) + delta)

    def _set_isi(self, value: int) -> None:
        value = max(ISI_MIN_MS, min(ISI_MAX_MS, int(value)))
        self.isi_ms = value
        self.isi_input.text = str(value)
        self._commit()

    def _read_isi_field(self) -> None:
        txt = self.isi_input.value
        if not txt:
            self.isi_input.text = str(self.isi_ms)
            return
        try:
            value = int(txt)
        except ValueError:
            self.isi_input.text = str(self.isi_ms)
            return
        if not ISI_MIN_MS <= value <= ISI_MAX_MS:
            self._say(f"Interval kept to {ISI_MIN_MS} to {ISI_MAX_MS} ms",
                      bad=True)
        if max(ISI_MIN_MS, min(ISI_MAX_MS, value)) != self.isi_ms:
            self._set_isi(value)
        else:
            self.isi_input.text = str(self.isi_ms)

    def _toggle_show(self) -> None:
        self.show_sequence = not self.show_sequence

    def _toggle_edit(self) -> None:
        self.editing = not self.editing
        self.seq_input.focused = self.editing
        self.seq_input.text = ""

    def _lab_sequence(self) -> None:
        self.sequence = tuple(LAB_SEQUENCE)
        self.editing = False
        self._commit()
        self._say("Lab sequence in use")

    def _use_typed(self) -> None:
        seq, why = parse_sequence(self.seq_input.value)
        if seq is None:
            self._say(why, bad=True)
            return
        self.sequence = seq
        self.editing = False
        self.seq_input.focused = False
        self._commit()
        self._say(f"Sequence of {len(seq)} in use")

    def _load(self, setup: SRTSetup) -> None:
        self.group = setup.group
        self.isi_ms = int(setup.isi_ms)
        self.sequence = tuple(setup.sequence)
        self.group_seg.set(self.group)
        self.isi_input.text = str(self.isi_ms)
        self._delete_armed = None
        if self.store is not None:
            self.store.set_current(setup)
        self._say(f"Loaded {setup.name}")

    def _save_as(self) -> None:
        if self.store is None:
            return
        self._read_isi_field()
        name = self.name_input.value
        why = self.store.save_as(name, self._values(name or UNSAVED))
        if why:
            self._say(why, bad=True)
            return
        self.name_input.text = ""
        self.name_input.focused = False
        self._say(f"Saved {name}")

    def _delete(self) -> None:
        if self.store is None:
            return
        name = self._matching_name()
        if name == UNSAVED or self.store.is_built_in(name):
            self._say("Load a saved setup first; lab setups stay",
                      bad=True)
            return
        if self._delete_armed != name:
            self._delete_armed = name
            self._say(f"Press Delete setup again to remove {name}")
            return
        self._delete_armed = None
        why = self.store.delete(name)
        self._commit()
        self._say(why or f"Removed {name}", bad=bool(why))

    def _back(self) -> None:
        self.engine.show_mode_select()

    def _start(self) -> None:
        self._read_isi_field()
        if self.editing and self.seq_input.value:
            seq, why = parse_sequence(self.seq_input.value)
            if seq is None:
                self._say(why, bad=True)
                return
            self.sequence = seq
        self.editing = False
        why = self._values().problem()
        if why:
            self._say(why, bad=True)
            return
        self._commit()
        me = self.music_seg.value
        self.engine._srt_musical_experience = (None if me is None
                                               else int(me))
        self.engine.begin_srt_block()

    # ---- events ------------------------------------------------------------------
    def handle_event(self, e: pygame.event.Event) -> None:
        was_isi_focused = self.isi_input.focused
        was_name_focused = self.name_input.focused
        was_seq_focused = self.editing and self.seq_input.focused
        for widget in (self.group_seg, self.isi_input, self.music_seg,
                       self.name_input):
            widget.handle_event(e)
        if self.editing:
            self.seq_input.handle_event(e)
            self.use_btn.handle_event(e)
        if self.group_seg.value and self.group_seg.value != self.group:
            self.group = self.group_seg.value
            self._commit()
        if was_isi_focused and not self.isi_input.focused:
            self._read_isi_field()
        for b in (self.minus_btn, self.plus_btn, self.show_btn,
                  self.edit_btn, self.lab_btn, self.save_btn,
                  self.delete_btn, self.back_btn, self.start_btn):
            b.handle_event(e)
        if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for rect, setup in self._row_rects:
                if rect.collidepoint(e.pos):
                    self._load(setup)
                    break
        elif e.type == pygame.MOUSEWHEEL:
            rows = len(self.store.all()) if self.store else 0
            self._scroll = max(0, min(max(0, rows - self.ROWS_SHOWN),
                                      self._scroll - int(e.y)))
        elif (e.type == pygame.KEYDOWN
              and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER)):
            # Enter finishes whatever field it was typed in; with no
            # field in use it starts the task.
            if was_seq_focused:
                self._use_typed()
            elif was_name_focused:
                self._save_as()
            elif not was_isi_focused:
                self._start()

    # ---- draw ---------------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        cx = self.layout.width // 2
        draw_text(surf, "Reaction setup", (cx, 52), self.theme, self.layout,
                  pt=FONT_H1, centre=True)
        draw_text(surf, "The lab's sequence task. Set this participant's "
                  "timing, then start.", (cx, 96), self.theme, self.layout,
                  pt=FONT_BODY, centre=True, colour=self.theme.muted)
        Card(self.LEFT, self.theme, layout=self.layout).draw(surf)
        Card(self.RIGHT, self.theme, layout=self.layout).draw(surf)
        self._draw_left(surf)
        self._draw_right(surf)
        self.back_btn.draw(surf)
        self.start_btn.draw(surf)
        self._draw_footer(surf)

    def _draw_left(self, surf: pygame.Surface) -> None:
        lx, ly = self.LEFT.x + 30, self.LEFT.y
        muted = self.theme.muted
        draw_text(surf, "This run", (lx, ly + 4), self.theme, self.layout,
                  pt=FONT_H2)
        self.group_seg.draw(surf)
        draw_text(surf, GROUP_LINES.get(self.group, ""), (lx, ly + 142),
                  self.theme, self.layout, pt=FONT_SMALL + 2, colour=muted)
        self.minus_btn.draw(surf)
        self.isi_input.draw(surf)
        self.plus_btn.draw(surf)
        short = int(round(self.isi_ms * 0.5))
        long_ = int(round(self.isi_ms * 1.5))
        detail = ("Learning blocks only; the random blocks stay at 500 ms."
                  if self.group == "constant" else
                  f"Learning blocks only: {short}, {self.isi_ms} and "
                  f"{long_} ms. Random blocks stay at 500 ms.")
        draw_text(surf, detail, (lx, ly + 256), self.theme,
                  self.layout, pt=FONT_SMALL + 2, colour=muted)
        draw_text(surf, "Sequence", (lx, ly + 290), self.theme, self.layout,
                  pt=FONT_SMALL + 4, colour=muted)
        lab = tuple(self.sequence) == LAB_SEQUENCE
        if self.show_sequence:
            text = sequence_text(self.sequence)
        else:
            text = (f"Lab sequence, {len(self.sequence)} items" if lab
                    else f"Custom, {len(self.sequence)} items")
        draw_text(surf, text, (lx, ly + 318), self.theme, self.layout,
                  pt=FONT_BODY)
        self.show_btn.label = "Hide" if self.show_sequence else "Show"
        self.show_btn.draw(surf)
        self.edit_btn.label = "Close" if self.editing else "Edit"
        self.edit_btn.draw(surf)
        self.lab_btn.draw(surf)
        if self.editing:
            self.seq_input.draw(surf)
            self.use_btn.draw(surf)
        else:
            draw_text(surf, "Hidden until Show, so the participant does "
                      "not see the order.", (lx, ly + 374), self.theme,
                      self.layout, pt=FONT_SMALL + 1, colour=muted)
        self.music_seg.draw(surf)
        me = self.music_seg.value
        caption = (MUSICAL_EXPERIENCE[int(me)][4:] if me is not None
                   else "not asked yet")
        draw_text(surf, caption, (lx + 380, ly + 466), self.theme,
                  self.layout, pt=FONT_SMALL + 2, colour=muted)
        counts = protocol_counts(self.engine.cfg)
        mins = estimate_minutes(self._values(), counts)
        n_learn = counts["learning_reps"] * len(self.sequence)
        draw_text(surf,
                  f"About {mins:.0f} min: {counts['random_trials']} practice, "
                  f"{counts['learning_blocks']} x {n_learn} learning, "
                  f"{counts['random_trials']} post-test, then recall",
                  (lx, ly + 520), self.theme, self.layout,
                  pt=FONT_SMALL + 2, colour=muted)

    def _draw_right(self, surf: pygame.Surface) -> None:
        rx = self.RIGHT.x + 24
        draw_text(surf, "Saved setups", (rx, self.RIGHT.y + 4), self.theme,
                  self.layout, pt=FONT_H2)
        self._row_rects = []
        setups = self.store.all() if self.store is not None else []
        current = self._matching_name()
        shown = setups[self._scroll:self._scroll + self.ROWS_SHOWN]
        for i, s in enumerate(shown):
            r = pygame.Rect(rx, self.ROWS_TOP + i * self.ROW_H,
                            self.RIGHT.w - 48, self.ROW_H - 4)
            picked = s.name == current
            fill = (tuple(min(255, c + (255 - c) * 3 // 4)
                          for c in self.theme.accent)
                    if picked else tuple(max(0, c - 8)
                                         for c in self.theme.background))
            pygame.draw.rect(surf, fill, r, border_radius=10)
            if picked:
                pygame.draw.rect(surf, self.theme.accent, r, 2,
                                 border_radius=10)
            draw_text(surf, s.name, (r.x + 14, r.y + 6), self.theme,
                      self.layout, pt=FONT_BODY)
            draw_text(surf, s.summary(), (r.x + 14, r.y + 29), self.theme,
                      self.layout, pt=FONT_SMALL + 1,
                      colour=self.theme.muted)
            self._row_rects.append((r, s))
        if len(setups) > self.ROWS_SHOWN:
            draw_text(surf, f"Scroll for more ({len(setups)} in all)",
                      (rx, self.ROWS_TOP + self.ROWS_SHOWN * self.ROW_H),
                      self.theme, self.layout, pt=FONT_SMALL + 1,
                      colour=self.theme.muted)
        self.name_input.draw(surf)
        self.save_btn.draw(surf)
        self.delete_btn.draw(surf)

    def _draw_footer(self, surf: pygame.Surface) -> None:
        cx = self.layout.width // 2
        y = self.layout.height - 64
        if self.note:
            colour = self.theme.error if self.note_bad else self.theme.success
            draw_text(surf, self.note, (cx, y - 14), self.theme,
                      self.layout, pt=FONT_BODY, centre=True, colour=colour)
        step = None
        pending = getattr(self.engine, "_protocol_current", None)
        if (getattr(self.engine, "_battery", None) is not None
                and isinstance(pending, dict)
                and pending.get("mode") == "srt"):
            step = pending
        if step is not None:
            of = (self.engine._battery or {}).get("of", "?")
            draw_text(surf, f"Play all: step {step.get('position', '?')} "
                      f"of {of}", (cx, y + 18), self.theme, self.layout,
                      pt=FONT_SMALL + 2, centre=True,
                      colour=self.theme.muted)
