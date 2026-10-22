"""The final data (8 to 22 October 2026) for the Curtin EEG laboratory
to check, as tables and figures with one-line captions: the sequence
task, press timing, the EEG markers, the early and learning responses
with the whole-head maps from each recording's own run, the error
signal, the device's own games and the processing. People are Person
1 to 6, as in the thesis.

    cd analysis
    python3 review_report.py --root RESULTS --out PDF --eeg S1 S2 --eeg-results D1 D2

RESULTS is the git-ignored results folder, S1 and S2 the two EEG
session folders and D1 and D2 their results' detail folders. The waves
are read once from each session's cached run (eeg.group.cached) and
kept beside the PDF, so a rebuild takes seconds.
"""
from __future__ import annotations

import argparse
import gc
import itertools
import json
import pickle
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from eeg import report as RP
from eeg.findings import p_text

# where each analysis left its results, inside RESULTS
SEQUENCE = "5 Thesis results/sequence_task/sequence_task.json"
PRESS = "5 Thesis results/press_check/press_check.json"
GROUP = "3 EEG lab/results/group_2026-10-22/group_summary.json"
SITTING = "1 Healthy study/sessions/cohort_results/cohort_metrics.csv"
EXTRA = "5 Thesis results/extra_blocks/sessions/cohort_results/cohort_metrics.csv"

# the sequence task's players as the PDF names them, the two EEG people first,
# and their colours (checked for colour-blind separation across all pairs)
NAMES = {"E1": "Person 1", "E2": "Person 2", "L1": "Person 3", "L2": "Person 4"}
ORDER = ["E1", "E2", "L1", "L2"]
HUE = {"E1": "#2a78d6", "L1": "#eb6834", "L2": "#1baf7a", "E2": "#a83279"}
MARK = {"E1": "o", "L1": "s", "L2": "^", "E2": "D"}
PATTERN, RANDOM = RP.KIND["pattern"][0], RP.KIND["random"][0]
PLANNED = {"N2": "N2: random_posttest vs sequence_late", "P3": "P3: random_practice vs sequence_late",
           "beta": "beta: random_posttest vs sequence_late", "P3 check": "P3: random_posttest vs sequence_late"}
INK, SOFT, MUTED, LINE, GREY = RP.INK, RP.SOFT, RP.MUTED, RP.LINE, RP.GREY
X0, W = RP.X0, RP.W


def _p(v) -> str:
    return "p " + p_text(v)


# ---- reading the results ---------------------------------------------------------
def eeg_waves(sessions: list[Path], keep: Path) -> list[dict]:
    """The waves and marker checks each EEG figure needs, taken from each
    session's cached run once and kept in keep."""
    if keep.is_file():
        stored = pickle.loads(keep.read_bytes())
        if stored.get("sessions") == [str(s.resolve()) for s in sessions]:
            return stored["waves"]
    import mne

    from eeg import checks as C
    from eeg.analyses import SRT_WINDOWS
    from eeg.group import cached, evoked
    mne.set_log_level("ERROR")
    out = []
    for s in sessions:
        blocks, cleaned, results = cached(s)
        c = C.compute(blocks, cleaned, results)
        f = c["sensory"]["flash"]
        erp = {}
        for comp, conds in (("N2", ("random_posttest", "sequence_late")),
                            ("P3", ("random_practice", "sequence_late", "random_posttest"))):
            for cond in conds:
                w = evoked(results, cond, SRT_WINDOWS[comp][1])
                if w is not None:
                    erp[f"{comp} {cond}"] = w
        out.append({"flash": {k: f[k] for k in ("ms", "control O1/O2", "n", "of", "halves", "pattern", "random")},
                    "rt": c["rt"], "errors": c["errors"], "erp": erp})
        del blocks, cleaned, results, c
        gc.collect()
    keep.parent.mkdir(parents=True, exist_ok=True)
    keep.write_bytes(pickle.dumps({"sessions": [str(s.resolve()) for s in sessions], "waves": out}))
    return out


def game_values(root: Path) -> dict:
    """Each game's measures from the analysis notebook, by participant."""
    m = pd.concat([pd.read_csv(root / SITTING), pd.read_csv(root / EXTRA)])
    return {(r.participant, r.mode, r.metric): float(r.value) for r in m.itertuples()}


# ---- the pieces of a page ---------------------------------------------------------------
def _table(doc: RP.Doc, n, caption, rows, widths, header, right=()):
    pg = doc.need(doc.pg.table_height(n, caption, rows, widths, header))
    pg.table(n, caption, rows, widths, header, right=right)


def _figure(doc: RP.Doc, n, caption, h, top=0.014) -> tuple[RP.Page, float]:
    """Room for a figure of height h and its caption; the bottom of the
    figure's space."""
    pg = doc.need(top + h + doc.pg.caption_height(n, caption))
    pg.y -= top
    return pg, pg.take(h)


def _head(doc: RP.Doc, secs, title, lead="") -> RP.Page:
    """A numbered heading, with a lead line only where one is needed."""
    if lead:
        return doc.heading(next(secs), title, lead)
    pg = doc.need(0.014 + 0.045 + 0.08)
    pg.heading(next(secs), title)
    return pg


LABEL, GAP = 0.022, 0.012


def _image(doc: RP.Doc, n, caption, paths, labels, width=W) -> None:
    """Figures the EEG analysis saved for each recording (detail/figures),
    one under another at the given share of the page width, each under
    its person's label."""
    import matplotlib.image as mpimg
    imgs = [mpimg.imread(str(f)) for f in paths]
    hs = [width * RP.A4[0] * im.shape[0] / im.shape[1] / RP.A4[1] for im in imgs]
    total = sum(hs) + LABEL * sum(1 for lab in labels if lab) + GAP * (len(imgs) - 1)
    pg, y0 = _figure(doc, n, caption, total)
    top = y0 + total
    for im, h, lab in zip(imgs, hs, labels):
        if lab:
            _label(pg, X0, top, lab)
            top -= LABEL
        ax = pg.axes(X0 + (W - width) / 2, top - h, width, h)
        ax.imshow(im)
        ax.axis("off")
        top -= h + GAP
    pg.caption(n, caption)


def _head_table(doc: RP.Doc, secs, title, n, caption, rows, widths, header) -> None:
    """A section's heading and its first table, kept on one page."""
    doc.need(0.014 + 0.045 + doc.pg.table_height(n, caption, rows, widths, header))
    _head(doc, secs, title).table(n, caption, rows, widths, header)


def _label(pg, x, y, s):
    pg.text(x, y, s, 9.5, True, va="top")


def _tidy(ax, xlabel="", ylabel=""):
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=8.5, color=SOFT)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=8.5, color=SOFT)


# ---- the front page -------------------------------------------------------------------------
def _front(doc: RP.Doc, tabs) -> None:
    pg = doc.pg
    pg.write("Final results", 22, True, after=0.0)
    pg.write("Sessions from 8 to 22 October 2026", 10, colour=MUTED, after=0.01)
    pg.ov.plot([X0, X0 + W], [pg.y, pg.y], color=LINE, lw=0.8)
    pg.y -= 0.012
    rows = [["Person 1", "8 Oct", "Sequence task, then Buzz Hunt", "Yes"],
            ["Person 2", "22 Oct", "Sequence task", "Yes"],
            ["Person 3", "15 Oct", "Sequence task", "No"],
            ["Person 4", "19 Oct", "Sequence task", "No"],
            ["Person 5", "20 Oct", "30-minute sitting of six games", "No"],
            ["Person 6", "15 Oct", "One Force Pilot block", "No"]]
    _table(doc, next(tabs), "Who played what.", rows, [0.12, 0.1, 0.4, 0.22], ["Person", "Date", "Played", "EEG"])


# ---- 1: sequence learning -----------------------------------------------------------------
def _sequence(doc: RP.Doc, seq, figs, tabs, secs) -> None:
    from sequence_task import SEGMENTS
    people, g = seq["people"], seq["group"]
    L = {k: people[k]["learning"] for k in ORDER}
    M = seq["mixed"]
    x = M["post_minus_block8"]
    pq = {k: people[k]["prediction"]["sequence"] for k in ORDER}
    ge = g["prediction"]["sequence"]
    rows = [["Learning score, ms (95% CI)",
             *[f"{L[k]['post_minus_block8_ms']:+.0f} ({L[k]['post_minus_block8_ci'][0]:.0f} to "
               f"{L[k]['post_minus_block8_ci'][1]:.0f})" for k in ORDER],
             f"{g['mean_ms']:+.0f} ({g['ci_ms'][0]:.0f} to {g['ci_ms'][1]:.0f})"],
            ["Mixed model, ms (95% CI)", "", "", "", "",
             f"{x['estimate']:+.0f} ({x['lower']:.0f} to {x['upper']:.0f}), {_p(x['p'])}"],
            ["Early presses on the right finger",
             *[f"{100 * pq[k]['right'] / pq[k]['early']:.0f}%" for k in ORDER],
             f"{100 * ge['right'] / ge['early']:.0f}% (guessing 33%)"],
            ["Score without presses under 100 ms",
             *[f"{people[k]['floored_ms']['100']:+.0f}" for k in ORDER], f"{g['floored']['100']['mean_ms']:+.0f}"]]
    _head_table(doc, secs, "Sequence learning", next(tabs),
                "Learning score: post-test minus block 8, correct presses under 1000 ms, each block's first trial "
                "left out. Mixed model: each person's own speed and learning effect.",
                rows, [0.24, 0.115, 0.115, 0.115, 0.115, 0.14], ["", *[NAMES[k] for k in ORDER], "All"])
    n = next(figs)
    cap = ("(a) Median RT per block and the mixed model's means (black); grey: random blocks. (b) Learning "
           "scores with 95% intervals.")
    h = 0.2
    pg, y0 = _figure(doc, n, cap, h)
    ax = pg.axes(X0 + 0.05, y0 + 0.045, 0.5, h - 0.07)
    xs = np.arange(len(SEGMENTS))
    for x in (0, len(SEGMENTS) - 1):
        ax.axvspan(x - 0.4, x + 0.4, color=GREY, alpha=0.2, lw=0)
    for k in ORDER:
        seg = {r["segment"]: r["rt_median_ms"] for r in people[k]["segments"]}
        ax.plot(xs, [seg.get(s, np.nan) for s in SEGMENTS], color=HUE[k], lw=1.6, marker=MARK[k], ms=4.5,
                mec="white", mew=0.6, label=NAMES[k])
    em = M["emmeans"]
    ax.plot(xs, [em[s]["estimate"] for s in SEGMENTS], color=INK, lw=2.2, marker="o", ms=3.5, zorder=5,
            label="Mixed model")
    ax.set_xticks(xs)
    ax.set_xticklabels(["Rnd"] + [str(i) for i in range(1, 9)] + ["Rnd"])
    ax.set_xlim(-0.6, len(SEGMENTS) - 0.4)
    _tidy(ax, "Block", "Reaction time (ms)")
    ax.legend(frameon=False, fontsize=8, ncols=5, loc="lower left", bbox_to_anchor=(0.0, 1.0),
              borderaxespad=0.2, handlelength=1.8, columnspacing=1.0)
    _label(pg, X0, y0 + h + 0.012, "(a) Reaction time through the task")
    ax = pg.axes(X0 + 0.65, y0 + 0.045, 0.19, h - 0.07)
    for i, (k, v) in enumerate(L.items()):
        lo, hi = v["post_minus_block8_ci"]
        ax.errorbar(i, v["post_minus_block8_ms"], yerr=[[v["post_minus_block8_ms"] - lo],
                                                         [hi - v["post_minus_block8_ms"]]],
                    fmt=MARK[k], color=HUE[k], ms=5, capsize=2.5, lw=1.4, mec="white", mew=0.6)
    i = len(L) + 0.3
    ax.errorbar(i, g["mean_ms"], yerr=[[g["mean_ms"] - g["ci_ms"][0]], [g["ci_ms"][1] - g["mean_ms"]]],
                fmt="o", color=INK, ms=5.5, capsize=3, lw=1.8)
    ax.axhline(0, color=LINE, lw=0.8)
    ax.set_xticks(list(range(len(L))) + [i])
    ax.set_xticklabels([NAMES[k].split()[1] for k in L] + ["Mean"], fontsize=8)
    ax.set_xlim(-0.6, i + 0.6)
    _tidy(ax, "Person", "Post-test minus block 8 (ms)")
    _label(pg, X0 + 0.58, y0 + h + 0.012, "(b) Learning score")
    pg.caption(n, cap)


# ---- 2: the press check ----------------------------------------------------------------------
def _press(doc: RP.Doc, press, figs, tabs, secs) -> None:
    from matplotlib.ticker import MaxNLocator

    from sequence_task import SEGMENTS
    seg = {k: pd.DataFrame(press[k]["segments"]).set_index("segment") for k in ORDER}
    rows = [["Push start to counted press, ms (IQR)",
             *[f"{press[k]['lag_ms'][1]:.0f} ({press[k]['lag_ms'][0]:.0f} to {press[k]['lag_ms'][2]:.0f})"
               for k in ORDER]],
            ["Spread of block medians, ms", *[f"{press[k]['lag_vs_segment_spread_ms']:.0f}" for k in ORDER]],
            ["r, RT at count against push", *[f"{press[k]['r_press_onset']:.3f}" for k in ORDER]],
            ["Released within 60 ms", *[str(press[k]["held_under_60ms"]) for k in ORDER]],
            ["Light touch before the push",
             *[f"{press[k]['weak_first_then_real']} of {press[k]['counted_presses']}" for k in ORDER]]]
    _head_table(doc, secs, "Press timing", next(tabs),
                "Each counted press against the start of its push on the force record.",
                rows, [0.32, 0.13, 0.13, 0.13, 0.13], ["", *[NAMES[k] for k in ORDER]])
    n = next(figs)
    cap = ("Median RT per block at the counted press (solid) and the push start (dotted). Person 4's gap varies "
           "more because it is a difference of two medians.")
    h = 0.3
    pg, y0 = _figure(doc, n, cap, h)
    xs = np.arange(len(SEGMENTS))
    for i, k in enumerate(ORDER):
        p = press[k]
        col, row = i % 2, i // 2
        x = X0 + 0.07 + col * 0.42
        y = y0 + 0.04 + (1 - row) * 0.135
        ax = pg.axes(x, y, 0.33, 0.085)
        s = seg[k].reindex(SEGMENTS)
        for x0 in (0, len(SEGMENTS) - 1):
            ax.axvspan(x0 - 0.4, x0 + 0.4, color=GREY, alpha=0.2, lw=0)
        ax.plot(xs, s.rt_press_ms, color=INK, lw=1.8, marker="o", ms=3.5, label="at the counted press")
        ax.plot(xs, s.rt_onset_ms, color=INK, lw=1.4, ls=(0, (1.5, 1.5)), marker="o", ms=3.5, mfc="white",
                label="at the start of the push")
        ax.set_xticks(xs)
        ax.set_xticklabels(["Rnd"] + [str(j) for j in range(1, 9)] + ["Rnd"] if row else [])
        ax.set_xlim(-0.6, len(SEGMENTS) - 0.4)
        ax.yaxis.set_major_locator(MaxNLocator(4, integer=True))
        _tidy(ax, "Block" if row else "", "RT (ms)" if col == 0 else "")
        lo, mid, hi = p["lag_ms"]
        pg.text(x, y + 0.085 + 0.022, f"{NAMES[k]}: lag {mid:.0f} ms ({lo:.0f} to {hi:.0f}), "
                                      f"r = {p['r_press_onset']:.3f}", 9, True, va="top")
        if i == 0:
            pg.fig.legend(*ax.get_legend_handles_labels(), loc="lower left", bbox_to_anchor=(x, y0 + h),
                          ncols=2, frameon=False, fontsize=8, handlelength=2.6, columnspacing=2.0)
    pg.caption(n, cap)


# ---- 3: the markers ------------------------------------------------------------------------------
def _markers(doc: RP.Doc, s1, s2, tabs, secs) -> None:
    c1, c2 = s1["checks"], s2["checks"]

    def matched(s):
        return f"{s['markers_matched']:,} of {s['markers_total']:,}"

    def fails(c):
        q = c["queue"].values()
        return "None" if all(v["failed"] == 0 and v["dropped"] == 0 for v in q) else "Some"

    def flashes(c):
        n = {r[0]: r[1] for r in c["by_condition"]}
        seq = sum(v for k, v in n.items() if k.startswith("Pattern"))
        return f"{n['Random, practice']}, {seq}, {n['Random, post-test']}"

    def presses(c):
        n = dict((r[0], r[2]) for r in c["counts"])
        return ", ".join(str(n[k]) for k in ("Correct presses", "Wrong finger", "Early presses", "Misses"))

    def wait(c):
        return f"{c['gaps_s']['press_next'][1]:.2f} s (practice {c['gaps_s']['press_next_practice'][1]:.2f} s)"

    def lanes(c):
        right, of = c["order"]["lanes"]
        return f"{right:,} of {of:,}"

    def spread(c):
        return f"{c['timing_ms']['sd']:.2f} ms ({c['timing_ms']['max']:.2f} ms)"
    halves = all(len(set(c["timing_halves_ms"]["srt"])) == 1 for c in (c1, c2))
    assert c1["by_condition_match"] and c2["by_condition_match"]
    rows = [["Markers matching the log", matched(s1), matched(s2)],
            ["Flashes: practice, sequence, post-test", flashes(c1), flashes(c2)],
            ["Presses: right, wrong, early, missed", presses(c1), presses(c2)],
            ["Response markers on the logged finger", lanes(c1), lanes(c2)],
            ["Press to next flash (500 ms wait)", wait(c1), wait(c2)],
            ["Timing spread (largest)", spread(c1), spread(c2)],
            ["RT, recording against log", f"r = {c1['rt']['r']:.5f}", f"r = {c2['rt']['r']:.5f}"],
            ["Markers failed or dropped", fails(c1), fails(c2)]]
    _head_table(doc, secs, "EEG markers", next(tabs),
                "Markers against the game's log; every count matches. Spread: SD around the fitted clock"
                + (", the same in each half." if halves else "."),
                rows, [0.4, 0.21, 0.21], ["Check", "EEG person 1", "EEG person 2"])


# ---- 4: early responses to the flash -------------------------------------------------------------
def _sensory(doc: RP.Doc, waves, buzz, details, figs, tabs, secs) -> None:
    def swing(w, wave):
        ms = np.asarray(w["flash"]["ms"])
        return float(np.abs(np.asarray(wave)[(ms >= 0) & (ms <= 300)]).max())
    fl = [w["flash"] for w in waves]
    rows = [["Flash P1, sequence trials, ms", *[f"{f['pattern']['P1'][0]:.0f}" for f in fl]],
            ["Flash N1, sequence trials, ms", *[f"{f['pattern']['N1'][0]:.0f}" for f in fl]],
            ["Flash P1, random trials, ms", *[f"{f['random']['P1'][0]:.0f}" for f in fl]],
            ["P1 in each half, ms", *[" and ".join(f"{h[0]:.0f}" for h in f["halves"]) for f in fl]],
            ["Largest swing to 0.3 s: flash, random times, µV",
             *[f"{swing(w, w['flash']['pattern']['O1/O2']):.1f}, {swing(w, w['flash']['control O1/O2']):.1f}"
               for w in waves]],
            ["Buzz, opposite hand area, ms", f"{buzz['first'][0]:.0f} and {buzz['neg'][0]:.0f}", "Not played"]]
    _head_table(doc, secs, "Early responses", next(tabs),
                "Early responses: flash at O1 and O2; random times are the control.",
                rows, [0.42, 0.2, 0.2], ["", "EEG person 1", "EEG person 2"])
    n = next(figs)
    cap = "Average at O1 and O2 around each flash: sequence (blue), random (orange), random times (grey)."
    h = 0.3
    pg, y0 = _figure(doc, n, cap, h)
    for k, (title, w) in enumerate(zip(("(a) EEG person 1", "(b) EEG person 2"), waves)):
        f = w["flash"]
        bottom = y0 + (1 - k) * 0.15 + 0.035
        pg.head(X0, bottom + 0.02, ["O1", "O2"], "back", PATTERN)
        ax = pg.axes(X0 + 0.13, bottom, W - 0.13, 0.085)
        p, rr = f["pattern"], f["random"]
        RP._wave(ax, f["ms"], [(p["O1/O2"], PATTERN, f"sequence ({p['n']})", "-"),
                               (rr["O1/O2"], RANDOM, f"random ({rr['n']})", "-"),
                               (f["control O1/O2"], GREY, "random times", "-")],
                 xlabel="Time after the flash (s)" if k else "")
        RP._mark(ax, p["P1"], "P1", PATTERN)
        RP._mark(ax, p["N1"], "N1", PATTERN)
        _label(pg, X0, bottom + 0.118, title)
    pg.caption(n, cap)
    _image(doc, next(figs), "The whole head through the response to the flash: every channel (lines) and the "
                            "scalp at four moments (maps), all correct trials.",
           [d / "figures" / "11_srt_erp_joint.png" for d in details], ["EEG person 1", "EEG person 2"], width=0.62)
    _image(doc, next(figs), "EEG person 1, the whole head after a flash (Reaction) and after a buzz (Buzz Hunt).",
           [details[0] / "figures" / "31_compare_scalp_maps.png"], [""])


# ---- 5: learning in the brain signal --------------------------------------------------------------
def _learning(doc: RP.Doc, grp, s1, s2, waves, details, figs, tabs, secs) -> None:
    t = grp["tests"]
    one = [s1["srt"], s2["srt"]]

    def cell(test, unit=""):
        return f"{test['diff']:+.1f}, {_p(test['p'])}".replace("+0.0", "0.0")

    def both(key):
        x = t[key]
        s = cell(x)
        return s + (f" (Holm {p_text(x['p_holm']).lstrip('= ')})" if "p_holm" in x else "")
    rows = [["N2, random minus learned (µV)",
             *[cell(s["stim_tests"][PLANNED["N2"]]) for s in one], both(PLANNED["N2"])],
            ["P3, random practice minus learned (µV)",
             *[cell(s["stim_tests"][PLANNED["P3"]]) for s in one], both(PLANNED["P3"])],
            ["Beta at C3, random minus learned (dB)",
             *[cell(s["band_tests"]["beta C3"]) for s in one], both(PLANNED["beta"])],
            ["Check: P3, random post-test minus learned",
             *[cell(s["stim_tests"][PLANNED["P3 check"]]) for s in one], both(PLANNED["P3 check"])],
            *[[label, *[cell(grp["beta_timing"][kind]["per_person"][n]) for n in ("EEG Subject 1", "EEG Subject 2")],
               cell(grp["beta_timing"][kind]["both"])]
              for kind, label in (("matched", "Check: beta, reaction times matched"),
                                  ("press", "Check: beta before the press"))]]
    reads = ["Person 1 only", "Smaller when learned", "Lower when learned", "As small: time on task",
             "Holds", "Holds"]
    rows = [r + [m] for r, m in zip(rows, reads)]
    tn = next(tabs)
    tcap = ("N2 and P3 planned, Holm across the two; beta secondary. Learned: sequence blocks 7 and 8. Both: "
            "labels shuffled within each person.")
    widths, header = [0.28, 0.13, 0.13, 0.17, 0.13], ["Measure", "EEG person 1", "EEG person 2", "Both", "Reads as"]
    doc.need(0.014 + 0.045 + doc.pg.table_height(tn, tcap, rows, widths, header))
    pg = _head(doc, secs, "Learning in the brain signal")
    pg.table(tn, tcap, rows, widths, header)
    n = next(figs)
    cap = "Random (orange) against learned (blue), trials in the legend. Grey: test window."
    from eeg.analyses import SRT_WINDOWS
    h = 0.29
    pg, y0 = _figure(doc, n, cap, h)
    panels = (("N2", "random_posttest", ["FCz", "Cz"], "top front"),
              ("P3", "random_practice", ["Pz", "CPz"], "top back"))
    for row, (name, w, s_) in enumerate(zip(("EEG person 1", "EEG person 2"), waves, one)):
        yb = y0 + (1 - row) * 0.145
        for col, (comp, rnd, chans, place) in enumerate(panels):
            xx = X0 + col * 0.43
            pg.head(xx, yb + 0.05, chans, place, PATTERN)
            ax = pg.axes(xx + 0.11, yb + 0.035, 0.29, 0.08)
            ms, ran = w["erp"][f"{comp} {rnd}"]
            late = w["erp"][f"{comp} sequence_late"][1]
            RP._wave(ax, ms, [(ran, RANDOM, f"random ({s_['stim_n'][rnd]})", "-"),
                              (late, PATTERN, f"learned ({s_['stim_n']['sequence_late']})", "-")],
                     shade=SRT_WINDOWS[comp][0], xlabel="Time after the flash (s)" if row else "")
            _label(pg, xx, yb + 0.137, f"{comp}, {name}")
    pg.caption(n, cap)
    _image(doc, next(figs), "The whole head in the N2 and P3 windows through the task; right: random minus learned.",
           [d / "figures" / "13_srt_erp_topomaps.png" for d in details], ["EEG person 1", "EEG person 2"])


# ---- 6: the error signal -------------------------------------------------------------------------
def _errors(doc: RP.Doc, waves, figs, tabs, secs) -> None:
    e1, e2 = waves[0]["errors"], waves[1]["errors"]
    x1, x2 = e1["pattern"], e2["pattern"]
    def test(x, key):
        return f"{x[key]['diff']:+.1f}, {_p(x[key]['p'])}"
    rows = [["Wrong presses kept", *[f"{x['n_error']} of {x['of_error']}" for x in (x1, x2)]],
            ["Correct presses kept", *[f"{x['n_correct']} of {x['of_correct']}" for x in (x1, x2)]],
            ["ERN at FCz, wrong minus correct, µV", *[test(x, "ern_test") for x in (x1, x2)]],
            ["Pe at Pz and CPz, wrong minus correct, µV", *[test(x, "pe_test") for x in (x1, x2)]]]
    _head_table(doc, secs, "Error signal", next(tabs), "Around each press in sequence trials.", rows,
                [0.42, 0.2, 0.2], ["", "EEG person 1", "EEG person 2"])
    n = next(figs)
    keep = e1["ms"] >= -200
    cap = "Around each press in sequence trials: wrong (red), correct (black)."
    h = 0.285
    pg, y0 = _figure(doc, n, cap, h)
    for row, (name, e) in enumerate((("EEG person 1", e1), ("EEG person 2", e2))):
        x = e["pattern"]
        ms = e["ms"][keep]
        yb = y0 + (1 - row) * 0.143
        for col, (title, chans, place, key) in enumerate(((f"ERN, {name}", ["FCz"], "top front", "FCz"),
                                                         (f"Pe, {name}", ["Pz", "CPz"], "top back",
                                                          "Pz/CPz"))):
            xx = X0 + col * 0.43
            pg.head(xx, yb + 0.055, chans, place, RP.RED)
            ax = pg.axes(xx + 0.1, yb + 0.035, 0.3, 0.09)
            RP._wave(ax, ms, [(x[f"{key} error"][keep], RP.RED, f"wrong ({x['n_error']})", "-"),
                              (x[f"{key} correct"][keep], INK, f"correct ({x['n_correct']})", "-")],
                     xlabel="Time after the press (s)" if row else "")
            _label(pg, xx, yb + 0.147, title)
    pg.caption(n, cap)


# ---- 7: the device's own games ------------------------------------------------------------------------
def _games(doc: RP.Doc, v, tabs, secs) -> None:
    tn = next(tabs)
    who = {"P01": "Person 5", "P02": "Person 6", "E01": "Person 1"}

    def g(w, mode, metric, fmt="{:.2f}", scale=1.0):
        x = v.get((w, mode, metric))
        return None if x is None else fmt.format(x * scale)

    def one(w, mode, metric, fmt="{:.2f}", scale=1.0):
        return f"{g(w, mode, metric, fmt, scale)} ({who[w]})"

    def two(a, b, mode, metric, fmt="{:.2f}", scale=1.0):
        return f"{one(a, mode, metric, fmt, scale)}, {one(b, mode, metric, fmt, scale)}"
    rows = [["Reaction", "Median reaction time, ms", one("P01", "reaction", "median_rt_ms", "{:.0f}"), "None set"],
            ["Chords", "Extra time per added finger, ms", one("P01", "chords", "chord_cost_ms", "{:.0f}"),
             "About 126 (Verwey, 2023)"],
            ["Force Pilot", "Time inside the target band", two("P01", "P02", "force_pilot", "time_in_corridor"),
             "Design: above 0.8"],
            ["Force Pilot", "Tracking error, % of own maximum", two("P01", "P02", "force_pilot", "mae_pct", "{:.1f}"),
             "None in these units"],
            ["Force Pilot", "Release error over press error", two("P01", "P02", "force_pilot", "pd_release_ratio"),
             "0.83 to 0.90 (Davidson et al.)"],
            ["Buzz Hunt", "Buzzes found, %", two("P01", "E01", "buzz_hunt", "loc_accuracy", "{:.0f}", 100),
             "Design: above 90"],
            ["Adaptive", "Top pace, beats a minute", one("P01", "adaptive", "bpm_max_reached", "{:.0f}"),
             "Pilot runs: 90 to 144"]]
    tcap = "Each game's main measures beside healthy values; one sitting, so values rather than tests."
    widths, header = [0.12, 0.27, 0.26, 0.19], ["Game", "Measure", "Value", "Healthy value"]
    doc.need(0.014 + 0.045 + doc.pg.table_height(tn, tcap, rows, widths, header))
    pg = _head(doc, secs, "The device's own games")
    pg.table(tn, tcap, rows, widths, header)


# ---- 8: processing -------------------------------------------------------------------------------
def _processing(doc: RP.Doc, s1, s2, grp, tabs, secs) -> None:
    r1 = {r["mode"]: r for r in s1["recordings"]}
    r2 = {r["mode"]: r for r in s2["recordings"]}
    ica = grp.get("ica_sensitivity", {}).get("EEG Subject 2", {})
    st1, st2 = s1["srt"]["reject"], s2["srt"]["reject"]
    rows = [["Recording", "BioSemi ActiveTwo, 64 channels, 512 Hz."],
            ["Filters", "0.1 to 40 Hz; 50 and 100 Hz notch."],
            ["Reference", "Common average."],
            ["Bad channels", f"EEG person 1: {', '.join(r1['srt']['bads'])}. EEG person 2: "
                             f"{', '.join(r2['srt']['bads'])}. Spherical-spline interpolation."],
            ["ICA", f"Picard; eye components by correlation with VEOG and HEOG. EEG person 1: "
                    f"{len(r1['srt']['ica_removed'])} removed. EEG person 2: none met the criterion; removing "
                    "the two most eye-like left N2 and P3 unchanged."
             if ica else "Picard; eye components by correlation with VEOG and HEOG."],
            ["Rejection", f"Over 150 µV peak to peak. Flash epochs kept: {st1['stimulus']['kept']} "
                          f"of {st1['stimulus']['of']} and {st2['stimulus']['kept']} of {st2['stimulus']['of']}."],
            ["Baseline", "-0.2 to 0 s before the flash; -0.4 to -0.2 s before the press."],
            ["Both people", "Differences averaged; labels shuffled within each person 10,000 times."]]
    tn = next(tabs)
    cap = "Processing, both recordings, in order."
    widths, header = [0.17, W - 0.17], ["Step", "What was done"]
    doc.need(0.014 + 0.045 + doc.pg.table_height(tn, cap, rows, widths, header))
    pg = _head(doc, secs, "Processing")
    pg.table(tn, cap, rows, widths, header)


# ---- the document ---------------------------------------------------------------------------------
def build(root: Path, out: Path, sessions: list[Path], details: list[Path]) -> Path:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages
    seq = json.loads((root / SEQUENCE).read_text(encoding="utf-8"))
    press = json.loads((root / PRESS).read_text(encoding="utf-8"))
    grp = json.loads((root / GROUP).read_text(encoding="utf-8"))
    s1, s2 = (json.loads((d / "summary.json").read_text(encoding="utf-8")) for d in details)
    waves = eeg_waves(sessions, out.parent / "review_eeg.pkl")
    values = game_values(root)
    figs, tabs, secs = itertools.count(1), itertools.count(1), itertools.count(1)
    with plt.rc_context({"font.family": RP.FONTS, "pdf.fonttype": 42, "axes.unicode_minus": False}):
        doc = RP.Doc()
        _front(doc, tabs)
        _sequence(doc, seq, figs, tabs, secs)
        _press(doc, press, figs, tabs, secs)
        _markers(doc, s1, s2, tabs, secs)
        _sensory(doc, waves, s1["checks"]["sensory"]["buzz"], details, figs, tabs, secs)
        _learning(doc, grp, s1, s2, waves, details, figs, tabs, secs)
        _errors(doc, waves, figs, tabs, secs)
        _games(doc, values, tabs, secs)
        _processing(doc, s1, s2, grp, tabs, secs)
        out.parent.mkdir(parents=True, exist_ok=True)
        with PdfPages(out, metadata={"Title": "Final results, 8 to 22 October 2026"}) as pdf:
            for page in doc.pages:
                pdf.savefig(page.fig)
                plt.close(page.fig)
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, required=True, help="the results folder")
    ap.add_argument("--out", type=Path, required=True, help="the PDF to write")
    ap.add_argument("--eeg", type=Path, nargs=2, required=True, help="the two EEG session folders")
    ap.add_argument("--eeg-results", type=Path, nargs=2, required=True, help="their detail/ folders")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    print("written", build(args.root, args.out, args.eeg, args.eeg_results))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
