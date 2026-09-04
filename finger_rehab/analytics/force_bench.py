"""Rayan's sensor bench analyses, ported from R and Python.

Rayan Ahmed characterised the SingleTact pads with a set of R scripts
and one Python script, left in bin/old_rayyan_stuff/data. They are the
only written record of how these sensors behave, and Welber's earlier
sessions were processed with the same detector, so the numbers have to
stay comparable rather than be reinterpreted. This module is that work
as pure functions: give each one a dataframe, get a dataframe back.
Nothing here reads a config, opens a port or touches the engine.

Every analysis function names the file it came from in its docstring:

    Max_Peak_Analysis.R                       stim_peaks, peak_summary
    Noise_Analysis.R                          baseline_noise, snr_summary
    repeatability.R                           repeatability
    analyze_baseline_drift.R                  response_waveforms
    analyze_baseline_drift_modified.R         stim_response_levels,
                                              baseline_shift
    analyze_baseline_drift_modified_newtons.R drift_newtons
    raw/process_force_peaks.py                processed_peaks
    raw/FingerRawforEachBlock.R               block_slices,
                                              plot_trial_peaks
    Data_analysis_Final.R                     block_table, block_model

Two log layouts go in, one set of frames comes out:

  His bench logs. Event rows carry the sensor value, the pads idle at a
  flat 255 counts, only fsr1 was wired, response events are "resp" or
  "resp_early_correct", and the trial number sits in detail as
  "trial=N". Load with `load_bench_raw`, scan with rows="all", offset
  RAYAN_STATIC_OFFSET.

  Our session logs. Event rows hold zeros in the fsr cells, so force is
  only ever read off sample rows; eight pads, each idling somewhere
  between 250 and 320 counts; the press event is "press"; the trial
  number is "trial_id=N". Load with `load_session_raw`, scan with
  rows="samples", offset from `resting_offsets`.

Sample rate is the other split. His stream is clean, so the median gap
between samples is the rate. Ours arrives in bursts (one serial read
delivers several samples stamped microseconds apart), which makes the
median gap far too short, so the rate is the sample count over the time
span. `estimate_fs` takes the mode; the choice matters because it sets
the filter cutoffs inside the onset detector, and on his file the two
rates move 39 of 514 onsets by up to 5.8 ms.

Units. Raw counts are not comparable between pads. His flat 51.2 counts
per newton is 512 counts over the 10 N rating from the SingleTact
manual, which is the right conversion for an uncalibrated part; a
session that carries fsr.force_calibration_n_per_count should use that
instead and pass it in.

The plotting helpers redraw his figures in the house style and return
the figure without saving it, so a notebook, a script or a test can
decide where it goes.
"""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

from finger_rehab.analytics.signal import lookback_baseline, teasdale_onset


# ---------------------------------------------------------------- constants

# His parameters, kept at his values so the ported numbers match his
# output CSVs. Changing one of these changes what the analysis means,
# so they are named rather than typed into the functions.
RAYAN_STATIC_OFFSET = 255.0      # his rigs idle level, subtracted flat
RAYAN_COUNTS_PER_NEWTON = 51.2   # 512 counts over the 10 N rating
PEAK_WINDOW_S = 1.2              # peak search: stim to stim + 1.2 s
NOISE_EXCLUDE_S = (0.2, 1.5)     # rest = outside stim - 0.2 s to + 1.5 s
SEGMENT_TRIALS = 50              # repeatability segment, stims per lane
SHORT_SEGMENT_TRIALS = 10        # our blocks are 20 to 50 trials, not 600
LOOKBACK_ROWS = 50               # 250 ms at 200 Hz, his local zero
CHUNK_TRIALS = 100               # main block split into chunks of 100
RT_MIN_MS = 0.0                  # his rt_min
RT_MAX_MS = 1000.0               # his rt_max
ONSET_PRE_S = 0.05               # his segment start, 50 ms before the cue
WAVEFORM_DOTS_MS = (50, 100, 150, 200, 250, 300, 350, 400)

# SingleTact scale, from the manual (V3.1, sections 2.4.3 and 2.6): the
# output register is 10-bit, zero load sits near 0x100 = 256 counts and
# the rating at 0x2FF = 767, so the span from zero load to the rating is
# 512 counts. Anything at or above the rating is past the part's linear
# range, and the ADC itself stops at 1023.
SINGLETACT_FULL_SCALE_COUNTS = 512
SINGLETACT_ADC_CEILING = 1020
SINGLETACT_RATING_N = 10.0

FINGERS = ("Index", "Middle", "Ring", "Pinky")

# The notebook palette, so a figure from here sits beside a figure from
# analysis/session_analysis.ipynb without the colours changing meaning.
FINGER_COLOUR = {"Index": "#ea580c", "Middle": "#0ea5e9",
                 "Ring": "#0f172a", "Pinky": "#ca8a04"}
HAND_COLOUR = {"right": "#2563eb", "left": "#a855f7"}
STIM_COLOUR = "#1565C0"          # his blue for a cue
RESPONSE_COLOUR = "#C62828"      # his red for a press
DOT_COLOUR = "#2E7D32"           # his green look-back dots
TRACE_COLOUR = "#94a3b8"

_FSR_RE = re.compile(r"fsr\d+$", re.I)
_RESPONSE_RE = re.compile(r"resp|press|response|key")
_TRIAL_RE = re.compile(r"trial(?:_id)?\s*=\s*(\d+)", re.I)


def fsr_columns(frame: pd.DataFrame) -> list[str]:
    """The fsr1..fsrN columns present, in numeric order."""
    cols = [c for c in frame.columns if _FSR_RE.fullmatch(str(c))]
    return sorted(cols, key=lambda c: int(str(c)[3:]))


def lane_column(lane: int) -> str:
    """Lane 0 is fsr1. His lanes are 0-based on raw.csv and so are ours
    (trials.csv is the +1 copy), so the same rule covers both."""
    return f"fsr{int(lane) + 1}"


def lane_finger(lane: int) -> str:
    """Index, Middle, Ring or Pinky. Lanes 4 to 7 are the left hand's
    copy of the same four fingers."""
    return FINGERS[int(lane) % 4]


def lane_side(lane: int, hand_mode: str = "right") -> str:
    """Which hand a lane belongs to. Lanes 0 to 3 are the right board
    and 4 to 7 the left, except in a one-handed left session where the
    only board in use is the left one and it still writes lanes 0 to 3.
    """
    if int(lane) >= 4:
        return "left"
    return "left" if str(hand_mode).lower() == "left" else "right"


def parse_trial(detail, fallback=None):
    """Trial number out of an event's detail cell. His logger wrote
    "trial=7" and ours writes "trial_id=7", so one pattern reads both.
    Returns `fallback` when the cell holds neither, which is what the
    stim-order numbering falls back to."""
    match = _TRIAL_RE.search(str(detail or ""))
    return int(match.group(1)) if match else fallback


# ------------------------------------------------------------------ loading

def _numeric(frame: pd.DataFrame, columns) -> pd.DataFrame:
    for col in columns:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")
    return frame


def load_bench_raw(path) -> pd.DataFrame:
    """One of Rayan's bench streams from bin/old_rayyan_stuff/data/raw.

    Read as he wrote it: event rows keep their sensor values, events are
    lower-cased and trimmed so "Stim" and "stim " both match, and lane
    stays 0-based. Reads a .csv or a .csv.gz, because the 7.4 MB stream
    is stored gzipped in tests/fixtures/rayan to keep the repository
    small (pandas decompresses by extension).
    """
    frame = pd.read_csv(path, low_memory=False)
    frame = _numeric(frame, ["t_perf", "lane", "sample_idx",
                             *fsr_columns(frame)])
    frame["event"] = (frame.get("event", "").fillna("")
                      .astype(str).str.strip().str.lower())
    return frame.reset_index(drop=True)


def load_bench_trials(paths) -> pd.DataFrame:
    """His per-trial logs stacked, with the source file kept.

    Data_analysis_Final.R reads every trial CSV in the folder and adds a
    source_file column, then recodes "aftertest" to "posttest"; the
    dedupe and the chunk numbering below are per source file, so the
    column has to survive the stack.
    """
    frames = []
    for path in paths:
        frame = pd.read_csv(path, low_memory=False)
        frame["source_file"] = Path(path).name
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    stacked = pd.concat(frames, ignore_index=True)
    stacked["block"] = stacked["block"].replace({"aftertest": "posttest"})
    return stacked


def load_session_raw(folder) -> pd.DataFrame | None:
    """One of our session folders' raw.csv, or None when there is none.

    A block played on the keyboard has no sample rows at all (there is
    no device to sample), so callers get an empty force stream rather
    than an exception; every analysis here checks for that.
    """
    path = Path(folder) / "raw.csv" if Path(folder).is_dir() else Path(folder)
    if not path.exists():
        return None
    frame = pd.read_csv(path, low_memory=False)
    frame = _numeric(frame, ["t_perf", "lane", "sample_idx",
                             *fsr_columns(frame)])
    frame["event"] = (frame.get("event", "").fillna("")
                      .astype(str).str.strip().str.lower())
    return frame.reset_index(drop=True)


def event_kinds(raw: pd.DataFrame) -> pd.DataFrame:
    """Stim and response rows with their original row index kept.

    His scripts classify by regular expression: "stim" is a cue, and
    anything matching resp|press|response|key is a response. That single
    rule covers his "resp" and "resp_early_correct" and our "press",
    which is why it is worth keeping rather than listing event names.
    The row index is kept because his look-back indexes into the whole
    frame, event rows included.
    """
    events = raw[raw["event"] != ""].copy()
    if events.empty:
        return events.assign(kind=pd.Series(dtype=object),
                            row=pd.Series(dtype=int))
    events["kind"] = np.where(
        events["event"] == "stim", "Stim",
        np.where(events["event"].str.contains(_RESPONSE_RE), "Response", ""))
    events = events[events["kind"] != ""].copy()
    events["row"] = events.index.to_numpy()
    return events


def sample_rows(raw: pd.DataFrame) -> pd.DataFrame:
    """The force stream: rows with no event on them.

    His loader also accepts a literal "sample" in the event column, so
    both spellings are treated as a plain sample.
    """
    keep = raw["event"].isin(["", "sample"])
    return raw[keep].dropna(subset=["t_perf"]).sort_values(
        "t_perf", kind="stable")


def estimate_fs(t, mode: str = "span") -> float:
    """Sample rate in Hz from a vector of timestamps.

    mode "median" is his estimate_fs: one over the median gap between
    samples. mode "span" is sample count over elapsed time, which is
    what our logs need because the serial reader delivers a burst of
    samples stamped microseconds apart and the median gap then reads as
    a rate several times the real one. On his clean stream the two
    agree to about 2 percent (195.66 against 199.67 Hz).
    """
    t = np.asarray(t, dtype=float)
    t = t[np.isfinite(t)]
    if len(t) < 2:
        return float("nan")
    if mode == "median":
        gaps = np.diff(t)
        gaps = gaps[(gaps > 0) & np.isfinite(gaps)]
        return float(1.0 / np.median(gaps)) if len(gaps) else float("nan")
    span = float(t[-1] - t[0])
    return (len(t) - 1) / span if span > 0 else float("nan")


def resting_offsets(raw: pd.DataFrame, min_samples: int = 20) -> dict:
    """Per pad, the level it rests at, standing in for his flat 255.

    His rig idled at 255 counts on every pad, so he subtracted that
    constant. Ours do not: each pad sits somewhere between 250 and 320
    depending on how the finger cup is done up, and the level drifts
    over a session. The resting level here is the median of the samples
    before the first cue, which is the same rule the notebook's drift
    chapter uses; with fewer than `min_samples` of those (a block that
    starts cueing immediately) it falls back to the 5th percentile of
    the whole stream, which is the pad at rest between presses.
    """
    samples = sample_rows(raw)
    stims = raw[raw["event"] == "stim"].dropna(subset=["t_perf"])
    if samples.empty:
        return {}
    t = samples["t_perf"].to_numpy(dtype=float)
    t0 = float(stims["t_perf"].min()) if len(stims) else float(t[0])
    out = {}
    for col in fsr_columns(samples):
        values = pd.to_numeric(samples[col], errors="coerce").to_numpy(float)
        pre = values[(t < t0) & np.isfinite(values)]
        if len(pre) >= min_samples:
            out[col] = float(np.median(pre))
        elif np.isfinite(values).any():
            out[col] = float(np.nanquantile(values, 0.05))
        else:
            out[col] = float("nan")
    return out


# ----------------------------------------------------- peak, noise, SNR, CV

def stim_peaks(raw: pd.DataFrame, offset=RAYAN_STATIC_OFFSET,
               window_s: float = PEAK_WINDOW_S, rows: str = "all",
               max_lane: int = 7) -> pd.DataFrame:
    """Peak of the cued pad in the window after every cue.

    The front end of three of his scripts (Max_Peak_Analysis.R,
    Noise_Analysis.R and repeatability.R all rebuild this same frame).
    For each stim row that names a lane, take the maximum of that lane's
    sensor over [t_stim, t_stim + window_s] and subtract the pad's
    offset.

    `offset` is either the flat RAYAN_STATIC_OFFSET or a dict of
    per-pad resting levels from `resting_offsets`. `rows="all"` scans
    every row, which is his convention and only correct when event rows
    carry sensor values; `rows="samples"` scans the force stream alone,
    which is what our logs need because our event rows hold zeros and
    would drag every peak down to the offset.

    One row per cue: trial (from the detail cell, else cue order),
    stim_order (1-based cue order, the only safe key across his files
    because his trial numbers restart per block), t_stim, lane, sensor,
    peak_counts above the offset, and raw_peak for the saturation checks.
    """
    columns = ["trial", "stim_order", "t_stim", "lane", "sensor",
               "peak_counts", "raw_peak", "offset"]
    scan = raw if rows == "all" else sample_rows(raw)
    scan = scan.dropna(subset=["t_perf"]).sort_values("t_perf", kind="stable")
    stims = (raw[(raw["event"] == "stim") & raw["lane"].notna()]
             .dropna(subset=["t_perf"]).sort_values("t_perf", kind="stable"))
    if scan.empty or stims.empty:
        return pd.DataFrame(columns=columns)
    t = scan["t_perf"].to_numpy(dtype=float)
    values = {col: pd.to_numeric(scan[col], errors="coerce").to_numpy(float)
              for col in fsr_columns(scan)}
    offsets = offset if isinstance(offset, dict) else None
    out = []
    for order, (_, stim) in enumerate(stims.iterrows(), start=1):
        lane = int(stim["lane"])
        if lane > max_lane:
            continue
        col = lane_column(lane)
        if col not in values:
            continue
        t0 = float(stim["t_perf"])
        lo = int(np.searchsorted(t, t0, side="left"))
        hi = int(np.searchsorted(t, t0 + window_s, side="right"))
        window = values[col][lo:hi]
        window = window[np.isfinite(window)]
        if not len(window):
            continue
        zero = float(offsets.get(col, np.nan)) if offsets is not None \
            else float(offset)
        raw_peak = float(np.max(window))
        out.append({"trial": parse_trial(stim.get("detail"), order),
                    "stim_order": order, "t_stim": t0, "lane": lane,
                    "sensor": col, "peak_counts": raw_peak - zero,
                    "raw_peak": raw_peak, "offset": zero})
    return pd.DataFrame(out, columns=columns)


def peak_summary(peaks: pd.DataFrame) -> pd.DataFrame:
    """Max_Peak_Analysis.R: the biggest and the average peak per pad.

    His output CSV (Peak Analysis/overall_peak_force_summary.csv) has
    the columns sensor, overall_max_peak, overall_avg_peak, n_presses,
    with the sensor written FS1 to FS4. Reproduced here so a run can be
    compared against his file directly.
    """
    columns = ["sensor", "overall_max_peak", "overall_avg_peak", "n_presses"]
    if peaks.empty:
        return pd.DataFrame(columns=columns)
    group = peaks.groupby("lane")["peak_counts"]
    out = pd.DataFrame({"overall_max_peak": group.max(),
                        "overall_avg_peak": group.mean(),
                        "n_presses": group.count()}).reset_index()
    out["sensor"] = "FS" + (out["lane"].astype(int) + 1).astype(str)
    return out[columns]


def baseline_noise(raw: pd.DataFrame, offset=RAYAN_STATIC_OFFSET,
                   exclude=NOISE_EXCLUDE_S, rows: str = "samples"
                   ) -> pd.DataFrame:
    """Noise_Analysis.R: how much each pad wanders while nothing presses.

    Rest is every sample row that falls outside [cue - 0.2 s,
    cue + 1.5 s] of every cue, so the press and its tail are cut out and
    what remains is the pad sitting still. Noise is the standard
    deviation of that (sample sd, ddof 1, as R's sd does). The offset
    cancels inside a standard deviation, so it is only carried here to
    keep the column readable next to the peaks.

    Returns one row per pad: sensor, baseline_noise_sd, n_rest_samples.
    """
    columns = ["sensor", "baseline_noise_sd", "n_rest_samples"]
    base = raw if rows == "all" else sample_rows(raw)
    cols = fsr_columns(base)
    base = base.dropna(subset=["t_perf", *cols])
    if base.empty:
        return pd.DataFrame(columns=columns)
    t = base["t_perf"].to_numpy(dtype=float)
    keep = np.ones(len(t), dtype=bool)
    stim_t = (raw.loc[raw["event"] == "stim", "t_perf"]
              .dropna().to_numpy(dtype=float))
    for cue in stim_t:
        keep &= ~((t >= cue - exclude[0]) & (t <= cue + exclude[1]))
    rest = base[keep]
    out = []
    for col in cols:
        values = pd.to_numeric(rest[col], errors="coerce")
        values = values[np.isfinite(values)]
        out.append({"sensor": col,
                    "baseline_noise_sd": (float(values.std(ddof=1))
                                          if len(values) > 2
                                          else float("nan")),
                    "n_rest_samples": int(len(values))})
    return pd.DataFrame(out, columns=columns)


def snr_summary(peaks: pd.DataFrame, noise: pd.DataFrame) -> pd.DataFrame:
    """Noise_Analysis.R: mean peak over the pad's own noise floor.

    Signal is the average peak of that pad's cued presses, noise its
    resting standard deviation, and the ratio is unitless, which is the
    point: raw counts are not comparable between pads, but a signal to
    noise ratio is, because both halves were measured on the same pad.

    His output CSV (Noise Analysis/grand_average_snr_summary.csv) has
    sensor, grand_avg_signal, grand_avg_noise, grand_snr, with the
    sensor written FS1 to FS4.
    """
    columns = ["sensor", "grand_avg_signal", "grand_avg_noise", "grand_snr"]
    if peaks.empty or noise.empty:
        return pd.DataFrame(columns=columns)
    signal = (peaks.groupby("lane")["peak_counts"].mean()
              .rename("grand_avg_signal").reset_index())
    signal["fsr"] = signal["lane"].map(lane_column)
    out = signal.merge(noise.rename(columns={"sensor": "fsr"}), on="fsr",
                       how="left")
    out["grand_avg_noise"] = out["baseline_noise_sd"]
    out["grand_snr"] = out["grand_avg_signal"] / out["grand_avg_noise"]
    out["sensor"] = "FS" + (out["lane"].astype(int) + 1).astype(str)
    return out[columns]


def repeatability(peaks: pd.DataFrame, segment: int = SEGMENT_TRIALS
                  ) -> pd.DataFrame:
    """repeatability.R: does the same finger press the same each time.

    Peaks are cut into consecutive segments of `segment` cues per lane
    in the order they were logged, and each segment gets a mean, a
    sample sd and a coefficient of variation (100 sd / mean). The CV is
    the repeatability number: a low CV with a steady mean is a stable
    pad, a low CV with a climbing mean is a participant pressing harder,
    and a high CV is the pad or the finger placement moving.

    Hopkins (2000), Measures of reliability in sports medicine and
    science, Sports Medicine 30(1):1-15, is the reference for reading a
    CV as a repeatability measure.

    Columns: lane, segment, n, mean_force, sd_force, cv_percent.
    """
    columns = ["lane", "segment", "n", "mean_force", "sd_force", "cv_percent"]
    if peaks.empty:
        return pd.DataFrame(columns=columns)
    frame = peaks.sort_values(["lane", "stim_order"], kind="stable").copy()
    frame["segment"] = frame.groupby("lane").cumcount() // int(segment) + 1
    group = frame.groupby(["lane", "segment"])["peak_counts"]
    out = pd.DataFrame({"n": group.count(), "mean_force": group.mean(),
                        "sd_force": group.std(ddof=1)}).reset_index()
    out["cv_percent"] = 100.0 * out["sd_force"] / out["mean_force"]
    return out[columns]


def segment_length(peaks: pd.DataFrame, segment: int | None = None) -> int:
    """How many cues to put in a repeatability segment.

    His bench run was 600 presses of one finger, so segments of 50 gave
    him twelve points to plot. Our blocks are 20 to 50 trials spread
    over four fingers, and segments of 50 would collapse every lane into
    one point with nothing to compare it against, so a short block drops
    to segments of 10.
    """
    if segment:
        return int(segment)
    if peaks.empty:
        return SEGMENT_TRIALS
    smallest = int(peaks.groupby("lane").size().min())
    return SEGMENT_TRIALS if smallest >= 2 * SEGMENT_TRIALS \
        else SHORT_SEGMENT_TRIALS


def saturation(peaks: pd.DataFrame) -> dict:
    """How many presses ran past the part's usable range.

    Above the rating (512 counts over zero load, 0x2FF on the SingleTact
    scale) the reading is no longer linear, and at the ADC ceiling it is
    simply clipped. Both matter for a mean or a CV taken over those
    presses: a clipped peak understates the force and overstates the
    consistency, so the count belongs beside every summary table.
    """
    if peaks.empty:
        return {"over_rating": 0, "at_ceiling": 0}
    return {
        "over_rating": int((peaks["peak_counts"]
                            >= SINGLETACT_FULL_SCALE_COUNTS).sum()),
        "at_ceiling": int((peaks["raw_peak"]
                           >= SINGLETACT_ADC_CEILING).sum()),
    }


def counts_to_newtons(counts, n_per_count: float | None = None):
    """Counts above the pad's rest level into newtons.

    Default is his 51.2 counts per newton, which is the manual's
    conversion for an uncalibrated 10 N part (512 counts over the
    rating). A session that recorded fsr.force_calibration_n_per_count
    should pass that instead, because a calibrated pad has its own
    constant and the flat one will be out by whatever the calibration
    corrected for.
    """
    per_count = (1.0 / RAYAN_COUNTS_PER_NEWTON) if n_per_count is None \
        else float(n_per_count)
    return np.asarray(counts, dtype=float) * per_count


# ------------------------------------------------------------ baseline drift

def stim_response_levels(raw: pd.DataFrame, sensor: str,
                         offset=RAYAN_STATIC_OFFSET, rows: str = "all"
                         ) -> pd.DataFrame:
    """analyze_baseline_drift_modified.R: the pad's level at each event.

    Two series against time: the sensor value on every cue row (blue in
    his plots) and on every response row (red). The cue series is the
    interesting one, because the finger is at rest when a cue lands, so
    that series IS the baseline sampled once a trial, and watching it
    climb over ten minutes is how the drift was found in the first
    place.

    `rows="all"` reads the value off the event row, his convention.
    `rows="samples"` reads the nearest sample by time, which is the only
    option on our logs; the two differ by a few counts on a rising edge
    because a sample and an event stamp sit about 5 ms apart.

    Columns: t_sec (seconds from the first cue), event_type, fsr_value
    (offset already subtracted), row.
    """
    columns = ["t_sec", "event_type", "fsr_value", "row"]
    events = event_kinds(raw)
    if events.empty or sensor not in raw.columns:
        return pd.DataFrame(columns=columns)
    level, _ = _event_levels(raw, events, sensor, rows)
    first_stim = events.loc[events["kind"] == "Stim", "t_perf"]
    t0 = float(first_stim.iloc[0]) if len(first_stim) else 0.0
    zero = float(offset[sensor]) if isinstance(offset, dict) else float(offset)
    return pd.DataFrame({
        "t_sec": events["t_perf"].to_numpy(dtype=float) - t0,
        "event_type": events["kind"].to_numpy(),
        "fsr_value": level - zero,
        "row": events["row"].to_numpy(),
    })


def _event_levels(raw: pd.DataFrame, events: pd.DataFrame, sensor: str,
                  rows: str):
    """The sensor level at each event row, and the index used to read it.

    Split out because the drift analyses need both the level and the
    index the look-back window counts back from, and the index is
    different in the two conventions: his indexes into the whole frame,
    ours into the sample rows only.
    """
    if rows == "all":
        values = pd.to_numeric(raw[sensor], errors="coerce").to_numpy(float)
        idx = events["row"].to_numpy()
        return values[idx], (values, idx)
    samples = sample_rows(raw)
    values = pd.to_numeric(samples[sensor], errors="coerce").to_numpy(float)
    st = samples["t_perf"].to_numpy(dtype=float)
    te = events["t_perf"].to_numpy(dtype=float)
    if not len(values):
        return np.full(len(te), np.nan), (values, np.zeros(len(te), int))
    idx = np.clip(np.searchsorted(st, te, side="left"), 0, len(values) - 1)
    prev = np.clip(idx - 1, 0, len(values) - 1)
    # Nearest sample by time, not the next one: the next sample already
    # sits on the rising edge of the press and reads high, while the
    # previous one is where the event row's own value came from.
    use_prev = np.abs(st[prev] - te) <= np.abs(st[idx] - te)
    idx = np.where(use_prev, prev, idx)
    return values[idx], (values, idx)


def baseline_shift(raw: pd.DataFrame, sensor: str, n_edge: int = 20,
                   rows: str = "all", offset=RAYAN_STATIC_OFFSET) -> float:
    """How far the pad's rest level moved over the block, in counts.

    The one number his stim-versus-response plot was read for by eye:
    the median cue-time level over the last `n_edge` cues minus the
    first `n_edge`. Positive means the pad's rest level climbed, which
    is what makes a fixed zero wrong by the end of a session and why the
    look-back zero below exists. Halves the edge when there are fewer
    than 2 * n_edge cues, and gives up under ten.
    """
    levels = stim_response_levels(raw, sensor, offset=offset, rows=rows)
    cues = levels.loc[levels["event_type"] == "Stim", "fsr_value"].to_numpy()
    cues = cues[np.isfinite(cues)]
    if len(cues) < 10:
        return float("nan")
    k = n_edge if len(cues) >= 2 * n_edge else len(cues) // 2
    return float(np.median(cues[-k:]) - np.median(cues[:k]))


def drift_newtons(raw: pd.DataFrame, sensor: str,
                  counts_per_newton: float = RAYAN_COUNTS_PER_NEWTON,
                  offset=RAYAN_STATIC_OFFSET, lookback: int = LOOKBACK_ROWS,
                  rows: str = "all"):
    """analyze_baseline_drift_modified_newtons.R: fixed zero against local.

    At every cue and press row the force is worked out twice. The raw
    series subtracts one static offset for the whole block, the way a
    fixed calibration constant would. The zeroed series subtracts the
    mean of the `lookback` rows immediately before that event, which at
    200 Hz is the quarter second the finger was resting through. Both
    are divided by `counts_per_newton` to land in newtons, and a
    straight line is fitted through the press rows of each.

    The comparison is the argument for the look-back: on his gradual
    force test the raw line climbs at 0.004 N/s off a 1.95 N intercept
    while the zeroed line climbs at 0.0017 N/s off 0.96 N. Most of the
    apparent trend was the pad's rest level drifting under a fixed zero,
    not the finger pressing harder.

    His rig held the finger down, so his press rows sat near the peak of
    the press. Ours logs a press the moment the pad crosses the on
    threshold, which is on the way up, so on our blocks read this as the
    drift of the level at event time and take press force from
    `stim_peaks` instead.

    Returns (frame, fits, mean_diff_counts): the per-event frame, a dict
    of (slope, intercept) for each series, and the mean press height
    above its own local floor in counts.
    """
    events = event_kinds(raw)
    empty = (pd.DataFrame(columns=["t_sec", "type", "fsr_raw",
                                   "local_floor_raw", "diff_counts",
                                   "force_n_raw", "force_n_zeroed"]),
             {"force_n_raw": (float("nan"), float("nan")),
              "force_n_zeroed": (float("nan"), float("nan"))},
             float("nan"))
    if events.empty or sensor not in raw.columns:
        return empty
    level, (series, idx) = _event_levels(raw, events, sensor, rows)
    if not len(series):
        return empty
    zero = float(offset[sensor]) if isinstance(offset, dict) else float(offset)
    first_stim = events.loc[events["kind"] == "Stim", "t_perf"]
    t0 = float(first_stim.iloc[0]) if len(first_stim) else 0.0
    floor = np.array([lookback_baseline(series, i, lookback) for i in idx])
    frame = pd.DataFrame({
        "t_sec": events["t_perf"].to_numpy(dtype=float) - t0,
        "type": events["kind"].to_numpy(),
        "fsr_raw": level,
        "local_floor_raw": floor,
    })
    frame["diff_counts"] = frame["fsr_raw"] - frame["local_floor_raw"]
    frame["force_n_raw"] = (frame["fsr_raw"] - zero) / counts_per_newton
    frame["force_n_zeroed"] = frame["diff_counts"] / counts_per_newton
    press = frame[(frame["type"] == "Response")
                  & np.isfinite(frame["force_n_zeroed"])]
    fits = {}
    for name in ("force_n_raw", "force_n_zeroed"):
        if len(press) >= 2:
            slope, intercept = np.polyfit(press["t_sec"], press[name], 1)
            fits[name] = (float(slope), float(intercept))
        else:
            fits[name] = (float("nan"), float("nan"))
    mean_diff = float(press["diff_counts"].mean()) if len(press) \
        else float("nan")
    return frame, fits, mean_diff


def response_waveforms(raw: pd.DataFrame, sensor: str, n_trials: int = 5,
                       pre_s: float = 0.5, post_s: float = 0.5,
                       fs: float = 200.0, dots_ms=WAVEFORM_DOTS_MS,
                       rows: str = "all", lane: int | None = None,
                       anchor: str = "response") -> list:
    """analyze_baseline_drift.R: the raw trace around the first few cues.

    For each of the first `n_trials` response events, find the cue
    before it and cut the stream from `pre_s` before that cue to
    `post_s` after it, with a marker on the cue, on the peak, and a dot
    at every step in `dots_ms` back from the cue. Strung end to end
    these are the picture that chose the 250 ms look-back window: the
    dots hold flat for about a quarter second before a cue and then the
    previous press's tail starts to lift them.

    His script cuts by ROW index at an assumed 200 Hz, which is exact on
    his stream; ours is cut by time instead when rows="samples", because
    a burst-stamped log has no fixed rows per second.

    He only ever had one finger wired, so he took the first responses in
    the file whatever lane they were on. Pass `lane` on a block that
    cues four fingers in turn, or the figure draws this sensor's trace
    through another finger's press.

    `anchor` is the other difference. His "response" starts from the
    first press events and looks back for the cue before each, which
    works because his rig pressed on every trial. Ours logs a press only
    when the pad crosses the on threshold, and a light finger can go a
    whole block without one, so anchor="cue" takes the first cues on
    that lane instead and draws whatever the pad did, press or no press.

    Returns a list of dicts, one per trial: t (relative seconds), values,
    cue_index, peak_index, peak_value, dot_indices, lane.
    """
    events = event_kinds(raw)
    if events.empty or sensor not in raw.columns:
        return []
    stims = events[events["kind"] == "Stim"]
    responses = events[events["kind"] == "Response"]
    if lane is not None:
        stims = stims[stims["lane"] == lane]
        # A press row carries the lane it was on; a logger that leaves
        # it blank still gets the cue filter above.
        if responses["lane"].notna().any():
            responses = responses[responses["lane"] == lane]
    if anchor == "cue":
        responses = stims.head(n_trials)
    else:
        responses = responses.head(n_trials)
    if responses.empty or stims.empty:
        return []
    if rows == "all":
        series = pd.to_numeric(raw[sensor], errors="coerce").to_numpy(float)
        t_all = raw["t_perf"].to_numpy(dtype=float)
    else:
        samples = sample_rows(raw)
        series = pd.to_numeric(samples[sensor],
                               errors="coerce").to_numpy(float)
        t_all = samples["t_perf"].to_numpy(dtype=float)
    out = []
    for _, response in responses.iterrows():
        if anchor == "cue":
            cue = response
        else:
            before = stims[stims["t_perf"] < float(response["t_perf"])]
            if before.empty:
                continue
            cue = before.iloc[-1]
        t_cue = float(cue["t_perf"])
        if rows == "all":
            cue_row = int(cue["row"])
            lo = max(0, cue_row - int(pre_s * fs))
            hi = min(len(series), cue_row + int(post_s * fs) + 1)
            cue_index = cue_row - lo
            dot_indices = [cue_row - int(ms / 1000.0 * fs) - lo
                           for ms in dots_ms]
        else:
            lo = int(np.searchsorted(t_all, t_cue - pre_s, side="left"))
            hi = int(np.searchsorted(t_all, t_cue + post_s, side="right"))
            cue_index = int(np.searchsorted(t_all, t_cue, side="left")) - lo
            dot_indices = [int(np.searchsorted(t_all, t_cue - ms / 1000.0,
                                               side="left")) - lo
                           for ms in dots_ms]
        values = series[lo:hi]
        if len(values) < 20 or not np.isfinite(values).any():
            continue
        peak_index = int(np.nanargmax(values))
        out.append({
            "t": t_all[lo:hi] - t_cue,
            "values": values,
            "cue_index": int(np.clip(cue_index, 0, len(values) - 1)),
            "peak_index": peak_index,
            "peak_value": float(values[peak_index]),
            "dot_indices": [d for d in dot_indices if 0 <= d < len(values)],
            "lane": (int(cue["lane"]) if pd.notna(cue.get("lane")) else None),
        })
    return out


# ------------------------------------------------- onset and per-trial peaks

def processed_peaks(raw: pd.DataFrame, offset=RAYAN_STATIC_OFFSET,
                    fs_mode: str = "median", window_s: float = PEAK_WINDOW_S,
                    pre_s: float = ONSET_PRE_S) -> pd.DataFrame:
    """raw/process_force_peaks.py: onset time and every pad's peak per cue.

    For each cue, cut the stream from `pre_s` before it to `window_s`
    after, find the movement onset on the cued pad with the Teasdale
    detector (finger_rehab/analytics/signal.teasdale_onset, itself the
    exact port of his file), and take each pad's maximum from the onset
    to the end of the window. Where no onset is found the peak is taken
    over the whole window, which is his fallback too.

    The reaction time here is a force-onset time, not the game's logged
    key or threshold time; it lands earlier, because the finger starts
    moving before the pad crosses any threshold.

    `fs_mode` picks the sample rate rule (see `estimate_fs`). It is not
    cosmetic: the rate sets the filter cutoffs inside the detector and
    the end of the search window, so his file and ours want different
    modes.

    Output columns match his processed CSV: trial_id, stim_time_s,
    stim_lane, reaction_time_ms, peak_fsr1_raw .. peak_fsrN_raw, with
    stim_order added so two runs can be lined up without trusting a
    trial number that restarts per block.
    """
    samples = sample_rows(raw)
    stims = (raw[(raw["event"] == "stim") & raw["lane"].notna()]
             .dropna(subset=["t_perf"]).sort_values("t_perf", kind="stable"))
    cols = fsr_columns(samples)
    base = ["trial_id", "stim_order", "stim_time_s", "stim_lane",
            "reaction_time_ms"]
    peak_cols = [f"peak_{c}_raw" for c in cols]
    if samples.empty or stims.empty or not cols:
        return pd.DataFrame(columns=base + peak_cols)
    t = samples["t_perf"].to_numpy(dtype=float)
    fs = estimate_fs(t, fs_mode)
    streams = []
    for col in cols:
        zero = float(offset[col]) if isinstance(offset, dict) \
            else float(offset)
        values = pd.to_numeric(samples[col], errors="coerce").to_numpy(float)
        streams.append(np.nan_to_num(values, nan=0.0) - zero)
    out = []
    for order, (_, stim) in enumerate(stims.iterrows(), start=1):
        t0 = float(stim["t_perf"])
        lane = int(stim["lane"])
        if lane >= len(streams):
            continue
        lo = int(np.searchsorted(t, t0 - pre_s, side="left"))
        hi = int(np.searchsorted(t, t0 + window_s, side="right"))
        onset, _, _ = teasdale_onset(streams[lane][lo:hi], fs=fs,
                                     search_from=0,
                                     search_to=int(window_s * fs))
        rt = None
        start = lo
        if onset is not None:
            rt = (t[lo + onset] - t0) * 1000.0
            start = lo + onset
        row = {"trial_id": parse_trial(stim.get("detail"), order),
               "stim_order": order, "stim_time_s": t0, "stim_lane": lane,
               "reaction_time_ms": rt}
        for col, stream in zip(peak_cols, streams):
            row[col] = float(np.max(stream[start:hi])) if start < hi \
                else np.nan
        out.append(row)
    return pd.DataFrame(out, columns=base + peak_cols)


def off_target_share(processed: pd.DataFrame, board_of_lane: bool = True
                     ) -> pd.DataFrame:
    """How much of a press landed on the fingers that were not cued.

    The spill number behind his four-panel plots: for each cue, the sum
    of the other pads' peaks over the sum of all four, clipped at zero
    so a pad reading below its own rest level cannot make the share
    negative. A perfectly individuated press is near zero; the pinky
    never gets there, because the tendons are shared.

    Only the pads on the cued hand's board count when `board_of_lane`,
    since the other hand's pads have nothing to do with this press.
    """
    peak_cols = [c for c in processed.columns
                 if c.startswith("peak_fsr") and c.endswith("_raw")]
    if processed.empty or not peak_cols:
        return processed.assign(on_target=[], off_share=[])
    out = processed.copy()
    on, share = [], []
    for _, row in out.iterrows():
        lane = int(row["stim_lane"])
        board = lane // 4
        mine = f"peak_{lane_column(lane)}_raw"
        target = max(0.0, float(row[mine])) if mine in out.columns \
            and pd.notna(row.get(mine)) else float("nan")
        others = []
        for col in peak_cols:
            other = int(col[len("peak_fsr"):-len("_raw")]) - 1
            if other == lane or pd.isna(row[col]):
                continue
            if board_of_lane and other // 4 != board:
                continue
            others.append(max(0.0, float(row[col])))
        total = (0.0 if not np.isfinite(target) else target) + sum(others)
        on.append(target)
        share.append(sum(others) / total if total > 0 else float("nan"))
    out["on_target"] = on
    out["off_share"] = share
    return out


def block_slices(processed: pd.DataFrame,
                 bounds=((1, 50, "block1 random"),
                         (51, 550, "block2 structured"),
                         (551, 600, "block3 random final"))) -> dict:
    """raw/FingerRawforEachBlock.R: cut the trials into his three blocks.

    His plots split the run at trials 1-50, 51-550 and 551-600, the
    pretest, the main block and the aftertest as he ran them. Worth
    knowing before reading one of his figures: his trial numbers restart
    per block, so his "51-550" panel actually holds main trials 51 to
    500 and none of the aftertest. Slicing on `stim_order` instead of
    trial_id fixes that, and is the default when the column is there.

    Returns {label: frame}, empty slices dropped.
    """
    key = "stim_order" if "stim_order" in processed.columns else "trial_id"
    out = {}
    for lo, hi, label in bounds:
        part = processed[(processed[key] >= lo) & (processed[key] <= hi)]
        if len(part):
            out[label] = part
    return out


# ----------------------------------------------- reaction time by block

def _as_bool(series: pd.Series) -> pd.Series:
    if pd.api.types.is_bool_dtype(series):
        return series
    return series.astype(str).str.strip().str.lower().map(
        {"true": True, "t": True, "1": True, "yes": True, "y": True,
         "false": False, "f": False, "0": False, "no": False, "n": False})


def session_trials_as_bench(trials: pd.DataFrame) -> pd.DataFrame:
    """Our trials.csv in his column vocabulary.

    He wrote one CSV per session with a block column reading pretest,
    main or aftertest. We write one folder per block with the mode in
    `block` and the protocol position in `phase`, and phase is only set
    when the block ran inside a protocol, so a block played on its own
    counts as main. The game folder stands in for his source_file,
    because his dedupe and chunk numbering are per file and ours have to
    be per block.
    """
    frame = trials.copy()
    phase = (frame["phase"].fillna("").astype(str) if "phase" in frame.columns
             else pd.Series("", index=frame.index))
    frame["block"] = np.where(phase == "pretest", "pretest",
                              np.where(phase == "aftertest", "posttest",
                                       "main"))
    if "source_file" not in frame.columns:
        frame["source_file"] = frame.get("game", frame.get("mode", "block"))
    return frame


def block_table(trials: pd.DataFrame, chunk: int = CHUNK_TRIALS,
                rt_min: float = RT_MIN_MS, rt_max: float = RT_MAX_MS,
                enforce_five: bool = False) -> pd.DataFrame:
    """Data_analysis_Final.R: the analytic set his model was fitted to.

    Four steps, in his order, because the order changes the answer:

      1. One row per (file, participant, block, trial), preferring a row
         that is not a miss when a trial appears twice.
      2. Number the rows within each block in file order and cut the
         main block into chunks of `chunk`. This happens BEFORE the
         filtering below, so a dropped trial thins its own chunk
         instead of pulling every later trial back a place.
      3. Drop trials with no reaction time, with one outside
         [rt_min, rt_max], or with a wrong finger pressed. A fixed
         window rather than an sd-based cut, which is the choice
         Ratcliff (1993) sets out for reaction time outliers.
      4. Map to his block_all: 0 pretest, 1 to 5 main chunks, 6
         aftertest, with is_random true for the two untrained blocks.

    Needs his column names, so pass our trials through
    `session_trials_as_bench` first.
    """
    columns = ["source_file", "participant", "block", "trial", "block_all",
               "is_random", "time_difference_ms", "lane"]
    if trials is None or trials.empty \
            or "time_difference_ms" not in trials.columns:
        return pd.DataFrame(columns=columns)
    frame = trials.copy()
    frame["row_idx"] = np.arange(len(frame))
    outcome = frame.get("early_late", pd.Series("", index=frame.index))
    error = frame.get("error_type", pd.Series("", index=frame.index))
    miss = (outcome.fillna("").astype(str).str.lower() == "miss") | \
        error.fillna("").astype(str).str.lower().isin(["miss", "timeout"])
    frame["is_miss_flag"] = miss
    keys = ["source_file", "participant", "block", "trial"]
    keys = [k for k in keys if k in frame.columns]
    frame = (frame.sort_values(keys + ["is_miss_flag", "row_idx"],
                               kind="stable")
             .drop_duplicates(keys, keep="first")
             .sort_values("row_idx", kind="stable"))
    group = [k for k in ("source_file", "participant", "block")
             if k in frame.columns]
    if enforce_five:
        # His enforce_five_blocks switch, off by default: throw away
        # anything past the fifth chunk instead of clipping it into it.
        over = frame.groupby(group).cumcount() + 1
        frame = frame[~((frame["block"] == "main") & (over > 5 * chunk))]
    frame["row_in_group"] = frame.groupby(group).cumcount() + 1
    frame["chunk"] = np.where(
        frame["block"] == "main",
        np.ceil(frame["row_in_group"] / chunk).astype(int), 1)
    wrong = (_as_bool(frame["had_incorrect_press"]).fillna(False).astype(bool)
             if "had_incorrect_press" in frame.columns
             else pd.Series(False, index=frame.index))
    pressed = frame["keys_pressed"].astype("string") \
        if "keys_pressed" in frame.columns else None
    wanted = frame["correct_keys"].astype("string") \
        if "correct_keys" in frame.columns else None
    mismatch = ((pressed.notna() & wanted.notna() & (pressed != wanted))
                .fillna(False).astype(bool)
                if pressed is not None and wanted is not None
                else pd.Series(False, index=frame.index))
    rt = pd.to_numeric(frame["time_difference_ms"], errors="coerce")
    keep = rt.notna() & (rt >= rt_min) & (rt <= rt_max) & ~wrong & ~mismatch
    out = frame[keep].copy()
    out["time_difference_ms"] = rt[keep]
    out["block_all"] = np.select(
        [out["block"] == "pretest", out["block"] == "main",
         out["block"] == "posttest"],
        [0, out["chunk"].clip(1, 5), 6], default=-1)
    out = out[out["block_all"] >= 0]
    out["is_random"] = out["block_all"].isin([0, 6])
    return out[[c for c in columns if c in out.columns]]


def holm(pvalues) -> np.ndarray:
    """Holm's step-down adjustment, the correction his pairwise call used.

    Holm S (1979). A simple sequentially rejective multiple test
    procedure. Scandinavian Journal of Statistics 6(2):65-70. Sort the p
    values, multiply each by the number of tests still standing, and
    carry the running maximum forward so the adjusted values cannot
    decrease.
    """
    p = np.asarray(pvalues, dtype=float)
    adjusted = np.empty(len(p))
    running = 0.0
    for rank, i in enumerate(np.argsort(p)):
        running = max(running, (len(p) - rank) * p[i])
        adjusted[i] = min(1.0, running)
    return adjusted


def block_model(analytic: pd.DataFrame):
    """Data_analysis_Final.R: reaction time against block, with contrasts.

    He fitted lmer(RT ~ block + (1 | participant)) and pulled estimated
    marginal means out with emmeans. There is no mixed-model package in
    this project's dependencies, so this is the stand-in: ordinary least
    squares with a dummy per block, plus a dummy per participant when
    there is more than one. On a balanced design the block means come
    out identical; the intervals are the within-participant ones, so
    they are narrower than his, which also carry the between-participant
    spread. Say so wherever the numbers are quoted.

    Returns (means, pairs, post_pre, trend, info):
      means     one row per block with a 95 percent interval
      pairs     every pairwise contrast, raw and Holm-adjusted p
      post_pre  aftertest minus pretest, only when both blocks exist
      trend     linear trend over blocks 1 to 5, weights -2 to 2, only
                when all five chunks exist
      info      residual variance, residual df, participant count
    """
    from scipy import stats

    empty = (pd.DataFrame(columns=["block", "n", "emmean", "SE", "lower",
                                   "upper"]),
             pd.DataFrame(), None, None, {})
    if analytic is None or analytic.empty \
            or analytic["block_all"].nunique() < 2:
        return empty
    blocks = sorted(int(b) for b in analytic["block_all"].unique())
    y = analytic["time_difference_ms"].to_numpy(dtype=float)
    design = pd.get_dummies(analytic["block_all"].astype("category")
                            ).to_numpy(dtype=float)
    people = analytic["participant"].astype(str) \
        if "participant" in analytic.columns \
        else pd.Series("one", index=analytic.index)
    n_people = int(people.nunique())
    if n_people > 1:
        design = np.hstack([design, pd.get_dummies(people, drop_first=True)
                            .to_numpy(dtype=float)])
    beta, *_ = np.linalg.lstsq(design, y, rcond=None)
    resid = y - design @ beta
    df_res = int(len(y) - np.linalg.matrix_rank(design))
    if df_res < 2:
        return empty
    mse = float(resid @ resid / df_res)
    cov = mse * np.linalg.pinv(design.T @ design)
    tcrit = float(stats.t.ppf(0.975, df_res))
    nb = len(blocks)
    # Marginal means: the block's own effect plus the average
    # participant effect, which is what emmeans reports.
    contrasts = np.zeros((nb, design.shape[1]))
    for i in range(nb):
        contrasts[i, i] = 1.0
        if n_people > 1:
            contrasts[i, nb:] = 1.0 / n_people
    emmean = contrasts @ beta
    se = np.sqrt(np.einsum("ij,jk,ik->i", contrasts, cov, contrasts))
    means = pd.DataFrame({
        "block": blocks,
        "n": analytic.groupby("block_all").size().reindex(blocks).to_numpy(),
        "emmean": emmean, "SE": se,
        "lower": emmean - tcrit * se, "upper": emmean + tcrit * se})

    def contrast(weights):
        weights = np.asarray(weights, dtype=float)
        estimate = float(weights @ emmean)
        row = weights @ contrasts
        se_c = float(np.sqrt(row @ cov @ row))
        tval = estimate / se_c if se_c > 0 else float("nan")
        p = float(2 * stats.t.sf(abs(tval), df_res)) if np.isfinite(tval) \
            else float("nan")
        return {"estimate": estimate, "SE": se_c, "t": tval, "df": df_res,
                "p": p, "lower": estimate - tcrit * se_c,
                "upper": estimate + tcrit * se_c}

    pairs = []
    for i in range(nb):
        for j in range(i + 1, nb):
            weights = np.zeros(nb)
            weights[i], weights[j] = 1.0, -1.0
            row = contrast(weights)
            row["contrast"] = f"{blocks[i]} - {blocks[j]}"
            pairs.append(row)
    pairs = pd.DataFrame(pairs)
    if len(pairs):
        pairs["p_holm"] = holm(pairs["p"].to_numpy())
    post_pre = None
    if 0 in blocks and 6 in blocks:
        weights = np.zeros(nb)
        weights[blocks.index(0)] = -1.0
        weights[blocks.index(6)] = 1.0
        post_pre = contrast(weights)
    trend = None
    if all(b in blocks for b in (1, 2, 3, 4, 5)):
        weights = np.zeros(nb)
        for weight, block in zip((-2, -1, 0, 1, 2), (1, 2, 3, 4, 5)):
            weights[blocks.index(block)] = weight
        trend = contrast(weights)
    return means, pairs, post_pre, trend, {"mse": mse, "df_res": df_res,
                                           "n_people": n_people}


# ----------------------------------------------------------------- plotting

def use_style() -> None:
    """Apply the house figure style to matplotlib's globals.

    A caller that wants every figure to match calls this once. The
    plotting helpers below do not call it, because a library that
    rewrites rcParams on import surprises whatever else is drawing in
    the same process.
    """
    import matplotlib.pyplot as plt
    plt.rcParams.update({
        "figure.dpi": 110, "savefig.dpi": 160,
        "axes.grid": True, "grid.color": "#e2e8f0", "grid.linewidth": 0.8,
        "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold",
        "axes.titlelocation": "left", "figure.autolayout": True,
    })


def _finish(ax, xlabel, ylabel, title):
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.grid(True, color="#e2e8f0", linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def plot_finger_peaks(peaks: pd.DataFrame, lane: int, rep=None,
                      hand_mode: str = "right"):
    """One finger: every cued press in order, with its segment means.

    The per-finger view of repeatability.R. The dots are the presses in
    the order they happened, the step line is the segment mean with its
    sd band, so a drifting pad and a tiring finger look different: the
    band widens when the presses scatter, and the line moves when the
    level does.
    """
    import matplotlib.pyplot as plt

    mine = peaks[peaks["lane"] == lane].sort_values("stim_order")
    finger = lane_finger(lane)
    colour = FINGER_COLOUR[finger]
    fig, ax = plt.subplots(figsize=(9, 3.2))
    # Against this finger's own press count, not the cue order over the
    # whole block: the segments are cut per finger, so the two axes
    # would put the segment means in the wrong place on a block that
    # cues four fingers in turn.
    index = np.arange(1, len(mine) + 1)
    ax.plot(index, mine["peak_counts"], "o", ms=4, alpha=0.7,
            color=colour, label="press")
    if rep is not None and len(rep):
        segment = rep[rep["lane"] == lane].sort_values("segment")
        if len(segment):
            ends = segment["n"].cumsum().to_numpy()
            centres = ends - segment["n"].to_numpy() / 2.0 + 0.5
            ax.errorbar(centres, segment["mean_force"],
                        yerr=segment["sd_force"], fmt="s-", color="#0f172a",
                        lw=1.4, ms=5, capsize=3, alpha=0.9,
                        label="segment mean +/- sd")
    ax.axhline(SINGLETACT_FULL_SCALE_COUNTS, color="#dc2626", ls=":", lw=1,
               label="sensor rating")
    _finish(ax, "cued press of this finger, in order",
            "peak above rest (counts)",
            f"{lane_side(lane, hand_mode)} {finger}: peak per press")
    ax.legend(frameon=False, fontsize=8)
    return fig


def plot_trial_peaks(processed: pd.DataFrame, title: str = "",
                     lanes=None):
    """raw/FingerRawforEachBlock.R: one panel per pad, peak per trial.

    Every pad is drawn on every trial. The big dot is the pad that was
    cued and the small ones are the other three, so the spill is visible
    straight away: a flat line of small dots means the press stayed on
    the target finger, and small dots that track the big ones mean it
    did not. His version showed the unwired pads as a flat line at -255;
    here an unwired or unpressed pad is flat at zero.
    """
    import matplotlib.pyplot as plt

    peak_cols = [c for c in processed.columns
                 if c.startswith("peak_fsr") and c.endswith("_raw")]
    all_lanes = [int(c[len("peak_fsr"):-len("_raw")]) - 1 for c in peak_cols]
    if lanes is None:
        board = int(processed["stim_lane"].iloc[0]) // 4 \
            if len(processed) else 0
        lanes = [l for l in all_lanes if l // 4 == board] or all_lanes
    key = "stim_order" if "stim_order" in processed.columns else "trial_id"
    fig, axes = plt.subplots(len(lanes), 1, figsize=(11, 2.0 * len(lanes)),
                             sharex=True, squeeze=False)
    for ax, lane in zip(axes[:, 0], lanes):
        col = f"peak_{lane_column(lane)}_raw"
        finger = lane_finger(lane)
        ax.plot(processed[key], processed[col], color=TRACE_COLOUR, lw=0.8)
        cued = processed["stim_lane"] == lane
        ax.scatter(processed.loc[~cued, key], processed.loc[~cued, col],
                   s=9, color=FINGER_COLOUR[finger], alpha=0.55)
        ax.scatter(processed.loc[cued, key], processed.loc[cued, col],
                   s=30, color=FINGER_COLOUR[finger])
        ax.set_ylabel(f"{finger}\ncounts", fontsize=8)
        ax.grid(True, color="#e2e8f0", linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
    axes[-1, 0].set_xlabel("trial")
    fig.suptitle(title or "Peak per trial on every pad (large = cued finger)",
                 fontsize=10)
    return fig


def plot_repeatability(rep: pd.DataFrame, hand_mode: str = "right",
                       segment_trials: int | None = None):
    """repeatability.R: the segment means, every finger on one axis.

    His plot was one line per lane with sd bars. Same here, with the
    fingers in the notebook's colours and one panel per hand, so a
    two-handed session does not stack eight lines on one axis.
    """
    import matplotlib.pyplot as plt

    if rep.empty:
        fig, ax = plt.subplots(figsize=(6.5, 3.4))
        _finish(ax, "segment", "mean peak (counts)",
                "Repeatability: no cued presses to segment")
        return fig
    sides = {int(lane): lane_side(int(lane), hand_mode)
             for lane in rep["lane"].unique()}
    hands = [h for h in ("right", "left") if h in set(sides.values())]
    fig, axes = plt.subplots(1, len(hands), figsize=(6.5 * len(hands), 3.6),
                             squeeze=False)
    for ax, hand in zip(axes[0], hands):
        for lane in sorted(sides):
            if sides[lane] != hand:
                continue
            mine = rep[rep["lane"] == lane].sort_values("segment")
            if mine.empty:
                continue
            finger = lane_finger(lane)
            ax.errorbar(mine["segment"], mine["mean_force"],
                        yerr=mine["sd_force"], fmt="o-", ms=4, lw=1.5,
                        capsize=3, alpha=0.85, color=FINGER_COLOUR[finger],
                        label=finger)
        label = "segment" if not segment_trials \
            else f"segment ({segment_trials} cued presses each)"
        _finish(ax, label, "mean peak (counts) +/- sd",
                f"Repeatability, {hand} hand")
        # Segments are whole numbers; a short block with two of them
        # otherwise gets ticks at 1.2 and 1.4, which mean nothing.
        from matplotlib.ticker import MaxNLocator
        ax.xaxis.set_major_locator(MaxNLocator(integer=True))
        ax.legend(frameon=False, fontsize=8)
    return fig


def plot_snr(summary: pd.DataFrame, hand_mode: str = "right"):
    """Noise_Analysis.R: signal to noise per pad, as bars.

    Unitless, so unlike raw counts these bars can be read against each
    other: a low bar is a pad whose presses are not far above its own
    noise, whether that is a loose finger cup or a failing sensor.
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(7, 3.2))
    if summary.empty:
        _finish(ax, "", "SNR", "Signal to noise per pad: nothing to show")
        return fig
    lanes = [int(str(s).replace("FS", "")) - 1 for s in summary["sensor"]]
    colours = [FINGER_COLOUR[lane_finger(l)] for l in lanes]
    x = np.arange(len(summary))
    ax.bar(x, summary["grand_snr"].fillna(0.0), color=colours, alpha=0.85)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{s}\n{lane_side(l, hand_mode)[0]} {lane_finger(l)}"
                        for s, l in zip(summary["sensor"], lanes)],
                       fontsize=8)
    _finish(ax, "", "SNR (mean peak / rest sd)", "Signal to noise per pad")
    return fig


def plot_cv_heatmap(rep: pd.DataFrame, hand_mode: str = "right",
                    min_presses: int = 3, hand: str | None = None):
    """repeatability.R: the CV as a finger by segment heatmap.

    Reading a whole run at once: dark is repeatable, light is not, and a
    row that lightens towards the right is a finger getting less
    consistent as the block goes on. Cells with fewer than
    `min_presses` presses stay blank, because a CV over one or two
    presses is noise with a number on it.

    Four rows, one per finger, so a two-handed selection would average
    a finger with its opposite. Pass `hand` to draw one side at a time
    when both are in the frame.
    """
    import matplotlib.pyplot as plt

    usable = rep[rep["n"] >= min_presses] if len(rep) else rep
    if hand is not None and len(usable):
        usable = usable[usable["lane"].map(
            lambda l: lane_side(int(l), hand_mode)) == hand]
    fig, ax = plt.subplots(figsize=(6.5, 3.4))
    if usable.empty:
        _finish(ax, "segment", "",
                f"CV percent: no segment with {min_presses}+ presses")
        return fig
    segments = sorted(usable["segment"].unique())
    grid = np.full((4, len(segments)), np.nan)
    for row, finger in enumerate(FINGERS):
        for col, segment in enumerate(segments):
            cell = usable[(usable["lane"].map(lane_finger) == finger)
                          & (usable["segment"] == segment)]["cv_percent"]
            if len(cell):
                grid[row, col] = float(cell.mean())
    top = float(np.nanmax(grid)) if np.isfinite(grid).any() else 1.0
    image = ax.imshow(grid, aspect="auto", cmap="viridis_r", vmin=0, vmax=top)
    ax.set_yticks(range(4))
    ax.set_yticklabels(list(FINGERS))
    ax.set_xticks(range(len(segments)))
    ax.set_xticklabels(segments)
    title = "CV percent of the peak" if hand is None \
        else f"CV percent of the peak, {hand} hand"
    _finish(ax, "segment", "", title)
    # After _finish, because it turns the grid on and grid lines drawn
    # over an image read as part of the data.
    ax.grid(False)
    for row in range(4):
        for col in range(len(segments)):
            if np.isfinite(grid[row, col]):
                ax.text(col, row, f"{grid[row, col]:.0f}", ha="center",
                        va="center", fontsize=7,
                        color="white" if grid[row, col] > 0.5 * top
                        else "black")
    fig.colorbar(image, ax=ax, fraction=0.04)
    return fig


def plot_stim_response(levels: pd.DataFrame, sensor: str):
    """analyze_baseline_drift_modified.R: cue level against press level.

    Blue is the pad at each cue, red at each press. The blue series is
    the baseline: with the finger resting when a cue lands, watching it
    walk upwards is the drift itself, and the gap between the two series
    is what a press is actually worth once the drift is taken out.
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 3.4))
    if levels.empty:
        _finish(ax, "seconds from the first cue", "counts",
                f"{sensor.upper()}: no cue or press events")
        return fig
    for kind, colour, marker in (("Stim", STIM_COLOUR, "o"),
                                 ("Response", RESPONSE_COLOUR, "^")):
        mine = levels[levels["event_type"] == kind]
        if mine.empty:
            continue
        ax.plot(mine["t_sec"], mine["fsr_value"], color=colour, lw=0.6,
                alpha=0.4)
        ax.plot(mine["t_sec"], mine["fsr_value"], marker, color=colour, ms=4,
                alpha=0.85, label=kind.lower())
    ax.axhline(0.0, color="#94a3b8", ls="--", lw=0.6)
    _finish(ax, "seconds from the first cue", "counts above the fixed zero",
            f"{sensor.upper()}: level at each cue and each press")
    ax.legend(frameon=False, fontsize=8)
    return fig


def plot_force_trends(drift: pd.DataFrame, fits: dict, sensor: str):
    """analyze_baseline_drift_modified_newtons.R: fixed zero against local.

    The faded series is a fixed offset for the whole block, the solid
    one is the same presses zeroed against the quarter second before
    each. Their fitted lines and equations are printed on the axis: when
    the faded line climbs and the solid one does not, the trend was the
    pad drifting, not the finger.
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(11, 3.8))
    if drift.empty:
        _finish(ax, "seconds from the first cue", "force (N)",
                f"{sensor.upper()}: no cue or press events")
        return fig
    press = drift[drift["type"] == "Response"]
    ax.plot(drift["t_sec"], drift["force_n_raw"], "o", ms=3, alpha=0.25,
            color="#94a3b8", label="fixed zero")
    ax.plot(drift["t_sec"], drift["force_n_zeroed"], "o", ms=3, alpha=0.8,
            color="#0f172a", label="local zero (250 ms look-back)")
    cues = drift[drift["type"] == "Stim"]
    ax.plot(cues["t_sec"], cues["force_n_zeroed"], "^", ms=4,
            color=STIM_COLOUR, alpha=0.7, label="cue")
    if len(press) >= 2:
        x = np.linspace(float(drift["t_sec"].min()),
                        float(drift["t_sec"].max()), 50)
        for name, colour, style in (("force_n_raw", "#f59e0b", "--"),
                                    ("force_n_zeroed", "#ca8a04", "-")):
            slope, intercept = fits.get(name, (np.nan, np.nan))
            if np.isfinite(slope):
                ax.plot(x, slope * x + intercept, style, color=colour, lw=1.4)
                # Top right, because the legend takes the top left and
                # his equations printed on the figure are worth keeping.
                ax.text(0.99, 0.96 if name == "force_n_raw" else 0.88,
                        f"{name}: y = {slope:.5f}x {intercept:+.3f}",
                        transform=ax.transAxes, fontsize=8, color=colour,
                        ha="right", va="top")
    _finish(ax, "seconds from the first cue", "force (N)",
            f"{sensor.upper()}: press force with a fixed and a local zero")
    ax.legend(frameon=False, fontsize=8)
    return fig


def plot_response_waveforms(segments: list, sensor: str):
    """analyze_baseline_drift.R: the trace around the first few cues.

    The figure that picked the look-back window. Each cue's trace is
    strung after the last, blue at the cue, red at the peak with its
    value, and a green dot at every 50 ms step back from the cue. Follow
    the dots leftwards: they sit flat for about 250 ms and then start to
    lift, which is the tail of the previous press, so 250 ms is as far
    back as the rest level can be trusted.
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(14, 3.4))
    if not segments:
        _finish(ax, "cues strung end to end (s)", "raw counts",
                f"{sensor.upper()}: no cue with a press after it")
        return fig
    offset = 0.0
    for number, segment in enumerate(segments, start=1):
        t = segment["t"] - segment["t"][0] + offset
        ax.plot(t, segment["values"], color="#0f172a", lw=0.7)
        ax.axvline(t[segment["cue_index"]], color=STIM_COLOUR, ls=":", lw=1)
        peak_x = t[segment["peak_index"]]
        ax.axvline(peak_x, color=RESPONSE_COLOUR, ls=":", lw=1)
        ax.text(peak_x, segment["peak_value"],
                f"{segment['peak_value']:.0f} cts", color=RESPONSE_COLOUR,
                fontsize=7, ha="center", va="bottom")
        for dot in segment["dot_indices"]:
            ax.plot(t[dot], segment["values"][dot], "o", color=DOT_COLOUR,
                    ms=3.5, alpha=0.85)
        ax.text(t[segment["cue_index"]], float(np.nanmin(segment["values"])),
                f"cue {number}", color="#64748b", fontsize=7, ha="center",
                va="top")
        offset = float(t[-1])
    _finish(ax, "cues strung end to end (s)", "raw counts",
            f"{sensor.upper()}: rest level before each cue, "
            "green dots every 50 ms back")
    return fig


def plot_block_distribution(analytic: pd.DataFrame):
    """Data_analysis_Final.R plot 1: reaction times per block.

    Violin plus box per block, the two untrained blocks in red and the
    trained chunks in blue, which is his colouring. The shape matters as
    much as the mean: a block whose violin has a long right tail is one
    where a few trials went badly, not one that was uniformly slower.
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.2))
    if analytic.empty:
        _finish(ax, "block", "reaction time (ms)",
                "Distribution of reaction times: nothing to plot")
        return fig
    blocks = sorted(int(b) for b in analytic["block_all"].unique())
    data = [analytic.loc[analytic["block_all"] == b,
                         "time_difference_ms"].to_numpy() for b in blocks]
    violin = ax.violinplot(data, positions=blocks, showextrema=False,
                           widths=0.8)
    for body, block in zip(violin["bodies"], blocks):
        body.set_facecolor(RESPONSE_COLOUR if block in (0, 6) else "#2563eb")
        body.set_alpha(0.55)
    ax.boxplot(data, positions=blocks, widths=0.15, showfliers=False,
               patch_artist=True, boxprops=dict(facecolor="white"))
    _finish(ax, "block (0 pretest, 1-5 main, 6 aftertest)",
            "reaction time (ms)", "Distribution of reaction times by block")
    return fig


def plot_block_means(means: pd.DataFrame):
    """Data_analysis_Final.R plot 2: the model means with intervals.

    One point per block with its 95 percent interval, joined so the
    learning curve is readable. Two blocks whose intervals overlap are
    not separated by this design, whatever the line between them looks
    like.
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.2))
    if means.empty:
        _finish(ax, "block", "estimated RT (ms)",
                "Model means by block: nothing to plot")
        return fig
    ax.plot(means["block"], means["emmean"], "-", color="#0f172a")
    for _, row in means.iterrows():
        colour = RESPONSE_COLOUR if int(row["block"]) in (0, 6) else "#2563eb"
        ax.errorbar(row["block"], row["emmean"],
                    yerr=[[row["emmean"] - row["lower"]],
                          [row["upper"] - row["emmean"]]],
                    fmt="o", color=colour, capsize=4)
    _finish(ax, "block", "estimated RT (ms)",
            "Model means by block, 95 percent intervals")
    return fig


def plot_block_spaghetti(analytic: pd.DataFrame):
    """Data_analysis_Final.R plot 3: one grey line per participant.

    The group mean sits on top with its standard error, but the grey
    lines are the point: they show the between-participant spread the
    model's within-participant intervals leave out, and one person going
    the other way is visible here and nowhere else.
    """
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.2))
    if analytic.empty:
        _finish(ax, "block", "mean RT per participant (ms)",
                "Individual curves: nothing to plot")
        return fig
    per_person = (analytic.groupby(["participant", "block_all"])
                  ["time_difference_ms"].mean().reset_index())
    group = (per_person.groupby("block_all")["time_difference_ms"]
             .agg(["mean", "std", "count"]).reset_index())
    group["se"] = np.where(group["count"] > 1,
                           group["std"] / np.sqrt(group["count"]), 0.0)
    for _, person in per_person.groupby("participant"):
        ax.plot(person["block_all"], person["time_difference_ms"],
                color="#64748b", alpha=0.55, lw=1)
    ax.plot(group["block_all"], group["mean"], color="#0f172a")
    for _, row in group.iterrows():
        colour = RESPONSE_COLOUR if int(row["block_all"]) in (0, 6) \
            else "#2563eb"
        ax.errorbar(row["block_all"], row["mean"], yerr=row["se"], fmt="o",
                    color=colour, capsize=4)
    _finish(ax, "block", "mean RT per participant (ms)",
            "Individual curves (grey) with the group mean")
    return fig


# ------------------------------------------------------------ one-call runs

def bench_report(raw: pd.DataFrame, offset=RAYAN_STATIC_OFFSET,
                 rows: str = "all", segment: int | None = None,
                 n_per_count: float | None = None) -> dict:
    """Every table his sensor scripts produce, from one stream.

    The convenience wrapper: peaks, his peak summary, the noise floor,
    the SNR table, repeatability, the saturation counts and the per-pad
    baseline shift, in one dict. Analyses stay separate above so a
    caller can run one of them; this exists so the common case is one
    line.
    """
    peaks = stim_peaks(raw, offset=offset, rows=rows)
    noise = baseline_noise(raw, offset=offset)
    seg = segment_length(peaks, segment)
    rep = repeatability(peaks, seg)
    shifts = {}
    for col in fsr_columns(raw):
        shifts[col] = baseline_shift(raw, col, rows=rows, offset=offset)
    summary = snr_summary(peaks, noise)
    if not summary.empty:
        summary["mean_peak_n"] = counts_to_newtons(summary["grand_avg_signal"],
                                                   n_per_count)
    return {"peaks": peaks, "peak_summary": peak_summary(peaks),
            "noise": noise, "snr": summary, "repeatability": rep,
            "segment_trials": seg, "saturation": saturation(peaks),
            "baseline_shift": shifts}
