"""Marker checks before any effect is read (Welber Marinovic, 9 October
2026): the markers against the game's own log, the early sensory
responses (fixed, known timing) beside an average at random times, and
the error signal locked to the response. counts(), gaps(), rt_match()
and order() are plain numpy and pandas, so they are tested without MNE.
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
    return {"flash_flash": np.diff(flash)[same],
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


def sensory(cleaned: dict, t: pd.DataFrame, buzz: pd.DataFrame) -> dict:
    """The early responses to the flash (O1/O2), the tone (Cz) and the
    buzz (C3/CP3 against C4/CP4), each with its random-time control."""
    from . import pipeline as P
    out = {}
    raw = cleaned["srt"].raw
    sf = raw.info["sfreq"]
    fl = P.make_epochs(raw, t.flash_sample, np.full(len(t), 30), t, *STIM_WIN, (STIM_WIN[0], 0.0))
    span = t.flash_sample.to_numpy(float) / sf
    rnd = _random(raw, len(t), np.nanmin(span), np.nanmax(span))
    ms = fl.times * 1000
    o, cz = _wave(fl, ["O1", "O2"]), _wave(fl, ["Cz"])
    out["flash"] = {"ms": ms, "O1/O2": o, "Cz": cz, "random O1/O2": _wave(rnd, ["O1", "O2"]),
                    "random Cz": _wave(rnd, ["Cz"]), "n": len(fl), "of": len(t),
                    "kept": fl.metadata.condition.value_counts().to_dict(),
                    "P1": _peak(ms, o, 60, 160, 1), "N1": _peak(ms, o, 120, 220, -1),
                    "Cz N1": _peak(ms, cz, 60, 250, -1), "Cz P2": _peak(ms, cz, 150, 300, 1)}
    raw = cleaned["buzz_hunt"].raw
    sf = raw.info["sfreq"]
    real = buzz[buzz.buzz_sample.notna()].reset_index(drop=True)
    bz = P.make_epochs(raw, real.buzz_sample, np.full(len(real), 38), real, *STIM_WIN,
                       (STIM_WIN[0], 0.0))
    span = real.buzz_sample.to_numpy(float) / sf
    rnd = _random(raw, len(real), span.min(), span.max())
    ms = bz.times * 1000
    c3 = _wave(bz, ["C3", "CP3"])
    out["buzz"] = {"ms": ms, "C3/CP3": c3, "C4/CP4": _wave(bz, ["C4", "CP4"]),
                   "random C3/CP3": _wave(rnd, ["C3", "CP3"]), "n": len(bz), "of": len(real),
                   "first": _peak(ms, c3, 60, 160, 1), "neg": _peak(ms, c3, 150, 400, -1),
                   "neg_right": _peak(ms, _wave(bz, ["C4", "CP4"]), 150, 400, -1)}
    return out


def errors(cleaned: dict, t: pd.DataFrame) -> dict:
    """The error signal (ERN) and correct-response CRN at FCz, and the Pe
    at Pz/CPz, locked to the press each response byte carries."""
    from . import pipeline as P
    from .analyses import perm_diff, window_means
    raw = cleaned["srt"].raw
    use = t.outcome.isin(["correct", "error"]).to_numpy() & np.isfinite(t.press_sample.to_numpy(float))
    tk = t[use].reset_index(drop=True)
    ep = P.make_epochs(raw, tk.press_sample, np.where(tk.outcome == "error", 2, 1), tk, *RESP_WIN,
                       RESP_BASE)
    err, cor = ep[ep.metadata.outcome == "error"], ep[ep.metadata.outcome == "correct"]
    ms = ep.times * 1000
    fe, fc = _wave(err, ["FCz"]), _wave(cor, ["FCz"])
    pe, pc = _wave(err, ["Pz", "CPz"]), _wave(cor, ["Pz", "CPz"])
    ern = perm_diff(window_means(err, (0.0, 0.1), ["FCz"]), window_means(cor, (0.0, 0.1), ["FCz"]))
    pos = perm_diff(window_means(err, (0.2, 0.4), ["Pz", "CPz"]),
                    window_means(cor, (0.2, 0.4), ["Pz", "CPz"]))
    return {"ms": ms, "FCz error": fe, "FCz correct": fc, "Pz/CPz error": pe, "Pz/CPz correct": pc,
            "n_error": len(err), "of_error": int((tk.outcome == "error").sum()),
            "n_correct": len(cor), "of_correct": int((tk.outcome == "correct").sum()),
            "ERN": _peak(ms, fe, -50, 150, -1), "CRN": _peak(ms, fc, -50, 150, -1),
            "ern_test": ern, "pe_test": pos}


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
    return {"counts": counts(t, srt.alignment.pairs.code_eeg, buzz, bh.alignment.pairs.code_eeg),
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
    return {"counts": [list(r) for r in c["counts"]],
            "timing_ms": {"sd": round(c["timing_sd_ms"], 2), "max": round(c["timing_max_ms"], 2)},
            "gaps_s": {k: pct(v) for k, v in g.items() if k != "flash_vs_log_ms"},
            "flash_vs_log_max_ms": round(c["order"]["gap_max_ms"], 2),
            "rt": {k: (round(v, 5) if isinstance(v, float) else v) for k, v in rt.items()
                   if k not in ("press_minus_log", "byte_minus_log")},
            "order": {k: list(v) if isinstance(v, tuple) else v for k, v in c["order"].items()},
            "sensory": {"flash": {k: [round(x, 1) for x in se["flash"][k]]
                                  for k in ("P1", "N1", "Cz N1", "Cz P2")},
                        "buzz": {k: [round(x, 1) for x in se["buzz"][k]]
                                 for k in ("first", "neg", "neg_right")},
                        "kept": {"flash": [se["flash"]["n"], se["flash"]["of"]],
                                 "buzz": [se["buzz"]["n"], se["buzz"]["of"]]}},
            "errors": {"ERN": [round(x, 2) for x in er["ERN"]], "CRN": [round(x, 2) for x in er["CRN"]],
                       "kept": {"error": [er["n_error"], er["of_error"]],
                                "correct": [er["n_correct"], er["of_correct"]]},
                       "ern_test": {k: er["ern_test"][k] for k in ("diff", "p")},
                       "pe_test": {k: er["pe_test"][k] for k in ("diff", "p")}},
            "bads": c["bads"], "ica": c["ica"]}
