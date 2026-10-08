"""Loading, cleaning and epoching a BioSemi recording with MNE-Python.

Every parameter sits at the top with its reason, so the methods text
can quote them and a rerun lands on the same numbers. The order is the
usual one for ERP work: the reference-free BioSemi data get their eye
channels and an average reference, line noise and slow drift are
filtered, blinks and eye movements are removed by ICA fitted on a 1 Hz
high-passed copy, and only then are trials cut and averaged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

import mne

from .align import Alignment, align, shifted_samples, wire_rows

# ---- parameters ----------------------------------------------------------
LINE_HZ = 50.0          # Australian mains, and its harmonic below Nyquist
HP_ERP = 0.1            # ERP high-pass: higher cut-offs distort slow ERPs
LP_ERP = 40.0           # ERP low-pass: keeps the components, drops EMG and hum
ICA_HP = 1.0            # ICA is fitted on a 1 Hz high-passed copy
ICA_LP = 40.0
ICA_VARIANCE = 0.99     # keep components explaining 99 percent of variance
ICA_SEED = 97
EOG_Z = 3.0             # |z| of a component's correlation with an eye channel
REJECT_UV = 150.0       # peak-to-peak limit for an epoch after ICA
FLAT_UV = 0.5           # a channel quieter than this (1-40 Hz SD) is flat
NOISE_Z = 5.0           # z of 55-95 Hz power (cap median and MAD) that marks a noisy channel
NEIGHBOUR_R = 0.4       # minimum correlation with the channel's neighbours
MONTAGE = "biosemi64"

# The two connected external electrodes, worked out from the signals
# (blink polarity and the horizontal F7/F8 pattern) because the lab
# sheet was not with the data: EXG1 sat under the right eye, EXG2 at the
# left outer canthus. EXG3 to EXG8 read one identical saturated value,
# so they were not plugged in.
EOG_BELOW = "EXG1"
EOG_CANTHUS = "EXG2"


@dataclass
class Cleaned:
    raw: mne.io.BaseRaw               # 0.1-40 Hz, average reference, ICA applied
    raw_ica_fit: mne.io.BaseRaw       # the 1-40 Hz copy ICA was fitted on
    ica: mne.preprocessing.ICA
    bads: list[str]
    bad_reasons: dict[str, str]
    eog_scores: dict[str, list[float]]
    unconnected: list[str]
    blinks_per_min: float
    psd_before: tuple[np.ndarray, np.ndarray]   # freqs, mean power (uV^2/Hz)
    psd_after: tuple[np.ndarray, np.ndarray]
    notes: list[str] = field(default_factory=list)


def read(bdf: Path) -> mne.io.BaseRaw:
    raw = mne.io.read_raw_bdf(bdf, preload=True, verbose="ERROR")
    return raw


def unconnected_exg(raw: mne.io.BaseRaw) -> list[str]:
    """External inputs with nothing plugged in: BioSemi reads them at a
    fixed, saturated offset (hundreds of mV) that is the same on every
    open input."""
    out = []
    for ch in raw.ch_names:
        if not ch.startswith("EXG"):
            continue
        x = raw.get_data(picks=[ch])[0]
        if abs(np.median(x)) > 0.1:      # volts: over 100 mV of offset
            out.append(ch)
    return out


def events(raw: mne.io.BaseRaw) -> np.ndarray:
    """Rising edges of the trigger byte, the low 8 bits of Status."""
    return mne.find_events(raw, stim_channel="Status", mask=0xFF,
                           mask_type="and", shortest_event=1,
                           consecutive=True, verbose="ERROR")


def pulse_widths_ms(raw: mne.io.BaseRaw) -> np.ndarray:
    st = raw.get_data(picks=["Status"])[0].astype(np.int64) & 0xFF
    on = np.flatnonzero(np.diff((st > 0).astype(int)) == 1) + 1
    off = np.flatnonzero(np.diff((st > 0).astype(int)) == -1) + 1
    if len(off) and len(on) and off[0] < on[0]:
        off = off[1:]
    k = min(len(on), len(off))
    return (off[:k] - on[:k]) / raw.info["sfreq"] * 1000.0


def _neighbour_r(raw: mne.io.BaseRaw, x: np.ndarray) -> np.ndarray:
    """Each channel's correlation with the mean of its nearest
    neighbours on the cap."""
    pos = np.array([raw.info["chs"][i]["loc"][:3]
                    for i in mne.pick_types(raw.info, eeg=True)])
    d = np.linalg.norm(pos[:, None] - pos[None], axis=2)
    r = np.empty(len(x))
    for i in range(len(x)):
        nb = np.argsort(d[i])[1:5]
        r[i] = np.corrcoef(x[i], x[nb].mean(0))[0, 1]
    return r


def find_bad_channels(raw: mne.io.BaseRaw) -> dict[str, str]:
    """Flat, noisy or uncorrelated scalp channels. Variance alone would
    flag the frontopolar sites for every blink, so the checks are flat
    signal, high-frequency noise against the cap's median, and
    correlation with the channel's neighbours."""
    eeg = raw.copy().pick("eeg")
    names = eeg.ch_names
    x = eeg.copy().filter(1.0, 40.0, verbose="ERROR").get_data() * 1e6
    sd = x.std(1)
    hf = eeg.copy().filter(55.0, 95.0, verbose="ERROR").get_data() * 1e6
    lhf = np.log(hf.std(1))
    med = np.median(lhf)
    mad = np.median(np.abs(lhf - med)) * 1.4826 or 1.0
    z = (lhf - med) / mad
    r = _neighbour_r(eeg, x)
    out: dict[str, str] = {}
    for i, ch in enumerate(names):
        if sd[i] < FLAT_UV:
            out[ch] = f"flat ({sd[i]:.2f} uV)"
        elif z[i] > NOISE_Z:
            out[ch] = f"noisy above 55 Hz (z {z[i]:.1f} from the cap median)"
        elif r[i] < NEIGHBOUR_R:
            out[ch] = f"unlike its neighbours (r {r[i]:.2f})"
    return out


def _mean_psd(raw: mne.io.BaseRaw, fmax: float = 120.0):
    p = raw.compute_psd(method="welch", fmin=0.5, fmax=fmax, picks="eeg",
                        n_fft=int(4 * raw.info["sfreq"]), verbose="ERROR")
    return p.freqs, p.get_data().mean(0) * 1e12


def _blink_rate(raw: mne.io.BaseRaw) -> float:
    from scipy.signal import find_peaks
    v = raw.copy().pick(["VEOG"]).filter(0.5, 10.0, picks="all",
                                         verbose="ERROR").get_data()[0] * 1e6
    thr = max(80.0, np.percentile(np.abs(v), 99.0))
    pk, _ = find_peaks(np.abs(v), height=thr,
                       distance=int(0.4 * raw.info["sfreq"]))
    return len(pk) / (raw.times[-1] / 60.0)


def clean(raw_in: mne.io.BaseRaw) -> Cleaned:
    raw = raw_in.copy()
    unconnected = unconnected_exg(raw)
    raw.drop_channels(unconnected)
    raw = mne.set_bipolar_reference(raw, anode=["Fp2", EOG_CANTHUS],
                                    cathode=[EOG_BELOW, "F8"],
                                    ch_name=["VEOG", "HEOG"],
                                    drop_refs=False, verbose="ERROR")
    raw.set_channel_types({"VEOG": "eog", "HEOG": "eog",
                           EOG_BELOW: "misc", EOG_CANTHUS: "misc"},
                          verbose="ERROR")
    raw.set_montage(MONTAGE, on_missing="ignore", verbose="ERROR")
    raw.set_eeg_reference("average", projection=False, verbose="ERROR")
    psd_before = _mean_psd(raw)
    freqs = [f for f in (LINE_HZ, 2 * LINE_HZ)
             if f < raw.info["sfreq"] / 2 - 5]
    raw.notch_filter(freqs, picks=["eeg", "eog"], verbose="ERROR")
    bad = find_bad_channels(raw)
    raw.info["bads"] = list(bad)
    fit = raw.copy().filter(ICA_HP, ICA_LP, picks=["eeg", "eog"],
                            verbose="ERROR")
    ica = mne.preprocessing.ICA(n_components=ICA_VARIANCE, method="picard",
                                fit_params=dict(ortho=False, extended=True),
                                random_state=ICA_SEED, max_iter="auto",
                                verbose="ERROR")
    ica.fit(fit, picks="eeg", decim=2, verbose="ERROR")
    scores = {}
    excl: set[int] = set()
    for ch in ("VEOG", "HEOG"):
        idx, sc = ica.find_bads_eog(fit, ch_name=ch, threshold=EOG_Z,
                                    measure="zscore", verbose="ERROR")
        scores[ch] = [float(s) for s in np.atleast_1d(sc)]
        excl.update(int(i) for i in idx)
    ica.exclude = sorted(excl)
    blinks = _blink_rate(raw)
    out = raw.copy().filter(HP_ERP, LP_ERP, picks=["eeg", "eog"],
                            verbose="ERROR")
    ica.apply(out, verbose="ERROR")
    if out.info["bads"]:
        out.interpolate_bads(reset_bads=True, verbose="ERROR")
    psd_after = _mean_psd(out)
    return Cleaned(raw=out, raw_ica_fit=fit, ica=ica, bads=list(bad),
                   bad_reasons=bad, eog_scores=scores,
                   unconnected=unconnected, blinks_per_min=blinks,
                   psd_before=psd_before, psd_after=psd_after)


# ---- pairing the recording with a game block ------------------------------
@dataclass
class Block:
    """One game block and its recording, paired."""
    name: str
    mode: str
    folder: Path
    bdf: Path
    raw: mne.io.BaseRaw
    eeg_events: np.ndarray
    alignment: Alignment
    trials: pd.DataFrame
    widths_ms: np.ndarray


BLOCK_CODES = {213: "srt", 210: "buzz_hunt"}


def pair(sessions: Path) -> list[Block]:
    """Every recording in sessions/eeg paired with the game block whose
    wire rows match its markers code for code."""
    recordings = sorted((sessions / "eeg").glob("*.bdf"))
    folders = [p.parent for p in sessions.glob("*/*/events.tsv")]
    logs = {f: wire_rows(pd.read_csv(f / "events.tsv", sep="\t",
                                     na_values="n/a")) for f in folders}
    blocks = []
    for bdf in recordings:
        raw = read(bdf)
        ev = events(raw)
        best = None
        for f, g in logs.items():
            a = align(ev[:, 0], ev[:, 2], raw.info["sfreq"], g)
            if best is None or a.matched > best[1].matched:
                best = (f, a)
        if best is None or best[1].matched == 0:
            continue
        f, a = best
        mode = next((BLOCK_CODES[c] for c in ev[:, 2] if c in BLOCK_CODES),
                    f.name.split("_", 2)[-1])
        trials = pd.read_csv(f / "trials.csv")
        blocks.append(Block(name=f.name, mode=mode, folder=f, bdf=bdf,
                            raw=raw, eeg_events=ev, alignment=a,
                            trials=trials, widths_ms=pulse_widths_ms(raw)))
    return blocks


# ---- SRT trials ------------------------------------------------------------
def srt_trials(block: Block) -> pd.DataFrame:
    """One row per SRT trial: the script-format file's columns, the flash
    sample and the response sample, the latter at the press and at the
    force onset."""
    script = sorted(p for p in block.folder.glob("SRT_*.csv")
                    if not p.name.startswith(("SRT_SEQUENCE_", "SRT_RECALL_")))
    t = pd.read_csv(script[0])
    pairs = block.alignment.pairs
    sf = block.raw.info["sfreq"]
    flash = pairs[pairs.code_eeg == 30].reset_index(drop=True)
    resp = pairs[(pairs.code_eeg >= 100) & (pairs.code_eeg <= 131)
                 ].reset_index(drop=True)
    n = min(len(t), len(flash), len(resp))
    t = t.iloc[:n].copy()
    t["flash_sample"] = np.round(flash.eeg_s[:n].to_numpy() * sf).astype(int)
    t["resp_code"] = resp.code_eeg[:n].to_numpy()
    t["press_sample"] = shifted_samples(resp.iloc[:n], sf, "press_offset_ms")
    t["onset_sample"] = shifted_samples(resp.iloc[:n], sf, "onset_offset_ms")
    t["rise_ms"] = (pd.to_numeric(resp.press_offset_ms[:n], errors="coerce")
                    - pd.to_numeric(resp.onset_offset_ms[:n], errors="coerce")
                    ).to_numpy()
    t["condition"] = "other"
    t.loc[t.phase == "practice", "condition"] = "random_practice"
    t.loc[(t.phase == "learning") & t.block.isin([1, 2]), "condition"] = "sequence_early"
    t.loc[(t.phase == "learning") & t.block.isin([3, 4, 5, 6]), "condition"] = "sequence_middle"
    t.loc[(t.phase == "learning") & t.block.isin([7, 8]), "condition"] = "sequence_late"
    t.loc[t.phase == "posttest", "condition"] = "random_posttest"
    t["outcome"] = t.accuracy.map({
        "correct": "correct", "incorrect": "error",
        "anticipatory_correct": "anticipation",
        "anticipatory_incorrect": "anticipation",
        "miss": "miss", "too_early": "anticipation"}).fillna("other")
    return t


def make_epochs(raw: mne.io.BaseRaw, samples, codes, meta: pd.DataFrame,
                tmin: float, tmax: float, baseline,
                reject: bool = True) -> mne.Epochs:
    ok = np.isfinite(np.asarray(samples, dtype=float))
    ev = np.column_stack([np.asarray(samples)[ok].astype(int),
                          np.zeros(ok.sum(), dtype=int),
                          np.asarray(codes)[ok].astype(int)])
    md = meta.loc[ok].reset_index(drop=True)
    ep = mne.Epochs(raw, ev, event_id=None, tmin=tmin, tmax=tmax,
                    baseline=baseline, metadata=md, preload=True,
                    reject=dict(eeg=REJECT_UV * 1e-6) if reject else None,
                    picks=["eeg", "eog"], event_repeated="drop",
                    verbose="ERROR")
    return ep


def map_game_times(block: Block, t_game) -> np.ndarray:
    """Game perf_counter times to recording samples."""
    sf = block.raw.info["sfreq"]
    return np.round(block.alignment.to_eeg_seconds(t_game) * sf)
