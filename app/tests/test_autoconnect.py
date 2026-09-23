"""Plugging an Arduino in has to be the whole procedure.

Basil's report: "when arduino connected software should automatically
refresh and find and connect it to the right hand, i need to press
refresh manually." The Refresh button on the Settings screen was the
only way a newly plugged board ever entered play, so a board plugged in
at the login screen, on the game hub or between two games stayed
invisible. Nothing warned; the session just ran with a hand that never
registered a press.

The contract pinned here:

  - A board appearing at ANY screen joins on its own and takes the hand
    the existing rules give it (first detected = right, second = left).
  - A board arriving mid-game waits for the game to end. A running
    trial is never recorded against a source that gets swapped under it.
  - A board unplugged and plugged back in returns to the hand it had,
    with its baseline re-primed, even when the OS renames the port and
    hands the list back in a different order.
  - Saved Settings overrides still win.
  - serial.autoconnect: false switches the whole thing off.

Everything runs through the real engine, the real discovery module and
a real MultiSerialSource. Only two things are faked: the OS port list
(a Rig standing in for pyserial's comports) and the wire behind each
port, so no real hardware is opened.
"""
from __future__ import annotations

import time

import pytest

import finger_rehab.hardware.serial_source as ss
from finger_rehab.hardware.discovery import PortWatcher


A = "/dev/cu.usbmodemA"
B = "/dev/cu.usbmodemB"
# macOS renames a port between plug-ins, which is the whole reason the
# hand a board comes back on cannot be decided by the port name alone.
B_RENAMED = "/dev/cu.usbmodemB2"

REST = [240.0, 246.0, 250.0, 262.0]


class _Comport:
    """One entry in the faked comports() list."""

    def __init__(self, device: str) -> None:
        self.device = device
        self.vid = 0x2341
        self.pid = 0x0001
        self.description = "Arduino"


class Rig:
    """The faked OS: which boards are plugged in right now.

    Mutating `plugged` between polls is how a test plugs a board in.
    Stands in for serial_source.list_ports, so discover_ports and
    list_available_ports both see it, which means the port watcher and
    the source builder read the same world.
    """

    def __init__(self, plugged=()) -> None:
        self.plugged = list(plugged)

    def comports(self):
        return [_Comport(d) for d in self.plugged]


class _Wire:
    """The bytes behind one open port. Streams a resting FSR line."""

    LINE = b"FSR: 240,246,250,262\n"

    def __init__(self) -> None:
        self.is_open = True
        self.closed = False
        self.written = []

    def read(self, _n):
        # Nap so a source thread reading flat out cannot starve the
        # test's own thread on a single-core runner.
        time.sleep(0.002)
        return self.LINE

    def write(self, data):
        self.written.append(data)
        return len(data)

    def close(self):
        self.closed = True

    def reset_input_buffer(self):
        pass


@pytest.fixture
def rig(monkeypatch):
    """A faked OS port list plus a faked wire behind every port.

    Opening an unplugged port raises exactly as pyserial would, so the
    underlying source's own reopen loop behaves the way it does on the
    bench.
    """
    r = Rig()
    monkeypatch.setattr(ss, "list_ports", r)

    def fake_open(self):
        if self.port not in r.plugged:
            raise ss.serial.SerialException(f"no such device {self.port}")
        return _Wire()

    monkeypatch.setattr(ss.SerialSource, "_open", fake_open)
    return r


def _cfg(tmp_path, **serial_over):
    from finger_rehab.config import Config
    cfg = Config.load()
    cfg.data["ui"]["resolution"] = [1280, 800]
    cfg.data["audio"]["enabled"] = False
    cfg.data["session"]["data_dir"] = str(tmp_path)
    cfg.data["report"] = {"enabled": False}
    s = cfg.data.setdefault("serial", {})
    s.update({"port": "auto", "left_port": None, "right_port": None})
    s.update(serial_over)
    return cfg


def _engine(cfg):
    """A real GameEngine on whatever the rig currently offers, falling
    back to keyboard exactly as main.py does when nothing is plugged
    in."""
    import pygame
    pygame.init()
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.discovery import build_source_from_config
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    src = build_source_from_config(cfg) or KeyboardOnlySource()
    src.start()
    eng = GameEngine(cfg, src)
    return eng


def _watch(eng):
    """Attach a watcher without its thread, so a test decides exactly
    when a poll happens. start_port_watch runs the same object with a
    timer around it."""
    w = PortWatcher(eng.cfg)
    eng.port_watcher = w
    eng._port_watch_gen = w.generation
    return w


def _tick(eng):
    """One poll plus the frame's worth of reaction the main loop does."""
    eng.port_watcher.poll_once()
    eng.maybe_autoconnect()


def _pairs(eng):
    return [(h.hand, h.port) for h in (getattr(eng.source, "hands", None)
                                       or [])]


def _shutdown(eng):
    try:
        eng.stop_port_watch()
    except Exception:
        pass
    try:
        eng.source.stop()
    except Exception:
        pass
    import pygame
    pygame.quit()


def _calibrate(eng, hands=("right", "left")):
    from finger_rehab.hardware.calibration_profile import CalibrationProfile
    eng._ensure_both_detectors()
    for hand in hands:
        eng.apply_calibration(CalibrationProfile(
            hand=hand, participant="T",
            empty=[r - 15 for r in REST],
            empty_noise=[1.1] * 4,
            resting=list(REST),
            press=[r + 60 for r in REST],
        ))


class TestABoardArrivingJoinsOnItsOwn:
    def test_first_board_at_the_title_screen_takes_the_right_hand(
            self, rig, tmp_path):
        """The reported case: app up on the login screen with nothing
        plugged in, board goes in, and it has to be in play."""
        cfg = _cfg(tmp_path)
        eng = _engine(cfg)
        try:
            from finger_rehab.ui.screens import TitleScreen
            title = TitleScreen(eng)
            assert not eng.source.provides_samples, "expected keyboard mode"
            assert "No Arduino" in title._hardware_status()[0]

            _watch(eng)
            rig.plugged = [A]
            _tick(eng)

            assert _pairs(eng) == [("right", A)]
            # And the login screen says so without anyone reopening it.
            line, _colour = title._hardware_status()
            assert "RIGHT = usbmodemA" in line
        finally:
            _shutdown(eng)

    def test_a_second_board_takes_the_left_hand(self, rig, tmp_path):
        cfg = _cfg(tmp_path)
        rig.plugged = [A]
        eng = _engine(cfg)
        try:
            assert _pairs(eng) == [("right", A)]
            _watch(eng)
            rig.plugged = [A, B]
            _tick(eng)
            assert _pairs(eng) == [("right", A), ("left", B)]
            assert eng.source.hand_modes_available == {"right", "left",
                                                       "both"}
        finally:
            _shutdown(eng)

    def test_it_says_which_hand_arrived(self, rig, tmp_path):
        cfg = _cfg(tmp_path)
        rig.plugged = [A]
        eng = _engine(cfg)
        try:
            _watch(eng)
            rig.plugged = [A, B]
            _tick(eng)
            assert eng.autoconnect_notice() == "Left hand connected"
        finally:
            _shutdown(eng)

    def test_the_note_draws_and_times_itself_out(self, rig, tmp_path):
        """It is a note, not a nag: nothing to dismiss and no click to
        take, so it has to clear itself."""
        import pygame
        cfg = _cfg(tmp_path)
        rig.plugged = [A]
        eng = _engine(cfg)
        try:
            _watch(eng)
            rig.plugged = [A, B]
            _tick(eng)
            assert eng.autoconnect_notice()
            eng._draw_autoconnect_note(pygame.Surface((1280, 800)))
            # Wind the clock past the window rather than sleeping.
            eng._autoconnect_toast_until = time.perf_counter() - 0.01
            assert eng.autoconnect_notice() == ""
            eng._draw_autoconnect_note(pygame.Surface((1280, 800)))
        finally:
            _shutdown(eng)

    def test_a_settled_rig_is_left_alone(self, rig, tmp_path):
        """Nothing changed means nothing is rebuilt. A source swapped
        for no reason costs the board's boot self-test, which buzzes
        every motor on the patient's fingers."""
        cfg = _cfg(tmp_path)
        rig.plugged = [A, B]
        eng = _engine(cfg)
        try:
            _watch(eng)
            before = eng.source
            for _ in range(5):
                _tick(eng)
            assert eng.source is before
        finally:
            _shutdown(eng)


class TestUnplugAndReplug:
    def test_an_unplug_alone_does_not_rebuild(self, rig, tmp_path):
        """The board that is still there must not be torn down because
        the other one left. The connection banner and the underlying
        source's own reopen loop own the unplug."""
        cfg = _cfg(tmp_path)
        rig.plugged = [A, B]
        eng = _engine(cfg)
        try:
            _watch(eng)
            before = eng.source
            rig.plugged = [A]
            _tick(eng)
            assert eng.source is before
            assert _pairs(eng) == [("right", A), ("left", B)]
        finally:
            _shutdown(eng)

    def test_replug_returns_to_the_same_hand_with_a_primed_baseline(
            self, rig, tmp_path):
        """The port comes back under a new name and in a different
        place in the list. On plug order alone that puts the patient's
        left board on the right hand's lanes, and every press after it
        is attributed to the wrong hand in the data."""
        cfg = _cfg(tmp_path)
        rig.plugged = [A, B]
        eng = _engine(cfg)
        try:
            _calibrate(eng)
            _watch(eng)
            assert _pairs(eng) == [("right", A), ("left", B)]

            rig.plugged = [A]
            _tick(eng)
            # Slide the dead hand's baseline off the calibrated resting
            # level, which is what a stretch of zero-fill does to it.
            for i in range(4):
                eng.detectors["left"].baseline[i] = 0.0

            rig.plugged = [B_RENAMED, A]
            _tick(eng)

            assert _pairs(eng) == [("right", A), ("left", B_RENAMED)]
            for i, r in enumerate(REST):
                assert abs(eng.detectors["left"].baseline[i] - r) < 1.0
            assert list(eng.detectors["left"].pressed) == [False] * 4
        finally:
            _shutdown(eng)

    def test_the_only_board_replugged_stays_on_its_hand(self, rig,
                                                        tmp_path):
        """A single board that was the LEFT hand, unplugged and back in
        the same socket. Plug order alone would call it the right hand,
        so a left-hand-only session would silently start driving the
        right lanes. Only the run's own memory can hold it."""
        cfg = _cfg(tmp_path)
        rig.plugged = [B]
        eng = _engine(cfg)
        try:
            # Put it on the left hand the way a rebuild would.
            eng._hand_port_memory = {"left": B}
            _watch(eng)
            rig.plugged = []
            _tick(eng)
            rig.plugged = [B]
            _tick(eng)
            assert _pairs(eng) == [("left", B)]
        finally:
            _shutdown(eng)

    def test_a_renamed_lone_board_falls_back_to_plug_order(self, rig,
                                                            tmp_path):
        """The honest limit of the memory: it keys on the port name, so
        one board that comes back under a NEW name has nothing to be
        recognised by and takes the right hand. Pin it in Settings if
        that matters; the saved override outranks everything here."""
        cfg = _cfg(tmp_path)
        rig.plugged = [B]
        eng = _engine(cfg)
        try:
            eng._hand_port_memory = {"left": B}
            _watch(eng)
            rig.plugged = [B_RENAMED]
            _tick(eng)
            assert _pairs(eng) == [("right", B_RENAMED)]
        finally:
            _shutdown(eng)


class TestMidBlockArrivalWaits:
    def _screens(self, eng):
        from unittest.mock import MagicMock
        gp = MagicMock()
        gp.lanes = []
        eng._screens = {"gameplay": gp, "results": MagicMock()}

    def test_it_does_not_disturb_a_running_trial(self, rig, tmp_path):
        cfg = _cfg(tmp_path)
        rig.plugged = [A]
        eng = _engine(cfg)
        try:
            _calibrate(eng, ("right",))
            self._screens(eng)
            _watch(eng)
            eng.begin_classic_block()
            source_during_block = eng.source
            trial_before = eng._trials_fired

            rig.plugged = [A, B]
            for _ in range(10):
                _tick(eng)
                eng._pump_source()

            assert eng.source is source_during_block, \
                "swapped the source out from under a running block"
            assert _pairs(eng) == [("right", A)]
            assert eng.session_paths is not None
            assert eng._trials_fired == trial_before
            assert eng._pending_autoconnect is True
            assert "end of this game" in eng.autoconnect_notice()
        finally:
            _shutdown(eng)

    def test_it_lands_at_the_end_of_the_block(self, rig, tmp_path):
        cfg = _cfg(tmp_path)
        rig.plugged = [A]
        eng = _engine(cfg)
        try:
            _calibrate(eng, ("right",))
            self._screens(eng)
            _watch(eng)
            eng.begin_classic_block()
            rig.plugged = [A, B]
            _tick(eng)
            assert _pairs(eng) == [("right", A)]

            eng.finish_block()
            # No new port change: the queued rebuild fires on the next
            # frame of the main loop on its own.
            eng.maybe_autoconnect()

            assert _pairs(eng) == [("right", A), ("left", B)]
            assert eng._pending_autoconnect is False
        finally:
            _shutdown(eng)

    def test_the_manual_reconnect_still_refuses_mid_block(self, rig,
                                                          tmp_path):
        """reconnect_source read an `in_block` attribute nothing ever
        set, so its guard could never fire. The open session folder is
        the signal that actually tracks a live block."""
        cfg = _cfg(tmp_path)
        rig.plugged = [A]
        eng = _engine(cfg)
        try:
            _calibrate(eng, ("right",))
            self._screens(eng)
            eng.begin_classic_block()
            assert eng.block_is_running() is True
            msg = eng.reconnect_source()
            assert "block" in msg.lower()
            eng.finish_block()
            assert eng.block_is_running() is False
        finally:
            _shutdown(eng)


class TestSavedOverridesStillWin:
    def test_a_pinned_hand_keeps_its_board_on_autoconnect(self, rig,
                                                          tmp_path):
        cfg = _cfg(tmp_path, right_port=B)
        rig.plugged = [A]
        eng = _engine(cfg)
        try:
            _watch(eng)
            rig.plugged = [A, B]
            _tick(eng)
            assert _pairs(eng) == [("right", B), ("left", A)]
        finally:
            _shutdown(eng)

    def test_an_override_outranks_the_hand_a_board_had_before(self, rig,
                                                              tmp_path):
        cfg = _cfg(tmp_path)
        rig.plugged = [A, B]
        eng = _engine(cfg)
        try:
            _watch(eng)
            assert _pairs(eng) == [("right", A), ("left", B)]
            # Therapist pins A to the left hand in Settings, then
            # replugs B under a new name.
            cfg.data["serial"]["left_port"] = A
            rig.plugged = [A, B_RENAMED]
            _tick(eng)
            assert _pairs(eng) == [("right", B_RENAMED), ("left", A)]
        finally:
            _shutdown(eng)

    def test_a_stale_override_still_falls_back(self, rig, tmp_path):
        cfg = _cfg(tmp_path, right_port="/dev/cu.usbserial-130")
        eng = _engine(cfg)
        try:
            _watch(eng)
            rig.plugged = [A]
            _tick(eng)
            assert _pairs(eng) == [("right", A)]
            assert "ignored" in eng.source.assignment_note
        finally:
            _shutdown(eng)


class TestThePollCanBeSwitchedOff:
    def test_disabled_means_no_watcher_and_no_connecting(self, rig,
                                                          tmp_path):
        cfg = _cfg(tmp_path, autoconnect=False)
        eng = _engine(cfg)
        try:
            eng.start_port_watch()
            assert eng.port_watcher is None
            rig.plugged = [A, B]
            for _ in range(5):
                eng.maybe_autoconnect()
            assert not eng.source.provides_samples, \
                "connected a board with the poll switched off"
        finally:
            _shutdown(eng)

    def test_the_manual_refresh_path_still_works_when_disabled(
            self, rig, tmp_path):
        """Switching the poll off must not cost the Settings screen its
        Save-and-reconnect, which is the stubborn case it exists for."""
        cfg = _cfg(tmp_path, autoconnect=False)
        eng = _engine(cfg)
        try:
            eng.start_port_watch()
            rig.plugged = [A]
            msg = eng.reconnect_source()
            assert _pairs(eng) == [("right", A)]
            assert "usbmodemA" in msg
        finally:
            _shutdown(eng)


class TestTheWatcherItself:
    def test_it_notices_a_change_on_its_own_thread(self, rig, tmp_path):
        """Without this the whole feature is dead in the real app: the
        engine only ever reads a counter somebody else has to bump."""
        cfg = _cfg(tmp_path, autoconnect_poll_s=0.1)
        eng = _engine(cfg)
        try:
            eng.start_port_watch()
            assert eng.port_watcher is not None
            rig.plugged = [A]
            deadline = time.perf_counter() + 5.0
            while time.perf_counter() < deadline:
                eng.maybe_autoconnect()
                if _pairs(eng):
                    break
                time.sleep(0.02)
            assert _pairs(eng) == [("right", A)]
        finally:
            _shutdown(eng)

    def test_a_reorder_of_the_same_boards_is_not_a_change(self, rig,
                                                          tmp_path):
        """The OS enumerates ports in whatever order it likes. A
        reshuffle that moved the patient's hands mid-session would be
        worse than doing nothing."""
        cfg = _cfg(tmp_path)
        rig.plugged = [A, B]
        eng = _engine(cfg)
        try:
            w = _watch(eng)
            w.poll_once()
            gen = w.generation
            rig.plugged = [B, A]
            w.poll_once()
            assert w.generation == gen
            assert _pairs(eng) == [("right", A), ("left", B)]
        finally:
            _shutdown(eng)

    def test_a_failing_scan_does_not_kill_the_watcher(self, tmp_path):
        cfg = _cfg(tmp_path)
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] == 1:
                raise OSError("usb stack hiccup")
            return [A]

        w = PortWatcher(cfg, scan=flaky)
        assert w.poll_once() == []
        assert w.generation == 0
        assert w.poll_once() == [A]
        assert w.generation == 1

    def test_a_mistyped_interval_cannot_spin(self, tmp_path):
        w = PortWatcher(_cfg(tmp_path, autoconnect_poll_s=0), scan=list)
        assert w.interval_s >= 0.1


class TestTheSettingsPanelKeepsItself:
    def test_a_new_port_appears_without_a_refresh_press(self, rig,
                                                        tmp_path):
        cfg = _cfg(tmp_path)
        rig.plugged = [A]
        eng = _engine(cfg)
        try:
            import pygame
            from finger_rehab.ui.screens import DiagnosticsScreen
            d = DiagnosticsScreen(eng)
            _watch(eng)
            assert B not in [v for v, _ in
                             d._port_dropdowns["left"].options]

            rig.plugged = [A, B]
            _tick(eng)
            d.update(1 / 60)

            assert B in [v for v, _ in d._port_dropdowns["left"].options]
            assert d._port_status == "Left hand connected"
            d.draw(pygame.Surface((1280, 800)))
        finally:
            _shutdown(eng)

    def test_an_open_dropdown_is_not_reshuffled_under_the_cursor(
            self, rig, tmp_path):
        """Growing the option list mid-click would move the rows out
        from under the pointer, so the pick lands on the wrong port."""
        cfg = _cfg(tmp_path)
        rig.plugged = [A]
        eng = _engine(cfg)
        try:
            from finger_rehab.ui.screens import DiagnosticsScreen
            d = DiagnosticsScreen(eng)
            _watch(eng)
            d._port_dropdowns["left"].is_open = True
            rig.plugged = [A, B]
            _tick(eng)
            d.update(1 / 60)
            assert B not in [v for v, _ in
                             d._port_dropdowns["left"].options]
            # Closing it lets the panel catch up on the next frame.
            d._port_dropdowns["left"].is_open = False
            d.update(1 / 60)
            assert B in [v for v, _ in d._port_dropdowns["left"].options]
        finally:
            _shutdown(eng)

    def test_an_unplug_is_reported_on_the_panel(self, rig, tmp_path):
        cfg = _cfg(tmp_path)
        rig.plugged = [A, B]
        eng = _engine(cfg)
        try:
            from finger_rehab.ui.screens import DiagnosticsScreen
            d = DiagnosticsScreen(eng)
            _watch(eng)
            rig.plugged = [A]
            _tick(eng)
            d.update(1 / 60)
            assert "1 Arduino-family port" in d._port_status
        finally:
            _shutdown(eng)
