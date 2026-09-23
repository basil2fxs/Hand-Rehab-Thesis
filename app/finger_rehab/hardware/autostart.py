"""Start the game by itself when a board is plugged in.

A therapist should be able to plug the rig into a clinic laptop and
have the game come up: no icon to hunt for, no port to choose. This
module is the piece that does that. The operating system starts a
small watcher when the user logs in, the watcher looks for an
Arduino-family board once a second, and the moment one appears it
launches the game.

WHY POLLING RATHER THAN AN OPERATING SYSTEM HOOK. Windows can fire a
scheduled task from a device-arrival event, but the event log that
carries it is switched off by default and the task then fires for
every device on the machine, mouse included. macOS launchd has no USB
trigger at all. Listing the serial ports takes well under two
milliseconds on this hardware and answers the only question that
matters, so the same code runs on both platforms and there is one
behaviour to explain to whoever inherits this.

WHAT IT DELIBERATELY WILL NOT DO.
  - Open a second copy. The running game holds a lock file and the
    watcher checks it first.
  - React to a board being unplugged and put back mid-session, for the
    same reason: the game is still running, so there is nothing to do.
  - Reopen the game after the user closes it with the board still
    plugged in. It acts on the CHANGE from no board to board, not on
    the board being present, otherwise closing the game would become
    impossible.

Registration is per user on both platforms: a scheduled task on
Windows, a LaunchAgent on macOS. Neither needs an administrator, which
matters because the Curtin lab machines do not hand out admin rights.
"""

from __future__ import annotations

import logging
import os
import plistlib
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

# Windows: hide the console window a subprocess would otherwise flash
# up. Harmless to define everywhere; only passed on Windows.
_CREATE_NO_WINDOW = 0x08000000
_DETACHED_PROCESS = 0x00000008

TASK_NAME = "FingerRehabAutostart"
AGENT_LABEL = "com.fingerrehab.autostart"
DEFAULT_POLL_S = 1.0


def user_root() -> Path:
    """Where the lock and the watcher's own files live.

    The same folder the game already falls back to when it cannot
    write beside itself, so a locked-down Program Files install and a
    portable copy behave the same.
    """
    if sys.platform == "win32":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return Path(base) / "Finger Rehab"
    return Path.home() / "Finger Rehab Data"


def run_lock_path() -> Path:
    return user_root() / "game.lock"


# ---------------------------------------------------------------------------
# Is the game already up?
#
# An advisory file lock rather than a pid file. A pid file left behind
# by a crash reads as "still running" forever and the auto-start
# quietly stops working, which is the worst kind of fault: silent. A
# lock is released by the operating system when the process dies,
# however it dies.
# ---------------------------------------------------------------------------

class RunLock:
    """Held by the game for as long as it runs."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path) if path else run_lock_path()
        self._fh = None

    def acquire(self) -> bool:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            fh = open(self.path, "a+b")
        except OSError:
            # No writable spot means no lock, and no lock means the
            # watcher may double-launch. Better to say so than to
            # pretend the lock was taken.
            log.warning("cannot open the run lock at %s", self.path)
            return False
        try:
            if sys.platform == "win32":
                import msvcrt
                msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            fh.close()
            return False
        self._fh = fh
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            if sys.platform == "win32":
                import msvcrt
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        except OSError:
            pass
        try:
            self._fh.close()
        finally:
            self._fh = None

    def __enter__(self) -> "RunLock":
        self.acquired = self.acquire()
        return self

    def __exit__(self, *exc) -> None:
        self.release()


def game_is_running(lock_path: Path | None = None) -> bool:
    """True when something already holds the run lock."""
    probe = RunLock(lock_path)
    if probe.acquire():
        probe.release()
        return False
    return True


# ---------------------------------------------------------------------------
# The watcher
# ---------------------------------------------------------------------------

@dataclass
class WatchResult:
    """What one pass of the loop decided, so tests can read it."""
    boards: int = 0
    launched: bool = False
    skipped_running: bool = False


def _default_ports(vendor_ids=None) -> list[str]:
    from .serial_source import discover_ports
    return discover_ports(vendor_ids)


def launch_game(game_cmd: list[str]) -> bool:
    """Start the game detached, with no console window."""
    kwargs: dict = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = _CREATE_NO_WINDOW | _DETACHED_PROCESS
    else:
        kwargs["start_new_session"] = True
    try:
        subprocess.Popen(game_cmd, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, **kwargs)
        log.info("launched the game: %s", " ".join(game_cmd))
        return True
    except Exception:
        log.exception("could not launch %s", game_cmd)
        return False


def watch(game_cmd: list[str], poll_s: float = DEFAULT_POLL_S,
          vendor_ids=None, ports_fn=None, launcher=None,
          lock_path: Path | None = None, iterations: int | None = None,
          sleep_fn=time.sleep) -> WatchResult:
    """Poll for a board and launch the game when one arrives.

    Runs forever unless `iterations` is given, which is how the tests
    drive it. `ports_fn` and `launcher` are injectable for the same
    reason: nothing here needs real hardware to be exercised.
    """
    ports_fn = ports_fn or (lambda: _default_ports(vendor_ids))
    launcher = launcher or launch_game
    poll_s = max(0.1, float(poll_s or DEFAULT_POLL_S))
    result = WatchResult()
    # Start from whatever is already plugged in, so logging in with the
    # board attached does not immediately open the game. The point is
    # to react to someone plugging it in.
    try:
        had_board = bool(ports_fn())
    except Exception:
        had_board = False
    n = 0
    while iterations is None or n < iterations:
        n += 1
        try:
            ports = ports_fn() or []
        except Exception:
            # A USB hiccup must not kill the watcher: it is meant to
            # sit there for the whole working day.
            log.debug("port scan failed", exc_info=True)
            ports = []
        result.boards = len(ports)
        arrived = bool(ports) and not had_board
        had_board = bool(ports)
        if arrived:
            if game_is_running(lock_path):
                result.skipped_running = True
                log.info("board arrived, game already running")
            elif launcher(game_cmd):
                result.launched = True
        if iterations is None or n < iterations:
            sleep_fn(poll_s)
    return result


# ---------------------------------------------------------------------------
# Registering with the operating system
# ---------------------------------------------------------------------------

def agent_plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{AGENT_LABEL}.plist"


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    kwargs: dict = {}
    if sys.platform == "win32":
        # The game is built without a console, so every schtasks call
        # would otherwise flash a black window over the Settings screen.
        kwargs["creationflags"] = _CREATE_NO_WINDOW
    return subprocess.run(cmd, capture_output=True, text=True, **kwargs)


def watcher_command(main_path: str | Path | None = None,
                    frozen: bool | None = None) -> list[str]:
    """The command the operating system should run at login.

    The watcher is this same executable with --watch, so a frozen copy
    registers itself and a source checkout registers the interpreter
    plus main.py. One rule, used by the launch-time sync, the two
    command line flags and the Settings switch, so they can never
    register three different things.
    """
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if frozen:
        return [sys.executable, "--watch"]
    main_py = Path(main_path) if main_path else \
        Path(__file__).resolve().parents[2] / "main.py"
    return [sys.executable, str(main_py), "--watch"]


def unsafe_location(exe: str | Path) -> str | None:
    """Why this executable must not be registered, or None.

    launchd runs exactly the path it was given, so an agent that points
    into a mounted disk image or into App Translocation's random
    folder breaks the moment the image is ejected or the app is next
    opened. Both happen on the first launch after a download, which is
    exactly when the first-launch registration would run.
    """
    text = str(exe)
    if sys.platform == "darwin":
        if text.startswith("/Volumes/") or "/AppTranslocation/" in text:
            return "Drag Finger Rehab into Applications to turn on auto-start."
    return None


def register(watcher_cmd: list[str], poll_s: float = DEFAULT_POLL_S,
             runner=_run) -> tuple[bool, str]:
    """Ask the operating system to start the watcher at login.

    Returns (ok, message). The message is written for the person at
    the machine, not for a log file.
    """
    if sys.platform == "win32":
        # /SC ONLOGON with no /RU runs as the logged-in user, which is
        # what keeps this free of an admin prompt. /F overwrites a
        # previous registration rather than failing.
        quoted = " ".join(f'"{c}"' if " " in c else c for c in watcher_cmd)
        proc = runner(["schtasks", "/Create", "/TN", TASK_NAME,
                       "/TR", quoted, "/SC", "ONLOGON", "/F"])
        if proc.returncode == 0:
            return True, "The game will start when a board is plugged in."
        return False, (proc.stderr or proc.stdout or "").strip() or \
            "Windows refused to create the scheduled task."
    if sys.platform == "darwin":
        plist = {
            "Label": AGENT_LABEL,
            "ProgramArguments": list(watcher_cmd),
            "RunAtLoad": True,
            # Restart the watcher if it ever exits, so one bad day does
            # not silently turn the feature off until the next reboot.
            "KeepAlive": True,
            "ProcessType": "Background",
        }
        path = agent_plist_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(plistlib.dumps(plist))
        # bootout first: loading over a live agent is an error, and a
        # stale one would keep running the old command.
        runner(["launchctl", "bootout", f"gui/{os.getuid()}/{AGENT_LABEL}"])
        proc = runner(["launchctl", "bootstrap", f"gui/{os.getuid()}",
                       str(path)])
        if proc.returncode == 0:
            return True, "The game will start when a board is plugged in."
        return False, (proc.stderr or proc.stdout or "").strip() or \
            "macOS refused to load the login item."
    return False, f"Auto-start is not supported on {sys.platform}."


def unregister(runner=_run) -> tuple[bool, str]:
    """Undo register(). Safe to call when nothing is registered."""
    if sys.platform == "win32":
        proc = runner(["schtasks", "/Delete", "/TN", TASK_NAME, "/F"])
        if proc.returncode == 0:
            return True, "Auto-start turned off."
        return False, (proc.stderr or proc.stdout or "").strip() or \
            "Could not remove the scheduled task."
    if sys.platform == "darwin":
        runner(["launchctl", "bootout", f"gui/{os.getuid()}/{AGENT_LABEL}"])
        path = agent_plist_path()
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            return False, str(exc)
        return True, "Auto-start turned off."
    return False, f"Auto-start is not supported on {sys.platform}."


def is_registered(runner=_run) -> bool:
    if sys.platform == "win32":
        proc = runner(["schtasks", "/Query", "/TN", TASK_NAME])
        return proc.returncode == 0
    if sys.platform == "darwin":
        return agent_plist_path().exists()
    return False


def status(runner=_run) -> dict:
    """One dict the Settings screen reads."""
    return {
        "supported": sys.platform in ("win32", "darwin"),
        "registered": is_registered(runner),
        "game_running": game_is_running(),
        "lock": str(run_lock_path()),
        "where": (TASK_NAME if sys.platform == "win32"
                  else str(agent_plist_path())),
    }


# ---------------------------------------------------------------------------
# Keeping the registration pointed at the app that is actually installed
# ---------------------------------------------------------------------------

def first_launch_marker() -> Path:
    """Touched once the installed game has registered itself.

    A file rather than a config key: user_settings.yaml is the file that
    decides how the device behaves in a session, and the tests guard it
    for that reason. Whether the first launch has happened is not a
    setting, so it does not belong in there.
    """
    return user_root() / "autostart.first_launch"


def _normalise(cmd: list[str]) -> list[str]:
    """Strip quotes and case so a moved path compares as moved and an
    unchanged one as unchanged, whichever way schtasks quoted it."""
    out = []
    for c in cmd:
        c = c.strip().strip('"')
        if c:
            out.append(c.lower() if sys.platform == "win32" else c)
    return out


def registered_command(runner=_run) -> list[str] | None:
    """What the operating system will run at login, or None.

    Windows keeps it in the task's XML as a Command element plus an
    Arguments element; macOS keeps it as ProgramArguments in the plist.
    An empty list means registered but unreadable, which the sync treats
    as "re-register to be sure".
    """
    if sys.platform == "win32":
        proc = runner(["schtasks", "/Query", "/TN", TASK_NAME, "/XML"])
        if proc.returncode != 0:
            return None
        import re
        text = proc.stdout or ""
        cmd = re.search(r"<Command>(.*?)</Command>", text, re.S)
        args = re.search(r"<Arguments>(.*?)</Arguments>", text, re.S)
        if not cmd:
            return []
        import html
        # schtasks keeps the quotes register() put round a path with a
        # space in it; the caller wants the path.
        parts = [html.unescape(cmd.group(1)).strip().strip('"')]
        if args:
            parts += html.unescape(args.group(1)).split()
        return parts
    if sys.platform == "darwin":
        path = agent_plist_path()
        if not path.exists():
            return None
        try:
            data = plistlib.loads(path.read_bytes())
            return [str(x) for x in data.get("ProgramArguments", [])]
        except Exception:
            return []
    return None


def sync(watcher_cmd: list[str], *, frozen: bool | None = None,
         poll_s: float = DEFAULT_POLL_S, runner=_run,
         marker: Path | None = None) -> tuple[str, str]:
    """Run once per normal launch. Returns (what happened, one line).

    The rules, in order:
      unsafe     the app is running from a disk image or a translocated
                 copy, so nothing is touched and the line says to drag
                 it into Applications
      source     a source checkout never registers itself
      moved      registered, but at a different path: re-register here
      kept       registered here already
      first      the installed copy's first launch: register once and
                 leave a marker so turning it off in Settings sticks
      off        the marker exists and nothing is registered, which is
                 the Settings switch having been turned off

    The message for "first" is the one line the title screen shows.
    """
    if frozen is None:
        frozen = bool(getattr(sys, "frozen", False))
    if sys.platform not in ("win32", "darwin"):
        return "unsupported", ""
    if not frozen:
        return "source", ""
    why = unsafe_location(watcher_cmd[0])
    if why:
        return "unsafe", why
    marker = Path(marker) if marker else first_launch_marker()

    def done_once() -> None:
        # A registration seen or made means the first launch is behind
        # us, whoever did the registering (the installer runs the flag
        # before the game ever opens). Without this, turning auto-start
        # off in Settings would be undone by the next launch.
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.touch()
        except OSError:
            log.warning("could not write the first-launch marker at %s",
                        marker)

    current = registered_command(runner)
    if current is not None:
        done_once()
        if _normalise(current) == _normalise(list(watcher_cmd)):
            return "kept", ""
        ok, msg = register(list(watcher_cmd), poll_s, runner)
        return ("moved", "") if ok else ("failed", msg)
    if marker.exists():
        return "off", ""
    ok, msg = register(list(watcher_cmd), poll_s, runner)
    if not ok:
        # No marker, so a refused schtasks call is tried again next
        # launch rather than silently given up on forever.
        return "failed", msg
    done_once()
    return "first", ("Auto-start is on: plug a board in and the game "
                     "opens. Settings turns it off.")
