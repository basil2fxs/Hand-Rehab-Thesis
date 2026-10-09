"""Marker checks before any effect is read (Welber Marinovic, 9 October
2026): the markers against the game's own log, the early sensory
responses (fixed, known timing) beside an average at random times, and
the error signal locked to the response. counts(), by_condition(),
gaps(), rt_match(), order(), queue() and status_bits() are plain numpy
and pandas, so they are tested without MNE.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

KEY_LANE = {"v": 0, "b": 1, "n": 2, "m": 3}       # the script's keys, lanes 0 to 3
MOTOR_MS = (71, 80)     # buzz command to vibration, four motors on the bench (24 Sep 2026)
STIM_WIN = (-0.2, 0.5)  # stimulus epochs, baseline to 0
RESP_WIN = (-0.4, 0.4)  # response epochs, plotted from -0.2
RESP_BASE = (-0.4, -0.2)  # ERP CORE: before the flash's own response reaches the press
SEED = 7
CONDITIONS = [("random_practice", "Random, practice"), ("sequence_early", "Pattern, blocks 1-2"),
              ("sequence_middle", "Pattern, blocks 3-6"), ("sequence_late", "Pattern, blocks 7-8"),
              ("random_posttest", "Random, post-test")]


def _band(codes: pd.Series, lo: int, width: int = 10) -> int:
    return int(((codes >= lo) & (codes < lo + width)).sum())


def response_bytes(pairs: pd.DataFrame) -> pd.DataFrame:
    """The Reaction game's response bytes (100 to 131) in wire order."""
    return pairs[(pairs.code_eeg >= 100) & (pairs.code_eeg <= 131)].reset_index(drop=True)


def counts(t: pd.DataFrame, srt_codes, buzz: pd.DataFrame, buzz_codes) -> list[tuple]:
    """Each marker type in the recording against the log's trials."""
    s, b = pd.Series(np.asarray(srt_codes)), pd.Series(np.asarray(buzz_codes))
    out = t.outcome
    return [("Flashes", int((s == 30).sum()), len(t)),
            ("Correct presses", _band(s, 100), int((out == "correct").sum())),
            ("Wrong finger", _band(s, 110), int((out == "error").sum())),
            ("Early presses", _band(s, 120), int((out == "anticipation").sum())),
            ("Misses", int((s == 130).sum()), int((out == "miss").sum())),
            ("Buzzes", int((b == 38).sum()), int((~buzz["catch"].astype(bool)).sum()))]


def by_condition(t: pd.DataFrame) -> tuple[list[list], bool]:
    """Flashes and response bytes per condition, read from the bytes, and
    whether every count equals the log's."""
    band = (t.resp_code // 10 * 10).map({100: "correct", 110: "error", 120: "anticipation",
                                         130: "miss"})
    kinds = ["correct", "error", "anticipation", "miss"]
    rows, same = [], True
    for key, label in CONDITIONS:
        m = t.condition == key
        eeg = [int((band[m] == k).sum()) for k in kinds]
        same &= eeg == [int((t.outcome[m] == k).sum()) for k in kinds]
        rows.append([label, int(m.sum())] + eeg)
    rows.append(["All", len(t)] + [sum(r[i] for r in rows) for i in range(2, 6)])
    return rows, bool(same)


def queue(events: pd.DataFrame) -> dict:
    """From a game's marker log: how long stimulus bytes waited between the
    event and the wire, how many bytes waited behind another, and how many
    failed or were dropped."""
    ev = events.copy()
    wait = (pd.to_numeric(ev.t_wire, errors="coerce") - pd.to_numeric(ev.t_event, errors="coerce")) * 1000
    stim = (ev.value >= 30) & (ev.value <= 39)
    late = pd.to_numeric(ev.delayed, errors="coerce").fillna(0) > 0
    return {"stim_wait_max_ms": float(wait[stim].max()) if stim.any() else float("nan"),
            "delayed_stim": int((late & stim).sum()), "delayed": int(late.sum()),
            "failed": int(pd.to_numeric(ev.failed, errors="coerce").fillna(0).sum()),
            "dropped": int(pd.to_numeric(ev.dropped, errors="coerce").fillna(0).sum())}


def status_bits(status) -> dict:
    """BioSemi status words (24 bit): the share of samples with the common
    mode sense (CMS) in range (bit 20) and with the battery low (bit 22)."""
    st = np.asarray(status, dtype=np.int64)
    return {"cms_in_range": float(((st >> 20) & 1).mean()), "battery_low": float(((st >> 22) & 1).mean())}


def read_status(bdf) -> np.ndarray:
    """The raw 24-bit status channel of a BioSemi BDF file, read from the
    bytes because MNE keeps only the trigger bits."""
    from pathlib import Path
    b = Path(bdf).read_bytes()
    head, ns = int(b[184:192]), int(b[252:256])
    labels = [b[256 + 16 * i: 272 + 16 * i].decode().strip() for i in range(ns)]
    at = 256 + ns * 216
    spr = [int(b[at + 8 * i: at + 8 * i + 8]) for i in range(ns)]
    i = labels.index("Status")
    rec, start, n = sum(spr) * 3, sum(spr[:i]) * 3, spr[i] * 3
    nrec = (len(b) - head) // rec
    raw = np.frombuffer(b[head: head + nrec * rec], dtype=np.uint8).reshape(nrec, rec)
    word = raw[:, start: start + n].reshape(-1, 3).astype(np.int64)
    return word[:, 0] | (word[:, 1] << 8) | (word[:, 2] << 16)


def _kind(conditions) -> np.ndarray:
    """Random or pattern for each trial, from the log's condition."""
    return np.where(pd.Series(conditions).astype(str).str.startswith("random"), "random", "pattern")


def _same_block(t: pd.DataFrame) -> np.ndarray:
    """True for each trial that follows another in the same block."""
    g = t.groupby(["phase", "block"], sort=False).ngroup().to_numpy()
    return np.diff(g) == 0


def gaps(t: pd.DataFrame, sf: float, buzz: pd.DataFrame) -> dict:
    """Seconds between markers in the recording: flash to flash and press
    to the next flash inside a block, localisation buzz to buzz, and the
    recording's flash gaps minus the log's."""
    flash = t.flash_sample.to_numpy(float) / sf
    press = t.press_sample.to_numpy(float) / sf
    same = _same_block(t)
    after_press = same & (t.outcome.to_numpy()[:-1] != "miss") & np.isfinite(press[:-1])
    practice = t.phase.to_numpy()[:-1] == "practice"
    nxt = flash[1:] - press[:-1]
    loc = buzz[(buzz.stage == "loc") & buzz.buzz_sample.notna()]
    kind = _kind(t.condition)[1:]
    return {"flash_flash": np.diff(flash)[same],
            "flash_flash_random": np.diff(flash)[same & (kind == "random")],
            "flash_flash_pattern": np.diff(flash)[same & (kind == "pattern")],
            "press_next": nxt[after_press & ~practice],
            "press_next_practice": nxt[after_press & practice],
            "buzz_buzz": np.diff(np.sort(loc.buzz_sample.to_numpy(float))) / sf,
            "flash_vs_log_ms": (np.diff(flash) - np.diff(t.onset_s.to_numpy(float))) * 1000}


def rt_match(t: pd.DataFrame, byte_sample, sf: float) -> dict:
    """Reaction times from the recording against the log's, from the press
    time each response byte carries and from the byte itself."""
    log = t.rt_ms.to_numpy(float)
    flash = t.flash_sample.to_numpy(float)
    press = (t.press_sample.to_numpy(float) - flash) / sf * 1000
    byte = (np.asarray(byte_sample, float) - flash) / sf * 1000
    ok = t.outcome.isin(["correct", "error", "anticipation"]).to_numpy() & np.isfinite(log)
    ok &= np.isfinite(press) & np.isfinite(byte)
    off, late = press[ok] - log[ok], byte[ok] - press[ok]
    return {"n": int(ok.sum()), "r": float(np.corrcoef(press[ok], log[ok])[0, 1]),
            "offset_ms": float(np.mean(off)), "offset_sd_ms": float(np.std(off)),
            "byte_late_ms": [float(np.percentile(late, q)) for q in (5, 50, 95)],
            "press_minus_log": off, "byte_minus_log": byte[ok] - log[ok]}


def order(t: pd.DataFrame, vs_log_ms) -> dict:
    """The log's trial labels against the recording, trial by trial: each
    response byte's lane against the key the log names, each byte's band
    against the log's outcome, and the largest flash gap difference."""
    pressed = t.outcome.isin(["correct", "error", "anticipation"]).to_numpy()
    lane = t.response_key.map(KEY_LANE).to_numpy(float)
    ok = pressed & np.isfinite(lane)
    code = t.resp_code.to_numpy(float)
    band = t.outcome.map({"correct": 100, "error": 110, "anticipation": 120, "miss": 130})
    return {"lanes": (int(((code % 10)[ok] == lane[ok]).sum()), int(ok.sum())),
            "bands": (int(((code // 10 * 10) == band.to_numpy(float)).sum()), len(t)),
            "gap_max_ms": float(np.nanmax(np.abs(vs_log_ms)))}


# ---- the parts that need MNE ---------------------------------------------------
def _wave(ep, chans) -> np.ndarray:
    return ep.average().copy().pick(chans).data.mean(0) * 1e6


def _peak(times_ms, y, t0, t1, sign) -> tuple[float, float]:
    m = (times_ms >= t0) & (times_ms <= t1)
    i = int(np.argmax(sign * y[m]))
    return float(times_ms[m][i]), float(y[m][i])


def _random(raw, n: int, first: float, last: float, seed: int = SEED):
    """n epochs at random times between first and last (seconds), the
    control that should average to a flat line."""
    from . import pipeline as P
    rng = np.random.default_rng(seed)
    sf = raw.info["sfreq"]
    s = np.sort(rng.integers(int(first * sf), int(last * sf), n))
    return P.make_epochs(raw, s, np.ones(n, int), pd.DataFrame({"i": range(n)}), *STIM_WIN,
                         (STIM_WIN[0], 0.0))


def _flash_peaks(ep, ms) -> dict:
    o, cz = _wave(ep, ["O1", "O2"]), _wave(ep, ["Cz"])
    return {"n": len(ep), "O1/O2": o, "Cz": cz,
            "P1": _peak(ms, o, 60, 160, 1), "N1": _peak(ms, o, 120, 220, -1),
            "Cz N1": _peak(ms, cz, 60, 250, -1), "Cz P2": _peak(ms, cz, 150, 300, 1)}


def sensory(cleaned: dict, t: pd.DataFrame, buzz: pd.DataFrame) -> dict:
    """The early responses to the flash (O1/O2) and the tone (Cz), random
    and pattern trials apart, and to the buzz (C3/CP3 against C4/CP4),
    each beside an average at random times (the control)."""
    from scipy.ndimage import uniform_filter1d

    from . import pipeline as P
    out = {}
    raw = cleaned["srt"].raw
    sf = raw.info["sfreq"]
    fl = P.make_epochs(raw, t.flash_sample, np.full(len(t), 30), t, *STIM_WIN, (STIM_WIN[0], 0.0))
    span = t.flash_sample.to_numpy(float) / sf
    ctrl = _random(raw, len(t), np.nanmin(span), np.nanmax(span))
    ms = fl.times * 1000
    kind = _kind(fl.metadata.condition)
    pat = fl[kind == "pattern"]
    early = pat.metadata.block.to_numpy() <= 4
    halves = [(_peak(ms, _wave(pat[m], ["O1", "O2"]), 60, 160, 1)[0],
               _peak(ms, _wave(pat[m], ["O1", "O2"]), 120, 220, -1)[0]) for m in (early, ~early)]
    single = fl.get_data(picks=["O1", "O2"]).mean(1) * 1e6
    out["flash"] = {"ms": ms, "control O1/O2": _wave(ctrl, ["O1", "O2"]),
                    "control Cz": _wave(ctrl, ["Cz"]), "n": len(fl), "of": len(t),
                    "kept": fl.metadata.condition.value_counts().to_dict(),
                    "random": _flash_peaks(fl[kind == "random"], ms), "pattern": _flash_peaks(pat, ms),
                    "halves": halves, "kinds": kind,
                    "image": uniform_filter1d(single, size=30, axis=0, mode="nearest")}
    raw = cleaned["buzz_hunt"].raw
    sf = raw.info["sfreq"]
    real = buzz[buzz.buzz_sample.notna()].reset_index(drop=True)
    bz = P.make_epochs(raw, real.buzz_sample, np.full(len(real), 38), real, *STIM_WIN,
                       (STIM_WIN[0], 0.0))
    span = real.buzz_sample.to_numpy(float) / sf
    ctrl = _random(raw, len(real), span.min(), span.max())
    ms = bz.times * 1000
    c3 = _wave(bz, ["C3", "CP3"])
    out["buzz"] = {"ms": ms, "C3/CP3": c3, "C4/CP4": _wave(bz, ["C4", "CP4"]),
                   "control C3/CP3": _wave(ctrl, ["C3", "CP3"]), "n": len(bz), "of": len(real),
                   "first": _peak(ms, c3, 60, 160, 1), "neg": _peak(ms, c3, 150, 400, -1),
                   "neg_right": _peak(ms, _wave(bz, ["C4", "CP4"]), 150, 400, -1)}
    return out


def errors(cleaned: dict, t: pd.DataFrame) -> dict:
    """The error signal (ERN) and correct-response CRN at FCz, and the Pe
    at Pz/CPz, locked to the press each response byte carries, for
    pattern and random trials apart."""
    from . import pipeline as P
    from .analyses import perm_diff, window_means
    raw = cleaned["srt"].raw
    use = t.outcome.isin(["correct", "error"]).to_numpy() & np.isfinite(t.press_sample.to_numpy(float))
    tk = t[use].reset_index(drop=True)
    ep = P.make_epochs(raw, tk.press_sample, np.where(tk.outcome == "error", 2, 1), tk, *RESP_WIN,
                       RESP_BASE)
    ms = ep.times * 1000
    kind, kept = _kind(ep.metadata.condition), _kind(tk.condition)
    out = {"ms": ms}
    for name in ("pattern", "random"):
        sub = ep[kind == name]
        err, cor = sub[sub.metadata.outcome == "error"], sub[sub.metadata.outcome == "correct"]
        all_err = int(((tk.outcome == "error") & (kept == name)).sum())
        all_cor = int(((tk.outcome == "correct") & (kept == name)).sum())
        res = {"n_error": len(err), "of_error": all_err, "n_correct": len(cor), "of_correct": all_cor}
        if len(err) >= 2 and len(cor) >= 2:
            fe, fc = _wave(err, ["FCz"]), _wave(cor, ["FCz"])
            res.update({"FCz error": fe, "FCz correct": fc,
                        "Pz/CPz error": _wave(err, ["Pz", "CPz"]),
                        "Pz/CPz correct": _wave(cor, ["Pz", "CPz"]),
                        "ERN": _peak(ms, fe, -50, 150, -1), "CRN": _peak(ms, fc, -50, 150, -1),
                        "ern_test": perm_diff(window_means(err, (0.0, 0.1), ["FCz"]),
                                              window_means(cor, (0.0, 0.1), ["FCz"]),
                                              rng=np.random.default_rng(SEED)),
                        "pe_test": perm_diff(window_means(err, (0.2, 0.4), ["Pz", "CPz"]),
                                             window_means(cor, (0.2, 0.4), ["Pz", "CPz"]),
                                             rng=np.random.default_rng(SEED))})
        out[name] = res
    return out


def compute(blocks, cleaned: dict, results: dict) -> dict:
    """Every check, from the pipeline's blocks, cleaned recordings and
    results. Empty without both games."""
    by = {b.mode: b for b in blocks}
    if "srt" not in by or "buzz_hunt" not in by or "srt" not in results:
        return {}
    t, buzz = results["srt"].trials, results["buzz_hunt"].trials
    srt, bh = by["srt"], by["buzz_hunt"]
    sf = srt.raw.info["sfreq"]
    resp = response_bytes(srt.alignment.pairs)
    n = min(len(t), len(resp))
    byte = np.full(len(t), np.nan)
    byte[:n] = np.round(resp.eeg_s.to_numpy()[:n] * sf)
    g = gaps(t, sf, buzz)
    logs = {b.mode: pd.read_csv(b.folder / "events.tsv", sep="\t", na_values="n/a") for b in blocks}
    halves = {}
    for b in blocks:
        r = b.alignment.residual_ms
        halves[b.mode] = (float(np.std(r[: len(r) // 2])), float(np.std(r[len(r) // 2:])))
    ica_kind = {}
    for m, c in cleaned.items():
        v, h = (np.abs(np.asarray(c.eog_scores.get(k, []), float)) for k in ("VEOG", "HEOG"))
        ica_kind[m] = ["blink" if (v[i] if i < len(v) else 0) >= (h[i] if i < len(h) else 0)
                       else "horizontal" for i in c.ica.exclude]
    rows, same = by_condition(t)
    real = buzz[~buzz["catch"].astype(bool)]
    return {"counts": counts(t, srt.alignment.pairs.code_eeg, buzz, bh.alignment.pairs.code_eeg),
            "by_condition": rows, "by_condition_match": same,
            "buzz_stages": {k: int(v) for k, v in real.stage.value_counts().items()},
            "catch": int(buzz["catch"].astype(bool).sum()),
            "queue": {b.mode: queue(logs[b.mode]) for b in blocks},
            "status": {b.mode: status_bits(read_status(b.bdf)) for b in blocks},
            "recordings": {b.mode: (b.bdf.name, float(b.raw.times[-1] / 60)) for b in blocks},
            "drift_ppm": {b.mode: float(b.alignment.drift_ppm) for b in blocks},
            "timing_halves": halves, "ica_kind": ica_kind,
            "blinks_per_min": {m: float(c.blinks_per_min) for m, c in cleaned.items()},
            "gaps": g, "rt": rt_match(t, byte, sf), "order": order(t, g["flash_vs_log_ms"]),
            "timing_sd_ms": max(float(np.std(b.alignment.residual_ms)) for b in blocks),
            "timing_max_ms": max(float(np.max(np.abs(b.alignment.residual_ms))) for b in blocks),
            "sensory": sensory(cleaned, t, buzz), "errors": errors(cleaned, t),
            "bads": {m: list(c.bads) for m, c in cleaned.items()},
            "ica": {m: (int(c.ica.n_components_), len(c.ica.exclude)) for m, c in cleaned.items()}}


def summary(c: dict) -> dict:
    """The JSON-safe numbers of compute(), for summary.json."""
    if not c:
        return {}
    g, rt, se, er = c["gaps"], c["rt"], c["sensory"], c["errors"]

    def pct(x, qs=(5, 50, 95)):
        return [round(float(np.percentile(x, q)), 3) for q in qs] if len(x) else []

    def pair(x):
        return [round(float(v), 2) for v in x]

    flash = {kind: {k: pair(se["flash"][kind][k]) for k in ("P1", "N1", "Cz N1", "Cz P2")}
             | {"n": se["flash"][kind]["n"]} for kind in ("random", "pattern")}
    errs = {}
    for kind in ("pattern", "random"):
        e = er[kind]
        errs[kind] = {k: e[k] for k in ("n_error", "of_error", "n_correct", "of_correct")}
        if "ERN" in e:
            errs[kind].update({"ERN": pair(e["ERN"]), "CRN": pair(e["CRN"]),
                               "ern_test": {k: e["ern_test"][k] for k in ("diff", "p")},
                               "pe_test": {k: e["pe_test"][k] for k in ("diff", "p")}})
    return {"counts": [list(r) for r in c["counts"]],
            "by_condition": c["by_condition"], "by_condition_match": c["by_condition_match"],
            "buzz_stages": c["buzz_stages"],
            "timing_ms": {"sd": round(c["timing_sd_ms"], 2), "max": round(c["timing_max_ms"], 2)},
            "timing_halves_ms": {k: pair(v) for k, v in c["timing_halves"].items()},
            "drift_ppm": {k: round(v, 1) for k, v in c["drift_ppm"].items()},
            "queue": c["queue"], "status": c["status"],
            "recordings": {k: [v[0], round(v[1], 1)] for k, v in c["recordings"].items()},
            "gaps_s": {k: pct(v) for k, v in g.items() if k != "flash_vs_log_ms"},
            "flash_vs_log_max_ms": round(c["order"]["gap_max_ms"], 2),
            "rt": {k: (round(v, 5) if isinstance(v, float) else v) for k, v in rt.items()
                   if k not in ("press_minus_log", "byte_minus_log")},
            "order": {k: list(v) if isinstance(v, tuple) else v for k, v in c["order"].items()},
            "sensory": {"flash": flash, "flash_pattern_halves_ms": [pair(h) for h in se["flash"]["halves"]],
                        "buzz": {k: pair(se["buzz"][k]) for k in ("first", "neg", "neg_right")},
                        "kept": {"flash": [se["flash"]["n"], se["flash"]["of"]],
                                 "buzz": [se["buzz"]["n"], se["buzz"]["of"]]}},
            "errors": errs,
            "bads": c["bads"], "ica": c["ica"], "ica_kind": c["ica_kind"]}
