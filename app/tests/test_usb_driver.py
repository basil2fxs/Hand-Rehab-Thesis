"""Flash firmware and Sensor address on a new PC (Basil, 29 September
2026): the install's own tools check, and the board's USB driver on
Windows found and fixed from inside the app. Nothing here needs
Windows or a board: PowerShell's answers are fed in as text.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from finger_rehab.hardware import usb_driver as U  # noqa: E402

NO_DRIVER = json.dumps({
    "Status": "Error", "Class": None, "FriendlyName": "USB2.0-Serial",
    "InstanceId": "USB\\VID_1A86&PID_7523\\5&2C3F1A&0&2", "Problem": 28})
WORKING = json.dumps([{
    "Status": "OK", "Class": "Ports",
    "FriendlyName": "USB-SERIAL CH340 (COM3)",
    "InstanceId": "USB\\VID_1A86&PID_7523\\5&2C3F1A&0&2", "Problem": 0}])


class _Res:
    def __init__(self, out=""):
        self.stdout = out
        self.stderr = ""


def test_a_board_with_no_driver_is_found_whatever_the_language():
    boards = U.parse_devices(NO_DRIVER)
    assert len(boards) == 1
    b = boards[0]
    assert (b["name"], b["chip"], b["problem"], b["has_driver"],
            b["working"]) == ("USB2.0-Serial", "CH340", 28, False, False)
    line, missing = U.describe(boards)
    assert missing and "no driver" in line
    # Some systems name the problem instead of numbering it.
    named = NO_DRIVER.replace('"Problem": 28',
                              '"Problem": "CM_PROB_FAILED_INSTALL"')
    assert U.parse_devices(named)[0]["has_driver"] is False


def test_an_ftdi_or_composite_board_with_its_driver_is_working():
    # An FTDI Nano lists a USB Serial Converter (class USB) beside its
    # COM port; a Leonardo a composite and an HID entry. None of them
    # is a missing driver.
    ftdi = json.dumps([
        {"Status": "OK", "Class": "USB", "FriendlyName":
         "USB Serial Converter", "InstanceId":
         "FTDIBUS\\VID_0403+PID_6001+A10K1234A\\0000", "Problem": 0},
        {"Status": "OK", "Class": "Ports", "FriendlyName":
         "USB Serial Port (COM4)", "InstanceId":
         "FTDIBUS\\VID_0403+PID_6001+A10K1234A\\0000", "Problem": 0}])
    line, missing = U.describe(U.parse_devices(ftdi))
    assert not missing and line == "Driver working: USB Serial Port (COM4)."
    leo = json.dumps([
        {"Status": "OK", "Class": "USB", "FriendlyName":
         "USB Composite Device", "InstanceId":
         "USB\\VID_2341&PID_8036\\7", "Problem": 0},
        {"Status": "OK", "Class": "HIDClass", "FriendlyName":
         "USB Input Device", "InstanceId":
         "USB\\VID_2341&PID_8036&MI_02\\8", "Problem": 0},
        {"Status": "OK", "Class": "Ports", "FriendlyName":
         "Arduino Leonardo (COM5)", "InstanceId":
         "USB\\VID_2341&PID_8036&MI_00\\9", "Problem": 0}])
    line, missing = U.describe(U.parse_devices(leo))
    assert not missing and "Arduino Leonardo (COM5)" in line


def test_a_fault_that_is_not_a_missing_driver_is_not_offered_the_fix():
    # Code 10, the device cannot start: a driver download will not fix
    # it, so the Setup tab says so and does not offer Get the driver.
    faulty = json.dumps({"Status": "Error", "Class": "Ports",
                         "FriendlyName": "USB-SERIAL CH340 (COM3)",
                         "InstanceId": "USB\\VID_1A86&PID_7523\\1",
                         "Problem": 10})
    line, missing = U.describe(U.parse_devices(faulty))
    assert not missing and "code 10" in line and "plug it back in" in line


def test_a_working_board_and_no_board():
    line, missing = U.describe(U.parse_devices(WORKING))
    assert not missing and "COM3" in line
    line, missing = U.describe(U.parse_devices("[]"))
    assert not missing and "No hand device" in line
    assert U.parse_devices("not json") == []


def test_the_query_asks_only_for_the_board_chips():
    seen = []

    def runner(argv, **kw):
        seen.append(argv)
        return _Res(NO_DRIVER)

    boards = U.find_boards(runner=runner)
    assert boards[0]["chip"] == "CH340"
    script = seen[0][-1]
    assert "Get-PnpDevice" in script and "ConvertTo-Json" in script
    assert "1A86" in script and "0403" in script


def test_the_fix_runs_elevated_and_reads_its_answer(tmp_path, monkeypatch):
    monkeypatch.setattr(U.tempfile, "mkdtemp",
                        lambda prefix="": str(tmp_path))
    seen = []

    def runner(argv, **kw):
        seen.append(argv[-1])
        (tmp_path / "result.json").write_text(json.dumps(
            {"ok": True, "message": "Installed: wch.cn - Ports"}),
            encoding="utf-8")
        return _Res()

    got = U.install_from_windows_update(runner=runner)
    assert got == {"ok": True, "message": "Installed: wch.cn - Ports"}
    assert "-Verb RunAs" in seen[0]
    script = (tmp_path / "get_driver.ps1").read_text(encoding="utf-8")
    assert "Microsoft.Update.Session" in script
    assert "Type='Driver'" in script
    assert "VID_(1A86|0403|2341|2A03)" in script


def test_a_turned_down_prompt_says_so(tmp_path, monkeypatch):
    monkeypatch.setattr(U.tempfile, "mkdtemp",
                        lambda prefix="": str(tmp_path))
    got = U.install_from_windows_update(runner=lambda *a, **k: _Res())
    assert not got["ok"] and "prompt" in got["message"]


def test_the_tools_check_reports_the_board_on_every_system(monkeypatch):
    # Windows asks Plug and Play and flags a missing driver. A Mac or
    # Linux has the drivers built in, so it names the board's port: it
    # used to say "No hand device plugged in" with a Nano attached.
    from finger_rehab.config import Config
    from finger_rehab.hardware import flasher
    cfg = Config.load()
    monkeypatch.setattr(U, "find_boards",
                        lambda runner=None: U.parse_devices(NO_DRIVER))
    monkeypatch.setattr(flasher, "candidate_ports", lambda cfg, source=None:
                        [("/dev/cu.usbserial-AI04VRMU", "usbserial-AI04VRMU")])
    monkeypatch.setattr(flasher, "_on_windows", lambda: True)
    report = flasher.self_check(cfg)
    assert "no driver" in report["usb_driver"]
    assert "board plugged in without a driver" in report["problems"]
    monkeypatch.setattr(flasher, "_on_windows", lambda: False)
    report = flasher.self_check(cfg)
    assert report["usb_driver"] == ("Board port: usbserial-AI04VRMU. No "
                                    "driver needed on this system.")
    assert "board plugged in without a driver" not in report["problems"]


def test_the_tools_check_passes_wherever_the_tools_are(tmp_path):
    """The same check CI runs on the installed Windows copy and the
    built macOS app. Here it must say ready whenever this checkout holds
    avrdude for this OS and both firmware files (a developer Mac or
    Windows PC); CI's test job has neither, so there it checks the
    report and the exit code agree."""
    report = tmp_path / "tools.json"
    res = subprocess.run([sys.executable, str(ROOT / "main.py"),
                          "--check-tools", str(report)],
                         capture_output=True, text=True, timeout=120,
                         cwd=str(ROOT))
    data = json.loads(report.read_text(encoding="utf-8"))
    assert set(data) >= {"game", "addr_tool", "avrdude", "pyserial",
                         "usb_driver", "problems", "ready"}
    assert data["ready"] == (res.returncode == 0)
    plat = {"darwin": "darwin", "win32": "win32"}.get(sys.platform)
    fw = ROOT / "assets" / "firmware"
    have_tools = bool(
        plat and list((ROOT / "tools" / "avrdude" / plat).glob("avrdude*"))
        and (fw / "finger_rehab_nano.hex").is_file()
        and (fw / "singletact_address_change.hex").is_file())
    if have_tools:
        assert data["ready"], data["problems"]
    if data["ready"]:
        assert data["avrdude"]["runs"]
        assert data["game"]["flash_bytes"] > 0


def test_the_tools_check_needs_the_socket_port_handler(monkeypatch):
    """The EEG simulator takes the game's markers over
    socket://127.0.0.1:50410, and pyserial serves socket:// from a
    module it imports by name when the port opens. The Windows build of
    3 October 2026 left that module out ("protocol 'socket' not known",
    found on a Windows VM on 5 October). The check runs on every built
    app in CI, so a build without it fails there."""
    from finger_rehab.config import Config
    from finger_rehab.hardware import flasher
    cfg = Config.load()
    report = flasher.self_check(cfg)
    assert report["pyserial_socket"] is True
    assert "no socket:// port support" not in report["problems"]
    monkeypatch.setattr(flasher, "_socket_ports_supported", lambda: False)
    report = flasher.self_check(cfg)
    assert report["pyserial_socket"] is False
    assert "no socket:// port support" in report["problems"]
    assert report["ready"] is False


def test_the_build_bundles_pyserials_url_handlers():
    spec = (ROOT / "finger_rehab.spec").read_text(encoding="utf-8")
    assert 'collect_submodules("serial.urlhandler")' in spec
