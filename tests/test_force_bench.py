"""finger_rehab/analytics/force_bench.py against Rayan's own numbers.

Two kinds of test here.

Parity. His summary CSVs are in tests/fixtures/rayan, copied out of
bin/old_rayyan_stuff/data, and every ported analysis is checked against
the file his R or Python wrote: the peak table, the noise floor and the
SNR, all twelve repeatability rows, the drift regression's printed
equations, his processed onset CSV, and the block means his plots show.
The point is that a future edit to one of these functions cannot
quietly change what a number means; the sensor characterisation in the
thesis rests on these values.

The 7.4 MB force stream is stored gzipped (pandas reads it by
extension) so the repository does not carry the same file twice at full
size. It is byte for byte the file in bin/old_rayyan_stuff/data/raw.

Our own format. His logger and ours disagree about three things that
would each silently corrupt a result: our event rows hold zeros in the
fsr cells, our pads do not idle at a flat 255, and our timestamps
arrive in bursts. Those are pinned on a synthetic frame in this
logger's own layout, and end to end on a session the real engine wrote.
"""
from __future__ import annotations

import random
import re
import sys
import tempfile
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finger_rehab.analytics import force_bench as fb

FIXTURES = ROOT / "tests" / "fixtures" / "rayan"
RAW_FILE = FIXTURES / "raw_T6_gradual.csv.gz"
HAVE_FIXTURES = RAW_FILE.exists()

needs_fixtures = pytest.mark.skipif(
    not HAVE_FIXTURES, reason="tests/fixtures/rayan is not present")


@pytest.fixture(scope="module")
def bench_raw():
    return fb.load_bench_raw(RAW_FILE)


@pytest.fixture(scope="module")
def bench_peaks(bench_raw):
    return fb.stim_peaks(bench_raw, rows="all")


# ------------------------------------------------ parity with his output

@needs_fixtures
class TestHisSensorNumbers:
    """Max_Peak_Analysis.R, Noise_Analysis.R and repeatability.R against
    the CSVs those scripts wrote."""

    def test_every_cue_produced_a_peak(self, bench_peaks):
        # 599 stim rows in his file, every one with a lane and a window.
        assert len(bench_peaks) == 599
        assert set(bench_peaks["lane"]) == {0}

    def test_peak_summary_matches_his_csv(self, bench_peaks):
        ours = fb.peak_summary(bench_peaks)
        his = pd.read_csv(FIXTURES / "his_overall_peak_force_summary.csv")
        assert list(ours["sensor"]) == list(his["sensor"]) == ["FS1"]
        assert float(ours["overall_max_peak"][0]) == \
            pytest.approx(float(his["overall_max_peak"][0]))
        assert float(ours["overall_avg_peak"][0]) == \
            pytest.approx(float(his["overall_avg_peak"][0]), abs=1e-9)
        assert int(ours["n_presses"][0]) == int(his["n_presses"][0])

    def test_the_peak_is_the_raw_adc_ceiling(self, bench_peaks):
        # His gradual force test ran the pad past its 10 N rating and
        # into the top of the 10-bit converter. If that stops being
        # true the fixture has been replaced with different data.
        assert float(bench_peaks["raw_peak"].max()) == 1022.0
        flags = fb.saturation(bench_peaks)
        assert flags["over_rating"] > 0
        assert flags["at_ceiling"] > 0

    def test_noise_and_snr_match_his_csv(self, bench_raw, bench_peaks):
        noise = fb.baseline_noise(bench_raw)
        fsr1 = noise[noise["sensor"] == "fsr1"].iloc[0]
        assert int(fsr1["n_rest_samples"]) == 8981
        ours = fb.snr_summary(bench_peaks, noise)
        his = pd.read_csv(FIXTURES / "his_grand_average_snr_summary.csv")
        row = ours[ours["sensor"] == "FS1"].iloc[0]
        assert float(row["grand_avg_signal"]) == \
            pytest.approx(float(his["grand_avg_signal"][0]), abs=1e-9)
        assert float(row["grand_avg_noise"]) == \
            pytest.approx(float(his["grand_avg_noise"][0]), abs=1e-9)
        assert float(row["grand_snr"]) == \
            pytest.approx(float(his["grand_snr"][0]), abs=1e-9)

    def test_every_repeatability_row_matches_his_csv(self, bench_peaks):
        ours = fb.repeatability(bench_peaks)
        his = pd.read_csv(FIXTURES / "his_repeatability_summary.csv")
        merged = ours.merge(his, on=["lane", "segment"],
                            suffixes=("", "_his"))
        assert len(merged) == len(his) == 12
        assert np.allclose(merged["mean_force"], merged["mean_force_his"],
                           atol=1e-9)
        assert np.allclose(merged["sd_force"], merged["sd_force_his"],
                           atol=1e-9)
        assert np.allclose(merged["cv_percent"], merged["cv_percent_his"],
                           atol=1e-9)

    def test_the_last_segment_is_the_finger_coming_off(self, bench_peaks):
        # Reading his run rather than only checking it: the mean climbs
        # to 728 counts by segment 11 and collapses to 24 in segment 12.
        rep = fb.repeatability(bench_peaks).set_index("segment")
        assert rep.loc[11, "mean_force"] > 700
        assert rep.loc[12, "mean_force"] < 30
        assert int(rep.loc[12, "n"]) == 49

    def test_a_short_block_gets_shorter_segments(self, bench_peaks):
        few = bench_peaks.head(40)
        assert fb.segment_length(few) == fb.SHORT_SEGMENT_TRIALS
        assert fb.segment_length(bench_peaks) == fb.SEGMENT_TRIALS
        assert fb.segment_length(few, 25) == 25


@needs_fixtures
class TestHisDriftNumbers:
    """analyze_baseline_drift_modified_newtons.R against the equations
    printed on his own figure."""

    def test_the_regressions_match_his_printed_equations(self, bench_raw):
        _frame, fits, mean_diff = fb.drift_newtons(bench_raw, "fsr1")
        raw_slope, raw_intercept = fits["force_n_raw"]
        zero_slope, zero_intercept = fits["force_n_zeroed"]
        # His plot prints y = 0.004x + 1.948 and y = 0.00171x + 0.956.
        assert raw_slope == pytest.approx(0.004, abs=5e-5)
        assert raw_intercept == pytest.approx(1.948, abs=5e-3)
        assert zero_slope == pytest.approx(0.00171, abs=5e-5)
        assert zero_intercept == pytest.approx(0.956, abs=5e-3)
        assert mean_diff == pytest.approx(71.47, abs=0.05)

    def test_the_local_zero_removes_most_of_the_apparent_trend(self,
                                                               bench_raw):
        # The reason the look-back exists: the fixed-zero line climbs
        # more than twice as fast as the locally zeroed one, and the
        # difference is the pad drifting, not the finger.
        _frame, fits, _ = fb.drift_newtons(bench_raw, "fsr1")
        assert fits["force_n_raw"][0] > 2 * fits["force_n_zeroed"][0]

    def test_reading_the_level_off_samples_tells_the_same_story(self,
                                                                bench_raw):
        # Our logs leave no choice: event rows hold zeros, so the level
        # has to come off the nearest sample. On his file, where both
        # conventions are available, they agree to 0.0003 N per second.
        _f1, his_way, _ = fb.drift_newtons(bench_raw, "fsr1", rows="all")
        _f2, our_way, _ = fb.drift_newtons(bench_raw, "fsr1", rows="samples")
        for key in ("force_n_raw", "force_n_zeroed"):
            assert his_way[key][0] == pytest.approx(our_way[key][0],
                                                    abs=3e-4)

    def test_the_baseline_climbed_over_his_run(self, bench_raw):
        # analyze_baseline_drift_modified.R read this off the blue
        # series by eye: the pad's rest level walks up over ten minutes.
        shift = fb.baseline_shift(bench_raw, "fsr1")
        assert shift > 20
        levels = fb.stim_response_levels(bench_raw, "fsr1")
        assert set(levels["event_type"]) == {"Stim", "Response"}
        assert len(levels[levels["event_type"] == "Stim"]) == 599


@needs_fixtures
class TestHisOnsetCsv:
    """raw/process_force_peaks.py against the CSV it wrote."""

    @pytest.fixture(scope="class")
    def his(self):
        frame = pd.read_csv(FIXTURES / "his_processed_peaks.csv")
        frame["rt"] = pd.to_numeric(frame["reaction_time_ms"],
                                    errors="coerce")
        return frame

    def test_onsets_match_at_his_sample_rate(self, bench_raw, his):
        ours = fb.processed_peaks(bench_raw, fs_mode="median")
        assert len(ours) == len(his) == 599
        found_his = his["rt"].notna().to_numpy()
        found_ours = ours["reaction_time_ms"].notna().to_numpy()
        # Same 85 cues with no detectable movement, same 514 with one.
        assert int((~found_his).sum()) == 85
        assert (found_his == found_ours).all()
        both = found_his & found_ours
        diff = np.abs(his.loc[both, "rt"].to_numpy()
                      - ours.loc[both, "reaction_time_ms"].to_numpy())
        # His CSV is written to one decimal, so 0.05 ms is the rounding.
        assert diff.max() <= 0.05

    def test_peaks_match_on_every_cue(self, bench_raw, his):
        ours = fb.processed_peaks(bench_raw, fs_mode="median")
        assert np.array_equal(his["peak_fsr1_raw"].to_numpy(),
                              ours["peak_fsr1_raw"].to_numpy())
        assert np.array_equal(his["stim_lane"].to_numpy(),
                              ours["stim_lane"].to_numpy())

    def test_the_sample_rate_rule_moves_some_onsets(self, bench_raw, his):
        # Not cosmetic: the rate sets the filter cutoffs and the end of
        # the search, so the two rules disagree by a few ms on his clean
        # stream. Ours has to use span (see the burst test below); this
        # pins how much that costs so a future change cannot hide it.
        median = fb.processed_peaks(bench_raw, fs_mode="median")
        span = fb.processed_peaks(bench_raw, fs_mode="span")
        both = (median["reaction_time_ms"].notna()
                & span["reaction_time_ms"].notna()).to_numpy()
        diff = np.abs(median.loc[both, "reaction_time_ms"].to_numpy()
                      - span.loc[both, "reaction_time_ms"].to_numpy())
        assert int((diff > 0.05).sum()) == 39
        assert diff.max() < 6.0

    def test_his_trial_numbers_restart_so_stim_order_is_the_key(self,
                                                                bench_raw):
        ours = fb.processed_peaks(bench_raw, fs_mode="median")
        # trial_id comes from his "trial=N" and restarts per block, so
        # joining two runs on it lines up the wrong trials. stim_order
        # is unique and monotonic, which is why it exists.
        assert ours["trial_id"].duplicated().any()
        assert list(ours["stim_order"]) == list(range(1, 600))

    def test_block_slices_follow_his_three_panels(self, bench_raw):
        ours = fb.processed_peaks(bench_raw, fs_mode="median")
        slices = fb.block_slices(ours)
        assert list(slices) == ["block1 random", "block2 structured",
                                "block3 random final"]
        assert len(slices["block1 random"]) == 50
        assert len(slices["block2 structured"]) == 500
        # 599 cues, not 600, so his final panel is one short.
        assert len(slices["block3 random final"]) == 49


@needs_fixtures
class TestHisBlockPipeline:
    """Data_analysis_Final.R on his three trial logs."""

    @pytest.fixture(scope="class")
    def analytic(self):
        trials = fb.load_bench_trials(sorted(FIXTURES.glob("trials_*.csv")))
        return fb.block_table(trials)

    def test_the_analytic_set_is_his(self, analytic):
        assert len(analytic) == 1582
        assert analytic.groupby("block_all").size().to_dict() == {
            0: 89, 1: 300, 2: 300, 3: 300, 4: 298, 5: 295}
        # Every aftertest trial in all three files timed out, so his
        # posttest block never reaches the model. Worth knowing before
        # anyone reads a pre against post contrast off his data.
        assert 6 not in set(analytic["block_all"])

    def test_the_block_means_match_his_plots(self, analytic):
        means, _pairs, _post, _trend, info = fb.block_model(analytic)
        expected = [299.16, 215.05, 178.17, 168.44, 144.64, 143.19]
        assert np.allclose(means["emmean"], expected, atol=0.01)
        assert info["n_people"] == 3
        assert info["df_res"] == 1574

    def test_holm_adjustment_matches_his_pairwise_table(self, analytic):
        _means, pairs, _post, _trend, _info = fb.block_model(analytic)
        adjusted = pairs.set_index("contrast")["p_holm"]
        assert adjusted["2 - 3"] == pytest.approx(0.2468, abs=1e-4)
        assert adjusted["4 - 5"] == pytest.approx(0.8197, abs=1e-4)
        others = adjusted.drop(["2 - 3", "4 - 5", "3 - 4", "3 - 5"])
        assert (others < 0.001).all()

    def test_the_linear_trend_over_the_trained_blocks(self, analytic):
        _means, _pairs, post, trend, _info = fb.block_model(analytic)
        assert trend is not None
        assert trend["estimate"] == pytest.approx(-177.254, abs=0.01)
        assert trend["p"] < 1e-9
        # No aftertest survives his own filter, so the contrast he
        # planned cannot be run on his data.
        assert post is None

    def test_holm_is_monotonic_and_bounded(self):
        raw = [0.001, 0.02, 0.04, 0.5]
        adjusted = fb.holm(raw)
        assert list(adjusted) == sorted(adjusted)
        assert adjusted.max() <= 1.0
        assert adjusted[0] == pytest.approx(0.004)


# ------------------------------------------- this logger's own conventions

def _our_frame(n_cues=8, hz=200.0, lanes=(0, 1, 5), rest=(258, 262, 290),
               bump=180.0):
    """A raw.csv in this logger's layout: eight fsr columns, event rows
    with zeros in them, lanes 0 to 7, trial_id=N in detail, and pads
    that idle well away from his flat 255."""
    columns = ["iso_ts", "t_perf", "sample_idx", *[f"fsr{i}" for i in
                                                   range(1, 9)],
               "hand", "event", "lane", "detail"]
    rng = random.Random(7)
    levels = {lane: rest[i] for i, lane in enumerate(lanes)}
    cues = [3.0 + 1.5 * k for k in range(n_cues)]
    order = [lanes[k % len(lanes)] for k in range(n_cues)]
    rows = []
    t = 0.0
    idx = 0
    while t < cues[-1] + 2.0:
        values = {f"fsr{i}": 0.0 for i in range(1, 9)}
        for lane, level in levels.items():
            values[fb.lane_column(lane)] = level + rng.gauss(0.0, 0.6)
        for cue, lane in zip(cues, order):
            since = t - (cue + 0.25)
            if 0.0 <= since < 0.30:
                col = fb.lane_column(lane)
                values[col] += bump * np.sin(np.pi * since / 0.30)
        idx += 1
        rows.append({"iso_ts": "2026-09-01T10:00:00.000", "t_perf": t,
                     "sample_idx": idx, "hand": "both", "event": "",
                     "lane": "", "detail": "", **values})
        t += 1.0 / hz
    for k, (cue, lane) in enumerate(zip(cues, order), start=1):
        for offset, event in ((0.0, "stim"), (0.30, "press")):
            idx += 1
            rows.append({"iso_ts": "2026-09-01T10:00:00.000",
                         "t_perf": cue + offset, "sample_idx": idx,
                         "hand": "both", "event": event, "lane": lane,
                         "detail": f"trial_id={k}",
                         # The trap: our event rows carry no force. 9999
                         # here so any function that reads one shows up.
                         **{f"fsr{i}": 9999 for i in range(1, 9)}})
    frame = pd.DataFrame(rows, columns=columns).sort_values(
        "t_perf", kind="stable").reset_index(drop=True)
    frame["event"] = frame["event"].astype(str)
    return frame


class TestOurLoggerConventions:
    """The three ways his assumptions break on our logs."""

    def test_force_is_never_read_off_an_event_row(self):
        frame = _our_frame()
        peaks = fb.stim_peaks(frame, offset=fb.resting_offsets(frame),
                              rows="samples")
        assert len(peaks) == 8
        # 9999 sits on every event row. Any peak near it means an event
        # row was scanned, which would put every result out by 9700.
        assert peaks["raw_peak"].max() < 1000
        assert (peaks["peak_counts"] > 120).all()
        assert (peaks["peak_counts"] < 200).all()

    def test_the_resting_level_stands_in_for_his_flat_255(self):
        frame = _our_frame()
        offsets = fb.resting_offsets(frame)
        assert offsets["fsr1"] == pytest.approx(258, abs=2)
        assert offsets["fsr2"] == pytest.approx(262, abs=2)
        assert offsets["fsr6"] == pytest.approx(290, abs=2)
        # Using his constant instead would credit the pinky pad with an
        # extra 35 counts of press it never made.
        his_way = fb.stim_peaks(frame, offset=fb.RAYAN_STATIC_OFFSET,
                                rows="samples")
        ours = fb.stim_peaks(frame, offset=offsets, rows="samples")
        pinky = his_way[his_way["lane"] == 5]["peak_counts"].mean() \
            - ours[ours["lane"] == 5]["peak_counts"].mean()
        assert pinky == pytest.approx(35, abs=3)

    def test_lanes_above_three_are_the_left_hand(self):
        frame = _our_frame()
        peaks = fb.stim_peaks(frame, offset=fb.resting_offsets(frame),
                              rows="samples")
        assert set(peaks["sensor"]) == {"fsr1", "fsr2", "fsr6"}
        assert fb.lane_side(5, "both") == "left"
        assert fb.lane_side(1, "both") == "right"
        # A one-handed left session still writes lanes 0 to 3.
        assert fb.lane_side(1, "left") == "left"
        assert fb.lane_finger(5) == "Middle"

    def test_burst_timestamps_break_the_median_rate_rule(self):
        # Two samples arrive from one serial read microseconds apart,
        # then a gap. His median-gap rule reads that as thousands of Hz.
        t = np.sort(np.concatenate([np.arange(0, 10, 0.01),
                                    np.arange(0, 10, 0.01) + 0.0002]))
        assert fb.estimate_fs(t, "median") > 1000
        assert fb.estimate_fs(t, "span") == pytest.approx(200, rel=0.02)

    def test_rest_windows_leave_the_cue_windows_out(self):
        frame = _our_frame()
        noise = fb.baseline_noise(frame)
        fsr1 = noise[noise["sensor"] == "fsr1"].iloc[0]
        cues = frame.loc[frame["event"] == "stim", "t_perf"].to_numpy(float)
        # The windows overlap here (cues 1.5 s apart, windows 1.7 s
        # long), so the exclusion is one run from the first cue to the
        # last, not eight separate ones. Getting this wrong would leave
        # press samples in the noise floor and inflate every sd.
        span = float(frame["t_perf"].max()) - float(frame["t_perf"].min())
        excluded = (cues.max() + fb.NOISE_EXCLUDE_S[1]) \
            - (cues.min() - fb.NOISE_EXCLUDE_S[0])
        assert int(fsr1["n_rest_samples"]) == \
            pytest.approx((span - excluded) * 200, abs=20)
        # Noise is the pad sitting still, so it must not pick up presses.
        assert float(fsr1["baseline_noise_sd"]) < 2.0

    def test_trial_ids_read_from_both_loggers(self):
        assert fb.parse_trial("trial=7") == 7
        assert fb.parse_trial("trial_id=7;stage=loc") == 7
        assert fb.parse_trial("", fallback=3) == 3
        assert fb.parse_trial(None) is None

    def test_phase_maps_to_his_block_numbers(self):
        rows = []
        k = 0
        for phase, count in (("pretest", 6), ("", 12), ("aftertest", 6)):
            for i in range(count):
                k += 1
                rows.append({"participant": "P1", "game": "g", "trial": k,
                             "phase": phase, "time_difference_ms": 300.0 - i,
                             "had_incorrect_press": False,
                             "keys_pressed": "1", "correct_keys": "1"})
        # One trial out of range and one wrong finger have to drop, and
        # the chunks are numbered before the filter as his R does, so
        # the wrong press thins its own chunk instead of pulling every
        # later trial back a place.
        rows[3]["time_difference_ms"] = 1500.0
        rows[10]["keys_pressed"] = "2"
        frame = fb.session_trials_as_bench(pd.DataFrame(rows))
        analytic = fb.block_table(frame, chunk=5)
        assert analytic.groupby("block_all").size().to_dict() == {
            0: 5, 1: 4, 2: 5, 3: 2, 6: 6}
        assert analytic.loc[analytic["block_all"].isin([0, 6]),
                            "is_random"].all()
        assert not analytic.loc[analytic["block_all"] == 1,
                                "is_random"].any()

    def test_a_keyboard_block_has_nothing_to_measure(self):
        # No device means no sample rows at all. Every analysis has to
        # come back empty rather than raise, because a keyboard block is
        # a normal thing to have in a selection.
        frame = _our_frame()
        events_only = frame[frame["event"] != ""].copy()
        assert fb.stim_peaks(events_only, rows="samples").empty
        assert fb.baseline_noise(events_only).empty
        assert fb.processed_peaks(events_only).empty
        assert fb.resting_offsets(events_only) == {}
        assert np.isnan(fb.baseline_shift(events_only, "fsr1",
                                          rows="samples"))

    def test_off_target_share_reads_the_spill(self):
        frame = _our_frame()
        offsets = fb.resting_offsets(frame)
        processed = fb.off_target_share(
            fb.processed_peaks(frame, offset=offsets, fs_mode="span"))
        assert len(processed) == 8
        # The synthetic press only moves its own pad, so the share of
        # the spread landing off target has to be near zero.
        assert processed["off_share"].max() < 0.05
        assert (processed["on_target"] > 120).all()

    def test_bench_report_gathers_every_table(self):
        frame = _our_frame()
        report = fb.bench_report(frame, offset=fb.resting_offsets(frame),
                                 rows="samples")
        assert set(report) == {"peaks", "peak_summary", "noise", "snr",
                               "repeatability", "segment_trials",
                               "saturation", "baseline_shift"}
        assert len(report["peaks"]) == 8
        assert report["saturation"] == {"over_rating": 0, "at_ceiling": 0}
        assert (report["snr"]["grand_snr"] > 20).all()
        # Newtons off the default conversion: 150-odd counts at 51.2
        # counts per newton is about 3 N.
        assert (report["snr"]["mean_peak_n"] > 2.0).all()
        assert (report["snr"]["mean_peak_n"] < 4.5).all()

    def test_the_session_calibration_overrides_his_constant(self):
        counts = np.array([512.0])
        assert fb.counts_to_newtons(counts)[0] == pytest.approx(10.0)
        assert fb.counts_to_newtons(counts, 0.03)[0] == pytest.approx(15.36)


# --------------------------------------------------------------- plotting

class TestFigures:
    """Every helper draws something, on his data and on a short block of
    ours, and says so on the axis rather than coming back blank."""

    @pytest.fixture(autouse=True)
    def _close(self):
        yield
        plt.close("all")

    def test_every_helper_draws_on_our_short_block(self):
        frame = _our_frame()
        offsets = fb.resting_offsets(frame)
        report = fb.bench_report(frame, offset=offsets, rows="samples")
        figures = [
            fb.plot_repeatability(report["repeatability"],
                                  segment_trials=report["segment_trials"]),
            fb.plot_snr(report["snr"]),
            fb.plot_cv_heatmap(report["repeatability"], min_presses=2),
            fb.plot_finger_peaks(report["peaks"], 0,
                                 report["repeatability"]),
            fb.plot_stim_response(
                fb.stim_response_levels(frame, "fsr1", offset=offsets,
                                        rows="samples"), "fsr1"),
            fb.plot_response_waveforms(
                fb.response_waveforms(frame, "fsr1", rows="samples",
                                      lane=0, anchor="cue"), "fsr1"),
        ]
        for figure in figures:
            assert figure.axes
            assert figure.axes[0].get_title()

    def test_the_trial_peak_panels_are_one_per_pad_on_that_board(self):
        frame = _our_frame(lanes=(0, 1, 2))
        processed = fb.processed_peaks(frame,
                                       offset=fb.resting_offsets(frame),
                                       fs_mode="span")
        figure = fb.plot_trial_peaks(processed)
        assert len(figure.axes) == 4
        assert [ax.get_ylabel().split("\n")[0] for ax in figure.axes] == \
            list(fb.FINGERS)

    def test_an_empty_frame_says_why_instead_of_drawing_nothing(self):
        blank = pd.DataFrame(columns=["lane", "segment", "n", "mean_force",
                                      "sd_force", "cv_percent"])
        for figure, wanted in (
                (fb.plot_repeatability(blank), "no cued presses"),
                (fb.plot_cv_heatmap(blank), "no segment"),
                (fb.plot_block_distribution(pd.DataFrame()), "nothing"),
                (fb.plot_block_means(pd.DataFrame()), "nothing"),
                (fb.plot_block_spaghetti(pd.DataFrame()), "nothing"),
                (fb.plot_response_waveforms([], "fsr1"), "no cue"),
        ):
            assert wanted in figure.axes[0].get_title()

    @needs_fixtures
    def test_his_figures_draw_from_his_data(self, bench_raw, bench_peaks):
        rep = fb.repeatability(bench_peaks)
        drift, fits, _ = fb.drift_newtons(bench_raw, "fsr1")
        figure = fb.plot_force_trends(drift, fits, "fsr1")
        # The two fitted equations are printed on the axis, as his were.
        printed = [t.get_text() for t in figure.axes[0].texts]
        assert any("0.00400" in t for t in printed)
        assert any("0.00171" in t for t in printed)
        assert fb.plot_repeatability(rep).axes[0].get_xlabel()
        waveforms = fb.response_waveforms(bench_raw, "fsr1")
        assert len(waveforms) == 5
        assert fb.plot_response_waveforms(waveforms, "fsr1").axes

    @needs_fixtures
    def test_the_block_figures_draw_from_his_trials(self):
        trials = fb.load_bench_trials(sorted(FIXTURES.glob("trials_*.csv")))
        analytic = fb.block_table(trials)
        means, _pairs, _post, _trend, _info = fb.block_model(analytic)
        assert fb.plot_block_distribution(analytic).axes
        assert fb.plot_block_means(means).axes
        assert fb.plot_block_spaghetti(analytic).axes


# ------------------------------------------------- end to end on a session

def _stream_for(folder: Path, rng: random.Random) -> int:
    """Give a keyboard session's raw.csv the 200 Hz stream the device
    would have written: each pad at its own rest level with a little
    noise, and the cued pad rising 180 counts around the moment the game
    logged the press. The engine's own event rows are kept exactly as
    written, zeros and all. Returns the cue count."""
    import csv

    from finger_rehab.data.logger import RAW_COLUMNS

    raw = pd.read_csv(folder / "raw.csv")
    events = raw["event"].fillna("").astype(str)
    stims = raw[(events == "stim") & raw["lane"].notna()].copy()
    trials = pd.read_csv(folder / "trials.csv")
    rt_of = {int(r["trial"]): float(r["time_difference_ms"])
             for _, r in trials.iterrows()
             if pd.notna(r.get("time_difference_ms"))}
    rest = [258.0, 262.0, 255.0, 290.0]
    bumps = []
    for _, stim in stims.iterrows():
        trial = fb.parse_trial(stim["detail"], 0)
        rt = rt_of.get(trial, 250.0) / 1000.0
        bumps.append((float(stim["t_perf"]) + rt - 0.03, int(stim["lane"])))
    t0 = float(stims["t_perf"].min()) - 3.0
    t1 = float(stims["t_perf"].max()) + 3.0
    kept = [dict(r) for _, r in raw[events != ""].iterrows()]
    rows = []
    t, idx = t0, 0
    while t < t1:
        values = [level + rng.gauss(0.0, 1.2) for level in rest]
        for start, lane in bumps:
            since = t - start
            if 0.0 <= since < 0.15:
                values[lane] += 180.0 * np.sin(0.5 * np.pi * since / 0.15)
            elif 0.15 <= since < 0.25:
                values[lane] += 180.0
            elif 0.25 <= since < 0.45:
                values[lane] += 180.0 * np.cos(
                    0.5 * np.pi * (since - 0.25) / 0.2)
        idx += 1
        rows.append({"iso_ts": "2026-09-01T10:00:00.000", "t_perf": t,
                     "sample_idx": idx, "hand": "right", "event": "",
                     "lane": "", "detail": "",
                     **{f"fsr{i + 1}": int(round(v))
                        for i, v in enumerate(values)},
                     **{f"fsr{i + 5}": 0 for i in range(4)}})
        t += 0.005
    for event in kept:
        idx += 1
        event["sample_idx"] = idx
        rows.append(event)
    out = pd.DataFrame(rows).sort_values("t_perf", kind="stable")
    out = out.reindex(columns=RAW_COLUMNS)
    out["lane"] = out["lane"].map(
        lambda v: "" if pd.isna(v) or v == "" else str(int(float(v))))
    out.to_csv(folder / "raw.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    return len(stims)


@pytest.fixture(scope="module")
def played_block():
    """One reaction block the real engine wrote on the keyboard source,
    given the force stream a device would have logged."""
    import pygame

    from tests.test_cohort_notebook import _engine, _play_reaction

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp) / "sessions"
        root.mkdir()
        pygame.init()
        engine = None
        try:
            engine = _engine(root)
            engine.begin_session("P77", "30", dominant_hand="right",
                                 visit="1")
            folder = _play_reaction(engine, "right", 250.0, random.Random(11),
                                    n_trials=12)
            engine.end_session()
        finally:
            if engine is not None:
                try:
                    engine._close_loggers()
                except Exception:
                    pass
            pygame.quit()
        cues = _stream_for(folder, random.Random(5))
        yield folder, cues


class TestOnASessionTheEngineWrote:
    """The module against a real block, not a frame built by hand: if
    the logger's layout changes, this fails before anyone opens the
    notebook."""

    def test_the_engine_left_a_cue_per_trial(self, played_block):
        folder, cues = played_block
        assert cues == 12
        raw = fb.load_session_raw(folder)
        assert raw is not None
        assert len(fb.sample_rows(raw)) > 1000

    def test_the_sensor_tables_come_out_of_a_real_block(self, played_block):
        folder, _ = played_block
        raw = fb.load_session_raw(folder)
        offsets = fb.resting_offsets(raw)
        report = fb.bench_report(raw, offset=offsets, rows="samples")
        assert len(report["peaks"]) == 12
        assert set(report["peaks"]["sensor"]) <= {"fsr1", "fsr2", "fsr3",
                                                  "fsr4"}
        assert (report["peaks"]["peak_counts"] > 150).all()
        assert (report["peaks"]["peak_counts"] < 200).all()
        assert (report["noise"].set_index("sensor")
                .loc[["fsr1", "fsr2", "fsr3", "fsr4"],
                     "baseline_noise_sd"] < 3.0).all()
        assert (report["snr"]["grand_snr"] > 40).all()
        assert report["saturation"] == {"over_rating": 0, "at_ceiling": 0}
        for sensor in ("fsr1", "fsr2", "fsr3", "fsr4"):
            assert abs(report["baseline_shift"][sensor]) < 5

    def test_onsets_land_before_the_logged_reaction_time(self,
                                                         played_block):
        folder, _ = played_block
        raw = fb.load_session_raw(folder)
        processed = fb.processed_peaks(raw,
                                       offset=fb.resting_offsets(raw),
                                       fs_mode="span")
        found = processed["reaction_time_ms"].dropna()
        assert len(found) >= 10
        trials = pd.read_csv(folder / "trials.csv")
        logged = pd.to_numeric(trials["time_difference_ms"],
                               errors="coerce").median()
        # Force starts moving before the key goes down, so the onset has
        # to sit earlier than the logged reaction time.
        assert found.median() < logged

    def test_one_short_block_cannot_fill_his_chunks(self, played_block):
        folder, _ = played_block
        trials = fb.session_trials_as_bench(
            pd.read_csv(folder / "trials.csv"))
        analytic = fb.block_table(trials)
        # 12 trials, no phase set, so everything lands in chunk 1 and
        # there is nothing to contrast. The section that calls this has
        # to say so rather than fit a one-block model.
        assert set(analytic["block_all"]) == {1}
        means, _pairs, _post, _trend, _info = fb.block_model(analytic)
        assert means.empty


# ---------------------------------------------- the notebook's bench chapter

NOTEBOOK = ROOT / "analysis" / "session_analysis.ipynb"


def _notebook_code() -> str:
    import json

    cells = json.loads(NOTEBOOK.read_text())["cells"]
    return "".join("".join(c["source"]) + "\n" for c in cells
                   if c["cell_type"] == "code")


class TestTheNotebookChapter:
    """The bench chapter in analysis/session_analysis.ipynb calls this
    module rather than carrying its own copy, because his CSVs only
    exist inside this repository and one copy cannot drift from another.

    These skip until the chapter is applied to the notebook. Once it is
    there, they hold the two sides together: a function renamed here
    would otherwise take the chapter down the next time someone opened
    it, weeks later.
    """

    @pytest.fixture(scope="class")
    def source(self):
        if not NOTEBOOK.exists():
            pytest.skip("no notebook on this machine")
        text = _notebook_code()
        if "sec_rayan_bench" not in text:
            pytest.skip("the bench chapter is not in the notebook yet")
        return text

    def test_the_chapter_is_wired_into_a_section(self, source):
        assert "def sec_rayan_bench" in source
        assert "rayan_bench" in source
        assert "keep(ctx, \"rayan_bench\"" in source \
            or "keep(ctx, 'rayan_bench'" in source

    def test_every_function_the_chapter_calls_still_exists(self, source):
        called = set(re.findall(r"fbench\.([A-Za-z_][A-Za-z0-9_]*)", source))
        assert called, "the chapter no longer calls the module"
        missing = sorted(name for name in called if not hasattr(fb, name))
        assert not missing, (
            f"the notebook's bench chapter calls {missing}, which "
            f"force_bench.py no longer defines")
