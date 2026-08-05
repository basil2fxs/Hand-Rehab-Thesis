"""The connection has to survive a glitch without a restart.

The reader thread used to exit for good the first time a read failed.
Any hiccup at all, a USB glitch, the board resetting, the cable nudged,
killed the connection permanently and the only way back was restarting
the app. Mid-session that costs the block.
"""
from __future__ import annotations

import time

import pytest

import rehab.hardware.serial_source as ss


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
        from rehab.game.engine import GameEngine
        assert hasattr(GameEngine, "reconnect_source")

    def test_it_refuses_mid_block(self):
        from rehab.game.engine import GameEngine
        e = GameEngine.__new__(GameEngine)
        e.in_block = True
        msg = GameEngine.reconnect_source(e)
        assert "block" in msg.lower()

    def test_startup_and_settings_share_one_resolver(self):
        """They were the same rules written twice and only one copy was
        ever kept up to date."""
        import main
        from rehab.hardware import discovery
        import inspect
        assert "discovery" in inspect.getsource(main._resolve_ports_and_hands)
