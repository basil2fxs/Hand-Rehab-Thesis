"""The results page: one self-contained HTML file with the findings, the
figures, the tables and an electrode explorer.

The page carries a person's EEG, so it is written to the results folder
and opened locally; nothing here uploads it anywhere.
"""
from __future__ import annotations

import base64
import html
import json
import re
from pathlib import Path

import numpy as np

import mne

from . import findings as FD
from . import pipeline as P
from .analyses import COLOURS, SRT_LABELS

DECIM = 4   # 512 Hz evoked to 128 Hz for the explorer (data are low-passed at 40 Hz)


def _uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def _cond(ev: mne.Evoked, name: str, colour: str, n: int) -> dict:
    e = ev.copy().pick("eeg")
    data = np.round(e.data[:, ::DECIM] * 1e6, 2)
    return {"name": name, "colour": colour, "n": int(n),
            "data": data.tolist(), "ch": e.ch_names}


def explorer(results) -> dict:
    sets = []
    chans = None
    if "srt" in results:
        r = results["srt"]
        conds = [_cond(r.stim[k], SRT_LABELS[k], COLOURS[k], r.stim_n[k])
                 for k in SRT_LABELS if k in r.stim]
        times = r.stim["all_correct"].times[::DECIM]
        sets.append({"id": "srt_flash", "title": "SRT: response to the flash",
                     "x": "ms after the flash", "times": np.round(times * 1000, 1).tolist(),
                     "windows": [[200, 300, "N2"], [300, 450, "P3"]], "conds": conds})
        if r.rerp:
            ev, n = r.rerp["evoked"], r.rerp["n"]
            names = {"flash/practice": ("random_practice", "Random, practice"),
                     "flash/seq_early": ("sequence_early", "Sequence, blocks 1-2"),
                     "flash/seq_late": ("sequence_late", "Sequence, blocks 7-8"),
                     "flash/posttest": ("random_posttest", "Random, post-test")}
            conds = [_cond(ev[k], lab, COLOURS[c], n[k]) for k, (c, lab) in names.items() if k in ev]
            if conds:
                times = ev[next(k for k in names if k in ev)].times[::DECIM]
                sets.append({"id": "srt_flash_rerp", "title": "SRT: flash, overlap removed (rERP)",
                             "x": "ms after the flash", "times": np.round(times * 1000, 1).tolist(),
                             "windows": [[200, 300, "N2"], [300, 450, "P3"]], "conds": conds})
        conds = [_cond(r.resp[k], k, COLOURS[k], r.resp_n[k]) for k in ("correct", "error", "anticipation") if k in r.resp]
        times = r.resp["correct"].times[::DECIM]
        sets.append({"id": "srt_press", "title": "SRT: response-locked, force onset",
                     "x": "ms from the force onset", "times": np.round(times * 1000, 1).tolist(),
                     "windows": [[0, 100, "ERN"], [200, 400, "Pe"]], "conds": conds})
        if r.rerp:
            ev, n = r.rerp["evoked"], r.rerp["n"]
            conds = [_cond(ev[f"press/{k}"], k, COLOURS[k], n[f"press/{k}"])
                     for k in ("correct", "error", "anticipation") if f"press/{k}" in ev]
            if conds:
                times = ev["press/correct"].times[::DECIM]
                sets.append({"id": "srt_press_rerp", "title": "SRT: response-locked, overlap removed (rERP)",
                             "x": "ms from the force onset", "times": np.round(times * 1000, 1).tolist(),
                             "windows": [[0, 100, "ERN"], [200, 400, "Pe"]], "conds": conds})
        chans = r.stim["all_correct"].copy().pick("eeg")
    if "buzz_hunt" in results:
        r = results["buzz_hunt"]
        col = {"localisation": "#7c3aed", "gap": "#d97706", "span": "#059669", "all_buzzes": "#111827"}
        conds = [_cond(r.erp[k], k.replace("_", " "), col[k], r.erp_n[k]) for k in col if k in r.erp]
        times = r.erp["localisation"].times[::DECIM]
        sets.append({"id": "buzz", "title": "Buzz Hunt: response to the buzz",
                     "x": "ms after the buzz command", "times": np.round(times * 1000, 1).tolist(),
                     "windows": [[180, 260, "N1"], [400, 650, "P3"]], "conds": conds})
        if r.press:
            ev = r.press["erp"]
            sets.append({"id": "buzz_press", "title": "Buzz Hunt: around the answering press",
                         "x": "ms from the force onset", "times": np.round(ev.times[::DECIM] * 1000, 1).tolist(),
                         "windows": [], "conds": [_cond(ev, "correct localisation presses", "#7c3aed", r.press["n"])]})
        if chans is None:
            chans = r.erp["localisation"].copy().pick("eeg")
    lay = mne.channels.make_eeg_layout(chans.info)
    pos = lay.pos[:, :2] + lay.pos[:, 2:] / 2
    pos = (pos - pos.mean(0)) / (np.abs(pos - pos.mean(0)).max() * 1.12)
    channels = [{"name": n, "x": round(float(x), 4), "y": round(float(y), 4)}
                for n, (x, y) in zip(lay.names, pos)]
    return {"sets": sets, "channels": channels}


def _table(rows, cols, fmt=None) -> str:
    fmt = fmt or {}
    head = "".join(f"<th>{html.escape(c[1])}</th>" for c in cols)
    body = []
    for r in rows:
        cells = []
        for key, _ in cols:
            v = r.get(key) if isinstance(r, dict) else getattr(r, key)
            f = fmt.get(key)
            if v is None or (isinstance(v, float) and not np.isfinite(v)):
                s = "n/a"
            elif f:
                s = f(v)
            else:
                s = str(v)
            cells.append(f"<td>{html.escape(s)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="tw"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


def _fig(figs: Path, name: str | None, caption: str) -> str:
    if not name:
        return ""
    p = figs / name
    if not p.is_file():
        return ""
    return (f'<figure><img loading="lazy" src="{_uri(p)}" alt="{html.escape(caption)}">'
            f'<figcaption>{caption}</figcaption></figure>')


def _p(v, nd=3):
    if v is None:
        return "n/a"
    return "< .001" if v < 0.001 else f"= {v:.{nd}f}".replace("0.", ".", 1)


CSS = r"""
:root{--bg:#f6f6f3;--card:#ffffff;--ink:#141821;--muted:#5f6673;--line:#e4e4df;--accent:#1d4ed8;
--good:#047857;--bad:#b91c1c;--warn:#b45309;--chip:#eef2ff;--shadow:0 1px 2px rgba(0,0,0,.05),0 4px 16px rgba(0,0,0,.04)}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0e1116;--card:#161a22;--ink:#e8eaee;--muted:#9aa3b2;--line:#262c37;
--accent:#7aa2ff;--good:#34d399;--bad:#f87171;--warn:#fbbf24;--chip:#1e2533;--shadow:none}}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Helvetica,Arial,sans-serif}
header{padding:40px 24px 28px;max-width:1240px;margin:0 auto}
header .eyebrow{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);font-weight:600}
header h1{font-size:34px;line-height:1.15;margin:8px 0 10px;letter-spacing:-.01em}
header p{color:var(--muted);margin:0;max-width:820px}
.layout{display:grid;grid-template-columns:220px minmax(0,1fr);gap:28px;max-width:1240px;margin:0 auto;padding:0 24px 80px}
nav{position:sticky;top:16px;align-self:start;font-size:13.5px}
nav a{display:block;color:var(--muted);text-decoration:none;padding:6px 10px;border-radius:8px;border-left:2px solid transparent}
nav a:hover{color:var(--ink);background:var(--card)}
nav a.on{color:var(--accent);border-left-color:var(--accent);background:var(--card);font-weight:600}
main{min-width:0}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:26px 28px;margin-bottom:22px;box-shadow:var(--shadow)}
section h2{font-size:21px;margin:0 0 4px;letter-spacing:-.005em}
section h3{font-size:15.5px;margin:22px 0 6px}
.lead{color:var(--muted);margin:0 0 16px}
.cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:6px 0 18px}
.card{border:1px solid var(--line);border-radius:12px;padding:14px 16px;background:var(--bg)}
.card .k{font-size:12px;color:var(--muted);text-transform:uppercase;letter-spacing:.06em;font-weight:600}
.card .v{font-size:26px;font-weight:700;margin:4px 0 2px;letter-spacing:-.01em}
.card .s{font-size:12.5px;color:var(--muted);line-height:1.4}
.good{color:var(--good)}.bad{color:var(--bad)}.warn{color:var(--warn)}
.plain{background:var(--chip);border-radius:10px;padding:12px 16px;margin:12px 0;font-size:14.5px}
.plain b{color:var(--accent)}
.caveat{border-left:3px solid var(--warn);padding:6px 14px;margin:12px 0;color:var(--muted);font-size:14px}
figure{margin:16px 0}
figure img{width:100%;height:auto;display:block;border-radius:10px;background:#fff;border:1px solid var(--line);cursor:zoom-in}
figcaption{font-size:13px;color:var(--muted);margin-top:8px}
.tw{overflow-x:auto;margin:10px 0}
table{border-collapse:collapse;width:100%;font-size:13.5px}
th,td{text-align:left;padding:7px 10px;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:12.5px;text-transform:uppercase;letter-spacing:.04em}
ul.find{padding-left:18px;margin:8px 0}ul.find li{margin:6px 0}
.lb{position:fixed;inset:0;background:rgba(10,12,16,.86);display:none;align-items:center;justify-content:center;z-index:50;padding:24px;cursor:zoom-out}
.lb img{max-width:96vw;max-height:92vh;background:#fff;border-radius:10px}
.lb.on{display:flex}
.ex{display:grid;grid-template-columns:300px minmax(0,1fr);gap:20px;align-items:start}
.ex svg{width:100%;height:auto}
.ex .dot{cursor:pointer}
.ex .ctl{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 10px}
.ex select{font:inherit;padding:6px 10px;border-radius:8px;border:1px solid var(--line);background:var(--bg);color:var(--ink)}
.chip{display:inline-flex;align-items:center;gap:6px;font-size:12.5px;padding:4px 10px;border-radius:999px;border:1px solid var(--line);background:var(--bg);cursor:pointer;user-select:none}
.chip i{width:10px;height:10px;border-radius:50%;display:inline-block}
.chip.off{opacity:.38}
canvas{width:100%;height:380px;display:block;background:var(--bg);border-radius:10px;border:1px solid var(--line)}
.hint{font-size:12.5px;color:var(--muted)}
.refs li{margin:5px 0;font-size:13.5px}
code{font-size:12.5px;background:var(--chip);padding:1px 5px;border-radius:5px}
footer{max-width:1240px;margin:0 auto;padding:0 24px 40px;color:var(--muted);font-size:12.5px}
@media (max-width:900px){.layout{grid-template-columns:1fr}nav{position:static;display:flex;flex-wrap:wrap;gap:4px}
nav a{border-left:none}.ex{grid-template-columns:1fr}section{padding:20px 16px}header{padding:28px 16px 18px}.layout{padding:0 16px 60px}}
@media print{nav,.lb,.ex .ctl,canvas,.hint{display:none}body{background:#fff}section{box-shadow:none;break-inside:avoid-page}
.layout{display:block}figure img{border:none}}
"""

JS = r"""
const D=JSON.parse(document.getElementById('d').textContent);
const lb=document.querySelector('.lb'),lbi=lb.querySelector('img');
document.querySelectorAll('figure img').forEach(i=>i.onclick=()=>{lbi.src=i.src;lb.classList.add('on')});
lb.onclick=()=>lb.classList.remove('on');
document.addEventListener('keydown',e=>{if(e.key==='Escape')lb.classList.remove('on')});
const links=[...document.querySelectorAll('nav a')];
const io=new IntersectionObserver(es=>{es.forEach(e=>{if(e.isIntersecting){links.forEach(a=>a.classList.toggle('on',a.getAttribute('href')==='#'+e.target.id))}})},{rootMargin:'-30% 0px -60% 0px'});
document.querySelectorAll('section[id]').forEach(s=>io.observe(s));
// ---- electrode explorer
const sel=document.getElementById('set'),svg=document.getElementById('head'),cv=document.getElementById('cv'),chips=document.getElementById('chips'),chName=document.getElementById('chname');
let cur=D.sets[0],ch='FCz',hidden=new Set();
D.sets.forEach((s,i)=>{const o=document.createElement('option');o.value=i;o.textContent=s.title;sel.appendChild(o)});
sel.onchange=()=>{cur=D.sets[+sel.value];hidden.clear();chipsDraw();draw()};
function headDraw(){const W=300,c=150,R=128;let h=`<circle cx="${c}" cy="${c+8}" r="${R}" fill="none" stroke="currentColor" stroke-opacity=".35" stroke-width="1.5"/>`+
`<path d="M ${c-12} ${c+8-R+3} L ${c} ${c+8-R-14} L ${c+12} ${c+8-R+3}" fill="none" stroke="currentColor" stroke-opacity=".35" stroke-width="1.5"/>`;
D.channels.forEach(p=>{const x=c+p.x*R,y=c+8-p.y*R,on=p.name===ch;
h+=`<g class="dot" data-n="${p.name}"><circle cx="${x}" cy="${y}" r="${on?9:6.5}" fill="${on?'var(--accent)':'var(--card)'}" stroke="${on?'var(--accent)':'currentColor'}" stroke-opacity="${on?1:.45}"/>`+
`<text x="${x}" y="${y-10}" text-anchor="middle" font-size="8.5" fill="currentColor" fill-opacity="${on?1:.55}">${p.name}</text></g>`});
svg.innerHTML=h;svg.querySelectorAll('.dot').forEach(g=>g.onclick=()=>{ch=g.dataset.n;headDraw();draw()})}
function chipsDraw(){chips.innerHTML='';cur.conds.forEach((c,i)=>{const b=document.createElement('span');b.className='chip'+(hidden.has(i)?' off':'');
b.innerHTML=`<i style="background:${c.colour}"></i>${c.name} (n=${c.n})`;b.onclick=()=>{hidden.has(i)?hidden.delete(i):hidden.add(i);chipsDraw();draw()};chips.appendChild(b)})}
let hoverX=null;
function draw(){chName.textContent=ch;const dpr=window.devicePixelRatio||1,w=cv.clientWidth,h=cv.clientHeight;cv.width=w*dpr;cv.height=h*dpr;
const g=cv.getContext('2d');g.setTransform(dpr,0,0,dpr,0,0);g.clearRect(0,0,w,h);
const cs=getComputedStyle(document.documentElement),ink=cs.getPropertyValue('--ink').trim(),mut=cs.getPropertyValue('--muted').trim(),ln=cs.getPropertyValue('--line').trim();
const T=cur.times,L=54,Rm=14,Tp=16,B=40,pw=w-L-Rm,ph=h-Tp-B;
const series=cur.conds.map((c,i)=>({c,i,y:c.data[c.ch.indexOf(ch)]})).filter(s=>s.y&&!hidden.has(s.i));
let lo=Infinity,hi=-Infinity;series.forEach(s=>s.y.forEach(v=>{lo=Math.min(lo,v);hi=Math.max(hi,v)}));
if(!isFinite(lo)){lo=-1;hi=1}const pad=(hi-lo)*.1||1;lo-=pad;hi+=pad;
const X=t=>L+(t-T[0])/(T[T.length-1]-T[0])*pw,Y=v=>Tp+(hi-v)/(hi-lo)*ph;
g.font='12px -apple-system,Segoe UI,Helvetica,Arial,sans-serif';
cur.windows.forEach(([a,b,n])=>{g.fillStyle=ln;g.globalAlpha=.6;g.fillRect(X(a),Tp,X(b)-X(a),ph);g.globalAlpha=1;g.fillStyle=mut;g.fillText(n,X(a)+4,Tp+14)});
g.strokeStyle=mut;g.lineWidth=1;g.globalAlpha=.6;g.beginPath();g.moveTo(L,Y(0));g.lineTo(L+pw,Y(0));
if(T[0]<0&&T[T.length-1]>0){g.moveTo(X(0),Tp);g.lineTo(X(0),Tp+ph)}g.stroke();g.globalAlpha=1;
g.fillStyle=mut;g.textAlign='right';const step=niceStep(hi-lo);for(let v=Math.ceil(lo/step)*step;v<=hi;v+=step){g.fillText(v.toFixed(step<1?1:0),L-8,Y(v)+4)}
g.textAlign='center';const ts=niceStep(T[T.length-1]-T[0])*1;for(let t=Math.ceil(T[0]/ts)*ts;t<=T[T.length-1];t+=ts){g.fillText(Math.round(t),X(t),h-B+18)}
g.fillText(cur.x,L+pw/2,h-6);g.save();g.translate(14,Tp+ph/2);g.rotate(-Math.PI/2);g.fillText('microvolts at '+ch,0,0);g.restore();
series.forEach(s=>{g.strokeStyle=s.c.colour;g.lineWidth=2;g.beginPath();s.y.forEach((v,k)=>{k?g.lineTo(X(T[k]),Y(v)):g.moveTo(X(T[k]),Y(v))});g.stroke()});
if(hoverX!==null){const t=T[0]+(hoverX-L)/pw*(T[T.length-1]-T[0]);let k=0,best=1e9;T.forEach((tt,j)=>{const d=Math.abs(tt-t);if(d<best){best=d;k=j}});
g.strokeStyle=ink;g.globalAlpha=.4;g.beginPath();g.moveTo(X(T[k]),Tp);g.lineTo(X(T[k]),Tp+ph);g.stroke();g.globalAlpha=1;
let ty=Tp+8;g.textAlign='left';const bx=Math.min(X(T[k])+10,w-210);g.fillStyle=ink;g.fillText(Math.round(T[k])+' ms',bx,ty+8);
series.forEach(s=>{ty+=17;g.fillStyle=s.c.colour;g.fillText(s.c.name+': '+s.y[k].toFixed(2)+' µV',bx,ty+8)})}}
function niceStep(r){const raw=r/6,p=Math.pow(10,Math.floor(Math.log10(raw))),m=raw/p;return (m<1.5?1:m<3?2:m<7?5:10)*p}
cv.onmousemove=e=>{const b=cv.getBoundingClientRect();hoverX=e.clientX-b.left;draw()};cv.onmouseleave=()=>{hoverX=null;draw()};
window.addEventListener('resize',draw);
const quick=document.getElementById('quick');['FCz','Cz','Pz','Oz','C3','C4','CP3','Fz'].forEach(n=>{const b=document.createElement('span');b.className='chip';b.textContent=n;b.onclick=()=>{ch=n;headDraw();draw()};quick.appendChild(b)});
headDraw();chipsDraw();draw();
"""


def page(s: dict, names: dict, figs: Path, data: dict, methods: list[str],
         references: list[str], limitations: list[str], files: list[tuple[str, str]]) -> str:
    srt = s.get("srt", {}); bz = s.get("buzz", {})
    recs = s["recordings"]
    rc = srt.get("recall", {})
    fd = FD.build(s)
    notes = fd["notes"]
    esc = html.escape

    cards = '<div class="cards">' + "".join(
        f'<div class="card"><div class="k">{esc(c["k"])}</div><div class="v {c["state"]}">{esc(c["v"])}</div>'
        f'<div class="s">{esc(c["s"])}</div></div>' for c in fd["cards"]) + "</div>"
    findings = '<ul class="find">' + "".join(
        f'<li><b>{esc(i["head"])}</b> {esc(i["text"])}</li>' for i in fd["items"]) + "</ul>"

    widths = [r["pulse_ms"] for r in recs if r.get("pulse_ms") and None not in r["pulse_ms"]]
    lost = not (s["markers_matched"] == s["markers_total"] and all(r["codes_agree"] for r in recs))
    pulse_txt = ((f"The trigger box held each byte {min(w[0] for w in widths):g} to {max(w[2] for w in widths):g} ms"
                  + (", long enough for ActiView to see every one, and no marker was lost, doubled or reordered."
                     if not lost else ", but some markers did not pair with the game's log; see the table."))
                 if widths else "")

    beh = srt.get("behaviour", [])
    prac = next((r["n"] for r in beh if r["segment"] == "Practice"), None)
    seqs = [r for r in beh if r["segment"].startswith("Sequence")]
    post = next((r["n"] for r in beh if r["segment"] == "Post-test"), None)
    srt_lead = (f"Practice ({prac} random flashes), {len(seqs)} learning blocks of a repeating "
                f"{rc.get('items', '?')}-item sequence ({seqs[0]['n'] if seqs else '?'} each"
                + (f", {s['srt_isi_ms']} ms between a press and the next flash" if s.get("srt_isi_ms") else "")
                + f") and a {post}-flash random post-test.")
    cyc = bz.get("cycle_s") or [None, None]
    buzz_lead = ("Localisation buzzes: one "
                 + (f"{bz['pulse_ms']} ms " if bz.get("pulse_ms") else "")
                 + "vibration on one finger"
                 + (f", {cyc[0]:g} to {cyc[1]:g} s apart (10th to 90th percentile)" if cyc[0] else "")
                 + ", so each response is clear of the next.")
    unc = sorted({x for r in recs for x in r.get("unconnected", [])},
                 key=lambda c: int(re.sub(r"\D", "", c) or 0))
    nums = [int(re.sub(r"\D", "", c) or 0) for c in unc]
    unc_txt = (f"{unc[0]} to {unc[-1]}" if len(unc) > 2 and nums == list(range(nums[0], nums[-1] + 1))
               else ", ".join(unc))
    exg = (f"{P.EOG_BELOW} is read as below the right eye and {P.EOG_CANTHUS} as the left outer eye corner "
           "(set in pipeline.py from the first session's signals; check the lab sheet)"
           + (f"; {unc_txt} read a saturated value, so were not plugged in, and were left out" if unc else "") + ".")

    def tests_rows(d):
        out = []
        for k, v in d.items():
            out.append({"test": k.replace("_", " "), "diff": v.get("diff"), "ci": v.get("ci"),
                        "d": v.get("d"), "p": v.get("p"), "n": v.get("n")})
        return out

    fmt_t = {"diff": lambda v: f"{v:+.2f}", "ci": lambda v: f"{v[0]:+.2f} to {v[1]:+.2f}" if v else "n/a",
             "d": lambda v: f"{v:+.2f}", "p": lambda v: ("< .001" if v < .001 else f"{v:.3f}"),
             "n": lambda v: " vs ".join(str(x) for x in v) if isinstance(v, list) else str(v)}
    cols_t = [("test", "comparison"), ("diff", "difference"), ("ci", "95% CI"), ("d", "Cohen's d"), ("p", "p (permutation)"), ("n", "trials")]
    meas_cols = [("condition", "condition"), ("measure", "measure"), ("window_ms", "window (ms)"), ("sites", "sites"),
                 ("n", "trials"), ("mean_uV", "mean (µV)"), ("sme_uV", "SME (µV)"), ("split_half", "split-half r")]
    fmt_m = {"mean_uV": lambda v: f"{v:+.2f}", "sme_uV": lambda v: f"{v:.2f}", "split_half": lambda v: f"{v:.2f}",
             "condition": lambda v: SRT_LABELS.get(v, v.replace("_", " "))}
    rec_cols = [("mode", "game"), ("file", "recording"), ("minutes", "minutes"), ("markers_eeg", "markers recorded"),
                ("markers_game", "markers sent"), ("matched", "matched"), ("residual_sd_ms", "scatter SD (ms)"),
                ("residual_max_ms", "max (ms)"), ("drift_ppm", "drift (ppm)"), ("port", "trigger port")]
    q_rows = [{"mode": r["mode"], "bads": ", ".join(r["bads"]) or "none",
               "ica": f"{len(r['ica_removed'])} of {r['ica_components']}",
               "blinks": r["blinks_per_min"], "unc": ", ".join(r["unconnected"])} for r in recs]
    beh_cols = [("segment", "block"), ("n", "trials"), ("rt_median_ms", "median RT (ms)"), ("accuracy", "correct"),
                ("wrong_finger", "wrong finger"), ("anticipations", "before the flash"), ("misses", "missed")]
    pct = lambda v: f"{v*100:.0f}%"
    band_rows = tests_rows(srt.get("band_tests", {}))
    nav = [("overview", "Overview"), ("markers", "Recording and markers"), ("quality", "Data quality"),
           ("srt-beh", "SRT behaviour"), ("srt-erp", "SRT: the flash"), ("srt-err", "SRT: errors"),
           ("srt-osc", "SRT: rhythms"), ("bh-beh", "Buzz Hunt behaviour"), ("bh-eeg", "Buzz Hunt: the brain"),
           ("explorer", "Electrode explorer"), ("methods", "Methods"), ("limits", "Limits and next steps"),
           ("refs", "References"), ("files", "Files")]
    navh = "".join(f'<a href="#{i}">{t}</a>' for i, t in nav)
    name = s.get("participant") or "participant"
    date = s.get("date_long") or s.get("date") or ""
    body = f"""
<section id="overview"><h2>Overview</h2>
<p class="lead">{html.escape(name)}, {s.get('age')}, {s.get('dominant_hand')}-handed, tested on {date} with the lab's 64-channel BioSemi system while playing two games on the hand device: the lab's serial reaction time task (SRT, {srt.get('n_trials', 0)} trials) and Buzz Hunt ({bz.get('trials', 0)} trials). The game ran on its own PC and wrote a marker byte into the recording at every flash, press and buzz.</p>
{cards}
<h3>What came out</h3>{findings}
<div class="plain"><b>In plain words:</b> {esc(fd['plain'])}</div>
<div class="caveat">One person, one session. Every p value here compares this person's trials with each other, so it says an effect is larger than this recording's own noise, not that it holds for people in general. A headline claims an effect only when its test passes; the N2 and P3 tests are corrected for being two looks at one question (Holm), and the other comparisons in the tables are exploratory.</div>
</section>

<section id="markers"><h2>Recording and markers</h2>
<p class="lead">Each recording paired with the game block whose marker log matches it code for code. The scatter is each marker's distance from a straight-line fit of recording time on the game's clock.</p>
{_table(recs, rec_cols)}
{_fig(figs, names.get('markers'), 'Left: every marker against the clock fit, inside the grey band of one sample. Middle: the scatter. Right: pulse widths on the Status channel.')}
<div class="plain"><b>What it means:</b> this is the marker check the thesis lists for the first laboratory day (V6). {esc(pulse_txt)} Any event the game logs, even ones it sends no byte for (a press in Buzz Hunt, a force onset), can be placed in the EEG through this clock fit.</div>
</section>

<section id="quality"><h2>Data quality</h2>
<p class="lead">BioSemi records without a reference, so the data were re-referenced to the average of the 64 scalp channels. {esc(exg)}</p>
{_table(q_rows, [("mode", "game"), ("bads", "channels rebuilt"), ("ica", "eye components removed"), ("blinks", "blinks per minute"), ("unc", "unused inputs")])}
{_fig(figs, (names.get('quality') or [None])[0], 'Power spectrum before and after cleaning: the 50 Hz mains peak and slow drift removed, the alpha peak near 10 Hz kept.')}
{_fig(figs, (names.get('quality') or [None, None])[1], 'Channel noise before blink removal (the front of the head carries the eyes). Crosses mark channels rebuilt from their neighbours.')}
{''.join(_fig(figs, n, 'Eye components ICA removed: horizontal eye movements (left-right frontal pattern) and blinks (frontopolar).') for n in (names.get('quality') or [])[2:])}
<div class="caveat">{esc(notes['quality'])}</div>
</section>

<section id="srt-beh"><h2>SRT behaviour</h2>
<p class="lead">{esc(srt_lead)}</p>
{_fig(figs, names.get('srt_behaviour'), 'Median RT of correct presses per block (bars, IQR whiskers) and the share of correct, wrong-finger and early presses.')}
{_table(srt.get('behaviour', []), beh_cols, {"rt_median_ms": lambda v: f"{v:.0f}", "accuracy": pct, "wrong_finger": pct, "anticipations": pct, "misses": pct})}
{f'<div class="plain"><b>Recall:</b> {esc(notes["recall"])}</div>' if notes.get("recall") else ""}
</section>

<section id="srt-erp"><h2>SRT: the brain's response to each flash</h2>
<p class="lead">Correct trials only, 200 ms before to 600 ms after the flash, baseline the 200 ms before it.</p>
{_fig(figs, names.get('srt_joint'), 'All correct trials: every channel (coloured by position) with scalp maps at the visual P1, the N1, and the later N2/P3 period.')}
{_fig(figs, names.get('srt_conditions'), 'The same response by phase at three sites. Grey bands are the measurement windows.')}
{_fig(figs, names.get('srt_topos'), 'Scalp maps of the N2 and P3 windows per phase; the right column is random post-test minus learned blocks 7-8.')}
{_fig(figs, names.get('srt_curve'), 'P3 and N2 block by block beside RT.')}
{_fig(figs, names.get('srt_rerp'), 'Regression ERPs (rERP): every flash and every press estimated together, so neighbouring trials no longer leak into each other.')}
<h3>Measures</h3>{_table(srt.get('stim_measures', []), meas_cols, fmt_m)}
<h3>Tests</h3>{_table(tests_rows(srt.get('stim_tests', {})), cols_t, fmt_t)}
<div class="plain"><b>What it means:</b> the N2 is the brain noticing that what happened was not what it expected; it grows for items that break a learned sequence, most in people who know the sequence (Eimer et al. 1996; Ferdinand et al. 2008). The P3 shrinks as targets become predictable (Jongsma et al. 2006). {esc(notes.get('erp', ''))}</div>
<div class="caveat">{esc(notes.get('display', ''))}</div>
</section>

<section id="srt-err"><h2>SRT: errors</h2>
<p class="lead">Response-locked to the force onset of each press, which the game finds offline on the force trace (median {srt.get('rise_ms_median', 'n/a')} ms before the 30 percent press point).</p>
{_fig(figs, names.get('srt_ern'), 'Correct, wrong-finger and early presses at FCz/Cz and CPz/Pz, the error-minus-correct scalp maps, and the cluster test.')}
{_fig(figs, names.get('srt_lock'), 'Error minus correct at FCz with the epochs locked to the force onset and to the 30 percent press point.')}
<h3>Measures</h3>{_table(srt.get('resp_measures', []), meas_cols, fmt_m)}
<h3>Tests</h3>{_table(tests_rows(srt.get('resp_tests', {})), cols_t, fmt_t)}
<div class="plain"><b>What it means:</b> the error-related negativity (ERN) is the brain's error alarm, a fronto-central dip within about 100 ms of a wrong response (Gehring et al. 1993). It is stable with 6 to 8 errors (Olvet and Hajcak 2009); this session has {srt.get('resp_n', {}).get('error', 0)}. Locking to the force onset and to the press point gives the same dip; later parts shift by the rise time between them.</div>
<div class="caveat">A wrong press often comes soon after the flash, so the flash's response overlaps the press's; the regression ERPs estimate the two separately. A cluster test says error and correct trials differ somewhere, not where or when (Sassenhagen and Draschkow 2019).</div>
</section>

<section id="srt-osc"><h2>SRT: brain rhythms</h2>
<p class="lead">Power by Morlet wavelets (4-30 Hz) after each flash, and power of each block as a whole.</p>
{_fig(figs, names.get('srt_tfr'), 'Time-frequency power at C3 and FCz on random post-test and learned trials, and their difference in dB.')}
{_fig(figs, names.get('srt_power'), 'Band power block by block. Random blocks shaded.')}
<h3>Tests, random post-test against learned blocks 7-8, 0-500 ms</h3>{_table(band_rows, cols_t, fmt_t)}
<div class="plain"><b>What it means:</b> beta and alpha over the motor cortex drop when a movement is prepared and made. The lab's own SRT work finds them lower in learned sequences and higher on random trials (Lum et al. 2023, 2024, 2025). {esc(notes.get('rhythm', ''))}</div>
<div class="caveat">Faster responding and more early presses also lower beta, and blocks follow one another in time, so learning, speed and time on task move together here.</div>
</section>

<section id="bh-beh"><h2>Buzz Hunt behaviour</h2>
{_fig(figs, names.get('buzz_behaviour'), 'Which finger buzzed: accuracy and RT per finger, and the confusions.')}
{_table([{"stage": "Localisation", "res": f"{bz.get('loc_accuracy', 0)*100:.0f}% correct, d' {bz.get('d_prime')}, median RT {bz.get('loc_rt_ms')} ms, response window reached {bz.get('window_final_s')} s"},
         {"stage": "Catch (no buzz)", "res": f"{(bz.get('catch') or {}).get('n', 0)} trials, {(bz.get('catch') or {}).get('false_alarms', 0)} false alarms"},
         {"stage": "Gap", "res": f"{bz.get('gap', {}).get('trials')} trials, {(bz.get('gap', {}).get('accuracy') or 0)*100:.0f}% correct, threshold about {bz.get('gap', {}).get('threshold_ms')} ms"},
         {"stage": "Span", "res": f"{bz.get('span', {}).get('trials')} trials, final length {bz.get('span', {}).get('final')}; hidden repeat {((bz.get('span', {}).get('hebb') or {}).get('accuracy') or 0)*100:.0f}%, new {((bz.get('span', {}).get('novel') or {}).get('accuracy') or 0)*100:.0f}%"}],
        [("stage", "stage"), ("res", "result")])}
</section>

<section id="bh-eeg"><h2>Buzz Hunt: the brain's response to touch</h2>
<p class="lead">{esc(buzz_lead)}</p>
{_fig(figs, names.get('buzz_erp'), 'Left hemisphere (opposite the buzzed hand) against right; P3 at Pz/CPz by stage; scalp maps across the response. The yellow band is when the motor starts turning, measured on the study laptop.')}
{_fig(figs, names.get('buzz_tfr'), 'Rhythm change after the buzz at C3 and Cz, against the 0.7 to 0.2 s before it.')}
{_fig(figs, names.get('buzz_press'), 'Around the press that answered each correct localisation, placed in the recording through the clock fit at its force onset.')}
<h3>Measures</h3>{_table(bz.get('measures', []), meas_cols, fmt_m)}
{_table([{"test": k, "diff": (f"{v['diff']:+.2f} {v.get('unit') or 'µV'}" if v.get("diff") is not None else None), "p": v.get("p"), "n": v.get("n")} for k, v in bz.get('tests', {}).items()], [("test", "comparison"), ("diff", "difference"), ("p", "p (sign flip)"), ("n", "trials")], {"p": lambda v: _p(v).lstrip("= "), "n": lambda v: f"{v:.0f}"})}
<div class="plain"><b>What it means:</b> touch on the right hand is processed first in the left hemisphere's somatosensory cortex, then becomes a P3 when it matters for the task. The 8-12 Hz mu rhythm over the motor cortex drops while the touch is felt and the finger is moved, and beta overshoots after the movement (the post-movement beta rebound). {esc(notes.get('touch', ''))}</div>
<div class="caveat">{esc(notes.get('touch_caveat', ''))}</div>
</section>

<section id="explorer"><h2>Electrode explorer</h2>
<p class="lead">Pick a dataset, click any electrode on the head, switch conditions on and off; hover the chart to read values.</p>
<div class="ex"><div><svg id="head" viewBox="0 0 300 300" style="color:var(--ink)"></svg><div class="hint">Selected: <b id="chname"></b></div><div class="ctl" id="quick" style="margin-top:8px"></div></div>
<div><div class="ctl"><select id="set"></select></div><div class="ctl" id="chips"></div><canvas id="cv"></canvas>
<div class="hint">Positive up. 0.1-40 Hz, average reference, eye components removed; condition averages of correct trials unless named.</div></div></div>
</section>

<section id="methods"><h2>Methods</h2>
<ol>{''.join(f'<li>{m}</li>' for m in methods)}</ol>
<p class="hint">Software: MNE-Python {s['software']['mne']}, NumPy {s['software']['numpy']}, pandas {s['software']['pandas']}, Python {s['software']['python']}; game version {s['software']['game']}.</p>
</section>

<section id="limits"><h2>Limits and next steps</h2><ul class="find">{''.join(f'<li>{x}</li>' for x in limitations)}</ul></section>
<section id="refs"><h2>References</h2><ol class="refs">{''.join(f'<li>{r}</li>' for r in references)}</ol></section>
<section id="files"><h2>Files in this folder</h2>{_table([{"f": f, "w": w} for f, w in files], [("f", "file"), ("w", "what it holds")])}</section>
"""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EEG results, {html.escape(name)}, {date}</title><style>{CSS}</style></head><body>
<header><div class="eyebrow">Finger rehabilitation device, EEG laboratory session</div>
<h1>EEG results: {html.escape(name)}, {date}</h1>
<p>Serial reaction time task and Buzz Hunt, BioSemi ActiveTwo, 64 channels at 512 Hz, analysed with MNE-Python. Click any figure to enlarge it.</p></header>
<div class="layout"><nav>{navh}</nav><main>{body}</main></div>
<footer>Made by analysis/eeg (python3 -m eeg) from the session folders and the BioSemi recordings. Contains a person's EEG: keep it with the study data.</footer>
<div class="lb"><img alt=""></div>
<script id="d" type="application/json">{json.dumps(data, separators=(",", ":"))}</script>
<script>{JS}</script></body></html>"""
