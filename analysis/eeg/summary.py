"""Every number the results page and the summary document quote, in
one dictionary, so the page, the document and summary.json cannot
disagree."""
from __future__ import annotations

import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd

import mne

from . import pipeline as P


def _f(x, nd=2):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(v) else round(v, nd)


def _long_date(iso: str) -> str:
    """2026-10-08 as 8 October 2026."""
    import datetime as _dt
    try:
        d = _dt.date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{d.day} {d.strftime('%B')} {d.year}"


def build(blocks, cleaned, results, sessions: Path) -> dict:
    meta = {}
    for b in blocks:
        m = json.loads((b.folder / "metadata.json").read_text())
        meta[b.mode] = m
    any_meta = next(iter(meta.values())) if meta else {}
    s = {
        "participant": any_meta.get("participant"),
        "age": any_meta.get("age"),
        "dominant_hand": any_meta.get("dominant_hand"),
        "hand": any_meta.get("hand"),
        "srt_isi_ms": (meta.get("srt", {}).get("block_summary", {}).get("srt") or {}).get("learning_isi_ms"),
        "srt_look": ((meta.get("srt", {}).get("block_summary", {}).get("srt") or {}).get("look")
                     or ((meta.get("srt", {}).get("config_snapshot") or {}).get("srt") or {}).get("look")),
        "date": (any_meta.get("started_at") or "")[:10],
        "date_long": _long_date((any_meta.get("started_at") or "")[:10]),
        "software": {"mne": mne.__version__, "numpy": np.__version__,
                     "pandas": pd.__version__, "python": platform.python_version(),
                     "game": any_meta.get("software_version")},
        "parameters": {k: getattr(P, k) for k in (
            "LINE_HZ", "HP_ERP", "LP_ERP", "ICA_HP", "ICA_LP", "ICA_VARIANCE",
            "EOG_Z", "REJECT_UV", "FLAT_UV", "NOISE_Z", "NEIGHBOUR_R", "MONTAGE")},
        "recordings": [],
    }
    total = matched = 0
    for b in blocks:
        a = b.alignment
        raw = b.raw
        c = cleaned[b.mode]
        eeg = (b.raw.info.get("meas_date"))
        rec = {
            "mode": b.mode, "file": b.bdf.name, "game_folder": b.name,
            "start": str(eeg)[:19] if eeg else None,
            "minutes": _f(raw.times[-1] / 60, 1), "sfreq": raw.info["sfreq"],
            "channels": len(raw.ch_names),
            "markers_eeg": a.n_eeg, "markers_game": a.n_game,
            "matched": a.matched, "codes_agree": a.codes_agree,
            "residual_sd_ms": _f(np.std(a.residual_ms)),
            "residual_max_ms": _f(np.max(np.abs(a.residual_ms))),
            "drift_ppm": _f(a.drift_ppm, 1),
            "pulse_ms": [_f(np.min(b.widths_ms), 1), _f(np.median(b.widths_ms), 1),
                         _f(np.max(b.widths_ms), 1)],
            "port": meta[b.mode].get("eeg", {}).get("port"),
            "bads": c.bads, "bad_reasons": c.bad_reasons,
            "unconnected": c.unconnected,
            "ica_components": int(c.ica.n_components_),
            "ica_removed": [int(i) for i in c.ica.exclude],
            "blinks_per_min": _f(c.blinks_per_min, 1),
        }
        total += a.n_eeg; matched += a.matched
        s["recordings"].append(rec)
    s["markers_total"] = total
    s["markers_matched"] = matched
    if "srt" in results:
        r = results["srt"]
        s["srt"] = {
            "behaviour": r.behaviour.round(3).to_dict(orient="records"),
            "learning": {k: (_f(v) if not isinstance(v, list) else [_f(x) for x in v])
                         for k, v in r.learning.items()},
            "recall": r.recall,
            "n_trials": int(len(r.trials)),
            "stim_n": r.stim_n, "resp_n": r.resp_n, "reject": r.reject,
            "stim_measures": r.stim_measures.round(3).to_dict(orient="records"),
            "stim_tests": {k: {kk: (_f(vv, 4) if not isinstance(vv, list) else [_f(x, 3) for x in vv])
                               for kk, vv in v.items()} for k, v in r.stim_tests.items()},
            "per_block": r.per_block.round(3).to_dict(orient="records"),
            "resp_measures": r.resp_measures.round(3).to_dict(orient="records"),
            "resp_tests": {k: {kk: (_f(vv, 4) if not isinstance(vv, list) else [_f(x, 3) for x in vv])
                               for kk, vv in v.items()} for k, v in r.resp_tests.items()},
            "ern_clusters": r.ern_cluster.get("clusters", []) if r.ern_cluster else [],
            "lock_compare": {k: {kk: _f(vv) for kk, vv in v.items()} for k, v in r.lock_compare.items()},
            "band_tests": {k: {kk: (_f(vv, 4) if not isinstance(vv, list) else [_f(x, 3) for x in vv])
                               for kk, vv in v.items()} for k, v in r.band_tests.items()},
            "block_power": r.block_power.round(3).to_dict(orient="records"),
            "rise_ms_median": _f(np.nanmedian(r.trials.rise_ms), 1),
        }
        if r.rerp:
            ev = r.rerp["evoked"]
            def mean_at(k, chans, lo, hi):
                if k not in ev:
                    return None
                return _f(ev[k].copy().pick(chans).crop(lo, hi).data.mean() * 1e6)
            s["srt"]["rerp"] = {
                "n": r.rerp["n"],
                "ern_error_uV": mean_at("press/error", ["FCz", "Cz"], 0.0, 0.1),
                "ern_correct_uV": mean_at("press/correct", ["FCz", "Cz"], 0.0, 0.1),
                "n2_posttest_uV": mean_at("flash/posttest", ["FCz", "Cz"], 0.2, 0.3),
                "n2_seq_late_uV": mean_at("flash/seq_late", ["FCz", "Cz"], 0.2, 0.3),
            }
            if "press/error" in ev:
                x = ev["press/error"].copy().pick(["FCz", "Cz"]).data.mean(0) * 1e6
                tt = ev["press/error"].times
                sel = (tt >= 0) & (tt <= 0.15)
                s["srt"]["rerp"]["ern_peak_uV"] = _f(x[sel].min())
                s["srt"]["rerp"]["ern_peak_ms"] = _f(tt[sel][np.argmin(x[sel])] * 1000, 0)
    if "buzz_hunt" in results:
        r = results["buzz_hunt"]
        bh = r.summary
        loc = bh.get("loc", {})
        s["buzz"] = {
            "trials": int(len(r.trials)),
            "loc_accuracy": _f(loc.get("accuracy"), 3), "loc_rt_ms": _f(loc.get("median_rt_ms"), 1),
            "d_prime": _f(loc.get("d_prime"), 2),
            "catch": loc.get("catch"), "per_lane": loc.get("per_lane"),
            "gap": {"trials": bh.get("gap", {}).get("trials"), "accuracy": _f(bh.get("gap", {}).get("accuracy"), 3),
                    "threshold_ms": _f(bh.get("gap", {}).get("threshold", {}).get("right", {}).get("estimate_ms"), 0)},
            "span": {"trials": bh.get("span", {}).get("trials"), "final": bh.get("span", {}).get("final"),
                     "hebb": bh.get("span", {}).get("hebb"), "novel": bh.get("span", {}).get("novel")},
            "window_final_s": bh.get("window", {}).get("per_hand", {}).get("right", {}).get("final_window_s"),
            "erp_n": r.erp_n, "reject": r.reject,
            "measures": r.measures.round(3).to_dict(orient="records"),
            "tests": {k: {kk: (vv if isinstance(vv, str) else _f(vv, 4)) for kk, vv in v.items()}
                      for k, v in r.tests.items()},
            "press_n": r.press.get("n") if r.press else 0,
            "pulse_ms": (meta.get("buzz_hunt", {}).get("block_summary", {}).get("buzz_hunt") or {}).get("pulse_ms"),
        }
        sf = next(b.raw.info["sfreq"] for b in blocks if b.mode == "buzz_hunt")
        loc = r.trials[(r.trials.stage == "loc") & r.trials.buzz_sample.notna()].buzz_sample.to_numpy(float)
        if len(loc) > 2:
            gaps = np.diff(np.sort(loc)) / sf
            s["buzz"]["cycle_s"] = [_f(np.percentile(gaps, 10), 1), _f(np.percentile(gaps, 90), 1)]
    return s


def write(s: dict, path: Path) -> None:
    def default(o):
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, (np.floating,)):
            return None if not np.isfinite(o) else float(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return str(o)
    path.write_text(json.dumps(s, indent=1, default=default))
