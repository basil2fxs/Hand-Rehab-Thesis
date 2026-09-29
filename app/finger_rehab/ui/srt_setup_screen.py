"""The SRT setup screen: what the Reaction card opens.

One view (Basil, 28 September 2026): the timing group, the lab script's
0 to 5 musical experience question, and START. The hands are not asked
here: they are the session's, picked at login, and the screen says
which will play (both hands runs the lab's two-hand layout). The rest
runs as the lab ran it, 500 ms and the lab's sequence. A different
interval or sequence can be written into the setups file by hand
(config/srt_setups.json, game/srt_setup.py), and the screen then names
it, so a change is never invisible.

The timing group picked is written to the setups file straight away,
so the next participant in the same group needs one click.

The sequence is never shown. The participant is often sitting in front
of this screen, and knowing the order is exactly what the task must not
hand them before it starts (explicit knowledge changes what an SRT
measures).

Musical experience belongs to the person logged in, not to the setup,
so it is kept for this login only and written into the performance
file with every trial.
"""
from __future__ import annotations

import dataclasses
from typing import TYPE_CHECKING

import pygame

from ..game.srt_setup import (
    DEFAULT_SETUP, GROUPS, LAB_SEQUENCE, MUSICAL_EXPERIENCE, SRTSetup,
    SetupStore, estimate_minutes, protocol_counts, store_path,
)
from .screens import Screen
from .widgets import (BUTTON_H, FONT_BODY, FONT_H1, FONT_H2, FONT_SMALL,
                      Button, Card, Segmented, draw_text)

if TYPE_CHECKING:
    from ..game.engine import GameEngine


UNSAVED = "Unsaved setup"
LAB_ISI_MS = 500

# What the hands picked at login will play.
HANDS_LINE = {
    "right": "Right hand, as picked at login.",
    "left": "Left hand, as picked at login.",
    "both": ("Both hands, as picked at login: left middle and index, "
             "right index and middle."),
}


def group_line(group: str, isi_ms: int) -> str:
    """The timing group in one plain line, with this setup's numbers."""
    short = int(round(isi_ms * 0.5))
    long_ = int(round(isi_ms * 1.5))
    if group == "constant":
        return f"Every gap before a flash is {isi_ms} ms."
    if group == "cyclical":
        return (f"Gaps of {short}, {isi_ms} and {long_} ms, in a set "
                f"order that follows the sequence.")
    return f"Gaps of {short}, {isi_ms} and {long_} ms, shuffled."


class SRTSetupScreen(Screen):

    MAIN = pygame.Rect(190, 146, 900, 446)

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        self.store: SetupStore | None = None
        self.group = DEFAULT_SETUP.group
        self.isi_ms = int(DEFAULT_SETUP.isi_ms)
        self.sequence = tuple(DEFAULT_SETUP.sequence)
        self.note = ""
        self.note_bad = False
        mx, my = self.MAIN.x + 40, self.MAIN.y
        self.group_seg = Segmented(
            pygame.Rect(mx, my + 74, 820, 64), self.theme, self.layout,
            [(g, g.capitalize()) for g in GROUPS], label="Timing group",
            initial=self.group)
        self.music_seg = Segmented(
            pygame.Rect(mx, my + 236, 480, 56), self.theme, self.layout,
            [(str(i), str(i)) for i in range(6)],
            label="Musical experience",
            hotkeys={str(i): str(i) for i in range(6)})
        h = engine.layout.height
        w = engine.layout.width
        self.back_btn = Button(pygame.Rect(40, h - 88, 180, BUTTON_H - 10),
                               "Back", self._back, self.theme, self.layout)
        self.start_btn = Button(pygame.Rect(w - 260, h - 94, 220, BUTTON_H),
                                "START", self._start, self.theme,
                                self.layout, font_pt=FONT_H2, primary=True)

    # ---- state ----------------------------------------------------------------
    def enter(self) -> None:
        """Fresh read of the setups file every visit, so a setup edited
        by hand is what shows."""
        self.store = SetupStore(store_path(self.engine.cfg))
        cur = self.store.current
        self.group = cur.group
        self.isi_ms = int(cur.isi_ms)
        self.sequence = tuple(cur.sequence)
        self.group_seg.set(self.group)
        me = getattr(self.engine, "_srt_musical_experience", None)
        self.music_seg.set(None if me is None else str(me))
        self.note = ""
        self.note_bad = False

    def _hand_mode(self) -> str:
        hand = str(getattr(self.engine, "hand_mode", "right") or "right")
        return hand if hand in HANDS_LINE else "right"

    @property
    def hands(self) -> str:
        """The session's hands in the setup's words."""
        return "two" if self._hand_mode() == "both" else "one"

    @property
    def custom(self) -> bool:
        """True when the setups file holds an interval or a sequence
        other than the lab's."""
        return (int(self.isi_ms) != LAB_ISI_MS
                or tuple(self.sequence) != LAB_SEQUENCE)

    def _values(self) -> SRTSetup:
        return SRTSetup(self._matching_name(), self.group, int(self.isi_ms),
                        tuple(self.sequence), self.hands)

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
    def _back(self) -> None:
        self.engine.show_mode_select()

    def _start(self) -> None:
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
        for widget in (self.group_seg, self.music_seg):
            widget.handle_event(e)
        if self.group_seg.value and self.group_seg.value != self.group:
            self.group = self.group_seg.value
            self._commit()
        for b in (self.back_btn, self.start_btn):
            b.handle_event(e)
        if (e.type == pygame.KEYDOWN
                and e.key in (pygame.K_RETURN, pygame.K_KP_ENTER)):
            self._start()

    # ---- draw ---------------------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        surf.fill(self.theme.background)
        cx = self.layout.width // 2
        draw_text(surf, "Reaction", (cx, 58), self.theme, self.layout,
                  pt=FONT_H1, centre=True)
        draw_text(surf, "Pick this participant's timing group, then "
                  "press START.", (cx, 102), self.theme, self.layout,
                  pt=FONT_BODY, centre=True, colour=self.theme.muted)
        Card(self.MAIN, self.theme, layout=self.layout).draw(surf)
        self._draw_main(surf)
        self.back_btn.draw(surf)
        self.start_btn.draw(surf)
        self._draw_footer(surf)

    def _draw_main(self, surf: pygame.Surface) -> None:
        mx, my = self.MAIN.x + 40, self.MAIN.y
        muted = self.theme.muted
        self.group_seg.draw(surf)
        draw_text(surf, group_line(self.group, int(self.isi_ms)),
                  (mx, my + 156), self.theme, self.layout, pt=FONT_BODY)
        self.music_seg.draw(surf)
        me = self.music_seg.value
        caption = (MUSICAL_EXPERIENCE[int(me)][4:] if me is not None
                   else "ask: none, or years of lessons")
        draw_text(surf, caption, (mx + 500, my + 252), self.theme,
                  self.layout, pt=FONT_BODY, colour=muted)
        draw_text(surf, HANDS_LINE[self._hand_mode()], (mx, my + 322),
                  self.theme, self.layout, pt=FONT_BODY, colour=muted)
        counts = protocol_counts(self.engine.cfg)
        mins = estimate_minutes(self._values(), counts)
        draw_text(surf,
                  f"About {mins:.0f} min: practice, "
                  f"{counts['learning_blocks']} learning blocks, a final "
                  f"test, then recall.",
                  (mx, my + 354), self.theme, self.layout,
                  pt=FONT_BODY, colour=muted)
        if self.custom:
            # Set away from the lab's own run in the setups file: said
            # here, so the change is never invisible.
            lab_hands = dataclasses.replace(self._values(), hands="one")
            draw_text(surf, "Custom setup from config/srt_setups.json: "
                      + lab_hands.summary() + ".",
                      (mx, my + 392), self.theme, self.layout,
                      pt=FONT_SMALL + 2, colour=self.theme.warning)

    def _draw_footer(self, surf: pygame.Surface) -> None:
        cx = self.layout.width // 2
        y = self.layout.height - 64
        if self.note:
            colour = self.theme.error if self.note_bad else self.theme.success
            draw_text(surf, self.note, (cx, y - 58), self.theme,
                      self.layout, pt=FONT_BODY, centre=True, colour=colour)
        pending = getattr(self.engine, "_protocol_current", None)
        if (getattr(self.engine, "_battery", None) is not None
                and isinstance(pending, dict)
                and pending.get("mode") == "srt"):
            of = (self.engine._battery or {}).get("of", "?")
            draw_text(surf, f"Session: step {pending.get('position', '?')} "
                      f"of {of}", (cx, y + 44), self.theme, self.layout,
                      pt=FONT_SMALL + 2, centre=True,
                      colour=self.theme.muted)
