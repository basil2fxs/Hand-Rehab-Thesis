"""The laboratory's sequence task, read across everyone who played it.

Each block is the Reaction card running the Curtin EEG laboratory's
serial reaction time task (48 random practice trials, eight blocks of the
10-item sequence, 48 random post-test trials, then a free recall). The
trials are kept as the laboratory's studies keep them: correct responses
under 1000 ms, with each block's first trial dropped. The learning score
is the post-test median reaction time minus block 8's, with a bootstrap
95 percent interval. It is also read without reversals, the A-B-A trials
that are slower to answer and twice as common in random order as in the
sequence (Vaquero et al. 2006). Recall is scored by position, at its best
starting point, by correct triplets and by the longest correct run, each
against simulated guessing.

The laboratory script labels a press that lands from about 2 ms after
the flash as correct, but nobody reacts to a flash that fast: those
presses were made before the flash was seen. They cluster in the late
sequence blocks and pull block 8's median down, so the learning score
is also given with presses under 100 and 150 ms left out (FLOORS_MS).
The EEG analysis's own score, on every correct press, is kept beside it
(learning_all_correct) so the two can be compared.

Two readings use the presses the learning score leaves out. A press
under 100 ms, or in the script's anticipation window before the flash,
was chosen before the flash could be seen, so the share of them on the
right finger is how well the player predicted the next target; neither
order repeats a finger, so a guess is right one time in three. Error
rates in random practice, block 8 and the random post-test show whether
the slowing in the post-test was bought with accuracy.

    cd analysis
    python3 sequence_task.py --out DIR LABEL=BLOCK_FOLDER [LABEL=BLOCK_FOLDER ...]

Writes DIR/sequence_task.json and DIR/sequence_task.png.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

SEGMENTS = ["Practice"] + [f"Sequence {i}" for i in range(1, 9)] + ["Post-test"]
FLOORS_MS = (100, 150)
LAB_MAX_RT_MS = 1000
KEYS = {"V": 1, "B": 2, "N": 3, "M": 4}       # the script's keys as the sequence's numbers
N_BOOT = 4000
N_CHANCE = 10000
SEED = 2026


def script_table(folder: Path) -> pd.DataFrame:
    """The block's trial file in the laboratory script's format."""
    files = sorted(p for p in folder.glob("SRT_*.csv")
                   if not p.name.startswith(("SRT_SEQUENCE_", "SRT_RECALL_")))
    t = pd.read_csv(files[0])
    t["rt_ms"] = pd.to_numeric(t.rt_ms, errors="coerce")
    return t


def lab_kept(t: pd.DataFrame) -> pd.Series:
    """The laboratory's rule: correct responses under 1000 ms, each
    block's first trial dropped."""
    first = t.groupby(["phase", "block"]).trial.transform("min") == t.trial
    return (~first) & (t.accuracy == "correct") & (t.rt_ms < LAB_MAX_RT_MS)


def reversal(t: pd.DataFrame) -> pd.Series:
    """A trial whose target is the one two before it in the same block."""
    return (t.target_lane == t.groupby(["phase", "block"]).target_lane.shift(2)).fillna(False)


def _segment(t: pd.DataFrame) -> pd.Series:
    return pd.Series(np.where(t.phase == "learning", "Sequence " + t.block.astype(str),
                              np.where(t.phase == "practice", "Practice", "Post-test")), index=t.index)


def learning(t: pd.DataFrame, keep: pd.Series, rng) -> dict:
    """Post-test median minus block 8's on the kept trials, with a
    bootstrap interval, and the medians it is read from."""
    c = t[keep]
    seg = _segment(c)
    rt = {name: c.rt_ms[seg == name].to_numpy(float) for name in SEGMENTS}
    post, late = rt["Post-test"], rt["Sequence 8"]
    boots = [np.median(rng.choice(post, len(post))) - np.median(rng.choice(late, len(late)))
             for _ in range(N_BOOT)]
    return {"post_minus_block8_ms": float(np.median(post) - np.median(late)),
            "post_minus_block8_ci": [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))],
            "practice_minus_post_ms": float(np.median(rt["Practice"]) - np.median(post)),
            "block1_ms": float(np.median(rt["Sequence 1"])), "block8_ms": float(np.median(late)),
            "post_ms": float(np.median(post)), "practice_ms": float(np.median(rt["Practice"])),
            "n": [int(len(post)), int(len(late))]}


def segments(t: pd.DataFrame, keep: pd.Series) -> list[dict]:
    """Median reaction time per block on the kept trials, with the
    block's accuracy over all its trials."""
    seg = _segment(t)
    rows = []
    for name in SEGMENTS:
        s = t[seg == name]
        k = s[keep[seg == name]]
        rows.append({"segment": name, "n": int(len(s)), "kept": int(len(k)),
                     "rt_median_ms": float(k.rt_ms.median()),
                     "accuracy": float((s.accuracy == "correct").mean())})
    return rows


def recall(folder: Path) -> dict:
    """The recall by position, at its best starting point, by correct
    triplets and by the longest correct run, each with the chance of a
    random recall from the four keys doing as well."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    from finger_rehab.game.srt_setup import recall_scores
    files = sorted(folder.glob("SRT_RECALL_*.csv"))
    if not files:
        return {}
    r = pd.read_csv(files[0])
    rec = [KEYS[str(x).upper()] for x in r.recalled_finger]
    act = [KEYS[str(x).upper()] for x in r.actual_finger]
    n = len(act)

    def best(x):
        return max(sum(a == b for a, b in zip(x, act[k:] + act[:k])) for k in range(n))
    got = recall_scores(rec, act)
    got["best_start"] = best(rec)
    draws = np.random.default_rng(SEED).integers(1, 5, (N_CHANCE, n))
    chance = {"positional": [], "best_start": [], "triplet": [], "longest_run": []}
    for d in draws:
        s = recall_scores(list(d), act)
        chance["positional"].append(s["positional"])
        chance["triplet"].append(s["triplet"])
        chance["longest_run"].append(s["longest_run"])
        chance["best_start"].append(best(list(d)))
    p = {k: float((np.sum(np.asarray(v) >= got[k]) + 1) / (len(v) + 1)) for k, v in chance.items()}
    return {"items": n, "recalled": "-".join(map(str, rec)), "actual": "-".join(map(str, act)),
            **{k: got[k] for k in chance}, "chance_p": p}


def mixed(tables) -> dict:
    """The learning model, lmer(RT ~ block + (1 + post-test | player)) by
    REML on every kept trial of every player
    (finger_rehab.analytics.mixed_model). Each player has their own speed
    and their own size of the post-test slowing, so the learning score's
    interval carries how much the effect varies between players, on the
    players less one degrees of freedom. A random intercept alone
    (intercept_only) treats the players as sharing one effect and gives an
    interval of the trial noise only. The contrasts are the learning score
    (post-test minus block 8), the speed-up per sequence block (the linear
    trend over blocks 1 to 8, read within players) and the post-test minus
    practice; the block means are read as emmeans reads them."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
    from finger_rehab.analytics.mixed_model import (fit_random_intercept, fit_random_slopes,
                                                     lmm_contrast, slopes_contrast)
    d = pd.concat([pd.DataFrame({"rt": t.rt_ms.to_numpy(float), "seg": _segment(t).to_numpy(), "who": i})
                   for i, t in enumerate(tables)], ignore_index=True)
    d = d[d.seg.isin(SEGMENTS)]
    X = np.column_stack([(d.seg == s).to_numpy(float) for s in SEGMENTS])
    post_col = (d.seg == "Post-test").to_numpy(float)
    Z = np.column_stack([np.ones(len(d)), post_col])
    fit = fit_random_slopes(d.rt.to_numpy(float), X, Z, d.who.to_numpy())
    between = fit["n_groups"] - 1
    post, b8, prac = (SEGMENTS.index(s) for s in ("Post-test", "Sequence 8", "Practice"))
    w = np.zeros((3, len(SEGMENTS)))
    w[0, post], w[0, b8] = 1, -1
    x = np.arange(1, 9) - 4.5
    w[1, 1:9] = x / (x ** 2).sum()
    w[2, post], w[2, prac] = 1, -1
    contrasts = {"post_minus_block8": slopes_contrast(fit, w[0], df=between),
                 "slope_per_block": slopes_contrast(fit, w[1]),
                 "post_minus_practice": slopes_contrast(fit, w[2], df=between)}
    emm = {}
    for i, seg in enumerate(SEGMENTS):
        c = slopes_contrast(fit, np.eye(len(SEGMENTS))[i], df=between)
        emm[seg] = {"estimate": c["estimate"], "lower": c["lower"], "upper": c["upper"]}
    simple = lmm_contrast(fit_random_intercept(d.rt.to_numpy(float), X, d.who.to_numpy()), w[0])
    return {"trials": int(len(d)), "players": int(len(tables)),
            "means": {s: float(m) for s, m in zip(SEGMENTS, fit["beta"])}, "emmeans": emm,
            "player_sd_ms": float(np.sqrt(fit["G"][0, 0])), "effect_sd_ms": float(np.sqrt(fit["G"][1, 1])),
            "trial_sd_ms": float(np.sqrt(fit["s2_e"])), **contrasts,
            "intercept_only": {k: simple[k] for k in ("estimate", "lower", "upper", "p")}}


def floored(t: pd.DataFrame, keep: pd.Series, floor_ms: float) -> float:
    """The learning score with presses under floor_ms left out as well."""
    c = t[keep & (t.rt_ms >= floor_ms)]
    seg = _segment(c)
    return float(c.rt_ms[seg == "Post-test"].median() - c.rt_ms[seg == "Sequence 8"].median())


RIGHT = ("correct", "anticipatory_correct")
WRONG = ("incorrect", "anticipatory_incorrect")
CHANCE = 1 / 3          # neither order repeats a finger, so a guess has three to pick from


def _answered(t: pd.DataFrame) -> pd.Series:
    first = t.groupby(["phase", "block"]).trial.transform("min") == t.trial
    return ~first & t.accuracy.isin(RIGHT + WRONG)


def prediction(t: pd.DataFrame) -> dict:
    """Presses too early to answer the flash, under FLOORS_MS[0] after it
    or in the anticipation window before it, and how many chose the right
    finger, in the sequence blocks and in the random ones."""
    answered = _answered(t)
    early = answered & (t.rt_ms < FLOORS_MS[0])
    out = {}
    for kind, sel in (("sequence", t.phase == "learning"), ("random", t.phase != "learning")):
        e = early & sel
        n, right = int(e.sum()), int((e & t.accuracy.isin(RIGHT)).sum())
        out[kind] = {"answered": int((answered & sel).sum()), "early": n, "right": right,
                     "p_vs_chance": (float(stats.binomtest(right, n, CHANCE, alternative="greater").pvalue)
                                     if n else None)}
    return out


def errors(t: pd.DataFrame) -> dict:
    """Share of answered trials on the wrong finger in random practice,
    block 8 and the random post-test, each block's first trial left out."""
    answered, seg = _answered(t), _segment(t)
    return {name: float(t.accuracy[answered & (seg == name)].isin(WRONG).mean())
            for name in ("Practice", "Sequence 8", "Post-test")}


def person(folder: Path) -> dict:
    from eeg import analyses as A
    t = script_table(folder)
    keep = lab_kept(t)
    rng = np.random.default_rng(SEED)
    A.RNG = np.random.default_rng(SEED)      # the stream a session's own EEG run starts from
    _beh, all_correct = A.srt_behaviour(t)
    c = t[keep]
    fast = c[c.rt_ms < FLOORS_MS[0]]
    return {"folder": folder.name, "trials": int(len(t)), "kept": int(keep.sum()),
            "segments": segments(t, keep), "learning": learning(t, keep, rng),
            "learning_no_reversals": learning(t, keep & ~reversal(t), rng),
            "learning_all_correct": all_correct,
            "reversal_share": {"random": float(reversal(t)[t.phase != "learning"].mean()),
                               "sequence": float(reversal(t)[t.phase == "learning"].mean())},
            "recall": recall(folder),
            "accuracy": float((t.accuracy == "correct").mean()),
            "fast_correct": int(len(fast)),
            "fast_by_block": {int(b): int(n) for b, n in
                              fast[fast.phase == "learning"].block.value_counts().sort_index().items()},
            "floored_ms": {str(f): floored(t, keep, f) for f in FLOORS_MS},
            "prediction": prediction(t), "errors": errors(t)}


def scores(x) -> dict:
    """One learning score per person, tested against zero."""
    x = np.asarray(x, float)
    t, p = stats.ttest_1samp(x, 0.0)
    return {"mean_ms": float(x.mean()), "t": float(t), "p": float(p), "positive": int((x > 0).sum())}


def lower_bound(people: dict) -> dict:
    """Each player's score against the faster of the two random blocks:
    the smaller of post-test minus block 8 and practice minus block 8. A
    post-test slowed by fatigue cannot raise it, and a practice block
    slowed by the unfamiliar device cannot either."""
    x = {k: min(q["learning"]["post_ms"], q["learning"]["practice_ms"]) - q["learning"]["block8_ms"]
         for k, q in people.items()}
    return {"per_person": x, **scores(list(x.values()))}


def random_blocks(people: dict) -> dict:
    """The two random blocks of one sitting, practice and post-test, as a
    repeat of the same measure within the session: the post-test minus
    practice difference per player, its mean and limits of agreement."""
    d = np.array([q["learning"]["post_ms"] - q["learning"]["practice_ms"] for q in people.values()], float)
    sd = float(d.std(ddof=1))
    return {"per_person": dict(zip(people, map(float, d))), "mean_ms": float(d.mean()), "sd_ms": sd,
            "loa_ms": [float(d.mean() - 1.96 * sd), float(d.mean() + 1.96 * sd)],
            "ci_halfwidths_ms": [float((q["learning"]["post_minus_block8_ci"][1]
                                        - q["learning"]["post_minus_block8_ci"][0]) / 2) for q in people.values()]}


def group(people: dict) -> dict:
    x = np.array([p["learning"]["post_minus_block8_ms"] for p in people.values()], float)
    t, p = stats.ttest_1samp(x, 0.0)
    half = stats.t.ppf(0.975, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    k = int((x > 0).sum())
    er = [q["errors"] for q in people.values()]
    return {"n": int(len(x)), "mean_ms": float(x.mean()), "sd_ms": float(x.std(ddof=1)),
            "ci_ms": [float(x.mean() - half), float(x.mean() + half)], "t": float(t), "p": float(p),
            "dz": float(x.mean() / x.std(ddof=1)), "positive": k,
            "sign_p_one_sided": float(stats.binomtest(k, len(x), 0.5, alternative="greater").pvalue),
            "floored": {str(f): scores([q["floored_ms"][str(f)] for q in people.values()])
                        for f in FLOORS_MS},
            "lower_bound": lower_bound(people),
            "random_blocks": random_blocks(people),
            "no_reversals": scores([q["learning_no_reversals"]["post_minus_block8_ms"] for q in people.values()]),
            "prediction": {kind: {c: sum(q["prediction"][kind][c] for q in people.values())
                                  for c in ("answered", "early", "right")} for kind in ("sequence", "random")},
            "errors_rose": {"vs_practice": int(sum(e["Post-test"] > e["Practice"] for e in er)),
                            "vs_block8": int(sum(e["Post-test"] > e["Sequence 8"] for e in er))}}


def figure(people: dict, path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    marks = ["o", "s", "^", "D", "v", "P"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(7.0, 2.9), gridspec_kw={"width_ratios": [2.1, 1]})
    xs = np.arange(len(SEGMENTS))
    for x0 in (0, len(SEGMENTS) - 1):
        a.axvspan(x0 - 0.45, x0 + 0.45, color="#fee2e2", zorder=0)
    for (label, p), m in zip(people.items(), marks):
        seg = {r["segment"]: r["rt_median_ms"] for r in p["segments"]}
        a.plot(xs, [seg.get(s, np.nan) for s in SEGMENTS], marker=m, ms=3.5, lw=1.0, label=label)
    a.set_xticks(xs)
    a.set_xticklabels(["Random\npractice"] + [str(i) for i in range(1, 9)] + ["Random\npost-test"], fontsize=7)
    a.set_xlabel("Sequence block", fontsize=8)
    a.set_ylabel("Median reaction time (ms)", fontsize=8)
    a.tick_params(labelsize=7)
    a.legend(fontsize=7, frameon=False, ncol=2)
    a.set_title("(a) Reaction time through the task", fontsize=9)
    for i, (label, p) in enumerate(people.items()):
        L = p["learning"]
        lo, hi = L["post_minus_block8_ci"]
        b.errorbar(i, L["post_minus_block8_ms"], yerr=[[L["post_minus_block8_ms"] - lo], [hi - L["post_minus_block8_ms"]]],
                   fmt=marks[i], color=f"C{i}", ms=4, capsize=2, lw=1)
    g = group(people)
    i = len(people) + 0.4
    b.errorbar(i, g["mean_ms"], yerr=[[g["mean_ms"] - g["ci_ms"][0]], [g["ci_ms"][1] - g["mean_ms"]]],
               fmt="D", color="black", ms=5, capsize=3, lw=1.4)
    b.axhline(0, color="#9ca3af", lw=0.7)
    b.set_xticks(list(range(len(people))) + [i])
    b.set_xticklabels(list(people) + ["Mean"], fontsize=7)
    b.set_ylabel("Post-test minus block 8 (ms)", fontsize=8)
    b.tick_params(labelsize=7)
    b.set_title("(b) Learning score", fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=300)
    plt.close(fig)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("blocks", nargs="+", help="LABEL=BLOCK_FOLDER")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args(argv)
    people = {}
    for spec in args.blocks:
        label, folder = spec.split("=", 1)
        people[label] = person(Path(folder))
    out = {"people": people, "group": group(people)}
    tables = []
    for spec in args.blocks:
        t = script_table(Path(spec.split("=", 1)[1]))
        tables.append(t[lab_kept(t)])
    out["mixed"] = mixed(tables)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "sequence_task.json").write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    figure(people, args.out / "sequence_task.png")
    for label, p in people.items():
        L, R = p["learning"], p["recall"]
        print(f"{label}: learning {L['post_minus_block8_ms']:+.1f} ms (95% CI {L['post_minus_block8_ci'][0]:.1f} to "
              f"{L['post_minus_block8_ci'][1]:.1f}); block 1 {L['block1_ms']:.0f}, block 8 {L['block8_ms']:.0f}, "
              f"post {L['post_ms']:.0f} ms; without reversals "
              f"{p['learning_no_reversals']['post_minus_block8_ms']:+.1f}; every correct press "
              f"{p['learning_all_correct']['post_minus_block8_ms']:+.1f}; recall {R['best_start']}/10 at best start "
              f"(p {R['chance_p']['best_start']:.4f}), {R['positional']}/10 by position (p "
              f"{R['chance_p']['positional']:.3f}), triplets {R['triplet']:.2f} (p {R['chance_p']['triplet']:.4f}), "
              f"longest run {R['longest_run']} (p {R['chance_p']['longest_run']:.4f}); "
              f"accuracy {p['accuracy']:.3f}; correct presses under "
              f"{FLOORS_MS[0]} ms {p['fast_correct']} (by block {p['fast_by_block']}); learning without them "
              + ", ".join(f"{v:+.1f} (floor {f} ms)" for f, v in p["floored_ms"].items()))
    print("group", json.dumps(out["group"]))
    M = out["mixed"]
    print("mixed model, " + f"{M['trials']} trials: " + "; ".join(
        f"{k} {M[k]['estimate']:+.1f} ms (95% CI {M[k]['lower']:.1f} to {M[k]['upper']:.1f}, "
        f"df {M[k]['df']:.0f}, p {M[k]['p']:.2g})" for k in ("post_minus_block8", "slope_per_block", "post_minus_practice")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
