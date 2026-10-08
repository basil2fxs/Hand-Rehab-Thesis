"""The measures: behaviour, ERPs, single-trial statistics and
time-frequency power for the SRT and Buzz Hunt blocks.

One participant, one session: every test here is across that person's
trials, so it says whether an effect is larger than this recording's
own trial-to-trial noise, not that it generalises to people. Each
measure carries its trial count, its standardised measurement error
(SME, the standard error of the single-trial mean amplitude) and, for
waveforms, an odd/even split-half reliability.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import mne

from . import pipeline as P
from .pipeline import REJECT_UV

RNG = np.random.default_rng(2026)
N_PERM = 5000

# Windows (seconds from the event) and their sites, from the
# literature the methods table cites.
SRT_WINDOWS = {
    "P1": ((0.080, 0.130), ["O1", "Oz", "O2"]),
    "N1": ((0.140, 0.200), ["PO7", "PO8", "O1", "O2"]),
    "N2": ((0.200, 0.300), ["FCz", "Cz"]),
    "P3": ((0.300, 0.450), ["Pz", "CPz"]),
}
RESP_BASELINE = (-0.4, -0.2)
RESP_WINDOWS = {
    "ERN": ((0.000, 0.100), ["FCz", "Cz"]),
    "Pe": ((0.200, 0.400), ["CPz", "Pz"]),
}
BUZZ_WINDOWS = {
    "N1 contra": ((0.180, 0.260), ["C3", "CP3", "CP5"]),
    "N1 ipsi": ((0.180, 0.260), ["C4", "CP4", "CP6"]),
    "P3": ((0.400, 0.650), ["Pz", "CPz"]),
}
SRT_LABELS = {
    "random_practice": "Random, practice",
    "sequence_early": "Sequence, blocks 1-2",
    "sequence_late": "Sequence, blocks 7-8",
    "random_posttest": "Random, post-test",
}
COLOURS = {
    "random_practice": "#6b7280", "sequence_early": "#60a5fa",
    "sequence_middle": "#3b82f6", "sequence_late": "#1d4ed8",
    "random_posttest": "#dc2626", "correct": "#059669",
    "error": "#dc2626", "anticipation": "#d97706", "contra": "#7c3aed",
    "ipsi": "#9ca3af", "all": "#111827",
}


# ---- statistics --------------------------------------------------------------
def window_means(ep: mne.Epochs, window, chans) -> np.ndarray:
    """Single-trial mean amplitude (uV) over a window and a site group."""
    lo, hi = window
    x = ep.copy().pick(chans).crop(lo, hi).get_data() * 1e6
    return x.mean(axis=(1, 2))


def sme(values: np.ndarray) -> float:
    """Analytic standardised measurement error of a mean amplitude
    (Luck et al. 2021): SD of the single-trial values over sqrt(n)."""
    v = np.asarray(values, dtype=float)
    return float(v.std(ddof=1) / np.sqrt(len(v))) if len(v) > 1 else np.nan


def perm_diff(a: np.ndarray, b: np.ndarray, n: int = N_PERM) -> dict:
    """Trial-level permutation test of a difference in means, with a
    bootstrap 95 percent interval and Cohen's d (pooled SD)."""
    a = np.asarray(a, float); b = np.asarray(b, float)
    obs = a.mean() - b.mean()
    both = np.concatenate([a, b])
    hits = 0
    for _ in range(n):
        RNG.shuffle(both)
        if abs(both[:len(a)].mean() - both[len(a):].mean()) >= abs(obs):
            hits += 1
    boots = [RNG.choice(a, len(a)).mean() - RNG.choice(b, len(b)).mean()
             for _ in range(2000)]
    sd = np.sqrt(((len(a) - 1) * a.var(ddof=1) + (len(b) - 1) * b.var(ddof=1))
                 / (len(a) + len(b) - 2))
    return {"diff": float(obs), "p": (hits + 1) / (n + 1),
            "ci": [float(np.percentile(boots, 2.5)),
                   float(np.percentile(boots, 97.5))],
            "d": float(obs / sd) if sd > 0 else np.nan,
            "n": [int(len(a)), int(len(b))]}


def split_half(ep: mne.Epochs, chans) -> float:
    """Odd/even split-half reliability of the averaged waveform at a site
    group: the correlation of the two half averages over the whole
    post-event epoch, Spearman-Brown corrected when positive. A short
    window would correlate two nearly flat lines, so the epoch is used."""
    if len(ep) < 4:
        return np.nan
    e = ep.copy().pick(chans).crop(0.0, None)
    x = e.get_data().mean(1)
    r = np.corrcoef(x[0::2].mean(0), x[1::2].mean(0))[0, 1]
    return float(2 * r / (1 + r)) if r > 0 else float(r)


def sign_flip(d: np.ndarray, n: int = N_PERM) -> float:
    """Two-sided sign-flip test of a mean against zero, for values that
    are already differences within a trial."""
    d = np.asarray(d, float)
    hits = sum(abs((d * RNG.choice([-1, 1], len(d))).mean()) >= abs(d.mean())
               for _ in range(n))
    return (hits + 1) / (n + 1)


def pct_change(ep: mne.Epochs, ch: str, fmin: float, fmax: float, rest, window) -> np.ndarray:
    """Each trial's power change from its own rest to a window, as a
    percent of the mean rest power, at one channel (Morlet wavelets,
    cycles half the frequency): the ERD/ERS percent of Pfurtscheller and
    Lopes da Silva (1999), kept linear because a trial-by-trial log
    ratio is biased downwards (Kinley et al. 2026, via MNE's notes)."""
    freqs = np.arange(fmin, fmax + 1, 1.0)
    p = ep.compute_tfr("morlet", freqs=freqs, n_cycles=freqs / 2.0,
                       return_itc=False, average=False, decim=4, picks=[ch],
                       verbose="ERROR")
    d, t = p.get_data()[:, 0], p.times
    base = d[:, :, (t >= rest[0]) & (t < rest[1])].mean((1, 2))
    act = d[:, :, (t >= window[0]) & (t < window[1])].mean((1, 2))
    return (act - base) / base.mean() * 100.0


def measure_table(groups: dict[str, mne.Epochs], windows: dict) -> pd.DataFrame:
    rows = []
    for name, ep in groups.items():
        for comp, (win, chans) in windows.items():
            v = window_means(ep, win, chans)
            rows.append({"condition": name, "measure": comp,
                         "window_ms": f"{int(win[0]*1000)}-{int(win[1]*1000)}",
                         "sites": "/".join(chans), "n": len(v),
                         "mean_uV": float(v.mean()), "sme_uV": sme(v),
                         "split_half": split_half(ep, chans)})
    return pd.DataFrame(rows)


def cluster_test(ep_a: mne.Epochs, ep_b: mne.Epochs, tmin=None, tmax=None,
                 n_perm: int = 1000) -> dict:
    """Spatio-temporal cluster permutation test across trials (Maris and
    Oostenveld 2007): which channels and times differ between two trial
    sets more than the recording's own noise allows."""
    from mne.stats import permutation_cluster_test
    a = ep_a.copy().pick("eeg"); b = ep_b.copy().pick("eeg")
    if tmin is not None:
        a.crop(tmin, tmax); b.crop(tmin, tmax)
    adj, names = mne.channels.find_ch_adjacency(a.info, ch_type="eeg")
    xa = a.get_data().transpose(0, 2, 1) * 1e6
    xb = b.get_data().transpose(0, 2, 1) * 1e6
    t_obs, clusters, pv, _ = permutation_cluster_test(
        [xa, xb], adjacency=adj, n_permutations=n_perm, tail=0,
        seed=2026, out_type="mask", verbose="ERROR")
    out = []
    for c, p in zip(clusters, pv):
        if p < 0.05:
            ti, ci = np.nonzero(c)
            out.append({"p": float(p),
                        "t_ms": [float(a.times[ti.min()] * 1000),
                                 float(a.times[ti.max()] * 1000)],
                        "channels": sorted({a.ch_names[i] for i in ci})})
    out.sort(key=lambda d: d["p"])
    sig = np.zeros(t_obs.shape, bool)
    for c, p in zip(clusters, pv):
        if p < 0.05:
            sig |= c
    return {"clusters": out, "t_obs": t_obs, "mask": sig,
            "times": a.times, "ch_names": a.ch_names}


# ---- SRT ---------------------------------------------------------------------
@dataclass
class SrtResult:
    trials: pd.DataFrame
    behaviour: pd.DataFrame
    learning: dict
    recall: dict
    stim: dict[str, mne.Evoked]
    stim_n: dict[str, int]
    stim_measures: pd.DataFrame
    stim_tests: dict
    per_block: pd.DataFrame
    resp: dict[str, mne.Evoked]
    resp_press: dict[str, mne.Evoked]
    resp_n: dict[str, int]
    resp_measures: pd.DataFrame
    resp_tests: dict
    ern_cluster: dict
    lock_compare: dict
    tfr: dict
    band_tests: dict
    block_power: pd.DataFrame
    beta: dict
    reject: dict = field(default_factory=dict)
    rerp: dict = field(default_factory=dict)


def srt_behaviour(t: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    t = t.copy()
    t["seg"] = np.where(t.phase == "learning", "Sequence " + t.block.astype(str),
                        np.where(t.phase == "practice", "Practice",
                                 "Post-test"))
    order = ["Practice"] + [f"Sequence {i}" for i in range(1, 9)] + ["Post-test"]
    rows = []
    for seg in order:
        s = t[t.seg == seg]
        if s.empty:
            continue
        c = s[s.accuracy == "correct"]
        rows.append({"segment": seg, "n": len(s),
                     "rt_median_ms": float(c.rt_ms.median()),
                     "rt_iqr_ms": float(c.rt_ms.quantile(.75) - c.rt_ms.quantile(.25)),
                     "accuracy": float((s.accuracy == "correct").mean()),
                     "wrong_finger": float((s.accuracy == "incorrect").mean()),
                     "anticipations": float(s.accuracy.str.startswith("anticip").mean()),
                     "misses": float((s.accuracy == "miss").mean())})
    beh = pd.DataFrame(rows)
    c = t[t.accuracy == "correct"]
    late = c[(c.phase == "learning") & (c.block == 8)].rt_ms.to_numpy()
    post = c[c.phase == "posttest"].rt_ms.to_numpy()
    prac = c[c.phase == "practice"].rt_ms.to_numpy()

    def med_ci(a, b):
        boots = [np.median(RNG.choice(a, len(a))) - np.median(RNG.choice(b, len(b)))
                 for _ in range(4000)]
        return [float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))]
    learning = {
        "post_minus_block8_ms": float(np.median(post) - np.median(late)),
        "post_minus_block8_ci": med_ci(post, late),
        "practice_minus_post_ms": float(np.median(prac) - np.median(post)),
        "block1_ms": float(c[(c.phase == "learning") & (c.block == 1)].rt_ms.median()),
        "block8_ms": float(np.median(late)), "post_ms": float(np.median(post)),
        "practice_ms": float(np.median(prac)),
        "n": [int(len(post)), int(len(late))],
    }
    return beh, learning


def srt_recall(folder: Path) -> dict:
    f = sorted(folder.glob("SRT_RECALL_*.csv"))
    if not f:
        return {}
    r = pd.read_csv(f[0])
    rec = r.recalled_finger.astype(str).str.upper().tolist()
    act = r.actual_finger.astype(str).str.upper().tolist()
    n = len(act)
    # The sequence repeats as a cycle, so a recall that starts elsewhere
    # in it is still the sequence: score the best rotation too.
    best = max(range(n), key=lambda k: sum(a == b for a, b in
                                            zip(rec, act[k:] + act[:k])))
    rot = act[best:] + act[:best]
    cyc = int(sum(a == b for a, b in zip(rec, rot)))
    # Taking the best rotation flatters a guess, so the chance level is
    # simulated the same way: random answers from the sequence's keys,
    # each scored at its own best rotation. For a 10-item sequence of
    # four keys, 8 of 10 comes up about 1 time in 240.
    keys = np.array(sorted(set(act)))
    draws = keys[np.random.default_rng(2026).integers(0, len(keys), (20000, n))]
    a = np.array(act)
    top = np.max([(draws == np.roll(a, -k)).sum(1) for k in range(n)], axis=0)
    chance = float(((top >= cyc).sum() + 1) / (len(top) + 1))
    return {"items": n, "correct": int(r.correct.sum()),
            "cyclic_correct": cyc, "cyclic_start": int(best + 1), "chance_p": chance,
            "recalled": "-".join(rec), "actual": "-".join(act)}


def _epochs_by(ep: mne.Epochs, col: str, values) -> dict[str, mne.Epochs]:
    return {v: ep[ep.metadata[col] == v] for v in values
            if (ep.metadata[col] == v).sum() > 0}


def srt(block: P.Block, cleaned: P.Cleaned) -> SrtResult:
    raw = cleaned.raw
    t = P.srt_trials(block)
    beh, learning = srt_behaviour(t)
    recall = srt_recall(block.folder)
    codes30 = np.full(len(t), 30)
    stim_all = P.make_epochs(raw, t.flash_sample, codes30, t, -0.2, 0.6,
                             (-0.2, 0.0))
    reject = {"stimulus": {"kept": len(stim_all), "of": len(t)}}
    stim_ok = stim_all[stim_all.metadata.accuracy == "correct"]
    groups = _epochs_by(stim_ok, "condition", list(SRT_LABELS))
    groups_all = {"all_correct": stim_ok, **groups}
    stim = {k: v.average() for k, v in groups_all.items()}
    stim_n = {k: len(v) for k, v in groups_all.items()}
    measures = measure_table(groups_all, SRT_WINDOWS)
    tests = {}
    for comp in ("N2", "P3"):
        win, chans = SRT_WINDOWS[comp]
        for a, b in (("random_posttest", "sequence_late"),
                     ("random_practice", "sequence_late"),
                     ("sequence_early", "sequence_late")):
            if a in groups and b in groups:
                tests[f"{comp}: {a} vs {b}"] = perm_diff(
                    window_means(groups[a], win, chans),
                    window_means(groups[b], win, chans))
    # P3 and N2 across the learning blocks, beside RT
    rows = []
    for blk in range(1, 9):
        e = stim_ok[(stim_ok.metadata.phase == "learning")
                    & (stim_ok.metadata.block == blk)]
        if len(e) < 5:
            continue
        rt = t[(t.phase == "learning") & (t.block == blk)
               & (t.accuracy == "correct")].rt_ms.median()
        rows.append({"block": blk, "n": len(e), "rt_median_ms": float(rt),
                     "P3_uV": float(window_means(e, *SRT_WINDOWS["P3"]).mean()),
                     "N2_uV": float(window_means(e, *SRT_WINDOWS["N2"]).mean())})
    per_block = pd.DataFrame(rows)

    # response-locked, at the force onset and at the press. ERP CORE's
    # ERN baseline (Kappenman et al. 2021): -400 to -200 ms, clear of
    # the movement's own build-up just before the response.
    codes = t.resp_code.to_numpy()
    resp_on = P.make_epochs(raw, t.onset_sample, codes, t, -0.6, 0.6,
                            RESP_BASELINE)
    resp_pr = P.make_epochs(raw, t.press_sample, codes, t, -0.6, 0.6,
                            RESP_BASELINE)
    reject["response_onset"] = {"kept": len(resp_on),
                                "of": int(np.isfinite(t.onset_sample).sum())}
    rg = _epochs_by(resp_on, "outcome", ["correct", "error", "anticipation"])
    rgp = _epochs_by(resp_pr, "outcome", ["correct", "error", "anticipation"])
    resp = {k: v.average() for k, v in rg.items()}
    resp_press = {k: v.average() for k, v in rgp.items()}
    resp_n = {k: len(v) for k, v in rg.items()}
    resp_measures = measure_table(rg, RESP_WINDOWS)
    resp_tests = {}
    for comp in ("ERN", "Pe"):
        win, chans = RESP_WINDOWS[comp]
        if "error" in rg and "correct" in rg:
            resp_tests[f"{comp}: error vs correct"] = perm_diff(
                window_means(rg["error"], win, chans),
                window_means(rg["correct"], win, chans))
    # The same ERN against the -200 to 0 ms baseline the first pass used,
    # reported beside it so the choice is visible.
    if "error" in rg and "correct" in rg:
        win, chans = RESP_WINDOWS["ERN"]
        alt = {k: rg[k].copy().apply_baseline((-0.2, 0.0), verbose="ERROR")
               for k in ("error", "correct")}
        resp_tests["ERN, baseline -200 to 0 ms: error vs correct"] = perm_diff(
            window_means(alt["error"], win, chans),
            window_means(alt["correct"], win, chans))
    ern_cluster = (cluster_test(rg["error"], rg["correct"], -0.1, 0.5)
                   if "error" in rg and "correct" in rg else {})
    # does locking to the force onset sharpen the ERN?
    lock = {}
    for name, g in (("onset", rg), ("press", rgp)):
        if "error" in g and "correct" in g:
            d = mne.combine_evoked([g["error"].average(), g["correct"].average()],
                                   weights=[1, -1]).pick(["FCz"])
            x = d.data[0] * 1e6
            tt = d.times
            sel = (tt >= -0.05) & (tt <= 0.15)
            i = np.argmin(x[sel])
            peak = float(x[sel][i])
            half = peak / 2
            below = np.flatnonzero(x[sel] <= half)
            width = float((tt[sel][below[-1]] - tt[sel][below[0]]) * 1000) if len(below) else np.nan
            lock[name] = {"peak_uV": peak, "peak_ms": float(tt[sel][i] * 1000),
                          "fwhm_ms": width}

    # time-frequency: random vs late sequence, stimulus-locked
    tf_ep = P.make_epochs(raw, t.flash_sample, codes30, t, -0.8, 1.0, None)
    tf_ok = tf_ep[tf_ep.metadata.accuracy == "correct"]
    freqs = np.arange(4, 31, 1.0)
    tfr = {}
    for cond in ("random_posttest", "sequence_late", "random_practice"):
        e = tf_ok[tf_ok.metadata.condition == cond]
        if len(e) < 5:
            continue
        p = e.compute_tfr("morlet", freqs=freqs, n_cycles=freqs / 2.0,
                          return_itc=False, average=False, decim=4,
                          picks=["FCz", "Cz", "C3", "C4", "Pz", "Oz"],
                          verbose="ERROR")
        tfr[cond] = p
    band_tests = {}
    bands = {"theta FCz/Cz": ((4, 7), ["FCz", "Cz"]),
             "alpha C3": ((8, 12), ["C3"]), "alpha Pz/Oz": ((8, 12), ["Pz", "Oz"]),
             "beta C3": ((13, 30), ["C3"])}
    if "random_posttest" in tfr and "sequence_late" in tfr:
        for name, ((f0, f1), chans) in bands.items():
            vals = {}
            for cond in ("random_posttest", "sequence_late"):
                p = tfr[cond]
                fi = (p.freqs >= f0) & (p.freqs <= f1)
                ti = (p.times >= 0.0) & (p.times <= 0.5)
                ci = [p.ch_names.index(c) for c in chans]
                x = p.data[:, ci][:, :, fi][:, :, :, ti].mean(axis=(1, 2, 3))
                vals[cond] = 10 * np.log10(x)
            band_tests[name] = perm_diff(vals["random_posttest"], vals["sequence_late"])

    # block-wise band power of the continuous recording, block by block
    rows = []
    sf = raw.info["sfreq"]
    tt = t.copy()
    tt["seg"] = np.where(tt.phase == "learning", "Sequence " + tt.block.astype(str),
                         np.where(tt.phase == "practice", "Practice", "Post-test"))
    for seg in ["Practice"] + [f"Sequence {i}" for i in range(1, 9)] + ["Post-test"]:
        s = tt[tt.seg == seg]
        if s.empty:
            continue
        a = int(s.flash_sample.min()); b = int(s.flash_sample.max() + 0.8 * sf)
        seg_raw = raw.copy().crop(a / sf, min(b / sf, raw.times[-1]))
        psd = seg_raw.compute_psd(method="welch", fmin=2, fmax=35, picks=["FCz", "Cz", "C3", "C4", "Pz", "Oz"],
                                  n_fft=int(2 * sf), verbose="ERROR")
        f = psd.freqs; d = psd.get_data() * 1e12
        def bp(ch, lo, hi):
            return float(10 * np.log10(d[psd.ch_names.index(ch)][(f >= lo) & (f <= hi)].mean()))
        rows.append({"segment": seg, "theta_FCz_dB": bp("FCz", 4, 7),
                     "alpha_Pz_dB": bp("Pz", 8, 12), "alpha_C3_dB": bp("C3", 8, 12),
                     "beta_C3_dB": bp("C3", 13, 30), "beta_C4_dB": bp("C4", 13, 30)})
    block_power = pd.DataFrame(rows)

    # movement beta around the press: C3 (contralateral) against C4
    beta = {}
    mv = P.make_epochs(raw, t.onset_sample, codes, t, -0.8, 0.8, None)
    mv = mv[mv.metadata.outcome == "correct"]
    if len(mv) > 10:
        p = mv.compute_tfr("morlet", freqs=freqs, n_cycles=freqs / 2.0,
                           return_itc=False, average=True, decim=4,
                           picks=["C3", "C4", "Cz"], verbose="ERROR")
        p.apply_baseline((None, None), mode="logratio", verbose="ERROR")
        beta = {"tfr": p, "n": len(mv)}
    rerp = srt_rerp(raw, t)
    return SrtResult(trials=t, behaviour=beh, learning=learning, recall=recall,
                     stim=stim, stim_n=stim_n, stim_measures=measures,
                     stim_tests=tests, per_block=per_block, resp=resp,
                     resp_press=resp_press, resp_n=resp_n,
                     resp_measures=resp_measures, resp_tests=resp_tests,
                     ern_cluster=ern_cluster, lock_compare=lock, tfr=tfr,
                     band_tests=band_tests, block_power=block_power,
                     beta=beta, reject=reject, rerp=rerp)


RERP_FLASH = {"practice": 1, "seq_early": 2, "seq_middle": 3, "seq_late": 4,
              "posttest": 5}
RERP_RESP = {"correct": 11, "error": 12, "anticipation": 13}
RERP_FLASH_OF = {"random_practice": "practice", "sequence_early": "seq_early",
                 "sequence_middle": "seq_middle", "sequence_late": "seq_late",
                 "random_posttest": "posttest"}


def srt_rerp(raw: mne.io.BaseRaw, t: pd.DataFrame) -> dict:
    """Overlap-corrected ERPs (regression ERPs, Smith and Kutas 2015):
    every flash and every press is a predictor at once, so the flash
    response no longer leaks into the press average and the press
    response no longer leaks into the next flash. Presses enter at their
    force onset."""
    from mne.stats import linear_regression_raw
    ev = []
    for _, r in t.iterrows():
        c = RERP_FLASH.get(RERP_FLASH_OF.get(r.condition, ""))
        if c:
            ev.append([int(r.flash_sample), 0, c])
        o = RERP_RESP.get(r.outcome)
        if o and np.isfinite(r.onset_sample):
            ev.append([int(r.onset_sample), 0, o])
    ev = np.array(sorted(ev, key=lambda e: e[0]))
    ev = ev[np.concatenate([[True], np.diff(ev[:, 0]) > 0])]
    ids = {f"flash/{k}": v for k, v in RERP_FLASH.items()}
    ids.update({f"press/{k}": v for k, v in RERP_RESP.items()})
    ids = {k: v for k, v in ids.items() if (ev[:, 2] == v).any()}
    tmin = {k: (-0.2 if k.startswith("flash") else -0.4) for k in ids}
    tmax = {k: (0.7 if k.startswith("flash") else 0.6) for k in ids}
    out = linear_regression_raw(raw.copy().pick("eeg"), ev, ids, tmin=tmin,
                                tmax=tmax, reject=dict(eeg=REJECT_UV * 1e-6),
                                tstep=0.5, solver="cholesky")
    for k, e in out.items():
        e.apply_baseline((-0.2, 0.0) if k.startswith("flash") else (-0.4, -0.2),
                         verbose="ERROR")
    counts = {k: int((ev[:, 2] == v).sum()) for k, v in ids.items()}
    return {"evoked": out, "n": counts}


# ---- Buzz Hunt ---------------------------------------------------------------
@dataclass
class BuzzResult:
    trials: pd.DataFrame
    summary: dict
    erp: dict[str, mne.Evoked]
    erp_n: dict[str, int]
    measures: pd.DataFrame
    tests: dict
    tfr: dict
    pre: dict
    reject: dict
    press: dict = field(default_factory=dict)


def _parse(stim: str) -> dict:
    parts = str(stim).split(";")
    out = {"stage": parts[0], "catch": "catch" in parts}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            out[k] = v
    return out


def buzz_trials(block: P.Block) -> pd.DataFrame:
    t = block.trials.copy()
    info = pd.DataFrame([_parse(s) for s in t.stimulus])
    t = pd.concat([t.reset_index(drop=True), info], axis=1)
    t["correct"] = t.error_type.isna() & t.feedback.isin(
        ["Good", "Late", "Great", "Perfect", "CatchOk"])
    pairs = block.alignment.pairs
    sf = block.raw.info["sfreq"]
    b38 = pairs[pairs.code_eeg == 38].reset_index(drop=True)
    real = t[~t["catch"]].index
    t["buzz_sample"] = np.nan
    t["marker_lane"] = np.nan
    k = min(len(real), len(b38))
    t.loc[real[:k], "buzz_sample"] = np.round(b38.eeg_s[:k].to_numpy() * sf)
    t.loc[real[:k], "marker_lane"] = pd.to_numeric(b38.lane[:k], errors="coerce").to_numpy()
    return t


def buzz(block: P.Block, cleaned: P.Cleaned) -> BuzzResult:
    raw = cleaned.raw
    t = buzz_trials(block)
    m = json.loads((block.folder / "metadata.json").read_text())
    summary = m["block_summary"]["buzz_hunt"]
    real = t[t.buzz_sample.notna()]
    ep = P.make_epochs(raw, real.buzz_sample, np.full(len(real), 38),
                       real.reset_index(drop=True), -0.2, 0.8, (-0.2, 0.0))
    reject = {"buzz": {"kept": len(ep), "of": len(real)}}
    loc = ep[ep.metadata.stage == "loc"]
    groups = {"localisation": loc, "all_buzzes": ep,
              "gap": ep[ep.metadata.stage == "gap"],
              "span": ep[ep.metadata.stage == "span"]}
    groups = {k: v for k, v in groups.items() if len(v)}
    erp = {k: v.average() for k, v in groups.items()}
    erp_n = {k: len(v) for k, v in groups.items()}
    measures = measure_table({"localisation": loc}, BUZZ_WINDOWS)
    tests = {}
    w, c3 = BUZZ_WINDOWS["N1 contra"]
    _, c4 = BUZZ_WINDOWS["N1 ipsi"]
    a = window_means(loc, w, c3); b = window_means(loc, w, c4)
    d = a - b
    tests["contra minus ipsi, 180-260 ms"] = {
        "diff": float(d.mean()), "p": sign_flip(d), "sme": sme(d),
        "n": int(len(d)), "unit": "µV"}
    # time-frequency: mu and beta after the buzz, C3 against C4
    tf = P.make_epochs(raw, real.buzz_sample, np.full(len(real), 38),
                       real.reset_index(drop=True), -1.0, 1.8, None)
    tf = tf[tf.metadata.stage == "loc"]
    freqs = np.arange(4, 31, 1.0)
    tfr = {}
    if len(tf) > 5:
        p = tf.compute_tfr("morlet", freqs=freqs, n_cycles=freqs / 2.0,
                           return_itc=False, average=True, decim=4,
                           picks=["C3", "C4", "Cz", "CP3", "CP4", "Pz"],
                           verbose="ERROR")
        p.apply_baseline((-0.7, -0.2), mode="percent", verbose="ERROR")
        tfr = {"tfr": p, "n": len(tf)}
        # mu over the hand's motor area while the touch is felt and the
        # finger answers, trial by trial against that trial's rest
        mu = pct_change(tf, "C3", 8, 12, (-0.7, -0.2), (0.2, 0.8))
        tests["mu C3 after the buzz, 0.2-0.8 s"] = {
            "diff": float(mu.mean()), "p": sign_flip(mu), "sme": sme(mu),
            "n": int(len(mu)), "unit": "%"}
    # the wait before the buzz: a slow negativity as the buzz nears
    pre_ep = P.make_epochs(raw, real.buzz_sample, np.full(len(real), 38),
                           real.reset_index(drop=True), -1.2, 0.3, (-1.2, -1.0))
    pre = {"evoked": pre_ep.average(), "n": len(pre_ep)} if len(pre_ep) else {}
    press = buzz_presses(block, cleaned, t)
    if press.get("rebound_db") is not None:
        reb = press["rebound_db"]
        tests["beta C3 after the press, 0.5-1.5 s"] = {
            "diff": float(reb.mean()), "p": sign_flip(reb), "sme": sme(reb),
            "n": int(len(reb)), "unit": "%"}
    return BuzzResult(trials=t, summary=summary, erp=erp, erp_n=erp_n,
                      measures=measures, tests=tests, tfr=tfr, pre=pre,
                      reject=reject, press=press)


def buzz_presses(block: P.Block, cleaned: P.Cleaned, t: pd.DataFrame) -> dict:
    """The press that answered each correct localisation buzz, placed in
    the recording through the game-to-EEG clock map at its force onset
    (the game sends no byte for these presses). Gives the motor cortex's
    activity before and after a well-spaced press."""
    import sys
    app = Path(__file__).resolve().parents[2] / "app"
    if str(app) not in sys.path:
        sys.path.insert(0, str(app))
    from finger_rehab.hardware.eeg_trigger import (read_force_streams,
                                                   response_offsets)
    raw_csv = block.folder / "raw.csv"
    streams = read_force_streams(raw_csv)
    log = pd.read_csv(raw_csv, low_memory=False)
    ev = log.event.fillna("").astype(str)
    presses = log[(ev == "press") & ~log.detail.fillna("").astype(str).str.contains("keyboard")]
    pairs = block.alignment.pairs
    b38 = pairs[pairs.code_eeg == 38].reset_index(drop=True)
    real = t[t.buzz_sample.notna()].reset_index(drop=True)
    samples, rows = [], []
    sf = block.raw.info["sfreq"]
    pt = presses.t_perf.to_numpy(float)
    for i, r in real.iterrows():
        if r.stage != "loc" or not r.correct or i >= len(b38):
            continue
        t_buzz = float(b38.t_event[i])
        j = int(np.searchsorted(pt, t_buzz))
        if j >= len(pt) or pt[j] - t_buzz > 3.0:
            continue
        p = presses.iloc[j]
        lane = int(p.lane)
        press_ms, onset_ms = response_offsets(streams, 100 + lane, lane, "right",
                                              float(p.t_perf), float(p.t_perf))
        if onset_ms is None:
            continue
        s_eeg = block.alignment.to_eeg_seconds(float(p.t_perf) + onset_ms / 1000.0)
        samples.append(int(round(s_eeg * sf)))
        rows.append({"trial": int(r.trial), "lane": lane,
                     "rt_ms": float(r.time_difference_ms),
                     "rise_ms": float(press_ms - onset_ms)})
    if len(samples) < 5:
        return {}
    meta = pd.DataFrame(rows)
    raw = cleaned.raw
    erp = P.make_epochs(raw, samples, np.full(len(samples), 100), meta,
                        -1.0, 0.6, (-1.0, -0.8))
    tf = P.make_epochs(raw, samples, np.full(len(samples), 100), meta,
                       -1.5, 2.0, None)
    freqs = np.arange(4, 31, 1.0)
    p = tf.compute_tfr("morlet", freqs=freqs, n_cycles=freqs / 2.0,
                       return_itc=False, average=True, decim=4,
                       picks=["C3", "Cz", "C4", "CP3"], verbose="ERROR")
    p.apply_baseline((-1.2, -0.8), mode="percent", verbose="ERROR")
    # the post-movement beta rebound (Pfurtscheller and Lopes da Silva
    # 1999), 0.5 to 1.5 s after the force onset, trial by trial
    rebound = pct_change(tf, "C3", 13, 30, (-1.2, -0.8), (0.5, 1.5))
    return {"erp": erp.average(), "n": len(erp), "tfr": p,
            "rise_ms": float(meta.rise_ms.median()), "rebound_db": rebound}
