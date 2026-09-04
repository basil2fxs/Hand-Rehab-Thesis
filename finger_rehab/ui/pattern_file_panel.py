"""The Settings card for the Muscle Memory sequence file.

WHY A CARD AND NOT A ROW OF BUTTONS. The Settings screen's bottom row
is full (Arduino ports, session data, firmware), and this job needs
more than a button: three actions, the name of whatever is loaded, a
typed-path box for a keyboard-only rig, and room for a list of
validation errors that a researcher has to be able to read and act on.
A small overlay card is the only place all of that fits without moving
somebody else's panel.

WHY A TYPED PATH. tkinter's file dialog is excluded from the frozen
build (finger_rehab.spec drops tkinter) and opening one beside an SDL
window has crashed the interpreter on macOS (CPython issues 44828 and
46573). So the picker runs only where it is safe, and everywhere else
the card opens the drop folder and takes a path typed or pasted into
the box. That box is also the keyboard-only route: it takes focus the
moment the card opens, so a rig with no mouse can still load a file.

The card never writes anything itself. Everything goes through
finger_rehab/data/pattern_file.py, where a rejected file changes
nothing on disk.
"""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pygame

from ..data import pattern_file
from .widgets import (Button, FONT_BODY, FONT_SMALL, TextInput, draw_text)


log = logging.getLogger(__name__)


def native_picker_is_safe() -> bool:
    """True only where a tkinter file dialog can be opened beside the
    SDL window without risking the whole app. Frozen builds have no
    tkinter at all, and macOS has crashed on it, so both fall back to
    the drop folder plus the typed path."""
    if getattr(sys, "frozen", False):
        return False
    if sys.platform == "darwin":
        return False
    try:
        import tkinter  # noqa: F401
        from tkinter import filedialog  # noqa: F401
    except Exception:
        return False
    return True


class PatternFilePanel:
    """Overlay card: load, save a template, or go back to the built-in
    riff. Owns its own buttons and hit testing, so nothing on the
    Settings screen underneath can fire while it is up."""

    W = 640
    H = 420
    PAD = 24
    ROW_H = 40
    ROW_GAP = 12

    def __init__(self, engine, theme, layout) -> None:
        self.engine = engine
        self.theme = theme
        self.layout = layout
        self.open = False
        self.status = ""
        self.status_is_error = False
        # Every validation error, so a file with six problems can be
        # fixed in one pass rather than one reload per problem.
        self.errors: list[str] = []
        self.buttons: list[Button] = []
        self.path_input: TextInput | None = None
        self._rect = pygame.Rect(0, 0, self.W, self.H)

    # ---- geometry ------------------------------------------------------
    def rect(self) -> pygame.Rect:
        r = pygame.Rect(0, 0, self.W, self.H)
        r.center = (self.layout.width // 2, self.layout.height // 2)
        return r

    def _row_y(self, i: int) -> int:
        return (self.rect().y + 118 + i * (self.ROW_H + self.ROW_GAP))

    def _build(self) -> None:
        r = self.rect()
        self._rect = r
        x = r.x + self.PAD
        w = r.w - self.PAD * 2
        half = (w - self.ROW_GAP) // 2
        self.buttons = [
            Button(pygame.Rect(x, self._row_y(0), w, self.ROW_H),
                   "Load pattern file", self._load_clicked,
                   self.theme, self.layout, font_pt=FONT_BODY - 2,
                   primary=True),
            Button(pygame.Rect(x, self._row_y(1), half, self.ROW_H),
                   "Save pattern template", self._template_clicked,
                   self.theme, self.layout, font_pt=FONT_BODY - 4),
            Button(pygame.Rect(x + half + self.ROW_GAP, self._row_y(1),
                               half, self.ROW_H),
                   "Use built-in riff", self._clear_clicked,
                   self.theme, self.layout, font_pt=FONT_BODY - 4),
            Button(pygame.Rect(r.right - self.PAD - 110,
                               r.bottom - self.PAD - 36, 110, 36),
                   "Close", self.close,
                   self.theme, self.layout, font_pt=FONT_BODY - 2),
        ]
        self.path_input = TextInput(
            pygame.Rect(x, self._row_y(2), w, self.ROW_H),
            self.theme, self.layout,
            placeholder="Type or paste a file path, then press Enter",
            max_len=400, font_pt=FONT_BODY - 4)
        # Focused on open so a rig with no mouse can type a path
        # straight away.
        self.path_input.focused = True

    # ---- open and close -------------------------------------------------
    def show(self) -> None:
        self.open = True
        self.errors = []
        self._build()
        # A file saved into the drop folder since the last menu screen
        # is picked up here too, so opening this card always shows what
        # is really on disk rather than what was true a screen ago.
        syncer = getattr(self.engine, "sync_pattern_sequence_file", None)
        if callable(syncer):
            try:
                syncer()
            except Exception as e:
                log.warning("drop folder not synced: %s", e)
        self._describe_active()

    def close(self) -> None:
        self.open = False

    def _describe_active(self) -> None:
        line = ""
        try:
            line = self.engine.pattern_plan_headline()
        except Exception as e:
            log.warning("could not read the active sequence file: %s", e)
        self.status = f"Loaded: {line}" if line else "Built-in riff in use"
        self.status_is_error = False

    # ---- actions ---------------------------------------------------------
    def _cfg(self):
        return self.engine.cfg

    def _drop_dir(self) -> Path:
        return pattern_file.drop_dir(self._cfg())

    def _reveal(self, path: Path) -> None:
        opener = getattr(self.engine, "_reveal_in_file_manager", None)
        if callable(opener):
            try:
                opener(str(path))
            except Exception as e:
                log.warning("could not open %s: %s", path, e)

    def _load_clicked(self) -> None:
        if native_picker_is_safe():
            picked = self._native_pick()
            if picked:
                self.load_path(picked)
                return
            self.status = "No file picked."
            self.status_is_error = False
            return
        folder = self._drop_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            log.warning("could not create the drop folder: %s", e)
        self._reveal(folder)
        if self.path_input is not None:
            self.path_input.focused = True
        self.status = (f"Drag the file onto the game window, save it in "
                       f"the folder just opened as {pattern_file.DROP_NAME}, "
                       f"or type its path below.")
        self.status_is_error = False

    def _native_pick(self) -> str:
        try:
            import tkinter
            from tkinter import filedialog
            root = tkinter.Tk()
            root.withdraw()
            path = filedialog.askopenfilename(
                title="Pick a Muscle Memory sequence file",
                filetypes=[("Sequence file", "*.yaml *.yml")],
                initialdir=str(self._drop_dir()))
            root.destroy()
            return path or ""
        except Exception as e:
            log.warning("file picker not available: %s", e)
            return ""

    def _template_clicked(self) -> None:
        try:
            paths = pattern_file.write_templates(self._cfg())
        except OSError as e:
            self.status = f"Template not saved: {e}"
            self.status_is_error = True
            return
        self._reveal(paths[0].parent)
        self.status = (f"Saved {paths[0].name} and {paths[1].name} in "
                       f"{paths[0].parent}. Edit one, then load it.")
        self.status_is_error = False

    def _clear_clicked(self) -> None:
        pattern_file.clear_active(self._cfg())
        self.errors = []
        self.status = ("Built-in riff in use. The files you loaded are "
                       "still in the history folder.")
        self.status_is_error = False

    def load_path(self, raw: str) -> None:
        """Import whatever the researcher pointed at. Quotes and stray
        spaces are stripped because dragging a file into a terminal or
        copying a path from Finder brings them along."""
        text = (raw or "").strip().strip('"').strip("'").strip()
        if not text:
            return
        path = Path(os.path.expanduser(text))
        if not path.is_file():
            self.status = f"There is no file at {path}."
            self.status_is_error = True
            self.errors = []
            return
        try:
            res = pattern_file.import_file(path, self._cfg())
        except Exception as e:
            log.warning("sequence file import failed: %s", e)
            self.status = f"{path.name} not loaded: {e}"
            self.status_is_error = True
            return
        self.errors = list(res.errors)
        self.status = res.message()
        self.status_is_error = not res.ok
        if res.ok:
            self.errors = list(res.warnings)
            if self.path_input is not None:
                self.path_input.text = ""
            note = getattr(self.engine, "pattern_file_note", None)
            if note is not None:
                self.engine.pattern_file_note = self.status

    # ---- events -----------------------------------------------------------
    def handle_event(self, e: pygame.event.Event) -> bool:
        """True when the card took the event. Everything on the screen
        underneath is blocked while it is up: a click that lands on a
        dimmed panel must not fire the control drawn there."""
        if not self.open:
            return False
        if self.path_input is not None:
            was = self.path_input.text
            self.path_input.handle_event(e)
            if (e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN,
                                                       pygame.K_KP_ENTER)):
                self.load_path(self.path_input.text)
                return True
            if self.path_input.text != was:
                return True
        for b in self.buttons:
            b.handle_event(e)
        # Swallow every mouse and key event: the card is modal.
        return e.type in (pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP,
                          pygame.MOUSEMOTION, pygame.KEYDOWN, pygame.KEYUP)

    # ---- drawing ----------------------------------------------------------
    def draw(self, surf: pygame.Surface) -> None:
        if not self.open:
            return
        dim = pygame.Surface((self.layout.width, self.layout.height),
                             pygame.SRCALPHA)
        dim.fill((0, 0, 0, 150))
        surf.blit(dim, (0, 0))
        r = self.rect()
        self._rect = r
        pygame.draw.rect(surf, self.theme.background, r, border_radius=16)
        pygame.draw.rect(surf, self.theme.muted, r, width=1,
                         border_radius=16)
        x = r.x + self.PAD
        draw_text(surf, "MUSCLE MEMORY RIFF FILE", (x, r.y + 20),
                  self.theme, self.layout, pt=FONT_BODY,
                  centre=False, colour=self.theme.foreground)
        blurb = ("A file sets the finger order, the pause after every "
                 "press and the rests. Once loaded it runs for every "
                 "Muscle Memory game until you change it.")
        self._wrapped(surf, blurb, x, r.y + 52, r.w - self.PAD * 2,
                      FONT_SMALL, self.theme.muted, max_lines=3)
        for b in self.buttons:
            b.draw(surf)
        if self.path_input is not None:
            self.path_input.draw(surf)
        colour = (self.theme.warning if self.status_is_error
                  else self.theme.foreground)
        y = self._row_y(3) + 4
        y = self._wrapped(surf, self.status, x, y, r.w - self.PAD * 2,
                          FONT_SMALL, colour, max_lines=2)
        # The status line already carries the first problem, so start at
        # the second one. Everything is in the log either way; the card
        # shows as many as fit above the Close button and no more,
        # because text spilling onto the dimmed screen behind reads as
        # a broken app rather than as a long error list.
        rest = self.errors[1:] if self.status_is_error else self.errors
        for line in rest:
            if y > r.bottom - self.PAD - 40:
                break
            y = self._wrapped(surf, line, x, y + 2, r.w - self.PAD * 2 - 130,
                              FONT_SMALL, self.theme.muted, max_lines=2)

    def _wrapped(self, surf: pygame.Surface, text: str, x: int, y: int,
                 w: int, pt: int, colour, max_lines: int = 2) -> int:
        """Draw `text` wrapped to `w`, return the y below it. Wrapping
        rather than truncating because a validation sentence is the
        whole point of showing it."""
        if not text:
            return y
        font = self.layout.font(pt)
        words = str(text).split()
        line = ""
        lines: list[str] = []
        for word in words:
            trial = f"{line} {word}".strip()
            if font.size(trial)[0] <= w or not line:
                line = trial
            else:
                lines.append(line)
                line = word
            if len(lines) >= max_lines:
                break
        if line and len(lines) < max_lines:
            lines.append(line)
        step = font.get_height() + 2
        for i, one in enumerate(lines):
            draw_text(surf, one, (x, y + i * step), self.theme, self.layout,
                      pt=pt, centre=False, colour=colour)
        return y + len(lines) * step
