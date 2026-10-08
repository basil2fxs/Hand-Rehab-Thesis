"""Reaction against Buzz Hunt: the brain's response to each game's cue.

Reaction's cue is a flash with a tone; Buzz Hunt's is a buzz on the
finger and nothing else. Both were recorded from the same cap in one
sitting, so the comparison is within one person. Reaction's random
flashes (practice and post-test) stand against Buzz Hunt's localisation
buzzes, so neither side carries a learned sequence.

Measures, all set before the comparison was run:
- the P3 as the mean of 300 to 650 ms at Pz/CPz, a window that holds
  both games' own P3 windows, compared trial against trial;
- the P3's timing as the 50 percent fractional area latency of the
  positive area in 250 to 750 ms (Luck 2014), compared by jackknife
  (Miller, Patterson and Ulrich 1998; Kiesel et al. 2008), leaving one
  trial out at a time;
- the earliest cortical response: the visual P1 at O1/Oz/O2 for the
  flash, the negativity opposite the buzzed hand at C3/CP3/CP5 for the
  buzz, as the peak of the average;
- reaction time and accuracy from the games' own logs.
"""
from __future__ import annotations

import numpy as np

import mne

from . import pipeline as P
from .analyses import BUZZ_WINDOWS, SRT_WINDOWS, perm_diff, sme, window_means

P3_COMMON = ((0.30, 0.65), ["Pz", "CPz"])
P3_LATENCY_WINDOW = (0.25, 0.75)
EARLY = {"reaction": ("visual P1", (0.06, 0.16), ["O1", "Oz", "O2"], +1),
         "buzz": ("touch N1", (0.12, 0.30), ["C3", "CP3", "CP5"], -1)}
SITES = ["Oz", "Cz", "C3", "Pz"]
TOPO_TIMES = (0.10, 0.20, 0.35, 0.50)
LABELS = {"reaction": "Reaction: flash and tone", "buzz": "Buzz Hunt: buzz only"}
COLOURS = {"reaction": "#ea580c", "buzz": "#7c3aed"}


def cue_epochs(results: dict, cleaned: dict) -> dict[str, mne.Epochs]:
    out = {}
    if "srt" in results:
        t = results["srt"].trials
        sel = t[t.condition.isin(["random_practice", "random_posttest"])
                & (t.accuracy == "correct")].reset_index(drop=True)
        out["reaction"] = P.make_epochs(cleaned["srt"].raw, sel.flash_sample,
                                        np.full(len(sel), 30), sel,
                                        -0.2, 0.8, (-0.2, 0.0))
    if "buzz_hunt" in results:
        t = results["buzz_hunt"].trials
        sel = t[(t.stage == "loc") & t.buzz_sample.notna()].reset_index(drop=True)
        out["buzz"] = P.make_epochs(cleaned["buzz_hunt"].raw, sel.buzz_sample,
                                    np.full(len(sel), 38), sel,
                                    -0.2, 0.8, (-0.2, 0.0))
    return out


def _site_wave(ep: mne.Epochs, chans) -> np.ndarray:
    """Trials by times, microvolts, averaged over the site group."""
    return ep.copy().pick(chans).get_data().mean(axis=1) * 1e6


def fractional_area_latency(wave: np.ndarray, times: np.ndarray,
                            window=P3_LATENCY_WINDOW, frac: float = 0.5) -> float:
    """Time (s) at which the positive area in the window reaches frac of
    its total."""
    sel = (times >= window[0]) & (times <= window[1])
    y = np.clip(wave[sel], 0, None)
    if y.sum() <= 0:
        return np.nan
    c = np.cumsum(y) / y.sum()
    return float(times[sel][np.searchsorted(c, frac)])


def jackknife_latency(trials: np.ndarray, times: np.ndarray) -> tuple[float, float]:
    """Latency of the full average and its jackknife standard error."""
    n = len(trials)
    full = fractional_area_latency(trials.mean(0), times)
    total = trials.sum(0)
    loo = np.array([fractional_area_latency((total - trials[i]) / (n - 1), times)
                    for i in range(n)])
    se = float(np.sqrt((n - 1) / n * np.nansum((loo - np.nanmean(loo)) ** 2)))
    return full, se


def _early_peak(ep: mne.Epochs, window, chans, sign) -> dict:
    w = _site_wave(ep, chans).mean(0)
    tt = ep.times
    sel = (tt >= window[0]) & (tt <= window[1])
    i = int(np.argmax(sign * w[sel]))
    return {"latency_ms": float(tt[sel][i] * 1000), "amplitude_uV": float(w[sel][i])}


def compare(results: dict, cleaned: dict, blocks) -> dict:
    """Every number the comparison quotes, plus the epochs it drew."""
    from scipy import stats
    ep = cue_epochs(results, cleaned)
    if len(ep) < 2:
        return {}
    out = {"epochs": ep, "modes": {}}
    sf = {b.mode: b.raw.info["sfreq"] for b in blocks}
    win, chans = P3_COMMON
    p3 = {k: window_means(e, win, chans) for k, e in ep.items()}
    lat = {k: jackknife_latency(_site_wave(e, chans), e.times) for k, e in ep.items()}
    own = {"reaction": SRT_WINDOWS["P3"], "buzz": BUZZ_WINDOWS["P3"]}
    for k, e in ep.items():
        early_name, ewin, echans, esign = EARLY[k]
        ow, oc = own[k]
        out["modes"][k] = {
            "label": LABELS[k], "n": int(len(e)),
            "p3_uV": float(p3[k].mean()), "p3_sme_uV": sme(p3[k]),
            "p3_latency_ms": lat[k][0] * 1000, "p3_latency_se_ms": lat[k][1] * 1000,
            "p3_own_uV": float(window_means(e, ow, oc).mean()),
            "p3_own_window_ms": f"{ow[0] * 1000:.0f}-{ow[1] * 1000:.0f}",
            "early": {"name": early_name, "sites": "/".join(echans),
                      **_early_peak(e, ewin, echans, esign)},
        }
    # behaviour and pacing from the games' own logs
    srt = results["srt"].trials
    rnd = srt[srt.condition.isin(["random_practice", "random_posttest"])]
    rt_r = rnd[rnd.accuracy == "correct"].rt_ms.to_numpy(float)
    fs = np.sort(srt.flash_sample.to_numpy(float))
    gaps_r = np.diff(fs) / sf["srt"]
    gaps_r = gaps_r[gaps_r < 3.0]
    bz = results["buzz_hunt"].trials
    loc = bz[(bz.stage == "loc") & bz.buzz_sample.notna()]
    rt_b = loc[loc.correct].time_difference_ms.to_numpy(float)
    bs = np.sort(loc.buzz_sample.to_numpy(float))
    gaps_b = np.diff(bs) / sf["buzz_hunt"]
    out["modes"]["reaction"].update(
        rt_ms=float(np.median(rt_r)), accuracy=float((rnd.accuracy == "correct").mean()),
        trials_logged=int(len(rnd)), spacing_s=[float(np.percentile(gaps_r, 10)),
                                                float(np.percentile(gaps_r, 90))])
    out["modes"]["buzz"].update(
        rt_ms=float(np.median(rt_b)), accuracy=float(loc.correct.mean()),
        trials_logged=int(len(loc)), spacing_s=[float(np.percentile(gaps_b, 10)),
                                                float(np.percentile(gaps_b, 90))])
    # the tests
    t_p3 = perm_diff(p3["buzz"], p3["reaction"])
    d_lat = (lat["buzz"][0] - lat["reaction"][0]) * 1000
    se_lat = np.hypot(lat["buzz"][1], lat["reaction"][1]) * 1000
    df = len(ep["buzz"]) + len(ep["reaction"]) - 2
    t_lat = d_lat / se_lat if se_lat > 0 else np.nan
    p_lat = float(2 * stats.t.sf(abs(t_lat), df)) if np.isfinite(t_lat) else None
    u = stats.mannwhitneyu(rt_b, rt_r, alternative="two-sided")
    out["tests"] = {
        "P3 300-650 ms, buzz minus reaction": {**t_p3, "unit": "µV"},
        "P3 latency, buzz minus reaction": {"diff": float(d_lat), "se": float(se_lat),
                                            "t": float(t_lat), "df": int(df), "p": p_lat,
                                            "unit": "ms"},
        "RT, buzz minus reaction": {"diff": float(np.median(rt_b) - np.median(rt_r)),
                                    "p": float(u.pvalue), "n": [int(len(rt_b)), int(len(rt_r))],
                                    "unit": "ms"},
    }
    return out


def summary(c: dict) -> dict:
    """The JSON-safe part of compare()."""
    if not c:
        return {}
    return {"modes": c["modes"], "tests": c["tests"],
            "p3_window_ms": [int(P3_COMMON[0][0] * 1000), int(P3_COMMON[0][1] * 1000)],
            "p3_sites": "/".join(P3_COMMON[1])}


def figure_erp(c: dict, path) -> str | None:
    """The cue-locked response at four sites, both games on one axis."""
    import matplotlib.pyplot as plt
    if not c:
        return None
    ep = c["epochs"]
    fig, axes = plt.subplots(1, 4, figsize=(13, 3.4), sharey=True)
    for ax, ch in zip(axes, SITES):
        for k in ("reaction", "buzz"):
            e = ep[k]
            w = e.copy().pick([ch]).get_data()[:, 0] * 1e6
            m, se = w.mean(0), w.std(0, ddof=1) / np.sqrt(len(w))
            ms = e.times * 1000
            ax.fill_between(ms, m - se, m + se, color=COLOURS[k], alpha=0.18, lw=0)
            ax.plot(ms, m, color=COLOURS[k], lw=1.8, label=f"{LABELS[k]} (n={len(w)})")
        ax.axvline(0, color="#6b7280", lw=0.8)
        ax.axhline(0, color="#6b7280", lw=0.8)
        if ch in P3_COMMON[1]:
            ax.axvspan(300, 650, color="#9ca3af", alpha=0.15, lw=0)
        ax.set_title(ch, fontsize=11)
        ax.set_xlabel("ms after the cue")
        ax.set_xlim(-200, 800)
    axes[0].set_ylabel("µV (positive up)")
    axes[0].legend(fontsize=8, loc="lower left", frameon=False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path.name


def figure_topo(c: dict, path) -> str | None:
    """Scalp maps at the same four times for both games, one colour scale."""
    import matplotlib.pyplot as plt
    if not c:
        return None
    ev = {k: e.average().pick("eeg") for k, e in c["epochs"].items()}
    lim = max(np.abs(ev[k].copy().crop(0.05, 0.6).data).max() for k in ev) * 1e6 * 0.8
    fig, axes = plt.subplots(2, len(TOPO_TIMES) + 1, figsize=(11, 5),
                             gridspec_kw={"width_ratios": [1] * len(TOPO_TIMES) + [0.08]})
    for r, k in enumerate(("reaction", "buzz")):
        ev[k].plot_topomap(times=list(TOPO_TIMES), axes=list(axes[r]),
                           vlim=(-lim, lim), show=False, colorbar=True)
        for a, t in zip(axes[r, :-1], TOPO_TIMES):
            a.set_title(f"{t * 1000:.0f} ms", fontsize=9)
    fig.text(0.01, 0.73, "Reaction", rotation=90, fontsize=11, color=COLOURS["reaction"],
             fontweight="bold", va="center")
    fig.text(0.01, 0.28, "Buzz Hunt", rotation=90, fontsize=11, color=COLOURS["buzz"],
             fontweight="bold", va="center")
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path.name


def table_rows(s: dict) -> list[tuple[str, str, str]]:
    """The at-a-glance table: (row, Reaction, Buzz Hunt)."""
    c = s.get("compare") or {}
    m = c.get("modes") or {}
    r, b = m.get("reaction", {}), m.get("buzz", {})
    if not r or not b:
        return []
    srt = s.get("srt", {})
    bz = s.get("buzz", {})
    lr = srt.get("learning", {})
    ci = lr.get("post_minus_block8_ci") or [0, 0]

    def sp(x):
        return f"{x['spacing_s'][0]:.1f} to {x['spacing_s'][1]:.1f} s"
    rows = [
        ("Cue", "flash on screen with a tone", "buzz on one finger, nothing on screen"),
        ("Trials in the comparison", f"{r['n']} random-order flashes", f"{b['n']} localisation buzzes"),
        ("Time between cues", sp(r), sp(b)),
        ("Reaction time (median, correct)", f"{r['rt_ms']:.0f} ms", f"{b['rt_ms']:.0f} ms"),
        ("Correct", f"{r['accuracy'] * 100:.0f}%", f"{b['accuracy'] * 100:.0f}%"),
        ("First cortical response", f"{r['early']['name']}, {r['early']['latency_ms']:.0f} ms "
                                    f"({r['early']['sites']})",
         f"{b['early']['name']}, {b['early']['latency_ms']:.0f} ms ({b['early']['sites']}), "
         f"after a motor delay of about 71-80 ms"),
        ("P3, 300-650 ms at Pz/CPz", f"{r['p3_uV']:+.1f} µV", f"{b['p3_uV']:+.1f} µV"),
        ("P3 in each game's own window", f"{r['p3_own_uV']:+.1f} µV ({r['p3_own_window_ms']} ms)",
         f"{b['p3_own_uV']:+.1f} µV ({b['p3_own_window_ms']} ms)"),
        ("P3 timing (50% area)", f"{r['p3_latency_ms']:.0f} ms", f"{b['p3_latency_ms']:.0f} ms"),
        ("Learning", f"{lr.get('post_minus_block8_ms', 0):.0f} ms slower when random order returned "
                     f"(95% CI {ci[0]:.0f} to {ci[1]:.0f})", "no sequence in this game"),
    ]
    mu = (bz.get("tests") or {}).get("mu C3 after the buzz, 0.2-0.8 s")
    beta = (srt.get("band_tests") or {}).get("beta C3")
    rows.append(("Motor rhythm at C3",
                 f"beta {beta['diff']:+.1f} dB on random against learned trials" if beta else "n/a",
                 f"mu {mu['diff']:+.0f}% after the buzz" if mu else "n/a"))
    return rows
