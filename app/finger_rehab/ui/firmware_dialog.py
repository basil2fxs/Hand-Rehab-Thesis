"""The modal behind the two Settings firmware buttons.

Two modes on one card so both jobs read the same:

  flash    write the game firmware. One board, one confirm, one click.
  address  move a SingleTact from one I2C address to another. The app
           flashes a tiny tool sketch, talks to it, then puts the game
           firmware back.

The address mode carries a warning that is not decoration. Every
SingleTact interface answers I2C address 0x04 as well as its own
configured address, so a write to 0x04 lands on every sensor wired to
the bus at once. Changing "0x04" with four sensors attached would set
all four to the same address and the finger mapping would be gone with
no way to tell which sensor is which. The job refuses that case outright
rather than warning about it, because the therapist cannot undo it.

Keyboard: Tab cycles the controls, Enter fires the focused one, Esc
closes while idle and does nothing at all while a job runs. Same rules
as ConfirmDialog, which is where the card geometry comes from.
"""
from __future__ import annotations

import pygame

from .theme import Theme
from .widgets import (
    FONT_BODY, FONT_H2, FONT_SMALL,
    Button, Dropdown, Layout, TextInput, draw_text,
)


# The four addresses the device itself uses, in finger order. Anything
# else goes in the "other" field, so the common case is a single click
# and the rare one is still reachable.
FINGER_ADDRESSES = (
    (0x05, "0x05  index"),
    (0x06, "0x06  middle"),
    (0x07, "0x07  ring"),
    (0x08, "0x08  little"),
)


class FirmwareDialog:
    """Modal card driving a FirmwareJob or an AddressJob.

    The dialog owns no hardware and starts no threads. The Settings
    screen supplies callbacks: `on_flash()` and `on_address(change, old,
    new)` both return a job object (or None when the screen refused),
    and the screen polls that job. Keeping the thread on the screen's
    side is what lets the engine teardown and rebuild happen on the main
    thread where they belong.
    """

    CARD_W = 720
    # The address card is taller: the 0x04 warning sits in its own box
    # above the board and the two addresses.
    CARD_H = {"flash": 330, "address": 420}
    BTN_W = 180
    BTN_H = 50
    FIELD_H = 40

    def __init__(self, mode: str, theme: Theme, layout: Layout,
                 *, ports: list[tuple[str, str]],
                 firmware_label: str,
                 on_flash=None, on_address=None, on_close=None) -> None:
        self.mode = mode              # "flash" or "address"
        self.theme = theme
        self.layout = layout
        self.ports = list(ports)
        self.firmware_label = firmware_label
        self._on_flash = on_flash
        self._on_address = on_address
        self._on_close = on_close

        self.job = None
        self.busy = False
        self.finished = False
        self.result_text = ""
        self.result_ok = False
        self.wants_close = False
        self._dim_cache: pygame.Surface | None = None

        cx = layout.width // 2
        card_h = self.CARD_H.get(mode, self.CARD_H["flash"])
        self.card = pygame.Rect(cx - self.CARD_W // 2,
                                layout.height // 2 - card_h // 2,
                                self.CARD_W, card_h)

        # Rows from the card top: the board, then (address) the two
        # addresses. Every field spans what it needs, so a long port
        # name never runs under the arrow.
        x = self.card.x + 28
        self.board_y = self.card.y + (178 if mode == "address" else 110)
        self.port = self.ports[0][0] if self.ports else ""
        self.port_dropdown: Dropdown | None = None
        if len(self.ports) > 1:
            self.port_dropdown = Dropdown(
                pygame.Rect(x, self.board_y, self.CARD_W - 56, self.FIELD_H),
                [(p, label) for p, label in self.ports], self.port,
                on_change=self._pick_port, theme=theme, layout=layout,
                placeholder="pick a board",
            )

        self.old_input: TextInput | None = None
        self.new_dropdown: Dropdown | None = None
        self.other_input: TextInput | None = None
        self.new_value: int | None = 0x05
        if mode == "address":
            row = self.card.y + 262
            self.old_input = TextInput(
                pygame.Rect(x, row, 130, self.FIELD_H),
                theme, layout, label="", initial="0x04", max_len=6,
                font_pt=FONT_BODY)
            self.new_dropdown = Dropdown(
                pygame.Rect(x + 150, row, 220, self.FIELD_H),
                list(FINGER_ADDRESSES) + [(None, "other...")], 0x05,
                on_change=self._pick_new, theme=theme, layout=layout,
                placeholder="NEW")
            self.other_input = TextInput(
                pygame.Rect(x + 390, row, 130, self.FIELD_H),
                theme, layout, label="", initial="", max_len=6,
                font_pt=FONT_BODY)

        self.buttons: list[Button] = []
        self.focus = 0
        self._build_buttons()

    # -- construction helpers -------------------------------------------

    def _pick_port(self, value) -> None:
        self.port = str(value)

    def _pick_new(self, value) -> None:
        self.new_value = value if value is None else int(value)
        # "other..." brings up the OTHER field with the typing cursor in
        # it, and only there: OLD may still hold the cursor from a
        # click. A finger address hides OTHER, and a hidden field must
        # not keep the cursor or it would swallow keys unseen.
        items = self._focusables()
        target = (self.other_input if self._other_shown()
                  else self.new_dropdown)
        if target in items:
            self.focus = items.index(target)
            self._apply_focus(items)

    def _form_open(self) -> bool:
        """The fields take part only while the form is on the card. A
        running or finished job draws its progress there instead."""
        return not self.busy and not self.finished

    def _other_shown(self) -> bool:
        return (self._form_open() and self.other_input is not None
                and self.new_value is None)

    def _dropdowns(self) -> list:
        if not self._form_open():
            return []
        return [dd for dd in (self.port_dropdown, self.new_dropdown)
                if dd is not None]

    def _park_the_form(self) -> None:
        """A job has started or ended: shut any open list and take the
        cursor out of the fields, which are no longer drawn."""
        for dd in (self.port_dropdown, self.new_dropdown):
            if dd is not None:
                dd.is_open = False
        for ti in (self.old_input, self.other_input):
            if ti is not None:
                ti.focused = False

    def _focus_the_safe_button(self) -> None:
        """Put the ring on Cancel (or Close), never on a field.

        A reflex Enter, or a second press of the key that opened the
        dialog, has to land on the harmless choice. Reaching Flash or
        Change takes a deliberate Tab or a click.
        """
        items = self._focusables()
        self.focus = max(0, len(items) - len(self.buttons))

    def _build_buttons(self) -> None:
        y = self.card.bottom - self.BTN_H - 26
        x = self.card.x + 28
        self.buttons = []
        if self.finished:
            self.buttons.append(Button(
                pygame.Rect(self.card.right - self.BTN_W - 28, y,
                            self.BTN_W, self.BTN_H),
                "Close", self.close, self.theme, self.layout,
                font_pt=FONT_BODY, primary=True))
            self.focus = 0
            return
        if self.busy:
            return
        self.buttons.append(Button(
            pygame.Rect(x, y, self.BTN_W, self.BTN_H),
            "Cancel", self.close, self.theme, self.layout,
            font_pt=FONT_BODY, primary=True))
        if self.mode == "flash":
            self.buttons.append(Button(
                pygame.Rect(self.card.right - self.BTN_W - 28, y,
                            self.BTN_W, self.BTN_H),
                "Flash", self._start_flash, self.theme, self.layout,
                font_pt=FONT_BODY))
        else:
            self.buttons.append(Button(
                pygame.Rect(self.card.right - self.BTN_W * 2 - 44, y,
                            self.BTN_W, self.BTN_H),
                "Scan", self._start_scan, self.theme, self.layout,
                font_pt=FONT_BODY))
            self.buttons.append(Button(
                pygame.Rect(self.card.right - self.BTN_W - 28, y,
                            self.BTN_W, self.BTN_H),
                "Change", self._start_change, self.theme, self.layout,
                font_pt=FONT_BODY))
        self._focus_the_safe_button()

    # -- address parsing -------------------------------------------------

    @staticmethod
    def parse_address(text: str) -> int | None:
        """0x05, 05 and 5 all mean five. None means "not an address"."""
        s = (text or "").strip().lower()
        if not s:
            return None
        try:
            value = int(s, 16) if s.startswith("0x") else int(s, 16)
        except ValueError:
            return None
        if value < 0x04 or value > 0x7F:
            return None
        return value

    def chosen_new(self) -> int | None:
        if self.new_value is not None:
            return int(self.new_value)
        return self.parse_address(self.other_input.text
                                  if self.other_input else "")

    def chosen_old(self) -> int | None:
        return self.parse_address(self.old_input.text
                                  if self.old_input else "")

    # -- starting a job ---------------------------------------------------

    def _launch(self, job) -> None:
        if job is None:
            # The screen refused (a block is running, no hex, no
            # avrdude). It puts the reason on the status line itself.
            self.close()
            return
        self.job = job
        self.busy = True
        self.finished = False
        self._park_the_form()
        self._build_buttons()

    def _start_flash(self) -> None:
        if self._on_flash is None:
            return
        self._launch(self._on_flash(self.port))

    def _start_scan(self) -> None:
        if self._on_address is None:
            return
        self._launch(self._on_address(self.port, False, None, None))

    def _start_change(self) -> None:
        if self._on_address is None:
            return
        old, new = self.chosen_old(), self.chosen_new()
        if old is None or new is None:
            self.result_text = ("Addresses must be between 0x04 and 0x7F. "
                                "Type them as 0x05 or 5.")
            self.result_ok = False
            return
        if old == new:
            self.result_text = "The old and new addresses are the same."
            self.result_ok = False
            return
        self._launch(self._on_address(self.port, True, old, new))

    def finish(self, text: str, ok: bool) -> None:
        """Called by the screen once the job is done and the engine has
        rebuilt its source."""
        self.job = None
        self.busy = False
        self.finished = True
        self.result_text = text
        self.result_ok = bool(ok)
        self._park_the_form()
        self._build_buttons()

    def close(self) -> None:
        if self.busy:
            return
        self.wants_close = True
        if self._on_close is not None:
            self._on_close()

    # -- input -------------------------------------------------------------

    def on_escape(self) -> bool:
        """True means the dialog swallowed the key.

        A running job swallows Esc without acting on it: avrdude is
        mid-write and there is nothing safe to cancel. An open list
        shuts first and the dialog stays.
        """
        if self.busy:
            return True
        for dd in self._dropdowns():
            if dd.is_open:
                dd.is_open = False
                return True
        self.close()
        return True

    def _focusables(self) -> list:
        items: list = []
        if self._form_open():
            if self.port_dropdown is not None:
                items.append(self.port_dropdown)
            if self.old_input is not None:
                items.append(self.old_input)
            if self.new_dropdown is not None:
                items.append(self.new_dropdown)
            if self._other_shown():
                items.append(self.other_input)
        items.extend(self.buttons)
        return items

    def _text_fields(self) -> list:
        """The fields on show: none once a job has started, and OTHER
        only while it is drawn."""
        if not self._form_open():
            return []
        return [ti for ti in (self.old_input, self.other_input)
                if ti is not None
                and (ti is not self.other_input or self._other_shown())]

    def handle_event(self, e: pygame.event.Event) -> bool:
        """Always returns True: the dialog is modal, so nothing behind
        the dim layer may react to anything."""
        if self.busy:
            return True
        # Once the job is done only Close is on the card, so only the
        # buttons hear anything: a click where OLD was drawn used to
        # reach the hidden field.
        dds = self._dropdowns()
        if e.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN,
                      pygame.MOUSEBUTTONUP):
            # An open list is drawn over the fields below it, so it
            # hears the click first, and one click works one control.
            # The port list covers the NEW picker: a pick there used
            # to open NEW as well.
            for dd in sorted(dds, key=lambda d: not d.is_open):
                if dd.handle_event(e):
                    for other in dds:
                        if other is not dd:
                            other.is_open = False
                    return True
            for ti in self._text_fields():
                ti.handle_event(e)
                if e.type == pygame.MOUSEBUTTONDOWN and ti.focused:
                    # The ring follows the click, so Tab walks on from
                    # the field being typed in.
                    items = self._focusables()
                    if ti in items:
                        self.focus = items.index(ti)
            for b in self.buttons:
                b.handle_event(e)
            return True
        if e.type == pygame.KEYDOWN:
            # An open list holds the keys until it shuts. Tab shuts it
            # and walks on as usual.
            for dd in dds:
                if dd.is_open:
                    if e.key != pygame.K_TAB:
                        dd.handle_key(e)
                        return True
                    dd.is_open = False
            # A focused text field takes the key first so typing an
            # address does not walk the focus ring.
            for ti in self._text_fields():
                if ti.focused and e.key not in (pygame.K_TAB,
                                                pygame.K_ESCAPE):
                    ti.handle_event(e)
                    return True
            items = self._focusables()
            if not items:
                return True
            if e.key in (pygame.K_TAB, pygame.K_DOWN, pygame.K_RIGHT):
                step = -1 if (e.mod & pygame.KMOD_SHIFT) else 1
                self.focus = (self.focus + step) % len(items)
                self._apply_focus(items)
            elif e.key in (pygame.K_UP, pygame.K_LEFT):
                self.focus = (self.focus - 1) % len(items)
                self._apply_focus(items)
            elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER,
                           pygame.K_SPACE):
                item = items[self.focus % len(items)]
                if isinstance(item, Button):
                    item.on_click()
                elif isinstance(item, Dropdown):
                    item.open_from_keys()
                elif isinstance(item, TextInput):
                    item.focused = True
            return True
        return True

    def _apply_focus(self, items) -> None:
        """Mirror the focus ring onto the text fields so a keyboard-only
        user can see where their typing will land."""
        current = items[self.focus % len(items)]
        for ti in (self.old_input, self.other_input):
            if ti is not None:
                ti.focused = ti is current

    # -- drawing ------------------------------------------------------------

    def _title(self) -> str:
        return ("Flash the game firmware" if self.mode == "flash"
                else "Change a sensor's I2C address")

    def draw(self, surf: pygame.Surface) -> None:
        th, ly = self.theme, self.layout
        if (self._dim_cache is None
                or self._dim_cache.get_size() != surf.get_size()):
            self._dim_cache = pygame.Surface(surf.get_size(),
                                             pygame.SRCALPHA)
            self._dim_cache.fill((0, 0, 0, 170))
        surf.blit(self._dim_cache, (0, 0))
        card = self.card
        pygame.draw.rect(surf, th.background, card, border_radius=18)
        pygame.draw.rect(surf, th.muted, card, 2, border_radius=18)
        draw_text(surf, self._title(), (card.centerx, card.y + 40), th, ly,
                  pt=FONT_H2, centre=True)
        rule = pygame.Rect(0, 0, 72, 4)
        rule.center = (card.centerx, card.y + 72)
        pygame.draw.rect(surf, th.accent, rule, border_radius=2)

        x = card.x + 28
        if self.busy or self.finished:
            self._draw_progress(surf, x)
        elif self.mode == "flash":
            self._draw_flash_form(surf, x)
        else:
            self._draw_address_form(surf, x)

        for b in self.buttons:
            b.draw(surf)
        items = self._focusables()
        if items and not self.busy:
            focused = items[self.focus % len(items)]
            ring = focused.rect.inflate(10, 10)
            pygame.draw.rect(surf, th.accent, ring, 3, border_radius=14)
        # Popups last so an open list covers the buttons under it.
        for dd in self._dropdowns():
            dd.draw_overlay(surf)

    def _board_line(self) -> str:
        for p, label in self.ports:
            if p == self.port:
                return label
        return self.port or "no board"

    def _label(self, surf, text: str, x: int, field_y: int) -> None:
        """The small caps name over a field, one style for all."""
        draw_text(surf, text, (x, field_y - 22), self.theme, self.layout,
                  pt=FONT_SMALL, centre=False, colour=self.theme.muted)

    def _draw_board(self, surf, x: int) -> None:
        """BOARD and its picker, or the one board there is."""
        th, ly = self.theme, self.layout
        self._label(surf, "BOARD", x, self.board_y)
        if self.port_dropdown is not None:
            self.port_dropdown.draw_closed(surf)
        else:
            draw_text(surf, self._board_line(), (x, self.board_y + 6), th,
                      ly, pt=FONT_BODY, centre=False)

    def _draw_flash_form(self, surf, x: int) -> None:
        th, ly = self.theme, self.layout
        card = self.card
        self._draw_board(surf, x)
        draw_text(surf, "Firmware: " + self.firmware_label,
                  (x, card.y + 170), th, ly, pt=FONT_BODY, centre=False,
                  colour=th.foreground)
        draw_text(surf, "Takes about ten seconds. The buzzers self test "
                        "when the board restarts.",
                  (x, card.y + 200), th, ly, pt=FONT_SMALL + 2,
                  centre=False, colour=th.muted)
        if self.result_text:
            draw_text(surf, self.result_text, (x, card.y + 226), th, ly,
                      pt=FONT_SMALL + 2, centre=False, colour=th.warning)

    def _draw_address_form(self, surf, x: int) -> None:
        th, ly = self.theme, self.layout
        card = self.card
        # The warning in a tinted box of its own: it is the one thing
        # on this card that cannot be undone if it is missed.
        box = pygame.Rect(x, card.y + 84, card.w - 56, 60)
        tint = tuple(int(c + (255 - c) * 0.86) for c in th.warning)
        ink = tuple(int(c * 0.72) for c in th.warning)
        pygame.draw.rect(surf, tint, box, border_radius=10)
        pygame.draw.rect(surf, th.warning, box, 1, border_radius=10)
        draw_text(surf, "Every SingleTact also answers 0x04. A change from "
                        "0x04 reaches every",
                  (box.x + 14, box.y + 9), th, ly, pt=FONT_SMALL + 2,
                  centre=False, colour=ink)
        draw_text(surf, "sensor on the bus. Connect ONE sensor only.",
                  (box.x + 14, box.y + 31), th, ly, pt=FONT_SMALL + 2,
                  centre=False, colour=ink)
        self._draw_board(surf, x)
        if self.old_input is not None:
            self._label(surf, "OLD", self.old_input.rect.x,
                        self.old_input.rect.y)
            self.old_input.draw(surf)
        if self.new_dropdown is not None:
            self._label(surf, "NEW", self.new_dropdown.rect.x,
                        self.new_dropdown.rect.y)
            self.new_dropdown.draw_closed(surf)
        if self.new_value is None and self.other_input is not None:
            self._label(surf, "OTHER", self.other_input.rect.x,
                        self.other_input.rect.y)
            self.other_input.draw(surf)
        if self.result_text:
            draw_text(surf, self.result_text, (x, card.y + 312), th, ly,
                      pt=FONT_SMALL + 2, centre=False, colour=th.warning)

    def _draw_progress(self, surf, x: int) -> None:
        th, ly = self.theme, self.layout
        card = self.card
        line = self.result_text if self.finished else (
            self.job.message if self.job is not None else "Working")
        colour = th.foreground
        if self.finished:
            colour = th.success if self.result_ok else th.error
        # Measured, not guessed at a character count: the result
        # sentences name addresses and port names, and a character
        # budget picked for one of them runs the other off the card.
        room = card.w - 56
        for i, chunk in enumerate(
                _wrap(str(line), ly.font(FONT_BODY), room)[:5]):
            draw_text(surf, chunk, (x, card.y + 96 + i * 28), th, ly,
                      pt=FONT_BODY, centre=False, colour=colour)
        if self.busy:
            draw_text(surf, "Do not unplug the board.",
                      (x, card.bottom - 56), th, ly, pt=FONT_SMALL + 2,
                      centre=False, colour=th.muted)


def _wrap(text: str, font, pixels: int) -> list[str]:
    """Greedy word wrap measured against the font that will draw it."""
    lines: list[str] = []
    current = ""
    for word in str(text).split():
        trial = f"{current} {word}".strip()
        if current and font.size(trial)[0] > pixels:
            lines.append(current)
            current = word
        else:
            current = trial
    if current:
        lines.append(current)
    return lines or [""]
