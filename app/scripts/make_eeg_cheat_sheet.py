"""Draw the EEG marker cheat sheet, dark and light, for the lab README.

One picture, kept to what most games send: a finger lights up, the
press, the result, and the numbers around each game. Every number is
read from the marker map the game sends (finger_rehab/hardware/
eeg_trigger.py CODES) and the lab's settings (config/eeg_lab.yaml), so
the picture cannot drift from what the game puts on the trigger lines.
The full map, with the numbers single games add, is saved with every
session as markers_codes.csv. tests/test_eeg_cheat_sheet.py fails when
the committed pictures are older than the map.

Run from app/:  python3 scripts/make_eeg_cheat_sheet.py
Writes docs/images/eeg_cheat_sheet_dark.svg and _light.svg.
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

from finger_rehab.hardware.eeg_trigger import CODES  # noqa: E402

OUT = APP / "docs" / "images"
W, H = 980, 632
SANS = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, "
        "Arial, sans-serif")
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

THEMES = {
    "dark": {
        "bg": "#0d1117", "card": "#161b22", "line": "#30363d",
        "ink": "#e6edf3", "muted": "#8b949e", "pill_ink": "#0d1117",
        "stim": "#60a5fa", "good": "#22c55e", "bad": "#f87171",
        "early": "#fb923c", "slow": "#9ca3af", "fb": "#a78bfa",
        "flow": "#9ca3af", "trace": "#8b949e",
    },
    "light": {
        "bg": "#ffffff", "card": "#f6f8fa", "line": "#d1d9e0",
        "ink": "#1f2328", "muted": "#59636e", "pill_ink": "#ffffff",
        "stim": "#1d4ed8", "good": "#15803d", "bad": "#dc2626",
        "early": "#c2410c", "slow": "#4b5563", "fb": "#6d28d9",
        "flow": "#4b5563", "trace": "#8c959f",
    },
}

# Game names as the hub shows them, for the note on the results.
GAME_NAMES = {
    "reaction": "Reaction", "rhythm": "Rhythm", "echo": "Echo",
    "force_pilot": "Force Pilot", "chords": "Chords",
    "buzz_hunt": "Buzz Hunt", "pattern": "Muscle Memory",
    "adaptive": "Adaptive", "syllables": "Syllables", "mirror": "Mirror",
}

# The ring finger, finger 2, carries the trial drawn.
RING = 2


def lab_config() -> dict:
    return yaml.safe_load((APP / "config" / "eeg_lab.yaml").read_text(
        encoding="utf-8")) or {}


def lab_feedback() -> list[str]:
    """The games whose results send a number in the lab build."""
    return list((lab_config().get("eeg") or {}).get("feedback_markers")
                or [])


class Svg:
    def __init__(self, t: dict) -> None:
        self.t = t
        self.parts: list[str] = []

    def add(self, s: str) -> None:
        self.parts.append(s)

    def text(self, x, y, s, size=15, weight=400, fill="ink", anchor="start",
             font=SANS, spacing=None) -> None:
        sp = f' letter-spacing="{spacing}"' if spacing else ""
        self.add(f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" '
                 f'font-size="{size}" font-weight="{weight}" '
                 f'fill="{self.t.get(fill, fill)}" text-anchor="{anchor}"'
                 f'{sp}>{escape(s)}</text>')

    def rect(self, x, y, w, h, r, fill, stroke=None) -> None:
        st = (f' stroke="{self.t.get(stroke, stroke)}" stroke-width="1"'
              if stroke else "")
        self.add(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
                 f'height="{h:.1f}" rx="{r}" fill="{self.t.get(fill, fill)}"'
                 f'{st}/>')

    def pill(self, x, y, code: str, colour: str, h=28) -> float:
        """A number pill with its top-left at (x, y); returns its width."""
        w = 18 + 9.6 * len(code)
        self.rect(x, y, w, h, 8, colour)
        self.text(x + w / 2, y + h / 2 + 5.5, code, size=16, weight=700,
                  fill="pill_ink", anchor="middle", font=MONO)
        return w

    def svg(self) -> str:
        body = "\n".join(self.parts)
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" '
                f'height="{H}" viewBox="0 0 {W} {H}" role="img" '
                f'aria-label="EEG marker cheat sheet">\n{body}\n</svg>\n')


def card(s: Svg, x, y, w, h, title: str) -> None:
    s.rect(x, y, w, h, 14, "card", "line")
    if title:
        s.text(x + 20, y + 32, title.upper(), size=13, weight=700,
               fill="muted", spacing="1.2")


def rows(s: Svg, x, y, items, gap=38) -> None:
    """Number pills down a card; an item may carry a second, quieter
    line under its label."""
    for code, colour, label, *more in items:
        w = s.pill(x, y, code, colour)
        s.text(x + w + 12, y + 19.5, label, size=15)
        if more:
            s.text(x + w + 12, y + 38, more[0], size=13, fill="muted")
            y += 18
        y += gap


def trace(s: Svg, x0, x1, mid, seed=3) -> None:
    rnd = random.Random(seed)
    pts = []
    for i in range(int(x1 - x0)):
        v = (math.sin(i * 0.19) * 4 + math.sin(i * 0.05) * 6
             + (rnd.random() - 0.5) * 7)
        pts.append(f"{x0 + i:.0f},{mid + v:.1f}")
    s.add(f'<polyline points="{" ".join(pts)}" fill="none" '
          f'stroke="{s.t["trace"]}" stroke-width="1.4" '
          f'stroke-linejoin="round" opacity="0.9"/>')


def flag(s: Svg, x, top, bottom, code: str, colour: str, caption: str,
         caption2: str = "") -> None:
    s.add(f'<line x1="{x}" y1="{top + 28}" x2="{x}" y2="{bottom}" '
          f'stroke="{s.t[colour]}" stroke-width="2.5"/>')
    w = 18 + 9.6 * len(code)
    s.pill(x - w / 2, top, code, colour)
    s.text(x, bottom + 22, caption, size=14, anchor="middle")
    if caption2:
        s.text(x, bottom + 40, caption2, size=13, fill="muted",
               anchor="middle")


def tiles(s: Svg, x, y, lit: int) -> None:
    """Four finger cards, the lit one in the cue's colour."""
    for k, h in enumerate((40, 48, 44, 34)):
        top = y + 48 - h
        if k == lit:
            s.rect(x + k * 30, top, 22, h, 5, "stim")
        else:
            s.add(f'<rect x="{x + k * 30:.1f}" y="{top:.1f}" width="22" '
                  f'height="{h}" rx="5" fill="none" '
                  f'stroke="{s.t["slow"]}" stroke-width="1.6"/>')


def draw(theme: str) -> str:
    t = THEMES[theme]
    s = Svg(t)
    c = CODES
    s.rect(0.5, 0.5, W - 1, H - 1, 18, "bg", "line")

    # Title.
    s.text(32, 50, "EEG markers", size=28, weight=800)
    s.text(32, 78, "One number on the recording the moment something "
           "happens, then back to 0.", size=15, fill="muted")

    # One trial on the recording: a finger lights up, the press, the
    # result.
    card(s, 24, 100, W - 48, 190, "One trial, as the recording sees it")
    trace(s, 48, W - 48, 226)
    for x, code, colour, cap, cap2 in (
            (230, c["stim_visual_buzz_tone"], "stim", "ring finger lights up",
             "with a beep and a buzz"),
            (490, c["resp_correct_base"] + RING, "good", "ring pressed",
             f"right finger: {c['resp_correct_base']} + {RING}"),
            (750, c["feedback_positive"], "fb", "result shown",
             "a hit, with the green flash")):
        flag(s, x, 146, 238, str(code), colour, cap, cap2)

    # The four families.
    y0, ch = 310, 216
    cw = (W - 48 - 3 * 16) / 4
    xs = [24 + i * (cw + 16) for i in range(4)]
    card(s, xs[0], y0, cw, ch, "The cue")
    rows(s, xs[0] + 20, y0 + 52, [
        (str(c["stim_visual_buzz_tone"]), "stim", "finger lights up",
         f"{c['stim_visual']} + 1 beep + 2 buzz"),
    ])
    tiles(s, xs[0] + 20, y0 + 128, RING)
    card(s, xs[1], y0, cw, ch, "The press")
    rows(s, xs[1] + 20, y0 + 52, [
        (f"{c['resp_correct_base']}+", "good", "right finger"),
        (f"{c['resp_wrong_base']}+", "bad", "wrong finger"),
        (f"{c['resp_anticipation_base']}+", "early", "too early"),
        (str(c["resp_timeout"]), "slow", "too slow"),
    ])
    card(s, xs[2], y0, cw, ch, "After the press")
    rows(s, xs[2] + 20, y0 + 52, [
        (str(c["feedback_positive"]), "fb", "result: hit"),
        (str(c["feedback_negative"]), "fb", "result: miss"),
    ])
    games = [GAME_NAMES[m] for m in lab_feedback()
             if m in GAME_NAMES and m != "reaction"]
    s.text(xs[2] + 20, y0 + ch - 36, "Lab setup only, in", size=13,
           fill="muted")
    s.text(xs[2] + 20, y0 + ch - 18, " and ".join(games) + ".",
           size=13, fill="muted")
    card(s, xs[3], y0, cw, ch, "Around the game")
    rows(s, xs[3] + 20, y0 + 52, [
        (str(c["prep_countdown"]), "flow", "GET READY"),
        (f"{c['block_start_base']}+", "flow", "game starts"),
        (f"{c['block_end_base']}+", "flow", "game ends"),
    ])

    # What the + means.
    y1 = y0 + ch + 18
    card(s, 24, y1, W - 48, 64, "")
    s.text(44, y1 + 38, "The + is the finger:", size=15, weight=700)
    x = 214
    for k, name in enumerate(("index", "middle", "ring", "little")):
        w = s.pill(x, y1 + 18, str(k), "slow")
        s.text(x + w + 8, y1 + 37, name, size=15)
        x += w + 8 + 7.6 * len(name) + 20
    return s.svg()


PICTURES = {"eeg_cheat_sheet": draw}


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
