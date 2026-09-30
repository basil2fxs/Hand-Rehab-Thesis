"""Draw the EEG marker pictures for the lab README, dark and light.

Three pictures, each answering one question someone new to the lab
asks, in the order the README shows them:

  eeg_markers_how    how a number gets onto the EEG recording
  eeg_markers_where  where the numbers land: a lab sitting, one game in
                     it, one trial in that
  eeg_cheat_sheet    what every number the lab sitting sends means

Every number is read from the marker map the game sends
(finger_rehab/hardware/eeg_trigger.py CODES and MODE_IDS), the lab's
wire settings, and the lab sitting the game builds from
config/eeg_lab.yaml over config/default.yaml, so the pictures cannot
drift from what the game puts on the trigger lines.
tests/test_eeg_cheat_sheet.py fails when a committed picture is older
than the map.

Run from app/:  python3 scripts/make_eeg_cheat_sheet.py
Writes docs/images/<name>_dark.svg and _light.svg for all three.
"""
from __future__ import annotations

import math
import random
import sys
from pathlib import Path
from xml.sax.saxutils import escape

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))

import yaml  # noqa: E402

from finger_rehab.hardware.eeg_trigger import (  # noqa: E402
    CODES, CODES_VERSION, MODE_IDS)

OUT = APP / "docs" / "images"
W = 880
TITLE_H = 44
# Drawn on an 880 wide grid with 40 px margins, then shown with 12: the
# titles line up with the README's own text above each picture.
CROP = 28
SANS = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', "
        "Helvetica, Arial, sans-serif")
MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, monospace"

# GitHub's own greys and accents, so the pictures sit on the README
# page as if they were part of it. No background is drawn: the page
# shows through. One colour per kind of event, the same in all three
# pictures: blue a cue, green a press, purple the result, grey the
# frame around them.
THEMES = {
    "light": {
        "page": "#ffffff", "ink": "#1f2328", "muted": "#59636e",
        "faint": "#818b98", "line": "#d1d9e0", "soft": "#f6f8fa",
        "blue": "#0969da", "green": "#1a7f37", "red": "#cf222e",
        "amber": "#9a6700", "purple": "#8250df", "grey": "#59636e",
        "tint": "0.1",
    },
    "dark": {
        "page": "#0d1117", "ink": "#e6edf3", "muted": "#9198a1",
        "faint": "#656c76", "line": "#3d444d", "soft": "#151b23",
        "blue": "#4493f8", "green": "#3fb950", "red": "#f85149",
        "amber": "#d29922", "purple": "#ab7df8", "grey": "#9198a1",
        "tint": "0.16",
    },
}

# Game names as the lab says them.
GAME_NAMES = {
    "srt": "Reaction (lab)", "reaction": "Reaction", "rhythm": "Rhythm",
    "echo": "Echo", "force_pilot": "Force Pilot", "chords": "Chords",
    "buzz_hunt": "Buzz Hunt", "pattern": "Muscle Memory",
    "adaptive": "Adaptive", "syllables": "Syllables", "mirror": "Mirror",
}
FINGERS = ("index", "middle", "ring", "little")


def lab_wire() -> dict:
    eeg = (yaml.safe_load((APP / "config" / "eeg_lab.yaml").read_text(
        encoding="utf-8")) or {}).get("eeg") or {}
    return {"port": eeg.get("port"), "baud": eeg.get("baud"),
            "pulse_ms": eeg.get("pulse_ms"),
            "feedback": list(eeg.get("feedback_markers") or [])}


def lab_sitting() -> list[str]:
    """The games of a lab sitting in order A, as the game builds it:
    the study battery with the lab's swaps and leave-outs applied."""
    from finger_rehab.config import Config
    from finger_rehab.game import battery
    cfg = Config.load(str(APP / "config" / "eeg_lab.yaml"))
    raw = battery.load_preset(cfg, "study_battery") or {}
    steps = [battery.BatteryStep(mode=str(e["mode"]), hand="right",
                                 hand_requested="right",
                                 rest_before_s=float(bool(
                                     e.get("rest_before"))))
             for e in raw["orders"]["A"] if isinstance(e, dict)]
    steps = battery.swap_once(steps, dict(raw.get("swap_once") or {}))
    steps = battery.leave_out(steps, set(raw.get("leave_out") or ()))
    return [s.mode for s in steps]


def text_w(s: str, size: float, weight: int = 400) -> float:
    """Rough width of a line of the sans font, for layout only."""
    w = 0.0
    for ch in s:
        if ch in "iljtfr.,:;'!|() ":
            w += 0.31
        elif ch in "mwMW":
            w += 0.84
        elif ch.isupper():
            w += 0.66
        else:
            w += 0.54
    return w * size * (1.06 if weight >= 600 else 1.0)


class Svg:
    def __init__(self, t: dict, h: float, label: str) -> None:
        self.t = t
        self.h = h
        self.label = label
        self.parts: list[str] = []

    def c(self, key: str) -> str:
        return self.t.get(key, key)

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x, y, s, size=15, weight=400, fill="ink", anchor="start",
             font=SANS, spacing=None, note="") -> None:
        """A line of text. A note follows it in smaller grey type,
        spaced off the words' real width by the browser, whatever font
        the reader's system has."""
        sp = f' letter-spacing="{spacing}"' if spacing else ""
        tail = (f'<tspan dx="8" font-size="{size - 1.5}" '
                f'fill="{self.c("muted")}">{escape(note)}</tspan>'
                if note else "")
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" '
                 f'font-size="{size}" font-weight="{weight}" '
                 f'fill="{self.c(fill)}" text-anchor="{anchor}"{sp}>'
                 f'{escape(s)}{tail}</text>')

    def rect(self, x, y, w, h, r, fill="none", stroke=None, sw=1.0,
             fill_opacity=None) -> None:
        st = (f' stroke="{self.c(stroke)}" stroke-width="{sw}"'
              if stroke else "")
        fo = f' fill-opacity="{fill_opacity}"' if fill_opacity else ""
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
                 f'height="{h:.1f}" rx="{r}" fill="{self.c(fill)}"{fo}{st}/>')

    def line(self, x1, y1, x2, y2, stroke="line", sw=1.5) -> None:
        self.add(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" '
                 f'y2="{y2:.1f}" stroke="{self.c(stroke)}" '
                 f'stroke-width="{sw}" stroke-linecap="round"/>')

    def path(self, d, stroke="ink", sw=1.5, fill="none",
             fill_opacity=None) -> None:
        fo = f' fill-opacity="{fill_opacity}"' if fill_opacity else ""
        st = (f' stroke="{self.c(stroke)}" stroke-width="{sw}" '
              f'stroke-linejoin="round" stroke-linecap="round"'
              if stroke else "")
        self.add(f'<path d="{d}" fill="{self.c(fill)}"{fo}{st}/>')

    def circle(self, cx, cy, r, fill="none", stroke=None, sw=1.5) -> None:
        st = (f' stroke="{self.c(stroke)}" stroke-width="{sw}"'
              if stroke else "")
        self.add(f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r}" '
                 f'fill="{self.c(fill)}"{st}/>')

    def code(self, cx, cy, code, colour, size=16, pad=10) -> float:
        """A marker number in a soft pill centred on (cx, cy); returns
        the pill's width."""
        s = str(code)
        w = 2 * pad + 0.6 * size * len(s)
        h = size + 12
        self.rect(cx - w / 2, cy - h / 2, w, h, 7, colour,
                  fill_opacity=self.t["tint"])
        self.text(cx, cy + size * 0.36, s, size=size, weight=700,
                  fill=colour, anchor="middle", font=MONO)
        return w

    def title(self, words: str) -> None:
        """The picture's question, top left; everything drawn after it
        sits TITLE_H lower."""
        self.text(40, 30, words, size=18, weight=700)
        self.add(f'<g transform="translate(0,{TITLE_H})">')
        self.h += TITLE_H
        self._open = True

    def svg(self) -> str:
        if getattr(self, "_open", False):
            self.parts.append("</g>")
            self._open = False
        body = "\n".join(self.parts)
        vw = W - 2 * CROP
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{vw}" '
                f'height="{self.h}" viewBox="{CROP} 0 {vw} {self.h}" '
                f'role="img" aria-label="{escape(self.label)}">\n{body}'
                f'\n</svg>\n')


def trace(s: Svg, x0, x1, mid, amp=1.0, seed=3, colour="faint",
          sw=1.4) -> None:
    """A made-up EEG trace: slow waves plus noise, the same every run."""
    rnd = random.Random(seed)
    pts = []
    for i in range(int(x1 - x0) + 1):
        v = (math.sin(i * 0.19) * 3.5 + math.sin(i * 0.047) * 5
             + (rnd.random() - 0.5) * 6) * amp
        pts.append(f"{x0 + i:.0f},{mid + v:.1f}")
    s.add(f'<polyline points="{" ".join(pts)}" fill="none" '
          f'stroke="{s.c(colour)}" stroke-width="{sw}" '
          f'stroke-linejoin="round"/>')


def tiles(s: Svg, cx, bottom, lit: int, scale=1.0, colour="blue") -> None:
    """The game's four finger tiles, index to little, one lit."""
    heights = (30, 38, 34, 24)
    w, gap = 18 * scale, 8 * scale
    x = cx - (4 * w + 3 * gap) / 2
    for i, hh in enumerate(heights):
        h = hh * scale
        if i == lit:
            s.rect(x, bottom - h, w, h, 4 * scale, colour)
        else:
            s.rect(x, bottom - h, w, h, 4 * scale, "none", "faint",
                   sw=1.3)
        x += w + gap


def arrow(s: Svg, x1, x2, y, colour="faint") -> None:
    s.line(x1, y, x2 - 2, y, colour, 1.6)
    s.path(f"M{x2 - 9:.1f},{y - 5:.1f} L{x2:.1f},{y:.1f} "
           f"L{x2 - 9:.1f},{y + 5:.1f}", colour, 1.6)


# ---- 1. how a number gets onto the recording ------------------------

def draw_how(theme: str) -> str:
    t = THEMES[theme]
    wire = lab_wire()
    c = CODES
    cue = c["stim_visual_buzz_tone"]
    s = Svg(t, 222, "How a marker gets onto the EEG recording")
    s.title("How a number reaches the recording")
    x1, x2, x3 = 130, 440, 750

    # The game: a laptop showing the four finger tiles, one lit.
    s.rect(x1 - 62, 38, 124, 78, 9, "none", "ink", 1.6)
    tiles(s, x1, 104, 2)
    s.rect(x1 - 78, 121, 156, 8, 4, "line")

    # The marker box, drawing the pulse it puts on the line.
    s.rect(x2 - 48, 52, 96, 52, 11, "soft", "ink", 1.6)
    s.path(f"M{x2 - 30},90 H{x2 - 11} V66 H{x2 + 11} V90 H{x2 + 30}",
           "blue", 2.2)

    # The recording: three channels and the marker line across them.
    s.rect(x3 - 82, 38, 164, 78, 9, "soft", "line", 1.0)
    for i, y in enumerate((60, 78, 96)):
        trace(s, x3 - 70, x3 + 70, y, amp=0.55, seed=11 + i)
    mx = x3 + 16
    s.line(mx, 30, mx, 110, "blue", 2.0)
    s.code(mx, 18, cue, "blue")

    # The number travels left to right.
    for a, b, px, what in ((x1 + 88, x2 - 56, (x1 + x2) / 2 + 16, "USB"),
                           (x2 + 56, x3 - 90, (x2 + x3) / 2 - 16,
                            "trigger cable")):
        arrow(s, a, b, 78)
        s.code(px, 56, cue, "blue")
        s.text(px, 100, what, size=13, fill="muted", anchor="middle")

    for x, head, sub in ((x1, "Game", "a finger lights up"),
                         (x2, "Marker box", f"an Arduino on {wire['port']}"),
                         (x3, "EEG recording", f"{cue} marks that moment")):
        s.text(x, 158, head, size=16, weight=700, anchor="middle")
        s.text(x, 180, sub, size=14, fill="muted", anchor="middle")
    s.text(W / 2, 212, f"One number for each event, held "
           f"{wire['pulse_ms']} ms, then back to 0.", size=14,
           fill="muted", anchor="middle")
    return s.svg()


# ---- 2. where the numbers land ----------------------------------------

def draw_where(theme: str) -> str:
    t = THEMES[theme]
    c = CODES
    s = Svg(t, 408, "Where the numbers land: a lab sitting, one game, "
                    "one trial")
    s.title("Where the numbers land")
    left, right = 160, W - 40

    def row_label(y, name, sub) -> None:
        s.text(40, y - 3, name, size=12, weight=700, fill="muted",
               spacing="1.2")
        s.text(40, y + 15, sub, size=13, fill="faint")

    # Row A: the sitting.
    ya = 42
    row_label(ya, "SITTING", "order A")
    s.line(left, ya, right, ya, "line", 1.5)
    x = left
    w = s.code(x + 24, ya, c["session_start"], "grey")
    s.text(x + w / 2, ya + 34, "starts", size=12, fill="muted",
           anchor="middle")
    x += w + 10
    games = lab_sitting()
    zoom_game = "chords"
    shown = games[:games.index(zoom_game) + 1]
    za = zb = 0.0
    for g in shown:
        name = GAME_NAMES.get(g, g)
        gw = text_w(name, 13.5) + 22
        hot = g == zoom_game
        s.rect(x, ya - 16, gw, 32, 8, "soft", "ink" if hot else "line",
               1.5 if hot else 1.0)
        s.text(x + gw / 2, ya + 5, name, size=13.5,
               weight=600 if hot else 400, anchor="middle")
        if hot:
            za, zb = x, x + gw
        x += gw + 7
    more = len(games) - len(shown)
    s.text(x + 6, ya + 5, f"+ {more} more", size=13, fill="muted")
    w = 2 * 10 + 0.6 * 16 * len(str(c["session_end"]))
    s.code(right - w / 2, ya, c["session_end"], "grey")
    s.text(right - w / 2, ya + 34, "ends", size=12, fill="muted",
           anchor="middle")

    def zoom(x0, x1, y0, y1) -> None:
        s.path(f"M{x0:.1f},{y0} L{x1:.1f},{y0} L{right},{y1} "
               f"L{left},{y1} Z", None, fill="ink", fill_opacity="0.035")
        s.line(x0, y0, left, y1, "line", 1.0)
        s.line(x1, y0, right, y1, "line", 1.0)

    zoom(za, zb, ya + 17, 112)

    # Row B: one game.
    yb = 142
    row_label(yb, "GAME", GAME_NAMES[zoom_game])
    s.line(left, yb, right, yb, "line", 1.5)
    gid = MODE_IDS[zoom_game]
    x = left
    for code, cap in ((c["prep_countdown"], "get ready"),
                      (c["block_start_base"] + gid, "starts")):
        w = s.code(x + (2 * 10 + 0.6 * 16 * len(str(code))) / 2, yb,
                   code, "grey")
        s.text(x + w / 2, yb + 34, cap, size=12, fill="muted",
               anchor="middle")
        x += w + 12
    tx = x + 8
    n_trials, hot = 9, 3
    tb = (0.0, 0.0)
    for i in range(n_trials):
        on = i == hot
        s.rect(tx, yb - 12, 34, 24, 6, "soft", "ink" if on else "line",
               1.5 if on else 1.0)
        if on:
            tb = (tx, tx + 34)
        tx += 42
    s.text(tx + 2, yb + 5, "...", size=15, fill="muted")
    s.text((x + 8 + tx - 8) / 2, yb + 34, "trials", size=12, fill="muted",
           anchor="middle")
    end = c["block_end_base"] + gid
    w = 2 * 10 + 0.6 * 16 * len(str(end))
    s.code(right - w / 2, yb, end, "grey")
    s.text(right - w / 2, yb + 34, "ends", size=12, fill="muted",
           anchor="middle")

    zoom(tb[0], tb[1], yb + 13, 206)

    # Row C: one trial, drawn to time (400 px a second).
    yc, top = 290, 236
    row_label(yc - 30, "TRIAL", "a few seconds")
    trace(s, left, right, yc, amp=1.2, seed=3, colour="faint")
    px = 400.0
    x_cue = left + 90
    x_press = x_cue + 0.45 * px
    x_fb = x_press + 0.8 * px
    ring = 2
    for x, code, colour in ((x_cue, c["stim_visual_buzz_tone"], "blue"),
                            (x_press, c["resp_correct_base"] + ring, "green"),
                            (x_fb, c["feedback_positive"], "purple")):
        s.line(x, top + 14, x, yc + 20, colour, 2.0)
        s.code(x, top, code, colour)
    for a, b, words in ((x_cue, x_press, "reaction time"),
                        (x_press, x_fb, "0.8 s")):
        s.text((a + b) / 2, top + 4.5, words, size=12.5, fill="muted",
               anchor="middle")

    # What each moment looks like, then what it is.
    yp = 346
    tiles(s, x_cue, yp, ring, scale=0.62)
    s.rect(x_press - 20, yp - 3, 40, 5, 2.5, "green")
    s.rect(x_press - 7, yp - 27, 14, 22, 7, "none", "green", 1.8)
    s.circle(x_fb, yp - 12, 11, "purple")
    for x, head, sub in ((x_cue, "a finger lights up",
                          "light, beep and buzz"),
                         (x_press, "the ring finger presses",
                          "the correct one"),
                         (x_fb, "the result shows", "a full ring: a hit")):
        s.text(x, yp + 26, head, size=14, weight=600, anchor="middle")
        s.text(x, yp + 45, sub, size=13, fill="muted", anchor="middle")
    return s.svg()


# ---- 3. what each number means -------------------------------------------

def draw(theme: str) -> str:
    t = THEMES[theme]
    wire = lab_wire()
    c = CODES
    games = []
    for g in lab_sitting():
        if g not in games:
            games.append(g)
    fb_games = [GAME_NAMES.get(m, m) for m in wire["feedback"]
                if m in games]
    s = Svg(t, 756, "EEG marker cheat sheet: every number a lab sitting "
                    "sends, by what happened")
    vw = 16 + 8.4 * len(f"map v{CODES_VERSION}")
    s.rect(W - 40 - vw, 12, vw, 26, 13, "none", "line", 1.0)
    s.text(W - 40 - vw / 2, 29.5, f"map v{CODES_VERSION}", size=13,
           weight=600, fill="muted", anchor="middle", font=MONO)
    s.title("What each number means")

    x0, col = 210, 330
    pitch = 38

    def band(top, bottom, rng, name, colour) -> None:
        s.rect(40, top, 3.5, bottom - top, 1.75, colour)
        s.text(56, top + 15, rng, size=14, weight=700, fill=colour,
               font=MONO)
        s.text(56, top + 35, name, size=14, fill="muted")

    def item(x, y, code, colour, label, note="") -> None:
        w = s.code(x + (2 * 10 + 0.6 * 16 * len(str(code))) / 2, y, code,
                   colour)
        s.text(x + w + 10, y + 5, label, size=14.5, note=note)

    # 20s: set-up and timing, the moments with no cue of their own.
    top = 18
    band(top, top + 70, "20s", "set-up and timing", "grey")
    item(x0, top + 16, c["prep_countdown"], "grey", "GET READY")
    item(x0 + col, top + 16, c["prep_buzz_lead"], "grey",
         "buzz before a beat", "Rhythm")
    item(x0, top + 16 + pitch, c["prep_run_start"], "grey", "run starts",
         "Force Pilot")
    item(x0 + col, top + 16 + pitch, c["prep_segment_edge"], "grey",
         "wave changes", "Force Pilot")

    # 30s: the cue.
    top = 124
    band(top, top + 70, "30s", "a cue", "blue")
    item(x0, top + 16, c["stim_visual_buzz_tone"], "blue",
         "light, beep and buzz", "most games")
    item(x0 + col, top + 16, c["stim_visual_tone"], "blue",
         "light and beep", "Rhythm")
    item(x0, top + 16 + pitch, c["stim_visual"], "blue", "the red flash",
         GAME_NAMES["srt"])
    item(x0 + col, top + 16 + pitch, c["stim_buzz_hunt"], "blue",
         "a buzz alone", "Buzz Hunt")

    # 100s: the press, a grid of what happened by finger.
    top = 230
    band(top, top + 158, "100s", "a press", "green")
    cx0, step = x0 + 136, 72
    for i, f in enumerate(FINGERS):
        s.text(cx0 + i * step, top + 14, f, size=13, fill="muted",
               anchor="middle")
    for r, (base, colour, what) in enumerate((
            (c["resp_correct_base"], "green", "correct"),
            (c["resp_wrong_base"], "red", "wrong finger"),
            (c["resp_anticipation_base"], "amber", "too early"))):
        yy = top + 42 + r * pitch
        s.text(x0, yy + 5, what, size=14.5)
        for i in range(4):
            s.code(cx0 + i * step, yy, base + i, colour)
    xr = cx0 + 3 * step + 62
    item(xr, top + 42, c["resp_timeout"], "grey", "no press in time")
    item(xr, top + 42 + pitch, c["resp_idle"], "grey",
         "press between notes")
    s.text(x0, top + 150, "Left hand, when both hands play: the last "
           "digit is 4 to 7.", size=13, fill="muted")

    # 140s: the result.
    top = 424
    band(top, top + 62, "140s", "the result", "purple")
    for i, (code, label) in enumerate((
            (c["feedback_positive"], "full ring: hit"),
            (c["feedback_negative"], "open ring: miss"),
            (c["feedback_neutral"], "half ring: close"))):
        item(x0 + i * 214, top + 16, code, "purple", label)
    s.text(x0, top + 56, " and ".join(fb_games) + " only. In Force Pilot, "
           "141 is the force leaving its corridor.", size=13, fill="muted")

    # 200s: each game's start and end.
    top = 522
    band(top, top + 110, "200s", "a game", "grey")
    cw = (W - 40 - x0 - 50) / len(games)
    s.text(x0, top + 61, "starts", size=13, fill="muted")
    s.text(x0, top + 99, "ends", size=13, fill="muted")
    for i, g in enumerate(games):
        gx = x0 + 50 + cw * (i + 0.5)
        name, _, extra = GAME_NAMES.get(g, g).partition(" (")
        s.text(gx, top + 14, name, size=12.5, anchor="middle")
        if extra:
            s.text(gx, top + 29, "(" + extra, size=12, fill="muted",
                   anchor="middle")
        s.code(gx, top + 56, c["block_start_base"] + MODE_IDS[g], "grey",
               size=15, pad=8)
        s.code(gx, top + 94, c["block_end_base"] + MODE_IDS[g], "grey",
               size=15, pad=8)

    # 240s: the session.
    top = 668
    band(top, top + 70, "240s", "the session", "grey")
    for i, (code, label) in enumerate((
            (c["session_start"], "first game"),
            (c["pause"], "pause"),
            (c["rest_start"], "rest starts"),
            (c["session_end"], "session ends"),
            (c["resume"], "resume"),
            (c["rest_end"], "rest ends"))):
        item(x0 + (i % 3) * 214, top + 16 + (i // 3) * pitch, code, "grey",
             label)
    return s.svg()


PICTURES = {
    "eeg_markers_how": draw_how,
    "eeg_markers_where": draw_where,
    "eeg_cheat_sheet": draw,
}


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for name, fn in PICTURES.items():
        for theme in THEMES:
            p = OUT / f"{name}_{theme}.svg"
            p.write_text(fn(theme), encoding="utf-8")
            print("wrote", p.relative_to(APP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
