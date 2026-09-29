"""The EEG simulator (Basil, 29 September 2026): the lab session
rehearsed on any PC. The game's own trigger code writes to a socket://
address, the simulator reads the bytes the box would get, names each one
from the code map and measures its pulse, and draws them over made-up
EEG. These tests run the real byte path over a local socket."""
from __future__ import annotations

import os
import socket
import sys
import time
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finger_rehab.utils import eeg_simulator as sim  # noqa: E402


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_every_code_is_named_in_plain_words():
    from finger_rehab.hardware import eeg_trigger as et
    for code in range(1, 256):
        name, words, band = sim.describe(code)
        assert words
        if et.name_of(code) != "unknown":
            assert band != "unknown", code
    assert sim.describe(103)[1] == "right press: right little"
    assert sim.describe(114)[1] == "wrong finger: left index"
    assert sim.describe(200)[1] == "start of a reaction block"


def test_the_games_trigger_code_reaches_it_over_a_socket():
    from finger_rehab.hardware import eeg_trigger as et
    port = _free_port()
    rx = sim.ByteReceiver(listen_port=port)
    rx.start()
    try:
        for _ in range(50):
            if rx.state == "waiting":
                break
            time.sleep(0.02)
        be = et.SerialBackend(f"socket://127.0.0.1:{port}", 9600)
        assert be.open(), be.last_error
        for code in (240, 33, 103):
            assert be.write_code(code)
            time.sleep(0.01)
            assert be.write_code(0)
            time.sleep(0.03)
        for _ in range(50):
            if len(rx.snapshot()) == 3:
                break
            time.sleep(0.02)
        got = rx.snapshot()
        assert [m.code for m in got] == [240, 33, 103]
        assert all(m.pulse_ms is not None and m.pulse_ms > 5 for m in got)
        assert rx.state == "connected"
        be.close()
    finally:
        rx.stop()


def test_a_pulse_is_the_time_to_the_zero_after_it():
    rx = sim.ByteReceiver()
    rx.feed(bytes([33]), t=10.0)
    rx.feed(bytes([0]), t=10.008)
    rx.feed(bytes([112, 0]), t=11.0)
    got = rx.snapshot()
    assert round(got[0].pulse_ms, 3) == 8.0
    assert got[1].code == 112 and got[1].pulse_ms == 0.0


def test_close_numbers_stack_instead_of_covering_each_other():
    # A cue, then a press and its feedback 17 ms apart, then a cue
    # well clear of them: 30 px chips at 82 px a second.
    chips = [(100.0, "c", 33), (130.0, "c", 101), (131.4, "c", 140),
             (300.0, "c", 21)]
    got = sim.stack_labels(chips, lambda code: 30, top=10)
    tops = [y for _x, _c, _code, y in got]
    assert tops == [10, 30, 50, 10]
    # More than three at one spot reuse the row that frees up first.
    crowd = [(100.0 + i, "c", 100 + i) for i in range(4)]
    assert [y for *_r, y in sim.stack_labels(crowd, lambda c: 30, 0)] \
        == [0, 20, 40, 0]


def test_the_window_fits_the_screens_it_has():
    app = sim.SimulatorApp(sim.ByteReceiver())
    # A second screen: the simulator takes it, at full size.
    display, size = app.window_plan([(1920, 1080), (1920, 1080)])
    assert display == 1 and size == (app.W, app.H)
    # One laptop screen: two thirds of its width at most, in proportion,
    # so the windowed game still has room beside it.
    display, (w, h) = app.window_plan([(1920, 1080)])
    assert display == 0 and w <= 1280 and abs(w / h - app.W / app.H) < 0.01
    display, (w, h) = app.window_plan([(1366, 768)])
    assert w <= 1366 * 2 // 3 and h <= 768 - 80
    assert app.window_plan([]) == (0, (app.W, app.H))


def test_a_blink_shows_in_full_at_the_frame_rate():
    # A frame is a handful of samples; each blink used to stop at the
    # end of the frame it began in, so live blinks never showed.
    eeg = sim.FakeEEG(seed=3)
    t0 = eeg.t0
    for i in range(1, 60 * 12):
        eeg.advance(t0 + i / 60, [])
    assert eeg.data[0].max() > 5.0     # Fp1: a blink peaks near 7


def test_a_long_pause_keeps_the_markers_on_time():
    # Away longer than the buffer holds: the newest samples must carry
    # their own times, or a cue's Pz response lands in the wrong place.
    eeg = sim.FakeEEG(seed=3)
    t0 = eeg.t0
    eeg.advance(t0 + 1.0, [])
    cue = sim.Marker(t0 + 39.0, 33)
    eeg.advance(t0 + 40.0, [cue])
    pz = eeg.data[5]
    peak_at = (40.0 - 39.3) * sim.RATE        # 0.3 s after the cue
    i = eeg.n - int(round(peak_at))
    window = pz[i - 10:i + 10]
    assert window.mean() > pz[: eeg.n // 2].mean() + 1.5


def test_saving_where_it_cannot_write_says_so(tmp_path, monkeypatch):
    import pygame
    pygame.init()
    try:
        app = sim.SimulatorApp(sim.ByteReceiver())
        locked = tmp_path / "locked"
        locked.mkdir()
        locked.chmod(0o500)
        monkeypatch.setattr(sim, "save_folder", lambda: locked / "x")
        assert app.handle_key(pygame.K_s) is True
        assert app.note.startswith("Could not save")
        monkeypatch.setattr(sim, "save_folder", lambda: tmp_path / "ok")
        app.handle_key(pygame.K_s)
        assert app.note.startswith("Saved ")
        assert list((tmp_path / "ok").glob("eeg_simulator_*.csv"))
        locked.chmod(0o700)
    finally:
        pygame.quit()


def test_the_window_draws_and_saves(tmp_path):
    import pygame
    pygame.init()
    try:
        rx = sim.ByteReceiver()
        app = sim.SimulatorApp(rx)
        surf = pygame.Surface((app.W, app.H))
        now = time.perf_counter()
        rx.feed(bytes([21]), t=now - 3.0)
        rx.feed(bytes([0]), t=now - 2.992)
        rx.feed(bytes([33]), t=now - 1.0)
        rx.feed(bytes([0]), t=now - 0.992)
        app.eeg.advance(now, rx.snapshot())
        app.draw(surf, now)
        assert app.handle_key(pygame.K_SPACE) and app.paused
        app.draw(surf, now)
        assert app.handle_key(pygame.K_ESCAPE) is False
        path = sim.save_csv(rx.snapshot(), tmp_path)
        rows = path.read_text(encoding="utf-8").splitlines()
        assert rows[0].startswith("seconds,code,name")
        assert len(rows) == 3
    finally:
        pygame.quit()


def test_the_game_starts_it_from_the_command_line():
    import main
    sys.argv = ["main.py", "--eeg-simulator", "--listen", "50411"]
    args = main.parse_args()
    assert args.eeg_simulator and args.listen == 50411
    # The rehearsal opens the game in a window beside the simulator.
    sys.argv = ["main.py", "--windowed", "--eeg-port",
                "socket://127.0.0.1:50410"]
    args = main.parse_args()
    assert args.windowed and args.eeg_port.startswith("socket://")
    cmd = (ROOT.parent / "EEG_Lab" / "developer"
           / "EEG simulator.cmd").read_text(encoding="utf-8")
    assert "--windowed --eeg-port socket://127.0.0.1:50410" in cmd
