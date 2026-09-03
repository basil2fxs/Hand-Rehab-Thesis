import os
import re
import sys
import csv
import math
import numpy as np
from pathlib import Path
from scipy.signal import butter, filtfilt, savgol_filter

# ========= Parameters from your viewer (can be adjusted) =========
WIN_POST_DEFAULT = 1.20   # How many seconds after stim to search for peak

MIN_RISE     = 80         # Teasdale: baselineからの最小上昇量
VMAX_MIN     = 30         # Teasdale: 速度ピークの最小値
LP_FORCE_HZ  = 20         # Forceローパス
LP_DFORCE_HZ = 10         # DForceローパス
SG_WIN       = 11         # Savitzky-Golay window（奇数）
SG_POLY      = 3          # Savitzky-Golay 次数

# ==== Search conditions for finding the start of a reaction ====
SEARCH_MIN_S     = -0.05  # 刺激前の50msから探索 (negative means before stimulus)
SEARCH_MAX_S     = 1.20   # この秒数までの範囲に限定して探索
FIRST_SLOPE_MIN  = 25     # DForce の絶対しきい（最小速度）
FIRST_STEP_MIN   = 12     # Force の短時間増分（およそ50ms）しきい
SLOPE_FRAC       = 0.18   # DForce の相対しきい（区間最大の18%）

# ========= CSV Column Names (flexible matching) =========
COL_T_PREFS     = ["t_perf", "ts_perf"]
COL_TREL_MS     = "t_rel_ms"
COL_EVT         = "event"
COL_FSR_LIST    = ["fsr1", "fsr2", "fsr3", "fsr4"]
COL_LANE_PREFS  = ["lane", "active_lane"]
COL_TRIAL_PREFS = ["trial", "trial_no", "trial_id"]
COL_DETAIL_PREF = ["detail", "feedback"]

# ========= Teasdale Onset Detection (from your viewer) =========
def teasdale_onset(force_values, fs=200.0, min_rise=MIN_RISE,
                   search_from=0, search_to=None, prefer_first=True):
    if force_values is None or len(force_values) < 20:
        return None, None, None
    x = np.asarray(force_values, dtype=float)
    baseline = np.mean(x[:min(20, len(x))])

    Wn = min(max(LP_FORCE_HZ/(fs/2.0), 1e-6), 0.999999)
    b, a = butter(2, Wn, btype="low")
    try:
        Force = filtfilt(b, a, x)
    except Exception:
        return None, None, None

    DForce = np.diff(Force) * fs
    if len(DForce) > SG_WIN:
        try:
            win = SG_WIN if SG_WIN % 2 else SG_WIN + 1
            DForce = savgol_filter(DForce, win, SG_POLY)
        except Exception: pass
    Wn_d = min(max(LP_DFORCE_HZ/(fs/2.0), 1e-6), 0.999999)
    bd, ad = butter(2, Wn_d, btype="low")
    if len(DForce) > 20:
        try:
            DForce = filtfilt(bd, ad, DForce)
        except Exception: pass

    if (np.max(Force) - baseline) < min_rise:
        return None, Force, DForce

    lo = max(0, int(search_from))
    hi = len(Force) if search_to is None else max(lo+5, int(search_to))
    hi = min(hi, len(Force))
    if hi - lo < 8 or len(DForce) < 5:
        return None, Force, DForce

    if prefer_first:
        d_seg = DForce[lo:hi-1]
        vmax  = float(np.max(d_seg)) if len(d_seg) > 0 else 0.0
        thr   = max(FIRST_SLOPE_MIN, SLOPE_FRAC * vmax)
        step_k = max(1, int(0.05*fs))

        for j in range(len(d_seg)-step_k):
            i = lo + j
            if d_seg[j] >= thr:
                if (Force[i+step_k] - Force[i]) >= FIRST_STEP_MIN:
                    return int(i), Force, DForce

    d_full = DForce
    Vmax_ind = lo + int(np.argmax(d_full[lo:max(lo+1, hi-1)]))
    Vmax = float(d_full[Vmax_ind])
    if Vmax <= 0 or Vmax < VMAX_MIN:
        return None, Force, DForce

    DForce_int = d_full[:Vmax_ind+1]
    DForce_int_rev = DForce_int[::-1]
    S = Vmax * 0.1
    candidates = np.where(DForce_int_rev < S)[0]
    S_ind = int(candidates[0]) if len(candidates) > 0 else 0

    if len(DForce_int) - S_ind > 0:
        sd = float(np.std(DForce_int[:len(DForce_int)-S_ind]))
        if not np.isfinite(sd) or sd == 0: sd = 1.0
    else:
        sd = 1.0

    onset_candidates = np.where(DForce_int_rev[S_ind:] < (S - sd))[0]
    if len(onset_candidates) > 0:
        onset_rev_ind = int(S_ind + onset_candidates[0])
        response_onset = len(DForce_int) - onset_rev_ind
    else:
        response_onset = Vmax_ind

    onset_idx = int(max(0, min(response_onset, len(Force)-1)))
    if not (lo <= onset_idx < hi):
        return None, Force, DForce
    return onset_idx, Force, DForce

# ========= CSV Loading (from your viewer) =========
def _read_dict_rows(path: Path):
    for enc in ("utf-8", "utf-8-sig", "cp932", "shift_jis", "latin-1"):
        try:
            with path.open("r", encoding=enc, newline="") as f:
                return list(csv.DictReader(f))
        except UnicodeDecodeError:
            continue
    raise RuntimeError(f"Could not read CSV {path} with any common encoding.")

def _first_existing(row, names):
    for n in names:
        v = row.get(n)
        if v is not None: return n, v
    return None, None

def load_session_raw(path: Path):
    rows = _read_dict_rows(path)
    if not rows: raise RuntimeError("CSV is empty")

    t_list, fsr_list, events = [], [[], [], [], []], []

    for row in rows:
        t_sec = None
        _, v_t_pref = _first_existing(row, COL_T_PREFS)
        if v_t_pref is not None:
            try: t_sec = float(v_t_pref)
            except (ValueError, TypeError): pass
        else:
            v_trel = row.get(COL_TREL_MS)
            if v_trel is not None:
                try: t_sec = float(v_trel) / 1000.0
                except (ValueError, TypeError): pass

        evt = (row.get(COL_EVT) or "").strip().lower()
        if evt in ("", "sample"):
            if t_sec is None or not np.isfinite(t_sec): continue
            t_list.append(t_sec)
            for i, col in enumerate(COL_FSR_LIST):
                try: v = float(row.get(col) or "nan")
                except (ValueError, TypeError): v = float("nan")
                # Subtract 255 from the raw sensor value
                fsr_list[i].append((v - 255.0) if np.isfinite(v) else 0.0)
        else:
            lane = None
            for ln in COL_LANE_PREFS:
                s = row.get(ln)
                if s is not None and str(s).strip().isdigit():
                    lane = int(str(s).strip())
                    break
            detail = ""
            _, v_detail = _first_existing(row, COL_DETAIL_PREF)
            if v_detail is not None: detail = str(v_detail).strip()
            
            _, v_trial = _first_existing(row, COL_TRIAL_PREFS)
            if v_trial is not None: detail = (f"{detail} trial={v_trial}").strip()

            events.append({"type": evt, "time": t_sec, "lane": lane, "detail": detail})

    if not t_list: raise RuntimeError("No sample data found.")
    return np.asarray(t_list), [np.asarray(lst) for lst in fsr_list], events

def estimate_fs(t: np.ndarray):
    d = np.diff(t)
    d = d[(d > 0) & np.isfinite(d)]
    return 1.0 / float(np.median(d)) if len(d) > 0 and np.median(d) > 0 else 200.0

def parse_trial_id(detail: str, fallback_id: int):
    m = re.search(r"trial\s*=\s*(\d+)", detail or "", flags=re.IGNORECASE)
    return int(m.group(1)) if m else fallback_id

# ========= Main Processing Function =========
def process_file(input_path: Path):
    """
    Loads a session CSV, analyzes each trial, and returns a list of result dicts.
    """
    print(f"Processing: {input_path.name}")
    try:
        t, fsr_data, events = load_session_raw(input_path)
        fs = estimate_fs(t)
    except Exception as e:
        print(f"  ERROR: Could not load or parse file. {e}")
        return []

    stim_events = [e for e in events if e["type"] == "stim" and e["time"] is not None and e["lane"] is not None]
    if not stim_events:
        print("  WARNING: No 'stim' events found in the file.")
        return []

    results = []
    auto_id = 0
    for stim_event in stim_events:
        auto_id += 1
        t_stim = stim_event["time"]
        lane = stim_event["lane"]
        trial_id = parse_trial_id(stim_event.get("detail", ""), auto_id)

        # Define a window around the stimulus to analyze
        win_start_t = t_stim + SEARCH_MIN_S # Start search window before stimulus
        win_end_t = t_stim + WIN_POST_DEFAULT
        i_start = np.searchsorted(t, win_start_t, side="left")
        i_end = np.searchsorted(t, win_end_t, side="right")

        # Use teasdale_onset to find the reaction start time
        # We analyze the lane that was stimulated
        analysis_segment = fsr_data[lane][i_start:i_end]
        
        # The search for onset needs to be relative to the segment
        search_from_idx = 0 # Start searching from the beginning of our new segment
        search_to_idx = int(SEARCH_MAX_S * fs)

        onset_idx_rel, _, _ = teasdale_onset(
            analysis_segment, fs=fs, search_from=search_from_idx, search_to=search_to_idx
        )

        rt_ms = None
        peak_search_start_idx = i_start # Default to searching from stimulus time

        if onset_idx_rel is not None:
            onset_t = t[i_start + onset_idx_rel]
            rt_ms = (onset_t - t_stim) * 1000.0
            # Start searching for the peak from the moment of reaction
            peak_search_start_idx = i_start + onset_idx_rel

        # Find the max raw value for each sensor after the reaction starts
        # The search window ends at the same time (t_stim + WIN_POST_DEFAULT)
        max_s1, max_s2, max_s3, max_s4 = (None,) * 4
        if peak_search_start_idx < i_end:
            max_s1 = np.max(fsr_data[0][peak_search_start_idx:i_end])
            max_s2 = np.max(fsr_data[1][peak_search_start_idx:i_end])
            max_s3 = np.max(fsr_data[2][peak_search_start_idx:i_end])
            max_s4 = np.max(fsr_data[3][peak_search_start_idx:i_end])

        results.append({
            "trial_id": trial_id,
            "stim_time_s": t_stim,
            "stim_lane": lane,
            "reaction_time_ms": f"{rt_ms:.1f}" if rt_ms is not None else "N/A",
            "peak_fsr1_raw": max_s1,
            "peak_fsr2_raw": max_s2,
            "peak_fsr3_raw": max_s3,
            "peak_fsr4_raw": max_s4,
        })
    
    print(f"  -> Found and processed {len(results)} trials.")
    return results

def save_results_to_csv(results: list, output_path: Path):
    if not results:
        print("No results to save.")
        return
    
    with output_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=results[0].keys())
        writer.writeheader()
        writer.writerows(results)
    print(f"Successfully saved results to: {output_path}")


if __name__ == "__main__":
    # Automatically find and process all CSV files in the current directory.
    # It will skip any files that it has already created (i.e., those starting with "processed_peaks_").
    
    current_directory = Path.cwd()
    output_dir = current_directory / "Processed Data"
    output_dir.mkdir(parents=True, exist_ok=True)  # Create the directory if it doesn't exist

    print(f"Scanning for CSV files in '{current_directory}'...")

    files_to_process = [
        f for f in current_directory.glob("*.csv") 
        if not f.name.startswith("processed_peaks_")
    ]

    if not files_to_process:
        print("No CSV files to process were found.")
        print("Note: Files starting with 'processed_peaks_' are ignored.")
    else:
        print(f"Found {len(files_to_process)} file(s) to process.")
        for input_file in files_to_process:
            # Process each file
            all_results = process_file(input_file)
            # Save the results to a corresponding new CSV file
            if all_results:
                output_filename = f"processed_peaks_{input_file.stem}.csv"
                output_path = output_dir / output_filename
                save_results_to_csv(all_results, output_path)
            print("-" * 20)