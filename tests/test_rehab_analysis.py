"""Regression tests for the analysis module.

Nothing under tests/ imported rehab_analysis before this file, which is
how a boolean column that read back as all-NaN survived: every check
built on those columns treats missing as "nothing to report", so a block
where every cue failed to reach the device came out looking clean.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "analysis"))

import rehab_analysis as ra


FINGER_COLS = ["iso_ts", "block_t_s", "participant", "age", "hand", "block",
               "trial", "lane", "time_difference_ms", "early_late", "points",
               "feedback", "error_type", "keys_pressed", "correct_keys",
               "num_presses", "had_incorrect_press", "first_incorrect_ms",
               "first_incorrect_lane", "bpm_at_trial", "streak_at_trial",
               "in_recovery", "song_time_s", "peak_force_n", "impulse_n",
               "phase", "loud_trial", "timeout_ms", "force_window_sum",
               "force_window_peaks", "stim_delivered", "cue_mode"]

EMPTY = [12.0, 15.0, 10.0, 18.0]
PRELOAD = [20.0, 25.0, 18.0, 40.0]


def _calibration(gaps, created_at="2026-08-05T09:00:00"):
    resting = [EMPTY[i] + PRELOAD[i] for i in range(4)]
    return {
        "created_at": created_at,
        "device_port": "/dev/cu.usbserial-test",
        "hand": "right",
        "empty": list(EMPTY),
        "resting": resting,
        "press": [resting[i] + gaps[i] for i in range(4)],
        "press_all": [resting[i] + gaps[i] * 0.88 for i in range(4)],
        "preload": list(PRELOAD),
        "gap": list(gaps),
        "on_delta": [round(g * 0.35, 1) for g in gaps],
        "off_delta": [round(g * 0.20, 1) for g in gaps],
        "multi_finger_deficit": 0.12,
    }


def _write_session(root, name, gaps, *, cal=True, delivered="TRUE",
                   wrong_on=(), clock="090000", day="2026-08-05",
                   n_trials=32, effort=1.40, spill=0.12, created_at=None):
    """One game folder. Behaviour is fixed, so two calls differing only in
    `gaps` describe the same hand on two differently sensitive devices."""
    folder = Path(root) / day / f"{name}_{clock}_classic"
    folder.mkdir(parents=True, exist_ok=True)

    rows = []
    for t in range(1, n_trials + 1):
        lane0 = (t - 1) % 4
        peaks = {i: (effort if i == lane0 else spill) * gaps[i]
                 for i in range(4)}
        rows.append({
            **{c: "" for c in FINGER_COLS},
            "iso_ts": f"{day}T09:00:00", "block_t_s": t * 1.2,
            "participant": name, "age": 30, "hand": "right",
            "block": "classic", "trial": t, "lane": lane0 + 1,
            "time_difference_ms": 400.0 + lane0, "early_late": "Good",
            "points": 3, "feedback": "Good",
            "keys_pressed": lane0 + 1, "correct_keys": lane0 + 1,
            "num_presses": 1,
            "had_incorrect_press": "TRUE" if t in wrong_on else "FALSE",
            "streak_at_trial": t, "in_recovery": "FALSE",
            "peak_force_n": round(peaks[lane0], 3),
            "impulse_n": round(peaks[lane0] * 0.19, 3),
            "loud_trial": "FALSE", "timeout_ms": 1000,
            "force_window_sum": round(sum(peaks.values()), 3),
            "force_window_peaks": ";".join(
                f"{i + 1}:{v:.3f}" for i, v in sorted(peaks.items())),
            "stim_delivered": delivered, "cue_mode": "both"})

    with open(folder / "trials.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FINGER_COLS)
        w.writeheader()
        w.writerows(rows)

    meta = {
        "participant": name, "hand": "right",
        "started_at": f"{day}T09:00:00",
        "source_name": "MultiSerial(right@/dev/cu.usbserial-test)",
        "block_summary": {"block": "classic", "status": "completed",
                          "trials": n_trials, "hit_rate": 1.0,
                          "avg_rt_ms": 400.0, "duration_s": 60.0,
                          "paused_total_s": 0.0,
                          "force_unit": "sensor counts"},
        "calibration": (_calibration(gaps, created_at or "2026-08-05T09:00:00")
                        if cal else {}),
    }
    (folder / "metadata.json").write_text(json.dumps(meta))
    return folder


# ------------------------------------------------------------ boolean columns

class TestAsBool:
    """read_csv already turns TRUE/FALSE into real booleans, so mapping
    the strings a second time wiped every value."""

    def test_real_booleans_pass_through(self):
        s = pd.Series([True, False, True])
        assert ra.as_bool(s).tolist() == [True, False, True]

    def test_uppercase_text_parses(self):
        s = pd.Series(["TRUE", "FALSE", "TRUE"], dtype=object)
        assert ra.as_bool(s).tolist() == [True, False, True]

    def test_mixed_text_and_blank(self):
        out = ra.as_bool(pd.Series(["TRUE", "", None, "FALSE"], dtype=object))
        assert out.iloc[0] is True
        assert out.iloc[3] is False
        assert pd.isna(out.iloc[1]) and pd.isna(out.iloc[2])

    def test_nothing_becomes_all_nan(self):
        for values in ([True, False], ["TRUE", "FALSE"], ["true", "false"]):
            out = ra.as_bool(pd.Series(values, dtype=object))
            assert out.notna().all(), values


class TestBooleanColumnsSurviveLoading:

    def test_undelivered_cues_are_not_lost(self, tmp_path):
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       delivered="FALSE", wrong_on=(3, 7, 11))
        trials = ra.prepare("all", root=tmp_path)["trials"]

        assert trials["stim_delivered"].notna().all()
        assert (trials["stim_delivered"] == False).sum() == 32
        assert int((trials["had_incorrect_press"] == True).sum()) == 3

    def test_cue_failure_count_is_never_negative(self, tmp_path, capsys):
        """Concatenating games leaves the column as object dtype, where
        `~` is integer bitwise negation."""
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       delivered="FALSE", clock="090000")
        _write_session(tmp_path, "P2", [49.0, 60.0, 75.0, 49.0],
                       delivered="TRUE", clock="100000")
        ctx = ra.prepare("all", root=tmp_path)
        ra.sec_quality(ctx["trials"], ctx["folders"], ctx["metas"])

        line = [l for l in capsys.readouterr().out.splitlines()
                if "cue commands not delivered" in l][0]
        assert "32 of 64" in line, line
        assert "-" not in line.split(":")[1]


# ------------------------------------------------------- the calibration fix

class TestCalibrationRemovesSensorSkew:
    """The same hand on two devices whose pinky pads differ. Raw counts
    must disagree and the normalised figure must not."""

    @staticmethod
    def _two_devices(tmp_path):
        _write_session(tmp_path, "HOT", [49.0, 60.0, 75.0, 115.0],
                       clock="090000")
        _write_session(tmp_path, "EVEN", [49.0, 60.0, 75.0, 49.0],
                       clock="100000")
        return (ra.prepare("HOT", root=tmp_path),
                ra.prepare("EVEN", root=tmp_path))

    def test_raw_counts_disagree_between_devices(self, tmp_path):
        hot, even = self._two_devices(tmp_path)
        h = hot["trials"]
        e = even["trials"]
        raw_h = h.loc[h["finger"] == "Pinky", "peak_force_n"].mean()
        raw_e = e.loc[e["finger"] == "Pinky", "peak_force_n"].mean()
        assert raw_h / raw_e == pytest.approx(115.0 / 49.0, rel=1e-6)

    def test_normalised_force_agrees_between_devices(self, tmp_path):
        hot, even = self._two_devices(tmp_path)
        h = hot["trials"]
        e = even["trials"]
        cal_h = h.loc[h["finger"] == "Pinky", "peak_force_cal"].mean()
        cal_e = e.loc[e["finger"] == "Pinky", "peak_force_cal"].mean()
        assert cal_h == pytest.approx(cal_e, rel=1e-9)
        assert cal_h == pytest.approx(1.40, rel=1e-6)

    def test_normalised_force_is_flat_across_fingers(self, tmp_path):
        hot, _ = self._two_devices(tmp_path)
        per = hot["trials"].groupby("finger")["peak_force_cal"].mean()
        assert per.max() - per.min() == pytest.approx(0.0, abs=1e-9)
        # The raw column over the same trials is anything but flat.
        raw = hot["trials"].groupby("finger")["peak_force_n"].mean()
        assert raw.max() / raw.min() == pytest.approx(115.0 / 49.0, rel=1e-6)

    def test_individuation_matches_between_devices(self, tmp_path):
        hot, even = self._two_devices(tmp_path)
        ind_h = ra.individuation(hot["trials"], hot["calset"])
        ind_e = ra.individuation(even["trials"], even["calset"])
        assert ind_h["corrected"].all() and ind_e["corrected"].all()
        assert (ind_h["individuation_cal"].mean()
                == pytest.approx(ind_e["individuation_cal"].mean(), rel=1e-9))
        # The uncorrected index is the one the hardware moves.
        assert (ind_h["individuation"].mean()
                != pytest.approx(ind_e["individuation"].mean(), rel=1e-4))

    def test_no_calibration_leaves_columns_blank_not_wrong(self, tmp_path):
        _write_session(tmp_path, "OLD", [49.0, 60.0, 75.0, 115.0], cal=False)
        ctx = ra.prepare("all", root=tmp_path)
        trials = ctx["trials"]
        assert ctx["calset"].status == "none"
        assert trials["peak_force_cal"].isna().all()
        assert not trials["force_calibrated"].any()
        assert trials["peak_force_n"].notna().all()


class TestCalibrationGrouping:

    def test_same_timestamp_different_numbers_stay_apart(self, tmp_path):
        """created_at alone is not an identity. Two profiles saved in the
        same second must not collapse into one printed table."""
        _write_session(tmp_path, "HOT", [49.0, 60.0, 75.0, 115.0],
                       clock="090000")
        _write_session(tmp_path, "EVEN", [49.0, 60.0, 75.0, 49.0],
                       clock="100000")
        cs = ra.prepare("all", root=tmp_path)["calset"]
        assert len(cs.stamps) == 2
        assert cs.status == "multiple"

    def test_identical_calibrations_still_group(self, tmp_path):
        _write_session(tmp_path, "A", [49.0, 60.0, 75.0, 115.0],
                       clock="090000")
        _write_session(tmp_path, "B", [49.0, 60.0, 75.0, 115.0],
                       clock="100000")
        cs = ra.prepare("all", root=tmp_path)["calset"]
        assert len(cs.stamps) == 1
        assert cs.status == "single"

    def test_signature_ignores_formatting_only_changes(self):
        a = _calibration([49.0, 60.0, 75.0, 115.0])
        b = _calibration([49, 60, 75, 115])
        assert ra.calibration_signature(a) == ra.calibration_signature(b)


class TestGameLabels:

    def test_two_games_in_one_minute_keep_separate_labels(self, tmp_path):
        """Sections group on game_label, so a collision merges two games
        and sec_compare then reports there is nothing to compare."""
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       clock="090000")
        _write_session(tmp_path, "P2", [49.0, 60.0, 75.0, 49.0],
                       clock="090000")
        trials = ra.prepare("all", root=tmp_path)["trials"]
        assert trials["game"].nunique() == 2
        assert trials["game_label"].nunique() == 2

    def test_distinct_times_keep_the_plain_label(self, tmp_path):
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       clock="090000")
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       clock="101500")
        labels = set(ra.prepare("all", root=tmp_path)["trials"]["game_label"])
        assert labels == {"09:00 classic", "10:15 classic"}


# -------------------------------------------------------------- empty states

class TestSectionsAlwaysSaySomething:
    """A section that prints nothing reads as a section that failed."""

    @pytest.mark.parametrize("section", [
        "sec_compare", "sec_rhythm", "sec_phase", "sec_objective_one",
    ])
    def test_trial_sections_explain_themselves(self, tmp_path, capsys,
                                               section):
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0],
                       delivered="FALSE")
        ctx = ra.prepare("all", root=tmp_path)
        getattr(ra, section)(ctx["trials"])
        assert capsys.readouterr().out.strip(), f"{section} printed nothing"

    @pytest.mark.parametrize("section", ["sec_raw", "sec_sampling_note"])
    def test_raw_sections_explain_themselves(self, tmp_path, capsys, section):
        folder = _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0])
        (folder / "raw.csv").write_text(
            "iso_ts,t_perf,sample_idx,fsr1,fsr2,fsr3,fsr4,hand,event,lane,"
            "detail\n"
            + "".join(f"2026-08-05T09:00:0{i % 10},{100.0 + i},{i},0,0,0,0,"
                      f"right,stim,1,trial_id={i}\n" for i in range(60)))
        getattr(ra, section)([folder])
        assert capsys.readouterr().out.strip(), f"{section} printed nothing"


class TestCheckAndCatalogue:

    def test_catalogue_and_check_agree(self, tmp_path, capsys):
        _write_session(tmp_path, "P1", [49.0, 60.0, 75.0, 115.0])
        cat = ra.build_catalogue(tmp_path)
        assert len(cat) == 1
        assert ra.check(tmp_path, verbose=False) is True
        capsys.readouterr()

    def test_check_reports_an_empty_folder(self, tmp_path, capsys):
        assert ra.check(tmp_path, verbose=False) is False
        assert "no recordings" in capsys.readouterr().out
