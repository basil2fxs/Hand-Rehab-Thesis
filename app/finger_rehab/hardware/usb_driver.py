"""The hand device's USB driver on Windows.

The Nano clones the device uses talk USB through a WCH CH340 chip,
which needs a vendor driver on Windows (FTDI and genuine Arduino boards
need one too, and Windows ships the Arduino one). On a PC that is online
Windows fetches it from Windows Update the first time the board is
plugged in. On one that is offline, or where a policy stops that, the
board shows up in Device Manager with no COM port, the game falls back
to the keyboard and Flash firmware finds nothing to flash.

This module finds that case and fixes it from inside the app:

  find_boards()        every plugged-in board with a known USB chip, and
                       whether Windows has a working driver for it
                       (PowerShell's Get-PnpDevice, read as JSON so the
                       answer does not depend on the Windows language)
  install_from_windows_update()
                       asks Windows Update for that chip's driver and
                       installs it: the same search Device Manager's
                       "Search automatically for drivers" runs. Needs
                       administrator rights, so Windows asks once.
  open_optional_updates()
                       the fallback: Windows Update's optional driver
                       page, where the same driver can be ticked.

The driver comes from Microsoft's own catalogue, so the app never ships
or downloads a third-party installer. Everything here is a no-op off
Windows. Nothing here touches pygame or the config: the Settings screen
runs it on a thread and reads the result.
"""
from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import tempfile
from pathlib import Path

log = logging.getLogger(__name__)

# USB vendor IDs of the boards the device is built from.
KNOWN_VIDS = {"1A86": "CH340", "0403": "FTDI", "2341": "Arduino",
              "2A03": "Arduino"}

_FIND = (
    "$d = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | "
    "Where-Object { $_.InstanceId -match 'VID_(1A86|0403|2341|2A03)' } | "
    "Select-Object Status, Class, FriendlyName, InstanceId, Problem; "
    "if ($d) { $d | ConvertTo-Json -Compress } else { '[]' }"
)

# Windows Update, driver updates only, for the board chips' hardware
# IDs. Written as a file and run elevated; it writes what it did to the
# path passed as its first argument.
_WU_SCRIPT = r"""
param([string]$Out)
$ErrorActionPreference = 'Stop'
$result = @{ ok = $false; installed = @(); message = '' }
try {
  $session = New-Object -ComObject Microsoft.Update.Session
  $searcher = $session.CreateUpdateSearcher()
  # Windows Update itself (2), not a school's update server, which
  # rarely carries drivers.
  $searcher.ServerSelection = 2
  $found = $searcher.Search("IsInstalled=0 and Type='Driver'")
  $want = New-Object -ComObject Microsoft.Update.UpdateColl
  foreach ($u in $found.Updates) {
    if ($u.DriverHardwareID -match 'VID_(1A86|0403|2341|2A03)') {
      $null = $want.Add($u)
      $result.installed += $u.Title
    }
  }
  if ($want.Count -eq 0) {
    $result.message = 'Windows Update has no driver for the board.'
  } else {
    $dl = $session.CreateUpdateDownloader()
    $dl.Updates = $want
    $null = $dl.Download()
    $inst = $session.CreateUpdateInstaller()
    $inst.Updates = $want
    $r = $inst.Install()
    $result.ok = ($r.ResultCode -eq 2 -or $r.ResultCode -eq 3)
    $result.message = 'Installed: ' + ($result.installed -join ', ')
  }
} catch {
  $result.message = $_.Exception.Message
}
$result | ConvertTo-Json -Compress | Set-Content -Path $Out -Encoding UTF8
"""


def _no_window() -> dict:
    return ({"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
            if sys.platform == "win32" else {})


def _chip(instance_id: str) -> str:
    up = str(instance_id or "").upper()
    for vid, name in KNOWN_VIDS.items():
        if f"VID_{vid}" in up:
            return name
    return "USB"


def parse_devices(text: str) -> list[dict]:
    """Get-PnpDevice's JSON (one object or a list) as plain dicts:
    name, chip, instance_id, has_driver."""
    try:
        data = json.loads(text or "[]")
    except ValueError:
        return []
    if isinstance(data, dict):
        data = [data]
    out = []
    for d in data if isinstance(data, list) else []:
        if not isinstance(d, dict):
            continue
        status = str(d.get("Status") or "")
        cls = str(d.get("Class") or "")
        problem = d.get("Problem")
        ok = (status.upper() == "OK" and cls.lower() == "ports"
              and problem in (None, 0, "CM_PROB_NONE", ""))
        out.append({"name": str(d.get("FriendlyName") or "USB device"),
                    "chip": _chip(d.get("InstanceId")),
                    "instance_id": str(d.get("InstanceId") or ""),
                    "has_driver": ok})
    return out


def find_boards(runner=subprocess.run) -> list[dict]:
    """Every plugged-in board with a known USB chip. [] off Windows or
    when PowerShell cannot answer."""
    if sys.platform != "win32" and runner is subprocess.run:
        return []
    try:
        res = runner(["powershell", "-NoProfile", "-NonInteractive",
                      "-Command", _FIND],
                     capture_output=True, text=True, timeout=20,
                     **_no_window())
    except (OSError, subprocess.SubprocessError) as e:
        log.warning("USB device check failed: %s", e)
        return []
    return parse_devices(getattr(res, "stdout", ""))


def describe(boards: list[dict]) -> tuple[str, bool]:
    """(one line for the Setup tab, whether a driver is missing)."""
    missing = [b for b in boards if not b["has_driver"]]
    if missing:
        b = missing[0]
        return (f"{b['chip']} board plugged in, but Windows has no driver "
                f"for it yet.", True)
    if boards:
        return (f"Driver working: {boards[0]['name']}.", False)
    return ("No hand device plugged in.", False)


def install_from_windows_update(runner=subprocess.run,
                                timeout_s: float = 600.0) -> dict:
    """Ask Windows Update for the board's driver and install it, with
    one administrator prompt. Returns {ok, message}."""
    if sys.platform != "win32" and runner is subprocess.run:
        return {"ok": False, "message": "Only needed on Windows."}
    work = Path(tempfile.mkdtemp(prefix="finger_rehab_driver_"))
    script = work / "get_driver.ps1"
    out = work / "result.json"
    script.write_text(_WU_SCRIPT, encoding="utf-8")
    # The app is not elevated, so a plain PowerShell starts the script
    # with RunAs and waits: Windows shows its prompt, then the script
    # writes what it did.
    def q(path: Path) -> str:
        # Inside a single-quoted PowerShell string, with the path in
        # double quotes for the child's command line.
        return "'\"" + str(path).replace("'", "''") + "\"'"

    launch = ("Start-Process powershell -Verb RunAs -Wait -WindowStyle "
              "Hidden -ArgumentList '-NoProfile','-ExecutionPolicy',"
              f"'Bypass','-File',{q(script)},{q(out)}")
    try:
        runner(["powershell", "-NoProfile", "-NonInteractive",
                "-Command", launch],
               capture_output=True, text=True, timeout=timeout_s,
               **_no_window())
    except (OSError, subprocess.SubprocessError) as e:
        return {"ok": False, "message": f"Could not start: {e}"}
    try:
        data = json.loads(out.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return {"ok": False,
                "message": "No answer: the administrator prompt was "
                           "turned down or Windows Update is off."}
    return {"ok": bool(data.get("ok")),
            "message": str(data.get("message") or "")}


def open_optional_updates() -> bool:
    """Open Windows Update's optional driver page."""
    if sys.platform != "win32":
        return False
    try:
        os.startfile("ms-settings:windowsupdate-optionalupdates")
        return True
    except OSError:
        return False
