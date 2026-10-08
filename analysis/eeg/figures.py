"""Figures for the EEG results, one PNG each, in one style."""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import mne

from .analyses import (BUZZ_WINDOWS, COLOURS, RESP_WINDOWS, SRT_LABELS,
                       SRT_WINDOWS)

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 160, "font.size": 10,
    "axes.titlesize": 11, "axes.titleweight": "bold", "axes.labelsize": 10,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "legend.fontsize": 9,
    "font.family": ["Helvetica Neue", "Arial", "DejaVu Sans"],
})
INK = "#111827"
MUTED = "#6b7280"


def _save(fig, out: Path, name: str) -> str:
    path = out / f"{name}.png"
    fig.savefig(path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return path.name


def _site(ev: mne.Evoked, chans) -> np.ndarray:
    return ev.copy().pick(chans).data.mean(0) * 1e6


def _shade(ax, window, colour="#e5e7eb"):
    ax.axvspan(window[0] * 1000, window[1] * 1000, color=colour, alpha=0.6,
               lw=0, zorder=0)


def _zero(ax):
    ax.axvline(0, color=MUTED, lw=0.8)
    ax.axhline(0, color=MUTED, lw=0.6)


# ---- markers and data quality ----------------------------------------------------
def markers(blocks, out: Path) -> str:
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.3))
    for b, col in zip(blocks, ("#1d4ed8", "#7c3aed")):
        p = b.alignment.pairs
        axes[0].plot(p.eeg_s / 60, p.resid_ms, ".", ms=2.5, color=col,
                     label=f"{b.mode.upper()} ({len(p)} markers)")
        axes[1].hist(p.resid_ms, bins=np.linspace(-1.5, 1.5, 31), color=col,
                     alpha=0.6, label=b.mode.upper())
        axes[2].hist(b.widths_ms, bins=np.arange(5, 22, 1.0), color=col,
                     alpha=0.6, label=b.mode.upper())
    axes[0].set(xlabel="time in recording (min)", ylabel="marker minus clock fit (ms)",
                title="Every marker against the game's clock")
    axes[0].axhspan(-1000 / 512, 1000 / 512, color="#e5e7eb", lw=0, zorder=0)
    axes[0].legend(loc="upper right")
    axes[1].set(xlabel="residual (ms)", ylabel="markers", title="Timing scatter")
    axes[2].set(xlabel="pulse width on the Status channel (ms)", ylabel="markers",
                title="Pulse widths")
    axes[1].legend(); axes[2].legend()
    return _save(fig, out, "01_markers")


def quality(cleaned: dict, out: Path) -> list[str]:
    names = []
    fig, axes = plt.subplots(1, len(cleaned), figsize=(6.5 * len(cleaned), 3.4),
                             squeeze=False)
    for ax, (mode, c) in zip(axes[0], cleaned.items()):
        f0, p0 = c.psd_before; f1, p1 = c.psd_after
        ax.semilogy(f0, p0, color=MUTED, lw=1, label="before cleaning")
        ax.semilogy(f1, p1, color="#1d4ed8", lw=1.4, label="after (0.1-40 Hz, ICA)")
        ax.axvline(50, color="#dc2626", lw=0.8, ls="--")
        ax.text(51, ax.get_ylim()[1] * 0.3, "mains 50 Hz", color="#dc2626", fontsize=8)
        ax.set(xlabel="frequency (Hz)", ylabel="power (µV²/Hz)", xlim=(0.5, 110),
               title=f"{mode.upper()}: power spectrum, mean of 64 channels")
        ax.legend(loc="upper right")
    names.append(_save(fig, out, "02_quality_spectrum"))
    fig, axes = plt.subplots(1, len(cleaned), figsize=(4.2 * len(cleaned), 4),
                             squeeze=False)
    for ax, (mode, c) in zip(axes[0], cleaned.items()):
        raw = c.raw_ica_fit.copy().pick("eeg")
        sd = raw.get_data().std(1) * 1e6
        mask = np.array([ch in c.bads for ch in raw.ch_names])
        im, _ = mne.viz.plot_topomap(sd, raw.info, axes=ax, show=False, cmap="magma_r",
                                     mask=mask, mask_params=dict(marker="x", markersize=9,
                                                                 markeredgecolor="#dc2626"),
                                     contours=0)
        plt.colorbar(im, ax=ax, shrink=0.7, label="SD 1-40 Hz (µV)")
        ax.set_title(f"{mode.upper()}: channel noise before blink removal\n" +
                     (f"rebuilt: {', '.join(c.bads)}" if c.bads else "no bad channels"),
                     fontsize=10)
    names.append(_save(fig, out, "03_quality_channels"))
    for mode, c in cleaned.items():
        if not c.ica.exclude:
            continue
        figs = c.ica.plot_components(picks=c.ica.exclude, show=False)
        figs = figs if isinstance(figs, list) else [figs]
        figs[0].suptitle(f"{mode.upper()}: eye components removed by ICA "
                         f"({len(c.ica.exclude)} of {c.ica.n_components_})",
                         fontsize=11, fontweight="bold")
        names.append(_save(figs[0], out, f"04_ica_{mode}"))
    return names


# ---- SRT -------------------------------------------------------------------------
def srt_behaviour(r, out: Path) -> str:
    b = r.behaviour
    x = np.arange(len(b))
    fig, ax = plt.subplots(1, 2, figsize=(13, 3.8), gridspec_kw=dict(width_ratios=[1.5, 1]))
    cols = [COLOURS["random_practice"]] + [COLOURS["sequence_late"]] * 8 + [COLOURS["random_posttest"]]
    ax[0].bar(x, b.rt_median_ms, color=cols[:len(b)], width=0.65)
    ax[0].errorbar(x, b.rt_median_ms, yerr=b.rt_iqr_ms / 2, fmt="none", ecolor=INK, lw=0.8, capsize=2)
    ax[0].set_xticks(x, [s.replace("Sequence ", "S") for s in b.segment], fontsize=9)
    ax[0].set(ylabel="median RT, correct trials (ms)",
              title=f"Responses sped up as the sequence was learned "
                    f"(post-test minus block 8: {r.learning['post_minus_block8_ms']:.0f} ms)")
    ax[1].plot(x, b.accuracy * 100, "o-", color="#059669", label="correct")
    ax[1].plot(x, b.wrong_finger * 100, "s-", color="#dc2626", label="wrong finger")
    ax[1].plot(x, b.anticipations * 100, "^-", color="#d97706", label="pressed before the flash")
    ax[1].set_xticks(x, [s.replace("Sequence ", "S") for s in b.segment], fontsize=9)
    ax[1].set(ylabel="% of trials", ylim=(0, 100), title="Accuracy and anticipation")
    ax[1].legend(loc="center left")
    return _save(fig, out, "10_srt_behaviour")


def srt_joint(r, out: Path) -> str:
    ev = r.stim["all_correct"].copy().pick("eeg")
    fig = ev.plot_joint(times=[0.11, 0.17, 0.25, 0.38], show=False,
                        title=f"SRT: response to each flash, all correct trials (n={r.stim_n['all_correct']})",
                        ts_args=dict(gfp=True), topomap_args=dict(contours=4))
    return _save(fig, out, "11_srt_erp_joint")


def srt_conditions(r, out: Path) -> str:
    sites = [("Visual cortex, O1/Oz/O2", ["O1", "Oz", "O2"], SRT_WINDOWS["P1"][0]),
             ("Fronto-central, FCz/Cz (N2)", ["FCz", "Cz"], SRT_WINDOWS["N2"][0]),
             ("Parietal, Pz/CPz (P3)", ["Pz", "CPz"], SRT_WINDOWS["P3"][0])]
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.8), sharey=False)
    for ax, (title, ch, win) in zip(axes, sites):
        _shade(ax, win)
        for cond, label in SRT_LABELS.items():
            if cond in r.stim:
                ev = r.stim[cond]
                ax.plot(ev.times * 1000, _site(ev, ch), color=COLOURS[cond], lw=1.6,
                        label=f"{label} (n={r.stim_n[cond]})")
        _zero(ax)
        ax.set(title=title, xlabel="ms after the flash", ylabel="µV")
    axes[0].legend(loc="lower left", fontsize=8)
    return _save(fig, out, "12_srt_erp_conditions")


def srt_topos(r, out: Path) -> str:
    conds = [c for c in SRT_LABELS if c in r.stim]
    fig, axes = plt.subplots(2, len(conds) + 1, figsize=(3.0 * (len(conds) + 1), 5.6))
    for row, comp in enumerate(("N2", "P3")):
        win, _ = SRT_WINDOWS[comp]
        vals = [r.stim[c].copy().pick("eeg").crop(*win).data.mean(1) * 1e6 for c in conds]
        lim = max(abs(np.concatenate(vals)).max(), 1)
        info = r.stim[conds[0]].copy().pick("eeg").info
        for col, (c, v) in enumerate(zip(conds, vals)):
            mne.viz.plot_topomap(v, info, axes=axes[row, col], show=False, vlim=(-lim, lim),
                                 cmap="RdBu_r", contours=4)
            axes[row, col].set_title(f"{SRT_LABELS[c]}\n{comp} {int(win[0]*1000)}-{int(win[1]*1000)} ms",
                                     fontsize=8.5)
        if "random_posttest" in conds and "sequence_late" in conds:
            d = vals[conds.index("random_posttest")] - vals[conds.index("sequence_late")]
            im, _ = mne.viz.plot_topomap(d, info, axes=axes[row, -1], show=False,
                                         vlim=(-lim, lim), cmap="RdBu_r", contours=4)
            axes[row, -1].set_title(f"Random minus learned\n{comp}", fontsize=8.5, color="#dc2626")
    fig.colorbar(im, ax=axes, shrink=0.6, label="µV")
    return _save(fig, out, "13_srt_erp_topomaps")


def srt_learning_curve(r, out: Path) -> str:
    pb = r.per_block
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    ax.plot(pb.block, pb.P3_uV, "o-", color="#1d4ed8", label="P3, Pz/CPz 300-450 ms")
    ax.plot(pb.block, pb.N2_uV, "s-", color="#7c3aed", label="N2, FCz/Cz 200-300 ms")
    ax.set(xlabel="sequence block", ylabel="mean amplitude (µV)",
           title="Brain responses across the learning blocks")
    ax2 = ax.twinx()
    ax2.plot(pb.block, pb.rt_median_ms, "--", color=MUTED, label="median RT (right axis)")
    ax2.set_ylabel("RT (ms)", color=MUTED)
    ax2.spines["right"].set_visible(True)
    h1, l1 = ax.get_legend_handles_labels(); h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower left", fontsize=8)
    return _save(fig, out, "14_srt_learning_curve")


def srt_ern(r, out: Path) -> str:
    fig = plt.figure(figsize=(14, 7.6))
    gs = fig.add_gridspec(2, 4, height_ratios=[1, 1.05], hspace=0.45)
    for i, (title, ch, comp) in enumerate((("FCz/Cz: error negativity", ["FCz", "Cz"], "ERN"),
                                           ("CPz/Pz: error positivity", ["CPz", "Pz"], "Pe"))):
        ax = fig.add_subplot(gs[0, 2 * i:2 * i + 2])
        _shade(ax, RESP_WINDOWS[comp][0])
        for cond in ("correct", "error", "anticipation"):
            if cond in r.resp:
                ev = r.resp[cond]
                ax.plot(ev.times * 1000, _site(ev, ch), color=COLOURS[cond], lw=1.6,
                        label=f"{cond} (n={r.resp_n[cond]})")
        _zero(ax)
        ax.set(title=title, xlabel="ms from the force onset of the press", ylabel="µV")
        ax.legend(loc="lower left", fontsize=8)
    if "error" in r.resp and "correct" in r.resp:
        diff = mne.combine_evoked([r.resp["error"], r.resp["correct"]], weights=[1, -1]).pick("eeg")
        for j, (comp, win) in enumerate((("ERN", RESP_WINDOWS["ERN"][0]), ("Pe", RESP_WINDOWS["Pe"][0]))):
            ax = fig.add_subplot(gs[1, j])
            v = diff.copy().crop(*win).data.mean(1) * 1e6
            lim = max(abs(v).max(), 0.5)
            mne.viz.plot_topomap(v, diff.info, axes=ax, show=False, vlim=(-lim, lim),
                                 cmap="RdBu_r", contours=4)
            ax.set_title(f"Error minus correct\n{comp} {int(win[0]*1000)}-{int(win[1]*1000)} ms", fontsize=9)
        cl = r.ern_cluster
        if cl and cl["mask"].any():
            ax = fig.add_subplot(gs[1, 2])
            frac = cl["mask"].mean(0) * 100  # % of the tested window significant, per channel
            info = r.resp["error"].copy().pick("eeg").info
            im, _ = mne.viz.plot_topomap(frac, info, axes=ax, show=False, cmap="Reds",
                                         vlim=(0, max(frac.max(), 1)), contours=0)
            ax.set_title("Cluster test: share of -100 to 500 ms\nwhere error and correct differ (%)", fontsize=9)
            plt.colorbar(im, ax=ax, shrink=0.7)
            ax = fig.add_subplot(gs[1, 3]); ax.axis("off")
            lines = ["Clusters, p < .05 (trial-level,", "1000 permutations):", ""]
            for c in cl["clusters"][:4]:
                lines.append(f"p = {c['p']:.3f}: {c['t_ms'][0]:.0f} to {c['t_ms'][1]:.0f} ms,")
                lines.append(f"  {len(c['channels'])} channels")
            ax.text(0, 1, "\n".join(lines), va="top", fontsize=9, family="monospace")
    return _save(fig, out, "15_srt_error_responses")


def srt_lock(r, out: Path) -> str:
    fig, ax = plt.subplots(figsize=(7.5, 3.6))
    for name, d, col in (("locked to the force onset", r.resp, "#1d4ed8"),
                         ("locked to the 30% press point", r.resp_press, MUTED)):
        if "error" in d and "correct" in d:
            diff = mne.combine_evoked([d["error"], d["correct"]], weights=[1, -1])
            ax.plot(diff.times * 1000, _site(diff, ["FCz"]), color=col, lw=1.6, label=name)
    _zero(ax)
    ax.set(xlabel="ms from the response", ylabel="error minus correct at FCz (µV)",
           title="Error response: force-onset lock against press lock")
    ax.legend(fontsize=8)
    return _save(fig, out, "16_srt_lock_compare")


def _tfr_panel(ax, tfr, ch, title, vlim=None, cmap="RdBu_r", label="dB"):
    d = tfr.copy().pick([ch])
    data = d.data[0]
    im = ax.imshow(data, aspect="auto", origin="lower", cmap=cmap,
                   extent=[d.times[0] * 1000, d.times[-1] * 1000, d.freqs[0], d.freqs[-1]],
                   vmin=None if vlim is None else -vlim, vmax=vlim)
    ax.axvline(0, color=INK, lw=0.8)
    ax.set(title=title, xlabel="ms", ylabel="Hz")
    return im


def srt_tfr(r, out: Path) -> str | None:
    if not ("random_posttest" in r.tfr and "sequence_late" in r.tfr):
        return None
    pr = r.tfr["random_posttest"].average(); ps = r.tfr["sequence_late"].average()
    for p in (pr, ps):
        p.crop(-0.4, 0.8)
    fig, axes = plt.subplots(2, 3, figsize=(14, 7.0))
    fig.subplots_adjust(hspace=0.5)
    for row, ch in enumerate(("C3", "FCz")):
        a = 10 * np.log10(pr.copy().pick([ch]).data[0] * 1e12); b = 10 * np.log10(ps.copy().pick([ch]).data[0] * 1e12)
        lo, hi = np.percentile(np.concatenate([a, b]), [2, 98])
        for col, (x, t) in enumerate(((a, "random, post-test"), (b, "sequence, blocks 7-8"))):
            im = axes[row, col].imshow(x, aspect="auto", origin="lower", cmap="viridis", vmin=lo, vmax=hi,
                                       extent=[pr.times[0] * 1000, pr.times[-1] * 1000, pr.freqs[0], pr.freqs[-1]])
            axes[row, col].axvline(0, color="white", lw=0.8)
            axes[row, col].set(title=f"{ch}: {t}", xlabel="ms after the flash", ylabel="Hz")
        plt.colorbar(im, ax=axes[row, :2], shrink=0.8, label="power (dB re 1 µV²/Hz)")
        d = a - b
        lim = np.percentile(abs(d), 98)
        im2 = axes[row, 2].imshow(d, aspect="auto", origin="lower", cmap="RdBu_r", vmin=-lim, vmax=lim,
                                  extent=[pr.times[0] * 1000, pr.times[-1] * 1000, pr.freqs[0], pr.freqs[-1]])
        axes[row, 2].axvline(0, color=INK, lw=0.8)
        axes[row, 2].set(title=f"{ch}: random minus learned", xlabel="ms after the flash", ylabel="Hz")
        plt.colorbar(im2, ax=axes[row, 2], shrink=0.8, label="dB")
    return _save(fig, out, "17_srt_time_frequency")


def srt_block_power(r, out: Path) -> str:
    bp = r.block_power
    x = np.arange(len(bp))
    fig, ax = plt.subplots(figsize=(10, 3.8))
    for col, lab, c in (("beta_C3_dB", "beta 13-30 Hz, C3 (left motor)", "#1d4ed8"),
                        ("beta_C4_dB", "beta 13-30 Hz, C4 (right motor)", "#93c5fd"),
                        ("alpha_C3_dB", "alpha 8-12 Hz, C3", "#7c3aed"),
                        ("alpha_Pz_dB", "alpha 8-12 Hz, Pz", "#c4b5fd"),
                        ("theta_FCz_dB", "theta 4-7 Hz, FCz", "#d97706")):
        ax.plot(x, bp[col], "o-", color=c, label=lab, lw=1.5, ms=4)
    ax.axvspan(-0.4, 0.4, color="#f3f4f6", zorder=0); ax.axvspan(len(bp) - 1.4, len(bp) - 0.6, color="#fee2e2", zorder=0)
    ax.set_xticks(x, [s.replace("Sequence ", "S") for s in bp.segment])
    ax.set(ylabel="power (dB re 1 µV²/Hz)", title="Brain rhythms block by block (random blocks shaded)")
    ax.legend(loc="center left", bbox_to_anchor=(1.0, 0.5), fontsize=8)
    return _save(fig, out, "18_srt_rhythms_by_block")


def srt_beta(r, out: Path) -> str | None:
    if not r.beta:
        return None
    p = r.beta["tfr"].copy().crop(-0.6, 0.6)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    lim = np.percentile(abs(p.data), 98)
    for ax, ch, t in zip(axes, ("C3", "C4"), ("C3, left motor cortex (opposite the hand)",
                                               "C4, right motor cortex")):
        im = _tfr_panel(ax, p, ch, t, vlim=lim)
        ax.set_xlabel("ms from the force onset of a correct press")
    plt.colorbar(im, ax=axes, label="log ratio to epoch mean")
    return _save(fig, out, "19_srt_movement_beta")


# ---- Buzz Hunt --------------------------------------------------------------------
def buzz_behaviour(r, out: Path) -> str:
    t = r.trials
    loc = t[(t.stage == "loc") & (~t["catch"])]
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.6))
    fingers = ["index", "middle", "ring", "little"]
    acc = [loc[loc.finger == f].correct.mean() * 100 for f in fingers]
    rt = [loc[(loc.finger == f) & loc.correct].time_difference_ms.median() for f in fingers]
    axes[0].bar(fingers, acc, color="#7c3aed")
    axes[0].set(ylim=(0, 105), ylabel="% correct", title=f"Which finger buzzed? ({len(loc)} trials)")
    axes[1].bar(fingers, rt, color="#a78bfa")
    axes[1].set(ylabel="median RT (ms)", title="Time to press the buzzed finger")
    conf = r.summary.get("confusion", {})
    m = np.zeros((4, 4))
    for a, row in conf.items():
        for b, n in row.items():
            m[int(a), int(b)] = n
    axes[2].imshow(m, cmap="Purples")
    for i in range(4):
        for j in range(4):
            if m[i, j]:
                axes[2].text(j, i, int(m[i, j]), ha="center", va="center",
                             color="white" if m[i, j] > m.max() / 2 else INK)
    axes[2].set_xticks(range(4), fingers); axes[2].set_yticks(range(4), fingers)
    axes[2].set(xlabel="pressed", ylabel="buzzed", title="Confusions")
    return _save(fig, out, "20_buzz_behaviour")


def buzz_erp(r, out: Path, delay_ms=(71, 80)) -> str:
    loc = r.erp.get("localisation")
    fig = plt.figure(figsize=(14, 7.0))
    gs = fig.add_gridspec(2, 4, hspace=0.45)
    ax = fig.add_subplot(gs[0, :2])
    ax.axvspan(*delay_ms, color="#fde68a", alpha=0.7, lw=0, label="motor starts (bench, study laptop)")
    _shade(ax, BUZZ_WINDOWS["N1 contra"][0])
    ax.plot(loc.times * 1000, _site(loc, ["C3", "CP3", "CP5"]), color=COLOURS["contra"], lw=1.8,
            label="left hemisphere C3/CP3/CP5 (opposite the hand)")
    ax.plot(loc.times * 1000, _site(loc, ["C4", "CP4", "CP6"]), color=COLOURS["ipsi"], lw=1.8,
            label="right hemisphere C4/CP4/CP6")
    _zero(ax)
    ax.set(title=f"Touch response, localisation buzzes (n={r.erp_n['localisation']})",
           xlabel="ms after the buzz command", ylabel="µV")
    ax.legend(fontsize=8, loc="upper left")
    ax = fig.add_subplot(gs[0, 2:])
    _shade(ax, BUZZ_WINDOWS["P3"][0])
    for k, c in (("localisation", "#7c3aed"), ("gap", "#d97706"), ("span", "#059669")):
        if k in r.erp:
            ax.plot(r.erp[k].times * 1000, _site(r.erp[k], ["Pz", "CPz"]), color=c, lw=1.6,
                    label=f"{k} (n={r.erp_n[k]})")
    _zero(ax)
    ax.set(title="Pz/CPz: attention to the buzz (P3)", xlabel="ms after the buzz command", ylabel="µV")
    ax.legend(fontsize=8)
    ev = loc.copy().pick("eeg")
    for i, (tw, t) in enumerate((((0.10, 0.16), "100-160 ms"), ((0.18, 0.26), "180-260 ms"),
                                  ((0.30, 0.40), "300-400 ms"), ((0.40, 0.65), "400-650 ms"))):
        a = fig.add_subplot(gs[1, i])
        v = ev.copy().crop(*tw).data.mean(1) * 1e6
        lim = max(abs(v).max(), 1)
        mne.viz.plot_topomap(v, ev.info, axes=a, show=False, vlim=(-lim, lim), cmap="RdBu_r", contours=4)
        a.set_title(t, fontsize=9)
    return _save(fig, out, "21_buzz_erp")


def buzz_tfr(r, out: Path) -> str | None:
    if not r.tfr:
        return None
    p = r.tfr["tfr"].copy().crop(-0.6, 1.6)
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6))
    lim = np.percentile(abs(p.data), 97)
    for ax, ch, t in zip(axes, ("C3", "Cz"), ("C3, left motor cortex", "Cz, midline")):
        im = _tfr_panel(ax, p, ch, f"{t}: rhythm change after the buzz", vlim=lim)
        ax.set_xlabel("ms after the buzz command")
    plt.colorbar(im, ax=axes, label="change from pre-buzz (fraction)")
    return _save(fig, out, "22_buzz_time_frequency")


def buzz_wait(r, out: Path) -> str | None:
    if not r.pre:
        return None
    ev = r.pre["evoked"]
    fig, ax = plt.subplots(figsize=(7.5, 3.4))
    for ch, c in ((["FCz", "Cz"], "#1d4ed8"), (["Pz"], MUTED)):
        ax.plot(ev.times * 1000, _site(ev, ch), color=c, lw=1.6, label="/".join(ch))
    _zero(ax)
    ax.set(xlabel="ms from the buzz command", ylabel="µV",
           title=f"Waiting for the buzz (n={r.pre['n']}): a slow shift before it?")
    ax.legend(fontsize=8)
    return _save(fig, out, "23_buzz_waiting")


def srt_rerp(r, out: Path) -> str | None:
    if not r.rerp:
        return None
    ev, n = r.rerp["evoked"], r.rerp["n"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 3.8))
    flash = (("flash/practice", "Random, practice", COLOURS["random_practice"]),
             ("flash/seq_early", "Sequence, blocks 1-2", COLOURS["sequence_early"]),
             ("flash/seq_late", "Sequence, blocks 7-8", COLOURS["sequence_late"]),
             ("flash/posttest", "Random, post-test", COLOURS["random_posttest"]))
    for ax, (ch, title, win) in zip(axes[:2], ((["FCz", "Cz"], "Flash, FCz/Cz (N2), overlap removed", SRT_WINDOWS["N2"][0]),
                                               (["Pz", "CPz"], "Flash, Pz/CPz (P3), overlap removed", SRT_WINDOWS["P3"][0]))):
        _shade(ax, win)
        for k, lab, c in flash:
            if k in ev:
                ax.plot(ev[k].times * 1000, _site(ev[k], ch), color=c, lw=1.6, label=f"{lab} (n={n[k]})")
        _zero(ax)
        ax.set(title=title, xlabel="ms after the flash", ylabel="µV")
    axes[0].legend(fontsize=7.5, loc="lower left")
    ax = axes[2]
    _shade(ax, RESP_WINDOWS["ERN"][0])
    for k, c in (("press/correct", COLOURS["correct"]), ("press/error", COLOURS["error"]),
                 ("press/anticipation", COLOURS["anticipation"])):
        if k in ev:
            ax.plot(ev[k].times * 1000, _site(ev[k], ["FCz", "Cz"]), color=c, lw=1.6,
                    label=f"{k.split('/')[1]} (n={n[k]})")
    _zero(ax)
    ax.set(title="Press, FCz/Cz, overlap removed", xlabel="ms from the force onset", ylabel="µV")
    ax.legend(fontsize=8, loc="lower left")
    return _save(fig, out, "19_srt_overlap_corrected")


def buzz_press(r, out: Path) -> str | None:
    if not r.press:
        return None
    ev = r.press["erp"]; p = r.press["tfr"].copy().crop(-1.2, 1.8)
    fig, axes = plt.subplots(1, 3, figsize=(15, 3.8))
    for ch, c in ((["C3"], "#7c3aed"), (["Cz"], "#1d4ed8"), (["C4"], "#9ca3af")):
        axes[0].plot(ev.times * 1000, _site(ev, ch), color=c, lw=1.6, label=ch[0])
    _zero(axes[0])
    axes[0].set(title=f"Motor cortex before and after a press (n={r.press['n']})",
                xlabel="ms from the force onset", ylabel="µV")
    axes[0].legend(fontsize=8)
    lim = np.percentile(abs(p.data), 97)
    for ax, ch in zip(axes[1:], ("C3", "Cz")):
        im = _tfr_panel(ax, p, ch, f"{ch}: rhythm change around the press", vlim=lim)
        ax.set_xlabel("ms from the force onset")
    plt.colorbar(im, ax=axes[1:], label="change from 1.2-0.8 s before (fraction)")
    return _save(fig, out, "24_buzz_press_motor")
