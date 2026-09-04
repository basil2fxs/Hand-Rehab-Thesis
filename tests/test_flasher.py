"""Flashing the Arduino from Settings, and moving a sensor's address.

Basil's ask: "in settings ... option to straight-up be able to flash the
arduino with platformio project with one click, silently (should be able
to happen on any computer once exe installed all dependencies) and also
with another button popup change the sensor address like the file
bin/old_rayyan_stuff/SingleTactAddressChange.ino does except silently in
background of app with exe covering all dependencies."

What is pinned here:

  - The avrdude command line is PlatformIO's own. If it drifts, a board
    that flashes from the IDE stops flashing from the app and nobody
    would know which of the two changed.
  - A board on the old bootloader still flashes. The baud is a guess,
    so a sync failure retries at the other speed and the winner is
    remembered. A busy port or a wrong chip is NOT retried: it fails
    the same way twice and only wastes the therapist's time.
  - The app's serial reader lets go of the port before avrdude opens it
    and gets it back afterwards, in that order. Both halves run on the
    main thread; the job thread never touches the engine.
  - A change from 0x04 is refused while any other address answers.
    Every SingleTact answers 0x04 as well as its own address, so that
    write would land on every sensor on the bus at once and the finger
    mapping would be gone with no way to tell which sensor is which.
  - The game firmware goes back on the board whatever happened, and
    when it cannot, the result says so in those words.
  - A hex whose sha256 does not match the manifest is never flashed. A
    half written flash leaves a board with nothing usable on it.

Only the OS edge is faked: a Python script stands in for avrdude, and a
scripted object stands in for the serial port. The engine, the screen,
the config and the dialog are all the real ones.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from finger_rehab.hardware import flasher


REPO_ROOT = Path(__file__).resolve().parents[1]


# ---------------------------------------------------------------------
# A fake avrdude
# ---------------------------------------------------------------------

FAKE_AVRDUDE = '''\
"""Stands in for avrdude. Behaviour comes from FAKE_AVRDUDE in the env.

Every run appends its argv to the file named by FAKE_AVRDUDE_LOG, so a
test can assert on the exact command line the flasher built.
"""
import json
import os
import sys
import time

argv = sys.argv[1:]
log = os.environ.get("FAKE_AVRDUDE_LOG")
if log:
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(argv) + "\\n")

mode = os.environ.get("FAKE_AVRDUDE", "ok")
baud = argv[argv.index("-b") + 1] if "-b" in argv else "0"

if mode == "hang":
    time.sleep(30)
    sys.exit(0)
if mode == "busy":
    sys.stdout.write("avrdude: ser_open(): cannot open port COM7: "
                     "Access is denied.\\n")
    sys.exit(1)
if mode == "wrongchip":
    sys.stdout.write("avrdude: Expected signature for ATmega328P is "
                     "1E 95 0F\\n")
    sys.exit(1)
if mode == "verifyfail":
    sys.stdout.write("avrdude: verification error, first mismatch at "
                     "byte 0x0100\\n")
    sys.exit(1)
if mode == "sync115200" and baud == "115200":
    sys.stdout.write("avrdude: stk500_getsync() attempt 1 of 10: not in "
                     "sync: resp=0x00\\n")
    sys.stdout.write("avrdude: programmer is not responding\\n")
    sys.exit(1)
if mode == "allsync":
    sys.stdout.write("avrdude: programmer is not responding\\n")
    sys.exit(1)

# Success. The carriage returns are what avrdude really emits for its
# progress bar, and the reader has to split on them.
sys.stdout.write("avrdude: writing flash (5522 bytes):\\n")
sys.stdout.write("#" * 20 + "\\r")
sys.stdout.write("#" * 50 + "\\r\\n")
sys.stdout.write("avrdude: 5522 bytes of flash written\\n")
sys.stdout.write("avrdude: reading on-chip flash data:\\n")
sys.stdout.write("avrdude: 5522 bytes of flash verified\\n")
sys.stdout.write("avrdude done.  Thank you.\\n")
sys.exit(0)
'''


@pytest.fixture
def fake_tool(tmp_path, monkeypatch):
    """An AvrdudeTool that runs a Python script instead of avrdude."""
    script = tmp_path / "fake_avrdude.py"
    script.write_text(FAKE_AVRDUDE, encoding="utf-8")
    conf = tmp_path / "avrdude.conf"
    conf.write_text("# not a real avrdude.conf\n", encoding="utf-8")
    log = tmp_path / "argv.log"
    monkeypatch.setenv("FAKE_AVRDUDE", "ok")
    monkeypatch.setenv("FAKE_AVRDUDE_LOG", str(log))
    tool = flasher.AvrdudeTool(argv=[sys.executable, str(script)],
                               conf=conf, origin="bundled")
    tool.log_path = log          # type: ignore[attr-defined]
    return tool


def runs(tool) -> list[list[str]]:
    log = Path(tool.log_path)
    if not log.exists():
        return []
    return [json.loads(line) for line in
            log.read_text(encoding="utf-8").splitlines() if line.strip()]


class FakePort:
    """A serial port that answers the address tool's protocol.

    `script` maps a command to the line the tool would send back. The
    banner is delivered on the first read so wait_for_banner sees it.
    """

    def __init__(self, banner: str = "### ADDR TOOL 1 ###", script=None):
        self._pending = [banner + "\n"]
        self._script = dict(script or {})
        self.written: list[str] = []
        self.closed = False

    def read(self, _n=1):
        if self._pending:
            return self._pending.pop(0).encode("ascii")
        return b""

    def write(self, data):
        text = data.decode("ascii") if isinstance(data, bytes) else str(data)
        self.written.append(text.strip())
        reply = self._script.get(text.strip())
        if reply:
            self._pending.append(reply + "\n")
        return len(data)

    def close(self):
        self.closed = True


@pytest.fixture
def cfg(tmp_path):
    from finger_rehab.config import Config
    c = Config.load()
    c.data.setdefault("ui", {})["resolution"] = [1280, 800]
    c.data.setdefault("audio", {})["enabled"] = False
    c.data["session"]["data_dir"] = str(tmp_path)
    c.data["report"] = {"enabled": False}
    return c


@pytest.fixture
def game_hex(tmp_path):
    """A tiny but structurally real Intel HEX file."""
    p = tmp_path / "finger_rehab_nano.hex"
    p.write_text(":100000000C9434000C943E000C943E000C943E0082\n"
                 ":00000001FF\n", encoding="ascii")
    return flasher.FirmwareImage(kind="game", path=p,
                                 sha256=flasher._sha256_file(p),
                                 size=p.stat().st_size,
                                 built_utc="2026-09-04T00:00:00Z",
                                 git_sha="abc1234")


# ---------------------------------------------------------------------
# The command line
# ---------------------------------------------------------------------

class TestCommandLine:

    def test_it_is_platformios_own_line(self, fake_tool, tmp_path):
        hex_path = tmp_path / "firmware.hex"
        argv = flasher.avrdude_argv(fake_tool, "/dev/cu.usbserial-130",
                                    hex_path, 115200)
        assert argv[:2] == fake_tool.argv
        assert argv[2:] == [
            "-C", str(fake_tool.conf),
            "-p", "atmega328p", "-c", "arduino",
            "-P", "/dev/cu.usbserial-130", "-b", "115200", "-D",
            "-U", f"flash:w:{hex_path}:i",
        ]

    def test_no_conf_means_no_dash_c(self, tmp_path):
        """A wrong -C is worse than none: avrdude has its own search."""
        tool = flasher.AvrdudeTool(argv=["avrdude"], conf=None)
        argv = flasher.avrdude_argv(tool, "COM7", tmp_path / "f.hex", 57600)
        assert "-C" not in argv


class TestClassify:

    @pytest.mark.parametrize("text,rc,expect", [
        ("avrdude: 5522 bytes of flash verified", 0, "ok"),
        ("nothing useful here", 0, "unknown"),
        ("stk500_getsync() attempt 1 of 10: not in sync", 1, "sync_failed"),
        ("avrdude: programmer is not responding", 1, "sync_failed"),
        ("cannot open port COM7: Access is denied", 1, "port_busy"),
        ("could not open port /dev/x: Permission denied", 1,
         "port_busy"),
        # A board that is simply not there is a different message:
        # "close the Arduino IDE" would send the therapist hunting
        # for a program that was never running.
        ("cannot open port /dev/cu.x: No such file or directory", 1,
         "port_missing"),
        ("Expected signature for ATmega328P is 1E 95 0F", 1, "wrong_chip"),
        ("verification error, first mismatch at byte 0x0100", 1,
         "verify_failed"),
        ("something nobody has seen before", 1, "unknown"),
        ("", None, "timeout"),
    ])
    def test_table(self, text, rc, expect):
        assert flasher.classify(text, rc) == expect

    def test_a_zero_exit_without_a_verify_line_is_not_success(self):
        """avrdude prints its thank-you line even when it failed, so the
        exit code alone is not enough to believe a write happened."""
        assert flasher.classify("avrdude done.  Thank you.", 0) == "unknown"


# ---------------------------------------------------------------------
# Running it
# ---------------------------------------------------------------------

class TestRunAvrdude:

    def test_a_good_run(self, fake_tool, game_hex):
        res = flasher.run_avrdude(fake_tool, "COM7", game_hex.path, 115200)
        assert res.kind == "ok"
        assert res.returncode == 0
        assert "verified" in res.output

    def test_progress_splits_on_carriage_returns(self, fake_tool, game_hex):
        """avrdude redraws its bar with \\r. A reader that only splits on
        \\n shows nothing at all until the flash is over."""
        lines: list[str] = []
        flasher.run_avrdude(fake_tool, "COM7", game_hex.path, 115200,
                            on_line=lines.append)
        assert len(lines) >= 4
        assert any(line.startswith("#") for line in lines)

    def test_a_hang_is_killed(self, fake_tool, game_hex, monkeypatch):
        monkeypatch.setenv("FAKE_AVRDUDE", "hang")
        started = time.perf_counter()
        res = flasher.run_avrdude(fake_tool, "COM7", game_hex.path, 115200,
                                  timeout_s=1.0)
        assert res.kind == "timeout"
        assert res.returncode is None
        assert time.perf_counter() - started < 10

    def test_a_missing_binary_is_not_a_crash(self, tmp_path, game_hex):
        tool = flasher.AvrdudeTool(
            argv=[str(tmp_path / "nope" / "avrdude")], conf=None)
        res = flasher.run_avrdude(tool, "COM7", game_hex.path, 115200)
        assert res.kind == "tool_missing"

    def test_bad_cpu_type_names_rosetta(self, tmp_path, game_hex,
                                        monkeypatch):
        """An x86_64 avrdude on an Apple silicon Mac with no Rosetta
        raises errno 86, and the message has to say what to do."""
        def boom(*a, **k):
            raise OSError(86, "Bad CPU type in executable")

        tool = flasher.AvrdudeTool(argv=["/x/avrdude"], conf=None)
        res = flasher.run_avrdude(tool, "COM7", game_hex.path, 115200,
                                  popen=boom)
        assert res.kind == "no_rosetta"
        assert "rosetta" in flasher._MESSAGES["no_rosetta"].lower()


# ---------------------------------------------------------------------
# The whole flash
# ---------------------------------------------------------------------

class TestFlashImage:

    def test_success_reports_the_baud_and_waits_for_the_banner(
            self, fake_tool, game_hex, cfg):
        port = FakePort(banner="### Setup Complete ###")
        res = flasher.flash_image(fake_tool, "COM7", game_hex, cfg,
                                  banner="### Setup Complete ###",
                                  open_port=lambda *a, **k: port)
        assert res.ok
        assert res.baud == 115200
        assert res.banner_seen
        assert "115200" in res.message
        assert len(runs(fake_tool)) == 1

    def test_an_old_bootloader_board_flashes_on_the_second_try(
            self, fake_tool, game_hex, cfg, monkeypatch):
        monkeypatch.setenv("FAKE_AVRDUDE", "sync115200")
        port = FakePort(banner="### Setup Complete ###")
        res = flasher.flash_image(fake_tool, "COM7", game_hex, cfg,
                                  banner="### Setup Complete ###",
                                  open_port=lambda *a, **k: port)
        assert res.ok
        assert res.baud == 57600
        attempts = runs(fake_tool)
        assert [a[a.index("-b") + 1] for a in attempts] == ["115200", "57600"]

    def test_a_busy_port_is_not_retried(self, fake_tool, game_hex, cfg,
                                        monkeypatch):
        """Only a sync failure is worth the other baud. A port somebody
        else has open fails identically twice."""
        monkeypatch.setenv("FAKE_AVRDUDE", "busy")
        res = flasher.flash_image(fake_tool, "COM7", game_hex, cfg,
                                  open_port=lambda *a, **k: FakePort())
        assert not res.ok
        assert res.kind == "port_busy"
        assert len(runs(fake_tool)) == 1
        assert "another program has it" in res.message

    def test_a_wrong_chip_says_nothing_was_written(
            self, fake_tool, game_hex, cfg, monkeypatch):
        monkeypatch.setenv("FAKE_AVRDUDE", "wrongchip")
        res = flasher.flash_image(fake_tool, "COM7", game_hex, cfg,
                                  open_port=lambda *a, **k: FakePort())
        assert res.kind == "wrong_chip"
        assert "Nothing was written" in res.message
        assert len(runs(fake_tool)) == 1

    def test_a_verify_failure_says_flash_again(self, fake_tool, game_hex,
                                               cfg, monkeypatch):
        monkeypatch.setenv("FAKE_AVRDUDE", "verifyfail")
        res = flasher.flash_image(fake_tool, "COM7", game_hex, cfg,
                                  open_port=lambda *a, **k: FakePort())
        assert res.kind == "verify_failed"
        assert "Flash again" in res.message

    def test_both_bauds_failing_says_check_the_cable(
            self, fake_tool, game_hex, cfg, monkeypatch):
        monkeypatch.setenv("FAKE_AVRDUDE", "allsync")
        res = flasher.flash_image(fake_tool, "COM7", game_hex, cfg,
                                  open_port=lambda *a, **k: FakePort())
        assert res.kind == "sync_failed"
        assert len(runs(fake_tool)) == 2
        assert "115200 or 57600" in res.message

    def test_a_silent_board_after_a_good_write_is_reported(
            self, fake_tool, game_hex, cfg):
        """Verified but no banner is a real state: the write worked and
        the board did not come back. Saying "flashed" alone would send
        the therapist off to play with a device that is not running."""
        res = flasher.flash_image(fake_tool, "COM7", game_hex, cfg,
                                  banner="### Setup Complete ###",
                                  open_port=lambda *a, **k: FakePort(
                                      banner="nothing like the banner"))
        assert res.ok
        assert not res.banner_seen
        assert "did not print its start-up banner" in res.message

    def test_the_remembered_baud_is_tried_first(self, cfg):
        cfg.data.setdefault("firmware", {})["preferred_baud"] = 57600
        assert flasher.baud_order_for(cfg) == [57600, 115200]
        cfg.data["firmware"]["preferred_baud"] = None
        assert flasher.baud_order_for(cfg) == [115200, 57600]


# ---------------------------------------------------------------------
# Finding the hex
# ---------------------------------------------------------------------

class TestFindHex:

    def _stage(self, tmp_path, body: str, sha: str | None = None):
        folder = tmp_path / "firmware"
        folder.mkdir()
        hex_path = folder / "finger_rehab_nano.hex"
        hex_path.write_text(body, encoding="ascii")
        digest = sha if sha is not None else flasher._sha256_file(hex_path)
        (folder / "manifest.json").write_text(json.dumps({
            "built_utc": "2026-09-04T01:02:03Z",
            "git_sha": "deadbee",
            "images": {"finger_rehab_nano.hex": {"sha256": digest}},
        }), encoding="utf-8")
        return hex_path

    def test_a_good_hex_carries_its_build_stamp(self, tmp_path, cfg):
        path = self._stage(tmp_path, ":00000001FF\n")
        cfg.data.setdefault("firmware", {})["game_hex"] = str(path)
        image = flasher.find_hex("game", cfg)
        assert image is not None
        assert image.git_sha == "deadbee"
        assert "deadbee" in image.label()

    def test_a_damaged_hex_is_refused(self, tmp_path, cfg):
        """A torn download handed to avrdude leaves a board with no
        usable firmware, which is worse than refusing to start."""
        path = self._stage(tmp_path, ":00000001FF\n", sha="0" * 64)
        cfg.data.setdefault("firmware", {})["game_hex"] = str(path)
        assert flasher.find_hex("game", cfg) is None

    def test_nothing_staged_falls_back_to_the_local_platformio_build(
            self, tmp_path, cfg, monkeypatch):
        """A source checkout should be able to flash what the developer
        just compiled, but the caption has to admit it is not the CI
        hex, so a lab machine is never left guessing what is on a
        board."""
        cfg.data.setdefault("firmware", {})["game_hex"] = str(
            tmp_path / "nowhere.hex")
        dev = tmp_path / "pio.hex"
        dev.write_text(":00000001FF\n", encoding="ascii")
        monkeypatch.setattr(flasher, "_dev_hex_path", lambda kind: dev)
        image = flasher.find_hex("game", cfg)
        assert image is not None
        assert image.dev_build
        assert "dev build" in image.label()

    def test_nothing_anywhere_is_none_not_a_crash(self, tmp_path, cfg,
                                                  monkeypatch):
        cfg.data.setdefault("firmware", {})["game_hex"] = str(
            tmp_path / "nowhere.hex")
        monkeypatch.setattr(flasher, "_dev_hex_path",
                            lambda kind: tmp_path / "also-nowhere.hex")
        assert flasher.find_hex("game", cfg) is None

    def test_flash_bytes_counts_only_data_records(self, tmp_path):
        p = tmp_path / "x.hex"
        p.write_text(":10000000" + "00" * 16 + "01\n"
                     ":00000001FF\n", encoding="ascii")
        assert flasher.flash_bytes(p) == 16


class TestFindAvrdude:

    def test_the_config_path_wins(self, cfg, tmp_path):
        fake = tmp_path / "myavrdude"
        fake.write_text("#!/bin/sh\n", encoding="utf-8")
        fake.chmod(0o755)
        cfg.data.setdefault("firmware", {})["avrdude"] = str(fake)
        tool = flasher.find_avrdude(cfg)
        assert tool is not None
        assert tool.origin == "config"
        assert tool.argv == [str(fake.resolve())]

    def test_the_conf_beside_the_binary_is_used(self, cfg, tmp_path):
        fake = tmp_path / "avrdude"
        fake.write_text("", encoding="utf-8")
        conf = tmp_path / "avrdude.conf"
        conf.write_text("", encoding="utf-8")
        cfg.data.setdefault("firmware", {})["avrdude"] = str(fake)
        tool = flasher.find_avrdude(cfg)
        assert tool is not None and tool.conf == conf

    def test_the_env_override_beats_the_bundle(self, cfg, tmp_path,
                                               monkeypatch):
        fake = tmp_path / "envavrdude"
        fake.write_text("", encoding="utf-8")
        cfg.data.setdefault("firmware", {})["avrdude"] = "auto"
        monkeypatch.setenv("FINGER_REHAB_AVRDUDE", str(fake))
        tool = flasher.find_avrdude(cfg)
        assert tool is not None and tool.origin == "env"


# ---------------------------------------------------------------------
# The address job
# ---------------------------------------------------------------------

def _addr_images(tmp_path):
    tool_hex = tmp_path / "singletact_address_change.hex"
    tool_hex.write_text(":00000001FF\n", encoding="ascii")
    game = tmp_path / "finger_rehab_nano.hex"
    game.write_text(":00000001FF\n", encoding="ascii")
    return (
        flasher.FirmwareImage("addr_tool", tool_hex,
                              flasher._sha256_file(tool_hex),
                              tool_hex.stat().st_size),
        flasher.FirmwareImage("game", game, flasher._sha256_file(game),
                              game.stat().st_size),
    )


def _run_address_job(fake_tool, cfg, tmp_path, script, **kw):
    """Drive an AddressJob with a scripted port and wait for it."""
    addr_img, game_img = _addr_images(tmp_path)
    ports = [FakePort(banner="### ADDR TOOL 1 ###", script=script),
             FakePort(banner="### Setup Complete ###")]

    def opener(*a, **k):
        return ports.pop(0) if ports else FakePort(banner="nothing")

    job = flasher.AddressJob(fake_tool, "COM7", addr_img, game_img, cfg,
                             open_port=opener, reply_timeout_s=1.0, **kw)
    job.run()
    return job


class TestAddressJob:

    def test_a_scan_lists_the_bus_and_puts_the_game_firmware_back(
            self, fake_tool, cfg, tmp_path):
        job = _run_address_job(
            fake_tool, cfg, tmp_path,
            {"SCAN": "FOUND: 0x04,0x05,0x06,0x07,0x08"})
        assert job.found_before == [0x04, 0x05, 0x06, 0x07, 0x08]
        # Two flashes: the tool, then the game firmware back.
        assert len(runs(fake_tool)) == 2

    def test_changing_from_0x04_is_refused_when_others_answer(
            self, fake_tool, cfg, tmp_path):
        """The one rule that decides the whole feature. Every SingleTact
        answers 0x04 as well as its own address, so this write would
        move all four sensors onto one address at once."""
        job = _run_address_job(
            fake_tool, cfg, tmp_path,
            {"SCAN": "FOUND: 0x04,0x05,0x06,0x07"},
            change=True, old=0x04, new=0x08)
        assert job.refused
        assert not job.ok
        assert "0x05, 0x06, 0x07" in job.summary
        assert "Unplug every other sensor" in job.summary
        # No CHANGE was ever sent, and the board is left playable.
        assert len(runs(fake_tool)) == 2

    def test_a_lone_sensor_on_0x04_is_allowed(self, fake_tool, cfg,
                                              tmp_path):
        job = _run_address_job(
            fake_tool, cfg, tmp_path,
            {"SCAN": "FOUND: 0x04", "CHANGE:0x04,0x07": "OK: 0x04 -> 0x07"},
            change=True, old=0x04, new=0x07)
        assert job.ok, job.summary
        assert "0x04 to 0x07" in job.summary
        assert "Game firmware restored" in job.summary

    def test_a_change_between_real_addresses_is_allowed(
            self, fake_tool, cfg, tmp_path):
        """0x06 to 0x08 only reaches the one sensor, so it is safe with
        the whole device still wired up."""
        job = _run_address_job(
            fake_tool, cfg, tmp_path,
            {"SCAN": "FOUND: 0x04,0x05,0x06,0x07,0x08",
             "CHANGE:0x06,0x09": "OK: 0x06 -> 0x09"},
            change=True, old=0x06, new=0x09)
        assert job.ok, job.summary

    def test_a_sensor_that_refuses_the_write_is_explained(
            self, fake_tool, cfg, tmp_path):
        job = _run_address_job(
            fake_tool, cfg, tmp_path,
            {"SCAN": "FOUND: 0x04",
             "CHANGE:0x04,0x07": "ERR: nothing answers at 0x07 after the "
                                 "write"},
            change=True, old=0x04, new=0x07)
        assert not job.ok
        assert "did not take the new address" in job.summary
        assert "calibrated unit" in job.summary

    def test_a_failed_restore_says_the_board_is_not_playable(
            self, fake_tool, cfg, tmp_path, monkeypatch):
        """The worst outcome of the whole feature: the address tool is
        on the board and the game firmware is not. It has to say so."""
        addr_img, game_img = _addr_images(tmp_path)
        state = {"n": 0}
        real_popen = subprocess.Popen

        def popen(argv, **kw):
            state["n"] += 1
            # First flash (the tool) succeeds, the restore does not.
            os.environ["FAKE_AVRDUDE"] = "ok" if state["n"] == 1 else "allsync"
            return real_popen(argv, **kw)

        ports = [FakePort(banner="### ADDR TOOL 1 ###",
                          script={"SCAN": "FOUND: 0x04"})]
        job = flasher.AddressJob(
            fake_tool, "COM7", addr_img, game_img, cfg,
            popen=popen, open_port=lambda *a, **k: (
                ports.pop(0) if ports else FakePort(banner="x")),
            reply_timeout_s=1.0)
        job.run()
        assert not job.ok
        assert "GAME firmware is NOT on the board" in job.summary

    def test_a_silent_tool_does_not_leave_the_board_broken(
            self, fake_tool, cfg, tmp_path):
        job = _run_address_job(fake_tool, cfg, tmp_path, {})
        assert not job.ok
        assert "did not answer" in job.summary
        # Restored anyway: two flashes.
        assert len(runs(fake_tool)) == 2

    def test_found_lists_parse_hex_tokens(self):
        parse = flasher.AddressJob._parse_found
        assert parse("FOUND: 0x04,0x05") == [4, 5]
        assert parse("FOUND: none") == []
        assert parse("FOUND: ") == []


# ---------------------------------------------------------------------
# Through the real engine and the real Settings screen
# ---------------------------------------------------------------------

@pytest.fixture
def settings(cfg):
    import pygame
    pygame.init()
    pygame.font.init()
    from finger_rehab.game.engine import GameEngine
    from finger_rehab.hardware.keyboard_source import KeyboardOnlySource
    from finger_rehab.ui.screens import DiagnosticsScreen
    eng = GameEngine(cfg, KeyboardOnlySource())
    screen = DiagnosticsScreen(eng)
    eng._screens["diagnostics"] = screen
    eng.screen_obj = screen
    yield screen, eng
    pygame.quit()


class TestSettingsWiring:

    def test_the_two_buttons_exist_and_are_in_the_firmware_panel(
            self, settings):
        screen, _ = settings
        labels = [b.label for b in screen._panel_buttons]
        assert "Flash firmware" in labels
        assert "Sensor address" in labels
        panel = screen._firmware_rect()
        for b in screen._panel_buttons:
            if b.label in ("Flash firmware", "Sensor address"):
                assert panel.contains(b.rect), b.label

    def test_a_running_block_refuses_without_opening_a_dialog(
            self, settings):
        """Swapping the firmware mid-block would leave a half recorded
        trial pointing at a source that no longer exists."""
        screen, eng = settings
        eng.in_block = True
        screen._open_flash_dialog()
        assert screen._dialog is None
        assert "Not while a block is running" in screen._port_status

    def test_no_board_says_what_to_do_about_the_driver(self, settings,
                                                       monkeypatch):
        screen, _ = settings
        monkeypatch.setattr(flasher, "candidate_ports",
                            lambda cfg, source=None: [])
        monkeypatch.setattr(flasher, "find_avrdude",
                            lambda cfg: flasher.AvrdudeTool(argv=["x"]))
        monkeypatch.setattr(
            flasher, "find_hex",
            lambda kind, cfg: flasher.FirmwareImage(
                kind, Path("x.hex"), "0" * 64, 1))
        screen._open_flash_dialog()
        assert screen._dialog is None
        assert "CH341SER" in screen._port_status

    def test_a_missing_avrdude_says_so(self, settings, monkeypatch):
        screen, _ = settings
        monkeypatch.setattr(flasher, "find_avrdude", lambda cfg: None)
        screen._open_flash_dialog()
        assert screen._dialog is None
        assert "avrdude is not in this build" in screen._port_status

    def test_the_port_is_released_then_taken_back_in_that_order(
            self, settings, fake_tool, game_hex, monkeypatch):
        """avrdude cannot have the port while the app's reader holds it,
        and the app cannot read once avrdude has been and gone unless
        the source is rebuilt."""
        screen, eng = settings
        order: list[str] = []
        monkeypatch.setattr(eng, "begin_firmware_job",
                            lambda: order.append("begin"))
        monkeypatch.setattr(eng, "end_firmware_job",
                            lambda: (order.append("end"), "Connected.")[1])
        monkeypatch.setattr(flasher, "find_avrdude", lambda cfg: fake_tool)
        monkeypatch.setattr(flasher, "find_hex",
                            lambda kind, cfg: game_hex)
        monkeypatch.setattr(flasher, "candidate_ports",
                            lambda cfg, source=None: [("COM7", "RIGHT hand, COM7")])
        monkeypatch.setattr(
            flasher, "wait_for_banner",
            lambda *a, **k: (True, FakePort(banner="### Setup Complete ###")))
        screen._open_flash_dialog()
        assert screen._dialog is not None
        screen._dialog._start_flash()
        assert order == ["begin"]
        screen._dialog.job.join(timeout=30)
        screen.update(0.016)
        assert order == ["begin", "end"]
        assert screen._dialog.finished
        assert "Connected." in screen._dialog.result_text

    def test_escape_is_swallowed_while_a_job_runs(self, settings):
        """Esc mid flash must not walk out of Settings: avrdude is
        writing and there is nothing safe to cancel."""
        from finger_rehab.ui.firmware_dialog import FirmwareDialog
        screen, eng = settings
        dlg = FirmwareDialog("flash", screen.theme, screen.layout,
                             ports=[("COM7", "COM7")], firmware_label="x")
        screen._dialog = dlg
        dlg.busy = True
        assert screen.on_escape() is True
        assert screen._dialog is dlg
        dlg.busy = False
        assert screen.on_escape() is True
        assert dlg.wants_close

    def test_escape_with_no_dialog_leaves_settings_alone(self, settings):
        screen, _ = settings
        assert screen.on_escape() is False

    def test_the_engine_routes_escape_through_the_screen(self, settings):
        from finger_rehab.ui.firmware_dialog import FirmwareDialog
        screen, eng = settings
        dlg = FirmwareDialog("flash", screen.theme, screen.layout,
                             ports=[("COM7", "COM7")], firmware_label="x")
        dlg.busy = True
        screen._dialog = dlg
        eng._handle_escape()
        # Still on Settings, dialog untouched.
        assert eng.screen_obj is screen
        assert screen._dialog is dlg


class TestFirmwareDialog:

    def _dialog(self, settings, mode="address", ports=None):
        from finger_rehab.ui.firmware_dialog import FirmwareDialog
        screen, _ = settings
        return FirmwareDialog(mode, screen.theme, screen.layout,
                              ports=ports or [("COM7", "RIGHT hand, COM7")],
                              firmware_label="hex abc1234, 2026-09-04")

    @pytest.mark.parametrize("mode", ["flash", "address"])
    @pytest.mark.parametrize("ports", [
        [("COM7", "RIGHT hand, COM7")],
        # Two boards means a board picker sits ahead of the buttons.
        # Focus still has to skip past it onto Cancel.
        [("COM7", "RIGHT hand, COM7"), ("COM8", "LEFT hand, COM8")],
    ])
    def test_cancel_owns_the_focus_when_it_opens(self, settings, mode,
                                                 ports):
        """A reflex Enter on a freshly opened dialog must back out, not
        write to a board."""
        dlg = self._dialog(settings, mode, ports)
        focused = dlg._focusables()[dlg.focus]
        assert getattr(focused, "label", None) == "Cancel"

    def test_tab_and_enter_reach_flash(self, settings):
        import pygame
        dlg = self._dialog(settings, "flash")
        fired: list[str] = []
        dlg._on_flash = lambda port: fired.append(port) or None
        dlg.handle_event(pygame.event.Event(pygame.KEYDOWN,
                                            key=pygame.K_TAB, mod=0))
        dlg.handle_event(pygame.event.Event(pygame.KEYDOWN,
                                            key=pygame.K_RETURN, mod=0))
        assert fired == ["COM7"]

    def test_addresses_parse_in_every_form_a_person_types(self, settings):
        dlg = self._dialog(settings)
        assert dlg.parse_address("0x05") == 5
        assert dlg.parse_address("05") == 5
        assert dlg.parse_address("5") == 5
        assert dlg.parse_address(" 0X0A ") == 10
        assert dlg.parse_address("") is None
        assert dlg.parse_address("hello") is None
        assert dlg.parse_address("0x03") is None      # below the minimum
        assert dlg.parse_address("0x80") is None      # above the maximum

    def test_a_junk_address_never_starts_a_job(self, settings):
        dlg = self._dialog(settings)
        started: list = []
        dlg._on_address = lambda *a: started.append(a) or None
        dlg.old_input.text = "zzz"
        dlg._start_change()
        assert started == []
        assert "0x04 and 0x7F" in dlg.result_text

    def test_the_same_address_twice_never_starts_a_job(self, settings):
        dlg = self._dialog(settings)
        started: list = []
        dlg._on_address = lambda *a: started.append(a) or None
        dlg.old_input.text = "0x05"
        dlg._pick_new(0x05)
        dlg._start_change()
        assert started == []
        assert "the same" in dlg.result_text

    def test_the_warning_about_0x04_is_on_the_card(self, settings,
                                                  monkeypatch):
        import pygame
        import finger_rehab.ui.firmware_dialog as mod
        dlg = self._dialog(settings)
        seen: list[str] = []
        original = mod.draw_text
        monkeypatch.setattr(mod, "draw_text",
                            lambda s, t, *a, **k: (seen.append(str(t)),
                                                   original(s, t, *a, **k))[1])
        dlg.draw(pygame.Surface((1280, 800)))
        text = " ".join(seen)
        assert "Every SingleTact also answers 0x04" in text
        assert "ONE sensor only" in text


# ---------------------------------------------------------------------
# The build products
# ---------------------------------------------------------------------

class TestFirmwareAssets:

    def test_the_sketch_project_has_both_bootloader_envs(self):
        ini = (REPO_ROOT / "arduino" / "singletact_address_change"
               / "platformio.ini").read_text(encoding="utf-8")
        assert "[env:nanoatmega328new]" in ini
        assert "[env:nanoatmega328]" in ini
        # An upload_port pinned in the file would fight the app, which
        # picks the port itself. Comments about it are fine; a setting
        # is not.
        settings = [ln.split("=")[0].strip() for ln in ini.splitlines()
                    if "=" in ln and not ln.lstrip().startswith(";")]
        assert "upload_port" not in settings
        assert "extra_scripts" not in settings

    def test_the_read_only_game_firmware_project_is_untouched(self):
        """arduino/firmware_on_device is off limits. The address tool is
        a sibling folder precisely so that stays true."""
        src = (REPO_ROOT / "arduino" / "firmware_on_device" / "src"
               / "main.cpp").read_text(encoding="utf-8", errors="replace")
        assert "CHANGE:" not in src
        assert "ADDR TOOL" not in src

    def test_the_sketch_sends_the_manuals_write_packet(self):
        """Table 3 of the SingleTact manual: 0x02 write, offset 0 (the
        address register), one byte, the new address, 0xFF terminator."""
        src = (REPO_ROOT / "arduino" / "singletact_address_change" / "src"
               / "main.cpp").read_text(encoding="utf-8")
        assert "{0x02, 0x00, 0x01, (uint8_t)newA, 0xFF}" in src

    @pytest.mark.skipif(
        not (REPO_ROOT / "assets" / "firmware" / "manifest.json").exists(),
        reason="no hexes staged in this checkout")
    def test_every_staged_hex_matches_its_manifest_entry(self):
        folder = REPO_ROOT / "assets" / "firmware"
        manifest = json.loads(
            (folder / "manifest.json").read_text(encoding="utf-8"))
        assert manifest["images"]
        for name, entry in manifest["images"].items():
            path = folder / name
            assert path.exists(), name
            assert flasher._sha256_file(path) == entry["sha256"], name
            assert entry["flash_bytes"] == flasher.flash_bytes(path), name
            assert 0 < entry["flash_bytes"] < flasher.MAX_FLASH_BYTES, name
            text = path.read_text(encoding="ascii", errors="replace")
            assert text.strip().endswith(":00000001FF"), name
