"""Post-block research report.

Reads a session folder's trials.csv + metadata.json and writes, next to
them:

    summary.csv     one flat row of headline numbers (spreadsheet-ready)
    charts/*.png    standalone figures sized for a thesis page
    report.html     self-contained page: tables + embedded charts

Also maintains sessions_index.csv at the top of the sessions/ folder,
one line per block, so a researcher can see every recording at a glance
without opening folders.

matplotlib imports lazily (inside the chart functions) so app startup
and most tests never pay for it. Every entry point is defensive: the
CSVs are already safe on disk before this module runs, so a report
failure must never take anything down - the engine wraps calls in
try/except as well, belt and braces.
"""
from __future__ import annotations

import base64
import csv
import html
import json
import logging
from pathlib import Path


log = logging.getLogger(__name__)


# Palette matched to the game's clinical theme so the report looks like
# it belongs to the software.
ACCENT = "#2563eb"
GREEN = "#16a34a"
RED = "#dc2626"
ORANGE = "#ea580c"
GREY = "#64748b"
BG = "#f8fafc"

FINGERS = ("Index", "Middle", "Ring", "Pinky")

# Fixed finger colours, matching the game's lane tiles so a chart in the
# report is read with the same colour language as the screen:
# index = orange, middle = light blue, ring = black, pinky = yellow.
FINGER_COLOURS = ("#ea580c", "#0ea5e9", "#0f172a", "#ca8a04")


def lane_label(lane: int, hand: str, n_per_hand: int = 4) -> str:
    """Human name for a global lane index. Unilateral: 0..3 on the
    session's hand. Bilateral: 0..3 right hand, 4..7 left hand."""
    finger = FINGERS[lane % n_per_hand]
    if hand == "both":
        side = "Right" if lane < n_per_hand else "Left"
        return f"{side} {finger}"
    side = "Left" if hand == "left" else "Right"
    return f"{side} {finger}"


# ---- loading ---------------------------------------------------------------

def _load_trials(session_root: Path) -> list[dict]:
    p = session_root / "trials.csv"
    if not p.exists():
        return []
    with p.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _load_meta(session_root: Path) -> dict:
    p = session_root / "metadata.json"
    if not p.exists():
        return {}
    try:
        with p.open("r", encoding="utf-8") as f:
            return json.load(f) or {}
    except (json.JSONDecodeError, OSError) as e:
        log.warning("report: could not read metadata.json: %s", e)
        return {}


def _f(value, default=None) -> float | None:
    """Float or None from a CSV cell that may be empty."""
    if value is None or value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---- charts ----------------------------------------------------------------

def _new_axes(figsize=(7.0, 3.4)):
    import matplotlib
    matplotlib.use("Agg", force=False)
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=figsize, dpi=150)
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    ax.grid(axis="y", color="#e2e8f0", linewidth=0.8)
    ax.set_axisbelow(True)
    return fig, ax


def _save(fig, path: Path) -> Path:
    import matplotlib.pyplot as plt
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def _chart_rt_per_finger(rows: list[dict], meta: dict,
                          out: Path, rhythm: bool) -> Path | None:
    """Bar chart: mean reaction time (or beat offset) per finger, with
    the standard deviation as an error bar when a finger has 2+ hits."""
    hand = str(meta.get("hand", "right"))
    by_lane: dict[int, list[float]] = {}
    for r in rows:
        rt = _f(r.get("time_difference_ms"))
        lane = _f(r.get("lane"))
        if rt is None or lane is None or r.get("early_late") == "Miss":
            continue
        by_lane.setdefault(int(lane) - 1, []).append(
            abs(rt) if rhythm else rt)
    if not by_lane:
        return None
    lanes = sorted(by_lane)
    means = [sum(by_lane[l]) / len(by_lane[l]) for l in lanes]
    stds = []
    for l in lanes:
        vals = by_lane[l]
        if len(vals) >= 2:
            m = sum(vals) / len(vals)
            stds.append((sum((v - m) ** 2 for v in vals)
                          / (len(vals) - 1)) ** 0.5)
        else:
            stds.append(0.0)
    fig, ax = _new_axes()
    xs = range(len(lanes))
    bar_colours = [FINGER_COLOURS[l % len(FINGER_COLOURS)] for l in lanes]
    ax.bar(xs, means, yerr=stds, capsize=4, color=bar_colours, width=0.6,
           error_kw={"ecolor": GREY, "elinewidth": 1.2})
    ax.set_xticks(list(xs))
    ax.set_xticklabels([lane_label(l, hand) for l in lanes], fontsize=9)
    ax.set_ylabel("Beat offset (ms)" if rhythm
                  else "Reaction time (ms)", fontsize=9)
    ax.set_title("Mean timing per finger (error bars: SD)",
                 fontsize=11, loc="left")
    return _save(fig, out)


def _chart_errors_per_finger(rows: list[dict], meta: dict,
                              out: Path) -> Path | None:
    """Grouped bars: timeouts (no press) and wrong presses per finger."""
    hand = str(meta.get("hand", "right"))
    misses: dict[int, int] = {}
    wrong: dict[int, int] = {}
    for r in rows:
        lane = _f(r.get("lane"))
        if lane is None:
            continue
        lane_i = int(lane) - 1
        if r.get("early_late") == "Miss":
            misses[lane_i] = misses.get(lane_i, 0) + 1
        if r.get("had_incorrect_press") == "TRUE":
            wrong[lane_i] = wrong.get(lane_i, 0) + 1
    lanes = sorted(set(misses) | set(wrong))
    if not lanes:
        return None
    fig, ax = _new_axes()
    xs = list(range(len(lanes)))
    w = 0.35
    ax.bar([x - w / 2 for x in xs],
           [misses.get(l, 0) for l in lanes],
           width=w, color=RED, label="Misses")
    ax.bar([x + w / 2 for x in xs],
           [wrong.get(l, 0) for l in lanes],
           width=w, color=ORANGE, label="Trials with a wrong press")
    ax.set_xticks(xs)
    ax.set_xticklabels([lane_label(l, hand) for l in lanes], fontsize=9)
    ax.set_ylabel("Count", fontsize=9)
    ax.yaxis.get_major_locator().set_params(integer=True)
    ax.set_title("Errors per finger", fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, out)


def _rolling(vals: list[float], window: int = 5) -> list[float]:
    out = []
    for i in range(len(vals)):
        lo = max(0, i - window + 1)
        chunk = vals[lo:i + 1]
        out.append(sum(chunk) / len(chunk))
    return out


def _chart_rt_over_trials(rows: list[dict], out: Path,
                           rhythm: bool) -> Path | None:
    """Per-trial timing across the block: raw points + rolling mean.
    The slope is the within-block learning / fatigue picture."""
    xs, ys = [], []
    for r in rows:
        rt = _f(r.get("time_difference_ms"))
        tr = _f(r.get("trial"))
        if rt is None or tr is None or r.get("early_late") == "Miss":
            continue
        xs.append(int(tr))
        ys.append(abs(rt) if rhythm else rt)
    if len(xs) < 2:
        return None
    fig, ax = _new_axes()
    ax.plot(xs, ys, "o", color=ACCENT, markersize=3.5, alpha=0.45,
            label="Trial")
    ax.plot(xs, _rolling(ys), color=ACCENT, linewidth=2,
            label="Rolling mean (5)")
    ax.set_xlabel("Trial", fontsize=9)
    ax.set_ylabel("Beat offset (ms)" if rhythm
                  else "Reaction time (ms)", fontsize=9)
    ax.set_title("Timing across the block", fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, out)


def _chart_force_over_trials(rows: list[dict], meta: dict,
                              out: Path) -> Path | None:
    """Per-trial peak force on the target finger. Only drawn when the
    block actually has force data (skipped in keyboard mode)."""
    xs, ys = [], []
    for r in rows:
        force = _f(r.get("peak_force_n"))
        tr = _f(r.get("trial"))
        if force is None or tr is None:
            continue
        xs.append(int(tr))
        ys.append(force)
    if len(xs) < 2:
        return None
    unit = str(meta.get("block_summary", {}).get("force_unit",
                                                  "sensor units"))
    fig, ax = _new_axes()
    ax.plot(xs, ys, "o", color=GREEN, markersize=3.5, alpha=0.45,
            label="Trial")
    ax.plot(xs, _rolling(ys), color=GREEN, linewidth=2,
            label="Rolling mean (5)")
    ax.set_xlabel("Trial", fontsize=9)
    ax.set_ylabel(f"Peak force ({unit})", fontsize=9)
    ax.set_title("Press force across the block", fontsize=11, loc="left")
    ax.legend(frameon=False, fontsize=8)
    return _save(fig, out)


# ---- summary.csv -----------------------------------------------------------

def _flatten(prefix: str, value, out: dict) -> None:
    """metadata.json is nested; spreadsheets want one flat row. Dotted
    keys keep the provenance readable (miss_force.total etc.)."""
    if isinstance(value, dict):
        for k, v in value.items():
            _flatten(f"{prefix}.{k}" if prefix else str(k), v, out)
    elif isinstance(value, list):
        out[prefix] = ";".join(str(v) for v in value)
    else:
        out[prefix] = value


def _write_summary_csv(meta: dict, out: Path) -> Path:
    row: dict = {}
    for key in ("participant", "age", "hand", "started_at", "finished_at",
                "source_name", "software_version"):
        row[key] = meta.get(key, "")
    _flatten("", meta.get("block_summary", {}) or {}, row)
    with out.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        writer.writeheader()
        writer.writerow(row)
    return out


# ---- report.html -----------------------------------------------------------

_CSS = """
body { font-family: -apple-system, 'Segoe UI', Helvetica, Arial,
       sans-serif; margin: 0; background: #f8fafc; color: #0f172a; }
.wrap { max-width: 900px; margin: 0 auto; padding: 32px 24px 48px; }
h1 { font-size: 26px; margin: 0 0 2px; }
h2 { font-size: 16px; margin: 28px 0 10px; color: #0f172a; }
.sub { color: #64748b; font-size: 13px; margin-bottom: 22px; }
.bar { height: 4px; width: 96px; background: #2563eb;
       border-radius: 2px; margin: 10px 0 18px; }
table { border-collapse: collapse; width: 100%; background: white;
        border: 1px solid #e2e8f0; border-radius: 8px;
        overflow: hidden; font-size: 13px; }
th, td { text-align: left; padding: 7px 12px;
         border-bottom: 1px solid #eef2f7; }
th { background: #f1f5f9; font-weight: 600; color: #334155; }
tr:last-child td { border-bottom: none; }
img.chart { width: 100%; background: white; border: 1px solid #e2e8f0;
            border-radius: 8px; margin: 6px 0 14px; }
.footer { color: #94a3b8; font-size: 11px; margin-top: 30px; }
"""


def _img_tag(png: Path) -> str:
    data = base64.b64encode(png.read_bytes()).decode("ascii")
    return (f'<img class="chart" alt="{html.escape(png.stem)}" '
            f'src="data:image/png;base64,{data}">')


def _kv_table(pairs: list[tuple[str, object]]) -> str:
    rows = "".join(
        f"<tr><td>{html.escape(str(k))}</td>"
        f"<td>{html.escape('' if v is None else str(v))}</td></tr>"
        for k, v in pairs)
    return f"<table><tbody>{rows}</tbody></table>"


def _per_finger_table(meta: dict) -> str:
    summary = meta.get("block_summary", {}) or {}
    per_lane = summary.get("per_lane", {}) or {}
    if not per_lane:
        return "<p class='sub'>No per-finger data recorded.</p>"
    hand = str(meta.get("hand", "right"))
    head = ("<tr><th>Finger</th><th>Trials</th><th>Hit rate</th>"
            "<th>Mean RT (ms)</th><th>RT SD</th><th>Timeout rate</th>"
            "<th>Wrong-press rate</th><th>Peak force (mean)</th></tr>")
    body = []
    for lane_str in sorted(per_lane, key=lambda s: int(s)):
        d = per_lane[lane_str]

        def cell(key, fmt="{}"):
            v = d.get(key)
            return "" if v is None else fmt.format(v)

        body.append(
            "<tr>"
            f"<td>{html.escape(lane_label(int(lane_str), hand))}</td>"
            f"<td>{cell('n_trials')}</td>"
            f"<td>{cell('hit_rate')}</td>"
            f"<td>{cell('rt_mean_ms')}</td>"
            f"<td>{cell('rt_std_ms')}</td>"
            f"<td>{cell('timeout_rate')}</td>"
            f"<td>{cell('misclick_rate')}</td>"
            f"<td>{cell('peak_force_mean')}</td>"
            "</tr>")
    return f"<table><thead>{head}</thead><tbody>{''.join(body)}</tbody></table>"


def _write_html(meta: dict, charts: list[Path], out: Path,
                n_trials: int) -> Path:
    summary = meta.get("block_summary", {}) or {}
    mf = summary.get("miss_force", {}) or {}
    loud = summary.get("loud_trials", {}) or {}
    song = summary.get("song", {}) or {}

    session_pairs = [
        ("Participant", meta.get("participant", "")),
        ("Age", meta.get("age", "")),
        ("Hand", meta.get("hand", "")),
        ("Mode", summary.get("block", "")),
        ("Status", summary.get("status", "")),
        ("Started", meta.get("started_at", "")),
        ("Finished", meta.get("finished_at", "")),
        ("Duration (s)", summary.get("duration_s", "")),
        ("Input source", meta.get("source_name", "")),
        ("Software version", meta.get("software_version", "")),
    ]
    if song:
        session_pairs.append(
            ("Song", f"{song.get('title', '')} "
                     f"({song.get('difficulty', '')}, "
                     f"{song.get('bpm', '')} BPM)"))

    headline_pairs = [
        ("Trials", summary.get("trials", n_trials)),
        ("Hits", summary.get("hits", "")),
        ("Misses", summary.get("misses", "")),
        ("Hit rate", summary.get("hit_rate", "")),
        ("Final score", summary.get("final_score", "")),
        ("Average RT (ms)", summary.get("avg_rt_ms", "")),
        ("Peak streak", summary.get("peak_streak", "")),
        ("Trials with a wrong press",
         summary.get("wrong_press_trials", "")),
        ("Idle presses", summary.get("idle_presses", "")),
        ("Loud trials played", loud.get("n", "")),
        (f"Miss-trial force, all fingers "
         f"(first {mf.get('window_ms', '')} ms)", mf.get("total", "")),
        ("Mean miss-trial force per miss", mf.get("mean_per_miss", "")),
        ("Force unit", summary.get("force_unit", "")),
    ]

    charts_html = "\n".join(_img_tag(p) for p in charts if p is not None)
    title = html.escape(
        f"{meta.get('participant', 'NA')} - "
        f"{summary.get('block', 'session')} block")
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>{title}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>Finger Rehab session report</h1>
  <div class="bar"></div>
  <div class="sub">Generated automatically at block end.
  All raw data stays in trials.csv and raw.csv in this folder.</div>
  <h2>Session</h2>
  {_kv_table(session_pairs)}
  <h2>Headline results</h2>
  {_kv_table(headline_pairs)}
  <h2>Per-finger breakdown</h2>
  {_per_finger_table(meta)}
  <h2>Charts</h2>
  {charts_html if charts_html else "<p class='sub'>Not enough data for charts.</p>"}
  <div class="footer">Finger Rehab
  v{html.escape(str(meta.get('software_version', '')))},
  Curtin University Mechatronic Engineering research project.
  This report is a convenience view; the CSVs are the source of truth.
  </div>
</div>
</body>
</html>
"""
    out.write_text(doc, encoding="utf-8")
    return out


# ---- entry points ----------------------------------------------------------

def generate(session_root: str | Path) -> Path | None:
    """Build summary.csv, charts/ and report.html inside the session
    folder. Returns the report path, or None when there was nothing to
    report on. Never raises for data problems; the caller additionally
    wraps it for belt and braces."""
    root = Path(session_root)
    meta = _load_meta(root)
    rows = _load_trials(root)
    if not meta and not rows:
        return None
    rhythm = (meta.get("block_summary", {}) or {}).get("block") == "rhythm"
    charts_dir = root / "charts"
    charts: list[Path] = []
    for fn in (
        lambda: _chart_rt_per_finger(
            rows, meta, charts_dir / "timing_per_finger.png", rhythm),
        lambda: _chart_errors_per_finger(
            rows, meta, charts_dir / "errors_per_finger.png"),
        lambda: _chart_rt_over_trials(
            rows, charts_dir / "timing_over_trials.png", rhythm),
        lambda: _chart_force_over_trials(
            rows, meta, charts_dir / "force_over_trials.png"),
    ):
        try:
            p = fn()
            if p is not None:
                charts.append(p)
        except Exception as e:
            log.warning("report chart failed: %s", e)
    try:
        _write_summary_csv(meta, root / "summary.csv")
    except Exception as e:
        log.warning("summary.csv failed: %s", e)
    return _write_html(meta, charts, root / "report.html", len(rows))


INDEX_COLUMNS = [
    "date", "finished_at", "participant", "age", "mode", "hand",
    "status", "trials", "hit_rate", "avg_rt_ms", "final_score",
    "folder",
]


def append_index(sessions_dir: str | Path, entry: dict) -> Path:
    """Append one line per block to sessions_index.csv at the top of
    the sessions folder: the researcher's table of contents. `date`
    leads so the file sorts and filters by day, matching the on-disk
    day folders; `folder` is the day-relative path. Creates the file
    with a header on first use. If an existing file has a different
    header (older schema), it is set aside as sessions_index_legacy.csv
    rather than mixing two schemas in one file."""
    path = Path(sessions_dir) / "sessions_index.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            with path.open("r", encoding="utf-8", newline="") as f:
                header = next(csv.reader(f), [])
        except OSError:
            header = []
        if header != INDEX_COLUMNS:
            legacy = path.with_name("sessions_index_legacy.csv")
            i = 0
            while legacy.exists():
                i += 1
                legacy = path.with_name(f"sessions_index_legacy_{i}.csv")
            path.rename(legacy)
            log.info("sessions_index schema changed; old file kept "
                     "as %s", legacy.name)
    new_file = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INDEX_COLUMNS,
                                 extrasaction="ignore")
        if new_file:
            writer.writeheader()
        writer.writerow({k: entry.get(k, "") for k in INDEX_COLUMNS})
    return path
