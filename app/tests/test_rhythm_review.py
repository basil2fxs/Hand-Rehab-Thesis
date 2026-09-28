"""Rhythm faults from the 27 September 2026 code review, each
reproduced before it was fixed.

Game side: the cue tone was played at the scored zero and so heard
its own output delay (77 ms) after the beat; notes missed while the
board was away counted as the participant's misses; the song's play
call landed up to a frame after the lead the beats assume; a note
closed on the raw clock, 87 ms into its own Late tier; a press on the
first note before the song started was scored against a zero placed
without the offset; the block never recorded the audio it ran with;
the outcome flash was stamped with song time and never drawn; and the
lag-1 of the asynchronies was read with the wrong sign.

Notebook side: tap_series put the offset in twice; the cohort
interval CV measured the chart's spacing; the Rh1 note named the
configured offset rather than the applied one; the EEG audit counted a
wrong-finger byte as a note response; the within-block windows moved
with every miss; and Rh-wk expected a negative asynchrony lag-1.
"""
from __future__ import annotations

import contextlib
import io
import json
import math
import os
import random
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

from tests.test_rhythm_tactile import (FRAME_S, _beatmap, _fake_clock,  # noqa: E402
                                       _make_engine, _make_mode, _press,
                                       _pump)


def _engine(td, rhythm_cfg, tone_ms=77.0):
    eng, board = _make_engine(td, rhythm_cfg)
    eng.cfg.data.setdefault("latency", {})["tone_ms"] = tone_ms
    return eng, board


def _zero(mode, note, offset_s):
    return mode._t_start + mode._countdown_s + note.t + offset_s


class ToneOnTheBeatTests(unittest.TestCase):

    def test_the_tone_is_heard_on_the_scored_zero(self):
        with tempfile.TemporaryDirectory() as td:
            eng, _board = _engine(td, {"tactile_mode": "on_beat",
                                       "metronome_offset_ms": 87})
            bm = _beatmap(4)
            eng.begin_rhythm_block(bm)
            mode = eng.mode
            _pump(eng, 2.6)
            tones = [t for t, _lane in eng.audio.tones]
            self.assertEqual(len(tones), 4)
            for t, n in zip(tones, bm.notes):
                heard = t + 0.077
                err_ms = (heard - _zero(mode, n, 0.087)) * 1000.0
                self.assertLessEqual(abs(err_ms), FRAME_S * 1000.0 + 2.0,
                                     err_ms)
            self.assertEqual(mode.audio_summary()["tone_lead_ms"], 77.0)


class DeviceDropTests(unittest.TestCase):

    def test_notes_lost_to_a_board_drop_are_not_misses(self):
        with tempfile.TemporaryDirectory() as td:
            eng, _board = _engine(td, {"tactile_mode": "on_beat"})
            bm = _beatmap(4)
            eng.begin_rhythm_block(bm)
            mode = eng.mode
            t0 = mode._t_start
            # Notes at 0.6, 1.1, 1.6 and 2.1 s, each closing 312 ms
            # after its beat. The board is away from 1.5 to 2.4 s, so
            # the last two notes close inside the drop; the first two
            # closed before it and stay misses.
            eng._block_drops = [{"hand": "right",
                                 "t_down": t0 + 1.5, "t_up": t0 + 2.4}]
            _pump(eng, 3.2)
            self.assertEqual(eng.hits, 0)
            self.assertEqual(eng.misses, 2)
            self.assertEqual(getattr(eng, "_block_drop_voided", 0), 2)
            self.assertEqual(sum(eng._per_lane_misses.values()), 2)


class LateWindowTests(unittest.TestCase):

    def test_a_late_press_inside_the_window_still_scores(self):
        with tempfile.TemporaryDirectory() as td:
            eng, _board = _engine(td, {"tactile_mode": "on_beat",
                                       "metronome_offset_ms": 87})
            bm = _beatmap(3)
            eng.begin_rhythm_block(bm)
            mode = eng.mode
            pressed = set()

            def responder(now):
                for i, n in enumerate(bm.notes):
                    if i in pressed:
                        continue
                    if now >= _zero(mode, n, 0.087) + 0.250:
                        pressed.add(i)
                        mode.queue_press(_press(n.lane, now))

            _pump(eng, 2.6, on_frame=responder)
            self.assertEqual(eng.misses, 0)
            self.assertEqual(eng._block_rhythm_spurious_presses, 0)
            self.assertEqual(eng.hits, 3)


class SongStartTests(unittest.TestCase):

    def test_the_clock_meets_the_play_call(self):
        with tempfile.TemporaryDirectory() as td:
            eng, _board = _engine(td, {"tactile_mode": "on_beat",
                                       "pre_song_lead_s": 0.5})
            called = []
            real = eng.audio.start_metronome.side_effect
            eng.audio.start_metronome = MagicMock(
                side_effect=lambda bpm: (called.append(time.perf_counter()),
                                         real(bpm)))
            eng.begin_rhythm_block(_beatmap(2))
            mode = eng.mode
            frames: list[float] = []
            _pump(eng, 1.0, on_frame=frames.append)
            self.assertEqual(len(called), 1)
            self.assertAlmostEqual(
                called[0], mode._t_start + mode._countdown_s + 0.5,
                delta=2e-3)
            summary = mode.audio_summary()
            self.assertEqual(summary["audio_source"], "metronome")
            self.assertEqual(summary["audio_offset_applied_ms"], 12.0)
            self.assertGreaterEqual(summary["song_start_lag_ms"], 0.0)
            # The play call lands on the first frame at or after the
            # lead, so the lag is at most one frame gap. The bound is
            # this run's longest gap, not FRAME_S: a real sleep
            # overshoots by a millisecond or two on a busy machine,
            # which failed the FRAME_S bound in 3 of 48 runs (18.0 ms
            # against 17.7).
            longest = max(b - a for a, b in zip(frames, frames[1:]))
            self.assertLess(summary["song_start_lag_ms"],
                            longest * 1000.0 + 1.0)

    def test_no_audio_records_none_and_zero(self):
        with tempfile.TemporaryDirectory() as td:
            eng, _board = _engine(td, {"tactile_mode": "on_beat"})
            eng.audio = None
            eng.begin_rhythm_block(_beatmap(2))
            _pump(eng, 0.5)
            summary = eng.mode.audio_summary()
            self.assertEqual(summary["audio_source"], "none")
            self.assertEqual(summary["audio_offset_applied_ms"], 0.0)


class FirstNoteTests(unittest.TestCase):

    def test_a_press_before_the_song_starts_uses_the_cued_zero(self):
        from finger_rehab.audio.beatmap import Note

        def go(clock):
            mode, engine, bm = _make_mode(
                cfg_extra={"rhythm.pre_song_lead_s": 1.0,
                           "rhythm.audio_offset_ms": 87,
                           "rhythm.tactile_mode": "on_beat"},
                notes=[Note(t=0.07, lane=1), Note(t=0.9, lane=2)])
            # The song is not playing until play_song is called.
            engine.audio._song_path = None
            engine.audio.play_song = MagicMock(
                side_effect=lambda p: setattr(engine.audio, "_song_path",
                                              p) or True)
            mode._countdown_done = True
            mode._countdown_s = 0.0
            # The first note's zero is 1.07 + 0.087 = 1.157 in song
            # time; press 167 ms before it, before the song starts.
            press_song_t = 1.157 - 0.167
            pressed = []
            while mode.song_time < 2.0:
                clock.t += FRAME_S
                if not pressed and mode.song_time >= press_song_t:
                    t_press = mode._t_start + press_song_t
                    mode.queue_press(_press(1, t_press))
                    pressed.append(t_press)
                mode.update(FRAME_S)
            self.assertTrue(pressed)
            hits = engine.log_rhythm_hit.call_args_list
            self.assertGreaterEqual(len(hits), 1)
            _sched, offset_ms = hits[0][0][0], hits[0][0][1]
            self.assertAlmostEqual(offset_ms, -167.0, delta=1.0)

        _fake_clock(go)


class FlashClockTests(unittest.TestCase):

    def test_the_outcome_flash_is_on_the_screen_clock(self):
        with tempfile.TemporaryDirectory() as td:
            eng, _board = _engine(td, {"tactile_mode": "on_beat"})
            bm = _beatmap(1)
            eng.begin_rhythm_block(bm)
            mode = eng.mode
            done = []

            def responder(now):
                if not done and now >= _zero(mode, bm.notes[0], 0.012):
                    done.append(now)
                    mode.queue_press(_press(bm.notes[0].lane, now))

            _pump(eng, 1.2, on_frame=responder)
            rs = eng._screens["rhythm"]
            self.assertTrue(rs.flash_lane.called)
            stamp = rs.flash_lane.call_args[0][3]
            self.assertLess(abs(stamp - time.perf_counter()), 2.0)


class ResidualLagTests(unittest.TestCase):

    @staticmethod
    def _series(alpha, n=400, seed=3):
        """Asynchronies under the linear phase-correction model with
        correction strength alpha, and the press and note times they
        come from."""
        rng = random.Random(seed)
        a, asyn, notes, press = 0.0, [], [], []
        for i in range(n):
            a = (1.0 - alpha) * a + rng.gauss(0.0, 0.02)
            asyn.append(a)
            notes.append(0.5 * i)
            press.append(0.5 * i + a)
        return asyn, press, notes

    def test_partial_correction_signs(self):
        from finger_rehab.analytics import metrics
        for alpha in (0.25, 0.5, 0.75):
            asyn, press, notes = self._series(alpha)
            r_asyn = metrics.tempo_entrainment_index(asyn[1:], asyn[:-1])
            r_resid = metrics.interval_residual_lag1(press, notes)
            self.assertGreater(r_asyn, 0.0, alpha)
            self.assertLess(r_resid, 0.0, alpha)
            self.assertGreaterEqual(r_resid, -0.6, alpha)

    def test_the_block_summary_carries_the_residual(self):
        with tempfile.TemporaryDirectory() as td:
            eng, _board = _engine(td, {"tactile_mode": "on_beat"})
            bm = _beatmap(8, spacing_s=0.4)
            eng.begin_rhythm_block(bm)
            mode = eng.mode
            pressed = set()
            rng = random.Random(1)

            def responder(now):
                for i, n in enumerate(bm.notes):
                    if i in pressed:
                        continue
                    if now >= _zero(mode, n, 0.012) + rng.uniform(-0.03, 0.03):
                        pressed.add(i)
                        mode.queue_press(_press(n.lane, now))

            _pump(eng, 4.0, on_frame=responder)
            summary = eng._build_block_summary("completed")
            bo = summary["beat_offset_stats"]
            self.assertIn("interval_resid_lag1_r", bo)
            self.assertIn("audio_offset_applied_ms", summary["song"])


# ---- notebook ------------------------------------------------------------


class NotebookTests(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from tests.test_force_pilot_notebook_levels import _load_ra
        cls.ra = _load_ra()

    def _rows(self, n=12, with_drop=False):
        import pandas as pd
        rows = []
        for i in range(n):
            song_t = 2.07 + 0.8 * i
            off = -20.0 + 6.0 * (i % 3)
            rows.append(dict(mode="rhythm", game="g1", session="s1",
                             side="right", trial=i + 1,
                             song_time_s=song_t + off / 1000.0,
                             time_difference_ms=off, early_late="Good",
                             error_type=""))
        if with_drop:
            for i in range(2):
                rows.append(dict(mode="rhythm", game="g1", session="s1",
                                 side="right", trial=n + i + 1,
                                 song_time_s=2.07 + 0.8 * (n + i) + 0.3,
                                 time_difference_ms=0.0, early_late="Miss",
                                 error_type="device_drop"))
        return pd.DataFrame(rows)

    def test_tap_series_reads_the_press_from_song_time(self):
        ra = self.ra
        rows = self._rows()
        press, note = ra.tap_series(ra.rhythm_rows(rows))
        self.assertAlmostEqual(press[0], rows.iloc[0]["song_time_s"])
        self.assertAlmostEqual(note[0], 2.07, places=6)
        self.assertAlmostEqual(note[1] - note[0], 0.8, places=6)

    def test_cohort_rows_use_the_person_only_cv_and_skip_drops(self):
        ra = self.ra
        rows = self._rows(with_drop=True)
        block = {"game": "g1", "folder": Path("."), "meta": {},
                 "bs": {"tap_variability_rel_cv": 0.031},
                 "rows": rows, "hand": "right", "calset": None,
                 "extra": {}}
        emitted = {m: (v, n) for _h, m, v, n in ra._cohort_rhythm(block)}
        self.assertAlmostEqual(emitted["interval_cv"][0], 0.031)
        self.assertAlmostEqual(emitted["hit_rate"][0], 1.0)
        self.assertEqual(emitted["hit_rate"][1], 12)

    def test_the_rh1_note_reads_the_applied_offset(self):
        ra = self.ra
        metas = [{"block_summary": {"block": "rhythm",
                                    "song": {"audio_source": "none",
                                             "audio_offset_applied_ms": 0.0}},
                  "config_snapshot": {"rhythm": {"audio_offset_ms": 87},
                                      "latency": {"measured": True},
                                      "audio": {"enabled": False}}}]
        note = ra.rhythm_offset_note(metas)
        self.assertIn("applied audio offset of 0 ms", note)
        self.assertIn("none", note)
        older = [{"block_summary": {"block": "rhythm"},
                  "config_snapshot": {"rhythm": {"audio_offset_ms": 87},
                                      "latency": {"measured": True},
                                      "audio": {"enabled": False}}}]
        self.assertIn("0 ms from the config snapshot",
                      ra.rhythm_offset_note(older))

    def test_the_fine_series_windows_are_cut_by_note_time(self):
        ra = self.ra
        rows = self._rows(n=80)          # notes 2.07 s to 65.3 s
        series, _better = ra.fine_series("rhythm", rows)
        self.assertEqual(len(series), 3)
        # Dropping ten early notes moves no window boundary: the
        # third window still holds the same notes.
        fewer = rows.iloc[10:]
        series2, _b = ra.fine_series("rhythm", fewer)
        self.assertEqual(len(series2), 3)
        self.assertAlmostEqual(series[2], series2[2], places=9)

    def test_rh_wk_reads_the_interval_residual(self):
        ra = self.ra
        rng = random.Random(5)
        a, rows = 0.0, []
        for i in range(60):
            a = 0.5 * a + rng.gauss(0.0, 0.025)
            rows.append(dict(mode="rhythm", game="g1", session="s1",
                             side="right", trial=i + 1,
                             song_time_s=2.0 + 0.5 * i + a,
                             time_difference_ms=a * 1000.0,
                             early_late="Good", error_type=""))
        import pandas as pd
        rhy = pd.DataFrame(rows)
        press, note = ra.tap_series(rhy)
        self.assertLess(ra.interval_residual_lag1(press, note), 0.0)
        self.assertGreater(ra._lag1(rhy["time_difference_ms"].tolist()),
                           0.0)
        self.assertLess(ra._blockwise_resid_lag1(rhy), 0.0)

    def test_the_eeg_audit_counts_a_wrong_finger_apart(self):
        import pandas as pd
        from finger_rehab.hardware import eeg_trigger
        from tests.test_force_pilot_notebook_levels import _RealRawLogger
        ra = self.ra
        with tempfile.TemporaryDirectory() as td:
            folder = Path(td) / "2026-08-10" / "Pat_100000_rhythm"
            folder.mkdir(parents=True)
            raw = _RealRawLogger(folder / "raw.csv")
            t = 1000.0
            for i in range(200):
                raw.queue_sample(t + i * 0.005, [265] * 4)
            raw.queue_event("block_start", t_perf=t + 1.0, detail="rhythm")

            def send(code, lane, at):
                rec = eeg_trigger.MarkerEmission(code=code, lane=lane,
                                                 t_event=at, t_wire=at,
                                                 delayed=False, failed=False)
                raw.queue_event("eeg", lane=lane, t_perf=at,
                                detail=eeg_trigger.format_detail(rec))

            # Two notes: a correct press on each, and one wrong finger
            # on the beat of the first.
            send(31, 0, t + 2.0)
            send(110 + 2, 2, t + 2.05)
            send(100 + 0, 0, t + 2.10)
            send(31, 1, t + 3.0)
            send(100 + 1, 1, t + 3.08)
            raw.close()
            rows = pd.DataFrame([
                dict(mode="rhythm", game=ra.game_key(folder), trial=1,
                     early_late="Good", time_difference_ms=100.0,
                     stimulus="", error_type=""),
                dict(mode="rhythm", game=ra.game_key(folder), trial=2,
                     early_late="Good", time_difference_ms=80.0,
                     stimulus="", error_type="")])
            meta = {"block_summary": {"block": "rhythm"},
                    "eeg": {"enabled": True, "pulse_ms": 2, "gap_ms": 2}}
            (folder / "metadata.json").write_text(json.dumps(meta))
            with contextlib.redirect_stdout(io.StringIO()):
                a = ra.eeg_audit_block(folder, meta, rows)
            self.assertTrue(a["ok"], a["problems"])


if __name__ == "__main__":
    unittest.main()
