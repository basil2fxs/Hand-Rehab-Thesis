"""The EEG trigger box port picker.

Two ways in. At launch, when lab mode cannot open the port its config
names, the window opens here instead of on the login screen, and the
only ways out are a port that opens or Quit: a lab session must never
run unmarked, and this is how that rule gets a way forward other than
a text editor. From Settings, the "EEG trigger box" button opens it to
move the markers to another port, or to reconnect a box that dropped
out mid-session.

Picking a port opens it exactly as the marker writer would, moves the
markers onto it, and saves it (hardware/eeg_port.save_port) on the
same line of eeg_lab.yaml a person would edit by hand.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import pygame

from .screens import Screen, _draw_header, _fit_text
from .widgets import BUTTON_H, FONT_BODY, FONT_SMALL, Button, draw_text

if TYPE_CHECKING:
    from ..game.engine import GameEngine

log = logging.getLogger(__name__)


class EegPortScreen(Screen):
    ROW_W = 820
    ROW_H = 50
    ROW_GAP = 10
    LIST_TOP = 236
    MAX_ROWS = 7
    BTN_W = 220
    BTN_Y_FROM_BOTTOM = 104

    def __init__(self, engine: "GameEngine") -> None:
        super().__init__(engine)
        # Injectable so a test can drive the screen with no hardware.
        from ..hardware import eeg_port
        self.scan = eeg_port.candidates
        self.opener = eeg_port.open_port
        self.saver = eeg_port.save_port
        self._back = None
        self._choices = []
        self._rows: list[tuple[pygame.Rect, str]] = []
        self._hover = -1
        self.status = ""
        self._status_kind = "muted"
        self._connected = False
        self._buttons: list[Button] = []
        self._hand_guess: list[str] = []

    # ---- entry ------------------------------------------------------------
    @property
    def at_launch(self) -> bool:
        return self._back is None

    def enter(self, back=None) -> None:
        """Called by engine.show_eeg_port each time the screen opens."""
        self._back = back
        self._connected = False
        markers = self.engine.markers
        if markers.needs_port:
            problem = markers.port_problem or "no port is set"
            self._say(f"Trigger box not found on {problem}.", "error")
        else:
            self._say(self._current_line(), "muted")
        self.rescan()

    def _current_line(self) -> str:
        backend = getattr(self.engine.markers, "backend", None)
        port = getattr(backend, "port", None)
        if port:
            line = f"Markers go out on {port}."
            if getattr(self.engine.markers, "degraded", False):
                line = (f"Markers stopped reaching {port}. Pick the box "
                        "again to reconnect it.")
            return line
        return ("No trigger box: markers are only written to the log. "
                "Pick the box's port to send them.")

    def _current_port(self) -> str | None:
        if self.engine.markers.needs_port:
            return None
        return getattr(self.engine.markers.backend, "port", None)

    def rescan(self) -> None:
        """List the ports again. The hand boards' ports are left out
        once they are running; at launch they have not been opened, so
        every port is fair game."""
        planned = [getattr(h, "port", None) for h in
                   (getattr(self.engine.source, "hands", None) or [])]
        planned = [p for p in planned if p]
        exclude = []
        self._hand_guess = []
        if getattr(self.engine, "_hand_source_started", False):
            exclude = planned
        else:
            # Not opened yet, so still pickable (the box itself may be
            # what was taken for a hand board), but tagged so a hand
            # board is not clicked by mistake.
            self._hand_guess = planned
        try:
            self._choices = list(self.scan(exclude=exclude))
        except Exception as e:
            log.warning("EEG port scan failed: %s", e)
            self._choices = []
            self._say(f"Port scan failed: {e}", "error")
        self._layout_rows()
        self._build_buttons()

    # ---- actions ----------------------------------------------------------
    def pick(self, device: str) -> None:
        from ..hardware.eeg_port import same_port
        current = self._current_port()
        markers = self.engine.markers
        if (same_port(device, current) and markers.active
                and not markers.degraded):
            self._say(f"Already sending on {device}.", "success")
            self._connected = True
            self._build_buttons()
            return
        if same_port(device, current):
            # Reconnecting the same port: release it first, or Windows
            # refuses a second handle on it.
            try:
                markers.backend.close()
            except Exception as e:
                log.debug("closing %s before reopening: %s", device, e)
        baud = int(self.engine.cfg.get("eeg.baud", 115200))
        backend, why = self.opener(device, baud)
        if backend is None:
            self._say(f"{device} did not open: {why}. Try another.",
                      "error")
            return
        markers.use_backend(backend)
        _, saved = self.saver(self.engine.cfg, device)
        self._connected = True
        self._say(f"Connected on {device}. {saved} ActiView's trigger "
                  "display should read 0 now.", "success")
        try:
            self.engine.eeg_port_ready()
        except Exception as e:
            log.warning("After the EEG port opened: %s", e)
        self.rescan()

    def carry_on(self) -> None:
        if self.at_launch:
            self.engine.show_title()
        else:
            self._back()

    def quit(self) -> None:
        self.engine.running = False

    def on_escape(self) -> None:
        if self.at_launch and not self._connected:
            self.quit()
        else:
            self.carry_on()

    # ---- layout -----------------------------------------------------------
    def _layout_rows(self) -> None:
        x = (self.layout.width - self.ROW_W) // 2
        self._rows = []
        for i, c in enumerate(self._choices[:self.MAX_ROWS]):
            y = self.LIST_TOP + i * (self.ROW_H + self.ROW_GAP)
            self._rows.append((pygame.Rect(x, y, self.ROW_W, self.ROW_H),
                               c.device))

    def _build_buttons(self) -> None:
        w, h = self.layout.width, self.layout.height
        y = h - self.BTN_Y_FROM_BOTTOM
        bh = BUTTON_H - 6
        buttons = [Button(pygame.Rect(40, y, self.BTN_W, bh),
                          "Scan again", self.rescan, self.theme,
                          self.layout)]
        right = w - 40
        if self.at_launch:
            if self._connected:
                buttons.append(Button(
                    pygame.Rect(right - self.BTN_W, y, self.BTN_W, bh),
                    "Continue", self.carry_on, self.theme, self.layout,
                    primary=True))
                right -= self.BTN_W + 20
            buttons.append(Button(
                pygame.Rect(right - self.BTN_W, y, self.BTN_W, bh),
                "Quit", self.quit, self.theme, self.layout))
        else:
            buttons.append(Button(
                pygame.Rect(right - self.BTN_W, y, self.BTN_W, bh),
                "Back", self.carry_on, self.theme, self.layout,
                primary=self._connected))
        self._buttons = buttons

    def _say(self, text: str, kind: str) -> None:
        self.status = text
        self._status_kind = kind

    # ---- pygame -----------------------------------------------------------
    def handle_event(self, e: pygame.event.Event) -> None:
        if e.type == pygame.MOUSEMOTION:
            self._hover = next((i for i, (r, _) in enumerate(self._rows)
                                if r.collidepoint(e.pos)), -1)
        elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
            for rect, device in self._rows:
                if rect.collidepoint(e.pos):
                    self.pick(device)
                    return
        elif e.type == pygame.KEYDOWN and e.key in (pygame.K_RETURN,
                                                    pygame.K_KP_ENTER):
            if self._connected:
                self.carry_on()
                return
        for b in list(self._buttons):
            b.handle_event(e)

    def update(self, dt: float) -> None:
        pass

    def draw(self, surf: pygame.Surface) -> None:
        theme, layout = self.theme, self.layout
        surf.fill(theme.background)
        subtitle = ("The game needs the trigger box before it can start"
                    if self.at_launch and not self._connected
                    else "Pick the port the trigger box is plugged into")
        _draw_header(surf, "EEG trigger box", subtitle, theme, layout)
        colour = {"error": theme.error, "success": theme.success}.get(
            self._status_kind, theme.muted)
        font = layout.font(FONT_BODY)
        draw_text(surf, _fit_text(self.status, font, layout.width - 80),
                  (layout.width // 2, 190), theme, layout, pt=FONT_BODY,
                  centre=True, colour=colour)
        current = self._current_port()
        from ..hardware.eeg_port import same_port
        row_font = layout.font(FONT_BODY)
        for i, (rect, device) in enumerate(self._rows):
            choice = self._choices[i]
            in_use = same_port(device, current)
            edge = (theme.success if in_use
                    else theme.accent if i == self._hover
                    else theme.muted)
            pygame.draw.rect(surf, theme.background, rect, border_radius=12)
            pygame.draw.rect(surf, edge, rect, 3 if in_use or
                             i == self._hover else 2, border_radius=12)
            tag = ("   (in use now)" if in_use else
                   "   (hand board?)" if any(same_port(device, g)
                                            for g in self._hand_guess)
                   else "")
            label = choice.label + tag
            label = _fit_text(label, row_font, rect.w - 40)
            draw_text(surf, label, (rect.x + 20,
                                    rect.centery - row_font.get_height() // 2),
                      theme, layout, pt=FONT_BODY, colour=theme.foreground)
        if not self._rows:
            draw_text(surf, "No serial ports found. Plug the trigger box "
                      "in, then press Scan again.",
                      (layout.width // 2, self.LIST_TOP + 30), theme,
                      layout, pt=FONT_BODY, centre=True,
                      colour=theme.foreground)
        elif len(self._choices) > self.MAX_ROWS:
            last = self._rows[-1][0]
            draw_text(surf, f"{len(self._choices) - self.MAX_ROWS} more "
                      "not shown. Unplug what you do not need.",
                      (layout.width // 2, last.bottom + 18), theme, layout,
                      pt=FONT_SMALL + 2, centre=True, colour=theme.muted)
        hint_y = layout.height - self.BTN_Y_FROM_BOTTOM - 70
        for k, line in enumerate((
                "Not sure which one? Unplug the box, press Scan again, "
                "and see which entry goes.",
                "Hand boards already in use are not listed. The choice is "
                "saved in eeg_lab.yaml for next time.")):
            draw_text(surf, line, (layout.width // 2, hint_y + k * 24),
                      theme, layout, pt=FONT_SMALL + 2, centre=True,
                      colour=theme.muted)
        for b in self._buttons:
            b.draw(surf)
