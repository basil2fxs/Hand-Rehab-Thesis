"""Every result from the final data (8 to 22 October 2026) on a few
pages, for the Curtin EEG laboratory, the supervisor and the project
team to check before the results go into the thesis. The layout is the
single-session EEG report's (eeg/report.py): a few plain words under
each heading, one "label: result" line per result, captions that say
how to read each figure, and people by code only.

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

# the sequence task's players in the order they played, and their colours
# (the reference categorical order, checked for colour-blind separation)
NAMES = {"E1": "EEG 1", "L1": "Lab 1", "L2": "Lab 2", "E2": "EEG 2"}
HUE = {"E1": "#2a78d6", "L1": "#eb6834", "L2": "#1baf7a", "E2": "#eda100"}
MARK = {"E1": "o", "L1": "s", "L2": "^", "E2": "D"}
PATTERN, RANDOM = RP.KIND["pattern"][0], RP.KIND["random"][0]
PLANNED = {"N2": "N2: random_posttest vs sequence_late", "P3": "P3: random_practice vs sequence_late",
           "beta": "beta: random_posttest vs sequence_late", "P3 check": "P3: random_posttest vs sequence_late"}
INK, SOFT, MUTED, LINE, GREY = RP.INK, RP.SOFT, RP.MUTED, RP.LINE, RP.GREY
X0, W = RP.X0, RP.W


def _p(v) -> str:
    return "p " + p_text(v)


def _ms(v) -> str:
    return f"{v:+.0f} ms"


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


def _label(pg, x, y, s):
    pg.text(x, y, s, 9.5, True, va="top")


def _tidy(ax, xlabel="", ylabel=""):
    if xlabel:
        ax.set_xlabel(xlabel, fontsize=8.5, color=SOFT)
    if ylabel:
        ax.set_ylabel(ylabel, fontsize=8.5, color=SOFT)


# ---- the front page -------------------------------------------------------------------------
def _front(doc: RP.Doc, seq, press, grp, s1, s2, tabs) -> None:
    pg = doc.pg
    pg.write("Final results", 22, True, after=0.0)
    pg.write("Sessions from 8 to 22 October 2026", 10, colour=MUTED, after=0.01)
    pg.ov.plot([X0, X0 + W], [pg.y, pg.y], color=LINE, lw=0.8)
    pg.y -= 0.012
    pg.write("Six people played the device between 8 and 22 October. Four played the Curtin EEG "
             "laboratory's sequence task on the device's Reaction game: press the finger whose square "
             "lights up, 896 times, with a hidden 10-item order repeating through eight blocks between "
             "a random practice block and a random post-test. Two of the four wore the laboratory's "
             "64-electrode cap. One more person played a 30-minute sitting of the device's own games, "
             "and another a Force Pilot block. Table 1 lists who played what, by code.",
             10, colour=SOFT, after=0.012)
    n = next(tabs)
    rows = [["EEG 1", "8 Oct", "Sequence task, then Buzz Hunt", "64 channels"],
            ["Lab 1", "15 Oct", "Sequence task", "None"],
            ["Lab 2", "19 Oct", "Sequence task", "None"],
            ["EEG 2", "22 Oct", "Sequence task", "64 channels"],
            ["P01", "20 Oct", "30-minute sitting: Force Pilot, Chords, Buzz Hunt, Adaptive, Reaction, Rhythm",
             "None"],
            ["P02", "15 Oct", "Force Pilot", "None"]]
    _table(doc, n, "Who played what. Three blocks stopped part way through are left out: a Force Pilot "
                   "block from each EEG session and EEG 2's Buzz Hunt.",
           rows, [0.11, 0.1, 0.48, 0.15], ["Code", "Date", "Played", "EEG"])

    g, t = seq["group"], grp["tests"]
    good = [p["genuine_share"] for p in press.values()]
    lags = [p["lag_ms"][1] for p in press.values()]
    recalled = sum(1 for p in seq["people"].values() if p["recall"]["chance_p"]["triplet"] < 0.05)
    pg = doc.need(0.05)
    pg.y -= 0.006
    pg.write("In short", 12, True, after=0.008)
    doc.bullet("Learning:", f"all four players of the sequence task slowed when the order turned random, "
                            f"by {g['mean_ms']:.0f} ms on average ({_p(g['p'])}), and "
                            f"{'all four' if recalled == len(seq['people']) else recalled} recalled more of the "
                            "order than guessing would (Section 1).")
    doc.bullet("Presses:", f"the device counts each press a steady {min(lags):.0f} to {max(lags):.0f} ms after "
                           f"the push starts, and {100 * min(good):.1f} to {100 * max(good):.0f}% of counted "
                           "presses were single, real presses (Section 2).")
    doc.bullet("Markers:", "in both EEG recordings every marker matched the game's log and landed within "
                           f"{max(s1['checks']['timing_ms']['max'], s2['checks']['timing_ms']['max']):.1f} ms "
                           "of its logged time (Section 3).")
    doc.bullet("Brain signal:", "in both people the resting rhythm over the left motor area was lower after "
                                f"learned flashes than random ones ({t[PLANNED['beta']]['diff']:.1f} dB lower, "
                                f"{_p(t[PLANNED['beta']]['p'])}), still so with reaction time taken out. The P3 "
                                "shrank from practice to the late "
                                "blocks but stayed small in the random post-test, and the N2 grew for random "
                                "flashes in EEG 1 only (Section 5).")
    doc.bullet("Device games:", "one 30-minute sitting and two single blocks give values beside published "
                                "healthy ones; each game's planned checks need eight people, so none could "
                                "be tested yet (Section 7).")


# ---- 1: sequence learning -----------------------------------------------------------------
def _sequence(doc: RP.Doc, seq, figs, secs) -> None:
    from sequence_task import SEGMENTS
    people, g = seq["people"], seq["group"]
    doc.heading(next(secs), "Sequence learning, four players",
                "A player who picks up the hidden order gets faster as it repeats, and slower again when "
                "it turns random in the post-test. The learning score is that slowing: the post-test "
                "median reaction time minus block 8's. As in the laboratory's own studies, only correct "
                "presses under 1000 ms count, and each block's first trial is left out. After the task "
                "each player typed the order back from memory.")
    n = next(figs)
    L = {k: p["learning"] for k, p in people.items()}
    doc.bullet("Learning score:", ", ".join(
        f"{NAMES[k]} {_ms(v['post_minus_block8_ms'])} ({v['post_minus_block8_ci'][0]:.0f} to "
        f"{v['post_minus_block8_ci'][1]:.0f})" for k, v in L.items())
        + f", each with its 95% interval. Mean {_ms(g['mean_ms'])} (95% CI {g['ci_ms'][0]:.0f} to "
          f"{g['ci_ms'][1]:.0f}), t({g['n'] - 1}) = {g['t']:.2f}, {_p(g['p'])}; above zero for all "
          f"{g['n']} (Figure {n}).")
    M = seq["mixed"]
    doc.bullet("All trials:", f"Rayyan's mixed model for this task (RT on block, a random intercept per player) "
                              f"on all {M['trials']:,} kept trials: post-test minus block 8 "
                              f"{_ms(M['post_minus_block8']['estimate'])} (95% CI "
                              f"{M['post_minus_block8']['lower']:.0f} to {M['post_minus_block8']['upper']:.0f}); "
                              f"{abs(M['slope_per_block']['estimate']):.1f} ms faster per sequence block; the two "
                              f"random blocks did not differ ({M['post_minus_practice']['estimate']:+.0f} ms, "
                              f"{M['post_minus_practice']['lower']:.0f} to {M['post_minus_practice']['upper']:.0f}), "
                              "so the speed-up belonged to the sequence.")
    lb, rb = g["lower_bound"], g["random_blocks"]
    doc.bullet("Fairer baseline:", "set against whichever random block was faster, practice or post-test, so that "
                                   "neither a tired post-test nor an unfamiliar first block can raise it, the score "
                                   "was " + ", ".join(f"{NAMES[k]} {_ms(x)}" for k, x in lb["per_person"].items())
               + f", mean {_ms(lb['mean_ms'])}; above zero for all four. The two random blocks, the same "
                 "measure taken twice, differed by "
               + ", ".join(f"{x:+.0f}" for x in rb["per_person"].values())
               + f" ms (post-test minus practice), mean {rb['mean_ms']:+.0f} ms.")
    rec = {k: p["recall"] for k, p in people.items()}
    whole = [NAMES[k] for k, r in rec.items() if r["best_start"] == r["items"]]
    rest = [k for k, r in rec.items() if r["best_start"] < r["items"]]
    doc.bullet("Recall:", "scored from whichever starting point matched best, since the order repeats as a "
                          f"loop, {' and '.join(whole)} typed the whole order back (10 of 10, chance "
                          f"{_p(max(rec[k]['chance_p']['best_start'] for k in L if NAMES[k] in whole))}), "
               + " and ".join(f"{NAMES[k]} {rec[k]['best_start']} of 10 ({_p(rec[k]['chance_p']['best_start'])})"
                              for k in rest)
               + ". Scored by runs of three, all four recalled more of the order than guessing would "
                 f"({_p(max(r['chance_p']['triplet'] for r in rec.values()))} or lower).")
    nr, share = g["no_reversals"], people[next(iter(people))]["reversal_share"]
    doc.bullet("Without reversals:", f"random blocks hold twice as many A-B-A trials as the sequence "
                                     f"({100 * share['random']:.0f}% against {100 * share['sequence']:.0f}%), "
                                     "and these are slower to answer. Without them the scores are "
               + ", ".join(f"{_ms(p['learning_no_reversals']['post_minus_block8_ms'])}" for p in people.values())
               + f", mean {_ms(nr['mean_ms'])} ({_p(nr['p'])}), all four still above zero.")
    fl = g["floored"]
    fast = ", ".join(f"{p['fast_correct']} of {NAMES[k]}'s" for k, p in people.items())
    doc.bullet("Fast presses:", "the laboratory's script counts any press after the flash as a correct "
                                "reaction, even one 2 ms after it, but nobody reacts to a flash that fast, so "
                                "those presses were made before the flash was seen. They fell mostly in "
                                f"blocks 4 to 8: {fast} correct presses came under 100 ms. Leaving them out "
                                f"gives a mean score of {_ms(fl['100']['mean_ms'])} ({_p(fl['100']['p'])}); "
                                f"leaving out everything under 150 ms gives {_ms(fl['150']['mean_ms'])} "
                                f"({_p(fl['150']['p'])}). All four stay above zero either way.")

    cap = ("(a) Median reaction time of each player's correct presses through the task: random practice, "
           "the eight sequence blocks and the random post-test (shaded). Lab 1's dip in blocks 4 to 6 is the "
           "presses made before the flash (Fast presses). (b) Each player's learning score, the post-test "
           "minus block 8, with its 95% interval, and the mean of the four (black) with its interval. Above "
           "zero means slower once the order turned random.")
    h = 0.2
    pg, y0 = _figure(doc, n, cap, h)
    ax = pg.axes(X0 + 0.05, y0 + 0.045, 0.5, h - 0.07)
    xs = np.arange(len(SEGMENTS))
    for x in (0, len(SEGMENTS) - 1):
        ax.axvspan(x - 0.4, x + 0.4, color=GREY, alpha=0.2, lw=0)
    for k, p in people.items():
        seg = {r["segment"]: r["rt_median_ms"] for r in p["segments"]}
        ax.plot(xs, [seg.get(s, np.nan) for s in SEGMENTS], color=HUE[k], lw=1.6, marker=MARK[k], ms=4.5,
                mec="white", mew=0.6, label=NAMES[k])
    ax.set_xticks(xs)
    ax.set_xticklabels(["Rnd"] + [str(i) for i in range(1, 9)] + ["Rnd"])
    ax.set_xlim(-0.6, len(SEGMENTS) - 0.4)
    _tidy(ax, "Block", "Median reaction time (ms)")
    ax.legend(frameon=False, fontsize=8, ncols=4, loc="lower left", bbox_to_anchor=(0.0, 1.0),
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
    ax.set_xticklabels([NAMES[k].replace(" ", "\n") for k in L] + ["Mean"], fontsize=7.5)
    ax.set_xlim(-0.6, i + 0.6)
    _tidy(ax, "", "Post-test minus block 8 (ms)")
    _label(pg, X0 + 0.58, y0 + h + 0.012, "(b) Learning score")
    pg.caption(n, cap)


# ---- 2: the press check ----------------------------------------------------------------------
def _press(doc: RP.Doc, press, figs, secs) -> None:
    from matplotlib.ticker import MaxNLocator

    from sequence_task import SEGMENTS
    doc.heading(next(secs), "Is each press read where it happened?",
                "The device counts a press when the force on the pad crosses a threshold part way up the "
                "push. If the time from the start of the push to that crossing changed as a player sped "
                "up, the reaction-time curve would bend away from the true one. And a light touch that "
                "crossed the threshold, fell back and was followed by the real push would give a reaction "
                "time taken from the touch. For every counted press the start of the push was found on "
                "the board's own force record with the software's onset detector, and the reaction time "
                "was read from both points.")
    n = next(figs)
    rs = [p["r_press_onset"] for p in press.values()]
    doc.bullet("Parallel lines:", "the two reaction times run parallel through every block for all four "
                                  f"players, and agree trial by trial at r = {min(rs):.3f} to {max(rs):.3f} "
                                  f"(Figure {n}).")
    seg = {k: pd.DataFrame(p["segments"]).set_index("segment") for k, p in press.items()}

    def score(k, col):
        return seg[k].loc["Post-test", col] - seg[k].loc["Sequence 8", col]
    spread = [p["lag_vs_segment_spread_ms"] for p in press.values()]
    doc.bullet("Lag:", "the press is counted a median "
               + ", ".join(f"{p['lag_ms'][1]:.0f} ms ({NAMES[k]})" for k, p in press.items())
               + f" after the push starts, and the lag moves by {min(spread):.0f} to {max(spread):.0f} ms at "
                 "most from block to block, two or three of the board's 5 ms samples. Read at the start of "
                 "the push, the learning scores are "
               + ", ".join(f"{score(k, 'rt_onset_ms'):.0f}" for k in press)
               + " ms, against " + ", ".join(f"{score(k, 'rt_press_ms'):.0f}" for k in press)
               + " ms at the counted press on the same trials.")
    found = sum(p["onset_found"] for p in press.values())
    counted = sum(p["counted_presses"] for p in press.values())
    doc.bullet("Start found:", f"for {found:,} of the {counted:,} counted presses "
                               f"({100 * found / counted:.0f}%).")
    re_ = sum(p["repress"] for p in press.values())
    weak = sum(p["weak_first_then_real"] for p in press.values())
    held = min(p["held_ms_p1"] for p in press.values())
    good = [p["genuine_share"] for p in press.values()]
    doc.bullet("False presses:", "no counted press was let go within 60 ms (the shortest 1% were held more "
                                 f"than {np.floor(held / 10) * 10:.0f} ms). The same finger pressed again "
                                 f"within 0.3 s of letting go {re_} times, and only {weak} of those began "
                                 "with a light touch, under half the player's usual force, before the real "
                                 f"push. So {100 * min(good):.1f} to {100 * max(good):.0f}% of each player's "
                                 "counted presses were single, real presses.")

    cap = ("Each player's median reaction time per block, read at the moment the device counted the press "
           "(solid) and at the start of the push on the force record (dotted). Lines that run parallel "
           "mean the counting point keeps a steady distance behind the push, so it cannot make or hide "
           "learning. Each title gives the median gap between the two (the lag) with its interquartile "
           "range, and the trial-by-trial correlation r. Shaded: the random blocks.")
    h = 0.3
    pg, y0 = _figure(doc, n, cap, h)
    xs = np.arange(len(SEGMENTS))
    for i, (k, p) in enumerate(press.items()):
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
    tn = next(tabs)
    doc.heading(next(secs), "EEG markers against the log",
                "The game logs every event with its time and sends a numbered marker for it into the EEG "
                "recording, so both should hold the same events in the same order at the same times. "
                f"Table {tn} sets the two recordings side by side.")
    c1, c2 = s1["checks"], s2["checks"]

    def rec(s):
        mins = {r["mode"]: r["minutes"] for r in s["recordings"]}
        return ", ".join(f"{v:.1f} min {'sequence task' if m == 'srt' else 'Buzz Hunt'}" for m, v in mins.items())

    def matched(s):
        return f"{s['markers_matched']:,} of {s['markers_total']:,}"

    def fails(c):
        q = c["queue"].values()
        return "None" if all(v["failed"] == 0 and v["dropped"] == 0 for v in q) else "Some"
    rows = [["Recording", rec(s1), rec(s2)],
            ["Markers in the recording that match the log", matched(s1), matched(s2)],
            ["Counts per block (flashes, correct, wrong, early, missed)",
             "All equal the log" if c1["by_condition_match"] else "Some differ",
             "All equal the log" if c2["by_condition_match"] else "Some differ"],
            ["Marker time against the log: spread (largest)",
             f"{c1['timing_ms']['sd']:.2f} ms ({c1['timing_ms']['max']:.2f} ms)",
             f"{c2['timing_ms']['sd']:.2f} ms ({c2['timing_ms']['max']:.2f} ms)"],
            ["Spread in the first and second half of the recording",
             " and ".join(f"{v:.2f}" for v in c1["timing_halves_ms"]["srt"]) + " ms",
             " and ".join(f"{v:.2f}" for v in c2["timing_halves_ms"]["srt"]) + " ms"],
            ["Reaction time from the recording against the log",
             f"r = {c1['rt']['r']:.5f}, offset {c1['rt']['offset_ms']:+.1f} ms",
             f"r = {c2['rt']['r']:.5f}, offset {c2['rt']['offset_ms']:+.1f} ms"],
            ["Response marker names the logged finger", f"{c1['order']['lanes'][0]} of {c1['order']['lanes'][1]}",
             f"{c2['order']['lanes'][0]} of {c2['order']['lanes'][1]}"],
            ["Markers that failed or dropped", fails(c1), fails(c2)]]
    _table(doc, tn, "The markers in each recording against the game's log. Spread is the standard "
                            "deviation of the marker times around the fitted clock; offset is the mean "
                            "difference between the reaction time read from the recording, using the press "
                            "time each response marker carries, and the logged one.",
           rows, [0.4, 0.22, 0.22], ["Check", "EEG 1, 8 Oct", "EEG 2, 22 Oct"])


# ---- 4: early responses to the flash -------------------------------------------------------------
def _sensory(doc: RP.Doc, waves, figs, secs) -> None:
    n = next(figs)
    doc.heading(next(secs), "Early responses to the flash",
                "A flash makes a small, fixed bump in the signal at the back of the head about a tenth "
                "of a second later. Averaging around every flash marker shows that bump only if the "
                "markers sit at the right time; markers late by a varying amount would smear it away. P1 "
                "and N1 are the first upward and downward bumps, and µV is a millionth of a volt.")
    for name, w in zip(("EEG 1:", "EEG 2:"), waves):
        f = w["flash"]
        p, r, hv = f["pattern"], f["random"], f["halves"]
        edge = p["P1"][0] >= 150      # the peak search runs 60 to 160 ms
        doc.bullet(name, (f"P1 at {r['P1'][0]:.0f} ms in random trials; in pattern trials the first upward "
                          f"wave is smaller and broader, highest at {p['P1'][0]:.0f} ms" if edge else
                          f"P1 at {p['P1'][0]:.0f} ms in pattern trials and {r['P1'][0]:.0f} ms in random trials")
                   + f"; N1 at {p['N1'][0]:.0f} and {r['N1'][0]:.0f} ms. The pattern blocks' P1 came at "
                     f"{hv[0][0]:.0f} ms in their first half and {hv[1][0]:.0f} ms in their second, so nothing "
                     "drifted.")
    doc.bullet("Control:", "averages taken at random moments, where nothing happened, are flat in both "
                           f"recordings (Figure {n}).")
    cap = ("The average signal at the back of the head (O1, O2) around each flash, for EEG 1 (a) and EEG 2 "
           "(b). Time runs left to right and 0 (dashed) is the flash marker. Blue is pattern trials, orange "
           "random trials and grey the random-time control, with the trial counts in the legend; the dots "
           "mark the P1 and N1 of the pattern average.")
    h = 0.3
    pg, y0 = _figure(doc, n, cap, h)
    for k, (title, w) in enumerate(zip(("(a) EEG 1", "(b) EEG 2"), waves)):
        f = w["flash"]
        bottom = y0 + (1 - k) * 0.15 + 0.035
        pg.head(X0, bottom + 0.02, ["O1", "O2"], "back", PATTERN)
        ax = pg.axes(X0 + 0.13, bottom, W - 0.13, 0.085)
        p, r = f["pattern"], f["random"]
        RP._wave(ax, f["ms"], [(p["O1/O2"], PATTERN, f"pattern ({p['n']})", "-"),
                               (r["O1/O2"], RANDOM, f"random ({r['n']})", "-"),
                               (f["control O1/O2"], GREY, "random times", "-")],
                 xlabel="Time after the flash (s)" if k else "")
        RP._mark(ax, p["P1"], "P1", PATTERN)
        RP._mark(ax, p["N1"], "N1", PATTERN)
        _label(pg, X0, bottom + 0.118, title)
    pg.caption(n, cap)


# ---- 5: learning in the brain signal --------------------------------------------------------------
def _learning(doc: RP.Doc, grp, s1, s2, waves, figs, tabs, secs) -> None:
    lead = ("Three measures were fixed before the second recording. The N2, a dip 0.2 to 0.3 s after the "
            "flash at the top front of the head (FCz, Cz), grows when a flash breaks an expected order. The "
            "P3, a rise 0.3 to 0.45 s after the flash further back (Pz, CPz), shrinks as flashes become "
            "predictable. Beta, the resting rhythm over the left motor area (C3, which runs the right hand), "
            "drops while a move is prepared. For both people together, each person's own difference is "
            "averaged and the trial labels are shuffled within each person; Holm's correction runs across "
            "the N2 and P3.")
    t = grp["tests"]
    one = [s1["srt"], s2["srt"]]

    def cell(test, unit=""):
        return f"{test['diff']:+.1f}, {_p(test['p'])}".replace("+0.0", "0.0")

    def both(key):
        x = t[key]
        s = cell(x)
        return s + (f" (Holm {p_text(x['p_holm']).lstrip('= ')})" if "p_holm" in x else "")
    rows = [["N2, random post-test minus late sequence (µV)",
             *[cell(s["stim_tests"][PLANNED["N2"]]) for s in one], both(PLANNED["N2"])],
            ["P3, random practice minus late sequence (µV)",
             *[cell(s["stim_tests"][PLANNED["P3"]]) for s in one], both(PLANNED["P3"])],
            ["Beta at C3, random post-test minus late sequence (dB)",
             *[cell(s["band_tests"]["beta C3"]) for s in one], both(PLANNED["beta"])],
            ["Check: P3, random post-test minus late sequence (µV)",
             *[cell(s["stim_tests"][PLANNED["P3 check"]]) for s in one], both(PLANNED["P3 check"])],
            *[[label, *[cell(grp["beta_timing"][kind]["per_person"][n]) for n in ("EEG Subject 1", "EEG Subject 2")],
               cell(grp["beta_timing"][kind]["both"])]
              for kind, label in (("matched", "Check: beta, learned trials matched in reaction time (dB)"),
                                  ("press", "Check: beta in the 0.5 s before the press (dB)"))]]
    tn = next(tabs)
    tcap = ("The planned tests for each person alone and for both together. Late sequence is blocks 7 and "
            "8. A minus sign on the N2 and a plus sign on the P3 and beta are the directions learning "
            "predicts. The last row checks whether the P3 recovers when the order turns random again.")
    widths, header = [0.36, 0.14, 0.14, 0.2], ["Measure", "EEG 1", "EEG 2", "Both"]
    doc.need(0.014 + 0.045 + doc.pg.lead_height(lead) + doc.pg.table_height(tn, tcap, rows, widths, header))
    pg = doc.heading(next(secs), "Learning in the brain signal", lead)
    pg.table(tn, tcap, rows, widths, header)
    n = next(figs)
    cap = ("Each person's flash response for random (orange) and learned (blue) flashes, EEG 1 on top and "
           "EEG 2 below, with the trial counts in the legend. Left: the N2 at the top front of the head (FCz, "
           "Cz), random post-test against the late sequence blocks. Right: the P3 further back (Pz, CPz), "
           "random practice against the late sequence blocks. The grey band is the window each test "
           "averages, and 0 (dashed) is the flash.")
    from eeg.analyses import SRT_WINDOWS
    h = 0.29
    pg, y0 = _figure(doc, n, cap, h)
    panels = (("N2", "random_posttest", ["FCz", "Cz"], "top front"),
              ("P3", "random_practice", ["Pz", "CPz"], "top back"))
    for row, (name, w, s_) in enumerate(zip(("EEG 1", "EEG 2"), waves, one)):
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
    pp = t[PLANNED["P3"]]["per_person"]
    doc.bullet("N2:", "larger for random flashes after learning in EEG 1 only; EEG 2's N2 did not change, so "
                      f"the two-person result rests on EEG 1 (Figure {n}, left).")
    doc.bullet("P3:", f"smaller in the late sequence blocks than in random practice, by {min(pp):.1f} to "
                      f"{max(pp):.1f} µV in both people (Figure {n}, right). It stayed as small in the random "
                      "post-test, though, so the drop may come from time on the task as much as from "
                      "learning the order.")
    bp = t[PLANNED["beta"]]["per_person"]
    bm, bpr = grp["beta_timing"]["matched"]["both"], grp["beta_timing"]["press"]["both"]
    doc.bullet("Beta:", f"lower after flashes in the learned order than after random ones, by {bp[0]:.1f} and "
                        f"{bp[1]:.1f} dB. Random flashes were answered about 80 ms later, which could move the "
                        "movement's own beta drop, so it was read twice more with reaction time taken out: "
                        f"{bm['diff']:.1f} dB against learned trials matched in reaction time ({_p(bm['p'])}), and "
                        f"{bpr['diff']:.1f} dB in the half second before the press ({_p(bpr['p'])}).")


# ---- 6: the error signal -------------------------------------------------------------------------
def _errors(doc: RP.Doc, waves, figs, secs) -> None:
    e1, e2 = waves[0]["errors"], waves[1]["errors"]
    rnd = [w["errors"]["random"] for w in waves]
    doc.heading(next(secs), "Error signal",
                "Within about a tenth of a second of a wrong press the signal at the top front of the head "
                "dips (the error-related negativity, ERN) further than after a correct press. Later, 0.2 to "
                "0.4 s after a wrong press, the signal further back rises (the Pe). Both need enough errors "
                f"to average, and the random blocks had only {rnd[0]['of_error']} and {rnd[1]['of_error']}, "
                "so the figure shows pattern trials. p is the chance of a difference this large arising by "
                "luck; under .05 counts as reliable.")
    n = next(figs)
    for name, e in (("EEG 1, pattern trials:", e1), ("EEG 2, pattern trials:", e2)):
        x = e["pattern"]
        doc.bullet(name, f"ERN {x['ern_test']['diff']:+.1f} µV against correct presses "
                         f"({_p(x['ern_test']['p'])}); Pe {x['pe_test']['diff']:+.1f} µV "
                         f"({_p(x['pe_test']['p'])}); {x['n_error']} of {x['of_error']} errors kept"
                         + (f" (Figure {n})." if e is e1 else "."))
    doc.bullet("Random trials:", "; ".join(
        f"{nm} ERN {x['ern_test']['diff']:+.1f} µV ({_p(x['ern_test']['p'])}), Pe {x['pe_test']['diff']:+.1f} "
        f"µV ({_p(x['pe_test']['p'])}) from {x['n_error']} errors" for nm, x in zip(("EEG 1", "EEG 2"), rnd))
        + ".")
    keep = e1["ms"] >= -200
    cap = ("The signal around each press in pattern trials, 0 (dashed) being the press time carried in its "
           "response marker, for EEG 1 (top) and EEG 2 (bottom). Red is wrong presses and black correct "
           "ones, with the counts in the legend. Left: FCz, where the ERN shows as the red line dipping "
           "below the black just after the press. Right: Pz and CPz, where the Pe shows as the red line "
           "above the black at 0.2 to 0.4 s. The next flash comes about 0.5 s after each press, so the "
           "right end of each plot already holds the next trial.")
    h = 0.32
    pg, y0 = _figure(doc, n, cap, h)
    for row, (name, e) in enumerate((("EEG 1", e1), ("EEG 2", e2))):
        x = e["pattern"]
        ms = e["ms"][keep]
        yb = y0 + (1 - row) * 0.16
        for col, (title, chans, place, key) in enumerate(((f"ERN, {name}", ["FCz"], "top front", "FCz"),
                                                         (f"Pe, {name}", ["Pz", "CPz"], "top back",
                                                          "Pz/CPz"))):
            xx = X0 + col * 0.43
            pg.head(xx, yb + 0.055, chans, place, RP.RED)
            ax = pg.axes(xx + 0.1, yb + 0.035, 0.3, 0.09)
            RP._wave(ax, ms, [(x[f"{key} error"][keep], RP.RED, f"error ({x['n_error']})", "-"),
                              (x[f"{key} correct"][keep], INK, f"correct ({x['n_correct']})", "-")],
                     xlabel="Time after the press (s)" if row else "")
            _label(pg, xx, yb + 0.147, title)
    pg.caption(n, cap)


# ---- 7: the device's own games ------------------------------------------------------------------------
def _games(doc: RP.Doc, v, tabs, secs) -> None:
    tn = next(tabs)
    lead = ("P01 played a 30-minute sitting of six games, P02 a Force Pilot block and EEG 1 a Buzz Hunt block "
            f"while recorded. Table {tn} sets each game's main measures beside a healthy value from the "
            "literature or the game's design, where one exists. With one or two people these are values to "
            "compare against, not norms: each game's planned checks need eight people, so none could be "
            "tested yet.")

    def g(who, mode, metric, fmt="{:.2f}", scale=1.0):
        x = v.get((who, mode, metric))
        return None if x is None else fmt.format(x * scale)

    def both(a, b, mode, metric, fmt="{:.2f}", scale=1.0):
        return f"{g(a, mode, metric, fmt, scale)} ({a}), {g(b, mode, metric, fmt, scale)} ({b})"

    def lab(s):
        return s.replace("(E01)", "(EEG 1)")
    rows = [["Reaction", "Median reaction time, ms", f"{g('P01', 'reaction', 'median_rt_ms', '{:.0f}')} (P01)",
             "None set for this device"],
            ["Chords", "Extra time per added finger, ms", f"{g('P01', 'chords', 'chord_cost_ms', '{:.0f}')} (P01)",
             "About 126, after long practice (Verwey, 2023)"],
            ["Chords", "Force on the fingers meant to stay still, share of the press",
             f"{g('P01', 'chords', 'median_er', '{:.2f}')} (P01)", "None in the same units"],
            ["Force Pilot", "Time inside the target band", both("P01", "P02", "force_pilot", "time_in_corridor"),
             "Design: above 0.8"],
            ["Force Pilot", "Tracking error, % of own maximum press",
             both("P01", "P02", "force_pilot", "mae_pct", "{:.1f}"), "None in the same units"],
            ["Force Pilot", "Release error over press error",
             both("P01", "P02", "force_pilot", "pd_release_ratio"),
             "0.83 to 0.90, young adults (Davidson et al., 2024, 2026)"],
            ["Force Pilot", "Gain on the sine waves", both("P01", "P02", "force_pilot", "pd_gain"),
             "About 0.83, young adults (Davidson et al., 2026)"],
            ["Buzz Hunt", "Buzzes found, %",
             lab(both("P01", "E01", "buzz_hunt", "loc_accuracy", "{:.0f}", 100)), "Design: above 90"],
            ["Buzz Hunt", "Median reaction time to a buzz, ms",
             lab(both("P01", "E01", "buzz_hunt", "loc_median_rt_ms", "{:.0f}")), "None set"],
            ["Buzz Hunt", "Longest buzz order repeated",
             lab(both("P01", "E01", "buzz_hunt", "span_max_correct", "{:.0f}")), "None set"],
            ["Adaptive", "Top pace reached, beats a minute",
             f"{g('P01', 'adaptive', 'bpm_max_reached', '{:.0f}')} (P01)", "Pilot runs: 90 to 144"],
            ["Adaptive", "Hit rate", f"{g('P01', 'adaptive', 'hit_rate')} (P01)",
             "The game holds it at 0.65 to 0.80"],
            ["Rhythm", "Press timing against the beat", "Not read",
             "The laboratory computer's sound delay was not measured"]]
    tcap = "Each game's main measures. P01 played every game listed; P02 and EEG 1 one block each."
    widths, header = [0.13, 0.29, 0.2, 0.22], ["Game", "Measure", "Value", "Healthy value"]
    doc.need(0.014 + 0.045 + doc.pg.lead_height(lead) + doc.pg.table_height(tn, tcap, rows, widths, header))
    pg = doc.heading(next(secs), "The device's own games", lead)
    pg.table(tn, tcap, rows, widths, header)
    worst = v.get(("P02", "force_pilot", "lvl10_mae_pct"))
    rest = [v[("P02", "force_pilot", f"lvl{i}_mae_pct")] for i in range(1, 13)
            if ("P02", "force_pilot", f"lvl{i}_mae_pct") in v and i != 10]
    doc.bullet("Force Pilot:", f"P02 lost the target on the tenth wave (error {worst:.1f}% against "
                               f"{min(rest):.1f} to {max(rest):.1f}% on the others), which raises the "
                               "block's error.")
    doc.bullet("Adaptive:", f"the game raised the pace from 30 to {v[('P01', 'adaptive', 'bpm_max_reached')]:.0f} "
                            f"beats a minute while P01 kept a {v[('P01', 'adaptive', 'hit_rate')]:.2f} hit "
                            "rate, inside the band it is built to hold.")


# ---- 8: processing -------------------------------------------------------------------------------
def _processing(doc: RP.Doc, s1, s2, grp, tabs, secs) -> None:
    r1 = {r["mode"]: r for r in s1["recordings"]}
    r2 = {r["mode"]: r for r in s2["recordings"]}
    ica = grp.get("ica_sensitivity", {}).get("EEG Subject 2", {})
    kind = s1["checks"]["ica_kind"]["srt"]
    st1, st2 = s1["srt"]["reject"], s2["srt"]["reject"]
    extra = [c for c in r1["buzz_hunt"]["bads"] if c not in r1["srt"]["bads"]] if "buzz_hunt" in r1 else []
    rows = [["Recordings", "BioSemi ActiveTwo, 64 channels at 512 Hz; CMS in range and battery fine "
                           "throughout both."],
            ["Filters", "0.1 to 40 Hz band-pass (zero-phase FIR) and a 50 and 100 Hz notch for mains hum; "
                        "ICA fitted on a 1 to 40 Hz copy."],
            ["Reference", "Common average of the 64 channels."],
            ["Bad channels", f"EEG 1: {', '.join(r1['srt']['bads'])}"
                             + (f" (Buzz Hunt also {', '.join(extra)})" if extra else "")
                             + f". EEG 2: {', '.join(r2['srt']['bads'])}. Flagged as unlike their neighbours "
                               "(correlation under 0.4) and rebuilt from the channels around them "
                               "(spherical-spline interpolation)."],
            ["ICA", "Picard, components to 99% of the variance, eye components chosen by correlation with "
                    f"VEOG and HEOG at |z| over 3. EEG 1: {r1['srt']['ica_components']} components, "
                    f"{len(r1['srt']['ica_removed'])} removed ({kind.count('blink')} blink, "
                    f"{kind.count('horizontal')} horizontal eye movement). EEG 2: "
                    f"{r2['srt']['ica_components']} components, none past the criterion "
                    f"({r2['srt']['blinks_per_min']:.1f} blinks a minute); removing its two most eye-like "
                    "components ("
                    + " and ".join(str(c) for c in ica.get("excluded", []))
                    + ") left the N2 at "
                    + f"{ica[PLANNED['N2']]['diff']:+.1f} µV ({_p(ica[PLANNED['N2']]['p'])}) and the P3 at "
                    + f"{ica[PLANNED['P3']]['diff']:+.1f} µV ({_p(ica[PLANNED['P3']]['p'])})."
             if ica else ""],
            ["Rejection", "Epochs swinging more than 150 µV peak to peak dropped as movement or muscle. Flash "
                          f"epochs kept: {st1['stimulus']['kept']} of {st1['stimulus']['of']} for EEG 1 and "
                          f"{st2['stimulus']['kept']} of {st2['stimulus']['of']} for EEG 2; press epochs "
                          f"{st1['response_onset']['kept']} of {st1['response_onset']['of']} and "
                          f"{st2['response_onset']['kept']} of {st2['response_onset']['of']}."],
            ["Baseline", "-0.2 to 0 s before the flash; -0.4 to -0.2 s before the press for the error signal."],
            ["Two people", "Each person's own difference averaged over the two; trial labels shuffled "
                           "within each person 10,000 times; Holm across the N2 and P3."]]
    lead = "How the two recordings were cleaned before any average above, in the order the steps ran."
    tn = next(tabs)
    cap = "Processing, both recordings."
    widths, header = [0.17, W - 0.17], ["Step", "What was done"]
    doc.need(0.014 + 0.045 + doc.pg.lead_height(lead) + doc.pg.table_height(tn, cap, rows, widths, header))
    pg = doc.heading(next(secs), "Processing", lead)
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
        _front(doc, seq, press, grp, s1, s2, tabs)
        _sequence(doc, seq, figs, secs)
        _press(doc, press, figs, secs)
        _markers(doc, s1, s2, tabs, secs)
        _sensory(doc, waves, figs, secs)
        _learning(doc, grp, s1, s2, waves, figs, tabs, secs)
        _errors(doc, waves, figs, secs)
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
