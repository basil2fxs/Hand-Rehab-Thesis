"""The internal report: the marker checks Welber Marinovic asked for
(9 October 2026) before any effect is read, laid out like a short
student report. Numbered sections, the results in plain words, numbered
figures and tables, and the processing steps the thesis needs. Drawn
straight to PDF; the full analysis stays in detail/."""
from __future__ import annotations

import itertools
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import findings as FD

# the games' colours, as on the results page
GAME = {"reaction": "#ea580c", "buzz": "#7c3aed"}
INK, SOFT, MUTED, LINE = "#111827", "#374151", "#6b7280", "#9ca3af"
RED, GREY, LILAC = "#dc2626", "#9ca3af", "#c4b5fd"
# Arial ships its regular and bold as separate files, which matplotlib
# needs to tell the two weights apart (it reads only one face of a .ttc)
FONTS = ["Arial", "DejaVu Sans"]
A4 = (8.27, 11.69)
X0, W = 0.08, 0.84          # the text column, in page units

# A flat sketch of the cap from above (nose up, left ear on the left),
# close enough to show where each electrode sits.
SPOT = {"FCz": (0.0, 0.21), "Cz": (0.0, 0.0), "CPz": (0.0, -0.21), "Pz": (0.0, -0.42),
        "O1": (-0.3, -0.8), "O2": (0.3, -0.8), "C3": (-0.42, 0.0), "CP3": (-0.42, -0.21)}
RT_TEST = "RT, buzz minus reaction"
SIZE_TEST = "P3 300-650 ms, buzz minus reaction"
TIME_TEST = "P3 latency, buzz minus reaction"


def _subject(s: dict) -> str:
    """The subject's code; the report never prints a name."""
    return s.get("subject") or "EEG Subject"


def _date(s: dict) -> str:
    import datetime as _dt
    try:
        d = _dt.date.fromisoformat(s.get("date") or "")
    except ValueError:
        return s.get("date_long", "")
    return f"{d.day} {d.strftime('%B')}"


def _p(v) -> str:
    return "p " + FD.p_text(v)


@lru_cache(maxsize=None)
def _width(s: str, size: float, bold: bool) -> float:
    """Printed width of a string, in page units."""
    from matplotlib.font_manager import FontProperties
    from matplotlib.textpath import TextPath
    if not s.strip():
        return 0.0
    prop = FontProperties(family=FONTS, weight="bold" if bold else "normal")
    return TextPath((0, 0), s, size=size, prop=prop).get_extents().x1 / 72 / A4[0]


def _wrap(text: str, size: float, bold: bool, first: float, rest: float) -> list[str]:
    words = []
    for word in text.split():
        if words and words[-1].endswith(("Figure", "Figures", "Table")):
            words[-1] += " " + word
        else:
            words.append(word)
    lines, cur = [], ""
    for word in words:
        trial = f"{cur} {word}" if cur else word
        if cur and _width(trial, size, bold) > (first if not lines else rest):
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return lines + [cur] if cur else lines


# ---- the page ----------------------------------------------------------------
class Page:
    """One A4 page filled from the top down: text wraps to the column and
    each figure takes the space it asks for."""

    def __init__(self, number: int):
        import matplotlib.pyplot as plt
        self.fig = plt.figure(figsize=A4)
        self.ov = self.fig.add_axes([0, 0, 1, 1], zorder=-1)
        self.ov.set_xlim(0, 1)
        self.ov.set_ylim(0, 1)
        self.ov.axis("off")
        self.y = 0.95
        self.text(0.5, 0.03, str(number), 8, colour=MUTED, ha="center")

    def text(self, x, y, s, size=10.0, bold=False, colour=INK, **kw):
        self.ov.text(x, y, s, fontsize=size, color=colour,
                     fontweight="bold" if bold else "normal", **kw)

    def write(self, s, size=10.0, bold=False, colour=INK, x=X0, width=W, lead=None, after=0.006):
        """Text at the cursor, wrapped to the column; lead is (words,
        colour) set in bold at the start."""
        space = size * 0.28 / 72 / A4[0]
        lw = _width(lead[0], size, True) + space if lead else 0.0
        step = size * 1.35 / 72 / A4[1]
        for k, line in enumerate(_wrap(s, size, bold, width - lw, width) or [""]):
            if k == 0 and lead:
                self.text(x, self.y, lead[0], size, True, lead[1], va="top")
            self.text(x + (lw if k == 0 else 0.0), self.y, line, size, bold, colour, va="top")
            self.y -= step
        self.y -= after

    def bullet(self, label, s):
        """A result line: what it is in bold, then what happened."""
        self.text(X0 + 0.006, self.y, "•", 10, va="top")
        self.write(s, x=X0 + 0.026, width=W - 0.026, lead=(label, INK), after=0.004)

    def heading(self, number, title):
        self.y -= 0.014
        self.text(X0, self.y, str(number), 14, True, va="top")
        self.write(title, 14, True, x=X0 + 0.035, width=W - 0.035, after=0.008)

    def take(self, h) -> float:
        """Room for a figure: the bottom of the space it gets."""
        self.y -= h
        return self.y

    def caption(self, n, s):
        self.y -= 0.008
        self.write(s, 9, colour=SOFT, lead=(f"Figure {n}.", INK), after=0.02)

    def table(self, n, caption, rows, widths, header, right=()):
        """A table under its caption: a bold header, cells wrapped to their
        column widths (page units), a light rule under each row; columns
        in right are right-aligned."""
        self.write(caption, 9, colour=SOFT, lead=(f"Table {n}.", INK), after=0.006)
        step, pad = 9 * 1.35 / 72 / A4[1], 0.012

        def rule():
            self.ov.plot([X0, X0 + sum(widths)], [self.y, self.y], color=LINE, lw=0.6)
        rule()
        for k, row in enumerate([header] + rows):
            bold = k == 0
            cells = [_wrap(str(c), 9, bold, w - pad, w - pad) or [""] for c, w in zip(row, widths)]
            x = X0
            for j, (lines, w) in enumerate(zip(cells, widths)):
                for i, line in enumerate(lines):
                    at = (x + w - pad, "right") if j in right else (x, "left")
                    self.text(at[0], self.y - 0.005 - i * step, line, 9, bold, INK if bold else SOFT,
                              va="top", ha=at[1])
                x += w
            self.y -= max(len(c) for c in cells) * step + 0.01
            rule()
        self.y -= 0.02

    def axes(self, x, y, w, h):
        ax = self.fig.add_axes([x, y, w, h])
        ax.set_facecolor("none")
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color(LINE)
        ax.tick_params(labelsize=8, colors=SOFT, length=3, color=LINE)
        return ax

    def head(self, x, y, chans, place, colour=INK, w=0.06):
        """A small head from above, the electrodes marked, the place in
        words and the electrode codes underneath."""
        from matplotlib.patches import Circle, Ellipse
        ax = self.fig.add_axes([x, y, w, w * A4[0] / A4[1]])
        ax.add_patch(Circle((0, 0), 1, fill=False, ec=INK, lw=1.1))
        ax.plot([-0.15, 0, 0.15], [0.99, 1.18, 0.99], color=INK, lw=1.1)
        for side in (-1, 1):
            ax.add_patch(Ellipse((side * 1.05, 0), 0.12, 0.36, fill=False, ec=INK, lw=1.1))
        for ch in chans:
            ax.scatter(*SPOT[ch], s=34, color=colour, zorder=3, lw=0)
        ax.set_xlim(-1.25, 1.25)
        ax.set_ylim(-1.25, 1.25)
        ax.set_aspect("equal")
        ax.axis("off")
        self.text(x + w / 2, y - 0.004, place, 8, colour=SOFT, ha="center", va="top")
        self.text(x + w / 2, y - 0.018, ", ".join(chans), 7.5, colour=MUTED, ha="center", va="top")


def _wave(ax, ms, series, shade=None, tag="", xlabel="") -> None:
    """Signal over time in seconds: 0 (dashed) is the marker."""
    from matplotlib.ticker import MaxNLocator, MultipleLocator
    t = np.asarray(ms) / 1000
    if shade:
        ax.axvspan(*shade, color=GREY, alpha=0.2, lw=0)
        ax.text(sum(shade) / 2, 1.0, tag, transform=ax.get_xaxis_transform(), ha="center",
                va="bottom", fontsize=7.5, color=MUTED)
    ax.axhline(0, color=LINE, lw=0.8)
    ax.axvline(0, color=INK, lw=1.0, ls=(0, (3, 3)))
    for y, colour, label, style in series:
        ax.plot(t, y, color=colour, lw=2.0 if style == "-" else 1.6, ls=style, label=label)
    lo = min(float(np.min(y)) for y, *_ in series)
    hi = max(float(np.max(y)) for y, *_ in series)
    ax.set_ylim(lo - 0.35 * (hi - lo), hi + 0.35 * (hi - lo))
    # snap the ends to the nearest 0.1 s so the first and last ticks show
    ax.set_xlim(*[round(v * 10) / 10 if abs(v * 10 - round(v * 10)) < 0.05 else v for v in (t[0], t[-1])])
    ax.xaxis.set_major_locator(MultipleLocator(0.1))
    ax.yaxis.set_major_locator(MaxNLocator(4, integer=True))
    ax.set_ylabel("µV", fontsize=8.5, color=SOFT)
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=8.5, color=SOFT)
    ax.legend(frameon=False, fontsize=8, loc="lower right", bbox_to_anchor=(1.0, 1.0),
              ncols=len(series), borderaxespad=0.2, handlelength=1.6)


def _mark(ax, peak, label, colour, dy=6) -> None:
    """A dot on a peak and its name and latency beside it."""
    ms, uv = peak
    ax.scatter([ms / 1000], [uv], s=26, color=colour, edgecolor="white", lw=1.2, zorder=5)
    ax.annotate(f"{label} {ms:.0f} ms".strip(), (ms / 1000, uv), xytext=(5, dy if uv >= 0 else -dy),
                textcoords="offset points", fontsize=8, fontweight="bold", color=colour,
                va="bottom" if uv >= 0 else "top")


# ---- 1: the markers against the log ---------------------------------------------
def _markers(pg: Page, c: dict, figs, tabs, secs) -> None:
    from matplotlib.ticker import MaxNLocator
    g, rt, od = c["gaps"], c["rt"], c["order"]
    pg.heading(next(secs), "Markers against the log")
    rows = [[name, f"{eeg:,}", f"{log:,}"] for name, eeg, log in c["counts"]]
    pg.table(next(tabs), "Markers in the EEG against trials in the game's log. Buzz Hunt's 3 "
             "catch trials have no buzz.", rows, [0.3, 0.13, 0.13], ["Marker", "EEG", "Log"],
             right=(1, 2))
    n1, n2 = next(figs), next(figs)
    ff = g["flash_flash"]
    inside = np.mean((ff >= 0.6) & (ff <= 0.9)) * 100
    bb = g["buzz_buzz"]
    usual = int(((bb >= 5.3) & (bb <= 6.8)).sum())
    pg.bullet("Timing:", f"every marker sits within {c['timing_max_ms']:.1f} ms of the time the game "
                         f"logged (SD {c['timing_sd_ms']:.2f} ms).")
    pg.bullet("Gaps:", f"flash to flash {inside:.0f}% within 0.6 to 0.9 s, as it includes the "
                       f"reaction time. Press to next flash is constant at "
                       f"{np.median(g['press_next']):.2f} s ({np.median(g['press_next_practice']):.2f} s "
                       f"in practice, which adds 0.2 s of feedback). Localisation buzzes: {usual} of "
                       f"{len(bb)} gaps within 5.3 to 6.8 s; two longer ones span a catch trial, one "
                       f"follows a miss (Figure {n1}).")
    pg.bullet("Reaction times:", f"EEG and log agree (r = {rt['r']:.5f}; EEG {abs(rt['offset_ms']):.1f} ms "
                                 f"{'shorter' if rt['offset_ms'] < 0 else 'longer'}, SD "
                                 f"{rt['offset_sd_ms']:.1f} ms), using the press time each response "
                                 f"byte carries. The byte itself goes out when the trial closes, "
                                 f"{rt['byte_late_ms'][0]:.0f} to {rt['byte_late_ms'][2]:.0f} ms after "
                                 f"the press (Figure {n2}).")
    pg.bullet("Block and condition labels:", "the Reaction game sends no block or condition codes, as "
              "in the lab script; random vs pattern and blocks 1 to 8 come from the log. They sit on "
              f"the right trials: {od['lanes'][0]} of {od['lanes'][1]} response bytes name the "
              f"finger the log names, and every flash gap matches the log within "
              f"{od['gap_max_ms']:.0f} ms.")
    pg.y -= 0.03

    h = 0.13
    y0 = pg.take(h)
    ax = pg.axes(X0 + 0.05, y0 + 0.035, 0.36, h - 0.045)
    ax.axvspan(0.6, 0.9, color=GREY, alpha=0.2, lw=0)
    top = ax.hist(np.clip(ff, 0.4, 1.2), np.arange(0.4, 1.21, 0.02), color=GAME["reaction"],
                  label="flash to flash")[0].max()
    ax.set_ylim(0, top * 1.7)
    ax.yaxis.set_major_locator(MaxNLocator(4, integer=True))
    wait = float(np.median(g["press_next"]))
    ax.axvline(wait, color=INK, lw=1.4, label=f"press to next flash, {wait:.2f} s every time")
    ax.set_xlim(0.4, 1.2)
    ax.set_xlabel("Seconds", fontsize=8.5, color=SOFT)
    ax.set_ylabel("Count", fontsize=8.5, color=SOFT)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    pg.text(X0, y0 + h + 0.012, "(a) Reaction game", 9.5, True, va="top")
    ax = pg.axes(X0 + 0.52, y0 + 0.035, 0.32, h - 0.045)
    ax.axvspan(5.5, 6.7, color=GREY, alpha=0.2, lw=0)
    top = ax.hist(np.clip(bb, 4, 10), np.arange(4, 10.01, 0.2), color=GAME["buzz"],
                  label="buzz to buzz")[0].max()
    ax.set_ylim(0, top * 1.7)
    ax.yaxis.set_major_locator(MaxNLocator(4, integer=True))
    ax.set_xlim(4, 10)
    ax.set_xlabel("Seconds", fontsize=8.5, color=SOFT)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    pg.text(X0 + 0.47, y0 + h + 0.012, "(b) Buzz Hunt, localisation", 9.5, True, va="top")
    pg.caption(n1, "Grey band: the expected range. Gaps past the right edge are stacked on it. "
                   "The press-to-flash line leaves out practice.")

    h = 0.13
    y0 = pg.take(h)
    ax = pg.axes(X0 + 0.05, y0 + 0.035, 0.5, h - 0.045)
    bins = np.arange(-10, 40.01, 1.0)
    ax.hist(np.clip(rt["byte_minus_log"], -10, 40), bins, color=GREY, label="the byte itself")
    ax.hist(np.clip(rt["press_minus_log"], -10, 40), bins, color=GAME["reaction"],
            label="the press time it carries")
    ax.set_xlim(-10, 40)
    ax.set_xlabel("EEG minus log reaction time (ms)", fontsize=8.5, color=SOFT)
    ax.set_ylabel("Presses", fontsize=8.5, color=SOFT)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    pg.caption(n2, f"All {rt['n']} presses; differences past 40 ms are stacked on the right edge.")


# ---- 2: the early sensory responses ----------------------------------------------
def _sensory(pg: Page, c: dict, figs, secs) -> None:
    f, b = c["sensory"]["flash"], c["sensory"]["buzz"]
    n = next(figs)
    pg.heading(next(secs), "Early sensory responses")
    pg.bullet("Flash (O1, O2):", f"P1 at {f['P1'][0]:.0f} ms and N1 at {f['N1'][0]:.0f} ms, both sharp "
                                 "(usual P1: about 100 ms).")
    pg.bullet("Tone (Cz):", f"N1 at {f['Cz N1'][0]:.0f} ms and P2 at {f['Cz P2'][0]:.0f} ms (usual N1: "
                            "about 100 ms). The tone plays with the flash, so the two responses overlap "
                            "at Cz.")
    pg.bullet("Buzz (C3, CP3):", f"first peak at {b['first'][0]:.0f} ms and main negativity at "
                                 f"{b['neg'][0]:.0f} ms ({b['neg'][1]:.1f} µV), larger than over the "
                                 f"right side ({b['neg_right'][1]:.1f} µV). The marker is the motor "
                                 "command; the vibration starts 71 to 80 ms later (bench test).")
    pg.bullet("Random times:", "flat at every site.")
    pg.y -= 0.01

    from .checks import MOTOR_MS
    rows = [("(a) Flash", ["O1", "O2"], "back", f["ms"],
             [(f["O1/O2"], GAME["reaction"], "flash", "-"), (f["random O1/O2"], GREY, "random", "-")],
             [(f["P1"], "P1"), (f["N1"], "N1")], None, ""),
            ("(b) Tone", ["Cz"], "top", f["ms"],
             [(f["Cz"], GAME["reaction"], "flash and tone", "-"), (f["random Cz"], GREY, "random", "-")],
             [(f["Cz N1"], "N1"), (f["Cz P2"], "P2")], None, ""),
            ("(c) Buzz", ["C3", "CP3"], "left side", b["ms"],
             [(b["C3/CP3"], GAME["buzz"], "left", "-"), (b["C4/CP4"], LILAC, "right", "--"),
              (b["random C3/CP3"], GREY, "random", "-")],
             [(b["first"], ""), (b["neg"], "")], [m / 1000 for m in MOTOR_MS], "vibration starts")]
    for k, (title, chans, place, ms, series, peaks, shade, tag) in enumerate(rows):
        last = k == len(rows) - 1
        h = 0.18 if last else 0.16
        y0 = pg.take(h)
        bottom = y0 + (0.05 if last else 0.03)
        pg.head(X0, bottom + 0.02, chans, place, series[0][1])
        ax = pg.axes(X0 + 0.13, bottom, W - 0.13, 0.09)
        _wave(ax, ms, series, shade, tag, "Time after the marker (s)" if last else "")
        for peak, label in peaks:
            _mark(ax, peak, label or "peak", series[0][1])
        pg.text(X0, bottom + 0.118, title, 9.5, True, va="top")
    pg.caption(n, f"Averages over {f['n']} of {f['of']} flashes and {b['n']} of {b['of']} buzzes. "
                  "Grey: the same average at random times.")


# ---- 3: the error signal -------------------------------------------------------------
def _errors(pg: Page, c: dict, figs, secs) -> None:
    e = c["errors"]
    n = next(figs)
    pg.heading(next(secs), "Error signal (ERN), Reaction game")
    pg.bullet("Errors:", f"{e['of_error']} wrong-finger presses, {e['n_error']} kept after rejection "
                         "(an ERN needs 6 to 8).")
    pg.bullet("FCz:", f"errors dip to {e['ERN'][1]:.1f} µV {e['ERN'][0]:.0f} ms after the press, correct "
                      f"presses (CRN) to {e['CRN'][1]:.1f} µV at {e['CRN'][0]:.0f} ms; not yet a "
                      f"reliable difference ({_p(e['ern_test']['p'])}).")
    pg.bullet("Pz, CPz (Pe):", f"errors {e['pe_test']['diff']:+.1f} µV against correct presses 0.2 to "
                               f"0.4 s after the press ({_p(e['pe_test']['p'])}).")
    pg.y -= 0.01

    keep = e["ms"] >= -200
    ms = e["ms"][keep]
    pg.y -= 0.015
    h = 0.17
    y0 = pg.take(h)
    for k, (title, chans, place, key) in enumerate((("(a) ERN and CRN", ["FCz"], "top front", "FCz"),
                                                     ("(b) Pe", ["Pz", "CPz"], "top back", "Pz/CPz"))):
        x = X0 + k * 0.43
        pg.head(x, y0 + 0.06, chans, place, RED)
        ax = pg.axes(x + 0.1, y0 + 0.035, 0.3, h - 0.06)
        _wave(ax, ms, [(e[f"{key} error"][keep], RED, "error", "-"),
                       (e[f"{key} correct"][keep], INK, "correct", "-")],
              xlabel="Time after the press (s)")
        pg.text(x, y0 + h + 0.012, title, 9.5, True, va="top")
    pg.caption(n, "Locked to the press each response byte carries; the next flash comes "
                  f"{np.median(c['gaps']['press_next']):.2f} s after it. Baseline -0.4 to -0.2 s.")


# ---- 4: processing ---------------------------------------------------------------------
def _processing(pg: Page, c: dict, tabs, secs) -> None:
    f, b, e = c["sensory"]["flash"], c["sensory"]["buzz"], c["errors"]
    k = f["kept"]
    pattern = sum(v for name, v in k.items() if name.startswith("sequence"))
    bads = c["bads"]
    ica = c["ica"]
    pg.heading(next(secs), "Processing")
    rows = [
        ["Filters", "0.1 to 40 Hz band-pass (zero-phase FIR) and a 50 and 100 Hz notch. ICA fitted "
                    "on a 1 to 40 Hz copy."],
        ["Reference", "Common average."],
        ["Bad channels", f"Reaction: {', '.join(bads.get('srt', [])) or 'none'}. Buzz Hunt: "
                         f"{', '.join(bads.get('buzz_hunt', [])) or 'none'}. Flagged as flat, noisy or "
                         "unlike their neighbours (r under 0.4); rebuilt by spherical-spline "
                         "interpolation."],
        ["ICA", f"Picard, components to 99% of the variance ({ica['srt'][0]} and "
                f"{ica['buzz_hunt'][0]}). {ica['srt'][1]} and {ica['buzz_hunt'][1]} removed: those "
                "correlating with the eye channels (VEOG, HEOG) at |z| over 3."],
        ["Rejection", f"Epochs over 150 µV peak to peak after ICA dropped. Kept: flashes {f['n']} of "
                      f"{f['of']} (random practice {k.get('random_practice', 0)} of 48, pattern "
                      f"{pattern} of 800, random post-test {k.get('random_posttest', 0)} of 48); "
                      f"presses {e['n_correct']} of {e['of_correct']} correct, {e['n_error']} of "
                      f"{e['of_error']} wrong; buzzes {b['n']} of {b['of']}."],
        ["Baseline", "-0.2 to 0 s before the flash or buzz; -0.4 to -0.2 s before the press for the "
                     "error signal."],
        ["Conditions", "Random and pattern trials kept apart in every analysis."],
    ]
    pg.table(next(tabs), "Processing, both recordings (BioSemi, 64 channels, 512 Hz).", rows,
             [0.17, W - 0.17], ["Step", "What was done"])


# ---- the document ------------------------------------------------------------
def build(s: dict, out: Path, results: dict | None = None, cmp: dict | None = None,
          checks: dict | None = None) -> list[str]:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    if not checks:
        return []
    figs, tabs, secs = itertools.count(1), itertools.count(1), itertools.count(1)
    with plt.rc_context({"font.family": FONTS, "pdf.fonttype": 42, "axes.unicode_minus": False}):
        first = Page(1)
        first.write(_subject(s), 22, True, after=0.0)
        first.write(_date(s), 10, colour=MUTED, after=0.01)
        first.ov.plot([X0, X0 + W], [first.y, first.y], color=LINE, lw=0.8)
        _markers(first, checks, figs, tabs, secs)
        second = Page(2)
        _sensory(second, checks, figs, secs)
        third = Page(3)
        _errors(third, checks, figs, secs)
        _processing(third, checks, tabs, secs)
        pages = [first, second, third]
        path = out / "EEG_report.pdf"
        with PdfPages(path, metadata={"Title": f"{_subject(s)}, {_date(s)}"}) as pdf:
            for page in pages:
                pdf.savefig(page.fig)
                plt.close(page.fig)
    return [path.name]


def comparison_lines(s: dict) -> list[str]:
    """The comparison as one line of numbers, for the results page."""
    c = s.get("compare") or {}
    m, t = c.get("modes") or {}, c.get("tests") or {}
    r, b = m.get("reaction"), m.get("buzz")
    if not r or not b:
        return []

    def p(name):
        return FD.p_text((t.get(name) or {}).get("p"))
    return [f"Reaction vs Buzz Hunt: P3 at Pz/CPz {r['p3_uV']:+.1f} vs {b['p3_uV']:+.1f} µV "
            f"(p {p(SIZE_TEST)}); P3 half-area latency {r['p3_latency_ms']:.0f} vs "
            f"{b['p3_latency_ms']:.0f} ms (p {p(TIME_TEST)}); median RT {r['rt_ms']:.0f} vs "
            f"{b['rt_ms']:.0f} ms (p {p(RT_TEST)})."]
