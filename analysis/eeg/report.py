"""The internal report: the figures and the numbers, nothing else.
Word and PDF (PDF through LibreOffice when it is installed). The full
analysis stays in detail/."""
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


# ---- the numbers -------------------------------------------------------------
def _pv(v) -> str:
    """A p value on its own: < .001 or .020."""
    return FD.p_text(v).replace("= ", "") if v is not None else ""


def _date(s: dict) -> str:
    import datetime as _dt
    try:
        d = _dt.date.fromisoformat(s.get("date") or "")
    except ValueError:
        return s.get("date_long", "")
    return f"{d.day} {d.strftime('%B')}"


def _compare_rows(s: dict) -> list[tuple]:
    c = s.get("compare") or {}
    m, t = c.get("modes") or {}, c.get("tests") or {}
    r, b = m.get("reaction"), m.get("buzz")
    if not r or not b:
        return []

    def gap(x):
        return f"{x['spacing_s'][0]:.1f} to {x['spacing_s'][1]:.1f} s"
    return [
        ("", "Reaction", "Buzz Hunt", "p"),
        ("Trials", str(r["n"]), str(b["n"]), ""),
        ("Time between cues", gap(r), gap(b), ""),
        ("RT, median", f"{r['rt_ms']:.0f} ms", f"{b['rt_ms']:.0f} ms",
         _pv(t.get("RT, buzz minus reaction", {}).get("p"))),
        ("Correct", f"{r['accuracy'] * 100:.0f}%", f"{b['accuracy'] * 100:.0f}%", ""),
        ("First peak", f"P1 {r['early']['latency_ms']:.0f} ms, O1/Oz/O2",
         f"N1 {b['early']['latency_ms']:.0f} ms, C3/CP3/CP5", ""),
        ("P3, Pz/CPz 300-650 ms", f"{r['p3_uV']:+.1f} µV", f"{b['p3_uV']:+.1f} µV",
         _pv(t.get("P3 300-650 ms, buzz minus reaction", {}).get("p"))),
        ("P3, own window", f"{r['p3_own_uV']:+.1f} µV", f"{b['p3_own_uV']:+.1f} µV", ""),
        ("P3, half-area latency", f"{r['p3_latency_ms']:.0f} ms", f"{b['p3_latency_ms']:.0f} ms",
         _pv(t.get("P3 latency, buzz minus reaction", {}).get("p"))),
    ]


def _srt_rows(s: dict) -> list[tuple]:
    srt = s.get("srt") or {}
    if not srt:
        return []
    lr, rc = srt.get("learning", {}), srt.get("recall", {})
    ci = lr.get("post_minus_block8_ci") or [0, 0]
    st, bt = srt.get("stim_tests", {}), srt.get("band_tests", {})
    n2, p3 = st.get(FD.N2_TEST, {}), st.get(FD.P3_TEST, {})
    adj = FD.holm([n2.get("p"), p3.get("p")])
    rows = [("", "Result", "p"),
            ("RT, random after block 8", f"+{lr.get('post_minus_block8_ms', 0):.0f} ms "
             f"(95% CI {ci[0]:.0f} to {ci[1]:.0f})", "")]
    if rc:
        rows.append(("Recall", f"{rc['correct']}/{rc['items']} by position, "
                               f"{rc['cyclic_correct']}/{rc['items']} as a loop", _pv(rc.get("chance_p"))))
    if n2:
        rows.append(("N2, FCz/Cz, random vs learned", f"{n2['diff']:+.1f} µV",
                     f"{_pv(n2['p'])} (Holm {_pv(adj[0])})"))
    if p3:
        rows.append(("P3, Pz/CPz, practice vs learned", f"{p3['diff']:+.1f} µV",
                     f"{_pv(p3['p'])} (Holm {_pv(adj[1])})"))
    for label, key in (("Beta, C3, random vs learned", "beta C3"),
                       ("Theta, FCz/Cz, random vs learned", "theta FCz/Cz")):
        x = bt.get(key)
        if x:
            rows.append((label, f"{x['diff']:+.1f} dB", _pv(x["p"])))
    ern = (srt.get("resp_tests") or {}).get(FD.ERN_TEST)
    if ern:
        rows.append(("ERN, FCz/Cz, wrong vs correct",
                     f"{ern['diff']:+.1f} µV, {(srt.get('resp_n') or {}).get('error', 0)} errors",
                     _pv(ern["p"])))
    return rows


def _buzz_rows(s: dict) -> list[tuple]:
    bz = s.get("buzz") or {}
    if not bz:
        return []
    bm = {x["measure"]: x for x in bz.get("measures", [])}
    tests = bz.get("tests", {})
    rows = [("", "Result", "p"),
            ("Localisation", f"{bz.get('loc_accuracy', 0) * 100:.0f}% correct, d' {bz.get('d_prime')}, "
                             f"RT {bz.get('loc_rt_ms', 0):.0f} ms", "")]
    if "P3" in bm:
        rows.append(("P3, Pz/CPz 400-650 ms", f"{bm['P3']['mean_uV']:+.1f} µV", ""))
    lat = tests.get(FD.TOUCH_TEST)
    if lat and "N1 contra" in bm and "N1 ipsi" in bm:
        rows.append(("Touch N1, left vs right", f"{bm['N1 contra']['mean_uV']:+.1f} vs "
                                                f"{bm['N1 ipsi']['mean_uV']:+.1f} µV", _pv(lat["p"])))
    for label, key in (("Mu, C3, after the buzz", FD.MU_TEST),
                       ("Beta, C3, after the press", FD.REBOUND_TEST)):
        x = tests.get(key)
        if x:
            rows.append((label, f"{x['diff']:+.0f}%", _pv(x["p"])))
    return rows


def _markers(s: dict) -> str:
    recs = s.get("recordings", [])
    if not recs:
        return ""
    mx = max((x["residual_max_ms"] or 0) for x in recs)
    sd = max((x["residual_sd_ms"] or 0) for x in recs)
    return (f"Markers: {s.get('markers_matched', 0):,} of {s.get('markers_total', 0):,}, "
            f"{sd} ms SD about the fitted clock (max {mx} ms).")


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
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(9.5)
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Cm(1.6)
        sec.top_margin = sec.bottom_margin = Cm(1.4)
    doc.add_heading(f"{s.get('participant') or 'Participant'}, {_date(s)}", 0)

    def picture(name, cm):
        f = figs / name if name else None
        if f is not None and f.is_file():
            doc.add_picture(str(f), width=Cm(cm))

    def table(rows):
        if not rows:
            return
        tb = doc.add_table(rows=0, cols=len(rows[0]))
        tb.style = "Light List Accent 1"
        for k, row in enumerate(rows):
            cells = tb.add_row().cells
            for cell, text in zip(cells, row):
                cell.text = text
                for para in cell.paragraphs:
                    para.paragraph_format.space_after = Pt(0)
                    for run in para.runs:
                        run.font.size = Pt(9)
                        run.bold = k == 0
        doc.add_paragraph().paragraph_format.space_after = Pt(0)

    doc.add_heading("Reaction vs Buzz Hunt", 1)
    picture(names["summary"], 16.0)
    picture("30_compare_cue_response.png", 17.8)
    picture("31_compare_scalp_maps.png", 13.5)
    table(_compare_rows(s))

    srt, bz = s.get("srt", {}), s.get("buzz", {})
    h = doc.add_heading(f"Reaction ({srt.get('n_trials', 0)} trials)", 1)
    h.paragraph_format.page_break_before = True
    picture(names["srt"], 15.5)
    table(_srt_rows(s))
    doc.add_heading(f"Buzz Hunt ({bz.get('trials', 0)} trials)", 1)
    picture(names["buzz"], 15.5)
    table(_buzz_rows(s))
    line = _markers(s)
    if line:
        para = doc.add_paragraph(line)
        para.runs[0].font.color.rgb = RGBColor(0x5F, 0x66, 0x73)

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
    """The comparison as one line of numbers, for the results page."""
    rows = _compare_rows(s)
    if not rows:
        return []
    keep = {r[0]: r for r in rows}
    parts = []
    for name in ("P3, Pz/CPz 300-650 ms", "P3, half-area latency", "RT, median"):
        x = keep.get(name)
        if x:
            parts.append(f"{name}: {x[1]} vs {x[2]} (p {x[3]})")
    return ["Reaction vs Buzz Hunt. " + "; ".join(parts) + "."]
