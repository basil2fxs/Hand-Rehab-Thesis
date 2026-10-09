"""The internal report: two A4 pages laid out like a short student
report. Numbered sections, the results in plain words, and numbered
figures whose captions say how to read them. EEG results whose test
passed, nothing else: press times, accuracy and recall come from any
game session. Drawn straight to PDF; the full analysis stays in
detail/."""
from __future__ import annotations

import itertools
from functools import lru_cache
from pathlib import Path

import numpy as np

from . import findings as FD

# the games' colours, as on the results page
GAME = {"reaction": "#ea580c", "buzz": "#7c3aed"}
NAME = {"reaction": "Reaction", "buzz": "Buzz Hunt"}
INK, SOFT, MUTED, LINE = "#111827", "#374151", "#6b7280", "#9ca3af"
BLUE, RED, GREY = "#2563eb", "#dc2626", "#9ca3af"
# Arial ships its regular and bold as separate files, which matplotlib
# needs to tell the two weights apart (it reads only one face of a .ttc)
FONTS = ["Arial", "DejaVu Sans"]
A4 = (8.27, 11.69)
X0, W = 0.08, 0.84          # the text column, in page units

# A flat sketch of the cap from above (nose up, left ear on the left),
# close enough to show where each electrode sits.
SPOT = {"FCz": (0.0, 0.21), "Cz": (0.0, 0.0), "CPz": (0.0, -0.21), "Pz": (0.0, -0.42),
        "Oz": (0.0, -0.85), "C3": (-0.42, 0.0), "C4": (0.42, 0.0)}
P3_SITES, N2_SITES = ["Pz", "CPz"], ["FCz", "Cz"]
RT_TEST = "RT, buzz minus reaction"
SIZE_TEST = "P3 300-650 ms, buzz minus reaction"
TIME_TEST = "P3 latency, buzz minus reaction"


def _clear(test: dict | None) -> bool:
    """A clear result: its test passed at .05."""
    return bool(test) and test.get("p") is not None and test["p"] < FD.ALPHA


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


def _site(ev, chans) -> np.ndarray:
    return ev.copy().pick(chans).data.mean(0) * 1e6


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
        if words and words[-1].endswith(("Figure", "Figures")):
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

    def axes(self, x, y, w, h):
        ax = self.fig.add_axes([x, y, w, h])
        ax.set_facecolor("none")
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color(LINE)
        ax.tick_params(labelsize=8, colors=SOFT, length=3, color=LINE)
        return ax

    def head(self, x, y, chans, place, colour=INK, w=0.07):
        """A small head from above, the electrodes marked, the place in
        words and the electrode codes underneath."""
        from matplotlib.patches import Circle, Ellipse
        ax = self.fig.add_axes([x, y, w, w * A4[0] / A4[1]])
        ax.add_patch(Circle((0, 0), 1, fill=False, ec=INK, lw=1.1))
        ax.plot([-0.15, 0, 0.15], [0.99, 1.18, 0.99], color=INK, lw=1.1)
        for side in (-1, 1):
            ax.add_patch(Ellipse((side * 1.05, 0), 0.12, 0.36, fill=False, ec=INK, lw=1.1))
        for ch in chans:
            ax.scatter(*SPOT[ch], s=40, color=colour, zorder=3, lw=0)
        ax.set_xlim(-1.25, 1.25)
        ax.set_ylim(-1.25, 1.25)
        ax.set_aspect("equal")
        ax.axis("off")
        self.text(x + w / 2, y - 0.004, place, 8, colour=SOFT, ha="center", va="top")
        self.text(x + w / 2, y - 0.018, ", ".join(chans), 7.5, colour=MUTED, ha="center", va="top")


def _bars(ax, labels, vals, colours, fmt="", top=None) -> None:
    from matplotlib.ticker import MaxNLocator
    xs = np.arange(len(vals))
    top = top or max(max(vals), 1e-9) * 1.3
    ax.bar(xs, [max(v, 0) for v in vals], color=colours, width=0.6)
    for x, v in zip(xs, vals if fmt else []):
        ax.text(x, max(v, 0) + top * 0.02, fmt.format(v), ha="center", va="bottom", fontsize=9,
                fontweight="bold", color=INK)
    ax.set_ylim(0, top)
    ax.set_xlim(-0.6, len(vals) - 0.4)
    ax.set_xticks(xs, labels)
    ax.yaxis.set_major_locator(MaxNLocator(3))


def _lines(ax, t, series, shade=None, tag="", legend=True) -> None:
    """Signal over time: 0 s (dashed) is the flash or buzz."""
    from matplotlib.ticker import MaxNLocator, MultipleLocator
    if shade:
        ax.axvspan(*shade, color=GREY, alpha=0.2, lw=0)
        ax.text(sum(shade) / 2, 1.0, tag, transform=ax.get_xaxis_transform(), ha="center",
                va="bottom", fontsize=7.5, color=MUTED)
    ax.axhline(0, color=LINE, lw=0.8)
    ax.axvline(0, color=INK, lw=1.0, ls=(0, (3, 3)))
    for y, colour, label in series:
        ax.plot(t, y, color=colour, lw=2.0, label=label)
    # snap the ends to the nearest 0.2 s so the first and last ticks show
    ax.set_xlim(*[round(v * 5) / 5 if abs(v * 5 - round(v * 5)) < 0.025 else v for v in (t[0], t[-1])])
    ax.xaxis.set_major_locator(MultipleLocator(0.2))
    ax.yaxis.set_major_locator(MaxNLocator(4, integer=True))
    ax.set_ylabel("Signal (µV)", fontsize=8.5, color=SOFT)
    if legend:
        ax.legend(frameon=False, fontsize=8.5, loc="upper left")


# ---- section 1: the two games side by side ------------------------------------
def _compare(pg: Page, s: dict, c: dict, figs, secs) -> None:
    import matplotlib as mpl
    import mne
    m, t = c["modes"], c["tests"]
    r, b = m["reaction"], m["buzz"]
    size_ok, time_ok = _clear(t.get(SIZE_TEST)), _clear(t.get(TIME_TEST))
    if not (size_ok or time_ok):
        return
    pg.heading(next(secs), "Reaction game vs Buzz Hunt")
    for key, label, what in (("reaction", "Reaction game:", "a square flashes and beeps"),
                             ("buzz", "Buzz Hunt:", "a finger buzzes")):
        gap = m[key].get("spacing_s")
        pg.write(what + (f", every {gap[0]:.1f} to {gap[1]:.1f} s." if gap else "."),
                 lead=(label, GAME[key]), after=0.001)
    pg.y -= 0.008

    panels = []
    if size_ok:
        panels.append(("Attention signal size (µV)", [r["p3_uV"], b["p3_uV"]], "{:.1f}"))
    if time_ok:
        panels.append(("Attention signal timing (s)", [r["p3_latency_ms"] / 1000,
                                                       b["p3_latency_ms"] / 1000], "{:.2f}"))
    n1, n2 = next(figs), next(figs)
    n3 = next(figs) if size_ok else None
    cue = {"reaction": "flash", "buzz": "buzz"}
    if size_ok:
        lo, hi = sorted(GAME, key=lambda k: m[k]["p3_uV"])
        ratio = m[hi]["p3_uV"] / m[lo]["p3_uV"] if m[lo]["p3_uV"] > 0 else 0
        pg.bullet("Attention signal (P3):",
                  f"{f'about {ratio:.0f} times ' if ratio >= 1.5 else ''}bigger after the {cue[hi]} "
                  f"({m[hi]['p3_uV']:.1f} vs {m[lo]['p3_uV']:.1f} µV, millionths of a volt).")
    if time_ok:
        soon, late = sorted(GAME, key=lambda k: m[k]["p3_latency_ms"])
        pg.bullet("Timing:", f"later after the {cue[late]} "
                             f"({m[late]['p3_latency_ms'] / 1000:.2f} vs "
                             f"{m[soon]['p3_latency_ms'] / 1000:.2f} s).")
    pg.y -= 0.01

    # Figure: the numbers as bars
    h = 0.15
    y0 = pg.take(h)
    for k, (title, vals, fmt) in enumerate(panels):
        x = X0 + 0.045 + k * 0.45
        ax = pg.axes(x, y0 + 0.022, 0.26, h - 0.055)
        _bars(ax, [NAME["reaction"], NAME["buzz"]], vals, [GAME["reaction"], GAME["buzz"]], fmt)
        pg.text(x - 0.045, y0 + h - 0.004, f"({'ab'[k]}) {title}", 9.5, True, va="top")
    pg.caption(n1, " ".join([f"Size: the average in Figure {n2}'s grey band."] * size_ok
                            + ["Timing: when the middle of the signal came."] * time_ok))

    # Figure: the attention signal over time
    ev = {k: e.average() for k, e in c["epochs"].items()}
    ys = {k: _site(ev[k], P3_SITES) for k in GAME}
    tt = ev["reaction"].times
    win = [v / 1000 for v in (s.get("compare") or {}).get("p3_window_ms", [300, 650])]
    h = 0.17
    y0 = pg.take(h)
    pg.head(X0, y0 + 0.07, P3_SITES, "top back")
    ax = pg.axes(X0 + 0.15, y0 + 0.035, W - 0.15, h - 0.045)
    _lines(ax, tt, [(ys[k], GAME[k], NAME[k]) for k in GAME], win if size_ok else None,
           "size measured here")
    lo, hi = min(y.min() for y in ys.values()), max(y.max() for y in ys.values())
    ax.set_ylim(lo - 0.1 * (hi - lo), hi + 0.3 * (hi - lo))
    if time_ok:
        top = hi + 0.12 * (hi - lo)
        for k in GAME:
            lt = m[k]["p3_latency_ms"] / 1000
            yv = float(np.interp(lt, tt, ys[k]))
            ax.plot([lt, lt], [yv, top], color=GAME[k], lw=1.0, ls=(0, (1, 2)))
            ax.scatter([lt], [yv], s=55, color=GAME[k], edgecolor="white", lw=1.5, zorder=5)
            ax.text(lt, top, f"{lt:.2f} s", ha="center", va="bottom", fontsize=8.5,
                    fontweight="bold", color=GAME[k])
    ax.set_xlabel("Time after the flash or buzz (s)", fontsize=8.5, color=SOFT)
    pg.caption(n2, "Attention signal at the top back of the head, average of all tries."
               + (" Dots: its timing." if time_ok else ""))

    if not size_ok:
        return
    # Figure: where on the head
    data = {k: e.copy().pick("eeg") for k, e in ev.items()}
    at = {k: data[k].data[:, int(np.argmin(np.abs(data[k].times - m[k]["p3_latency_ms"] / 1000)))]
          * 1e6 for k in GAME}
    lim = max(np.abs(x).max() for x in at.values()) * 0.85
    h, w = 0.205, 0.26
    y0 = pg.take(h)
    for k, key in enumerate(GAME):
        x0 = X0 + 0.04 + k * 0.5
        ax = pg.fig.add_axes([x0, y0, w, w * A4[0] / A4[1]])
        mne.viz.plot_topomap(at[key], data[key].info, axes=ax, show=False, cmap="RdBu_r",
                             vlim=(-lim, lim), contours=0, sensors=False,
                             mask=np.isin(data[key].ch_names, P3_SITES),
                             mask_params=dict(marker="o", markerfacecolor=INK, markeredgecolor="white",
                                              markersize=7))
        name = "Reaction game" if key == "reaction" else NAME[key]
        pg.text(x0 + w / 2, y0 + h - 0.002, f"{name}, {m[key]['p3_latency_ms'] / 1000:.2f} s", 9.5,
                True, GAME[key], ha="center", va="top")
        pg.text(x0 - 0.004, y0 + 0.092, "left", 8, colour=MUTED, ha="right", va="center")
        pg.text(x0 + w + 0.004, y0 + 0.092, "right", 8, colour=MUTED, va="center")
    cax = pg.fig.add_axes([X0 + 0.415, y0 + 0.035, 0.012, 0.12])
    bar = pg.fig.colorbar(mpl.cm.ScalarMappable(norm=mpl.colors.Normalize(-lim, lim), cmap="RdBu_r"),
                          cax=cax, ticks=[-lim, 0, lim])
    bar.ax.set_yticklabels([f"{-lim:.0f}", "0", f"+{lim:.0f}"])
    bar.ax.tick_params(labelsize=8, colors=SOFT, length=2)
    bar.outline.set_visible(False)
    cax.set_title("µV", fontsize=8, color=SOFT)
    pg.caption(n3, "Head from above, nose up, at each signal's timing. Red: up. Blue: down. Black "
                   f"dots: the spots in Figure {n2}.")


# ---- section 2: learning the pattern -------------------------------------------
def _learning(pg: Page, s: dict, r, figs, secs) -> None:
    srt = s["srt"]
    rc = srt.get("recall", {})
    st, bt = srt.get("stim_tests", {}), srt.get("band_tests", {})
    n2, p3 = st.get(FD.N2_TEST, {}), st.get(FD.P3_TEST, {})
    adj = FD.holm([n2.get("p"), p3.get("p")])
    ev_l, ev_r = r.stim.get("sequence_late"), r.stim.get("random_posttest")
    n2_ok = adj[0] is not None and adj[0] < FD.ALPHA and ev_l is not None and ev_r is not None
    p3_ok = adj[1] is not None and adj[1] < FD.ALPHA
    beta = bt.get("beta C3")
    if not (n2_ok or p3_ok or _clear(beta)):
        return
    blocks = sum(str(x).startswith("Sequence") for x in r.behaviour.segment)

    pg.heading(next(secs), "Learning a pattern (Reaction game)")
    pattern = f"a repeating pattern of {rc['items']}" if rc else "a repeating pattern"
    pg.write(f"Random order, then {pattern} (blocks 1 to {blocks}), then random again.", after=0.008)
    if n2_ok:
        pg.bullet("Surprise signal (N2):",
                  f"dipped {'lower' if n2.get('diff', 0) < 0 else 'less'} for random flashes.")
    if p3_ok:
        pg.bullet("Attention signal (P3):",
                  f"{'smaller' if p3.get('diff', 0) > 0 else 'bigger'} once the pattern was learned.")
    if _clear(beta):
        pg.bullet("Resting rhythm (beta), left side:",
                  "lower once learned, so that area was busier." if beta["diff"] > 0 else
                  "higher once learned.")
    pg.y -= 0.01
    if not n2_ok:
        return

    n = next(figs)
    h = 0.17
    y0 = pg.take(h)
    pg.head(X0, y0 + 0.07, N2_SITES, "top")
    ax = pg.axes(X0 + 0.15, y0 + 0.035, W - 0.15, h - 0.045)
    tn, yl, yr = ev_l.times, _site(ev_l, N2_SITES), _site(ev_r, N2_SITES)
    _lines(ax, tn, [(yl, BLUE, "learned pattern"), (yr, RED, "random")], (0.2, 0.3), "measured here",
           legend=False)
    for k, (colour, label) in enumerate(((BLUE, "learned pattern"), (RED, "random"))):
        ax.text(0.99, 0.97 - k * 0.11, label, transform=ax.transAxes, ha="right", va="top",
                fontsize=8.5, fontweight="bold", color=colour)
    ax.set_xlabel("Time after the flash (s)", fontsize=8.5, color=SOFT)
    pg.caption(n, "Surprise signal at the top of the head, average of all tries. Learned pattern: "
                  "blocks 7 and 8.")


# ---- section 3: feeling the buzz -------------------------------------------------
def _buzz(pg: Page, s: dict, figs, secs) -> None:
    mu = (s["buzz"].get("tests") or {}).get(FD.MU_TEST)
    if not _clear(mu):
        return
    pg.heading(next(secs), "Feeling the buzz (Buzz Hunt)")
    drop = mu["diff"] < 0
    pg.bullet("Resting rhythm (mu), left side:",
              f"{abs(mu['diff']):.0f}% {'lower' if drop else 'higher'} after the buzz"
              + (", so that area got busy." if drop else "."))
    pg.y -= 0.01

    n = next(figs)
    h = 0.17
    y0 = pg.take(h)
    pg.head(X0, y0 + 0.06, ["C3"], "left side", GAME["buzz"])
    ax = pg.axes(X0 + 0.15, y0 + 0.022, 0.3, h - 0.045)
    after = 100.0 + mu["diff"]
    _bars(ax, ["Before the buzz", "After the buzz"], [100.0, after], [GREY, GAME["buzz"]], top=135)
    ax.set_yticks([0, 50, 100], ["0", "50", "100%"])
    ax.set_ylabel("Rhythm strength", fontsize=8.5, color=SOFT)
    ax.annotate("", xy=(1, after + 4), xytext=(0, 104),
                arrowprops=dict(arrowstyle="->", color=INK, lw=1.3, shrinkA=0, shrinkB=0,
                                connectionstyle="arc3,rad=-0.3"))
    ax.text(0.5, max(100.0, after) + 16, f"{mu['diff']:+.0f}%", ha="center", fontsize=10,
            fontweight="bold", color=INK)
    pg.caption(n, "The resting rhythm drops when a brain area gets busy. The left side feels the "
                  "right hand.")


# ---- the document ------------------------------------------------------------
def build(s: dict, out: Path, results: dict | None = None, cmp: dict | None = None) -> list[str]:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    results = results or {}
    figs, secs = itertools.count(1), itertools.count(1)
    with plt.rc_context({"font.family": FONTS, "pdf.fonttype": 42, "axes.unicode_minus": False}):
        pages = []
        first = Page(1)
        first.write(_subject(s), 22, True, after=0.0)
        first.write(_date(s), 10, colour=MUTED, after=0.01)
        first.ov.plot([X0, X0 + W], [first.y, first.y], color=LINE, lw=0.8)
        if cmp and "epochs" in cmp:
            _compare(first, s, cmp, figs, secs)
        pages.append(first)
        second = Page(2)
        top = second.y
        if s.get("srt") and results.get("srt") is not None:
            _learning(second, s, results["srt"], figs, secs)
        if s.get("buzz"):
            _buzz(second, s, figs, secs)
        if second.y < top:
            pages.append(second)
        else:
            plt.close(second.fig)
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
