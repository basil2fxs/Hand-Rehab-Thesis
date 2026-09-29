"""The EEG lab without the lab: a window standing in for the trigger box
and the amplifier, so the lab session can be rehearsed on any PC.

In the lab the game writes one byte per event to the Arduino trigger
box on COM10, the box puts it on the amplifier's trigger lines for 8 ms,
and ActiView shows it as a step on the trigger channel under the EEG.
Here the game writes the same bytes, through the same code, to this
window instead:

    Finger Rehab --eeg-simulator
    Finger Rehab --eeg-port socket://127.0.0.1:50410

The first listens on 127.0.0.1:50410; the second is the lab game with
its trigger port pointed at it (pyserial opens socket:// addresses with
the same write calls it uses for COM10). EEG_Lab/developer/EEG
simulator.cmd starts both. With a virtual serial pair installed (for
example com0com, COM10 to COM11), --sim-port COM11 reads the other end
instead and the game runs on COM10 exactly as in the lab.

The window shows eight channels of made-up EEG (alpha over the back of
the head, blinks at the front, a small made-up response after each cue
and a dip after a wrong press, so a marker lines up with something), the
trigger channel as the amplifier would record it, a line at every marker
with its number, and beside it every marker in plain words, with counts
and the measured pulse width. The EEG is simulated and says so; only
the markers are real.

Keys: Space pause, Up and Down gain, Left and Right time span, C clear,
S save the markers to a CSV beside the game, Esc quit.
"""
from __future__ import annotations

import csv
import math
import socket
import threading
import time
from collections import Counter, deque
from pathlib import Path

LISTEN_PORT = 50410
RATE = 250                       # samples a second, drawn
CHANNELS = ("Fp1", "Fz", "C3", "Cz", "C4", "Pz", "O1", "O2")
SPANS = (5.0, 10.0, 20.0)        # seconds across the trace area

BAND_COLOURS = {
    "prep": (148, 163, 184),
    "stim": (37, 99, 235),
    "stim_pattern": (14, 165, 233),
    "stim_choice": (168, 85, 247),
    "resp": (22, 163, 74),
    "feedback": (234, 88, 12),
    "block": (220, 38, 38),
    "flow": (71, 85, 105),
    "unknown": (100, 116, 139),
}
BAND_WORDS = {"prep": "Get ready", "stim": "Cues", "stim_pattern": "Riff",
              "stim_choice": "Syllable sets", "resp": "Presses",
              "feedback": "Feedback", "block": "Blocks",
              "flow": "Session", "unknown": "Other"}


def describe(code: int) -> tuple[str, str, str]:
    """(name, plain words, band) for a marker byte, from the game's own
    code map so the two can never disagree."""
    from ..hardware import eeg_trigger as et
    name = et.name_of(code)
    band = et.band_of(code)
    notes = getattr(et, "CODE_NOTES", {})
    if name in notes:
        return name, notes[name][2], band
    finger = {0: "index", 1: "middle", 2: "ring", 3: "little"}
    for prefix, words in (("resp_correct_lane", "right press"),
                          ("resp_wrong_lane", "wrong finger"),
                          ("resp_anticipation_lane", "early press")):
        if name.startswith(prefix):
            lane = int(name[len(prefix):])
            hand = "left" if lane >= 4 else "right"
            return name, f"{words}: {hand} {finger[lane % 4]}", band
    for prefix, words in (("block_start_", "start of"),
                          ("block_end_", "end of")):
        if name.startswith(prefix):
            game = name[len(prefix):].replace("_", " ")
            return name, f"{words} a {game} block", band
    return name, "not in the code map", band


class Marker:
    __slots__ = ("t", "code", "name", "words", "band", "pulse_ms")

    def __init__(self, t: float, code: int) -> None:
        self.t = t
        self.code = code
        self.name, self.words, self.band = describe(code)
        self.pulse_ms: float | None = None


class ByteReceiver:
    """Reads the game's trigger bytes on a thread: from a TCP socket the
    game connects to, or from a serial port. Every byte is timestamped
    on arrival; a code is a marker and the 0 after it closes its pulse."""

    def __init__(self, listen_port: int = LISTEN_PORT,
                 serial_port: str | None = None) -> None:
        self.listen_port = int(listen_port)
        self.serial_port = serial_port
        self.markers: deque[Marker] = deque(maxlen=5000)
        self.state = "starting"
        self.peer = ""
        self.bytes_in = 0
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._open: Marker | None = None
        self._thread = threading.Thread(target=self._run, daemon=True,
                                        name="eeg-sim-rx")

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def clear(self) -> None:
        with self._lock:
            self.markers.clear()
            self._open = None

    def snapshot(self) -> list[Marker]:
        with self._lock:
            return list(self.markers)

    def feed(self, data: bytes, t: float | None = None) -> None:
        """Take bytes as the box would. Public so a test can drive it."""
        t = time.perf_counter() if t is None else t
        with self._lock:
            for b in data:
                self.bytes_in += 1
                if b == 0:
                    if self._open is not None:
                        self._open.pulse_ms = (t - self._open.t) * 1000.0
                        self._open = None
                    continue
                m = Marker(t, b)
                self.markers.append(m)
                self._open = m

    def _run(self) -> None:
        if self.serial_port:
            self._run_serial()
        else:
            self._run_socket()

    def _run_socket(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # On Windows SO_REUSEADDR lets a second simulator bind the same
        # port, and the game would feed whichever it reached; exclusive
        # use makes the second one say the port is taken instead.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        else:
            srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            srv.bind(("127.0.0.1", self.listen_port))
        except OSError as e:
            self.state = f"cannot listen on {self.listen_port}: {e}"
            return
        srv.listen(1)
        srv.settimeout(0.5)
        while not self._stop.is_set():
            self.state = "waiting"
            self.peer = f"127.0.0.1:{self.listen_port}"
            try:
                conn, _addr = srv.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            self.state = "connected"
            conn.settimeout(0.5)
            with conn:
                while not self._stop.is_set():
                    try:
                        data = conn.recv(4096)
                    except socket.timeout:
                        continue
                    except OSError:
                        break
                    if not data:
                        break
                    self.feed(data)
        srv.close()

    def _run_serial(self) -> None:
        try:
            import serial
        except ImportError:
            self.state = "pyserial is not installed"
            return
        while not self._stop.is_set():
            try:
                ser = serial.Serial(self.serial_port, 9600, timeout=0.2)
            except Exception as e:
                self.state = f"{self.serial_port}: {e}"
                time.sleep(1.0)
                continue
            self.state = "connected"
            self.peer = str(self.serial_port)
            with ser:
                while not self._stop.is_set():
                    try:
                        data = ser.read(256)
                    except Exception:
                        break
                    if data:
                        self.feed(data)


class FakeEEG:
    """Eight channels of made-up EEG, generated as the clock runs, with
    the markers' after-effects mixed in so a cue or a press lines up
    with something on the traces."""

    def __init__(self, seconds: float = max(SPANS), seed: int = 7) -> None:
        import numpy as np
        self.np = np
        self.n = int(seconds * RATE)
        self.data = np.zeros((len(CHANNELS), self.n))
        self.rng = np.random.default_rng(seed)
        self.sample = 0                   # samples generated so far
        self.t0 = time.perf_counter()
        self._drift = np.zeros(len(CHANNELS))
        self._alpha_amp = 1.0
        self._next_blink = 3.0
        # What is left of a blink that ran past the last stretch.
        self._blink_tail = np.zeros(0)
        # Alpha is strongest over the back of the head.
        self._alpha_gain = np.array([0.3, 0.4, 0.6, 0.6, 0.6, 1.0, 1.4, 1.4])

    def advance(self, now: float, markers: list[Marker]) -> None:
        np = self.np
        due = int((now - self.t0) * RATE)
        k = min(due - self.sample, self.n)
        if k <= 0:
            return
        if due - self.sample > self.n:
            # Longer away than the buffer holds (a long pause): only
            # the newest samples are made, stamped with their own time.
            self._blink_tail = np.zeros(0)
        t = (due - k + np.arange(k)) / RATE
        noise = self.rng.normal(0.0, 0.35, (len(CHANNELS), k))
        # Slow wander, a random walk pulled back to zero.
        steps = self.rng.normal(0.0, 0.03, (len(CHANNELS), k))
        walk = np.empty_like(steps)
        drift = self._drift.copy()
        for i in range(k):
            drift = drift * 0.995 + steps[:, i]
            walk[:, i] = drift
        self._drift = drift
        self._alpha_amp = min(1.6, max(0.4, self._alpha_amp
                                       + self.rng.normal(0.0, 0.05)))
        alpha = (self._alpha_amp * np.sin(2 * math.pi * 10.0 * t)
                 + 0.25 * np.sin(2 * math.pi * 21.0 * t + 1.0))
        block = noise + walk + np.outer(self._alpha_gain, alpha)
        # A blink every few seconds, big at the front of the head. One
        # frame is a handful of samples, so a blink runs on into the
        # next stretches rather than stopping at this one's end.
        if self._blink_tail.size:
            m = min(k, self._blink_tail.size)
            block[0, :m] += self._blink_tail[:m]
            block[1, :m] += self._blink_tail[:m] * 0.4
            self._blink_tail = self._blink_tail[m:]
        for j in range(k):
            ts = t[j]
            if ts >= self._next_blink:
                self._next_blink = ts + self.rng.uniform(3.0, 7.0)
                shape = np.hanning(int(0.3 * RATE)) * 7.0
                end = min(k, j + shape.size)
                block[0, j:end] += shape[: end - j]
                block[1, j:end] += shape[: end - j] * 0.4
                self._blink_tail = shape[end - j:]
        # After-effects of the markers in this stretch of time.
        for m in markers:
            dt = t - (m.t - self.t0)
            if dt[-1] < 0 or dt[0] > 0.8:
                continue
            if m.band in ("stim", "stim_pattern", "stim_choice"):
                bump = np.exp(-((dt - 0.30) ** 2) / (2 * 0.06 ** 2))
                block[5] += 3.0 * bump            # Pz
                block[3] += 1.8 * bump            # Cz
                early = np.exp(-((dt - 0.10) ** 2) / (2 * 0.03 ** 2))
                block[6:8] -= 1.5 * early         # O1, O2
            elif m.name.startswith("resp_wrong"):
                dip = np.exp(-((dt - 0.08) ** 2) / (2 * 0.03 ** 2))
                block[1] -= 3.0 * dip             # Fz
                block[3] -= 2.0 * dip             # Cz
        # Into the ring buffer.
        self.data = np.roll(self.data, -k, axis=1)
        self.data[:, -k:] = block
        self.sample = due


class SimulatorApp:
    W, H = 1280, 760
    PANEL_W = 380
    TOP = 64
    LEFT = 64

    def __init__(self, receiver: ByteReceiver) -> None:
        self.rx = receiver
        self.eeg = FakeEEG()
        self.gain = 1.0
        self.span_i = 1
        self.paused = False
        self.note = ""
        self._frozen_at: float | None = None

    # ---- geometry -------------------------------------------------------
    def trace_rect(self):
        import pygame
        return pygame.Rect(self.LEFT, self.TOP,
                           self.W - self.PANEL_W - self.LEFT - 20,
                           self.H - self.TOP - 62)

    def row_mid(self, i: int) -> int:
        r = self.trace_rect()
        rows = len(CHANNELS) + 1
        return int(r.y + (i + 0.5) * r.h / rows)

    # ---- drawing ----------------------------------------------------------
    def draw(self, surf, now: float) -> None:
        import pygame
        np = self.eeg.np
        bg, ink, muted = (248, 250, 252), (15, 23, 42), (100, 116, 139)
        surf.fill(bg)
        f_big = pygame.font.SysFont("Segoe UI,Helvetica Neue,Arial", 30,
                                    bold=True)
        f = pygame.font.SysFont("Segoe UI,Helvetica Neue,Arial", 17)
        f_small = pygame.font.SysFont("Segoe UI,Helvetica Neue,Arial", 14)
        f_bold = pygame.font.SysFont("Segoe UI,Helvetica Neue,Arial", 17,
                                     bold=True)
        title = f_big.render("EEG simulator", True, ink)
        surf.blit(title, (self.LEFT, 14))
        state = self.rx.state
        dot = ((22, 163, 74) if state == "connected"
               else (202, 138, 4) if state == "waiting" else (220, 38, 38))
        words = {"connected": f"Game connected ({self.rx.peer})",
                 "waiting": f"Waiting for the game on {self.rx.peer}",
                 "starting": "Starting"}.get(state, state)
        pygame.draw.circle(surf, dot, (self.LEFT + title.get_width() + 30,
                                       34), 7)
        surf.blit(f.render(words, True, ink),
                  (self.LEFT + title.get_width() + 44, 24))
        tag = f_small.render("Simulated EEG. Only the markers are real.",
                             True, muted)
        surf.blit(tag, (self.W - self.PANEL_W - 20 - tag.get_width(), 30))

        r = self.trace_rect()
        pygame.draw.rect(surf, (255, 255, 255), r, border_radius=10)
        pygame.draw.rect(surf, (226, 232, 240), r, 1, border_radius=10)
        span = SPANS[self.span_i]
        view_now = self._frozen_at if self.paused else now
        markers = self.rx.snapshot()
        px_per_s = r.w / span
        # One point per pixel column.
        n = int(span * RATE)
        cols = max(2, r.w)
        idx = np.linspace(self.eeg.n - n, self.eeg.n - 1, cols).astype(int)
        xs = np.linspace(r.x, r.right - 1, cols)
        rows = len(CHANNELS) + 1
        row_h = r.h / rows
        scale = row_h * 0.12 * self.gain
        for i, name in enumerate(CHANNELS):
            y0 = self.row_mid(i)
            ys = y0 - self.eeg.data[i, idx] * scale
            ys = np.clip(ys, y0 - row_h * 0.55, y0 + row_h * 0.55)
            pygame.draw.lines(surf, (30, 41, 59), False,
                              list(zip(xs.tolist(), ys.tolist())), 1)
            surf.blit(f_bold.render(name, True, muted), (16, y0 - 10))
        # The trigger channel: each code held for its pulse, as the
        # amplifier records it.
        ty = self.row_mid(len(CHANNELS))
        surf.blit(f_bold.render("Trig", True, muted), (16, ty - 10))
        base = ty + row_h * 0.35
        pygame.draw.line(surf, (148, 163, 184), (r.x, base), (r.right, base))
        chips = []
        for m in markers:
            x = r.right - (view_now - m.t) * px_per_s
            if x < r.x or x > r.right:
                continue
            colour = BAND_COLOURS.get(m.band, BAND_COLOURS["unknown"])
            pulse = (m.pulse_ms or 8.0) / 1000.0
            w = max(2, int(pulse * px_per_s))
            h = row_h * 0.6 * (m.code / 255.0) + 4
            pygame.draw.rect(surf, colour, (int(x), int(base - h), w, int(h)))
            # The line through every channel; its number goes on top.
            pygame.draw.line(surf, colour, (x, r.y + 4), (x, base), 1)
            chips.append((x, colour, m.code))
        # A press and its feedback land a frame apart, so a number that
        # would cover the one before it drops to the next row down.
        for x, colour, code, top in stack_labels(
                chips, lambda c: f_small.size(str(c))[0] + 8, r.y + 4):
            lab = f_small.render(str(code), True, (255, 255, 255))
            chip = pygame.Rect(0, 0, lab.get_width() + 8, 18)
            chip.midtop = (int(x), top)
            pygame.draw.rect(surf, colour, chip, border_radius=4)
            surf.blit(lab, lab.get_rect(center=chip.center))
        # Time axis.
        for s in range(int(span) + 1):
            x = r.right - s * px_per_s
            pygame.draw.line(surf, (226, 232, 240), (x, r.bottom - 6),
                             (x, r.bottom))
            if s % (1 if span <= 5 else 2 if span <= 10 else 5) == 0:
                t = f_small.render(f"-{s}s" if s else "now", True, muted)
                surf.blit(t, t.get_rect(midtop=(x, r.bottom + 4)))
        self._draw_panel(surf, markers, f, f_small, f_bold, f_big, ink,
                         muted)
        help_line = ("Space pause   Up/Down gain   Left/Right span   "
                     "C clear   S save   Esc quit")
        help_img = f_small.render(help_line, True, muted)
        surf.blit(help_img, (self.LEFT, self.H - 20))
        if self.note:
            # Where S saved to, or why it could not, beside the keys.
            x = self.LEFT + help_img.get_width() + 24
            text = _fit(self.note, f_small, self.W - 16 - x)
            surf.blit(f_small.render(text, True, ink), (x, self.H - 20))
        if self.paused:
            p = f_bold.render("PAUSED", True, (220, 38, 38))
            surf.blit(p, (r.right - p.get_width() - 10, r.y + 26))

    def _draw_panel(self, surf, markers, f, f_small, f_bold, f_big, ink,
                    muted) -> None:
        import pygame
        x = self.W - self.PANEL_W
        panel = pygame.Rect(x, self.TOP, self.PANEL_W - 16,
                            self.H - self.TOP - 62)
        pygame.draw.rect(surf, (255, 255, 255), panel, border_radius=10)
        pygame.draw.rect(surf, (226, 232, 240), panel, 1, border_radius=10)
        px, y = panel.x + 16, panel.y + 12
        surf.blit(f_small.render("LAST MARKER", True, muted), (px, y))
        y += 22
        if markers:
            m = markers[-1]
            colour = BAND_COLOURS.get(m.band, BAND_COLOURS["unknown"])
            code = f_big.render(str(m.code), True, colour)
            surf.blit(code, (px, y))
            name = f_bold.render(m.name, True, ink)
            surf.blit(name, (px + code.get_width() + 12, y + 2))
            y += 38
            for line in _wrap(m.words, f, panel.w - 32)[:2]:
                surf.blit(f.render(line, True, ink), (px, y))
                y += 20
        else:
            surf.blit(f.render("None yet. Start a game.", True, muted),
                      (px, y))
            y += 40
        y += 8
        # Counts by kind, and the pulse the box would hold.
        bands = Counter(m.band for m in markers)
        pulses = [m.pulse_ms for m in markers if m.pulse_ms is not None]
        surf.blit(f_small.render(f"MARKERS  {len(markers)}", True, muted),
                  (px, y))
        if pulses:
            mean = sum(pulses) / len(pulses)
            pl = f_small.render(f"pulse {mean:.1f} ms", True, muted)
            surf.blit(pl, (panel.right - 16 - pl.get_width(), y))
        y += 20
        col = 0
        for band, n in sorted(bands.items(), key=lambda kv: -kv[1]):
            colour = BAND_COLOURS.get(band, BAND_COLOURS["unknown"])
            cx = px + col * (panel.w // 2 - 8)
            pygame.draw.circle(surf, colour, (cx + 5, y + 9), 5)
            surf.blit(f.render(f"{BAND_WORDS.get(band, band)} {n}", True,
                               ink), (cx + 16, y))
            col += 1
            if col == 2:
                col = 0
                y += 22
        if col:
            y += 22
        y += 8
        # The latest markers, newest first.
        surf.blit(f_small.render("RECENT", True, muted), (px, y))
        y += 20
        t0 = markers[0].t if markers else 0.0
        for m in reversed(markers):
            if y > panel.bottom - 24:
                break
            colour = BAND_COLOURS.get(m.band, BAND_COLOURS["unknown"])
            t = f_small.render(f"{m.t - t0:7.2f}s", True, muted)
            surf.blit(t, (px, y + 2))
            code = f_bold.render(f"{m.code:>3}", True, colour)
            surf.blit(code, (px + 70, y))
            words = _fit(m.words, f_small, panel.w - 32 - 110)
            surf.blit(f_small.render(words, True, ink), (px + 110, y + 2))
            y += 21

    # ---- input and the loop ------------------------------------------------
    def handle_key(self, key) -> bool:
        import pygame
        if key == pygame.K_ESCAPE:
            return False
        if key == pygame.K_SPACE:
            self.paused = not self.paused
            self._frozen_at = time.perf_counter() if self.paused else None
        elif key == pygame.K_UP:
            self.gain = min(4.0, self.gain * 1.25)
        elif key == pygame.K_DOWN:
            self.gain = max(0.25, self.gain / 1.25)
        elif key == pygame.K_RIGHT:
            self.span_i = min(len(SPANS) - 1, self.span_i + 1)
        elif key == pygame.K_LEFT:
            self.span_i = max(0, self.span_i - 1)
        elif key == pygame.K_c:
            self.rx.clear()
        elif key == pygame.K_s:
            try:
                path = save_csv(self.rx.snapshot(), save_folder())
                try:
                    shown = "~/" + path.relative_to(Path.home()).as_posix()
                except ValueError:
                    shown = str(path)
                self.note = f"Saved {shown}"
            except OSError as e:
                self.note = f"Could not save: {e}"
        return True

    def window_plan(self, desktops: list[tuple[int, int]]
                    ) -> tuple[int, tuple[int, int]]:
        """(display, window size). With a second screen the simulator
        takes it at full size, leaving the game the first. On one
        screen it opens at most two thirds of the screen wide, in
        proportion, and the window can be dragged to any size: the
        picture scales to fit."""
        if len(desktops) > 1:
            w, h = desktops[1]
            scale = min(1.0, (w - 40) / self.W, (h - 80) / self.H)
            return 1, (int(self.W * scale), int(self.H * scale))
        if desktops:
            w, h = desktops[0]
            scale = min(1.0, (w * 2 // 3) / self.W, (h - 80) / self.H)
            return 0, (int(self.W * scale), int(self.H * scale))
        return 0, (self.W, self.H)

    def run(self) -> int:
        import os
        import pygame
        os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
        pygame.init()
        try:
            desktops = list(pygame.display.get_desktop_sizes())
        except Exception:
            desktops = []
        display, size = self.window_plan(desktops)
        try:
            window = pygame.display.set_mode(size, pygame.RESIZABLE,
                                             display=display)
        except Exception:
            window = pygame.display.set_mode(size, pygame.RESIZABLE)
        pygame.display.set_caption("EEG simulator")
        # Drawn at its own size, then scaled to whatever the window is.
        canvas = pygame.Surface((self.W, self.H))
        clock = pygame.time.Clock()
        self.rx.start()
        running = True
        while running:
            for e in pygame.event.get():
                if e.type == pygame.QUIT:
                    running = False
                elif e.type == pygame.KEYDOWN:
                    running = self.handle_key(e.key)
            now = time.perf_counter()
            if not self.paused:
                self.eeg.advance(now, self.rx.snapshot()[-50:])
            self.draw(canvas, now)
            window = pygame.display.get_surface()
            if window.get_size() == canvas.get_size():
                window.blit(canvas, (0, 0))
            else:
                window.fill((248, 250, 252))
                ww, wh = window.get_size()
                scale = min(ww / self.W, wh / self.H)
                fit = (max(1, int(self.W * scale)),
                       max(1, int(self.H * scale)))
                window.blit(pygame.transform.smoothscale(canvas, fit),
                            ((ww - fit[0]) // 2, (wh - fit[1]) // 2))
            pygame.display.flip()
            clock.tick(60)
        self.rx.stop()
        pygame.quit()
        return 0


def stack_labels(chips, width_of, top: int, rows: int = 3,
                 row_h: int = 20, gap: int = 2):
    """(x, colour, code, y) for each chip, left to right: the first row
    where it clears the chip before it, or else the row that frees up
    soonest."""
    ends = [float("-inf")] * rows
    out = []
    for x, colour, code in sorted(chips, key=lambda c: c[0]):
        w = width_of(code)
        left = x - w / 2
        row = next((i for i in range(rows) if left >= ends[i] + gap),
                   min(range(rows), key=lambda i: ends[i]))
        ends[row] = x + w / 2
        out.append((x, colour, code, top + row * row_h))
    return out


def _fit(text: str, font, width: int) -> str:
    if font.size(text)[0] <= width:
        return text
    while text and font.size(text + "...")[0] > width:
        text = text[:-1]
    return text + "..."


def _wrap(text: str, font, width: int) -> list[str]:
    words, lines, line = text.split(), [], ""
    for w in words:
        trial = (line + " " + w).strip()
        if font.size(trial)[0] <= width:
            line = trial
        else:
            if line:
                lines.append(line)
            line = w
    if line:
        lines.append(line)
    return lines


def save_folder() -> Path:
    """Where S saves: the app's own fallback data folder, the same on
    every PC and never inside the repository or the lab's sessions."""
    return Path.home() / "Finger Rehab Data" / "EEG simulator"


def save_csv(markers: list[Marker], folder: Path) -> Path:
    """The markers so far, one row each, for checking against a run."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / time.strftime("eeg_simulator_%Y-%m-%d_%H%M%S.csv")
    t0 = markers[0].t if markers else 0.0
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["seconds", "code", "name", "meaning", "band",
                    "pulse_ms"])
        for m in markers:
            w.writerow([f"{m.t - t0:.4f}", m.code, m.name, m.words, m.band,
                        "" if m.pulse_ms is None else f"{m.pulse_ms:.2f}"])
    return path


def main(listen_port: int = LISTEN_PORT, serial_port: str | None = None) -> int:
    return SimulatorApp(ByteReceiver(listen_port, serial_port)).run()
