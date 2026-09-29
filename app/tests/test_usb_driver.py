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
    assert boards == [{"name": "USB2.0-Serial", "chip": "CH340",
                       "instance_id": "USB\\VID_1A86&PID_7523\\5&2C3F1A&0&2",
                       "has_driver": False}]
    line, missing = U.describe(boards)
    assert missing and "no driver" in line


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


def test_the_install_can_flash_with_nothing_else_installed(tmp_path):
    """The same check CI runs on each build's installed copy."""
    report = tmp_path / "tools.json"
    res = subprocess.run([sys.executable, str(ROOT / "main.py"),
                          "--check-tools", str(report)],
                         capture_output=True, text=True, timeout=120,
                         cwd=str(ROOT))
    data = json.loads(report.read_text(encoding="utf-8"))
    assert set(data) >= {"game", "addr_tool", "avrdude", "pyserial",
                         "usb_driver", "problems", "ready"}
    assert data["ready"] == (res.returncode == 0)
    if data["ready"]:
        assert data["avrdude"]["runs"]
        assert data["game"]["flash_bytes"] > 0
