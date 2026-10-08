"""The short report to send, Word and PDF (PDF through LibreOffice
when it is installed): the session in one table, Reaction against Buzz
Hunt, what was found and what to keep in mind. Everything else stays in
detail/."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from . import compare as CMP
from . import findings as FD

REFS = [
    "Eimer M, Goschke T, Schlaghecken F, Sturmer B (1996). Explicit and implicit learning of event sequences: "
    "evidence from event-related brain potentials. JEP: LMC 22(4):970-987.",
    "Gehring WJ, Goss B, Coles MGH, Meyer DE, Donchin E (1993). A neural system for error detection and "
    "compensation. Psychological Science 4(6):385-390.",
    "Gramfort A, et al. (2013). MEG and EEG data analysis with MNE-Python. Frontiers in Neuroscience 7:267.",
    "Jongsma MLA, et al. (2006). Tracking pattern learning with single-trial event-related potentials. "
    "Clinical Neurophysiology 117(9):1957-1973.",
    "Kappenman ES, Farrens JL, Zhang W, Stewart AX, Luck SJ (2021). ERP CORE. NeuroImage 225:117465.",
    "Lum JAG, et al. (2024). Top-down and bottom-up oscillatory dynamics regulate implicit visuomotor sequence "
    "learning. Cerebral Cortex 34(7):bhae266.",
    "Miller J, Patterson T, Ulrich R (1998). Jackknife-based method for measuring LRP onset latency "
    "differences. Psychophysiology 35(1):99-115.",
    "Pfurtscheller G, Lopes da Silva FH (1999). Event-related EEG/MEG synchronization and desynchronization. "
    "Clinical Neurophysiology 110(11):1842-1857.",
]


def comparison_lines(s: dict) -> list[str]:
    c = s.get("compare") or {}
    m, t = c.get("modes") or {}, c.get("tests") or {}
    r, b = m.get("reaction"), m.get("buzz")
    if not r or not b:
        return []
    p = FD.p_text
    p3 = t.get("P3 300-650 ms, buzz minus reaction", {})
    lat = t.get("P3 latency, buzz minus reaction", {})
    rt = t.get("RT, buzz minus reaction", {})
    out = []
    if p3:
        bigger = p3.get("p") is not None and p3["p"] < FD.ALPHA
        out.append(
            (f"The buzz drew a larger P3 than the flash: {b['p3_uV']:+.1f} against {r['p3_uV']:+.1f} µV at Pz/CPz "
             if bigger and p3["diff"] > 0 else
             f"The P3 was {b['p3_uV']:+.1f} µV to the buzz and {r['p3_uV']:+.1f} µV to the flash at Pz/CPz ")
            + f"(300-650 ms; difference {p3['diff']:+.1f} µV, 95% CI {p3['ci'][0]:+.1f} to {p3['ci'][1]:+.1f}, "
              f"p {p(p3['p'])}). In each game's own window the flash's P3 is {r['p3_own_uV']:+.1f} µV and the "
              f"buzz's {b['p3_own_uV']:+.1f} µV.")
    if lat:
        out.append(
            f"It peaked later: half its area was reached at {b['p3_latency_ms']:.0f} ms after the buzz against "
            f"{r['p3_latency_ms']:.0f} ms after the flash ({lat['diff']:+.0f} ms, jackknife t({lat['df']}) = "
            f"{lat['t']:.1f}, p {p(lat['p'])})."
            if lat.get("p") is not None and lat["p"] < FD.ALPHA else
            f"Half the P3's area came at {b['p3_latency_ms']:.0f} ms after the buzz and {r['p3_latency_ms']:.0f} ms "
            f"after the flash ({lat['diff']:+.0f} ms, p {p(lat['p'])}).")
    out.append(
        f"The first cortical response differs by sense: a visual P1 at {r['early']['latency_ms']:.0f} ms over the "
        f"occipital sites for the flash, and a negativity over the left hemisphere, opposite the buzzed hand, at "
        f"{b['early']['latency_ms']:.0f} ms for the buzz, of which about 71-80 ms is the motor starting.")
    if rt:
        out.append(f"Answers took {b['rt_ms']:.0f} ms after the buzz and {r['rt_ms']:.0f} ms after the flash "
                   f"(median of correct answers; p {p(rt['p'])}).")
    return out


def build(s: dict, figs: Path, out: Path) -> list[str]:
    from docx import Document
    from docx.shared import Cm, Pt, RGBColor
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name = "Calibri"
    st.font.size = Pt(10)
    for sec in doc.sections:
        sec.left_margin = sec.right_margin = Cm(1.8)
        sec.top_margin = sec.bottom_margin = Cm(1.5)
    srt, bz = s.get("srt", {}), s.get("buzz", {})
    fd = FD.build(s)
    who = s.get("participant") or "Participant"
    doc.add_heading(f"EEG pilot: {who}, {s.get('date_long', '')}", 0)
    doc.add_paragraph(
        f"{who}, {s.get('age')}, {s.get('dominant_hand')}-handed, on the hand device: Reaction, the lab's SRT "
        f"({srt.get('n_trials')} trials, a flash with a tone), and Buzz Hunt ({bz.get('trials')} trials, a buzz "
        f"on one finger). BioSemi ActiveTwo, 64 channels at 512 Hz; the game on its own PC sent a marker byte at "
        f"every cue and press. Analysed with MNE-Python {s['software']['mne']}.")

    doc.add_heading("Reaction against Buzz Hunt", 1)
    rows = CMP.table_rows(s)
    if rows:
        table = doc.add_table(rows=1, cols=3)
        table.style = "Light Grid Accent 1"
        head = table.rows[0].cells
        for cell, text in zip(head, ("", "Reaction", "Buzz Hunt")):
            cell.text = text
        for name, a, b in rows:
            cells = table.add_row().cells
            cells[0].text, cells[1].text, cells[2].text = name, a, b
        for row in table.rows:
            for cell in row.cells:
                for para in cell.paragraphs:
                    for run in para.runs:
                        run.font.size = Pt(9)
    for x in comparison_lines(s):
        doc.add_paragraph(x, style="List Bullet")
    f = figs / "30_compare_cue_response.png"
    if f.is_file():
        doc.add_picture(str(f), width=Cm(17.4))
        cap = doc.add_paragraph("The response to each game's cue at four sites (mean and one standard error; grey: "
                                "the P3 window). Reaction: random-order flashes only, so no learned sequence is "
                                "in either average.")
        cap.runs[0].italic = True
        cap.runs[0].font.size = Pt(8.5)
    f = figs / "31_compare_scalp_maps.png"
    if f.is_file():
        doc.add_picture(str(f), width=Cm(12.5))
        cap = doc.add_paragraph("Scalp maps at the same four times for both games, one colour scale: the flash's "
                                "early occipital response against the buzz's later left-hemisphere and parietal "
                                "responses.")
        cap.runs[0].italic = True
        cap.runs[0].font.size = Pt(8.5)

    doc.add_heading("What the session showed", 1)
    for i in fd["items"]:
        para = doc.add_paragraph(style="List Bullet")
        para.add_run(i["head"] + " ").bold = True
        para.add_run(i["short"])

    doc.add_heading("Keep in mind", 1)
    cyc = (s.get("compare") or {}).get("modes", {})
    pace = ""
    if cyc.get("reaction") and cyc.get("buzz"):
        pace = (f" (a cue every {cyc['reaction']['spacing_s'][0]:.1f} to {cyc['reaction']['spacing_s'][1]:.1f} s "
                f"against {cyc['buzz']['spacing_s'][0]:.1f} to {cyc['buzz']['spacing_s'][1]:.1f} s)")
    for x in (
        "One person, one session: each test compares this person's trials, so it shows what the setup can "
        "measure, not what holds for people in general.",
        "The two games differ in more than the sense cued: Reaction is a fast learning task and Buzz Hunt a slow "
        f"localisation task{pace}, so part of any difference is pace and task.",
        "Cue timing on the lab PC is not measured yet: the screen's delay and the motor's spin-up shift "
        "latencies." + (" This session used the game's own Reaction cards, brighter and wider apart than the "
                        "lab's script, which every build now draws by default." if s.get("srt_look") == "app"
                        else ""),
    ):
        doc.add_paragraph(x.strip(), style="List Bullet")
    para = doc.add_paragraph("Full analysis (interactive page, MNE reports, every figure and table): the detail "
                             "folder beside this report.")
    para.runs[0].font.color.rgb = RGBColor(0x5F, 0x66, 0x73)
    doc.add_heading("References", 2)
    for r in REFS:
        para = doc.add_paragraph(r)
        para.paragraph_format.space_after = Pt(0)
        para.runs[0].font.size = Pt(7.5)

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
