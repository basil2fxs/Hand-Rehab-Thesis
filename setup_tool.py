"""Finger Rehab Setup: install the game, and fix the rig when it sulks.

One window, six buttons, a log down the right hand side. It is the
installer on a fresh machine and the repair kit afterwards, which is
deliberate: whoever inherits the rig should have exactly one thing to
open when something is wrong, not a folder of scripts and a README
telling them which to run.

WHAT IT DOES
  Install or repair   copy the game where it belongs, register the
                      auto-start, leave a shortcut
  Auto-start          on or off, no reinstall needed
  Show boards         what the machine can actually see right now
  Flash firmware      put the current firmware back on a Nano
  Sensor address      move a SingleTact off the factory 0x04
  Uninstall           undo all of it, leaving sessions alone

Built with pygame because the game already ships it, so the setup tool
adds no dependency and looks like the thing it installs. Every action
runs on a worker thread with its output streamed into the log, so a
two minute flash never freezes the window.

Run: python setup_tool.py
"""

from __future__ import annotations

import argparse
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pygame

from finger_rehab.config import Config
from finger_rehab.hardware import autostart
from finger_rehab.ui import theme as theme_mod
from finger_rehab.ui.widgets import Button, Layout, draw_text

WIDTH, HEIGHT = 1000, 640
LOG_LINES = 26


def install_root() -> Path:
    """Where the game gets installed.

    Per user, not Program Files or /Applications. The Curtin lab
    machines do not hand out admin rights, and an install that needs
    one is an install that does not happen.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "Finger Rehab"
    if sys.platform == "darwin":
        return Path.home() / "Applications" / "Finger Rehab"
    return Path.home() / ".local" / "share" / "finger-rehab"


def running_from() -> Path:
    """The folder holding this tool and, next to it, the game."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def game_executable(root: Path) -> Path | None:
    """The installed game, whatever it is called on this platform."""
    names = ["Finger Rehab.exe", "Finger Rehab", "main.py"]
    for name in names:
        candidate = root / name
        if candidate.exists():
            return candidate
    app = root / "Finger Rehab.app"
    if app.exists():
        inner = app / "Contents" / "MacOS" / "Finger Rehab"
        return inner if inner.exists() else app
    return None


def game_command(exe: Path, *extra: str) -> list[str]:
    if exe.suffix == ".py":
        return [sys.executable, str(exe), *extra]
    if exe.suffix == ".app":
        return ["open", "-a", str(exe), "--args", *extra]
    return [str(exe), *extra]


class Job(threading.Thread):
    """A background action that writes lines back to the window."""

    def __init__(self, fn, out: "queue.Queue[str]") -> None:
        super().__init__(daemon=True)
        self.fn = fn
        self.out = out
        self.done = False

    def run(self) -> None:
        try:
            self.fn(self.out.put)
        except Exception as exc:
            self.out.put(f"Stopped: {exc}")
        finally:
            self.done = True


# ---------------------------------------------------------------------------
# The actions
# ---------------------------------------------------------------------------

def action_install(say, cfg) -> None:
    src = running_from()
    dst = install_root()
    say(f"Installing into {dst}")
    dst.mkdir(parents=True, exist_ok=True)
    exe = game_executable(src)
    if exe is None:
        say("Cannot find the game next to this tool.")
        say("Keep Setup and the game in the same folder and try again.")
        return
    copied = 0
    for item in src.iterdir():
        if item.name.lower().startswith("finger rehab setup"):
            continue  # do not copy the installer into the install
        target = dst / item.name
        try:
            if item.is_dir():
                shutil.copytree(item, target, dirs_exist_ok=True)
            else:
                shutil.copy2(item, target)
            copied += 1
        except Exception as exc:
            say(f"Could not copy {item.name}: {exc}")
    say(f"Copied {copied} item(s).")
    installed = game_executable(dst)
    if installed is None:
        say("The copy finished but the game is not where expected.")
        return
    say("Turning on auto-start.")
    ok, msg = autostart.register(game_command(installed, "--watch"))
    say(msg)
    if ok:
        say("Plug a board in and the game will open by itself.")
    _make_shortcut(installed, say)
    say("Done. This tool can stay here for repairs.")


def _make_shortcut(exe: Path, say) -> None:
    """A way in that is not the auto-start, for a keyboard-only session."""
    try:
        if sys.platform == "darwin":
            link = Path.home() / "Desktop" / "Finger Rehab"
            if link.exists() or link.is_symlink():
                link.unlink()
            link.symlink_to(exe)
            say("Put a shortcut on the Desktop.")
        elif sys.platform == "win32":
            # A .bat rather than a .lnk: a shortcut file needs COM and
            # pywin32, which is a dependency for one line of polish.
            bat = Path.home() / "Desktop" / "Finger Rehab.bat"
            bat.write_text(f'@start "" "{exe}"\r\n', encoding="utf-8")
            say("Put a shortcut on the Desktop.")
    except Exception as exc:
        say(f"No shortcut: {exc}")


def action_autostart_on(say, cfg) -> None:
    exe = game_executable(install_root()) or game_executable(running_from())
    if exe is None:
        say("Install the game first.")
        return
    ok, msg = autostart.register(game_command(exe, "--watch"))
    say(msg)


def action_autostart_off(say, cfg) -> None:
    ok, msg = autostart.unregister()
    say(msg)


def action_boards(say, cfg) -> None:
    from finger_rehab.hardware.serial_source import (discover_ports,
                                                     list_available_ports)
    say("Serial ports on this machine:")
    ports = list_available_ports()
    if not ports:
        say("  none at all. Check the USB lead and the board's light.")
        return
    for p in ports:
        vid = f"0x{p.vid:04x}" if p.vid is not None else "?"
        say(f"  {p.device}   vid={vid}   {p.description}")
    picked = discover_ports(cfg.get("serial.vendor_ids"))
    if picked:
        say(f"Would use: {', '.join(picked)}")
        say("First is the right hand, second the left.")
    else:
        say("None of these look like an Arduino, so the game would")
        say("fall back to the keyboard.")


def action_flash(say, cfg) -> None:
    from finger_rehab.hardware import flasher
    tool = flasher.find_avrdude(cfg)
    if tool is None:
        say("No avrdude bundled with this build, so no flashing here.")
        return
    image = flasher.find_hex("firmware", cfg)
    if image is None:
        say("No firmware image found in this build.")
        return
    ports = flasher.candidate_ports(cfg)
    if not ports:
        say("No board to flash. Plug one in and try again.")
        return
    port = ports[0][0]
    say(f"Flashing {image.short_label()} to {port}.")
    say("Do not unplug the board.")
    job = flasher.FirmwareJob(tool, port, image, cfg)
    job.start()
    while job.is_alive():
        for line in job.drain() if hasattr(job, "drain") else []:
            say(line)
        time.sleep(0.1)
    for line in job.drain() if hasattr(job, "drain") else []:
        say(line)
    say(getattr(job, "summary", "Finished."))


def action_address(say, cfg) -> None:
    say("Sensor address change.")
    say("Connect ONE sensor only, then run this.")
    say("Every SingleTact answers 0x04 as well as its own address, so")
    say("a change with several wired up would move all of them.")
    say("")
    say("Use the game's Settings screen for the full flow: it asks")
    say("which address to move from and to, and puts the game")
    say("firmware back afterwards.")


def action_uninstall(say, cfg) -> None:
    ok, msg = autostart.unregister()
    say(msg)
    dst = install_root()
    if dst.exists():
        try:
            shutil.rmtree(dst)
            say(f"Removed {dst}")
        except Exception as exc:
            say(f"Could not remove {dst}: {exc}")
    for name in ("Finger Rehab", "Finger Rehab.bat"):
        link = Path.home() / "Desktop" / name
        try:
            if link.exists() or link.is_symlink():
                link.unlink()
        except OSError:
            pass
    say("Sessions and calibration were left alone.")


ACTIONS = [
    ("Install or repair", action_install, True),
    ("Auto-start ON", action_autostart_on, False),
    ("Auto-start OFF", action_autostart_off, False),
    ("Show boards", action_boards, False),
    ("Flash firmware", action_flash, False),
    ("Sensor address", action_address, False),
    ("Uninstall", action_uninstall, False),
]


def run_headless(name: str) -> int:
    """Same actions without a window, for a locked-down machine.

    A lab computer that refuses to open a graphical window should still
    be repairable over a remote session.
    """
    cfg = Config.load()
    wanted = name.replace("-", " ").lower()
    for label, fn, _ in ACTIONS:
        if label.lower().startswith(wanted):
            fn(lambda line: print(line), cfg)
            return 0
    print("Actions: " + ", ".join(a[0] for a in ACTIONS))
    return 2


def main() -> int:
    ap = argparse.ArgumentParser(description="Finger Rehab setup")
    ap.add_argument("--do", default=None,
                    help="Run one action with no window, e.g. --do install")
    args = ap.parse_args()
    if args.do:
        return run_headless(args.do)

    cfg = Config.load()
    pygame.init()
    pygame.display.set_caption("Finger Rehab Setup")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    layout = Layout(WIDTH, HEIGHT)
    th = theme_mod.get(cfg.get("ui.theme", "light"))
    clock = pygame.time.Clock()

    lines: list[str] = []
    out: "queue.Queue[str]" = queue.Queue()
    job: Job | None = None

    st = autostart.status()
    lines.append("Finger Rehab setup and diagnostics.")
    lines.append(f"Auto-start is {'on' if st['registered'] else 'off'}.")
    lines.append("")

    def start(fn):
        nonlocal job
        if job is not None and not job.done:
            out.put("Still working, one moment.")
            return
        job = Job(lambda say: fn(say, cfg), out)
        job.start()

    buttons: list[Button] = []
    y = 90
    for label, fn, primary in ACTIONS:
        rect = pygame.Rect(40, y, 300, 56)
        buttons.append(Button(rect, label, (lambda f=fn: start(f)),
                              th, layout, primary=primary))
        y += 68

    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE:
                running = False
            for b in buttons:
                b.handle_event(e)
        while not out.empty():
            lines.append(out.get())
        del lines[:-200]

        screen.fill(th.background)
        draw_text(screen, "Finger Rehab Setup", (40, 34), th, layout, pt=30)
        for b in buttons:
            b.draw(screen)
        panel = pygame.Rect(370, 84, WIDTH - 410, HEIGHT - 130)
        pygame.draw.rect(screen, th.panel if hasattr(th, "panel")
                         else th.background, panel, border_radius=10)
        pygame.draw.rect(screen, th.accent, panel, width=1, border_radius=10)
        for i, line in enumerate(lines[-LOG_LINES:]):
            draw_text(screen, line[:78], (panel.x + 14, panel.y + 12 + i * 21),
                      th, layout, pt=15)
        draw_text(screen, "Esc to close", (40, HEIGHT - 34), th, layout, pt=14)
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
