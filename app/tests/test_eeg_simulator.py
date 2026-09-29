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
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

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
