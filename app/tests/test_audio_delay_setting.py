"""Settings, Setup, Audio delay: this computer's sound and buzz delays measured
from inside the app (Basil, 28 September 2026), so a new computer, the
lab's included, needs nothing installed before Rhythm is scored.

The measurement itself is the script's, moved into the package
(audio/latency_measure.py); these tests pin the button, the card, the
hand-over of the port and the music, and the values landing in the
running config.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


@pytest.fixture
def settings():
    import pygame
    pygame.init()
    pygame.font.init()
    from finger_rehab.config import Config
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    from finger_rehab.ui.screens import DiagnosticsScreen
    cfg = Config.load()
    cfg.data.setdefault("ui", {})["resolution"] = [1280, 800]
    cfg.data.setdefault("latency", {})["measured"] = False
    eng = GameEngine(cfg, KeyboardOnlySource())
    screen = DiagnosticsScreen(eng)
    eng._screens["diagnostics"] = screen
    eng.screen_obj = screen
    yield screen, eng
    pygame.quit()


class FakeJob:
    """A LatencyJob that finishes when the test says so."""

    def __init__(self, ok=True, values=None, message="Saved."):
        self.done = False
        self.ok = ok
        self.values = values if values is not None else {
            "audio_offset_ms": 80, "metronome_offset_ms": 70,
            "tone_ms": 70, "buzzer_ms": 60}
        self.message = message
        self.lines = ["Microphone delay: 12.0 ms."]

    def start(self):
        pass


def _button(screen, label):
    return next(b for b in screen._panel_buttons if b.label == label)


def _hand_over(eng, monkeypatch):
    calls = []
    monkeypatch.setattr(eng, "begin_firmware_job",
                        lambda: calls.append("begin"))
    monkeypatch.setattr(eng, "end_firmware_job",
                        lambda: calls.append("end") or "")
    return calls


def test_the_button_sits_in_setup_and_says_what_to_do(settings):
    screen, eng = settings
    b = _button(screen, "Measure audio delay")
    assert screen._firmware_rect().contains(b.rect)
    eng.cfg.data["latency"]["measured"] = True
    screen.rebuild_panel()
    assert screen._firmware_rect().contains(
        _button(screen, "Audio delay: measured").rect)


def test_the_card_says_what_is_in_use_and_esc_closes_it(settings):
    import pygame
    from finger_rehab.ui.audio_delay_dialog import AudioDelayDialog
    screen, _eng = settings
    _button(screen, "Measure audio delay").on_click()
    assert isinstance(screen._dialog, AudioDelayDialog)
    assert "not measured on this computer" in screen._dialog.now_line
    screen.draw(pygame.Surface((1280, 800)))
    assert screen.on_escape() is True
    assert screen._dialog is None


def test_a_measurement_quiets_the_game_and_lands_in_the_config(
        settings, monkeypatch):
    from finger_rehab.audio import latency_measure
    screen, eng = settings
    job = FakeJob()
    started = []
    monkeypatch.setattr(latency_measure, "LatencyJob",
                        lambda track, port: started.append(track) or job)
    calls = _hand_over(eng, monkeypatch)
    screen._open_audio_dialog()
    dlg = screen._dialog
    dlg._start()
    assert dlg.busy and calls == ["begin"]
    assert eng._measuring_audio
    assert started[0].name == "Easy_Lemon.mp3"
    screen.update(0.016)
    assert dlg.busy
    job.done = True
    screen.update(0.016)
    assert calls == ["begin", "end"]
    assert not eng._measuring_audio
    assert dlg.finished and dlg.result_ok
    assert eng.cfg.get("rhythm.audio_offset_ms") == 80
    assert eng.cfg.get("latency.measured") is True
    assert eng.latency_settings().tone_ms == 70
    assert eng.latency_settings().buzzer_ms == 60
    assert "song 80 ms" in dlg.now_line
    assert _button(screen, "Audio delay: measured")


def test_a_failed_measurement_changes_nothing(settings, monkeypatch):
    from finger_rehab.audio import latency_measure
    screen, eng = settings
    before = eng.cfg.get("rhythm.audio_offset_ms")
    job = FakeJob(ok=False, values={}, message=latency_measure.NOT_SAVED)
    monkeypatch.setattr(latency_measure, "LatencyJob",
                        lambda track, port: job)
    _hand_over(eng, monkeypatch)
    screen._open_audio_dialog()
    dlg = screen._dialog
    dlg._start()
    job.done = True
    screen.update(0.016)
    assert dlg.finished and not dlg.result_ok
    assert dlg.result_text == latency_measure.NOT_SAVED
    assert eng.cfg.get("rhythm.audio_offset_ms") == before
    assert eng.cfg.get("latency.measured") is False
    assert _button(screen, "Measure audio delay")


def test_a_running_block_refuses(settings, monkeypatch):
    screen, eng = settings
    monkeypatch.setattr(eng, "firmware_job_allowed",
                        lambda: "Not while a block is running.")
    screen._open_audio_dialog()
    assert screen._dialog is None
    assert "Not while a block" in screen._port_status


def test_the_menu_music_is_silent_while_it_listens(settings, monkeypatch):
    _screen, eng = settings

    class Player:
        def __init__(self):
            self.muted = []
            self.stopped = 0

        def update(self, _key, _running, muted=False):
            self.muted.append(muted)

        def stop_now(self):
            self.stopped += 1

    eng.audio = object()
    eng.menu_music = Player()
    _hand_over(eng, monkeypatch)
    eng.begin_audio_measurement()
    assert eng.menu_music.stopped == 1
    eng._tick_menu_music()
    assert eng.menu_music.muted[-1] is True
    eng.end_audio_measurement()
    eng._tick_menu_music()
    assert eng.menu_music.muted[-1] is False


# ---- the measurement's own logic -------------------------------------------

def _rows(song, click):
    rows = [{"path": "song", "take": i + 1, "to_mic_ms": v, "usable": True}
            for i, v in enumerate(song)]
    rows += [{"path": "click", "take": i + 1, "to_mic_ms": v,
              "usable": True} for i, v in enumerate(click)]
    return rows


def test_the_values_are_the_medians_less_the_microphone():
    from finger_rehab.audio import latency_measure as lm
    rows = _rows([100, 102, 98], [90, 92, 88])
    values, detail = lm.result_values(rows, 20.0,
                                      {1: 93, 2: 95, 3: 95, 4: 99})
    assert values == {"audio_offset_ms": 80, "tone_ms": 70,
                      "metronome_offset_ms": 70, "buzzer_ms": 75}
    assert detail["microphone_delay_ms"] == 20.0
    assert lm.savable(values)
    assert lm.summary(values) == "song 80 ms, short sounds 70 ms, buzz 75 ms"
    # Two clear song takes are not enough to save.
    values, _ = lm.result_values(_rows([100, 102], [90, 92, 88]), 20.0, {})
    assert "audio_offset_ms" not in values
    assert not lm.savable(values)


def test_with_no_way_to_time_the_microphone_it_says_why(monkeypatch):
    from finger_rehab.audio import latency_measure as lm
    monkeypatch.setattr(lm, "coreaudio_input_ms", lambda: (None, {}))

    def never(*_a, **_k):
        raise AssertionError("no sound step without a microphone delay")
    monkeypatch.setattr(lm, "run_sound", never)
    said = []
    res = lm.measure(Path("song.mp3"), None, say=said.append)
    assert res["problem"] == lm.NO_MIC
    assert res["rows"] == []


def test_every_step_runs_and_the_result_is_savable(monkeypatch):
    from finger_rehab.audio import latency_measure as lm
    monkeypatch.setattr(lm, "coreaudio_input_ms", lambda: (20.0, {}))
    monkeypatch.setattr(lm, "run_sound",
                        lambda *_a, **_k: _rows([100, 102, 98],
                                                [90, 92, 88]))
    monkeypatch.setattr(lm, "run_motors",
                        lambda *_a, **_k: {1: 93, 2: 95, 3: 95, 4: 99})
    said = []
    res = lm.measure(Path("song.mp3"), "COM3", say=said.append)
    assert res["problem"] == ""
    assert res["values"]["buzzer_ms"] == 75
    assert any("Microphone delay: 20.0 ms" in s for s in said)


def test_the_job_saves_the_profile_the_game_reads(tmp_path, monkeypatch):
    from finger_rehab import config as cfgmod
    from finger_rehab.audio import latency_measure as lm
    monkeypatch.setattr(cfgmod, "LATENCY_PROFILE",
                        tmp_path / "config" / "latency_profile.yaml")
    monkeypatch.setattr(cfgmod, "USER_ROOT", tmp_path)
    values = {"audio_offset_ms": 80, "tone_ms": 70,
              "metronome_offset_ms": 70}
    monkeypatch.setattr(lm, "measure", lambda *_a, **_k: {
        "values": values, "detail": {"microphone_delay_ms": 20.0},
        "rows": _rows([100, 102, 98], [90, 92, 88]), "problem": ""})
    job = lm.LatencyJob(Path("song.mp3"), None)
    job._run()
    assert job.done and job.ok
    assert job.message == "Saved: song 80 ms, short sounds 70 ms."
    got = cfgmod.read_latency_profile()
    assert got["rhythm"]["audio_offset_ms"] == 80
    assert got["latency"]["measured"] is True
    assert list((tmp_path / "config" / "calibration").glob(
        "audio_latency_*.csv"))


def test_the_card_asks_for_taps_where_the_system_cannot_say(
        settings, monkeypatch):
    from finger_rehab.ui import audio_delay_dialog as ad
    screen, _eng = settings

    def lines(taps, board):
        monkeypatch.setattr(ad, "needs_taps", lambda: taps)
        dlg = ad.AudioDelayDialog(screen.theme, screen.layout,
                                  now_line="x", has_board=board)
        return dlg.intro_lines()
    warn = [t for t, w in lines(True, False) if w]
    assert warn and "Plug the board in" in warn[0]
    assert any("tap the index pad" in t for t, _w in lines(True, True))
    assert not any("tap" in t for t, _w in lines(False, True))


def test_the_script_is_a_front_end_to_the_same_code():
    sys.path.insert(0, str(ROOT / "scripts"))
    import audio_latency as al
    from finger_rehab.audio import latency_measure as lm
    assert al.measure is lm.measure
    assert al._lag is lm._lag


def test_the_mac_build_asks_for_the_microphone():
    spec = (ROOT / "finger_rehab.spec").read_text(encoding="utf-8")
    assert "NSMicrophoneUsageDescription" in spec
    assert "pygame._sdl2.audio" in spec
