"""The internal report: two A4 pages drawn straight to PDF, made to read
at a glance. Plain words, a few big numbers and simple pictures, with a
"clear" or "not sure yet" badge from each test in place of p values.
The full analysis stays in detail/."""
from __future__ import annotations

from pathlib import Path

import numpy as np

from . import findings as FD

# the games' colours, as on the results page
GAME = {"reaction": "#ea580c", "buzz": "#7c3aed"}
NAME = {"reaction": "Reaction", "buzz": "Buzz Hunt"}
INK, MUTED, CARD = "#111827", "#6b7280", "#f3f4f6"
BLUE, RED, GREY, GREEN = "#2563eb", "#dc2626", "#9ca3af", "#059669"
# Arial ships its regular and bold as separate files, which matplotlib
# needs to tell the two weights apart (it reads only one face of a .ttc)
FONTS = ["Arial", "DejaVu Sans"]
A4 = (8.27, 11.69)

# A flat sketch of the cap from above (nose up, left ear on the left),
# close enough to show where each electrode sits.
SPOT = {"FCz": (0.0, 0.21), "Cz": (0.0, 0.0), "CPz": (0.0, -0.21), "Pz": (0.0, -0.42),
        "Oz": (0.0, -0.85), "C3": (-0.42, 0.0), "C4": (0.42, 0.0)}


def _clear(test: dict | None) -> bool:
    """The badge: the test passed at .05."""
    return bool(test) and test.get("p") is not None and test["p"] < FD.ALPHA


def _s(ms: float) -> str:
    return f"{ms / 1000:.2f} s"


def _date(s: dict) -> str:
    import datetime as _dt
    try:
        d = _dt.date.fromisoformat(s.get("date") or "")
    except ValueError:
        return s.get("date_long", "")
    return f"{d.day} {d.strftime('%B')}"


def _site(ev, chans) -> np.ndarray:
    return ev.copy().pick(chans).data.mean(0) * 1e6


# ---- drawing -----------------------------------------------------------------
class Page:
    """One A4 page. Words, cards and badges sit on a layer under the
    charts, placed in page units (0 to 1 across and up)."""

    def __init__(self):
        import matplotlib.pyplot as plt
        self.fig = plt.figure(figsize=A4)
        self.ov = self.fig.add_axes([0, 0, 1, 1], zorder=-1)
        self.ov.set_xlim(0, 1)
        self.ov.set_ylim(0, 1)
        self.ov.axis("off")

    def text(self, x, y, s, size=9.0, bold=False, colour=INK, **kw):
        self.ov.text(x, y, s, fontsize=size, color=colour,
                     fontweight="bold" if bold else "normal", **kw)

    def heading(self, y, title, *how):
        self.text(0.06, y, title, 16, True)
        for k, line in enumerate(how):
            self.text(0.06, y - 0.02 - k * 0.016, line, 9, colour=MUTED)

    def dot(self, x, y, colour):
        self.ov.scatter([x], [y], s=70, color=colour, lw=0)

    def badge(self, x, y, clear: bool, ha="right", va="top"):
        self.ov.text(x, y, "clear" if clear else "not sure yet", fontsize=8, fontweight="bold",
                     color="white", ha=ha, va=va,
                     bbox=dict(boxstyle="round,pad=0.35", fc=GREEN if clear else GREY, ec="none"))

    def card(self, x, y, w, h, title, badge=None, big="", note=""):
        from matplotlib.patches import FancyBboxPatch
        self.ov.add_patch(FancyBboxPatch((x, y), w, h, fc=CARD, ec="none",
                                         boxstyle="round,pad=0,rounding_size=0.012",
                                         mutation_aspect=A4[0] / A4[1]))
        self.text(x + 0.016, y + h - 0.014, title, 10.5, True, va="top")
        if badge is not None:
            self.badge(x + w - 0.014, y + h - 0.012, badge)
        if big:
            self.text(x + 0.016, y + h - 0.045, big, 19, True, va="top")
        if note:
            self.text(x + 0.016, y + 0.012, note, 8, colour=MUTED, va="bottom", linespacing=1.3)

    def chart(self, x, y, w, h):
        ax = self.fig.add_axes([x, y, w, h])
        ax.set_facecolor("none")
        ax.spines[["top", "right", "left"]].set_visible(False)
        ax.spines["bottom"].set_color(GREY)
        ax.tick_params(length=0, labelsize=8, colors=MUTED)
        return ax

    def head(self, x, y, dots, label, w=0.07):
        """A small head from above with the electrodes in use marked,
        dots as (electrode, colour), and their names underneath."""
        ax = self.fig.add_axes([x, y, w, w * A4[0] / A4[1]])
        _outline(ax, 1.1)
        for chan, colour in dots:
            ax.scatter(*SPOT[chan], s=42, color=colour, zorder=3, lw=0)
        self.text(x + w / 2, y - 0.004, label, 7.5, colour=MUTED, ha="center", va="top")


def _outline(ax, lw=1.4) -> None:
    from matplotlib.patches import Circle, Ellipse
    ax.add_patch(Circle((0, 0), 1, fill=False, ec=INK, lw=lw))
    ax.plot([-0.15, 0, 0.15], [0.99, 1.18, 0.99], color=INK, lw=lw, solid_joinstyle="round")
    for side in (-1, 1):
        ax.add_patch(Ellipse((side * 1.05, 0), 0.12, 0.36, fill=False, ec=INK, lw=lw))
    ax.set_xlim(-1.25, 1.25)
    ax.set_ylim(-1.25, 1.25)
    ax.set_aspect("equal")
    ax.axis("off")


def _wave(ax, t, lines, ylim, shade=None, tag="") -> None:
    """Signal against time; the dashed line is the flash or buzz."""
    if shade:
        ax.axvspan(*shade, color=GREY, alpha=0.2, lw=0)
        if tag:
            ax.text(sum(shade) / 2, ylim[1], tag, ha="center", va="bottom", fontsize=7.5,
                    color=MUTED)
    ax.axhline(0, color=GREY, lw=0.8)
    ax.axvline(0, color=INK, lw=1.0, ls=(0, (3, 3)))
    for y, colour in lines:
        ax.plot(t, y, color=colour, lw=2.2)
    ax.set_xlim(t[0], t[-1])
    ax.set_ylim(*ylim)
    ax.spines["bottom"].set_visible(False)
    step = 5
    ticks = np.arange(np.ceil(ylim[0] / step) * step, ylim[1] + 1e-9, step)
    ax.set_yticks(ticks, ["0" if v == 0 else f"{v:+.0f}" for v in ticks])
    sec = np.arange(0, t[-1] + 0.01, 0.4 if t[-1] > 0.7 else 0.2)
    ax.set_xticks(sec, [f"{v:g}" for v in sec[:-1]] + [f"{sec[-1]:g} s"])


def _limits(*waves) -> tuple[float, float]:
    return min(w.min() for w in waves) * 1.1, max(w.max() for w in waves) * 1.15


def _card_bars(pg, x, y, vals, fmt) -> None:
    """Reaction above Buzz Hunt inside a card, the number at the end."""
    ax = pg.fig.add_axes([x + 0.105, y + 0.05, 0.14, 0.055])
    ax.axis("off")
    top = max(max(vals), 1e-9) * 1.6
    for row, (key, v) in enumerate(zip(("reaction", "buzz"), vals)):
        ax.barh(1 - row, max(v, 0), height=0.62, color=GAME[key])
        ax.text(-top * 0.04, 1 - row, NAME[key], ha="right", va="center", fontsize=9, color=INK)
        ax.text(max(v, 0) + top * 0.04, 1 - row, fmt.format(v), va="center", fontsize=11,
                fontweight="bold", color=GAME[key])
    ax.set_xlim(0, top)
    ax.set_ylim(-0.55, 1.55)


def _footer(pg) -> None:
    pg.badge(0.06, 0.026, True, ha="left", va="center")
    pg.text(0.112, 0.026, "very unlikely to be luck", 8, colour=MUTED, va="center")
    pg.badge(0.34, 0.026, False, ha="left", va="center")
    pg.text(0.432, 0.026, "could be luck, needs more tries", 8, colour=MUTED, va="center")


# ---- page 1: the two games side by side ---------------------------------------
def _compare_page(s: dict, c: dict):
    import mne
    pg = Page()
    m, t = c["modes"], c["tests"]
    r, b = m["reaction"], m["buzz"]
    pg.text(0.06, 0.948, f"{s.get('participant') or 'Participant'}, {_date(s)}", 26, True)
    what = {"reaction": "Reaction game: a square flashes and beeps",
            "buzz": "Buzz Hunt: a finger buzzes"}
    for k, key in enumerate(("reaction", "buzz")):
        y = 0.918 - k * 0.019
        gap = m[key].get("spacing_s")
        pg.dot(0.066, y, GAME[key])
        pg.text(0.078, y, what[key] + (f", one every {gap[0]:.1f} to {gap[1]:.1f} s" if gap else ""),
                10, va="center")

    pg.heading(0.862, "Reaction game vs Buzz Hunt")
    cards = [("Time to press", t.get("RT, buzz minus reaction"),
              [r["rt_ms"] / 1000, b["rt_ms"] / 1000], "{:.2f} s", "Shorter bar = faster."),
             ("Attention signal (P3)", t.get("P3 300-650 ms, buzz minus reaction"),
              [r["p3_uV"], b["p3_uV"]], "{:.1f}",
              "Bigger bar = stronger.\nIn µV (millionths of a volt)."),
             ("Attention timing", t.get("P3 latency, buzz minus reaction"),
              [r["p3_latency_ms"] / 1000, b["p3_latency_ms"] / 1000], "{:.2f} s",
              "When the middle of the signal came.\nShorter bar = sooner.")]
    for k, (title, test, vals, fmt, note) in enumerate(cards):
        x = 0.06 + k * 0.3
        pg.card(x, 0.70, 0.28, 0.145, title, badge=_clear(test), note=note)
        _card_bars(pg, x, 0.70, vals, fmt)

    pg.heading(0.652, "The brain signal after each flash or buzz",
               "Orange: Reaction game. Purple: Buzz Hunt. Each line is the average of all the tries.",
               "Dashed line: the flash or buzz. Up and down in µV.")
    ev = {k: e.average() for k, e in c["epochs"].items()}
    win = [v / 1000 for v in (s.get("compare") or {}).get("p3_window_ms", [300, 650])]
    spots = [("Back of head (seeing)", ["Oz"], None),
             ("Top of head (middle)", ["Cz"], None),
             ("Left side (right hand area)", ["C3"], None),
             ("Top back (paying attention)", ["Pz", "CPz"], win)]
    waves = {(key, i): _site(ev[key], sp[1]) for i, sp in enumerate(spots) for key in GAME}
    ylim = _limits(*waves.values())
    for i, (title, chans, shade) in enumerate(spots):
        x0, y0 = 0.06 + (i % 2) * 0.47, 0.50 - (i // 2) * 0.135
        pg.head(x0, y0 + 0.012, [(ch, INK) for ch in chans], ", ".join(chans))
        ax = pg.chart(x0 + 0.105, y0, 0.31, 0.075)
        _wave(ax, ev["reaction"].times, [(waves[("reaction", i)], GAME["reaction"]),
                                         (waves[("buzz", i)], GAME["buzz"])],
              ylim, shade, "attention" if shade else "")
        pg.text(x0, y0 + 0.09, title, 10, True)

    pg.heading(0.312, "Where on the head the attention signal was",
               "Looking down on the head, nose at the top. Red: signal up. Blue: signal down.")
    data = {k: e.copy().pick("eeg") for k, e in ev.items()}
    at = {k: data[k].data[:, int(np.argmin(np.abs(data[k].times - m[k]["p3_latency_ms"] / 1000)))]
          * 1e6 for k in data}
    lim = max(np.abs(x).max() for x in at.values()) * 0.85
    cue = {"reaction": "flash", "buzz": "buzz"}
    for k, key in enumerate(("reaction", "buzz")):
        x0, w = 0.12 + k * 0.51, 0.25
        ax = pg.fig.add_axes([x0, 0.08, w, w * A4[0] / A4[1]])
        mne.viz.plot_topomap(at[key], data[key].info, axes=ax, show=False, cmap="RdBu_r",
                             vlim=(-lim, lim), contours=0, sensors=False)
        pg.text(x0 + w / 2, 0.262, "Reaction game" if key == "reaction" else NAME[key], 11, True,
                colour=GAME[key], ha="center")
        pg.text(x0 + w / 2, 0.072, f"{_s(m[key]['p3_latency_ms'])} after the {cue[key]}", 8.5,
                colour=MUTED, ha="center", va="top")
        pg.text(x0 - 0.006, 0.168, "left", 8, colour=MUTED, ha="right", va="center")
        pg.text(x0 + w + 0.006, 0.168, "right", 8, colour=MUTED, va="center")
    key_ax = pg.fig.add_axes([0.493, 0.115, 0.014, 0.105])
    key_ax.imshow(np.linspace(1, -1, 256)[:, None], aspect="auto", cmap="RdBu_r")
    key_ax.set_axis_off()
    pg.text(0.5, 0.226, "up", 8, colour=MUTED, ha="center", va="bottom")
    pg.text(0.5, 0.109, "down", 8, colour=MUTED, ha="center", va="top")
    _footer(pg)
    return pg.fig


# ---- page 2: each game on its own ---------------------------------------------
def _learning(pg, s: dict, r) -> None:
    srt = s["srt"]
    lr, rc = srt.get("learning", {}), srt.get("recall", {})
    st, bt = srt.get("stim_tests", {}), srt.get("band_tests", {})
    pattern = f"a repeating pattern of {rc['items']}" if rc else "a repeating pattern"
    pg.heading(0.95, "Learning a pattern (Reaction game)",
               f"The squares lit up at random, then in {pattern}, then at random again.")
    y, h, w = 0.80, 0.105, 0.28
    b1, b8 = lr.get("block1_ms", 0), lr.get("block8_ms", 0)
    pg.card(0.06, y, w, h, "Got faster with practice" if b8 < b1 else "Speed with practice",
            big=f"{b1 / 1000:.2f} → {_s(b8)}", note="Time to press, pattern block 1 vs 8.")
    ci = lr.get("post_minus_block8_ci") or [0, 0]
    cost = lr.get("post_minus_block8_ms", 0)
    pg.card(0.36, y, w, h, "Pattern taken away", badge=ci[0] > 0 or ci[1] < 0,
            big=f"{abs(cost) / 1000:.2f} s {'slower' if cost > 0 else 'faster'}",
            note="Random again after block 8.")
    if rc:
        whole = rc["cyclic_correct"] == rc["items"]
        note = ("All in the right order" + ("." if rc["correct"] == rc["items"] else
                                            ",\nstarting at a different point in the loop.")
                if whole else f"{rc['cyclic_correct']} of {rc['items']} in the right order.")
        pg.card(0.66, y, w, h, "Typed the pattern back", badge=_clear({"p": rc.get("chance_p")}),
                big=f"{rc['cyclic_correct']} / {rc['items']}", note=note)

    bh = r.behaviour
    ax = pg.chart(0.06, 0.585, 0.38, 0.13)
    lab = ["Start" if x == "Practice" else "End" if x == "Post-test" else x.replace("Sequence ", "")
           for x in bh.segment]
    col = [GREY if x == "Practice" else RED if x == "Post-test" else BLUE for x in bh.segment]
    ax.bar(range(len(lab)), bh.rt_median_ms / 1000, color=col, width=0.7)
    ax.set_xticks(range(len(lab)), lab)
    top = float(max(bh.rt_median_ms)) / 1000 * 1.15
    ax.set_ylim(0, top)
    ax.set_yticks(np.arange(0, top, 0.1), [f"{v:.1f}" for v in np.arange(0, top, 0.1)])
    pg.text(0.06, 0.765, "Time to press, block by block", 11, True)
    pg.text(0.06, 0.748, "Seconds. Blue: the pattern. Grey and red: random order.", 8, colour=MUTED)

    n2, p3 = st.get(FD.N2_TEST, {}), st.get(FD.P3_TEST, {})
    adj = FD.holm([n2.get("p"), p3.get("p")])
    ev_l, ev_r = r.stim.get("sequence_late"), r.stim.get("random_posttest")
    if ev_l is not None and ev_r is not None:
        pg.head(0.53, 0.615, [("FCz", INK), ("Cz", INK)], "FCz, Cz")
        ax = pg.chart(0.635, 0.585, 0.305, 0.13)
        ys = [_site(ev_l, ["FCz", "Cz"]), _site(ev_r, ["FCz", "Cz"])]
        _wave(ax, ev_l.times, [(ys[0], BLUE), (ys[1], RED)], _limits(*ys), (0.2, 0.3), "surprise")
        pg.text(0.53, 0.765, "Surprise signal (N2)", 11, True)
        pg.text(0.53, 0.748, "Blue: the pattern. Red: random. A deeper dip = more surprise.", 8,
                colour=MUTED)
        pg.badge(0.94, 0.779, adj[0] is not None and adj[0] < FD.ALPHA)

    ern = (srt.get("resp_tests") or {}).get(FD.ERN_TEST)
    beta = bt.get("beta C3")
    small = [("Attention signal", p3 and adj[1] is not None and adj[1] < FD.ALPHA,
              "Smaller once learned" if (p3 or {}).get("diff", 0) > 0 else "Bigger once learned",
              "P3, top back of the head.", p3),
             ("Movement hum", _clear(beta),
              "Quieter once learned" if (beta or {}).get("diff", 0) > 0 else "Louder once learned",
              "Beta, left side (right hand area).", beta),
             ("Mistake signal", _clear(ern),
              "Dips after mistakes" if (ern or {}).get("diff", 0) < 0 else "No dip after mistakes",
              "ERN, top of the head.", ern)]
    for k, (title, ok, result, note, test) in enumerate(small):
        if not test:
            continue
        x = 0.06 + k * 0.3
        pg.card(x, 0.462, w, 0.085, title, badge=bool(ok), note=note)
        pg.text(x + 0.016, 0.505, result, 12, True, va="center")


def _buzz(pg, s: dict, rb) -> None:
    bz = s["buzz"]
    tests = bz.get("tests", {})
    pg.heading(0.42, "Feeling the buzz (Buzz Hunt)",
               f"One finger buzzed and {s.get('participant') or 'the player'} pressed that finger.")
    y, h, w = 0.27, 0.105, 0.28
    lanes = (bz.get("per_lane") or {}).values()
    n, hit = sum(x["n"] for x in lanes), sum(x["correct"] for x in lanes)
    pg.card(0.06, y, w, h, "Found the right finger", big=f"{bz.get('loc_accuracy', 0) * 100:.0f}%",
            note=f"{hit} of {n} tries." if n else "")
    pg.card(0.36, y, w, h, "Time to press", big=_s(bz.get("loc_rt_ms", 0)),
            note="From the buzz to the press.")
    mu = tests.get(FD.MU_TEST)
    if mu:
        pg.card(0.66, y, w, h, "Movement hum", badge=_clear(mu),
                big=f"{'Dropped' if mu['diff'] < 0 else 'Rose'} {abs(mu['diff']):.0f}%",
                note="Mu, left side, just after the buzz.")

    ev = rb.erp.get("localisation")
    if ev is not None:
        pg.head(0.06, 0.09, [("C3", GAME["buzz"]), ("C4", GREY)], "C3, C4")
        ax = pg.chart(0.17, 0.06, 0.77, 0.13)
        ys = [_site(ev, ["C3", "CP3", "CP5"]), _site(ev, ["C4", "CP4", "CP6"])]
        _wave(ax, ev.times, [(ys[0], GAME["buzz"]), (ys[1], GREY)], _limits(*ys), (0.18, 0.26),
              "touch")
        pg.text(0.06, 0.235, "Left vs right side of the head after the buzz", 11, True)
        pg.text(0.06, 0.218, "Purple: left side, which feels the right hand. Grey: right side.", 8,
                colour=MUTED)
        pg.badge(0.94, 0.249, _clear(tests.get(FD.TOUCH_TEST)))


def _games_page(s: dict, results: dict):
    pg = Page()
    if s.get("srt") and results.get("srt") is not None:
        _learning(pg, s, results["srt"])
    if s.get("buzz") and results.get("buzz_hunt") is not None:
        _buzz(pg, s, results["buzz_hunt"])
    _footer(pg)
    return pg.fig


# ---- the document ------------------------------------------------------------
def build(s: dict, out: Path, results: dict | None = None, cmp: dict | None = None) -> list[str]:
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    results = results or {}
    with plt.rc_context({"font.family": FONTS, "pdf.fonttype": 42, "axes.unicode_minus": False}):
        pages = []
        if cmp and "epochs" in cmp:
            pages.append(_compare_page(s, cmp))
        if results.get("srt") is not None or results.get("buzz_hunt") is not None:
            pages.append(_games_page(s, results))
        if not pages:
            return []
        path = out / "EEG_report.pdf"
        title = f"{s.get('participant') or 'Participant'}, {_date(s)}"
        with PdfPages(path, metadata={"Title": title}) as pdf:
            for fig in pages:
                pdf.savefig(fig)
                plt.close(fig)
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
            f"(p {p('P3 300-650 ms, buzz minus reaction')}); P3 half-area latency "
            f"{r['p3_latency_ms']:.0f} vs {b['p3_latency_ms']:.0f} ms "
            f"(p {p('P3 latency, buzz minus reaction')}); median RT {r['rt_ms']:.0f} vs "
            f"{b['rt_ms']:.0f} ms (p {p('RT, buzz minus reaction')})."]
