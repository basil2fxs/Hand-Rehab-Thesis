"""The internal report: the results of the marker checks Welber
Marinovic asked for (9 October 2026), laid out like a short student
report, with the Reaction game's random and pattern trials apart in
every average. Results only: the answers to his questions go in the
reply, not here. Each section opens with a few plain words on what the
check is, and every table and figure says how to read it, for a reader
who knows the project but not EEG. Pages flow: a block that will not
fit opens the next page. Drawn straight to PDF; the full analysis
stays in detail/."""
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
KIND = {"pattern": ("#2563eb", "pattern"), "random": ("#d97706", "random")}   # the two trial types
# Arial ships its regular and bold as separate files, which matplotlib
# needs to tell the two weights apart (it reads only one face of a .ttc)
FONTS = ["Arial", "DejaVu Sans"]
A4 = (8.27, 11.69)
X0, W = 0.08, 0.84          # the text column, in page units
BOTTOM = 0.06               # a block never starts below this

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

    @staticmethod
    def height(s, size=10.0, bold=False, width=W, lead=None, after=0.006) -> float:
        """What write() would take, so a block can be kept together."""
        space = size * 0.28 / 72 / A4[0]
        lw = _width(lead[0], size, True) + space if lead else 0.0
        step = size * 1.35 / 72 / A4[1]
        return len(_wrap(s, size, bold, width - lw, width) or [""]) * step + after

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

    def bullet_height(self, label, s) -> float:
        return self.height(s, width=W - 0.026, lead=(label, INK), after=0.004)

    def lead(self, s):
        """A few plain words under a heading: what the section checks."""
        self.write(s, 10, colour=SOFT, after=0.01)

    def lead_height(self, s) -> float:
        return self.height(s, 10, after=0.01)

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

    def caption_height(self, n, s) -> float:
        return 0.008 + self.height(s, 9, lead=(f"Figure {n}.", INK), after=0.02)

    def table_height(self, n, caption, rows, widths, header) -> float:
        """What table() would take."""
        step, pad = 9 * 1.35 / 72 / A4[1], 0.012
        h = self.height(caption, 9, lead=(f"Table {n}.", INK), after=0.006)
        for k, row in enumerate([header] + rows):
            cells = [_wrap(str(c), 9, k == 0, w - pad, w - pad) or [""] for c, w in zip(row, widths)]
            h += max(len(c) for c in cells) * step + 0.01
        return h + 0.02

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


class Doc:
    """The pages, filled in order: need(h) hands back a page with at
    least h of room, opening the next page when the current one has
    less."""

    def __init__(self):
        self.pages: list[Page] = []
        self.pg = self.new_page()

    def new_page(self) -> Page:
        self.pg = Page(len(self.pages) + 1)
        self.pages.append(self.pg)
        return self.pg

    def need(self, h: float) -> Page:
        if self.pg.y - h < BOTTOM:
            self.new_page()
        return self.pg

    def heading(self, number, title, lead_text) -> Page:
        """A heading with its lead, never left alone at a page's foot."""
        pg = self.need(0.014 + 0.045 + self.pg.lead_height(lead_text) + 0.08)
        pg.heading(number, title)
        pg.lead(lead_text)
        return pg

    def bullet(self, label, s) -> Page:
        pg = self.need(self.pg.bullet_height(label, s))
        pg.bullet(label, s)
        return pg


def pg_caption_height(doc: Doc, n, s) -> float:
    return doc.pg.caption_height(n, s)


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
def _markers(doc: Doc, c: dict, figs, tabs, secs) -> None:
    from matplotlib.ticker import MaxNLocator
    g, rt, od = c["gaps"], c["rt"], c["order"]
    pg = doc.heading(next(secs), "Markers against the log",
                     "The game logs every event with its time and sends a numbered marker (one byte) "
                     "for it into the EEG recording, so both should hold the same events in the same "
                     "order at the same times. Table 1 counts them; the rest compares the times.")
    rows = [[r[0]] + [f"{v:,}" for v in r[1:]] for r in c["by_condition"]]
    buzzes = next(r for r in c["counts"] if r[0] == "Buzzes")
    stages = c["buzz_stages"]
    tn = next(tabs)
    cap = ("Reaction game markers in the recording, one row per stage: practice (random order), the "
           "pattern blocks (the hidden repeating order), the post-test (random again). Flashes counts "
           "the markers for a square lighting up; Correct, Wrong, Early and Missed count the response "
           "markers, what the player did on that flash. "
           + ("Every count equals the game's log." if c["by_condition_match"] else
              "Some counts differ from the game's log.")
           + f" Buzz Hunt: {buzzes[1]} buzz markers for {buzzes[2]} buzz trials ({stages.get('loc', 0)} "
           f"localisation, {stages.get('gap', 0)} gap, {stages.get('span', 0)} span), and none for its "
           f"{c['catch']} catch trials, which have no buzz.")
    widths = [0.27, 0.11, 0.11, 0.11, 0.11, 0.11]
    header = ["Condition", "Flashes", "Correct", "Wrong", "Early", "Missed"]
    pg = doc.need(pg.table_height(tn, cap, rows, widths, header))
    pg.table(tn, cap, rows, widths, header, right=(1, 2, 3, 4, 5))
    n1, n2 = next(figs), next(figs)
    q = c["queue"].values()
    halves = [x for v in c["timing_halves"].values() for x in v]
    clean = all(v["failed"] == 0 and v["dropped"] == 0 for v in q)
    wait = float(np.median(c["gaps"]["press_next"]))

    def span(x):
        return f"{np.percentile(x, 5):.2f} to {np.percentile(x, 95):.2f} s"
    bb = g["buzz_buzz"]
    usual = (bb >= 5.3) & (bb <= 6.8)
    doc.bullet("Timing:", f"every marker landed within {c['timing_max_ms']:.1f} ms of the time the game "
                          f"logged it (spread {min(halves):.1f} to {max(halves):.1f} ms in each half of "
                          "both recordings, so nothing drifted); flash and buzz markers left within "
                          f"{max(v['stim_wait_max_ms'] for v in q):.1f} ms of the screen flip or the "
                          "motor command" + ("; none failed or dropped." if clean else "."))
    doc.bullet("Gaps:", f"flash to flash {span(g['flash_flash_pattern'])} in pattern blocks and "
                        f"{span(g['flash_flash_random'])} in random blocks (5th to 95th percentile), "
                        f"since the next flash follows each press by a fixed {wait:.2f} s and random "
                        "blocks are pressed more slowly; localisation buzzes "
                        f"{bb[usual].min():.1f} to {bb[usual].max():.1f} s apart, {int((~usual).sum())} "
                        f"gaps longer (Figure {n1}).")
    doc.bullet("Reaction times:", "the reaction time read from the recording against the one in the log: "
                                  f"r = {rt['r']:.5f} (1 would be identical), offset {rt['offset_ms']:+.1f} "
                                  f"ms (spread {rt['offset_sd_ms']:.1f} ms), using the press time each "
                                  "response marker carries; the marker byte itself leaves "
                                  f"{rt['byte_late_ms'][0]:.0f} to {rt['byte_late_ms'][2]:.0f} ms after "
                                  f"the press, when the trial closes (Figure {n2}).")
    doc.bullet("Trial order:", f"the response marker names the same finger as the log on {od['lanes'][0]} "
                               f"of {od['lanes'][1]} trials, and the gaps between flashes match the log "
                               f"within {od['gap_max_ms']:.0f} ms, so no marker sits on the wrong trial.")

    h = 0.112
    cap1 = ("Time from one flash to the next (a) and from one buzz to the next (b). Each bar counts the "
            "gaps that fell in that range of seconds. In (a) blue is the pattern blocks and orange the "
            "random blocks; the grey band is the range the task is built to give. Gaps longer than the "
            "axis are stacked on its right edge; in (b) a long gap spans a trial with no buzz.")
    pg = doc.need(0.014 + h + pg.caption_height(n1, cap1))
    pg.y -= 0.014
    y0 = pg.take(h)
    ax = pg.axes(X0 + 0.05, y0 + 0.035, 0.36, h - 0.045)
    ax.axvspan(0.6, 0.9, color=GREY, alpha=0.2, lw=0)
    bins = np.arange(0.4, 1.31, 0.02)
    top = 0
    for kind in ("pattern", "random"):
        colour, label = KIND[kind]
        n = ax.hist(np.clip(g[f"flash_flash_{kind}"], 0.4, 1.3), bins, color=colour, alpha=0.85,
                    label=label)[0]
        top = max(top, n.max())
    ax.set_ylim(0, top * 1.6)
    ax.yaxis.set_major_locator(MaxNLocator(4, integer=True))
    ax.set_xlim(0.4, 1.3)
    ax.set_xlabel("Seconds", fontsize=8.5, color=SOFT)
    ax.set_ylabel("Count", fontsize=8.5, color=SOFT)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    pg.text(X0, y0 + h + 0.012, "(a) Reaction game, flash to flash", 9.5, True, va="top")
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
    pg.caption(n1, cap1)

    h = 0.13
    cap2 = (f"How far the recording's reaction time sits from the logged one, for all {rt['n']} presses. "
            "Orange: using the press time carried inside each response marker, which is what every "
            "average in this report uses; it sits within a millisecond of zero. Grey: using the moment the "
            "marker byte itself "
            "arrived, a little later. Differences past 40 ms are stacked on the right edge.")
    pg = doc.need(0.02 + h + pg.caption_height(n2, cap2))
    pg.y -= 0.02
    y0 = pg.take(h)
    ax = pg.axes(X0 + 0.05, y0 + 0.035, 0.5, h - 0.045)
    bins = np.arange(-10, 40.01, 1.0)
    ax.hist(np.clip(rt["byte_minus_log"], -10, 40), bins, color=GREY, label="response marker")
    ax.hist(np.clip(rt["press_minus_log"], -10, 40), bins, color=GAME["reaction"],
            label="press time logged with it")
    ax.set_xlim(-10, 40)
    ax.set_xlabel("EEG minus log reaction time (ms)", fontsize=8.5, color=SOFT)
    ax.set_ylabel("Presses", fontsize=8.5, color=SOFT)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    pg.caption(n2, cap2)


# ---- 2: the early sensory responses ----------------------------------------------
def _sensory(doc: Doc, c: dict, figs, secs) -> None:
    import matplotlib as mpl
    f, b = c["sensory"]["flash"], c["sensory"]["buzz"]
    r, p = f["random"], f["pattern"]
    n, n4 = next(figs), next(figs)
    hv = f["halves"]
    pg = doc.heading(next(secs), "Early sensory responses",
                "A flash, a tone or a buzz makes a small, fixed bump in the brain signal about a tenth of "
                "a second later, much the same in everyone. Averaging the signal around every marker of "
                "one kind shows that bump only if the markers sit at the right time; markers that were "
                "late by a varying amount would smear it away. P1, N1 and P2 are the standard names for "
                "the first bumps in order (P up, N down), and µV is a millionth of a volt.")
    doc.bullet("Flash (O1, O2, the back of the head):", f"P1 at {p['P1'][0]:.0f} ms in pattern trials and "
                                                        f"{r['P1'][0]:.0f} ms in random trials; N1 at "
                                                        f"{p['N1'][0]:.0f} and {r['N1'][0]:.0f} ms. First "
                                                        "and second half of the pattern blocks: P1 at "
                                                        f"{hv[0][0]:.0f} and {hv[1][0]:.0f} ms, so nothing "
                                                        f"drifted over the session (Figure {n4}).")
    doc.bullet("Tone (Cz, the top of the head):", f"N1 at {p['Cz N1'][0]:.0f} ms in pattern trials and "
                                                  f"{r['Cz N1'][0]:.0f} ms in random trials; P2 at "
                                                  f"{p['Cz P2'][0]:.0f} and {r['Cz P2'][0]:.0f} ms.")
    doc.bullet("Buzz (C3, CP3, the left side, which handles the right hand):",
               f"first peak at {b['first'][0]:.0f} ms and the main dip at {b['neg'][0]:.0f} ms "
               f"({b['neg'][1]:.1f} µV), against {b['neg_right'][1]:.1f} µV over the right side (C4, "
               "CP4), the larger side being the one expected for a right-hand buzz.")
    doc.bullet("Control:", "averages taken at random moments, where nothing happened, are flat at every "
                           "site, so the bumps come from the events and not from the averaging.")

    from .checks import MOTOR_MS
    pc, rc = KIND["pattern"][0], KIND["random"][0]
    rows = [("(a) Flash", ["O1", "O2"], "back", f["ms"],
             [(p["O1/O2"], pc, f"pattern ({p['n']})", "-"), (r["O1/O2"], rc, f"random ({r['n']})", "-"),
              (f["control O1/O2"], GREY, "random times", "-")],
             [(p["P1"], "P1"), (p["N1"], "N1")], None, ""),
            ("(b) Tone", ["Cz"], "top", f["ms"],
             [(p["Cz"], pc, "pattern", "-"), (r["Cz"], rc, "random", "-"),
              (f["control Cz"], GREY, "random times", "-")],
             [(p["Cz N1"], "N1"), (p["Cz P2"], "P2")], None, ""),
            ("(c) Buzz", ["C3", "CP3"], "left side", b["ms"],
             [(b["C3/CP3"], GAME["buzz"], "left", "-"), (b["C4/CP4"], LILAC, "right", "--"),
              (b["control C3/CP3"], GREY, "random times", "-")],
             [(b["first"], ""), (b["neg"], "")], [m / 1000 for m in MOTOR_MS], "vibration starts")]
    cap3 = (f"The average signal around each kind of marker, over {f['n']} of {f['of']} flashes and "
            f"{b['n']} of {b['of']} buzzes (the rest were dropped as too noisy, Section 4). Time runs "
            "left to right and 0 (dashed) is the marker. The small head shows which electrodes were "
            "read. (a) The flash at the back of the head: blue the pattern trials, orange the random "
            "trials, grey the random-time control, with the P1 and N1 peaks marked on the pattern "
            "average. (b) The tone at the top of the head, same colours. (c) The buzz: purple the left "
            "side of the head, dashed lilac the right side, grey the control; the shaded bar is when "
            "the motor actually starts to vibrate, measured on the bench, so the buzz response is read "
            "from there.")
    pg = doc.need(0.01 + 0.16 + 0.16 + 0.18 + pg.caption_height(n, cap3))
    pg.y -= 0.01
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
    pg.caption(n, cap3)

    img = f["image"]
    lim = float(np.percentile(np.abs(img), 98))
    hgt = 0.14
    cap4 = ("The same flash response one trial at a time, the first trial at the top and the last at "
            "the bottom, each row the running mean of 30 trials to tame the noise. Red is the signal "
            "going up and blue going down, in µV. The labels at the right name the blocks: random "
            "practice, the pattern blocks, random post-test. The dashed lines are the P1 and N1 times "
            "of the pattern average: a vertical stripe at each means the response kept the same timing "
            "all session, which is what markers with no drift look like.")
    pg = doc.need(hgt + pg.caption_height(n4, cap4))
    y0 = pg.take(hgt)
    pg.head(X0, y0 + 0.045, ["O1", "O2"], "back", pc)
    ax = pg.axes(X0 + 0.13, y0 + 0.035, W - 0.24, hgt - 0.04)
    ax.imshow(img, aspect="auto", cmap="RdBu_r", vmin=-lim, vmax=lim, interpolation="nearest",
              extent=[f["ms"][0] / 1000, f["ms"][-1] / 1000, len(img), 1])
    for peak in (p["P1"], p["N1"]):
        ax.axvline(peak[0] / 1000, color=INK, lw=0.9, ls=(0, (3, 3)))
    kinds = list(f["kinds"])
    start = 0
    for i in range(1, len(kinds) + 1):
        if i == len(kinds) or kinds[i] != kinds[start]:
            if start:
                ax.axhline(start + 0.5, color=INK, lw=0.8)
            ax.text(1.01, 1 - (start + i) / 2 / len(kinds), KIND[kinds[start]][1],
                    transform=ax.transAxes, fontsize=7.5, color=KIND[kinds[start]][0], va="center")
            start = i
    ax.set_xlabel("Time after the marker (s)", fontsize=8.5, color=SOFT)
    ax.set_ylabel("Trial", fontsize=8.5, color=SOFT)
    cax = pg.fig.add_axes([X0 + W - 0.04, y0 + 0.045, 0.01, hgt - 0.07])
    bar = pg.fig.colorbar(mpl.cm.ScalarMappable(norm=mpl.colors.Normalize(-lim, lim), cmap="RdBu_r"),
                          cax=cax, ticks=[-lim, 0, lim])
    bar.ax.set_yticklabels([f"{-lim:.0f}", "0", f"+{lim:.0f}"])
    bar.ax.tick_params(labelsize=8, colors=SOFT, length=2)
    bar.outline.set_visible(False)
    cax.set_title("µV", fontsize=8, color=SOFT)
    pg.caption(n4, cap4)


# ---- 3: the error signal -------------------------------------------------------------
def _errors(doc: Doc, c: dict, figs, secs) -> None:
    e = c["errors"]
    n = next(figs)
    wait = float(np.median(c["gaps"]["press_next"]))
    doc.heading(next(secs), "Error signal (ERN), Reaction game",
                "Within about a tenth of a second of a wrong press the brain makes a sharp dip at the "
                "front of the head, the error-related negativity (ERN); a correct press makes a smaller "
                "dip (CRN). A little later, 0.2 to 0.4 s after a wrong press, the signal further back "
                "rises (the Pe). These show only if each response marker is paired with the right "
                "press, and they need enough errors to average, six to eight at least. Pattern and "
                "random blocks are read apart because the random blocks hold few errors. p is the "
                "chance of a difference this large arising by luck; under .05 counts as reliable.")
    pt, rd = e["pattern"], e["random"]
    doc.bullet("Errors:", f"{pt['of_error']} in pattern blocks ({pt['n_error']} kept after cleaning) and "
                          f"{rd['of_error']} in random blocks ({rd['n_error']} kept).")
    for label, x in (("Pattern trials:", pt), ("Random trials:", rd)):
        if "ERN" not in x:
            continue
        doc.bullet(label, f"at FCz errors dip to {x['ERN'][1]:.1f} µV {x['ERN'][0]:.0f} ms after the "
                          f"press, correct presses (CRN) to {x['CRN'][1]:.1f} µV at {x['CRN'][0]:.0f} ms "
                          f"({_p(x['ern_test']['p'])}); at Pz, CPz errors sit {x['pe_test']['diff']:+.1f} "
                          f"µV against correct over 0.2 to 0.4 s ({_p(x['pe_test']['p'])}).")

    keep = e["ms"] >= -200
    ms = e["ms"][keep]
    cap5 = ("The signal around each press, with 0 (dashed) the press time logged with its response "
            "marker, for pattern trials (top row) and random trials (bottom row). Red is wrong presses "
            "and black correct presses, with the trial counts in the legend. Left: FCz at the front, "
            "where the ERN shows as the red line dipping below the black one just after the press. "
            "Right: Pz and CPz further back, where the Pe shows as the red line sitting above the "
            f"black one at 0.2 to 0.4 s. The next flash comes {wait:.2f} s after the press, so the right "
            "end of each plot already holds the next trial. Baseline -0.4 to -0.2 s: each trace is "
            "shifted so that stretch averages zero.")
    shown = [x for x in (pt, rd) if "ERN" in x]
    pg = doc.need(len(shown) * (0.015 + 0.15) + pg_caption_height(doc, n, cap5))
    for kind, x in (("pattern", pt), ("random", rd)):
        if "ERN" not in x:
            continue
        pg.y -= 0.015
        h = 0.15
        y0 = pg.take(h)
        for k, (title, chans, place, key) in enumerate(((f"ERN and CRN, {kind} trials", ["FCz"],
                                                         "top front", "FCz"),
                                                        (f"Pe, {kind} trials", ["Pz", "CPz"], "top back",
                                                         "Pz/CPz"))):
            xx = X0 + k * 0.43
            pg.head(xx, y0 + 0.055, chans, place, RED)
            ax = pg.axes(xx + 0.1, y0 + 0.035, 0.3, h - 0.06)
            _wave(ax, ms, [(x[f"{key} error"][keep], RED, f"error ({x['n_error']})", "-"),
                           (x[f"{key} correct"][keep], INK, f"correct ({x['n_correct']})", "-")],
                  xlabel="Time after the press (s)")
            pg.text(xx, y0 + h + 0.012, title, 9.5, True, va="top")
    pg.caption(n, cap5)


# ---- 4: processing ---------------------------------------------------------------------
def _processing(doc: Doc, c: dict, tabs, secs) -> None:
    f, b, e = c["sensory"]["flash"], c["sensory"]["buzz"], c["errors"]
    k = f["kept"]
    random = sum(v for name, v in k.items() if name.startswith("random"))
    pattern = sum(v for name, v in k.items() if name.startswith("sequence"))
    bads, ica, rec, st = c["bads"], c["ica"], c["recordings"], c["status"]
    fine = all(v["cms_in_range"] == 1.0 and v["battery_low"] == 0.0 for v in st.values())
    kinds = {m: f"{v.count('blink')} blink, {v.count('horizontal')} horizontal eye movement"
             for m, v in c["ica_kind"].items()}
    pt, rd = e["pattern"], e["random"]
    lead = ("How the two recordings were cleaned before any average above, in the order the steps "
            "ran. The terms are the standard ones, each with its plain meaning.")
    rows = [
        ["Recordings", f"{rec['srt'][0]} (Reaction, {rec['srt'][1]:.1f} min) and {rec['buzz_hunt'][0]} "
                       f"(Buzz Hunt, {rec['buzz_hunt'][1]:.1f} min); BioSemi ActiveTwo, 64 channels at "
                       "512 Hz" + ("; CMS in range and battery fine throughout." if fine else ".")],
        ["Filters", "Amplifier DC to 104 Hz; then 0.1 to 40 Hz band-pass (keeps the brain's range, "
                    "drops slow drift and muscle noise; zero-phase FIR) and a 50 and 100 Hz notch for "
                    "mains hum. ICA fitted on a 1 to 40 Hz copy."],
        ["Reference", "Common average: every channel is read against the mean of all 64, taken before "
                      "the bad channels are rebuilt."],
        ["Bad channels", f"Reaction: {', '.join(bads.get('srt', [])) or 'none'}. Buzz Hunt: "
                         f"{', '.join(bads.get('buzz_hunt', [])) or 'none'}. Flagged as flat, noisy or "
                         "unlike their neighbours (correlation under 0.4); rebuilt from the channels "
                         "around them (spherical-spline interpolation)."],
        ["ICA", "Independent component analysis, which unmixes the 64 channels into sources so eye "
                f"blinks and eye movements can be taken out. Picard, components to 99% of the variance ({ica['srt'][0]} and "
                f"{ica['buzz_hunt'][0]}). Removed: {ica['srt'][1]} in Reaction ({kinds['srt']}) and "
                f"{ica['buzz_hunt'][1]} in Buzz Hunt ({kinds['buzz_hunt']}), chosen by correlation "
                "with the eye channels (VEOG, HEOG) at |z| over 3."],
        ["Rejection", "Epochs (the slices of signal around each marker) swinging more than 150 µV "
                      "peak to peak after ICA were dropped as movement or muscle. Kept here: flashes "
                      f"{pattern} of 800 "
                      f"pattern and {random} of 96 random; presses {pt['n_correct']} of "
                      f"{pt['of_correct']} correct and {pt['n_error']} of {pt['of_error']} wrong in "
                      f"pattern blocks, {rd['n_correct']} of {rd['of_correct']} and {rd['n_error']} of "
                      f"{rd['of_error']} in random blocks; buzzes {b['n']} of {b['of']}."],
        ["Baseline", "The stretch each slice is zeroed on: -0.2 to 0 s before the flash or buzz; "
                     "-0.4 to -0.2 s before the press for the error signal."],
        ["Conditions", "Random and pattern trials kept apart in every Reaction game average."],
    ]
    tn = next(tabs)
    cap = "Processing, both recordings, in the order it ran."
    widths, header = [0.17, W - 0.17], ["Step", "What was done"]
    doc.need(0.014 + 0.045 + doc.pg.lead_height(lead) + doc.pg.table_height(tn, cap, rows, widths, header))
    pg = doc.heading(next(secs), "Processing", lead)
    pg.table(tn, cap, rows, widths, header)


# ---- the document ------------------------------------------------------------
def build(s: dict, out: Path, results: dict | None = None, cmp: dict | None = None,
          checks: dict | None = None) -> list[str]:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    if not checks:
        return []
    figs, tabs, secs = itertools.count(1), itertools.count(1), itertools.count(1)
    with plt.rc_context({"font.family": FONTS, "pdf.fonttype": 42, "axes.unicode_minus": False}):
        doc = Doc()
        first = doc.pg
        first.write(_subject(s), 22, True, after=0.0)
        first.write(_date(s), 10, colour=MUTED, after=0.01)
        first.ov.plot([X0, X0 + W], [first.y, first.y], color=LINE, lw=0.8)
        first.y -= 0.012
        first.write(_setting(s, checks), 10, colour=SOFT, after=0.004)
        _markers(doc, checks, figs, tabs, secs)
        _sensory(doc, checks, figs, secs)
        _errors(doc, checks, figs, secs)
        _processing(doc, checks, tabs, secs)
        path = out / "EEG_report.pdf"
        with PdfPages(path, metadata={"Title": f"{_subject(s)}, {_date(s)}"}) as pdf:
            for page in doc.pages:
                pdf.savefig(page.fig)
                plt.close(page.fig)
    return [path.name]


def _setting(s: dict, c: dict) -> str:
    """The session in a few plain words, for a reader who knows the
    project but not EEG."""
    flashes = next(r for r in c["by_condition"] if r[0] == "All")[1]
    buzzes = next(r for r in c["counts"] if r[0] == "Buzzes")[2]
    return (f"One participant played two of the device's games in the Curtin EEG lab while 64 "
            f"electrodes recorded the brain. Reaction: press the finger whose square lights up, "
            f"{flashes:,} trials, most following a hidden repeating order with random blocks first and "
            f"last. Buzz Hunt: press the finger that buzzes, {buzzes + c['catch']} trials. Each flash, "
            "buzz and press sent a numbered marker from the game into the recording; the checks below "
            "test those markers.")


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
