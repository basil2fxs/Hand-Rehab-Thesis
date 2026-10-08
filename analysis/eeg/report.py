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
    ax[0].set_ylabel("µV (microvolts), top back of head")
    ax[0].set_title(f"P3 (attention response) size, {_p(t['P3 300-650 ms, buzz minus reaction']['p'])}",
                    fontsize=10)
    v = [m[k]["p3_latency_ms"] for k in keys]
    e = [m[k]["p3_latency_se_ms"] for k in keys]
    ax[1].errorbar([0, 1], v, yerr=e, fmt="none", ecolor="#374151", capsize=4)
    ax[1].scatter([0, 1], v, color=cols, s=110, zorder=3)
    ax[1].set_xticks([0, 1], names)
    ax[1].set_xlim(-0.6, 1.6)
    ax[1].set_ylabel("ms until half the P3 is done")
    ax[1].set_title(f"P3 timing, {_p(t['P3 latency, buzz minus reaction']['p'])}", fontsize=10)
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
    ax[2].set_title(f"Reaction time, {_p(t['RT, buzz minus reaction']['p'])}", fontsize=10)
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
    ax[0].set_ylabel("median reaction time, ms")
    ax[0].set_title("Reaction time by block (random: grey, red)", fontsize=10)
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
    ax[1].set_ylabel("µV (microvolts), top centre")
    ax[1].set_title("N2 (surprise response), shaded", fontsize=10)
    ax[1].legend(fontsize=8, frameon=False, loc="lower left")
    bp = r.block_power
    x = np.arange(len(bp))
    seg = list(bp.segment)
    ax[2].plot(x, bp.beta_C3_dB, color=BLUE, lw=2, zorder=2)
    ax[2].scatter(x, bp.beta_C3_dB, zorder=3, s=40,
                  color=[RED if s in ("Practice", "Post-test") else BLUE for s in seg])
    ax[2].set_xticks(x, ["Prac" if s == "Practice" else "Post" if s == "Post-test"
                         else s.replace("Sequence ", "S") for s in seg])
    ax[2].set_ylabel("dB (power)")
    ax[2].set_title("Beta (13-30 Hz motor rhythm) at C3", fontsize=10)
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
    ax[0].set_title("Touch response, left vs right (shaded)", fontsize=10)
    ax[0].legend(fontsize=8, frameon=False, loc="upper left")
    p3 = ev.copy().pick(["Pz", "CPz"]).data.mean(0) * 1e6
    ax[1].plot(t, p3, color=PURPLE, lw=2)
    ax[1].axvspan(400, 650, color=LIGHT, alpha=0.25, lw=0)
    ax[1].set_title("P3 (attention response), shaded", fontsize=10)
    for a in ax[:2]:
        a.axhline(0, color=GREY, lw=0.6)
        a.axvline(0, color=GREY, lw=0.6)
        a.set_xlabel("ms after the buzz")
        a.set_ylabel("µV (microvolts)")
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
        ax[2].set_title("Rhythm at C3, left motor area (blue: drop)", fontsize=10)
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
        ("", "Reaction", "Buzz Hunt", "p (under .05 = probably real)"),
        ("Trials", str(r["n"]), str(b["n"]), ""),
        ("Time between cues", gap(r), gap(b), ""),
        ("Reaction time, median", f"{r['rt_ms']:.0f} ms", f"{b['rt_ms']:.0f} ms",
         _pv(t.get("RT, buzz minus reaction", {}).get("p"))),
        ("Correct", f"{r['accuracy'] * 100:.0f}%", f"{b['accuracy'] * 100:.0f}%", ""),
        ("First brain response", f"P1 (first visual response) {r['early']['latency_ms']:.0f} ms, "
                                 f"O1/Oz/O2 (back of head)",
         f"N1 (first touch response) {b['early']['latency_ms']:.0f} ms, C3/CP3/CP5 (left side)", ""),
        ("P3 (attention response), Pz/CPz (top back of head), 300-650 ms",
         f"{r['p3_uV']:+.1f} µV (microvolts)", f"{b['p3_uV']:+.1f} µV",
         _pv(t.get("P3 300-650 ms, buzz minus reaction", {}).get("p"))),
        ("P3, each game's usual window", f"{r['p3_own_uV']:+.1f} µV", f"{b['p3_own_uV']:+.1f} µV", ""),
        ("P3 timing (half-way point)", f"{r['p3_latency_ms']:.0f} ms",
         f"{b['p3_latency_ms']:.0f} ms",
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
            ("Reaction time, random after block 8", f"+{lr.get('post_minus_block8_ms', 0):.0f} ms "
             f"(likely range {ci[0]:.0f} to {ci[1]:.0f})", "")]
    if rc:
        rows.append(("Recall", f"{rc['correct']}/{rc['items']} by position, "
                               f"{rc['cyclic_correct']}/{rc['items']} as a loop", _pv(rc.get("chance_p"))))
    if n2:
        rows.append(("N2 (surprise response), FCz/Cz (top centre), random vs learned",
                     f"{n2['diff']:+.1f} µV (microvolts)",
                     f"{_pv(n2['p'])} ({_pv(adj[0])} corrected for 2 tests)"))
    if p3:
        rows.append(("P3 (attention response), Pz/CPz (top back), practice vs learned",
                     f"{p3['diff']:+.1f} µV", f"{_pv(p3['p'])} ({_pv(adj[1])} corrected)"))
    for label, key, unit in (
            ("Beta (13-30 Hz motor rhythm), C3 (left motor area), random vs learned", "beta C3",
             " dB (power)"),
            ("Theta (4-7 Hz rhythm), FCz/Cz (top centre), random vs learned", "theta FCz/Cz", " dB")):
        x = bt.get(key)
        if x:
            rows.append((label, f"{x['diff']:+.1f}{unit}", _pv(x["p"])))
    ern = (srt.get("resp_tests") or {}).get(FD.ERN_TEST)
    if ern:
        rows.append(("ERN (error signal), FCz/Cz (top centre), wrong vs correct",
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
            ("Which finger buzzed", f"{bz.get('loc_accuracy', 0) * 100:.0f}% correct, d' {bz.get('d_prime')} "
                                    f"(how well fingers were told apart), reaction time "
                                    f"{bz.get('loc_rt_ms', 0):.0f} ms", "")]
    if "P3" in bm:
        rows.append(("P3 (attention response), Pz/CPz (top back), 400-650 ms",
                     f"{bm['P3']['mean_uV']:+.1f} µV (microvolts)", ""))
    lat = tests.get(FD.TOUCH_TEST)
    if lat and "N1 contra" in bm and "N1 ipsi" in bm:
        rows.append(("N1 (first touch response), left vs right side", f"{bm['N1 contra']['mean_uV']:+.1f} vs "
                                                f"{bm['N1 ipsi']['mean_uV']:+.1f} µV", _pv(lat["p"])))
    for label, key in (("Mu (8-12 Hz motor rhythm), C3 (left motor area), after the buzz", FD.MU_TEST),
                       ("Beta (13-30 Hz motor rhythm), C3, after the press", FD.REBOUND_TEST)):
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
    return (f"Markers (event codes sent to the EEG): {s.get('markers_matched', 0):,} of "
            f"{s.get('markers_total', 0):,} arrived, timing spread {sd} ms SD (max {mx} ms).")


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

    def picture(name, cm, how=""):
        f = figs / name if name else None
        if f is not None and f.is_file():
            doc.add_picture(str(f), width=Cm(cm))
            if how:
                cap = doc.add_paragraph(how)
                cap.paragraph_format.space_after = Pt(4)
                cap.runs[0].font.size = Pt(8.5)
                cap.runs[0].font.color.rgb = RGBColor(0x5F, 0x66, 0x73)

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
    picture(names["summary"], 14.0,
            "Bars: average. Thin lines: how sure. Boxes: the middle half of answers, white line the median.")
    picture("30_compare_cue_response.png", 17.0,
            "Brain voltage over time at four spots on the head; 0 ms is the cue. Orange: Reaction. Purple: Buzz "
            "Hunt. Shading: how sure. Grey: the P3 window.")
    picture("31_compare_scalp_maps.png", 12.0,
            "The head seen from above, nose at the top, left ear on the left. Red: positive voltage. Blue: "
            "negative. Dots: electrodes. Top row Reaction, bottom row Buzz Hunt, at four times after the cue, "
            "same colour scale.")
    table(_compare_rows(s))

    srt, bz = s.get("srt", {}), s.get("buzz", {})
    h = doc.add_heading(f"Reaction ({srt.get('n_trials', 0)} trials)", 1)
    h.paragraph_format.page_break_before = True
    picture(names["srt"], 15.5,
            "Left: reaction time per block. Middle: voltage after the flash, random (red) vs learned (blue). "
            "Right: motor rhythm strength per block.")
    table(_srt_rows(s))
    doc.add_heading(f"Buzz Hunt ({bz.get('trials', 0)} trials)", 1)
    picture(names["buzz"], 15.5,
            "Left and middle: voltage after the buzz. Right: rhythm strength by frequency (up) and time "
            "(across); blue means it dropped.")
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
