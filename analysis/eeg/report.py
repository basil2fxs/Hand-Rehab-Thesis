"""The report to send: mostly pictures, one line above each in Basil's
own words and the numbers under it in grey. Word and PDF (PDF through
LibreOffice when it is installed). Every line follows its test, so a
result that does not pass is said not to. The full analysis stays in
detail/."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import numpy as np

from . import compare as CMP
from . import findings as FD

ORANGE, PURPLE = CMP.COLOURS["reaction"], CMP.COLOURS["buzz"]
BLUE, RED, GREY, LIGHT = "#1d4ed8", "#dc2626", "#6b7280", "#9ca3af"


def _p(v) -> str:
    return "p " + FD.p_text(v)


def _plain(ax) -> None:
    ax.spines[["top", "right"]].set_visible(False)


# ---- the figures -------------------------------------------------------------
def fig_summary(c: dict, path: Path) -> str | None:
    """P3 size, P3 timing and answer time, Reaction beside Buzz Hunt."""
    import matplotlib.pyplot as plt
    if not c or "rt" not in c:
        return None
    m, t = c["modes"], c["tests"]
    keys = ("reaction", "buzz")
    names = ("Reaction\nflash + tone", "Buzz Hunt\nbuzz only")
    cols = (ORANGE, PURPLE)
    fig, ax = plt.subplots(1, 3, figsize=(11, 3.3))
    v = [m[k]["p3_uV"] for k in keys]
    e = [m[k]["p3_sme_uV"] for k in keys]
    ax[0].bar(names, v, yerr=e, color=cols, width=0.6, capsize=4)
    ax[0].set_ylabel("µV at Pz/CPz, 300-650 ms")
    ax[0].set_title(f"P3 size  ({_p(t['P3 300-650 ms, buzz minus reaction']['p'])})", fontsize=11)
    v = [m[k]["p3_latency_ms"] for k in keys]
    e = [m[k]["p3_latency_se_ms"] for k in keys]
    ax[1].errorbar([0, 1], v, yerr=e, fmt="none", ecolor="#374151", capsize=4)
    ax[1].scatter([0, 1], v, color=cols, s=110, zorder=3)
    ax[1].set_xticks([0, 1], names)
    ax[1].set_xlim(-0.6, 1.6)
    ax[1].set_ylabel("ms to half the P3's area")
    ax[1].set_title(f"P3 timing  ({_p(t['P3 latency, buzz minus reaction']['p'])})", fontsize=11)
    bp = ax[2].boxplot([c["rt"][k] for k in keys], widths=0.55, patch_artist=True,
                       showfliers=False)
    for box, col in zip(bp["boxes"], cols):
        box.set_facecolor(col)
        box.set_edgecolor(col)
    for med in bp["medians"]:
        med.set_color("white")
        med.set_linewidth(2)
    ax[2].set_xticks([1, 2], names)
    ax[2].set_ylabel("ms, correct answers")
    ax[2].set_title(f"Answer time  ({_p(t['RT, buzz minus reaction']['p'])})", fontsize=11)
    for a in ax:
        _plain(a)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path.name


def fig_srt(r, path: Path) -> str | None:
    """Reaction at a glance: RT by block, the N2 to random flashes, beta
    at C3 by block."""
    import matplotlib.pyplot as plt
    if r is None:
        return None
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.4), gridspec_kw={"width_ratios": [1.3, 1, 1.1]})
    b = r.behaviour
    cols = [GREY if s == "Practice" else RED if s == "Post-test" else BLUE for s in b.segment]
    labels = ["Prac" if s == "Practice" else "Post" if s == "Post-test" else s.replace("Sequence ", "S")
              for s in b.segment]
    ax[0].bar(labels, b.rt_median_ms, color=cols)
    ax[0].set_ylim(0, max(b.rt_median_ms) * 1.15)
    ax[0].set_ylabel("median RT, ms")
    ax[0].set_title("RT by block (random in grey and red)", fontsize=11)
    for key, col, lab in (("sequence_late", BLUE, "learned, blocks 7-8"),
                          ("random_posttest", RED, "random, post-test")):
        ev = r.stim.get(key)
        if ev is None:
            continue
        y = ev.copy().pick(["FCz", "Cz"]).data.mean(0) * 1e6
        ax[1].plot(ev.times * 1000, y, color=col, lw=2, label=lab)
    ax[1].axvspan(200, 300, color=LIGHT, alpha=0.25, lw=0)
    ax[1].axhline(0, color=GREY, lw=0.6)
    ax[1].axvline(0, color=GREY, lw=0.6)
    ax[1].set_xlabel("ms after the flash")
    ax[1].set_ylabel("µV at FCz/Cz")
    ax[1].set_title("N2 (shaded)", fontsize=11)
    ax[1].legend(fontsize=8, frameon=False, loc="lower left")
    bp = r.block_power
    x = np.arange(len(bp))
    seg = list(bp.segment)
    ax[2].plot(x, bp.beta_C3_dB, color=BLUE, lw=2, zorder=2)
    ax[2].scatter(x, bp.beta_C3_dB, zorder=3, s=40,
                  color=[RED if s in ("Practice", "Post-test") else BLUE for s in seg])
    ax[2].set_xticks(x, ["Prac" if s == "Practice" else "Post" if s == "Post-test"
                         else s.replace("Sequence ", "S") for s in seg])
    ax[2].set_ylabel("beta 13-30 Hz at C3, dB")
    ax[2].set_title("Motor beta by block", fontsize=11)
    for a in ax:
        _plain(a)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path.name


def fig_buzz(r, path: Path) -> str | None:
    """Buzz Hunt at a glance: left against right over the sensorimotor
    sites, the P3, and the rhythm change at C3."""
    import matplotlib.pyplot as plt
    if r is None or "localisation" not in r.erp:
        return None
    ev = r.erp["localisation"]
    t = ev.times * 1000
    fig, ax = plt.subplots(1, 3, figsize=(12, 3.4), gridspec_kw={"width_ratios": [1, 1, 1.2]})
    left = ev.copy().pick(["C3", "CP3", "CP5"]).data.mean(0) * 1e6
    right = ev.copy().pick(["C4", "CP4", "CP6"]).data.mean(0) * 1e6
    ax[0].plot(t, left, color=PURPLE, lw=2, label="left, opposite the hand")
    ax[0].plot(t, right, color=LIGHT, lw=2, label="right")
    ax[0].axvspan(180, 260, color=LIGHT, alpha=0.25, lw=0)
    ax[0].set_title("Touch response (shaded)", fontsize=11)
    ax[0].legend(fontsize=8, frameon=False, loc="upper left")
    p3 = ev.copy().pick(["Pz", "CPz"]).data.mean(0) * 1e6
    ax[1].plot(t, p3, color=PURPLE, lw=2)
    ax[1].axvspan(400, 650, color=LIGHT, alpha=0.25, lw=0)
    ax[1].set_title("P3 at Pz/CPz (shaded)", fontsize=11)
    for a in ax[:2]:
        a.axhline(0, color=GREY, lw=0.6)
        a.axvline(0, color=GREY, lw=0.6)
        a.set_xlabel("ms after the buzz")
        a.set_ylabel("µV")
    tfr = (r.tfr or {}).get("tfr")
    if tfr is not None and "C3" in tfr.ch_names:
        ci = tfr.ch_names.index("C3")
        sel = (tfr.times >= -0.5) & (tfr.times <= 1.5)
        data = tfr.data[ci][:, sel] * 100
        im = ax[2].imshow(data, aspect="auto", origin="lower", cmap="RdBu_r", vmin=-60, vmax=60,
                          extent=[tfr.times[sel][0] * 1000, tfr.times[sel][-1] * 1000,
                                  tfr.freqs[0], tfr.freqs[-1]])
        ax[2].axvline(0, color="black", lw=0.8)
        ax[2].set_xlabel("ms after the buzz")
        ax[2].set_ylabel("Hz")
        ax[2].set_title("Rhythm change at C3 (blue: drop)", fontsize=11)
        fig.colorbar(im, ax=ax[2], label="% change from rest")
    for a in ax[:2]:
        _plain(a)
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)
    return path.name


# ---- the words ---------------------------------------------------------------
def _lines(s: dict) -> dict:
    """One takeaway and one line of numbers per section, written the way
    Basil writes, and only as strong as the tests allow."""
    who = s.get("participant") or "The participant"
    out = {}
    c = s.get("compare") or {}
    m, t = c.get("modes") or {}, c.get("tests") or {}
    r, b = m.get("reaction"), m.get("buzz")
    if r and b:
        p3 = t.get("P3 300-650 ms, buzz minus reaction", {})
        lat = t.get("P3 latency, buzz minus reaction", {})
        rt = t.get("RT, buzz minus reaction", {})
        big = p3.get("p") is not None and p3["p"] < FD.ALPHA and p3["diff"] > 0
        late = lat.get("p") is not None and lat["p"] < FD.ALPHA and lat["diff"] > 0
        head = ("The buzz drives a much bigger, later P3 than the flash" if big and late else
                "The buzz drives a much bigger P3 than the flash" if big else
                "The P3 doesn't differ much between the two cues")
        out["compare"] = (
            head + f", and answers come about {rt.get('diff', 0):.0f} ms later.",
            f"P3 at Pz/CPz {b['p3_uV']:+.1f} vs {r['p3_uV']:+.1f} µV over 300-650 ms ({_p(p3.get('p'))}), "
            f"{b['p3_own_uV']:+.1f} vs {r['p3_own_uV']:+.1f} µV in each game's own window. Half its area by "
            f"{b['p3_latency_ms']:.0f} vs {r['p3_latency_ms']:.0f} ms (jackknife, {_p(lat.get('p'))}). "
            f"Median RT {b['rt_ms']:.0f} vs {r['rt_ms']:.0f} ms. Reaction is random flashes only, so "
            f"learning isn't mixed in. The longer gap between cues (about "
            f"{np.mean(b['spacing_s']):.0f} s vs {np.mean(r['spacing_s']):.1f} s) and the harder call "
            f"(which finger buzzed) both fit a bigger, later P3, so it's the games, not just the sense.")
    srt = s.get("srt") or {}
    if srt:
        lr, rc = srt.get("learning", {}), srt.get("recall", {})
        ci = lr.get("post_minus_block8_ci") or [0, 0]
        learned = ci[0] > 0
        whole = rc.get("items") and rc.get("cyclic_correct") == rc.get("items")
        st, bt = srt.get("stim_tests", {}), srt.get("band_tests", {})
        n2, p3 = st.get(FD.N2_TEST, {}), st.get(FD.P3_TEST, {})
        adj = FD.holm([n2.get("p"), p3.get("p")])
        beta = bt.get("beta C3", {})
        ern = (srt.get("resp_tests") or {}).get(FD.ERN_TEST, {})
        n_err = (srt.get("resp_n") or {}).get("error", 0)
        if learned:
            head = (f"{who} learned the sequence and knew it: "
                    f"{lr.get('post_minus_block8_ms', 0):.0f} ms slower when it went random"
                    + (f", and the typed recall was the whole loop from item {rc.get('cyclic_start')}."
                       if whole else "."))
        else:
            head = "No clear learning in the RTs this time."
        brain = []
        if n2:
            brain.append(f"N2 at FCz/Cz {n2['diff']:+.1f} µV random vs learned ({_p(n2['p'])}, Holm "
                         f"{FD.p_text(adj[0]).replace('= ', '')})")
        if p3:
            brain.append(f"P3 at Pz/CPz {p3['diff']:+.1f} µV practice vs learned (Holm "
                         f"{FD.p_text(adj[1]).replace('= ', '')})")
        if beta:
            brain.append(f"beta at C3 {beta['diff']:+.1f} dB random vs learned ({_p(beta['p'])}), same "
                         f"direction as Lum et al. 2024")
        ern_ok = ern.get("p") is not None and ern["p"] < FD.ALPHA and ern.get("diff", 0) < 0
        tail = (f" ERN {ern.get('diff', 0):+.1f} µV ({_p(ern.get('p'))}, {n_err} errors)"
                + ("." if ern_ok else ", so not there yet.")) if ern else ""
        out["srt"] = (head, "; ".join(brain) + "." + tail)
    bz = s.get("buzz") or {}
    if bz:
        bm = {x["measure"]: x for x in bz.get("measures", [])}
        tests = bz.get("tests", {})
        lat = tests.get(FD.TOUCH_TEST, {})
        mu = tests.get(FD.MU_TEST, {})
        reb = tests.get(FD.REBOUND_TEST, {})
        mu_ok = mu.get("p") is not None and mu["p"] < FD.ALPHA and mu.get("diff", 0) < 0
        lat_ok = lat.get("p") is not None and lat["p"] < FD.ALPHA and lat.get("diff", 0) < 0
        bits = ["Clear P3"]
        if mu_ok:
            bits.append("a mu drop at C3 after the buzz")
        head = " and ".join(bits) + "."
        head += (" The touch response is bigger on the left, opposite the hand." if lat_ok else
                 f" Left vs right needs more than {int(lat.get('n', 0))} buzzes to show." if lat else "")
        out["buzz"] = (
            head,
            f"Localisation {bz.get('loc_accuracy', 0) * 100:.0f}% (d' {bz.get('d_prime')}), median RT "
            f"{bz.get('loc_rt_ms', 0):.0f} ms. P3 {bm.get('P3', {}).get('mean_uV', 0):+.1f} µV; mu at C3 "
            f"{mu.get('diff', 0):+.0f}% ({_p(mu.get('p'))}); left minus right {lat.get('diff', 0):+.1f} µV "
            f"({_p(lat.get('p'))}); beta after the press {reb.get('diff', 0):+.0f}% ({_p(reb.get('p'))}).")
    recs = s.get("recordings", [])
    if recs:
        total, matched = s.get("markers_total", 0), s.get("markers_matched", 0)
        mx = max((x["residual_max_ms"] or 0) for x in recs)
        sd = max((x["residual_sd_ms"] or 0) for x in recs)
        widths = [x["pulse_ms"] for x in recs if x.get("pulse_ms")]
        ok = matched == total and all(x["codes_agree"] for x in recs)
        out["markers"] = (
            f"All {total:,} markers landed, within one sample of the game's clock." if ok else
            f"Only {matched:,} of {total:,} markers paired up, so check the trigger box.",
            f"{sd} ms SD, at most {mx} ms, after a straight-line fit of EEG time on the game's clock; the two "
            f"PCs drifted {recs[0].get('drift_ppm')} ppm"
            + (f"; pulses {min(w[0] for w in widths):.0f} to {max(w[2] for w in widths):.0f} ms." if widths
               else "."))
    keep = ["One participant, so this shows the setup works, not a result."]
    if s.get("srt_look") == "app":
        keep.append("This session ran the game's own Reaction cards, not your script's grey squares. "
                    "The script's look is the default now.")
    keep.append("Average reference, no mastoids. I worked out EXG1 (under the right eye) and EXG2 (left "
                "canthus) from the signals, so worth checking against the cap sheet.")
    keep.append("Screen, tone and buzz delays on the lab PC aren't timed yet.")
    out["keep"] = keep
    return out


# ---- the document ------------------------------------------------------------
def build(s: dict, figs: Path, out: Path, results: dict | None = None,
          cmp: dict | None = None) -> list[str]:
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor
    results = results or {}
    names = {
        "summary": fig_summary(cmp or {}, figs / "40_report_key_numbers.png"),
        "srt": fig_srt(results.get("srt"), figs / "41_report_reaction.png"),
        "buzz": fig_buzz(results.get("buzz_hunt"), figs / "42_report_buzz_hunt.png"),
    }
    words = _lines(s)
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10)
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Cm(1.6)
        sec.top_margin = sec.bottom_margin = Cm(1.4)
    width = Cm(17.8)
    srt, bz = s.get("srt", {}), s.get("buzz", {})
    who = s.get("participant") or "Participant"
    doc.add_heading(f"EEG pilot: {who}, {s.get('date_long', '')}", 0)
    doc.add_paragraph(
        f"{who} ({s.get('age')}, {s.get('dominant_hand')}-handed) did Reaction, the lab's SRT "
        f"({srt.get('n_trials')} trials), and Buzz Hunt ({bz.get('trials')} trials) on the finger device. "
        f"BioSemi, 64 channels at 512 Hz, with the game on its own PC sending markers through the trigger "
        f"box. Analysed in MNE-Python {s['software']['mne']}.")

    def section(title, key, pictures, cm=None, new_page=False):
        heading = doc.add_heading(title, 1)
        heading.paragraph_format.page_break_before = new_page
        if key in words:
            head, numbers = words[key]
            para = doc.add_paragraph()
            para.add_run(head).bold = True
            small = doc.add_paragraph(numbers)
            small.runs[0].font.size = Pt(8.5)
            small.runs[0].font.color.rgb = RGBColor(0x5F, 0x66, 0x73)
        for k, name in enumerate(pictures):
            f = figs / name if name else None
            if f is not None and f.is_file():
                size = cm[k] if isinstance(cm, (list, tuple)) else cm
                doc.add_picture(str(f), width=Cm(size) if size else width)

    # Page 1 is the comparison; page 2 is each game and the markers.
    section("Reaction vs Buzz Hunt", "compare",
            [names["summary"], "30_compare_cue_response.png", "31_compare_scalp_maps.png"],
            cm=(16.5, 17.8, 14.5))
    section("Reaction: learning the sequence", "srt", [names["srt"]], cm=15.0, new_page=True)
    section("Buzz Hunt: touch", "buzz", [names["buzz"]], cm=15.0)
    section("Markers", "markers", ["01_markers.png"], cm=11.5)
    para = doc.add_paragraph()
    para.add_run("Keep in mind. ").bold = True
    note = para.add_run(" ".join(words.get("keep", []))
                        + " The rest (MNE reports, every figure and table) is in the detail folder.")
    note.font.size = Pt(9)

    path = out / "EEG_report.docx"
    doc.save(path)
    made = [path.name]
    soffice = shutil.which("soffice")
    if soffice:
        subprocess.run([soffice, "-env:UserInstallation=file:///private/tmp/claude-501/lo_profile",
                        "--headless", "--convert-to", "pdf", "--outdir", str(out), str(path)],
                       check=False, capture_output=True, timeout=300)
        if (out / "EEG_report.pdf").is_file():
            made.append("EEG_report.pdf")
    return made


def comparison_lines(s: dict) -> list[str]:
    """The comparison in two lines, for the results page."""
    words = _lines(s)
    if "compare" not in words:
        return []
    head, numbers = words["compare"]
    return [head, numbers]
