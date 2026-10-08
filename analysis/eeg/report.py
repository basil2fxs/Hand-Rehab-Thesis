"""The internal report: two A4 pages laid out like a short student
report. Numbered sections, the results in plain words, and numbered
figures whose captions say how to read them. Only clear results are
shown (each passed its test). Drawn straight to PDF; the full analysis
stays in detail/."""
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


def _who(s: dict) -> str:
    return s.get("participant") or "The participant"


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

    def bullet(self, s):
        self.text(X0 + 0.006, self.y, "•", 10, va="top")
        self.write(s, x=X0 + 0.026, width=W - 0.026, after=0.004)

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

    def head(self, x, y, chans, colour=INK, w=0.07):
        """A small head from above, the electrodes marked and named."""
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
        self.text(x + w / 2, y - 0.004, ", ".join(chans), 7.5, colour=MUTED, ha="center", va="top")


def _bars(ax, labels, vals, colours, fmt, top=None) -> None:
    from matplotlib.ticker import MaxNLocator
    xs = np.arange(len(vals))
    top = top or max(max(vals), 1e-9) * 1.3
    ax.bar(xs, [max(v, 0) for v in vals], color=colours, width=0.6)
    for x, v in zip(xs, vals):
        ax.text(x, max(v, 0) + top * 0.02, fmt.format(v), ha="center", va="bottom", fontsize=9,
                fontweight="bold", color=INK)
    ax.set_ylim(0, top)
    ax.set_xlim(-0.6, len(vals) - 0.4)
    ax.set_xticks(xs, labels)
    ax.yaxis.set_major_locator(MaxNLocator(3))


def _lines(ax, t, series, shade=None, tag="", legend=True) -> None:
    """Signal over time: 0 s (dashed) is the flash or buzz."""
    from matplotlib.ticker import MaxNLocator
    if shade:
        ax.axvspan(*shade, color=GREY, alpha=0.2, lw=0)
        ax.text(sum(shade) / 2, 1.0, tag, transform=ax.get_xaxis_transform(), ha="center",
                va="bottom", fontsize=7.5, color=MUTED)
    ax.axhline(0, color=LINE, lw=0.8)
    ax.axvline(0, color=INK, lw=1.0, ls=(0, (3, 3)))
    for y, colour, label in series:
        ax.plot(t, y, color=colour, lw=2.0, label=label)
    ax.set_xlim(t[0], t[-1])
    ax.yaxis.set_major_locator(MaxNLocator(4, integer=True))
    ax.set_ylabel("Signal (µV)", fontsize=8.5, color=SOFT)
    if legend:
        ax.legend(frameon=False, fontsize=8.5, loc="upper left")


# ---- section 1: the two games side by side ------------------------------------
def _compare(pg: Page, s: dict, c: dict, count) -> None:
    import matplotlib as mpl
    import mne
    who = _who(s)
    m, t = c["modes"], c["tests"]
    r, b = m["reaction"], m["buzz"]
    rt_ok, size_ok, time_ok = _clear(t.get(RT_TEST)), _clear(t.get(SIZE_TEST)), _clear(t.get(TIME_TEST))
    pg.heading(1, "Reaction game vs Buzz Hunt")
    for key, label, what in (("reaction", "Reaction game:", "a square flashes and beeps"),
                             ("buzz", "Buzz Hunt:", "a finger buzzes")):
        gap = m[key].get("spacing_s")
        pg.write(what + (f", one every {gap[0]:.1f} to {gap[1]:.1f} s." if gap else "."),
                 lead=(label, GAME[key]), after=0.001)
    pg.y -= 0.008

    panels = []
    if rt_ok:
        panels.append(("rt", "Time to press (s)", [r["rt_ms"] / 1000, b["rt_ms"] / 1000], "{:.2f}",
                       "the typical time to press"))
    if size_ok:
        panels.append(("size", "Attention signal size (µV)", [r["p3_uV"], b["p3_uV"]], "{:.1f}",
                       "the size of the attention signal at the top back of the head"))
    if time_ok:
        panels.append(("time", "Attention signal timing (s)", [r["p3_latency_ms"] / 1000,
                                                               b["p3_latency_ms"] / 1000], "{:.2f}",
                       "when the middle of that signal came"))
    n1 = next(count) if panels else None
    n2 = next(count) if size_ok or time_ok else None
    n3 = next(count) if size_ok else None
    fig1 = {p[0]: f"{n1}{'abc'[k]}" for k, p in enumerate(panels)}
    cue = {"reaction": "flash", "buzz": "buzz"}
    if rt_ok:
        fast, slow = sorted(GAME, key=lambda k: m[k]["rt_ms"])
        pg.bullet(f"{who} pressed faster after the {cue[fast]} ({m[fast]['rt_ms'] / 1000:.2f} s) than "
                  f"after the {cue[slow]} ({m[slow]['rt_ms'] / 1000:.2f} s) (Figure {fig1['rt']}).")
    if size_ok:
        lo, hi = sorted(GAME, key=lambda k: m[k]["p3_uV"])
        ratio = m[hi]["p3_uV"] / m[lo]["p3_uV"] if m[lo]["p3_uV"] > 0 else 0
        pg.bullet(f"The brain's attention signal (P3) was "
                  f"{f'about {ratio:.0f} times ' if ratio >= 1.5 else ''}bigger after the {cue[hi]}: "
                  f"{m[hi]['p3_uV']:.1f} vs {m[lo]['p3_uV']:.1f} µV, millionths of a volt "
                  f"(Figures {fig1['size']} and {n3}).")
    if time_ok:
        soon, late = sorted(GAME, key=lambda k: m[k]["p3_latency_ms"])
        pg.bullet(f"{'It also' if size_ok else 'The attention signal (P3)'} came later after the "
                  f"{cue[late]}: {m[late]['p3_latency_ms'] / 1000:.2f} vs "
                  f"{m[soon]['p3_latency_ms'] / 1000:.2f} s (Figures {fig1['time']} and {n2}).")
    pg.y -= 0.01

    # Figure: the numbers as bars
    if panels:
        h = 0.15
        y0 = pg.take(h)
        for k, (_, title, vals, fmt, _) in enumerate(panels):
            x = X0 + 0.045 + k * 0.29
            ax = pg.axes(x, y0 + 0.022, 0.2, h - 0.055)
            _bars(ax, [NAME["reaction"], NAME["buzz"]], vals, [GAME["reaction"], GAME["buzz"]], fmt)
            pg.text(x - 0.045, y0 + h - 0.004, f"({'abc'[k]}) {title}", 9.5, True, va="top")
        pg.caption(n1, " ".join(f"({'abc'[k]}) {p[4][0].upper()}{p[4][1:]}." for k, p in enumerate(panels))
                   + " Orange: Reaction game. Purple: Buzz Hunt.")

    if not (size_ok or time_ok):
        return
    # Figure: the attention signal over time
    ev = {k: e.average() for k, e in c["epochs"].items()}
    ys = {k: _site(ev[k], P3_SITES) for k in GAME}
    tt = ev["reaction"].times
    win = [v / 1000 for v in (s.get("compare") or {}).get("p3_window_ms", [300, 650])]
    h = 0.17
    y0 = pg.take(h)
    pg.head(X0, y0 + 0.06, P3_SITES)
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
    pg.caption(n2, "The attention signal over time at the top back of the head (black dots on the "
                   "small head), averaged over all the tries. 0 s is the flash or buzz."
               + (" Grey band: where we measured its size." if size_ok else "")
               + (" Dots: when the middle of each signal came." if time_ok else ""))

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
    tops = {k: data[k].ch_names[int(np.argmax(at[k]))] for k in GAME}
    back = all(ch.startswith(("P", "CP")) for ch in tops.values())
    pg.caption(n3, "The head seen from above, nose at the top, when each attention signal was at its "
                   "middle. Red: signal up. Blue: signal down. Black dots: where Figure "
                   f"{n2} was measured."
               + (" Both signals were strongest at the top back of the head." if back else ""))


# ---- section 2: learning the pattern -------------------------------------------
def _learning(pg: Page, s: dict, r, count) -> None:
    srt, who = s["srt"], _who(s)
    lr, rc = srt.get("learning", {}), srt.get("recall", {})
    st, bt = srt.get("stim_tests", {}), srt.get("band_tests", {})
    n2, p3 = st.get(FD.N2_TEST, {}), st.get(FD.P3_TEST, {})
    adj = FD.holm([n2.get("p"), p3.get("p")])
    ci = lr.get("post_minus_block8_ci") or [0, 0]
    cost, b1, b8 = (lr.get(k, 0) / 1000 for k in ("post_minus_block8_ms", "block1_ms", "block8_ms"))
    ev_l, ev_r = r.stim.get("sequence_late"), r.stim.get("random_posttest")
    learned = ci[0] > 0
    n2_ok = adj[0] is not None and adj[0] < FD.ALPHA and ev_l is not None and ev_r is not None
    p3_ok = adj[1] is not None and adj[1] < FD.ALPHA
    beta = bt.get("beta C3")
    n = next(count)

    pg.heading(2, "Learning a pattern (Reaction game)")
    pattern = f"a repeating pattern of {rc['items']}" if rc else "a repeating pattern"
    pg.write(f"The squares lit up at random, then in {pattern}, then at random again.", after=0.008)
    if learned:
        pg.bullet((f"{who} got faster with the pattern ({b1:.2f} to {b8:.2f} s) and was"
                   if b8 < b1 else f"{who} was")
                  + f" {cost:.2f} s slower when it was taken away, so the pattern was learned "
                    f"(Figure {n}a).")
    if rc and _clear({"p": rc.get("chance_p")}):
        if rc["cyclic_correct"] == rc["items"]:
            pg.bullet(f"{who} typed the whole pattern back in the right order"
                      + ("." if rc["correct"] == rc["items"] else
                         ", just starting at a different point in the loop."))
        else:
            pg.bullet(f"{who} typed back {rc['cyclic_correct']} of {rc['items']} in the right order, "
                      "more than guessing would give.")
    if n2_ok:
        pg.bullet(f"Random flashes made the surprise signal (N2) dip "
                  f"{'lower' if n2.get('diff', 0) < 0 else 'less'} than the learned pattern did "
                  f"(Figure {n}b).")
    once = []
    if p3_ok:
        once.append(f"the attention signal (P3) was {'smaller' if p3.get('diff', 0) > 0 else 'bigger'}")
    if _clear(beta):
        once.append("the movement hum (beta) over the left side was "
                    + ("quieter" if beta["diff"] > 0 else "louder"))
    if once:
        pg.bullet("Once the pattern was learned, " + " and ".join(once) + ".")
    pg.y -= 0.01

    h = 0.19
    y0 = pg.take(h)
    bh = r.behaviour
    seg = list(bh.segment)
    rt = bh.rt_median_ms.to_numpy(float) / 1000
    ax = pg.axes(X0 + 0.045, y0 + 0.035, 0.31, h - 0.07)
    ax.bar(range(len(seg)), rt, width=0.7,
           color=[GREY if x == "Practice" else RED if x == "Post-test" else BLUE for x in seg])
    ax.set_xticks(range(len(seg)), ["Start" if x == "Practice" else "End" if x == "Post-test"
                                    else x.replace("Sequence ", "") for x in seg])
    ax.set_ylim(0, rt.max() * 1.3)
    ax.set_xlabel("Block", fontsize=8.5, color=SOFT)
    if learned and "Sequence 8" in seg and "Post-test" in seg:
        i, j = seg.index("Sequence 8"), seg.index("Post-test")
        ax.annotate("", xy=(j, rt[j] + 0.01), xytext=(i, rt[i] + 0.01),
                    arrowprops=dict(arrowstyle="->", color=INK, lw=1.2,
                                    connectionstyle="arc3,rad=-0.45"))
        ax.text((i + j) / 2, max(rt[i], rt[j]) + 0.035, f"+{cost:.2f} s", ha="center", fontsize=8.5,
                fontweight="bold", color=INK)
    pg.text(X0, y0 + h - 0.004, "(a) Time to press in each block (s)", 9.5, True, va="top")
    words = ("(a) The typical time to press in each block. Blue: the pattern. Grey and red: random "
             "order." + (" The arrow is the slow-down when the pattern was taken away." if learned else ""))
    if n2_ok:
        pg.head(X0 + 0.42, y0 + 0.065, N2_SITES, w=0.06)
        ax = pg.axes(X0 + 0.54, y0 + 0.035, W - 0.54, h - 0.07)
        tn, yl, yr = ev_l.times, _site(ev_l, N2_SITES), _site(ev_r, N2_SITES)
        _lines(ax, tn, [(yl, BLUE, "learned pattern"), (yr, RED, "random")], (0.2, 0.3),
               "measured here", legend=False)
        for k, (colour, label) in enumerate(((BLUE, "learned pattern"), (RED, "random"))):
            ax.text(0.99, 0.97 - k * 0.11, label, transform=ax.transAxes, ha="right", va="top",
                    fontsize=8.5, fontweight="bold", color=colour)
        ax.set_xlabel("Time after the flash (s)", fontsize=8.5, color=SOFT)
        pg.text(X0 + 0.42, y0 + h - 0.004, "(b) Surprise signal (N2)", 9.5, True, va="top")
        words += (" (b) The brain signal at the top of the head (small head) after each flash. Blue: the "
                  "learned pattern (blocks 7 and 8). Red: random flashes at the end. Grey band: where "
                  "we measured the surprise signal.")
    pg.caption(n, words)


# ---- section 3: feeling the buzz -------------------------------------------------
def _buzz(pg: Page, s: dict, count) -> None:
    bz, who = s["buzz"], _who(s)
    mu = (bz.get("tests") or {}).get(FD.MU_TEST)
    lanes = list((bz.get("per_lane") or {}).values())
    n_try, hit = sum(x["n"] for x in lanes), sum(x["correct"] for x in lanes)
    acc, chance = bz.get("loc_accuracy", 0) * 100, 100 / len(lanes) if lanes else 0
    n = next(count)

    pg.heading(3, "Feeling the buzz (Buzz Hunt)")
    pg.write(f"One finger buzzed and {who} pressed that finger.", after=0.008)
    pg.bullet(f"{who} found the right finger in {hit} of {n_try} tries ({acc:.0f}%), about "
              f"{bz.get('loc_rt_ms', 0) / 1000:.2f} s after the buzz. Guessing would get {chance:.0f}% "
              f"(Figure {n}a).")
    if _clear(mu):
        pg.bullet(f"The movement hum (mu) over the left side, which feels the right hand, "
                  f"{'dropped' if mu['diff'] < 0 else 'rose'} {abs(mu['diff']):.0f}% after the buzz "
                  f"(Figure {n}b).")
    pg.y -= 0.01

    h = 0.16
    y0 = pg.take(h)
    ax = pg.axes(X0 + 0.045, y0 + 0.022, 0.24, h - 0.055)
    _bars(ax, [who, "Guessing"], [acc, chance], [GAME["buzz"], GREY], "{:.0f}%", top=118)
    ax.set_yticks([0, 50, 100], ["0", "50", "100%"])
    pg.text(X0, y0 + h - 0.004, "(a) Right finger found", 9.5, True, va="top")
    words = f"(a) How often {who} pressed the finger that buzzed, against guessing."
    if _clear(mu):
        pg.head(X0 + 0.47, y0 + 0.05, ["C3"], GAME["buzz"])
        ax = pg.axes(X0 + 0.6, y0 + 0.022, 0.24, h - 0.055)
        _bars(ax, ["Before", "After"], [100.0, 100.0 + mu["diff"]], [GREY, GAME["buzz"]], "{:.0f}%",
              top=125)
        ax.set_yticks([0, 50, 100], ["0", "50", "100%"])
        pg.text(X0 + 0.47, y0 + h - 0.004, "(b) Movement hum, left side", 9.5, True, va="top")
        words += (" (b) How strong the movement hum was over the left side (small head) before and "
                  "after the buzz, with before set to 100%.")
    pg.caption(n, words)


# ---- the document ------------------------------------------------------------
def build(s: dict, out: Path, results: dict | None = None, cmp: dict | None = None) -> list[str]:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    results = results or {}
    count = itertools.count(1)
    with plt.rc_context({"font.family": FONTS, "pdf.fonttype": 42, "axes.unicode_minus": False}):
        pages = []
        first = Page(1)
        first.write(f"{_who(s)}, {_date(s)}", 20, True, after=0.002)
        first.write("Only clear results are shown: each one passed its test, so it is very unlikely "
                    "to be luck.", 9, colour=MUTED, after=0.006)
        first.ov.plot([X0, X0 + W], [first.y, first.y], color=LINE, lw=0.8)
        if cmp and "epochs" in cmp:
            _compare(first, s, cmp, count)
        pages.append(first)
        srt_ok = bool(s.get("srt")) and results.get("srt") is not None
        if srt_ok or s.get("buzz"):
            second = Page(2)
            if srt_ok:
                _learning(second, s, results["srt"], count)
            if s.get("buzz"):
                _buzz(second, s, count)
            pages.append(second)
        path = out / "EEG_report.pdf"
        with PdfPages(path, metadata={"Title": f"{_who(s)}, {_date(s)}"}) as pdf:
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
