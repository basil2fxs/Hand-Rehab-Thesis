"""Two or more recorded sessions read together.

Each session is analysed on its own first (python3 -m eeg SESSIONS); this
reads the sessions' cached computations back and asks whether an effect
holds across the people recorded. The statistic is each person's own
difference between two conditions, averaged over people, and the test
shuffles the condition labels within each person only, so one person's
level never stands in for an effect. With two people the answer is about
these two people, not about people in general.

    cd analysis
    python3 -m eeg.group SESSIONS_1 SESSIONS_2 --out DIR

Writes DIR/group_summary.json and DIR/figures/. The measures are the
single-session ones (analyses.SRT_WINDOWS, the band tests): the N2 and P3
of the flash and beta power at C3, random against learned.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pickle
import tempfile
import warnings
from pathlib import Path

import numpy as np

N_PERM = 10000
SEED = 2026


# ---- statistics (plain numpy, tested without MNE) ---------------------------
def stratified_perm(people, n: int = N_PERM, seed: int = SEED) -> dict:
    """people is a list of (a, b) single-trial arrays, one pair per person.
    The statistic is the mean over people of mean(a) minus mean(b); the
    null shuffles a against b inside each person."""
    rng = np.random.default_rng(seed)
    pairs = [(np.asarray(a, float), np.asarray(b, float)) for a, b in people]
    per = [float(a.mean() - b.mean()) for a, b in pairs]
    obs = float(np.mean(per))
    pools = [np.concatenate([a, b]) for a, b in pairs]
    hits = 0
    for _ in range(n):
        d = []
        for (a, _b), pool in zip(pairs, pools):
            rng.shuffle(pool)
            d.append(pool[:len(a)].mean() - pool[len(a):].mean())
        if abs(np.mean(d)) >= abs(obs):
            hits += 1
    return {"diff": obs, "per_person": per, "p": (hits + 1) / (n + 1),
            "n": [[int(len(a)), int(len(b))] for a, b in pairs]}


def rt_matched(rt_a, rt_b) -> np.ndarray:
    """For each trial of a, the index of the trial of b whose reaction
    time is nearest, each trial of b used once. The slowest trials of a
    pick first, since a fast learned block has the fewest partners for
    them."""
    rt_a, rt_b = np.asarray(rt_a, float), np.asarray(rt_b, float)
    if len(rt_b) < len(rt_a):
        raise ValueError("fewer trials to match from than to match")
    free = np.ones(len(rt_b), bool)
    out = np.empty(len(rt_a), int)
    for i in np.argsort(-rt_a):
        j = int(np.argmin(np.where(free, np.abs(rt_b - rt_a[i]), np.inf)))
        out[i], free[j] = j, False
    return out


def holm(ps) -> list[float]:
    """Holm's step-down adjustment, in the order given."""
    ps = list(map(float, ps))
    order = np.argsort(ps)
    out, run = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - rank) * ps[i]))
        out[i] = run
    return out


# ---- reading the sessions back ------------------------------------------------
def cached(sessions: Path):
    """The (blocks, cleaned, results) a session run left in the temporary
    folder, computed afresh when the cache is gone."""
    key = hashlib.sha1(str(sessions.resolve()).encode()).hexdigest()[:12]
    cache = Path(tempfile.gettempdir()) / f"finger_rehab_eeg_{key}.pkl"
    if cache.is_file():
        return pickle.loads(cache.read_bytes())
    from .__main__ import compute
    out = compute(sessions.resolve())
    cache.write_bytes(pickle.dumps(out))
    return out


def single_trials(cleaned, results) -> dict:
    """Per condition, the single-trial N2 and P3 window means of correct
    flash trials (uV), and the single-trial beta power at C3 (dB) for the
    two conditions the band test compares."""
    from . import pipeline as P
    from .analyses import SRT_WINDOWS, window_means
    r = results["srt"]
    t = r.trials
    ep = P.make_epochs(cleaned["srt"].raw, t.flash_sample, np.full(len(t), 30), t, -0.2, 0.6,
                       (-0.2, 0.0))
    ep = ep[ep.metadata.accuracy == "correct"]
    out = {}
    for comp in ("N2", "P3"):
        win, chans = SRT_WINDOWS[comp]
        out[comp] = {c: window_means(ep[ep.metadata.condition == c], win, chans)
                     for c in ("random_practice", "sequence_early", "sequence_late", "random_posttest")
                     if (ep.metadata.condition == c).sum() > 0}
    beta = {}
    for cond, p in (r.tfr or {}).items():
        fi = (p.freqs >= 13) & (p.freqs <= 30)
        ti = (p.times >= 0.0) & (p.times <= 0.5)
        ci = [p.ch_names.index("C3")]
        x = p.data[:, ci][:, :, fi][:, :, :, ti].mean(axis=(1, 2, 3))
        beta[cond] = 10 * np.log10(x)
    out["beta"] = beta
    return out


def evoked(results, cond: str, chans) -> tuple[np.ndarray, np.ndarray] | None:
    """A session's average flash response for one condition at a site
    group, in uV, with its times in ms."""
    e = (results["srt"].stim or {}).get(cond)
    if e is None:
        return None
    return e.times * 1000, e.copy().pick(chans).data.mean(0) * 1e6


CONTRASTS = (("N2", "random_posttest", "sequence_late"),
             ("P3", "random_practice", "sequence_late"),
             ("beta", "random_posttest", "sequence_late"))
# The P3's planned contrast runs from the first block to the last ones,
# so time on the task could shrink it as well as learning. The random
# post-test comes last and tells the two apart; it is reported as a
# check, outside Holm.
CHECKS = (("P3", "random_posttest", "sequence_late"),)


def group(trials: list[dict]) -> dict:
    """The across-people tests of the single-session contrasts, Holm
    across the N2 and P3 as in each session's own analysis."""
    tests = {}
    for comp, a, b in CONTRASTS + CHECKS:
        people = [(tr[comp][a], tr[comp][b]) for tr in trials if a in tr[comp] and b in tr[comp]]
        if len(people) == len(trials):
            tests[f"{comp}: {a} vs {b}"] = stratified_perm(people)
    erp = [k for k in (f"{c}: {a} vs {b}" for c, a, b in CONTRASTS if c in ("N2", "P3")) if k in tests]
    for k, p in zip(erp, holm([tests[k]["p"] for k in erp])):
        tests[k]["p_holm"] = p
    return tests


def _beta_db(p, t0: float, t1: float) -> np.ndarray:
    """Single-trial beta power (13 to 30 Hz) at C3 in a time window, dB."""
    fi = (p.freqs >= 13) & (p.freqs <= 30)
    ti = (p.times >= t0) & (p.times <= t1)
    ci = [p.ch_names.index("C3")]
    return 10 * np.log10(p.data[:, ci][:, :, fi][:, :, :, ti].mean(axis=(1, 2, 3)))


def beta_timing(cleaned, results) -> dict:
    """Is the beta difference timing? Random flashes are answered later
    than learned ones, so a window fixed to the flash can catch the beta
    drop of the movement later on random trials. Two readings take
    reaction time out: the flash-locked beta with each random trial set
    against the learned trial nearest it in reaction time, and the beta
    in the half second before the press itself."""
    from . import pipeline as P
    r = results["srt"]
    a, b = r.tfr["random_posttest"], r.tfr["sequence_late"]
    rt_a, rt_b = a.metadata.rt_ms.to_numpy(float), b.metadata.rt_ms.to_numpy(float)
    idx = rt_matched(rt_a, rt_b)
    out = {"matched": {"random": _beta_db(a, 0.0, 0.5), "learned": _beta_db(b, 0.0, 0.5)[idx],
                       "rt_ms": [float(np.median(rt_a)), float(np.median(rt_b[idx])), float(np.median(rt_b))]}}
    t = r.trials
    use = ((t.accuracy == "correct") & t.condition.isin(["random_posttest", "sequence_late"])
           & np.isfinite(t.press_sample.to_numpy(float))).to_numpy()
    tk = t[use].reset_index(drop=True)
    ep = P.make_epochs(cleaned["srt"].raw, tk.press_sample, np.full(len(tk), 1), tk, -1.0, 0.6, None)
    freqs = np.arange(13, 31, 1.0)
    pr = ep.compute_tfr("morlet", freqs=freqs, n_cycles=freqs / 2.0, return_itc=False, average=False,
                        decim=4, picks=["C3"], verbose="ERROR")
    cond = pr.metadata.condition.to_numpy()
    pre = _beta_db(pr, -0.5, 0.0)
    out["press"] = {"random": pre[cond == "random_posttest"], "learned": pre[cond == "sequence_late"]}
    return out


def ica_sensitivity(cleaned, results, exclude) -> dict:
    """The single-session N2 and P3 tests again after removing the named
    independent components, for a recording where no eye component met
    the criterion: whether leaving them in changed the result."""
    from . import pipeline as P
    from .analyses import SRT_WINDOWS, perm_diff, window_means
    c = cleaned["srt"]
    ica = c.ica.copy()
    ica.exclude = list(exclude)
    raw = ica.apply(c.raw.copy(), verbose="ERROR")
    t = results["srt"].trials
    ep = P.make_epochs(raw, t.flash_sample, np.full(len(t), 30), t, -0.2, 0.6, (-0.2, 0.0))
    ep = ep[ep.metadata.accuracy == "correct"]
    out = {"excluded": list(map(int, exclude)), "kept": int(len(ep))}
    for comp, a, b in CONTRASTS[:2]:
        win, chans = SRT_WINDOWS[comp]
        va = window_means(ep[ep.metadata.condition == a], win, chans)
        vb = window_means(ep[ep.metadata.condition == b], win, chans)
        out[f"{comp}: {a} vs {b}"] = perm_diff(va, vb, rng=np.random.default_rng(SEED))
    return out


def figure(results_list, names, path: Path) -> str:
    """The flash response of each person and their average: the N2 at
    FCz/Cz, random post-test against the learned sequence, and the P3 at
    Pz/CPz, random practice against the learned sequence."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from .analyses import COLOURS, SRT_WINDOWS
    panels = [("N2", "random_posttest", "sequence_late", "Front of the head (FCz, Cz)"),
              ("P3", "random_practice", "sequence_late", "Top back of the head (Pz, CPz)")]
    fig, axes = plt.subplots(1, 2, figsize=(7.0, 2.9), sharex=True)
    for ax, (comp, a, b, title) in zip(axes, panels):
        win, chans = SRT_WINDOWS[comp]
        ax.axvspan(win[0] * 1000, win[1] * 1000, color="#e5e7eb", zorder=0)
        for cond, lab in ((a, "random"), (b, "learned")):
            waves = [evoked(r, cond, chans) for r in results_list]
            waves = [w for w in waves if w is not None]
            if not waves:
                continue
            ms = waves[0][0]
            for w in waves:
                ax.plot(ms, w[1], color=COLOURS[cond], lw=0.7, alpha=0.45)
            ax.plot(ms, np.mean([w[1] for w in waves], 0), color=COLOURS[cond], lw=2.0,
                    label=f"{lab}, mean of {len(waves)}")
        ax.axvline(0, color="#6b7280", lw=0.6, ls="--")
        ax.axhline(0, color="#9ca3af", lw=0.5)
        ax.set_title(f"{comp}: {title}", fontsize=9)
        ax.set_xlabel("Time after the flash (ms)", fontsize=8)
        ax.tick_params(labelsize=7)
        ax.set_xlim(-200, 600)
        ax.legend(fontsize=7, frameon=False, loc="lower left" if comp == "N2" else "upper right")
    axes[0].set_ylabel("µV", fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=300)
    plt.close(fig)
    return path.name


def _json(o):
    if isinstance(o, dict):
        return {str(k): _json(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, float) and not np.isfinite(o):
        return None
    return o


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("sessions", type=Path, nargs="+")
    ap.add_argument("--names", nargs="+", default=None)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--beta-check", action="store_true",
                    help="the beta contrast with reaction time taken out (beta_timing)")
    ap.add_argument("--ica-check", nargs="*", default=[],
                    help="SESSION_INDEX:COMP,COMP to rerun one session's N2 and P3 without those components")
    args = ap.parse_args(argv)
    warnings.filterwarnings("ignore")
    import mne
    mne.set_log_level("ERROR")
    names = args.names or [f"EEG Subject {i + 1}" for i in range(len(args.sessions))]
    runs = [cached(s) for s in args.sessions]
    trials = [single_trials(c, r) for _b, c, r in runs]
    out = {"people": names, "tests": group(trials), "per_person": {}}
    for name, tr in zip(names, trials):
        out["per_person"][name] = {
            comp: {cond: {"n": int(len(v)), "mean": float(np.mean(v))} for cond, v in tr[comp].items()}
            for comp in ("N2", "P3", "beta")}
    if args.beta_check:
        from .analyses import perm_diff
        timing = [beta_timing(c, r) for _b, c, r in runs]
        out["beta_timing"] = {}
        for kind in ("matched", "press"):
            people = [(x[kind]["random"], x[kind]["learned"]) for x in timing]
            out["beta_timing"][kind] = {
                "both": stratified_perm(people),
                "per_person": {name: perm_diff(*pair, rng=np.random.default_rng(SEED))
                               for name, pair in zip(names, people)}}
        out["beta_timing"]["matched"]["rt_ms"] = {name: x["matched"]["rt_ms"] for name, x in zip(names, timing)}
    for spec in args.ica_check:
        i, comps = spec.split(":")
        _b, c, r = runs[int(i)]
        out.setdefault("ica_sensitivity", {})[names[int(i)]] = ica_sensitivity(
            c, r, [int(x) for x in comps.split(",")])
    out["figure"] = figure([r for _b, _c, r in runs], names, args.out / "figures" / "group_srt_erp.png")
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "group_summary.json").write_text(json.dumps(_json(out), indent=1), encoding="utf-8")
    print(json.dumps(_json(out["tests"]), indent=1))
    if "ica_sensitivity" in out:
        print(json.dumps(_json(out["ica_sensitivity"]), indent=1))
    if "beta_timing" in out:
        print(json.dumps(_json(out["beta_timing"]), indent=1))
    print("written", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
