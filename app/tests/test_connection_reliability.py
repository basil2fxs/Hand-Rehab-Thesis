"""The connection has to survive a glitch without a restart.

The reader thread used to exit for good the first time a read failed.
Any hiccup at all, a USB glitch, the board resetting, the cable nudged,
killed the connection permanently and the only way back was restarting
the app. Mid-session that costs the block.
"""
from __future__ import annotations

import time

import pytest

import finger_rehab.hardware.serial_source as ss


class FakePort:
    """A port that dies after a set number of reads."""

    def __init__(self, die_after=None):
        self.is_open = True
        self.reads = 0
        self.die_after = die_after
        self.closed = False
        self.written = []

    def read(self, _n):
        self.reads += 1
        if self.die_after is not None and self.reads > self.die_after:
            raise OSError("device disconnected")
        return b"FSR: 250,260,255,270\n"

    def write(self, data):
        self.written.append(data)
        return len(data)

    def close(self):
        self.closed = True

    def reset_input_buffer(self):
        pass


@pytest.fixture
def source_factory(monkeypatch):
    made = []

    def build(open_plan):
        """open_plan: list of FakePort or Exception, one per open call."""
        calls = {"n": 0}

        def fake_open(self):
            i = calls["n"]
            calls["n"] += 1
            item = open_plan[min(i, len(open_plan) - 1)]
            if isinstance(item, Exception):
                raise item
            return item

        monkeypatch.setattr(ss.SerialSource, "_open", fake_open)
        src = ss.SerialSource.__new__(ss.SerialSource)
        ss.SerialSource.__init__(src, port="/dev/fake", baud=115200)
        src.reconnect_delay_s = 0.02
        src.reconnect_max_delay_s = 0.05
        made.append((src, calls))
        return src, calls

    yield build
    for src, _ in made:
        try:
            src.stop()
        except Exception:
            pass


class TestItComesBack:
    def test_a_dropped_read_reconnects(self, source_factory):
        src, calls = source_factory([FakePort(die_after=3), FakePort()])
        src.start()
        time.sleep(0.5)
        assert calls["n"] >= 2, "never tried to reopen"
        assert src._connected, "did not come back"

    def test_samples_flow_again_after_a_drop(self, source_factory):
        src, _ = source_factory([FakePort(die_after=2), FakePort()])
        src.start()
        time.sleep(0.5)
        assert src.get_sample(timeout=0.4) is not None

    def test_it_keeps_trying_when_the_port_is_missing(self, source_factory):
        """An unplugged board should recover the moment it is plugged
        back in, with no restart and no button to press."""
        src, calls = source_factory([
            ss.serial.SerialException("no such device"),
            ss.serial.SerialException("no such device"),
            FakePort(),
        ])
        src.start()
        time.sleep(0.6)
        assert calls["n"] >= 3
        assert src._connected

    def test_it_backs_off_rather_than_spinning(self, source_factory):
        src, calls = source_factory(
            [ss.serial.SerialException("nope")])
        src.reconnect_delay_s = 0.05
        src.reconnect_max_delay_s = 0.2
        src.start()
        time.sleep(0.8)
        src.stop()
        # Without a backoff this would be hundreds of attempts.
        assert calls["n"] < 40, f"spinning: {calls['n']} attempts"

    def test_stop_still_ends_the_thread(self, source_factory):
        src, _ = source_factory([FakePort()])
        src.start()
        time.sleep(0.2)
        src.stop()
        time.sleep(0.2)
        assert not src._connected
        assert src._thread is None or not src._thread.is_alive()

    def test_the_old_port_is_closed_on_reconnect(self, source_factory):
        first = FakePort(die_after=2)
        src, _ = source_factory([first, FakePort()])
        src.start()
        time.sleep(0.4)
        assert first.closed, "leaked the dead port"


class TestWritesDoNotCrash:
    def test_sending_while_disconnected_returns_false(self, source_factory):
        src, _ = source_factory([ss.serial.SerialException("nope")])
        src.start()
        time.sleep(0.1)
        assert src.send_command("STIM:1") is False

    def test_sending_works_again_after_a_reconnect(self, source_factory):
        port = FakePort()
        src, _ = source_factory([FakePort(die_after=2), port])
        src.start()
        time.sleep(0.5)
        assert src.send_command("STIM:4") is True
        assert any(b"STIM:4" in w for w in port.written)


class TestPortChangesApplyLive:
    def test_the_engine_can_rebuild_its_source(self):
        """Changing a port used to need an app restart, which the
        Settings screen said out loud."""
        from finger_rehab.game.engine import GameEngine
        assert hasattr(GameEngine, "reconnect_source")

    def test_it_refuses_mid_block(self):
        from finger_rehab.game.engine import GameEngine
        e = GameEngine.__new__(GameEngine)
        e.in_block = True
        msg = GameEngine.reconnect_source(e)
        assert "block" in msg.lower()

    def test_startup_and_settings_share_one_resolver(self):
        """They were the same rules written twice and only one copy was
        ever kept up to date. Startup now delegates to the exact
        builder the Settings reconnect calls."""
        import main
        import inspect
        src = inspect.getsource(main._build_source)
        assert "build_source_from_config" in src


class TestOneBoardDropInBilateral:
    """A one-board drop in a bilateral block used to be invisible:
    is_connected is any-board-alive, so the engine's drop handler never
    fired, the merger's zero-fill slid the dead hand's baseline toward
    0, and the reconnect fired phantom presses on every lane that then
    latched permanently (the frozen off threshold sits below even an
    empty pad's reading). All patient-attributed, nothing logged."""

    REST_R = [238.0, 245.0, 248.0, 268.0]
    REST_L = [242.0, 251.0, 239.0, 260.0]

    class FakeSample:
        def __init__(self, t, values):
            self.t_perf = t
            self.values = values

    class FakeMultiSource:
        """MultiSerial-shaped: 8-value samples, right then left; a
        dead left board zero-fills, exactly like the real merger."""
        provides_samples = True
        name = "FakeMulti(right@/dev/r,left@/dev/l)"

        def __init__(self):
            self.queued = []
            self.left_alive = True
            self.right_alive = True

        @property
        def is_connected(self):
            return self.left_alive or self.right_alive

        @property
        def hands_connected(self):
            return {"right": self.right_alive, "left": self.left_alive}

        def start(self): ...

        def stop(self): ...

        def get_sample(self, timeout=0.0):
            return self.queued.pop(0) if self.queued else None

        def send_command(self, cmd):
            return True

        def has_recent_data(self, window_s=1.0):
            return True

    def _engine(self, tmp_path):
        import os
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        import pygame
        pygame.init()
        from unittest.mock import MagicMock
        from finger_rehab.config import Config
        from finger_rehab.game.engine import GameEngine
        from finger_rehab.hardware.calibration_profile import (
            CalibrationProfile)
        cfg = Config.load()
        cfg.data["ui"]["resolution"] = [640, 480]
        cfg.data["audio"]["enabled"] = False
        cfg.data["session"]["data_dir"] = str(tmp_path)
        cfg.data["report"] = {"enabled": False}
        cfg.data.setdefault("bilateral", {})["hand"] = "both"
        src = self.FakeMultiSource()
        eng = GameEngine(cfg, src)
        gp = MagicMock()
        gp.lanes = []
        eng._screens = {"gameplay": gp, "results": MagicMock()}
        for hand, rest in (("right", self.REST_R), ("left", self.REST_L)):
            prof = CalibrationProfile(
                hand=hand, participant="T",
                empty=[r - 15 for r in rest],
                empty_noise=[1.1] * 4,
                resting=list(rest),
                press=[r + 60 for r in rest])
            eng.apply_calibration(prof)
        return eng, src

    def _feed(self, eng, src, t0, secs, left_zero=False):
        t = t0
        dt = 1 / 200
        for _ in range(int(secs * 200)):
            t += dt
            left = ((0,) * 4 if left_zero
                    else tuple(int(v) for v in self.REST_L))
            right = tuple(int(v) for v in self.REST_R)
            src.queued.append(self.FakeSample(t, right + left))
            if len(src.queued) > 30:
                eng._pump_source()
        eng._pump_source()
        return t

    def _events(self, eng):
        import csv
        from pathlib import Path
        root = Path(eng.session_paths.root)
        eng.raw_logger.flush() if hasattr(eng.raw_logger, "flush") else None
        eng.finish_block()
        with (root / "raw.csv").open() as f:
            return [(r["event"], r.get("hand"))
                    for r in csv.DictReader(f)
                    if r.get("event") in ("source_disconnected",
                                          "source_reconnected")]

    def test_drop_and_reconnect_leave_no_phantoms_and_are_logged(
            self, tmp_path):
        import time as _time
        eng, src = self._engine(tmp_path)
        eng.begin_classic_block()
        presses = []
        for det in eng.detectors.values():
            orig = det.on_press

            def wrap(ev, _orig=orig):
                presses.append((ev.hand, ev.lane))
                return _orig(ev)

            det.on_press = wrap
        t = _time.perf_counter()
        t = self._feed(eng, src, t, 2.0)
        src.left_alive = False
        t = self._feed(eng, src, t, 2.0, left_zero=True)
        src.left_alive = True
        n0 = len(presses)
        t = self._feed(eng, src, t, 3.0)
        left = eng.detectors["left"]
        # No phantom presses at reconnect, nothing latched, baseline
        # re-primed at the calibrated resting level.
        assert presses[n0:] == []
        assert list(left.pressed) == [False] * 4
        for i, r in enumerate(self.REST_L):
            assert abs(left.baseline[i] - r) < 1.0
        # A real press after the reconnect still registers.
        press_vals = tuple(int(v) for v in self.REST_R) + (
            int(self.REST_L[0] + 60),) + tuple(
            int(v) for v in self.REST_L[1:])
        dt = 1 / 200
        for _ in range(120):
            t += dt
            src.queued.append(self.FakeSample(t, press_vals))
        eng._pump_source()
        assert ("left", 0) in presses[n0:]
        events = self._events(eng)
        assert ("source_disconnected", "left") in events
        assert ("source_reconnected", "left") in events

    def test_dead_hand_is_parked_not_fed_zeros(self, tmp_path):
        import time as _time
        eng, src = self._engine(tmp_path)
        eng.begin_classic_block()
        t = _time.perf_counter()
        t = self._feed(eng, src, t, 1.0)
        base_before = list(eng.detectors["left"].baseline)
        src.left_alive = False
        self._feed(eng, src, t, 3.0, left_zero=True)
        base_after = list(eng.detectors["left"].baseline)
        # The baseline held instead of sliding toward the zero-fill.
        for b0, b1 in zip(base_before, base_after):
            assert abs(b0 - b1) < 0.5
        assert "left" in eng._hands_down
        eng.finish_block()

    def test_connection_alert_names_the_dead_hand(self, tmp_path):
        import time as _time
        eng, src = self._engine(tmp_path)
        eng.begin_classic_block()
        t = _time.perf_counter()
        t = self._feed(eng, src, t, 0.5)
        assert eng.connection_alert() is None
        src.left_alive = False
        self._feed(eng, src, t, 0.5, left_zero=True)
        alert = eng.connection_alert()
        assert alert is not None and "LEFT" in alert
        eng.finish_block()
        # No block open: nothing to warn over.
        assert eng.connection_alert() is None

    def test_full_drop_reconnect_writes_the_marker(self, tmp_path):
        # The reconnect moment matters: opening the port resets the
        # Arduino, whose boot self-test buzzes all four motors.
        # Trials overlapping that unmarked stimulation used to be
        # indistinguishable afterwards.
        import time as _time
        eng, src = self._engine(tmp_path)
        eng.begin_classic_block()
        t = _time.perf_counter()
        t = self._feed(eng, src, t, 0.5)
        src.left_alive = False
        src.right_alive = False
        eng._pump_source()
        src.left_alive = True
        src.right_alive = True
        self._feed(eng, src, t, 0.5)
        events = self._events(eng)
        assert ("source_disconnected", "both") in events
        assert ("source_reconnected", "both") in events
