"""Draw the EEG marker cheat sheet, dark and light, for the lab README.

Every number on the sheet is read from the marker map the game sends
(finger_rehab/hardware/eeg_trigger.py CODES and MODE_IDS) and the lab's
wire settings (config/eeg_lab.yaml), so the picture cannot drift from
what the game puts on the trigger lines. tests/test_eeg_cheat_sheet.py
fails when the committed pictures are older than the map.

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

from finger_rehab.hardware.eeg_trigger import (  # noqa: E402
    CODES, CODES_VERSION, MODE_IDS)

OUT = APP / "docs" / "images"
W, H = 980, 782
SANS = ("-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, "
        "Arial, sans-serif")
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

THEMES = {
    "dark": {
        "bg": "#0d1117", "card": "#161b22", "line": "#30363d",
        "ink": "#e6edf3", "muted": "#8b949e", "pill_ink": "#0d1117",
        "wait": "#f59e0b", "stim": "#60a5fa", "good": "#22c55e",
        "bad": "#f87171", "early": "#fb923c", "slow": "#9ca3af",
        "fb": "#a78bfa", "flow": "#9ca3af", "trace": "#8b949e",
    },
    "light": {
        "bg": "#ffffff", "card": "#f6f8fa", "line": "#d1d9e0",
        "ink": "#1f2328", "muted": "#59636e", "pill_ink": "#ffffff",
        "wait": "#b45309", "stim": "#1d4ed8", "good": "#15803d",
        "bad": "#dc2626", "early": "#c2410c", "slow": "#4b5563",
        "fb": "#6d28d9", "flow": "#4b5563", "trace": "#8c959f",
    },
}

# Game names as the hub shows them, for the 200+ and 220+ rows.
GAME_NAMES = {
    "srt": "Reaction (lab task)", "reaction": "Reaction", "rhythm": "Rhythm",
    "echo": "Echo", "force_pilot": "Force Pilot", "chords": "Chords",
    "buzz_hunt": "Buzz Hunt", "pattern": "Muscle Memory",
    "adaptive": "Adaptive", "syllables": "Syllables", "mirror": "Mirror",
}


def lab_wire() -> dict:
    eeg = (yaml.safe_load((APP / "config" / "eeg_lab.yaml").read_text(
        encoding="utf-8")) or {}).get("eeg") or {}
    return {"port": eeg.get("port"), "baud": eeg.get("baud"),
            "pulse_ms": eeg.get("pulse_ms"),
            "feedback": list(eeg.get("feedback_markers") or [])}


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
        """A code pill with its top-left at (x, y); returns its width."""
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
    s.text(x + 20, y + 32, title.upper(), size=13, weight=700, fill="muted",
           spacing="1.2")


def rows(s: Svg, x, y, items, gap=38) -> None:
    """Code pills down a card; an item may carry a second, quieter
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


def draw(theme: str) -> str:
    t = THEMES[theme]
    s = Svg(t)
    c = CODES
    wire = lab_wire()
    s.rect(0.5, 0.5, W - 1, H - 1, 18, "bg", "line")

    # Title.
    s.text(32, 50, "EEG markers", size=28, weight=800)
    s.text(32, 78, f"One byte on the trigger lines the moment something "
           f"happens, held {wire['pulse_ms']} ms, then 0. "
           f"{wire['port']}, {wire['baud']} baud.", size=15, fill="muted")
    vw = 18 + 8.4 * len(f"map v{CODES_VERSION}")
    s.rect(W - 32 - vw, 30, vw, 26, 13, "card", "line")
    s.text(W - 32 - vw / 2, 48, f"map v{CODES_VERSION}", size=14,
           weight=600, fill="muted", anchor="middle", font=MONO)

    # One trial on the recording.
    card(s, 24, 100, W - 48, 190, "One trial, as the recording sees it")
    trace(s, 48, W - 48, 226)
    lane_ring = 2
    for x, code, colour, cap, cap2 in (
            (190, c["prep_foreperiod"], "wait", "wait starts", "hand resting"),
            (420, c["stim_visual_buzz_tone"], "stim", "ring finger lights",
             "with a beep and a buzz"),
            (620, c["resp_correct_base"] + lane_ring, "good", "ring pressed",
             "right finger: 100 + 2"),
            (820, c["feedback_positive"], "fb", "full ring shown",
             "a hit, 0.8 s later")):
        flag(s, x, 146, 238, str(code), colour, cap, cap2)

    # The four families.
    y0, ch = 310, 252
    cw = (W - 48 - 3 * 16) / 4
    xs = [24 + i * (cw + 16) for i in range(4)]
    base = c["stim_visual"]
    card(s, xs[0], y0, cw, ch, "Before the press")
    rows(s, xs[0] + 20, y0 + 52, [
        (str(c["prep_foreperiod"]), "wait", "wait starts"),
        (str(c["stim_visual_buzz_tone"]), "stim", "finger lights",
         f"{base} + 1 beep + 2 buzz"),
        (str(c["stim_buzz_hunt"]), "stim", "Buzz Hunt buzz",
         "the buzz is the cue"),
    ])
    card(s, xs[1], y0, cw, ch, "The press")
    rows(s, xs[1] + 20, y0 + 52, [
        (f"{c['resp_correct_base']}+", "good", "right finger"),
        (f"{c['resp_wrong_base']}+", "bad", "wrong finger"),
        (f"{c['resp_anticipation_base']}+", "early", "too early"),
        (str(c["resp_timeout"]), "slow", "too slow"),
    ])
    card(s, xs[2], y0, cw, ch, "After the press")
    rows(s, xs[2] + 20, y0 + 52, [
        (str(c["feedback_positive"]), "fb", "full ring: hit"),
        (str(c["feedback_negative"]), "fb", "open ring: miss"),
        (str(c["feedback_neutral"]), "fb", "half ring: close"),
    ])
    fb_games = [GAME_NAMES.get(m, m) for m in wire["feedback"]
                if m in GAME_NAMES]
    lab_games = [g for g in fb_games if g != "Reaction"]
    s.text(xs[2] + 20, y0 + ch - 42, "Lab setup only, in", size=13,
           fill="muted")
    s.text(xs[2] + 20, y0 + ch - 24, " and ".join(lab_games) + ".",
           size=13, fill="muted")
    card(s, xs[3], y0, cw, ch, "Around the game")
    rows(s, xs[3] + 20, y0 + 52, [
        (str(c["prep_countdown"]), "flow", "GET READY"),
        (f"{c['block_start_base']}+", "flow", "game starts"),
        (f"{c['block_end_base']}+", "flow", "game ends"),
        (str(c["session_start"]), "flow", "first game"),
        (str(c["session_end"]), "flow", "End session"),
    ])

    # What the + means.
    y1 = 578
    card(s, 24, y1, W - 48, 64, "")
    s.text(44, y1 + 38, "The + is the finger:", size=15, weight=700)
    x = 214
    for k, name in enumerate(("index", "middle", "ring", "little")):
        w = s.pill(x, y1 + 18, str(k), "slow")
        s.text(x + w + 8, y1 + 37, name, size=15)
        x += w + 8 + 7.6 * len(name) + 20
    s.text(x + 4, y1 + 37, "4 to 7 are the left hand when both play.",
           size=14, fill="muted")

    # The lab task and the game numbers.
    y2 = 658
    half = (W - 48 - 16) / 2
    card(s, 24, y2, half, 104, "Reaction, the lab's SRT task")
    srt = MODE_IDS["srt"]
    x = 44
    for code, colour, label in (
            (str(c["block_start_base"] + srt), "flow", "start"),
            (str(base), "stim", "each red flash"),
            (str(c["block_end_base"] + srt), "flow", "end")):
        w = s.pill(x, y2 + 46, code, colour)
        s.text(x + w + 8, y2 + 65, label, size=14)
        x += w + 8 + 7.0 * len(label) + 18
    s.text(44, y2 + 94, "Nothing else per trial, as the lab's own script.",
           size=13, fill="muted")
    gx = 24 + half + 16
    card(s, gx, y2, half, 104, "Game numbers after 200+ and 220+")
    order = ("srt", "rhythm", "echo", "force_pilot", "chords", "buzz_hunt",
             "pattern", "adaptive")
    x, y = gx + 20, y2 + 62
    for mode in order:
        label = f"{MODE_IDS[mode]} {GAME_NAMES[mode].split(' (')[0]}"
        w = 14 + 7.4 * len(label)
        if x + w > gx + half - 16:
            x, y = gx + 20, y + 28
        s.rect(x, y - 16, w, 23, 7, "bg", "line")
        s.text(x + w / 2, y + 0.5, label, size=12.5, anchor="middle",
               fill="ink")
        x += w + 6
    return s.svg()


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        p = OUT / f"eeg_cheat_sheet_{theme}.svg"
        p.write_text(draw(theme), encoding="utf-8")
        print("wrote", p.relative_to(APP))
    return 0


if __name__ == "__main__":
    sys.exit(main())
