"""Where rhythm's buzz sits relative to the beat (rhythm.tactile_mode).

Basil's report: the buzzer "goes off noticeably late and only buzzes
exactly when the press should have happened". A STIM command on the
beat is felt about 45 ms after it (serial path plus ERM lag), and a
player who reacts to the buzz then presses a reaction time after
that. The fix is a buzz that LEADS the beat by a reaction allowance
plus the motor's rise, adapted to the player, with a feedback-only
buzz as the fallback Basil named. Only the buzz moves: the tone, the
falling note, the scoring zero and the beat's EEG marker stay put.

Three layers here:
  - the mode on a fake clock, for the dispatch arithmetic and the
    adaptation rule (same harness as test_rhythm's CueOnTheBeatTests);
  - the real GameEngine on a fake sensor board that timestamps every
    command, pumped at 60 Hz on the real clock, for the numbers a wire
    would see in each mode;
  - the trial rows, block summary and metadata a block leaves behind.
"""
from __future__ import annotations

import csv
import json
import os
import statistics
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


FRAME_S = 1.0 / 60.0


# ---- layer 1: the mode on a fake clock --------------------------------------

class _Clock:
    def __init__(self, t0: float) -> None:
        self.t = t0

    def perf_counter(self) -> float:
        return self.t


def _fake_clock(fn):
    import finger_rehab.game.modes.rhythm as rhythm_mod
    real_time = rhythm_mod.time
    clock = _Clock(1000.0)
    rhythm_mod.time = clock
    try:
        return fn(clock)
    finally:
        rhythm_mod.time = real_time


def _make_mode(cfg_extra: dict | None = None, notes=None, song=True,
               engine=None):
    from finger_rehab.audio.beatmap import Beatmap, Note
    from finger_rehab.game.modes.rhythm import RhythmMode
    from finger_rehab.game.scoring import RhythmWindows, ScoreConfig
    if notes is None:
        notes = [Note(t=1.0 + 0.5 * i, lane=i % 4) for i in range(40)]
    bm = Beatmap(notes=notes, song=("song.mp3" if song else None))
    if engine is None:
        engine = MagicMock()
        engine._rhythm_buzz_lead_ms = None
    cfg = {
        "rhythm.pre_song_lead_s": 0,
        "game.start_countdown_s": 0,
        "rhythm.audio_offset_ms": 40,
        "rhythm.metronome_offset_ms": 12,
        "rhythm.buzz_rise_comp_ms": 0,
        "rhythm.tactile_mode": "lead",
        "rhythm.buzz_lead_ms": 150,
        "rhythm.buzz_lead_adapt": True,
        "rhythm.buzz_lead_window": 8,
        "rhythm.buzz_lead_every": 4,
        "rhythm.buzz_lead_gain": 0.5,
        "rhythm.buzz_lead_max_ms": 400,
        "rhythm.buzz_lead_step_ms": 25,
        "latency.buzzer_ms": 45,
        "latency.visual_ms": 20,
    }
    cfg.update(cfg_extra or {})
    engine.cfg.get = MagicMock(side_effect=lambda k, d=None: cfg.get(k, d))
    if song:
        engine.audio._song_path = "song.mp3"
        engine.audio._metronome_period = None
    else:
        engine.audio._song_path = None
        engine.audio._metronome_period = 0.5
    engine.audio.play_song = MagicMock(return_value=True)
    mode = RhythmMode(engine, bm, RhythmWindows(), ScoreConfig())
    return mode, engine, bm


def _drive(mode, clock, until_song_t: float) -> None:
    end = mode._t_start + until_song_t
    while clock.t < end:
        clock.t += FRAME_S
        mode.update(FRAME_S)


def _press(lane: int, t_perf: float):
    from finger_rehab.hardware.fsr_detector import PressEvent
    return PressEvent(lane=lane, t_perf=t_perf, value=0, baseline=0.0,
                      hand="right")


class LeadDispatchTests(unittest.TestCase):
    """Lead mode splits every note into a buzz ahead of the beat and a
    beat dispatch without the buzz."""

    def test_buzz_leads_the_scored_zero_by_lead_plus_rise(self) -> None:
        def go(clock):
            mode, engine, bm = _make_mode()
            buzz_at, beat_at = [], []
            engine.on_tactile_lead.side_effect = (
                lambda lane, idx, t: buzz_at.append((idx, t, clock.t)))
            engine.on_stim.side_effect = (
                lambda lane, idx, t, buzz=True: beat_at.append(
                    (idx, t, clock.t, buzz)))
            _drive(mode, clock, 2.3)
            self.assertEqual([b[0] for b in buzz_at], [0, 1, 2])
            self.assertEqual([b[0] for b in beat_at], [0, 1, 2])
            for (bi, t_buzz, at_buzz), (si, t_beat, at_beat, buzz) in zip(
                    buzz_at, beat_at):
                note = bm.notes[bi]
                zero = mode._t_start + note.t + 0.040
                # Scheduled moments: the beat on the scored zero, the
                # buzz 150 + 45 ms ahead of it.
                self.assertAlmostEqual(t_beat, zero, places=9)
                self.assertAlmostEqual(t_buzz, zero - 0.195, places=9)
                self.assertFalse(buzz, "beat dispatch must not buzz")
                # Dispatch frames centred on the targets.
                half = FRAME_S * 1000.0 / 2 + 0.5
                self.assertLessEqual(abs((at_beat - zero) * 1000.0), half)
                self.assertLessEqual(
                    abs((at_buzz - (zero - 0.195)) * 1000.0), half)

        _fake_clock(go)

    def test_press_on_the_beat_still_scores_zero(self) -> None:
        # The scoring zero does not move with the buzz.
        def go(clock):
            mode, engine, bm = _make_mode()
            _drive(mode, clock, 1.1)
            zero = mode._t_start + bm.notes[0].t + 0.040
            mode.queue_press(_press(0, zero))
            clock.t += FRAME_S
            mode.update(FRAME_S)
            engine.log_rhythm_hit.assert_called_once()
            self.assertLess(abs(engine.log_rhythm_hit.call_args[0][1]),
                            1.0)

        _fake_clock(go)

    def test_lead_cursor_runs_ahead_on_a_fast_chart(self) -> None:
        # Notes 100 ms apart with a 195 ms lead: the buzz for note N+1
        # is due before the beat of note N. A single cursor would fire
        # it late; the lead cursor fires every buzz on time.
        from finger_rehab.audio.beatmap import Note
        notes = [Note(t=1.0 + 0.1 * i, lane=i % 4) for i in range(6)]

        def go(clock):
            mode, engine, bm = _make_mode(notes=notes)
            order = []
            engine.on_tactile_lead.side_effect = (
                lambda lane, idx, t: order.append(("buzz", idx, t)))
            engine.on_stim.side_effect = (
                lambda lane, idx, t, buzz=True: order.append(
                    ("beat", idx, t)))
            _drive(mode, clock, 1.9)
            buzzes = [o for o in order if o[0] == "buzz"]
            beats = [o for o in order if o[0] == "beat"]
            self.assertEqual([b[1] for b in buzzes], list(range(6)))
            self.assertEqual([b[1] for b in beats], list(range(6)))
            for b in buzzes:
                self.assertAlmostEqual(
                    b[2], mode._t_start + notes[b[1]].t + 0.040 - 0.195,
                    places=9)
            # The buzz for note 1 (due 95 ms before the beat of note
            # 0) went out first.
            self.assertLess(order.index(("buzz", 1, buzzes[1][2])),
                            order.index(("beat", 0, beats[0][2])))

        _fake_clock(go)

    def test_feedback_mode_never_buzzes_before_the_beat(self) -> None:
        def go(clock):
            mode, engine, bm = _make_mode(
                {"rhythm.tactile_mode": "feedback"})
            _drive(mode, clock, 2.3)
            engine.on_tactile_lead.assert_not_called()
            self.assertEqual(engine.on_stim.call_count, 3)
            for call in engine.on_stim.call_args_list:
                self.assertFalse(call[1]["buzz"])
            self.assertEqual(mode.lead_total_s(), 0.0)

        _fake_clock(go)

    def test_on_beat_mode_uses_the_rise_only(self) -> None:
        def go(clock):
            mode, engine, bm = _make_mode(
                {"rhythm.tactile_mode": "on_beat"})
            self.assertEqual(mode.buzz_lead_ms, 0.0)
            self.assertAlmostEqual(mode.lead_total_s(), 0.045)
            _drive(mode, clock, 1.1)
            _lane, _idx, t_buzz = engine.on_tactile_lead.call_args[0]
            self.assertAlmostEqual(
                t_buzz, mode._t_start + bm.notes[0].t + 0.040 - 0.045,
                places=9)
            self.assertFalse(mode._lead_adapt)

        _fake_clock(go)

    def test_bench_rise_comp_beats_the_datasheet_latency(self) -> None:
        mode, _engine, _bm = _make_mode({"rhythm.buzz_rise_comp_ms": 30})
        self.assertAlmostEqual(mode.lead_total_s(), 0.180)

    def test_unknown_mode_falls_back_to_lead(self) -> None:
        mode, _engine, _bm = _make_mode({"rhythm.tactile_mode": "sideways"})
        self.assertEqual(mode.tactile_mode, "lead")

    def test_display_clock_leads_by_panel_lag_minus_audio_offset(self):
        # The note must reach the strike line on the retina on the
        # audible beat: drawn 20 ms early for the panel, 40 ms late
        # for the song's audio path, net 20 ms behind song_time.
        def go(clock):
            mode, _engine, _bm = _make_mode()
            _drive(mode, clock, 0.5)
            self.assertAlmostEqual(
                mode.display_song_time, mode.song_time - 0.040 + 0.020,
                places=9)

        _fake_clock(go)


class LeadAdaptationTests(unittest.TestCase):
    """The lead walks toward the player's own asynchrony."""

    def _play(self, mode, clock, offsets_fn, n_notes: int) -> list[float]:
        """Score n_notes presses; offsets_fn(lead_ms) gives the press
        offset from the beat for a note cued under that lead. Returns
        the lead in force after each note."""
        leads = []
        for i in range(n_notes):
            note = mode.beatmap.notes[i]
            zero = mode._t_start + note.t + 0.040
            _drive(mode, clock, note.t + 0.041)
            offset_ms = offsets_fn(mode.buzz_lead_ms)
            mode.queue_press(_press(note.lane, zero + offset_ms / 1000.0))
            clock.t += FRAME_S
            mode.update(FRAME_S)
            leads.append(mode.buzz_lead_ms)
        return leads

    def test_no_update_before_the_first_four_hits(self) -> None:
        def go(clock):
            mode, engine, _bm = _make_mode()
            leads = self._play(mode, clock, lambda lead: 120.0, 3)
            self.assertEqual(leads, [150.0, 150.0, 150.0])

        _fake_clock(go)

    def test_reactor_converges_on_their_reaction_time(self) -> None:
        # A reactor presses 270 ms after the buzz command whatever
        # the lead: offset = 270 - lead, so +120 at the shipped 150.
        # The lead rises in 25 ms steps and settles within a step of
        # 270, never past the maximum.
        def go(clock):
            mode, engine, _bm = _make_mode()
            leads = self._play(mode, clock, lambda lead: 270.0 - lead, 40)
            self.assertEqual(leads[3], 175.0)
            self.assertEqual(leads[7], 200.0)
            steps = [b - a for a, b in zip(leads, leads[1:]) if b != a]
            self.assertTrue(all(0 < s <= 25.0 for s in steps), steps)
            self.assertLessEqual(abs(leads[-1] - 270.0), 25.0, leads[-1])
            self.assertLessEqual(max(leads), 400.0)
            self.assertEqual(engine._rhythm_buzz_lead_ms, leads[-1])

        _fake_clock(go)

    def test_predictor_walks_the_lead_to_zero_and_stays(self) -> None:
        def go(clock):
            mode, engine, _bm = _make_mode()
            leads = self._play(mode, clock, lambda lead: -40.0, 40)
            # -40 median times gain 0.5 is -20 per update, under the
            # step, so 150, 130, 110 ... 10, 0 and then 0 for good.
            self.assertEqual(leads[3], 130.0)
            self.assertEqual(leads[7], 110.0)
            self.assertEqual(leads[-1], 0.0)
            zero_from = leads.index(0.0)
            self.assertTrue(all(v == 0.0 for v in leads[zero_from:]))

        _fake_clock(go)

    def test_late_early_and_miss_do_not_move_the_lead(self) -> None:
        def go(clock):
            mode, engine, _bm = _make_mode()
            # +200 is Late (past good_ms 175, inside miss_ms 300),
            # -250 is Early, +400 is a Miss: none count as hits.
            for offset in (200.0, -250.0, 400.0, 200.0):
                leads = self._play(mode, clock, lambda lead, o=offset: o, 1)
            self.assertEqual(mode.buzz_lead_ms, 150.0)
            self.assertEqual(len(mode._lead_offsets), 0)

        _fake_clock(go)

    def test_median_not_mean_ignores_one_wild_press(self) -> None:
        def go(clock):
            mode, engine, _bm = _make_mode()
            # Three presses dead on the beat and one +170 (Good, so it
            # counts): the mean would move the lead, the median stays 0.
            seq = iter([0.0, 0.0, 170.0, 0.0])
            leads = self._play(mode, clock, lambda lead: next(seq), 4)
            self.assertEqual(leads[-1], 150.0)

        _fake_clock(go)

    def test_adapt_off_holds_the_configured_lead(self) -> None:
        def go(clock):
            mode, engine, _bm = _make_mode({"rhythm.buzz_lead_adapt": False})
            leads = self._play(mode, clock, lambda lead: 120.0, 12)
            self.assertTrue(all(v == 150.0 for v in leads))

        _fake_clock(go)

    def test_lead_carries_into_the_next_block_of_the_session(self) -> None:
        def go(clock):
            engine = MagicMock()
            engine._rhythm_buzz_lead_ms = None
            mode, engine, _bm = _make_mode(engine=engine)
            self._play(mode, clock, lambda lead: 270.0 - lead, 8)
            self.assertEqual(engine._rhythm_buzz_lead_ms, 200.0)
            mode2, _e, _b = _make_mode(engine=engine)
            self.assertEqual(mode2.buzz_lead_ms, 200.0)
            self.assertEqual(mode2.tactile_summary()["buzz_lead_start_ms"],
                             200.0)

        _fake_clock(go)

    def test_per_note_params_record_the_lead_in_force(self) -> None:
        def go(clock):
            mode, engine, _bm = _make_mode()
            self._play(mode, clock, lambda lead: 270.0 - lead, 5)
            # Note 0 was cued at 150; note 4 was cued after the first
            # update took the lead to 175.
            self.assertEqual(mode.tactile_params(0)["buzz_lead_ms"], 150.0)
            self.assertEqual(mode.tactile_params(4)["buzz_lead_ms"], 175.0)
            self.assertEqual(mode.tactile_params(0)["tactile_mode"], "lead")
            self.assertEqual(mode.tactile_params(0)["buzz_rise_comp_ms"],
                             45.0)

        _fake_clock(go)


# ---- layer 2: the real engine on a fake wire ---------------------------------

class _StubBoard:
    """One Arduino's serial handle, timestamping every command."""

    is_connected = True

    def __init__(self) -> None:
        self.commands: list[tuple[float, str]] = []

    def send_command(self, cmd: str) -> bool:
        self.commands.append((time.perf_counter(), cmd))
        return True

    def get_sample(self, timeout: float = 0.0):
        return None

    def start(self) -> None:
        pass

    def stop(self) -> None:
        pass


def _fake_source():
    from finger_rehab.hardware.multi_serial import MultiSerialSource
    board = _StubBoard()
    src = MultiSerialSource(ports=["fake"], hand_assignment=["right"])
    src.hands[0].source = board
    return src, board


def _fake_audio():
    """Enough of the AudioEngine for rhythm: the metronome starts
    (so the click-track offset applies), and every stim tone is
    timestamped."""
    audio = MagicMock()
    audio._song_path = None
    audio._metronome_period = None
    audio.play_song = MagicMock(return_value=False)
    audio.tones: list[tuple[float, int]] = []

    def start_metronome(bpm):
        audio._metronome_period = 60.0 / float(bpm)

    audio.start_metronome = MagicMock(side_effect=start_metronome)
    audio.play_stim = MagicMock(
        side_effect=lambda lane: audio.tones.append(
            (time.perf_counter(), lane)))
    return audio


def _make_engine(td: str, rhythm_cfg: dict, eeg: dict | None = None,
                 cue_ms: int = 150, buzz_before: bool = True):
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [640, 480]
    cfg.data["audio"]["enabled"] = False
    cfg.data["session"]["data_dir"] = td
    cfg.data["report"] = {"enabled": False}
    cfg.data["cue"] = {"buzz_before": buzz_before, "sound_before": True,
                       "sound_after": False, "buzz_after": False,
                       "show_target": True}
    cfg.data["motor"]["cue_ms"] = cue_ms
    cfg.data["game"]["start_countdown_s"] = 0
    cfg.data["rhythm"].update({"pre_song_lead_s": 0,
                               "audio_offset_ms": 40,
                               "metronome_offset_ms": 12})
    cfg.data["rhythm"].update(rhythm_cfg)
    cfg.data["eeg"] = eeg or {"enabled": False}
    source, board = _fake_source()
    eng = GameEngine(cfg, source)
    eng.audio = _fake_audio()
    rs = MagicMock()
    rs.lanes = []
    eng._screens = {"gameplay": MagicMock(lanes=[]), "rhythm": rs,
                    "results": MagicMock()}
    return eng, board


def _beatmap(n: int, spacing_s: float = 0.5, first_s: float = 0.6):
    from finger_rehab.audio.beatmap import Beatmap, Note
    return Beatmap(notes=[Note(t=first_s + spacing_s * i, lane=i % 4)
                          for i in range(n)], bpm=120.0)


def _pump(eng, seconds: float, on_frame=None) -> None:
    """A 60 Hz frame loop without the drawing: the mode update, the
    motor queue drain and the marker plumbing, in run()'s order."""
    end = time.perf_counter() + seconds
    last = time.perf_counter()
    while time.perf_counter() < end:
        now = time.perf_counter()
        dt = now - last
        last = now
        if on_frame is not None:
            on_frame(now)
        if eng.mode is not None:
            eng.mode.update(dt)
        eng._drain_motor_queue()
        eng._flush_eeg_stim()
        eng.markers.tick()
        time.sleep(max(0.0, FRAME_S - (time.perf_counter() - now)))


def _stims(board) -> list[float]:
    return [t for t, c in board.commands if c.startswith("STIM:")]


class FakeWireTests(unittest.TestCase):
    """What a wire sees in each tactile mode, through the real engine."""

    def setUp(self) -> None:
        import pygame
        pygame.init()

    def tearDown(self) -> None:
        import pygame
        pygame.quit()

    def test_lead_mode_stim_precedes_the_beat_by_the_lead_total(self):
        with tempfile.TemporaryDirectory() as td:
            eng, board = _make_engine(td, {"tactile_mode": "lead",
                                           "buzz_lead_ms": 150,
                                           "buzz_lead_adapt": False})
            bm = _beatmap(4)
            eng.begin_rhythm_block(bm)
            mode = eng.mode
            board.commands.clear()
            _pump(eng, 2.6)
            stims = _stims(board)
            self.assertEqual(len(stims), 4, board.commands)
            # The scored zero on the perf clock: note time plus the
            # click-track offset (the fake audio runs the metronome).
            zeros = [mode._t_start + n.t + 0.012 for n in bm.notes]
            errs = [(s - (z - 0.195)) * 1000.0 for s, z in zip(stims, zeros)]
            for e in errs:
                self.assertLessEqual(abs(e), FRAME_S * 1000.0 + 2.0, errs)
            # The tone stays on the beat.
            tones = [t for t, _lane in eng.audio.tones]
            self.assertEqual(len(tones), 4)
            for t, z in zip(tones, zeros):
                self.assertLessEqual(abs((t - z) * 1000.0),
                                     FRAME_S * 1000.0 + 2.0)
            # And the buzz really did go out about 195 ms before it.
            gaps = [(t - s) * 1000.0 for s, t in zip(stims, tones)]
            self.assertGreater(min(gaps), 195.0 - FRAME_S * 1000.0 * 2)
            self.assertLess(max(gaps), 195.0 + FRAME_S * 1000.0 * 2)

    def test_feedback_mode_buzzes_only_after_a_scored_hit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            eng, board = _make_engine(td, {"tactile_mode": "feedback"})
            bm = _beatmap(4)
            eng.begin_rhythm_block(bm)
            mode = eng.mode
            board.commands.clear()
            zeros = [mode._t_start + n.t + 0.012 for n in bm.notes]
            # Note 0: press on the beat (hit). Note 1: no press (miss).
            # Note 2: press 200 ms late (Late, not a hit). Note 3: hit.
            plan = {0: 0.0, 2: 0.200, 3: 0.0}
            pressed = set()
            press_at = {}

            def responder(now):
                for i, off in plan.items():
                    if i in pressed:
                        continue
                    if now >= zeros[i] + off:
                        pressed.add(i)
                        press_at[i] = now
                        mode.queue_press(_press(bm.notes[i].lane, now))

            _pump(eng, 2.8, on_frame=responder)
            stims = _stims(board)
            self.assertEqual(len(stims), 2, board.commands)
            # Nothing before the first beat, and each buzz lands
            # within a frame after its press.
            self.assertGreater(stims[0], zeros[0] - 0.001)
            for s, i in zip(stims, (0, 3)):
                lag_ms = (s - press_at[i]) * 1000.0
                self.assertGreaterEqual(lag_ms, -0.5)
                self.assertLessEqual(lag_ms, FRAME_S * 1000.0 + 2.0)
            # Every stim went to the pressed finger.
            self.assertEqual([c for _t, c in board.commands
                              if c.startswith("STIM:")],
                             ["STIM:1", "STIM:4"])

    def test_on_beat_mode_with_zero_latency_buzzes_on_the_beat(self):
        with tempfile.TemporaryDirectory() as td:
            eng, board = _make_engine(td, {"tactile_mode": "on_beat",
                                           "buzz_rise_comp_ms": 0})
            eng.cfg.data["latency"] = {"buzzer_ms": 0, "visual_ms": 0,
                                       "tone_ms": 0}
            bm = _beatmap(3)
            eng.begin_rhythm_block(bm)
            mode = eng.mode
            board.commands.clear()
            _pump(eng, 2.1)
            stims = _stims(board)
            self.assertEqual(len(stims), 3)
            zeros = [mode._t_start + n.t + 0.012 for n in bm.notes]
            errs = [(s - z) * 1000.0 for s, z in zip(stims, zeros)]
            self.assertLessEqual(abs(statistics.mean(errs)),
                                 FRAME_S * 1000.0)
            for e in errs:
                self.assertLessEqual(abs(e), FRAME_S * 1000.0 + 2.0, errs)


class BlockRecordTests(unittest.TestCase):
    """What a rhythm block leaves behind about its buzz."""

    def setUp(self) -> None:
        import pygame
        pygame.init()

    def tearDown(self) -> None:
        import pygame
        pygame.quit()

    def test_rows_summary_and_metadata_carry_the_tactile_state(self):
        with tempfile.TemporaryDirectory() as td:
            eng, board = _make_engine(td, {"tactile_mode": "lead",
                                           "buzz_lead_ms": 150,
                                           "buzz_lead_adapt": True,
                                           "buzz_lead_every": 2})
            bm = _beatmap(3, spacing_s=0.4)
            eng.begin_rhythm_block(bm)
            mode = eng.mode
            zeros = [mode._t_start + n.t + 0.012 for n in bm.notes]
            pressed = set()

            def responder(now):
                # Presses 100 ms late: two hits move the lead by 25.
                for i, z in enumerate(zeros):
                    if i not in pressed and now >= z + 0.100:
                        pressed.add(i)
                        mode.queue_press(_press(bm.notes[i].lane, now))

            _pump(eng, 2.2, on_frame=responder)
            root = Path(eng.session_paths.root)
            eng.finish_block()
            with (root / "trials.csv").open() as f:
                rows = list(csv.DictReader(f))
            self.assertEqual(len(rows), 3)
            params = [r["waveform_params"] for r in rows]
            self.assertIn("buzz_lead_ms=150", params[0])
            self.assertIn("tactile_mode=lead", params[0])
            self.assertIn("buzz_rise_comp_ms=45", params[0])
            # The third note was cued after the first update.
            self.assertIn("buzz_lead_ms=175", params[2])
            meta = json.loads((root / "metadata.json").read_text())
            tactile = meta["block_summary"]["tactile_cue"]
            self.assertEqual(tactile["mode"], "lead")
            self.assertEqual(tactile["buzz_lead_start_ms"], 150.0)
            self.assertEqual(tactile["buzz_lead_end_ms"], 175.0)
            self.assertEqual(tactile["buzz_lead_updates"], 1)
            lat = meta["eeg"]["latency"]
            self.assertEqual(lat["buzzer_ms"], 45.0)
            self.assertEqual(lat["visual_ms"], 20.0)
            self.assertFalse(lat["measured"])
            offs = meta["eeg"]["marker_offsets_ms"]
            self.assertEqual(offs["prep_buzz_lead"], 45.0)
            self.assertEqual(offs["stim_visual"], 20.0)
            self.assertEqual(offs["response"], 0.0)
            # The raw log names the leading pulse as such.
            with (root / "raw.csv").open() as f:
                raw = [r for r in csv.DictReader(f)
                       if r["event"] == "stim_motor"]
            self.assertEqual(len(raw), 3)
            self.assertTrue(all(r["detail"].startswith("lead;")
                                for r in raw))
            # The lead survives into the next block of the session.
            self.assertEqual(eng._rhythm_buzz_lead_ms, 175.0)
            eng._clear_session_carry()
            self.assertFalse(hasattr(eng, "_rhythm_buzz_lead_ms"))

    def test_shipping_default_is_lead_mode(self) -> None:
        from finger_rehab.config import Config
        cfg = Config.load()
        self.assertEqual(cfg.get("rhythm.tactile_mode"), "lead")
        self.assertEqual(float(cfg.get("rhythm.buzz_lead_ms")), 150.0)
        self.assertTrue(cfg.get("rhythm.buzz_lead_adapt"))
        self.assertEqual(float(cfg.get("rhythm.buzz_rise_comp_ms")), 0.0)
        self.assertFalse(cfg.get("latency.measured"))
        self.assertEqual(float(cfg.get("latency.buzzer_ms")), 45.0)
        self.assertEqual(float(cfg.get("latency.visual_ms")), 20.0)
        self.assertEqual(float(cfg.get("latency.tone_ms")), 12.0)


class ScreenClockTests(unittest.TestCase):
    """The falling notes read the display clock, not song_time."""

    def test_rhythm_screen_draws_against_display_song_time(self) -> None:
        import inspect
        from finger_rehab.ui import screens
        src = inspect.getsource(screens.RhythmScreen)
        self.assertGreaterEqual(src.count("display_song_time"), 2)


if __name__ == "__main__":
    unittest.main()
